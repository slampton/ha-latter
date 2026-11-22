"""Tests for Home Hub rebuild, alarm caps, separate alarm vs Latter PINs, climate/cover controls, and categories."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import ServiceValidationError
import pytest

from custom_components.latter.areas.curation import (
    compute_alarm_caps,
    compute_climate_caps,
    compute_vacuum_caps,
)
from custom_components.latter.areas.telemetry import (
    get_available_home_categories,
    get_home_alarm_summary,
    get_home_hub_summary,
)
from custom_components.latter.const import (
    CONF_ALARM_ENTITY,
    CONF_BROADCAST_SPEAKERS,
    CONF_CAMERA_ENTITIES,
    CONF_GARAGE_ENTITIES,
    CONF_HOME_CATEGORIES,
    CONF_LOCK_ENTITIES,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_THERMOSTAT_ENTITIES,
    CONF_VACUUM_ENTITIES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
)
from custom_components.latter.protocol_policy import hash_security_pin, wrap_pin_code


async def test_home_hub_rebuild_alarm_caps_separate_pins_climate_cover_and_categories(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify alarm_caps bitmask, separate HA alarm vs Latter PINs, climate/cover/lock/vacuum dispatch, and 6-tab categories."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)

    # 1. Seed Home Hub entities: alarm with code_format="number", code_arm_required=False, supported_features=3
    hass.states.async_set(
        "alarm_control_panel.home_alarm",
        "armed_away",
        {
            "friendly_name": "Home Security",
            "code_format": "number",
            "code_arm_required": False,
            "supported_features": 3,
        },
    )
    hass.states.async_set(
        "climate.main_thermostat",
        "heat",
        {
            "friendly_name": "Main Thermostat",
            "temperature": 70,
            "current_temperature": 68.5,
            "hvac_modes": ["off", "heat", "cool", "auto"],
        },
    )
    hass.states.async_set(
        "lock.front_door",
        "locked",
        {"friendly_name": "Front Door", "supported_features": 0},
    )
    hass.states.async_set(
        "cover.main_garage",
        "closed",
        {"device_class": "garage", "friendly_name": "Main Garage"},
    )
    hass.states.async_set(
        "vacuum.robo_vac",
        "docked",
        {"friendly_name": "Robo Vac"},
    )
    hass.states.async_set(
        "camera.front_porch",
        "idle",
        {"friendly_name": "Front Porch"},
    )
    hass.states.async_set(
        "tts.piper",
        "unknown",
        {"friendly_name": "Piper TTS"},
    )
    await hass.async_block_till_done()

    global_cfg = hass.data[DOMAIN][DATA_GLOBAL_CONFIG]
    global_cfg[CONF_ALARM_ENTITY] = "alarm_control_panel.home_alarm"
    global_cfg[CONF_THERMOSTAT_ENTITIES] = ["climate.main_thermostat"]
    global_cfg[CONF_LOCK_ENTITIES] = ["lock.front_door"]
    global_cfg[CONF_GARAGE_ENTITIES] = ["cover.main_garage"]
    global_cfg[CONF_VACUUM_ENTITIES] = ["vacuum.robo_vac"]
    global_cfg[CONF_BROADCAST_SPEAKERS] = ["media_player.kitchen_speaker"]
    global_cfg[CONF_CAMERA_ENTITIES] = ["camera.front_porch"]

    # Set Latter System Security PIN to "2580" and stationary require_pin policy
    global_cfg[CONF_SECURITY_PIN_HASH] = hash_security_pin("2580")
    coord._runtime.hello_manifest = {**coord.hardware_manifest, "stationary": 1}
    assert coord.security_pin_policy == "require_pin"

    # Verify alarm_caps bitmask = 1 (disarm code) | 4 (arm_home) | 8 (arm_away) = 13
    alarm_sum = get_home_alarm_summary(hass, "alarm_control_panel.home_alarm")
    assert alarm_sum["alarm_caps"] == 13
    assert compute_alarm_caps(None) == 0

    # Verify code_arm_required=True + arm_night (sf=7) -> 1 | 2 | 4 | 8 | 16 = 31, and +arm_vacation (sf=39) -> 63
    hass.states.async_set(
        "alarm_control_panel.full_caps",
        "disarmed",
        {"code_format": "text", "code_arm_required": True, "supported_features": 7},
    )
    assert compute_alarm_caps(hass.states.get("alarm_control_panel.full_caps")) == 31
    hass.states.async_set(
        "alarm_control_panel.vacation_caps",
        "disarmed",
        {"code_format": "text", "code_arm_required": True, "supported_features": 39},
    )
    assert compute_alarm_caps(hass.states.get("alarm_control_panel.vacation_caps")) == 63
    hass.states.async_set(
        "alarm_control_panel.zero_sf",
        "disarmed",
        {"code_format": None, "supported_features": 0},
    )
    assert compute_alarm_caps(hass.states.get("alarm_control_panel.zero_sf")) == 12
    assert compute_climate_caps(None) == 0
    assert compute_vacuum_caps(None) == 0

    # Verify area_context wire indices 15..19 (summaries), 34 (home_categories), 38 (alarm_caps="13"), 39..40 (camera stream & alert entity)
    coord.cached_area_payload = None
    _area_st, area_attrs = coord.get_area_context_payload()
    assert area_attrs["alarm_caps"] == 13
    assert area_attrs["thermostats"][0]["caps"] == 79
    assert area_attrs["vacuums"][0]["caps"] == 11
    assert area_attrs["home_categories"] == "alarm,intercom,thermostat,entry,vacuum"
    wire_fields = area_attrs["payload"].split("\x1f")
    assert len(wire_fields) == 43  # 3 header fields + 40 body fields (indices 3..42)
    assert "climate.main_thermostat|Main Thermostat||heat|70|68.5|79" in wire_fields[15]
    assert "lock.front_door|Front Door||locked" in wire_fields[16]
    assert "cover.main_garage|Main Garage||closed" in wire_fields[17]
    assert "vacuum.robo_vac|Robo Vac||docked|11" in wire_fields[18]
    assert wire_fields[34] == "alarm,intercom,thermostat,entry,vacuum"
    assert wire_fields[38] == "13"
    assert "/api/latter/camera_stream/" in wire_fields[39]

    # Custom category ordering is preserved
    hub_sum = get_home_hub_summary(
        hass,
        thermostat_entities=["climate.main_thermostat"],
        lock_entities=["lock.front_door"],
        garage_entities=["cover.main_garage"],
        vacuum_entities=["vacuum.robo_vac"],
    )
    assert (
        get_available_home_categories(
            alarm_sum,
            hub_sum,
            home_categories="vacuum,intercom,alarm,entry,thermostat",
            coordinator=coord,
            hass=hass,
        )
        == "vacuum,intercom,alarm,entry,thermostat"
    )
    assert coord.home_categories_csv == "alarm,intercom,thermostat,entry,vacuum"
    assert CONF_HOME_CATEGORIES == "home_categories"

    # Register service recorders
    svc_calls: list[tuple[str, str, dict[str, Any]]] = []
    for dom_name, svcs in {
        "alarm_control_panel": (
            "alarm_arm_home",
            "alarm_arm_away",
            "alarm_arm_night",
            "alarm_arm_vacation",
            "alarm_disarm",
        ),
        "climate": ("set_temperature", "set_hvac_mode"),
        "lock": ("lock", "unlock"),
        "cover": ("open_cover", "close_cover", "stop_cover"),
        "vacuum": (
            "start",
            "turn_on",
            "pause",
            "stop",
            "turn_off",
            "return_to_base",
            "clean_spot",
            "locate",
        ),
    }.items():
        for svc_name in svcs:
            hass.services.async_register(
                dom_name,
                svc_name,
                lambda call, d=dom_name, s=svc_name: svc_calls.append(
                    (d, s, dict(call.data))
                ),
            )

    # 2. Separate PINs on home_hub.alarm:
    # Arming requires ZERO PIN when code_arm_required=False and omits "code"
    hub_nonce = 0

    def _wrap_hub(ent: str, act: str, pin: str) -> str:
        nonlocal hub_nonce
        hub_nonce += 1
        return wrap_pin_code(
            coord.pin_session_key_id, coord.pin_session_key_bytes, hub_nonce, ent, act, pin
        )

    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {
            "entity_id": "home_hub.alarm",
            "action": "arm_home",
        },
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {"action": "arm_away"},
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {"action": "arm_vacation"},
    )
    assert ("alarm_control_panel", "alarm_arm_home", {"entity_id": "alarm_control_panel.home_alarm"}) in svc_calls
    assert ("alarm_control_panel", "alarm_arm_away", {"entity_id": "alarm_control_panel.home_alarm"}) in svc_calls
    assert ("alarm_control_panel", "alarm_arm_vacation", {"entity_id": "alarm_control_panel.home_alarm"}) in svc_calls

    # Disarm with empty PIN when code_format="number" -> security_pin_required
    with pytest.raises(ServiceValidationError) as exc_empty_pin:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {"entity_id": "home_hub.alarm", "action": "disarm"},
        )
    assert exc_empty_pin.value.translation_key == "security_pin_required"

    # Disarm with non-4..12-digit / unwrapped PIN when code_format="number" -> security_pin_invalid
    with pytest.raises(ServiceValidationError) as exc_bad_fmt:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {"entity_id": "home_hub.alarm", "action": "disarm", "code": "12"},
        )
    assert exc_bad_fmt.value.translation_key == "security_pin_invalid"

    # Disarm with HA's SEPARATE alarm PIN ("9876", different from Latter's "2580"!) SUCCEEDS and forwards code!
    svc_calls.clear()
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {
            "entity_id": "home_hub.alarm",
            "action": "disarm",
            "code": _wrap_hub("home_hub.alarm", "disarm", "9876"),
        },
    )
    assert svc_calls == [
        (
            "alarm_control_panel",
            "alarm_disarm",
            {"entity_id": "alarm_control_panel.home_alarm", "code": "9876"},
        )
    ]

    # When HA alarm has NO code_format, disarm falls back to Latter's security_pin_hash ("2580")
    hass.states.async_set(
        "alarm_control_panel.home_alarm",
        "armed_home",
        {"friendly_name": "Home Security", "code_format": None, "code_arm_required": False},
    )
    with pytest.raises(ServiceValidationError) as exc_wrong_latter_pin:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "entity_id": "home_hub.alarm",
                "action": "disarm",
                "code": _wrap_hub("home_hub.alarm", "disarm", "9876"),
            },
        )
    assert exc_wrong_latter_pin.value.translation_key == "security_pin_invalid"

    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {
            "entity_id": "home_hub.alarm",
            "action": "disarm",
            "code": _wrap_hub("home_hub.alarm", "disarm", "2580"),
        },
    )

    # Restore code_format="number" and verify security_pin_policy="block" rejects disarm
    hass.states.async_set(
        "alarm_control_panel.home_alarm",
        "armed_away",
        {"friendly_name": "Home Security", "code_format": "number", "code_arm_required": False},
    )
    sub = entry.subentries["sub_pocket"]
    hass.config_entries.async_update_subentry(
        entry, sub, data={**sub.data, CONF_SECURITY_PIN_POLICY: "block"}
    )
    coord.subentry = entry.subentries["sub_pocket"]
    await coord.async_apply_options()

    with pytest.raises(ServiceValidationError) as exc_blocked_disarm:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "entity_id": "home_hub.alarm",
                "action": "disarm",
                "code": _wrap_hub("home_hub.alarm", "disarm", "9876"),
            },
        )
    assert exc_blocked_disarm.value.translation_key == "security_action_blocked"

    # Switch back to require_pin for lock/garage tests
    hass.config_entries.async_update_subentry(
        entry, sub, data={**sub.data, CONF_SECURITY_PIN_POLICY: "require_pin"}
    )
    coord.subentry = entry.subentries["sub_pocket"]
    await coord.async_apply_options()

    # 3. Thermostat setpoint & HVAC mode adaptation
    svc_calls.clear()
    for clim_act, clim_extra in (
        ("set_temperature", {"level": 72.5}),
        ("hvac_heat", {}),
        ("hvac_cool", {}),
        ("hvac_heat_cool", {}),
        ("hvac_off", {}),
    ):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {"entity_id": "climate.main_thermostat", "action": clim_act, **clim_extra},
        )
    # Reverse adaptation: hvac_modes has "heat_cool" (not "auto") -> adapts "hvac_auto" to "heat_cool"
    hass.states.async_set(
        "climate.main_thermostat",
        "heat_cool",
        {"hvac_modes": ["off", "heat", "cool", "heat_cool"]},
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {"entity_id": "climate.main_thermostat", "action": "hvac_auto"},
    )
    assert (
        "climate",
        "set_temperature",
        {"entity_id": "climate.main_thermostat", "temperature": 72.5},
    ) in svc_calls
    assert (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.main_thermostat", "hvac_mode": "heat"},
    ) in svc_calls
    assert (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.main_thermostat", "hvac_mode": "cool"},
    ) in svc_calls
    assert (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.main_thermostat", "hvac_mode": "auto"},
    ) in svc_calls
    assert (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.main_thermostat", "hvac_mode": "off"},
    ) in svc_calls
    assert (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.main_thermostat", "hvac_mode": "heat_cool"},
    ) in svc_calls

    # 4. Lock, Garage (open_cover / close_cover / stop_cover idempotent), and Vacuum
    svc_calls.clear()
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {"entity_id": "lock.front_door", "action": "lock"},
    )
    with pytest.raises(ServiceValidationError) as exc_lock_pin:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "entity_id": "lock.front_door",
                "action": "unlock",
                "code": _wrap_hub("lock.front_door", "unlock", "9876"),
            },
        )
    assert exc_lock_pin.value.translation_key == "security_pin_invalid"
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {
            "entity_id": "lock.front_door",
            "action": "unlock",
            "code": _wrap_hub("lock.front_door", "unlock", "2580"),
        },
    )

    # Garage is currently "closed": close_cover MUST still call close_cover (never toggle open!)
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {"entity_id": "cover.main_garage", "action": "close_cover"},
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {
            "entity_id": "cover.main_garage",
            "action": "open_cover",
            "code": _wrap_hub("cover.main_garage", "open_cover", "2580"),
        },
    )
    for g_ent, g_act in (
        ("cover.main_garage", "stop_cover"),
        ("vacuum.robo_vac", "start"),
        ("vacuum.robo_vac", "pause"),
        ("vacuum.robo_vac", "return_to_base"),
    ):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {"entity_id": g_ent, "action": g_act},
        )

    assert ("lock", "lock", {"entity_id": "lock.front_door"}) in svc_calls
    assert ("lock", "unlock", {"entity_id": "lock.front_door"}) in svc_calls
    assert ("cover", "close_cover", {"entity_id": "cover.main_garage"}) in svc_calls
    assert ("cover", "open_cover", {"entity_id": "cover.main_garage"}) in svc_calls
    assert ("cover", "stop_cover", {"entity_id": "cover.main_garage"}) in svc_calls
    assert ("vacuum", "start", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "pause", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "return_to_base", {"entity_id": "vacuum.robo_vac"}) in svc_calls

    # 5. Dual-setpoint range + fan_only + dry + Celsius climate_caps & range setpoint shifting
    hass.states.async_set(
        "climate.main_thermostat",
        "heat_cool",
        {
            "friendly_name": "Main Thermostat",
            "hvac_modes": ["off", "heat", "cool", "heat_cool", "fan_only", "dry"],
            "supported_features": 2,
            "temperature": None,
            "target_temp_low": 20.0,
            "target_temp_high": 24.0,
            "current_temperature": 21.5,
            "temperature_unit": "°C",
        },
    )
    assert compute_climate_caps(hass.states.get("climate.main_thermostat")) == 0xFF
    range_sum = get_home_hub_summary(
        hass, thermostat_entities=["climate.main_thermostat"]
    )
    assert range_sum["thermostats"][0]["target_temp"] == 22
    assert range_sum["thermostats"][0]["caps"] == 0xFF

    # Odd spread midpoint (20.0 .. 23.0 -> 21.5)
    hass.states.async_set(
        "climate.main_thermostat",
        "heat_cool",
        {
            "friendly_name": "Main Thermostat",
            "hvac_modes": ["off", "heat", "cool", "heat_cool", "fan_only", "dry"],
            "supported_features": 2,
            "temperature": None,
            "target_temp_low": 20.0,
            "target_temp_high": 23.0,
            "current_temperature": 21.5,
            "temperature_unit": "°C",
        },
    )
    assert (
        get_home_hub_summary(hass, thermostat_entities=["climate.main_thermostat"])[
            "thermostats"
        ][0]["target_temp"]
        == 21.5
    )

    svc_calls.clear()
    hass.states.async_set(
        "climate.main_thermostat",
        "heat_cool",
        {
            "friendly_name": "Main Thermostat",
            "hvac_modes": ["off", "heat", "cool", "heat_cool", "fan_only", "dry"],
            "supported_features": 2,
            "temperature": None,
            "target_temp_low": 20.0,
            "target_temp_high": 24.0,
            "current_temperature": 21.5,
            "temperature_unit": "°C",
        },
    )
    for act_c, extra_c in (
        ("set_temperature", {"level": 23.0}),
        ("hvac_fan_only", {}),
        ("dry", {}),
    ):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "entity_id": "climate.main_thermostat",
                "action": act_c,
                **extra_c,
            },
        )
    assert (
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.main_thermostat",
            "target_temp_low": 21.0,
            "target_temp_high": 25.0,
        },
    ) in svc_calls
    assert (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.main_thermostat", "hvac_mode": "fan_only"},
    ) in svc_calls
    assert (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.main_thermostat", "hvac_mode": "dry"},
    ) in svc_calls

    # 6. Full VacuumEntityFeature bitmask (`vacuum_caps` = 0x3F) + all vacuum verbs + TURN_ON/TURN_OFF fallback
    hass.states.async_set(
        "vacuum.robo_vac",
        "docked",
        {
            "friendly_name": "Robo Vac",
            "supported_features": 8192 | 4 | 8 | 16 | 1024 | 512,
        },
    )
    assert compute_vacuum_caps(hass.states.get("vacuum.robo_vac")) == 0x3F
    svc_calls.clear()
    for vac_act in ("clean", "pause", "stop", "dock", "clean_spot", "spot", "locate"):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "entity_id": "vacuum.robo_vac",
                "action": vac_act,
            },
        )
    assert ("vacuum", "start", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "pause", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "stop", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "return_to_base", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "clean_spot", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "locate", {"entity_id": "vacuum.robo_vac"}) in svc_calls

    # Legacy TURN_ON (1) | TURN_OFF (2) vacuum without START (8192) or STOP (8)
    hass.states.async_set(
        "vacuum.robo_vac",
        "docked",
        {"friendly_name": "Legacy Vac", "supported_features": 1 | 2},
    )
    assert compute_vacuum_caps(hass.states.get("vacuum.robo_vac")) == 0x05
    svc_calls.clear()
    for vac_act in ("start", "stop"):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "entity_id": "vacuum.robo_vac",
                "action": vac_act,
            },
        )
    assert ("vacuum", "turn_on", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "turn_off", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert await hass.config_entries.async_unload(entry.entry_id) is True
