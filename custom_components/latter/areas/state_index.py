"""AreaStateIndex re-exports and Area/Device entity registry resolution helpers (`L1b`)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..const import CONF_ESPHOME_DEVICE_ID, DOMAIN, SUBENTRY_DEVICE
from ..hub_registry import (
    INDEXED_DOMAINS as INDEXED_DOMAINS,
    AreaStateIndex as AreaStateIndex,
    async_stop_area_state_index as async_stop_area_state_index,
    get_area_state_index as get_area_state_index,
    is_media_position_only_tick as is_media_position_only_tick,
)
from ..identity import resolve_bound_esphome_device_id

__all__ = [
    "INDEXED_DOMAINS",
    "AreaStateIndex",
    "async_stop_area_state_index",
    "get_area_state_index",
    "is_media_position_only_tick",
    "latter_bound_esphome_device_ids",
    "resolve_entity_area_id",
]


def resolve_entity_area_id(
    hass: HomeAssistant,
    entity_id: str,
    *,
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
) -> str | None:
    """Resolve the Home Assistant `area_id` for an entity (directly or via its parent device)."""
    if ent_reg is None and dev_reg is None:
        return get_area_state_index(hass).resolve_entity_area_id(entity_id)
    if ent_reg is None:
        ent_reg = er.async_get(hass)

    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return None
    if entry.area_id:
        return str(entry.area_id)
    if entry.device_id:
        if dev_reg is None:
            dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(entry.device_id)
        if device and device.area_id:
            return str(device.area_id)
    return None


def latter_bound_esphome_device_ids(hass: HomeAssistant) -> set[str]:
    """Return all Device Registry IDs belonging to Latter or its bound ESPHome devices."""
    out: set[str] = set()
    dev_reg = dr.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        for child_dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            out.add(child_dev.id)
        for sub in entry.subentries.values():
            if sub.subentry_type != SUBENTRY_DEVICE:
                continue
            dev_id = resolve_bound_esphome_device_id(
                hass,
                str(sub.data.get(CONF_ESPHOME_DEVICE_ID) or "") or None,
                str(sub.data.get("mac") or "") or None,
            )
            if dev_id:
                out.add(dev_id)
    return out
