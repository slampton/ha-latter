"""Config flow, Options flow, and ESPHome Auto-Discovery for Latter."""

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

from .ble_engine import _iter_devices, _iter_entities
from .const import (
    CONF_ALARM_ENTITY,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_CALENDAR_ENTITIES,
    CONF_CUSTOM_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_REMOTE_1,
    CONF_REMOTE_2,
    CONF_REMOTE_3,
    CONF_REMOTE_4,
    CONF_SYNC_DEVICE_AREA,
    CONF_VOL_SPEAKER_1,
    CONF_VOL_SPEAKER_2,
    CONF_VOL_TARGET_1,
    CONF_VOL_TARGET_2,
    CONF_WEATHER_ENTITY,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_NATIVE_BLE_TRACKING,
    DEFAULT_SYNC_DEVICE_AREA,
    DOMAIN,
    normalize_device_slug,
)


def _discover_esphome_slug(hass: HomeAssistant) -> str:
    """Auto-discover an ESPHome node exposing slot services or media/display entities."""
    esphome_services = hass.services.async_services().get("esphome", {})
    for suffix in ("_set_browse_slots", "_set_room_slots"):
        for service_name in esphome_services:
            if service_name.endswith(suffix):
                return service_name[: -len(suffix)]

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    for dev in _iter_devices(dev_reg):
        entries = er.async_entries_for_device(ent_reg, dev.id)
        if not any(e.platform == "esphome" for e in entries):
            continue
        dev_name = str(dev.name_by_user or dev.name or "").strip()
        if dev_name and "proxy" not in dev_name.lower():
            slug = re.sub(r"[^a-z0-9]+", "_", dev_name.lower()).strip("_")
            if slug:
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


def _add_optional_entity(
    schema_dict: dict[Any, Any],
    key: str,
    current_val: Any,
    domains: str | list[str],
) -> None:
    """Add an optional EntitySelector field using suggested_value so saving/clearing works reliably."""
    cfg = selector.EntitySelectorConfig(domain=domains)
    if current_val:
        schema_dict[
            vol.Optional(key, description={"suggested_value": current_val})
        ] = selector.EntitySelector(cfg)
    else:
        schema_dict[vol.Optional(key)] = selector.EntitySelector(cfg)


def _build_schema(
    hass: HomeAssistant, current: dict[str, Any]
) -> vol.Schema:
    """Build the shared Voluptuous schema for ConfigFlow and OptionsFlow."""
    default_slug = current.get(CONF_DEVICE_SLUG) or _discover_esphome_slug(hass)
    default_weather = (
        current.get(CONF_WEATHER_ENTITY)
        if CONF_WEATHER_ENTITY in current
        else _discover_default_weather(hass)
    )
    default_alarm = (
        current.get(CONF_ALARM_ENTITY)
        if CONF_ALARM_ENTITY in current
        else _discover_default_alarm(hass)
    )
    default_speaker = current.get(CONF_DEFAULT_SPEAKER) or _discover_default_speaker(
        hass, str(default_slug)
    )
    default_area = current.get(CONF_DEFAULT_AREA)
    native_ble = current.get(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)
    beacon_uuid = current.get(CONF_BLE_BEACON_UUID, DEFAULT_BLE_BEACON_UUID)
    presence_entity = current.get(CONF_PRESENCE_ENTITY)
    ble_auto = current.get(CONF_BLE_AUTO_SWITCH, DEFAULT_BLE_AUTO_SWITCH)
    sync_dev_area = current.get(CONF_SYNC_DEVICE_AREA, DEFAULT_SYNC_DEVICE_AREA)
    area_handoff = current.get(CONF_AREA_HANDOFF, DEFAULT_AREA_HANDOFF)
    calendars = current.get(CONF_CALENDAR_ENTITIES, [])
    custom_entities = current.get(CONF_CUSTOM_ENTITIES, [])
    art_size = str(current.get(CONF_ART_SIZE, DEFAULT_ART_SIZE))

    schema_dict: dict[Any, Any] = {
        vol.Required(CONF_DEVICE_SLUG, default=default_slug): selector.TextSelector(),
        vol.Optional(
            CONF_DEFAULT_SPEAKER,
            description={"suggested_value": default_speaker} if default_speaker else {},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player")
        ),
    }

    _add_optional_entity(
        schema_dict,
        CONF_VOL_SPEAKER_1,
        current.get(CONF_VOL_SPEAKER_1),
        ["media_player", "remote"],
    )
    _add_optional_entity(
        schema_dict,
        CONF_VOL_TARGET_1,
        current.get(CONF_VOL_TARGET_1),
        ["media_player", "number", "input_number"],
    )
    _add_optional_entity(
        schema_dict,
        CONF_VOL_SPEAKER_2,
        current.get(CONF_VOL_SPEAKER_2),
        ["media_player", "remote"],
    )
    _add_optional_entity(
        schema_dict,
        CONF_VOL_TARGET_2,
        current.get(CONF_VOL_TARGET_2),
        ["media_player", "number", "input_number"],
    )

    if default_area:
        schema_dict[
            vol.Optional(
                CONF_DEFAULT_AREA, description={"suggested_value": default_area}
            )
        ] = selector.AreaSelector()
    else:
        schema_dict[vol.Optional(CONF_DEFAULT_AREA)] = selector.AreaSelector()

    schema_dict[
        vol.Required(CONF_NATIVE_BLE_TRACKING, default=native_ble)
    ] = selector.BooleanSelector()

    schema_dict[
        vol.Optional(CONF_BLE_BEACON_UUID, default=beacon_uuid)
    ] = selector.TextSelector()

    _add_optional_entity(
        schema_dict,
        CONF_PRESENCE_ENTITY,
        presence_entity,
        ["sensor", "device_tracker", "input_text"],
    )

    schema_dict[
        vol.Required(CONF_BLE_AUTO_SWITCH, default=ble_auto)
    ] = selector.BooleanSelector()

    schema_dict[
        vol.Required(CONF_SYNC_DEVICE_AREA, default=sync_dev_area)
    ] = selector.BooleanSelector()

    schema_dict[
        vol.Required(CONF_AREA_HANDOFF, default=area_handoff)
    ] = selector.BooleanSelector()

    _add_optional_entity(
        schema_dict,
        CONF_ALARM_ENTITY,
        default_alarm,
        "alarm_control_panel",
    )

    for slot_key in (CONF_REMOTE_1, CONF_REMOTE_2, CONF_REMOTE_3, CONF_REMOTE_4):
        _add_optional_entity(
            schema_dict,
            slot_key,
            current.get(slot_key),
            ["remote", "media_player"],
        )

    _add_optional_entity(
        schema_dict,
        CONF_WEATHER_ENTITY,
        default_weather,
        "weather",
    )

    schema_dict[
        vol.Optional(CONF_CALENDAR_ENTITIES, default=calendars)
    ] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="calendar", multiple=True)
    )

    schema_dict[
        vol.Optional(CONF_CUSTOM_ENTITIES, default=custom_entities)
    ] = selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=[
                "light",
                "cover",
                "climate",
                "fan",
                "switch",
                "scene",
                "sensor",
                "alarm_control_panel",
            ],
            multiple=True,
        )
    )

    schema_dict[
        vol.Required(CONF_ART_SIZE, default=art_size)
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(
                    value="466", label="466x466 (1.75\" Round AMOLED)"
                ),
                selector.SelectOptionDict(
                    value="410x502", label="410x502 (2.06\" Watch AMOLED)"
                ),
                selector.SelectOptionDict(
                    value="360", label="360x360 (Round LCD / AMOLED)"
                ),
                selector.SelectOptionDict(
                    value="240", label="240x240 (Compact Display)"
                ),
                selector.SelectOptionDict(
                    value="233", label="233x233 (Fast Low-Bandwidth Thumbnail)"
                ),
                selector.SelectOptionDict(
                    value="480", label="480x480 (Large Wall Panel)"
                ),
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )

    return vol.Schema(schema_dict)


def _normalize_art_size(raw_val: Any) -> int | str:
    """Normalize square integer art size (466) or rectangular WxH string ('410x502')."""
    s_val = str(raw_val or DEFAULT_ART_SIZE).strip().lower()
    if "x" in s_val:
        return s_val
    try:
        return int(s_val)
    except ValueError:
        return DEFAULT_ART_SIZE


def _format_clean_device_title(hass: HomeAssistant, slug: str, fallback_name: str = "") -> str:
    """Resolve the clean friendly name for an ESPHome device without 'Latter (...)' wrapper."""
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
    """Handle a config flow and automatic ESPHome device discovery for Latter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered_slug: str = ""
        self._discovered_name: str = ""

    async def async_step_zeroconf(
        self, discovery_info: Any
    ) -> ConfigFlowResult:
        """Handle Zeroconf mDNS auto-discovery of ESPHome devices on the LAN."""
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

        # Only auto-discover ESPHome nodes that exist in HA with interactive entities (not bare BLE proxies)
        from . import is_latter_compatible_esphome_device

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

        await self.async_set_unique_id(f"{DOMAIN}_{slug}")
        self._abort_if_unique_id_configured()

        self._discovered_slug = slug
        self._discovered_name = _format_clean_device_title(self.hass, slug, raw_name)
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_user()

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle auto-discovery of a new ESPHome device."""
        slug = normalize_device_slug(str(discovery_info.get(CONF_DEVICE_SLUG) or ""))
        if not slug:
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(f"{DOMAIN}_{slug}")
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
        """Handle the initial setup step (manual or pre-filled from ESPHome auto-discovery)."""
        if user_input is not None:
            slug = normalize_device_slug(str(user_input[CONF_DEVICE_SLUG]))
            user_input[CONF_DEVICE_SLUG] = slug
            user_input[CONF_ART_SIZE] = _normalize_art_size(user_input.get(CONF_ART_SIZE, DEFAULT_ART_SIZE))

            await self.async_set_unique_id(f"{DOMAIN}_{slug}")
            self._abort_if_unique_id_configured()

            clean_title = _format_clean_device_title(
                self.hass, slug, self._discovered_name
            )
            return self.async_create_entry(
                title=clean_title,
                data=user_input,
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
        if user_input is not None:
            slug = normalize_device_slug(str(user_input[CONF_DEVICE_SLUG]))
            user_input[CONF_DEVICE_SLUG] = slug
            user_input[CONF_ART_SIZE] = _normalize_art_size(
                user_input.get(CONF_ART_SIZE, DEFAULT_ART_SIZE)
            )
            await self.async_set_unique_id(f"{DOMAIN}_{slug}")
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates=user_input,
            )

        current = (
            dict(reconfigure_entry.options)
            if reconfigure_entry.options
            else dict(reconfigure_entry.data)
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
        if user_input is not None:
            user_input[CONF_DEVICE_SLUG] = normalize_device_slug(
                str(user_input[CONF_DEVICE_SLUG])
            )
            user_input[CONF_ART_SIZE] = _normalize_art_size(user_input.get(CONF_ART_SIZE, DEFAULT_ART_SIZE))
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input
            )
            return self.async_create_entry(title="", data=user_input)

        current = (
            dict(self.config_entry.options)
            if self.config_entry.options
            else dict(self.config_entry.data)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(self.hass, current),
        )