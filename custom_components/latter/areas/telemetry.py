"""Home Hub summaries, `area_context` v3 payload builder, and coordinator Area listeners."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
import math
import time
from typing import Any, Final

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from ..cameras.capabilities import resolve_camera_capabilities
from ..const import (
    CONF_ALARM_ENTITY,
    CONF_BROADCAST_SPEAKERS,
    CONF_WORLD_CLOCKS,
    DEFAULT_BROADCAST_PHRASES,
    DOMAIN,
)
from ..hub_registry import peek_global_config
from ..protocol_codec import (
    AREA_CLIMATES_MAX_RECORDS,
    CAMERAS_MAX_RECORDS,
    GARAGES_MAX_RECORDS,
    LOCKS_MAX_RECORDS,
    THERMOSTATS_MAX_RECORDS,
    VACUUMS_MAX_RECORDS,
    V3Records,
    area_climate_records,
    broadcast_phrase_records,
    build_time_zone_payloads,
    camera_records,
    entry_records,
    ha_value,
    thermostat_records,
    vacuum_records,
)
from ..protocol_policy import activity_payload
from ..protocol_specs import DEFAULT_HOME_CATEGORIES, parse_home_categories
from .catalogs import get_area_available_domains, get_area_entities
from .curation import (
    compute_climate_caps,
    compute_vacuum_caps,
    extract_climate_temps,
    get_home_alarm_summary as get_home_alarm_summary,
    is_curated_area_entity,
)
from .registry import (
    apply_ambient_light_deadband,
    apply_ha_display_precision,
    area_illuminance_sensor_choices,
    area_illuminance_settings,
    get_area_state_index,
    is_media_position_only_tick,
    latter_bound_esphome_device_ids,
    resolve_active_area_entry,
    resolve_area_ambient_light,
    resolve_area_icon,
    resolve_entity_area_id,
)

__all__ = [
    "bind_coordinator_area_listeners",
    "build_area_context_payload",
    "get_area_climate_telemetry",
    "get_area_climates_summary",
    "get_available_home_categories",
    "get_home_alarm_summary",
    "get_home_hub_summary",
]

_AREA_CACHE_TTL_S: Final = 0.15
_AREA_DEBOUNCE_S: Final = 0.25
_RELEVANT_AREA_SENSOR_CLASSES: Final[frozenset[str]] = frozenset(
    {"temperature", "humidity", "illuminance", "battery"}
)
_RELEVANT_AREA_SENSOR_UNITS: Final[frozenset[str]] = frozenset({"lx", "lux"})


def _is_relevant_area_sensor(
    hass: HomeAssistant, entity_id: str, configured_lux_ent: str
) -> bool:
    """Return True when `entity_id` is an Area climate/illuminance/battery or explicit lux sensor."""
    if configured_lux_ent != "auto" and entity_id == configured_lux_ent:
        return True
    st = hass.states.get(entity_id)
    if st is None:
        return False
    attrs = st.attributes
    dev_class = str(attrs.get("device_class") or "").strip().lower()
    if dev_class in _RELEVANT_AREA_SENSOR_CLASSES:
        return True
    unit = str(attrs.get("unit_of_measurement") or "").strip().lower()
    return unit in _RELEVANT_AREA_SENSOR_UNITS


@callback
def _invalidate_area_domain(coordinator: Any) -> None:
    """Invalidate ONLY the cached `area_context` payload and schedule a debounced push."""
    coordinator.cached_area_payload = None
    coordinator.schedule_debounced_notify()


def _parse_finite_sensor_float(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return val if math.isfinite(val) else None


def _fill_sensor_climate_telemetry(
    sensor_states: list[State],
    ent_reg: er.EntityRegistry,
    latter_dev_ids: set[str],
    result: dict[str, Any],
) -> None:
    for state_obj in sorted(sensor_states, key=lambda s: s.entity_id):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        entry = ent_reg.async_get(state_obj.entity_id)
        if entry is not None and (
            entry.platform == DOMAIN
            or bool(entry.disabled_by)
            or bool(entry.hidden_by)
            or entry.entity_category is not None
            or (entry.device_id and entry.device_id in latter_dev_ids)
        ):
            continue
        dev_class = str(state_obj.attributes.get("device_class") or "").lower()
        val_f = _parse_finite_sensor_float(state_obj.state)
        if val_f is None:
            continue
        if dev_class == "temperature" and result["temperature"] is None:
            result["temperature"] = apply_ha_display_precision(
                entry, val_f, default_precision=0
            )
            result["temperature_unit"] = str(
                state_obj.attributes.get("unit_of_measurement") or "°"
            )
        elif dev_class == "humidity" and result["humidity"] is None:
            result["humidity"] = apply_ha_display_precision(
                entry, val_f, default_precision=0
            )
        if result["temperature"] is not None and result["humidity"] is not None:
            return


def _fill_fallback_climate_telemetry(
    climate_states: list[State], result: dict[str, Any]
) -> None:
    for state_obj in sorted(climate_states, key=lambda s: s.entity_id):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        attrs = state_obj.attributes
        if result["temperature"] is None:
            cur_t = _parse_finite_sensor_float(attrs.get("current_temperature"))
            if cur_t is not None:
                result["temperature"] = round(cur_t, 1)
        if result["humidity"] is None:
            cur_h = _parse_finite_sensor_float(attrs.get("current_humidity"))
            if cur_h is not None:
                result["humidity"] = round(cur_h, 1)
        if result["temperature"] is not None and result["humidity"] is not None:
            return


def get_area_climate_telemetry(
    hass: HomeAssistant, area_id: str | None
) -> dict[str, Any]:
    """Discover ambient Area temperature and humidity assigned to `area_id` via `AreaStateIndex`."""
    result: dict[str, Any] = {
        "temperature": None,
        "temperature_unit": "",
        "humidity": None,
    }
    if not area_id:
        return result

    idx = get_area_state_index(hass)
    ent_reg = er.async_get(hass)
    latter_dev_ids = latter_bound_esphome_device_ids(hass)

    _fill_sensor_climate_telemetry(
        idx.entities_in_area(area_id, ("sensor",)),
        ent_reg,
        latter_dev_ids,
        result,
    )
    if result["temperature"] is None or result["humidity"] is None:
        _fill_fallback_climate_telemetry(
            idx.entities_in_area(area_id, ("climate",)), result
        )
    return result


def _clean_configured_ids(raw: Iterable[str] | None, limit: int) -> list[str]:
    if not raw or isinstance(raw, (str, bytes)):
        return []
    out: list[str] = []
    for item in raw:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out[:limit]


def get_home_hub_summary(
    hass: HomeAssistant,
    thermostat_entities: Iterable[str] | None = None,
    lock_entities: Iterable[str] | None = None,
    garage_entities: Iterable[str] | None = None,
    vacuum_entities: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Resolve explicitly configured multi-entity Home Hub Thermostats, Locks, Garages, and Vacuums."""
    idx = get_area_state_index(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def _area_of(ent_id: str) -> str:
        if idx.started:
            return idx.resolve_entity_area_id(ent_id) or ""
        return (
            resolve_entity_area_id(hass, ent_id, ent_reg=ent_reg, dev_reg=dev_reg) or ""
        )

    thermostats: list[dict[str, Any]] = []
    for ent_id in _clean_configured_ids(thermostat_entities, THERMOSTATS_MAX_RECORDS):
        if (t_st := hass.states.get(ent_id)) is None:
            continue
        tgt_temp, cur_temp = extract_climate_temps(t_st)
        thermostats.append(
            {
                "entity_id": t_st.entity_id,
                "name": str(t_st.attributes.get("friendly_name") or t_st.entity_id),
                "area_id": _area_of(t_st.entity_id),
                "state": ha_value(t_st.state),
                "target_temp": tgt_temp,
                "current_temp": cur_temp,
                "caps": compute_climate_caps(t_st),
            }
        )

    locks = [
        {
            "entity_id": l_st.entity_id,
            "name": str(l_st.attributes.get("friendly_name") or l_st.entity_id),
            "area_id": _area_of(l_st.entity_id),
            "state": ha_value(l_st.state),
        }
        for ent_id in _clean_configured_ids(lock_entities, LOCKS_MAX_RECORDS)
        if (l_st := hass.states.get(ent_id)) is not None
    ]
    garages = [
        {
            "entity_id": g_st.entity_id,
            "name": str(g_st.attributes.get("friendly_name") or g_st.entity_id),
            "area_id": _area_of(g_st.entity_id),
            "state": ha_value(g_st.state),
        }
        for ent_id in _clean_configured_ids(garage_entities, GARAGES_MAX_RECORDS)
        if (g_st := hass.states.get(ent_id)) is not None
    ]
    vacuums = [
        {
            "entity_id": v_st.entity_id,
            "name": str(v_st.attributes.get("friendly_name") or v_st.entity_id),
            "area_id": _area_of(v_st.entity_id),
            "state": ha_value(v_st.state),
            "caps": compute_vacuum_caps(v_st),
        }
        for ent_id in _clean_configured_ids(vacuum_entities, VACUUMS_MAX_RECORDS)
        if (v_st := hass.states.get(ent_id)) is not None
    ]

    return {
        "thermostats": thermostats,
        "thermostats_summary": thermostat_records(thermostats),
        "locks": locks,
        "locks_summary": entry_records(locks, LOCKS_MAX_RECORDS),
        "garages": garages,
        "garages_summary": entry_records(garages, GARAGES_MAX_RECORDS),
        "vacuums": vacuums,
        "vacuums_summary": vacuum_records(vacuums),
    }


def _is_intercom_available(
    hass: HomeAssistant | None,
    coordinator: Any,
    hub_info: Mapping[str, Any],
) -> bool:
    if hub_info.get("intercom_available"):
        return True
    if coordinator is not None:
        eff_speakers = getattr(coordinator, "effective_broadcast_speakers", None)
        if isinstance(eff_speakers, (list, tuple)):
            return bool(eff_speakers)
    hass_obj = hass or (
        getattr(coordinator, "hass", None) if coordinator is not None else None
    )
    if hass_obj is not None and hasattr(hass_obj, "data"):
        raw_spks = peek_global_config(hass_obj).get(CONF_BROADCAST_SPEAKERS)
        if isinstance(raw_spks, (list, tuple)) and any(
            str(s or "").strip().startswith("media_player.") for s in raw_spks
        ):
            return True
    return False


def get_available_home_categories(
    alarm_info: Mapping[str, Any],
    hub_info: Mapping[str, Any],
    home_categories: str | None = None,
    *,
    coordinator: Any = None,
    hass: HomeAssistant | None = None,
    has_intercom: bool | None = None,
) -> str:
    """Return comma-separated enabled Home Hub categories that have at least one configured entity."""
    configured = parse_home_categories(home_categories) or list(
        parse_home_categories(DEFAULT_HOME_CATEGORIES)
    )
    intercom_ok = (
        has_intercom
        if has_intercom is not None
        else _is_intercom_available(hass, coordinator, hub_info)
    )
    ordered: list[str] = []
    for tok in configured:
        if tok == "alarm" and alarm_info.get("entity_id"):
            ordered.append("alarm")
        elif tok == "intercom" and intercom_ok:
            ordered.append("intercom")
        elif tok == "thermostat" and hub_info.get("thermostats"):
            ordered.append("thermostat")
        elif tok == "entry" and (hub_info.get("locks") or hub_info.get("garages")):
            ordered.append("entry")
        elif tok == "vacuum" and hub_info.get("vacuums"):
            ordered.append("vacuum")
    return ",".join(ordered)


def get_area_climates_summary(
    hass: HomeAssistant,
    area_id: str | None,
    local_speaker: str = "",
) -> V3Records:
    """Return `area_climate_records` for curated `climate.*` entities in `area_id`."""
    if not area_id:
        return area_climate_records(())
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    idx = get_area_state_index(hass)
    bound_device_ids = latter_bound_esphome_device_ids(hass)
    area_entry = area_reg.async_get_area(area_id)
    area_name = area_entry.name if area_entry else ""

    rows: list[dict[str, Any]] = []
    for state_obj in sorted(
        idx.entities_in_area(area_id, ("climate",)), key=lambda s: s.entity_id
    ):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if not is_curated_area_entity(
            hass,
            state_obj,
            local_speaker,
            ent_reg=ent_reg,
            bound_device_ids=bound_device_ids,
        ):
            continue
        tgt_temp, cur_temp = extract_climate_temps(state_obj)
        friendly = str(state_obj.attributes.get("friendly_name") or state_obj.entity_id)
        if area_name and friendly.lower().startswith(area_name.lower() + " "):
            friendly = friendly[len(area_name) + 1 :].strip() or friendly
        rows.append(
            {
                "entity_id": state_obj.entity_id,
                "name": friendly,
                "state": ha_value(state_obj.state),
                "target_temp": tgt_temp,
                "current_temp": cur_temp,
                "caps": compute_climate_caps(state_obj),
            }
        )
        if len(rows) >= AREA_CLIMATES_MAX_RECORDS:
            break
    return area_climate_records(rows)


def _build_broadcast_phrases_summary(coordinator: Any) -> V3Records:
    phrases = getattr(coordinator, "broadcast_phrases", None)
    if not isinstance(phrases, (list, tuple)):
        phrases = DEFAULT_BROADCAST_PHRASES
    return broadcast_phrase_records(phrases)


def _build_cameras_summary(coordinator: Any) -> V3Records:
    visible_cams = getattr(
        coordinator, "visible_camera_entities", coordinator.camera_entities
    )
    carousel_cams = getattr(coordinator, "carousel_camera_entities", visible_cams)
    ring_map = coordinator.doorbell_ring_map
    vol_overrides = getattr(coordinator, "volume_overrides", None)
    cam_configs = getattr(coordinator, "camera_configs", None) or {}
    rows: list[dict[str, Any]] = []
    for ent_id in visible_cams[:CAMERAS_MAX_RECORDS]:
        meta = resolve_camera_capabilities(
            coordinator.hass,
            ent_id,
            doorbell_ring_map=ring_map,
            carousel_entities=carousel_cams,
            volume_overrides=vol_overrides,
            camera_config=cam_configs.get(ent_id),
        )
        rows.append(
            {
                "entity_id": meta["entity_id"],
                "name": meta["name"],
                "area_id": meta["area_id"],
                "caps": meta["caps"],
                "unlock_entity": meta["unlock_entity"],
            }
        )
    return camera_records(rows)


def build_area_context_payload(coordinator: Any) -> tuple[str, dict[str, Any]]:
    """Compute state and attributes for Protocol v3 `area_context`."""
    now_m = time.monotonic()
    cached = coordinator.cached_area_payload
    if cached is not None and (now_m - cached[0]) < _AREA_CACHE_TTL_S:
        cached_payload: tuple[str, dict[str, Any]] = cached[1]
        return cached_payload

    area_entry = resolve_active_area_entry(coordinator)
    area_name = area_entry.name if area_entry else "Unassigned"
    area_icon = resolve_area_icon(area_entry)
    eff_area_id = (
        area_entry.id
        if area_entry
        else ("" if coordinator.is_device_away() else (coordinator.active_area_id or ""))
    )

    if eff_area_id:
        entities = get_area_entities(
            coordinator.hass,
            area_id=eff_area_id,
            domain_filter="all",
            local_speaker=coordinator.local_speaker,
        )
        avail_domains = get_area_available_domains(
            coordinator.hass,
            area_id=eff_area_id,
            local_speaker=coordinator.local_speaker,
            entities=entities,
            area_categories=coordinator.area_categories_csv,
        )
    else:
        entities = []
        avail_domains = ""
    lights_on = sum(1 for e in entities if e["type"] == "light" and e["active"])
    covers_open = sum(1 for e in entities if e["type"] == "cover" and e["active"])
    climate_telemetry = get_area_climate_telemetry(
        coordinator.hass, eff_area_id or None
    )
    ambient_info = resolve_area_ambient_light(coordinator.hass, eff_area_id or None)
    eff_ambient = apply_ambient_light_deadband(
        coordinator.last_ambient_light,
        eff_area_id,
        ambient_info["ambient_pct"],
        ambient_info["wire"],
    )
    coordinator.last_ambient_light = eff_ambient
    area_ambient_wire = eff_ambient[2]

    alarm_info = get_home_alarm_summary(
        coordinator.hass, coordinator.get_opt(CONF_ALARM_ENTITY)
    )
    hub_info = get_home_hub_summary(
        coordinator.hass,
        thermostat_entities=coordinator.thermostat_entities,
        lock_entities=coordinator.lock_entities,
        garage_entities=coordinator.garage_entities,
        vacuum_entities=coordinator.vacuum_entities,
    )
    area_climates_summary = get_area_climates_summary(
        coordinator.hass, eff_area_id or None, coordinator.local_speaker
    )
    active_cam = coordinator.active_carousel_camera or coordinator.camera_entity
    camera_snapshot_url = (
        coordinator.build_camera_allowlist_snapshot_url(active_cam)
        if active_cam
        else ""
    )
    camera_stream_url = coordinator.build_camera_stream_url()
    alert_camera_entity = (
        coordinator.alert_camera_entity if coordinator.alert_id else ""
    )

    eff_pin_policy = coordinator.security_pin_policy
    alarm_caps = int(alarm_info.get("alarm_caps") or 0)
    avail_home_cats = get_available_home_categories(
        alarm_info,
        hub_info,
        home_categories=coordinator.home_categories_csv,
        coordinator=coordinator,
        hass=coordinator.hass,
    )
    local_tz_info, world_clocks_summary = build_time_zone_payloads(
        getattr(coordinator.hass.config, "time_zone", None),
        str(coordinator.get_opt(CONF_WORLD_CLOCKS, "") or ""),
    )
    ble_tracker = coordinator.ble_tracker
    area_attrs: dict[str, Any] = {
        "site_id": coordinator.site_id,
        "area_id": eff_area_id,
        "area_name": area_name,
        "area_icon": area_icon,
        "ble_closest_proxy": ble_tracker.closest_scanner if ble_tracker else "",
        "activity_card": coordinator.activity_card_enabled,
        "activity_sources": coordinator.activity_sources_csv,
        "security_pin_policy": eff_pin_policy,
        "home_categories": avail_home_cats,
        "wallpaper_url": coordinator.build_wallpaper_url(),
        "available_domains": avail_domains,
        "area_temp": climate_telemetry["temperature"],
        "area_humidity": climate_telemetry["humidity"],
        "lights_on": lights_on,
        "covers_open": covers_open,
        "alarm_entity": alarm_info["entity_id"],
        "alarm_state": alarm_info["state"],
        "alarm_caps": alarm_caps,
        "thermostats": hub_info["thermostats"],
        "thermostats_summary": hub_info["thermostats_summary"],
        "locks": hub_info["locks"],
        "locks_summary": hub_info["locks_summary"],
        "garages": hub_info["garages"],
        "garages_summary": hub_info["garages_summary"],
        "vacuums": hub_info["vacuums"],
        "vacuums_summary": hub_info["vacuums_summary"],
        "area_climates_summary": area_climates_summary,
        "camera_snapshot_url": camera_snapshot_url,
        "camera_stream_url": camera_stream_url,
        "cameras_summary": _build_cameras_summary(coordinator),
        "doorbell_talk_state": coordinator.doorbell_talk_state,
        "broadcast_phrases": _build_broadcast_phrases_summary(coordinator),
        "alert_id": coordinator.alert_id,
        "alert_title": coordinator.alert_title,
        "alert_message": coordinator.alert_message,
        "alert_priority": coordinator.alert_priority,
        "alert_duration": coordinator.alert_duration,
        "alert_chime": coordinator.alert_chime,
        "alert_camera_url": coordinator.alert_camera_url,
        "alert_camera_entity": alert_camera_entity,
        "local_tz_info": local_tz_info,
        "world_clocks_summary": world_clocks_summary,
        "screensaver_photo_url": coordinator.build_screensaver_photo_url(),
        "area_ambient_light": area_ambient_wire,
        "area_lux": ambient_info["lux"],
        "area_lux_display": ambient_info["lux_display"],
        "area_ambient_pct": ambient_info["ambient_pct"],
        "area_illuminance_entity": ambient_info["resolved_entity"],
        "area_illuminance_name": ambient_info["resolved_name"],
    }
    area_rev, area_payload = coordinator.pack_domain_payload(
        "area_context",
        area_attrs["area_id"],
        area_entry.name if area_entry else "",
        area_attrs["site_id"],
        area_attrs["ble_closest_proxy"],
        area_attrs["wallpaper_url"],
        area_attrs["available_domains"],
        area_attrs["area_temp"],
        area_attrs["area_humidity"],
        lights_on,
        covers_open,
        area_attrs["alarm_entity"],
        area_attrs["alarm_state"],
        area_attrs["thermostats_summary"],
        area_attrs["locks_summary"],
        area_attrs["garages_summary"],
        area_attrs["vacuums_summary"],
        area_attrs["area_climates_summary"],
        area_attrs["camera_snapshot_url"],
        area_attrs["cameras_summary"],
        area_attrs["doorbell_talk_state"],
        area_attrs["broadcast_phrases"],
        *(
            (
                coordinator.alert_id,
                coordinator.alert_title,
                coordinator.alert_message,
                coordinator.alert_priority,
                coordinator.alert_duration,
                1 if coordinator.alert_chime else 0,
                coordinator.alert_camera_url,
            )
            if coordinator.alert_id
            else (0, "", "", "", None, None, "")
        ),
        *activity_payload(
            coordinator.activity_card_enabled, coordinator.activity_sources_csv
        ),
        eff_pin_policy,
        area_attrs["home_categories"],
        area_icon,
        local_tz_info,
        world_clocks_summary,
        alarm_caps,
        camera_stream_url,
        alert_camera_entity,
        area_attrs["screensaver_photo_url"],
        area_ambient_wire,
    )
    area_attrs["rev"] = area_rev
    area_attrs["payload"] = area_payload
    res = (area_name, area_attrs)
    coordinator.cached_area_payload = (time.monotonic(), res)
    return res


def _build_active_area_listener(
    coordinator: Any,
    schedule_area_push: Callable[[], None],
) -> Callable[[], None] | None:
    idx = get_area_state_index(coordinator.hass)
    unsubs_area: list[Callable[[], None]] = []
    eff_area_entry = resolve_active_area_entry(coordinator)
    listen_area_id = (
        eff_area_entry.id
        if eff_area_entry is not None
        else (coordinator.active_area_id or "")
    )
    if not listen_area_id:
        return None

    @callback
    def _on_lux_or_sensor_event(event: Event[EventStateChangedData]) -> None:
        new_st = event.data.get("new_state")
        old_st = event.data.get("old_state")
        if new_st is None or (old_st is not None and new_st.state == old_st.state):
            return
        _invalidate_area_domain(coordinator)

    lux_ent = str(
        area_illuminance_settings(coordinator.hass, listen_area_id)["entity_id"]
    )
    if idx.started:

        @callback
        def _on_indexed_area_change(changed_eid: str) -> None:
            if changed_eid.startswith("sensor."):
                if _is_relevant_area_sensor(coordinator.hass, changed_eid, lux_ent):
                    _invalidate_area_domain(coordinator)
                return
            schedule_area_push()

        unsubs_area.append(
            idx.register_area_listener(listen_area_id, _on_indexed_area_change)
        )
    else:

        @callback
        def _on_area_entity_event(event: Event[EventStateChangedData]) -> None:
            if is_media_position_only_tick(
                event.data.get("old_state"), event.data.get("new_state")
            ):
                return
            schedule_area_push()

        area_items = get_area_entities(
            coordinator.hass,
            area_id=listen_area_id,
            domain_filter="all",
            local_speaker=coordinator.local_speaker,
        )
        tracked_ids = [str(it["id"]) for it in area_items if it.get("id")]
        if tracked_ids:
            unsubs_area.append(
                async_track_state_change_event(
                    coordinator.hass, tracked_ids, _on_area_entity_event
                )
            )
        if lux_ent == "auto":
            fallback_lux = [
                str(c["entity_id"])
                for c in area_illuminance_sensor_choices(
                    coordinator.hass, listen_area_id
                )
                if c.get("entity_id")
            ]
            if fallback_lux:
                unsubs_area.append(
                    async_track_state_change_event(
                        coordinator.hass, fallback_lux, _on_lux_or_sensor_event
                    )
                )

    if lux_ent != "auto" and lux_ent.startswith("sensor."):
        unsubs_area.append(
            async_track_state_change_event(
                coordinator.hass, [lux_ent], _on_lux_or_sensor_event
            )
        )

    if not unsubs_area:
        return None

    @callback
    def _unsub_area_all() -> None:
        for u in unsubs_area:
            u()

    unsub_fn: Callable[[], None] = _unsub_area_all
    return unsub_fn


def _build_shortcuts_listener(coordinator: Any) -> Callable[[], None] | None:
    tracked_shortcuts: list[str] = []
    for sc_list in (coordinator.dock_items, coordinator.pinned_items):
        for sc in sc_list:
            if sc.get("kind") == "entity":
                ent = str(sc.get("target") or "").strip()
                if ent and ent not in tracked_shortcuts:
                    tracked_shortcuts.append(ent)
    if not tracked_shortcuts:
        return None

    @callback
    def _on_shortcut_entity_event(event: Event[EventStateChangedData]) -> None:
        old_st = event.data.get("old_state")
        new_st = event.data.get("new_state")
        if is_media_position_only_tick(old_st, new_st):
            return
        if (
            old_st is not None
            and new_st is not None
            and old_st.state == new_st.state
            and old_st.attributes.get("icon") == new_st.attributes.get("icon")
            and old_st.attributes.get("friendly_name")
            == new_st.attributes.get("friendly_name")
        ):
            return
        coordinator.async_notify_listeners()

    unsub: Callable[[], None] = async_track_state_change_event(
        coordinator.hass, tracked_shortcuts, _on_shortcut_entity_event
    )
    return unsub


@callback
def bind_coordinator_area_listeners(coordinator: Any) -> None:
    """Bind active Area, Home Hub, Remote Slot, and Shortcut entity listeners on `coordinator`."""
    coordinator.replace_area_listener_unsubs(
        area_entities=None, alarm=None, remotes=None, shortcuts=None
    )

    @callback
    def _schedule_area_push() -> None:
        _invalidate_area_domain(coordinator)

        @callback
        def _push_area_update(_now: datetime) -> None:
            coordinator.replace_area_debounce_unsub(None)
            if coordinator.on_area_changed_push_slots is not None:
                coro = coordinator.on_area_changed_push_slots(coordinator)
                task_name = f"latter_area_slots_{coordinator.device_slug}"
                if hasattr(coordinator, "create_background_task"):
                    coordinator.create_background_task(coro, task_name)
                else:
                    coordinator.entry.async_create_background_task(
                        coordinator.hass, coro, task_name
                    )

        coordinator.replace_area_debounce_unsub(
            async_call_later(coordinator.hass, _AREA_DEBOUNCE_S, _push_area_update)
        )

    area_unsub = _build_active_area_listener(coordinator, _schedule_area_push)

    tracked_hub: list[str] = []
    for cand in (
        coordinator.alarm_entity,
        *coordinator.thermostat_entities,
        *coordinator.lock_entities,
        *coordinator.garage_entities,
        *coordinator.vacuum_entities,
    ):
        if cand and cand not in tracked_hub:
            tracked_hub.append(cand)
    alarm_unsub: Callable[[], None] | None = (
        async_track_state_change_event(
            coordinator.hass,
            tracked_hub,
            lambda _ev: coordinator.async_notify_listeners(),
        )
        if tracked_hub
        else None
    )

    tracked_rem: list[str] = []
    for slot in coordinator.get_remote_slots():
        for key in ("remote_entity", "media_player_entity"):
            ent = slot.get(key)
            if ent and ent not in tracked_rem:
                tracked_rem.append(ent)
    @callback
    def _on_remote_entity_event(event: Event[EventStateChangedData]) -> None:
        if is_media_position_only_tick(
            event.data.get("old_state"), event.data.get("new_state")
        ):
            return
        coordinator.cached_remote_payload = None
        coordinator.schedule_debounced_notify()

    remotes_unsub: Callable[[], None] | None = (
        async_track_state_change_event(
            coordinator.hass,
            tracked_rem,
            _on_remote_entity_event,
        )
        if tracked_rem
        else None
    )

    shortcuts_unsub = _build_shortcuts_listener(coordinator)
    coordinator.replace_area_listener_unsubs(
        area_entities=area_unsub,
        alarm=alarm_unsub,
        remotes=remotes_unsub,
        shortcuts=shortcuts_unsub,
    )
