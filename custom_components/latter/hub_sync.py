"""System-level feed listeners, bedtime schedule evaluation, HMAC rotation, and global config broadcast (`L3`)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import secrets
import time
from typing import Any

from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CALENDAR_REFRESH_INTERVAL_MINUTES,
    CONF_CALENDAR_ENTITIES,
    CONF_SYSTEM_CONFIG_REV,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DATA_HMAC_SECRET,
    DOMAIN,
    FORECAST_REFRESH_INTERVAL_MINUTES,
)
from .feeds import (
    async_fetch_raw_calendar_events,
    async_fetch_weather_snapshot,
    read_sun_and_moon_fields,
)
from .http.signing import UrlSigner
from .hub_registry import (
    LatterSystemHub,
    get_system_config_lock,
    get_system_config_rev,
    iter_coordinators,
    register_hub_hooks,
)
from .protocol_codec import V3Records

_SKY_TRACKED_ENTITIES: tuple[str, ...] = ("sun.sun", "sensor.moon_phase", "sensor.moon")
_HMAC_SECRET_BYTES = 32
_HOURS_PER_DAY = 24
_DEFAULT_BEDTIME_START_HOUR = 22
_DEFAULT_BEDTIME_END_HOUR = 7
_BEDTIME_CHECK_INTERVAL_SECONDS = 60
_DEFAULT_CALENDAR_DAYS = 30
_COALESCE_WINDOW_SECONDS = 0.5


def _safe_hour(val: Any, default: int) -> int:
    """Coerce a schedule hour preference into `0..23` without raising on corrupted input."""
    if isinstance(val, bool) or val is None:
        return default
    try:
        return int(val) % _HOURS_PER_DAY
    except (TypeError, ValueError):
        return default


def _live_global_config(sys_obj: LatterSystemHub) -> dict[str, Any]:
    """Return the live System-Wide configuration dict."""
    domain_data = sys_obj.hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
    if isinstance(global_cfg, dict):
        sys_obj.config = global_cfg
    return sys_obj.config


def _hub_weather_entity(sys_obj: LatterSystemHub) -> str | None:
    """Return the configured System-Wide weather entity_id."""
    val = _live_global_config(sys_obj).get(CONF_WEATHER_ENTITY)
    return str(val).strip() if val and str(val).strip() else None


def _hub_calendar_entities(sys_obj: LatterSystemHub) -> list[str]:
    """Return the configured System-Wide calendar entity_ids."""
    val = _live_global_config(sys_obj).get(CONF_CALENDAR_ENTITIES, [])
    return (
        [str(x).strip() for x in val if str(x or "").strip()]
        if isinstance(val, (list, tuple))
        else []
    )


def _is_hour_in_bedtime_window(hour: int, start_h: int, end_h: int) -> bool:
    """Return True when `hour` (0..23) falls inside `[start_h, end_h)`."""
    if start_h == end_h:
        return False
    if start_h < end_h:
        return start_h <= hour < end_h
    return hour >= start_h or hour < end_h


_HUB_SYNC_STATE_ATTR = "_hub_sync_state"


class _HubFeedRuntime:
    """Internal listener, timer, and background-task state attached to one `LatterSystemHub`."""

    def __init__(self) -> None:
        self.unsub_weather_state: Callable[[], None] | None = None
        self.unsub_sky_state: Callable[[], None] | None = None
        self.unsub_forecast_timer: Callable[[], None] | None = None
        self.unsub_calendar_timer: Callable[[], None] | None = None
        self.unsub_bedtime_timer: Callable[[], None] | None = None
        self.unsub_core_config: Callable[[], None] | None = None
        self.bedtime_sched_trackers: dict[str, tuple[bool, int, int, bool]] = {}
        self.tracked_weather_entity: str | None = None
        self.weather_last_fetch_mono: float = 0.0
        self.calendar_last_fetch_mono: float = 0.0
        self.background_tasks: set[asyncio.Task[Any]] = set()


def _get_feed_runtime(sys_obj: LatterSystemHub) -> _HubFeedRuntime:
    """Return or initialize the feed runtime state on `sys_obj`."""
    rt = getattr(sys_obj, _HUB_SYNC_STATE_ATTR, None)
    if not isinstance(rt, _HubFeedRuntime):
        rt = _HubFeedRuntime()
        setattr(sys_obj, _HUB_SYNC_STATE_ATTR, rt)
    if getattr(sys_obj, "url_signer", None) is None:
        sys_obj.url_signer = UrlSigner(sys_obj.hass, "system", sys_obj.hmac_secret)
    return rt


@callback
def _spawn_hub_task(sys_obj: LatterSystemHub, coro: Any, name: str) -> None:
    """Schedule a tracked background task on `sys_obj` that is cancelled on feed cleanup."""
    rt = _get_feed_runtime(sys_obj)
    task = sys_obj.hass.async_create_task(coro, name)
    rt.background_tasks.add(task)
    task.add_done_callback(rt.background_tasks.discard)


async def async_rotate_hub_hmac_secret(sys_obj: LatterSystemHub) -> None:
    """Mint a fresh 256-bit HMAC signing secret, persist it, and republish all signed URLs."""
    _get_feed_runtime(sys_obj)
    new_hex = secrets.token_hex(_HMAC_SECRET_BYTES)
    new_secret = bytes.fromhex(new_hex)
    async with get_system_config_lock(sys_obj.hass):
        sys_obj.hmac_secret = new_secret
        signer = UrlSigner(sys_obj.hass, "system", new_secret)
        sys_obj.url_signer = signer
        await signer.async_prime_lan_base_url()
        domain_data = sys_obj.hass.data.setdefault(DOMAIN, {})
        domain_data[DATA_HMAC_SECRET] = new_secret
        global_cfg = _live_global_config(sys_obj)
        global_cfg["hmac_secret_hex"] = new_hex
        await sys_obj.store.async_save(global_cfg)
    for coord in list(sys_obj.coordinators.values()):
        coord.update_hmac_secret(new_secret)
        coord.force_republish_all_domains()


def _seed_bedtime_schedule_trackers(
    sys_obj: LatterSystemHub, rt: _HubFeedRuntime
) -> None:
    """Seed initial schedule state per coordinator without clobbering manual overrides on restart."""
    cur_hour = int(dt_util.now().hour) % _HOURS_PER_DAY
    for coord in list(sys_obj.coordinators.values()):
        if coord.is_ble_tag or not coord.has_display:
            continue
        if coord.subentry_id in rt.bedtime_sched_trackers:
            continue
        sched_on = bool(coord.get_device_pref("bedtime_schedule"))
        start_h = _safe_hour(
            coord.get_device_pref("bedtime_start_hour"), _DEFAULT_BEDTIME_START_HOUR
        )
        end_h = _safe_hour(
            coord.get_device_pref("bedtime_end_hour"), _DEFAULT_BEDTIME_END_HOUR
        )
        in_win = _is_hour_in_bedtime_window(cur_hour, start_h, end_h)
        rt.bedtime_sched_trackers[coord.subentry_id] = (
            sched_on,
            start_h,
            end_h,
            in_win,
        )


@callback
def bind_hub_feed_listeners(sys_obj: LatterSystemHub) -> None:
    """Bind or rebind System-level weather, sun/moon, and periodic feed listeners."""
    rt = _get_feed_runtime(sys_obj)

    @callback
    def _on_core_config_updated(_event: Event[Any]) -> None:
        if sys_obj.url_signer is not None:
            sys_obj.url_signer.invalidate_lan_base_url()
        for coord in list(sys_obj.coordinators.values()):
            coord.url_signer.invalidate_lan_base_url()

    @callback
    def _on_weather_state_change(_event: Event[EventStateChangedData]) -> None:
        _spawn_hub_task(
            sys_obj,
            async_refresh_hub_weather(sys_obj),
            "latter_system_weather_refresh",
        )

    @callback
    def _on_sky_state_change(_event: Event[EventStateChangedData]) -> None:
        if sys_obj.weather_snapshot is not None:
            recs, fields = sys_obj.weather_snapshot
            merged = {**fields, **read_sun_and_moon_fields(sys_obj.hass)}
            if merged == fields:
                return
            sys_obj.weather_snapshot = (recs, merged)
            weather_ent = _hub_weather_entity(sys_obj)
            for coord in list(sys_obj.coordinators.values()):
                if not coord.is_ble_tag:
                    coord.apply_weather_snapshot(weather_ent, sys_obj.weather_snapshot)
            return
        _spawn_hub_task(
            sys_obj,
            async_refresh_hub_weather(sys_obj, coalesce=True),
            "latter_system_sky_refresh",
        )

    async def _periodic_weather(_now: datetime) -> None:
        await async_refresh_hub_weather(sys_obj)

    async def _periodic_calendar(_now: datetime) -> None:
        await async_refresh_hub_calendar(sys_obj)

    async def _periodic_bedtime(now: datetime) -> None:
        await async_evaluate_hub_bedtime_schedules(sys_obj, now=now)

    if rt.unsub_core_config is None:
        rt.unsub_core_config = sys_obj.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, _on_core_config_updated
        )
    weather_ent = _hub_weather_entity(sys_obj)
    if weather_ent != rt.tracked_weather_entity or (
        weather_ent and rt.unsub_weather_state is None
    ):
        if rt.unsub_weather_state is not None:
            rt.unsub_weather_state()
            rt.unsub_weather_state = None
        rt.tracked_weather_entity = weather_ent
        if weather_ent:
            rt.unsub_weather_state = async_track_state_change_event(
                sys_obj.hass, [weather_ent], _on_weather_state_change
            )
    if rt.unsub_sky_state is None:
        rt.unsub_sky_state = async_track_state_change_event(
            sys_obj.hass, list(_SKY_TRACKED_ENTITIES), _on_sky_state_change
        )
    if rt.unsub_forecast_timer is None:
        rt.unsub_forecast_timer = async_track_time_interval(
            sys_obj.hass,
            _periodic_weather,
            timedelta(minutes=FORECAST_REFRESH_INTERVAL_MINUTES),
        )
    if rt.unsub_calendar_timer is None:
        rt.unsub_calendar_timer = async_track_time_interval(
            sys_obj.hass,
            _periodic_calendar,
            timedelta(minutes=CALENDAR_REFRESH_INTERVAL_MINUTES),
        )
    if rt.unsub_bedtime_timer is None:
        rt.unsub_bedtime_timer = async_track_time_interval(
            sys_obj.hass,
            _periodic_bedtime,
            timedelta(seconds=_BEDTIME_CHECK_INTERVAL_SECONDS),
        )
        _seed_bedtime_schedule_trackers(sys_obj, rt)


@callback
def async_cleanup_hub_feeds(sys_obj: LatterSystemHub) -> None:
    """Unsubscribe System-level weather/calendar listeners and cancel tracked tasks on unload."""
    rt = _get_feed_runtime(sys_obj)
    for task in list(rt.background_tasks):
        if not task.done():
            task.cancel()
    rt.background_tasks.clear()
    for unsub in (
        rt.unsub_weather_state,
        rt.unsub_sky_state,
        rt.unsub_forecast_timer,
        rt.unsub_calendar_timer,
        rt.unsub_bedtime_timer,
        rt.unsub_core_config,
    ):
        if unsub is not None:
            unsub()
    rt.unsub_weather_state = None
    rt.unsub_sky_state = None
    rt.unsub_forecast_timer = None
    rt.unsub_calendar_timer = None
    rt.unsub_bedtime_timer = None
    rt.unsub_core_config = None
    rt.bedtime_sched_trackers.clear()
    rt.tracked_weather_entity = None
    sys_obj.weather_loaded = False
    sys_obj.calendar_loaded = False


async def async_evaluate_hub_bedtime_schedules(
    sys_obj: LatterSystemHub, *, now: datetime | None = None
) -> None:
    """Apply Bedtime Mode schedule boundary transitions while preserving mid-window manual overrides."""
    rt = _get_feed_runtime(sys_obj)
    local_dt = dt_util.as_local(now) if now is not None else dt_util.now()
    cur_hour = int(local_dt.hour) % _HOURS_PER_DAY
    live_ids: set[str] = set()
    for coord in list(sys_obj.coordinators.values()):
        if coord.is_ble_tag or not coord.has_display:
            continue
        sub_id = coord.subentry_id
        live_ids.add(sub_id)
        sched_on = bool(coord.get_device_pref("bedtime_schedule"))
        start_h = _safe_hour(
            coord.get_device_pref("bedtime_start_hour"), _DEFAULT_BEDTIME_START_HOUR
        )
        end_h = _safe_hour(
            coord.get_device_pref("bedtime_end_hour"), _DEFAULT_BEDTIME_END_HOUR
        )
        in_win = _is_hour_in_bedtime_window(cur_hour, start_h, end_h)
        prev = rt.bedtime_sched_trackers.get(sub_id)
        rt.bedtime_sched_trackers[sub_id] = (sched_on, start_h, end_h, in_win)
        if not sched_on or prev is None:
            continue
        prev_sched_on, prev_start_h, prev_end_h, prev_in_win = prev
        schedule_config_changed = (
            not prev_sched_on or prev_start_h != start_h or prev_end_h != end_h
        )
        window_edge_crossed = prev_in_win != in_win
        if (schedule_config_changed or window_edge_crossed) and (
            bool(coord.get_device_pref("bedtime_active")) != in_win
        ):
            await coord.async_update_device_prefs({"bedtime_active": in_win})
    for stale_id in set(rt.bedtime_sched_trackers) - live_ids:
        rt.bedtime_sched_trackers.pop(stale_id, None)


async def async_refresh_hub_weather(
    sys_obj: LatterSystemHub, *, coalesce: bool = False
) -> None:
    """Fetch the daily forecast once for the Site and fan out to all display coordinators."""
    rt = _get_feed_runtime(sys_obj)
    bind_hub_feed_listeners(sys_obj)
    now_m = time.monotonic()
    weather_ent = _hub_weather_entity(sys_obj)
    if (
        coalesce
        and sys_obj.weather_loaded
        and (now_m - rt.weather_last_fetch_mono) < _COALESCE_WINDOW_SECONDS
    ):
        return
    rt.weather_last_fetch_mono = now_m
    snap = await async_fetch_weather_snapshot(sys_obj.hass, weather_ent)
    if snap is None:
        sky_only = (
            V3Records(),
            {
                "condition": "",
                "temperature": None,
                "humidity": None,
                "wind_speed": None,
                "wind_bearing": None,
                "high": None,
                "low": None,
                **read_sun_and_moon_fields(sys_obj.hass),
            },
        )
        sys_obj.weather_snapshot = sky_only
        sys_obj.weather_loaded = True
        for coord in list(sys_obj.coordinators.values()):
            if not coord.is_ble_tag:
                coord.apply_weather_snapshot(None, sky_only)
        return

    sys_obj.weather_snapshot = snap
    sys_obj.weather_loaded = True
    for coord in list(sys_obj.coordinators.values()):
        if not coord.is_ble_tag:
            coord.apply_weather_snapshot(weather_ent, snap)


async def async_refresh_hub_calendar(
    sys_obj: LatterSystemHub,
    days: int = _DEFAULT_CALENDAR_DAYS,
    *,
    coalesce: bool = False,
) -> tuple[V3Records, list[dict[str, Any]]]:
    """Fetch and deduplicate upcoming calendar events once for the Site and fan out to all display coordinators."""
    rt = _get_feed_runtime(sys_obj)
    bind_hub_feed_listeners(sys_obj)
    now_m = time.monotonic()
    if (
        coalesce
        and days == _DEFAULT_CALENDAR_DAYS
        and (now_m - rt.calendar_last_fetch_mono) < _COALESCE_WINDOW_SECONDS
    ):
        return sys_obj.calendar_records, sys_obj.calendar_raw_rows
    prev_mono = rt.calendar_last_fetch_mono
    if days == _DEFAULT_CALENDAR_DAYS:
        rt.calendar_last_fetch_mono = now_m
    try:
        records, raw_rows = await async_fetch_raw_calendar_events(
            sys_obj.hass,
            _hub_calendar_entities(sys_obj),
            days=days,
        )
    except Exception:
        if days == _DEFAULT_CALENDAR_DAYS:
            rt.calendar_last_fetch_mono = prev_mono
        raise
    if days == _DEFAULT_CALENDAR_DAYS:
        sys_obj.calendar_records = records
        sys_obj.calendar_raw_rows = raw_rows
        sys_obj.calendar_loaded = True
        for coord in list(sys_obj.coordinators.values()):
            if not coord.is_ble_tag:
                coord.apply_calendar_snapshot(records, raw_rows)
    return records, raw_rows


def _register_default_hub_hooks() -> None:
    """Register `L3` `UrlSigner` and feed/schedule hooks onto `L1a` `hub_registry`."""

    async def _eval_bedtime(sys_obj: LatterSystemHub, now: datetime | None) -> None:
        await async_evaluate_hub_bedtime_schedules(sys_obj, now=now)

    async def _refresh_weather(sys_obj: LatterSystemHub, coalesce: bool) -> None:
        await async_refresh_hub_weather(sys_obj, coalesce=coalesce)

    async def _refresh_calendar(
        sys_obj: LatterSystemHub, days: int, coalesce: bool
    ) -> tuple[V3Records, list[dict[str, Any]]]:
        return await async_refresh_hub_calendar(sys_obj, days=days, coalesce=coalesce)

    register_hub_hooks(
        url_signer_factory=UrlSigner,
        bind_feeds=bind_hub_feed_listeners,
        cleanup_feeds=async_cleanup_hub_feeds,
        evaluate_bedtime=_eval_bedtime,
        refresh_weather=_refresh_weather,
        refresh_calendar=_refresh_calendar,
    )


_register_default_hub_hooks()


def attach_hub_sync_methods(sys_obj: LatterSystemHub) -> LatterSystemHub:
    """Ensure `L3` `hub_sync` hooks and runtime state are initialized on `sys_obj`."""
    _register_default_hub_hooks()
    _get_feed_runtime(sys_obj)
    return sys_obj


async def async_save_and_broadcast_global_config(
    hass: HomeAssistant, updates: dict[str, Any]
) -> dict[str, Any]:
    """Persist updates to `.storage/latter.site` and broadcast to all loaded device coordinators."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
    if not updates:
        return global_cfg
    changed_keys = {k for k, v in updates.items() if global_cfg.get(k) != v}
    global_cfg.update(updates)
    if changed_keys:
        cur_rev = get_system_config_rev(hass)
        global_cfg[CONF_SYSTEM_CONFIG_REV] = cur_rev + 1
    store = domain_data.get(DATA_GLOBAL_STORE)
    if store is not None:
        await store.async_save(global_cfg)
    for coord in iter_coordinators(hass):
        await coord.async_on_global_config_updated(changed_keys or set(updates.keys()))
    return global_cfg
