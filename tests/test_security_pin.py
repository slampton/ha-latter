"""Tests for 3-tier security PIN policy, PBKDF2 verification, Sendspin MA auto-linking, and MA cache coalescing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
import pytest

from custom_components.latter.config_flow import _apply_onboarding_profile_and_defaults
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
from custom_components.latter.media import (
    linking as linking_mod,
    state_payload as state_payload_mod,
)
from custom_components.latter.media.linking import (
    async_heal_coordinator_ma_links,
    async_set_ma_player_link,
    clear_ma_counterpart_cache,
    resolve_ma_counterpart_entity,
)
from custom_components.latter.media.state_payload import build_active_media_payload
from custom_components.latter.protocol_policy import (
    check_perimeter_action_allowed,
    hash_security_pin,
    is_sensitive_perimeter_action,
    verify_security_pin,
    wrap_pin_code,
)
from tests.helpers import (
    add_mock_entry,
    get_service_calls,
    make_subentry,
    register_device,
    register_entity,
)


async def test_three_tier_security_pin_policy_and_pbkdf2_verification(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify auto/allow/require_pin/block policies across locks, alarms, and garage covers."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    hass.states.async_set("lock.front_door", "locked", {"friendly_name": "Front Door"})
    hass.states.async_set(
        "alarm_control_panel.home_alarm", "armed_away", {"friendly_name": "Home Alarm"}
    )
    hass.states.async_set(
        "cover.garage_door",
        "closed",
        {"device_class": "garage", "friendly_name": "Garage Door"},
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

    # Stationary hardware manifest with "auto" -> requires PIN on unlock/disarm/open_cover(garage)
    coord._runtime.hello_manifest = {**coord.hardware_manifest, "stationary": 1}
    assert coord.security_pin_policy == "require_pin"

    # Closing/locking/arming verbs NEVER require a PIN
    assert is_sensitive_perimeter_action("lock", "lock") is False
    assert is_sensitive_perimeter_action("alarm_control_panel", "arm_away") is False
    assert (
        is_sensitive_perimeter_action("cover", "close_cover", device_class="garage")
        is False
    )
    assert is_sensitive_perimeter_action("lock", "unlock") is True
    assert check_perimeter_action_allowed(
        "require_pin", provided_code="2580", stored_pin_hash=pin_hash
    ) == (True, "")

    nonce_seq = 0

    def _wrap(ent: str, act: str, pin: str) -> str:
        nonlocal nonce_seq
        nonce_seq += 1
        return wrap_pin_code(
            coord.pin_session_key_id,
            coord.pin_session_key_bytes,
            nonce_seq,
            ent,
            act,
            pin,
        )

    # Unlock without PIN -> security_pin_required
    with pytest.raises(ServiceValidationError) as exc_req:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "action": "unlock",
                "entity_id": "lock.front_door",
            },
        )
    assert exc_req.value.translation_key == "security_pin_required"

    # Unlock with wrong PIN -> security_pin_invalid
    with pytest.raises(ServiceValidationError) as exc_bad:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "action": "unlock",
                "entity_id": "lock.front_door",
                "code": _wrap("lock.front_door", "unlock", "0000"),
            },
        )
    assert exc_bad.value.translation_key == "security_pin_invalid"

    # Unlock with valid PIN -> succeeds!
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "area_action",
        {
            "action": "unlock",
            "entity_id": "lock.front_door",
            "code": _wrap("lock.front_door", "unlock", "2580"),
        },
    )
    assert any(
        c.domain == "lock" and c.service == "unlock" for c in get_service_calls(hass)
    )

    # Policy = "block" rejects even when valid PIN is supplied
    sub = entry.subentries["sub_pocket"]
    blocked_data = {**sub.data, CONF_SECURITY_PIN_POLICY: "block"}
    hass.config_entries.async_update_subentry(entry, sub, data=blocked_data)
    await hass.async_block_till_done()
    coord.subentry = entry.subentries["sub_pocket"]
    await coord.async_apply_options()

    with pytest.raises(ServiceValidationError) as exc_blk:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            "area_action",
            {
                "action": "open_cover",
                "entity_id": "cover.garage_door",
                "code": _wrap("cover.garage_door", "open_cover", "2580"),
            },
        )
    assert exc_blk.value.translation_key == "security_action_blocked"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_sendspin_mass_players_mac_auto_links_twin_boards_and_heals_cross_link(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify MA 2.10 `universal_player` (`up...`) auto-links twin same-model boards via `mass.players` MACs without cross-linking."""
    entry, _sys_obj_init, _pocket_coord = await setup_latter_hub(hass)
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
    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="ma_sendspin_twins",
        data={},
    )
    ma_entry.runtime_data = SimpleNamespace(mass=SimpleNamespace(players=mass_players))

    ma_desk_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        identifiers={("music_assistant", "up4a1a675f")},
        name="Desk Assistant",
        manufacturer="Latter",
        model="desk-assistant-p4-86",
    )
    ma_garage_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        identifiers={("music_assistant", "up94060b4a")},
        name="Garage Assistant",
        manufacturer="Latter",
        model="desk-assistant-p4-86",
    )
    register_entity(
        hass,
        "media_player.desk_assistant",
        platform="music_assistant",
        unique_id="up4a1a675f",
        device_id=ma_desk_dev.id,
        config_entry=ma_entry,
    )
    register_entity(
        hass,
        "media_player.garage_assistant",
        platform="music_assistant",
        unique_id="up94060b4a",
        device_id=ma_garage_dev.id,
        config_entry=ma_entry,
    )

    # Board 1: Desk Assistant (offline while Garage Assistant's Sendspin player comes online first!)
    esp_desk_entry = add_mock_entry(
        hass,
        domain="esphome",
        title="Desk Assistant",
        entry_id="esp_desk_p4",
        data={"device_name": "desk_assistant"},
    )
    esp_desk_dev = register_device(
        hass,
        config_entry_id=esp_desk_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e8:f6:0a:e0:f2:fe")},
        name="Desk Assistant",
        manufacturer="Latter",
        model="desk-assistant-p4-86",
        area_id="living_room",
    )
    register_entity(
        hass,
        "media_player.desk_assistant_music",
        platform="esphome",
        device_id=esp_desk_dev.id,
        config_entry=esp_desk_entry,
    )
    hass.states.async_set("media_player.desk_assistant_music", "unavailable", {})
    hass.states.async_set("media_player.desk_assistant", "unavailable", {})
    hass.states.async_set("media_player.garage_assistant", "idle", {})

    # Even before Garage Assistant is added to ESPHome, Pass 3 MUST NOT cross-link Desk Assistant to Garage Assistant!
    sub_desk = make_subentry(
        {
            CONF_ESPHOME_DEVICE_ID: esp_desk_dev.id,
            "mac": "e8:f6:0a:e0:f2:fe",
            CONF_DEVICE_SLUG: "desk_assistant",
            CONF_DEFAULT_AREA: "living_room",
            CONF_MA_PLAYER_ENTITY: "media_player.garage_assistant",
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Desk Assistant",
        unique_id="latter_e8:f6:0a:e0:f2:fe",
        subentry_id="sub_desk_p4",
    )
    hass.config_entries.async_add_subentry(entry, sub_desk)
    await hass.async_block_till_done()

    # Board 2: Garage Assistant (exact same manufacturer & model: Latter / desk-assistant-p4-86)
    esp_garage_entry = add_mock_entry(
        hass,
        domain="esphome",
        title="Garage Assistant",
        entry_id="esp_garage_p4",
        data={"device_name": "garage_assistant"},
    )
    esp_garage_dev = register_device(
        hass,
        config_entry_id=esp_garage_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e8:f6:0a:e0:f2:da")},
        name="Garage Assistant",
        manufacturer="Latter",
        model="desk-assistant-p4-86",
        area_id="garage",
    )
    register_entity(
        hass,
        "media_player.garage_assistant_music",
        platform="esphome",
        device_id=esp_garage_dev.id,
        config_entry=esp_garage_entry,
    )
    hass.states.async_set("media_player.garage_assistant_music", "idle", {})

    # Onboarding Garage Assistant auto-populates `ma_player_entity` directly from Sendspin MAC!
    clear_ma_counterpart_cache(hass)
    onboarded_data = _apply_onboarding_profile_and_defaults(
        hass, esp_garage_dev, {"device_group": "auto"}, rebind_hardware=True
    )
    assert onboarded_data[CONF_MA_PLAYER_ENTITY] == "media_player.garage_assistant"

    sub_garage = make_subentry(
        {k: v for k, v in onboarded_data.items() if k != CONF_MA_PLAYER_ENTITY},
        subentry_type=SUBENTRY_DEVICE,
        title="Garage Assistant",
        unique_id="latter_e8:f6:0a:e0:f2:da",
        subentry_id="sub_garage_p4",
    )
    hass.config_entries.async_add_subentry(entry, sub_garage)
    await hass.async_block_till_done()

    async_heal_coordinator_ma_links(hass)
    sys_obj = entry.runtime_data
    coord_desk = sys_obj.coordinators["sub_desk_p4"]
    coord_garage = sys_obj.coordinators["sub_garage_p4"]

    assert (
        resolve_ma_counterpart_entity(hass, "media_player.garage_assistant_music")
        == "media_player.garage_assistant"
    )
    assert coord_garage.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.garage_assistant"
    assert not any("sub_garage_p4" in k[1] for k in issue_reg.issues)

    # And Desk Assistant's cross-linked `media_player.garage_assistant` self-healed back to `media_player.desk_assistant`!
    assert (
        resolve_ma_counterpart_entity(hass, "media_player.desk_assistant_music")
        == "media_player.desk_assistant"
    )
    assert coord_desk.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.desk_assistant"
    assert not any("sub_desk_p4" in k[1] for k in issue_reg.issues)

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_firmware_flash_and_reboot_stagger_never_flashes_transient_ma_repair(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify firmware flash / restart staggered reconnects never briefly raise `link_ma_player`."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    issue_reg = ir.async_get(hass)

    # Register another always-online MA speaker in the Site so `live_candidates` is non-empty
    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="ma_reboot_test",
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

    for uid, eid, name in (
        ("up_pocket", "media_player.pocket_ma", "Pocket Assistant"),
        ("up_hifi", "media_player.site_hifi", "Site HiFi"),
    ):
        d = register_device(
            hass,
            config_entry_id=ma_entry.entry_id,
            entry_domain="music_assistant",
            identifiers={("music_assistant", uid)},
            name=name,
            manufacturer="Latter",
        )
        register_entity(
            hass,
            eid,
            platform="music_assistant",
            unique_id=uid,
            device_id=d.id,
            config_entry=ma_entry,
        )

    hass.states.async_set(coord.local_speaker, "idle", {})
    hass.states.async_set("media_player.site_hifi", "idle", {})
    hass.states.async_set("media_player.pocket_ma", "idle", {})
    await hass.async_block_till_done()

    assert (
        resolve_ma_counterpart_entity(hass, coord.local_speaker)
        == "media_player.pocket_ma"
    )
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)

    # 1) Simulate Sendspin detaching on reboot (`device_info` loses MAC while detached, MA entity goes `unavailable`
    #    BEFORE ESPHome's `local_speaker` marks itself `unavailable`):
    mass_players["up_pocket"].device_info = SimpleNamespace(
        mac_address=None, identifiers={}
    )
    hass.states.async_set("media_player.pocket_ma", "unavailable", {})
    await hass.async_block_till_done()
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)

    # 2) ESPHome Native API drops, then reconnects FIRST (`unavailable` -> `idle`) while Sendspin is still `unavailable`:
    hass.states.async_set(coord.local_speaker, "unavailable", {})
    await hass.async_block_till_done()
    hass.states.async_set(coord.local_speaker, "idle", {})
    await hass.async_block_till_done()
    assert (
        resolve_ma_counterpart_entity(hass, coord.local_speaker)
        == "media_player.pocket_ma"
    )
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)

    # 3) Also test a manually-linked non-MAC MA speaker (`media_player.site_hifi`) bouncing across reboot:
    async_set_ma_player_link(hass, coord, "media_player.site_hifi")
    hass.states.async_set("media_player.site_hifi", "unavailable", {})
    await hass.async_block_till_done()
    assert (
        resolve_ma_counterpart_entity(hass, coord.local_speaker)
        == "media_player.site_hifi"
    )
    assert not any("link_ma_player" in k[1] for k in issue_reg.issues)

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_ma_2_10_encrypted_sendspin_client_id_and_nth_twin_bijection(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify MA 2.10.12 encrypted Sendspin (`output_protocols` client_id, empty `identifiers`) + Nth twin bijection."""
    entry, _sys_obj_init, _pocket_coord = await setup_latter_hub(hass)
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
    ma_entry = add_mock_entry(
        hass, domain="music_assistant", title="Music Assistant", entry_id="ma_210_sendspin", data={}
    )
    ma_entry.runtime_data = SimpleNamespace(mass=SimpleNamespace(players=mass_players))

    boards = [
        ("desk_assistant", "Desk Assistant", "e8:f6:0a:e0:f2:fe", "ss_noise_key_desk_01", "up4a1a675f", "media_player.desk_assistant", "unavailable"),
        ("garage_assistant", "Garage Assistant", "e8:f6:0a:e0:f2:da", "ss_noise_key_garage_02", "up94060b4a", "media_player.garage_assistant", "idle"),
        ("test_assistant", "Test Assistant", "30:ed:a0:e2:3d:92", "ss_noise_key_test_03", "upefc5c691", "media_player.desk_assistant_2", "idle"),
    ]
    esp_devs: dict[str, Any] = {}
    for slug, title, mac, ss_cid, ma_uid, ma_eid, st in boards:
        ma_dev = register_device(
            hass, config_entry_id=ma_entry.entry_id, entry_domain="music_assistant",
            identifiers={("music_assistant", ma_uid)}, name=title, manufacturer="Latter", model="desk-assistant-p4-86",
        )
        register_entity(
            hass, ma_eid, platform="music_assistant", unique_id=ma_uid, device_id=ma_dev.id, config_entry=ma_entry,
        )
        hass.states.async_set(ma_eid, st, {"friendly_name": title})

        esp_ce = add_mock_entry(hass, domain="esphome", title=title, entry_id=f"esp_{slug}", data={"device_name": slug})
        esp_ce.runtime_data = SimpleNamespace(
            device_capabilities=SimpleNamespace(sendspin=SimpleNamespace(client_id=ss_cid, feature_flags=1))
        )
        esp_d = register_device(
            hass, config_entry_id=esp_ce.entry_id, connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=title, manufacturer="Latter", model="desk-assistant-p4-86",
        )
        esp_devs[slug] = esp_d
        register_entity(hass, f"media_player.{slug}_music", platform="esphome", device_id=esp_d.id, config_entry=esp_ce)
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
        (
            "desk_assistant",
            "Desk Assistant",
            "e8:f6:0a:e0:f2:fe",
            "media_player.desk_assistant",
        ),
        (
            "garage_assistant",
            "Garage Assistant",
            "e8:f6:0a:e0:f2:da",
            "media_player.garage_assistant",
        ),
    ):
        sub = make_subentry(
            {
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
        hass.config_entries.async_add_subentry(entry, sub)
    await hass.async_block_till_done()

    onboarded_test = _apply_onboarding_profile_and_defaults(
        hass, esp_devs["test_assistant"], {"device_group": "auto"}, rebind_hardware=True
    )
    assert onboarded_test[CONF_MA_PLAYER_ENTITY] == "media_player.desk_assistant_2"

    sub_test = make_subentry(
        {k: v for k, v in onboarded_test.items() if k != CONF_MA_PLAYER_ENTITY},
        subentry_type=SUBENTRY_DEVICE,
        title="Test Assistant",
        unique_id="latter_30:ed:a0:e2:3d:92",
        subentry_id="sub_test_assistant",
    )
    hass.config_entries.async_add_subentry(entry, sub_test)
    await hass.async_block_till_done()
    async_heal_coordinator_ma_links(hass)

    c_test = entry.runtime_data.coordinators["sub_test_assistant"]
    assert c_test.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.desk_assistant_2"
    assert not any("sub_test_assistant" in k[1] for k in issue_reg.issues)

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_sendspin_uses_config_entry_id_and_caches_ma_misses(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prevent MainThread CPU storms: never touch deprecated DeviceEntry.config_entries, cache offline/None MA lookups, and coalesce active_media builds."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)

    def _forbid_deprecated_config_entries(_self: Any) -> set[str]:
        raise AssertionError(
            "Must not access deprecated DeviceEntry.config_entries"
        )

    esp_ce = add_mock_entry(
        hass, domain="esphome", title="Strict", entry_id="esp_strict_entry", data={}
    )
    esp_ce.runtime_data = SimpleNamespace(
        device_capabilities=SimpleNamespace(
            sendspin=SimpleNamespace(client_id="ss_strict_client_123", feature_flags=1)
        )
    )
    strict_dev = register_device(
        hass,
        config_entry_id=esp_ce.entry_id,
        identifiers={("esphome", "strict_no_legacy")},
        name="Strict",
        manufacturer="Latter",
    )
    with monkeypatch.context() as mp:
        mp.setattr(
            dr.DeviceEntry,
            "config_entries",
            property(_forbid_deprecated_config_entries),
            raising=False,
        )
        extract_fn = (
            vars(linking_mod).get("extract_esphome_sendspin_info")
            or linking_mod._extract_esphome_sendspin_info
        )
        cids, pending = extract_fn(hass, [strict_dev.id])
    assert cids == {"ss_strict_client_123"}
    assert pending is False

    # Unmatched / offline speaker must be cached so repeated calls do not rescan MA candidates
    clear_ma_counterpart_cache(hass)
    scan_calls = 0
    cand_attr = (
        "build_ma_candidates"
        if "build_ma_candidates" in vars(linking_mod)
        else "_build_ma_candidates"
    )
    orig_build_candidates = vars(linking_mod)[cand_attr]

    def _counting_build_candidates(h: Any) -> Any:
        nonlocal scan_calls
        scan_calls += 1
        return orig_build_candidates(h)

    monkeypatch.setattr(linking_mod, cand_attr, _counting_build_candidates)

    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) is None
    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) is None
    assert scan_calls == 1

    # build_active_media_payload must call resolve_ma_counterpart_entity once per build and coalesce back-to-back reads
    resolve_calls = 0
    orig_resolve = linking_mod.resolve_ma_counterpart_entity

    def _counting_resolve(h: Any, spk: str) -> Any:
        nonlocal resolve_calls
        resolve_calls += 1
        return orig_resolve(h, spk)

    monkeypatch.setattr(
        linking_mod, "resolve_ma_counterpart_entity", _counting_resolve
    )
    monkeypatch.setattr(
        state_payload_mod, "resolve_ma_counterpart_entity", _counting_resolve
    )
    coord.cached_media_payload = None
    _state1, _attrs1 = build_active_media_payload(coord)
    _state2, _attrs2 = build_active_media_payload(coord)
    assert resolve_calls == 1

    assert await hass.config_entries.async_unload(entry.entry_id) is True
