"""Real-HA coverage tests for `doorbell.py` and `remotes.py` edge branches."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest

from custom_components.latter import doorbell as doorbell_mod
from custom_components.latter.const import (
    CONF_CAMERA_ENTITIES,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_REMOTES_LIST,
    CONF_VOLUME_OVERRIDES,
    DOMAIN,
)
from custom_components.latter.doorbell import (
    _async_boost_door_speaker_if_quiet,
    _async_stop_local_speaker,
    _is_valid_ring_transition,
    _spawn_coordinator_task,
    async_execute_doorbell_intercom,
    bind_coordinator_doorbell_listener,
    resolve_doorbell_ring_entities,
    resolve_doorbell_targets,
)
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.remotes import (
    _async_step_remote_volume_target,
    _parse_mp_volume_flags,
    _resolve_slot_platform,
    async_execute_remote_action,
    resolve_effective_remote_entities,
    resolve_remote_slot_pair,
)
from tests.helpers import mock_service, register_device, register_entity


def _make_state_event(
    entity_id: str | None,
    old_val: str | None,
    new_val: str | None,
) -> Event[Any]:
    """Construct a real HA `state_changed` event with real `State` instances."""
    old_state = State(entity_id, old_val) if (entity_id and old_val is not None) else None
    new_state = State(entity_id, new_val) if (entity_id and new_val is not None) else None
    return Event(
        "state_changed",
        {
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
        },
    )


async def test_doorbell_targets_ring_discovery_and_transition_validation(
    hass: Any,
) -> None:
    """Cover target override resolution, ring `event` preference, and ring transition guards."""
    # Empty / None camera returns default target info
    assert resolve_doorbell_targets(hass, None)["camera_entity"] == ""
    assert resolve_doorbell_targets(hass, "")["friendly_name"] == "Camera"

    # Register a doorbell device with camera, sibling speaker, event ring, binary ring, and noise
    porch_dev = register_device(
        hass,
        config_entry_id="entry_porch",
        entry_domain="generic_cam",
        identifiers={("generic_cam", "porch_1")},
        name="Porch Doorbell",
        area_id="entryway",
    )
    register_entity(
        hass,
        "camera.porch_cam",
        platform="generic_cam",
        device_id=porch_dev.id,
        config_entry_id="entry_porch",
    )
    register_entity(
        hass,
        "media_player.porch_sibling_spk",
        platform="generic_cam",
        device_id=porch_dev.id,
        config_entry_id="entry_porch",
    )
    register_entity(
        hass,
        "media_player.unifi_override_spk",
        platform="unifiprotect",
        config_entry_id="entry_unifi_override",
    )
    register_entity(
        hass,
        "event.porch_doorbell_ring",
        platform="generic_cam",
        device_id=porch_dev.id,
        config_entry_id="entry_porch",
    )
    register_entity(
        hass,
        "binary_sensor.porch_doorbell_ring",
        platform="generic_cam",
        device_id=porch_dev.id,
        config_entry_id="entry_porch",
    )
    register_entity(
        hass,
        "binary_sensor.porch_motion",
        platform="generic_cam",
        device_id=porch_dev.id,
        config_entry_id="entry_porch",
    )
    register_entity(
        hass,
        "event.porch_visitor_disabled",
        platform="generic_cam",
        device_id=porch_dev.id,
        config_entry_id="entry_porch",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    hass.states.async_set("camera.porch_cam", "streaming", {"friendly_name": "Porch Cam"})

    # Explicit `media_player.` volume override takes precedence and enables unifiprotect lead-in
    override_info = resolve_doorbell_targets(
        hass,
        "camera.porch_cam",
        volume_overrides={"camera.porch_cam": "  media_player.unifi_override_spk  "},
    )
    assert override_info["door_speaker"] == "media_player.unifi_override_spk"
    assert override_info["tts_lead_in"] is True
    assert override_info["area_id"] == "entryway"

    # Non-`media_player.` override is ignored and falls back to same-device sibling speaker
    fallback_info = resolve_doorbell_targets(
        hass,
        "camera.porch_cam",
        volume_overrides={"camera.porch_cam": "number.not_a_speaker"},
    )
    assert fallback_info["door_speaker"] == "media_player.porch_sibling_spk"
    assert fallback_info["tts_lead_in"] is False

    # Gate camera with binary_sensor ring only
    gate_dev = register_device(
        hass,
        config_entry_id="entry_gate",
        entry_domain="generic_cam",
        identifiers={("generic_cam", "gate_1")},
        name="Gate Cam",
    )
    register_entity(
        hass,
        "camera.gate_cam",
        platform="generic_cam",
        device_id=gate_dev.id,
        config_entry_id="entry_gate",
    )
    register_entity(
        hass,
        "binary_sensor.gate_visitor",
        platform="generic_cam",
        device_id=gate_dev.id,
        config_entry_id="entry_gate",
    )

    assert resolve_doorbell_ring_entities(hass, []) == {}
    ring_map = resolve_doorbell_ring_entities(
        hass,
        [
            "",
            "sensor.not_a_camera",
            "camera.unregistered_cam",
            "camera.porch_cam",
            "camera.gate_cam",
        ],
    )
    # `event.` ring entity takes priority over sibling `binary_sensor.` on porch_cam
    assert ring_map == {
        "event.porch_doorbell_ring": "camera.porch_cam",
        "binary_sensor.gate_visitor": "camera.gate_cam",
    }

    # `_is_valid_ring_transition` edge branches
    assert _is_valid_ring_transition(_make_state_event(None, "off", "on")) is None
    assert _is_valid_ring_transition(_make_state_event("binary_sensor.ring", None, "on")) is None
    assert _is_valid_ring_transition(_make_state_event("binary_sensor.ring", "off", None)) is None
    assert (
        _is_valid_ring_transition(_make_state_event("binary_sensor.ring", STATE_UNAVAILABLE, "on"))
        is None
    )
    assert (
        _is_valid_ring_transition(_make_state_event("binary_sensor.ring", STATE_UNKNOWN, "on"))
        is None
    )
    assert _is_valid_ring_transition(_make_state_event("binary_sensor.ring", "on", "off")) is None
    assert (
        _is_valid_ring_transition(_make_state_event("binary_sensor.ring", "on", STATE_UNAVAILABLE))
        is None
    )
    assert _is_valid_ring_transition(_make_state_event("binary_sensor.ring", "on", "on")) is None
    assert (
        _is_valid_ring_transition(_make_state_event("binary_sensor.ring", "idle", "ringing"))
        is None
    )
    assert (
        _is_valid_ring_transition(_make_state_event("binary_sensor.ring", "off", "on"))
        == "binary_sensor.ring"
    )

    now_utc = dt_util.utcnow()
    old_ts = (now_utc - timedelta(seconds=120)).isoformat()
    stale_ts = (now_utc - timedelta(seconds=60)).isoformat()
    fresh_ts = now_utc.isoformat()
    assert _is_valid_ring_transition(_make_state_event("event.ring", old_ts, "not-a-dt")) is None
    assert _is_valid_ring_transition(_make_state_event("event.ring", old_ts, stale_ts)) is None
    assert (
        _is_valid_ring_transition(_make_state_event("event.ring", old_ts, fresh_ts))
        == "event.ring"
    )


async def test_doorbell_speaker_helpers_and_volume_boost(hass: Any) -> None:
    """Cover local speaker stop guards/errors and door speaker quiet-volume boost edge cases."""
    # Empty local speaker returns immediately
    await _async_stop_local_speaker(hass, "")

    # Unregistered `media_player.media_stop` raises real ServiceNotFound, caught & logged cleanly
    await _async_stop_local_speaker(hass, "media_player.desk_speaker")

    vol_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "media_player",
        "volume_set",
        lambda call: vol_calls.append(dict(call.data)),
    )

    # Missing state -> no boost
    await _async_boost_door_speaker_if_quiet(hass, "media_player.missing_door")
    # Missing / bool / non-numeric / NaN / already loud volume_level -> no boost
    for raw_vol in (None, True, "bad_float", float("nan"), 0.50):
        attrs = {} if raw_vol is None else {"volume_level": raw_vol}
        hass.states.async_set("media_player.door_spk", "idle", attrs)
        await _async_boost_door_speaker_if_quiet(hass, "media_player.door_spk")
    assert vol_calls == []

    # Quiet speaker (< 0.25) -> boosted to 0.80
    hass.states.async_set("media_player.door_spk", "idle", {"volume_level": 0.10})
    await _async_boost_door_speaker_if_quiet(hass, "media_player.door_spk")
    assert vol_calls == [{"entity_id": "media_player.door_spk", "volume_level": 0.80}]

    # Boost service error is caught cleanly
    def _fail_vol(_call: Any) -> None:
        raise HomeAssistantError("Door speaker offline")

    mock_service(hass, "media_player", "volume_set", _fail_vol)
    await _async_boost_door_speaker_if_quiet(hass, "media_player.door_spk")


async def test_doorbell_intercom_talk_reply_restore_and_task_fallbacks(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover `_spawn_coordinator_task` fallbacks, camera index/toggle, listen errors, and talk restore."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    try:
        # 1) `_spawn_coordinator_task` entry fallback and hass fallback
        async def _tag_coro(val: str) -> str:
            return val

        with monkeypatch.context() as mp:
            mp.setattr(coord, "create_background_task", None)
            t_entry = _spawn_coordinator_task(hass, coord, _tag_coro("from_entry"), "test_entry_bg")
            assert await t_entry == "from_entry"

            mp.setattr(coord, "entry", None)
            t_hass = _spawn_coordinator_task(hass, coord, _tag_coro("from_hass"), "test_hass_bg")
            assert await t_hass == "from_hass"

        # 2) Seed UniFi doorbell camera + sibling door speaker + second camera
        db_dev = register_device(
            hass,
            config_entry_id="entry_unifi_db",
            entry_domain="unifiprotect",
            identifiers={("unifiprotect", "front_db")},
            name="Front Doorbell",
            area_id="entryway",
        )
        register_entity(
            hass,
            "camera.front_door",
            platform="unifiprotect",
            device_id=db_dev.id,
            config_entry_id="entry_unifi_db",
        )
        register_entity(
            hass,
            "media_player.front_door_spk",
            platform="unifiprotect",
            device_id=db_dev.id,
            config_entry_id="entry_unifi_db",
        )
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = [
            "camera.front_door",
            "camera.side_gate",
        ]
        hass.states.async_set("camera.front_door", "streaming", {"friendly_name": "Front Door"})
        hass.states.async_set("camera.side_gate", "idle", {"friendly_name": "Side Gate"})
        hass.states.async_set(
            "media_player.front_door_spk",
            "idle",
            {"friendly_name": "Front Door Speaker", "volume_level": 0.12},
        )
        hass.states.async_set("tts.piper", "unknown", {})

        # Non-visible explicit camera raises ServiceValidationError
        with pytest.raises(ServiceValidationError) as exc_cam:
            await async_execute_doorbell_intercom(
                hass, coord, action="listen_start", camera_entity="camera.hidden_cam"
            )
        assert exc_cam.value.translation_domain == DOMAIN
        assert exc_cam.value.translation_key == "not_supported"

        # `select_camera` with valid index and invalid non-int index
        info_idx = await async_execute_doorbell_intercom(
            hass, coord, action="select_camera", camera_index=1
        )
        assert info_idx["camera_entity"] == "camera.side_gate"
        assert coord.active_carousel_camera == "camera.side_gate"
        assert coord.doorbell_talk_state == "idle"

        bad_index: Any = "not_a_number"
        info_bad = await async_execute_doorbell_intercom(
            hass, coord, action="select_camera", camera_index=bad_index
        )
        assert info_bad["camera_entity"] == "camera.side_gate"

        # `set_noise_reduction` while idle updates setting without starting listen
        await async_execute_doorbell_intercom(
            hass, coord, action="set_noise_reduction", noise_reduction="strong"
        )
        assert coord.doorbell_noise_reduction == "strong"
        assert coord.doorbell_talk_state == "idle"

        # `listen_toggle` flips idle -> listening -> idle
        await async_execute_doorbell_intercom(
            hass, coord, action="listen_toggle", camera_entity="camera.front_door"
        )
        assert coord.doorbell_talk_state == "listening"
        await async_execute_doorbell_intercom(hass, coord, action="listen_toggle")
        assert coord.doorbell_talk_state == "idle"

        # `_async_start_camera_audio_listen` early return when no cameras configured
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = []
        coord.active_carousel_camera = ""
        await async_execute_doorbell_intercom(hass, coord, action="listen_start")
        assert coord.doorbell_talk_state == "idle"

        # Restore cameras and trigger `media_player.play_media` ServiceNotFound exception path
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = [
            "camera.front_door",
            "camera.side_gate",
        ]
        play_calls: list[dict[str, Any]] = []
        hass.services.async_remove("media_player", "play_media")
        try:
            await async_execute_doorbell_intercom(
                hass, coord, action="listen_start", camera_entity="camera.front_door"
            )
            assert coord.doorbell_talk_state == "listening"
        finally:
            mock_service(
                hass,
                "media_player",
                "play_media",
                lambda call: play_calls.append(dict(call.data)),
            )

        # 3) Full talk lifecycle: quiet speaker boost, unifiprotect lead-in, re-entrant cancel,
        # TTS announce failure, post-reply resume listen, post-reply idle, and non-talking abort.
        vol_calls: list[dict[str, Any]] = []
        tts_calls: list[dict[str, Any]] = []
        mock_service(
            hass,
            "media_player",
            "volume_set",
            lambda call: vol_calls.append(dict(call.data)),
        )
        mock_service(
            hass,
            "tts",
            "speak",
            lambda call: tts_calls.append(dict(call.data)),
        )

        orig_sleep = asyncio.sleep
        reply_gate = asyncio.Event()

        async def _gated_sleep(delay: float, result: Any = None) -> Any:
            if delay >= 2.0:
                await reply_gate.wait()
                return result
            return await orig_sleep(delay, result)

        with monkeypatch.context() as mp:
            mp.setattr(doorbell_mod.asyncio, "sleep", _gated_sleep)

            # Talk while listening -> boosts door speaker, speaks with `... ` lead-in
            await async_execute_doorbell_intercom(
                hass,
                coord,
                action="talk_message",
                camera_entity="camera.front_door",
                message="Coming now",
            )
            assert coord.doorbell_talk_state == "talking"
            assert coord.doorbell_reply_resume_listen is True
            assert vol_calls == [
                {"entity_id": "media_player.front_door_spk", "volume_level": 0.80}
            ]
            assert len(tts_calls) == 1
            assert tts_calls[0]["message"] == "... Coming now"
            assert tts_calls[0]["media_player_entity_id"] == ["media_player.front_door_spk"]

            first_task = coord.doorbell_reply_task
            assert first_task is not None
            await orig_sleep(0)
            assert not first_task.done()

            # Re-entrant quick_reply while first task is pending + failing TTS announce
            def _fail_tts(_call: Any) -> None:
                raise HomeAssistantError("TTS backend unavailable")

            mock_service(hass, "tts", "speak", _fail_tts)
            await async_execute_doorbell_intercom(
                hass,
                coord,
                action="quick_reply",
                camera_entity="camera.front_door",
                message="",
            )
            await orig_sleep(0)
            assert first_task.cancelled()
            assert coord.doorbell_reply_resume_listen is True

            # Release gate -> `_post_reply_restore` resumes listen_start (`was_listening=True`) without self-cancelling
            second_task = coord.doorbell_reply_task
            assert second_task is not None
            reply_gate.set()
            await second_task
            assert coord.doorbell_talk_state == "listening"
            assert len(play_calls) >= 1

            # Stop listening, then talk while idle -> `_post_reply_restore` returns to idle
            await async_execute_doorbell_intercom(hass, coord, action="listen_stop")
            assert coord.doorbell_talk_state == "idle"
            mock_service(
                hass,
                "tts",
                "speak",
                lambda call: tts_calls.append(dict(call.data)),
            )
            await async_execute_doorbell_intercom(
                hass,
                coord,
                action="talk",
                camera_entity="camera.front_door",
                message="Thank you",
            )
            idle_restore_task = coord.doorbell_reply_task
            assert idle_restore_task is not None
            await idle_restore_task
            assert coord.doorbell_talk_state == "idle"

            # `_post_reply_restore` exits early when talk_state changed away from "talking"
            reply_gate.clear()
            await async_execute_doorbell_intercom(
                hass,
                coord,
                action="talk",
                camera_entity="camera.front_door",
                message="Hold on",
            )
            abort_task = coord.doorbell_reply_task
            assert abort_task is not None
            await orig_sleep(0)
            coord.doorbell_talk_state = "idle"
            reply_gate.set()
            await abort_task
            assert coord.doorbell_talk_state == "idle"
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_doorbell_ring_listener_ble_tag_cooldown_invalid_and_push_error(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Cover BLE tag early return, invalid transitions, cooldown suppression, cleared map, and push errors."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_ble_tag=True)
    try:
        # BLE tag coordinator returns early without binding ring listeners
        tag_coord = sys_obj.coordinators["sub_tag"]
        bind_coordinator_doorbell_listener(tag_coord)
        assert tag_coord.doorbell_ring_map == {}

        # Register porch (`event.` ring) and side (`binary_sensor.` ring) cameras
        porch_dev = register_device(
            hass,
            config_entry_id="entry_ring_porch",
            entry_domain="unifiprotect",
            identifiers={("unifiprotect", "ring_porch")},
            name="Porch Doorbell",
        )
        register_entity(
            hass,
            "camera.porch_door",
            platform="unifiprotect",
            device_id=porch_dev.id,
            config_entry_id="entry_ring_porch",
        )
        register_entity(
            hass,
            "event.porch_door_ring",
            platform="unifiprotect",
            device_id=porch_dev.id,
            config_entry_id="entry_ring_porch",
        )

        side_dev = register_device(
            hass,
            config_entry_id="entry_ring_side",
            entry_domain="generic_cam",
            identifiers={("generic_cam", "ring_side")},
            name="Side Doorbell",
        )
        register_entity(
            hass,
            "camera.side_door",
            platform="generic_cam",
            device_id=side_dev.id,
            config_entry_id="entry_ring_side",
        )
        register_entity(
            hass,
            "binary_sensor.side_door_ring",
            platform="generic_cam",
            device_id=side_dev.id,
            config_entry_id="entry_ring_side",
        )

        get_global_config(hass)[CONF_CAMERA_ENTITIES] = [
            "camera.porch_door",
            "camera.side_door",
        ]
        hass.states.async_set("camera.porch_door", "streaming", {"friendly_name": "Porch"})
        hass.states.async_set("camera.side_door", "streaming", {"friendly_name": "Side Door"})
        base_ts = (dt_util.utcnow() - timedelta(minutes=10)).isoformat()
        hass.states.async_set("event.porch_door_ring", base_ts)
        hass.states.async_set("binary_sensor.side_door_ring", "off")

        bind_coordinator_doorbell_listener(coord)
        assert coord.doorbell_ring_map == {
            "event.porch_door_ring": "camera.porch_door",
            "binary_sensor.side_door_ring": "camera.side_door",
        }

        # Invalid transition (stale timestamp) is ignored cleanly
        stale_ts = (dt_util.utcnow() - timedelta(minutes=5)).isoformat()
        hass.states.async_set("event.porch_door_ring", stale_ts)
        await hass.async_block_till_done()
        assert coord.alert_id == 0

        # Failing ESPHome popup service triggers debug error handler cleanly
        notify_attempts: list[dict[str, Any]] = []

        def _fail_esphome_notify(call: Any) -> None:
            notify_attempts.append(dict(call.data))
            raise HomeAssistantError("ESPHome API disconnected")

        mock_service(
            hass,
            "esphome",
            "pocket_assistant_latter_show_notification",
            _fail_esphome_notify,
        )

        fresh_ts_1 = dt_util.utcnow().isoformat()
        hass.states.async_set("event.porch_door_ring", fresh_ts_1)
        await hass.async_block_till_done()
        if coord._background_tasks:
            await asyncio.gather(*list(coord._background_tasks), return_exceptions=True)

        assert coord.alert_id == 1
        assert coord.alert_camera_entity == "camera.porch_door"
        assert len(notify_attempts) == 1
        assert notify_attempts[0]["priority"] == "critical"

        # Immediate second valid ring within 15s cooldown is suppressed
        fresh_ts_2 = (dt_util.utcnow() + timedelta(milliseconds=50)).isoformat()
        hass.states.async_set("event.porch_door_ring", fresh_ts_2)
        await hass.async_block_till_done()
        assert coord.alert_id == 1

        # Ring arriving after camera config & ring map cleared returns cleanly without dispatching
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = []
        coord.set_doorbell_ring_map({})
        hass.states.async_set("binary_sensor.side_door_ring", "on")
        await hass.async_block_till_done()
        assert coord.alert_id == 1
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_remotes_slot_resolution_effective_lists_and_platform_lookup(
    hass: Any,
) -> None:
    """Cover empty/missing slots, disabled sibling skipping, `all`/area-group modes, and platform lookup."""
    assert resolve_remote_slot_pair(hass, None)["name"] == "Unassigned"
    assert resolve_remote_slot_pair(hass, "")["remote_entity"] == ""
    assert resolve_remote_slot_pair(hass, "remote.ghost_entity")["name"] == "Unassigned"

    # Device with enabled `remote.*`, disabled sibling `media_player.*`, and enabled sibling `media_player.*`
    avr_dev = register_device(
        hass,
        config_entry_id="entry_denon_avr",
        entry_domain="denonavr",
        identifiers={("denonavr", "avr_1")},
        name="Denon AVR",
        area_id="living_room",
    )
    register_entity(
        hass,
        "remote.denon_avr",
        platform="denonavr",
        device_id=avr_dev.id,
        config_entry_id="entry_denon_avr",
    )
    register_entity(
        hass,
        "media_player.denon_avr_disabled",
        platform="denonavr",
        device_id=avr_dev.id,
        config_entry_id="entry_denon_avr",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    register_entity(
        hass,
        "media_player.denon_avr_main",
        platform="denonavr",
        device_id=avr_dev.id,
        config_entry_id="entry_denon_avr",
    )
    hass.states.async_set("remote.denon_avr", "on", {"friendly_name": "Denon Remote"})
    hass.states.async_set("media_player.denon_avr_main", "playing", {"friendly_name": "Denon Main"})

    pair = resolve_remote_slot_pair(hass, "remote.denon_avr")
    assert pair["remote_entity"] == "remote.denon_avr"
    assert pair["media_player_entity"] == "media_player.denon_avr_main"
    assert pair["platform"] == "denonavr"
    assert pair["name"] == "Denon Main"
    assert pair["state"] == "playing"

    # `mode="all"` slices inventory to max 10 slots
    big_inventory = [f"remote.slot_{i}" for i in range(12)]
    all_res = resolve_effective_remote_entities(
        hass,
        all_inventory=big_inventory,
        groups=[],
        mode="all",
        cur_area="living_room",
    )
    assert len(all_res) == 10
    assert all_res[0] == "remote.slot_0"
    assert all_res[-1] == "remote.slot_9"

    # Area-matched groups merge and deduplicate remotes
    groups = [
        {"id": "g_main", "area_id": "living_room", "remotes": ["remote.tv", "remote.avr"]},
        {"id": "g_aux", "area_id": "living_room", "remotes": ["remote.avr", "remote.atv"]},
        {"id": "g_other", "area_id": "kitchen", "remotes": ["remote.kitchen_tv"]},
    ]
    area_res = resolve_effective_remote_entities(
        hass,
        all_inventory=big_inventory,
        groups=groups,
        mode="auto",
        cur_area="living_room",
    )
    assert area_res == ["remote.tv", "remote.avr", "remote.atv"]

    # Non-matching area when groups exist returns empty list
    assert (
        resolve_effective_remote_entities(
            hass,
            all_inventory=big_inventory,
            groups=groups,
            mode="auto",
            cur_area="garage",
        )
        == []
    )

    # `_resolve_slot_platform` registry scan fallback hit and miss
    assert (
        _resolve_slot_platform(
            hass,
            {
                "platform": "",
                "remote_entity": "remote.not_registered",
                "media_player_entity": "media_player.denon_avr_main",
            },
        )
        == "denonavr"
    )
    assert (
        _resolve_slot_platform(
            hass,
            {
                "platform": "",
                "remote_entity": "remote.not_registered",
                "media_player_entity": "media_player.also_missing",
            },
        )
        == ""
    )


async def test_remotes_volume_targets_and_flags(hass: Any) -> None:
    """Cover number/input_number stepping, domain guards, feature flag parsing, and mp mute/step."""
    calls_log: list[tuple[str, str, dict[str, Any]]] = []
    for dom, svcs in (
        ("number", ("set_value",)),
        ("input_number", ("set_value",)),
        ("media_player", ("volume_mute", "volume_up", "volume_down")),
    ):
        for svc in svcs:
            mock_service(
                hass,
                dom,
                svc,
                lambda call, d=dom, s=svc: calls_log.append((d, s, dict(call.data))),
            )

    # Invalid target format & unsupported domain
    assert await _async_step_remote_volume_target(hass, "", "volume_up") is False
    assert await _async_step_remote_volume_target(hass, "no_domain_dot", "volume_up") is False
    assert await _async_step_remote_volume_target(hass, "light.lamp", "volume_up") is False

    # `number` / `input_number` volume stepping edge cases
    assert await _async_step_remote_volume_target(hass, "number.avr_vol", "volume_mute") is False
    assert await _async_step_remote_volume_target(hass, "number.missing_vol", "volume_up") is False

    hass.states.async_set("number.bad_vol", STATE_UNAVAILABLE, {"min": 0, "max": 100})
    assert await _async_step_remote_volume_target(hass, "number.bad_vol", "volume_up") is False

    hass.states.async_set("number.bad_bounds", "50", {"min": 100, "max": 10, "step": 5})
    assert await _async_step_remote_volume_target(hass, "number.bad_bounds", "volume_up") is False

    hass.states.async_set("number.nan_vol", "nan", {"min": 0, "max": 100})
    assert await _async_step_remote_volume_target(hass, "number.nan_vol", "volume_up") is False

    hass.states.async_set("number.avr_vol", "40", {"min": 0, "max": 100, "step": 5})
    assert await _async_step_remote_volume_target(hass, "number.avr_vol", "volume_up") is True

    # `input_number` without explicit `step` defaults to 5% of span and clamps to `min`
    hass.states.async_set("input_number.amp_vol", "2", {"min": 0, "max": 100})
    assert await _async_step_remote_volume_target(hass, "input_number.amp_vol", "volume_down") is True

    # `_parse_mp_volume_flags` None, bool, invalid string, and bitmasks
    assert _parse_mp_volume_flags(None) == (True, True)
    assert _parse_mp_volume_flags(State("media_player.x", "on", {"supported_features": True})) == (
        True,
        True,
    )
    assert _parse_mp_volume_flags(
        State("media_player.x", "on", {"supported_features": "not_an_int"})
    ) == (True, True)

    # `media_player` step-only vs mute-only vs missing features
    hass.states.async_set("media_player.step_only", "on", {"supported_features": 1024})
    assert await _async_step_remote_volume_target(hass, "media_player.step_only", "volume_mute") is False
    assert await _async_step_remote_volume_target(hass, "media_player.step_only", "volume_down") is True

    hass.states.async_set(
        "media_player.mute_only",
        "on",
        {"supported_features": 8, "is_volume_muted": True},
    )
    assert await _async_step_remote_volume_target(hass, "media_player.mute_only", "volume_mute") is True
    assert await _async_step_remote_volume_target(hass, "media_player.mute_only", "volume_up") is False

    hass.states.async_set("media_player.no_sf", "on", {"is_volume_muted": False})
    assert await _async_step_remote_volume_target(hass, "media_player.no_sf", "volume_mute") is True

    await hass.async_block_till_done()
    assert calls_log == [
        ("number", "set_value", {"entity_id": "number.avr_vol", "value": 45.0}),
        ("input_number", "set_value", {"entity_id": "input_number.amp_vol", "value": 0.0}),
        ("media_player", "volume_down", {"entity_id": "media_player.step_only"}),
        (
            "media_player",
            "volume_mute",
            {"entity_id": "media_player.mute_only", "is_volume_muted": False},
        ),
        (
            "media_player",
            "volume_mute",
            {"entity_id": "media_player.no_sf", "is_volume_muted": True},
        ),
    ]


async def test_remotes_dispatch_media_volume_denon_webos_and_guards(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Cover empty/select/blank-long-press guards, play_pause, volume overrides, Denon, webOS, and custom cmds."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, extra_device_data={CONF_DEVICE_REMOTE_GROUP: "all"}
    )
    try:
        calls_log: list[tuple[str, str, dict[str, Any]]] = []
        for dom, svcs in (
            ("media_player", ("media_play_pause", "volume_up", "volume_down", "volume_mute")),
            ("number", ("set_value",)),
            ("remote", ("send_command",)),
            ("denonavr", ("get_command",)),
            ("webostv", ("button",)),
        ):
            for svc in svcs:
                mock_service(
                    hass,
                    dom,
                    svc,
                    lambda call, d=dom, s=svc: calls_log.append((d, s, dict(call.data))),
                )

        # 1) Empty slots returns cleanly
        get_global_config(hass)[CONF_REMOTES_LIST] = []
        await async_execute_remote_action(hass, coord, slot=1, action="up")
        await hass.async_block_till_done()
        assert calls_log == []

        # 2) Seed 6 diverse remote slots
        register_entity(hass, "media_player.denon_avr", platform="denonavr", area_id="living_room")
        register_entity(hass, "media_player.lg_oled", platform="webostv", area_id="living_room")
        register_entity(
            hass, "remote.shield_only", platform="androidtv_remote", area_id="living_room"
        )
        register_entity(hass, "remote.atv_only", platform="apple_tv", area_id="living_room")
        register_entity(hass, "media_player.fixed_amp", platform="generic", area_id="living_room")

        hass.states.async_set(
            "media_player.denon_avr",
            "on",
            {"friendly_name": "Denon AVR", "supported_features": 1 | 8 | 1024},
        )
        hass.states.async_set(
            "media_player.lg_oled",
            "on",
            {"friendly_name": "LG OLED", "supported_features": 1},
        )
        hass.states.async_set("remote.shield_only", "on", {"friendly_name": "Shield"})
        hass.states.async_set("remote.atv_only", "on", {"friendly_name": "Apple TV"})
        hass.states.async_set(
            "media_player.fixed_amp",
            "on",
            {"friendly_name": "Fixed Amp", "supported_features": 0},
        )
        hass.states.async_set("remote.state_only", "on", {"friendly_name": "State Only"})

        get_global_config(hass)[CONF_REMOTES_LIST] = [
            "media_player.denon_avr",
            "media_player.lg_oled",
            "remote.shield_only",
            "remote.atv_only",
            "media_player.fixed_amp",
            "remote.state_only",
        ]

        # 3) `select_slot`, empty action, and `long_press` with blank command return early
        await async_execute_remote_action(hass, coord, slot=2, action="select_slot")
        assert coord.active_remote_slot == 2
        await async_execute_remote_action(hass, coord, slot=1, action="")
        assert coord.active_remote_slot == 1
        await async_execute_remote_action(hass, coord, slot=1, action="long_press", command="")
        await hass.async_block_till_done()
        assert calls_log == []

        # 4) Media play_pause & volume dispatch paths
        await async_execute_remote_action(hass, coord, slot=1, action="media_play_pause")
        await async_execute_remote_action(hass, coord, slot=1, action="volume_up")

        hass.states.async_set("number.avr_master", "50", {"min": 0, "max": 100, "step": 2})
        get_global_config(hass)[CONF_VOLUME_OVERRIDES] = [
            {"speaker": "media_player.denon_avr", "target": "number.avr_master"}
        ]
        await async_execute_remote_action(hass, coord, slot=1, action="volume_down")

        # Remote-only `media_play_pause` falls back to `remote.send_command` (Android TV vs standard)
        await async_execute_remote_action(hass, coord, slot=3, action="media_play_pause")
        await async_execute_remote_action(hass, coord, slot=4, action="media_play_pause")

        # Fixed media_player with sf=0 and no sibling remote returns False without sending commands
        await async_execute_remote_action(hass, coord, slot=5, action="volume_up")

        # 5) Platform navigation commands: Denon AVR, webOS TV, Apple TV custom cmd, unregistered remote
        await async_execute_remote_action(hass, coord, slot=1, action="command", command="up")
        await async_execute_remote_action(
            hass,
            coord,
            slot=1,
            action="command",
            command="/goform/formiPhoneAppDirect.xml?SIHDMI1",
        )
        await async_execute_remote_action(
            hass, coord, slot=1, action="command", command="unmapped_noop"
        )
        await async_execute_remote_action(hass, coord, slot=2, action="command", command="select")
        await async_execute_remote_action(hass, coord, slot=2, action="command", command="netflix")
        await async_execute_remote_action(
            hass, coord, slot=4, action="command", command="top_shelf"
        )
        await async_execute_remote_action(hass, coord, slot=6, action="command", command="up")

        await hass.async_block_till_done()
        assert calls_log == [
            ("media_player", "media_play_pause", {"entity_id": "media_player.denon_avr"}),
            ("media_player", "volume_up", {"entity_id": "media_player.denon_avr"}),
            ("number", "set_value", {"entity_id": "number.avr_master", "value": 48.0}),
            (
                "remote",
                "send_command",
                {"entity_id": "remote.shield_only", "command": "MEDIA_PLAY_PAUSE"},
            ),
            (
                "remote",
                "send_command",
                {"entity_id": "remote.atv_only", "command": "play_pause"},
            ),
            (
                "denonavr",
                "get_command",
                {
                    "entity_id": "media_player.denon_avr",
                    "command": "/goform/formiPhoneAppDirect.xml?MNCUP",
                },
            ),
            (
                "denonavr",
                "get_command",
                {
                    "entity_id": "media_player.denon_avr",
                    "command": "/goform/formiPhoneAppDirect.xml?SIHDMI1",
                },
            ),
            (
                "webostv",
                "button",
                {"entity_id": "media_player.lg_oled", "button": "ENTER"},
            ),
            (
                "webostv",
                "button",
                {"entity_id": "media_player.lg_oled", "button": "NETFLIX"},
            ),
            (
                "remote",
                "send_command",
                {"entity_id": "remote.atv_only", "command": "top_shelf"},
            ),
            (
                "remote",
                "send_command",
                {"entity_id": "remote.state_only", "command": "up"},
            ),
        ]
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id) is True
