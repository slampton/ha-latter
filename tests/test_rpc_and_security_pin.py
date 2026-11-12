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

