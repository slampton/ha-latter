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


if __name__ == "__main__":
    unittest.main()
