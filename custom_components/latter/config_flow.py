"""Config flow, Device Subentry flow, Options flow, and Hardware-Auto-Detecting Onboarding for Latter."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

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
from homeassistant.helpers import device_registry as dr, entity_registry as er, selector

from .backup_engine import get_device_groups_and_profiles
from .ble_engine import _iter_devices
from .const import (
    CONF_ALARM_ENTITY,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_BLE_AUTO_SWITCH,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_SLUG,
    CONF_DISPLAY_SHAPE,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SYNC_DEVICE_AREA,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_AREA_FOLLOW_DWELL_S,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DOCK_APPS,
    DEFAULT_PAGE_SIZE,
    DOMAIN,
    normalize_device_slug,
)
from .identity import (
    esphome_service,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    read_device_hardware_manifest,
)
from .system import get_latter_system

CONF_APPLY_PROFILE = "apply_profile"


def _iter_configured_device_records(hass: HomeAssistant) -> list[tuple[dict[str, Any], str | None]]:
    """Return (data_dict, unique_id) pairs across all Latter device subentries and legacy entries."""
    records: list[tuple[dict[str, Any], str | None]] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        for sub in entry.subentries.values():
            if sub.subentry_type == "device":
                records.append((dict(sub.data), sub.unique_id))
        if entry.data.get(CONF_DEVICE_SLUG):
            records.append((dict(entry.data), entry.unique_id))
    return records


def _resolve_esphome_device_and_unique_id(
    hass: HomeAssistant, slug: str
) -> tuple[dr.DeviceEntry | None, str]:
    """Resolve the HA DeviceEntry and canonical unique_id (MAC-backed when available) for a slug."""
    from .area_engine import find_esphome_device_id

    norm = normalize_device_slug(slug)
    dev_reg = dr.async_get(hass)
    found_id = find_esphome_device_id(hass, norm)
    matched_dev = dev_reg.async_get(found_id) if found_id else None

    for data_dict, uid in _iter_configured_device_records(hass):
        if normalize_device_slug(str(data_dict.get(CONF_DEVICE_SLUG, ""))) == norm and uid:
            dev_id = str(data_dict.get(CONF_ESPHOME_DEVICE_ID, "") or "")
            dev = dev_reg.async_get(dev_id) if dev_id else matched_dev
            return dev, uid

    if matched_dev is not None:
        for _ctype, cval in matched_dev.connections:
            if cval:
                return matched_dev, f"{DOMAIN}_{dr.format_mac(str(cval))}"
    return matched_dev, f"{DOMAIN}_{norm}"


def _discover_esphome_slug(hass: HomeAssistant) -> str:
    """Auto-discover an unconfigured ESPHome node exposing Latter actions or interactive entities."""
    configured_slugs = {
        normalize_device_slug(str(data_dict.get(CONF_DEVICE_SLUG, "")))
        for data_dict, _uid in _iter_configured_device_records(hass)
        if data_dict.get(CONF_DEVICE_SLUG)
    }
    esphome_services = hass.services.async_services().get("esphome", {})
    for suffix in ("_set_browse_slots", "_set_area_slots", "_latter_ping"):
        for service_name in esphome_services:
            if service_name.endswith(suffix):
                cand = normalize_device_slug(service_name[: -len(suffix)])
                if cand not in configured_slugs:
                    return cand

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    for dev in _iter_devices(dev_reg):
        entries = er.async_entries_for_device(ent_reg, dev.id)
        if not any(e.platform == "esphome" for e in entries):
            continue
        dev_name = str(dev.name_by_user or dev.name or "").strip()
        if dev_name and "proxy" not in dev_name.lower():
            slug = normalize_device_slug(dev_name)
            if slug and slug != "esphome_device" and slug not in configured_slugs:
                return slug

    return "esphome_device"


def _discover_default_weather(hass: HomeAssistant) -> str | None:
    """Return the first available weather.* entity in Home Assistant."""
    states = hass.states.async_all("weather")
    if states:
        return states[0].entity_id
    return None


def _discover_default_alarm(hass: HomeAssistant) -> str | None:
    """Return the first available alarm_control_panel.* entity in Home Assistant."""
    states = hass.states.async_all("alarm_control_panel")
    if states:
        return states[0].entity_id
    return None


def _discover_default_speaker(
    hass: HomeAssistant,
    device_slug: str,
    esphome_device_id: str | None = None,
) -> str:
    """Return the device's own on-device media_player entity if present, or empty string if speakerless."""
    found = find_device_entity_by_suffix(
        hass,
        esphome_device_id,
        "media_player",
        ("", "_music", "_media_player"),
        fallback_slug=device_slug,
    )
    if found:
        return found
    slug_norm = normalize_device_slug(device_slug)
    for candidate in (f"media_player.{slug_norm}", f"media_player.{slug_norm}_music"):
        if hass.states.get(candidate) is not None:
            return candidate
    return ""


def _detect_hardware_defaults(hass: HomeAssistant, slug: str) -> dict[str, Any]:
    """Auto-detect screen shape, art_size, archetype, area, and roaming BLE capability from the device's hardware manifest."""
    norm = normalize_device_slug(slug)
    ent_reg = er.async_get(hass)

    matched_dev = get_bound_esphome_device(hass, None, fallback_slug=norm)
    dev_id = matched_dev.id if matched_dev else None
    manifest = read_device_hardware_manifest(hass, dev_id, fallback_slug=norm)

    has_native_slots = bool(
        esphome_service(hass, dev_id, "set_browse_slots", fallback_slug=norm)
        or esphome_service(hass, dev_id, "set_area_slots", fallback_slug=norm)
    )

    has_ble_beacon = isinstance(manifest.get("beacon"), dict)
    if not has_ble_beacon and matched_dev:
        for e in er.async_entries_for_device(ent_reg, matched_dev.id):
            if e.entity_id.endswith("_ble_presence_beacon"):
                has_ble_beacon = True
                break

    if manifest and "w" in manifest and "h" in manifest:
        w = int(manifest.get("w") or 466)
        h = int(manifest.get("h") or 466)
        shape = str(manifest.get("shape") or ("circle" if w == h == 466 else "square"))
        is_stationary = bool(int(manifest.get("stationary") or 0) == 1)
        art_size: int | str = w if w == h else f"{w}x{h}"
        profile = str(
            manifest.get("profile")
            or ("stationary_display" if is_stationary else "mobile_display")
        )
        return {
            CONF_DEVICE_PROFILE: profile,
            CONF_DEVICE_GROUP: "wall_panels" if is_stationary else "handhelds",
            CONF_DISPLAY_SHAPE: shape,
            CONF_ART_SIZE: art_size,
            CONF_DEFAULT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
            CONF_NATIVE_BLE_TRACKING: not is_stationary,
            CONF_BLE_AUTO_SWITCH: not is_stationary,
            CONF_SYNC_DEVICE_AREA: not is_stationary,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: (matched_dev.area_id or "") if (matched_dev and is_stationary) else "",
            "dock_apps": DEFAULT_DOCK_APPS,
        }

    if has_native_slots:
        return {
            CONF_DEVICE_PROFILE: "mobile_display",
            CONF_DEVICE_GROUP: "handhelds",
            CONF_DISPLAY_SHAPE: "circle",
            CONF_ART_SIZE: DEFAULT_ART_SIZE,
            CONF_DEFAULT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "",
            "dock_apps": DEFAULT_DOCK_APPS,
        }

    return {
        CONF_DEVICE_PROFILE: "headless_node",
        CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP,
        CONF_DISPLAY_SHAPE: "square",
        CONF_ART_SIZE: DEFAULT_ART_SIZE,
        CONF_DEFAULT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
        CONF_NATIVE_BLE_TRACKING: has_ble_beacon,
        CONF_BLE_AUTO_SWITCH: has_ble_beacon,
        CONF_SYNC_DEVICE_AREA: has_ble_beacon,
        CONF_AREA_HANDOFF: False,
        CONF_DEFAULT_AREA: (matched_dev.area_id or "") if matched_dev else "",
    }


def _apply_onboarding_profile_and_defaults(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    existing: dict[str, Any] | None = None,
    *,
    rebind_hardware: bool = False,
) -> dict[str, Any]:
    """Merge auto-detected hardware defaults, roaming flag, optional Profile, and global system defaults."""
    slug = normalize_device_slug(
        str(
            user_input.get(CONF_DEVICE_SLUG)
            or (existing or {}).get(CONF_DEVICE_SLUG)
            or "esphome_device"
        )
    )
    hw_defaults = _detect_hardware_defaults(hass, slug)
    matched_dev, _uid = _resolve_esphome_device_and_unique_id(hass, slug)

    passthrough_keys = (
        "device_profile",
        "device_group",
        "ble_target_address",
        "assigned_person",
        "default_area",
        CONF_ESPHOME_DEVICE_ID,
        "mac",
    )
    extra_init = {
        k: user_input[k]
        for k in passthrough_keys
        if k in user_input and user_input[k] not in (None, "")
    }
    merged: dict[str, Any] = {
        **hw_defaults,
        **(existing or {}),
        **extra_init,
        CONF_DEVICE_SLUG: slug,
    }
    if matched_dev is not None and (rebind_hardware or not merged.get(CONF_ESPHOME_DEVICE_ID)):
        merged[CONF_ESPHOME_DEVICE_ID] = matched_dev.id
        for _ctype, cval in matched_dev.connections:
            if cval:
                merged["mac"] = dr.format_mac(str(cval))
                break

    if rebind_hardware or not merged.get(CONF_DEFAULT_SPEAKER):
        merged[CONF_DEFAULT_SPEAKER] = _discover_default_speaker(
            hass, slug, str(merged.get(CONF_ESPHOME_DEVICE_ID) or "") or None
        )

    prof_id = str(user_input.get(CONF_APPLY_PROFILE) or "auto").strip()
    if prof_id and prof_id != "auto":
        _, profiles = get_device_groups_and_profiles(hass)
        matched_prof = next((p for p in profiles if p.get("id") == prof_id), None)
        if matched_prof and isinstance(matched_prof.get("device_config"), dict):
            for k, v in matched_prof["device_config"].items():
                if v is not None:
                    merged[k] = v

    if CONF_NATIVE_BLE_TRACKING in user_input:
        is_roaming = bool(user_input[CONF_NATIVE_BLE_TRACKING])
        merged[CONF_NATIVE_BLE_TRACKING] = is_roaming
        merged[CONF_BLE_AUTO_SWITCH] = is_roaming
        merged[CONF_SYNC_DEVICE_AREA] = is_roaming
        if not is_roaming and merged.get(CONF_DEVICE_PROFILE) == "mobile_display":
            merged[CONF_DEVICE_PROFILE] = "stationary_display"

    # Seed global system weather & alarm if not yet configured anywhere
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

    return merged


def _build_schema(
    hass: HomeAssistant,
    current: dict[str, Any],
    *,
    include_device_slug: bool = True,
) -> vol.Schema:
    """Build the device onboarding/reconfigure schema."""
    default_slug = str(current.get(CONF_DEVICE_SLUG) or _discover_esphome_slug(hass))
    hw_defs = _detect_hardware_defaults(hass, default_slug)
    is_roaming_default = bool(
        current.get(
            CONF_NATIVE_BLE_TRACKING,
            hw_defs.get(CONF_NATIVE_BLE_TRACKING, True),
        )
    )

    _, profiles = get_device_groups_and_profiles(hass)
    art_sz = str(hw_defs.get(CONF_ART_SIZE) or "")
    hw_shape_lbl = (
        "410x502 Watch"
        if art_sz == "410x502"
        else "480x480 Square AMOLED"
        if art_sz == "480"
        else "320x480 Widescreen Handheld"
        if art_sz == "320x480"
        else "720x720 Stationary Display"
        if art_sz == "720"
        else "466x466 Round Display"
        if hw_defs.get(CONF_DISPLAY_SHAPE) == "circle"
        else "ESPHome Node"
    )
    profile_options = [
        selector.SelectOptionDict(
            value="auto",
            label=f"Auto-Detect from Device Hardware ({hw_shape_lbl})",
        )
    ]
    for p in profiles:
        if isinstance(p, dict) and p.get("id") and p.get("name"):
            profile_options.append(
                selector.SelectOptionDict(
                    value=str(p["id"]),
                    label=f"Profile: {p['name']}",
                )
            )

    schema_dict: dict[Any, Any] = {}
    if include_device_slug:
        schema_dict[
            vol.Required(CONF_DEVICE_SLUG, default=default_slug)
        ] = selector.TextSelector()
    schema_dict[
        vol.Required(CONF_APPLY_PROFILE, default="auto")
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=profile_options,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
    schema_dict[
        vol.Required(
            CONF_NATIVE_BLE_TRACKING, default=is_roaming_default
        )
    ] = selector.BooleanSelector()

    return vol.Schema(schema_dict)


def _abort_competing_flows_for_slug(
    hass: HomeAssistant, slug: str, keep_flow_id: str | None = None
) -> None:
    """Abort any background discovery flow for the same slug when the user submits a manual setup flow."""
    _dev, target_uid = _resolve_esphome_device_and_unique_id(hass, slug)
    legacy_uid = f"{DOMAIN}_{normalize_device_slug(slug)}"
    for flow in list(hass.config_entries.flow.async_progress_by_handler(DOMAIN)):
        fid = flow.get("flow_id")
        if not fid or fid == keep_flow_id:
            continue
        ctx = flow.get("context") or {}
        if flow.get("step_id") is None or (
            ctx.get("unique_id") in (target_uid, legacy_uid)
            and ctx.get("source") != "user"
        ):
            hass.config_entries.flow.async_abort(fid)


def _format_clean_device_title(
    hass: HomeAssistant, slug: str, fallback_name: str = ""
) -> str:
    """Resolve the clean friendly name for an ESPHome device."""
    norm = normalize_device_slug(slug)
    dev_reg = dr.async_get(hass)
    for dev in _iter_devices(dev_reg):
        dev_name = str(dev.name_by_user or dev.name or "").strip()
        if dev_name and normalize_device_slug(dev_name) == norm:
            return dev_name
    if fallback_name and fallback_name.strip():
        return fallback_name.strip()
    return norm.replace("_", " ").title()


class LatterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the single System hub config flow and initial ESPHome device discovery for Latter."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered_slug: str = ""
        self._discovered_name: str = ""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by the Latter System hub."""
        return {"device": LatterDeviceSubentryFlow}

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle auto-discovery of a Latter-compatible ESPHome device when no hub entry exists yet."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        slug = normalize_device_slug(str(discovery_info.get(CONF_DEVICE_SLUG) or ""))
        if not slug:
            return self.async_abort(reason="already_configured")

        _dev, target_uid = _resolve_esphome_device_and_unique_id(self.hass, slug)
        await self.async_set_unique_id(target_uid)
        self._abort_if_unique_id_configured()

        self._discovered_slug = slug
        self._discovered_name = _format_clean_device_title(
            self.hass, slug, str(discovery_info.get("name") or "")
        )
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single Latter System hub entry and optionally onboard the first device subentry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, user_input
            )
            slug = merged_data[CONF_DEVICE_SLUG]

            _abort_competing_flows_for_slug(
                self.hass, slug, keep_flow_id=self.flow_id
            )
            _dev, target_uid = _resolve_esphome_device_and_unique_id(self.hass, slug)
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            clean_title = _format_clean_device_title(
                self.hass, slug, self._discovered_name
            )
            subentries: list[ConfigSubentryData] = []
            if slug and slug != "esphome_device":
                subentries.append(
                    ConfigSubentryData(
                        data=merged_data,
                        subentry_type="device",
                        title=clean_title,
                        unique_id=target_uid,
                    )
                )
            return self.async_create_entry(
                title="Latter",
                data={},
                subentries=subentries,
            )

        initial: dict[str, Any] = {}
        if self._discovered_slug:
            initial[CONF_DEVICE_SLUG] = self._discovered_slug

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
            for k in (CONF_WEATHER_ENTITY, CONF_ALARM_ENTITY, CONF_AREA_FOLLOW_DWELL_S):
                if k in user_input:
                    global_cfg[k] = user_input[k]
            domain_data[DATA_GLOBAL_CONFIG] = global_cfg
            store = domain_data.get(DATA_GLOBAL_STORE)
            if store is not None:
                await store.async_save(global_cfg)
            sys_obj = get_latter_system(self.hass)
            if sys_obj is not None:
                sys_obj.config = global_cfg
                for coord in list(sys_obj.coordinators.values()):
                    await coord.async_on_global_config_updated()
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
        """Add a new ESPHome companion display or BLE device subentry to the Latter System hub."""
        entry = self._get_entry()
        if user_input is not None:
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, user_input, rebind_hardware=True
            )
            slug = merged_data[CONF_DEVICE_SLUG]
            _abort_competing_flows_for_slug(self.hass, slug)
            _dev, target_uid = _resolve_esphome_device_and_unique_id(self.hass, slug)

            for existing_sub in entry.subentries.values():
                existing_slug = normalize_device_slug(
                    str(existing_sub.data.get(CONF_DEVICE_SLUG, ""))
                )
                if existing_sub.unique_id == target_uid or existing_slug == slug:
                    return self.async_abort(reason="already_configured")

            clean_title = _format_clean_device_title(self.hass, slug)
            return self.async_create_entry(
                title=clean_title,
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
        old_slug = normalize_device_slug(str(current.get(CONF_DEVICE_SLUG, "")))
        old_mac = str(current.get("mac", "") or "").strip()

        if user_input is not None:
            new_slug = normalize_device_slug(
                str(user_input.get(CONF_DEVICE_SLUG) or old_slug)
            )
            is_replacing_hw = new_slug != old_slug
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass,
                user_input,
                existing=current,
                rebind_hardware=is_replacing_hw,
            )
            _dev, target_uid = _resolve_esphome_device_and_unique_id(
                self.hass, new_slug
            )

            for other_sub in entry.subentries.values():
                if other_sub.subentry_id == subentry.subentry_id:
                    continue
                other_slug = normalize_device_slug(
                    str(other_sub.data.get(CONF_DEVICE_SLUG, ""))
                )
                if other_sub.unique_id == target_uid or other_slug == new_slug:
                    return self.async_abort(reason="already_configured")

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

            clean_title = _format_clean_device_title(self.hass, new_slug)
            return self.async_update_and_abort(
                entry,
                subentry,
                title=clean_title,
                data=merged_data,
                unique_id=target_uid,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(self.hass, current),
        )


def _build_system_options_schema(
    hass: HomeAssistant, global_cfg: dict[str, Any]
) -> vol.Schema:
    """Build the System-level Options schema for shared weather, alarm, and BLE dwell settings."""
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
    default_dwell = int(
        global_cfg.get(CONF_AREA_FOLLOW_DWELL_S, DEFAULT_AREA_FOLLOW_DWELL_S)
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
            vol.Required(
                CONF_AREA_FOLLOW_DWELL_S,
                default=default_dwell,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=3,
                    max=60,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


class LatterOptionsFlowHandler(OptionsFlow):
    """Handle System-level options flow updates for the Latter hub."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage System-level options."""
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = dict(domain_data.get(DATA_GLOBAL_CONFIG, {}))
        if user_input is not None:
            for k in (CONF_WEATHER_ENTITY, CONF_ALARM_ENTITY, CONF_AREA_FOLLOW_DWELL_S):
                if k in user_input:
                    global_cfg[k] = user_input[k]
            domain_data[DATA_GLOBAL_CONFIG] = global_cfg
            store = domain_data.get(DATA_GLOBAL_STORE)
            if store is not None:
                await store.async_save(global_cfg)
            sys_obj = get_latter_system(self.hass)
            if sys_obj is not None:
                sys_obj.config = global_cfg
                for coord in list(sys_obj.coordinators.values()):
                    await coord.async_on_global_config_updated()
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_system_options_schema(self.hass, global_cfg),
        )
