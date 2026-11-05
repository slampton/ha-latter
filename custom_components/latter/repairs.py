"""Home Assistant Repairs & Configuration Health Monitor for Latter."""

from __future__ import annotations

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
from .issue_ids import (
    ble_no_proxies_issue_id,
    device_issue_ids,
    missing_mapped_entity_issue_id,
)


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
    sub_id = coordinator.subentry_id
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

    def _create_scoped_issue(
        issue_id: str, translation_key: str, placeholders: dict[str, str]
    ) -> None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders=placeholders,
            config_entry_id=entry_id,
        )

    missing_issue_id = missing_mapped_entity_issue_id(sub_id)
    if missing_labels:
        _create_scoped_issue(
            missing_issue_id,
            "missing_mapped_entity",
            {
                "device_slug": slug,
                "missing_list": ", ".join(missing_labels),
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, missing_issue_id)

    # 2. Check BLE proxy availability when native BLE tracking is enabled on roaming hardware
    ble_issue_id = ble_no_proxies_issue_id(sub_id)
    tracker = coordinator._ble_tracker
    has_seen_ble = bool(
        (tracker is not None and tracker.packets_seen > 0)
        or coordinator.ble_area_offsets
    )
    if (
        hass.is_running
        and coordinator.native_ble_tracking_enabled
        and coordinator.is_roaming_device
        and not coordinator.presence_entity
        and not has_seen_ble
    ):
        proxy_areas = get_ble_proxy_area_ids(hass)
        if not proxy_areas:
            warnings.append(
                {
                    "code": "ble_no_proxies",
                    "message": "Built-in BLE Area Tracking is enabled, but no Bluetooth proxies assigned to a Home Assistant Area were found.",
                }
            )
            _create_scoped_issue(
                ble_issue_id,
                "ble_no_proxies",
                {"device_slug": slug},
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, ble_issue_id)
    else:
        ir.async_delete_issue(hass, DOMAIN, ble_issue_id)

    return warnings


@callback
def async_delete_device_issues(hass: HomeAssistant, subentry_id: str) -> None:
    """Delete every repair issue raised for one Device (called when its subentry is removed)."""
    for issue_id in device_issue_ids(subentry_id):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    domain_data = hass.data.get(DOMAIN, {})
    if isinstance(domain_data, dict):
        for key in ("_slot_push_failures", "_slot_push_last_warn"):
            bucket = domain_data.get(key)
            if isinstance(bucket, dict):
                bucket.pop(subentry_id, None)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a RepairsFlow to acknowledge and clear a Latter configuration issue."""
    return ConfirmRepairFlow()