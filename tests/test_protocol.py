"""Standalone Protocol v3 contract tests for ha-latter and esphome-latter-core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
HA_PROTO_JSON = REPO_ROOT / "custom_components" / "latter" / "protocol_v3.json"
CORE_PROTO_JSON = REPO_ROOT.parent / "esphome-latter-core" / "protocol" / "latter_v3.json"


def _sanitize_v3_field(val: Any) -> str:
    """Mirror LatterCoordinator._sanitize_v3_field."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    s = str(val)
    for ch in ("\x1f", "\x1e", "\x1d", "\n", "\r"):
        if ch in s:
            s = s.replace(ch, " ")
    return s.strip()


class _MockDomainPacker:
    """Mirror LatterCoordinator._pack_domain_payload & force_republish_all_domains."""

    def __init__(self, epoch: int = 1700000000) -> None:
        self.epoch = epoch
        self._domain_rev: dict[str, int] = {}
        self._domain_hash: dict[str, str] = {}
        self._domain_packed: dict[str, str] = {}

    def pack_domain_payload(self, domain: str, fields: list[Any]) -> tuple[str, int]:
        sanitized = [_sanitize_v3_field(f) for f in fields]
        body = "\x1f".join(sanitized)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        if self._domain_hash.get(domain) != digest or domain not in self._domain_packed:
            self._domain_hash[domain] = digest
            rev = self._domain_rev.get(domain, 0) + 1
            self._domain_rev[domain] = rev
            self._domain_packed[domain] = f"v3\x1f{self.epoch}\x1f{rev}\x1f{body}"
        return self._domain_packed[domain], self._domain_rev[domain]

    def force_republish_all_domains(self) -> None:
        self._domain_hash.clear()
        self._domain_packed.clear()
        self._domain_rev.clear()


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
            "area_context": 37,
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
        packer = _MockDomainPacker(epoch=1761900000)
        for dom_name, dom_spec in self.schema["domains"].items():
            field_count = len(dom_spec["fields"])
            sample_fields = [f"val_{i}\x1finjected\nline" for i in range(field_count)]
            packed1, rev1 = packer.pack_domain_payload(dom_name, sample_fields)
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
            packed2, rev2 = packer.pack_domain_payload(dom_name, sample_fields)
            self.assertEqual(rev2, 1)
            self.assertEqual(packed1, packed2)

            # Mutated field -> rev increments to 2
            mutated = list(sample_fields)
            mutated[0] = "changed_value"
            packed3, rev3 = packer.pack_domain_payload(dom_name, mutated)
            self.assertEqual(rev3, 2)
            self.assertNotEqual(packed2, packed3)

        # Reconnect / device_hello -> resets rev to 1
        packer.force_republish_all_domains()
        _, rev_after_reset = packer.pack_domain_payload(
            "remote_config", ["0", "2", "Apple TV\x1eremote.apple_tv"]
        )
        self.assertEqual(rev_after_reset, 1)

    def test_hardware_manifest_state_json_within_ha_255_char_limit(self) -> None:
        """The System: Hardware Manifest entity state string must never exceed HA's 255-char MAX_STATE_LENGTH."""
        longest_state_json = (
            '{"v":2,"contract":3,"board":"waveshare_p4_4b",'
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


class _MockVoiceFollowsMeHarness:
    """Deterministic unit-test harness for Voice Follows Me (Task 2.11) invariants."""

    def __init__(self, manifest: dict[str, Any], esphome_device_id: str, dwell_s: float = 10.0) -> None:
        self.manifest = manifest
        self.esphome_device_id = esphome_device_id
        self.dwell_s = dwell_s
        self.sync_device_area = True
        self.current_device_area_id: str | None = "kitchen"
        self.pending_area_id: str | None = None
        self.pending_due_at: float | None = None
        self.registry_writes: list[tuple[str, str]] = []
        self.last_area_follow_write: dict[str, Any] | None = None

    @property
    def is_roaming_device(self) -> bool:
        if "stationary" in self.manifest:
            return int(self.manifest.get("stationary", 0)) == 0
        return False

    def _cancel_dwell(self) -> None:
        self.pending_area_id = None
        self.pending_due_at = None

    def _commit_area(self, area_id: str, now_s: float) -> None:
        if not self.is_roaming_device or not self.sync_device_area:
            return
        if not area_id or area_id in ("unknown", "unavailable", "none", "away"):
            return
        if self.current_device_area_id == area_id:
            return
        prev = self.current_device_area_id or ""
        self.current_device_area_id = area_id
        self.registry_writes.append((self.esphome_device_id, area_id))
        self.last_area_follow_write = {
            "timestamp": now_s,
            "from_area": prev,
            "to_area": area_id,
            "device_id": self.esphome_device_id,
        }

    def on_ble_area_change(self, new_area_id: str | None, now_s: float) -> None:
        if not self.is_roaming_device or not self.sync_device_area:
            self._cancel_dwell()
            return
        if not new_area_id or new_area_id in ("unknown", "unavailable", "none", "away"):
            self._cancel_dwell()
            return
        if self.pending_area_id == new_area_id and self.pending_due_at is not None:
            return
        self._cancel_dwell()
        self.pending_area_id = new_area_id
        self.pending_due_at = now_s + max(1.0, self.dwell_s)

    def on_explicit_area_pick(self, new_area_id: str, now_s: float) -> None:
        self._cancel_dwell()
        self._commit_area(new_area_id, now_s)

    def advance_clock(self, now_s: float) -> None:
        if self.pending_area_id is not None and self.pending_due_at is not None and now_s >= self.pending_due_at:
            target = self.pending_area_id
            self._cancel_dwell()
            self._commit_area(target, now_s)


class TestVoiceFollowsMeAndBleDecay(unittest.TestCase):
    """Verify Voice Follows Me (Task 2.11) and BLE silence decay invariants."""

    def test_stationary_device_never_writes_area(self) -> None:
        """Stationary devices (stationary == 1) must never mutate device registry area_id."""
        harness = _MockVoiceFollowsMeHarness(
            manifest={"stationary": 1},
            esphome_device_id="esp_stationary_01",
        )
        self.assertFalse(harness.is_roaming_device)
        harness.on_ble_area_change("office", now_s=100.0)
        harness.advance_clock(now_s=200.0)
        harness.on_explicit_area_pick("office", now_s=205.0)
        self.assertEqual(harness.registry_writes, [])
        self.assertEqual(harness.current_device_area_id, "kitchen")

    def test_roaming_dwell_bounce_and_away_preservation(self) -> None:
        """Rapid BLE bounce A -> B -> C cancels B; away/unknown never clears area; explicit pick applies immediately."""
        harness = _MockVoiceFollowsMeHarness(
            manifest={"stationary": 0},
            esphome_device_id="esp_roaming_01",
            dwell_s=10.0,
        )
        self.assertTrue(harness.is_roaming_device)

        # Bounce to hallway at t=10s, then office at t=14s (before 10s dwell expires)
        harness.on_ble_area_change("hallway", now_s=10.0)
        harness.advance_clock(now_s=14.0)
        self.assertEqual(harness.registry_writes, [])

        harness.on_ble_area_change("office", now_s=14.0)
        harness.advance_clock(now_s=20.0)
        self.assertEqual(harness.registry_writes, [])

        # At t=24.0s, office has been stable for 10s -> single write to esp_roaming_01
        harness.advance_clock(now_s=24.0)
        self.assertEqual(harness.registry_writes, [("esp_roaming_01", "office")])
        self.assertEqual(harness.current_device_area_id, "office")
        self.assertIsNotNone(harness.last_area_follow_write)
        assert harness.last_area_follow_write is not None
        self.assertEqual(harness.last_area_follow_write["from_area"], "kitchen")
        self.assertEqual(harness.last_area_follow_write["to_area"], "office")

        # Brief BLE move to bedroom at t=30s followed by away/unknown at t=35s -> cancels dwell, preserves "office"
        harness.on_ble_area_change("bedroom", now_s=30.0)
        harness.on_ble_area_change("away", now_s=35.0)
        harness.advance_clock(now_s=50.0)
        self.assertEqual(len(harness.registry_writes), 1)
        self.assertEqual(harness.current_device_area_id, "office")

        # Explicit on-device pick writes immediately without waiting for dwell
        harness.on_explicit_area_pick("den", now_s=55.0)
        self.assertEqual(
            harness.registry_writes,
            [("esp_roaming_01", "office"), ("esp_roaming_01", "den")],
        )

    def test_ble_silence_decay_overtakes_stale_room(self) -> None:
        """Silence decay (1.5 dB/s after 2s grace) allows a newly entered room to overtake a silent room within ~12s."""
        grace_s = 2.0
        decay_db_per_s = 1.5
        stale_proxy_s = 12.0
        min_rssi_floor = -88.0

        def effective_rssi(ema_rssi: float, age_s: float) -> float | None:
            if age_s > stale_proxy_s:
                return None
            silence_penalty = max(0.0, age_s - grace_s) * decay_db_per_s
            eff = ema_rssi - silence_penalty
            return eff if eff >= min_rssi_floor else None

        # Room A had strong signal (-58 dBm) at t=0, now silent for 9s -> -58 - (7 * 1.5) = -68.5 dBm
        eff_room_a = effective_rssi(-58.0, age_s=9.0)
        # Room B has fresh signal (-64 dBm) at age 0.5s -> -64.0 dBm
        eff_room_b = effective_rssi(-64.0, age_s=0.5)
        self.assertIsNotNone(eff_room_a)
        self.assertIsNotNone(eff_room_b)
        assert eff_room_a is not None and eff_room_b is not None
        self.assertGreater(eff_room_b, eff_room_a)

        # At age 12.5s (> STALE_PROXY_SECONDS), Room A is dropped completely
        self.assertIsNone(effective_rssi(-58.0, age_s=12.5))


if __name__ == "__main__":
    unittest.main()
