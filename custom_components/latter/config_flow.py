"""Config flow, Device Subentry flow, Options flow, and hardware-detecting onboarding for Latter.

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
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    selector,
)
import voluptuous as vol

from .const import (
    CONF_ALARM_ENTITY,
    CONF_AREA_CATEGORIES,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_ITEMS,
    CONF_ESPHOME_DEVICE_ID,
    CONF_HOME_CATEGORIES,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_SYNC_DEVICE_AREA,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_HOME_CATEGORIES,
    DOMAIN,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
    normalize_device_slug,
)
from .groups import active_group_keys, get_device_groups
from .hub import get_area_state_index, get_latter_system
from .identity import (
    esphome_node_name,
    esphome_service,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    is_esphome_device,
    is_latter_compatible_esphome_device,
    read_device_hardware_manifest,
)
from .presence import _iter_devices
from .protocol import default_dock_items


def _iter_configured_device_records(hass: HomeAssistant) -> list[tuple[dict[str, Any], str | None]]:
    """Return (data_dict, unique_id) pairs across all Latter device subentries."""
    records: list[tuple[dict[str, Any], str | None]] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        for sub in entry.subentries.values():
            if sub.subentry_type == SUBENTRY_DEVICE:
                records.append((dict(sub.data), sub.unique_id))
    return records


def _device_mac(dev: dr.DeviceEntry) -> str:
    """Return the ESPHome device's network MAC connection, formatted, or ''."""
    for ctype, cval in dev.connections:
        if ctype == dr.CONNECTION_NETWORK_MAC and cval:
            return dr.format_mac(str(cval))
    return ""


def _device_unique_id(dev: dr.DeviceEntry) -> str:
    """Return the subentry unique_id for an ESPHome device: its MAC, else its device ID."""
    mac = _device_mac(dev)
    return f"{DOMAIN}_{mac}" if mac else f"{DOMAIN}_{dev.id}"


def _ble_unique_id(slug: str) -> str:
    """Return the subentry unique_id for a Studio-adopted BLE tag (no ESPHome device)."""
    return f"{DOMAIN}_ble_{slug}"


def get_discovered_latter_devices(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return unbound ESPHome devices running Latter firmware ready for Studio adoption."""
    records = _iter_configured_device_records(hass)
    configured_ids = {
        str(data.get(CONF_ESPHOME_DEVICE_ID) or "")
        for data, _uid in records
        if data.get(CONF_ESPHOME_DEVICE_ID)
    }
    configured_uids = {str(uid) for _data, uid in records if uid}
    area_reg = ar.async_get(hass)
    candidates = [
        dev
        for dev in _iter_devices(dr.async_get(hass))
        if dev.id not in configured_ids
        and _device_unique_id(dev) not in configured_uids
        and is_esphome_device(hass, dev)
        and is_latter_compatible_esphome_device(hass, dev)
    ]
    candidates.sort(key=lambda d: str(d.name_by_user or d.name or d.id).lower())

    out: list[dict[str, Any]] = []
    for dev in candidates:
        manifest = read_device_hardware_manifest(hass, dev.id)
        hw_defs = _detect_hardware_defaults(hass, dev, manifest)
        raw_model = str(dev.model or "").strip()
        w = int(manifest.get("w") or 0)
        h = int(manifest.get("h") or 0)
        board = str(manifest.get("board") or "").strip()
        if w > 0 and h > 0:
            model_label = (
                f"{raw_model} ({w}x{h})"
                if raw_model
                else f"Latter display ({w}x{h}{f' {board}' if board else ''})"
            )
        else:
            model_label = raw_model or "Latter ESPHome Device"
        esp_area_id = str(dev.area_id or "").strip()
        area_obj = area_reg.async_get_area(esp_area_id) if esp_area_id else None
        out.append(
            {
                "esphome_device_id": dev.id,
                "node_name": esphome_node_name(hass, dev),
                "title": _device_title(dev),
                "model_label": model_label,
                "area_name": area_obj.name if area_obj else "",
                "default_group": str(
                    hw_defs.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP
                ),
            }
        )
    return out


def _discover_unconfigured_latter_device_id(hass: HomeAssistant) -> str:
    """Return the ID of an ESPHome device running Latter that isn't bound yet (form default only), or ''."""
    candidates = get_discovered_latter_devices(hass)
    return str(candidates[0]["esphome_device_id"]) if candidates else ""


def _discover_default_weather(hass: HomeAssistant) -> str | None:
    """Return the first available weather.* entity in Home Assistant."""
    states = sorted(
        get_area_state_index(hass).states_for_domain("weather"),
        key=lambda s: s.entity_id,
    )
    if states:
        return states[0].entity_id
    return None


def _discover_default_alarm(hass: HomeAssistant) -> str | None:
    """Return the first available alarm_control_panel.* entity in Home Assistant."""
    states = sorted(
        get_area_state_index(hass).states_for_domain("alarm_control_panel"),
        key=lambda s: s.entity_id,
    )
    if states:
        return states[0].entity_id
    return None


def _discover_default_speaker(hass: HomeAssistant, esphome_device_id: str | None) -> str:
    """Return the bound device's own media_player entity, or '' if it has no speaker."""
    return (
        find_device_entity_by_suffix(
            hass, esphome_device_id, "media_player", ("", "_music", "_media_player")
        )
        or ""
    )


def _detect_hardware_defaults(
    hass: HomeAssistant,
    dev: dr.DeviceEntry | None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Auto-detect group, area, and roaming BLE capability from the device's hardware manifest."""
    ent_reg = er.async_get(hass)
    dev_id = dev.id if dev is not None else None
    if manifest is None:
        manifest = read_device_hardware_manifest(hass, dev_id)

    has_native_slots = bool(
        esphome_service(hass, dev_id, "latter_set_slots")
    )

    has_ble_beacon = isinstance(manifest.get("beacon"), dict)
    if not has_ble_beacon and dev is not None:
        for e in er.async_entries_for_device(ent_reg, dev.id):
            if e.entity_id.endswith("_ble_radio_active"):
                has_ble_beacon = True
                break

    esp_area = str(dev.area_id or "").strip() if dev is not None else ""

    if manifest and "w" in manifest and "h" in manifest:
        is_stationary = bool(int(manifest.get("stationary") or 0) == 1)
        is_wearable = bool(int(manifest.get("wearable") or 0) == 1)
        is_round_battery = (
            str(manifest.get("shape") or "").strip().lower() == "circle"
            and bool(int(manifest.get("battery") or 0) == 1)
        )
        default_grp = (
            "wall_panels"
            if is_stationary
            else (
                "wearables"
                if is_wearable
                else ("pocket_carry" if is_round_battery else "handhelds")
            )
        )
        default_roaming = (not bool(esp_area)) if is_stationary else True
        return {
            CONF_DEVICE_GROUP: default_grp,
            CONF_NATIVE_BLE_TRACKING: default_roaming,
            CONF_BLE_AUTO_SWITCH: default_roaming,
            CONF_SYNC_DEVICE_AREA: default_roaming and not is_stationary,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "" if default_roaming else esp_area,
            CONF_DOCK_ITEMS: default_dock_items(),
            CONF_PINNED_ITEMS: [],
            CONF_AREA_CATEGORIES: DEFAULT_AREA_CATEGORIES,
            CONF_HOME_CATEGORIES: DEFAULT_HOME_CATEGORIES,
        }

    if has_native_slots:
        return {
            CONF_DEVICE_GROUP: "handhelds",
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "",
            CONF_DOCK_ITEMS: default_dock_items(),
            CONF_PINNED_ITEMS: [],
            CONF_AREA_CATEGORIES: DEFAULT_AREA_CATEGORIES,
            CONF_HOME_CATEGORIES: DEFAULT_HOME_CATEGORIES,
        }

    return {
        CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP,
        CONF_NATIVE_BLE_TRACKING: has_ble_beacon,
        CONF_BLE_AUTO_SWITCH: has_ble_beacon,
        CONF_SYNC_DEVICE_AREA: has_ble_beacon,
        CONF_AREA_HANDOFF: False,
        CONF_DEFAULT_AREA: (dev.area_id or "") if dev else "",
    }


def device_option_defaults(
    hass: HomeAssistant, dev: dr.DeviceEntry | None, manifest: dict[str, Any]
) -> dict[str, Any]:
    """Return the option defaults a newly onboarded ESPHome Latter device gets (used by Reset to defaults)."""
    hw_defs = _detect_hardware_defaults(hass, dev, manifest)
    grp_id = str(hw_defs.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP)
    matched_grp = next(
        (g for g in get_device_groups(hass) if g.get("id") == grp_id), None
    )
    group_defs: dict[str, Any] = {}
    if matched_grp and isinstance(matched_grp.get("device_config"), dict):
        for k in active_group_keys(matched_grp):
            if k in (
                CONF_NATIVE_BLE_TRACKING,
                CONF_BLE_AUTO_SWITCH,
                CONF_SYNC_DEVICE_AREA,
            ):
                continue
            if (
                k in matched_grp["device_config"]
                and matched_grp["device_config"][k] is not None
            ):
                group_defs[k] = matched_grp["device_config"][k]
    return {
        **hw_defs,
        **group_defs,
        CONF_DEFAULT_SPEAKER: _discover_default_speaker(hass, dev.id if dev is not None else None),
    }


def ble_tag_option_defaults(slug: str, target_address: str) -> dict[str, Any]:
    """Return the data a newly added BLE tag gets for this name and address (used by Reset to defaults)."""
    return _build_ble_tag_data({"name": slug, CONF_BLE_TARGET_ADDRESS: target_address}) or {}


def _selected_device(
    hass: HomeAssistant, user_input: dict[str, Any], existing: dict[str, Any] | None = None
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


def _apply_onboarding_profile_and_defaults(
    hass: HomeAssistant,
    dev: dr.DeviceEntry,
    user_input: dict[str, Any],
    existing: dict[str, Any] | None = None,
    *,
    rebind_hardware: bool = False,
) -> dict[str, Any]:
    """Merge auto-detected hardware defaults, the device binding, roaming flag, optional Group, and global defaults."""
    hw_manifest = read_device_hardware_manifest(hass, dev.id)
    is_stationary_hw = bool(int(hw_manifest.get("stationary") or 0) == 1)
    hw_defaults = _detect_hardware_defaults(hass, dev, hw_manifest)
    merged: dict[str, Any] = {**hw_defaults, **(existing or {})}
    merged[CONF_DEVICE_SLUG] = esphome_node_name(hass, dev)
    if rebind_hardware or not merged.get(CONF_ESPHOME_DEVICE_ID):
        merged[CONF_ESPHOME_DEVICE_ID] = dev.id
        mac = _device_mac(dev)
        if mac:
            merged["mac"] = mac
        else:
            merged.pop("mac", None)

    if rebind_hardware or not merged.get(CONF_DEFAULT_SPEAKER):
        merged[CONF_DEFAULT_SPEAKER] = _discover_default_speaker(hass, dev.id)

    raw_grp_id = str(user_input.get(CONF_DEVICE_GROUP) or "auto").strip()
    grp_id = raw_grp_id
    groups = get_device_groups(hass)
    if grp_id == "auto":
        grp_id = str(hw_defaults.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP)
    if grp_id in ("", DEFAULT_DEVICE_GROUP, "unassigned"):
        merged[CONF_DEVICE_GROUP] = DEFAULT_DEVICE_GROUP
        matched_grp = None
    else:
        matched_grp = next((g for g in groups if g.get("id") == grp_id), None)
    if matched_grp:
        merged[CONF_DEVICE_GROUP] = str(matched_grp["id"])
        if isinstance(matched_grp.get("device_config"), dict):
            for k in active_group_keys(matched_grp):
                if (
                    raw_grp_id == "auto"
                    and not existing
                    and CONF_NATIVE_BLE_TRACKING not in user_input
                    and k
                    in (
                        CONF_NATIVE_BLE_TRACKING,
                        CONF_BLE_AUTO_SWITCH,
                        CONF_SYNC_DEVICE_AREA,
                    )
                ):
                    continue
                if k in matched_grp["device_config"] and matched_grp["device_config"][k] is not None:
                    merged[k] = matched_grp["device_config"][k]
    else:
        merged[CONF_DEVICE_GROUP] = DEFAULT_DEVICE_GROUP

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
        if bool(merged.get(CONF_NATIVE_BLE_TRACKING)) != bool(
            base_cfg.get(CONF_NATIVE_BLE_TRACKING)
        ) or bool(merged.get(CONF_BLE_AUTO_SWITCH)) != bool(
            base_cfg.get(CONF_BLE_AUTO_SWITCH)
        ) or (
            not is_stationary_hw
            and bool(merged.get(CONF_SYNC_DEVICE_AREA))
            != bool(base_cfg.get(CONF_SYNC_DEVICE_AREA))
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
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
    if isinstance(global_cfg, dict):
        if CONF_WEATHER_ENTITY not in global_cfg:
            def_w = _discover_default_weather(hass)
            if def_w:
                global_cfg[CONF_WEATHER_ENTITY] = def_w
        if CONF_ALARM_ENTITY not in global_cfg:
            def_a = _discover_default_alarm(hass)
            if def_a:
                global_cfg[CONF_ALARM_ENTITY] = def_a


def _build_ble_tag_data(user_input: dict[str, Any]) -> dict[str, Any] | None:
    """Return subentry data for a BLE tag (phone, watch, tag), or None if the name or address is missing."""
    slug = normalize_device_slug(str(user_input.get("name") or ""))
    target = str(user_input.get(CONF_BLE_TARGET_ADDRESS) or "").strip()
    if slug == "esphome_device" or not target:
        return None
    return {
        CONF_DEVICE_SLUG: slug,
        CONF_BLE_TARGET_ADDRESS: target,
        CONF_ASSIGNED_PERSON: str(user_input.get(CONF_ASSIGNED_PERSON) or "").strip(),
        CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP,
        CONF_DEFAULT_SPEAKER: "",
        CONF_NATIVE_BLE_TRACKING: True,
        CONF_BLE_AUTO_SWITCH: True,
        CONF_SYNC_DEVICE_AREA: False,
    }


def _build_schema(
    hass: HomeAssistant,
    current: dict[str, Any],
) -> vol.Schema:
    """Build the device onboarding/reconfigure schema."""
    default_dev_id = str(
        current.get(CONF_ESPHOME_DEVICE_ID) or _discover_unconfigured_latter_device_id(hass)
    )
    default_dev = get_bound_esphome_device(hass, default_dev_id)
    hw_manifest = read_device_hardware_manifest(hass, default_dev.id if default_dev else None)
    hw_defs = _detect_hardware_defaults(hass, default_dev, hw_manifest)
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
    ]
    for g in groups:
        if isinstance(g, dict) and g.get("id") and g.get("name"):
            group_options.append(
                selector.SelectOptionDict(
                    value=str(g["id"]),
                    label=f"Group: {g['name']}",
                )
            )

    current_group = str(current.get(CONF_DEVICE_GROUP) or "auto")
    if current_group not in {opt["value"] for opt in group_options}:
        current_group = "auto"

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
            vol.Required(CONF_DEVICE_GROUP, default=current_group): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=group_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
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
            ctx.get("unique_id") == target_uid
            and ctx.get("source") != "user"
        ):
            hass.config_entries.flow.async_abort(fid)


def _device_title(dev: dr.DeviceEntry) -> str:
    """Return the friendly name of the bound ESPHome device."""
    return str(dev.name_by_user or dev.name or dev.id).strip()


def _bound_elsewhere(
    entry: ConfigEntry, dev: dr.DeviceEntry, target_uid: str, skip_subentry_id: str = ""
) -> bool:
    """Return True if another Device subentry already binds this ESPHome device."""
    for sub in entry.subentries.values():
        if sub.subentry_id == skip_subentry_id:
            continue
        if sub.unique_id == target_uid or sub.data.get(CONF_ESPHOME_DEVICE_ID) == dev.id:
            return True
    return False


class LatterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the single System hub config flow and initial ESPHome device discovery for Latter."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self._discovered_device_id: str = ""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by the Latter System hub."""
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

        await self.async_set_unique_id(_device_unique_id(dev))
        self._abort_if_unique_id_configured()

        self._discovered_device_id = dev.id
        self.context["title_placeholders"] = {"name": _device_title(dev)}
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single Latter System hub entry and onboard the first Device subentry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            dev = _selected_device(self.hass, user_input)
            if dev is None or not is_latter_compatible_esphome_device(self.hass, dev):
                return self.async_show_form(
                    step_id="user",
                    data_schema=_build_schema(self.hass, user_input),
                    errors={CONF_ESPHOME_DEVICE_ID: "not_latter_device"},
                )
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, dev, user_input
            )
            target_uid = _device_unique_id(dev)
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
                        title=_device_title(dev),
                        unique_id=target_uid,
                    )
                ],
            )

        initial: dict[str, Any] = {}
        if self._discovered_device_id:
            initial[CONF_ESPHOME_DEVICE_ID] = self._discovered_device_id
        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(self.hass, initial),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration on the System hub entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = dict(domain_data.get(DATA_GLOBAL_CONFIG, {}))
        if user_input is not None:
            await _async_save_system_options(self.hass, user_input)
            return self.async_update_and_abort(
                reconfigure_entry,
                data_updates={},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_system_options_schema(self.hass, global_cfg),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the System-level options flow handler."""
        return LatterOptionsFlowHandler()


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
            target_uid = _device_unique_id(dev)
            if _bound_elsewhere(entry, dev, target_uid):
                return self.async_abort(reason="already_configured")
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, dev, user_input, rebind_hardware=True
            )
            _abort_competing_flows(self.hass, target_uid)
            return self.async_create_entry(
                title=_device_title(dev),
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
                is_replacing_hw and not is_latter_compatible_esphome_device(self.hass, dev)
            ):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=_build_schema(self.hass, {**current, **user_input}),
                    errors={CONF_ESPHOME_DEVICE_ID: "not_latter_device"},
                )
            target_uid = _device_unique_id(dev) if is_replacing_hw else str(subentry.unique_id or "")
            if is_replacing_hw and _bound_elsewhere(
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

            new_mac = str(merged_data.get("mac", "") or "").strip()
            if is_replacing_hw:
                dev_reg = dr.async_get(self.hass)
                old_ident_keys = [subentry.subentry_id]
                if old_mac:
                    old_ident_keys.insert(0, dr.format_mac(old_mac))
                new_ident_key = (
                    dr.format_mac(new_mac) if new_mac else subentry.subentry_id
                )
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
                        )
                        break

            return self.async_update_and_abort(
                entry,
                subentry,
                title=_device_title(dev) if is_replacing_hw else subentry.title,
                data=merged_data,
                unique_id=target_uid,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(self.hass, current),
        )


class LatterBleTagSubentryFlow(ConfigSubentryFlow):
    """Add a BLE tag (phone, watch or tag tracked through Bluetooth proxies) to the Latter System."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create the BLE tag from the form."""
        entry = self._get_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _build_ble_tag_data(user_input)
            if data is None:
                errors["base"] = "ble_tag_incomplete"
            else:
                target_uid = _ble_unique_id(data[CONF_DEVICE_SLUG])
                for sub in entry.subentries.values():
                    if (
                        sub.unique_id == target_uid
                        or sub.data.get(CONF_DEVICE_SLUG) == data[CONF_DEVICE_SLUG]
                        or sub.data.get(CONF_BLE_TARGET_ADDRESS) == data[CONF_BLE_TARGET_ADDRESS]
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


def _build_system_options_schema(
    hass: HomeAssistant, global_cfg: dict[str, Any]
) -> vol.Schema:
    """Build the System-level Options schema for the shared weather and alarm entities."""
    default_weather = str(
        global_cfg.get(CONF_WEATHER_ENTITY)
        or _discover_default_weather(hass)
        or ""
    )
    default_alarm = str(
        global_cfg.get(CONF_ALARM_ENTITY)
        or _discover_default_alarm(hass)
        or ""
    )
    return vol.Schema(
        {
            vol.Optional(
                CONF_WEATHER_ENTITY,
                description={"suggested_value": default_weather},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(
                CONF_ALARM_ENTITY,
                description={"suggested_value": default_alarm},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="alarm_control_panel")
            ),
        }
    )


async def _async_save_system_options(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> None:
    """Persist System-level weather and alarm options and notify coordinators of changed keys."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
    changed_keys: set[str] = set()
    for k in (CONF_WEATHER_ENTITY, CONF_ALARM_ENTITY):
        if k in user_input and global_cfg.get(k) != user_input[k]:
            global_cfg[k] = user_input[k]
            changed_keys.add(k)
    store = domain_data.get(DATA_GLOBAL_STORE)
    if store is not None:
        await store.async_save(global_cfg)
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        sys_obj.config = global_cfg
        for coord in list(sys_obj.coordinators.values()):
            await coord.async_on_global_config_updated(changed_keys)


class LatterOptionsFlowHandler(OptionsFlow):
    """Handle System-level options flow updates for the Latter hub."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage System-level options."""
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = dict(domain_data.get(DATA_GLOBAL_CONFIG, {}))
        if user_input is not None:
            await _async_save_system_options(self.hass, user_input)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_build_system_options_schema(self.hass, global_cfg),
        )
