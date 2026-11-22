"""Studio WebSocket command handlers for presence calibration, device actions, and onboarding (`L3`)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
import logging
import math
import re
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from ..areas.actions import async_execute_area_action
from ..areas.registry import area_illuminance_sensor_choices, resolve_area_ambient_light
from ..const import (
    CONF_AREA_FUSION_CONFIG,
    CONF_AREA_ILLUMINANCE_CONFIG,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_CATEGORY,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_GROUP,
    CONF_ESPHOME_DEVICE_ID,
    CONF_IGNORED_DISCOVERED_DEVICES,
    DATA_GLOBAL_CONFIG,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..groups.device_groups import get_device_groups
from ..hub_registry import get_system_config_lock, iter_coordinators
from ..hub_sync import async_save_and_broadcast_global_config
from ..identity import (
    bound_elsewhere,
    device_entities,
    device_title,
    device_unique_id,
    get_bound_esphome_device,
    is_esphome_device,
    is_latter_compatible_esphome_device,
)
from ..presence.area_fusion import area_fusion_sensor_choices
from ..presence.ble_fabric import get_ble_fabric
from .payload_shared import StudioCommandError, log_studio_event
from .settings_cleaners import (
    MAX_IGNORED_DISCOVERED,
    clean_area_fusion,
    clean_area_illuminance,
)
from .state_gates import (
    ALLOWED_DEVICE_ACTIONS,
    DEVICE_ENTITY_VERBS,
    allowed_entity_targets,
    checked_entity_verb,
    find_by_subentry_id,
)

_LOGGER = logging.getLogger(__name__)

_OPT_STR_MAX_LEN: Final = 128
_SCANNER_OFFSET_ABS_MAX: Final = 25.0
_SCANNER_OFFSET_ZERO_EPS: Final = 0.1
_DARK_LUX_MAX: Final = 500.0
_BRIGHT_LUX_MAX: Final = 100000.0
_BRIGHT_LUX_MIN_DELTA: Final = 5.0
_LUX_DECIMAL_CUTOFF: Final = 10.0
_MIN_POS_MEAN_SAMPLES: Final = 4
_RECORDER_CALIBRATION_DAYS: Final = 7
_UPDATE_ENTITY_TIMEOUT_S: Final = 30
_IBEACON_PREFIX: Final = "ibeacon:"


def _optional_level(body: dict[str, Any]) -> int | None:
    level = body.get("level")
    if level is None:
        return None
    if isinstance(level, bool):
        raise StudioCommandError("invalid_format", "level must be a number")
    try:
        fval = float(level)
    except (TypeError, ValueError) as err:
        raise StudioCommandError("invalid_format", f"Invalid level: {err}") from None
    if not math.isfinite(fval):
        raise StudioCommandError("invalid_format", "level must be a finite number")
    return round(fval)


def _optional_option(body: dict[str, Any]) -> str | None:
    option = body.get("option")
    return str(option)[:_OPT_STR_MAX_LEN] if option is not None else None


async def _cmd_set_ble_scanner_offset(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    scanner_source = str(body.get("scanner_source") or "").strip().upper()
    if not scanner_source:
        raise StudioCommandError("invalid_format", "scanner_source is required")
    raw_offset = body.get("offset_db", 0.0)
    if isinstance(raw_offset, bool):
        raise StudioCommandError("invalid_format", "offset_db must be a number")
    try:
        offset_val = float(raw_offset if raw_offset is not None else 0.0)
    except (TypeError, ValueError) as err:
        raise StudioCommandError("invalid_format", f"Invalid offset_db: {err}") from None
    if not math.isfinite(offset_val):
        raise StudioCommandError("invalid_format", "offset_db must be a finite number")

    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_offsets = live_cfg.get(CONF_BLE_SCANNER_OFFSETS)
        offsets: dict[str, float] = {}
        if isinstance(raw_offsets, dict):
            for k, v in raw_offsets.items():
                norm_k = str(k or "").strip().upper()
                if not norm_k:
                    continue
                try:
                    clamped = max(-_SCANNER_OFFSET_ABS_MAX, min(_SCANNER_OFFSET_ABS_MAX, float(v)))
                    offsets[norm_k] = round(clamped, 1)
                except (TypeError, ValueError) as err:
                    _LOGGER.debug("Ignoring malformed scanner offset %s: %s", norm_k, err)
        if abs(offset_val) < _SCANNER_OFFSET_ZERO_EPS:
            offsets.pop(scanner_source, None)
        else:
            clamped_new = max(-_SCANNER_OFFSET_ABS_MAX, min(_SCANNER_OFFSET_ABS_MAX, offset_val))
            offsets[scanner_source] = round(clamped_new, 1)
        await async_save_and_broadcast_global_config(hass, {CONF_BLE_SCANNER_OFFSETS: offsets})


async def _cmd_set_area_fusion(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    area_id = str(body.get("area_id") or "").strip()
    if not area_id or ar.async_get(hass).async_get_area(area_id) is None:
        raise StudioCommandError("not_found", f"Unknown Area '{area_id}'")
    allowed_sensors = {s["entity_id"] for s in area_fusion_sensor_choices(hass, area_id)}
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_fusion = live_cfg.get(CONF_AREA_FUSION_CONFIG) or {}
        fusion_cfg = dict(raw_fusion) if isinstance(raw_fusion, dict) else {}
        current_area = fusion_cfg.get(area_id)
        fusion_cfg[area_id] = clean_area_fusion(
            current_area if isinstance(current_area, dict) else {},
            {k: body[k] for k in ("mode", "threshold_pct", "sensors") if k in body},
            allowed_sensors,
        )
        await async_save_and_broadcast_global_config(hass, {CONF_AREA_FUSION_CONFIG: fusion_cfg})
    fabric = get_ble_fabric(hass)
    fabric.rebind_fusion_sensor_listener()
    fabric.notify_occupancy_listeners()


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linearly interpolated percentile (`q` in `0..1`) over a non-empty sorted list."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = max(0.0, min(1.0, q)) * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = min(len(sorted_vals) - 1, lo + 1)
    return sorted_vals[lo] + (pos - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _append_non_negative_float(dest: list[float], raw: Any) -> None:
    if raw is None or isinstance(raw, bool):
        return
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return
    if math.isfinite(val) and val >= 0.0:
        dest.append(val)


def compute_illuminance_calibration_from_stats(
    rows: list[Mapping[str, Any]],
) -> tuple[float, float] | None:
    """Derive `(dark_lux, bright_lux)` from hourly HA recorder statistics rows."""
    mins: list[float] = []
    means: list[float] = []
    for row in rows:
        _append_non_negative_float(mins, row.get("min"))
        _append_non_negative_float(means, row.get("mean"))
    if not means:
        return None
    mins_sorted = sorted(mins or means)
    means_sorted = sorted(means)
    dark_raw = max(0.0, min(_DARK_LUX_MAX, _percentile(mins_sorted, 0.10)))
    dark_lux = round(dark_raw, 1) if dark_raw < _LUX_DECIMAL_CUTOFF else float(round(dark_raw))

    pos_means = [v for v in means_sorted if v > dark_lux + 0.1]
    if len(pos_means) >= _MIN_POS_MEAN_SAMPLES:
        bright_raw = _percentile(pos_means, 0.90)
    elif pos_means:
        bright_raw = max(pos_means)
    else:
        bright_raw = _percentile(means_sorted, 0.90)
    bright_raw = max(dark_lux + _BRIGHT_LUX_MIN_DELTA, min(_BRIGHT_LUX_MAX, bright_raw))
    bright_lux = (
        round(bright_raw, 1) if bright_raw < _LUX_DECIMAL_CUTOFF else float(round(bright_raw))
    )
    return (dark_lux, bright_lux)


def _refresh_coordinators_ambient_light(hass: HomeAssistant) -> None:
    """Clear ambient-light deadband caches and notify all Device coordinators immediately."""
    for coord in iter_coordinators(hass):
        coord.last_ambient_light = ("", None, "")
        coord.cached_area_payload = None
        coord.async_notify_listeners()


async def _cmd_set_area_illuminance(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    area_id = str(body.get("area_id") or "").strip()
    if not area_id or ar.async_get(hass).async_get_area(area_id) is None:
        raise StudioCommandError("not_found", f"Unknown Area '{area_id}'")
    allowed_sensors = {str(s["entity_id"]) for s in area_illuminance_sensor_choices(hass, area_id)}
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_lux = live_cfg.get(CONF_AREA_ILLUMINANCE_CONFIG) or {}
        lux_cfg = dict(raw_lux) if isinstance(raw_lux, dict) else {}
        current_area = lux_cfg.get(area_id)
        lux_cfg[area_id] = clean_area_illuminance(
            current_area if isinstance(current_area, dict) else {},
            {k: body[k] for k in ("entity_id", "dark_lux", "bright_lux") if k in body},
            allowed_sensors,
        )
        await async_save_and_broadcast_global_config(hass, {CONF_AREA_ILLUMINANCE_CONFIG: lux_cfg})
    _refresh_coordinators_ambient_light(hass)


def _collect_illuminance_targets(
    hass: HomeAssistant, target_area_id: str
) -> tuple[list[tuple[str, str, str]], list[str]]:
    area_reg = ar.async_get(hass)
    if target_area_id:
        area_entry = area_reg.async_get_area(target_area_id)
        if area_entry is None:
            raise StudioCommandError("not_found", f"Unknown Area '{target_area_id}'")
        target_areas = [area_entry]
    else:
        target_areas = list(area_reg.async_list_areas())

    area_targets: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    for area_entry in target_areas:
        ambient = resolve_area_ambient_light(hass, area_entry.id)
        if ambient["configured_entity"] == "disabled":
            skipped.append(area_entry.name)
            continue
        eid = str(ambient["resolved_entity"] or "")
        if not eid:
            if target_area_id:
                raise StudioCommandError(
                    "invalid_format", f"No illuminance sensor found in {area_entry.name}"
                )
            continue
        area_targets.append((area_entry.id, area_entry.name, eid))

    if not area_targets:
        raise StudioCommandError("invalid_format", "No illuminance sensors found to calibrate")
    return area_targets, skipped


async def _async_fetch_illuminance_stats(
    hass: HomeAssistant, statistic_ids: list[str]
) -> dict[str, list[Mapping[str, Any]]]:
    try:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        end_dt = dt_util.utcnow()
        start_dt = end_dt - timedelta(days=_RECORDER_CALIBRATION_DAYS)
        rec = get_instance(hass)
        res: dict[str, list[Mapping[str, Any]]] = await rec.async_add_executor_job(
            statistics_during_period,
            hass,
            start_dt,
            end_dt,
            set(statistic_ids),
            "hour",
            None,
            {"min", "mean"},
        )
        return res
    except Exception as err:
        _LOGGER.debug("Recorder statistics unavailable for illuminance calibration: %s", err)
        raise StudioCommandError(
            "failed",
            "Recorder hourly statistics are unavailable for ambient light calibration",
        ) from err


async def _cmd_calibrate_area_illuminance(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    if "recorder" not in hass.config.components:
        raise StudioCommandError(
            "not_supported",
            "Home Assistant recorder component is not enabled for ambient light calibration",
        )
    target_area_id = str(body.get("area_id") or "").strip()
    area_targets, skipped = _collect_illuminance_targets(hass, target_area_id)
    stats_by_eid = await _async_fetch_illuminance_stats(
        hass, sorted({eid for _, _, eid in area_targets})
    )

    calibrated: list[dict[str, Any]] = []
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_lux = live_cfg.get(CONF_AREA_ILLUMINANCE_CONFIG) or {}
        lux_cfg = dict(raw_lux) if isinstance(raw_lux, dict) else {}
        for aid, aname, eid in area_targets:
            rows = list(stats_by_eid.get(eid) or [])
            cal = compute_illuminance_calibration_from_stats(rows)
            if cal is None:
                skipped.append(aname)
                continue
            dark_lux, bright_lux = cal
            cur = dict(lux_cfg.get(aid) or {}) if isinstance(lux_cfg.get(aid), dict) else {}
            cur["dark_lux"] = dark_lux
            cur["bright_lux"] = bright_lux
            lux_cfg[aid] = cur
            calibrated.append(
                {
                    "area_id": aid,
                    "area_name": aname,
                    "entity_id": eid,
                    "dark_lux": dark_lux,
                    "bright_lux": bright_lux,
                    "samples": len(rows),
                }
            )
        if not calibrated:
            raise StudioCommandError(
                "invalid_format",
                "Not enough recorded illuminance history yet (wait for hourly statistics)",
            )
        await async_save_and_broadcast_global_config(hass, {CONF_AREA_ILLUMINANCE_CONFIG: lux_cfg})

    _refresh_coordinators_ambient_light(hass)
    extra["calibrated"] = calibrated
    extra["skipped"] = skipped
    log_studio_event(
        hass, "INFO", "system", f"Auto-calibrated ambient light for {len(calibrated)} Area(s)"
    )


async def _cmd_capture_ble_area_signature(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    target_area_id = str(body.get("area_id") or "").strip()
    survey_id = str(body.get("survey_subentry_id") or "").strip()
    if not target_area_id:
        raise StudioCommandError("invalid_format", "area_id is required")
    if ar.async_get(hass).async_get_area(target_area_id) is None:
        raise StudioCommandError("not_found", f"Unknown Area '{target_area_id}'")
    if not survey_id:
        raise StudioCommandError(
            "invalid_format", "survey_subentry_id is required: select the BLE survey Device"
        )
    survey_coord = find_by_subentry_id(iter_coordinators(hass), survey_id)
    if survey_coord is None:
        raise StudioCommandError("not_found", f"No Latter Device with subentry_id '{survey_id}'")
    tracker = survey_coord.ble_tracker
    if tracker is None:
        raise StudioCommandError(
            "not_supported",
            f"{survey_coord.device_title} has no BLE tracker: enable Track the Area with BLE Proxies for it first",
        )

    scanners_sig = tracker.capture_area_signature()
    if not scanners_sig:
        raise StudioCommandError(
            "not_ready",
            "No fresh Bluetooth proxy readings yet for this Device — wait a few seconds and try again",
        )

    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_sigs = live_cfg.get(CONF_BLE_AREA_SIGNATURES)
        signatures = dict(raw_sigs) if isinstance(raw_sigs, dict) else {}
        signatures[target_area_id] = {
            "scanners": scanners_sig,
            "captured_at": dt_util.utcnow().isoformat(timespec="seconds"),
            "sample_count": sum(int(v.get("n", 1)) for v in scanners_sig.values()),
        }
        await async_save_and_broadcast_global_config(hass, {CONF_BLE_AREA_SIGNATURES: signatures})
    survey_coord.async_set_active_area(
        target_area_id, handoff_media=False, sync_device_registry=True
    )


async def _cmd_clear_ble_area_signature(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    target_area_id = str(body.get("area_id") or "").strip()
    if not target_area_id:
        raise StudioCommandError("invalid_format", "area_id is required")
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_sigs = live_cfg.get(CONF_BLE_AREA_SIGNATURES)
        signatures = dict(raw_sigs) if isinstance(raw_sigs, dict) else {}
        signatures.pop(target_area_id, None)
        await async_save_and_broadcast_global_config(hass, {CONF_BLE_AREA_SIGNATURES: signatures})


async def _cmd_esphome_entity_action(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    if coordinator is None:
        raise StudioCommandError("not_found", "Device required")
    allowed = {e.entity_id for e in device_entities(hass, coordinator.esphome_device_id)}
    (entity_id,) = allowed_entity_targets(
        [body.get("entity_id")], allowed, f"an entity of {coordinator.device_title}"
    )
    action = checked_entity_verb(body, DEVICE_ENTITY_VERBS)
    try:
        await async_execute_area_action(
            hass,
            entity_id=entity_id,
            action=action or "toggle",
            level=_optional_level(body),
            option=_optional_option(body),
            blocking=True,
            raise_on_missing=True,
        )
    except ServiceValidationError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    except HomeAssistantError as err:
        raise StudioCommandError("command_failed", str(err)) from err


async def _cmd_device_action(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    if coordinator is None:
        raise StudioCommandError("not_found", "Device required")
    action = str(body.get("action") or "").strip().lower()
    if action not in ALLOWED_DEVICE_ACTIONS:
        raise StudioCommandError(
            "invalid_format",
            f"Unsupported device action '{action}' (expected one of {', '.join(ALLOWED_DEVICE_ACTIONS)})",
        )
    try:
        await coordinator.async_send_device_command(action, raise_if_offline=True)
    except HomeAssistantError as err:
        raise StudioCommandError("command_failed", str(err)) from err
    log_studio_event(
        hass,
        "INFO",
        coordinator.device_slug,
        f"Sent device action '{action}' to '{coordinator.device_slug}'",
    )


async def _cmd_check_system_updates(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    _body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    coords = [c for c in iter_coordinators(hass) if not c.is_ble_tag]
    update_ids = {
        c.subentry_id: [
            e.entity_id for e in device_entities(hass, c.esphome_device_id, domain="update")
        ]
        for c in coords
    }
    all_ids = [eid for ids in update_ids.values() for eid in ids]
    if all_ids:
        try:
            async with asyncio.timeout(_UPDATE_ENTITY_TIMEOUT_S):
                await hass.services.async_call(
                    "homeassistant", "update_entity", {"entity_id": all_ids}, blocking=True
                )
        except TimeoutError:
            raise StudioCommandError(
                "timeout", "The firmware check took longer than 30 seconds; try again"
            ) from None
    extra["update_check"] = {
        "checked": sum(1 for ids in update_ids.values() if ids),
        "available": sum(
            1
            for ids in update_ids.values()
            if any((st := hass.states.get(eid)) is not None and st.state == "on" for eid in ids)
        ),
    }


async def _cmd_clear_internal_logs(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    _body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    hass.data.setdefault(DOMAIN, {})["internal_logs"] = []
    log_studio_event(hass, "INFO", "studio", "Cleared internal diagnostic log")


async def _cmd_ignore_discovered_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    esp_dev_id = str(body.get("esphome_device_id") or "").strip()
    if not esp_dev_id:
        raise StudioCommandError("invalid_format", "esphome_device_id is required")
    dev = get_bound_esphome_device(hass, esp_dev_id)
    if dev is None:
        raise StudioCommandError("not_found", f"Unknown ESPHome device '{esp_dev_id}'")
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_ignored = live_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES) or []
        ignored = [
            str(x).strip()
            for x in (raw_ignored if isinstance(raw_ignored, list) else [])
            if str(x or "").strip()
        ]
        if esp_dev_id not in ignored:
            ignored = [*ignored, esp_dev_id][:MAX_IGNORED_DISCOVERED]
            await async_save_and_broadcast_global_config(
                hass, {CONF_IGNORED_DISCOVERED_DEVICES: ignored}
            )
    log_studio_event(hass, "INFO", "studio", f"Ignored discovered device '{device_title(dev)}'")


async def _cmd_unignore_discovered_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    esp_dev_id = str(body.get("esphome_device_id") or "").strip()
    if not esp_dev_id:
        raise StudioCommandError("invalid_format", "esphome_device_id is required")
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_ignored = live_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES) or []
        ignored = [
            str(x).strip()
            for x in (raw_ignored if isinstance(raw_ignored, list) else [])
            if str(x or "").strip() and str(x).strip() != esp_dev_id
        ]
        if ignored != raw_ignored:
            await async_save_and_broadcast_global_config(
                hass, {CONF_IGNORED_DISCOVERED_DEVICES: ignored}
            )


async def _cmd_remove_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    target_coord = find_by_subentry_id(
        iter_coordinators(hass), str(body.get("subentry_id") or "")
    )
    if target_coord is None:
        raise StudioCommandError(
            "not_found", "subentry_id of the Device to remove is missing or unknown"
        )
    removed_slug = target_coord.device_slug
    hass.config_entries.async_remove_subentry(target_coord.entry, target_coord.subentry_id)
    log_studio_event(hass, "INFO", "studio", f"Removed device '{removed_slug}' from Latter")
    extra["removed"] = True
    extra["removed_subentry_id"] = target_coord.subentry_id


def _validate_add_latter_device_request(
    hass: HomeAssistant, system_entry: Any, body: dict[str, Any]
) -> tuple[dr.DeviceEntry, dict[str, Any]]:
    esp_dev_id = str(body.get("esphome_device_id") or "").strip()
    if not esp_dev_id:
        raise StudioCommandError("invalid_format", "Choose a discovered Latter ESPHome Device")
    dev = get_bound_esphome_device(hass, esp_dev_id)
    if (
        dev is None
        or not is_esphome_device(hass, dev)
        or not is_latter_compatible_esphome_device(hass, dev)
    ):
        raise StudioCommandError(
            "not_latter_device", "Selected ESPHome device is not running Latter firmware"
        )
    if bound_elsewhere(system_entry, dev, device_unique_id(dev)):
        raise StudioCommandError(
            "already_configured", f"'{device_title(dev)}' is already managed in Latter"
        )
    raw_group = str(body.get("device_group") or "auto").strip() or "auto"
    if raw_group not in ("auto", DEFAULT_DEVICE_GROUP) and not any(
        g.get("id") == raw_group for g in get_device_groups(hass)
    ):
        raise StudioCommandError("not_found", f"Unknown Device Group '{raw_group}'")
    assigned_person = str(body.get("assigned_person") or "").strip()
    if assigned_person and (
        not assigned_person.startswith("person.")
        or (
            hass.states.get(assigned_person) is None
            and er.async_get(hass).async_get(assigned_person) is None
        )
    ):
        raise StudioCommandError("not_found", f"Unknown person entity '{assigned_person}'")
    init_data: dict[str, Any] = {CONF_ESPHOME_DEVICE_ID: dev.id, CONF_DEVICE_GROUP: raw_group}
    if assigned_person:
        init_data[CONF_ASSIGNED_PERSON] = assigned_person
    return dev, init_data


async def _cmd_add_latter_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    system_entries = hass.config_entries.async_entries(DOMAIN)
    if not system_entries:
        raise StudioCommandError("not_found", "Latter System entry is not set up")
    dev, init_data = _validate_add_latter_device_request(hass, system_entries[0], body)
    flow_res = await hass.config_entries.subentries.async_init(
        (system_entries[0].entry_id, SUBENTRY_DEVICE),
        context={"source": "user"},
        data=init_data,
    )
    if isinstance(flow_res, Mapping) and flow_res.get("type") != "create_entry":
        reason = str(
            flow_res.get("reason")
            or next(iter((flow_res.get("errors") or {}).values()), "")
            or "invalid_format"
        )
        raise StudioCommandError(reason, f"Could not add '{device_title(dev)}' ({reason})")
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_ignored = live_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES) or []
        if isinstance(raw_ignored, list) and dev.id in raw_ignored:
            cleaned_ignored = [
                str(x).strip()
                for x in raw_ignored
                if str(x or "").strip() and str(x).strip() != dev.id
            ]
            await async_save_and_broadcast_global_config(
                hass, {CONF_IGNORED_DISCOVERED_DEVICES: cleaned_ignored}
            )
    adopted_coord = next(
        (c for c in iter_coordinators(hass) if c.esphome_device_id == dev.id), None
    )
    extra["adopted_esphome_device_id"] = dev.id
    matched_sub = (
        adopted_coord.subentry_id
        if adopted_coord is not None
        else next(
            (
                sub.subentry_id
                for sub in system_entries[0].subentries.values()
                if sub.data.get(CONF_ESPHOME_DEVICE_ID) == dev.id
            ),
            "",
        )
    )
    if matched_sub:
        extra["adopted_subentry_id"] = matched_sub
    log_studio_event(hass, "INFO", "studio", f"Adopted Latter device '{device_title(dev)}'")


def _normalize_ble_target_key(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"(?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12}", s):
        return str(dr.format_mac(s)).upper()
    low = s.lower()
    return low[len(_IBEACON_PREFIX) :].strip() if low.startswith(_IBEACON_PREFIX) else low


def _ensure_ble_target_unique(
    hass: HomeAssistant, system_entry: Any, target_slug: str, target_addr: str
) -> None:
    norm_key = _normalize_ble_target_key(target_addr)
    for existing in iter_coordinators(hass):
        if existing.device_slug == target_slug:
            raise StudioCommandError(
                "already_configured", f"A Device named '{target_slug}' already exists"
            )
        existing_addr = str(getattr(existing, "ble_target_address", "") or "").strip()
        if norm_key and existing_addr and _normalize_ble_target_key(existing_addr) == norm_key:
            raise StudioCommandError(
                "already_configured",
                f"Target '{target_addr}' is already tracked by '{existing.device_slug}'",
            )
    for sub in system_entry.subentries.values():
        sub_addr = str(sub.data.get(CONF_BLE_TARGET_ADDRESS) or "").strip()
        if norm_key and sub_addr and _normalize_ble_target_key(sub_addr) == norm_key:
            raise StudioCommandError(
                "already_configured", f"Target '{target_addr}' is already configured in Latter"
            )


async def _cmd_add_ble_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    system_entries = hass.config_entries.async_entries(DOMAIN)
    if not system_entries:
        raise StudioCommandError("not_found", "Latter System entry is not set up")
    raw_name = str(body.get("name") or "").strip()
    target_addr = str(body.get("target_address") or "").strip()
    assigned_person = str(body.get("assigned_person") or "").strip()
    raw_cat = str(body.get(CONF_BLE_CATEGORY) or DEFAULT_BLE_CATEGORY).strip().lower()
    if raw_cat not in ("auto", "phone", "ble_tag"):
        raise StudioCommandError("invalid_format", f"Unknown BLE category '{raw_cat}'")
    target_slug = normalize_device_slug(raw_name) if raw_name else ""
    if not target_slug or target_slug == "esphome_device" or not target_addr:
        raise StudioCommandError("invalid_format", "A BLE tag needs a name and a target address")
    _ensure_ble_target_unique(hass, system_entries[0], target_slug, target_addr)
    flow_res = await hass.config_entries.subentries.async_init(
        (system_entries[0].entry_id, SUBENTRY_BLE_TAG),
        context={"source": "user"},
        data={
            "name": raw_name,
            CONF_BLE_TARGET_ADDRESS: target_addr,
            CONF_BLE_CATEGORY: raw_cat,
            CONF_ASSIGNED_PERSON: assigned_person,
        },
    )
    if isinstance(flow_res, Mapping) and flow_res.get("type") != "create_entry":
        reason = str(
            flow_res.get("reason")
            or next(iter((flow_res.get("errors") or {}).values()), "")
            or "invalid_format"
        )
        raise StudioCommandError(reason, f"Could not add BLE tag '{raw_name}' ({reason})")
    adopted_ble = next(
        (c for c in iter_coordinators(hass) if c.device_slug == target_slug), None
    )
    if adopted_ble is not None:
        extra["adopted_subentry_id"] = adopted_ble.subentry_id


__all__ = [
    "StudioCommandError",
    "_cmd_add_ble_device",
    "_cmd_add_latter_device",
    "_cmd_calibrate_area_illuminance",
    "_cmd_capture_ble_area_signature",
    "_cmd_check_system_updates",
    "_cmd_clear_ble_area_signature",
    "_cmd_clear_internal_logs",
    "_cmd_device_action",
    "_cmd_esphome_entity_action",
    "_cmd_ignore_discovered_device",
    "_cmd_remove_device",
    "_cmd_set_area_fusion",
    "_cmd_set_area_illuminance",
    "_cmd_set_ble_scanner_offset",
    "_cmd_unignore_discovered_device",
    "compute_illuminance_calibration_from_stats",
]
