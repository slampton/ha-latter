"""Service call recording and external domain target service stubs for real Home Assistant tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import (
    Context,
    Event,
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)

_SERVICE_CALLS_KEY = "_latter_test_service_calls"
_SERVICE_SPY_INSTALLED_KEY = "_latter_test_service_spy"

_COMMON_TARGET_SERVICES: dict[str, tuple[str, ...]] = {
    "alarm_control_panel": (
        "alarm_arm_away",
        "alarm_arm_custom_bypass",
        "alarm_arm_home",
        "alarm_arm_night",
        "alarm_arm_vacation",
        "alarm_disarm",
        "alarm_trigger",
    ),
    "automation": ("trigger", "turn_off", "turn_on", "toggle"),
    "climate": (
        "set_fan_mode",
        "set_humidity",
        "set_hvac_mode",
        "set_preset_mode",
        "set_swing_mode",
        "set_temperature",
        "turn_off",
        "turn_on",
    ),
    "cover": (
        "close_cover",
        "close_cover_tilt",
        "open_cover",
        "open_cover_tilt",
        "set_cover_position",
        "set_cover_tilt_position",
        "stop_cover",
        "toggle",
    ),
    "fan": (
        "decrease_speed",
        "increase_speed",
        "oscillate",
        "set_direction",
        "set_percentage",
        "set_preset_mode",
        "toggle",
        "turn_off",
        "turn_on",
    ),
    "input_boolean": ("toggle", "turn_off", "turn_on"),
    "input_button": ("press",),
    "input_number": ("decrement", "increment", "set_value"),
    "input_select": (
        "select_first",
        "select_last",
        "select_next",
        "select_option",
        "select_previous",
    ),
    "lock": ("lock", "open", "unlock"),
    "media_player": (
        "clear_playlist",
        "join",
        "media_next_track",
        "media_pause",
        "media_play",
        "media_play_pause",
        "media_previous_track",
        "media_seek",
        "media_stop",
        "play_media",
        "repeat_set",
        "select_sound_mode",
        "select_source",
        "shuffle_set",
        "toggle",
        "turn_off",
        "turn_on",
        "unjoin",
        "volume_down",
        "volume_mute",
        "volume_set",
        "volume_up",
    ),
    "notify": ("notify", "persistent_notification"),
    "remote": ("delete_command", "learn_command", "send_command", "toggle", "turn_off", "turn_on"),
    "scene": ("apply", "turn_on"),
    "script": ("reload", "toggle", "turn_off", "turn_on"),
    "tts": ("clear_cache", "cloud_say", "speak"),
    "vacuum": (
        "clean_spot",
        "locate",
        "pause",
        "return_to_base",
        "send_command",
        "set_fan_speed",
        "start",
        "start_pause",
        "stop",
    ),
}


@dataclass
class RecordedServiceCall:
    """Captured invocation of `hass.services.async_call` for test assertions."""

    domain: str
    service: str
    data: dict[str, Any] = field(default_factory=dict)
    context: Context | None = None
    return_response: bool = False


def get_service_calls(hass: HomeAssistant) -> list[RecordedServiceCall]:
    """Return the mutable list of recorded `hass.services.async_call` invocations for `hass`."""
    calls: list[RecordedServiceCall] = hass.data.setdefault(_SERVICE_CALLS_KEY, [])
    return calls


def install_service_call_recorder(hass: HomeAssistant) -> list[RecordedServiceCall]:
    """Subscribe to `EVENT_CALL_SERVICE` once on `hass.bus` so all service calls are recorded."""
    calls = get_service_calls(hass)
    if hass.data.get(_SERVICE_SPY_INSTALLED_KEY):
        return calls

    @callback
    def _on_call_service(event: Event[Any]) -> None:
        raw_data = event.data.get("service_data")
        calls.append(
            RecordedServiceCall(
                domain=str(event.data.get("domain") or ""),
                service=str(event.data.get("service") or ""),
                data=dict(raw_data) if isinstance(raw_data, dict) else {},
                context=event.context,
            )
        )

    hass.data[_SERVICE_SPY_INSTALLED_KEY] = hass.bus.async_listen(
        EVENT_CALL_SERVICE, _on_call_service
    )
    return calls


def mock_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    handler: Callable[[ServiceCall], Any] | None = None,
    *,
    schema: Any = None,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> list[ServiceCall]:
    """Register a mock service on real `hass.services` and return its captured `ServiceCall` list."""
    install_service_call_recorder(hass)
    per_service_calls: list[ServiceCall] = []

    async def _svc_handler(call: ServiceCall) -> Any:
        per_service_calls.append(call)
        if handler is not None:
            res = handler(call)
            if asyncio.iscoroutine(res):
                return await res
            return res
        return {} if supports_response != SupportsResponse.NONE else None

    hass.services.async_register(
        domain,
        service,
        _svc_handler,
        schema=schema,
        supports_response=supports_response,
    )
    return per_service_calls


def register_common_target_services(hass: HomeAssistant) -> None:
    """Register lightweight target services for external domains not backed by Latter entity platforms."""
    install_service_call_recorder(hass)
    for dom, services in _COMMON_TARGET_SERVICES.items():
        for svc in services:
            if not hass.services.has_service(dom, svc):
                mock_service(hass, dom, svc)


__all__ = [
    "RecordedServiceCall",
    "get_service_calls",
    "install_service_call_recorder",
    "mock_service",
    "register_common_target_services",
]
