"""Canonical ESPHome device identity, entity registry, and service resolution for Latter."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_DEVICE_SLUG, CONF_ESPHOME_DEVICE_ID, DOMAIN, normalize_device_slug


def get_bound_esphome_device(
    hass: HomeAssistant,
    entry_or_device_id: ConfigEntry | str | None,
    fallback_slug: str = "",
) -> dr.DeviceEntry | None:
    """Resolve the bound ESPHome DeviceEntry from a ConfigEntry or device_id without substring guessing."""
    dev_reg = dr.async_get(hass)
    explicit_id = ""
    slug = normalize_device_slug(fallback_slug) if fallback_slug else ""

    if isinstance(entry_or_device_id, ConfigEntry):
        explicit_id = str(
            entry_or_device_id.options.get(CONF_ESPHOME_DEVICE_ID)
            or entry_or_device_id.data.get(CONF_ESPHOME_DEVICE_ID)
            or ""
        ).strip()
        if not slug:
            raw_slug = str(
                entry_or_device_id.data.get(CONF_DEVICE_SLUG)
                or entry_or_device_id.title
                or ""
            ).strip()
            if raw_slug:
                slug = normalize_device_slug(raw_slug)
    elif isinstance(entry_or_device_id, str):
        explicit_id = entry_or_device_id.strip()

    if explicit_id:
        dev = dev_reg.async_get(explicit_id)
        if dev is not None:
            # If the caller passed a Latter DeviceEntry ID, follow via_device_id to the ESPHome device
            is_latter_only = any(ident[0] == DOMAIN for ident in dev.identifiers) and not any(
                (ce := hass.config_entries.async_get_entry(cid)) is not None and ce.domain == "esphome"
                for cid in dev.config_entries
            )
            if is_latter_only and dev.via_device_id:
                via_dev = dev_reg.async_get(dev.via_device_id)
                if via_dev is not None:
                    return via_dev
            return dev

    if not slug:
        return None

    ent_reg = er.async_get(hass)
    manifest_ent = ent_reg.async_get(f"sensor.{slug}_system_hardware_manifest")
    if manifest_ent is not None and manifest_ent.device_id:
        dev = dev_reg.async_get(manifest_ent.device_id)
        if dev is not None:
            return dev

    for dev in dev_reg.devices.values():
        is_esphome = any(
            (ce := hass.config_entries.async_get_entry(cid)) is not None
            and ce.domain == "esphome"
            for cid in dev.config_entries
        )
        if not is_esphome:
            continue
        for cid in dev.config_entries:
            ce = hass.config_entries.async_get_entry(cid)
            if ce is not None and ce.domain == "esphome":
                node_name = str(ce.data.get("device_name") or ce.title or "")
                if node_name and normalize_device_slug(node_name) == slug:
                    return dev
        if dev.name and normalize_device_slug(dev.name) == slug:
            return dev

    return None


def device_entities(
    hass: HomeAssistant,
    device_id: str | None,
    domain: str | None = None,
) -> list[er.RegistryEntry]:
    """Return all enabled entity registry entries belonging to the bound ESPHome device."""
    if not device_id:
        return []
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    target_id = device_id
    dev = dev_reg.async_get(device_id)
    if dev is not None and dev.via_device_id and any(i[0] == DOMAIN for i in dev.identifiers):
        target_id = dev.via_device_id

    entries = [
        e
        for e in er.async_entries_for_device(ent_reg, target_id)
        if not e.disabled_by
    ]
    if domain:
        return [e for e in entries if e.domain == domain]
    return entries


def find_device_entity_by_suffix(
    hass: HomeAssistant,
    device_id: str | None,
    domain: str,
    suffixes: tuple[str, ...],
) -> str | None:
    """Find an enabled entity on the bound device in `domain` matching one of `suffixes` in priority order."""
    entries = device_entities(hass, device_id, domain=domain)
    if not entries:
        return None
    for sfx in suffixes:
        for entry in entries:
            if not sfx or entry.entity_id.endswith(sfx):
                return entry.entity_id
    return entries[0].entity_id


def esphome_node_name(
    hass: HomeAssistant,
    device_id: str | None,
    fallback_slug: str = "",
) -> str:
    """Resolve the canonical underscore-normalized ESPHome node name for `esphome.<node>_*` service calls."""
    if device_id:
        dev = get_bound_esphome_device(hass, device_id, fallback_slug=fallback_slug)
        if dev is not None:
            for cid in dev.config_entries:
                ce = hass.config_entries.async_get_entry(cid)
                if ce is not None and ce.domain == "esphome":
                    dev_name = str(ce.data.get("device_name") or "").strip()
                    if dev_name:
                        return normalize_device_slug(dev_name)
            for entry in device_entities(hass, dev.id, domain="sensor"):
                if entry.entity_id.endswith("_system_hardware_manifest"):
                    stem = entry.entity_id.removeprefix("sensor.").removesuffix(
                        "_system_hardware_manifest"
                    )
                    if stem:
                        return normalize_device_slug(stem)
            if dev.name:
                return normalize_device_slug(dev.name)
    return normalize_device_slug(fallback_slug) if fallback_slug else ""


def esphome_service(
    hass: HomeAssistant,
    device_id: str | None,
    action: str,
    fallback_slug: str = "",
) -> str | None:
    """Resolve the registered `esphome.<node>_<action>` service name for a bound device, or None if unavailable."""
    node = esphome_node_name(hass, device_id, fallback_slug=fallback_slug)
    if not node:
        return None
    svc = f"{node}_{action}"
    if hass.services.has_service("esphome", svc):
        return svc
    if fallback_slug:
        alt = f"{normalize_device_slug(fallback_slug)}_{action}"
        if hass.services.has_service("esphome", alt):
            return alt
    return None


def get_device_mac(
    hass: HomeAssistant,
    device_id: str | None,
    fallback_slug: str = "",
) -> str | None:
    """Extract the formatted network/BLE MAC address from a bound ESPHome DeviceEntry."""
    dev = get_bound_esphome_device(hass, device_id, fallback_slug=fallback_slug)
    if dev is None:
        return None
    for conn_type, conn_val in dev.connections:
        if conn_type in (dr.CONNECTION_NETWORK_MAC, "bluetooth") and conn_val:
            return dr.format_mac(conn_val)
    for _domain, ident_val in dev.identifiers:
        cleaned = str(ident_val).strip()
        if len(cleaned) in (12, 17) and all(
            c in "0123456789abcdefABCDEF:-" for c in cleaned
        ):
            return dr.format_mac(cleaned)
    return None


def read_device_hardware_manifest(
    hass: HomeAssistant,
    device_id: str | None,
    fallback_slug: str = "",
    cached_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read the parsed JSON hardware manifest from the bound device's System: Hardware Manifest sensor."""
    manifest_ent_id = find_device_entity_by_suffix(
        hass,
        device_id,
        "sensor",
        ("_system_hardware_manifest", "_hardware_manifest"),
    )
    if not manifest_ent_id and fallback_slug:
        slug = normalize_device_slug(fallback_slug)
        manifest_ent_id = f"sensor.{slug}_system_hardware_manifest"

    if manifest_ent_id:
        st = hass.states.get(manifest_ent_id)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            try:
                parsed = json.loads(st.state)
                if isinstance(parsed, dict) and "w" in parsed and "h" in parsed:
                    return parsed
            except (ValueError, TypeError):
                pass

    if isinstance(cached_manifest, dict) and "w" in cached_manifest and "h" in cached_manifest:
        return dict(cached_manifest)
    return {}
