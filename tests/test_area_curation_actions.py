"""Tests for Area curated entities, area actions, Home Hub strict shared entities, and wrapped PIN RPC."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock.const import LockEntityFeature
from homeassistant.exceptions import ServiceValidationError
import pytest

from custom_components.latter.areas.actions import async_execute_area_action
from custom_components.latter.areas.catalogs import (
    find_area_media_entities,
    get_area_available_domains,
    get_area_entities,
    get_areas_summary,
    get_home_wide_entities,
)
from custom_components.latter.areas.registry import match_area_by_name_or_id
from custom_components.latter.areas.telemetry import (
    get_available_home_categories,
    get_home_alarm_summary,
    get_home_hub_summary,
)
from custom_components.latter.const import (
    CONF_ALARM_ENTITY,
    CONF_BROADCAST_SPEAKERS,
    CONF_CAMERA_ENTITIES,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_DOCK_ITEMS,
    CONF_ESPHOME_DEVICE_ID,
    CONF_GARAGE_ENTITIES,
    CONF_LOCK_ENTITIES,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_THERMOSTAT_ENTITIES,
    CONF_VACUUM_ENTITIES,
    SUBENTRY_DEVICE,
)
from custom_components.latter.groups.esphome_inspector import (
    get_esphome_device_entities,
)
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.protocol_policy import hash_security_pin, wrap_pin_code
from custom_components.latter.remotes import build_remote_config_payload
from tests.helpers import (
    ensure_area,
    get_service_calls,
    make_subentry,
    mock_service,
    register_entity,
)


async def test_context_builder_curated_entities_and_area_actions(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise Area Context v3 building, curated filtering, whole-home summary, and all action verbs."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)

    # Seed rich controllable & environmental entities in living_room
    seeded: list[tuple[str, str, str, dict[str, Any]]] = [
        ("light.lr_ceiling", "hue", "on", {"brightness": 128, "friendly_name": "Living Room Ceiling"}),
        ("cover.lr_shades", "lutron", "open", {"current_position": 80, "device_class": "shade"}),
        ("fan.lr_fan", "bond", "on", {"percentage": 50, "friendly_name": "Ceiling Fan"}),
        ("switch.lr_outlet", "matter", "off", {"friendly_name": "Lamp Outlet"}),
        ("scene.movie_time", "homeassistant", "scening", {"friendly_name": "Movie Time"}),
        ("script.goodnight", "script", "off", {"friendly_name": "Goodnight"}),
        (
            "climate.lr_hvac",
            "ecobee",
            "heat",
            {"temperature": 70, "current_temperature": 68.5, "current_humidity": 44},
        ),
        (
            "sensor.lr_temp",
            "esphome_env",
            "71.4",
            {"device_class": "temperature", "unit_of_measurement": "°F"},
        ),
        (
            "sensor.lr_hum",
            "esphome_env",
            "46",
            {"device_class": "humidity", "unit_of_measurement": "%"},
        ),
        (
            "media_player.lr_ma",
            "music_assistant",
            "playing",
            {"volume_level": 0.4, "mass_player_type": "player", "friendly_name": "LR Speaker"},
        ),
        ("remote.lr_tv", "androidtv_remote", "on", {"friendly_name": "Living TV"}),
    ]
    for eid, platform, st_val, attrs in seeded:
        register_entity(hass, eid, platform=platform, area_id="living_room")
        hass.states.async_set(eid, st_val, attrs)

    # Whole-home perimeter & utility entities
    hass.states.async_set(
        "alarm_control_panel.home_alarm",
        "disarmed",
        {"friendly_name": "Home Alarm", "code_arm_required": False},
    )
    hass.states.async_set(
        "lock.front_door",
        "locked",
        {"friendly_name": "Front Door", "supported_features": 0},
    )
    hass.states.async_set(
        "lock.side_latch",
        "locked",
        {"friendly_name": "Side Latch", "supported_features": LockEntityFeature.OPEN},
    )
    hass.states.async_set(
        "cover.main_garage",
        "closed",
        {"device_class": "garage", "friendly_name": "Main Garage"},
    )
    hass.states.async_set("vacuum.roborock", "docked", {"friendly_name": "Roborock"})
    hass.states.async_set("button.reboot_router", "unknown", {})
    hass.states.async_set("select.theme_mode", "dark", {"options": ["dark", "light"]})
    hass.states.async_set("number.amp_gain", "50", {"min": 0, "max": 100})
    hass.states.async_set("update.node_fw", "on", {})
    await hass.async_block_till_done()

    assert match_area_by_name_or_id(hass, "Living Room") == "living_room"
    assert match_area_by_name_or_id(hass, "living-room") == "living_room"
    assert match_area_by_name_or_id(hass, "away") is None

    # Exact non-substring matching: Area "Garden" ("garden") MUST NOT match query "den"
    ensure_area(hass, "Garden", area_id="garden")
    assert match_area_by_name_or_id(hass, "Garden") == "garden"
    assert match_area_by_name_or_id(hass, "den") is None

    areas_summary = get_areas_summary(
        hass, active_area_id="living_room", local_speaker=coord.local_speaker
    )
    assert areas_summary and areas_summary[0]["id"] == "living_room"
    assert "1 on" in areas_summary[0]["name"]

    all_lr = get_area_entities(hass, "living_room", "all", coord.local_speaker)
    lr_ids = {item["id"] for item in all_lr}
    assert f"light.{coord.device_slug}_screen" not in lr_ids
    assert f"switch.{coord.device_slug}_screensaver" not in lr_ids
    assert f"switch.{coord.device_slug}_do_not_disturb" not in lr_ids
    avail = get_area_available_domains(hass, "living_room", coord.local_speaker, all_lr)
    assert avail == "scene,light,cover,fan,switch,climate,media"
    assert (
        get_area_available_domains(
            hass,
            "living_room",
            coord.local_speaker,
            all_lr,
            area_categories="media,light,all",
        )
        == "media,light,all"
    )
    assert (
        get_area_available_domains(
            hass,
            "living_room",
            coord.local_speaker,
            all_lr,
            area_categories="fan,scene",
        )
        == "fan,scene"
    )
    assert (
        get_area_available_domains(
            hass,
            "living_room",
            coord.local_speaker,
            [],
            area_categories="all,light",
        )
        == ""
    )

    assert len(get_area_entities(hass, "living_room", "lights", coord.local_speaker)) == 1
    assert len(get_area_entities(hass, "living_room", "covers", coord.local_speaker)) == 1
    assert len(get_area_entities(hass, "living_room", "fans", coord.local_speaker)) == 1
    assert len(get_area_entities(hass, "living_room", "switches", coord.local_speaker)) == 1
    assert len(get_area_entities(hass, "living_room", "scenes", coord.local_speaker)) == 1
    assert len(get_area_entities(hass, "living_room", "light,fan", coord.local_speaker)) == 2

    media_pair = find_area_media_entities(hass, "living_room", coord.local_speaker)
    assert media_pair == {"speaker": "media_player.lr_ma", "remote": "remote.lr_tv"}

    assert get_home_wide_entities(hass) == []
    assert get_home_alarm_summary(hass)["entity_id"] == ""
    assert get_home_hub_summary(hass)["thermostats"] == []

    global_cfg = get_global_config(hass)
    global_cfg[CONF_ALARM_ENTITY] = "alarm_control_panel.home_alarm"
    global_cfg[CONF_THERMOSTAT_ENTITIES] = ["climate.lr_hvac"]
    global_cfg[CONF_LOCK_ENTITIES] = ["lock.front_door"]
    global_cfg[CONF_GARAGE_ENTITIES] = ["cover.main_garage"]
    global_cfg[CONF_VACUUM_ENTITIES] = ["vacuum.roborock"]

    home_wide = get_home_wide_entities(
        hass, configured_alarm_entity="alarm_control_panel.home_alarm"
    )
    assert home_wide and home_wide[0]["id"] == "alarm_control_panel.home_alarm"

    wh = get_home_hub_summary(
        hass,
        thermostat_entities=["climate.lr_hvac"],
        lock_entities=["lock.front_door"],
        garage_entities=["cover.main_garage"],
        vacuum_entities=["vacuum.roborock"],
    )
    assert wh["thermostats"][0]["entity_id"] == "climate.lr_hvac"
    assert wh["locks"][0]["entity_id"] == "lock.front_door"
    assert wh["garages"][0]["entity_id"] == "cover.main_garage"
    assert wh["vacuums"][0]["entity_id"] == "vacuum.roborock"
    alarm_sum = get_home_alarm_summary(hass, "alarm_control_panel.home_alarm")
    assert (
        get_available_home_categories(alarm_sum, wh)
        == "alarm,thermostat,entry,vacuum"
    )
    assert (
        get_available_home_categories(
            alarm_sum, wh, home_categories="vacuum,entry"
        )
        == "vacuum,entry"
    )
    assert (
        get_available_home_categories(
            {"entity_id": ""},
            {
                "thermostats": [],
                "locks": [{"entity_id": "lock.front_door"}],
                "garages": [],
                "vacuums": [],
            },
            home_categories="alarm,thermostat,entry,vacuum",
        )
        == "entry"
    )

    esp_grouped = get_esphome_device_entities(
        hass, coord.esphome_device_id, coord.device_slug
    )
    assert esp_grouped["device"]["device_id"] == coord.esphome_device_id

    rem_empty_state, rem_empty_attrs = build_remote_config_payload(coord)
    assert rem_empty_state is None and "payload" in rem_empty_attrs
    get_global_config(hass)["remotes_list"] = ["remote.lr_tv"]
    coord.cached_remote_payload = None
    rem_state, rem_attrs = build_remote_config_payload(coord)
    assert rem_state == "Living TV" and "payload" in rem_attrs

    area_state, area_attrs = coord.get_area_context_payload()
    assert area_state == "Living Room"
    assert area_attrs["payload"].startswith("v3\x1f")

    # Mock target services and record calls across all action domains
    for svc_dom, svcs in {
        "light": ("turn_on", "turn_off", "toggle"),
        "cover": ("open_cover", "close_cover", "set_cover_position"),
        "fan": ("turn_on", "turn_off", "set_percentage"),
        "climate": ("set_hvac_mode", "set_temperature"),
        "scene": ("turn_on",),
        "script": ("turn_on",),
        "vacuum": ("start", "pause", "return_to_base"),
        "lock": ("lock", "unlock", "open"),
        "alarm_control_panel": ("alarm_arm_home", "alarm_disarm"),
        "button": ("press",),
        "select": ("select_option",),
        "number": ("set_value",),
        "update": ("install",),
        "media_player": ("volume_set", "media_play_pause"),
    }.items():
        for s_name in svcs:
            mock_service(hass, svc_dom, s_name)

    calls = get_service_calls(hass)
    calls.clear()

    await async_execute_area_action(hass, "light.lr_ceiling", "set_level", level=80)
    await async_execute_area_action(hass, "light.lr_ceiling", "set_level", level=0)
    await async_execute_area_action(hass, "light.lr_ceiling", "set_color", level=60, code="#3388FF")
    await async_execute_area_action(hass, "light.lr_ceiling", "set_kelvin", level=3200)
    await async_execute_area_action(hass, "light.lr_ceiling", "step_up")
    await async_execute_area_action(hass, "cover.lr_shades", "toggle")
    await async_execute_area_action(hass, "cover.lr_shades", "set_level", level=45)
    await async_execute_area_action(hass, "fan.lr_fan", "set_level", level=75)
    await async_execute_area_action(hass, "fan.lr_fan", "set_level", level=0)
    await async_execute_area_action(hass, "climate.lr_hvac", "cool")
    await async_execute_area_action(hass, "climate.lr_hvac", "step_up")
    await async_execute_area_action(hass, "scene.movie_time", "turn_on")
    await async_execute_area_action(hass, "script.goodnight", "turn_on")
    await async_execute_area_action(hass, "vacuum.roborock", "dock")
    await async_execute_area_action(hass, "button.reboot_router", "toggle")
    await async_execute_area_action(hass, "select.theme_mode", "select", option="light")
    await async_execute_area_action(hass, "number.amp_gain", "set_level", level=65)
    await async_execute_area_action(hass, "update.node_fw", "install")
    await async_execute_area_action(hass, "media_player.lr_ma", "step_up")
    await async_execute_area_action(hass, "lock.front_door", "unlock")
    await async_execute_area_action(hass, "lock.side_latch", "open")
    await async_execute_area_action(
        hass, "alarm_control_panel.home_alarm", "arm_home", code="1234"
    )

    with pytest.raises(ServiceValidationError) as exc_lock_toggle:
        await async_execute_area_action(hass, "lock.front_door", "toggle")
    assert exc_lock_toggle.value.translation_key == "explicit_action_required"

    with pytest.raises(ServiceValidationError) as exc_lock_open:
        await async_execute_area_action(hass, "lock.front_door", "open")
    assert exc_lock_open.value.translation_key == "not_supported"

    with pytest.raises(ServiceValidationError) as exc_alarm_toggle:
        await async_execute_area_action(hass, "alarm_control_panel.home_alarm", "toggle")
    assert exc_alarm_toggle.value.translation_key == "explicit_action_required"

    called_pairs = {(c.domain, c.service) for c in calls}
    assert ("light", "turn_on") in called_pairs
    assert ("cover", "close_cover") in called_pairs
    assert ("cover", "set_cover_position") in called_pairs
    assert ("fan", "set_percentage") in called_pairs
    assert ("climate", "set_hvac_mode") in called_pairs
    assert ("climate", "set_temperature") in called_pairs
    assert ("vacuum", "return_to_base") in called_pairs
    assert ("lock", "open") in called_pairs
    assert ("alarm_control_panel", "alarm_arm_home") in called_pairs

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_home_hub_strict_shared_entities_no_auto_discovery(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify unassigned Shared Entities never auto-discover HA entities or show Home Hub tabs."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, extra_device_data={CONF_DEFAULT_SPEAKER: ""}
    )

    # Seed every Home Hub domain + TTS + unrelated TV/speaker in Home Assistant states
    hass.states.async_set(
        "alarm_control_panel.unassigned_alarm",
        "armed_home",
        {"friendly_name": "Unassigned Alarm", "code_format": "number", "supported_features": 3},
    )
    hass.states.async_set(
        "climate.unassigned_hvac",
        "heat",
        {"friendly_name": "Unassigned HVAC", "temperature": 71, "hvac_modes": ["off", "heat"]},
    )
    hass.states.async_set(
        "lock.unassigned_lock",
        "locked",
        {"friendly_name": "Unassigned Lock"},
    )
    hass.states.async_set(
        "cover.unassigned_garage",
        "closed",
        {"device_class": "garage", "friendly_name": "Unassigned Garage"},
    )
    hass.states.async_set(
        "vacuum.unassigned_vac",
        "docked",
        {"friendly_name": "Unassigned Vacuum"},
    )
    hass.states.async_set(
        "camera.unassigned_cam",
        "idle",
        {"friendly_name": "Unassigned Camera"},
    )
    hass.states.async_set(
        "tts.piper",
        "unknown",
        {"friendly_name": "Piper TTS"},
    )
    hass.states.async_set(
        "media_player.living_room_tv",
        "idle",
        {"device_class": "tv", "friendly_name": "Living Room TV"},
    )
    await hass.async_block_till_done()

    # 1. With Shared Entities unassigned on a 1-device install (no default_speaker/doorbell_media_player):
    #    summaries and home_categories MUST all be empty ("") so ZERO Home Hub tabs appear!
    alarm_empty = get_home_alarm_summary(hass, None)
    assert alarm_empty == {
        "entity_id": "",
        "state": "",
        "name": "",
        "supported_features": 0,
        "code_arm_required": False,
        "alarm_caps": 0,
    }
    assert get_home_alarm_summary(hass) == alarm_empty
    assert get_home_wide_entities(hass) == []

    hub_empty = get_home_hub_summary(hass)
    assert hub_empty["thermostats"] == []
    assert hub_empty["locks"] == []
    assert hub_empty["garages"] == []
    assert hub_empty["vacuums"] == []
    assert list(hub_empty["thermostats_summary"]) == []
    assert list(hub_empty["locks_summary"]) == []
    assert list(hub_empty["garages_summary"]) == []
    assert list(hub_empty["vacuums_summary"]) == []
    assert (
        get_available_home_categories(
            alarm_empty, hub_empty, coordinator=coord, hass=hass
        )
        == ""
    )

    coord.cached_area_payload = None
    _st, empty_attrs = coord.get_area_context_payload()
    assert empty_attrs["home_categories"] == ""
    assert empty_attrs["alarm_entity"] == ""
    assert empty_attrs["alarm_caps"] == 0
    assert empty_attrs["thermostats"] == []
    assert empty_attrs["locks"] == []
    assert empty_attrs["garages"] == []
    assert empty_attrs["vacuums"] == []
    assert empty_attrs["payload"].split("\x1f")[34] == ""

    # Unassigned home_hub.alarm must NOT command unconfigured HA entities
    dispatched: list[tuple[str, str, dict[str, Any]]] = []
    mock_service(
        hass,
        "vacuum",
        "return_to_base",
        lambda call: dispatched.append(("vacuum", "return_to_base", dict(call.data))),
    )
    await async_execute_area_action(hass, "home_hub.alarm", "disarm")
    assert dispatched == []

    # 2. Explicitly assigning each Shared Entity immediately enables only its corresponding category
    global_cfg = get_global_config(hass)

    global_cfg[CONF_ALARM_ENTITY] = "alarm_control_panel.unassigned_alarm"
    coord.cached_area_payload = None
    assert coord.get_area_context_payload()[1]["home_categories"] == "alarm"

    global_cfg[CONF_CAMERA_ENTITIES] = ["camera.unassigned_cam"]
    coord.cached_area_payload = None
    cam_attrs = coord.get_area_context_payload()[1]
    assert cam_attrs["home_categories"] == "alarm"
    assert "/api/latter/camera_stream/" in cam_attrs["camera_stream_url"]
    assert cam_attrs["cameras_summary"][0][0] == "camera.unassigned_cam"

    global_cfg[CONF_THERMOSTAT_ENTITIES] = ["climate.unassigned_hvac"]
    coord.cached_area_payload = None
    assert (
        coord.get_area_context_payload()[1]["home_categories"]
        == "alarm,thermostat"
    )

    # Assigning lock/garage enables 'entry' ONLY (never 'intercom' by itself)
    global_cfg[CONF_LOCK_ENTITIES] = ["lock.unassigned_lock"]
    coord.cached_area_payload = None
    assert (
        coord.get_area_context_payload()[1]["home_categories"]
        == "alarm,thermostat,entry"
    )
    global_cfg.pop(CONF_LOCK_ENTITIES)
    global_cfg[CONF_GARAGE_ENTITIES] = ["cover.unassigned_garage"]
    coord.cached_area_payload = None
    assert (
        coord.get_area_context_payload()[1]["home_categories"]
        == "alarm,thermostat,entry"
    )

    global_cfg[CONF_VACUUM_ENTITIES] = ["vacuum.unassigned_vac"]
    coord.cached_area_payload = None
    assert (
        coord.get_area_context_payload()[1]["home_categories"]
        == "alarm,thermostat,entry,vacuum"
    )
    await async_execute_area_action(hass, "vacuum.unassigned_vac", "dock")
    assert dispatched == [
        ("vacuum", "return_to_base", {"entity_id": "vacuum.unassigned_vac"})
    ]

    # Assigning Broadcast speakers enables 'intercom' (Broadcast); unconfigured speakers keep it hidden even with 2 displays
    esp_dev_2, mac_2 = make_esphome_device(
        hass,
        slug="kitchen_panel",
        mac="aa:bb:cc:dd:ee:09",
        name="Kitchen Panel",
        area_id="kitchen",
        stationary=1,
    )
    hass.config_entries.async_add_subentry(
        entry,
        make_subentry(
            {
                CONF_ESPHOME_DEVICE_ID: esp_dev_2.id,
                "mac": mac_2,
                CONF_DEVICE_SLUG: "kitchen_panel",
            },
            subentry_type=SUBENTRY_DEVICE,
            title="Kitchen Panel",
            unique_id=mac_2,
            subentry_id="sub_kitchen",
        ),
    )
    await hass.async_block_till_done()
    coord = entry.runtime_data.coordinators["sub_pocket"]
    coord.cached_area_payload = None
    assert (
        coord.get_area_context_payload()[1]["home_categories"]
        == "alarm,thermostat,entry,vacuum"
    )

    global_cfg[CONF_BROADCAST_SPEAKERS] = ["media_player.living_room_tv"]
    coord.cached_area_payload = None
    assert (
        coord.get_area_context_payload()[1]["home_categories"]
        == "alarm,intercom,thermostat,entry,vacuum"
    )

    global_cfg.pop(CONF_BROADCAST_SPEAKERS)
    coord.cached_area_payload = None
    assert (
        coord.get_area_context_payload()[1]["home_categories"]
        == "alarm,thermostat,entry,vacuum"
    )

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_wrapped_pin_enforced_on_area_and_shortcut_rpc(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `area_action` and `shortcut_action` enforce `wrap_pin_code` envelopes and anti-replay nonces."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    register_entity(hass, "lock.front_door", platform="zwave_js", area_id="living_room")
    hass.states.async_set("lock.front_door", "locked", {"friendly_name": "Front Door"})

    unlocked_calls: list[dict[str, Any]] = []
    mock_service(
        hass, "lock", "unlock", lambda call: unlocked_calls.append(dict(call.data))
    )

    pin_hash = hash_security_pin("2468")
    coord.update_device_config(
        {
            **coord.device_data,
            CONF_SECURITY_PIN_POLICY: "require_pin",
            CONF_SECURITY_PIN_HASH: pin_hash,
            CONF_DOCK_ITEMS: [
                {"kind": "entity", "target": "lock.front_door", "action": "unlock", "label": "Unlock"},
            ],
        }
    )
    await hass.async_block_till_done()
    assert coord.pin_session_key_id and coord.pin_session_key_bytes

    # 1. Unwrapped plaintext PIN on `area_action` is rejected
    with pytest.raises(ServiceValidationError) as exc_plain:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {"entity_id": "lock.front_door", "action": "unlock", "code": "2468"},
        )
    assert exc_plain.value.translation_key == "security_pin_invalid"
    assert unlocked_calls == []

    # 2. Valid wrapped PIN (`nonce=1`) on `area_action` succeeds
    wrapped_area = wrap_pin_code(
        coord.pin_session_key_id,
        coord.pin_session_key_bytes,
        1,
        "lock.front_door",
        "unlock",
        "2468",
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {"entity_id": "lock.front_door", "action": "unlock", "code": wrapped_area},
    )
    assert len(unlocked_calls) == 1

    # 3. Replaying `nonce=1` is rejected
    with pytest.raises(ServiceValidationError) as exc_replay:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {"entity_id": "lock.front_door", "action": "unlock", "code": wrapped_area},
        )
    assert exc_replay.value.translation_key == "security_pin_invalid"
    assert len(unlocked_calls) == 1

    # 4. Fresh `nonce=2` wrapped PIN on `shortcut_action` succeeds
    wrapped_sc = wrap_pin_code(
        coord.pin_session_key_id,
        coord.pin_session_key_bytes,
        2,
        "lock.front_door",
        "unlock",
        "2468",
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "shortcut_action",
        {"entity_id": "lock.front_door", "action": "unlock", "code": wrapped_sc},
    )
    assert len(unlocked_calls) == 2

    assert await hass.config_entries.async_unload(entry.entry_id) is True
