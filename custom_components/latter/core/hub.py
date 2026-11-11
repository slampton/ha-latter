"""System-level singleton (`LatterSystemHub`) holding shared site settings, HMAC secret, and active device coordinators."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import secrets
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

from ..areas.calendar import (
    async_fetch_raw_calendar_events,
    async_fetch_weather_snapshot,
    read_sun_and_moon_fields,
)
from ..const import (
    CALENDAR_REFRESH_INTERVAL_MINUTES,
    CONF_CALENDAR_ENTITIES,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DATA_HMAC_SECRET,
    DOMAIN,
    FORECAST_REFRESH_INTERVAL_MINUTES,
    INTEGRATION_VERSION,
)
from ..http.url_signer import UrlSigner
from .payloads import V3Records

if TYPE_CHECKING:
    from ..areas.state_index import AreaStateIndex
    from .device_coordinator import LatterCoordinator

DATA_SYSTEM = "system"
_SKY_TRACKED_ENTITIES: tuple[str, ...] = ("sun.sun", "sensor.moon_phase", "sensor.moon")


class LatterSystemHub:
    """Represents the shared Latter System state across all configured devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[dict[str, Any]],
        config: dict[str, Any],
        hmac_secret: bytes,
    ) -> None:
        """Initialize the shared LatterSystemHub instance."""
        self.hass = hass
        self.store = store
        self.config = config
        self.hmac_secret = hmac_secret
        self.url_signer = UrlSigner(hass, "system", hmac_secret)
        self.coordinators: dict[str, LatterCoordinator] = {}
        self.area_state_index: AreaStateIndex | None = None

        self._unsub_weather_state: Callable[[], None] | None = None
        self._unsub_sky_state: Callable[[], None] | None = None
        self._unsub_forecast_timer: Callable[[], None] | None = None
        self._unsub_calendar_timer: Callable[[], None] | None = None
        self._tracked_weather_entity: str | None = None

        self.weather_snapshot: tuple[V3Records, dict[str, Any]] | None = None
        self.weather_loaded: bool = False
        self._weather_last_fetch_mono: float = 0.0

        self.calendar_records: V3Records = V3Records()
        self.calendar_raw_rows: list[dict[str, Any]] = []
        self.calendar_loaded: bool = False
        self._calendar_last_fetch_mono: float = 0.0

    def _live_global_config(self) -> dict[str, Any]:
        """Return the live System-Wide configuration dict."""
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
        if isinstance(global_cfg, dict):
            self.config = global_cfg
        return self.config

    @property
    def weather_entity(self) -> str | None:
        """Return the configured System-Wide weather entity_id."""
        val = self._live_global_config().get(CONF_WEATHER_ENTITY)
        return str(val).strip() if val and str(val).strip() else None

    @property
    def calendar_entities(self) -> list[str]:
        """Return the configured System-Wide calendar entity_ids."""
        val = self._live_global_config().get(CONF_CALENDAR_ENTITIES, [])
        return (
            [str(x).strip() for x in val if str(x or "").strip()]
            if isinstance(val, (list, tuple))
            else []
        )

    async def async_rotate_hmac_secret(self) -> None:
        """Mint a fresh 256-bit HMAC signing secret, persist it, and republish all signed URLs."""
        new_hex = secrets.token_hex(32)
        new_secret = bytes.fromhex(new_hex)
        self.hmac_secret = new_secret
        self.url_signer = UrlSigner(self.hass, "system", new_secret)
        await self.url_signer.async_prime_lan_base_url()
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        domain_data[DATA_HMAC_SECRET] = new_secret
        global_cfg = self._live_global_config()
        global_cfg["hmac_secret_hex"] = new_hex
        await self.store.async_save(global_cfg)
        for coord in list(self.coordinators.values()):
            coord.update_hmac_secret(new_secret)
            coord.force_republish_all_domains()

    @callback
    def bind_feed_listeners(self) -> None:
        """Bind or rebind the single System-level weather, sun/moon, and periodic feed listeners."""
        weather_ent = self.weather_entity
        if weather_ent != self._tracked_weather_entity or (
            weather_ent and self._unsub_weather_state is None
        ):
            if self._unsub_weather_state is not None:
                self._unsub_weather_state()
                self._unsub_weather_state = None
            self._tracked_weather_entity = weather_ent
            if weather_ent:
                self._unsub_weather_state = async_track_state_change_event(
                    self.hass,
                    [weather_ent],
                    self._async_on_weather_state_change,
                )

        if self._unsub_sky_state is None:
            self._unsub_sky_state = async_track_state_change_event(
                self.hass,
                list(_SKY_TRACKED_ENTITIES),
                self._async_on_sky_state_change,
            )

        if self._unsub_forecast_timer is None:
            self._unsub_forecast_timer = async_track_time_interval(
                self.hass,
                self._async_periodic_weather_refresh,
                timedelta(minutes=FORECAST_REFRESH_INTERVAL_MINUTES),
            )
        if self._unsub_calendar_timer is None:
            self._unsub_calendar_timer = async_track_time_interval(
                self.hass,
                self._async_periodic_calendar_refresh,
                timedelta(minutes=CALENDAR_REFRESH_INTERVAL_MINUTES),
            )

    @callback
    def async_cleanup_feeds(self) -> None:
        """Unsubscribe System-level weather and calendar listeners/timers on unload."""
        for unsub in (
            self._unsub_weather_state,
            self._unsub_sky_state,
            self._unsub_forecast_timer,
            self._unsub_calendar_timer,
        ):
            if unsub is not None:
                unsub()
        self._unsub_weather_state = None
        self._unsub_sky_state = None
        self._unsub_forecast_timer = None
        self._unsub_calendar_timer = None
        self._tracked_weather_entity = None
        self.weather_loaded = False
        self.calendar_loaded = False

    @callback
    def _async_on_weather_state_change(
        self, _event: Event[EventStateChangedData]
    ) -> None:
        """Refresh the Site weather snapshot once when the configured weather entity updates."""
        self.hass.async_create_task(
            self.async_refresh_weather_forecast(),
            "latter_system_weather_refresh",
        )

    @callback
    def _async_on_sky_state_change(
        self, _event: Event[EventStateChangedData]
    ) -> None:
        """Update sun/moon fields on cached weather snapshot (or refresh if not yet loaded)."""
        if self.weather_snapshot is not None:
            recs, fields = self.weather_snapshot
            merged = {**fields, **read_sun_and_moon_fields(self.hass)}
            if merged == fields:
                return
            self.weather_snapshot = (recs, merged)
            weather_ent = self.weather_entity
            for coord in list(self.coordinators.values()):
                if not coord.is_ble_tag:
                    coord.apply_weather_snapshot(weather_ent, self.weather_snapshot)
            return
        self.hass.async_create_task(
            self.async_refresh_weather_forecast(coalesce=True),
            "latter_system_sky_refresh",
        )

    async def _async_periodic_weather_refresh(self, _now: datetime) -> None:
        """Refresh the 5-day Site weather forecast every 30 minutes."""
        await self.async_refresh_weather_forecast()

    async def _async_periodic_calendar_refresh(self, _now: datetime) -> None:
        """Refresh the Site calendar agenda every 15 minutes."""
        await self.async_refresh_calendar_agenda()

    async def async_refresh_weather_forecast(self, *, coalesce: bool = False) -> None:
        """Fetch the daily forecast once for the Site and fan out to all display coordinators."""
        self.bind_feed_listeners()
        now_m = time.monotonic()
        weather_ent = self.weather_entity
        if (
            coalesce
            and self.weather_loaded
            and (now_m - self._weather_last_fetch_mono) < 0.5
        ):
            return
        self._weather_last_fetch_mono = now_m
        snap = await async_fetch_weather_snapshot(self.hass, weather_ent)
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
                    **read_sun_and_moon_fields(self.hass),
                },
            )
            self.weather_snapshot = sky_only
            self.weather_loaded = True
            for coord in list(self.coordinators.values()):
                if not coord.is_ble_tag:
                    coord.apply_weather_snapshot(None, sky_only)
            return

        self.weather_snapshot = snap
        self.weather_loaded = True
        for coord in list(self.coordinators.values()):
            if not coord.is_ble_tag:
                coord.apply_weather_snapshot(weather_ent, snap)

    async def async_refresh_calendar_agenda(
        self, days: int = 30, *, coalesce: bool = False
    ) -> tuple[V3Records, list[dict[str, Any]]]:
        """Fetch and deduplicate upcoming calendar events once for the Site and fan out to all display coordinators."""
        self.bind_feed_listeners()
        now_m = time.monotonic()
        if (
            coalesce
            and days == 30
            and self.calendar_loaded
            and (now_m - self._calendar_last_fetch_mono) < 0.5
        ):
            return self.calendar_records, self.calendar_raw_rows
        records, raw_rows = await async_fetch_raw_calendar_events(
            self.hass,
            self.calendar_entities,
            days=days,
        )
        if days == 30:
            self.calendar_records = records
            self.calendar_raw_rows = raw_rows
            self.calendar_loaded = True
            self._calendar_last_fetch_mono = now_m
            for coord in list(self.coordinators.values()):
                if not coord.is_ble_tag:
                    coord.apply_calendar_snapshot(records, raw_rows)
        return records, raw_rows


LatterSystem = LatterSystemHub


def get_latter_system(hass: HomeAssistant) -> LatterSystemHub | None:
    """Return the initialized LatterSystemHub instance if present."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return None
    sys_obj = domain_data.get(DATA_SYSTEM)
    if isinstance(sys_obj, LatterSystemHub):
        return sys_obj
    store = domain_data.get(DATA_GLOBAL_STORE)
    cfg = domain_data.get(DATA_GLOBAL_CONFIG)
    secret = domain_data.get(DATA_HMAC_SECRET)
    if isinstance(store, Store) and isinstance(cfg, dict) and isinstance(secret, bytes):
        sys_obj = LatterSystemHub(hass, store, cfg, secret)
        domain_data[DATA_SYSTEM] = sys_obj
        return sys_obj
    return None


def get_system_device_info() -> DeviceInfo:
    """Return canonical DeviceInfo for the System-level Latter service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, "system")},
        entry_type=dr.DeviceEntryType.SERVICE,
        name="Latter System",
        manufacturer="Lampton Labs",
        model="Latter Site & BLE Fabric Engine",
        sw_version=INTEGRATION_VERSION,
        configuration_url="homeassistant://latter",
    )
