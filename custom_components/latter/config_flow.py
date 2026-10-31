"""Config flow, Options flow, and Hardware-Auto-Detecting Onboarding for Latter."""

from __future__ import annotations

import re
from typing import Any
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, selector

from .backup_engine import get_device_groups_and_profiles
from .ble_engine import _iter_devices, _iter_entities
from .const import (
    CONF_ALARM_ENTITY,
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
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DOCK_APPS,
    DEFAULT_PAGE_SIZE,
    DOMAIN,
    normalize_device_slug,
)

CONF_APPLY_PROFILE = "apply_profile"


def _resolve_esphome_device_and_unique_id(
    hass: HomeAssistant, slug: str
) -> tuple[dr.DeviceEntry | None, str]:
    """Resolve the HA DeviceEntry and canonical unique_id (MAC-backed when available) for a slug."""
    from .area_engine import find_esphome_device_id

    norm = normalize_device_slug(slug)
    dev_reg = dr.async_get(hass)
    found_id = find_esphome_device_id(hass, norm)
    matched_dev = dev_reg.async_get(found_id) if found_id else None

    for entry in hass.config_entries.async_entries(DOMAIN):
        if normalize_device_slug(str(entry.data.get(CONF_DEVICE_SLUG, ""))) == norm and entry.unique_id:
            dev_id = str(entry.data.get(CONF_ESPHOME_DEVICE_ID, "") or "")
            dev = dev_reg.async_get(dev_id) if dev_id else matched_dev
            return dev, entry.unique_id

    if matched_dev is not None:
        for _ctype, cval in matched_dev.connections:
            if cval:
                return matched_dev, f"{DOMAIN}_{dr.format_mac(str(cval))}"
    return matched_dev, f"{DOMAIN}_{norm}"


def _discover_esphome_slug(hass: HomeAssistant) -> str:
    """Auto-discover an unconfigured ESPHome node exposing Latter actions or interactive entities."""
    configured_slugs = {
        normalize_device_slug(str(e.data.get(CONF_DEVICE_SLUG, "")))
        for e in hass.config_entries.async_entries(DOMAIN)
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


def _discover_default_speaker(hass: HomeAssistant, device_slug: str) -> str:
    """Return the device's own on-device media_player entity if present, or empty string if speakerless."""
    slug_norm = normalize_device_slug(device_slug)
    for candidate in (f"media_player.{slug_norm}", f"media_player.{slug_norm}_music"):
        if hass.states.get(candidate) is not None:
            return candidate
    ent_reg = er.async_get(hass)
    for entry in _iter_entities(ent_reg):
        if entry.domain == "media_player" and entry.platform == "esphome":
            if slug_norm in entry.entity_id and not entry.disabled_by:
                return entry.entity_id
    return ""


def _detect_hardware_defaults(hass: HomeAssistant, slug: str) -> dict[str, Any]:
    """Auto-detect screen shape, art_size (410x502 vs 466), archetype, area, and roaming BLE capability."""
    norm = normalize_device_slug(slug)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    esphome_svcs = hass.services.async_services().get("esphome", {})

    matched_dev: dr.DeviceEntry | None = None
    for dev in _iter_devices(dev_reg):
        d_name = str(dev.name_by_user or dev.name or "").strip()
        if d_name and normalize_device_slug(d_name) == norm:
            matched_dev = dev
            break
    if matched_dev is None:
        from .area_engine import find_esphome_device_id

        found_id = find_esphome_device_id(hass, norm)
        if found_id:
            matched_dev = dev_reg.async_get(found_id)

    model_meta = (
        f"{matched_dev.model or ''} {matched_dev.sw_version or ''} {matched_dev.name or ''} {norm}".lower()
        if matched_dev
        else norm
    )

    has_native_slots = any(
        (s.endswith("_set_browse_slots") or s.endswith("_set_area_slots")) and norm in s
        for s in esphome_svcs
    )

    has_ble_beacon = False
    if matched_dev:
        for e in er.async_entries_for_device(ent_reg, matched_dev.id):
            if "ble" in e.entity_id.lower() and "beacon" in e.entity_id.lower():
                has_ble_beacon = True
                break

    is_desk_4b = any(k in model_meta for k in ("desk_assistant", "desk-assistant", "4b", "720"))
    is_remote_35 = any(k in model_meta for k in ("remote_assistant", "remote-assistant", "p4_35", "320x480", "3.5"))
    is_mobile_216 = any(k in model_meta for k in ("mobile_assistant", "mobile-assistant", "216", "2.16", "480x480"))
    is_watch_206 = "410x502" in model_meta or "206" in model_meta or "2.06" in model_meta
    is_round_175 = "466x466" in model_meta or "175" in model_meta or "1.75" in model_meta

    if is_desk_4b:
        return {
            CONF_DEVICE_PROFILE: "stationary_display",
            CONF_DEVICE_GROUP: "wall_panels",
            CONF_DISPLAY_SHAPE: "square",
            CONF_ART_SIZE: 720,
            CONF_DEFAULT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: (matched_dev.area_id or "") if matched_dev else "",
            "dock_apps": DEFAULT_DOCK_APPS,
        }

    if is_remote_35:
        return {
            CONF_DEVICE_PROFILE: "mobile_display",
            CONF_DEVICE_GROUP: "handhelds",
            CONF_DISPLAY_SHAPE: "square",
            CONF_ART_SIZE: "320x480",
            CONF_DEFAULT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "",
            "dock_apps": DEFAULT_DOCK_APPS,
        }

    if is_mobile_216:
        return {
            CONF_DEVICE_PROFILE: "mobile_display",
            CONF_DEVICE_GROUP: "handhelds",
            CONF_DISPLAY_SHAPE: "square",
            CONF_ART_SIZE: 480,
            CONF_DEFAULT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "",
        }

    if is_watch_206:
        return {
            CONF_DEVICE_PROFILE: "mobile_display",
            CONF_DEVICE_GROUP: "handhelds",
            CONF_DISPLAY_SHAPE: "square",
            CONF_ART_SIZE: "410x502",
            CONF_DEFAULT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "",
        }

    if is_round_175 or has_native_slots:
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
    hass: HomeAssistant, user_input: dict[str, Any], existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Merge auto-detected hardware defaults, roaming flag, optional Profile, and global system defaults."""
    slug = normalize_device_slug(str(user_input.get(CONF_DEVICE_SLUG) or "esphome_device"))
    hw_defaults = _detect_hardware_defaults(hass, slug)
    matched_dev, _uid = _resolve_esphome_device_and_unique_id(hass, slug)

    passthrough_keys = (
        "device_profile",
        "device_group",
        "ble_target_address",
        "assigned_person",
        "default_area",
        CONF_ESPHOME_DEVICE_ID,
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
    if matched_dev is not None and not merged.get(CONF_ESPHOME_DEVICE_ID):
        merged[CONF_ESPHOME_DEVICE_ID] = matched_dev.id

    if not merged.get(CONF_DEFAULT_SPEAKER):
        merged[CONF_DEFAULT_SPEAKER] = _discover_default_speaker(hass, slug)

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
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG, {})
    if not global_cfg.get(CONF_WEATHER_ENTITY) and not merged.get(CONF_WEATHER_ENTITY):
        def_w = _discover_default_weather(hass)
        if def_w:
            merged[CONF_WEATHER_ENTITY] = def_w
    if not global_cfg.get(CONF_ALARM_ENTITY) and not merged.get(CONF_ALARM_ENTITY):
        def_a = _discover_default_alarm(hass)
        if def_a:
            merged[CONF_ALARM_ENTITY] = def_a

    return merged


def _build_schema(hass: HomeAssistant, current: dict[str, Any]) -> vol.Schema:
    """Build the clean 3-field onboarding schema (Device Slug, Profile, Roaming Toggle)."""
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

    schema_dict: dict[Any, Any] = {
        vol.Required(CONF_DEVICE_SLUG, default=default_slug): selector.TextSelector(),
        vol.Required(CONF_APPLY_PROFILE, default="auto"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=profile_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_NATIVE_BLE_TRACKING, default=is_roaming_default
        ): selector.BooleanSelector(),
    }

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
    """Handle a streamlined config flow and automatic ESPHome device discovery for Latter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered_slug: str = ""
        self._discovered_name: str = ""

    async def async_step_zeroconf(
        self, discovery_info: Any
    ) -> ConfigFlowResult:
        """Handle Zeroconf mDNS auto-discovery of Latter-compatible ESPHome devices."""
        from . import is_latter_compatible_esphome_device

        raw_name = (
            str(discovery_info.properties.get("friendly_name") or "")
            or str(discovery_info.properties.get("name") or "")
            or discovery_info.name.split(".", 1)[0]
        ).strip()
        node_name = (
            str(discovery_info.properties.get("name") or "")
            or discovery_info.hostname.split(".", 1)[0]
            or raw_name
        ).strip()
        slug = normalize_device_slug(node_name)
        if not slug or "proxy" in slug or "proxy" in raw_name.lower():
            return self.async_abort(reason="not_supported")

        dev_reg = dr.async_get(self.hass)
        matched_dev: dr.DeviceEntry | None = None
        for dev in _iter_devices(dev_reg):
            d_name = str(dev.name_by_user or dev.name or "").strip()
            if normalize_device_slug(d_name) == slug:
                matched_dev = dev
                break

        if matched_dev is None or not is_latter_compatible_esphome_device(
            self.hass, matched_dev, slug
        ):
            return self.async_abort(reason="not_supported")

        _dev, target_uid = _resolve_esphome_device_and_unique_id(self.hass, slug)
        await self.async_set_unique_id(target_uid)
        self._abort_if_unique_id_configured()

        self._discovered_slug = slug
        self._discovered_name = _format_clean_device_title(self.hass, slug, raw_name)
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_user()

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle auto-discovery of a new Latter-compatible ESPHome device."""
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
        """Handle the streamlined initial setup step."""
        if user_input is not None:
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, user_input
            )
            slug = merged_data[CONF_DEVICE_SLUG]

            _abort_competing_flows_for_slug(
                self.hass, slug, keep_flow_id=self.flow_id
            )
            _dev, target_uid = _resolve_esphome_device_and_unique_id(self.hass, slug)
            if self.unique_id != target_uid:
                await self.async_set_unique_id(target_uid)
            self._abort_if_unique_id_configured()

            clean_title = _format_clean_device_title(
                self.hass, slug, self._discovered_name
            )
            return self.async_create_entry(
                title=clean_title,
                data=merged_data,
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
        """Handle a reconfiguration flow initialized by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        current = (
            dict(reconfigure_entry.options)
            if reconfigure_entry.options
            else dict(reconfigure_entry.data)
        )
        if user_input is not None:
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, user_input, existing=current
            )
            slug = merged_data[CONF_DEVICE_SLUG]
            _dev, target_uid = _resolve_esphome_device_and_unique_id(self.hass, slug)
            await self.async_set_unique_id(reconfigure_entry.unique_id or target_uid)
            self._abort_if_unique_id_mismatch()
            return self.async_update_and_abort(
                reconfigure_entry,
                data_updates=merged_data,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(self.hass, current),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return LatterOptionsFlowHandler()


class LatterOptionsFlowHandler(OptionsFlow):
    """Handle options flow updates for Latter."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        current = (
            dict(self.config_entry.options)
            if self.config_entry.options
            else dict(self.config_entry.data)
        )
        if user_input is not None:
            merged_data = _apply_onboarding_profile_and_defaults(
                self.hass, user_input, existing=current
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=merged_data, options=merged_data
            )
            return self.async_create_entry(title="", data=merged_data)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(self.hass, current),
        )