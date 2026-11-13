"""Integration tests for AreaStateIndex, Area Context v3, Calendar, and Doorbell Reflexes."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from homeassistant.components.lock import LockEntityFeature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.areas import (
    async_execute_area_action,
    find_area_media_entities,
    get_area_available_domains,
    get_area_entities,
    get_areas_summary,
    get_available_home_categories,
    get_home_alarm_summary,
    get_home_wide_entities,
    get_whole_home_summary,
    match_area_by_name_or_id,
)
from custom_components.latter.const import CONF_CAMERA_ENTITIES, DATA_GLOBAL_CONFIG, DOMAIN
from custom_components.latter.doorbell import (
    bind_coordinator_doorbell_listener,
    resolve_doorbell_ring_entities,
    resolve_doorbell_targets,
)
from custom_components.latter.feeds import (
    async_fetch_calendar_agenda,
    async_fetch_calendar_snapshot,
    compute_moon_phase,
    read_sun_and_moon_fields,
)
from custom_components.latter.groups import get_esphome_device_entities
from custom_components.latter.http import (
    LatterCameraAudioStreamView,
    _build_silence_wav,
    async_shutdown_doorbell_streams,
    build_noise_reduction_filter,
)
from custom_components.latter.hub import (
    get_area_state_index,
    is_media_position_only_tick,
)
from custom_components.latter.remotes import build_remote_config_payload


def _make_query_request(url: str) -> Any:
    parsed = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    return SimpleNamespace(query=query, headers={})


@pytest.mark.asyncio
async def test_area_state_index_reactive_lookup_and_media_tick_filtering(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify O(1) AreaStateIndex updates on registry events and ignores media_position-only ticks."""
    entry, _sys_obj, _coord = await setup_latter_hub(hass)
    idx = get_area_state_index(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    # Register a lamp device in living_room with a light and temperature sensor
    lamp_dev = dev_reg.async_get_or_create(
        config_entry_id="hue_entry",
        identifiers={("hue", "lamp_1")},
        name="Floor Lamp",
        area_id="living_room",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="light.floor_lamp",
            platform="hue",
            device_id=lamp_dev.id,
        )
    )
    hass.states.async_set(
        "light.floor_lamp",
        "on",
        {"brightness": 204, "friendly_name": "Living Room Floor Lamp"},
    )

    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.living_speaker",
            platform="music_assistant",
            area_id="living_room",
        )
    )
    now_dt = dt_util.utcnow()
    hass.states.async_set(
        "media_player.living_speaker",
        "playing",
        {
            "media_title": "Track One",
            "media_position": 10.0,
            "media_position_updated_at": now_dt,
            "mass_player_type": "player",
        },
    )
    await hass.async_block_till_done()

    assert "light.floor_lamp" in [s.entity_id for s in idx.entities_in_area("living_room", ("light",))]
    assert idx.resolve_entity_area_id("light.floor_lamp") == "living_room"

    fired_events: list[str] = []
    unsub_lr = idx.register_area_listener(
        "living_room", lambda eid="": fired_events.append(str(eid))
    )

    # Media position tick only -> MUST NOT trigger area invalidation listener
    old_mp = hass.states.get("media_player.living_speaker")
    hass.states.async_set(
        "media_player.living_speaker",
        "playing",
        {
            "media_title": "Track One",
            "media_position": 11.0,
            "media_position_updated_at": now_dt + timedelta(seconds=1),
            "mass_player_type": "player",
        },
    )
    new_mp = hass.states.get("media_player.living_speaker")
    assert is_media_position_only_tick(old_mp, new_mp) is True
    assert fired_events == []

    # Actual track change -> MUST trigger area listener
    hass.states.async_set(
        "media_player.living_speaker",
        "playing",
        {
            "media_title": "Track Two",
            "media_position": 0.0,
            "media_position_updated_at": now_dt + timedelta(seconds=2),
            "mass_player_type": "player",
        },
    )
    assert len(fired_events) == 1

    # Move device from living_room -> kitchen dynamically
    dev_reg.async_update_device(lamp_dev.id, area_id="kitchen")
    await hass.async_block_till_done()
    assert idx.resolve_entity_area_id("light.floor_lamp") == "kitchen"
    assert "light.floor_lamp" in [s.entity_id for s in idx.entities_in_area("kitchen", ("light",))]
    assert "light.floor_lamp" not in [s.entity_id for s in idx.entities_in_area("living_room", ("light",))]

    # Dynamic new Area creation & deletion
    area_reg.async_create("Patio", area_id="patio")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.patio_ble_occupancy") is not None
    area_reg.async_delete("patio")
    await hass.async_block_till_done()

    unsub_lr()
    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_context_builder_curated_entities_and_area_actions(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise Area Context v3 building, curated filtering, whole-home summary, and all action verbs."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ent_reg = er.async_get(hass)

    # Seed rich controllable & environmental entities in living_room
    seeded = [
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
        ent_reg.async_register(
            er.RegistryEntry(entity_id=eid, platform=platform, area_id="living_room")
        )
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
    ar.async_get(hass).async_create("Garden", area_id="garden")
    assert match_area_by_name_or_id(hass, "Garden") == "garden"
    assert match_area_by_name_or_id(hass, "den") is None

    areas_summary = get_areas_summary(
        hass, active_area_id="living_room", local_speaker=coord.local_speaker
    )
    assert areas_summary and areas_summary[0]["id"] == "living_room"
    assert "1 on" in areas_summary[0]["name"]

    all_lr = get_area_entities(hass, "living_room", "all", coord.local_speaker)
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

    home_wide = get_home_wide_entities(hass)
    assert home_wide and home_wide[0]["id"] == "alarm_control_panel.home_alarm"

    wh = get_whole_home_summary(hass)
    assert wh["thermostat_entity"] == "climate.lr_hvac"
    assert wh["lock_entity"] in ("lock.front_door", "lock.side_latch")
    assert wh["garage_entity"] == "cover.main_garage"
    assert wh["vacuum_entity"] == "vacuum.roborock"
    alarm_sum = get_home_alarm_summary(hass)
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
                "thermostat_entity": "",
                "lock_entity": "lock.front_door",
                "garage_entity": "",
                "vacuum_entity": "",
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
    hass.data[DOMAIN]["global_config"]["remotes_list"] = ["remote.lr_tv"]
    coord._cached_remote_payload = None
    rem_state, rem_attrs = build_remote_config_payload(coord)
    assert rem_state == "Living TV" and "payload" in rem_attrs

    area_state, area_attrs = coord.get_area_context_payload()
    assert area_state == "Living Room"
    assert area_attrs["payload"].startswith("v3\x1f")

    # Record service calls across all action domains
    recorded: list[tuple[str, str, dict[str, Any]]] = []
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
            hass.services.async_register(
                svc_dom,
                s_name,
                lambda call, d=svc_dom, s=s_name: recorded.append((d, s, dict(call.data))),
            )

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
    await async_execute_area_action(hass, "whole_home.vacuum", "dock")
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

    called_pairs = {(d, s) for d, s, _ in recorded}
    assert ("light", "turn_on") in called_pairs
    assert ("cover", "close_cover") in called_pairs
    assert ("cover", "set_cover_position") in called_pairs
    assert ("fan", "set_percentage") in called_pairs
    assert ("climate", "set_hvac_mode") in called_pairs
    assert ("climate", "set_temperature") in called_pairs
    assert ("vacuum", "return_to_base") in called_pairs
    assert ("lock", "open") in called_pairs
    assert ("alarm_control_panel", "alarm_arm_home") in called_pairs

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_calendar_feeds_and_doorbell_ring_reflex(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify calendar/forecast snapshot builders and doorbell ring (not motion) auto-wake reflex."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    # Calendar + Sun/Moon + Weather forecast
    assert compute_moon_phase(947182440.0) == "new_moon"
    sky = read_sun_and_moon_fields(hass)
    assert sky["sun_state"] == "above_horizon"
    assert sky["moon_phase"] != ""

    hass.states.async_set("calendar.family", "off", {"friendly_name": "Family"})
    now_local = dt_util.now()
    tomorrow_str = (now_local + timedelta(days=2)).strftime("%Y-%m-%d")
    event_iso = (now_local + timedelta(hours=2)).isoformat()

    hass.services.async_register(
        "calendar",
        "get_events",
        lambda _call: {
            "calendar.family": {
                "events": [
                    {
                        "summary": "Design Review",
                        "start": event_iso,
                        "end": (now_local + timedelta(hours=3)).isoformat(),
                        "location": "37.8044,-122.2712",
                    },
                    {
                        "summary": "Design Review",
                        "start": event_iso,
                        "end": (now_local + timedelta(hours=3)).isoformat(),
                        "location": "37.8044,-122.2712",
                    },
                    {
                        "summary": "Offsite Day",
                        "start": tomorrow_str,
                        "end": tomorrow_str,
                    },
                ]
            }
        },
    )
    hass.services.async_register(
        "weather",
        "get_forecasts",
        lambda _call: {
            "weather.home": {
                "forecast": [
                    {
                        "datetime": (now_local + timedelta(days=i)).isoformat(),
                        "condition": "sunny",
                        "temperature": 72 + i,
                        "templow": 55 + i,
                    }
                    for i in range(5)
                ]
            }
        },
    )

    records, slots = await async_fetch_calendar_agenda(
        hass, ["calendar.family"], days=14, map_url_builder=coord.build_map_snapshot_url
    )
    assert len(records) == 2  # Duplicate deduplicated!
    assert len(slots) == 2
    assert "/api/latter/map/" in slots[0]["map_url"]

    _, snap_slots = await async_fetch_calendar_snapshot(
        hass, ["calendar.family"], days=7, map_url_builder=coord.build_map_snapshot_url
    )
    assert len(snap_slots) == 2

    # Doorbell device with camera, speaker, lock, ring sensor, AND motion sensor
    door_dev = dev_reg.async_get_or_create(
        config_entry_id="protect_entry",
        identifiers={("unifiprotect", "g4_doorbell")},
        name="Front Doorbell",
        area_id="living_room",
    )
    for eid, orig_name, st_val in (
        ("camera.front_door_high", "Front Door High", "streaming"),
        ("media_player.front_door_speaker", "Speaker", "idle"),
        ("lock.front_door_deadbolt", "Deadbolt", "locked"),
        ("binary_sensor.front_door_doorbell", "Doorbell", "off"),
        ("binary_sensor.front_door_motion", "Motion", "off"),
    ):
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=eid,
                platform="unifiprotect",
                device_id=door_dev.id,
                original_name=orig_name,
            )
        )
        hass.states.async_set(eid, st_val, {"friendly_name": orig_name})

    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_CAMERA_ENTITIES] = [
        "camera.front_door_high"
    ]
    bind_coordinator_doorbell_listener(coord)

    ring_map = resolve_doorbell_ring_entities(hass, ["camera.front_door_high"])
    assert "binary_sensor.front_door_doorbell" in ring_map
    assert "binary_sensor.front_door_motion" not in ring_map

    targets = resolve_doorbell_targets(hass, "camera.front_door_high")
    assert targets["door_speaker"] == "media_player.front_door_speaker"
    assert targets["lock_entity"] == "lock.front_door_deadbolt"
    assert targets["tts_lead_in"] is True

    # Exact device_id sibling matching: a standalone camera MUST NOT substring-match an unrelated speaker
    patio_cam_dev = dev_reg.async_get_or_create(
        config_entry_id="protect_entry",
        identifiers={("unifiprotect", "patio_cam")},
        name="Patio Cam",
    )
    other_spk_dev = dev_reg.async_get_or_create(
        config_entry_id="sonos_entry",
        identifiers={("sonos", "patio_spk")},
        name="Patio Cam Speaker",
    )
    ent_reg.async_register(
        er.RegistryEntry(entity_id="camera.patio_cam", platform="unifiprotect", device_id=patio_cam_dev.id)
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.patio_cam_speaker", platform="sonos", device_id=other_spk_dev.id
        )
    )
    hass.states.async_set("camera.patio_cam", "streaming")
    hass.states.async_set("media_player.patio_cam_speaker", "idle")
    assert resolve_doorbell_targets(hass, "camera.patio_cam")["door_speaker"] == ""

    assert "afftdn" not in build_noise_reduction_filter("off")
    assert "nf=-20" in build_noise_reduction_filter("light")
    assert "nf=-26" in build_noise_reduction_filter("strong")
    wav_bytes = _build_silence_wav(100, 48000)
    assert wav_bytes[:4] == b"RIFF"

    prev_alert_id = coord.alert_id
    # Motion sensor turning on MUST NOT trigger doorbell alert
    hass.states.async_set("binary_sensor.front_door_motion", "on")
    await hass.async_block_till_done()
    assert coord.alert_id == prev_alert_id

    # Ring sensor turning on MUST wake display with critical Doorbell Ringing alert
    hass.states.async_set("binary_sensor.front_door_doorbell", "on")
    await hass.async_block_till_done()
    assert coord.alert_id > prev_alert_id
    assert coord.alert_title == "Doorbell Ringing"
    assert "/api/latter/camera/" in coord.alert_camera_url

    # Camera Audio Stream HTTP View auth & HMAC render-parameter binding (`camera_audio:<cam>|<nr>|<fmt>`)
    audio_view = LatterCameraAudioStreamView(hass)
    r_404 = await audio_view.get(_make_query_request("/api/latter/camera_audio/unknown"), "unknown")
    assert r_404.status == 404

    r_403 = await audio_view.get(
        _make_query_request(
            f"/api/latter/camera_audio/{coord.device_slug}?entity_id=camera.front_door_high&sig=bad"
        ),
        coord.device_slug,
    )
    assert r_403.status == 403

    unauth_sig = coord.sign_on_demand_resource("camera_audio:camera.secret_cam|strong|flac")
    r_unauth = await audio_view.get(
        _make_query_request(
            f"/api/latter/camera_audio/{coord.device_slug}?entity_id=camera.secret_cam&nr=strong&fmt=flac&sig={unauth_sig}"
        ),
        coord.device_slug,
    )
    assert r_unauth.status == 403

    # Query tampering on nr= or fmt= MUST be rejected with 403!
    signed_flac_url = coord.build_camera_audio_url("camera.front_door_high", "strong", "flac")
    assert "&nr=strong&fmt=flac&" in signed_flac_url
    assert "&sig=" in signed_flac_url
    r_tampered_nr = await audio_view.get(
        _make_query_request(signed_flac_url.replace("&nr=strong", "&nr=off")),
        coord.device_slug,
    )
    assert r_tampered_nr.status == 403
    r_tampered_fmt = await audio_view.get(
        _make_query_request(signed_flac_url.replace("&fmt=flac", "&fmt=wav")),
        coord.device_slug,
    )
    assert r_tampered_fmt.status == 403

    signed_wav_url = coord.build_camera_audio_url("camera.front_door_high", "strong", "wav")
    r_no_rtsp = await audio_view.get(_make_query_request(signed_wav_url), coord.device_slug)
    # Without RTSP stream URL configured, returns silent WAV fallback cleanly
    assert r_no_rtsp.status == 200
    assert r_no_rtsp.body[:4] == b"RIFF"

    await async_shutdown_doorbell_streams(hass)
    assert await async_unload_entry(hass, entry) is True
