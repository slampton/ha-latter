"""Home Assistant Diagnostics platform and PII/secret redaction pipeline for Latter."""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .hub import LatterSystemHub, get_latter_system
from .presence import get_all_scanners_diagnostic_map

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

REDACTED = "**REDACTED**"

REDACTED_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "alert_camera_url",
        "art_url",
        "ble_beacon_uuid",
        "ble_target_address",
        "hmac_secret_hex",
        "mac",
        "payload",
        "security_pin",
        "security_pin_hash",
        "system_ble_uuid",
        "wallpaper_url",
    }
)

TO_REDACT: set[str] = set(REDACTED_FIELD_KEYS)

_MAC_KEY_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_SIG_QUERY_RE = re.compile(r"([?&])sig=[^&#\s\"']+")


def _redact_string(val: str) -> str:
    """Strip resource HMAC signatures from URL strings while keeping path/shape structure."""
    if "sig=" in val:
        return _SIG_QUERY_RE.sub(rf"\1sig={REDACTED}", val)
    return val


def _redact_mac_dict_key(key: str) -> str:
    """Replace raw MAC address dictionary keys with a deterministic non-reversible short digest."""
    if _MAC_KEY_RE.match(key):
        norm = key.replace("-", ":").upper()
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]
        return f"mac_{digest}"
    return key


def sanitize_diagnostics_payload(obj: Any, *, parent_key: str = "") -> Any:
    """Recursively strip HMAC signatures, v3 payloads, MAC keys, PINs, and calendar PII from diagnostics."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for raw_k, raw_v in obj.items():
            k_str = str(raw_k)
            if k_str in REDACTED_FIELD_KEYS:
                out[k_str] = REDACTED
                continue
            safe_k = _redact_mac_dict_key(k_str)
            if (
                parent_key == "calendar_agenda"
                and k_str == "records"
                and isinstance(raw_v, list)
            ):
                sanitized_records: list[Any] = []
                for rec in raw_v:
                    if isinstance(rec, (list, tuple)) and len(rec) >= 4:
                        sanitized_records.append(
                            [str(rec[0]), REDACTED, REDACTED, str(rec[3])]
                        )
                    else:
                        sanitized_records.append(REDACTED)
                out[safe_k] = sanitized_records
                continue
            out[safe_k] = sanitize_diagnostics_payload(raw_v, parent_key=k_str)
        return out
    if isinstance(obj, (list, tuple)):
        return [sanitize_diagnostics_payload(item, parent_key=parent_key) for item in obj]
    if isinstance(obj, str):
        return _redact_string(obj)
    return obj


def _build_coordinator_diagnostics(coordinator: LatterCoordinator) -> dict[str, Any]:
    """Build diagnostic snapshot for a single LatterCoordinator."""
    cur_area_state, cur_area_attrs = coordinator.get_current_area_and_distance()
    if coordinator.is_ble_tag:
        sensors_diag: dict[str, Any] = {
            "current_area": {"state": cur_area_state, "attributes": cur_area_attrs},
        }
    else:
        media_state, media_attrs = coordinator.get_active_media_payload()
        area_state, area_attrs = coordinator.get_area_context_payload()
        remote_state, remote_attrs = coordinator.get_remote_config_payload()
        sensors_diag = {
            "current_area": {"state": cur_area_state, "attributes": cur_area_attrs},
            "active_media": {"state": media_state, "attributes": media_attrs},
            "area_context": {"state": area_state, "attributes": area_attrs},
            "remote_config": {"state": remote_state, "attributes": remote_attrs},
            "weather_forecast": {
                "records": [list(rec) for rec in coordinator.forecast_records],
                "attributes": coordinator.weather_attributes,
            },
            "calendar_agenda": {
                "records": [list(rec) for rec in coordinator.calendar_records],
                "event_count": len(coordinator.calendar_events),
            },
        }
    return {
        "subentry_id": coordinator.subentry_id,
        "title": coordinator.device_title,
        "device_data": coordinator.device_data,
        "runtime": {
            "device_slug": coordinator.device_slug,
            "kind": "ble_tag" if coordinator.is_ble_tag else "device",
            "has_display": coordinator.has_display,
            "is_roaming": coordinator.is_roaming_device,
            "is_wearable": coordinator.is_wearable,
            "display_shape": coordinator.display_shape,
            "list_slot_capacity": coordinator.list_slot_capacity,
            "card_slot_capacity": coordinator.card_slot_capacity,
            "area_categories": coordinator.area_categories_csv,
            "home_categories": coordinator.home_categories_csv,
            "local_speaker": coordinator.local_speaker,
            "active_speaker": coordinator.active_speaker,
            "last_speaker": coordinator.last_speaker,
            "active_area_id": coordinator.active_area_id,
            "active_remote_slot": coordinator.active_remote_slot,
            "volume_overrides": coordinator.volume_overrides,
            "last_area_follow_write": coordinator.last_area_follow_write,
            "has_security_pin": coordinator.has_security_pin,
        },
        "device_health": coordinator.last_device_health,
        "sensors": sensors_diag,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[LatterSystemHub]
) -> dict[str, Any]:
    """Return diagnostics for the Latter System hub entry and all its device subentries."""
    runtime = getattr(entry, "runtime_data", None)
    sys_obj = runtime if isinstance(runtime, LatterSystemHub) else get_latter_system(hass)
    if sys_obj is None:
        return {
            "entry_data": async_redact_data(
                sanitize_diagnostics_payload(dict(entry.data)), TO_REDACT
            )
        }

    payload: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
            "subentry_count": len(entry.subentries),
        },
        "system_config": dict(sys_obj.config),
        "ble_scanners": get_all_scanners_diagnostic_map(hass),
        "devices": {
            sub_id: _build_coordinator_diagnostics(coord)
            for sub_id, coord in sys_obj.coordinators.items()
        },
    }
    return async_redact_data(sanitize_diagnostics_payload(payload), TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[LatterSystemHub], device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for an individual Latter device or the Latter System service device."""
    from .coordinator import resolve_coordinator

    coord = resolve_coordinator(hass, device.id)
    if coord is not None:
        return async_redact_data(
            sanitize_diagnostics_payload(_build_coordinator_diagnostics(coord)),
            TO_REDACT,
        )
    return await async_get_config_entry_diagnostics(hass, entry)
