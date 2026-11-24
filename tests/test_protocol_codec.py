"""Unit tests for Protocol v3 schema parity, DomainPayloadPacker, V3Records builders, and absent values."""

from __future__ import annotations

import json
from typing import Any
import unittest

from custom_components.latter import protocol_codec as _PAYLOADS_MOD, protocol_policy
from tests.conftest import LATTER_DIR, REPO_ROOT, read_py_tree

HA_PROTO_JSON = LATTER_DIR / "protocol_v3.json"
CORE_PROTO_JSON = REPO_ROOT.parent / "esphome-latter-core" / "protocol" / "latter_v3.json"
DomainPayloadPacker = _PAYLOADS_MOD.DomainPayloadPacker
sanitize_v3_field = _PAYLOADS_MOD.sanitize_v3_field


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
            "area_context": 40,
            "active_media": 21,
            "remote_config": 3,
            "weather_forecast": 15,
            "calendar_agenda": 4,
            "device_prefs": 75,
            "shortcuts": 5,
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

    def test_lyrics_track_key_escapes_wire_delimiters(self) -> None:
        """Lyrics track_key escapes `\\`, `|`, and `;` symmetrically with firmware `build_music_track_key()`."""
        from custom_components.latter.media.lyrics import build_lyrics_track_key

        self.assertEqual(build_lyrics_track_key("", "Artist"), "")
        self.assertEqual(
            build_lyrics_track_key("Would?", "Alice In Chains"),
            "Would?|Alice In Chains",
        )
        self.assertEqual(
            build_lyrics_track_key("Part 1 | Part 2; C\\D", "A | B"),
            "Part 1 \\p Part 2\\s C\\\\D|A \\p B",
        )

    def test_show_notification_includes_alert_id(self) -> None:
        """latter_show_notification device action must include alert_id for deduplication."""
        notif_vars = (
            self.schema.get("device_actions", {})
            .get("latter_show_notification", {})
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
        nasty = "A|B\\C;D\x1fE\x1eF\x1dG\nH\r\tI\x00J\u2028K  \u00a0 L"
        clean = self.p.sanitize_v3_subfield(nasty)
        self.assertEqual(clean, "A\\pB\\\\C\\sD E F G H I J K L")
        self.assertEqual(self.p.unescape_v3_subfield(clean), "A|B\\C;D E F G H I J K L")
        records = self.p.calendar_agenda_records(
            [self.ev(2026, 11, 8, 9, 0, summary=nasty, location=" Area | 2; B\\1\n")], self.today
        )
        title, location = records[0][1], records[0][2]
        for sub in records[0]:
            self.assertFalse(any(ch in sub for ch in "|;\x1f\x1e\x1d\n\r\t\x00"), repr(sub))
        self.assertEqual(location, "Area \\p 2\\s B\\\\1")
        self.assertEqual(self.p.unescape_v3_subfield(location), "Area | 2; B\\1")
        self.assertTrue(title.startswith("A\\pB\\\\C\\sD E F"))
        packed = DomainPayloadPacker(epoch=7).pack("calendar_agenda", records, 1, nasty)[1]
        self.assertEqual(len(packed.split("\x1f")), 6)
        # Pre-sanitized V3Records must NOT be double-escaped when packed!
        self.assertEqual(packed.split("\x1f")[3].count("|"), 3)
        self.assertIn("Area \\p 2\\s B\\\\1", packed.split("\x1f")[3])
        self.assertNotIn("Area \\\\p", packed.split("\x1f")[3])

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
                ("area_context", "broadcast_phrases"),
                ("area_context", "thermostats_summary"),
                ("area_context", "locks_summary"),
                ("area_context", "garages_summary"),
                ("area_context", "vacuums_summary"),
                ("area_context", "area_climates_summary"),
                ("remote_config", "slots_summary"),
                ("weather_forecast", "forecast_5d"),
                ("calendar_agenda", "summary"),
                ("calendar_agenda", "calendars_meta"),
                ("calendar_agenda", "locations_catalog"),
                ("shortcuts", "dock_items"),
                ("shortcuts", "pinned_items"),
            },
        )
        ctx_src = read_py_tree("areas")
        rem_src = read_py_tree("remotes.py")
        feeds_src = read_py_tree("feeds.py")
        coord_src = read_py_tree("coordinator")
        for builder in (
            "camera_records(",
            "broadcast_phrase_records(",
            "thermostat_records(",
            "entry_records(",
            "vacuum_records(",
            "area_climate_records(",
        ):
            self.assertIn(builder, ctx_src)
        self.assertIn("remote_slot_records(", rem_src)
        self.assertIn("forecast_records(", feeds_src)
        self.assertIn("calendar_agenda_records(", feeds_src)
        self.assertIn("calendar_sources_records(", feeds_src)
        self.assertIn("calendar_locations_records(", feeds_src)
        self.assertIn("shortcut_records(", coord_src)

    def test_cameras(self) -> None:
        self.assertEqual(
            self.layout("area_context", "cameras_summary"),
            ["entity_id", "name", "area_id", "caps", "unlock_entity"],
        )
        recs = self.p.camera_records(
            [
                {
                    "entity_id": "camera.front",
                    "name": "Front | Door\n",
                    "area_id": "porch",
                    "caps": 63,
                    "unlock_entity": "lock.front_door",
                },
                {"entity_id": "camera.yard", "name": "Y" * 80, "area_id": "", "caps": 1},
            ]
        )
        self.assertEqual(
            recs[0], ("camera.front", "Front \\p Door", "porch", "63", "lock.front_door")
        )
        self.assertEqual(recs[1][1], "Y" * self.p.CAMERA_NAME_MAX)
        self.assertEqual(recs[1][2], "")
        self.assertEqual(recs[1][3], "1")
        self.assertEqual(recs[1][4], "")
        self.assertEqual(self.p.encode_v3_records(recs).count("\x1e"), 1)
        many = [{"entity_id": f"camera.c{i}", "name": "c", "area_id": "", "caps": 0} for i in range(15)]
        self.assertEqual(len(self.p.camera_records(many)), self.p.CAMERAS_MAX_RECORDS)
        self.assertEqual(self.p.encode_v3_records(self.p.camera_records([])), "")

    def test_broadcast_phrases(self) -> None:
        recs = self.p.broadcast_phrase_records(
            [
                "Dinner is ready",
                "  Come upstairs  ",
                "Dinner is ready",
                "",
                "A" * 80,
            ]
        )
        self.assertEqual(
            list(recs),
            [("Dinner is ready",), ("Come upstairs",), ("A" * self.p.BROADCAST_PHRASE_MAX_LEN,)],
        )
        self.assertEqual(
            len(self.p.broadcast_phrase_records([f"Phrase {i}" for i in range(20)])),
            self.p.BROADCAST_PHRASES_MAX_RECORDS,
        )
        self.assertEqual(self.p.encode_v3_records(self.p.broadcast_phrase_records([])), "")

    def test_home_hub_and_area_climate_records(self) -> None:
        self.assertEqual(
            self.layout("area_context", "thermostats_summary"),
            ["entity_id", "name", "area_id", "state", "target_temp", "current_temp", "caps"],
        )
        self.assertEqual(self.layout("area_context", "locks_summary"), ["entity_id", "name", "area_id", "state"])
        self.assertEqual(self.layout("area_context", "garages_summary"), ["entity_id", "name", "area_id", "state"])
        self.assertEqual(
            self.layout("area_context", "vacuums_summary"),
            ["entity_id", "name", "area_id", "state", "caps"],
        )
        self.assertEqual(
            self.layout("area_context", "area_climates_summary"),
            ["entity_id", "name", "state", "target_temp", "current_temp", "caps"],
        )
        therms = self.p.thermostat_records(
            [{"entity_id": "climate.main", "name": "Main|Zone", "area_id": "living", "state": "heat", "target_temp": 72, "current_temp": 70.5, "caps": 7}]
        )
        self.assertEqual(list(therms), [("climate.main", "Main\\pZone", "living", "heat", "72", "70.5", "7")])
        locks = self.p.entry_records(
            [{"entity_id": "lock.front", "name": "Front Door", "area_id": "entry", "state": "locked"}],
            max_records=self.p.LOCKS_MAX_RECORDS,
        )
        self.assertEqual(list(locks), [("lock.front", "Front Door", "entry", "locked")])
        vacs = self.p.vacuum_records(
            [{"entity_id": "vacuum.main", "name": "Downstairs Vac", "area_id": "living", "state": "docked", "caps": 7}]
        )
        self.assertEqual(list(vacs), [("vacuum.main", "Downstairs Vac", "living", "docked", "7")])
        climates = self.p.area_climate_records(
            [{"entity_id": "climate.office", "name": "Office Split", "state": "cool", "target_temp": 70, "current_temp": 73.2, "caps": 15}]
        )
        self.assertEqual(list(climates), [("climate.office", "Office Split", "cool", "70", "73.2", "15")])

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
            "above_horizon", 42.5, 180.0, "2026-11-09T06:45:00Z", "2026-11-08T17:02:00Z", "waxing_gibbous", "F",
        )[1]
        fields = packed.split("\x1f")
        self.assertEqual(len(fields), 18)
        self.assertEqual(fields[10].split("\x1e")[0], "SUN|partlycloudy|72|55")
        self.assertEqual(fields[4:6], ["70", ""])
        self.assertEqual(fields[11], "above_horizon")
        self.assertEqual(fields[16], "waxing_gibbous")
        self.assertEqual(fields[17], "F")

    def test_shortcuts(self) -> None:
        expected_layout = [
            "kind",
            "target",
            "action",
            "label",
            "icon",
            "confirm",
            "state",
            "badge_style",
            "accent",
        ]
        self.assertEqual(self.layout("shortcuts", "dock_items"), expected_layout)
        self.assertEqual(self.layout("shortcuts", "pinned_items"), expected_layout)
        recs = protocol_policy.shortcut_records(
            [
                {
                    "kind": "route",
                    "target": "weather:moon",
                    "label": "Moon",
                    "icon": "mdi:moon-waning-crescent",
                    "badge_style": "inverted",
                    "accent": "primary",
                },
                {
                    "kind": "entity",
                    "target": "light.desk",
                    "action": "toggle",
                    "label": "Desk",
                    "icon": "mdi:lamp",
                    "confirm": True,
                    "state": 1,
                    "badge_style": "glass",
                    "accent": "orange",
                },
            ]
        )
        self.assertEqual(
            list(recs),
            [
                ("route", "weather:moon", "", "Moon", "mdi:moon-waning-crescent", "0", "-1", "inverted", "primary"),
                ("entity", "light.desk", "toggle", "Desk", "mdi:lamp", "1", "1", "", "orange"),
            ],
        )

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
        "coordinator",
        "areas",
        "http",
        "media_cache.py",
        "feeds.py",
        "protocol_specs.py",
        "protocol_codec.py",
        "protocol_policy.py",
        "media",
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
            src = read_py_tree(name)
            for pat in self.FORBIDDEN:
                self.assertNotRegex(src, pat, f"{name}: {pat}")
        ctx_src = read_py_tree("areas")
        # The area_context payload sends "" without an Area (the HA sensor state may still say Unassigned).
        self.assertIn('area_entry.name if area_entry else "",', ctx_src)
