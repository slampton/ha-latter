"""Standalone tests for ha-latter: Protocol v3 contract, Voice Follows Me, BLE Area scoring, and URL signing.

They run without Home Assistant installed. Each production module under test (payloads.py,
area_follow.py, traits.py, ble_math.py, resource_signing.py, ...) is standard-library only and loaded by file path.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"
HA_PROTO_JSON = LATTER_DIR / "protocol_v3.json"
CORE_PROTO_JSON = REPO_ROOT.parent / "esphome-latter-core" / "protocol" / "latter_v3.json"


def _load_ha_free_module(name: str) -> ModuleType:
    """Load a Home Assistant-free production module from custom_components/latter by file path."""
    spec = importlib.util.spec_from_file_location(
        f"latter_{name.replace('/', '_')}", LATTER_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PAYLOADS_MOD = _load_ha_free_module("payloads")
DomainPayloadPacker = _PAYLOADS_MOD.DomainPayloadPacker
sanitize_v3_field = _PAYLOADS_MOD.sanitize_v3_field

area_follow = _load_ha_free_module("area_follow")
AreaFollowDwell = area_follow.AreaFollowDwell
FollowAction = area_follow.FollowAction
traits = _load_ha_free_module("traits")
manifest_is_roaming = traits.manifest_is_roaming

ble_math = _load_ha_free_module("ble_math")
resource_signing = _load_ha_free_module("resource_signing")
issue_ids = _load_ha_free_module("issue_ids")
health = _load_ha_free_module("health")
ma_link = _load_ha_free_module("ma_link")
studio_scope = _load_ha_free_module("studio/scope")
STUDIO_JS = LATTER_DIR / "frontend" / "latter-studio.js"


class TestProtocolV3Contract(unittest.TestCase):
    """Verify Protocol v3 schema parity, field counts, and packing/hashing invariants."""

    def setUp(self) -> None:
        self.schema = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))

    def test_schema_files_byte_identical(self) -> None:
        """Both repos must carry a byte-identical Protocol v3 JSON specification."""
        self.assertTrue(HA_PROTO_JSON.is_file(), f"Missing {HA_PROTO_JSON}")
        if CORE_PROTO_JSON.is_file():
            self.assertEqual(
                HA_PROTO_JSON.read_bytes(),
                CORE_PROTO_JSON.read_bytes(),
                "ha-latter/custom_components/latter/protocol_v3.json and esphome-latter-core/protocol/latter_v3.json differ",
            )

    def test_domain_field_counts_and_contiguous_indices(self) -> None:
        """Every v3 domain must have contiguous 3..COUNT-1 indices matching expected counts."""
        expected_counts = {
            "area_context": 35,
            "active_media": 17,
            "remote_config": 3,
            "weather_forecast": 8,
            "calendar_agenda": 3,
        }
        domains = self.schema.get("domains", {})
        self.assertEqual(set(domains.keys()), set(expected_counts.keys()))
        for dom_name, expected_len in expected_counts.items():
            fields = domains[dom_name]["fields"]
            self.assertEqual(
                len(fields),
                expected_len,
                f"Domain {dom_name} expected {expected_len} fields, got {len(fields)}",
            )
            indices = [f["index"] for f in fields]
            self.assertEqual(
                indices,
                list(range(3, 3 + expected_len)),
                f"Domain {dom_name} has non-contiguous indices: {indices}",
            )

    def test_content_hashed_revision_and_delimiters(self) -> None:
        """Unchanged domain content must not bump rev; delimiter characters must be sanitized."""
        packer = DomainPayloadPacker(epoch=1761900000)
        self.assertEqual(sanitize_v3_field("a\x1fb\nc"), "a b c")
        for dom_name, dom_spec in self.schema["domains"].items():
            field_count = len(dom_spec["fields"])
            sample_fields = [f"val_{i}\x1finjected\nline" for i in range(field_count)]
            rev1, packed1 = packer.pack(dom_name, *sample_fields)
            self.assertEqual(rev1, 1)
            tokens = packed1.split("\x1f")
            self.assertEqual(
                len(tokens),
                3 + field_count,
                f"Domain {dom_name} packed token count mismatch",
            )
            self.assertEqual(tokens[0], "v3")
            self.assertEqual(tokens[1], "1761900000")
            self.assertEqual(tokens[2], "1")

            # Identical content -> rev stays 1
            rev2, packed2 = packer.pack(dom_name, *sample_fields)
            self.assertEqual(rev2, 1)
            self.assertEqual(packed1, packed2)

            # Mutated field -> rev increments to 2
            mutated = list(sample_fields)
            mutated[0] = "changed_value"
            rev3, packed3 = packer.pack(dom_name, *mutated)
            self.assertEqual(rev3, 2)
            self.assertNotEqual(packed2, packed3)

        # Reconnect / device_hello -> increments rev across all domains
        packer.force_republish_all_domains()
        rev_after_reset, _ = packer.pack(
            "remote_config", "0", "2", "Apple TV\x1eremote.apple_tv"
        )
        self.assertEqual(rev_after_reset, 3)

    def test_hardware_manifest_state_json_within_ha_255_char_limit(self) -> None:
        """The System: Hardware Manifest entity state string must never exceed HA's 255-char MAX_STATE_LENGTH."""
        longest_state_json = (
            '{"v":2,"contract":3,"board":"waveshare_p4_86_panel",'
            '"w":720,"h":720,"shape":"square",'
            '"display":1,"touch":1,"audio":1,"mic":1,"spk":1,'
            '"imu":0,"battery":0,"stationary":1,"wearable":0,'
            '"ips":1,"chip":"ESP32-P4","psram_mb":32,"minor":5}'
        )
        self.assertLessEqual(
            len(longest_state_json),
            255,
            f"Hardware manifest state JSON is {len(longest_state_json)} chars (> 255 limit)",
        )
        parsed = json.loads(longest_state_json)
        self.assertEqual(parsed["v"], 2)
        self.assertEqual(parsed["minor"], 5)

    def test_show_notification_includes_alert_id(self) -> None:
        """show_notification device action must include alert_id for deduplication."""
        notif_vars = (
            self.schema.get("device_actions", {})
            .get("show_notification", {})
            .get("variables", {})
        )
        self.assertEqual(notif_vars.get("alert_id"), "int")


class _FollowHarness:
    """Drives the production `AreaFollowDwell` the way `LatterAreaFollowController` does.

    Only the Home Assistant parts are faked: the timer is a stored deadline, and the Device
    Registry write is appended to `registry_writes`. Every decision (roaming trait, dwell,
    pending, ignore) comes from `area_follow.py`.
    """

    def __init__(self, manifest: dict[str, Any], esphome_device_id: str, dwell_s: float = 10.0) -> None:
        self.manifest = manifest
        self.esphome_device_id = esphome_device_id
        self.dwell_s = dwell_s
        self.sync_device_area = True
        self.device_area_id: str | None = "kitchen"
        self.dwell = AreaFollowDwell()
        self.timer: tuple[float, str] | None = None
        self.registry_writes: list[tuple[str, str]] = []

    @property
    def is_roaming_device(self) -> bool:
        return manifest_is_roaming(self.manifest)

    def _allowed(self) -> bool:
        return self.is_roaming_device and self.sync_device_area

    def _write(self, area_id: str) -> None:
        if self.device_area_id != area_id:
            self.device_area_id = area_id
            self.registry_writes.append((self.esphome_device_id, area_id))

    def cancel(self) -> None:
        self.timer = None
        self.dwell.cancel()

    def set_area(self, area_id: str, *, ble_driven: bool, now: float) -> None:
        if not self._allowed():
            self.cancel()
            return
        action = self.dwell.request(area_id, ble_driven=ble_driven, dwell_s=self.dwell_s, now=now)
        if action is FollowAction.PENDING:
            return
        self.timer = None
        if action is FollowAction.IGNORE:
            return
        if action is FollowAction.DWELL:
            self.timer = (now + self.dwell_s, area_id)
            return
        self._write(area_id)

    def advance_clock(self, now: float) -> None:
        if self.timer is not None and now >= self.timer[0]:
            target = self.timer[1]
            self.timer = None
            if self.dwell.take_due(target, now) and self._allowed():
                self._write(target)


class TestVoiceFollowsMe(unittest.TestCase):
    """Voice Follows Me invariants, exercised through `area_follow.py`."""

    def test_roaming_comes_from_hardware_traits_only(self) -> None:
        """stationary == 0 or wearable == 1 is roaming; missing or malformed traits are not."""
        self.assertTrue(manifest_is_roaming({"stationary": 0}))
        self.assertTrue(manifest_is_roaming({"stationary": 0, "wearable": 1}))
        self.assertTrue(manifest_is_roaming({"wearable": 1}))
        self.assertFalse(manifest_is_roaming({"stationary": 1, "wearable": 0}))
        self.assertFalse(manifest_is_roaming({}))
        self.assertFalse(manifest_is_roaming({"stationary": "x"}))
        self.assertFalse(manifest_is_roaming({"display": 1}))

    def test_display_and_wearable_traits(self) -> None:
        """Headless only when the manifest says display == 0; wearable only when it says wearable == 1."""
        self.assertTrue(traits.manifest_has_display({"display": 1}))
        self.assertFalse(traits.manifest_has_display({"display": 0}))
        self.assertFalse(traits.manifest_has_display({"display": "0"}))
        self.assertTrue(traits.manifest_has_display({}), "an unreported trait never makes a Device headless")
        self.assertTrue(traits.manifest_has_display({"display": "x"}))
        self.assertTrue(traits.manifest_is_wearable({"wearable": 1}))
        self.assertFalse(traits.manifest_is_wearable({"wearable": 0}))
        self.assertFalse(traits.manifest_is_wearable({}))

    def test_stationary_device_never_writes_area(self) -> None:
        """Stationary devices (stationary == 1) must never mutate the device registry area_id."""
        harness = _FollowHarness(manifest={"stationary": 1}, esphome_device_id="esp_stationary_01")
        self.assertFalse(harness.is_roaming_device)
        harness.set_area("office", ble_driven=True, now=100.0)
        harness.advance_clock(now=200.0)
        harness.set_area("office", ble_driven=False, now=205.0)
        self.assertEqual(harness.registry_writes, [])
        self.assertEqual(harness.device_area_id, "kitchen")

    def test_roaming_dwell_bounce_and_away_preservation(self) -> None:
        """Bounce A -> B cancels A; away/unknown never clears the Area; an explicit pick applies immediately."""
        harness = _FollowHarness(manifest={"stationary": 0}, esphome_device_id="esp_roaming_01", dwell_s=10.0)
        self.assertTrue(harness.is_roaming_device)

        harness.set_area("hallway", ble_driven=True, now=10.0)
        harness.advance_clock(now=14.0)
        self.assertEqual(harness.registry_writes, [])

        harness.set_area("office", ble_driven=True, now=14.0)
        harness.advance_clock(now=20.0)
        self.assertEqual(harness.registry_writes, [])

        harness.advance_clock(now=24.0)
        self.assertEqual(harness.registry_writes, [("esp_roaming_01", "office")])
        self.assertEqual(harness.device_area_id, "office")

        # Brief move to bedroom, then the source reports away -> pending move dropped, "office" kept.
        harness.set_area("bedroom", ble_driven=True, now=30.0)
        harness.set_area("away", ble_driven=True, now=35.0)
        harness.advance_clock(now=50.0)
        self.assertEqual(len(harness.registry_writes), 1)
        self.assertEqual(harness.device_area_id, "office")
        self.assertIsNone(harness.dwell.pending_area_id)

        harness.set_area("den", ble_driven=False, now=55.0)
        self.assertEqual(
            harness.registry_writes,
            [("esp_roaming_01", "office"), ("esp_roaming_01", "den")],
        )

    def test_repeated_ble_report_keeps_original_deadline(self) -> None:
        """Re-reporting the pending Area must not restart the dwell."""
        dwell = AreaFollowDwell()
        self.assertIs(dwell.request("hallway", ble_driven=True, dwell_s=10, now=10.0), FollowAction.DWELL)
        self.assertIs(dwell.request("hallway", ble_driven=True, dwell_s=10, now=15.0), FollowAction.PENDING)
        self.assertFalse(dwell.take_due("hallway", now=19.0))
        self.assertTrue(dwell.take_due("hallway", now=20.0))
        self.assertIsNone(dwell.pending_area_id)

    def test_non_area_states_and_zero_dwell(self) -> None:
        """Placeholders are ignored and cancel; a zero dwell commits at once."""
        dwell = AreaFollowDwell()
        dwell.request("office", ble_driven=True, dwell_s=10, now=0.0)
        for placeholder in ("", "unknown", "unavailable", "none", "away", "not_home", "Away"):
            self.assertIs(dwell.request(placeholder, ble_driven=True, dwell_s=10, now=1.0), FollowAction.IGNORE)
            self.assertIsNone(dwell.pending_area_id)
        self.assertIs(dwell.request("office", ble_driven=True, dwell_s=0, now=2.0), FollowAction.COMMIT)
        self.assertFalse(dwell.take_due("office", now=100.0))


def _never_cross_floor(_area_id: str) -> bool:
    return False


class TestBleAreaScoring(unittest.TestCase):
    """BLE Area scoring and switching, exercised through `ble_math.py`."""

    def test_silence_decay_lets_new_room_overtake_and_stale_room_drops(self) -> None:
        """After the 2 s grace an Area loses 1.5 dB/s, so a fresh Area overtakes a silent one; > 12 s silent drops it."""
        area_rssi = {"room_a": (-58.0, 0.0), "room_b": (-64.0, 8.5)}

        scores = ble_math.score_areas(area_rssi, 9.0, _never_cross_floor)
        self.assertAlmostEqual(scores["room_a"], -58.0 - 7.0 * 1.5)
        self.assertAlmostEqual(scores["room_b"], -64.0)
        decision = ble_math.decide_area(scores, "room_a", 9.0, last_switch=0.0)
        assert decision is not None
        self.assertEqual(decision.best_area_id, "room_b")
        self.assertFalse(decision.switch, "a 4.5 dB lead is inside the 5 dB hysteresis")

        scores = ble_math.score_areas({"room_a": (-58.0, 0.0), "room_b": (-64.0, 9.5)}, 10.0, _never_cross_floor)
        decision = ble_math.decide_area(scores, "room_a", 10.0, last_switch=0.0)
        assert decision is not None
        self.assertTrue(decision.switch)
        self.assertEqual(decision.best_area_id, "room_b")

        scores = ble_math.score_areas(area_rssi, 12.5, _never_cross_floor)
        self.assertNotIn("room_a", scores)

    def test_cross_floor_penalty(self) -> None:
        """Candidates on another floor lose CROSS_FLOOR_ATTENUATION_DB (6 dB)."""
        scores = ble_math.score_areas(
            {"upstairs": (-60.0, 10.0), "kitchen": (-63.0, 10.0)},
            10.0,
            lambda area_id: area_id == "upstairs",
        )
        self.assertAlmostEqual(scores["upstairs"], -66.0)
        decision = ble_math.decide_area(scores, "kitchen", 10.0, last_switch=0.0)
        assert decision is not None
        self.assertEqual(decision.best_area_id, "kitchen")
        self.assertFalse(decision.switch)

    def test_hold_override_and_floor(self) -> None:
        """Within the 4 s hold only an 8 dB lead switches; nothing below -88 dBm wins; no current Area locks at once."""
        scores = {"a": -70.0, "b": -64.0}
        decision = ble_math.decide_area(scores, "a", now=11.0, last_switch=10.0)
        assert decision is not None
        self.assertFalse(decision.switch)
        decision = ble_math.decide_area({"a": -70.0, "b": -61.0}, "a", now=11.0, last_switch=10.0)
        assert decision is not None
        self.assertTrue(decision.switch)
        self.assertIsNone(ble_math.decide_area({"a": -90.0}, None, now=0.0, last_switch=0.0))
        self.assertIsNone(ble_math.decide_area({}, None, now=0.0, last_switch=0.0))
        decision = ble_math.decide_area({"a": -80.0}, None, now=0.0, last_switch=0.0)
        assert decision is not None
        self.assertTrue(decision.switch)

    def test_smoothing_restarts_after_stale_gap(self) -> None:
        """The EMA blends 50/50 and restarts from the raw value after a stale gap."""
        self.assertEqual(ble_math.smooth_rssi(None, -70.0, 5.0), -70.0)
        self.assertEqual(ble_math.smooth_rssi((-60.0, 4.0), -70.0, 5.0), -65.0)
        self.assertEqual(ble_math.smooth_rssi((-60.0, 0.0), -70.0, 13.0), -70.0)


class TestResourceSigning(unittest.TestCase):
    """HMAC resource signatures, exercised through `resource_signing.py`."""

    SECRET = bytes.fromhex("a5" * 32)
    DAY_START = 1761955200

    def _sign_bucketed(self, resource: str, now_s: int, scope: str = "sub_abc") -> str:
        exp = resource_signing.day_bucketed_expiry(now_s, resource_signing.PAYLOAD_TTL_DAYS)
        return resource_signing.sign(self.SECRET, scope, resource, exp)

    def test_day_bucketed_is_deterministic_and_scoped(self) -> None:
        """Same UTC day -> identical signature, bound to the Device scope and the render parameters."""
        res = "artwork|480|480|circle"
        sig_t0 = self._sign_bucketed(res, self.DAY_START + 10)
        sig_t1 = self._sign_bucketed(res, self.DAY_START + 3600)
        self.assertEqual(sig_t0, sig_t1)
        self.assertNotEqual(sig_t0, self._sign_bucketed(res, self.DAY_START + 86400 + 10))

        verify = resource_signing.verify
        now = self.DAY_START + 7200
        self.assertTrue(verify(self.SECRET, "sub_abc", res, sig_t0, now))
        self.assertFalse(verify(self.SECRET, "sub_other", res, sig_t0, now))
        self.assertFalse(verify(self.SECRET, "sub_abc", "artwork|720|720|square", sig_t0, now))
        self.assertFalse(verify(self.SECRET, "sub_abc", "camera:camera.front_door|480|480|circle", sig_t0, now))

    def test_day_bucketed_lifetime_is_ttl_to_ttl_plus_one_day(self) -> None:
        """A 7-day URL signed at any time of day stays valid for 7 to 8 days."""
        for offset in (0, 43200, 86399):
            now = self.DAY_START + offset
            exp = resource_signing.day_bucketed_expiry(now, 7)
            self.assertEqual(exp % 86400, 0)
            self.assertGreaterEqual(exp - now, 7 * 86400)
            self.assertLessEqual(exp - now, 8 * 86400)
        sig = self._sign_bucketed("map:Home|480|480|circle", self.DAY_START)
        exp = int(sig.split(".", 1)[0])
        self.assertTrue(resource_signing.verify(self.SECRET, "sub_abc", "map:Home|480|480|circle", sig, exp))
        self.assertFalse(resource_signing.verify(self.SECRET, "sub_abc", "map:Home|480|480|circle", sig, exp + 1))

    def test_exact_expiry_for_on_demand_urls(self) -> None:
        """An on-demand URL expires exactly ON_DEMAND_TTL_SECONDS (10 min) after signing."""
        now = self.DAY_START + 12345
        ttl = resource_signing.ON_DEMAND_TTL_SECONDS
        self.assertEqual(ttl, 600)
        exp = resource_signing.exact_expiry(now, ttl)
        self.assertEqual(exp, now + 600)
        sig = resource_signing.sign(self.SECRET, "sub_abc", "camera_audio:camera.door", exp)
        verify = resource_signing.verify
        self.assertTrue(verify(self.SECRET, "sub_abc", "camera_audio:camera.door", sig, now + 600))
        self.assertFalse(verify(self.SECRET, "sub_abc", "camera_audio:camera.door", sig, now + 601))

    def test_rejects_tampered_malformed_and_bad_ttl(self) -> None:
        """Tampered MACs, malformed or non-ASCII tokens are rejected without raising; ttl must be positive."""
        res = "artwork|480|480|circle"
        sig = self._sign_bucketed(res, self.DAY_START)
        now = self.DAY_START + 100
        verify = resource_signing.verify
        tampered = f"{sig[:-1]}{'0' if sig[-1] != '0' else '1'}"
        for bad in (tampered, "malformed", None, "", ".", "abc.def", f"{sig}é", "１２３.abcd", f"+{sig}"):
            self.assertFalse(verify(self.SECRET, "sub_abc", res, bad, now), bad)
        with self.assertRaises(ValueError):
            resource_signing.day_bucketed_expiry(now, 0)
        with self.assertRaises(ValueError):
            resource_signing.exact_expiry(now, 0)


class _Dev:
    def __init__(self, subentry_id: str, slug: str) -> None:
        self.subentry_id = subentry_id
        self.device_slug = slug


def _js_command_set(js_src: str, const_name: str) -> set[str]:
    match = re.search(rf"const {const_name} = new Set\(\[(.*?)\]\);", js_src, re.S)
    assert match is not None, const_name
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


class TestStudioTargeting(unittest.TestCase):
    """Studio Device targeting and command scopes, exercised through studio/scope.py."""

    def test_target_resolves_by_exact_subentry_id_only(self) -> None:
        """No first-Device fallback, no slug or entry_id matching."""
        devs = [_Dev("sub_a", "kitchen"), _Dev("sub_b", "pocket")]
        find = studio_scope.find_by_subentry_id
        self.assertIs(find(devs, "sub_b"), devs[1])
        self.assertIs(find(devs, " sub_a "), devs[0])
        for missing in (None, "", "   ", "pocket", "SUB_A", "sub", "entry_hub"):
            self.assertIsNone(find(devs, missing), missing)
        self.assertIsNone(find([], "sub_a"))

    def test_command_scopes(self) -> None:
        """Device commands need a Device; System commands only in their Device-scoped modes; unknown commands fail."""
        needs = studio_scope.command_requires_device
        self.assertFalse(studio_scope.SYSTEM_COMMANDS & studio_scope.DEVICE_COMMANDS)
        for cmd in studio_scope.DEVICE_COMMANDS:
            self.assertTrue(needs(cmd, {}), cmd)
        for cmd in ("set_ble_area_offset", "auto_calibrate_here", "remove_device", "check_system_updates"):
            self.assertFalse(needs(cmd, {}), cmd)
        self.assertTrue(needs("apply_profile", {}))
        self.assertTrue(needs("apply_profile", {"target_scope": "current"}))
        self.assertFalse(needs("apply_profile", {"target_scope": "all"}))
        self.assertFalse(needs("apply_profile", {"target_scope": "device:sub_a"}))
        self.assertTrue(needs("export_backup_json", {}))
        self.assertFalse(needs("export_backup_json", {"scope": "system"}))
        self.assertTrue(needs("restore_backup", {"bundle": {"scope": "device"}}))
        self.assertFalse(needs("restore_backup", {"bundle": {"scope": "system"}}))
        self.assertTrue(needs("send_test_notification", {"include_camera": True}))
        self.assertFalse(needs("send_test_notification", {"target_device": "all"}))
        with self.assertRaises(studio_scope.UnknownStudioCommand):
            needs("format_disk", {})

    def test_studio_js_command_sets_match_backend(self) -> None:
        """latter-studio.js must classify every command exactly as studio/scope.py does."""
        js_src = STUDIO_JS.read_text(encoding="utf-8")
        self.assertEqual(_js_command_set(js_src, "SYSTEM_WS_COMMANDS"), set(studio_scope.SYSTEM_COMMANDS))
        self.assertEqual(_js_command_set(js_src, "DEVICE_WS_COMMANDS"), set(studio_scope.DEVICE_COMMANDS))
        sent = set(re.findall(r'command: "([a-z_]+)"', js_src))
        known = studio_scope.SYSTEM_COMMANDS | studio_scope.DEVICE_COMMANDS
        self.assertFalse(sent - known, f"Studio sends unknown commands: {sorted(sent - known)}")


class TestNoDeviceProfile(unittest.TestCase):
    """Hardware kind is the subentry type plus manifest traits; no code reads a device profile."""

    def test_no_profile_readers_remain(self) -> None:
        pattern = re.compile(r"device_profile|DEVICE_PROFILE|headless_node|mobile_display|stationary_display|wearable_display|\"ble_beacon\"")
        offenders = []
        for path in sorted(LATTER_DIR.rglob("*")):
            if path.suffix not in (".py", ".js", ".json", ".yaml") or "__pycache__" in path.parts:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(LATTER_DIR)}:{lineno}: {line.strip()}")
        self.assertEqual(offenders, [])


class TestDeviceIssueIds(unittest.TestCase):
    """Per-Device repair issue IDs, exercised through issue_ids.py."""

    def test_device_issue_ids_cover_every_per_device_issue(self) -> None:
        self.assertEqual(
            set(issue_ids.device_issue_ids("sub_a")),
            {
                "link_ma_player_sub_a",
                "missing_mapped_entity_sub_a",
                "ble_no_proxies_sub_a",
                "slot_push_failing_sub_a",
                "device_crashed_sub_a",
                "device_brownout_sub_a",
                "firmware_rolled_back_sub_a",
            },
        )


class TestDeviceHealth(unittest.TestCase):
    """Crash / brownout / rollback repair decisions, exercised through `health.py`."""

    def _actions(self, manifest: dict[str, Any]):
        return health.evaluate_device_health(health.parse_device_health(manifest))

    def test_crash_resets_raise_device_crashed(self) -> None:
        for reason in ("panic", "int-wdt", "task-wdt", "wdt", "stall"):
            acts = self._actions({"sdk": 41, "reset": reason, "crash": 1, "rollback": 0})
            self.assertEqual(acts.raise_issues, {"device_crashed": {"reason": reason, "sdk": "41"}})
            self.assertEqual(acts.delete_issues, {"firmware_rolled_back"})

    def test_brownout_raises_its_own_issue(self) -> None:
        acts = self._actions({"sdk": 41, "reset": "brownout", "crash": 0})
        self.assertEqual(acts.raise_issues, {"device_brownout": {"sdk": "41"}})
        self.assertEqual(acts.delete_issues, frozenset())

    def test_clean_reset_clears_crash_and_brownout(self) -> None:
        for reason in ("power-on", "external", "software", "deep-sleep"):
            acts = self._actions({"sdk": 41, "reset": reason, "crash": 0, "rollback": 0})
            self.assertEqual(acts.raise_issues, {})
            self.assertEqual(
                acts.delete_issues, {"device_crashed", "device_brownout", "firmware_rolled_back"}
            )

    def test_unknown_or_missing_reset_leaves_issues_alone(self) -> None:
        for manifest in ({"reset": "unknown"}, {}, {"w": 466, "h": 466}):
            acts = self._actions(manifest)
            self.assertEqual(acts.raise_issues, {})
            self.assertEqual(acts.delete_issues, frozenset())

    def test_rollback(self) -> None:
        acts = self._actions({"sdk": 40, "reset": "software", "rollback": 1})
        self.assertEqual(acts.raise_issues, {"firmware_rolled_back": {"sdk": "40"}})
        self.assertNotIn("firmware_rolled_back", acts.delete_issues)
        acts = self._actions({"reset": "panic", "rollback": "1"})
        self.assertEqual(
            set(acts.raise_issues), {"device_crashed", "firmware_rolled_back"}
        )
        self.assertEqual(acts.raise_issues["firmware_rolled_back"], {"sdk": "unknown"})

    def test_parse_tolerates_bad_values(self) -> None:
        parsed = health.parse_device_health({"sdk": "x", "reset": " PANIC ", "crash": "1", "rollback": None})
        self.assertEqual(parsed, health.DeviceHealth(sdk=None, reset="panic", crash=True, rollback=None))
        self.assertEqual(health.parse_device_health(None), health.DeviceHealth(None, None, None, None))

    def test_health_issue_ids_are_cleaned_with_the_device(self) -> None:
        ids = set(issue_ids.device_issue_ids("sub_a"))
        for kind in (health.ISSUE_CRASHED, health.ISSUE_BROWNOUT, health.ISSUE_ROLLED_BACK):
            self.assertIn(issue_ids.device_health_issue_id(kind, "sub_a"), ids)
            self.assertIn(kind, issue_ids.DEVICE_HEALTH_ISSUE_KINDS)


class TestMaPlayerLink(unittest.TestCase):
    """Music Assistant player link for a Latter Device, exercised through `ma_link.py`."""

    CANDIDATES = [
        ("media_player.desk_assistant", "slampton", "desk-assistant-p4-86"),
        ("media_player.pocket_assistant", "slampton", "pocket-assistant-s3-206"),
        ("media_player.office_amp", "Music Assistant", "Sendspin"),
    ]

    def test_configured_link_takes_precedence_when_it_is_a_current_ma_player(self) -> None:
        ma_ids = [c[0] for c in self.CANDIDATES]
        self.assertEqual(
            ma_link.configured_link("media_player.desk_assistant", ma_ids),
            "media_player.desk_assistant",
        )
        self.assertIsNone(ma_link.configured_link("media_player.gone", ma_ids))
        self.assertIsNone(ma_link.configured_link("", ma_ids))
        self.assertIsNone(ma_link.configured_link(None, ma_ids))

    def test_suggestion_needs_exactly_one_manufacturer_and_model_match(self) -> None:
        suggest = ma_link.suggest_ma_player
        self.assertEqual(
            suggest(("slampton", "desk-assistant-p4-86"), self.CANDIDATES),
            "media_player.desk_assistant",
        )
        self.assertIsNone(suggest(("slampton", "remote-assistant-p4-35"), self.CANDIDATES))
        twins = self.CANDIDATES + [("media_player.desk_assistant_2", "slampton", "desk-assistant-p4-86")]
        self.assertIsNone(suggest(("slampton", "desk-assistant-p4-86"), twins))
        self.assertIsNone(suggest(("slampton", None), self.CANDIDATES))
        self.assertIsNone(suggest((None, "desk-assistant-p4-86"), self.CANDIDATES))
        self.assertIsNone(suggest(("Slampton", "desk-assistant-p4-86"), self.CANDIDATES), "exact match only")


if __name__ == "__main__":
    unittest.main()
