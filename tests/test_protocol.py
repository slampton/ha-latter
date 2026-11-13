"""Standalone tests for ha-latter: Protocol v3 contract, Voice Follows Me, BLE Area scoring, and URL signing.

They run without Home Assistant installed. Each production module under test (payloads.py,
area_follow.py, traits.py, ble_math.py, resource_signing.py, ...) is standard-library only and loaded by file path.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, ClassVar
import unittest

from custom_components.latter import (
    diagnostics as diagnostics_sanitizer,
    groups as reset_policy,
    http as resource_signing,
    identity,
    media as ma_link,
    presence,
    protocol as _PAYLOADS_MOD,
    repairs,
)
from custom_components.latter.studio import settings as studio_scope

health = repairs
issue_ids = repairs
rpc_protocol = identity
security_policy = _PAYLOADS_MOD
traits = identity
area_follow = presence
ble_math = presence

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"
HA_PROTO_JSON = LATTER_DIR / "protocol_v3.json"
CORE_PROTO_JSON = REPO_ROOT.parent / "esphome-latter-core" / "protocol" / "latter_v3.json"

DomainPayloadPacker = _PAYLOADS_MOD.DomainPayloadPacker
sanitize_v3_field = _PAYLOADS_MOD.sanitize_v3_field
AreaFollowDwell = area_follow.AreaFollowDwell
FollowAction = area_follow.FollowAction
manifest_is_roaming = traits.manifest_is_roaming
presence_beacon = area_follow
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
            "area_context": 38,
            "active_media": 17,
            "remote_config": 3,
            "weather_forecast": 14,
            "calendar_agenda": 3,
            "device_prefs": 48,
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


class TestCalendarAgendaRecords(unittest.TestCase):
    """calendar_agenda.summary: 0x1E-joined time|title|location|all_day records, sanitized and capped."""

    def setUp(self) -> None:
        from datetime import date, datetime

        self.p = _PAYLOADS_MOD
        self.today = date(2026, 11, 8)  # a Sunday
        self.dt = datetime

    def ev(self, y: int, m: int, d: int, hh: int = 0, mm: int = 0, **kw: Any) -> dict[str, Any]:
        return {"start_dt": self.dt(y, m, d, hh, mm), "summary": "Event", "location": "", "all_day": False, **kw}

    def test_spec_names_the_record_layout(self) -> None:
        spec = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))
        self.assertEqual(spec["record_separator"], self.p.RECORD_SEP)
        self.assertEqual(spec["separator"], self.p.FIELD_SEP)
        summary = spec["domains"]["calendar_agenda"]["fields"][0]
        self.assertEqual((summary["name"], summary["type"]), ("summary", "records"))
        self.assertIn("time|title|location|all_day", summary["description"])

    def test_time_labels(self) -> None:
        label = self.p.calendar_time_label
        t = self.today
        self.assertEqual(label(self.dt(2026, 11, 8, 14, 30), t, False), "TODAY 14:30")
        self.assertEqual(label(self.dt(2026, 11, 7, 23, 0), t, False), "TODAY 23:00")  # under way
        self.assertEqual(label(self.dt(2026, 11, 9, 9, 0), t, False), "TOM 09:00")
        self.assertEqual(label(self.dt(2026, 11, 13, 18, 0), t, False), "FRI 18:00")
        self.assertEqual(label(self.dt(2026, 11, 20, 8, 5), t, False), "NOV 20 08:05")
        self.assertEqual(label(self.dt(2026, 11, 8), t, True), "TODAY ALL DAY")
        self.assertEqual(label(self.dt(2026, 11, 9), t, True), "TOM ALL DAY")
        self.assertEqual(label(self.dt(2026, 11, 12), t, True), "THU ALL DAY")
        self.assertEqual(label(self.dt(2026, 12, 1), t, True), "DEC 01")
        for case in ("TODAY ALL DAY", "NOV 20 08:05", "WED 18:00"):
            self.assertLessEqual(len(case), self.p.CALENDAR_TIME_MAX)

    def test_encoding_layout_and_all_day(self) -> None:
        events = [
            self.ev(2026, 11, 8, 14, 30, summary="Dentist", location="12 Main St"),
            self.ev(2026, 11, 9, all_day=True, summary="Trip"),
        ]
        records = self.p.calendar_agenda_records(events, self.today)
        self.assertEqual(
            list(records),
            [("TODAY 14:30", "Dentist", "12 Main St", "0"), ("TOM ALL DAY", "Trip", "", "1")],
        )
        _rev, packed = DomainPayloadPacker(epoch=7).pack("calendar_agenda", records, 2, "TODAY 14:30: Dentist")
        fields = packed.split("\x1f")
        self.assertEqual(len(fields), 6)
        self.assertEqual(fields[3], "TODAY 14:30|Dentist|12 Main St|0\x1eTOM ALL DAY|Trip||1")
        self.assertEqual([r.split("|") for r in fields[3].split("\x1e")], [list(r) for r in records])
        self.assertEqual(fields[4:], ["2", "TODAY 14:30: Dentist"])

    def test_no_events_is_an_empty_field(self) -> None:
        records = self.p.calendar_agenda_records([], self.today)
        _rev, packed = DomainPayloadPacker(epoch=7).pack("calendar_agenda", records, 0, "")
        self.assertEqual(packed.split("\x1f")[3:], ["", "0", ""])

    def test_sanitizing_keeps_the_separators_out(self) -> None:
        nasty = "A|B\x1fC\x1eD\x1dE\nF\r\tG\x00H\u2028I  \u00a0 J"
        clean = self.p.sanitize_v3_subfield(nasty)
        self.assertEqual(clean, "A/B C D E F G H I J")
        records = self.p.calendar_agenda_records(
            [self.ev(2026, 11, 8, 9, 0, summary=nasty, location=" Room | 2\n")], self.today
        )
        title, location = records[0][1], records[0][2]
        for sub in records[0]:
            self.assertFalse(any(ch in sub for ch in "|\x1f\x1e\x1d\n\r\t\x00"), repr(sub))
        self.assertEqual(location, "Room / 2")
        self.assertTrue(title.startswith("A/B C D"))
        packed = DomainPayloadPacker(epoch=7).pack("calendar_agenda", records, 1, nasty)[1]
        self.assertEqual(len(packed.split("\x1f")), 6)
        self.assertEqual(packed.split("\x1f")[3].count("|"), 3)

    def test_caps(self) -> None:
        events = [
            self.ev(2026, 11, 8, 8 + i, 0, summary="T" * 200, location="L" * 200) for i in range(9)
        ]
        records = self.p.calendar_agenda_records(events, self.today)
        self.assertEqual(len(records), self.p.CALENDAR_MAX_RECORDS)
        self.assertEqual(self.p.CALENDAR_MAX_RECORDS, 5)
        for time_label, title, location, all_day in records:
            self.assertLessEqual(len(time_label), self.p.CALENDAR_TIME_MAX)
            self.assertEqual(len(title), self.p.CALENDAR_TITLE_MAX)
            self.assertEqual(len(location), self.p.CALENDAR_LOCATION_MAX)
            self.assertIn(all_day, ("0", "1"))
        # Cutting never leaves trailing whitespace.
        self.assertEqual(self.p.sanitize_v3_subfield("abc def", 4), "abc")

    def test_rev_is_deterministic(self) -> None:
        events = [self.ev(2026, 11, 8, 9, 0, summary="Standup"), self.ev(2026, 11, 10, 12, 0, summary="Lunch")]
        a = DomainPayloadPacker(epoch=7)
        b = DomainPayloadPacker(epoch=7)
        r1 = a.pack("calendar_agenda", self.p.calendar_agenda_records(events, self.today), 2, "x")
        r2 = a.pack("calendar_agenda", self.p.calendar_agenda_records(list(events), self.today), 2, "x")
        r3 = b.pack("calendar_agenda", self.p.calendar_agenda_records(events, self.today), 2, "x")
        self.assertEqual(r1, r2)
        self.assertEqual(r1, r3)
        r4 = a.pack("calendar_agenda", self.p.calendar_agenda_records(events[:1], self.today), 1, "x")
        self.assertEqual(r4[0], r1[0] + 1)

    def test_plain_lists_are_not_records(self) -> None:
        # Only an explicit V3Records is encoded as records; a plain string keeps the old field sanitizing.
        self.assertEqual(sanitize_v3_field("a\x1eb"), "a b")
        self.assertEqual(sanitize_v3_field(self.p.V3Records([("a", "b"), ("c", "d")])), "a|b\x1ec|d")


class TestRecordsFields(unittest.TestCase):
    """Every "records" field: 0x1E between records, '|' between subfields, the spec's subfield order."""

    def setUp(self) -> None:
        self.p = _PAYLOADS_MOD
        self.spec = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))

    def layout(self, domain: str, field: str) -> list[str]:
        """The subfield names a records field's spec description lists (the a|b|c token)."""
        desc = next(f for f in self.spec["domains"][domain]["fields"] if f["name"] == field)["description"]
        return next(tok for tok in desc.split() if "|" in tok).split("|")

    def test_every_records_field_is_built_with_v3_records(self) -> None:
        records_fields = {
            (dom, f["name"])
            for dom, spec in self.spec["domains"].items()
            for f in spec["fields"]
            if f["type"] == "records"
        }
        self.assertEqual(
            records_fields,
            {
                ("area_context", "cameras_summary"),
                ("area_context", "intercom_targets_summary"),
                ("remote_config", "slots_summary"),
                ("weather_forecast", "forecast_5d"),
                ("calendar_agenda", "summary"),
            },
        )
        ctx_src = (LATTER_DIR / "areas.py").read_text(encoding="utf-8")
        rem_src = (LATTER_DIR / "remotes.py").read_text(encoding="utf-8")
        feeds_src = (LATTER_DIR / "feeds.py").read_text(encoding="utf-8")
        for builder in ("camera_records(", "intercom_target_records("):
            self.assertIn(builder, ctx_src)
        self.assertIn("remote_slot_records(", rem_src)
        self.assertIn("forecast_records(", feeds_src)
        self.assertIn("calendar_agenda_records(", feeds_src)

    def test_cameras(self) -> None:
        self.assertEqual(self.layout("area_context", "cameras_summary"), ["entity_id", "name", "area_id", "snapshot_url"])
        recs = self.p.camera_records(
            [
                {"entity_id": "camera.front", "name": "Front | Door\n", "area_id": "porch", "snapshot_url": "http://h/x?sig=1"},
                {"entity_id": "camera.yard", "name": "Y" * 80, "area_id": "", "snapshot_url": "http://h/y"},
            ]
        )
        self.assertEqual(recs[0], ("camera.front", "Front / Door", "porch", "http://h/x?sig=1"))
        self.assertEqual(recs[1][1], "Y" * self.p.CAMERA_NAME_MAX)
        self.assertEqual(recs[1][2], "")
        self.assertEqual(self.p.encode_v3_records(recs).count("\x1e"), 1)
        many = [{"entity_id": f"camera.c{i}", "name": "c", "area_id": "", "snapshot_url": ""} for i in range(15)]
        self.assertEqual(len(self.p.camera_records(many)), self.p.CAMERAS_MAX_RECORDS)
        self.assertEqual(self.p.encode_v3_records(self.p.camera_records([])), "")

    def test_intercom_targets(self) -> None:
        self.assertEqual(self.layout("area_context", "intercom_targets_summary"), ["target_id", "label", "kind"])
        recs = self.p.intercom_target_records(
            [
                {"target_id": "all", "label": "All Devices", "kind": "all"},
                {"target_id": "kitchen", "label": "Kitchen|Display", "kind": "device"},
            ]
        )
        self.assertEqual(list(recs), [("all", "All Devices", "all"), ("kitchen", "Kitchen/Display", "device")])
        with self.assertRaises(ValueError):
            self.p.intercom_target_records([{"target_id": "x", "label": "x", "kind": "speaker"}])
        for kind in self.p.INTERCOM_KINDS:
            self.assertIn(kind, next(f for f in self.spec["domains"]["area_context"]["fields"] if f["name"] == "intercom_targets_summary")["description"])

    def test_remote_slots(self) -> None:
        self.assertEqual(
            self.layout("remote_config", "slots_summary"),
            ["index", "label", "entity_id", "kind", "area_id", "state"],
        )
        recs = self.p.remote_slot_records(
            [
                {"index": 1, "label": "Living TV", "entity_id": "remote.living_tv", "area_id": "living", "state": "on"},
                {"index": 3, "label": "Bedroom\tSpeaker", "entity_id": "media_player.bed", "area_id": "", "state": "idle"},
            ]
        )
        self.assertEqual(
            list(recs),
            [
                ("1", "Living TV", "remote.living_tv", "remote", "living", "on"),
                ("3", "Bedroom Speaker", "media_player.bed", "media_player", "", "idle"),
            ],
        )
        with self.assertRaises(ValueError):
            self.p.remote_slot_records([{"index": 1, "label": "x", "entity_id": "switch.tv", "area_id": "", "state": "on"}])

    def test_forecast(self) -> None:
        self.assertEqual(self.layout("weather_forecast", "forecast_5d"), ["day", "cond", "high", "low"])
        days = [
            {"day": "SUN", "condition": "partlycloudy", "high": 71.6, "low": 55.4},
            {"day": "MON", "condition": "rainy", "high": None, "low": 50},
        ] + [{"day": "TUE", "condition": "sunny", "high": 70, "low": 60}] * 6
        recs = self.p.forecast_records(days)
        self.assertEqual(recs[0], ("SUN", "partlycloudy", "72", "55"))
        self.assertEqual(recs[1], ("MON", "rainy", "", "50"))
        self.assertEqual(len(recs), self.p.FORECAST_MAX_RECORDS)
        packed = DomainPayloadPacker(epoch=9).pack(
            "weather_forecast", "sunny", 70, None, None, None, 72, 55, recs,
            "above_horizon", 42.5, 180.0, "2026-11-09T06:45:00Z", "2026-11-08T17:02:00Z", "waxing_gibbous",
        )[1]
        fields = packed.split("\x1f")
        self.assertEqual(len(fields), 17)
        self.assertEqual(fields[10].split("\x1e")[0], "SUN|partlycloudy|72|55")
        self.assertEqual(fields[4:6], ["70", ""])
        self.assertEqual(fields[11], "above_horizon")
        self.assertEqual(fields[16], "waxing_gibbous")

    def test_records_revs_are_content_hashed(self) -> None:
        packer = DomainPayloadPacker(epoch=9)
        slots = [{"index": 1, "label": "TV", "entity_id": "remote.tv", "area_id": "", "state": "on"}]
        r1 = packer.pack("remote_config", 1, 1, self.p.remote_slot_records(slots))
        r2 = packer.pack("remote_config", 1, 1, self.p.remote_slot_records(list(slots)))
        self.assertEqual(r1, r2)
        slots[0]["state"] = "off"
        r3 = packer.pack("remote_config", 1, 1, self.p.remote_slot_records(slots))
        self.assertEqual(r3[0], r1[0] + 1)


class TestAbsentValues(unittest.TestCase):
    """Protocol v3 sends "" for a missing value: no none/None/NONE/unknown/Idle placeholders, no made-up states."""

    SOURCES = (
        "coordinator.py",
        "areas.py",
        "http.py",
        "feeds.py",
        "protocol.py",
        "media_browse.py",
    )
    FORBIDDEN = (
        r'return "none"',
        r'= "none"',
        r'else "none"',
        r'or "Idle"',
        r'or "None"',
        r'"art_url": "none"',
        r'"state": "none"',
        r'"Local Speaker"',
        r'"thermostat_state": "off"',
        r'"lock_state": "locked"',
        r'"garage_state": "closed"',
        r'"vacuum_state": "docked"',
        r'"condition": "unknown"',
        r'"weather_forecast",\s*"unknown"',
        r'"remote_config", clamped_active, 0',
        r'\.temperature", 0\.0|"high", 0\.0|"low", 0\.0',
        # Nothing accepts "None"/"Idle" back from the device either (ESPHome's text sensors publish "").
        r'[=!]= "None"',
        r'"Idle"',
    )

    def test_ha_value(self) -> None:
        ha_value = _PAYLOADS_MOD.ha_value
        for absent in (None, "", "unknown", "Unavailable", " unknown "):
            self.assertEqual(ha_value(absent), "", repr(absent))
        for real in ("off", "locked", "disarmed", 0, 0.0, "None of these"):
            self.assertEqual(ha_value(real), real)
        self.assertEqual(sanitize_v3_field(ha_value(None)), "")

    def test_spec_states_the_rule(self) -> None:
        spec = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))
        self.assertIn("empty string", spec["absent_value"])
        state = next(f for f in spec["domains"]["active_media"]["fields"] if f["name"] == "state")
        self.assertIn("buffering", state["description"])
        self.assertNotRegex(json.dumps(spec["domains"]), r'\b(NONE|none)\b(?![,)])')

    def test_no_placeholders_in_payload_sources(self) -> None:
        for name in self.SOURCES:
            src = (LATTER_DIR / name).read_text(encoding="utf-8")
            for pat in self.FORBIDDEN:
                self.assertNotRegex(src, pat, f"{name}: {pat}")
        ctx_src = (LATTER_DIR / "areas.py").read_text(encoding="utf-8")
        # The area_context payload sends "" without an Area (the HA sensor state may still say Unassigned).
        self.assertIn('area_entry.name if area_entry else "",', ctx_src)


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
        """A 2-day (48 h) payload URL signed at any time of day stays valid for 2 to 3 days."""
        self.assertEqual(resource_signing.PAYLOAD_TTL_DAYS, 2)
        for offset in (0, 43200, 86399):
            now = self.DAY_START + offset
            exp = resource_signing.day_bucketed_expiry(now, resource_signing.PAYLOAD_TTL_DAYS)
            self.assertEqual(exp % 86400, 0)
            self.assertGreaterEqual(exp - now, 2 * 86400)
            self.assertLessEqual(exp - now, 3 * 86400)
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
        # System actions that act on one Device name it in their payload, so they stay System commands.
        for cmd in ("seed_group_baseline", "test_doorbell_speaker", "remove_device", "sync_device_group"):
            self.assertEqual(scope(cmd), "system", cmd)
        for retired in ("save_config", "log_client_error", "export_backup_json", "restore_backup", "format_disk", "capture_profile", "apply_profile"):
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


def _const_conf_values() -> set[str]:
    """Return every CONF_* string value defined in const.py."""
    import ast

    values: set[str] = set()
    for node in ast.parse((LATTER_DIR / "const.py").read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(node, "value", None), ast.Constant):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id.startswith("CONF_") for t in targets):
                values.add(str(node.value.value))
    return values


class TestResetPolicy(unittest.TestCase):
    """Reset to defaults: keep/reset decision and flag validation, exercised through `reset_policy.py`."""

    CURRENT: ClassVar[dict[str, Any]] = {
        "esphome_device_id": "dev123",
        "mac": "aa:bb:cc:dd:ee:ff",
        "device_slug": "desk_assistant",
        "ma_player_entity": "media_player.desk_assistant",
        "dock_apps": "music,games",
        "wallpaper_source": "upload:desk/beach.jpg",
        "wallpaper_favorites": ["a", "b"],
        "device_custom_color": "#FF0000",
        "default_area": "kitchen",
        "native_ble_tracking": True,
        "custom_palettes": [{"name": "x", "hex": "#000000"}],
    }
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "device_group": "wall_panels",
        "default_page_size": 3,
        "native_ble_tracking": False,
        "ble_auto_switch": False,
        "sync_device_area": False,
        "area_handoff": False,
        "default_area": "office",
        "dock_apps": "music,alarm,area,remote,games,tools",
        "default_speaker": "media_player.desk_assistant_music",
        "esphome_device_id": "must_not_win",
    }

    def test_device_reset_keeps_identity_and_link_and_restores_defaults(self) -> None:
        out = reset_policy.reset_subentry_data(
            self.CURRENT, self.DEFAULTS, reset_policy.DEVICE_IDENTITY_KEYS
        )
        for key in ("esphome_device_id", "mac", "device_slug", "ma_player_entity"):
            self.assertEqual(out[key], self.CURRENT[key], key)
        self.assertEqual(out["dock_apps"], self.DEFAULTS["dock_apps"])
        self.assertEqual(out["default_area"], "office")
        self.assertFalse(out["native_ble_tracking"])
        for dropped in ("wallpaper_source", "wallpaper_favorites", "device_custom_color", "custom_palettes"):
            self.assertNotIn(dropped, out)

    def test_ble_tag_reset_keeps_name_and_address(self) -> None:
        current = {"device_slug": "seans_phone", "ble_target_address": "AA:BB:CC:DD:EE:FF", "assigned_person": "person.sean"}
        defaults = {"device_slug": "x", "ble_target_address": "y", "assigned_person": "", "native_ble_tracking": True}
        out = reset_policy.reset_subentry_data(current, defaults, reset_policy.BLE_TAG_IDENTITY_KEYS)
        self.assertEqual(out["device_slug"], "seans_phone")
        self.assertEqual(out["ble_target_address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(out["assigned_person"], "")
        self.assertTrue(out["native_ble_tracking"])

    def test_missing_identity_keys_are_not_invented(self) -> None:
        out = reset_policy.reset_subentry_data({"device_slug": "x"}, {}, reset_policy.DEVICE_IDENTITY_KEYS)
        self.assertEqual(out, {"device_slug": "x"})

    def test_flag_validation(self) -> None:
        err = reset_policy.reset_flags_error
        self.assertIsNone(err(True, True, is_ble_tag=False))
        self.assertIsNone(err(True, False, is_ble_tag=False))
        self.assertIsNone(err(False, True, is_ble_tag=False))
        self.assertIsNone(err(False, True, is_ble_tag=True))
        self.assertEqual(err(False, False, is_ble_tag=False), "reset_nothing_selected")
        self.assertEqual(err(False, False, is_ble_tag=True), "reset_nothing_selected")
        self.assertEqual(err(True, True, is_ble_tag=True), "reset_ble_tag_has_no_device_settings")

    def test_field_lists_name_real_subentry_keys(self) -> None:
        """Every enumerated key is a real config key (const.py CONF_* value), and identity lists only share device_slug."""
        conf_values = _const_conf_values() | {"mac"}
        keys = reset_policy.DEVICE_IDENTITY_KEYS + reset_policy.BLE_TAG_IDENTITY_KEYS
        self.assertFalse(set(keys) - conf_values, sorted(set(keys) - conf_values))
        self.assertEqual(set(reset_policy.DEVICE_IDENTITY_KEYS) & set(reset_policy.BLE_TAG_IDENTITY_KEYS), {"device_slug"})

    def test_reset_error_keys_are_translated(self) -> None:
        strings = json.loads((LATTER_DIR / "strings.json").read_text(encoding="utf-8"))
        for key in ("reset_nothing_selected", "reset_ble_tag_has_no_device_settings", "factory_reset_unsupported", "factory_reset_failed"):
            self.assertIn(key, strings["exceptions"], key)


class TestDevicePrefsProtocol(unittest.TestCase):
    """Protocol v3 `device_prefs` packing, offline `dirty_prefs` parsing, and `PowerProfile` cascade."""

    def test_pack_device_prefs_matches_schema_field_count_and_ble_consolidation(self) -> None:
        schema = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))
        spec_fields = schema["domains"]["device_prefs"]["fields"]
        fields = _PAYLOADS_MOD.pack_device_prefs_fields(
            9,
            {
                "power_profile": "Handheld Roaming",
                "clock_face": "Modern Roman (Analog)",
                "alert_volume": 75,
            },
            native_ble_tracking=True,
            custom_color_hex="#112233",
            is_round_display=False,
        )
        self.assertEqual(len(fields), len(spec_fields))
        self.assertEqual(fields[0], 9)
        idx_by_name = {f["name"]: i for i, f in enumerate(spec_fields)}
        # Rectangular display clamps "Modern Roman (Analog)" to "Minimal Digital"
        self.assertEqual(fields[idx_by_name["clock_face"]], "Minimal Digital")
        self.assertIs(fields[idx_by_name["ble_beacon_enabled"]], True)
        self.assertEqual(fields[idx_by_name["theme_color_hex"]], "#112233")
        self.assertEqual(fields[idx_by_name["alert_volume"]], 75)

        packer = _PAYLOADS_MOD.DomainPayloadPacker()
        _rev, wire = packer.pack("device_prefs", *fields)
        wire_parts = wire.split("\x1f")
        self.assertEqual(len(wire_parts), 3 + len(spec_fields))
        self.assertEqual(wire_parts[3 + idx_by_name["ble_beacon_enabled"]], "1")
        self.assertEqual(wire_parts[3 + idx_by_name["clock_face"]], "Minimal Digital")

    def test_parse_dirty_prefs_records_validates_and_maps_ble_beacon(self) -> None:
        raw = "\x1e".join(
            [
                "alert_volume=65",
                "ble_beacon_enabled=0",
                "docked_screensaver=1",
                "color_profile=NotARealProfile",
                "clock_face=Modern Digital (Bold)",
            ]
        )
        parsed = _PAYLOADS_MOD.parse_dirty_prefs_records(raw)
        self.assertEqual(
            parsed,
            {
                "alert_volume": 65,
                "native_ble_tracking": False,
                "docked_screensaver": True,
                "clock_face": "Modern Digital (Bold)",
            },
        )

    def test_power_profile_cascade_and_custom_flip(self) -> None:
        cascaded = studio_scope.clean_device_settings({"power_profile": "Always-On Wall / Desk"})
        self.assertEqual(cascaded["power_profile"], "Always-On Wall / Desk")
        self.assertEqual(cascaded["wake_word_mode"], "Always On")
        self.assertEqual(cascaded["battery_screen_timeout"], "Never")
        self.assertEqual(cascaded["battery_hibernate_timeout"], "Disabled")

        flipped = studio_scope.clean_device_settings(
            {"tap_to_wake": "Disabled"},
            current=cascaded,
        )
        self.assertEqual(flipped["tap_to_wake"], "Disabled")
        self.assertEqual(flipped["power_profile"], "Custom")


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
            ("doorbell", "unlock_door", "camera.front_door"),
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


if __name__ == "__main__":
    unittest.main()
