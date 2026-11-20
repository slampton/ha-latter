"""Integration tests for bound Device -> HA RPC reassembly, target pinning, and 3-tier security PIN policy."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest

from custom_components.latter.const import (
    CONF_DEFAULT_AREA,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_MA_PLAYER_ENTITY,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    SUBENTRY_DEVICE,
)
from custom_components.latter.coordinator import LatterCoordinator
from custom_components.latter.identity import MAX_RPC_BYTES, RpcReassembler, parse_rpc_frame
from custom_components.latter.media import (
    async_set_ma_player_link,
    build_active_media_payload,
    clear_ma_counterpart_cache,
    execute_coordinator_media_command,
    resolve_ma_counterpart_entity,
    set_coordinator_active_speaker,
    suggest_ma_player_for,
)
from custom_components.latter.protocol import (
    check_perimeter_action_allowed,
    hash_security_pin,
    is_sensitive_perimeter_action,
    verify_security_pin,
)
from custom_components.latter.services import async_dispatch_bound_rpc
from custom_components.latter.studio.payload import build_studio_state_payload


async def test_rpc_outbox_single_and_multipart_dispatch_and_target_pinning(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any, caplog: Any
) -> None:
    """Verify `System: RPC Outbox` state changes reassemble chunks, deduplicate replays, and pin target_device."""
    entry, sys_obj, coord_a = await setup_latter_hub(hass)

    # Add a second device B so we can prove Device A cannot spoof target_device="panel_b"
    dev_b, mac_b = make_esphome_device(
        hass, slug="panel_b", mac="aa:bb:cc:dd:ee:99", name="Panel B", area_id="bedroom", stationary=1
    )
    sub_b = ConfigSubentry(
        data={
            CONF_ESPHOME_DEVICE_ID: dev_b.id,
            "mac": mac_b,
            CONF_DEVICE_SLUG: "panel_b",
            CONF_DEFAULT_AREA: "bedroom",
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Panel B",
        unique_id=mac_b,
        subentry_id="sub_panel_b",
    )
    hass.config_entries.async_add_subentry(entry, sub_b)

    coord_b = LatterCoordinator(
        hass=hass,
        entry=entry,
        hmac_secret=hass.data[DOMAIN]["hmac_secret"],
        subentry=sub_b,
    )
    await coord_b.async_setup()
    sys_obj.coordinators["sub_panel_b"] = coord_b
    hass.data[DOMAIN]["sub_panel_b"] = coord_b

    # Register a light in kitchen so area_action can run
    ent_reg = er.async_get(hass)
    ent_reg.async_register(
        er.RegistryEntry(entity_id="light.kitchen_ceiling", platform="hue", area_id="kitchen")
    )
    hass.states.async_set("light.kitchen_ceiling", "off", {"friendly_name": "Kitchen Ceiling"})

    # 1. Single-frame RPC attempting to spoof target_device="panel_b" while setting active area to kitchen
    spoof_envelope = json.dumps(
        {"s": "set_active_area", "d": {"target_device": "panel_b", "area_id": "kitchen"}}
    )
    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", f"a1b2:1:1/1|{spoof_envelope}")
    await hass.async_block_till_done()

    # Device A moved to kitchen; Device B stayed in bedroom!
    assert coord_a.active_area_id == "kitchen"
    assert coord_b.active_area_id == "bedroom"

    # 2. Replay of exact same (boot_id, seq) is ignored
    coord_a.active_area_id = "living_room"
    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", "")
    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", f"a1b2:1:1/1|{spoof_envelope}")
    await hass.async_block_till_done()
    assert coord_a.active_area_id == "living_room"

    # 3. Multi-chunk (3-part) RPC frame reassembles and executes area_action
    full_env = json.dumps(
        {
            "s": "latter.area_action",
            "d": {"action": "turn_on", "entity_id": "light.kitchen_ceiling"},
        }
    )
    c1, c2, c3 = full_env[:25], full_env[25:55], full_env[55:]
    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", f"a1b2:2:1/3|{c1}")
    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", f"a1b2:2:2/3|{c2}")
    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", f"a1b2:2:3/3|{c3}")
    await hass.async_block_till_done()
    assert any(c.domain == "light" and c.service == "turn_on" for c in hass.services.calls)

    # 4. Disconnect (`unavailable`) -> reconnect (`unknown`) clears push cache and republishes all 5 v3 domains
    push_calls = [
        c for c in hass.services.calls
        if c.domain == "esphome" and c.service == "pocket_assistant_latter_push_v3"
    ]
    before_reconnect_count = len(push_calls)
    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", "unavailable")
    await hass.async_block_till_done()
    assert coord_a._last_pushed_v3 == {}

    # Pushing while unavailable is skipped cleanly without poisoning _last_pushed_v3
    await coord_a.async_push_dirty_v3_domains()
    assert coord_a._last_pushed_v3 == {}

    hass.states.async_set("sensor.pocket_assistant_system_rpc_outbox", "unknown")
    await hass.async_block_till_done()
    reconnected_domains = {
        c.data.get("domain")
        for c in hass.services.calls[before_reconnect_count:]
        if c.domain == "esphome" and c.service == "pocket_assistant_latter_push_v3"
    }
    assert {"active_media", "weather_forecast", "area_context", "calendar_agenda", "remote_config"} <= reconnected_domains

    # 5. Transient ESPHome service failure (e.g., ConnectionNotEstablishedAPIError) never poisons _last_pushed_v3
    from homeassistant.exceptions import HomeAssistantError

    async def _failing_push(_call: Any) -> None:
        raise HomeAssistantError("Not connected to panel_b")

    hass.services.async_register("esphome", "panel_b_latter_push_v3", _failing_push)
    coord_b._last_pushed_v3.clear()
    await coord_b.async_push_dirty_v3_domains()
    assert coord_b._last_pushed_v3 == {}

    # 6. Malformed / oversize / unauthorized service RPCs are rejected safely
    assert parse_rpc_frame("not_a_valid_frame") is None
    assert parse_rpc_frame("zzzz:1:1/1|{}") is None
    assert parse_rpc_frame("a1b2:1:1/1|" + ("x" * (MAX_RPC_BYTES + 10))) is None
    r = RpcReassembler()
    assert r.feed("a1b2:5:1/2|" + ("a" * 5000), now_mono=10.0) is None
    assert r.feed("a1b2:5:2/2|" + ("b" * 5000), now_mono=11.0) is None

    # Disallowed admin service via bound RPC is rejected and logged
    await async_dispatch_bound_rpc(hass, coord_a, "reset_device", {})
    assert "Rejected unsupported RPC 'reset_device'" in caplog.text


async def test_three_tier_security_pin_policy_and_pbkdf2_verification(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify auto/allow/require_pin/block policies across locks, alarms, and garage covers."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    hass.states.async_set("lock.front_door", "locked", {"friendly_name": "Front Door"})
    hass.states.async_set("alarm_control_panel.home_alarm", "armed_away", {"friendly_name": "Home Alarm"})
    hass.states.async_set(
        "cover.garage_door", "closed", {"device_class": "garage", "friendly_name": "Garage Door"}
    )

    # Hash & verify PBKDF2-HMAC-SHA256 PIN
    pin_hash = hash_security_pin("2580")
    assert verify_security_pin("2580", pin_hash) is True
    assert verify_security_pin("9999", pin_hash) is False
    assert verify_security_pin("abcd", pin_hash) is False
    with pytest.raises(ValueError):
        hash_security_pin("12")  # <4 digits rejected

    # Store system PIN hash in global config
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_SECURITY_PIN_HASH] = pin_hash

    # Roaming handheld (stationary == 0) with "auto" policy resolves to "allow" when no device PIN set,
    # or let's test explicit "require_pin" and "block" and stationary "auto" -> "require_pin"!
    # Stationary hardware manifest with "auto" -> requires PIN on unlock/disarm/open_cover(garage)
    coord._runtime.hello_manifest = {**coord.hardware_manifest, "stationary": 1}
    assert coord.security_pin_policy == "require_pin"

    # Closing/locking/arming verbs NEVER require a PIN
    assert is_sensitive_perimeter_action("lock", "lock") is False
    assert is_sensitive_perimeter_action("alarm_control_panel", "arm_away") is False
    assert is_sensitive_perimeter_action("cover", "close_cover", device_class="garage") is False
    assert is_sensitive_perimeter_action("lock", "unlock") is True
    assert check_perimeter_action_allowed(
        "require_pin", provided_code="2580", stored_pin_hash=pin_hash
    ) == (True, "")

    # Unlock without PIN -> security_pin_required
    with pytest.raises(ServiceValidationError) as exc_req:
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": "pocket_assistant",
                "action": "unlock",
                "entity_id": "lock.front_door",
            },
            blocking=True,
        )
    assert exc_req.value.translation_key == "security_pin_required"

    # Unlock with wrong PIN -> security_pin_invalid
    with pytest.raises(ServiceValidationError) as exc_bad:
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": "pocket_assistant",
                "action": "unlock",
                "entity_id": "lock.front_door",
                "code": "0000",
            },
            blocking=True,
        )
    assert exc_bad.value.translation_key == "security_pin_invalid"

    # Unlock with valid PIN -> succeeds!
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": "pocket_assistant",
            "action": "unlock",
            "entity_id": "lock.front_door",
            "code": "2580",
        },
        blocking=True,
    )
    assert any(c.domain == "lock" and c.service == "unlock" for c in hass.services.calls)

    # Policy = "block" rejects even when valid PIN is supplied
    sub = entry.subentries["sub_pocket"]
    blocked_data = {**sub.data, CONF_SECURITY_PIN_POLICY: "block"}
    hass.config_entries.async_update_subentry(entry, sub, data=blocked_data)
    coord.subentry = entry.subentries["sub_pocket"]
    await coord.async_apply_options()

    with pytest.raises(ServiceValidationError) as exc_blk:
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": "pocket_assistant",
                "action": "open_cover",
                "entity_id": "cover.garage_door",
                "code": "2580",
            },
            blocking=True,
        )
    assert exc_blk.value.translation_key == "security_action_blocked"


async def test_remote_speaker_queue_transfer_spinup_hold_pause_and_empty_queue_recovery(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify queue transfer holds playing state during MA spin-up, honors immediate pause, and recovers empty queues."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)

    # Local Sendspin speaker is playing while track metadata lives on its linked MA counterpart
    ma_entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="ma_entry_1",
            domain="music_assistant",
            title="Music Assistant",
            data={},
        )
    )
    ent_reg = er.async_get(hass)
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_assistant",
            platform="music_assistant",
            unique_id="ma_pocket_assistant",
            config_entry_id=ma_entry.entry_id,
        )
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.garage_hifi",
            platform="music_assistant",
            unique_id="ma_garage_hifi",
            config_entry_id=ma_entry.entry_id,
        )
    )
    async_set_ma_player_link(hass, coord, "media_player.pocket_assistant")
    hass.states.async_set(
        coord.local_speaker,
        "playing",
        {"friendly_name": "Pocket Assistant Music", "volume_level": 0.65},
    )
    hass.states.async_set(
        "media_player.pocket_assistant",
        "playing",
        {
            "friendly_name": "Pocket Assistant",
            "media_title": "Up From The Sea",
            "media_artist": "Swervedriver",
            "media_album_name": "99th Dream",
            "media_duration": 212.0,
            "media_position": 18.0,
            "media_content_id": "library://track/42",
            "media_content_type": "music",
            "volume_level": 0.65,
        },
    )
    # Remote target speaker starts idle while Music Assistant spins up the transferred stream
    hass.states.async_set(
        "media_player.garage_hifi",
        "idle",
        {"friendly_name": "Garage HiFi", "volume_level": 0.50},
    )

    set_coordinator_active_speaker(coord, "media_player.garage_hifi", transfer_queue=True)
    await hass.async_block_till_done()

    coord._cached_media_payload = None
    state_during_spinup, attrs_during_spinup = build_active_media_payload(coord)
    assert state_during_spinup == "playing"
    assert attrs_during_spinup["title"] == "Up From The Sea"
    assert attrs_during_spinup["is_local"] is False

    # User taps Pause while remote speaker is still spinning up -> clears spinup hold & calls media_pause
    await execute_coordinator_media_command(coord, "pause")
    assert coord._transfer_hold_spinup_until == 0.0
    assert any(
        c.domain == "media_player"
        and c.service == "media_pause"
        and c.data.get("entity_id") == "media_player.garage_hifi"
        for c in hass.services.calls
    )

    # Empty MA queue on media_play is caught cleanly (never raises uncaught HomeAssistantError) and falls back to play_media
    coord._resuming_guard_until = 0.0
    coord.last_media_uri = "library://album/4"
    coord.last_media_type = "album"

    orig_async_call = hass.services.async_call
    play_media_calls: list[dict[str, Any]] = []

    async def _mock_service_call(
        domain: str, service: str, service_data: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        if domain == "media_player" and service == "media_play":
            raise HomeAssistantError("The queue is empty")
        if domain == "media_player" and service == "play_media":
            play_media_calls.append(dict(service_data or {}))
            return None
        return await orig_async_call(domain, service, service_data, **kwargs)

    hass.services.async_call = _mock_service_call
    try:
        await execute_coordinator_media_command(coord, "play")
    finally:
        hass.services.async_call = orig_async_call

    assert len(play_media_calls) >= 1
    assert play_media_calls[0]["media_content_id"] == "library://album/4"


async def test_orphaned_unavailable_ma_link_self_heals_and_guards_ambiguous_twins(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify recreated `_2` MA players heal orphaned unavailable links without cross-linking identical twins."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        extra_device_data={CONF_MA_PLAYER_ENTITY: "media_player.pocket_assistant"},
    )
    ma_entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="ma_entry_heal",
            domain="music_assistant",
            title="Music Assistant",
            data={},
        )
    )
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    ghost_dev = dev_reg.async_get_or_create(
        config_entry_id=ma_entry.entry_id,
        identifiers={("music_assistant", "ghost_up1")},
        name="Pocket Assistant",
        manufacturer="slampton",
        model="pocket_assistant-board",
    )
    live_dev = dev_reg.async_get_or_create(
        config_entry_id=ma_entry.entry_id,
        identifiers={("music_assistant", "live_up2")},
        name="Pocket Assistant",
        manufacturer="slampton",
        model="pocket_assistant-board",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_assistant",
            platform="music_assistant",
            unique_id="ghost_up1",
            device_id=ghost_dev.id,
            config_entry_id=ma_entry.entry_id,
        )
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_assistant_2",
            platform="music_assistant",
            unique_id="live_up2",
            device_id=live_dev.id,
            config_entry_id=ma_entry.entry_id,
        )
    )
    hass.states.async_set(coord.local_speaker, "idle", {"friendly_name": "Pocket Assistant Music"})
    hass.states.async_set("media_player.pocket_assistant", "unavailable", {"friendly_name": "Pocket Assistant"})
    # Transitioning the recreated `_2` entity online triggers live cache invalidation + subentry self-healing
    hass.states.async_set("media_player.pocket_assistant_2", "idle", {"friendly_name": "Pocket Assistant"})
    await hass.async_block_till_done()

    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) == "media_player.pocket_assistant_2"
    assert coord.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.pocket_assistant_2"
    assert coord._tracked_ma_counterpart == "media_player.pocket_assistant_2"
    assert suggest_ma_player_for(hass, coord) == "media_player.pocket_assistant_2"

    ma_play_calls: list[dict[str, Any]] = []
    hass.services.async_register(
        "music_assistant",
        "play_media",
        lambda call: ma_play_calls.append(dict(call.data)),
    )
    await execute_coordinator_media_command(
        coord,
        "play_media",
        speaker=coord.local_speaker,
        media_id="library://album/2",
        media_type="album",
        enqueue="replace",
    )
    assert len(ma_play_calls) == 1
    assert ma_play_calls[0]["entity_id"] == "media_player.pocket_assistant_2"
    assert ma_play_calls[0]["media_id"] == "library://album/2"

    studio_payload = build_studio_state_payload(hass, coord)
    ma_catalog = {item["id"]: item["name"] for item in studio_payload["catalog"]["ma_players"]}
    assert ma_catalog["media_player.pocket_assistant"].endswith("(unavailable)")
    assert not ma_catalog["media_player.pocket_assistant_2"].endswith("(unavailable)")

    # Ambiguity guard: if a second ESPHome device of the exact same (manufacturer, model) exists,
    # unlinked resolution refuses to guess and raises `link_ma_player` repair instead.
    esp_twin_entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="esp_twin_2",
            domain="esphome",
            title="Pocket Twin",
            data={"device_name": "pocket_twin"},
        )
    )
    esp_twin_dev = dev_reg.async_get_or_create(
        config_entry_id=esp_twin_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:77")},
        identifiers={("esphome", "aa:bb:cc:dd:ee:77")},
        name="Pocket Twin",
        manufacturer="slampton",
        model="pocket_assistant-board",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_twin_music",
            platform="esphome",
            device_id=esp_twin_dev.id,
            config_entry_id=esp_twin_entry.entry_id,
        )
    )
    hass.states.async_set("media_player.pocket_twin_music", "idle", {})
    sub_twin = ConfigSubentry(
        data={
            CONF_ESPHOME_DEVICE_ID: esp_twin_dev.id,
            "mac": "aa:bb:cc:dd:ee:77",
            CONF_DEVICE_SLUG: "pocket_twin",
            CONF_DEFAULT_AREA: "bedroom",
            CONF_MA_PLAYER_ENTITY: "media_player.pocket_assistant",
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Pocket Twin",
        unique_id="aa:bb:cc:dd:ee:77",
        subentry_id="sub_twin",
    )
    entry.subentries[sub_twin.subentry_id] = sub_twin
    coord_twin = LatterCoordinator(hass=hass, entry=entry, hmac_secret="00" * 32, subentry=sub_twin)
    await coord_twin.async_setup()
    hass.data[DOMAIN][coord_twin.subentry_id] = coord_twin
    entry.runtime_data.coordinators[coord_twin.subentry_id] = coord_twin
    clear_ma_counterpart_cache(hass)

    assert resolve_ma_counterpart_entity(hass, "media_player.pocket_twin_music") is None
    issue_reg = ir.async_get(hass)
    assert any("link_ma_player_sub_twin" in k[1] for k in issue_reg.issues)


async def test_idle_play_resumes_displayed_track_via_ma_library_when_uri_missing(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify tapping Play on an idle speaker with empty MA queue and empty last_media_uri resumes by title + artist."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    ma_entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="ma_entry_lib",
            domain="music_assistant",
            title="Music Assistant",
            data={},
        )
    )
    ent_reg = er.async_get(hass)
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_assistant_2",
            platform="music_assistant",
            unique_id="live_ma_2",
            config_entry_id=ma_entry.entry_id,
        )
    )
    hass.states.async_set(coord.local_speaker, "idle", {"friendly_name": "Pocket Assistant Music"})
    hass.states.async_set("media_player.pocket_assistant_2", "idle", {"friendly_name": "Pocket Assistant"})
    async_set_ma_player_link(hass, coord, "media_player.pocket_assistant_2")

    coord._local_needs_cold_resume = False
    coord._resuming_guard_until = 0.0
    coord.last_media_uri = ""
    coord.last_media_title = "Up From The Sea"
    coord.last_media_artist = "Swervedriver"
    coord.last_media_type = "track"

    ma_play_calls: list[dict[str, Any]] = []
    hass.services.async_register(
        "music_assistant",
        "get_queue",
        lambda _call: {"media_player.pocket_assistant_2": {"current_item": None}},
        supports_response=True,
    )
    hass.services.async_register(
        "music_assistant",
        "get_library",
        lambda _call: {
            "items": [
                {
                    "name": "Up From The Sea",
                    "artist_str": "Swervedriver",
                    "uri": "library://track/99",
                }
            ]
        },
        supports_response=True,
    )
    hass.services.async_register(
        "music_assistant",
        "play_media",
        lambda call: ma_play_calls.append(dict(call.data)),
    )

    orig_async_call = hass.services.async_call

    async def _mock_service_call(
        domain: str, service: str, service_data: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        if domain == "media_player" and service == "media_play":
            raise HomeAssistantError("Queue is empty")
        return await orig_async_call(domain, service, service_data, **kwargs)

    hass.services.async_call = _mock_service_call
    try:
        await execute_coordinator_media_command(coord, "play")
    finally:
        hass.services.async_call = orig_async_call

    assert len(ma_play_calls) == 1
    assert ma_play_calls[0]["entity_id"] == "media_player.pocket_assistant_2"
    assert ma_play_calls[0]["media_id"] == "library://track/99"


async def test_cold_boot_resume_and_album_drilldown_preserve_remaining_tracks_and_ignore_tts(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cold-boot Play preserves remaining album tracks, album track drilldown queues the album tail, and TTS never pollutes last_media_uri."""
    from homeassistant.config_entries import ConfigEntryState

    import custom_components.latter.media as media_mod

    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    ma_entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="ma_entry_album_tail",
            domain="music_assistant",
            title="Music Assistant",
            data={},
        )
    )
    ma_entry._state = ConfigEntryState.LOADED
    ent_reg = er.async_get(hass)
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_assistant_ma",
            platform="music_assistant",
            unique_id="live_ma_tail",
            config_entry_id=ma_entry.entry_id,
        )
    )
    hass.states.async_set(
        coord.local_speaker, "idle", {"friendly_name": "Pocket Assistant Music"}
    )
    hass.states.async_set(
        "media_player.pocket_assistant_ma",
        "paused",
        {
            "friendly_name": "Pocket Assistant",
            "media_title": "Up From The Sea",
            "media_artist": "Swervedriver",
            "media_album_name": "99th Dream",
            "media_content_id": "library://track/42",
            "media_duration": 215.0,
        },
    )
    async_set_ma_player_link(hass, coord, "media_player.pocket_assistant_ma")
    await hass.async_block_till_done()

    # 1. Voice Assistant TTS stream on local ESPHome media_player must NEVER overwrite last_media_uri
    assert coord.last_media_uri == "library://track/42"
    hass.states.async_set(
        coord.local_speaker,
        "playing",
        {
            "friendly_name": "Pocket Assistant Music",
            "media_content_id": "http://10.0.20.10/api/tts_proxy/6v3JLHVdy6kXxeopWCRxaQ.flac",
            "media_duration": 1.4,
        },
    )
    await hass.async_block_till_done()
    assert coord.last_media_uri == "library://track/42"
    assert coord.last_media_duration == 215.0

    hass.states.async_set(
        coord.local_speaker, "idle", {"friendly_name": "Pocket Assistant Music"}
    )
    hass.states.async_set(
        "media_player.pocket_assistant_ma",
        "idle",
        {"friendly_name": "Pocket Assistant"},
    )
    await hass.async_block_till_done()

    album_children = [
        {"title": "99th Dream", "media_content_id": "library://track/41", "media_content_type": "track"},
        {"title": "Up From The Sea", "media_content_id": "library://track/42", "media_content_type": "track"},
        {"title": "She Weaves A Tender Trap", "media_content_id": "library://track/43", "media_content_type": "track"},
        {"title": "These Times", "media_content_id": "library://track/44", "media_content_type": "track"},
    ]
    ma_play_calls: list[dict[str, Any]] = []
    hass.services.async_register(
        "music_assistant",
        "get_queue",
        lambda _call: {
            "media_player.pocket_assistant_ma": {
                "current_item": {
                    "media_item": {
                        "uri": "library://track/42",
                        "album": {"uri": "library://album/4", "name": "99th Dream"},
                    }
                },
                "next_item": {"media_item": {"uri": "library://track/43"}},
                "elapsed_time": 0.0,
            }
        },
        supports_response=True,
    )
    hass.services.async_register(
        "music_assistant",
        "get_library",
        lambda _call: {"items": [{"name": "99th Dream", "uri": "library://album/4"}]},
        supports_response=True,
    )
    hass.services.async_register(
        "media_player",
        "browse_media",
        lambda _call: {
            "media_player.pocket_assistant_ma": {
                "title": "99th Dream",
                "children": album_children,
            }
        },
        supports_response=True,
    )
    hass.services.async_register(
        "music_assistant",
        "play_media",
        lambda call: ma_play_calls.append(dict(call.data)),
    )

    # 2. Cold-boot Play where Sendspin Noise handshake takes ~1.0s (4 * 0.25s) to flip to playing:
    # must NOT invoke play_media or clobber the existing Music Assistant queue.
    sleep_ticks = 0

    async def _fast_sleep(_sec: float) -> None:
        nonlocal sleep_ticks
        sleep_ticks += 1
        if sleep_ticks == 4:
            hass.states.async_set(coord.local_speaker, "playing", {})

    monkeypatch.setattr(media_mod.asyncio, "sleep", _fast_sleep)
    coord._local_needs_cold_resume = True
    coord._resuming_guard_until = 0.0
    await execute_coordinator_media_command(coord, "play")
    assert ma_play_calls == []
    assert coord._local_needs_cold_resume is False

    # 3. Cold-boot Play when media_play raises empty-queue error: expands remaining album tracks [42, 43, 44]
    hass.states.async_set(coord.local_speaker, "idle", {})
    coord._local_needs_cold_resume = True
    coord._resuming_guard_until = 0.0
    orig_async_call = hass.services.async_call

    async def _fail_media_play(
        domain: str, service: str, service_data: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        if domain == "media_player" and service == "media_play":
            raise HomeAssistantError("Queue is empty")
        return await orig_async_call(domain, service, service_data, **kwargs)

    hass.services.async_call = _fail_media_play
    try:
        await execute_coordinator_media_command(coord, "play")
    finally:
        hass.services.async_call = orig_async_call

    assert len(ma_play_calls) == 1
    assert ma_play_calls[0]["media_id"] == [
        "library://track/42",
        "library://track/43",
        "library://track/44",
    ]

    assert ma_play_calls[0]["media_type"] == "track"
    assert ma_play_calls[0]["enqueue"] == "replace"

    # 4. Drilling into album_tracks via music_browse and tapping track 2 queues [42, 43, 44]
    ma_play_calls.clear()
    await hass.services.async_call(
        DOMAIN,
        "music_browse",
        {
            "target_device": coord.device_slug,
            "req_id": 1,
            "mode": "album_tracks",
            "page": 1,
            "page_size": 5,
            "search": "library://album/4",
            "speaker": coord.local_speaker,
        },
        blocking=True,
    )
    await execute_coordinator_media_command(
        coord,
        "play_media",
        speaker=coord.local_speaker,
        media_id="library://track/42",
        media_type="track",
        enqueue="replace",
    )
    assert len(ma_play_calls) == 1
    assert ma_play_calls[0]["media_id"] == [
        "library://track/42",
        "library://track/43",
        "library://track/44",
    ]


async def test_home_hub_rebuild_alarm_caps_separate_pins_climate_cover_and_categories(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify alarm_caps bitmask, separate HA alarm vs Latter PINs, climate/cover/lock/vacuum dispatch, and 6-tab categories."""
    from custom_components.latter.areas import (
        compute_alarm_caps,
        compute_climate_caps,
        compute_vacuum_caps,
        get_available_home_categories,
        get_home_alarm_summary,
        get_home_hub_summary,
    )
    from custom_components.latter.const import (
        CONF_ALARM_ENTITY,
        CONF_CAMERA_ENTITIES,
        CONF_GARAGE_ENTITIES,
        CONF_HOME_CATEGORIES,
        CONF_LOCK_ENTITIES,
        CONF_THERMOSTAT_ENTITIES,
        CONF_VACUUM_ENTITIES,
    )

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
    coord._cached_area_payload = None
    _area_st, area_attrs = coord.get_area_context_payload()
    assert area_attrs["alarm_caps"] == 13
    assert area_attrs["thermostats"][0]["caps"] == 79
    assert area_attrs["vacuums"][0]["caps"] == 11
    assert area_attrs["home_categories"] == "alarm,intercom,thermostat,entry,vacuum"
    wire_fields = area_attrs["payload"].split("\x1f")
    assert len(wire_fields) == 42  # 3 header fields + 39 body fields (indices 3..41)
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
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "home_hub.alarm",
            "action": "arm_home",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "action": "arm_away",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "action": "arm_vacation",
        },
        blocking=True,
    )
    assert ("alarm_control_panel", "alarm_arm_home", {"entity_id": "alarm_control_panel.home_alarm"}) in svc_calls
    assert ("alarm_control_panel", "alarm_arm_away", {"entity_id": "alarm_control_panel.home_alarm"}) in svc_calls
    assert ("alarm_control_panel", "alarm_arm_vacation", {"entity_id": "alarm_control_panel.home_alarm"}) in svc_calls

    # Disarm with empty PIN when code_format="number" -> security_pin_required
    with pytest.raises(ServiceValidationError) as exc_empty_pin:
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "home_hub.alarm",
                "action": "disarm",
            },
            blocking=True,
        )
    assert exc_empty_pin.value.translation_key == "security_pin_required"

    # Disarm with non-4..8-digit PIN when code_format="number" -> security_pin_invalid
    with pytest.raises(ServiceValidationError) as exc_bad_fmt:
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "home_hub.alarm",
                "action": "disarm",
                "code": "12",
            },
            blocking=True,
        )
    assert exc_bad_fmt.value.translation_key == "security_pin_invalid"

    # Disarm with HA's SEPARATE alarm PIN ("9876", different from Latter's "2580"!) SUCCEEDS and forwards code!
    svc_calls.clear()
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "home_hub.alarm",
            "action": "disarm",
            "code": "9876",
        },
        blocking=True,
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
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "home_hub.alarm",
                "action": "disarm",
                "code": "9876",
            },
            blocking=True,
        )
    assert exc_wrong_latter_pin.value.translation_key == "security_pin_invalid"

    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "home_hub.alarm",
            "action": "disarm",
            "code": "2580",
        },
        blocking=True,
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
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "home_hub.alarm",
                "action": "disarm",
                "code": "9876",
            },
            blocking=True,
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
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "climate.main_thermostat",
            "action": "set_temperature",
            "level": 72.5,
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "climate.main_thermostat",
            "action": "hvac_heat",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "climate.main_thermostat",
            "action": "hvac_cool",
        },
        blocking=True,
    )
    # hvac_modes has "auto" (not "heat_cool") -> adapts "hvac_heat_cool" to "auto"
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "climate.main_thermostat",
            "action": "hvac_heat_cool",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "climate.main_thermostat",
            "action": "hvac_off",
        },
        blocking=True,
    )
    # Reverse adaptation: hvac_modes has "heat_cool" (not "auto") -> adapts "hvac_auto" to "heat_cool"
    hass.states.async_set(
        "climate.main_thermostat",
        "heat_cool",
        {"hvac_modes": ["off", "heat", "cool", "heat_cool"]},
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "climate.main_thermostat",
            "action": "hvac_auto",
        },
        blocking=True,
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
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "lock.front_door",
            "action": "lock",
        },
        blocking=True,
    )
    with pytest.raises(ServiceValidationError) as exc_lock_pin:
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "lock.front_door",
                "action": "unlock",
                "code": "9876",
            },
            blocking=True,
        )
    assert exc_lock_pin.value.translation_key == "security_pin_invalid"
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "lock.front_door",
            "action": "unlock",
            "code": "2580",
        },
        blocking=True,
    )

    # Garage is currently "closed": close_cover MUST still call close_cover (never toggle open!)
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "cover.main_garage",
            "action": "close_cover",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "cover.main_garage",
            "action": "open_cover",
            "code": "2580",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "cover.main_garage",
            "action": "stop_cover",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "vacuum.robo_vac",
            "action": "start",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "vacuum.robo_vac",
            "action": "pause",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "area_action",
        {
            "target_device": coord.device_slug,
            "entity_id": "vacuum.robo_vac",
            "action": "return_to_base",
        },
        blocking=True,
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
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "climate.main_thermostat",
                "action": act_c,
                **extra_c,
            },
            blocking=True,
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
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "vacuum.robo_vac",
                "action": vac_act,
            },
            blocking=True,
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
        await hass.services.async_call(
            DOMAIN,
            "area_action",
            {
                "target_device": coord.device_slug,
                "entity_id": "vacuum.robo_vac",
                "action": vac_act,
            },
            blocking=True,
        )
    assert ("vacuum", "turn_on", {"entity_id": "vacuum.robo_vac"}) in svc_calls
    assert ("vacuum", "turn_off", {"entity_id": "vacuum.robo_vac"}) in svc_calls


async def test_sendspin_mass_players_mac_auto_links_twin_boards_and_heals_cross_link(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify MA 2.10 `universal_player` (`up...`) auto-links twin same-model boards via `mass.players` MACs without cross-linking."""
    from types import SimpleNamespace

    from custom_components.latter.config_flow import _apply_onboarding_profile_and_defaults
    from custom_components.latter.media import async_heal_coordinator_ma_links, clear_ma_counterpart_cache

    entry, _sys_obj, _pocket_coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    issue_reg = ir.async_get(hass)

    # Set up Music Assistant entry with runtime `mass.players` holding Sendspin MACs (HA Device Registry has connections=[])
    mass_players: dict[str, Any] = {
        "up4a1a675f": SimpleNamespace(
            player_id="up4a1a675f",
            device_info=SimpleNamespace(
                mac_address="E8:F6:0A:E0:F2:FE",
                identifiers={"mac_address": "E8:F6:0A:E0:F2:FE"},
            ),
            protocols=[],
            output_protocols=[],
        ),
        "up94060b4a": SimpleNamespace(
            player_id="up94060b4a",
            device_info=SimpleNamespace(
                mac_address="E8:F6:0A:E0:F2:DA",
                identifiers={"mac_address": "E8:F6:0A:E0:F2:DA"},
            ),
            protocols=[],
            output_protocols=[],
        ),
    }
    ma_entry = ConfigEntry(
        entry_id="ma_sendspin_twins",
        domain="music_assistant",
        title="Music Assistant",
        data={},
    )
    ma_entry.runtime_data = SimpleNamespace(mass=SimpleNamespace(players=mass_players))
    hass.config_entries.add_entry(ma_entry)

    ma_desk_dev = dev_reg.async_get_or_create(
        config_entry_id=ma_entry.entry_id,
        identifiers={("music_assistant", "up4a1a675f")},
        name="Desk Assistant",
        manufacturer="slampton",
        model="desk-assistant-p4-86",
    )
    ma_garage_dev = dev_reg.async_get_or_create(
        config_entry_id=ma_entry.entry_id,
        identifiers={("music_assistant", "up94060b4a")},
        name="Garage Assistant",
        manufacturer="slampton",
        model="desk-assistant-p4-86",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.desk_assistant",
            platform="music_assistant",
            unique_id="up4a1a675f",
            device_id=ma_desk_dev.id,
            config_entry_id=ma_entry.entry_id,
        )
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.garage_assistant",
            platform="music_assistant",
            unique_id="up94060b4a",
            device_id=ma_garage_dev.id,
            config_entry_id=ma_entry.entry_id,
        )
    )

    # Board 1: Desk Assistant (offline while Garage Assistant's Sendspin player comes online first!)
    esp_desk_entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="esp_desk_p4",
            domain="esphome",
            title="Desk Assistant",
            data={"device_name": "desk_assistant"},
        )
    )
    esp_desk_dev = dev_reg.async_get_or_create(
        config_entry_id=esp_desk_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e8:f6:0a:e0:f2:fe")},
        name="Desk Assistant",
        manufacturer="slampton",
        model="desk-assistant-p4-86",
        area_id="living_room",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.desk_assistant_music",
            platform="esphome",
            device_id=esp_desk_dev.id,
            config_entry_id=esp_desk_entry.entry_id,
        )
    )
    hass.states.async_set("media_player.desk_assistant_music", "unavailable", {})
    hass.states.async_set("media_player.desk_assistant", "unavailable", {})
    hass.states.async_set("media_player.garage_assistant", "idle", {})

    # Even before Garage Assistant is added to ESPHome, Pass 3 MUST NOT cross-link Desk Assistant to Garage Assistant!
    sub_desk = ConfigSubentry(
        data={
            CONF_ESPHOME_DEVICE_ID: esp_desk_dev.id,
            "mac": "e8:f6:0a:e0:f2:fe",
            CONF_DEVICE_SLUG: "desk_assistant",
            CONF_DEFAULT_AREA: "living_room",
            CONF_MA_PLAYER_ENTITY: "media_player.garage_assistant",  # Simulate prior accidental cross-link
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Desk Assistant",
        unique_id="latter_e8:f6:0a:e0:f2:fe",
        subentry_id="sub_desk_p4",
    )
    entry.subentries[sub_desk.subentry_id] = sub_desk
    coord_desk = LatterCoordinator(hass=hass, entry=entry, hmac_secret=b"\x01" * 32, subentry=sub_desk)
    await coord_desk.async_setup()
    hass.data[DOMAIN][coord_desk.subentry_id] = coord_desk
    entry.runtime_data.coordinators[coord_desk.subentry_id] = coord_desk

    # Board 2: Garage Assistant (exact same manufacturer & model: slampton / desk-assistant-p4-86)
    esp_garage_entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="esp_garage_p4",
            domain="esphome",
            title="Garage Assistant",
            data={"device_name": "garage_assistant"},
        )
    )
    esp_garage_dev = dev_reg.async_get_or_create(
        config_entry_id=esp_garage_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e8:f6:0a:e0:f2:da")},
        name="Garage Assistant",
        manufacturer="slampton",
        model="desk-assistant-p4-86",
        area_id="garage",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.garage_assistant_music",
            platform="esphome",
            device_id=esp_garage_dev.id,
            config_entry_id=esp_garage_entry.entry_id,
        )
    )
    hass.states.async_set("media_player.garage_assistant_music", "idle", {})

    # Onboarding Garage Assistant auto-populates `ma_player_entity` directly from Sendspin MAC!
    clear_ma_counterpart_cache(hass)
    onboarded_data = _apply_onboarding_profile_and_defaults(
        hass, esp_garage_dev, {"device_group": "auto"}, rebind_hardware=True
    )
    assert onboarded_data[CONF_MA_PLAYER_ENTITY] == "media_player.garage_assistant"

    sub_garage = ConfigSubentry(
        data={k: v for k, v in onboarded_data.items() if k != CONF_MA_PLAYER_ENTITY},  # Also test runtime auto-link!
        subentry_type=SUBENTRY_DEVICE,
        title="Garage Assistant",
        unique_id="latter_e8:f6:0a:e0:f2:da",
        subentry_id="sub_garage_p4",
    )
    entry.subentries[sub_garage.subentry_id] = sub_garage
    coord_garage = LatterCoordinator(hass=hass, entry=entry, hmac_secret=b"\x01" * 32, subentry=sub_garage)
    await coord_garage.async_setup()
    hass.data[DOMAIN][coord_garage.subentry_id] = coord_garage
    entry.runtime_data.coordinators[coord_garage.subentry_id] = coord_garage

    async_heal_coordinator_ma_links(hass)

    assert resolve_ma_counterpart_entity(hass, "media_player.garage_assistant_music") == "media_player.garage_assistant"
    assert coord_garage.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.garage_assistant"
    assert not any("sub_garage_p4" in k[1] for k in issue_reg.issues)

    # And Desk Assistant's cross-linked `media_player.garage_assistant` self-healed back to `media_player.desk_assistant`!
    assert resolve_ma_counterpart_entity(hass, "media_player.desk_assistant_music") == "media_player.desk_assistant"
    assert coord_desk.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.desk_assistant"
    assert not any("sub_desk_p4" in k[1] for k in issue_reg.issues)


async def test_firmware_flash_and_reboot_stagger_never_flashes_transient_ma_repair(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify firmware flash / restart staggered reconnects never briefly raise `link_ma_player`."""
    from types import SimpleNamespace

    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    issue_reg = ir.async_get(hass)

    # Register another always-online MA speaker in the house so `live_candidates` is non-empty
    ma_entry = ConfigEntry(
        entry_id="ma_reboot_test",
        domain="music_assistant",
        title="Music Assistant",
        data={},
    )
    mass_players: dict[str, Any] = {
        "up_pocket": SimpleNamespace(
            player_id="up_pocket",
            device_info=SimpleNamespace(
                mac_address="AA:BB:CC:DD:EE:01",
                identifiers={"mac_address": "AA:BB:CC:DD:EE:01"},
            ),
            protocols=[],
            output_protocols=[],
        ),
        "up_hifi": SimpleNamespace(
            player_id="up_hifi",
            device_info=SimpleNamespace(mac_address=None, identifiers={}),
            protocols=[],
            output_protocols=[],
        ),
    }
    ma_entry.runtime_data = SimpleNamespace(mass=SimpleNamespace(players=mass_players))
    hass.config_entries.add_entry(ma_entry)

    for uid, eid, name in (
        ("up_pocket", "media_player.pocket_ma", "Pocket Assistant"),
        ("up_hifi", "media_player.house_hifi", "House HiFi"),
    ):
        d = dev_reg.async_get_or_create(
            config_entry_id=ma_entry.entry_id,
            identifiers={("music_assistant", uid)},
            name=name,
        )
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=eid,
                platform="music_assistant",
                unique_id=uid,
                device_id=d.id,
                config_entry_id=ma_entry.entry_id,
            )
        )

    hass.states.async_set(coord.local_speaker, "idle", {})
    hass.states.async_set("media_player.house_hifi", "idle", {})
    hass.states.async_set("media_player.pocket_ma", "idle", {})
    await hass.async_block_till_done()

    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) == "media_player.pocket_ma"
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)

    # 1) Simulate Sendspin detaching on reboot (`device_info` loses MAC while detached, MA entity goes `unavailable`
    #    BEFORE ESPHome's `local_speaker` marks itself `unavailable`):
    mass_players["up_pocket"].device_info = SimpleNamespace(mac_address=None, identifiers={})
    hass.states.async_set("media_player.pocket_ma", "unavailable", {})
    await hass.async_block_till_done()
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)

    # 2) ESPHome Native API drops, then reconnects FIRST (`unavailable` -> `idle`) while Sendspin is still `unavailable`:
    hass.states.async_set(coord.local_speaker, "unavailable", {})
    await hass.async_block_till_done()
    hass.states.async_set(coord.local_speaker, "idle", {})
    await hass.async_block_till_done()
    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) == "media_player.pocket_ma"
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)

    # 3) Also test a manually-linked non-MAC MA speaker (`media_player.house_hifi`) bouncing across reboot:
    async_set_ma_player_link(hass, coord, "media_player.house_hifi")
    hass.states.async_set("media_player.house_hifi", "unavailable", {})
    await hass.async_block_till_done()
    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) == "media_player.house_hifi"
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)


async def test_ma_2_10_encrypted_sendspin_client_id_and_nth_twin_bijection(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify MA 2.10.12 encrypted Sendspin (`output_protocols` client_id, empty `identifiers`) + Nth twin bijection."""
    from types import SimpleNamespace

    from custom_components.latter.config_flow import _apply_onboarding_profile_and_defaults
    from custom_components.latter.media import async_heal_coordinator_ma_links, clear_ma_counterpart_cache

    entry, _sys_obj, _pocket_coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    issue_reg = ir.async_get(hass)

    # Exact MA 2.10.12 shape: `device_info.identifiers == {}` (no MAC!), encrypted Sendspin `client_id` in `output_protocols`
    mass_players: dict[str, Any] = {
        "up4a1a675f": SimpleNamespace(
            player_id="up4a1a675f",
            provider="universal_player--inst",
            device_info=SimpleNamespace(mac_address=None, identifiers={}),
            protocols=[],
            output_protocols=[
                SimpleNamespace(
                    output_protocol_id="ss_noise_key_desk_01",
                    protocol_domain="sendspin",
                    derived_from=None,
                )
            ],
        ),
        "up94060b4a": SimpleNamespace(
            player_id="up94060b4a",
            provider="universal_player--inst",
            device_info=SimpleNamespace(mac_address=None, identifiers={}),
            protocols=[],
            output_protocols=[
                SimpleNamespace(
                    output_protocol_id="ss_noise_key_garage_02",
                    protocol_domain="sendspin",
                    derived_from=None,
                )
            ],
        ),
        "upefc5c691": SimpleNamespace(
            player_id="upefc5c691",
            provider="universal_player--inst",
            device_info=SimpleNamespace(mac_address=None, identifiers={}),
            protocols=[],
            output_protocols=[
                SimpleNamespace(
                    output_protocol_id="ss_noise_key_test_03",
                    protocol_domain="sendspin",
                    derived_from=None,
                )
            ],
        ),
    }
    ma_entry = ConfigEntry(
        entry_id="ma_210_sendspin",
        domain="music_assistant",
        title="Music Assistant",
        data={},
    )
    ma_entry.runtime_data = SimpleNamespace(mass=SimpleNamespace(players=mass_players))
    hass.config_entries.add_entry(ma_entry)

    boards = [
        ("desk_assistant", "Desk Assistant", "e8:f6:0a:e0:f2:fe", "ss_noise_key_desk_01", "up4a1a675f", "media_player.desk_assistant", "unavailable"),
        ("garage_assistant", "Garage Assistant", "e8:f6:0a:e0:f2:da", "ss_noise_key_garage_02", "up94060b4a", "media_player.garage_assistant", "idle"),
        ("test_assistant", "Test Assistant", "30:ed:a0:e2:3d:92", "ss_noise_key_test_03", "upefc5c691", "media_player.desk_assistant_2", "idle"),
    ]
    esp_devs: dict[str, Any] = {}
    esp_entries: dict[str, Any] = {}
    for slug, title, mac, ss_cid, ma_uid, ma_eid, st in boards:
        ma_dev = dev_reg.async_get_or_create(
            config_entry_id=ma_entry.entry_id,
            identifiers={("music_assistant", ma_uid)},
            name=title,
            manufacturer="slampton",
            model="desk-assistant-p4-86",
        )
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=ma_eid,
                platform="music_assistant",
                unique_id=ma_uid,
                device_id=ma_dev.id,
                config_entry_id=ma_entry.entry_id,
            )
        )
        hass.states.async_set(ma_eid, st, {"friendly_name": title})

        esp_ce = ConfigEntry(
            entry_id=f"esp_{slug}",
            domain="esphome",
            title=title,
            data={"device_name": slug},
        )
        esp_ce.runtime_data = SimpleNamespace(
            device_capabilities=SimpleNamespace(
                sendspin=SimpleNamespace(client_id=ss_cid, feature_flags=1)
            )
        )
        hass.config_entries.add_entry(esp_ce)
        esp_entries[slug] = esp_ce
        esp_d = dev_reg.async_get_or_create(
            config_entry_id=esp_ce.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=title,
            manufacturer="slampton",
            model="desk-assistant-p4-86",
        )
        esp_devs[slug] = esp_d
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=f"media_player.{slug}_music",
                platform="esphome",
                device_id=esp_d.id,
                config_entry_id=esp_ce.entry_id,
            )
        )
        hass.states.async_set(f"media_player.{slug}_music", st, {})

    # 1) Even when ALL THREE `desk-assistant-p4-86` boards are unbound simultaneously, encrypted Sendspin `client_id`
    #    auto-discovers each board's exact `universal_player` entity 1-to-1 with zero ambiguity!
    clear_ma_counterpart_cache(hass)
    for slug, _title, _mac, _ss_cid, _ma_uid, expected_ma_eid, _st in boards:
        onboarded = _apply_onboarding_profile_and_defaults(
            hass, esp_devs[slug], {"device_group": "auto"}, rebind_hardware=True
        )
        assert onboarded[CONF_MA_PLAYER_ENTITY] == expected_ma_eid

    # 2) Also verify Nth-twin unbound bijection when `mass` client is temporarily unavailable during onboarding
    #    while Desk Assistant (offline) and Garage Assistant (online) are already bound in Latter:
    ma_entry.runtime_data = None
    clear_ma_counterpart_cache(hass)
    for slug, title, mac, ma_eid in (
        ("desk_assistant", "Desk Assistant", "e8:f6:0a:e0:f2:fe", "media_player.desk_assistant"),
        ("garage_assistant", "Garage Assistant", "e8:f6:0a:e0:f2:da", "media_player.garage_assistant"),
    ):
        sub = ConfigSubentry(
            data={
                CONF_ESPHOME_DEVICE_ID: esp_devs[slug].id,
                "mac": mac,
                CONF_DEVICE_SLUG: slug,
                CONF_MA_PLAYER_ENTITY: ma_eid,
            },
            subentry_type=SUBENTRY_DEVICE,
            title=title,
            unique_id=f"latter_{mac}",
            subentry_id=f"sub_{slug}",
        )
        entry.subentries[sub.subentry_id] = sub
        c = LatterCoordinator(hass=hass, entry=entry, hmac_secret=b"\x02" * 32, subentry=sub)
        hass.data[DOMAIN][c.subentry_id] = c
        entry.runtime_data.coordinators[c.subentry_id] = c
        await c.async_setup()

    onboarded_test = _apply_onboarding_profile_and_defaults(
        hass, esp_devs["test_assistant"], {"device_group": "auto"}, rebind_hardware=True
    )
    assert onboarded_test[CONF_MA_PLAYER_ENTITY] == "media_player.desk_assistant_2"

    sub_test = ConfigSubentry(
        data={k: v for k, v in onboarded_test.items() if k != CONF_MA_PLAYER_ENTITY},
        subentry_type=SUBENTRY_DEVICE,
        title="Test Assistant",
        unique_id="latter_30:ed:a0:e2:3d:92",
        subentry_id="sub_test_assistant",
    )
    entry.subentries[sub_test.subentry_id] = sub_test
    c_test = LatterCoordinator(hass=hass, entry=entry, hmac_secret=b"\x02" * 32, subentry=sub_test)
    hass.data[DOMAIN][c_test.subentry_id] = c_test
    entry.runtime_data.coordinators[c_test.subentry_id] = c_test
    await c_test.async_setup()
    async_heal_coordinator_ma_links(hass)

    assert c_test.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.desk_assistant_2"
    assert not any("sub_test_assistant" in k[1] for k in issue_reg.issues)


async def test_sendspin_uses_config_entry_id_and_caches_ma_misses(
    hass: Any, setup_latter_hub: Any, monkeypatch: Any
) -> None:
    """Prevent MainThread CPU storms: never touch deprecated DeviceEntry.config_entries, cache offline/None MA lookups, and coalesce active_media builds."""
    from types import SimpleNamespace

    from custom_components.latter import media as media_mod
    from custom_components.latter.media import (
        _extract_esphome_sendspin_info,
        build_active_media_payload,
        clear_ma_counterpart_cache,
    )

    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)

    class _NoDeprecatedConfigEntriesDev:
        id = "dev_strict_no_legacy"
        config_entry_id = "esp_strict_entry"

        @property
        def config_entries(self) -> set[str]:
            raise AssertionError("Must not access deprecated DeviceEntry.config_entries")

    esp_ce = hass.config_entries.add_entry(
        ConfigEntry(entry_id="esp_strict_entry", domain="esphome", title="Strict")
    )
    esp_ce.runtime_data = SimpleNamespace(
        device_capabilities=SimpleNamespace(
            sendspin=SimpleNamespace(client_id="ss_strict_client_123", feature_flags=1)
        )
    )
    dev_reg.devices[_NoDeprecatedConfigEntriesDev.id] = _NoDeprecatedConfigEntriesDev()  # type: ignore[assignment]

    cids, pending = _extract_esphome_sendspin_info(hass, [_NoDeprecatedConfigEntriesDev.id])
    assert cids == {"ss_strict_client_123"}
    assert pending is False

    # Unmatched / offline speaker must be cached so repeated calls do not rescan MA candidates
    clear_ma_counterpart_cache(hass)
    scan_calls = 0
    orig_build_candidates = media_mod._build_ma_candidates

    def _counting_build_candidates(h: Any) -> Any:
        nonlocal scan_calls
        scan_calls += 1
        return orig_build_candidates(h)

    monkeypatch.setattr(media_mod, "_build_ma_candidates", _counting_build_candidates)

    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) is None
    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) is None
    assert scan_calls == 1

    # build_active_media_payload must call resolve_ma_counterpart_entity once per build and coalesce back-to-back reads
    resolve_calls = 0
    orig_resolve = media_mod.resolve_ma_counterpart_entity

    def _counting_resolve(h: Any, spk: str) -> Any:
        nonlocal resolve_calls
        resolve_calls += 1
        return orig_resolve(h, spk)

    monkeypatch.setattr(media_mod, "resolve_ma_counterpart_entity", _counting_resolve)
    coord._cached_media_payload = None
    _state1, _attrs1 = build_active_media_payload(coord)
    _state2, _attrs2 = build_active_media_payload(coord)
    assert resolve_calls == 1






