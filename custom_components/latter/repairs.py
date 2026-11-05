"""Home Assistant Repairs & Configuration Health Monitor for Latter."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir, selector

from .ble_engine import get_ble_proxy_area_ids
from .const import (
    CONF_ALARM_ENTITY,
    CONF_DEFAULT_SPEAKER,
    CONF_MA_PLAYER_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)
from .coordinator import LatterCoordinator
from .issue_ids import (
    ble_no_proxies_issue_id,
    device_issue_ids,
    link_ma_player_issue_id,
    missing_mapped_entity_issue_id,
)
from .media_engine import (
    async_set_ma_player_link,
    ma_player_entities,
    suggest_ma_player_for,
)
from .system import get_latter_system


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


class LinkMaPlayerRepairFlow(RepairsFlow):
    """Pick the Music Assistant player of one Latter Device and save it as that Device's link."""

    def __init__(self, subentry_id: str) -> None:
        """Remember which Device this repair belongs to."""
        self._subentry_id = subentry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Start at the player picker."""
        return await self.async_step_pick()

    async def async_step_pick(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the MA player picker (pre-selected only on a unique manufacturer + model match) and save the choice."""
        sys_obj = get_latter_system(self.hass)
        coordinator = sys_obj.coordinators.get(self._subentry_id) if sys_obj else None
        if coordinator is None:
            return self.async_abort(reason="device_removed")

        valid = {e.entity_id for e in ma_player_entities(self.hass)}
        errors: dict[str, str] = {}
        if user_input is not None:
            choice = str(user_input.get(CONF_MA_PLAYER_ENTITY) or "").strip()
            if choice in valid:
                async_set_ma_player_link(self.hass, coordinator, choice)
                ir.async_delete_issue(
                    self.hass, DOMAIN, link_ma_player_issue_id(self._subentry_id)
                )
                return self.async_create_entry(data={})
            errors[CONF_MA_PLAYER_ENTITY] = "invalid_ma_player"

        suggestion = suggest_ma_player_for(self.hass, coordinator)
        key = (
            vol.Required(CONF_MA_PLAYER_ENTITY, default=suggestion)
            if suggestion
            else vol.Required(CONF_MA_PLAYER_ENTITY)
        )
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    key: selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="media_player", integration="music_assistant"
                        )
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "device_slug": coordinator.device_slug,
                "speaker_entity": coordinator.local_speaker or "",
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for a Latter repair: the MA player picker, or a plain confirm."""
    if issue_id.startswith("link_ma_player_"):
        # The issue ID is link_ma_player_<subentry_id> (issue_ids.link_ma_player_issue_id).
        return LinkMaPlayerRepairFlow(issue_id.removeprefix("link_ma_player_"))
    return ConfirmRepairFlow()