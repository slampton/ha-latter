"""Integration tests for bound Device -> HA RPC reassembly, target pinning, and 3-tier security PIN policy."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.latter.const import (
    CONF_DEFAULT_AREA,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
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
    execute_coordinator_media_command,
    set_coordinator_active_speaker,
)
from custom_components.latter.protocol import (
    check_perimeter_action_allowed,
    hash_security_pin,
    is_sensitive_perimeter_action,
    verify_security_pin,
)
from custom_components.latter.services import async_dispatch_bound_rpc


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
