"""Real-HA coverage tests for Areas modules (`actions`, `telemetry`, `registry`, `curation`, `catalogs`, `sync`) and Protocol v3 modules (`protocol_codec`, `protocol_specs`, `protocol_policy`)."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, PropertyMock, patch

from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
import pytest

from custom_components.latter import protocol_codec, protocol_policy, protocol_specs
from custom_components.latter.areas import actions as area_actions
from custom_components.latter.areas.catalogs import (
    get_area_entities,
    get_areas_summary,
    get_home_wide_entities,
)
from custom_components.latter.areas.curation import (
    extract_climate_temps,
    find_area_media_entities,
    format_entity_slot_name,
    get_entity_level,
    is_curated_area_entity,
)
from custom_components.latter.areas.registry import (
    apply_ha_display_precision,
    area_illuminance_sensor_choices,
    area_illuminance_settings,
    normalize_ambient_lux,
    resolve_area_ambient_light,
    resolve_entity_area_id,
)
from custom_components.latter.areas.sync import sync_esphome_device_area
from custom_components.latter.areas.telemetry import (
    _build_active_area_listener,
    bind_coordinator_area_listeners,
    build_area_context_payload,
    get_area_climate_telemetry,
    get_area_climates_summary,
    get_available_home_categories,
    get_home_hub_summary,
)
from custom_components.latter.const import (
    CONF_ALARM_ENTITY,
    CONF_AREA_ILLUMINANCE_CONFIG,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BROADCAST_SPEAKERS,
    CONF_DOCK_ITEMS,
    DEFAULT_BROADCAST_PHRASES,
)
from custom_components.latter.hub_registry import (
    get_area_state_index,
    get_global_config,
)
from tests.helpers import (
    ensure_area,
    get_service_calls,
    mock_service,
    register_device,
    register_entity,
)


def test_protocol_codec_escaping_records_and_dirty_prefs() -> None:
    """Exercise Protocol v3 subfield escaping, numeric edge guards, record caps, and dirty prefs parsing."""
    assert protocol_codec.escape_v3_subfield(None) == ""
    assert protocol_codec.escape_v3_subfield(True) == "1"
    assert protocol_codec.escape_v3_subfield(False) == "0"
    escaped = protocol_codec.escape_v3_subfield("a\\b|c;d\ne")
    assert escaped == "a\\\\b\\pc\\sd e"
    assert protocol_codec.unescape_v3_subfield(escaped) == "a\\b|c;d e"

    assert protocol_codec.sanitize_v3_subfield(None) == ""
    assert protocol_codec.sanitize_v3_subfield(True) == "1"
    assert protocol_codec.sanitize_v3_subfield(False) == "0"
    assert protocol_codec.sanitize_v3_field(float("nan")) == ""
    assert protocol_codec.sanitize_v3_field(float("inf")) == ""

    # Numeric coercion guards across forecast, weather, thermostat, camera, and active_media packers
    fc = protocol_codec.forecast_records(
        [{"day": "MON", "condition": "sunny", "high": "bad", "low": float("nan")}]
    )
    assert list(fc) == [("MON", "sunny", "", "")]

    weather_fields = protocol_codec.pack_weather_forecast_fields(
        condition="sunny",
        temperature="not_a_float",
        humidity=float("inf"),
        wind_speed=12.5,
    )
    assert weather_fields[1] == ""
    assert weather_fields[2] == ""
    assert weather_fields[3] == 12.5

    therms = protocol_codec.thermostat_records(
        [
            {
                "entity_id": "climate.zone1",
                "name": "Zone 1",
                "area_id": "kitchen",
                "state": "heat",
                "target_temp": float("nan"),
                "current_temp": "bad_temp",
                "caps": True,
            },
            {
                "entity_id": "climate.zone2",
                "name": "Zone 2",
                "area_id": "office",
                "state": "cool",
                "target_temp": 70.0,
                "current_temp": 72.3,
                "caps": "not_int",
            },
        ]
    )
    assert therms[0] == ("climate.zone1", "Zone 1", "kitchen", "heat", "", "", "0")
    assert therms[1] == ("climate.zone2", "Zone 2", "office", "cool", "70", "72.3", "0")

    bad_vol: Any = "bad_vol"
    media_fields = protocol_codec.pack_active_media_fields(
        state="playing",
        volume=bad_vol,
    )
    assert media_fields[6] == ""
    nan_vol: Any = float("nan")
    assert protocol_codec.pack_active_media_fields(volume=nan_vol)[6] == ""

    # Calendar sources (skip blank entity_id + enforce CALENDAR_SOURCES_MAX cap)
    sources = [
        {"entity_id": "", "label": "Blank"},
        *(
            {"entity_id": f"calendar.cal_{i}", "label": f"Cal {i}", "color_idx": i}
            for i in range(10)
        ),
    ]
    cal_srcs = protocol_codec.calendar_sources_records(sources)
    assert len(cal_srcs) == protocol_codec.CALENDAR_SOURCES_MAX - 1
    assert cal_srcs[0][0] == "calendar.cal_0"

    # Calendar locations cap
    locs = protocol_codec.calendar_locations_records(
        [f"Location {i}" for i in range(20)]
    )
    assert len(locs) == protocol_codec.CALENDAR_LOCATIONS_MAX

    # Calendar window chunks: skip missing start_ymd; handle None and bool fields
    chunks = protocol_codec.pack_calendar_window_chunks(
        [
            {"start_ymd": "", "summary": "Skipped"},
            {
                "start_ymd": "2026-11-20",
                "end_ymd": "2026-11-20",
                "start_min": 600,
                "end_min": 660,
                "all_day": False,
                "cal_idx": 0,
                "uid": "u1",
                "recurrence_id": None,
                "summary": "Standup",
                "location": None,
                "description": True,
            },
        ],
        "2026-11-01",
        "2026-11-30",
        req_id=3,
    )
    assert len(chunks) == 1
    parts = chunks[0]["events"].split(protocol_codec.FIELD_SEP)
    assert parts[0] == "2026-11-20"
    assert parts[7] == ""
    assert parts[9] == ""
    assert parts[10] == "1"

    # pack_device_prefs_fields fallback on invalid launcher CSVs and invalid custom hex
    pref_fields = protocol_codec.pack_device_prefs_fields(
        4,
        {
            "tools_items": "not_a_real_tool",
            "games_items": "",
            "camera_doorbell_popup": "Live Video",
        },
        native_ble_tracking=False,
        custom_color_hex="not-hex-color",
        supports_hw_jpeg=False,
    )
    names = [
        str(f["name"])
        for f in protocol_specs.PROTOCOL_V3_DATA["domains"]["device_prefs"]["fields"]
    ]
    by_name = dict(zip(names, pref_fields, strict=True))
    assert by_name["theme_color_hex"] == ""
    assert by_name["tools_items"] == protocol_specs.DEFAULT_TOOLS_ITEMS
    assert by_name["games_items"] == protocol_specs.DEFAULT_GAMES_ITEMS
    assert by_name["camera_doorbell_popup"] == "Snapshot"

    # parse_dirty_prefs_records edge branches
    raw_dirty = protocol_codec.RECORD_SEP.join(
        [
            "malformed_without_equals",
            "theme_color_hex=#12abef",
            "theme_color_hex=invalid_hex",
            "alarms_summary=bad_alarm_string",
            "alert_volume=nan",
            "volume_step_size=not_a_number",
            "calendar_lookahead_days=12",
        ]
    )
    parsed = protocol_codec.parse_dirty_prefs_records(raw_dirty)
    assert parsed == {
        "device_custom_color": "#12ABEF",
        "calendar_lookahead_days": 14,
    }
    assert protocol_codec._parse_dirty_text_spec_value("unhandled_text_key", "abc") is None


def test_protocol_codec_timezone_dst_fallback_and_offset_abbr() -> None:
    """Exercise TZ catalog DST fallback rules (us, eu, eg, au, au30, nz, none) and UTC offset formatting."""
    assert protocol_codec.format_tz_record("") == ""
    assert protocol_codec.format_tz_record("UTC") == "UTC|UTC|UTC|0|0"
    assert protocol_codec.format_tz_record("Etc/UTC") == "Etc/UTC|UTC|UTC|0|0"

    assert protocol_codec._format_utc_offset_abbr(0) == "UTC"
    assert protocol_codec._format_utc_offset_abbr(60) == "UTC+1"
    assert protocol_codec._format_utc_offset_abbr(-300) == "UTC-5"
    assert protocol_codec._format_utc_offset_abbr(330) == "UTC+5:30"
    assert protocol_codec._format_utc_offset_abbr(-210) == "UTC-3:30"

    # Exercise December last-weekday branch in _nth_weekday_of_month
    last_sun_dec = protocol_codec._nth_weekday_of_month(2026, 12, 6, -1)
    assert last_sun_dec.month == 12
    assert last_sun_dec.weekday() == 6

    summer_utc = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    winter_utc = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

    with patch(
        "custom_components.latter.protocol_codec.get_cached_zoneinfo",
        return_value=None,
    ):
        assert protocol_codec.format_tz_record("Unknown/NoSuchZone", summer_utc) == ""
        assert (
            protocol_codec.format_tz_record("America/New_York", summer_utc)
            == "America/New_York|New York|EDT|-240|1"
        )
        assert (
            protocol_codec.format_tz_record("America/New_York", winter_utc)
            == "America/New_York|New York|EST|-300|0"
        )
        assert (
            protocol_codec.format_tz_record("Europe/London", summer_utc)
            == "Europe/London|London|BST|60|1"
        )
        assert (
            protocol_codec.format_tz_record("Europe/London", winter_utc)
            == "Europe/London|London|GMT|0|0"
        )
        assert (
            protocol_codec.format_tz_record("Africa/Cairo", summer_utc)
            == "Africa/Cairo|Cairo|EEST|180|1"
        )
        assert (
            protocol_codec.format_tz_record("Africa/Cairo", winter_utc)
            == "Africa/Cairo|Cairo|EET|120|0"
        )
        assert (
            protocol_codec.format_tz_record("Australia/Sydney", winter_utc)
            == "Australia/Sydney|Sydney|AEDT|660|1"
        )
        assert (
            protocol_codec.format_tz_record("Australia/Sydney", summer_utc)
            == "Australia/Sydney|Sydney|AEST|600|0"
        )
        assert (
            protocol_codec.format_tz_record("Australia/Lord_Howe", winter_utc)
            == "Australia/Lord_Howe|Lord Howe|LHDT|660|1"
        )
        assert (
            protocol_codec.format_tz_record("Australia/Lord_Howe", summer_utc)
            == "Australia/Lord_Howe|Lord Howe|LHST|630|0"
        )
        assert (
            protocol_codec.format_tz_record("Pacific/Auckland", winter_utc)
            == "Pacific/Auckland|Auckland|NZDT|780|1"
        )
        assert (
            protocol_codec.format_tz_record("Pacific/Auckland", summer_utc)
            == "Pacific/Auckland|Auckland|NZST|720|0"
        )
        assert (
            protocol_codec.format_tz_record("Asia/Tokyo", summer_utc)
            == "Asia/Tokyo|Tokyo|JST|540|0"
        )


def test_protocol_specs_lookahead_tz_cache_and_humanize() -> None:
    """Exercise lookahead snapping, ZoneInfo cache fallbacks, IANA validation, and model label humanization."""
    assert protocol_specs.snap_calendar_lookahead_days(True) == 30
    assert protocol_specs.snap_calendar_lookahead_days(None) == 30
    assert protocol_specs.snap_calendar_lookahead_days("not_a_number") == 30
    assert protocol_specs.snap_calendar_lookahead_days(5) == 7
    assert protocol_specs.snap_calendar_lookahead_days(14) == 14
    assert protocol_specs.snap_calendar_lookahead_days(30) == 30
    assert protocol_specs.snap_calendar_lookahead_days(90) == 60

    assert protocol_specs.get_cached_zoneinfo("") is None
    assert protocol_specs.is_valid_iana_zone("") is False
    assert protocol_specs.is_valid_iana_zone("UTC") is False
    assert protocol_specs.is_valid_iana_zone("A/" + "B" * 60) is False
    assert protocol_specs.is_valid_iana_zone("NoSlashToken") is False

    orig_avail = protocol_specs._AVAILABLE_IANA_ZONES
    orig_cache = dict(protocol_specs._ZONEINFO_CACHE)
    try:
        protocol_specs._ZONEINFO_CACHE.clear()
        with patch(
            "custom_components.latter.protocol_specs.available_timezones",
            side_effect=RuntimeError("tzdb unavailable"),
        ):
            protocol_specs.warm_timezone_cache(extra_zones=("America/Boise", ""))
        assert protocol_specs._AVAILABLE_IANA_ZONES is not None
        assert len(protocol_specs._AVAILABLE_IANA_ZONES) == 0

        protocol_specs._AVAILABLE_IANA_ZONES = frozenset({"America/New_York"})
        protocol_specs._ZONEINFO_CACHE.pop("Invalid/Zone_Test", None)
        assert protocol_specs.get_cached_zoneinfo("Invalid/Zone_Test") is None
        assert protocol_specs._ZONEINFO_CACHE["Invalid/Zone_Test"] is None

        protocol_specs._AVAILABLE_IANA_ZONES = None
        protocol_specs._ZONEINFO_CACHE.pop("America/Boise", None)
        protocol_specs._ZONEINFO_CACHE.pop("Invalid/Cold_Zone", None)
        assert protocol_specs.get_cached_zoneinfo("America/Boise") is not None
        assert protocol_specs.is_valid_iana_zone("America/Boise") is True
        assert protocol_specs.is_valid_iana_zone("Invalid/Cold_Zone") is False
    finally:
        protocol_specs._AVAILABLE_IANA_ZONES = orig_avail
        protocol_specs._ZONEINFO_CACHE.clear()
        protocol_specs._ZONEINFO_CACHE.update(orig_cache)

    assert protocol_specs._humanize_slug_tokens("___") == "___"
    assert (
        protocol_specs._humanize_slug_tokens("esp32_s3_amoled_1.75in_touchLCD")
        == "Esp32 S3 AMOLED 1.75in touchLCD"
    )
    assert (
        protocol_specs.humanize_device_model_label(
            "", {"w": "bad", "h": 466, "board": "esp32_p4_panel"}
        )
        == "Esp32 P4 Panel"
    )
    assert (
        protocol_specs.humanize_device_model_label(
            "", {"w": 480, "h": 480, "board": "esp32_s3_display"}
        )
        == "Esp32 S3 Display (480x480)"
    )
    assert (
        protocol_specs.humanize_device_model_label("", {"w": 480, "h": 480})
        == "Latter Display (480x480)"
    )
    assert protocol_specs.default_city_for_iana("America/Indiana/Tell_City") == "Tell City"


def test_protocol_specs_world_clocks_alarms_shortcuts_and_prefs() -> None:
    """Exercise non-strict/strict World Clock, Alarm, Shortcut, MDI icon, and device pref resolvers."""
    assert protocol_specs.parse_world_clocks_spec(None) == []
    assert protocol_specs.parse_world_clocks_spec(
        [
            {"label": "Boise Hub", "iana": "America/New_York"},
            {"label": "", "iana": ""},
        ]
    ) == [("Boise Hub", "America/New_York")]
    assert (
        protocol_specs.parse_world_clocks_spec(
            "MissingPipe;BadCity|Not/AZone;London|Europe/London", strict=False
        )
        == [("London", "Europe/London")]
    )
    five_clocks = (
        "A|Europe/London;B|Asia/Tokyo;C|Asia/Kolkata;D|Australia/Sydney;E|America/New_York"
    )
    assert len(protocol_specs.parse_world_clocks_spec(five_clocks, strict=False)) == 4

    assert (
        protocol_specs.normalize_alarms_summary("", strict=False)
        == protocol_specs.DEFAULT_ALARMS_SUMMARY
    )
    assert (
        protocol_specs.normalize_alarms_summary("07:00|1|0", strict=False)
        == protocol_specs.DEFAULT_ALARMS_SUMMARY
    )
    assert (
        protocol_specs.normalize_alarms_summary(
            "bad;08:30|0|2;09:00|0|2", strict=False
        )
        == protocol_specs.DEFAULT_ALARMS_SUMMARY
    )
    assert (
        protocol_specs.normalize_alarms_summary(
            "25:00|1|0;08:30|0|2;09:00|0|2", strict=False
        )
        == protocol_specs.DEFAULT_ALARMS_SUMMARY
    )

    long_lbl = protocol_specs.sanitize_shortcut_label(
        "A Very Long Shortcut Label Exceeding Limit"
    )
    assert len(long_lbl) <= protocol_specs.SHORTCUT_LABEL_MAX

    assert protocol_specs.normalize_mdi_icon("mdi-lightbulb") == "mdi:lightbulb"
    assert protocol_specs.normalize_mdi_icon("bad icon!!", strict=False) == ""
    with pytest.raises(ValueError, match="Invalid MDI icon"):
        protocol_specs.normalize_mdi_icon("bad icon!!", strict=True)

    # Shortcut badge_style and accent normalization (strict & non-strict)
    assert protocol_specs.normalize_shortcut_badge_style(None) == ""
    assert protocol_specs.normalize_shortcut_badge_style("") == ""
    assert protocol_specs.normalize_shortcut_badge_style("  GLASS  ") == ""
    assert protocol_specs.normalize_shortcut_badge_style(" Inverted ") == "inverted"
    assert protocol_specs.normalize_shortcut_badge_style("solid", strict=False) == ""
    assert protocol_specs.normalize_shortcut_badge_style(False, strict=False) == ""
    with pytest.raises(ValueError, match="Unknown shortcut badge style"):
        protocol_specs.normalize_shortcut_badge_style("solid", strict=True)
    with pytest.raises(ValueError, match="Unknown shortcut badge style"):
        protocol_specs.normalize_shortcut_badge_style(False, strict=True)

    assert protocol_specs.normalize_shortcut_accent(None) == ""
    assert protocol_specs.normalize_shortcut_accent("") == ""
    assert protocol_specs.normalize_shortcut_accent("  Default ") == ""
    for accent_tok in ("primary", "gold", "green", "red", "orange"):
        assert (
            protocol_specs.normalize_shortcut_accent(f" {accent_tok.upper()} ")
            == accent_tok
        )
    assert protocol_specs.normalize_shortcut_accent("purple", strict=False) == ""
    assert protocol_specs.normalize_shortcut_accent(0, strict=False) == ""
    with pytest.raises(ValueError, match="Unknown shortcut accent"):
        protocol_specs.normalize_shortcut_accent("purple", strict=True)
    with pytest.raises(ValueError, match="Unknown shortcut accent"):
        protocol_specs.normalize_shortcut_accent(0, strict=True)

    # Non-strict & strict shortcut item normalization branches
    assert (
        protocol_specs.normalize_shortcut_item(
            {"kind": "route", "target": "app:unknown_route"},
            is_dock=True,
            strict=False,
        )
        is None
    )
    assert (
        protocol_specs.normalize_shortcut_item(
            {"kind": "route", "target": "app:pinned"},
            is_dock=False,
            strict=False,
        )
        is None
    )
    str_confirm = protocol_specs.normalize_shortcut_item(
        {
            "kind": "entity",
            "target": "light.desk",
            "action": "toggle",
            "confirm": "yes",
        },
        is_dock=False,
        strict=True,
    )
    assert str_confirm is not None
    assert str_confirm["confirm"] is True

    with pytest.raises(ValueError, match="Invalid entity_id"):
        protocol_specs.normalize_shortcut_item(
            {"kind": "entity", "target": "bad_entity"}, is_dock=False, strict=True
        )
    assert (
        protocol_specs.normalize_shortcut_item(
            {"kind": "entity", "target": "bad_entity"}, is_dock=False, strict=False
        )
        is None
    )
    with pytest.raises(ValueError, match="Unsupported shortcut entity domain"):
        protocol_specs.normalize_shortcut_item(
            {"kind": "entity", "target": "sensor.temp"}, is_dock=False, strict=True
        )
    assert (
        protocol_specs.normalize_shortcut_item(
            {"kind": "entity", "target": "sensor.temp"}, is_dock=False, strict=False
        )
        is None
    )
    defaulted_act = protocol_specs.normalize_shortcut_item(
        {"kind": "entity", "target": "light.desk", "action": ""},
        is_dock=False,
        strict=False,
    )
    assert defaulted_act is not None
    assert defaulted_act["action"] == "toggle"
    assert (
        protocol_specs.normalize_shortcut_item(
            {"kind": "entity", "target": "light.desk", "action": "bogus"},
            is_dock=False,
            strict=False,
        )
        is None
    )
    with pytest.raises(ValueError, match="must be an object"):
        protocol_specs.normalize_shortcut_item("not_a_dict", is_dock=True, strict=True)
    assert (
        protocol_specs.normalize_shortcut_item("not_a_dict", is_dock=True, strict=False)
        is None
    )
    with pytest.raises(ValueError, match="Unknown shortcut kind"):
        protocol_specs.normalize_shortcut_item(
            {"kind": "other"}, is_dock=True, strict=True
        )
    assert (
        protocol_specs.normalize_shortcut_item(
            {"kind": "other"}, is_dock=True, strict=False
        )
        is None
    )

    # Shortcut list validation, deduplication, and overflow caps
    with pytest.raises(ValueError, match="dock_items must be a list"):
        protocol_specs.normalize_dock_items("not_a_list", strict=True)
    assert (
        protocol_specs.normalize_dock_items("not_a_list", strict=False)
        == protocol_specs.default_dock_items()
    )
    assert protocol_specs.normalize_pinned_items("not_a_list", strict=False) == []

    dup_item = {"kind": "entity", "target": "light.desk", "action": "toggle"}
    assert len(protocol_specs.normalize_pinned_items([dup_item, dup_item])) == 1

    many_dock = [
        {"kind": "entity", "target": f"switch.s{i}", "action": "toggle"}
        for i in range(protocol_specs.MAX_DOCK_ITEMS + 2)
    ]
    with pytest.raises(ValueError, match="supports at most"):
        protocol_specs.normalize_dock_items(many_dock, strict=True)
    assert (
        len(protocol_specs.normalize_dock_items(many_dock, strict=False))
        == protocol_specs.MAX_DOCK_ITEMS
    )

    # Device pref value resolution edge branches
    assert protocol_specs._resolve_text_pref("custom_text", "  hello  ") == "hello"
    assert (
        protocol_specs.resolve_device_pref_value({"alert_volume": True}, "alert_volume")
        == protocol_specs.DEVICE_PREF_SPEC_MAP["alert_volume"].default
    )
    assert (
        protocol_specs.resolve_device_pref_value(
            {"alert_volume": "not_int"}, "alert_volume"
        )
        == protocol_specs.DEVICE_PREF_SPEC_MAP["alert_volume"].default
    )
    assert (
        protocol_specs.resolve_device_pref_value(
            {"do_not_disturb": "true"}, "do_not_disturb"
        )
        is True
    )
    assert (
        protocol_specs.resolve_device_pref_value(
            {"do_not_disturb": "off"}, "do_not_disturb"
        )
        is False
    )


def test_protocol_policy_icons_states_pin_wrap_lockout_and_verify() -> None:
    """Exercise shortcut icons/states, PIN wrap validation, crafted MAC payload guards, lockout reset, and policy checks."""
    assert (
        protocol_policy.resolve_shortcut_entity_icon(
            "cover", device_class="door", state="open"
        )
        == "mdi:door-open"
    )
    assert (
        protocol_policy.resolve_shortcut_entity_icon(
            "cover", device_class="door", state="closed"
        )
        == "mdi:door-closed"
    )

    assert (
        protocol_policy.resolve_shortcut_live_state("alarm_control_panel", "disarmed")
        == 0
    )
    assert (
        protocol_policy.resolve_shortcut_live_state("alarm_control_panel", "armed_away")
        == 1
    )
    assert protocol_policy.resolve_shortcut_live_state("climate", "off") == 0
    assert protocol_policy.resolve_shortcut_live_state("climate", "heat") == 1
    assert protocol_policy.resolve_shortcut_live_state("water_heater", "eco") == 1
    assert protocol_policy.resolve_shortcut_live_state("script", "unknown") == 0
    assert protocol_policy.resolve_shortcut_live_state("light", "unknown") == -1
    assert protocol_policy.resolve_shortcut_live_state("automation", "on") == -1
    assert (
        protocol_policy.resolve_shortcut_live_state(
            "automation", "on", action="trigger"
        )
        == -1
    )
    assert (
        protocol_policy.resolve_shortcut_live_state(
            "automation", "unavailable", action="trigger"
        )
        == 2
    )
    assert (
        protocol_policy.resolve_shortcut_live_state(
            "automation", "on", action="toggle"
        )
        == 1
    )
    assert (
        protocol_policy.resolve_shortcut_live_state(
            "automation", "off", action="toggle"
        )
        == 0
    )
    assert (
        protocol_policy.resolve_shortcut_live_state(
            "automation", "unknown", action="toggle"
        )
        == 0
    )

    recs = protocol_policy.shortcut_records(
        [
            {
                "kind": "entity",
                "target": "light.a",
                "action": "toggle",
                "state": "bad_state_num",
                "badge_style": "glass",
                "accent": "default",
            },
            {
                "kind": "route",
                "target": "weather:moon",
                "label": "Moon",
                "badge_style": "INVERTED",
                "accent": "GOLD",
            },
            {
                "kind": "entity",
                "target": "switch.b",
                "action": "toggle",
                "state": 1,
                "badge_style": "bogus",
                "accent": "bogus",
            },
        ]
    )
    assert len(recs[0]) == 14
    assert recs[0][6:] == ("-1", "", "", "", "", "", "", "")
    assert recs[1] == (
        "route",
        "weather:moon",
        "",
        "Moon",
        "",
        "0",
        "-1",
        "inverted",
        "gold",
        "",
        "",
        "",
        "",
        "",
    )
    assert recs[2][6:] == ("1", "", "", "", "", "", "", "")

    # Grid field branches in protocol_specs & protocol_policy
    assert protocol_specs._parse_grid_int("") is None
    assert protocol_specs._parse_grid_int("   ") is None
    assert protocol_specs._parse_grid_int("3") == 3
    assert protocol_specs._parse_grid_int(3.5) is None
    assert (
        protocol_specs.normalize_pinned_items(
            [{"kind": "route", "target": "app:music", "page": "", "col": "", "row": "", "col_span": ""}],
            strict=True,
        )[0].get("page")
        is None
    )
    assert protocol_policy.pinned_page_title_records({"1": "One", "0": "Zero"}) == (
        ("0", "Zero"),
        ("1", "One"),
    )

    non_str_pin: Any = 1234
    assert protocol_policy.is_valid_pin_digits(None) is False
    assert protocol_policy.is_valid_pin_digits(non_str_pin) is False

    kid, key_bytes = protocol_policy.mint_pin_session_key()
    with pytest.raises(ValueError, match="key_id"):
        protocol_policy.wrap_pin_code("bad_kid", key_bytes, 1, "lock.a", "unlock", "1234")
    with pytest.raises(ValueError, match="key_bytes"):
        protocol_policy.wrap_pin_code(kid, b"short", 1, "lock.a", "unlock", "1234")
    with pytest.raises(ValueError, match="nonce"):
        protocol_policy.wrap_pin_code(kid, key_bytes, 0, "lock.a", "unlock", "1234")

    with pytest.raises(protocol_policy.PinWrapError) as exc_hex:
        protocol_policy.unwrap_pin_code(
            kid,
            key_bytes,
            0,
            "lock.a",
            "unlock",
            f"v1:{kid}:00000001:ZZZZZZZZ:{'a' * 32}",
        )
    assert exc_hex.value.reason == "malformed"

    with pytest.raises(ValueError, match="last_nonce"):
        protocol_policy.unwrap_pin_code(
            kid, key_bytes, -1, "lock.a", "unlock", "v1:0:0:0:0"
        )

    # Craft validly MAC'd envelopes carrying (a) non-ASCII plaintext and (b) non-digit ASCII plaintext
    def _craft_envelope(nonce_int: int, pt_bytes: bytes) -> str:
        nonce_hex8 = f"{nonce_int:08x}"
        ks = hmac.new(
            key_bytes, f"stream|{kid}|{nonce_hex8}".encode(), hashlib.sha256
        ).digest()[: len(pt_bytes)]
        ct_hex = bytes(b ^ k for b, k in zip(pt_bytes, ks, strict=True)).hex()
        mac_hex32 = hmac.new(
            key_bytes,
            f"latter-pin-v1|{kid}|{nonce_hex8}|lock.a|unlock|{ct_hex}".encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        return f"v1:{kid}:{nonce_hex8}:{ct_hex}:{mac_hex32}"

    with pytest.raises(protocol_policy.PinWrapError) as exc_non_ascii:
        protocol_policy.unwrap_pin_code(
            kid, key_bytes, 0, "lock.a", "unlock", _craft_envelope(1, b"\xff\xfe\xfd\xfc")
        )
    assert exc_non_ascii.value.reason == "invalid_digits"

    with pytest.raises(protocol_policy.PinWrapError) as exc_non_digit:
        protocol_policy.unwrap_pin_code(
            kid, key_bytes, 0, "lock.a", "unlock", _craft_envelope(2, b"abcd")
        )
    assert exc_non_digit.value.reason == "invalid_digits"

    # PinLockoutTracker.reset (single scope vs all scopes)
    tracker = protocol_policy.PinLockoutTracker(max_failures=2, base_cooldown_s=30.0)
    tracker.record_failure("dev_a", now=100.0)
    tracker.record_failure("dev_a", now=101.0)
    tracker.record_failure("dev_b", now=100.0)
    assert tracker.is_locked_out("dev_a", now=102.0) is True
    tracker.reset("dev_a")
    assert tracker.failure_count("dev_a") == 0
    assert tracker.failure_count("dev_b") == 1
    tracker.reset()
    assert tracker.failure_count("dev_b") == 0

    # verify_security_pin malformed / out-of-range stored hashes
    assert protocol_policy.verify_security_pin("1234", "bad_scheme$200000$00$11") is False
    assert (
        protocol_policy.verify_security_pin("1234", "pbkdf2_sha256$not_int$00$11")
        is False
    )
    assert (
        protocol_policy.verify_security_pin("1234", "pbkdf2_sha256$200000$zzzz$11")
        is False
    )
    assert (
        protocol_policy.verify_security_pin(
            "1234", f"pbkdf2_sha256$5000${'00' * 16}${'11' * 32}"
        )
        is False
    )

    # check_perimeter_action_allowed branches
    assert protocol_policy.check_perimeter_action_allowed(
        "allow", provided_code=None, stored_pin_hash=None
    ) == (True, "")
    assert protocol_policy.check_perimeter_action_allowed(
        "require_pin",
        provided_code="1234",
        stored_pin_hash=None,
        alarm_accepts_passthrough_code=True,
    ) == (True, "")
    assert protocol_policy.check_perimeter_action_allowed(
        "require_pin",
        provided_code="1234",
        stored_pin_hash=None,
        alarm_accepts_passthrough_code=False,
    ) == (False, "security_pin_not_configured")


async def test_areas_actions_alarm_climate_vacuum_and_light_edges(hass: Any) -> None:
    """Exercise alarm mapping/PIN validation, climate step/toggle/setpoint edges, vacuum toggle, media step, and light hex errors."""
    for dom, svcs in (
        ("alarm_control_panel", ("alarm_disarm", "alarm_arm_away")),
        ("climate", ("set_temperature", "set_hvac_mode", "turn_off")),
        ("media_player", ("volume_set", "volume_down", "volume_up")),
        ("light", ("turn_on", "turn_off", "toggle")),
        ("switch", ("turn_on", "turn_off", "toggle")),
        ("vacuum", ("start", "turn_on", "pause", "stop", "turn_off")),
    ):
        for svc in svcs:
            mock_service(hass, dom, svc)

    calls = get_service_calls(hass)

    # Alarm: empty entity_id maps to home_hub.alarm -> configured CONF_ALARM_ENTITY
    get_global_config(hass)[CONF_ALARM_ENTITY] = "alarm_control_panel.site_alarm"
    hass.states.async_set(
        "alarm_control_panel.site_alarm",
        "armed_away",
        {"code_format": "number", "code_arm_required": True},
    )
    with pytest.raises(ServiceValidationError) as exc_req:
        await area_actions.async_execute_area_action(hass, "", "disarm", code="")
    assert exc_req.value.translation_key == "security_pin_required"

    with pytest.raises(ServiceValidationError) as exc_inv:
        await area_actions.async_execute_area_action(
            hass, "", "arm_away", code="abcd"
        )
    assert exc_inv.value.translation_key == "security_pin_invalid"

    calls.clear()
    await area_actions.async_execute_area_action(hass, "", "disarm", code="2468")
    assert calls[-1].domain == "alarm_control_panel"
    assert calls[-1].service == "alarm_disarm"
    assert calls[-1].data == {
        "entity_id": "alarm_control_panel.site_alarm",
        "code": "2468",
    }

    # Climate step & setpoint edge branches
    hass.states.async_set(
        "climate.dual_zone",
        "heat_cool",
        {"target_temp_low": 68, "target_temp_high": 74, "hvac_modes": ["off", "heat_cool"]},
    )
    calls.clear()
    await area_actions.async_execute_area_action(hass, "climate.dual_zone", "step_up")
    assert calls[-1].service == "set_temperature"
    assert calls[-1].data["target_temp_low"] == 69.0
    assert calls[-1].data["target_temp_high"] == 75.0

    hass.states.async_set(
        "climate.bad_dual",
        "heat",
        {"target_temp_low": "bad", "target_temp_high": "bad"},
    )
    calls.clear()
    await area_actions.async_execute_area_action(hass, "climate.bad_dual", "step_down")
    assert calls[-1].service == "set_temperature"
    assert calls[-1].data == {"entity_id": "climate.bad_dual", "temperature": 19.0}

    hass.states.async_set(
        "climate.cur_only",
        "heat",
        {"current_temperature": 70},
    )
    calls.clear()
    await area_actions.async_execute_area_action(hass, "climate.cur_only", "step_up")
    assert calls[-1].data == {"entity_id": "climate.cur_only", "temperature": 71.0}

    # Climate turn_off / turn_on / toggle branches (before & after climate.turn_on / climate.toggle exist)
    hass.states.async_set(
        "climate.mode_off", "off", {"hvac_modes": ["off", "cool"]}
    )
    hass.states.async_set(
        "climate.mode_on", "heat", {"hvac_modes": ["off", "heat"]}
    )
    hass.states.async_set("climate.no_off", "heat", {"hvac_modes": ["heat"]})
    hass.states.async_set("climate.empty_off", "off", {"hvac_modes": []})

    calls.clear()
    await area_actions.async_execute_area_action(hass, "climate.mode_off", "turn_on")
    assert calls[-1].service == "set_hvac_mode"
    assert calls[-1].data["hvac_mode"] == "cool"

    await area_actions.async_execute_area_action(hass, "climate.mode_off", "toggle")
    assert calls[-1].service == "set_hvac_mode"
    assert calls[-1].data["hvac_mode"] == "cool"

    await area_actions.async_execute_area_action(hass, "climate.mode_on", "turn_off")
    assert calls[-1].service == "set_hvac_mode"
    assert calls[-1].data["hvac_mode"] == "off"

    await area_actions.async_execute_area_action(hass, "climate.mode_on", "toggle")
    assert calls[-1].service == "set_hvac_mode"
    assert calls[-1].data["hvac_mode"] == "off"

    await area_actions.async_execute_area_action(hass, "climate.no_off", "turn_off")
    assert calls[-1].service == "turn_off"

    await area_actions.async_execute_area_action(hass, "climate.no_off", "toggle")
    assert calls[-1].service == "turn_off"

    mock_service(hass, "climate", "turn_on")
    await area_actions.async_execute_area_action(hass, "climate.empty_off", "turn_on")
    assert calls[-1].service == "turn_on"

    await area_actions.async_execute_area_action(hass, "climate.empty_off", "toggle")
    assert calls[-1].service == "turn_on"

    mock_service(hass, "climate", "toggle")
    await area_actions.async_execute_area_action(hass, "climate.mode_on", "toggle")
    assert calls[-1].service == "toggle"

    # Unhandled climate verb falls through _try_climate_action returning False -> ignored in generic
    calls.clear()
    await area_actions.async_execute_area_action(
        hass, "climate.mode_on", "unknown_verb", raise_on_missing=False
    )
    assert calls == []

    # Media step with unparseable volume_level -> falls back to volume_down
    hass.states.async_set(
        "media_player.bad_vol", "playing", {"volume_level": "not_a_float"}
    )
    calls.clear()
    await area_actions.async_execute_area_action(
        hass, "media_player.bad_vol", "step_down"
    )
    assert (calls[-1].domain, calls[-1].service) == ("media_player", "volume_down")

    # Light set_color with invalid 6-char hex
    hass.states.async_set("light.rgb", "on", {})
    calls.clear()
    await area_actions.async_execute_area_action(
        hass, "light.rgb", "set_color", level=50, code="#ZZZZZZ"
    )
    assert calls == []

    # Vacuum toggle across cleaning/docked & feature bitmasks
    for eid, st_val, sf, expected_svc in (
        ("vacuum.v_pause", "cleaning", 0, "pause"),
        ("vacuum.v_turnoff", "cleaning", 2, "turn_off"),
        ("vacuum.v_stop", "cleaning", 8, "stop"),
        ("vacuum.v_turnon", "docked", 1, "turn_on"),
        ("vacuum.v_start", "docked", 8192, "start"),
    ):
        hass.states.async_set(eid, st_val, {"supported_features": sf})
        calls.clear()
        await area_actions.async_execute_area_action(hass, eid, "toggle")
        assert (calls[-1].domain, calls[-1].service) == ("vacuum", expected_svc)

    # _try_set_level_action: media_player direct path + unsupported switch returning False
    hass.states.async_set("media_player.direct_vol", "playing", {"volume_level": 0.4})
    hass.states.async_set("switch.no_level", "off", {})
    calls.clear()
    mp_st = hass.states.get("media_player.direct_vol")
    assert mp_st is not None
    assert (
        await area_actions._try_set_level_action(hass, mp_st, 65, blocking=True)
        is True
    )
    assert (calls[-1].domain, calls[-1].service) == ("media_player", "volume_set")
    await area_actions.async_execute_area_action(
        hass, "switch.no_level", "set_level", level=50, blocking=True
    )
    await hass.async_block_till_done()


async def test_areas_actions_helpers_utilities_generic_and_missing_states(
    hass: Any,
) -> None:
    """Exercise helper/utility/generic action branches, empty-action normalization, and missing/unavailable guards."""
    for dom, svcs in (
        ("homeassistant", ("update_entity",)),
        ("select", ("select_next", "select_previous")),
        ("automation", ("trigger", "turn_off", "toggle")),
        ("valve", ("open_valve", "close_valve", "stop_valve")),
        ("lawn_mower", ("start_mowing", "pause", "dock")),
        ("switch", ("turn_off", "toggle")),
        ("cover", ("close_cover",)),
        ("media_player", ("media_play_pause", "media_next_track")),
        ("light", ("turn_on",)),
        ("button", ("press",)),
    ):
        for svc in svcs:
            mock_service(hass, dom, svc)

    calls = get_service_calls(hass)

    # Stateless / helper domains: update fallback, select_next, missing option/level validation
    hass.states.async_set("update.idle_fw", "off", {})
    hass.states.async_set("select.mode", "a", {"options": ["a", "b"]})
    hass.states.async_set("number.gain", "10", {"min": 0, "max": 100})

    calls.clear()
    await area_actions.async_execute_area_action(hass, "update.idle_fw", "check")
    assert (calls[-1].domain, calls[-1].service) == ("homeassistant", "update_entity")

    await area_actions.async_execute_area_action(hass, "select.mode", "select_next")
    assert (calls[-1].domain, calls[-1].service) == ("select", "select_next")

    with pytest.raises(ServiceValidationError) as exc_sel:
        await area_actions.async_execute_area_action(
            hass, "select.mode", "toggle", raise_on_missing=True
        )
    assert exc_sel.value.translation_key == "explicit_action_required"

    with pytest.raises(ServiceValidationError) as exc_num:
        await area_actions.async_execute_area_action(
            hass, "number.gain", "toggle", raise_on_missing=True
        )
    assert exc_num.value.translation_key == "explicit_action_required"

    # Utility domains: automation, valve, lawn_mower
    hass.states.async_set("automation.morning", "on", {})
    hass.states.async_set("valve.main_water", "open", {})
    hass.states.async_set("lawn_mower.yard", "docked", {})

    calls.clear()
    await area_actions.async_execute_area_action(hass, "automation.morning", "turn_off")
    assert (calls[-1].domain, calls[-1].service) == ("automation", "turn_off")
    await area_actions.async_execute_area_action(hass, "automation.morning", "other")
    assert (calls[-1].domain, calls[-1].service) == ("automation", "trigger")

    await area_actions.async_execute_area_action(hass, "valve.main_water", "open")
    assert (calls[-1].domain, calls[-1].service) == ("valve", "open_valve")
    await area_actions.async_execute_area_action(hass, "valve.main_water", "close")
    assert (calls[-1].domain, calls[-1].service) == ("valve", "close_valve")
    await area_actions.async_execute_area_action(hass, "valve.main_water", "stop")
    assert (calls[-1].domain, calls[-1].service) == ("valve", "stop_valve")
    await area_actions.async_execute_area_action(hass, "valve.main_water", "toggle")
    assert (calls[-1].domain, calls[-1].service) == ("valve", "close_valve")
    hass.states.async_set("valve.main_water", "closed", {})
    await area_actions.async_execute_area_action(hass, "valve.main_water", "toggle")
    assert (calls[-1].domain, calls[-1].service) == ("valve", "open_valve")

    await area_actions.async_execute_area_action(hass, "lawn_mower.yard", "dock")
    assert (calls[-1].domain, calls[-1].service) == ("lawn_mower", "dock")
    await area_actions.async_execute_area_action(hass, "lawn_mower.yard", "toggle")
    assert (calls[-1].domain, calls[-1].service) == ("lawn_mower", "start_mowing")

    # Generic domain edges + media transport + empty action normalization
    hass.states.async_set("sensor.temp", "70", {})
    hass.states.async_set("switch.desk", "on", {})
    hass.states.async_set("cover.shade", "open", {})
    hass.states.async_set("media_player.spk", "playing", {})
    hass.states.async_set("lock.door", "locked", {})
    hass.states.async_set("light.lamp", "off", {})

    with pytest.raises(ServiceValidationError) as exc_unsup:
        await area_actions.async_execute_area_action(
            hass, "sensor.temp", "toggle", raise_on_missing=True
        )
    assert exc_unsup.value.translation_key == "not_supported"

    calls.clear()
    await area_actions.async_execute_area_action(
        hass, "sensor.temp", "toggle", raise_on_missing=False
    )
    assert calls == []

    await area_actions.async_execute_area_action(hass, "switch.desk", "turn_off")
    assert (calls[-1].domain, calls[-1].service) == ("switch", "turn_off")
    await area_actions.async_execute_area_action(hass, "cover.shade", "turn_off")
    assert (calls[-1].domain, calls[-1].service) == ("cover", "close_cover")
    await area_actions.async_execute_area_action(hass, "media_player.spk", "toggle")
    assert (calls[-1].domain, calls[-1].service) == ("media_player", "media_play_pause")
    await area_actions.async_execute_area_action(
        hass, "media_player.spk", "media_next_track"
    )
    assert (calls[-1].domain, calls[-1].service) == ("media_player", "media_next_track")

    with pytest.raises(ServiceValidationError) as exc_bad_verb:
        await area_actions.async_execute_area_action(
            hass, "switch.desk", "bogus_verb", raise_on_missing=True
        )
    assert exc_bad_verb.value.translation_key == "not_supported"

    # Empty action normalization: lock -> explicit_action_required; light + level -> set_level; switch -> toggle
    with pytest.raises(ServiceValidationError) as exc_lock_empty:
        await area_actions.async_execute_area_action(hass, "lock.door", "")
    assert exc_lock_empty.value.translation_key == "explicit_action_required"

    calls.clear()
    await area_actions.async_execute_area_action(hass, "light.lamp", "", level=40)
    assert (calls[-1].domain, calls[-1].service) == ("light", "turn_on")
    assert calls[-1].data["brightness_pct"] == 40

    await area_actions.async_execute_area_action(hass, "switch.desk", "")
    assert (calls[-1].domain, calls[-1].service) == ("switch", "toggle")

    # Missing button falls back to press; missing/unavailable raise HomeAssistantError when requested
    calls.clear()
    await area_actions.async_execute_area_action(
        hass, "button.unseen_btn", "press", raise_on_missing=False
    )
    assert (calls[-1].domain, calls[-1].service) == ("button", "press")

    with pytest.raises(HomeAssistantError) as exc_missing:
        await area_actions.async_execute_area_action(
            hass, "switch.missing_sw", "toggle", raise_on_missing=True
        )
    assert exc_missing.value.translation_key == "entity_not_found"

    hass.states.async_set("light.offline", "unavailable", {})
    with pytest.raises(HomeAssistantError) as exc_unavail:
        await area_actions.async_execute_area_action(
            hass, "light.offline", "toggle", raise_on_missing=True
        )
    assert exc_unavail.value.translation_key == "entity_unavailable"
    await hass.async_block_till_done()


async def test_areas_registry_curation_catalogs_and_sync_edges(hass: Any) -> None:
    """Exercise registry, curation, catalogs, sync, and stateless telemetry edge branches on real HA registries."""
    ensure_area(hass, "Kitchen", area_id="kitchen")
    ensure_area(hass, "Office", area_id="office")
    ensure_area(hass, "Study", area_id="study")
    ensure_area(hass, "Garage", area_id="garage")

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    # Devices for resolve_entity_area_id & sync_esphome_device_area
    dev_with_area = register_device(
        hass,
        config_entry_id="esp_entry_sync_test",
        identifiers={("esphome", "aa:bb:cc:dd:ee:10")},
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:10")},
        name="Sync Device",
        area_id="kitchen",
    )
    dev_no_area = register_device(
        hass,
        config_entry_id="esp_entry_no_area",
        identifiers={("esphome", "aa:bb:cc:dd:ee:11")},
        name="Unassigned Device",
    )
    ent_direct = register_entity(
        hass, "light.kitchen_direct", platform="hue", area_id="kitchen"
    )
    ent_via_dev = register_entity(
        hass, "light.dev_inherited", platform="hue", device_id=dev_with_area.id
    )
    ent_no_area = register_entity(
        hass, "light.dev_unassigned", platform="hue", device_id=dev_no_area.id
    )

    # resolve_entity_area_id branches (lines 90-106)
    assert resolve_entity_area_id(hass, ent_direct.entity_id) == "kitchen"
    assert resolve_entity_area_id(hass, "light.nonexistent", dev_reg=dev_reg) is None
    assert (
        resolve_entity_area_id(hass, ent_direct.entity_id, ent_reg=ent_reg) == "kitchen"
    )
    assert (
        resolve_entity_area_id(hass, ent_via_dev.entity_id, ent_reg=ent_reg)
        == "kitchen"
    )
    assert (
        resolve_entity_area_id(hass, ent_no_area.entity_id, ent_reg=ent_reg) is None
    )

    # apply_ha_display_precision (lines 137-140)
    sens_prec1 = register_entity(
        hass, "sensor.kitchen_prec1", platform="esphome_env", area_id="kitchen"
    )
    sens_prec1 = ent_reg.async_update_entity_options(
        sens_prec1.entity_id, "sensor", {"display_precision": 1}
    )
    sens_prec2 = register_entity(
        hass, "sensor.kitchen_prec2", platform="esphome_env", area_id="kitchen"
    )
    sens_prec2 = ent_reg.async_update_entity_options(
        sens_prec2.entity_id, "sensor", {"suggested_display_precision": 2}
    )
    assert apply_ha_display_precision(sens_prec1, 71.46, default_precision=0) == 71.5
    assert apply_ha_display_precision(sens_prec2, 71.456, default_precision=0) == 71.46

    # Ambient light edge branches (registry.py 202, 231-232, 275, 295, 328, 376-377)
    assert normalize_ambient_lux(float("nan")) == 0
    assert area_illuminance_sensor_choices(hass, None) == []

    global_cfg = get_global_config(hass)
    global_cfg[CONF_AREA_ILLUMINANCE_CONFIG] = {
        "kitchen": {
            "entity_id": "sensor.external_lux",
            "dark_lux": "bad_lux",
            "bright_lux": 100.0,
        }
    }
    kit_lux_cfg = area_illuminance_settings(hass, "kitchen")
    assert kit_lux_cfg["entity_id"] == "sensor.external_lux"
    hass.states.async_set(
        "sensor.external_lux",
        "25.0",
        {"device_class": "illuminance", "unit_of_measurement": "lx"},
    )
    register_entity(hass, "sensor.office_neg_lux", platform="esphome_env", area_id="office")
    hass.states.async_set(
        "sensor.office_neg_lux",
        "-5.0",
        {"device_class": "illuminance", "unit_of_measurement": "lx"},
    )
    register_entity(
        hass, "sensor.study_unavail_lux", platform="esphome_env", area_id="study"
    )
    hass.states.async_set(
        "sensor.study_unavail_lux",
        "unavailable",
        {
            "device_class": "illuminance",
            "unit_of_measurement": "lx",
            "friendly_name": "Study Lux",
        },
    )

    # Curation edge branches (curation.py 66-67, 81, 93, 135, 165, 189-190, 314, 321, 328, 334)
    st_light_off = State("light.dev_inherited", "off", {"brightness": "bad"})
    assert is_curated_area_entity(hass, st_light_off) is True
    assert get_entity_level(st_light_off) == 0
    assert (
        get_entity_level(State("light.bad_bri", "on", {"brightness": "not_num"})) == 100
    )
    st_clim_cur = State(
        "climate.study_unit",
        "heat",
        {"friendly_name": "Study Unit", "current_temperature": 69.4},
    )
    assert format_entity_slot_name(st_clim_cur) == "Study Unit (69°)"
    st_clim_low_only = State(
        "climate.low_only",
        "heat",
        {"target_temp_low": 67.5, "current_temperature": 68.0},
    )
    assert extract_climate_temps(st_clim_low_only) == (67.5, 68.0)

    assert find_area_media_entities(hass, None, "") == {"speaker": "", "remote": ""}
    register_entity(
        hass, "media_player.study_unavail", platform="music_assistant", area_id="study"
    )
    hass.states.async_set("media_player.study_unavail", "unavailable", {})
    register_entity(
        hass, "media_player.study_tv", platform="webostv", area_id="study"
    )
    hass.states.async_set("media_player.study_tv", "on", {"device_class": "tv"})
    register_entity(hass, "remote.study_unavail", platform="apple_tv", area_id="study")
    hass.states.async_set("remote.study_unavail", "unavailable", {})

    # Catalogs & telemetry sensor/climate fallbacks (catalogs 100, 119, 130, 135-136, 183-184, 221-223;
    # telemetry 86, 89-90, 115, 135-147, 205, 212, 276, 285-289, 346, 354, 358, 370)
    register_entity(hass, "light.garage_light", platform="hue", area_id="garage")
    hass.states.async_set("light.garage_light", "on", {})
    register_entity(
        hass, "sensor.a_garage_unavail_temp", platform="esphome_env", area_id="garage"
    )
    hass.states.async_set(
        "sensor.a_garage_unavail_temp",
        "unavailable",
        {"device_class": "temperature"},
    )
    register_entity(
        hass,
        "sensor.b_garage_hidden_temp",
        platform="esphome_env",
        area_id="garage",
        hidden_by=er.RegistryEntryHider.USER,
    )
    hass.states.async_set(
        "sensor.b_garage_hidden_temp", "70", {"device_class": "temperature"}
    )
    register_entity(
        hass, "sensor.c_garage_bad_temp", platform="esphome_env", area_id="garage"
    )
    hass.states.async_set(
        "sensor.c_garage_bad_temp", "bad_float", {"device_class": "temperature"}
    )
    register_entity(hass, "climate.garage_bad", platform="ecobee", area_id="garage")
    hass.states.async_set(
        "climate.garage_bad", "heat", {"current_temperature": "not_num"}
    )

    # Office: climate fallback telemetry + area_climates_summary (unavailable, hidden, prefix strip, max 6 cap)
    register_entity(hass, "climate.a_office_unavail", platform="ecobee", area_id="office")
    hass.states.async_set("climate.a_office_unavail", "unavailable", {})
    register_entity(
        hass,
        "climate.b_office_hidden",
        platform="ecobee",
        area_id="office",
        hidden_by=er.RegistryEntryHider.USER,
    )
    hass.states.async_set("climate.b_office_hidden", "heat", {"temperature": 70})
    for idx_c in range(7):
        cid = f"climate.c_office_{idx_c}"
        register_entity(hass, cid, platform="ecobee", area_id="office")
        hass.states.async_set(
            cid,
            "heat",
            {
                "friendly_name": f"Office Zone {idx_c}",
                "temperature": 70 + idx_c,
                "current_temperature": None if idx_c == 0 else 71.34,
                "current_humidity": "bad_hum" if idx_c == 0 else 45.67,
            },
        )

    # Rebuild AreaStateIndex explicitly while stopped (`idx.started == False`)
    idx = get_area_state_index(hass)
    assert idx.started is False
    idx.rebuild()

    kit_choices = area_illuminance_sensor_choices(hass, "kitchen")
    assert any(c["entity_id"] == "sensor.external_lux" for c in kit_choices)

    office_amb = resolve_area_ambient_light(hass, "office")
    assert office_amb["lux"] is None
    study_amb = resolve_area_ambient_light(hass, "study")
    assert study_amb["resolved_entity"] == "sensor.study_unavail_lux"
    assert study_amb["resolved_name"] == "Study Lux"
    assert study_amb["wire"] == ""

    assert find_area_media_entities(hass, "study", "") == {
        "speaker": "",
        "remote": "media_player.study_tv",
    }

    # get_home_wide_entities TOCTOU guard (line 100)
    with patch(
        "custom_components.latter.areas.catalogs.get_home_alarm_summary",
        return_value={"entity_id": "alarm_control_panel.vanished"},
    ):
        assert get_home_wide_entities(hass, "alarm_control_panel.vanished") == []

    areas_sum = get_areas_summary(hass)
    assert any(item["id"] == "garage" for item in areas_sum)

    assert len(get_area_entities(hass, "office", "climate")) == 7
    assert len(get_area_entities(hass, "garage", "bogus_domain_filter")) == 2

    # Climate telemetry: bad sensor skipped (line 115) & climate fallback (lines 135-147)
    gar_tel = get_area_climate_telemetry(hass, "garage")
    assert gar_tel["temperature"] is None
    off_tel = get_area_climate_telemetry(hass, "office")
    assert off_tel["temperature"] == 71.3
    assert off_tel["humidity"] == 45.7

    # get_home_hub_summary with stopped AreaStateIndex (line 205) & missing thermostat (line 212)
    hub_sum = get_home_hub_summary(
        hass,
        thermostat_entities=["climate.missing_one", "climate.c_office_1"],
    )
    assert len(hub_sum["thermostats"]) == 1
    assert hub_sum["thermostats"][0]["area_id"] == "office"

    # get_available_home_categories intercom branches (lines 276, 285-289)
    assert (
        get_available_home_categories(
            {"entity_id": ""}, {"intercom_available": True}, home_categories="intercom"
        )
        == "intercom"
    )
    global_cfg[CONF_BROADCAST_SPEAKERS] = ["media_player.study_tv"]
    assert (
        get_available_home_categories(
            {"entity_id": ""}, {}, home_categories="intercom", hass=hass
        )
        == "intercom"
    )

    # get_area_climates_summary (unavail skipped, hidden skipped, prefix stripped, capped at 6)
    area_climates = get_area_climates_summary(hass, "office")
    assert len(area_climates) == 6
    assert area_climates[0][1] == "Zone 0"

    # areas/sync.py edge branches (lines 37, 40-46)
    assert sync_esphome_device_area(hass, "", "kitchen") is None
    assert sync_esphome_device_area(hass, dev_with_area.id, None, allow_clear=False) is None

    global_cfg[CONF_BLE_AREA_SIGNATURES] = {
        "kitchen": {"scanners": {"aa:bb:cc:dd:ee:ff": {"mean": -60.0, "n": 3}}}
    }
    assert (
        sync_esphome_device_area(
            hass, dev_with_area.id, "office", require_ble_proxy_area=True
        )
        is None
    )
    synced_dev = dev_reg.async_get(dev_with_area.id)
    assert synced_dev is not None
    assert synced_dev.area_id == "kitchen"


async def test_areas_telemetry_listeners_fallback_debounce_and_shortcuts(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise broadcast phrase fallback, lux/fallback Area listeners, debounce push, and shortcut filters."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ensure_area(hass, "Empty Zone", area_id="empty_zone")

    # 1. Broadcast phrases fallback when coordinator.broadcast_phrases is not a list/tuple (line 377)
    coord.cached_area_payload = None
    with patch.object(
        type(coord), "broadcast_phrases", new_callable=PropertyMock, return_value=None
    ):
        _name, attrs = build_area_context_payload(coord)
    assert len(attrs["broadcast_phrases"]) == len(DEFAULT_BROADCAST_PHRASES)

    # 2. Explicit lux listener (_on_lux_or_sensor_event lines 619-623) isolated from AreaStateIndex
    global_cfg = get_global_config(hass)
    global_cfg[CONF_AREA_ILLUMINANCE_CONFIG] = {
        "living_room": {"entity_id": "sensor.explicit_lux_probe"}
    }
    hass.states.async_set(
        "sensor.explicit_lux_probe",
        "10.0",
        {"device_class": "illuminance", "unit_of_measurement": "lx"},
    )
    await hass.async_block_till_done()
    bind_coordinator_area_listeners(coord)

    with patch.object(
        coord, "async_notify_listeners", wraps=coord.async_notify_listeners
    ) as notify_spy:
        # Same state value (attribute-only change) -> ignored at lines 621-622
        hass.states.async_set(
            "sensor.explicit_lux_probe",
            "10.0",
            {
                "device_class": "illuminance",
                "unit_of_measurement": "lx",
                "friendly_name": "Renamed Lux",
            },
        )
        await hass.async_block_till_done()
        assert notify_spy.call_count == 0

        # Real state change -> notifies coordinator at line 623
        hass.states.async_set(
            "sensor.explicit_lux_probe",
            "22.5",
            {"device_class": "illuminance", "unit_of_measurement": "lx"},
        )
        await hass.async_block_till_done()
        assert notify_spy.call_count == 1

        # State removed (new_st is None) -> ignored at lines 621-622
        hass.states.async_remove("sensor.explicit_lux_probe")
        await hass.async_block_till_done()
        assert notify_spy.call_count == 1

    # 3. Shortcuts listener filtering (_build_shortcuts_listener lines 710-723)
    register_entity(hass, "light.shortcut_lamp", platform="hue", area_id="kitchen")
    hass.states.async_set(
        "light.shortcut_lamp",
        "on",
        {"friendly_name": "Kitchen Lamp", "icon": "mdi:lamp", "brightness": 100},
    )
    register_entity(
        hass,
        "media_player.shortcut_ma",
        platform="music_assistant",
        area_id="kitchen",
    )
    hass.states.async_set(
        "media_player.shortcut_ma",
        "playing",
        {"friendly_name": "Kitchen Speaker", "media_position": 10},
    )
    await hass.async_block_till_done()

    coord.update_device_config(
        {
            **coord.device_data,
            CONF_DOCK_ITEMS: [
                {
                    "kind": "entity",
                    "target": "light.shortcut_lamp",
                    "action": "toggle",
                    "label": "Lamp",
                },
                {
                    "kind": "entity",
                    "target": "media_player.shortcut_ma",
                    "action": "media_play_pause",
                    "label": "Speaker",
                },
            ],
        }
    )
    await hass.async_block_till_done()

    with patch.object(
        coord, "async_notify_listeners", wraps=coord.async_notify_listeners
    ) as sc_spy:
        # Media position-only tick -> ignored at lines 712-713
        hass.states.async_set(
            "media_player.shortcut_ma",
            "playing",
            {"friendly_name": "Kitchen Speaker", "media_position": 11},
        )
        await hass.async_block_till_done()
        assert sc_spy.call_count == 0

        # Non-visual attribute change (same state, icon, friendly_name) -> ignored at lines 714-722
        hass.states.async_set(
            "light.shortcut_lamp",
            "on",
            {"friendly_name": "Kitchen Lamp", "icon": "mdi:lamp", "brightness": 200},
        )
        await hass.async_block_till_done()
        assert sc_spy.call_count == 0

        # State change -> notifies coordinator at line 723
        hass.states.async_set(
            "light.shortcut_lamp",
            "off",
            {"friendly_name": "Kitchen Lamp", "icon": "mdi:lamp", "brightness": 200},
        )
        await hass.async_block_till_done()
        assert sc_spy.call_count == 1

    # 4. Non-indexed Area listener fallback (lines 642-676, 686) & debounced slot push (lines 744-749)
    global_cfg[CONF_AREA_ILLUMINANCE_CONFIG] = {}
    register_entity(hass, "light.lr_fallback_lamp", platform="hue", area_id="living_room")
    hass.states.async_set("light.lr_fallback_lamp", "off", {})
    register_entity(
        hass,
        "media_player.lr_fallback_ma",
        platform="music_assistant",
        area_id="living_room",
    )
    hass.states.async_set(
        "media_player.lr_fallback_ma",
        "playing",
        {"friendly_name": "LR Speaker", "media_position": 5},
    )
    register_entity(
        hass, "sensor.lr_auto_lux", platform="esphome_env", area_id="living_room"
    )
    hass.states.async_set(
        "sensor.lr_auto_lux",
        "14.0",
        {"device_class": "illuminance", "unit_of_measurement": "lx"},
    )
    await hass.async_block_till_done()

    idx = get_area_state_index(hass)
    idx.stop()
    scheduled_cbs: list[Any] = []

    def _capture_call_later(_hass: Any, _delay: float, action: Any) -> Any:
        scheduled_cbs.append(action)
        return lambda: None

    push_slots_mock = AsyncMock()
    coord.on_area_changed_push_slots = push_slots_mock

    with patch(
        "custom_components.latter.areas.telemetry.async_call_later",
        side_effect=_capture_call_later,
    ):
        bind_coordinator_area_listeners(coord)

        # Position-only tick on Area media_player -> suppressed at lines 644-647
        hass.states.async_set(
            "media_player.lr_fallback_ma",
            "playing",
            {"friendly_name": "LR Speaker", "media_position": 6},
        )
        await hass.async_block_till_done()
        assert scheduled_cbs == []

        # Real state change on Area light -> schedules debounce push at line 648
        hass.states.async_set("light.lr_fallback_lamp", "on", {})
        await hass.async_block_till_done()
        assert len(scheduled_cbs) == 1

        # Fire captured debounce callback -> runs _push_area_update lines 744-749
        scheduled_cbs.pop()(dt_util.utcnow())
        await hass.async_block_till_done()
        push_slots_mock.assert_awaited_once_with(coord)

        # Auto-discovered fallback lux listener fires on state change (lines 663-676)
        with patch.object(
            coord, "async_notify_listeners", wraps=coord.async_notify_listeners
        ) as lux_spy:
            hass.states.async_set(
                "sensor.lr_auto_lux",
                "35.0",
                {"device_class": "illuminance", "unit_of_measurement": "lx"},
            )
            await hass.async_block_till_done()
            assert lux_spy.call_count == 1

        # Empty Area with stopped index returns None from _build_active_area_listener (line 686)
        coord.async_set_active_area("empty_zone")
        assert _build_active_area_listener(coord, lambda: None) is None
        bind_coordinator_area_listeners(coord)
        await hass.async_block_till_done()

    idx.start()
    assert await hass.config_entries.async_unload(entry.entry_id) is True
