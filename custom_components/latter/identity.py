"""Canonical ESPHome device identity, hardware traits, and unbound device discovery (`L1b`)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import json
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .config_defaults import compute_hardware_defaults
from .const import (
    CONF_DEVICE_GROUP,
    CONF_ESPHOME_DEVICE_ID,
    CONF_IGNORED_DISCOVERED_DEVICES,
    DATA_GLOBAL_CONFIG,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    SUBENTRY_DEVICE,
    normalize_device_slug,
)
from .protocol_specs import humanize_device_model_label

_DEFAULT_DISPLAY_DIM: Final = 466
_DEFAULT_ALIGNED_DIM: Final = 464
_MIN_VIDEO_DIM: Final = 64
_MACROBLOCK_ALIGN: Final = 16
_MAX_VIDEO_FPS_CAP: Final = 15

# ---------------------------------------------------------------------------
# Registry Iteration & Bound Identity Helpers
# ---------------------------------------------------------------------------


def iter_devices(dev_reg: dr.DeviceRegistry) -> Iterable[dr.DeviceEntry]:
    """Iterate active `DeviceEntry` objects in the Home Assistant `DeviceRegistry`."""
    return dev_reg.devices


_iter_devices = iter_devices


def iter_entities(ent_reg: er.EntityRegistry) -> Iterable[er.RegistryEntry]:
    """Iterate active `RegistryEntry` objects in the Home Assistant `EntityRegistry`."""
    return ent_reg.entities.values()


_iter_entities = iter_entities


def device_mac(dev: dr.DeviceEntry) -> str:
    """Return the ESPHome device's network MAC connection, formatted, or `''`."""
    for ctype, cval in dev.connections:
        if ctype == dr.CONNECTION_NETWORK_MAC and cval:
            return str(dr.format_mac(str(cval)))
    return ""


_device_mac = device_mac


def device_unique_id(dev: dr.DeviceEntry) -> str:
    """Return the subentry `unique_id` for an ESPHome device: its MAC, else its device ID."""
    mac = device_mac(dev)
    return f"{DOMAIN}_{mac}" if mac else f"{DOMAIN}_{dev.id}"


_device_unique_id = device_unique_id


def ble_unique_id(slug: str) -> str:
    """Return the subentry `unique_id` for a Studio-adopted BLE tag (no ESPHome device)."""
    return f"{DOMAIN}_ble_{slug}"


_ble_unique_id = ble_unique_id


def device_title(dev: dr.DeviceEntry) -> str:
    """Return the friendly name of the bound ESPHome device."""
    return str(dev.name_by_user or dev.name or dev.id).strip()


_device_title = device_title


def bound_elsewhere(
    entry: ConfigEntry[Any],
    dev: dr.DeviceEntry,
    target_uid: str,
    skip_subentry_id: str = "",
) -> bool:
    """Return True if another Device subentry already binds this ESPHome device."""
    for sub in entry.subentries.values():
        if sub.subentry_id == skip_subentry_id:
            continue
        if (
            sub.unique_id == target_uid
            or sub.data.get(CONF_ESPHOME_DEVICE_ID) == dev.id
        ):
            return True
    return False


_bound_elsewhere = bound_elsewhere


# ---------------------------------------------------------------------------
# Hardware Manifest Traits
# ---------------------------------------------------------------------------


def manifest_flag(manifest: Mapping[str, Any], key: str) -> int | None:
    """Return an integer hardware-manifest trait, or `None` when missing or malformed."""
    if key not in manifest:
        return None
    raw = manifest[key]
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def manifest_is_roaming(manifest: Mapping[str, Any]) -> bool:
    """Return True for roaming hardware: `stationary == 0`, or `wearable == 1`."""
    return (
        manifest_flag(manifest, "stationary") == 0
        or manifest_flag(manifest, "wearable") == 1
    )


def manifest_is_wearable(manifest: Mapping[str, Any]) -> bool:
    """Return True only when the manifest reports `wearable == 1`."""
    return manifest_flag(manifest, "wearable") == 1


def manifest_has_display(manifest: Mapping[str, Any]) -> bool:
    """Return False only when the manifest reports `display == 0` (a headless node)."""
    return manifest_flag(manifest, "display") != 0


def manifest_has_mic(manifest: Mapping[str, Any]) -> bool:
    """Return False only when the manifest reports `mic == 0`."""
    return manifest_flag(manifest, "mic") != 0


def manifest_has_speaker(manifest: Mapping[str, Any]) -> bool:
    """Return False only when the manifest reports `spk == 0`."""
    return manifest_flag(manifest, "spk") != 0


def manifest_has_audio(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware exposes a microphone or speaker."""
    return manifest_has_mic(manifest) or manifest_has_speaker(manifest)


def manifest_has_imu(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware exposes an active motion IMU (non-stationary `imu == 1`)."""
    if not manifest:
        return True
    return (
        manifest_flag(manifest, "imu") == 1
        and manifest_flag(manifest, "stationary") != 1
    )


def manifest_has_battery(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware has a rechargeable battery (`battery == 1` or pre-hello)."""
    if not manifest:
        return True
    return manifest_flag(manifest, "battery") == 1


def manifest_is_round(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware display shape is circular."""
    if not manifest_has_display(manifest):
        return False
    return str(manifest.get("shape") or "circle").strip().lower() != "square"


def manifest_video_caps(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Parse hardware manifest `video` capabilities with trait-based fallback."""
    has_disp = manifest_has_display(manifest)
    has_batt = manifest_has_battery(manifest)
    chip = str(manifest.get("chip") or "").strip().upper()
    is_p4 = chip == "ESP32-P4" or "P4" in chip

    raw_video = manifest.get("video")
    default_w = (int(manifest.get("w") or _DEFAULT_DISPLAY_DIM) & ~15) if has_disp else 0
    default_h = (int(manifest.get("h") or _DEFAULT_DISPLAY_DIM) & ~15) if has_disp else 0
    if isinstance(raw_video, Mapping):
        hw_jpeg = has_disp and bool(int(raw_video.get("hw_jpeg") or 0))
        raw_max_w = raw_video.get("max_w")
        raw_max_h = raw_video.get("max_h")
        max_w = int(raw_max_w) if raw_max_w is not None else default_w
        max_h = int(raw_max_h) if raw_max_h is not None else default_h
        max_fps = int(
            raw_video.get("max_fps") or ((10 if has_batt else 15) if hw_jpeg else 5)
        )
        grid_fps = int(
            raw_video.get("grid_fps") or ((5 if has_batt else 8) if hw_jpeg else 2)
        )
    else:
        hw_jpeg = has_disp and is_p4
        max_w = default_w
        max_h = default_h
        max_fps = (10 if has_batt else 15) if is_p4 else 5
        grid_fps = (5 if has_batt else 8) if is_p4 else 2

    if not has_disp:
        max_w = 0
        max_h = 0
    else:
        max_w = (
            max(_MIN_VIDEO_DIM, (max_w // _MACROBLOCK_ALIGN) * _MACROBLOCK_ALIGN)
            if max_w > 0
            else _DEFAULT_ALIGNED_DIM
        )
        max_h = (
            max(_MIN_VIDEO_DIM, (max_h // _MACROBLOCK_ALIGN) * _MACROBLOCK_ALIGN)
            if max_h > 0
            else _DEFAULT_ALIGNED_DIM
        )

    return {
        "hw_jpeg": hw_jpeg,
        "max_w": max_w,
        "max_h": max_h,
        "max_fps": max(1, min(_MAX_VIDEO_FPS_CAP, max_fps)),
        "grid_fps": max(1, min(_MAX_VIDEO_FPS_CAP, grid_fps)),
    }


def manifest_supports_hw_jpeg(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware manifest reports a hardware JPEG decoder."""
    return bool(manifest_video_caps(manifest)["hw_jpeg"])


# ---------------------------------------------------------------------------
# Bound ESPHome Device Identity & Service Resolution
# ---------------------------------------------------------------------------

LATTER_CONTRACT_ACTION_SUFFIXES: Final[tuple[str, ...]] = (
    "_latter_push_v3",
    "_latter_device_command",
    "_latter_set_slots",
    "_latter_set_music_lyrics",
    "_latter_set_calendar_view",
    "_latter_show_notification",
    "_latter_ping",
    "_latter_set_beacon_uuid",
    "_latter_factory_reset",
)


def _esphome_entry_for_device(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> ConfigEntry[Any] | None:
    """Return the ESPHome config entry that owns `device`, or `None` if it isn't an ESPHome device."""
    dev_reg = dr.async_get(hass)
    for ce in hass.config_entries.async_entries("esphome"):
        if any(
            d.id == device.id
            for d in dr.async_entries_for_config_entry(dev_reg, ce.entry_id)
        ):
            return ce
    return None


def is_esphome_device(hass: HomeAssistant, device: dr.DeviceEntry) -> bool:
    """Return True if `device` belongs to an ESPHome config entry."""
    return _esphome_entry_for_device(hass, device) is not None


def get_bound_esphome_device(
    hass: HomeAssistant, device_or_id: dr.DeviceEntry | str | None
) -> dr.DeviceEntry | None:
    """Return the ESPHome `DeviceEntry` for an ESPHome device ID, or follow `via_device_id`."""
    dev_reg = dr.async_get(hass)
    if isinstance(device_or_id, dr.DeviceEntry):
        dev: dr.DeviceEntry | None = device_or_id
    elif isinstance(device_or_id, str) and device_or_id.strip():
        got = dev_reg.async_get(device_or_id.strip())
        dev = got if isinstance(got, dr.DeviceEntry) else None
    else:
        return None
    if dev is None:
        return None
    if (
        any(ident[0] == DOMAIN for ident in dev.identifiers)
        and not is_esphome_device(hass, dev)
        and dev.via_device_id
    ):
        via = dev_reg.async_get(dev.via_device_id)
        return via if isinstance(via, dr.DeviceEntry) else None
    return dev


def esphome_node_name(
    hass: HomeAssistant, device_or_id: dr.DeviceEntry | str | None
) -> str:
    """Return the ESPHome node name (`device_name` of its ESPHome config entry), normalized."""
    dev = get_bound_esphome_device(hass, device_or_id)
    if dev is None:
        return ""
    ce = _esphome_entry_for_device(hass, dev)
    if ce is None:
        return ""
    node = str(ce.data.get("device_name") or "").strip()
    return normalize_device_slug(node) if node else ""


def device_entities(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    domain: str | None = None,
    include_disabled: bool = False,
) -> list[er.RegistryEntry]:
    """Return all entity registry entries belonging to the bound ESPHome device."""
    dev = get_bound_esphome_device(hass, device_or_id)
    if dev is None:
        return []
    entries = [
        e
        for e in er.async_entries_for_device(er.async_get(hass), dev.id)
        if include_disabled or not e.disabled_by
    ]
    return [e for e in entries if e.domain == domain] if domain else entries


def find_device_entity_by_suffix(  # noqa: PLR0913, PLR0917
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    domain: str,
    suffixes: tuple[str, ...] | list[str],
    original_names: tuple[str, ...] = (),
    unique_id_suffixes: tuple[str, ...] = (),
) -> str | None:
    """Find an enabled entity on the bound device in `domain` matching `suffixes` or `original_names`."""
    entries = device_entities(hass, device_or_id, domain=domain)
    for sfx in suffixes:
        for entry in entries:
            if not sfx or entry.entity_id.endswith(sfx):
                return str(entry.entity_id)
    for orig in original_names:
        for entry in entries:
            if (entry.original_name or "") == orig:
                return str(entry.entity_id)
    for uid_sfx in unique_id_suffixes:
        for entry in entries:
            if uid_sfx and (entry.unique_id or "").endswith(uid_sfx):
                return str(entry.entity_id)
    return None


def is_latter_compatible_esphome_device(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> bool:
    """Return True ONLY if the ESPHome device implements the Latter API contract or runs Latter firmware."""
    node = esphome_node_name(hass, device)
    if node:
        esphome_services = hass.services.async_services_for_domain("esphome")
        if any(
            f"{node}{sfx}" in esphome_services
            for sfx in LATTER_CONTRACT_ACTION_SUFFIXES
        ):
            return True

    model_str = f"{device.model or ''} {device.sw_version or ''}".lower()
    if "latter" in model_str:
        return True
    return (
        find_device_entity_by_suffix(hass, device, "update", ("_project_firmware",))
        is not None
    )


def find_esphome_device_by_mac(
    hass: HomeAssistant, mac: str | None
) -> dr.DeviceEntry | None:
    """Return the ESPHome device whose network MAC connection equals `mac` exactly, or `None`."""
    if not mac:
        return None
    target = (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
    dev_reg = dr.async_get(hass)
    for ce in hass.config_entries.async_entries("esphome"):
        for dev in dr.async_entries_for_config_entry(dev_reg, ce.entry_id):
            if target in dev.connections:
                return dev
    return None


def resolve_bound_esphome_device_id(
    hass: HomeAssistant, esphome_device_id: str | None, mac: str | None
) -> str | None:
    """Resolve a Device's ESPHome device: stored device ID, else stored MAC."""
    dev = get_bound_esphome_device(hass, esphome_device_id)
    if dev is None:
        dev = find_esphome_device_by_mac(hass, mac)
    return dev.id if dev is not None else None


def esphome_service(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    action: str,
) -> str | None:
    """Resolve the registered `esphome.<node>_<action>` service name for a bound device, or `None`."""
    node = esphome_node_name(hass, device_or_id)
    if not node:
        return None
    svc = f"{node}_{action}"
    return svc if hass.services.has_service("esphome", svc) else None


def read_device_hardware_manifest(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    cached_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read and merge the parsed JSON hardware manifest from `device_hello` and the manifest sensor."""
    merged: dict[str, Any] = {}
    manifest_ent_id = find_device_entity_by_suffix(
        hass,
        device_or_id,
        "sensor",
        ("_system_hardware_manifest",),
        original_names=("System: Hardware Manifest",),
        unique_id_suffixes=("/text_sensor/System: Hardware Manifest",),
    )
    if manifest_ent_id:
        st = hass.states.get(manifest_ent_id)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            try:
                parsed = json.loads(st.state)
                if isinstance(parsed, dict) and "w" in parsed and "h" in parsed:
                    merged.update(parsed)
            except (ValueError, TypeError):
                pass

    if isinstance(cached_manifest, dict) and (
        ("w" in cached_manifest and "h" in cached_manifest)
        or "sdk" in cached_manifest
    ):
        merged.update(cached_manifest)

    return merged


# ---------------------------------------------------------------------------
# Unbound Latter ESPHome Discovery Queries (`L1b`)
# ---------------------------------------------------------------------------


def get_ignored_discovered_device_ids(hass: HomeAssistant) -> set[str]:
    """Return the set of `esphome_device_id` values marked ignored in System config."""
    raw_cfg = (hass.data.get(DOMAIN) or {}).get(DATA_GLOBAL_CONFIG)
    if not isinstance(raw_cfg, dict):
        return set()
    raw_list = raw_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES)
    if not isinstance(raw_list, (list, tuple)):
        return set()
    return {str(x).strip() for x in raw_list if str(x or "").strip()}


def _has_ble_beacon_entity_or_manifest(
    hass: HomeAssistant, dev: dr.DeviceEntry, manifest: Mapping[str, Any]
) -> bool:
    if isinstance(manifest.get("beacon"), Mapping):
        return True
    ent_reg = er.async_get(hass)
    return any(
        e.entity_id.endswith("_ble_radio_active")
        for e in er.async_entries_for_device(ent_reg, dev.id)
    )


def get_discovered_latter_devices(
    hass: HomeAssistant, *, only_ignored: bool = False
) -> list[dict[str, Any]]:
    """Return unbound ESPHome devices running Latter firmware ready for Studio adoption (or ignored)."""
    configured_ids: set[str] = set()
    configured_uids: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        for sub in entry.subentries.values():
            if sub.subentry_type != SUBENTRY_DEVICE:
                continue
            dev_id = str(sub.data.get(CONF_ESPHOME_DEVICE_ID) or "")
            if dev_id:
                configured_ids.add(dev_id)
            if sub.unique_id:
                configured_uids.add(str(sub.unique_id))

    ignored_ids = get_ignored_discovered_device_ids(hass)
    area_reg = ar.async_get(hass)
    candidates = [
        dev
        for dev in iter_devices(dr.async_get(hass))
        if dev.id not in configured_ids
        and device_unique_id(dev) not in configured_uids
        and ((dev.id in ignored_ids) if only_ignored else (dev.id not in ignored_ids))
        and is_esphome_device(hass, dev)
        and is_latter_compatible_esphome_device(hass, dev)
    ]
    candidates.sort(key=lambda d: str(d.name_by_user or d.name or d.id).lower())

    out: list[dict[str, Any]] = []
    for dev in candidates:
        manifest = read_device_hardware_manifest(hass, dev.id)
        esp_area_id = str(dev.area_id or "").strip()
        hw_defs = compute_hardware_defaults(
            manifest,
            esp_area_id=esp_area_id,
            has_native_slots=bool(esphome_service(hass, dev.id, "latter_set_slots")),
            has_ble_beacon=_has_ble_beacon_entity_or_manifest(hass, dev, manifest),
        )
        raw_model = str(dev.model or "").strip()
        model_label = humanize_device_model_label(
            raw_model, manifest, fallback="Latter ESPHome Device"
        )
        area_obj = area_reg.async_get_area(esp_area_id) if esp_area_id else None
        out.append(
            {
                "esphome_device_id": dev.id,
                "node_name": esphome_node_name(hass, dev),
                "title": device_title(dev),
                "model_label": model_label,
                "area_name": area_obj.name if area_obj else "",
                "default_group": str(
                    hw_defs.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP
                ),
            }
        )
    return out
