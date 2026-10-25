"""Home Assistant Repairs & Configuration Health Monitor for Latter."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .ble_engine import get_ble_proxy_area_ids
from .const import (
    CONF_ALARM_ENTITY,
    CONF_DEFAULT_SPEAKER,
    CONF_PRESENCE_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)
from .coordinator import LatterCoordinator


def _entity_exists_in_ha(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True if an entity exists in either the state machine or the Entity Registry (even if powered off/unavailable)."""
    if not entity_id:
        return True
    if hass.states.get(entity_id) is not None:
        return True
    ent_reg = er.async_get(hass)
    return ent_reg.async_get(entity_id) is not None


@callback
def async_audit_coordinator_health(
    hass: HomeAssistant, coordinator: LatterCoordinator
) -> list[dict[str, str]]:
    """Audit mapped entities and BLE proxy availability, updating HA Repairs and returning active warnings for the Web Studio."""
    entry_id = coordinator.entry.entry_id
    slug = coordinator.device_slug
    warnings: list[dict[str, str]] = []

    # 1. Check mapped entities (Weather, Alarm, Default Speaker, External Presence)
    checked_keys: tuple[tuple[str, str], ...] = (
        (CONF_WEATHER_ENTITY, "Weather Provider"),
        (CONF_ALARM_ENTITY, "Home Security Alarm"),
        (CONF_DEFAULT_SPEAKER, "Default Speaker"),
        (CONF_PRESENCE_ENTITY, "External BLE Presence Sensor"),
    )
    missing_labels: list[str] = []
    for conf_key, label in checked_keys:
        ent_id = str(coordinator.get_opt(conf_key) or "").strip()
        if ent_id and not _entity_exists_in_ha(hass, ent_id):
            missing_labels.append(f"{label} ({ent_id})")
            warnings.append(
                {
                    "code": "missing_entity",
                    "message": f"{label} entity '{ent_id}' no longer exists in Home Assistant.",
                }
            )

    missing_issue_id = f"missing_mapped_entity_{entry_id}"
    if missing_labels:
        ir.async_create_issue(
            hass,
            DOMAIN,
            missing_issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_mapped_entity",
            translation_placeholders={
                "device_slug": slug,
                "missing_list": ", ".join(missing_labels),
                "companion_url": coordinator.build_companion_url(),
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, missing_issue_id)

    # 2. Check BLE proxy availability when native BLE tracking is enabled on a mobile display
    ble_issue_id = f"ble_no_proxies_{entry_id}"
    tracker = coordinator._ble_tracker
    has_seen_ble = bool(
        (tracker is not None and tracker.packets_seen > 0)
        or coordinator.ble_room_offsets
    )
    if (
        hass.is_running
        and coordinator.native_ble_tracking_enabled
        and coordinator.device_profile == "mobile_display"
        and not coordinator.presence_entity
        and not has_seen_ble
    ):
        proxy_areas = get_ble_proxy_area_ids(hass)
        if not proxy_areas:
            warnings.append(
                {
                    "code": "ble_no_proxies",
                    "message": "Built-in BLE Room Tracking is enabled, but no Bluetooth proxies assigned to a Home Assistant Area were found.",
                }
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                ble_issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="ble_no_proxies",
                translation_placeholders={
                    "device_slug": slug,
                },
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, ble_issue_id)
    else:
        ir.async_delete_issue(hass, DOMAIN, ble_issue_id)

    return warnings


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a RepairsFlow to acknowledge and clear a Latter configuration issue."""
    return ConfirmRepairFlow()