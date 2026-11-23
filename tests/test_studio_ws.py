"""Studio WS client, optimistic overlay, quick actions sorting, store controllers, handoff state, and 7,447 MDI catalog."""

from __future__ import annotations

from typing import Any
import unittest

from tests.conftest import (
    NODE_BIN as NODE,
    read_py_tree,
    read_ts_tree,
    run_studio_node_esm as _run_node_esm,
)


@unittest.skipUnless(NODE, "node is not installed")
class TestLiveConditionalRows(unittest.TestCase):
    """A Device entity change shows at once and survives payloads that still carry the old state."""

    def test_pending_state_overlay(self) -> None:
        got = _run_node_esm(
            """
            import { overlayPendingEntityStates } from "./src/state/group-overlay.js";
            const pending = new Map();
            const payload = (state) => ({
              esphome: { sections: [{ id: "voice", title: "voice", items: [{ entity_id: "select.x_wake_word_mode", domain: "select", name: "Wake word mode", state }] }] },
            });
            const out = {};
            pending.set("select.x_wake_word_mode", { state: "Always On", expires: Date.now() + 5000 });
            let p = payload("Disabled");
            overlayPendingEntityStates(p, pending);
            out.staleAnswer = p.esphome.sections[0].items[0].state;
            out.stillPending = pending.size;
            p = payload("Always On");
            overlayPendingEntityStates(p, pending);
            out.confirmed = p.esphome.sections[0].items[0].state;
            out.clearedAfterConfirm = pending.size;
            pending.set("number.x_volume", { state: "70", expires: Date.now() + 5000 });
            p = { esphome: { sections: [{ id: "sound", title: "sound", items: [{ entity_id: "number.x_volume", domain: "number", name: "Volume", state: "70.0" }] }] } };
            overlayPendingEntityStates(p, pending);
            out.numericMatch = pending.size;
            pending.set("select.x_wake_word_mode", { state: "Always On", expires: Date.now() - 1 });
            p = payload("Disabled");
            overlayPendingEntityStates(p, pending);
            out.expired = [p.esphome.sections[0].items[0].state, pending.size];
            process.stdout.write(JSON.stringify(out));
            """
        )
        self.assertEqual(
            got,
            {
                "staleAnswer": "Always On",
                "stillPending": 1,
                "confirmed": "Always On",
                "clearedAfterConfirm": 0,
                "numericMatch": 0,
                "expired": ["Disabled", 0],
            },
        )

    def test_wiring(self) -> None:
        state_ts = read_ts_tree("state")
        self.assertIn("overlayPendingEntityStates(", state_ts)
        self.assertIn("executeEntityAction(", state_ts)
        cmds = read_py_tree(
            "studio/commands.py",
            "studio/system_commands.py",
            "studio/device_commands.py",
        )
        self.assertRegex(
            cmds,
            r"async_track_state_change_event\(\s*hass,\s*entity_ids,\s*_entity_changed\s*\)",
        )
        self.assertIn("_track_device_states()", cmds)


@unittest.skipUnless(NODE, "node is not installed")
class TestQuickActionsSorting(unittest.TestCase):
    """Quick-action buttons sort deterministically by canonical rank regardless of entity state."""

    def test_quick_action_ordering(self) -> None:
        got = _run_node_esm(
            """
            globalThis.document ??= { createTreeWalker: () => ({}), createComment: () => ({}) };
            const { sortQuickActionButtons } = await import("./src/components/controls/entity-adapters.js");
            const shuffled = [
              { entity_id: "button.pocket_assistant_actions_restart_device", domain: "button", name: "Restart Device", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_hibernate_device", domain: "button", name: "Hibernate Device", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_activate_screensaver", domain: "button", name: "Activate Screensaver", state: "unavailable" },
              { entity_id: "button.pocket_assistant_actions_trigger_voice_assistant", domain: "button", name: "Trigger Voice Assistant", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_find_my_device", domain: "button", name: "Find My Device", state: "2026-11-12T18:00:00+00:00" },
            ];
            const sorted = sortQuickActionButtons(shuffled);
            process.stdout.write(JSON.stringify(sorted.map((it) => it.entity_id)));
            """
        )
        self.assertEqual(
            got,
            [
                "button.pocket_assistant_actions_find_my_device",
                "button.pocket_assistant_actions_trigger_voice_assistant",
                "button.pocket_assistant_actions_activate_screensaver",
                "button.pocket_assistant_actions_hibernate_device",
                "button.pocket_assistant_actions_restart_device",
            ],
        )


@unittest.skipUnless(NODE, "node is not installed")
class TestWallpaperUploadBearerAuth(unittest.TestCase):
    """D-025: POST /api/latter/wallpaper/upload uses live hass.auth Bearer token, never auth/sign_path."""

    def test_xhr_bearer_header_preflight_refresh_and_401_retry(self) -> None:
        got = _run_node_esm(
            """
            import { StudioWsClient } from "./src/api/ws-client.js";
            const wsCalls = [];
            const xhrLog = [];
            let nextResponses = [];
            globalThis.XMLHttpRequest = class MockXHR {
              constructor() {
                this.headers = {};
                this.upload = {};
                this.status = 0;
                this.response = null;
                this.responseType = "";
              }
              open(method, url) {
                this.method = method;
                this.url = url;
              }
              setRequestHeader(k, v) {
                this.headers[k] = v;
              }
              send(form) {
                const step = nextResponses.shift() || { status: 200, body: { ok: true } };
                xhrLog.push({
                  method: this.method,
                  url: this.url,
                  auth: this.headers.Authorization || "",
                  scope: form.get("scope"),
                  subentryId: form.get("subentry_id"),
                });
                if (this.upload && this.upload.onprogress) {
                  this.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
                }
                this.status = step.status;
                this.response = step.body;
                this.onload();
              }
            };
            let refreshCalls = 0;
            const auth = {
              data: { access_token: "tok_live" },
              expired: false,
              async refreshAccessToken() {
                refreshCalls += 1;
                auth.expired = false;
                auth.data.access_token = `tok_refreshed_${refreshCalls}`;
              },
            };
            const client = new StudioWsClient(() => {});
            client.setHass({
              auth,
              async callWS(msg) {
                wsCalls.push(msg.type);
                throw new Error(`Unexpected WS call: ${msg.type}`);
              },
            });
            const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "crater.png", { type: "image/png" });
            const progress = [];
            nextResponses = [{ status: 200, body: { ok: true, source_id: "upload:_system/crater_1a2b3c.jpg" } }];
            const sysRes = await client.uploadWallpaperMultipart({
              scope: "system",
              file,
              onProgress: (p) => progress.push(p),
            });
            auth.expired = true;
            nextResponses = [{ status: 200, body: { ok: true, source_id: "upload:desk/crater_1a2b3c.jpg" } }];
            const devRes = await client.uploadWallpaperMultipart({
              scope: "device",
              subentryId: "sub_desk",
              file,
            });
            nextResponses = [
              { status: 401, body: null },
              { status: 200, body: { ok: true, source_id: "upload:_system/retry_ok.jpg" } },
            ];
            const skewRes = await client.uploadWallpaperMultipart({ scope: "system", file });
            nextResponses = [{ status: 401, body: null }, { status: 401, body: null }];
            let persistentErr = "";
            try {
              await client.uploadWallpaperMultipart({ scope: "system", file });
            } catch (err) {
              persistentErr = err.message;
            }
            process.stdout.write(JSON.stringify({
              wsCalls, refreshCalls, progress, sysRes, devRes, skewRes, persistentErr, xhrLog,
            }));
            """
        )
        self.assertEqual(got["wsCalls"], [])
        self.assertEqual(got["refreshCalls"], 3)
        self.assertEqual(got["progress"], [50, 100])
        self.assertEqual(got["sysRes"]["source_id"], "upload:_system/crater_1a2b3c.jpg")
        self.assertEqual(got["devRes"]["source_id"], "upload:desk/crater_1a2b3c.jpg")
        self.assertEqual(got["skewRes"]["source_id"], "upload:_system/retry_ok.jpg")
        self.assertEqual(got["persistentErr"], "Wallpaper upload failed (HTTP 401)")
        self.assertEqual(len(got["xhrLog"]), 6)


@unittest.skipUnless(NODE, "node is not installed")
class TestStudioInteractiveFlows(unittest.TestCase):
    """Focus-safe input detection, keydown isolation, world clock domain, group batch controllers, handoff state, and 7,447 MDI catalog."""

    def test_focus_guard_keydown_isolation_and_world_clocks_domain(self) -> None:
        got = _run_node_esm(
            """
            globalThis.document ??= { createTreeWalker: () => ({}), createComment: () => ({}) };
            globalThis.customElements ??= { get: () => undefined, define() {} };
            import { WORLD_CLOCK_ZONES_CATALOG } from "./src/constants.js";
            import {
              isValidWorldClockZone,
              parseWorldClocksSpec,
              sanitizeClockLabel,
              serializeWorldClocksSpec,
            } from "./src/domain/world-clocks.js";
            const { LatterStudio } = await import("./src/latter-studio.js");
            const { isActivelyFocusedTextControl } = await import("./src/lib/lit.js");

            const rootObj = { activeElement: null };
            const textEl = { tagName: "INPUT", type: "text", getRootNode: () => rootObj };
            const rangeEl = { tagName: "INPUT", type: "range", getRootNode: () => rootObj };
            rootObj.activeElement = textEl;
            const focusedText = isActivelyFocusedTextControl(textEl);
            rootObj.activeElement = rangeEl;
            const focusedRange = isActivelyFocusedTextControl(rangeEl);
            rootObj.activeElement = null;
            const blurredText = isActivelyFocusedTextControl(textEl);

            function runKeyDown(key, opts = {}) {
              let stopped = false;
              const fakeInner = { tagName: opts.tagName || "INPUT" };
              const ev = {
                key,
                ctrlKey: Boolean(opts.ctrlKey),
                metaKey: Boolean(opts.metaKey),
                altKey: Boolean(opts.altKey),
                composedPath: () => [fakeInner],
                stopPropagation() { stopped = true; },
              };
              LatterStudio.prototype._onRootKeyDown.call({}, ev);
              return stopped;
            }

            const parsed = parseWorldClocksSpec("Westminster|Europe/London; ;Invalid|UTC");
            const serialized = serializeWorldClocksSpec([
              ...parsed,
              { label: sanitizeClockLabel("  Akron; OH | "), iana: "America/New_York" },
            ]);
            process.stdout.write(JSON.stringify({
              focusedText,
              focusedRange,
              blurredText,
              stopLetterA: runKeyDown("a"),
              stopLetterC: runKeyDown("c"),
              allowEscape: !runKeyDown("Escape"),
              allowTab: !runKeyDown("Tab"),
              allowCtrlC: !runKeyDown("c", { ctrlKey: true }),
              allowButtonKey: !runKeyDown("c", { tagName: "BUTTON" }),
              firstCatalogZone: WORLD_CLOCK_ZONES_CATALOG[0],
              lastCatalogZone: WORLD_CLOCK_ZONES_CATALOG[WORLD_CLOCK_ZONES_CATALOG.length - 1],
              rejectPinnedUtc: isValidWorldClockZone("UTC"),
              acceptIana: isValidWorldClockZone("America/New_York"),
              liveUntrimmed: sanitizeClockLabel("Main ", 32, false),
              committedTrimmed: sanitizeClockLabel("Main "),
              serialized,
            }));
            """
        )
        self.assertTrue(got["focusedText"])
        self.assertFalse(got["focusedRange"])
        self.assertFalse(got["blurredText"])
        self.assertTrue(got["stopLetterA"])
        self.assertTrue(got["stopLetterC"])
        self.assertTrue(got["allowEscape"])
        self.assertTrue(got["allowTab"])
        self.assertTrue(got["allowCtrlC"])
        self.assertTrue(got["allowButtonKey"])
        self.assertEqual(got["firstCatalogZone"]["iana"], "Etc/GMT+12")
        self.assertEqual(got["lastCatalogZone"]["iana"], "Pacific/Kiritimati")
        self.assertFalse(got["rejectPinnedUtc"])
        self.assertTrue(got["acceptIana"])
        self.assertEqual(got["liveUntrimmed"], "Main ")
        self.assertEqual(got["committedTrimmed"], "Main")
        self.assertEqual(got["serialized"], "Westminster|Europe/London;Akron OH|America/New_York")

    def test_groups_staged_batch_controls_timers_and_non_detaching_bedtime_preview(self) -> None:
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
            store.activeSubentryId = "sub_mobile";
            store.ingestPayload({
              subentry_id: "sub_mobile",
              device_config_rev: 1,
              title: "Mobile Assistant",
              config: {
                kind: "device",
                device_slug: "mobile_assistant",
                device_group: "custom",
                native_ble_tracking: true,
              },
              live: {
                timer_running: true,
                timer_ends_at: "2026-11-19T00:02:05Z",
                stopwatch_running: true,
                stopwatch_started_at: "2026-11-18T22:58:55Z",
              },
              pref_specs: [
                { key: "bedtime_active", label: "Bedtime mode", section: "power", group_tier: null, domain: "switch", default: false, options: [] },
                { key: "bedtime_display", label: "Idle display in bedtime", section: "power", group_tier: "behavior", domain: "select", default: "Screen Off", options: ["Screen Off", "Ambient Clock"] },
                { key: "sync_device_area", label: "Voice Follows Me", section: "audio", group_tier: "behavior", domain: "switch", default: false, options: [] },
              ],
              device_groups: [
                { id: "pocket_carry", name: "Pocket Carry", description: "Compact displays", builtin: true, device_config: { sync_device_area: false } },
              ],
              system_devices: [
                { subentry_id: "sub_mobile", title: "Mobile Assistant", device_slug: "mobile_assistant", kind: "device", is_online: true, device_group: "custom" },
                { subentry_id: "sub_pocket", title: "Pocket Assistant", device_slug: "pocket_assistant", kind: "device", is_online: true, device_group: "pocket_carry" },
              ],
            }, false);

            store.liveClockNowMs = Date.parse("2026-11-19T00:00:00Z");
            const timerRemaining = store.activeTimerRemainingSec();
            const stopwatchElapsed = store.activeStopwatchElapsedSec();

            store.groups.stageBatchSetting("bedtime_active", true);
            const detachBedtimeOnly = store.groups.previewBatchDetachmentCount();
            store.groups.stageBatchSetting("bedtime_display", "Ambient Clock");
            const detachWithPolicy = store.groups.previewBatchDetachmentCount();
            store.groups.resetBatchDraft();

            store.groups.requestResetDeviceGroup("pocket_carry", "Pocket Carry", 1);
            await store.tools.runConfirmedAction();
            store.newGroupName = "Patio Panels";
            await store.groups.createDeviceGroup();
            store.groups.stageBatchSetting("sync_device_area", true);
            await store.groups.applyBatchDraft();
            store.groups.openSaveGroupModal();
            store.saveGroupModal = { ...store.saveGroupModal, name: " Alex Carry ", description: "Personal handheld" };
            await store.groups.confirmSaveGroupModal();

            process.stdout.write(JSON.stringify({
              timerRemaining,
              stopwatchElapsed,
              detachBedtimeOnly,
              detachWithPolicy,
              sysCalls,
            }));
            """
        )
        self.assertEqual(got["timerRemaining"], 125)
        self.assertEqual(got["stopwatchElapsed"], 3665)
        self.assertEqual(got["detachBedtimeOnly"], 0)
        self.assertEqual(got["detachWithPolicy"], 1)
        self.assertEqual(
            [c["command"] for c in got["sysCalls"]],
            [
                "update_group_baseline",
                "create_device_group",
                "apply_batch_device_setting",
                "create_device_group",
            ],
        )
        self.assertEqual(
            got["sysCalls"][0]["payload"],
            {"group_id": "pocket_carry", "reset_to_default": True},
        )

    def test_full_7447_mdi_catalog_and_ranked_search(self) -> None:
        """Lazy `latter-studio-mdi.js` chunk unpacks all 7,447 icons in 1:1 parity with firmware."""
        got = _run_node_esm(
            """
            import { PACKED_MDI_CHUNKS } from "../custom_components/latter/frontend/latter-studio-mdi.js";
            import { SHORTCUT_ROUTES_CATALOG } from "./src/constants.js";
            import {
              getAllMdiIcons,
              isKnownMdiIcon,
              isMdiCatalogLoaded,
              registerPackedMdiChunks,
              ROUTE_PREVIEW_ICONS,
              searchMdiIcons,
            } from "./src/mdi-catalog.js";
            const beforeLoaded = isMdiCatalogLoaded();
            registerPackedMdiChunks(PACKED_MDI_CHUNKS);
            const afterLoaded = isMdiCatalogLoaded();
            const all = getAllMdiIcons();
            const teddy = searchMdiIcons("teddy-bear");
            const multiWord = searchMdiIcons("teddy bear");
            const empty = searchMdiIcons("");
            const missingRouteIcons = SHORTCUT_ROUTES_CATALOG
              .map((r) => r.token)
              .filter((tok) => !ROUTE_PREVIEW_ICONS[tok] || !isKnownMdiIcon(ROUTE_PREVIEW_ICONS[tok]));
            process.stdout.write(JSON.stringify({
              beforeLoaded,
              afterLoaded,
              count: all.length,
              hasTeddyBear: isKnownMdiIcon("mdi:teddy-bear"),
              hasBareTeddy: isKnownMdiIcon("teddy-bear"),
              unknownFake: isKnownMdiIcon("mdi:definitely-not-an-icon-xyz"),
              teddyTop: teddy.items[0],
              multiWordTop: multiWord.items[0],
              emptyTotal: empty.totalMatches,
              missingRouteIcons,
            }));
            """
        )
        self.assertTrue(got["beforeLoaded"])
        self.assertTrue(got["afterLoaded"])
        self.assertEqual(got["count"], 7447)
        self.assertEqual(got["missingRouteIcons"], [])
        self.assertTrue(got["hasTeddyBear"])
        self.assertTrue(got["hasBareTeddy"])
        self.assertFalse(got["unknownFake"])
        self.assertEqual(got["teddyTop"], "mdi:teddy-bear")
        self.assertEqual(got["multiWordTop"], "mdi:teddy-bear")
        self.assertEqual(got["emptyTotal"], 7447)

    def test_section_handoff_state_machine_and_css_tokens(self) -> None:
        got = _run_node_esm(
            """
            globalThis.document ??= { createTreeWalker: () => ({}), createComment: () => ({}) };
            globalThis.dispatchEvent ??= () => true;
            import { StudioStore } from "./src/state/store.js";
            const { STUDIO_STYLES } = await import("./src/styles/tokens.js");
            globalThis.history = { pushState() {}, replaceState() {} };
            const host = {
              isConnected: false,
              addController() {},
              removeController() {},
              requestUpdate() {},
              dispatchEvent() { return true; },
              updateComplete: Promise.resolve(true),
            };
            const store = new StudioStore(host);
            store.activeSubentryId = "sub_1";
            store.deviceSelected = true;
            store.state = {
              subentry_id: "sub_1",
              device_config_rev: 1,
              config: { kind: "device", device_slug: "alex_pocket", device_group: "handhelds" },
              system_devices: [{ subentry_id: "sub_1", title: "Alex Pocket", kind: "device", is_online: true, has_display: true }],
            };

            store.openSystemSection("area_tracking", "area-box-living");
            const areaTargets = Array.from(store.handoffTargetIds);
            const areaScroll = store.pendingScrollCardId;

            store.openSystemSection("shared_entities", "card-cameras-doorbell", ["card-cameras-doorbell", "card-calendars"]);
            const sharedTargets = Array.from(store.handoffTargetIds);

            store.openSystemSection("remotes");
            const remotesTargets = Array.from(store.handoffTargetIds);

            store.openManageGroups("handhelds");
            const groupsTargets = Array.from(store.handoffTargetIds);
            const groupOpen = store.openGroupIds.has("handhelds");

            store.openDeviceSection("tools", "card-device-diagnostics");
            const devTargetsBefore = Array.from(store.handoffTargetIds);
            store.hostUpdated();
            store.onMainFocusIn({
              target: { tagName: "BUTTON", id: "other-btn", parentElement: { id: "card-replace-hardware", parentElement: null } },
            });
            const devTargetsAfterOutsideFocus = Array.from(store.handoffTargetIds);

            const cssText = Array.isArray(STUDIO_STYLES)
              ? STUDIO_STYLES.map((s) => s.cssText).join("\\n")
              : STUDIO_STYLES.cssText;
            process.stdout.write(JSON.stringify({
              cssText,
              areaTargets,
              areaScroll,
              sharedTargets,
              remotesTargets,
              groupsTargets,
              groupOpen,
              devTargetsBefore,
              devTargetsAfterOutsideFocus,
            }));
            """
        )
        self.assertIn("--studio-handoff-surface:", got["cssText"])
        self.assertEqual(got["areaTargets"], ["area-box-living"])
        self.assertEqual(got["areaScroll"], "area-box-living")
        self.assertEqual(got["sharedTargets"], ["card-cameras-doorbell", "card-calendars"])
        self.assertEqual(got["remotesTargets"], [])
        self.assertEqual(got["groupsTargets"], ["group-box-handhelds"])
        self.assertTrue(got["groupOpen"])
        self.assertEqual(got["devTargetsBefore"], ["card-device-diagnostics"])
        self.assertEqual(got["devTargetsAfterOutsideFocus"], [])


async def test_studio_ws_get_state_and_subscribe_catalog_diet(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify live Studio WS `get_state` and `subscribe` enforce the catalog diet across pushes and registry updates."""
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant.common import async_fire_time_changed

    from custom_components.latter.const import STUDIO_REV
    from tests.helpers.ble_and_ws import call_ws, make_ws_connection
    from tests.helpers.ha_setup import ensure_area, flush_debouncers

    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    assert coord is not None
    conn = make_ws_connection(hass)

    res = await call_ws(
        hass,
        conn,
        1,
        "latter/system/get_state",
        subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    assert res is not None and res["success"] is True
    assert "catalog" in res["result"]

    sub_res = await call_ws(
        hass,
        conn,
        2,
        "latter/system/subscribe",
        subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    assert sub_res is not None and sub_res["success"] is True
    await hass.async_block_till_done()
    initial_events = [m for m in conn.sent if m.get("id") == 2 and m.get("type") == "event"]
    assert initial_events
    assert "catalog" in initial_events[0]["event"]

    # Subsequent coordinator notify omits catalog (diet)
    conn.sent.clear()
    coord.async_update_listeners()
    await flush_debouncers(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    diet_events = [m for m in conn.sent if m.get("id") == 2 and m.get("type") == "event"]
    assert diet_events
    assert "catalog" not in diet_events[-1]["event"]

    # Area registry mutation marks CatalogGate dirty so next push carries catalog again
    conn.sent.clear()
    ensure_area(hass, "Sunroom", area_id="sunroom")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    reg_events = [m for m in conn.sent if m.get("id") == 2 and m.get("type") == "event"]
    assert reg_events
    assert any("catalog" in ev["event"] for ev in reg_events)
    conn.subscriptions.pop(2)()
    assert await hass.config_entries.async_unload(entry.entry_id) is True


if __name__ == "__main__":
    unittest.main()
