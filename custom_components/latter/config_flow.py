"""Config flow and Options flow for Latter (ESPHome Companion & Entity Middleware)."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_ALARM_ENTITY,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_BLE_AUTO_SWITCH,
    CONF_CALENDAR_ENTITIES,
    CONF_CUSTOM_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_LOCAL_SPEAKER,
    CONF_PRESENCE_ENTITY,
    CONF_REMOTE_1,
    CONF_REMOTE_2,
    CONF_REMOTE_3,
    CONF_REMOTE_4,
    CONF_SYNC_DEVICE_AREA,
    CONF_VOLUME_OVERRIDES,
    CONF_WEATHER_ENTITY,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_DEVICE_SLUG,
    DEFAULT_LOCAL_SPEAKER,
    DEFAULT_SYNC_DEVICE_AREA,
    DOMAIN,
)


def _discover_esphome_slug(hass: HomeAssistant) -> str:
    """Auto-discover an ESPHome node exposing *_set_browse_slots."""
    esphome_services = hass.services.async_services().get("esphome", {})
    for service_name in esphome_services:
        if service_name.endswith("_set_browse_slots"):
            return service_name[: -len("_set_browse_slots")]
    return DEFAULT_DEVICE_SLUG


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


def _discover_default_speaker(hass: HomeAssistant) -> str:
    """Return a sensible default media_player entity."""
    if hass.states.get(DEFAULT_LOCAL_SPEAKER) is not None:
        return DEFAULT_LOCAL_SPEAKER
    states = hass.states.async_all("media_player")
    if states:
        return states[0].entity_id
    return DEFAULT_LOCAL_SPEAKER


def _add_optional_entity(
    schema_dict: dict[Any, Any],
    key: str,
    current_val: Any,
    domains: str | list[str],
) -> None:
    """Add an optional EntitySelector field with a clean default if set."""
    cfg = selector.EntitySelectorConfig(domain=domains)
    if current_val:
        schema_dict[vol.Optional(key, default=current_val)] = selector.EntitySelector(cfg)
    else:
        schema_dict[vol.Optional(key)] = selector.EntitySelector(cfg)


def _build_schema(
    hass: HomeAssistant, current: dict[str, Any]
) -> vol.Schema:
    """Build the shared Voluptuous schema for ConfigFlow and OptionsFlow."""
    default_slug = current.get(CONF_DEVICE_SLUG) or _discover_esphome_slug(hass)
    default_weather = current.get(CONF_WEATHER_ENTITY) or _discover_default_weather(hass)
    default_alarm = current.get(CONF_ALARM_ENTITY) or _discover_default_alarm(hass)
    default_speaker = current.get(CONF_DEFAULT_SPEAKER) or _discover_default_speaker(hass)
    local_speaker = current.get(CONF_LOCAL_SPEAKER) or DEFAULT_LOCAL_SPEAKER
    vol_overrides = current.get(CONF_VOLUME_OVERRIDES, "")
    default_area = current.get(CONF_DEFAULT_AREA)
    presence_entity = current.get(CONF_PRESENCE_ENTITY)
    ble_auto = current.get(CONF_BLE_AUTO_SWITCH, DEFAULT_BLE_AUTO_SWITCH)
    sync_dev_area = current.get(CONF_SYNC_DEVICE_AREA, DEFAULT_SYNC_DEVICE_AREA)
    area_handoff = current.get(CONF_AREA_HANDOFF, DEFAULT_AREA_HANDOFF)
    calendars = current.get(CONF_CALENDAR_ENTITIES, [])
    custom_entities = current.get(CONF_CUSTOM_ENTITIES, [])
    art_size = str(current.get(CONF_ART_SIZE, DEFAULT_ART_SIZE))

    schema_dict: dict[Any, Any] = {
        vol.Required(CONF_DEVICE_SLUG, default=default_slug): selector.TextSelector(),
        vol.Required(
            CONF_DEFAULT_SPEAKER, default=default_speaker
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player")
        ),
        vol.Optional(
            CONF_LOCAL_SPEAKER, default=local_speaker
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player")
        ),
        vol.Optional(
            CONF_VOLUME_OVERRIDES, default=vol_overrides
        ): selector.TextSelector(
            selector.TextSelectorConfig(multiline=False)
        ),
    }

    if default_area:
        schema_dict[
            vol.Optional(CONF_DEFAULT_AREA, default=default_area)
        ] = selector.AreaSelector()
    else:
        schema_dict[vol.Optional(CONF_DEFAULT_AREA)] = selector.AreaSelector()

    # BLE Trilateration / Room Presence Sensor (Bermuda, ESPresense, etc.)
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

    # Home Security Alarm Entity Override
    _add_optional_entity(
        schema_dict,
        CONF_ALARM_ENTITY,
        default_alarm,
        "alarm_control_panel",
    )

    # 4-Slot TV / Media Remote Entities (Replaces YAML Substitutions!)
    for slot_key in (CONF_REMOTE_1, CONF_REMOTE_2, CONF_REMOTE_3, CONF_REMOTE_4):
        _add_optional_entity(
            schema_dict,
            slot_key,
            current.get(slot_key),
            ["remote", "media_player"],
        )

    # Weather Provider
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
                    value="466", label="466x466 (Full Native AMOLED)"
                ),
                selector.SelectOptionDict(
                    value="233", label="233x233 (Fast Low-Bandwidth Thumbnail)"
                ),
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )

    return vol.Schema(schema_dict)


class LatterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Latter (ESPHome Companion & Entity Middleware)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        if user_input is not None:
            slug = (
                str(user_input[CONF_DEVICE_SLUG])
                .strip()
                .lower()
                .replace("-", "_")
            )
            user_input[CONF_DEVICE_SLUG] = slug
            user_input[CONF_ART_SIZE] = int(user_input.get(CONF_ART_SIZE, DEFAULT_ART_SIZE))

            await self.async_set_unique_id(f"{DOMAIN}_{slug}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Latter ({slug})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(self.hass, {}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return LatterOptionsFlowHandler(config_entry)


class LatterOptionsFlowHandler(OptionsFlow):
    """Handle options flow updates for Latter."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            user_input[CONF_DEVICE_SLUG] = (
                str(user_input[CONF_DEVICE_SLUG])
                .strip()
                .lower()
                .replace("-", "_")
            )
            user_input[CONF_ART_SIZE] = int(user_input.get(CONF_ART_SIZE, DEFAULT_ART_SIZE))
            return self.async_create_entry(title="", data=user_input)

        merged = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(self.hass, merged),
        )