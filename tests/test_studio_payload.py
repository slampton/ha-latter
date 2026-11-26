"""Studio entity labels, ESPHome entity section classifier, pure catalog/time helpers, and live Studio state payloads."""

from __future__ import annotations

import json
from typing import Any
import unittest

from tests.conftest import (
    FRONTEND_SRC,
    LATTER_DIR,
    NODE_BIN as NODE,
    read_py_tree,
    read_ts_tree,
    run_studio_node_esm as _run_node_esm,
)

STUDIO_JS = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")


@unittest.skipUnless(NODE, "node is not installed")
class TestEntityLabels(unittest.TestCase):
    """D-061: labels from entity names use HA Sentence case while preserving acronyms & parenthesized units."""

    def test_entity_label_sentence_case(self) -> None:
        cases = {
            "Wake word": "Wake word",
            "Wake word 2": "Wake word 2",
            "Finished speaking detection": "Finished speaking detection",
            "Assist satellite": "Assist satellite",
            "wifi signal": "Wi-Fi signal",
            "BLE presence beacon": "BLE presence beacon",
            "iBeacon uuid": "iBeacon UUID",
            "Ram low water": "RAM low water",
            "Latency (ms)": "Latency (ms)",
            "Signal (dBm)": "Signal (dBm)",
            "ESPHome node": "ESPHome node",
            "security pin": "Security PIN",
        }
        got = _run_node_esm(
            f"""
            import {{ entityLabel }} from "./src/utils/format.js";
            const inputs = {json.dumps(list(cases))};
            process.stdout.write(JSON.stringify(inputs.map(entityLabel)));
            """
        )
        self.assertEqual(dict(zip(cases, got, strict=True)), cases)

    def test_every_entity_label_goes_through_it(self) -> None:
        format_ts = read_ts_tree("utils/format.ts")
        controls_ts = read_ts_tree("components/controls.ts", "components/controls")
        shared_ts = (FRONTEND_SRC / "views" / "system-shared-view.ts").read_text(encoding="utf-8")
        self.assertIn("export function entityLabel(", format_ts)
        self.assertIn("entityLabel(", controls_ts)
        self.assertIn("entityLabel(", shared_ts)
        self.assertNotIn("window.entityLabel", STUDIO_JS)


class TestEntitySections(unittest.TestCase):
    """Which Studio section a Device entity lands in."""

    def classify(
        self, entity_id: str, name: str, domain: str = "select", key: str | None = None
    ) -> str:
        from custom_components.latter.groups import esphome_inspector as entity_sections

        return entity_sections.classify_esphome_entity_section(
            entity_id,
            name,
            domain,
            "",
            "config",
            translation_key=key,
            device_object_prefixes=("latter_desk_display", "desk_display"),
        )

    def test_assist_satellite_entities_are_voice(self) -> None:
        self.assertEqual(
            self.classify("select.desk_display_assistant", "Assistant", key="pipeline"), "voice"
        )
        self.assertEqual(
            self.classify(
                "select.desk_display_finished_speaking_detection",
                "Finished speaking detection",
                key="vad_sensitivity",
            ),
            "voice",
        )
        self.assertEqual(
            self.classify("select.desk_display_wake_word", "Wake word", key="wake_word"), "voice"
        )
        self.assertEqual(
            self.classify("select.desk_display_wake_word_2", "Wake word 2", key="wake_word_n"),
            "voice",
        )
        self.assertEqual(
            self.classify(
                "assist_satellite.desk_display_assist_satellite",
                "Assist satellite",
                domain="assist_satellite",
            ),
            "voice",
        )

    def test_device_prefix_never_decides(self) -> None:
        self.assertEqual(
            self.classify("switch.desk_display_mute", "Mute", domain="switch"), "other"
        )
        self.assertEqual(
            self.classify("select.desk_display_voice_visual_profile", "Voice: Visual Profile"),
            "other",
        )
        self.assertEqual(
            self.classify("select.desk_display_display_clock_face", "Display: Clock Face"),
            "other",
        )

    def test_desk_power_and_battery_page_regression(self) -> None:
        from custom_components.latter.groups import esphome_inspector as entity_sections

        desk = [
            ("sensor.desk_assistant_battery_level", "Battery Level"),
            ("binary_sensor.desk_assistant_battery_charging", "Battery Charging"),
            ("switch.desk_assistant_speaker_enable", "Speaker Enable"),
            ("binary_sensor.desk_assistant_boot_button", "Boot Button"),
        ]
        sections: dict[str, list[dict[str, str]]] = {}
        for ent, name in desk:
            sec = entity_sections.classify_esphome_entity_section(
                ent,
                name,
                ent.split(".")[0],
                "",
                "config",
                device_object_prefixes=("desk_assistant",),
            )
            sections.setdefault(sec, []).append({"entity_id": ent})
        payload_sections = [
            {"id": sid, "title": sid, "items": items} for sid, items in sections.items()
        ]
        self.assertEqual(set(sections), {"other", "battery"})
        self.assertEqual(entity_sections.present_section_ids(payload_sections), {"other", "battery"})
        self.assertEqual(
            entity_sections.present_section_ids([{"id": "battery", "items": []}, "junk"]), set()
        )
        payload_src = read_py_tree("studio/payload.py")
        self.assertIn('sec_ids = present_section_ids(esphome_inspector.get("sections"))', payload_src)
        self.assertNotIn('("sleep" in sec_ids)', payload_src)
        self.assertIn('("battery" in sec_ids)', payload_src)
        self.assertNotIn('s.get("count"', payload_src)

    def test_ha_wake_word_is_the_one_wake_word_control(self) -> None:
        self.assertNotIn("active_wake", STUDIO_JS)
        self.assertNotIn("active wake", STUDIO_JS)
        audio_ts = (FRONTEND_SRC / "views" / "device-audio-view.ts").read_text(encoding="utf-8")
        self.assertIn('it.key === "wake_word"', audio_ts)
        self.assertIn('it.key === "wake_word_n"', audio_ts)

    def test_quick_action_buttons_always_classify_as_actions(self) -> None:
        from custom_components.latter.groups import esphome_inspector as entity_sections

        cases = [
            ("button.desk_display_actions_hibernate_device", "Actions: Hibernate Device"),
            ("button.desk_display_actions_restart_device", "Actions: Restart Device"),
            ("button.desk_display_restart", "Restart"),
        ]
        for ent_id, friendly in cases:
            with self.subTest(entity_id=ent_id, friendly=friendly):
                self.assertEqual(self.classify(ent_id, friendly, domain="button"), "actions")
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "sensor.desk_display_wi_fi_signal",
                "Wi-Fi Signal",
                "sensor",
                "signal_strength",
                "diagnostic",
                device_object_prefixes=("desk_display",),
            ),
            "network",
        )
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "sensor.desk_display_timer_ends",
                "Timer Ends",
                "sensor",
                "timestamp",
                "diagnostic",
                device_object_prefixes=("desk_display",),
            ),
            "network",
        )
        self.assertEqual(
            self.classify(
                "switch.desk_display_speaker_enable",
                "Speaker Enable",
                domain="switch",
            ),
            "other",
        )


@unittest.skipUnless(NODE, "node is not installed")
class TestStudioTimeAndCatalogLogic(unittest.TestCase):
    """Pure Studio TypeScript time formatting, alarm slots, capability catalog gates, and pref section overlay."""

    def test_universal_12h_vs_24h_time_and_alarm_formatters(self) -> None:
        got = _run_node_esm(
            """
            import {
              formatClockDuration,
              parseAlarmsSummary,
              serializeAlarmsSummary,
            } from "./src/domain/alarms.js";
            import {
              defaultLocaleTimeFormat,
              formatClockHhMm,
              formatHourSlot,
            } from "./src/utils/format.js";
            const slots = parseAlarmsSummary("19:30|1|0;08:30|0|2;09:00|0|2");
            const hours12 = Array.from({ length: 24 }, (_, h) => formatHourSlot(h, false));
            const hours24 = Array.from({ length: 24 }, (_, h) => formatHourSlot(h, true));
            process.stdout.write(JSON.stringify({
              tf24: defaultLocaleTimeFormat({ locale: { language: "en", time_format: "24" } }),
              tf12: defaultLocaleTimeFormat({ locale: { language: "en", time_format: "am_pm" } }),
              alarm12: formatClockHhMm(slots[0].time, false),
              alarm24: formatClockHhMm(slots[0].time, true),
              roundtrip: serializeAlarmsSummary(slots),
              hours12Sample: [hours12[0], hours12[7], hours12[12], hours12[22]],
              hours24Sample: [hours24[0], hours24[7], hours24[12], hours24[22]],
              durShort: formatClockDuration(125),
              durLong: formatClockDuration(3665),
            }));
            """
        )
        self.assertEqual(got["tf24"], "24-Hour")
        self.assertEqual(got["tf12"], "12-Hour (AM/PM)")
        self.assertEqual(got["alarm12"], "7:30 PM")
        self.assertEqual(got["alarm24"], "19:30")
        self.assertEqual(got["roundtrip"], "19:30|1|0;08:30|0|2;09:00|0|2")
        self.assertEqual(
            got["hours12Sample"], ["12:00 AM", "7:00 AM", "12:00 PM", "10:00 PM"]
        )
        self.assertEqual(got["hours24Sample"], ["00:00", "07:00", "12:00", "22:00"])
        self.assertEqual(got["durShort"], "02:05")
        self.assertEqual(got["durLong"], "01:01:05")

    def test_capability_catalog_filtering_and_pref_section_overlay(self) -> None:
        got = _run_node_esm(
            """
            import { GAMES_ITEMS_CATALOG, SHORTCUT_ROUTES_CATALOG, TOOLS_ITEMS_CATALOG } from "./src/constants.js";
            import {
              isCatalogItemSupported,
              overlayDevicePrefsOnSections,
            } from "./src/state/group-overlay.js";
            const roundImuCaps = { has_display: true, is_round: true, has_imu: true };
            const rectWallCaps = { has_display: true, is_round: false, has_imu: false };
            const unknownImuCaps = { has_display: true };
            const roundTools = TOOLS_ITEMS_CATALOG.filter((it) => isCatalogItemSupported(it, roundImuCaps)).map((it) => it.token);
            const rectTools = TOOLS_ITEMS_CATALOG.filter((it) => isCatalogItemSupported(it, rectWallCaps)).map((it) => it.token);
            const imuGames = GAMES_ITEMS_CATALOG.filter((it) => isCatalogItemSupported(it, roundImuCaps)).map((it) => it.token);
            const noImuGames = GAMES_ITEMS_CATALOG.filter((it) => isCatalogItemSupported(it, rectWallCaps)).map((it) => it.token);
            const unknownGames = GAMES_ITEMS_CATALOG.filter((it) => isCatalogItemSupported(it, unknownImuCaps)).map((it) => it.token);
            const imuGameRoutes = SHORTCUT_ROUTES_CATALOG.filter((it) => it.group === "Games" && isCatalogItemSupported(it, roundImuCaps)).map((it) => it.token);
            const noImuGameRoutes = SHORTCUT_ROUTES_CATALOG.filter((it) => it.group === "Games" && isCatalogItemSupported(it, rectWallCaps)).map((it) => it.token);
            const payload = {
              subentry_id: "sub_1",
              config: {
                kind: "device",
                device_group: "pocket_carry",
                home_screen_enabled: true,
                start_screen: "Home",
                is_roaming: true,
              },
              capabilities: rectWallCaps,
              device_groups: [
                { id: "pocket_carry", name: "Pocket Carry", device_config: { sync_device_area: false } },
              ],
              device_prefs: [
                { key: "sync_device_area", label: "Voice Follows Me", section: "audio", group_tier: "behavior", domain: "switch", value: false },
                { key: "bedtime_brightness", label: "Bedtime brightness", section: "power", group_tier: "behavior", domain: "number", value: 15 },
              ],
              esphome: {
                sections: [
                  {
                    id: "power",
                    title: "power",
                    items: [{ entity_id: "pref:bedtime_brightness", pref_key: "bedtime_brightness", domain: "number", name: "Bedtime brightness", state: "15" }],
                  },
                ],
              },
            };
            overlayDevicePrefsOnSections(payload, { home_screen_enabled: false, bedtime_brightness: 25 });
            const startAfterSingleApp = payload.config.start_screen;
            const bedtimeSectionState = payload.esphome.sections[0].items[0].state;
            overlayDevicePrefsOnSections(payload, { sync_device_area: true });
            const detachedGroup = payload.config.device_group;
            process.stdout.write(JSON.stringify({
              roundTools,
              rectTools,
              imuGames,
              noImuGames,
              unknownGames,
              imuGameRoutes,
              noImuGameRoutes,
              startAfterSingleApp,
              bedtimeSectionState,
              detachedGroup,
            }));
            """
        )
        self.assertIn("level", got["roundTools"])
        self.assertNotIn("level", got["rectTools"])
        self.assertIn("flashlight", got["rectTools"])
        self.assertEqual(got["imuGames"], ["marbles", "archery", "bricks", "chomp"])
        self.assertEqual(got["noImuGames"], ["blocks", "snake", "drop_four", "marbles"])
        self.assertEqual(
            got["unknownGames"],
            ["blocks", "snake", "drop_four", "marbles", "archery", "bricks", "chomp"],
        )
        self.assertEqual(
            got["imuGameRoutes"],
            ["games:marbles", "games:archery", "games:bricks", "games:chomp"],
        )
        self.assertEqual(
            got["noImuGameRoutes"],
            ["games:marbles", "games:blocks", "games:snake", "games:drop_four"],
        )
        self.assertEqual(got["startAfterSingleApp"], "Time App")
        self.assertEqual(got["bedtimeSectionState"], "25")
        self.assertEqual(got["detachedGroup"], "custom")


async def test_build_studio_state_payload_device_ble_tag_and_system_scopes(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify real Home Assistant Studio state payload builder across Device, BLE Tag, and System scopes."""
    from custom_components.latter.studio.payload import build_studio_state_payload
    from tests.helpers.ha_setup import register_entity

    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    assert coord is not None
    tag_coord = sys_obj.coordinators["sub_tag"]

    # Seed representative ESPHome entities on the bound device
    esp_dev_id = coord.esphome_device_id
    assert esp_dev_id is not None
    for eid, name, state in (
        ("select.pocket_assistant_wake_word", "Wake word", "okay_nabu"),
        ("button.pocket_assistant_actions_find_my_device", "Actions: Find My Device", "unknown"),
        ("sensor.pocket_assistant_battery_level", "Battery level", "84"),
    ):
        register_entity(
            hass,
            eid,
            platform="esphome",
            device_id=esp_dev_id,
            original_name=name,
            translation_key="wake_word" if eid.endswith("_wake_word") else None,
        )
        hass.states.async_set(eid, state)

    dev_payload = build_studio_state_payload(hass, coord, include_catalog=True)
    assert dev_payload["config"]["kind"] == "device"
    assert "catalog" in dev_payload
    assert dev_payload["capabilities"]["has_display"] is True
    sys_dev_map = {d["subentry_id"]: d for d in dev_payload["system_devices"]}
    assert sys_dev_map[coord.subentry_id]["has_imu"] is coord.has_imu
    assert sys_dev_map[tag_coord.subentry_id]["has_imu"] is False
    assert any(p["key"] == "time_format" for p in dev_payload["device_prefs"])
    sec_by_id = {s["id"]: s["items"] for s in dev_payload["esphome"]["sections"]}
    assert any(it["entity_id"] == "select.pocket_assistant_wake_word" for it in sec_by_id["voice"])
    assert any(
        it["entity_id"] == "button.pocket_assistant_actions_find_my_device"
        for it in sec_by_id["actions"]
    )

    # Diet payload omits catalog while preserving device sections & system_devices
    diet_payload = build_studio_state_payload(hass, coord, include_catalog=False)
    assert "catalog" not in diet_payload
    assert len(diet_payload["system_devices"]) == 2

    # BLE tag payload marks kind="ble_tag" with empty hardware display sections
    ble_payload = build_studio_state_payload(hass, tag_coord, include_catalog=False)
    assert ble_payload["config"]["kind"] == "ble_tag"
    assert ble_payload["capabilities"]["has_display"] is False

    # System-only payload (coordinator=None) works cleanly without an active device
    sys_payload = build_studio_state_payload(hass, None, include_catalog=True)
    assert "system_config" in sys_payload
    assert "catalog" in sys_payload
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_studio_payload_skip_sections_and_single_pass_optimizations(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify skip_sections omits all 9 heavy sections without HMAC-signing catalogs, computes device_group once per device, and caches BLE tag model lookups."""
    from unittest.mock import patch

    from custom_components.latter.const import (
        CONF_SCREENSAVER_PHOTO_IDS,
        CONF_WALLPAPER_FAVORITES,
        CONF_WALLPAPER_MODE,
        CONF_WALLPAPER_SOURCE,
    )
    from custom_components.latter.studio import payload as payload_mod
    from custom_components.latter.studio.state_gates import HEAVY_SUBSCRIPTION_SECTIONS

    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    assert coord is not None
    tag_coord = sys_obj.coordinators["sub_tag"]
    coord.update_device_config(
        {
            **coord.device_data,
            CONF_WALLPAPER_MODE: "single",
            CONF_WALLPAPER_SOURCE: "preset:ocean_waves",
            CONF_WALLPAPER_FAVORITES: ["preset:ocean_waves", "missing_photo_id"],
            CONF_SCREENSAVER_PHOTO_IDS: ["preset:ocean_waves", "missing_ss_id"],
        }
    )
    coord.current_wallpaper = "preset:ocean_waves"

    # 1) Skipping all 9 heavy sections omits them, skips list_wallpaper_catalog entirely,
    #    yet still computes active thumb URL and cleans favorite/screensaver ID lists.
    with patch.object(
        payload_mod, "list_wallpaper_catalog", side_effect=AssertionError("should not be called")
    ):
        slim = payload_mod.build_studio_state_payload(
            hass,
            coord,
            include_catalog=True,
            skip_sections=HEAVY_SUBSCRIPTION_SECTIONS,
        )
    for skipped_key in HEAVY_SUBSCRIPTION_SECTIONS:
        assert skipped_key not in slim
    assert "catalog" in slim
    assert slim["config"]["wallpaper_favorites"] == ["preset:ocean_waves"]
    assert slim["config"]["screensaver_photo_ids"] == ["preset:ocean_waves"]
    assert "preset%3Aocean_waves" in slim["live"]["active_wallpaper_thumb_url"]
    assert "&sig=" in slim["live"]["active_wallpaper_thumb_url"]

    # 2) Full payload resolves device_group ONCE per non-BLE-tag coordinator (not 300+ times)
    from custom_components.latter.groups.device_groups import resolve_effective_device_group

    grp_calls: list[str] = []

    def _spy_resolve_grp(*args: Any, **kwargs: Any) -> str:
        grp_calls.append(args[1].subentry_id)
        return resolve_effective_device_group(*args, **kwargs)

    with patch.object(payload_mod, "resolve_effective_device_group", side_effect=_spy_resolve_grp):
        payload_mod.build_studio_state_payload(hass, coord, include_catalog=False)
    assert grp_calls == [coord.subentry_id]

    # 3) BLE tag model description is cached across repeated pushes (zero repeated BT scans)
    payload_mod._BLE_MODEL_CACHE.clear()
    with patch.object(
        payload_mod, "describe_ble_target_model", return_value="Apple AirTag"
    ) as mock_desc:
        p1 = payload_mod.build_studio_state_payload(hass, tag_coord, include_catalog=False)
        p2 = payload_mod.build_studio_state_payload(hass, tag_coord, include_catalog=False)
    assert mock_desc.call_count == 1
    row1 = next(d for d in p1["system_devices"] if d["subentry_id"] == tag_coord.subentry_id)
    row2 = next(d for d in p2["system_devices"] if d["subentry_id"] == tag_coord.subentry_id)
    assert row1["model_label"] == "Apple AirTag"
    assert row2["model_label"] == "Apple AirTag"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


if __name__ == "__main__":
    unittest.main()
