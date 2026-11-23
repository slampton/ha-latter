"""Security, RPC outbox, LRU cache concurrency, sensor fusion, and broadcast/DND regression suite."""

from __future__ import annotations

import json
import threading
from typing import Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.latter.const import (
    CONF_AREA_FUSION_CONFIG,
    CONF_BROADCAST_SPEAKERS,
    CONF_CAMERA_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_DO_NOT_DISTURB,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    DOMAIN,
    RPC_AREA_ACTION,
    RPC_INTERCOM_BROADCAST,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_NOTIFY,
    SUBENTRY_DEVICE,
)
from custom_components.latter.doorbell import bind_coordinator_doorbell_listener
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.media_cache import (
    _ARTWORK_LRU_CACHE,
    _THUMB_LRU_CACHE,
    _cache_get,
    _cache_put,
    evict_wallpaper_lru_cache,
    get_circular_mask_surfaces,
)
from custom_components.latter.presence.area_fusion import (
    discover_area_fusion_sensors,
    evaluate_area_sensor_fusion,
)
from custom_components.latter.presence.ble_fabric import (
    get_all_areas_presence_summary,
    get_ble_fabric,
)
from custom_components.latter.protocol_policy import (
    MAX_PIN_LEN,
    MIN_PIN_LEN,
    PinLockoutTracker,
    PinWrapError,
    hash_security_pin,
    mint_pin_session_key,
    unwrap_pin_code,
    wrap_pin_code,
)
from custom_components.latter.services.rpc_slots import (
    async_execute_intercom_broadcast as _async_execute_intercom_broadcast,
)
from tests.helpers import (
    get_service_calls,
    make_subentry,
    mock_service,
    register_device,
    register_entity,
)


async def test_pin_session_key_crypto_bounds_and_exponential_lockout(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify v1 session-key PIN wrap/unwrap, 4..12 digit bounds, anti-replay, and 5-try lockout."""
    assert (MIN_PIN_LEN, MAX_PIN_LEN) == (4, 12)
    key_id, key_bytes = mint_pin_session_key()
    assert len(key_id) == 8 and key_id == key_id.lower()
    assert len(key_bytes) == 32

    # 1. Round-trip 4-digit and 12-digit PINs
    w4 = wrap_pin_code(key_id, key_bytes, 1, "lock.front_door", "unlock", "2468")
    assert w4.startswith(f"v1:{key_id}:00000001:")
    pin4, n1 = unwrap_pin_code(key_id, key_bytes, 0, "lock.front_door", "unlock", w4)
    assert (pin4, n1) == ("2468", 1)

    w12 = wrap_pin_code(
        key_id, key_bytes, 2, "alarm_control_panel.main", "disarm", "987654321012"
    )
    pin12, n2 = unwrap_pin_code(
        key_id, key_bytes, n1, "alarm_control_panel.main", "disarm", w12
    )
    assert (pin12, n2) == ("987654321012", 2)

    # 2. Out-of-bounds / non-digit PINs rejected
    for bad_pin in ("123", "1234567890123", "12a4", ""):
        with pytest.raises(ValueError):
            wrap_pin_code(key_id, key_bytes, 3, "lock.front_door", "unlock", bad_pin)
        with pytest.raises(ValueError):
            hash_security_pin(bad_pin)
    assert hash_security_pin("987654321012").startswith("pbkdf2_sha256$")

    # 3. Replay, key mismatch, entity/action binding mismatch, tampered MAC, and plaintext rejection
    with pytest.raises(PinWrapError) as err_replay:
        unwrap_pin_code(key_id, key_bytes, n2, "alarm_control_panel.main", "disarm", w12)
    assert err_replay.value.reason == "replay"

    other_id, other_bytes = mint_pin_session_key()
    with pytest.raises(PinWrapError) as err_kid:
        unwrap_pin_code(
            other_id, other_bytes, 0, "lock.front_door", "unlock", w4
        )
    assert err_kid.value.reason == "key_mismatch"

    with pytest.raises(PinWrapError) as err_ent:
        unwrap_pin_code(key_id, key_bytes, 0, "lock.back_door", "unlock", w4)
    assert err_ent.value.reason == "bad_mac"

    with pytest.raises(PinWrapError) as err_act:
        unwrap_pin_code(key_id, key_bytes, 0, "lock.front_door", "open", w4)
    assert err_act.value.reason == "bad_mac"

    tampered = w4[:-2] + ("00" if w4[-2:] != "00" else "ff")
    with pytest.raises(PinWrapError) as err_mac:
        unwrap_pin_code(key_id, key_bytes, 0, "lock.front_door", "unlock", tampered)
    assert err_mac.value.reason == "bad_mac"

    with pytest.raises(PinWrapError) as err_plain:
        unwrap_pin_code(key_id, key_bytes, 0, "lock.front_door", "unlock", "2468")
    assert err_plain.value.reason == "malformed"

    # 4. PinLockoutTracker deterministic 5-try lockout + 60s exponential backoff up to 900s
    fake_now = 1000.0
    tracker = PinLockoutTracker(clock=lambda: fake_now)
    for attempt in range(1, 5):
        assert tracker.record_failure("dev1") == 0.0
        assert tracker.failure_count("dev1") == attempt
        assert tracker.is_locked_out("dev1") is False

    assert tracker.record_failure("dev1") == 60.0
    assert tracker.is_locked_out("dev1") is True
    assert tracker.remaining_cooldown("dev1") == 60.0

    fake_now += 61.0
    assert tracker.is_locked_out("dev1") is False
    # 6th consecutive failure doubles cooldown to 120s; subsequent failures cap at 900s
    assert tracker.record_failure("dev1") == 120.0
    fake_now += 121.0
    for expected_cd in (240.0, 480.0, 900.0, 900.0):
        assert tracker.record_failure("dev1") == expected_cd
        fake_now += expected_cd + 1.0
    tracker.record_success("dev1")
    assert tracker.failure_count("dev1") == 0

    # 5. End-to-end RPC enforcement: plaintext rejected, 5 bad tries trigger security_pin_locked_out
    entry, sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    hass.states.async_set("lock.front_door", "locked", {"friendly_name": "Front Door"})
    unlocked_calls: list[dict[str, Any]] = []
    mock_service(
        hass, "lock", "unlock", lambda call: unlocked_calls.append(dict(call.data))
    )
    get_global_config(hass)[CONF_SECURITY_PIN_HASH] = hash_security_pin(
        "135790123456"
    )
    coord.update_device_config(
        {**coord.device_data, CONF_SECURITY_PIN_POLICY: "require_pin"}
    )

    clock_val = 5000.0
    coord.pin_lockout._clock = lambda: clock_val
    sys_obj.pin_lockout._clock = lambda: clock_val

    # Plaintext PIN over RPC is rejected (counts as failure 1)
    with pytest.raises(ServiceValidationError) as exc_plain:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_AREA_ACTION,
            {
                "entity_id": "lock.front_door",
                "action": "unlock",
                "code": "135790123456",
            },
        )
    assert exc_plain.value.translation_key == "security_pin_invalid"

    # Attempts 2..4 with wrong wrapped PIN -> security_pin_invalid
    for nonce in (1, 2, 3):
        bad_wrapped = wrap_pin_code(
            coord.pin_session_key_id,
            coord.pin_session_key_bytes,
            nonce,
            "lock.front_door",
            "unlock",
            "0000",
        )
        with pytest.raises(ServiceValidationError) as exc_bad:
            await sys_obj.rpc_dispatcher.async_dispatch(
                coord,
                RPC_AREA_ACTION,
                {
                    "entity_id": "lock.front_door",
                    "action": "unlock",
                    "code": bad_wrapped,
                },
            )
        assert exc_bad.value.translation_key == "security_pin_invalid"

    # 5th failure triggers security_pin_locked_out
    bad_wrapped_5 = wrap_pin_code(
        coord.pin_session_key_id,
        coord.pin_session_key_bytes,
        4,
        "lock.front_door",
        "unlock",
        "1111",
    )
    with pytest.raises(ServiceValidationError) as exc_lock5:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_AREA_ACTION,
            {
                "entity_id": "lock.front_door",
                "action": "unlock",
                "code": bad_wrapped_5,
            },
        )
    assert exc_lock5.value.translation_key == "security_pin_locked_out"

    # Even the VALID 12-digit PIN is blocked while locked out!
    valid_during_lockout = wrap_pin_code(
        coord.pin_session_key_id,
        coord.pin_session_key_bytes,
        5,
        "lock.front_door",
        "unlock",
        "135790123456",
    )
    with pytest.raises(ServiceValidationError) as exc_still_locked:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_AREA_ACTION,
            {
                "entity_id": "lock.front_door",
                "action": "unlock",
                "code": valid_during_lockout,
            },
        )
    assert exc_still_locked.value.translation_key == "security_pin_locked_out"
    assert unlocked_calls == []

    # Advance past 60s cooldown -> valid 12-digit wrapped PIN succeeds and resets failure count
    clock_val += 61.0
    valid_after_cooldown = wrap_pin_code(
        coord.pin_session_key_id,
        coord.pin_session_key_bytes,
        6,
        "lock.front_door",
        "unlock",
        "135790123456",
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_AREA_ACTION,
        {
            "entity_id": "lock.front_door",
            "action": "unlock",
            "code": valid_after_cooldown,
        },
    )
    assert unlocked_calls == [{"entity_id": "lock.front_door"}]
    assert coord.pin_lockout.failure_count(coord.subentry_id) == 0
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_rpc_receiver_rebind_silent_seed_no_replay_and_hidden_outbox(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify rebind() seeds (boot_id, seq) silently without replay and auto-hides outbox."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ent_reg = er.async_get(hass)
    rpc_eid = f"sensor.{coord.device_slug}_system_rpc_outbox"

    # Verify initial setup auto-hid the outbox entity with RegistryEntryHider.INTEGRATION
    reg_entry = ent_reg.async_get(rpc_eid)
    assert reg_entry is not None
    assert reg_entry.hidden_by == er.RegistryEntryHider.INTEGRATION

    register_entity(
        hass,
        "light.living_lamp",
        platform="hue",
        config_entry_id="entry_hue_bridge",
        area_id="living_room",
    )
    hass.states.async_set("light.living_lamp", "off", {"friendly_name": "Living Lamp"})
    calls = get_service_calls(hass)
    calls.clear()

    # Simulate receiver stop + stale frame sitting in state machine across HA/ESPHome reconnect
    coord._rpc_receiver.stop()
    ent_reg.async_update_entity(rpc_eid, hidden_by=None)
    env_json = json.dumps(
        {
            "s": "area_action",
            "d": {"entity_id": "light.living_lamp", "action": "toggle"},
        },
        separators=(",", ":"),
    )
    stale_frame = f"b00742:17:1/1|{env_json}"
    hass.states.async_set(rpc_eid, stale_frame)

    # Rebind must auto-hide outbox AND silently seed (b00742, 17) with ZERO replay!
    coord._rpc_receiver.rebind()
    await hass.async_block_till_done()
    assert ent_reg.async_get(rpc_eid).hidden_by == er.RegistryEntryHider.INTEGRATION
    assert [c for c in calls if c.domain == "light"] == []

    # Re-emitting seq 17 on same boot_id is still ignored (already seeded in _completed)
    hass.states.async_set(rpc_eid, "")
    hass.states.async_set(rpc_eid, stale_frame)
    await hass.async_block_till_done()
    assert [c for c in calls if c.domain == "light"] == []

    # Emitting (b00742, seq=18) dispatches normally!
    next_frame = f"b00742:18:1/1|{env_json}"
    hass.states.async_set(rpc_eid, next_frame)
    await hass.async_block_till_done()
    light_calls = [c for c in calls if c.domain == "light"]
    assert len(light_calls) == 1
    assert light_calls[0].service == "toggle"
    assert light_calls[0].data == {"entity_id": "light.living_lamp"}
    assert await hass.config_entries.async_unload(entry.entry_id) is True


def test_multithreaded_lru_cache_and_mask_concurrency_stress() -> None:
    """Verify concurrent _ARTWORK_LRU_CACHE / _THUMB_LRU_CACHE reads, writes, and evictions never raise."""
    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def _worker(tid: int) -> None:
        try:
            barrier.wait(timeout=5.0)
            for i in range(250):
                key = (f"upload:photo_{i % 48}.jpg", 240, 240, tid % 2 == 0, 1.0)
                _cache_put(_ARTWORK_LRU_CACHE, key, b"\xff\xd8\xff\xd9", limit=24)
                _cache_put(_THUMB_LRU_CACHE, key, b"\xff\xd8\xff\xd9", limit=32)
                _ = _cache_get(_ARTWORK_LRU_CACHE, key)
                _ = _cache_get(_THUMB_LRU_CACHE, key)
                if i % 7 == 0:
                    evict_wallpaper_lru_cache(f"upload:photo_{i % 48}.jpg")
                if i % 19 == 0:
                    _ = get_circular_mask_surfaces(
                        64 + (tid % 3) * 16, 64 + (tid % 3) * 16
                    )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(idx,)) for idx in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert errors == []


async def test_own_occupancy_exclusion_and_ble_and_sensor_fail_closed(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify self-feedback rejection on binary_sensor.<area>_occupancy and fail-closed ble_and_sensor."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ent_reg = er.async_get(hass)
    fabric = get_ble_fabric(hass)

    # 1. Self-feedback exclusion: binary_sensor.latter_system_living_room_occupancy exists and is NEVER discovered or accepted as physical input
    own_occ_eid = "binary_sensor.latter_system_living_room_occupancy"
    assert hass.states.get(own_occ_eid) is not None
    assert ent_reg.async_get(own_occ_eid) is not None
    ent_reg.async_update_entity(own_occ_eid, area_id="living_room")

    # Even if forced "on" in state machine and explicitly listed in fusion config, own sensor is ignored
    hass.states.async_set(
        own_occ_eid,
        "on",
        {"device_class": "occupancy", "friendly_name": "Living Room Occupancy"},
    )
    occ_on, occ_off, motion_on, _door, avail = discover_area_fusion_sensors(
        hass, "living_room", [own_occ_eid]
    )
    assert own_occ_eid not in occ_on
    assert own_occ_eid not in occ_off
    assert own_occ_eid not in motion_on
    assert own_occ_eid not in avail

    # When BLE leaves living_room -> kitchen, living_room clears cleanly with zero self-latch!
    assert coord.ble_tracker is not None
    coord.ble_tracker.current_area_id = "kitchen"
    coord.ble_tracker.is_away = False
    fabric.notify_occupancy_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(own_occ_eid).state == "off"

    # 2. Fail-closed fusion: ble_and_sensor fails closed when configured physical sensor is unavailable or unknown
    mmwave_eid = "binary_sensor.living_room_mmwave"
    register_entity(
        hass,
        mmwave_eid,
        platform="esphome",
        config_entry_id="esp_entry_pocket_assistant",
        area_id="living_room",
        original_device_class="occupancy",
    )
    get_global_config(hass)[CONF_AREA_FUSION_CONFIG] = {
        "living_room": {
            "mode": "ble_and_sensor",
            "sensors": [mmwave_eid],
            "threshold_pct": 50,
        }
    }
    coord.ble_tracker.current_area_id = "living_room"
    coord.ble_tracker.is_away = False

    # Physical sensor ON + BLE present -> occupied
    hass.states.async_set(
        mmwave_eid,
        "on",
        {"device_class": "occupancy", "friendly_name": "Living mmWave"},
    )
    fabric.notify_occupancy_listeners()
    res_on = evaluate_area_sensor_fusion(
        hass, "living_room", ble_present=True, best_rssi=-62
    )
    assert res_on["is_occupied"] is True
    assert res_on["confidence_pct"] > 0
    assert res_on["unavailable_sensors"] == []

    # Physical sensor UNAVAILABLE or UNKNOWN -> MUST fail closed (is_occupied=False, confidence_pct=0)!
    for degraded_state in ("unavailable", "unknown"):
        hass.states.async_set(
            mmwave_eid,
            degraded_state,
            {"device_class": "occupancy", "friendly_name": "Living mmWave"},
        )
        fabric.notify_occupancy_listeners()
        await hass.async_block_till_done()
        res_deg = evaluate_area_sensor_fusion(
            hass, "living_room", ble_present=True, best_rssi=-62
        )
        assert res_deg["is_occupied"] is False
        assert res_deg["confidence_pct"] == 0
        assert mmwave_eid in res_deg["unavailable_sensors"]
        summary_map = {
            row["area_id"]: row for row in get_all_areas_presence_summary(hass)
        }
        assert summary_map["living_room"]["is_occupied"] is False

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_broadcast_caller_exclusion_empty_pool_and_dnd_behavior(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify caller_subentry_id & empty broadcast_speakers error, plus DND suppression & silent doorbell."""
    entry, _initial_sys, _initial_pocket = await setup_latter_hub(hass)

    # Add a second display Device in Kitchen (`desk_panel`) via real ConfigSubentry + reload
    esp_desk, mac_desk = make_esphome_device(
        hass,
        slug="desk_panel",
        mac="aa:bb:cc:dd:ee:02",
        name="Desk Panel",
        area_id="kitchen",
        stationary=1,
    )
    sub_desk = make_subentry(
        {
            CONF_ESPHOME_DEVICE_ID: esp_desk.id,
            "mac": mac_desk,
            CONF_DEVICE_SLUG: "desk_panel",
            CONF_DEFAULT_AREA: "kitchen",
            CONF_DEFAULT_SPEAKER: "media_player.desk_panel_music",
            CONF_NATIVE_BLE_TRACKING: False,
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Desk Panel",
        unique_id=mac_desk,
        subentry_id="sub_desk",
    )
    hass.config_entries.async_add_subentry(entry, sub_desk)
    await hass.async_block_till_done()
    if "sub_desk" not in entry.runtime_data.coordinators:
        assert await hass.config_entries.async_reload(entry.entry_id) is True
        await hass.async_block_till_done()
    sys_obj = entry.runtime_data
    coord_pocket = sys_obj.coordinators["sub_pocket"]
    coord_desk = sys_obj.coordinators["sub_desk"]

    tts_calls: list[dict[str, Any]] = []
    hass.states.async_set("tts.piper", "unknown", {})
    mock_service(
        hass, "tts", "speak", lambda call: tts_calls.append(dict(call.data))
    )

    pocket_notifies: list[dict[str, Any]] = []
    desk_notifies: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_show_notification",
        lambda call: pocket_notifies.append(dict(call.data)),
    )
    mock_service(
        hass,
        "esphome",
        "desk_panel_latter_show_notification",
        lambda call: desk_notifies.append(dict(call.data)),
    )

    # 1. Empty broadcast_speakers raises ServiceValidationError(translation_key="no_broadcast_speakers")
    get_global_config(hass)[CONF_BROADCAST_SPEAKERS] = []
    with pytest.raises(ServiceValidationError) as exc_empty:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INTERCOM_BROADCAST,
            {"message": "Hello everyone"},
            blocking=True,
        )
    assert exc_empty.value.translation_key == "no_broadcast_speakers"
    assert tts_calls == []

    # Configure both speakers in broadcast_speakers
    get_global_config(hass)[CONF_BROADCAST_SPEAKERS] = [
        "media_player.pocket_assistant_music",
        "media_player.desk_panel_music",
    ]

    # Caller exclusion with caller_subentry_id excludes caller WITHOUT clobbering target_device!
    res_caller = await _async_execute_intercom_broadcast(
        hass,
        {"target_device": "desk_panel", "message": "Dinner in kitchen"},
        caller_subentry_id="sub_pocket",
    )
    assert res_caller["delivered"] is True
    assert res_caller["targets"] == ["media_player.desk_panel_music"]
    assert tts_calls[-1]["media_player_entity_id"] == ["media_player.desk_panel_music"]

    # Device-originated RPC intercom_broadcast from sub_pocket with target="all" excludes sub_pocket speaker
    tts_calls.clear()
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord_pocket,
        RPC_INTERCOM_BROADCAST,
        {"message": "Broadcast from pocket"},
    )
    assert len(tts_calls) == 1
    assert tts_calls[0]["media_player_entity_id"] == ["media_player.desk_panel_music"]

    # 2. Enable Do Not Disturb on desk_panel -> suppresses normal/warning notify & intercom_broadcast,
    # critical notify breaks through, and doorbell ring dispatches silent visual popup (chime=False)!
    coord_desk.update_device_config(
        {**coord_desk.device_data, CONF_DO_NOT_DISTURB: True}
    )
    assert coord_desk.do_not_disturb is True

    pocket_notifies.clear()
    desk_notifies.clear()
    tts_calls.clear()

    for prio in ("normal", "warning"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NOTIFY,
            {
                "target_device": "all",
                "title": "Heads Up",
                "message": f"{prio} note",
                "priority": prio,
                "announce": True,
            },
            blocking=True,
        )
    # Pocket received both; Desk in DND received ZERO!
    assert len(pocket_notifies) == 2
    assert desk_notifies == []

    # Intercom broadcast to "all" skips Desk (in DND) and delivers only to Pocket
    tts_calls.clear()
    res_dnd_bc = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": "all", "message": "Quiet check"},
        blocking=True,
        return_response=True,
    )
    assert res_dnd_bc["targets"] == ["media_player.pocket_assistant_music"]

    # Critical notify breaks through DND on Desk!
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {
            "target_device": "desk_panel",
            "title": "Smoke Alarm",
            "message": "Check kitchen immediately",
            "priority": "critical",
            "chime": True,
        },
        blocking=True,
    )
    assert len(desk_notifies) == 1
    assert desk_notifies[0]["priority"] == "critical"

    # Doorbell ring on configured camera: Desk (in DND) gets visual popup with chime=False; Pocket gets chime=True!
    door_dev = register_device(
        hass,
        config_entry_id="entry_doorbell_cam",
        entry_domain="doorbell_cam",
        identifiers={("doorbell_cam", "front_doorbell")},
        name="Front Doorbell",
        manufacturer="Latter",
        area_id="living_room",
    )
    register_entity(
        hass,
        "camera.front_doorbell",
        platform="doorbell_cam",
        config_entry_id="entry_doorbell_cam",
        device_id=door_dev.id,
        area_id="living_room",
    )
    register_entity(
        hass,
        "binary_sensor.front_doorbell_visitor",
        platform="doorbell_cam",
        config_entry_id="entry_doorbell_cam",
        device_id=door_dev.id,
        area_id="living_room",
        original_name="Visitor",
    )
    hass.states.async_set(
        "camera.front_doorbell", "streaming", {"friendly_name": "Front Doorbell"}
    )
    hass.states.async_set(
        "binary_sensor.front_doorbell_visitor", "off", {"friendly_name": "Visitor"}
    )
    get_global_config(hass)[CONF_CAMERA_ENTITIES] = [
        "camera.front_doorbell"
    ]
    bind_coordinator_doorbell_listener(coord_pocket)
    bind_coordinator_doorbell_listener(coord_desk)

    pocket_notifies.clear()
    desk_notifies.clear()
    hass.states.async_set(
        "binary_sensor.front_doorbell_visitor", "on", {"friendly_name": "Visitor"}
    )
    await hass.async_block_till_done()

    assert len(pocket_notifies) == 1
    assert pocket_notifies[0]["camera_entity"] == "camera.front_doorbell"
    assert pocket_notifies[0]["chime"] is True

    assert len(desk_notifies) == 1
    assert desk_notifies[0]["camera_entity"] == "camera.front_doorbell"
    assert desk_notifies[0]["chime"] is False

    assert await hass.config_entries.async_unload(entry.entry_id) is True
