"""Unit tests for RPC reassembly, HMAC signing, security policy, diagnostics redaction, Voice Follows Me, BLE math, Studio targeting, repairs, and MA linking."""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar
import unittest

from custom_components.latter import (
    diagnostics as diagnostics_sanitizer,
    identity as traits,
    protocol_policy as security_policy,
    repairs_keys as health,
)
from custom_components.latter.http import signing as resource_signing
from custom_components.latter.media import linking as ma_link
from custom_components.latter.presence import ble_math
from custom_components.latter.services import rpc_receiver as rpc_protocol
from custom_components.latter.studio import state_gates as studio_scope
from tests.conftest import LATTER_DIR

issue_ids = health
AreaFollowDwell = ble_math.AreaFollowDwell
FollowAction = ble_math.FollowAction
manifest_is_roaming = traits.manifest_is_roaming
STUDIO_JS = LATTER_DIR / "frontend" / "latter-studio.js"


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


class TestBleAreaScoring(unittest.TestCase):
    """BLE Area hysteresis, silence decay constants, deadband, and path-loss distance math (`ble_math.py`)."""

    def test_silence_decay_lets_new_room_overtake_and_stale_room_drops(self) -> None:
        """Silence decay constants and `decide_area` hysteresis govern Area takeover."""
        age_a = 9.0 - 0.0
        decayed_a = -58.0 - ble_math.SILENCE_DECAY_DB_PER_S * max(
            0.0, age_a - ble_math.SILENCE_GRACE_SECONDS
        )
        self.assertAlmostEqual(decayed_a, -58.0 - 7.0 * 1.5)
        scores = {"room_a": decayed_a, "room_b": -64.0}
        decision = ble_math.decide_area(scores, "room_a", 9.0, last_switch=0.0)
        assert decision is not None
        self.assertEqual(decision.best_area_id, "room_b")
        self.assertFalse(decision.switch, "a 4.5 dB lead is inside the 5 dB hysteresis")

        age_a2 = 10.0 - 0.0
        decayed_a2 = -58.0 - ble_math.SILENCE_DECAY_DB_PER_S * max(
            0.0, age_a2 - ble_math.SILENCE_GRACE_SECONDS
        )
        decision = ble_math.decide_area(
            {"room_a": decayed_a2, "room_b": -64.0}, "room_a", 10.0, last_switch=0.0
        )
        assert decision is not None
        self.assertTrue(decision.switch)
        self.assertEqual(decision.best_area_id, "room_b")
        self.assertGreater(12.5, ble_math.STALE_PROXY_SECONDS)

    def test_cross_floor_penalty(self) -> None:
        """Candidates on another floor lose CROSS_FLOOR_ATTENUATION_DB (6 dB)."""
        self.assertAlmostEqual(ble_math.CROSS_FLOOR_ATTENUATION_DB, 6.0)
        scores = {
            "upstairs": -60.0 - ble_math.CROSS_FLOOR_ATTENUATION_DB,
            "kitchen": -63.0,
        }
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

    def test_deadband_and_distance_roundtrip(self) -> None:
        """RSSI deadband is 3 dBm and continuous path-loss distance inverts cleanly."""
        self.assertFalse(ble_math.within_rssi_deadband(None, -70))
        self.assertTrue(ble_math.within_rssi_deadband(-70, -68))
        self.assertFalse(ble_math.within_rssi_deadband(-70, -67))
        self.assertAlmostEqual(ble_math.rssi_to_distance_m(-59.0), 1.0)
        dist = ble_math.continuous_distance_m(-68.0, 2.2)
        self.assertAlmostEqual(ble_math.distance_m_to_norm_dbm(dist, 2.2), -68.0, places=5)


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
        """A 2-day (48 h) payload URL signed at any time of day stays valid for 2 to 3 days."""
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
        for bad in (tampered, "malformed", None, "", ".", "abc.def", f"{sig}é", "\uff11\uff12\uff13.abcd", f"+{sig}"):
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
    match = re.search(rf"const {const_name}\s*=\s*new Set\(\[(.*?)\]\);", js_src, re.S)
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
        """The websocket type is the scope: every command belongs to exactly one; unknown commands fail."""
        scope = studio_scope.command_scope
        self.assertFalse(studio_scope.SYSTEM_COMMANDS & studio_scope.DEVICE_COMMANDS)
        for cmd in studio_scope.DEVICE_COMMANDS:
            self.assertEqual(scope(cmd), "device", cmd)
        for cmd in studio_scope.SYSTEM_COMMANDS:
            self.assertEqual(scope(cmd), "system", cmd)
        # Saves are split by scope; entity actions on a Device's own entities are Device commands.
        self.assertEqual(scope("save_system_config"), "system")
        self.assertEqual(scope("save_device_config"), "device")
        self.assertEqual(scope("esphome_entity_action"), "device")
        # System actions that act on one Device or Group name it in their payload, so they stay System commands.
        for cmd in ("update_group_baseline", "apply_batch_device_setting", "test_doorbell_speaker", "remove_device"):
            self.assertEqual(scope(cmd), "system", cmd)
        for retired in (
            "save_config",
            "system_entity_action",
            "log_client_error",
            "export_backup_json",
            "restore_backup",
            "format_disk",
            "capture_profile",
            "apply_profile",
            "seed_group_baseline",
            "sync_device_group",
            "set_group_device_setting",
        ):
            with self.assertRaises(studio_scope.UnknownStudioCommand):
                scope(retired)

    def test_studio_js_command_sets_match_backend(self) -> None:
        """latter-studio.js must classify every command exactly as studio/settings.py does."""
        js_src = STUDIO_JS.read_text(encoding="utf-8")
        self.assertEqual(_js_command_set(js_src, "SYSTEM_WS_COMMANDS"), set(studio_scope.SYSTEM_COMMANDS))
        self.assertEqual(_js_command_set(js_src, "DEVICE_WS_COMMANDS"), set(studio_scope.DEVICE_COMMANDS))
        sent = set(re.findall(r'command:\s*"([a-z_]+)"', js_src))
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

    CANDIDATES: ClassVar[list[tuple[str, str, str]]] = [
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
        twins = [*self.CANDIDATES, ("media_player.desk_assistant_2", "slampton", "desk-assistant-p4-86")]
        self.assertIsNone(suggest(("slampton", "desk-assistant-p4-86"), twins))
        self.assertIsNone(suggest(("slampton", None), self.CANDIDATES))
        self.assertIsNone(suggest((None, "desk-assistant-p4-86"), self.CANDIDATES))
        self.assertIsNone(suggest(("Slampton", "desk-assistant-p4-86"), self.CANDIDATES), "exact match only")

    def test_no_slug_matching_helper_exists(self) -> None:
        self.assertFalse(hasattr(ma_link, "slug_matched_ma_player"))



class TestBoundRpcReassembler(unittest.TestCase):
    """Bound Device-to-HA text_sensor RPC framing, multi-part reassembly, and replay rejection."""

    def test_single_part_and_replay_dedup(self) -> None:
        rx = rpc_protocol.RpcReassembler()
        msg = rx.feed('1a2b3c4d:1:1/1|{"s":"area_action","d":{"entity_id":"light.kitchen","action":"turn_on"}}', now_mono=10.0)
        assert msg is not None
        self.assertEqual(msg[0], "area_action")
        self.assertEqual(msg[1]["entity_id"], "light.kitchen")
        # Duplicate HA reconnect replay with identical (boot_id, seq) is ignored
        self.assertIsNone(
            rx.feed('1a2b3c4d:1:1/1|{"s":"area_action","d":{"entity_id":"light.kitchen","action":"turn_on"}}', now_mono=11.0)
        )

    def test_multipart_utf8_reassembly_and_reboot_reset(self) -> None:
        rx = rpc_protocol.RpcReassembler()
        body = json.dumps(
            {
                "s": "latter.device_hello",
                "d": {
                    "manifest": {
                        "v": 2,
                        "board": "waveshare_p4_86_panel",
                        "label": "Café Living — Panel ✨",
                        "w": 720,
                        "h": 720,
                    }
                },
            },
            ensure_ascii=False,
        )
        p1, p2, p3 = body[:45], body[45:95], body[95:]
        self.assertIsNone(rx.feed(f"00aa11bb:7:1/3|{p1}", now_mono=20.0))
        self.assertIsNone(rx.feed(f"00aa11bb:7:2/3|{p2}", now_mono=20.1))
        msg = rx.feed(f"00aa11bb:7:3/3|{p3}", now_mono=20.2)
        assert msg is not None
        self.assertEqual(msg[0], "device_hello")
        self.assertEqual(msg[1]["manifest"]["label"], "Café Living — Panel ✨")

        # Partial message from old boot is discarded on new boot_id
        self.assertIsNone(rx.feed('00aa11bb:8:1/2|{"s":"music_', now_mono=30.0))
        fresh = rx.feed('99ff0011:1:1/1|{"s":"calendar_fetch","d":{"req_id":4}}', now_mono=31.0)
        assert fresh is not None
        self.assertEqual((fresh[0], fresh[1]["req_id"]), ("calendar_fetch", 4))


class TestPerimeterSecurityPolicy(unittest.TestCase):
    """3-tier Perimeter Security Policy (auto/allow/require_pin/block) and PBKDF2 PIN verification."""

    def test_pbkdf2_pin_roundtrip_and_validation(self) -> None:
        hashed = security_policy.hash_security_pin("2580")
        self.assertTrue(security_policy.verify_security_pin("2580", hashed))
        self.assertFalse(security_policy.verify_security_pin("2581", hashed))
        self.assertFalse(security_policy.verify_security_pin("", hashed))
        for bad_pin in ("123", "1234567890123", "12ab", ""):
            with self.assertRaises(ValueError):
                security_policy.hash_security_pin(bad_pin)

    def test_closing_actions_always_permitted_even_when_blocked(self) -> None:
        for domain, verb, ent in (
            ("lock", "lock", "lock.front_door"),
            ("alarm_control_panel", "arm_away", "alarm_control_panel.home"),
            ("alarm_control_panel", "arm_home", "alarm_control_panel.home"),
            ("cover", "close_cover", "cover.garage_door"),
            ("cover", "open_cover", "cover.living_room_shades"),  # non-perimeter window shade
        ):
            self.assertFalse(
                security_policy.is_sensitive_perimeter_action(domain, verb, entity_id=ent),
                (domain, verb, ent),
            )
        for domain, verb, ent in (
            ("lock", "unlock", "lock.front_door"),
            ("alarm_control_panel", "disarm", "alarm_control_panel.home"),
            ("cover", "open_cover", "cover.garage_door"),
        ):
            self.assertTrue(
                security_policy.is_sensitive_perimeter_action(domain, verb, entity_id=ent),
                (domain, verb, ent),
            )

    def test_three_tier_opening_enforcement(self) -> None:
        pin_hash = security_policy.hash_security_pin("4826")
        # Stationary panels default 'auto' -> 'require_pin'
        self.assertEqual(
            security_policy.effective_security_pin_policy(
                "auto", is_roaming=False, alarm_has_code=False
            ),
            "require_pin",
        )
        # Roaming without alarm code defaults 'auto' -> 'allow'
        self.assertEqual(
            security_policy.effective_security_pin_policy(
                "auto", is_roaming=True, alarm_has_code=False
            ),
            "allow",
        )
        # Block rejects even with a valid PIN
        self.assertEqual(
            security_policy.check_perimeter_action_allowed(
                "block", provided_code="4826", stored_pin_hash=pin_hash
            ),
            (False, "security_action_blocked"),
        )
        # Require PIN rejects missing/wrong PIN, accepts matching PIN
        self.assertEqual(
            security_policy.check_perimeter_action_allowed(
                "require_pin", provided_code="", stored_pin_hash=pin_hash
            ),
            (False, "security_pin_required"),
        )
        self.assertEqual(
            security_policy.check_perimeter_action_allowed(
                "require_pin", provided_code="0000", stored_pin_hash=pin_hash
            ),
            (False, "security_pin_invalid"),
        )
        self.assertEqual(
            security_policy.check_perimeter_action_allowed(
                "require_pin", provided_code="4826", stored_pin_hash=pin_hash
            ),
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
                "AA:BB:CC:DD:EE:FF": {
                    "url": "http://192.168.1.10:8123/api/latter/camera/desk?w=466&sig=1762000000.deadbeef"
                }
            },
            "sensors": {
                "area_context": {"payload": "v3\x1f1\x1f1\x1fsecret", "rev": 4},
                "calendar_agenda": {
                    "records": [["TODAY 14:30", "Doctor Appointment", "123 Private Way", "0"]],
                    "event_count": 1,
                },
            },
        }
        clean = diagnostics_sanitizer.sanitize_diagnostics_payload(raw)
        self.assertEqual(clean["system_config"]["security_pin_hash"], "**REDACTED**")
        self.assertEqual(clean["system_config"]["system_ble_uuid"], "**REDACTED**")
        self.assertNotIn("AA:BB:CC:DD:EE:FF", clean["ble_scanners"])
        scanner_key = next(iter(clean["ble_scanners"]))
        self.assertTrue(scanner_key.startswith("mac_"))
        self.assertIn("sig=**REDACTED**", clean["ble_scanners"][scanner_key]["url"])
        self.assertNotIn("deadbeef", clean["ble_scanners"][scanner_key]["url"])
        self.assertEqual(clean["sensors"]["area_context"]["payload"], "**REDACTED**")
        self.assertEqual(
            clean["sensors"]["calendar_agenda"]["records"],
            [["TODAY 14:30", "**REDACTED**", "**REDACTED**", "0"]],
        )
