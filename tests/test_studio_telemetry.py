"""Studio diagnostics telemetry, BLE tag capability routing, walk-around survey state, and discovered hardware payloads."""

from __future__ import annotations

from typing import Any
import unittest

from tests.conftest import (
    NODE_BIN as NODE,
    run_studio_node_esm as _run_node_esm,
)


@unittest.skipUnless(NODE, "node is not installed")
class TestStudioStoreTelemetryAndPresenceState(unittest.TestCase):
    """Pure StudioStore capability view predicates, walk-around BLE calibration state, and pause/resume streams."""

    def test_device_has_view_capability_and_ble_tag_guards(self) -> None:
        got = _run_node_esm(
            """
            import { StudioStore, deviceHasView } from "./src/state/store.js";
            const host = {
              isConnected: false,
              addController() {},
              removeController() {},
              requestUpdate() {},
              updateComplete: Promise.resolve(true),
            };
            const store = new StudioStore(host);
            store.activeSubentryId = "sub_ble";
            store.state = {
              subentry_id: "sub_ble",
              config: { kind: "ble_tag" },
              capabilities: { has_display: false, has_audio: false, has_voice: false, has_power: false },
              system_devices: [{ subentry_id: "sub_ble", kind: "ble_tag" }],
            };
            const bleViews = ["dashboard", "display", "interface", "audio_voice", "power", "presence", "tools"]
              .filter((v) => store.deviceHasView(v));
            const headlessViews = ["dashboard", "display", "interface", "audio_voice", "power", "presence", "tools"]
              .filter((v) => deviceHasView(v, { has_display: false, has_audio: true, has_voice: true, has_power: false }, "device"));
            process.stdout.write(JSON.stringify({ bleViews, headlessViews }));
            """
        )
        self.assertEqual(got["bleViews"], ["dashboard", "presence", "tools"])
        self.assertEqual(
            got["headlessViews"], ["dashboard", "audio_voice", "presence", "tools"]
        )

    def test_system_presence_walk_around_state_and_ble_stream_pause_resume(self) -> None:
        got = _run_node_esm(
            """
            import { StudioStore } from "./src/state/store.js";
            const sysCalls = [];
            const host = {
              isConnected: false,
              addController() {},
              removeController() {},
              requestUpdate() {},
              updateComplete: Promise.resolve(true),
            };
            const store = new StudioStore(host);
            store.ws.runSystemCommand = async (command, payload, activeSubentryId) => {
              sysCalls.push({ command, payload, activeSubentryId });
              return null;
            };
            store.ingestPayload({
              subentry_id: "sub_desk",
              device_config_rev: 1,
              system_config: {
                ble_away_timeout_s: 180,
                ble_max_radius_m: 12,
                ble_max_velocity_mps: 3.5,
                ble_attenuation: 2.2,
              },
              system_devices: [
                {
                  subentry_id: "sub_desk",
                  title: "Desk Assistant",
                  has_ble: true,
                  ble_tracked: false,
                  kind: "device",
                  active_area_name: "Office",
                  ble_packets_seen: 0,
                  ble_survey_rows: [],
                },
                {
                  subentry_id: "sub_pocket",
                  title: "Pocket Assistant",
                  has_ble: true,
                  ble_tracked: true,
                  kind: "device",
                  active_area_name: "Bedroom",
                  ble_packets_seen: 14,
                  ble_survey_rows: [
                    {
                      area_id: "bedroom",
                      area_name: "Bedroom",
                      scanner_source: "AA:BB:CC:DD:EE:01",
                      scanner_name: "Bedroom Proxy",
                      raw_rssi: -58,
                      effective_rssi: -57,
                      offset_db: 1.0,
                      distance_m: 1.2,
                      age_seconds: 1,
                      is_fresh: true,
                      is_winner: true,
                    },
                  ],
                },
                {
                  subentry_id: "sub_tag",
                  title: "Keyring Tag",
                  has_ble: false,
                  ble_tracked: false,
                  kind: "ble_tag",
                  active_area_name: "Kitchen",
                  ble_packets_seen: 5,
                  ble_survey_rows: [],
                },
              ],
              ble_area_signatures: [
                { area_id: "bedroom", area_name: "Bedroom", floor_id: "upstairs", has_ble_proxy: true, has_signature: true, scanner_count: 2, sample_count: 18, captured_at: "2026-11-16T20:00:00Z" },
                { area_id: "office", area_name: "Office", floor_id: "downstairs", has_ble_proxy: false, has_signature: false, scanner_count: 0, sample_count: 0, captured_at: "" },
              ],
              discovered_ble_devices: [
                { title: "Zoe's Watch", target_address: "device_tracker.watch_ble", kind: "Private BLE", is_tracker: true, rssi: -58, area_name: "Office" },
                { title: "Living TV BLE", target_address: "11:22:33:44:55:66", kind: "Named BLE", is_tracker: false, rssi: -79, area_name: "Living Area" },
              ],
            }, false);

            const defaultSurveyAfterFilter = store.bleSurveySubentryId;
            store.groups.selectBleCalibrateArea("office", true);
            const handoffActiveAfterSelect = store.bleCalibrateHandoffActive;
            await store.groups.captureBleAreaSignature("office");
            const handoffAfterCapture = store.bleCalibrateHandoffActive;

            store.groups.toggleBleLiveStream(false);
            store.applyBleSurveyDelta({
              type: "ble_survey_delta",
              subentry_id: "sub_pocket",
              ble_packets_seen: 99,
              ble_survey_rows: [{ area_id: "kitchen", area_name: "Kitchen", scanner_source: "AA:BB:CC:DD:EE:99", scanner_name: "Kitchen Proxy", raw_rssi: -42, effective_rssi: -42, offset_db: 0, distance_m: 0.5, age_seconds: 0, is_fresh: true, is_winner: true }],
            });
            const afterPausedDeltaDev = structuredClone(store.groups.getActiveSurveyDevice());

            store.groups.toggleBleLiveStream(true);
            store.applyBleSurveyDelta({
              type: "ble_survey_delta",
              subentry_id: "sub_pocket",
              ble_packets_seen: 42,
              ble_survey_rows: [{ area_id: "kitchen", area_name: "Kitchen", scanner_source: "AA:BB:CC:DD:EE:99", scanner_name: "Kitchen Proxy", raw_rssi: -44, effective_rssi: -44, offset_db: 0, distance_m: 0.6, age_seconds: 0, is_fresh: true, is_winner: true }],
            });
            const afterResumedDeltaDev = structuredClone(store.groups.getActiveSurveyDevice());

            store.toggleDiscoveredBlePause(true);
            const frozenCount = store.discoveredBleFrozenSnapshot?.length || 0;
            store.evictAdoptedBleCandidate("11:22:33:44:55:66");
            const frozenAfterEvict = store.discoveredBleFrozenSnapshot?.length || 0;

            process.stdout.write(JSON.stringify({
              defaultSurveyAfterFilter,
              handoffActiveAfterSelect,
              handoffAfterCapture,
              afterPausedDeltaDev,
              afterResumedDeltaDev,
              sysCalls,
              frozenCount,
              frozenAfterEvict,
            }));
            """
        )
        self.assertEqual(got["defaultSurveyAfterFilter"], "sub_pocket")
        self.assertTrue(got["handoffActiveAfterSelect"])
        self.assertFalse(got["handoffAfterCapture"])
        self.assertEqual(got["afterPausedDeltaDev"]["ble_packets_seen"], 14)
        self.assertEqual(got["afterResumedDeltaDev"]["ble_packets_seen"], 42)
        self.assertEqual(got["sysCalls"][0]["command"], "capture_ble_area_signature")
        self.assertEqual(got["frozenCount"], 2)
        self.assertEqual(got["frozenAfterEvict"], 1)


async def test_studio_telemetry_link_report_and_discovered_devices_payload(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify link report, firmware update, discovered/ignored Latter devices, and telemetry RPC in Studio payload."""
    from custom_components.latter.const import (
        CONF_IGNORED_DISCOVERED_DEVICES,
    )
    from custom_components.latter.hub_registry import get_global_config
    from custom_components.latter.studio.payload import build_studio_state_payload
    from tests.helpers.ha_setup import ensure_area, register_entity

    ensure_area(hass, "Kitchen", area_id="kitchen")
    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    assert coord is not None
    esp_dev_id = coord.esphome_device_id
    assert esp_dev_id is not None

    # Seed diagnostic & update entities on the bound ESPHome device (including a C6 co-processor update
    # that sorts alphabetically before Project Firmware to verify the ESP32-P4 primary-update tie-breaker)
    for eid, name, state, cat in (
        ("update.pocket_assistant_aaa_c6_co_processor_firmware", "System: C6 Co-Processor Firmware", "off", "config"),
        ("update.pocket_assistant_firmware", "Firmware", "on", "config"),
        ("sensor.pocket_assistant_wifi_signal", "Wi-Fi signal", "-54", "diagnostic"),
        ("sensor.pocket_assistant_ip_address", "IP address", "192.168.1.44", "diagnostic"),
        ("sensor.pocket_assistant_battery_level", "Battery Level", "82", "diagnostic"),
        ("binary_sensor.pocket_assistant_battery_charging", "Battery Charging", "on", "diagnostic"),
        (
            "sensor.pocket_assistant_system_link_report",
            "System: Link Report",
            "up=7320 rst=POWERON bto=1 disc=2 rsn=0 rssi=-55/-62 n=120",
            "diagnostic",
        ),
    ):
        register_entity(
            hass,
            eid,
            platform="esphome",
            device_id=esp_dev_id,
            original_name=name,
        )
        attrs: dict[str, Any] = {"friendly_name": name}
        if eid.startswith("update."):
            attrs.update({"installed_version": "3.0.0", "latest_version": "3.0.1"})
        if cat:
            attrs["entity_category"] = cat
        hass.states.async_set(eid, state, attrs)

    # Seed one newly discovered Latter display and one ignored Latter display
    disc_dev, _ = make_esphome_device(
        hass,
        slug="kitchen_panel",
        mac="aa:bb:cc:22:33:44",
        name="Kitchen Panel",
        area_id="kitchen",
        stationary=1,
    )
    ignored_dev, _ = make_esphome_device(
        hass,
        slug="test_bench",
        mac="aa:bb:cc:22:33:55",
        name="Test Bench",
        area_id=None,
        stationary=0,
    )
    get_global_config(hass)[CONF_IGNORED_DISCOVERED_DEVICES] = [ignored_dev.id]

    # Dispatch live device_telemetry RPC
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "device_telemetry",
        {
            "link_json": {"state": "connected", "rssi": -58, "uptime_s": 7320, "reset_reason": "POWERON"},
            "int_ram_free_kb": 64,
            "int_ram_min_kb": 48,
            "int_ram_largest_kb": 32,
            "psram_min_kb": 4096,
            "ble_active": True,
            "profiler_on": False,
        },
    )

    payload = build_studio_state_payload(hass, coord, include_catalog=True)
    assert payload["live"]["fw_update_available"] is True
    assert payload["live"]["fw_update_entity"] == "update.pocket_assistant_firmware"
    assert payload["live"]["telemetry"]["int_ram_free_kb"] == 64
    alex_person = next(
        p for p in payload["catalog"]["persons"] if p["id"] == "person.alex"
    )
    assert "(sensor.latter_system_alex_current_area)" in alex_person["name"]

    dev_summary = next(
        d for d in payload["system_devices"] if d["subentry_id"] == coord.subentry_id
    )
    assert dev_summary["ip_address"] == "192.168.1.44"
    assert dev_summary["battery_level"] == 82
    assert dev_summary["is_charging"] is True

    disc_ids = [d["esphome_device_id"] for d in payload["discovered_latter_devices"]]
    ignored_ids = [d["esphome_device_id"] for d in payload["ignored_latter_devices"]]
    assert disc_dev.id in disc_ids
    assert ignored_dev.id not in disc_ids
    assert ignored_dev.id in ignored_ids
    assert payload["system_info"]["integration_version"] == "3.0.0"
    assert await hass.config_entries.async_unload(entry.entry_id) is True


if __name__ == "__main__":
    unittest.main()
