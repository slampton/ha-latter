"""Config flow, Device Subentry flow, BLE Tag Subentry flow, and hardware-detecting onboarding.

A Device subentry is bound to one ESPHome device chosen by the user (device selector) or
offered by discovery. The subentry stores that device's ID and MAC; its slug is the ESPHome
node name of that device. Nothing is looked up by typed names or slugs.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    selector,
)
import probatio as vol

from .config_defaults import (
    ble_tag_option_defaults,
    build_ble_tag_data,
)
from .const import (
    CONF_ALARM_ENTITY,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_CATEGORY,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SYNC_DEVICE_AREA,
    CONF_WEATHER_ENTITY,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)
from .groups.device_groups import (
    active_group_keys,
    detect_hardware_defaults,
    device_option_defaults,
    get_device_groups,
)
from .hub_registry import (
    get_area_state_index,
    get_system_config_lock,
    iter_coordinators,
    peek_domain_data,
)
from .identity import (
    ble_unique_id,
    bound_elsewhere,
    device_mac,
    device_title,
    device_unique_id,
    esphome_node_name,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    get_discovered_latter_devices,
    get_ignored_discovered_device_ids,
    is_esphome_device,
    is_latter_compatible_esphome_device,
    read_device_hardware_manifest,
)
from .media.linking import discover_ma_player_for_device
from .repairs import async_delete_device_issues


def _discover_unconfigured_latter_device_id(hass: HomeAssistant) -> str:
    """Return the ID of an ESPHome device running Latter that isn't bound yet (form default only), or ''."""
    candidates = get_discovered_latter_devices(hass)
    return str(candidates[0]["esphome_device_id"]) if candidates else ""


def _discover_default_weather(hass: HomeAssistant) -> str | None:
    """Return the first available `weather.*` entity in Home Assistant."""
    states = sorted(
        get_area_state_index(hass).states_for_domain("weather"),
        key=lambda s: s.entity_id,
    )
    return str(states[0].entity_id) if states else None


def _discover_default_alarm(hass: HomeAssistant) -> str | None:
    """Return the first available `alarm_control_panel.*` entity in Home Assistant."""
    states = sorted(
        get_area_state_index(hass).states_for_domain("alarm_control_panel"),
        key=lambda s: s.entity_id,
    )
    return str(states[0].entity_id) if states else None


def _discover_default_speaker(
    hass: HomeAssistant, esphome_device_id: str | None
) -> str:
    """Return the bound device's own `media_player` entity, or '' if it has no speaker."""
    return (
        find_device_entity_by_suffix(
            hass, esphome_device_id, "media_player", ("", "_music", "_media_player")
        )
        or ""
    )


def _selected_device(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dr.DeviceEntry | None:
    """Return the ESPHome device picked in the form (or the existing binding when the form has none)."""
    dev_id = str(
        user_input.get(CONF_ESPHOME_DEVICE_ID)
        or (existing or {}).get(CONF_ESPHOME_DEVICE_ID)
        or ""
    ).strip()
    dev = get_bound_esphome_device(hass, dev_id)
    if dev is None or not is_esphome_device(hass, dev):
        return None
    return dev


def _apply_group_selection(
    hass: HomeAssistant,
    merged: dict[str, Any],
    hw_defaults: dict[str, Any],
    user_input: dict[str, Any],
    existing: dict[str, Any] | None,
) -> dict[str, Any] | None:
    raw_grp_id = str(user_input.get(CONF_DEVICE_GROUP) or "auto").strip()
    grp_id = (
        str(hw_defaults.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP)
        if raw_grp_id == "auto"
        else raw_grp_id
    )
    matched_grp = (
        None
        if grp_id in ("", DEFAULT_DEVICE_GROUP)
        else next(
            (g for g in get_device_groups(hass) if g.get("id") == grp_id), None
        )
    )
    prev_grp_id = (
        str(existing.get(CONF_DEVICE_GROUP) or "").strip() if existing else ""
    )
    group_changed = (not existing) or (grp_id != prev_grp_id)
    if not matched_grp:
        merged[CONF_DEVICE_GROUP] = DEFAULT_DEVICE_GROUP
        return None

    merged[CONF_DEVICE_GROUP] = str(matched_grp["id"])
    grp_cfg = matched_grp.get("device_config")
    if isinstance(grp_cfg, dict) and group_changed:
        skip_auto_roaming = (
            raw_grp_id == "auto"
            and not existing
            and CONF_NATIVE_BLE_TRACKING not in user_input
        )
        for key in active_group_keys(matched_grp):
            if skip_auto_roaming and key in (
                CONF_NATIVE_BLE_TRACKING,
                CONF_BLE_AUTO_SWITCH,
                CONF_SYNC_DEVICE_AREA,
            ):
                continue
            if key in grp_cfg and grp_cfg[key] is not None:
                merged[key] = grp_cfg[key]
    return matched_grp


def _cached_manifest_for_device(
    hass: HomeAssistant, dev_id: str | None
) -> dict[str, Any] | None:
    """Return a bound coordinator's cached `device_hello` manifest for `dev_id`, if any."""
    if not dev_id:
        return None
    for coord in iter_coordinators(hass):
        if coord.esphome_device_id == dev_id and coord.hardware_manifest:
            return dict(coord.hardware_manifest)
    return None


def _apply_onboarding_profile_and_defaults(
    hass: HomeAssistant,
    dev: dr.DeviceEntry,
    user_input: dict[str, Any],
    existing: dict[str, Any] | None = None,
    *,
    rebind_hardware: bool = False,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge auto-detected hardware defaults, the device binding, roaming flag, optional Group, and global defaults."""
    hw_manifest = read_device_hardware_manifest(
        hass,
        dev.id,
        cached_manifest=manifest
        if manifest is not None
        else _cached_manifest_for_device(hass, dev.id),
    )
    is_stationary_hw = int(hw_manifest.get("stationary") or 0) == 1
    hw_defaults = detect_hardware_defaults(hass, dev, hw_manifest)
    merged: dict[str, Any] = {**hw_defaults, **(existing or {})}
    merged[CONF_DEVICE_SLUG] = esphome_node_name(hass, dev)
    if rebind_hardware or not merged.get(CONF_ESPHOME_DEVICE_ID):
        merged[CONF_ESPHOME_DEVICE_ID] = dev.id
        mac = device_mac(dev)
        if mac:
            merged["mac"] = mac
        else:
            merged.pop("mac", None)

    if rebind_hardware or not merged.get(CONF_DEFAULT_SPEAKER):
        merged[CONF_DEFAULT_SPEAKER] = _discover_default_speaker(hass, dev.id)

    if rebind_hardware or not merged.get(CONF_MA_PLAYER_ENTITY):
        discovered_ma = discover_ma_player_for_device(hass, dev.id)
        if discovered_ma:
            merged[CONF_MA_PLAYER_ENTITY] = discovered_ma
        elif rebind_hardware:
            merged.pop(CONF_MA_PLAYER_ENTITY, None)

    matched_grp = _apply_group_selection(
        hass, merged, hw_defaults, user_input, existing
    )

    if CONF_NATIVE_BLE_TRACKING in user_input:
        is_roaming = bool(user_input[CONF_NATIVE_BLE_TRACKING])
        merged[CONF_NATIVE_BLE_TRACKING] = is_roaming
        merged[CONF_BLE_AUTO_SWITCH] = is_roaming
        merged[CONF_SYNC_DEVICE_AREA] = is_roaming and not is_stationary_hw
        if not existing or CONF_DEFAULT_AREA not in existing or rebind_hardware:
            merged[CONF_DEFAULT_AREA] = (
                "" if is_roaming else str(dev.area_id or "").strip()
            )

    if matched_grp and isinstance(matched_grp.get("device_config"), dict):
        base_cfg = matched_grp["device_config"]
        if (
            bool(merged.get(CONF_NATIVE_BLE_TRACKING))
            != bool(base_cfg.get(CONF_NATIVE_BLE_TRACKING))
            or bool(merged.get(CONF_BLE_AUTO_SWITCH))
            != bool(base_cfg.get(CONF_BLE_AUTO_SWITCH))
            or (
                not is_stationary_hw
                and bool(merged.get(CONF_SYNC_DEVICE_AREA))
                != bool(base_cfg.get(CONF_SYNC_DEVICE_AREA))
            )
        ):
            merged[CONF_DEVICE_GROUP] = DEFAULT_DEVICE_GROUP

    if CONF_ASSIGNED_PERSON in user_input:
        merged[CONF_ASSIGNED_PERSON] = str(
            user_input.get(CONF_ASSIGNED_PERSON) or ""
        ).strip()

    _seed_global_defaults(hass)
    return merged


def _seed_global_defaults(hass: HomeAssistant) -> None:
    """Seed the System weather and alarm entities if none are configured yet."""
    domain_data = peek_domain_data(hass)
    if domain_data is not None:
        global_cfg = domain_data.global_config
        if CONF_WEATHER_ENTITY not in global_cfg:
            def_w = _discover_default_weather(hass)
            if def_w:
                global_cfg[CONF_WEATHER_ENTITY] = def_w
        if CONF_ALARM_ENTITY not in global_cfg:
            def_a = _discover_default_alarm(hass)
            if def_a:
                global_cfg[CONF_ALARM_ENTITY] = def_a


def _build_schema(
    hass: HomeAssistant,
    current: dict[str, Any],
    *,
    optional_device: bool = False,
) -> vol.Schema:
    """Build the device onboarding/reconfigure schema."""
    default_dev_id = str(
        current.get(CONF_ESPHOME_DEVICE_ID)
        or _discover_unconfigured_latter_device_id(hass)
    )
    default_dev = get_bound_esphome_device(hass, default_dev_id)
    default_id = default_dev.id if default_dev else None
    hw_manifest = read_device_hardware_manifest(
        hass,
        default_id,
        cached_manifest=_cached_manifest_for_device(hass, default_id),
    )
    hw_defs = detect_hardware_defaults(hass, default_dev, hw_manifest)
    is_roaming_default = bool(
        current.get(
            CONF_NATIVE_BLE_TRACKING,
            hw_defs.get(CONF_NATIVE_BLE_TRACKING, True),
        )
    )

    groups = get_device_groups(hass)
    hw_w, hw_h = int(hw_manifest.get("w") or 0), int(hw_manifest.get("h") or 0)
    hw_shape_lbl = (
        f"{hw_w}x{hw_h} {'round' if hw_manifest.get('shape') == 'circle' else 'rectangular'} display"
        if hw_w and hw_h
        else "no hardware manifest reported yet"
    )
    group_options = [
        selector.SelectOptionDict(
            value="auto",
            label=f"Auto-Detect from Device Hardware ({hw_shape_lbl})",
        ),
        selector.SelectOptionDict(
            value=DEFAULT_DEVICE_GROUP,
            label="Custom (Individual Settings)",
        ),
        *(
            selector.SelectOptionDict(
                value=str(g["id"]),
                label=f"Group: {g['name']}",
            )
            for g in groups
            if isinstance(g, dict) and g.get("id") and g.get("name")
        ),
    ]

    current_group = str(current.get(CONF_DEVICE_GROUP) or "auto")
    if current_group not in {opt["value"] for opt in group_options}:
        current_group = "auto"

    if optional_device:
        device_key: Any = (
            vol.Optional(
                CONF_ESPHOME_DEVICE_ID,
                description={"suggested_value": default_dev_id},
            )
            if default_dev_id
            else vol.Optional(CONF_ESPHOME_DEVICE_ID)
        )
    else:
        device_key = (
            vol.Required(CONF_ESPHOME_DEVICE_ID, default=default_dev_id)
            if default_dev_id
            else vol.Required(CONF_ESPHOME_DEVICE_ID)
        )
    return vol.Schema(
        {
            device_key: selector.DeviceSelector(
                selector.DeviceSelectorConfig(integration="esphome")
            ),
            vol.Optional(CONF_DEVICE_GROUP, default=current_group)
            if optional_device
            else vol.Required(
                CONF_DEVICE_GROUP, default=current_group
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=group_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_NATIVE_BLE_TRACKING, default=is_roaming_default)
            if optional_device
            else vol.Required(
                CONF_NATIVE_BLE_TRACKING, default=is_roaming_default
            ): selector.BooleanSelector(),
        }
    )


def _abort_competing_flows(
    hass: HomeAssistant, target_uid: str, keep_flow_id: str | None = None
) -> None:
    """Abort background discovery flows for the same device when the user submits a setup flow."""
    for flow in list(hass.config_entries.flow.async_progress_by_handler(DOMAIN)):
        fid = flow.get("flow_id")
        if not fid or fid == keep_flow_id:
            continue
        ctx = flow.get("context") or {}
        if flow.get("step_id") is None or (
            ctx.get("unique_id") == target_uid and ctx.get("source") != "user"
        ):
            hass.config_entries.flow.async_abort(fid)


def _migrate_replaced_hardware_registry(
    hass: HomeAssistant,
    entry: ConfigEntry[Any],
    subentry_id: str,
    mac_pair: tuple[str, str],
    new_esp_dev_id: str,
) -> None:
    old_mac, new_mac = mac_pair
    dev_reg = dr.async_get(hass)
    old_ident_keys = [subentry_id]
    if old_mac:
        old_ident_keys.insert(0, dr.format_mac(old_mac))
    new_ident_key = dr.format_mac(new_mac) if new_mac else subentry_id
    entry_devs = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for key in old_ident_keys:
        latter_dev = next(
            (d for d in entry_devs if (DOMAIN, key) in d.identifiers),
            None,
        )
        if latter_dev is not None:
            dev_reg.async_update_device(
                latter_dev.id,
                new_identifiers={(DOMAIN, new_ident_key)},
                via_device_id=new_esp_dev_id,
            )
            break
    async_delete_device_issues(hass, subentry_id)


class LatterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the single System hub config flow and initial ESPHome device discovery for Latter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self._discovered_device_id: str = ""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry[Any]
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by the Latter System hub."""
        _ = config_entry
        return {
            SUBENTRY_DEVICE: LatterDeviceSubentryFlow,
            SUBENTRY_BLE_TAG: LatterBleTagSubentryFlow,
        }

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle auto-discovery of a Latter-compatible ESPHome device when no hub entry exists yet."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        dev = get_bound_esphome_device(
            self.hass, str(discovery_info.get(CONF_ESPHOME_DEVICE_ID) or "")
        )
        if dev is None or not is_esphome_device(self.hass, dev):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(device_unique_id(dev))
        self._abort_if_unique_id_configured()

        self._discovered_device_id = dev.id
        self.context["title_placeholders"] = {"name": device_title(dev)}
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single Latter System hub entry (with optional initial ESPHome Device subentry)."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            raw_dev_id = str(user_input.get(CONF_ESPHOME_DEVICE_ID) or "").strip()
            if not raw_dev_id:
                async with get_system_config_lock(self.hass):
                    _seed_global_defaults(self.hass)
                    domain_data = peek_domain_data(self.hass)
                    if domain_data is not None and domain_data.global_store is not None:
                        await domain_data.global_store.async_save(domain_data.global_config)
                _abort_competing_flows(self.hass, "", keep_flow_id=self.flow_id)
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Latter",
                    data={},
                    subentries=[],
                )

            dev = _selected_device(self.hass, user_input)
            if dev is None or not is_latter_compatible_esphome_device(self.hass, dev):
                return self.async_show_form(
                    step_id="user",
                    data_schema=_build_schema(
                        self.hass, user_input, optional_device=True
                    ),
                    errors={CONF_ESPHOME_DEVICE_ID: "not_latter_device"},
                )
            async with get_system_config_lock(self.hass):
                merged_data = _apply_onboarding_profile_and_defaults(
                    self.hass, dev, user_input
                )
            target_uid = device_unique_id(dev)
            _abort_competing_flows(self.hass, target_uid, keep_flow_id=self.flow_id)
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Latter",
                data={},
                subentries=[
                    ConfigSubentryData(
                        data=merged_data,
                        subentry_type=SUBENTRY_DEVICE,
                        title=device_title(dev),
                        unique_id=target_uid,
                    )
                ],
            )

        initial: dict[str, Any] = {}
        if self._discovered_device_id:
            initial[CONF_ESPHOME_DEVICE_ID] = self._discovered_device_id
        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(self.hass, initial, optional_device=True),
        )


class LatterDeviceSubentryFlow(ConfigSubentryFlow):
    """Handle adding, reconfiguring, and replacing hardware for a Latter Device subentry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add an ESPHome Latter device (picked in the form) to the System."""
        entry = self._get_entry()
        if user_input is not None:
            dev = _selected_device(self.hass, user_input)
            if dev is None or not is_latter_compatible_esphome_device(self.hass, dev):
                return self.async_show_form(
                    step_id="user",
                    data_schema=_build_schema(self.hass, user_input),
                    errors={CONF_ESPHOME_DEVICE_ID: "not_latter_device"},
                )
            target_uid = device_unique_id(dev)
            if bound_elsewhere(entry, dev, target_uid):
                return self.async_abort(reason="already_configured")
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, dev, user_input, rebind_hardware=True
            )
            _abort_competing_flows(self.hass, target_uid)
            return self.async_create_entry(
                title=device_title(dev),
                data=merged_data,
                unique_id=target_uid,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(self.hass, {}),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure a device subentry or replace its bound ESPHome hardware in-place."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        current = dict(subentry.data)
        old_dev_id = str(current.get(CONF_ESPHOME_DEVICE_ID) or "")
        old_mac = str(current.get("mac", "") or "").strip()

        if user_input is not None:
            dev = _selected_device(self.hass, user_input, current)
            is_replacing_hw = dev is not None and dev.id != old_dev_id
            if dev is None or (
                is_replacing_hw
                and not is_latter_compatible_esphome_device(self.hass, dev)
            ):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=_build_schema(self.hass, {**current, **user_input}),
                    errors={CONF_ESPHOME_DEVICE_ID: "not_latter_device"},
                )
            target_uid = (
                device_unique_id(dev)
                if is_replacing_hw
                else str(subentry.unique_id or "")
            )
            if is_replacing_hw and bound_elsewhere(
                entry, dev, target_uid, skip_subentry_id=subentry.subentry_id
            ):
                return self.async_abort(reason="already_configured")
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass,
                dev,
                user_input,
                existing=current,
                rebind_hardware=is_replacing_hw,
            )
            if is_replacing_hw:
                _migrate_replaced_hardware_registry(
                    self.hass,
                    entry,
                    subentry.subentry_id,
                    (old_mac, str(merged_data.get("mac", "") or "").strip()),
                    dev.id,
                )

            return self.async_update_and_abort(
                entry,
                subentry,
                title=device_title(dev) if is_replacing_hw else subentry.title,
                data=merged_data,
                unique_id=target_uid,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(self.hass, current),
        )


class LatterBleTagSubentryFlow(ConfigSubentryFlow):
    """Add a BLE tag (phone, watch, or tag tracked through Bluetooth proxies) to the Latter System."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create the BLE tag from the form."""
        entry = self._get_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = build_ble_tag_data(user_input)
            if data is None:
                errors["base"] = "ble_tag_incomplete"
            else:
                target_uid = ble_unique_id(data[CONF_DEVICE_SLUG])
                for sub in entry.subentries.values():
                    if (
                        sub.unique_id == target_uid
                        or sub.data.get(CONF_DEVICE_SLUG) == data[CONF_DEVICE_SLUG]
                        or sub.data.get(CONF_BLE_TARGET_ADDRESS)
                        == data[CONF_BLE_TARGET_ADDRESS]
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=str(user_input.get("name") or data[CONF_DEVICE_SLUG]).strip(),
                    data=data,
                    unique_id=target_uid,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): selector.TextSelector(),
                    vol.Required(CONF_BLE_TARGET_ADDRESS): selector.TextSelector(),
                    vol.Optional(CONF_ASSIGNED_PERSON): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person")
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing BLE tag subentry in place."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        current = dict(subentry.data)
        errors: dict[str, str] = {}

        if user_input is not None:
            merged_input = {
                "name": str(subentry.title or current.get(CONF_DEVICE_SLUG) or ""),
                CONF_BLE_CATEGORY: current.get(
                    CONF_BLE_CATEGORY, DEFAULT_BLE_CATEGORY
                ),
                **user_input,
            }
            data = build_ble_tag_data(merged_input)
            if data is None:
                errors["base"] = "ble_tag_incomplete"
            else:
                data[CONF_DEVICE_SLUG] = str(
                    current.get(CONF_DEVICE_SLUG) or data[CONF_DEVICE_SLUG]
                )
                for sub in entry.subentries.values():
                    if sub.subentry_id == subentry.subentry_id:
                        continue
                    if (
                        sub.data.get(CONF_BLE_TARGET_ADDRESS)
                        == data[CONF_BLE_TARGET_ADDRESS]
                    ):
                        return self.async_abort(reason="already_configured")
                updated_data = {**current, **data}
                new_title = str(user_input.get("name") or subentry.title).strip()
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=new_title or subentry.title,
                    data=updated_data,
                    unique_id=subentry.unique_id,
                )

        default_name = str(subentry.title or current.get(CONF_DEVICE_SLUG) or "")
        default_addr = str(current.get(CONF_BLE_TARGET_ADDRESS) or "")
        default_person = str(current.get(CONF_ASSIGNED_PERSON) or "")
        person_key: Any = (
            vol.Optional(
                CONF_ASSIGNED_PERSON,
                description={"suggested_value": default_person},
            )
            if default_person
            else vol.Optional(CONF_ASSIGNED_PERSON)
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name", default=default_name
                    ): selector.TextSelector(),
                    vol.Required(
                        CONF_BLE_TARGET_ADDRESS, default=default_addr
                    ): selector.TextSelector(),
                    person_key: selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person")
                    ),
                }
            ),
            errors=errors,
        )


__all__ = [
    "LatterBleTagSubentryFlow",
    "LatterConfigFlow",
    "LatterDeviceSubentryFlow",
    "ble_tag_option_defaults",
    "device_option_defaults",
    "get_discovered_latter_devices",
    "get_ignored_discovered_device_ids",
]
