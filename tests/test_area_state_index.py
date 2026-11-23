"""Tests for AreaStateIndex, calendar/weather feeds, doorbell ring reflex, and Area icon wire packing."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from homeassistant.core import SupportsResponse
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.util import dt as dt_util

from custom_components.latter.areas.registry import (
    infer_area_icon_from_name,
    resolve_area_icon,
)
from custom_components.latter.const import (
    CONF_CAMERA_ENTITIES,
    CONF_DEFAULT_AREA,
)
from custom_components.latter.doorbell import (
    bind_coordinator_doorbell_listener,
    resolve_doorbell_ring_entities,
    resolve_doorbell_targets,
)
from custom_components.latter.feeds import (
    async_fetch_calendar_agenda,
    compute_moon_phase,
    read_sun_and_moon_fields,
)
from custom_components.latter.http.camera_views import (
    LatterCameraAudioStreamView,
    _build_silence_wav,
    async_shutdown_doorbell_streams,
    build_noise_reduction_filter,
)
from custom_components.latter.hub_registry import (
    get_area_state_index,
    get_global_config,
    is_media_position_only_tick,
)
from tests.helpers import ensure_area, mock_service, register_device, register_entity


def _make_query_request(url: str) -> Any:
    parsed = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    return SimpleNamespace(query=query, headers={})


async def test_area_state_index_reactive_lookup_and_media_tick_filtering(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify O(1) AreaStateIndex updates on registry events and ignores media_position-only ticks."""
    entry, _sys_obj, _coord = await setup_latter_hub(hass)
    idx = get_area_state_index(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    # Register a lamp device in living_room with a light
    lamp_dev = register_device(
        hass,
        config_entry_id="hue_entry",
        entry_domain="hue",
        identifiers={("hue", "lamp_1")},
        name="Floor Lamp",
        manufacturer="Latter",
        area_id="living_room",
    )
    register_entity(
        hass,
        "light.floor_lamp",
        platform="hue",
        config_entry_id="hue_entry",
        device_id=lamp_dev.id,
    )
    hass.states.async_set(
        "light.floor_lamp",
        "on",
        {"brightness": 204, "friendly_name": "Living Room Floor Lamp"},
    )

    register_entity(
        hass,
        "media_player.living_speaker",
        platform="music_assistant",
        area_id="living_room",
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
    await hass.async_block_till_done()
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
    await hass.async_block_till_done()
    assert len(fired_events) == 1

    # Move device from living_room -> kitchen dynamically
    dev_reg.async_update_device(lamp_dev.id, area_id="kitchen")
    await hass.async_block_till_done()
    assert idx.resolve_entity_area_id("light.floor_lamp") == "kitchen"
    assert "light.floor_lamp" in [s.entity_id for s in idx.entities_in_area("kitchen", ("light",))]
    assert "light.floor_lamp" not in [s.entity_id for s in idx.entities_in_area("living_room", ("light",))]

    # Dynamic new Area creation & deletion
    patio = ensure_area(hass, "Patio", area_id="patio")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.latter_system_patio_occupancy") is not None
    area_reg.async_delete(patio.id)
    await hass.async_block_till_done()

    unsub_lr()
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_calendar_feeds_and_doorbell_ring_reflex(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify calendar/forecast snapshot builders and doorbell ring (not motion) auto-wake reflex."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)

    # Calendar + Sun/Moon + Weather forecast
    assert compute_moon_phase(947182440.0) == "new_moon"
    sky = read_sun_and_moon_fields(hass)
    assert sky["sun_state"] == "above_horizon"
    assert sky["moon_phase"] != ""

    hass.states.async_set("calendar.family", "off", {"friendly_name": "Family"})
    now_local = dt_util.now()
    tomorrow_str = (now_local + timedelta(days=2)).strftime("%Y-%m-%d")
    event_iso = (now_local + timedelta(hours=2)).isoformat()

    mock_service(
        hass,
        "calendar",
        "get_events",
        lambda _call: {
            "calendar.family": {
                "events": [
                    {
                        "summary": "Design Review",
                        "start": event_iso,
                        "end": (now_local + timedelta(hours=3)).isoformat(),
                        "location": "Downtown HQ",
                    },
                    {
                        "summary": "Design Review",
                        "start": event_iso,
                        "end": (now_local + timedelta(hours=3)).isoformat(),
                        "location": "Downtown HQ",
                    },
                    {
                        "summary": "Offsite Day",
                        "start": tomorrow_str,
                        "end": tomorrow_str,
                    },
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )
    mock_service(
        hass,
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
        supports_response=SupportsResponse.ONLY,
    )

    records, slots = await async_fetch_calendar_agenda(
        hass, ["calendar.family"], days=14
    )
    assert len(records) == 2  # Duplicate deduplicated!
    assert len(slots) == 2
    assert slots[0]["location"] == "Downtown HQ"
    assert slots[0]["map_url"] == ""
    assert not hasattr(coord, "build_map_snapshot_url")

    # Doorbell device with camera, speaker, lock, ring sensor, AND motion sensor
    door_dev = register_device(
        hass,
        config_entry_id="protect_entry",
        entry_domain="unifiprotect",
        identifiers={("unifiprotect", "g4_doorbell")},
        name="Front Doorbell",
        manufacturer="Latter",
        area_id="living_room",
    )
    for eid, orig_name, st_val in (
        ("camera.front_door_high", "Front Door High", "streaming"),
        ("media_player.front_door_speaker", "Speaker", "idle"),
        ("lock.front_door_deadbolt", "Deadbolt", "locked"),
        ("binary_sensor.front_door_doorbell", "Doorbell", "off"),
        ("binary_sensor.front_door_motion", "Motion", "off"),
    ):
        register_entity(
            hass,
            eid,
            platform="unifiprotect",
            config_entry_id="protect_entry",
            device_id=door_dev.id,
            original_name=orig_name,
        )
        hass.states.async_set(eid, st_val, {"friendly_name": orig_name})

    get_global_config(hass)[CONF_CAMERA_ENTITIES] = [
        "camera.front_door_high"
    ]
    bind_coordinator_doorbell_listener(coord)

    ring_map = resolve_doorbell_ring_entities(hass, ["camera.front_door_high"])
    assert "binary_sensor.front_door_doorbell" in ring_map
    assert "binary_sensor.front_door_motion" not in ring_map

    targets = resolve_doorbell_targets(hass, "camera.front_door_high")
    assert targets["door_speaker"] == "media_player.front_door_speaker"
    assert "lock_entity" not in targets
    assert targets["tts_lead_in"] is True

    # Exact device_id sibling matching: a standalone camera MUST NOT substring-match an unrelated speaker
    patio_cam_dev = register_device(
        hass,
        config_entry_id="protect_entry",
        entry_domain="unifiprotect",
        identifiers={("unifiprotect", "patio_cam")},
        name="Patio Cam",
        manufacturer="Latter",
    )
    other_spk_dev = register_device(
        hass,
        config_entry_id="sonos_entry",
        entry_domain="sonos",
        identifiers={("sonos", "patio_spk")},
        name="Patio Cam Speaker",
        manufacturer="Latter",
    )
    register_entity(
        hass,
        "camera.patio_cam",
        platform="unifiprotect",
        config_entry_id="protect_entry",
        device_id=patio_cam_dev.id,
    )
    register_entity(
        hass,
        "media_player.patio_cam_speaker",
        platform="sonos",
        config_entry_id="sonos_entry",
        device_id=other_spk_dev.id,
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
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_area_icon_resolution_wire_packing_and_live_registry_update(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify explicit AreaEntry.icon, 24-archetype name inference, unassigned empty string, and Protocol v3 field 42."""
    assert resolve_area_icon(None) == ""
    assert (
        resolve_area_icon(SimpleNamespace(id="custom", name="Kitchen", icon="  mdi:lamp  "))
        == "mdi:lamp"
    )
    assert (
        resolve_area_icon(SimpleNamespace(id="custom", name="Kitchen", icon="   "))
        == "mdi:countertop"
    )

    expected_archetypes = {
        "Kitchen": "mdi:countertop",
        "Butler Pantry": "mdi:countertop",
        "Formal Dining": "mdi:silverware-fork-knife",
        "Living Area": "mdi:sofa",
        "Family Lounge": "mdi:sofa",
        "Cozy Den": "mdi:sofa",
        "Baby Nursery": "mdi:baby-carriage",
        "Kids Play": "mdi:teddy-bear",
        "Primary Suite": "mdi:bed-king-outline",
        "Primary Bath": "mdi:shower",
        "Powder Lavatory": "mdi:shower",
        "Home Office": "mdi:desk",
        "HomeTheater": "mdi:television",
        "Arcade Game": "mdi:gamepad-variant-outline",
        "Yoga Gym": "mdi:dumbbell",
        "Laundry Utility": "mdi:washing-machine",
        "Two-Car Garage": "mdi:garage",
        "Craft Workshop": "mdi:tools",
        "Walk-In Closet": "mdi:wardrobe-outline",
        "Front Foyer": "mdi:door-open",
        "Upper Hallway": "mdi:transit-connection-horizontal",
        "Main Stairwell": "mdi:stairs",
        "Upper Attic": "mdi:home-roof",
        "Wine Cellar": "mdi:stairs-down",
        "Basement": "mdi:stairs-down",
        "Backyard Pool": "mdi:pool",
        "Front Porch": "mdi:balcony",
        "Sun Terrace": "mdi:balcony",
        "Herb Garden": "mdi:tree-outline",
        "Music Studio": "mdi:speaker",
        "Zone Alpha": "mdi:map-marker-outline",
        "": "mdi:map-marker-outline",
    }
    for label, expected_icon in expected_archetypes.items():
        assert infer_area_icon_from_name(label) == expected_icon, label

    entry, _sys_obj, coord = await setup_latter_hub(hass)
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    living = ensure_area(hass, "Living Area", area_id="living")
    assert living.icon is None

    await hass.config.async_set_time_zone("America/Los_Angeles")
    coord.async_set_active_area("living")
    coord.cached_area_payload = None
    area_state, area_attrs = coord.get_area_context_payload()
    assert area_state == "Living Area"
    assert area_attrs["area_icon"] == "mdi:sofa"
    wire_tokens = area_attrs["payload"].split("\x1f")
    assert len(wire_tokens) == 43
    assert wire_tokens[35] == "mdi:sofa"
    assert wire_tokens[36].startswith("America/Los_Angeles|Los Angeles|")
    assert wire_tokens[37] == ""
    assert wire_tokens[38] == "0"
    assert wire_tokens[39] == ""
    assert wire_tokens[40] == ""
    assert wire_tokens[41] == ""

    # Live Area registry icon edit invalidates cached payload and updates wire index 35
    area_reg.async_update(living.id, icon="mdi:television-classic")
    await hass.async_block_till_done()
    area_state_updated, area_attrs_updated = coord.get_area_context_payload()
    assert area_state_updated == "Living Area"
    assert area_attrs_updated["area_icon"] == "mdi:television-classic"
    assert area_attrs_updated["payload"].split("\x1f")[35] == "mdi:television-classic"

    # Unassigned Device sends empty area_icon ("")
    if coord.esphome_device_id:
        dev_reg.async_update_device(coord.esphome_device_id, area_id=None)
    hass.config_entries.async_update_subentry(
        entry,
        coord._live_subentry(),
        data={**coord.device_data, CONF_DEFAULT_AREA: ""},
    )
    await hass.async_block_till_done()
    coord._clear_active_area()
    coord.cached_area_payload = None
    unassigned_state, unassigned_attrs = coord.get_area_context_payload()
    assert unassigned_state == "Unassigned"
    assert unassigned_attrs["area_icon"] == ""
    assert unassigned_attrs["payload"].split("\x1f")[35] == ""

    assert await hass.config_entries.async_unload(entry.entry_id) is True
