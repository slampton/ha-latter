"""Home Assistant Diagnostics platform and PII/secret redaction pipeline for Latter."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .coordinator import LatterCoordinator, resolve_coordinator
from .hub_registry import LatterSystemHub, get_latter_system
from .presence.ble_registry import get_all_scanners_diagnostic_map

REDACTED = "**REDACTED**"

REDACTED_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "alert_camera_url",
        "art_url",
        "ble_beacon_uuid",
        "ble_target_address",
        "camera_snapshot_url",
        "camera_stream_url",
        "hmac_secret_hex",
        "mac",
        "payload",
        "screensaver_photo_url",
        "security_pin",
        "security_pin_hash",
        "system_ble_uuid",
        "wallpaper_url",
    }
)

TO_REDACT: set[str] = set(REDACTED_FIELD_KEYS)

_MAC_KEY_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_MAC_HEX12_RE = re.compile(r"^[0-9A-Fa-f]{12}$")
_MAC_INLINE_RE = re.compile(
    r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])"
)
_SIG_QUERY_RE = re.compile(r"([?&])sig=[^&#\s\"']+")
_MIN_CALENDAR_RECORD_FIELDS = 4


def _mac_digest_token(raw_mac: str) -> str:
    """Return deterministic non-reversible `mac_<8hex>` digest for a MAC string."""
    clean = raw_mac.replace("-", "").replace(":", "").upper()
    norm = ":".join(clean[i : i + 2] for i in range(0, 12, 2))
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]
    return f"mac_{digest}"


def _redact_string(val: str) -> str:
    """Strip resource HMAC signatures and inline MAC addresses from diagnostic strings."""
    out = _SIG_QUERY_RE.sub(rf"\1sig={REDACTED}", val) if "sig=" in val else val
    if ":" in out or "-" in out:
        out = _MAC_INLINE_RE.sub(lambda m: _mac_digest_token(m.group(0)), out)
    return out


def _redact_mac_dict_key(key: str, *, parent_key: str = "") -> str:
    """Replace raw MAC address dictionary keys with a deterministic non-reversible short digest."""
    if _MAC_KEY_RE.match(key):
        return _mac_digest_token(key)
    if parent_key in ("ble_scanner_offsets", "scanners", "ble_scanners") and _MAC_HEX12_RE.match(key):
        return _mac_digest_token(key)
    if ":" in key or "-" in key:
        return _MAC_INLINE_RE.sub(lambda m: _mac_digest_token(m.group(0)), key)
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
            safe_k = _redact_mac_dict_key(k_str, parent_key=parent_key)
            if (
                parent_key == "calendar_agenda"
                and k_str == "records"
                and isinstance(raw_v, list)
            ):
                out[safe_k] = [
                    [str(rec[0]), REDACTED, REDACTED, str(rec[3])]
                    if isinstance(rec, (list, tuple))
                    and len(rec) >= _MIN_CALENDAR_RECORD_FIELDS
                    else REDACTED
                    for rec in raw_v
                ]
                continue
            out[safe_k] = sanitize_diagnostics_payload(raw_v, parent_key=k_str)
        return out
    if isinstance(obj, (list, tuple)):
        return [sanitize_diagnostics_payload(item, parent_key=parent_key) for item in obj]
    if isinstance(obj, str):
        return _redact_string(obj)
    return obj


def _build_coordinator_diagnostics(coordinator: LatterCoordinator) -> dict[str, Any]:
    """Build diagnostic snapshot for a single `LatterCoordinator`."""
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
            "core_rev": coordinator.core_rev,
            "firmware_outdated": coordinator.firmware_outdated,
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
        "device_telemetry": coordinator.device_telemetry,
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
    redacted: dict[str, Any] = async_redact_data(
        sanitize_diagnostics_payload(payload), TO_REDACT
    )
    return redacted


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[LatterSystemHub], device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for an individual Latter device or the Latter System service device."""
    coord = resolve_coordinator(hass, device.id)
    if coord is not None:
        dev_redacted: dict[str, Any] = async_redact_data(
            sanitize_diagnostics_payload(_build_coordinator_diagnostics(coord)),
            TO_REDACT,
        )
        return dev_redacted
    return await async_get_config_entry_diagnostics(hass, entry)
