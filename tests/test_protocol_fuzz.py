"""Unit and Hypothesis property-based fuzz tests for Protocol v3, PIN wrapping, RPC reassembly, HMAC signing, BLE math, Studio scope, repairs, MA linking, and diagnostics redaction."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
from typing import Any, ClassVar
import unittest

from hypothesis import configuration, given, settings, strategies as st

from custom_components.latter import (
    diagnostics as diagnostics_sanitizer,
    identity as traits,
    protocol_codec,
    protocol_policy as security_policy,
    repairs_keys as health,
)
from custom_components.latter.http import signing as resource_signing
from custom_components.latter.media import linking as ma_link
from custom_components.latter.presence import ble_math
from custom_components.latter.services import rpc_receiver as rpc_protocol
from custom_components.latter.studio import state_gates as studio_scope
from tests.conftest import LATTER_DIR, read_ts_tree

configuration.set_hypothesis_home_dir(Path(tempfile.gettempdir()) / "latter_hypothesis")

STUDIO_JS = LATTER_DIR / "frontend" / "latter-studio.js"

issue_ids = health
AreaFollowDwell = ble_math.AreaFollowDwell
FollowAction = ble_math.FollowAction
manifest_is_roaming = traits.manifest_is_roaming

_ADVERSARIAL_ALPHABET = (
    "|;\x1f\x1e\\\x00\t\r\n\x7f\u2028\u2029"
    "abcXYZ0129:/=-_.'\""
    "éüñΩЖ✨🔥🎵"
    "\u0301\u0308\u200d"
)
_ADVERSARIAL_TEXT = st.one_of(
    st.text(alphabet=_ADVERSARIAL_ALPHABET, min_size=0, max_size=80),
    st.text(min_size=0, max_size=80),
)
_UNSAFE_CTRL_RE = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")


class _FollowHarness:
    """Drives production `AreaFollowDwell` with deterministic clock and registry write log."""

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
    """Voice Follows Me invariants, exercised through `ble_math.AreaFollowDwell`."""

    def test_roaming_comes_from_hardware_traits_only(self) -> None:
        self.assertTrue(manifest_is_roaming({"stationary": 0}))
        self.assertTrue(manifest_is_roaming({"stationary": 0, "wearable": 1}))
        self.assertTrue(manifest_is_roaming({"wearable": 1}))
        self.assertFalse(manifest_is_roaming({"stationary": 1, "wearable": 0}))
        self.assertFalse(manifest_is_roaming({}))
        self.assertFalse(manifest_is_roaming({"stationary": "x"}))
        self.assertFalse(manifest_is_roaming({"display": 1}))

    def test_display_and_wearable_traits(self) -> None:
        self.assertTrue(traits.manifest_has_display({"display": 1}))
        self.assertFalse(traits.manifest_has_display({"display": 0}))
        self.assertFalse(traits.manifest_has_display({"display": "0"}))
        self.assertTrue(traits.manifest_has_display({}))
        self.assertTrue(traits.manifest_has_display({"display": "x"}))
        self.assertTrue(traits.manifest_is_wearable({"wearable": 1}))
        self.assertFalse(traits.manifest_is_wearable({"wearable": 0}))
        self.assertFalse(traits.manifest_is_wearable({}))

    def test_stationary_device_never_writes_area(self) -> None:
        harness = _FollowHarness(manifest={"stationary": 1}, esphome_device_id="esp_stationary_01")
        self.assertFalse(harness.is_roaming_device)
        harness.set_area("office", ble_driven=True, now=100.0)
        harness.advance_clock(now=200.0)
        harness.set_area("office", ble_driven=False, now=205.0)
        self.assertEqual(harness.registry_writes, [])
        self.assertEqual(harness.device_area_id, "kitchen")

    def test_roaming_dwell_bounce_and_away_preservation(self) -> None:
        harness = _FollowHarness(manifest={"stationary": 0}, esphome_device_id="esp_roaming_01", dwell_s=10.0)
        harness.set_area("hallway", ble_driven=True, now=10.0)
        harness.advance_clock(now=14.0)
        self.assertEqual(harness.registry_writes, [])
        harness.set_area("office", ble_driven=True, now=14.0)
        harness.advance_clock(now=20.0)
        self.assertEqual(harness.registry_writes, [])
        harness.advance_clock(now=24.0)
        self.assertEqual(harness.registry_writes, [("esp_roaming_01", "office")])
        harness.set_area("bedroom", ble_driven=True, now=30.0)
        harness.set_area("away", ble_driven=True, now=35.0)
        harness.advance_clock(now=50.0)
        self.assertEqual(harness.device_area_id, "office")
        self.assertIsNone(harness.dwell.pending_area_id)
        harness.set_area("den", ble_driven=False, now=55.0)
        self.assertEqual(harness.registry_writes, [("esp_roaming_01", "office"), ("esp_roaming_01", "den")])

    def test_repeated_ble_report_keeps_original_deadline(self) -> None:
        dwell = AreaFollowDwell()
        self.assertIs(dwell.request("hallway", ble_driven=True, dwell_s=10, now=10.0), FollowAction.DWELL)
        self.assertIs(dwell.request("hallway", ble_driven=True, dwell_s=10, now=15.0), FollowAction.PENDING)
        self.assertFalse(dwell.take_due("hallway", now=19.0))
        self.assertTrue(dwell.take_due("hallway", now=20.0))
        self.assertIsNone(dwell.pending_area_id)

    def test_non_area_states_and_zero_dwell(self) -> None:
        dwell = AreaFollowDwell()
        dwell.request("office", ble_driven=True, dwell_s=10, now=0.0)
        for placeholder in ("", "unknown", "unavailable", "none", "away", "not_home", "Away"):
            self.assertIs(dwell.request(placeholder, ble_driven=True, dwell_s=10, now=1.0), FollowAction.IGNORE)
            self.assertIsNone(dwell.pending_area_id)
        self.assertIs(dwell.request("office", ble_driven=True, dwell_s=0, now=2.0), FollowAction.COMMIT)
        self.assertFalse(dwell.take_due("office", now=100.0))


class TestBleAreaScoring(unittest.TestCase):
    """BLE Area hysteresis, silence decay constants, deadband, and path-loss distance math."""

    def test_silence_decay_and_hysteresis_takeover(self) -> None:
        decayed_a = -58.0 - ble_math.SILENCE_DECAY_DB_PER_S * max(0.0, 9.0 - ble_math.SILENCE_GRACE_SECONDS)
        self.assertAlmostEqual(decayed_a, -58.0 - 7.0 * 1.5)
        decision = ble_math.decide_area({"area_a": decayed_a, "area_b": -64.0}, "area_a", 9.0, last_switch=0.0)
        assert decision is not None
        self.assertEqual(decision.best_area_id, "area_b")
        self.assertFalse(decision.switch)

        decayed_a2 = -58.0 - ble_math.SILENCE_DECAY_DB_PER_S * max(0.0, 10.0 - ble_math.SILENCE_GRACE_SECONDS)
        decision = ble_math.decide_area({"area_a": decayed_a2, "area_b": -64.0}, "area_a", 10.0, last_switch=0.0)
        assert decision is not None
        self.assertTrue(decision.switch)
        self.assertEqual(decision.best_area_id, "area_b")
        self.assertGreater(12.5, ble_math.STALE_PROXY_SECONDS)

    def test_cross_floor_penalty(self) -> None:
        self.assertAlmostEqual(ble_math.CROSS_FLOOR_ATTENUATION_DB, 6.0)
        scores = {"upstairs": -60.0 - ble_math.CROSS_FLOOR_ATTENUATION_DB, "kitchen": -63.0}
        decision = ble_math.decide_area(scores, "kitchen", 10.0, last_switch=0.0)
        assert decision is not None
        self.assertEqual(decision.best_area_id, "kitchen")
        self.assertFalse(decision.switch)

    def test_hold_override_and_floor(self) -> None:
        decision = ble_math.decide_area({"a": -70.0, "b": -64.0}, "a", now=11.0, last_switch=10.0)
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

    def test_deadband_and_distance_roundtrip(self) -> None:
        self.assertFalse(ble_math.within_rssi_deadband(None, -70))
        self.assertTrue(ble_math.within_rssi_deadband(-70, -68))
        self.assertFalse(ble_math.within_rssi_deadband(-70, -67))
        self.assertAlmostEqual(ble_math.rssi_to_distance_m(-59.0), 1.0)
        dist = ble_math.continuous_distance_m(-68.0, 2.2)
        self.assertAlmostEqual(ble_math.distance_m_to_norm_dbm(dist, 2.2), -68.0, places=5)


class TestResourceSigning(unittest.TestCase):
    """HMAC resource signatures, exercised through `http/signing.py`."""

    SECRET = bytes.fromhex("a5" * 32)
    DAY_START = 1761955200

    def _sign_bucketed(self, resource: str, now_s: int, scope: str = "sub_abc") -> str:
        exp = resource_signing.day_bucketed_expiry(now_s, resource_signing.PAYLOAD_TTL_DAYS)
        return resource_signing.sign(self.SECRET, scope, resource, exp)

    def test_day_bucketed_is_deterministic_and_scoped(self) -> None:
        res = "artwork|480|480|circle"
        sig_t0 = self._sign_bucketed(res, self.DAY_START + 10)
        self.assertEqual(sig_t0, self._sign_bucketed(res, self.DAY_START + 3600))
        self.assertNotEqual(sig_t0, self._sign_bucketed(res, self.DAY_START + 86400 + 10))
        now = self.DAY_START + 7200
        self.assertTrue(resource_signing.verify(self.SECRET, "sub_abc", res, sig_t0, now))
        self.assertFalse(resource_signing.verify(self.SECRET, "sub_other", res, sig_t0, now))
        self.assertFalse(resource_signing.verify(self.SECRET, "sub_abc", "artwork|720|720|square", sig_t0, now))
        self.assertFalse(resource_signing.verify(self.SECRET, "sub_abc", "camera:camera.front_door|480|480|circle", sig_t0, now))

    def test_day_bucketed_lifetime_and_exact_expiry(self) -> None:
        self.assertEqual(resource_signing.PAYLOAD_TTL_DAYS, 2)
        for offset in (0, 43200, 86399):
            now = self.DAY_START + offset
            exp = resource_signing.day_bucketed_expiry(now, resource_signing.PAYLOAD_TTL_DAYS)
            self.assertEqual(exp % 86400, 0)
            self.assertGreaterEqual(exp - now, 2 * 86400)
            self.assertLessEqual(exp - now, 3 * 86400)
        sig = self._sign_bucketed("wallpaper:preset:aurora|480|480|circle", self.DAY_START)
        exp = int(sig.split(".", 1)[0])
        self.assertTrue(resource_signing.verify(self.SECRET, "sub_abc", "wallpaper:preset:aurora|480|480|circle", sig, exp))
        self.assertFalse(resource_signing.verify(self.SECRET, "sub_abc", "wallpaper:preset:aurora|480|480|circle", sig, exp + 1))

        now_od = self.DAY_START + 12345
        exp_od = resource_signing.exact_expiry(now_od, resource_signing.ON_DEMAND_TTL_SECONDS)
        sig_od = resource_signing.sign(self.SECRET, "sub_abc", "camera_audio:camera.door", exp_od)
        self.assertTrue(resource_signing.verify(self.SECRET, "sub_abc", "camera_audio:camera.door", sig_od, now_od + 600))
        self.assertFalse(resource_signing.verify(self.SECRET, "sub_abc", "camera_audio:camera.door", sig_od, now_od + 601))

    def test_rejects_tampered_malformed_and_bad_ttl(self) -> None:
        res = "artwork|480|480|circle"
        sig = self._sign_bucketed(res, self.DAY_START)
        now = self.DAY_START + 100
        tampered = f"{sig[:-1]}{'0' if sig[-1] != '0' else '1'}"
        for bad in (tampered, "malformed", None, "", ".", "abc.def", f"{sig}é", "\uff11\uff12\uff13.abcd", f"+{sig}"):
            self.assertFalse(resource_signing.verify(self.SECRET, "sub_abc", res, bad, now), bad)
        with self.assertRaises(ValueError):
            resource_signing.day_bucketed_expiry(now, 0)
        with self.assertRaises(ValueError):
            resource_signing.exact_expiry(now, 0)


class _Dev:
    def __init__(self, subentry_id: str, slug: str) -> None:
        self.subentry_id = subentry_id
        self.device_slug = slug


def _ts_command_set(ts_src: str, const_name: str) -> set[str]:
    match = re.search(rf"const {const_name}(?::\s*[^=]+)?\s*=\s*new Set\(\[(.*?)\]\);", ts_src, re.S)
    assert match is not None, const_name
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


class TestStudioTargeting(unittest.TestCase):
    """Studio Device targeting and command scopes, exercised through `studio/state_gates.py`."""

    def test_target_resolves_by_exact_subentry_id_only(self) -> None:
        devs = [_Dev("sub_a", "kitchen"), _Dev("sub_b", "mobile")]
        find = studio_scope.find_by_subentry_id
        self.assertIs(find(devs, "sub_b"), devs[1])
        self.assertIs(find(devs, " sub_a "), devs[0])
        for missing in (None, "", "   ", "mobile", "SUB_A", "sub", "entry_hub"):
            self.assertIsNone(find(devs, missing), missing)
        self.assertIsNone(find([], "sub_a"))

    def test_command_scopes(self) -> None:
        scope = studio_scope.command_scope
        self.assertFalse(studio_scope.SYSTEM_COMMANDS & studio_scope.DEVICE_COMMANDS)
        for cmd in studio_scope.DEVICE_COMMANDS:
            self.assertEqual(scope(cmd), "device", cmd)
        for cmd in studio_scope.SYSTEM_COMMANDS:
            self.assertEqual(scope(cmd), "system", cmd)
        for retired in (
            "save_config", "system_entity_action", "log_client_error", "export_backup_json",
            "restore_backup", "format_disk", "capture_profile", "apply_profile",
            "seed_group_baseline", "sync_device_group", "set_group_device_setting",
        ):
            with self.assertRaises(studio_scope.UnknownStudioCommand):
                scope(retired)

    def test_studio_js_command_sets_match_backend(self) -> None:
        schema_ts = read_ts_tree("protocol-schema.ts")
        self.assertEqual(
            _ts_command_set(schema_ts, "SYSTEM_WS_COMMANDS"), set(studio_scope.SYSTEM_COMMANDS)
        )
        self.assertEqual(
            _ts_command_set(schema_ts, "DEVICE_WS_COMMANDS"), set(studio_scope.DEVICE_COMMANDS)
        )
        all_ts = read_ts_tree(".")
        bundle_js = STUDIO_JS.read_text(encoding="utf-8")
        sent = set(re.findall(r'command:\s*"([a-z_]+)"', all_ts)) | set(
            re.findall(r'command:\s*"([a-z_]+)"', bundle_js)
        )
        known = studio_scope.SYSTEM_COMMANDS | studio_scope.DEVICE_COMMANDS
        self.assertFalse(sent - known, f"Studio sends unknown commands: {sorted(sent - known)}")


class TestNoDeviceProfile(unittest.TestCase):
    """Hardware kind is the subentry type plus manifest traits; no code reads a device profile."""

    def test_no_profile_readers_remain(self) -> None:
        pattern = re.compile(
            r'device_profile|DEVICE_PROFILE|headless_node|mobile_display|stationary_display|wearable_display|"ble_beacon"'
        )
        offenders = [
            f"{path.relative_to(LATTER_DIR)}:{lineno}: {line.strip()}"
            for path in sorted(LATTER_DIR.rglob("*"))
            if path.suffix in (".py", ".js", ".json", ".yaml") and "__pycache__" not in path.parts
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if pattern.search(line)
        ]
        self.assertEqual(offenders, [])


class TestDeviceHealthAndIssues(unittest.TestCase):
    """Per-Device repair issue IDs and crash/brownout/rollback evaluation."""

    def test_device_issue_ids_and_health_transitions(self) -> None:
        ids = set(issue_ids.device_issue_ids("sub_a"))
        self.assertEqual(
            ids,
            {
                "link_ma_player_sub_a", "missing_mapped_entity_sub_a", "ble_no_proxies_sub_a",
                "slot_push_failing_sub_a", "device_crashed_sub_a", "device_brownout_sub_a",
                "firmware_rolled_back_sub_a", "outdated_firmware_sub_a",
            },
        )
        for reason in ("panic", "int-wdt", "task-wdt", "wdt", "stall"):
            acts = health.evaluate_device_health(
                health.parse_device_health({"core_rev": 41, "reset": reason, "crash": 1, "rollback": 0})
            )
            self.assertEqual(acts.raise_issues, {"device_crashed": {"reason": reason, "core_rev": "41"}})
            self.assertEqual(acts.delete_issues, {"firmware_rolled_back"})

        brownout = health.evaluate_device_health(
            health.parse_device_health({"core_rev": 41, "reset": "brownout", "crash": 0})
        )
        self.assertEqual(brownout.raise_issues, {"device_brownout": {"core_rev": "41"}})

        for reason in ("power-on", "external", "software", "deep-sleep"):
            clean = health.evaluate_device_health(
                health.parse_device_health({"core_rev": 41, "reset": reason, "crash": 0, "rollback": 0})
            )
            self.assertEqual(clean.raise_issues, {})
            self.assertEqual(clean.delete_issues, {"device_crashed", "device_brownout", "firmware_rolled_back"})

        rb = health.evaluate_device_health(health.parse_device_health({"reset": "panic", "rollback": "1"}))
        self.assertEqual(set(rb.raise_issues), {"device_crashed", "firmware_rolled_back"})
        self.assertEqual(health.parse_device_health(None), health.DeviceHealth(None, None, None, None))


class TestMaPlayerLink(unittest.TestCase):
    """Music Assistant player link helpers, exercised through `media/linking.py`."""

    CANDIDATES: ClassVar[list[tuple[str, str, str]]] = [
        ("media_player.desk_assistant", "Latter", "desk-assistant-p4-86"),
        ("media_player.mobile_assistant", "Latter", "mobile-assistant-s3-206"),
        ("media_player.office_amp", "Music Assistant", "Sendspin"),
    ]

    def test_configured_link_and_exact_suggestion(self) -> None:
        ma_ids = [c[0] for c in self.CANDIDATES]
        self.assertEqual(ma_link.configured_link("media_player.desk_assistant", ma_ids), "media_player.desk_assistant")
        self.assertIsNone(ma_link.configured_link("media_player.gone", ma_ids))
        self.assertIsNone(ma_link.configured_link("", ma_ids))
        self.assertIsNone(ma_link.configured_link(None, ma_ids))

        suggest = ma_link.suggest_ma_player
        self.assertEqual(suggest(("Latter", "desk-assistant-p4-86"), self.CANDIDATES), "media_player.desk_assistant")
        self.assertIsNone(suggest(("Latter", "remote-assistant-p4-35"), self.CANDIDATES))
        twins = [*self.CANDIDATES, ("media_player.desk_assistant_2", "Latter", "desk-assistant-p4-86")]
        self.assertIsNone(suggest(("Latter", "desk-assistant-p4-86"), twins))
        self.assertIsNone(suggest(("latter", "desk-assistant-p4-86"), self.CANDIDATES))
        self.assertFalse(hasattr(ma_link, "slug_matched_ma_player"))


class TestBoundRpcReassembler(unittest.TestCase):
    """Bound Device-to-HA text_sensor RPC framing, multi-part reassembly, and replay rejection."""

    def test_single_part_multipart_and_reboot_reset(self) -> None:
        rx = rpc_protocol.RpcReassembler()
        msg = rx.feed('1a2b3c4d:1:1/1|{"s":"area_action","d":{"entity_id":"light.kitchen","action":"turn_on"}}', now_mono=10.0)
        assert msg is not None
        self.assertEqual((msg[0], msg[1]["entity_id"]), ("area_action", "light.kitchen"))
        self.assertIsNone(
            rx.feed('1a2b3c4d:1:1/1|{"s":"area_action","d":{"entity_id":"light.kitchen","action":"turn_on"}}', now_mono=11.0)
        )

        body = json.dumps(
            {"s": "latter.device_hello", "d": {"manifest": {"v": 2, "label": "Café Living — Panel ✨", "w": 720, "h": 720}}},
            ensure_ascii=False,
        )
        p1, p2, p3 = body[:45], body[45:95], body[95:]
        self.assertIsNone(rx.feed(f"00aa11bb:7:1/3|{p1}", now_mono=20.0))
        self.assertIsNone(rx.feed(f"00aa11bb:7:2/3|{p2}", now_mono=20.1))
        done = rx.feed(f"00aa11bb:7:3/3|{p3}", now_mono=20.2)
        assert done is not None
        manifest = done[1]["manifest"]
        assert isinstance(manifest, dict)
        self.assertEqual((done[0], manifest["label"]), ("device_hello", "Café Living — Panel ✨"))

        self.assertIsNone(rx.feed('00aa11bb:8:1/2|{"s":"music_', now_mono=30.0))
        fresh = rx.feed('99ff0011:1:1/1|{"s":"calendar_fetch","d":{"req_id":4}}', now_mono=31.0)
        assert fresh is not None
        self.assertEqual((fresh[0], fresh[1]["req_id"]), ("calendar_fetch", 4))


class TestPerimeterSecurityPolicy(unittest.TestCase):
    """3-tier Perimeter Security Policy (auto/allow/require_pin/block) and PBKDF2 PIN verification."""

    def test_pbkdf2_pin_and_three_tier_enforcement(self) -> None:
        hashed = security_policy.hash_security_pin("2580")
        self.assertTrue(security_policy.verify_security_pin("2580", hashed))
        self.assertFalse(security_policy.verify_security_pin("2581", hashed))
        for bad_pin in ("123", "1234567890123", "12ab", ""):
            with self.assertRaises(ValueError):
                security_policy.hash_security_pin(bad_pin)

        self.assertFalse(security_policy.is_sensitive_perimeter_action("lock", "lock", entity_id="lock.front_door"))
        self.assertFalse(security_policy.is_sensitive_perimeter_action("cover", "open_cover", entity_id="cover.living_room_shades"))
        self.assertTrue(security_policy.is_sensitive_perimeter_action("lock", "unlock", entity_id="lock.front_door"))
        self.assertTrue(security_policy.is_sensitive_perimeter_action("alarm_control_panel", "disarm", entity_id="alarm_control_panel.home"))
        self.assertTrue(security_policy.is_sensitive_perimeter_action("cover", "open_cover", entity_id="cover.garage_door"))

        self.assertEqual(security_policy.effective_security_pin_policy("auto", is_roaming=False, alarm_has_code=False), "require_pin")
        self.assertEqual(security_policy.effective_security_pin_policy("auto", is_roaming=True, alarm_has_code=False), "allow")
        self.assertEqual(
            security_policy.check_perimeter_action_allowed("block", provided_code="2580", stored_pin_hash=hashed),
            (False, "security_action_blocked"),
        )
        self.assertEqual(
            security_policy.check_perimeter_action_allowed("require_pin", provided_code="", stored_pin_hash=hashed),
            (False, "security_pin_required"),
        )
        self.assertEqual(
            security_policy.check_perimeter_action_allowed("require_pin", provided_code="0000", stored_pin_hash=hashed),
            (False, "security_pin_invalid"),
        )
        self.assertEqual(
            security_policy.check_perimeter_action_allowed("require_pin", provided_code="2580", stored_pin_hash=hashed),
            (True, ""),
        )


class TestDiagnosticsSanitizer(unittest.TestCase):
    """Recursive diagnostics sanitizer strips sig=, payload, MAC keys, and calendar PII."""

    def test_sanitizes_sigs_macs_payloads_and_calendar_pii(self) -> None:
        raw = {
            "system_config": {
                "security_pin_hash": "pbkdf2_sha256$200000$aa$bb",
                "system_ble_uuid": "11223344-5566-7788-99aa-bbccddeeff00",
            },
            "ble_scanners": {
                "AA:BB:CC:DD:EE:FF": {"url": "http://192.168.1.10:8123/api/latter/camera/desk?w=466&sig=1762000000.deadbeef"}
            },
            "sensors": {
                "area_context": {"payload": "v3\x1f1\x1f1\x1fsecret", "rev": 4},
                "calendar_agenda": {"records": [["TODAY 14:30", "Doctor Appointment", "123 Private Way", "0"]], "event_count": 1},
            },
        }
        clean = diagnostics_sanitizer.sanitize_diagnostics_payload(raw)
        self.assertEqual(clean["system_config"]["security_pin_hash"], "**REDACTED**")
        self.assertEqual(clean["system_config"]["system_ble_uuid"], "**REDACTED**")
        self.assertNotIn("AA:BB:CC:DD:EE:FF", clean["ble_scanners"])
        scanner_key = next(iter(clean["ble_scanners"]))
        self.assertTrue(scanner_key.startswith("mac_"))
        self.assertIn("sig=**REDACTED**", clean["ble_scanners"][scanner_key]["url"])
        self.assertEqual(clean["sensors"]["area_context"]["payload"], "**REDACTED**")
        self.assertEqual(clean["sensors"]["calendar_agenda"]["records"], [["TODAY 14:30", "**REDACTED**", "**REDACTED**", "0"]])


def _flip_hex_char(hex_str: str, idx: int) -> str:
    pos = idx % len(hex_str)
    replacement = "0" if hex_str[pos] != "0" else "1"
    return f"{hex_str[:pos]}{replacement}{hex_str[pos + 1:]}"


class TestHypothesisProtocolAndSecurityFuzz(unittest.TestCase):
    """Property-based Hypothesis fuzzers for Protocol v3 delimiters, UTF-8 truncation, PIN AEAD wrap, and RPC chunking."""

    @settings(max_examples=100, deadline=None, database=None)
    @given(
        subfields=st.lists(_ADVERSARIAL_TEXT, min_size=1, max_size=8),
        records=st.lists(st.lists(_ADVERSARIAL_TEXT, min_size=1, max_size=5), min_size=1, max_size=6),
    )
    def test_v3_multi_tier_delimiter_escaping_and_record_packing(
        self, subfields: list[str], records: list[list[str]]
    ) -> None:
        escaped_parts = [protocol_codec.escape_v3_subfield(s) for s in subfields]
        for esc in escaped_parts:
            self.assertNotIn("|", esc)
            self.assertNotIn(";", esc)
            self.assertIsNone(_UNSAFE_CTRL_RE.search(esc))

        pipe_joined = "|".join(escaped_parts)
        semi_joined = ";".join(escaped_parts)
        self.assertEqual(
            [protocol_codec.unescape_v3_subfield(tok) for tok in pipe_joined.split("|")],
            [_UNSAFE_CTRL_RE.sub(" ", s) for s in subfields],
        )
        self.assertEqual(
            [protocol_codec.unescape_v3_subfield(tok) for tok in semi_joined.split(";")],
            [_UNSAFE_CTRL_RE.sub(" ", s) for s in subfields],
        )

        packer = protocol_codec.DomainPayloadPacker(epoch=123456)
        _rev, frame = packer.pack("area_context", *subfields)
        wire_fields = frame.split(protocol_codec.FIELD_SEP)
        self.assertEqual(len(wire_fields), 3 + len(subfields))
        for sf in wire_fields[3:]:
            self.assertIsNone(_UNSAFE_CTRL_RE.search(sf))

        encoded_recs = protocol_codec.encode_v3_records(records)
        rec_slices = encoded_recs.split(protocol_codec.RECORD_SEP)
        self.assertEqual(len(rec_slices), len(records))
        for rec_str, orig_rec in zip(rec_slices, records, strict=True):
            cols = rec_str.split(protocol_codec.SUBFIELD_SEP)
            self.assertEqual(len(cols), len(orig_rec))
            for col in cols:
                self.assertIsNone(_UNSAFE_CTRL_RE.search(col))

    @settings(max_examples=100, deadline=None, database=None)
    @given(
        text=_ADVERSARIAL_TEXT,
        max_bytes=st.integers(min_value=0, max_value=512),
    )
    def test_utf8_safe_truncate_never_splits_multibyte_sequences(self, text: str, max_bytes: int) -> None:
        out = protocol_codec.utf8_safe_truncate(text, max_bytes)
        encoded = out.encode("utf-8")
        self.assertLessEqual(len(encoded), max_bytes)
        self.assertTrue(text.startswith(out))
        if "\ufffd" not in text:
            self.assertNotIn("\ufffd", out)
        if len(out) < len(text):
            next_char_bytes = len((out + text[len(out)]).encode("utf-8"))
            self.assertGreater(next_char_bytes, max_bytes)
        self.assertEqual(protocol_codec.utf8_safe_truncate(text, -5), "")

    @settings(max_examples=100, deadline=None, database=None)
    @given(
        pins=st.lists(
            st.text(alphabet="0123456789", min_size=security_policy.MIN_PIN_LEN, max_size=security_policy.MAX_PIN_LEN),
            min_size=1,
            max_size=6,
        ),
        nonce_steps=st.lists(st.integers(min_value=1, max_value=5000), min_size=6, max_size=6),
        entity_id=st.sampled_from(["lock.front_door", "alarm_control_panel.site", "cover.garage_door"]),
        action=st.sampled_from(["unlock", "disarm", "open_cover"]),
        tamper_idx=st.integers(min_value=0, max_value=63),
    )
    def test_pin_session_key_wrap_unwrap_and_tamper_replay_rejection(
        self,
        pins: list[str],
        nonce_steps: list[int],
        entity_id: str,
        action: str,
        tamper_idx: int,
    ) -> None:
        key_id, key_bytes = security_policy.mint_pin_session_key()
        last_nonce = 0
        last_wrapped = ""
        for pin, step in zip(pins, nonce_steps, strict=False):
            nonce = last_nonce + step
            wrapped = security_policy.wrap_pin_code(key_id, key_bytes, nonce, entity_id, action, pin)
            self.assertTrue(security_policy.is_wrapped_pin_code(wrapped))
            unwrapped_pin, unwrapped_nonce = security_policy.unwrap_pin_code(
                key_id, key_bytes, last_nonce, entity_id, action, wrapped
            )
            self.assertEqual(unwrapped_pin, pin)
            self.assertEqual(unwrapped_nonce, nonce)

            with self.assertRaises(security_policy.PinWrapError) as replay_ctx:
                security_policy.unwrap_pin_code(key_id, key_bytes, nonce, entity_id, action, wrapped)
            self.assertEqual(replay_ctx.exception.reason, "replay")
            last_nonce = nonce
            last_wrapped = wrapped

        parts = last_wrapped.split(":")
        bad_ct = ":".join([parts[0], parts[1], parts[2], _flip_hex_char(parts[3], tamper_idx), parts[4]])
        with self.assertRaises(security_policy.PinWrapError) as ct_ctx:
            security_policy.unwrap_pin_code(key_id, key_bytes, 0, entity_id, action, bad_ct)
        self.assertEqual(ct_ctx.exception.reason, "bad_mac")

        bad_mac = ":".join([parts[0], parts[1], parts[2], parts[3], _flip_hex_char(parts[4], tamper_idx)])
        with self.assertRaises(security_policy.PinWrapError) as mac_ctx:
            security_policy.unwrap_pin_code(key_id, key_bytes, 0, entity_id, action, bad_mac)
        self.assertEqual(mac_ctx.exception.reason, "bad_mac")

        bad_kid = ":".join([parts[0], _flip_hex_char(parts[1], tamper_idx), parts[2], parts[3], parts[4]])
        with self.assertRaises(security_policy.PinWrapError) as kid_ctx:
            security_policy.unwrap_pin_code(key_id, key_bytes, 0, entity_id, action, bad_kid)
        self.assertEqual(kid_ctx.exception.reason, "key_mismatch")

        with self.assertRaises(security_policy.PinWrapError) as aad_ctx:
            security_policy.unwrap_pin_code(key_id, key_bytes, 0, f"{entity_id}_other", action, last_wrapped)
        self.assertEqual(aad_ctx.exception.reason, "bad_mac")

    @settings(max_examples=100, deadline=None, database=None)
    @given(data=st.data())
    def test_rpc_reassembler_chunking_out_of_order_duplicates_and_bounds(self, data: st.DataObject) -> None:
        svc = data.draw(st.sampled_from(["area_action", "device_hello", "set_device_prefs", "music_browse"]))
        payload_dict = data.draw(
            st.dictionaries(
                keys=st.text(alphabet="abcdefghij_", min_size=1, max_size=12),
                values=st.one_of(_ADVERSARIAL_TEXT, st.integers(-9999, 9999), st.booleans()),
                min_size=0,
                max_size=6,
            )
        )
        encoded_json = json.dumps({"s": f"latter.{svc}", "d": payload_dict}, ensure_ascii=False)
        max_parts = min(rpc_protocol.MAX_RPC_PARTS, max(1, len(encoded_json)))
        total = data.draw(st.integers(min_value=1, max_value=max_parts))

        cuts = sorted(data.draw(st.lists(st.integers(1, len(encoded_json) - 1), min_size=total - 1, max_size=total - 1, unique=True))) if total > 1 else []
        bounds = [0, *cuts, len(encoded_json)]
        slices = [encoded_json[bounds[i] : bounds[i + 1]] for i in range(total)]
        order = data.draw(st.permutations(list(range(1, total + 1))))
        dup_part = data.draw(st.integers(min_value=1, max_value=total))

        rx = rpc_protocol.RpcReassembler()
        boot_id = "deadbeef"
        seq = data.draw(st.integers(min_value=1, max_value=10000))
        seen: set[int] = set()
        result: tuple[str, dict[str, object]] | None = None
        for step_idx, part_no in enumerate(order):
            raw_frame = f"{boot_id}:{seq}:{part_no}/{total}|{slices[part_no - 1]}"
            out = rx.feed(raw_frame, now_mono=100.0 + step_idx * 0.05)
            seen.add(part_no)
            if len(seen) < total:
                self.assertIsNone(out)
                if part_no == dup_part:
                    self.assertIsNone(rx.feed(raw_frame, now_mono=100.0 + step_idx * 0.05 + 0.01))
            else:
                result = out
        assert result is not None
        self.assertEqual(result, (svc, payload_dict))
        # Replay after completion is suppressed
        self.assertIsNone(rx.feed(f"{boot_id}:{seq}:1/{total}|{slices[0]}", now_mono=120.0))

        # > MAX_RPC_PARTS rejected
        over_parts = data.draw(st.integers(min_value=rpc_protocol.MAX_RPC_PARTS + 1, max_value=64))
        self.assertIsNone(rx.feed(f"{boot_id}:{seq + 1}:1/{over_parts}|{{}}", now_mono=121.0))

        # > MAX_RPC_BYTES rejected (single-frame and accumulated multi-part)
        oversized_chunk = "x" * (rpc_protocol.MAX_RPC_BYTES // 2 + 64)
        self.assertIsNone(rx.feed(f"{boot_id}:{seq + 2}:1/1|{oversized_chunk * 2}", now_mono=122.0))
        self.assertIsNone(rx.feed(f"{boot_id}:{seq + 3}:1/2|{oversized_chunk}", now_mono=123.0))
        self.assertIsNone(rx.feed(f"{boot_id}:{seq + 3}:2/2|{oversized_chunk}", now_mono=123.1))
