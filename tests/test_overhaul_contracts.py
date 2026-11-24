"""Regression and contract tests for the Latter v3.0.0 Pre-GA Architecture Overhaul."""

from __future__ import annotations

from datetime import timedelta
import json
from typing import Any
from unittest.mock import patch

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import (
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util
import pytest

from custom_components.latter.config_defaults import compute_hardware_defaults
from custom_components.latter.const import (
    CONF_BLE_AUTO_SWITCH,
    CONF_DEFAULT_AREA,
    CONF_DEVICE_GROUP,
    CONF_GLASS_STYLE,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SYNC_DEVICE_AREA,
    DOMAIN,
    MIN_FIRMWARE_CORE_REV,
    STUDIO_REV,
    WALLPAPER_MAX_DIM,
)
from custom_components.latter.diagnostics import async_get_config_entry_diagnostics
from custom_components.latter.groups.device_groups import (
    GROUP_DISPLAY_DEVICE_KEYS,
    coordinator_supports_pref,
)
from custom_components.latter.protocol_codec import (
    DomainPayloadPacker,
    V3Records,
    build_v3_records,
    encode_v3_records,
    pack_device_prefs_fields,
    sanitize_v3_subfield,
    unescape_v3_subfield,
)
from custom_components.latter.protocol_specs import (
    DEVICE_PREF_SPEC_MAP,
    DEVICE_PREF_SPECS,
    GLASS_STYLE_OPTIONS,
    WORLD_CLOCK_CATALOG,
    WORLD_CLOCK_ZONES,
)
from custom_components.latter.repairs_keys import (
    ISSUE_OUTDATED_FIRMWARE,
    outdated_firmware_issue_id,
)
from custom_components.latter.services.rpc_receiver import (
    MAX_RPC_PARTS,
    RECONNECT_DEFER_SECONDS,
    RpcReassembler,
)
from custom_components.latter.services.rpc_slots import is_coord_in_quiet_mode
from custom_components.latter.studio.commands import (
    StudioCommandError,
    async_execute_studio_command,
)
from custom_components.latter.studio.payload import (
    build_studio_state_payload,
    build_system_section,
)
from custom_components.latter.studio.settings_cleaners import (
    SettingsScopeError,
    clean_device_settings,
)
from tests.helpers import (
    LATTER_DIR,
    call_ws,
    find_entity_instance,
    flush_debouncers,
    get_service_calls,
    make_ws_connection,
)


def _encode_rpc_part(boot_hex: str, seq: int, part: int, total: int, body: str) -> str:
    return f"{boot_hex}:{seq}:{part}/{total}|{body}"


def test_studio_contract_split_and_pref_ui_merge() -> None:
    """Verify `studio_contract.json` owns Studio metadata/UI while `protocol_v3.json` stays lean."""
    proto = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
    contract = json.loads((LATTER_DIR / "studio_contract.json").read_text(encoding="utf-8"))

    assert STUDIO_REV == 51
    assert WALLPAPER_MAX_DIM == 1280
    assert contract["studio_contract"]["studio_rev"] == STUDIO_REV
    assert "studio_contract" not in proto
    assert "ha_services" not in proto
    assert "world_clock_zones" not in proto
    assert "world_clock_aliases" not in proto

    proto_keys = {spec["key"] for spec in proto["device_pref_specs"]}
    ui_keys = set(contract["device_pref_ui"])
    assert proto_keys == ui_keys
    assert len(DEVICE_PREF_SPECS) == 70
    for raw_spec in proto["device_pref_specs"]:
        for ui_only in ("label", "section", "group_tier", "unit"):
            assert ui_only not in raw_spec

    assert len(WORLD_CLOCK_ZONES) == len(contract["world_clock_zones"])
    assert len(WORLD_CLOCK_CATALOG) == len(contract["world_clock_zones"]) + len(
        contract["world_clock_aliases"]
    )
    assert GLASS_STYLE_OPTIONS == ("Auto", "Clear", "Dark")


def test_v3_subfield_escaping_symmetry_and_no_double_escape() -> None:
    """Verify `sanitize_v3_subfield` escapes `\\`, `|`, `;`, strips control chars, and never double-escapes `V3Records`."""
    raw = "A\\B|C;D\x1eE\x1fF\nG"
    escaped = sanitize_v3_subfield(raw)
    assert escaped == "A\\\\B\\pC\\sD E F G"
    assert unescape_v3_subfield(escaped) == "A\\B|C;D E F G"

    # Control characters \x1e / \x1f never appear in output
    assert "\x1e" not in escaped
    assert "\x1f" not in escaped
    assert "|" not in escaped
    assert ";" not in escaped

    # Logical length cap respects unescaped logical characters and never ends on dangling backslash
    capped = sanitize_v3_subfield("a|b\\c;d", max_len=4)
    assert unescape_v3_subfield(capped) == "a|b\\"
    assert capped == "a\\pb\\\\"

    # Pre-sanitized V3Records (including slices!) must NOT be double-escaped when encoded or packed
    recs = build_v3_records(
        [
            ("k1", "Alpha | Beta; C\\D"),
            ("k2", "Second | Entry"),
            ("k3", "Third ; Entry"),
        ],
        (16, 48),
        5,
    )
    assert isinstance(recs, V3Records)
    encoded_full = encode_v3_records(recs)
    assert encoded_full == "k1|Alpha \\p Beta\\s C\\\\D\x1ek2|Second \\p Entry\x1ek3|Third \\s Entry"
    assert "\\\\p" not in encoded_full
    assert "\\\\s" not in encoded_full

    sliced = recs[0:2]
    assert isinstance(sliced, V3Records)
    encoded_slice = encode_v3_records(sliced)
    assert encoded_slice == "k1|Alpha \\p Beta\\s C\\\\D\x1ek2|Second \\p Entry"

    # Raw (unsanitized) tuples passed directly to encode_v3_records ARE escaped once
    raw_encoded = encode_v3_records([("id1", "X|Y;Z\\W")])
    assert raw_encoded == "id1|X\\pY\\sZ\\\\W"

    # Packing through DomainPayloadPacker preserves single escaping
    _rev, packed = DomainPayloadPacker(epoch=3).pack("shortcuts", sliced, 1, 1)
    assert packed.split("\x1f")[3] == encoded_slice


def test_rpc_reassembler_seed_silent_mid_multipart_and_32_part_limit() -> None:
    """Verify `MAX_RPC_PARTS == 32` and `seed_silent()` on `part < total` stages instead of dropping."""
    assert MAX_RPC_PARTS == 32

    # 1) seed_silent on part 1/3 stages in-flight so parts 2/3 & 3/3 complete cleanly
    reasm = RpcReassembler()
    payload = json.dumps({"s": "device_hello", "d": {"boot_id": "b1", "manifest": "{}"}})
    chunk = max(1, (len(payload) + 2) // 3)
    parts = [payload[i : i + chunk] for i in range(0, len(payload), chunk)]
    assert len(parts) == 3

    reasm.seed_silent(_encode_rpc_part("b1", 7, 1, 3, parts[0]))
    assert reasm.feed(_encode_rpc_part("b1", 7, 2, 3, parts[1])) is None
    res = reasm.feed(_encode_rpc_part("b1", 7, 3, 3, parts[2]))
    assert res == ("device_hello", {"boot_id": "b1", "manifest": "{}"})

    # 2) seed_silent on final part (part == total) marks completed and suppresses replay
    reasm.seed_silent(_encode_rpc_part("b1", 8, 2, 2, '{"s":"ping","d":{}}'))
    assert reasm.feed(_encode_rpc_part("b1", 8, 2, 2, '{"s":"ping","d":{}}')) is None

    # 3) 24-part RPC (> old 16 limit, <= 32) reassembles cleanly
    big_payload = json.dumps({"s": "device_telemetry", "d": {"pad": "x" * 240}})
    n_parts = 24
    step = (len(big_payload) + n_parts - 1) // n_parts
    chunks24 = [big_payload[i * step : (i + 1) * step] for i in range(n_parts)]
    out: tuple[str, dict[str, object]] | None = None
    for idx, piece in enumerate(chunks24, 1):
        out = reasm.feed(_encode_rpc_part("b2", 1, idx, n_parts, piece))
    assert out == ("device_telemetry", {"pad": "x" * 240})

    # 4) 33-part RPC (> MAX_RPC_PARTS) is rejected
    assert reasm.feed(_encode_rpc_part("b2", 2, 1, 33, "{")) is None


async def test_outdated_firmware_repair_non_blocking_and_auto_clearing(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify outdated `core_rev` raises non-fixable warning Repair, keeps syncing, and auto-clears on upgrade/unload."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    iss_reg = ir.async_get(hass)
    issue_id = outdated_firmware_issue_id(coord.subentry_id)

    # Starts up-to-date
    assert coord.core_rev == str(MIN_FIRMWARE_CORE_REV)
    assert coord.firmware_outdated is False
    assert iss_reg.async_get_issue(DOMAIN, issue_id) is None

    # Legacy `sdk`-only manifest (no `core_rev`) is NOT read as `core_rev` (Zero-Legacy)
    coord._runtime.hello_manifest = {"v": 2, "w": 466, "h": 466, "sdk": 2026010101}
    assert coord.core_rev == ""
    assert coord.firmware_outdated is False

    # Outdated `core_rev` via `device_hello` raises non-fixable warning Repair AND still syncs domains
    old_rev = MIN_FIRMWARE_CORE_REV - 1
    calls = get_service_calls(hass)
    calls.clear()
    await coord.async_handle_device_hello(
        boot_id="boot_old",
        manifest_raw=json.dumps(
            {
                "v": 2,
                "contract": 3,
                "w": 466,
                "h": 466,
                "shape": "circle",
                "display": 1,
                "audio": 1,
                "mic": 1,
                "spk": 1,
                "core_rev": old_rev,
            }
        ),
    )
    await flush_debouncers(hass)

    assert coord.core_rev == str(old_rev)
    assert coord.firmware_outdated is True
    issue = iss_reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == ISSUE_OUTDATED_FIRMWARE
    assert issue.translation_placeholders == {
        "device": coord.device_title,
        "core_rev": str(old_rev),
        "min_core_rev": str(MIN_FIRMWARE_CORE_REV),
    }

    # Best-effort domain sync STILL ran despite outdated firmware
    push_calls = [c for c in calls if c.service.endswith("_latter_push_v3")]
    assert len(push_calls) >= 1

    # Studio payload & diagnostics expose `min_firmware_core_rev`, `core_rev`, `firmware_outdated`, and issue row
    sys_section = build_system_section(hass, coord.subentry_id)
    assert sys_section["system_info"]["min_firmware_core_rev"] == MIN_FIRMWARE_CORE_REV
    assert "min_firmware_sdk_rev" not in sys_section["system_info"]
    assert any(
        iss["kind"] == ISSUE_OUTDATED_FIRMWARE
        and f"{old_rev} < {MIN_FIRMWARE_CORE_REV}" in iss["detail"]
        for iss in sys_section["issues"]
    )
    studio_payload = build_studio_state_payload(hass, coord)
    dev_live = studio_payload["live"]
    assert dev_live["core_rev"] == str(old_rev)
    assert dev_live["firmware_outdated"] is True
    assert "sdk_rev" not in dev_live
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["devices"][coord.subentry_id]["runtime"]["core_rev"] == str(old_rev)
    assert diag["devices"][coord.subentry_id]["runtime"]["firmware_outdated"] is True

    # Upgrade to >= MIN_FIRMWARE_CORE_REV auto-clears the Repair
    await coord.async_handle_device_hello(
        boot_id="boot_upgraded",
        manifest_raw=json.dumps(
            {
                "v": 2,
                "contract": 3,
                "w": 466,
                "h": 466,
                "shape": "circle",
                "display": 1,
                "audio": 1,
                "mic": 1,
                "spk": 1,
                "core_rev": MIN_FIRMWARE_CORE_REV,
            }
        ),
    )
    assert coord.firmware_outdated is False
    assert iss_reg.async_get_issue(DOMAIN, issue_id) is None

    # Re-trigger outdated issue, then verify unload auto-deletes it
    await coord.async_handle_device_hello(
        boot_id="boot_downgraded",
        manifest_raw=json.dumps({"v": 2, "w": 466, "h": 466, "display": 1, "core_rev": old_rev}),
    )
    assert iss_reg.async_get_issue(DOMAIN, issue_id) is not None
    assert await hass.config_entries.async_unload(entry.entry_id) is True
    assert iss_reg.async_get_issue(DOMAIN, issue_id) is None


async def test_reconnect_storm_deduplicated_across_rpc_receiver_and_device_hello(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify a single ESPHome reconnect does NOT rotate PIN key or republish all 7 domains twice."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    outbox_eid = f"sensor.{coord.device_slug}_system_rpc_outbox"
    compact_manifest = json.dumps(
        {
            "v": 2,
            "w": 466,
            "h": 466,
            "shape": "circle",
            "display": 1,
            "stationary": 0,
            "battery": 1,
            "core_rev": MIN_FIRMWARE_CORE_REV,
        },
        separators=(",", ":"),
    )
    calls = get_service_calls(hass)

    # Case A: unavailable -> unknown (transport reconnect) followed immediately by device_hello
    with patch("custom_components.latter.coordinator.core.async_call_later", return_value=lambda: None):
        hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
        await hass.async_block_till_done()
        calls.clear()

        hass.states.async_set(outbox_eid, STATE_UNKNOWN)
        await hass.async_block_till_done()
        await flush_debouncers(hass)

        hello_frame = _encode_rpc_part(
            "deadbeef01",
            1,
            1,
            1,
            json.dumps(
                {
                    "s": "device_hello",
                    "d": {"boot_id": "deadbeef01", "manifest": compact_manifest, "prefs_seq": 0},
                },
                separators=(",", ":"),
            ),
        )
        assert len(hello_frame) <= 255
        hass.states.async_set(outbox_eid, hello_frame)
        await hass.async_block_till_done()
        await flush_debouncers(hass)

    pin_key_calls = [
        c
        for c in calls
        if c.service.endswith("_latter_device_command")
        and str(c.data.get("command") or "").startswith("set_pin_key:")
    ]
    assert len(pin_key_calls) == 1
    pushed_domains = [
        str(c.data.get("domain"))
        for c in calls
        if c.service.endswith("_latter_push_v3")
    ]
    # Must NOT republish the 6 non-prefs display domains twice!
    for dom in ("active_media", "weather_forecast", "area_context", "calendar_agenda", "remote_config", "shortcuts"):
        assert pushed_domains.count(dom) == 1, f"Domain {dom} pushed {pushed_domains.count(dom)} times"

    # Case B: unavailable -> device_hello in a single state transition
    with patch("custom_components.latter.coordinator.core.async_call_later", return_value=lambda: None):
        hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
        await hass.async_block_till_done()
        calls.clear()

        hello_frame_b = _encode_rpc_part(
            "deadbeef02",
            1,
            1,
            1,
            json.dumps(
                {
                    "s": "device_hello",
                    "d": {"boot_id": "deadbeef02", "manifest": compact_manifest, "prefs_seq": 0},
                },
                separators=(",", ":"),
            ),
        )
        assert len(hello_frame_b) <= 255
        hass.states.async_set(outbox_eid, hello_frame_b)
        await hass.async_block_till_done()
        await flush_debouncers(hass)

    pin_key_calls_b = [
        c
        for c in calls
        if c.service.endswith("_latter_device_command")
        and str(c.data.get("command") or "").startswith("set_pin_key:")
    ]
    assert len(pin_key_calls_b) == 1
    pushed_domains_b = [
        str(c.data.get("domain"))
        for c in calls
        if c.service.endswith("_latter_push_v3")
    ]
    for dom in ("active_media", "weather_forecast", "area_context", "calendar_agenda", "remote_config", "shortcuts"):
        assert pushed_domains_b.count(dom) == 1, f"Domain {dom} pushed {pushed_domains_b.count(dom)} times"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_glass_style_end_to_end_pref_select_wire_and_studio(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `glass_style` works across config, select entity, wire index 72, cleaners, groups, and Studio WS."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    slug = coord.device_slug

    assert CONF_GLASS_STYLE == "glass_style"
    assert CONF_GLASS_STYLE in GROUP_DISPLAY_DEVICE_KEYS
    assert coord.get_device_pref("glass_style") == "Auto"

    # Settings cleaner accepts valid options and rejects invalid values
    assert clean_device_settings({"glass_style": "Clear"}) == {"glass_style": "Clear"}
    assert clean_device_settings({"glass_style": "Dark"}) == {"glass_style": "Dark"}
    with pytest.raises(SettingsScopeError):
        clean_device_settings({"glass_style": "Frosted"})

    # HA Select entity works and updates packed wire field 72 (body[69])
    glass_sel = find_entity_instance(hass, "select", f"select.{slug}_glass_style")
    assert glass_sel.current_option == "Auto"
    assert glass_sel.options == ["Auto", "Clear", "Dark"]
    await glass_sel.async_select_option("Dark")
    await hass.async_block_till_done()
    assert coord.get_device_pref("glass_style") == "Dark"
    assert hass.states.get(f"select.{slug}_glass_style").state == "Dark"

    packed_fields = pack_device_prefs_fields(
        max(1, coord.prefs_seq),
        coord.device_data,
        native_ble_tracking=coord.native_ble_tracking_enabled,
        custom_color_hex=coord.device_custom_color,
        is_round_display=coord.is_round_display,
        supports_hw_jpeg=coord.supports_hw_jpeg,
        do_not_disturb=coord.do_not_disturb,
    )
    assert len(packed_fields) == 75  # indices 3..77 inclusive
    assert packed_fields[69] == "Dark"
    assert packed_fields[70:75] == (True, True, True, "Current Weather", True)
    _seq, prefs_payload = coord.get_device_prefs_payload()
    wire_parts = str(prefs_payload["payload"]).split("\x1f")
    assert len(wire_parts) == 78  # 3 header fields + 75 pref fields
    assert wire_parts[72] == "Dark"
    assert wire_parts[73:78] == ["1", "1", "1", "Current Weather", "1"]

    # Studio payload and WS save_device_config / apply_batch_control
    conn = make_ws_connection(hass)
    await call_ws(
        hass,
        conn,
        1,
        "latter/device/command",
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={"config": {"glass_style": "Clear"}},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert coord.get_device_pref("glass_style") == "Clear"
    payload = build_studio_state_payload(hass, coord)
    assert payload["config"]["glass_style"] == "Clear"

    await call_ws(
        hass,
        conn,
        2,
        "latter/system/command",
        command="apply_batch_device_setting",
        payload={"target": "all", "config": {"glass_style": "Dark"}},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert coord.get_device_pref("glass_style") == "Dark"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_headless_display_zero_defaults_runtime_restore_and_capability_pruning(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify headless `display=0`, audio-less pruning, `display_shape='none'`, display push skip, and `do_not_disturb`."""
    # 1) compute_hardware_defaults never classifies a headless stationary node as wall_panels
    headless_defaults = compute_hardware_defaults(
        {
            "display": 0,
            "w": 0,
            "h": 0,
            "stationary": 1,
            "shape": "none",
            "core_rev": MIN_FIRMWARE_CORE_REV,
        },
        esp_area_id="living_room",
        has_native_slots=True,
        has_ble_beacon=True,
    )
    assert headless_defaults[CONF_DEVICE_GROUP] == "custom"
    assert headless_defaults[CONF_NATIVE_BLE_TRACKING] is False
    assert headless_defaults[CONF_BLE_AUTO_SWITCH] is False
    assert headless_defaults[CONF_SYNC_DEVICE_AREA] is False

    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    slug = coord.device_slug
    ent_reg = er.async_get(hass)

    # All capability-gated entities exist initially on a full-featured display+audio device
    display_eids = (
        f"sensor.{slug}_timer_remaining",
        f"binary_sensor.{slug}_timer_active",
        f"binary_sensor.{slug}_alarm_ringing",
        f"light.{slug}_screen",
        f"button.{slug}_dismiss_alert",
        f"select.{slug}_glass_style",
        f"switch.{slug}_bedtime_mode",
        f"switch.{slug}_screensaver",
    )
    mic_eid = f"select.{slug}_wake_word_mode"
    spk_eids = (f"button.{slug}_find_my_device", f"number.{slug}_alert_volume")
    dnd_eid = f"switch.{slug}_do_not_disturb"

    for eid in (*display_eids, mic_eid, *spk_eids, dnd_eid):
        assert ent_reg.async_get(eid) is not None, f"Expected initial entity {eid}"

    # 2) Audio-less display device (`audio=0, mic=0, spk=0`) prunes mic & speaker entities but keeps display + DND
    await coord.async_handle_device_hello(
        boot_id="boot_no_audio",
        manifest_raw=json.dumps(
            {
                "v": 2,
                "contract": 3,
                "w": 466,
                "h": 466,
                "shape": "circle",
                "display": 1,
                "audio": 0,
                "mic": 0,
                "spk": 0,
                "core_rev": MIN_FIRMWARE_CORE_REV,
            }
        ),
    )
    assert coord.has_display is True
    assert coord.has_mic is False
    assert coord.has_speaker is False
    assert ent_reg.async_get(mic_eid) is None
    for eid in spk_eids:
        assert ent_reg.async_get(eid) is None
    for eid in (*display_eids, dnd_eid):
        assert ent_reg.async_get(eid) is not None
    assert coordinator_supports_pref(coord, DEVICE_PREF_SPEC_MAP["do_not_disturb"]) is True

    # 3) _apply_stored_runtime preserves display=0 manifest even when w & h are omitted; display_shape is "none"
    coord._runtime.hello_manifest = {}
    coord._apply_stored_runtime(
        {
            "hello_manifest": {
                "display": 0,
                "shape": "none",
                "audio": 1,
                "mic": 0,
                "spk": 1,
                "core_rev": MIN_FIRMWARE_CORE_REV,
            }
        }
    )
    assert coord.has_display is False
    assert coord.display_shape == "none"
    assert coord.has_speaker is True
    assert coord.has_mic is False

    # Headless speaker device supports `do_not_disturb` (`display_or_audio`) and respects quiet mode
    assert coordinator_supports_pref(coord, DEVICE_PREF_SPEC_MAP["do_not_disturb"]) is True
    await coord.async_update_device_prefs({"do_not_disturb": True})
    assert is_coord_in_quiet_mode(coord) is True
    calls = get_service_calls(hass)
    calls.clear()
    await hass.services.async_call(
        DOMAIN,
        "notify",
        {"target_device": slug, "title": "Quiet Check", "message": "Suppressed", "priority": "normal"},
        blocking=True,
    )
    assert not any(c.service.endswith("_latter_show_notification") for c in calls)

    # Headless speaker device skips display-only domain pushes and ONLY pushes `device_prefs`
    calls = get_service_calls(hass)
    calls.clear()
    coord.force_republish_all_domains()
    await flush_debouncers(hass)
    pushed_headless = {
        str(c.data.get("domain"))
        for c in calls
        if c.service.endswith("_latter_push_v3")
    }
    assert pushed_headless == {"device_prefs"}

    # 4) Reconciling headless speaker device prunes all 8 display entities while keeping DND
    coord.reconcile_capability_entities()
    for eid in display_eids:
        assert ent_reg.async_get(eid) is None, f"Stale display entity {eid} not pruned"
    assert ent_reg.async_get(dnd_eid) is not None

    # 5) Headless silent device (`display=0, audio=0`) prunes DND too and does NOT support DND pref
    await coord.async_handle_device_hello(
        boot_id="boot_silent_headless",
        manifest_raw=json.dumps(
            {
                "v": 2,
                "contract": 3,
                "display": 0,
                "shape": "none",
                "audio": 0,
                "core_rev": MIN_FIRMWARE_CORE_REV,
            }
        ),
    )
    assert coord.has_display is False
    assert coord.has_speaker is False
    assert coord.display_shape == "none"
    assert ent_reg.async_get(dnd_eid) is None
    assert coordinator_supports_pref(coord, DEVICE_PREF_SPEC_MAP["do_not_disturb"]) is False

    assert await hass.config_entries.async_unload(entry.entry_id) is True


def test_compute_hardware_defaults_stationary_and_screenless_edges() -> None:
    """Verify area-less stationary wall panels and screenless stationary nodes never default to roaming/VFM."""
    # 1) Stationary wall panel onboarded before HA Area assignment stays static in `wall_panels`
    panel_no_area = compute_hardware_defaults(
        {
            "display": 1,
            "w": 1024,
            "h": 600,
            "shape": "square",
            "stationary": 1,
            "battery": 0,
            "core_rev": MIN_FIRMWARE_CORE_REV,
        },
        esp_area_id="",
        has_native_slots=True,
        has_ble_beacon=True,
    )
    assert panel_no_area[CONF_DEVICE_GROUP] == "wall_panels"
    assert panel_no_area[CONF_NATIVE_BLE_TRACKING] is False
    assert panel_no_area[CONF_BLE_AUTO_SWITCH] is False
    assert panel_no_area[CONF_SYNC_DEVICE_AREA] is False
    assert panel_no_area[CONF_DEFAULT_AREA] == ""

    # 2) Screenless stationary node (`display=0, stationary=1`) never enables VFM `sync_device_area`
    screenless_stationary = compute_hardware_defaults(
        {
            "display": 0,
            "w": 0,
            "h": 0,
            "shape": "none",
            "stationary": 1,
            "core_rev": MIN_FIRMWARE_CORE_REV,
        },
        esp_area_id="office",
        has_native_slots=False,
        has_ble_beacon=True,
    )
    assert screenless_stationary[CONF_DEVICE_GROUP] == "custom"
    assert screenless_stationary[CONF_NATIVE_BLE_TRACKING] is False
    assert screenless_stationary[CONF_BLE_AUTO_SWITCH] is False
    assert screenless_stationary[CONF_SYNC_DEVICE_AREA] is False
    assert screenless_stationary[CONF_DEFAULT_AREA] == "office"

    # 3) Screenless roaming node (`display=0, stationary=0`) with BLE beacon still tracks & syncs Area
    screenless_roaming = compute_hardware_defaults(
        {
            "display": 0,
            "w": 0,
            "h": 0,
            "shape": "none",
            "stationary": 0,
            "core_rev": MIN_FIRMWARE_CORE_REV,
        },
        esp_area_id="",
        has_native_slots=False,
        has_ble_beacon=True,
    )
    assert screenless_roaming[CONF_DEVICE_GROUP] == "custom"
    assert screenless_roaming[CONF_NATIVE_BLE_TRACKING] is True
    assert screenless_roaming[CONF_BLE_AUTO_SWITCH] is True
    assert screenless_roaming[CONF_SYNC_DEVICE_AREA] is True


async def test_reconnect_deferral_multipart_hello_fallback_and_unload_cleanup(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify deferred reconnect prevents stale pref overwrite on multipart `device_hello`, falls back on silence, and cancels cleanly."""
    from pytest_homeassistant.common import async_fire_time_changed

    assert RECONNECT_DEFER_SECONDS == 0.5
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    receiver = coord.rpc_receiver
    assert receiver is not None
    outbox_eid = f"sensor.{coord.device_slug}_system_rpc_outbox"
    calls = get_service_calls(hass)

    # Seed baseline HA pref state (`night_brightness=35` at `prefs_seq=5`)
    await coord.async_update_device_prefs({"night_brightness": 35})
    coord.prefs_seq = 5
    coord.prefs_key_seq.clear()
    await flush_debouncers(hass)

    # Build realistic 4-part chunked `device_hello` carrying an offline edit (`night_brightness=55`, `prefs_seq=6`)
    full_manifest = json.dumps(
        {
            "v": 2,
            "contract": 3,
            "w": 1024,
            "h": 600,
            "shape": "square",
            "display": 1,
            "stationary": 0,
            "battery": 1,
            "audio": 1,
            "mic": 1,
            "spk": 1,
            "core_rev": MIN_FIRMWARE_CORE_REV,
            "video": {"hw_jpeg": 1, "max_w": 768, "max_h": 592, "max_fps": 10, "grid_fps": 5},
        },
        separators=(",", ":"),
    )
    hello_env = json.dumps(
        {
            "s": "device_hello",
            "d": {
                "boot_id": "cafe4401",
                "manifest": full_manifest,
                "prefs_seq": 6,
                "dirty_prefs": "night_brightness=55",
            },
        },
        separators=(",", ":"),
    )
    step = (len(hello_env) + 3) // 4
    chunks = [hello_env[i * step : (i + 1) * step] for i in range(4)]
    assert len(chunks) == 4 and all(chunks)

    # 1) `unavailable -> unknown` arms timer without pushing stale `device_prefs`; multipart chunks postpone timer
    with patch("custom_components.latter.coordinator.core.async_call_later", return_value=lambda: None):
        hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
        await hass.async_block_till_done()
        calls.clear()

        hass.states.async_set(outbox_eid, STATE_UNKNOWN)
        await hass.async_block_till_done()
        await flush_debouncers(hass)
        prev_timer = receiver._unsub_reconnect_timer
        assert prev_timer is not None
        assert not [c for c in calls if c.service.endswith("_latter_push_v3")]

        for idx in range(3):
            hass.states.async_set(
                outbox_eid, _encode_rpc_part("cafe4401", 1, idx + 1, 4, chunks[idx])
            )
            await hass.async_block_till_done()
            # Each incoming multipart slice reschedules (postpones) the reconnect fallback timer
            cur_timer = receiver._unsub_reconnect_timer
            assert cur_timer is not None
            assert cur_timer is not prev_timer
            prev_timer = cur_timer
            assert not [c for c in calls if c.service.endswith("_latter_push_v3")]

        # Final 4/4 chunk completes `device_hello`, cancels timer, merges dirty_prefs, and pushes all domains ONCE
        hass.states.async_set(outbox_eid, _encode_rpc_part("cafe4401", 1, 4, 4, chunks[3]))
        await hass.async_block_till_done()
        await flush_debouncers(hass)
        assert receiver._unsub_reconnect_timer is None
        assert coord.get_device_pref("night_brightness") == 55
        assert coord.prefs_seq == 7

        # Advancing clock well past 0.5s must not fire any duplicate reconnect push
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
        await hass.async_block_till_done()
        await flush_debouncers(hass)

    pushed_after_hello = [
        c for c in calls if c.service.endswith("_latter_push_v3")
    ]
    prefs_pushes = [c for c in pushed_after_hello if c.data.get("domain") == "device_prefs"]
    assert len(prefs_pushes) == 1
    prefs_parts = str(prefs_pushes[0].data.get("payload") or "").split("\x1f")
    assert prefs_parts[3] == "7"
    assert prefs_parts[15] == "55"
    pin_pushes = [
        c
        for c in calls
        if c.service.endswith("_latter_device_command")
        and str(c.data.get("command") or "").startswith("set_pin_key:")
    ]
    assert len(pin_pushes) == 1

    # 2) Fallback republish when NO `device_hello` arrives after `unavailable -> unknown`
    with patch("custom_components.latter.coordinator.core.async_call_later", return_value=lambda: None):
        hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
        await hass.async_block_till_done()
        calls.clear()

        hass.states.async_set(outbox_eid, STATE_UNKNOWN)
        await hass.async_block_till_done()
        await flush_debouncers(hass)
        assert receiver._unsub_reconnect_timer is not None
        assert not [c for c in calls if c.service.endswith("_latter_push_v3")]

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done()
        await flush_debouncers(hass)
        assert receiver._unsub_reconnect_timer is None
        fallback_domains = {
            str(c.data.get("domain"))
            for c in calls
            if c.service.endswith("_latter_push_v3")
        }
        assert {"active_media", "weather_forecast", "area_context", "device_prefs"} <= fallback_domains

    # 3) Re-disconnecting cancels pending timer; unloading while timer is armed cancels cleanly
    hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_set(outbox_eid, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert receiver._unsub_reconnect_timer is not None
    hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert receiver._unsub_reconnect_timer is None

    hass.states.async_set(outbox_eid, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert receiver._unsub_reconnect_timer is not None
    assert await hass.config_entries.async_unload(entry.entry_id) is True
    assert receiver._unsub_reconnect_timer is None


async def test_async_execute_studio_command_public_seam(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify transport-agnostic `async_execute_studio_command()` supports System & Device scopes and error contracts."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)

    # 1) System command (auto-inferred scope)
    res_sys = await async_execute_studio_command(hass, "clear_internal_logs", {})
    assert isinstance(res_sys, dict)

    # 2) Device command resolved via `subentry_id`
    await async_execute_studio_command(
        hass,
        "save_device_config",
        {"config": {"glass_style": "Clear"}},
        subentry_id=coord.subentry_id,
    )
    assert coord.get_device_pref("glass_style") == "Clear"

    # 3) Device command with explicit `coordinator` and `scope`
    await async_execute_studio_command(
        hass,
        "save_device_config",
        {"config": {"glass_style": "Dark"}},
        scope="device",
        coordinator=coord,
    )
    assert coord.get_device_pref("glass_style") == "Dark"

    # 4) Error contracts: unknown command, wrong explicit scope, missing device, invalid schema
    with pytest.raises(StudioCommandError) as exc_unk:
        await async_execute_studio_command(hass, "no_such_studio_cmd")
    assert exc_unk.value.code == "unknown_command"

    with pytest.raises(StudioCommandError) as exc_scope:
        await async_execute_studio_command(
            hass, "clear_internal_logs", scope="device", subentry_id=coord.subentry_id
        )
    assert exc_scope.value.code == "wrong_scope"

    with pytest.raises(StudioCommandError) as exc_missing:
        await async_execute_studio_command(
            hass, "save_device_config", {"config": {}}, subentry_id="missing_sub"
        )
    assert exc_missing.value.code == "not_found"

    with pytest.raises(StudioCommandError) as exc_fmt:
        await async_execute_studio_command(
            hass,
            "save_device_config",
            {"config": "not_a_dict"},
            subentry_id=coord.subentry_id,
        )
    assert exc_fmt.value.code == "invalid_format"

    assert await hass.config_entries.async_unload(entry.entry_id) is True
