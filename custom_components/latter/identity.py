"""Canonical ESPHome device identity, entity registry, and service resolution for Latter.

Every lookup starts from a bound ESPHome device ID (stored in the Device subentry), or from the
Device's stored MAC when the ESPHome device was re-created. Nothing is resolved from names,
slugs or entity_id patterns.
"""

from __future__ import annotations

import json
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DEFAULT_BLE_BEACON_UUID, DOMAIN, normalize_device_slug


LATTER_CONTRACT_ACTION_SUFFIXES: tuple[str, ...] = (
    "_set_browse_slots",
    "_set_area_slots",
    "_show_notification",
    "_latter_ping",
)


def _esphome_entry_for_device(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> Any | None:
    """Return the ESPHome config entry that owns `device`, or None if it isn't an ESPHome device."""
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


def esphome_node_name(
    hass: HomeAssistant, device_or_id: dr.DeviceEntry | str | None
) -> str:
    """Return the ESPHome node name (`device_name` of its ESPHome config entry), normalized for `esphome.<node>_*` services."""
    dev = get_bound_esphome_device(hass, device_or_id)
    if dev is None:
        return ""
    ce = _esphome_entry_for_device(hass, dev)
    if ce is None:
        return ""
    node = str(ce.data.get("device_name") or "").strip()
    return normalize_device_slug(node) if node else ""


def is_latter_compatible_esphome_device(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> bool:
    """Return True ONLY if the ESPHome device implements the Latter API contract or runs Latter firmware."""
    node = esphome_node_name(hass, device)
    if node:
        esphome_services = hass.services.async_services_for_domain("esphome")
        if any(f"{node}{sfx}" in esphome_services for sfx in LATTER_CONTRACT_ACTION_SUFFIXES):
            return True

    model_str = f"{device.model or ''} {device.sw_version or ''}".lower()
    if "latter" in model_str:
        return True
    return find_device_entity_by_suffix(
        hass, device, "update", ("_project_firmware",)
    ) is not None


def get_bound_esphome_device(
    hass: HomeAssistant, device_or_id: dr.DeviceEntry | str | None
) -> dr.DeviceEntry | None:
    """Return the ESPHome DeviceEntry for an ESPHome device ID, or for a Latter device ID (followed via `via_device_id`)."""
    dev_reg = dr.async_get(hass)
    if isinstance(device_or_id, dr.DeviceEntry):
        dev: dr.DeviceEntry | None = device_or_id
    elif isinstance(device_or_id, str) and device_or_id.strip():
        dev = dev_reg.async_get(device_or_id.strip())
    else:
        return None
    if dev is None:
        return None
    if (
        any(ident[0] == DOMAIN for ident in dev.identifiers)
        and not is_esphome_device(hass, dev)
        and dev.via_device_id
    ):
        return dev_reg.async_get(dev.via_device_id)
    return dev


def find_esphome_device_by_mac(
    hass: HomeAssistant, mac: str | None
) -> dr.DeviceEntry | None:
    """Return the ESPHome device whose network MAC connection equals `mac` exactly, or None."""
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
    """Resolve a Device's ESPHome device: the stored device ID, else the ESPHome device carrying the stored MAC."""
    dev = get_bound_esphome_device(hass, esphome_device_id)
    if dev is None:
        dev = find_esphome_device_by_mac(hass, mac)
    return dev.id if dev is not None else None


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
    if domain:
        return [e for e in entries if e.domain == domain]
    return entries


def find_device_entity_by_suffix(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    domain: str,
    suffixes: tuple[str, ...] | list[str],
) -> str | None:
    """Find an enabled entity on the bound device in `domain` matching one of `suffixes` in priority order."""
    entries = device_entities(hass, device_or_id, domain=domain)
    for sfx in suffixes:
        for entry in entries:
            if not sfx or entry.entity_id.endswith(sfx):
                return entry.entity_id
    return None


def esphome_service(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    action: str,
) -> str | None:
    """Resolve the registered `esphome.<node>_<action>` service name for a bound device, or None if unavailable."""
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
    """Read and merge the parsed JSON hardware manifest from `device_hello` and the bound device's manifest sensor."""
    merged: dict[str, Any] = {}
    manifest_ent_id = find_device_entity_by_suffix(
        hass,
        device_or_id,
        "sensor",
        ("_system_hardware_manifest", "_hardware_manifest"),
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

    if isinstance(cached_manifest, dict) and "w" in cached_manifest and "h" in cached_manifest:
        merged.update(cached_manifest)

    if merged:
        if "beacon" not in merged and int(merged.get("minor") or 0) > 0:
            merged["beacon"] = {
                "uuid": DEFAULT_BLE_BEACON_UUID,
                "major": 1,
                "minor": int(merged["minor"]),
            }
    return merged
