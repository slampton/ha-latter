"""Unit and integration tests for D-075 Area-Aware Ambient Light Brightness."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.helpers import area_registry as ar, entity_registry as er
import pytest

from custom_components.latter.areas.registry import (
    apply_ambient_light_deadband,
    area_illuminance_sensor_choices,
    format_ambient_lux,
    normalize_ambient_lux,
    resolve_area_ambient_light,
)
from custom_components.latter.const import (
    CONF_AREA_ILLUMINANCE_CONFIG,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    STUDIO_REV,
)
from custom_components.latter.studio.cmd_presence_devices import (
    compute_illuminance_calibration_from_stats,
)
from custom_components.latter.studio.settings_cleaners import (
    SettingsScopeError,
    clean_area_illuminance,
)


async def _call_ws(
    hass: Any,
    conn: websocket_api.ActiveConnection,
    msg_id: int,
    msg_type: str,
    **kwargs: Any,
) -> None:
    handler = hass._ws_commands[msg_type]
    schema = getattr(handler, "_ws_schema", None)
    raw_msg = {"id": msg_id, "type": msg_type, **kwargs}
    validated = schema(raw_msg) if schema is not None else raw_msg
    await handler(hass, conn, validated)


def test_normalize_and_format_ambient_lux_real_sensor_ranges() -> None:
    """Verify logarithmic perceptual curve across diffused EP1 and bare tablet lux ranges."""
    # Diffused EP1 in Living Room (dark=0.0, bright=35.0): evening 5.6 lx maps cleanly to mid-bright
    assert normalize_ambient_lux(0.0, 0.0, 35.0) == 0
    eve_pct = normalize_ambient_lux(5.6, 0.0, 35.0)
    assert 48 <= eve_pct <= 60
    assert normalize_ambient_lux(35.0, 0.0, 35.0) == 100
    assert normalize_ambient_lux(98.6, 0.0, 35.0) == 100

    # Diffused EP1 in Office (dark=0.2, bright=15.0): evening 3.8 lx maps to ~55%
    assert normalize_ambient_lux(0.1, 0.2, 15.0) == 0
    off_eve = normalize_ambient_lux(3.8, 0.2, 15.0)
    assert 50 <= off_eve <= 62
    assert normalize_ambient_lux(15.0, 0.2, 15.0) == 100

    # Bare Kitchen Tablet (dark=5.0, bright=250.0): 5.0 lx night floor = 0%, 25 lx evening ~55%
    assert normalize_ambient_lux(5.0, 5.0, 250.0) == 0
    kit_eve = normalize_ambient_lux(25.0, 5.0, 250.0)
    assert 50 <= kit_eve <= 62
    assert normalize_ambient_lux(250.0, 5.0, 250.0) == 100

    assert format_ambient_lux(0.0) == "0"
    assert format_ambient_lux(0.02) == "0"
    assert format_ambient_lux(5.63) == "5.6"
    assert format_ambient_lux(5.0) == "5"
    assert format_ambient_lux(42.4) == "42"
    assert format_ambient_lux(150000.0) == "100000"


def test_ambient_light_deadband_suppresses_jitter_and_flushes_transitions() -> None:
    """Verify scale-independent 4% deadband suppresses noise yet reacts to Area/boundary changes."""
    s0 = apply_ambient_light_deadband(("", None, ""), "living_room", 52, "52|5.6")
    assert s0 == ("living_room", 52, "52|5.6")

    # Small +/-3% jitter within same Area stays suppressed
    s1 = apply_ambient_light_deadband(s0, "living_room", 55, "55|6.2")
    assert s1 == ("living_room", 52, "52|5.6")

    # >= 4% change updates immediately
    s2 = apply_ambient_light_deadband(s0, "living_room", 56, "56|6.5")
    assert s2 == ("living_room", 56, "56|6.5")

    # Boundary crossing to 0 or 100 updates immediately even if < 4% away
    s_near_zero = ("living_room", 2, "2|0.6")
    assert apply_ambient_light_deadband(s_near_zero, "living_room", 0, "0|0") == (
        "living_room",
        0,
        "0|0",
    )

    # Area switch flushes immediately even if normalized pct matches
    s3 = apply_ambient_light_deadband(s2, "office", 56, "56|3.8")
    assert s3 == ("office", 56, "56|3.8")

    # Sensor disappearing flushes to empty string immediately
    s4 = apply_ambient_light_deadband(s3, "office", None, "")
    assert s4 == ("office", None, "")


def test_compute_illuminance_calibration_rejects_direct_sun_spikes() -> None:
    """Verify 7-day hourly statistics calibration ignores isolated direct-sunlight spikes."""
    rows = [
        {"min": 0.9, "mean": 1.18},
        {"min": 0.9, "mean": 1.18},
        {"min": 0.9, "mean": 1.18},
        {"min": 1.0, "mean": 1.2},
        {"min": 1.2, "mean": 3.4},
        {"min": 1.5, "mean": 5.5},
        {"min": 8.0, "mean": 19.0},
        {"min": 14.0, "mean": 22.0},
        {"min": 18.0, "mean": 28.0},
        {"min": 20.0, "mean": 35.0},
        {"min": 22.0, "mean": 41.0},
        {"min": 17.0, "mean": 1118.6},  # brief direct sunbeam spike
    ]
    cal = compute_illuminance_calibration_from_stats(rows)
    assert cal is not None
    dark_lux, bright_lux = cal
    assert 0.8 <= dark_lux <= 1.2
    assert 30.0 <= bright_lux <= 60.0
    assert compute_illuminance_calibration_from_stats([]) is None


def test_clean_area_illuminance_validation() -> None:
    """Verify per-Area illuminance validation enforces Area allowlist and dark < bright."""
    allowed = {"sensor.living_room_ep1_illuminance"}
    cleaned = clean_area_illuminance(
        {},
        {
            "entity_id": "sensor.living_room_ep1_illuminance",
            "dark_lux": 1.0,
            "bright_lux": 35.0,
        },
        allowed,
    )
    assert cleaned == {
        "entity_id": "sensor.living_room_ep1_illuminance",
        "dark_lux": 1.0,
        "bright_lux": 35.0,
    }
    assert clean_area_illuminance(cleaned, {"entity_id": "disabled"}, allowed)["entity_id"] == "disabled"
    assert clean_area_illuminance(cleaned, {"entity_id": "auto"}, allowed)["entity_id"] == "auto"

    # Rejects dark_lux >= bright_lux, bool, NaN, Inf, and out-of-Area entities
    for bad_update in (
        {"dark_lux": 20.0, "bright_lux": 10.0},
        {"dark_lux": 20.0, "bright_lux": 20.0},
        {"dark_lux": True, "bright_lux": 35.0},
        {"dark_lux": 1.0, "bright_lux": False},
        {"dark_lux": float("nan"), "bright_lux": 35.0},
        {"dark_lux": 1.0, "bright_lux": float("inf")},
        {"entity_id": "sensor.other_room_lux"},
    ):
        with pytest.raises(SettingsScopeError):
            clean_area_illuminance({}, bad_update, allowed)


@pytest.mark.asyncio
async def test_area_ambient_light_wire_packing_and_studio_command(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify Area illuminance discovery, wire field 42 packing, and set_area_illuminance WS command."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    area_reg.async_create("Living Room", area_id="living_room")

    e1_id = "sensor.living_room_ep1_illuminance"
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id=e1_id,
            platform="esphome",
            area_id="living_room",
        )
    )
    hass.states.async_set(
        e1_id,
        "5.6",
        {
            "device_class": "illuminance",
            "unit_of_measurement": "lx",
            "friendly_name": "Living Room EP1 Illuminance",
        },
    )

    e_unavail_id = "sensor.a_tablet_illuminance"
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id=e_unavail_id,
            platform="esphome",
            area_id="living_room",
        )
    )
    hass.states.async_set(
        e_unavail_id,
        "unavailable",
        {
            "device_class": "illuminance",
            "unit_of_measurement": "lx",
            "friendly_name": "Tablet Illuminance",
        },
    )

    # Latter's own platform entities never leak into Area illuminance choices
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="sensor.living_room_latter_own_lux",
            platform=DOMAIN,
            area_id="living_room",
        )
    )
    hass.states.async_set(
        "sensor.living_room_latter_own_lux",
        "12.0",
        {"device_class": "illuminance", "unit_of_measurement": "lx"},
    )

    # Auto-discovery skips unavailable & own-platform sensors and picks the live EP1 sensor
    choices = area_illuminance_sensor_choices(hass, "living_room")
    assert len(choices) == 2
    assert all(c["entity_id"] != "sensor.living_room_latter_own_lux" for c in choices)
    amb = resolve_area_ambient_light(hass, "living_room")
    assert amb["resolved_entity"] == e1_id
    assert amb["lux_display"] == "5.6"
    assert amb["ambient_pct"] is not None

    coord.async_set_active_area("living_room")
    coord.cached_area_payload = None
    _state, area_attrs = coord.get_area_context_payload()
    wire = area_attrs["payload"].split("\x1f")
    assert len(wire) == 43
    assert wire[42] == f"{amb['ambient_pct']}|5.6"

    # Update per-Area calibration via Studio WebSocket command and confirm immediate refresh
    conn = websocket_api.ActiveConnection()
    await _call_ws(
        hass,
        conn,
        1,
        "latter/system/command",
        command="set_area_illuminance",
        payload={
            "area_id": "living_room",
            "entity_id": e1_id,
            "dark_lux": 0.0,
            "bright_lux": 35.0,
        },
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors

    saved_cfg = hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_AREA_ILLUMINANCE_CONFIG]
    assert saved_cfg["living_room"]["bright_lux"] == 35.0
    _state2, area_attrs2 = coord.get_area_context_payload()
    wire2 = area_attrs2["payload"].split("\x1f")
    assert wire2[42] == f"{normalize_ambient_lux(5.6, 0.0, 35.0)}|5.6"

    # Disabling the Area sensor clears wire field 42 cleanly (empty string, zero placeholders)
    await _call_ws(
        hass,
        conn,
        2,
        "latter/system/command",
        command="set_area_illuminance",
        payload={"area_id": "living_room", "entity_id": "disabled"},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    _state3, area_attrs3 = coord.get_area_context_payload()
    assert area_attrs3["payload"].split("\x1f")[42] == ""
