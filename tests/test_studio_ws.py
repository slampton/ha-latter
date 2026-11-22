"""Studio WS client, optimistic overlay, quick actions, time card, batch modals, section handoff, and MDI catalog."""

from __future__ import annotations

import unittest

from tests.conftest import (
    LATTER_DIR,
    NODE_BIN as NODE,
    read_py_tree,
    run_studio_node_esm as _run_node_esm,
)

STUDIO_JS = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")


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
        self.assertIn("overlayPendingEntityStates(", STUDIO_JS)
        self.assertIn("executeEntityAction(", STUDIO_JS)
        cmds = read_py_tree("studio/commands.py", "studio/cmd_presence_devices.py", "studio/cmd_photos_media.py", "studio/cmd_groups_security.py")
        self.assertRegex(
            cmds,
            r"async_track_state_change_event\(\s*hass,\s*entity_ids,\s*_entity_changed\s*\)",
        )
        self.assertIn("_track_device_states()", cmds)


@unittest.skipUnless(NODE, "node is not installed")
class TestQuickActionsControls(unittest.TestCase):
    """Stateless HA button entities (`state === 'unknown'`) render enabled unless offline (`forceDisabled`)."""

    def test_quick_action_ordering_unknown_state_and_offline_disable(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToContainer } from "./test/fake-store.js";
            import {
              renderNativeControlRow,
              renderQuickActionGrid,
              sortQuickActionButtons,
            } from "./src/components/controls.js";
            const shuffled = [
              { entity_id: "button.pocket_assistant_actions_restart_device", domain: "button", name: "Restart Device", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_hibernate_device", domain: "button", name: "Hibernate Device", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_activate_screensaver", domain: "button", name: "Activate Screensaver", state: "unavailable" },
              { entity_id: "button.pocket_assistant_actions_trigger_voice_assistant", domain: "button", name: "Trigger Voice Assistant", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_find_my_device", domain: "button", name: "Find My Device", state: "2026-11-12T18:00:00+00:00" },
            ];
            const sorted = sortQuickActionButtons(shuffled);
            const { store } = makeFakeStore();
            const calls = [];
            store.entity.espAction = async (eid, action, _opt, toast) => {
              calls.push({ eid, action, toast });
              return true;
            };
            const gridEl = renderToContainer(renderQuickActionGrid(store, shuffled));
            const btns = gridEl.querySelectorAll("button");
            const gridStates = btns.map((b) => ({
              disabled: b.disabled,
              svgHtml: b.querySelector("svg")?.outerHTML || "",
              label: b.textContent.trim(),
            }));
            btns[0].click();
            btns[2].click(); // disabled -> no-op
            btns[3].click();
            btns[4].click();
            const offlineGridEl = renderToContainer(renderQuickActionGrid(store, shuffled, true));
            const allDisabledOffline = offlineGridEl.querySelectorAll("button").every((b) => b.disabled);
            const rowUnknown = renderToContainer(renderNativeControlRow(store, {
              entity_id: "button.pocket_system_log_memory_report",
              domain: "button",
              name: "Log Memory Report",
              state: "unknown",
            }));
            const rowUnavail = renderToContainer(renderNativeControlRow(store, {
              entity_id: "button.pocket_system_log_memory_report",
              domain: "button",
              name: "Log Memory Report",
              state: "unavailable",
            }));
            const swUnknown = renderToContainer(renderNativeControlRow(store, {
              entity_id: "switch.pocket_home_sun",
              domain: "switch",
              name: "Sun",
              state: "unknown",
            }));
            process.stdout.write(JSON.stringify({
              sortedIds: sorted.map((it) => it.entity_id),
              gridStates,
              calls,
              allDisabledOffline,
              rowButtonUnknownDisabled: rowUnknown.querySelector("button")?.disabled,
              rowButtonUnavailDisabled: rowUnavail.querySelector("button")?.disabled,
              switchUnknownDisabled: swUnknown.querySelector("input")?.disabled,
            }));
            """
        )
        self.assertEqual(
            got["sortedIds"],
            [
                "button.pocket_assistant_actions_find_my_device",
                "button.pocket_assistant_actions_trigger_voice_assistant",
                "button.pocket_assistant_actions_activate_screensaver",
                "button.pocket_assistant_actions_hibernate_device",
                "button.pocket_assistant_actions_restart_device",
            ],
        )
        self.assertEqual(
            [st["disabled"] for st in got["gridStates"]],
            [False, False, True, False, False],
        )
        self.assertEqual(len({st["svgHtml"] for st in got["gridStates"]}), 5)
        self.assertEqual(len(got["calls"]), 3)
        self.assertEqual(
            [c["eid"] for c in got["calls"]],
            [
                "button.pocket_assistant_actions_find_my_device",
                "button.pocket_assistant_actions_hibernate_device",
                "button.pocket_assistant_actions_restart_device",
            ],
        )
        self.assertTrue(got["allDisabledOffline"])
        self.assertFalse(got["rowButtonUnknownDisabled"])
        self.assertTrue(got["rowButtonUnavailDisabled"])
        self.assertTrue(got["switchUnknownDisabled"])


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
    """Time card focus-safe typing, group batch controls, bedtime batch preview, section handoff, and 7,447 MDI catalog."""

    def test_time_card_focus_safe_typing_and_manual_world_clock_add(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { SimEvent } from "./test/dom-shim.js";
            import { makeFakeStore, renderToContainer } from "./test/fake-store.js";
            import { WORLD_CLOCK_ZONES_CATALOG } from "./src/constants.js";
            import { renderAppConfigModalBody } from "./src/components/dialogs.js";
            import { focusSafe, html, render } from "./src/lib/lit.js";
            import { LatterStudio } from "./src/latter-studio.js";
            // 1. focusSafe() preserves focused text input across background updates
            const tplInput = (val) => html`<input id="t" type="text" .value=${focusSafe(val)} />`;
            const box = renderToContainer(tplInput("Init"));
            document.body.appendChild(box);
            const inp = box.querySelector("#t");
            inp.focus();
            inp.value = "M";
            render(tplInput(""), box);
            const preservedWhileFocused = inp.value;
            inp.blur();
            render(tplInput("Synced"), box);
            const updatedAfterBlur = inp.value;
            // 2. ShadowRoot keydown isolation stops HA single-key shortcuts on INPUT
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
            // 3. World clock manual city label flow
            const { store, toasts } = makeFakeStore({
              activeSubentryId: "sub_1",
              state: {
                config: {
                  kind: "device",
                  local_clock_label: "",
                  world_clocks: "Westminster|Europe/London",
                },
              },
            });
            store.appConfigModal = { open: true, app: "time" };
            const stagedCalls = [];
            store.entity.stageDeviceSetting = (key, val, domId, debounceMs) => {
              stagedCalls.push({ key, val, domId, debounceMs });
              store.state.config[key] = val;
            };
            const modalRoot = renderToContainer(renderAppConfigModalBody(store));
            store.host.renderRoot = modalRoot;
            const localInput = modalRoot.querySelector("#cfg-local_clock_label");
            localInput.value = "Main ";
            localInput.dispatchEvent(new SimEvent("input", { bubbles: true }));
            const localDomDuringTyping = localInput.value;
            const localInputStagedVal = stagedCalls[0]?.val;
            localInput.dispatchEvent(new SimEvent("change", { bubbles: true }));
            const localChangeStagedVal = stagedCalls[1]?.val;
            const zoneSelect = modalRoot.querySelector("#cfg-world_clocks_add");
            zoneSelect.value = "America/New_York";
            zoneSelect.dispatchEvent(new SimEvent("change", { bubbles: true }));
            const labelAfterZonePick = store.worldClockNewLabel;
            const stagedWorldClocksAfterPick = stagedCalls.filter((c) => c.key === "world_clocks").length;
            modalRoot.querySelector("#btn-world_clock_add").click();
            const toastOnMissingCity = toasts[toasts.length - 1]?.msg || "";
            const newCityInput = modalRoot.querySelector("#cfg-world_clock_new_label");
            newCityInput.value = "Akron, OH";
            newCityInput.dispatchEvent(new SimEvent("input", { bubbles: true }));
            modalRoot.querySelector("#btn-world_clock_add").click();
            process.stdout.write(JSON.stringify({
              preservedWhileFocused,
              updatedAfterBlur,
              stopLetterA: runKeyDown("a"),
              stopLetterC: runKeyDown("c"),
              allowEscape: !runKeyDown("Escape"),
              allowTab: !runKeyDown("Tab"),
              allowCtrlC: !runKeyDown("c", { ctrlKey: true }),
              allowButtonKey: !runKeyDown("c", { tagName: "BUTTON" }),
              firstCatalogZone: WORLD_CLOCK_ZONES_CATALOG[0],
              lastCatalogZone: WORLD_CLOCK_ZONES_CATALOG[WORLD_CLOCK_ZONES_CATALOG.length - 1],
              localDomDuringTyping,
              localStagedCall: stagedCalls[0],
              localInputStagedVal,
              localChangeStagedVal,
              labelAfterZonePick,
              stagedWorldClocksAfterPick,
              toastOnMissingCity,
              finalWorldClocks: store.state.config.world_clocks,
              clearedDraftLabel: store.worldClockNewLabel,
              clearedDraftZone: store.worldClockNewZone,
            }));
            """
        )
        self.assertEqual(got["preservedWhileFocused"], "M")
        self.assertEqual(got["updatedAfterBlur"], "Synced")
        self.assertTrue(got["stopLetterA"])
        self.assertTrue(got["stopLetterC"])
        self.assertTrue(got["allowEscape"])
        self.assertTrue(got["allowTab"])
        self.assertTrue(got["allowCtrlC"])
        self.assertTrue(got["allowButtonKey"])
        self.assertEqual(got["firstCatalogZone"]["iana"], "Etc/GMT+12")
        self.assertEqual(got["lastCatalogZone"]["iana"], "Pacific/Kiritimati")
        self.assertEqual(got["localDomDuringTyping"], "Main ")
        self.assertEqual(got["localStagedCall"]["key"], "local_clock_label")
        self.assertEqual(got["localInputStagedVal"], "Main ")
        self.assertEqual(got["localChangeStagedVal"], "Main")
        self.assertEqual(got["labelAfterZonePick"], "")
        self.assertEqual(got["stagedWorldClocksAfterPick"], 0)
        self.assertTrue(got["toastOnMissingCity"])
        self.assertEqual(
            got["finalWorldClocks"],
            "Westminster|Europe/London;Akron, OH|America/New_York",
        )
        self.assertEqual(got["clearedDraftLabel"], "")
        self.assertEqual(got["clearedDraftZone"], "")

    def test_groups_boxes_staged_batch_controls_and_save_custom_modal(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDeviceOverviewView } from "./src/views/device-overview-view.js";
            import { renderSystemGroupsView } from "./src/views/system-groups-view.js";
            import { renderSystemToolsView } from "./src/views/system-tools-view.js";
            const { store, sysCalls } = makeFakeStore({
              activeSubentryId: "sub_mobile",
              state: {
                title: "Mobile Assistant",
                system_info: { ha_version: "2026.11.0", integration_version: "3.0.0", min_firmware_sdk_rev: 2026111801, studio_rev: 34 },
                config: {
                  kind: "device",
                  device_slug: "mobile_assistant",
                  device_group: "custom",
                  assigned_person: "person.alex",
                  device_remote_group: "area_auto",
                  native_ble_tracking: true,
                },
                capabilities: { has_display: true, has_battery: true, is_roaming_device: true },
                live: { active_area_name: "Office" },
                device_groups: [
                  { id: "pocket_carry", name: "Pocket Carry", description: "Compact displays", builtin: true, include_display: false, include_interface: false, device_config: { tap_to_wake: "Docked Only", native_ble_tracking: true } },
                  { id: "handhelds", name: "Handhelds", description: "Battery displays", builtin: true, include_display: false, include_interface: false, device_config: { tap_to_wake: "Single Tap", native_ble_tracking: true } },
                  { id: "guest_suites", name: "Guest Suites", description: "Guest displays", builtin: false, include_display: true, include_interface: true, device_config: { clock_face: "Hybrid Digital" } },
                ],
                system_devices: [
                  { subentry_id: "sub_mobile", title: "Mobile Assistant", device_slug: "mobile_assistant", kind: "device", has_display: true, has_battery: true, is_online: true, is_roaming: true, ble_tracked: true, device_group: "custom", device_group_name: "Custom", status_code: "online", status_label: "Online" },
                  { subentry_id: "sub_pocket", title: "Pocket Assistant", device_slug: "pocket_assistant", kind: "device", has_display: true, has_battery: true, is_online: true, is_roaming: true, ble_tracked: true, device_group: "pocket_carry", device_group_name: "Pocket Carry", status_code: "online", status_label: "Online" },
                ],
                system_controls: [
                  {
                    key: "audio:switch:voice follows me",
                    pref_key: "sync_device_area",
                    tier: "behavior",
                    section: "audio",
                    section_title: "Audio",
                    name: "Voice Follows Me",
                    domain: "switch",
                    state: "off",
                    options: [],
                    targets: [
                      { device_slug: "mobile_assistant", device_group: "custom", is_online: true, is_roaming: true, pref_key: "sync_device_area", state: "on" },
                      { device_slug: "pocket_assistant", device_group: "pocket_carry", is_online: true, is_roaming: true, pref_key: "sync_device_area", state: "off" },
                    ],
                  },
                ],
              },
            });
            const groupsHtml = renderToHtml(renderSystemGroupsView(store));
            store.groups.requestResetDeviceGroup("pocket_carry", "Pocket Carry", 1);
            await store.tools.runConfirmedAction();
            store.groups.toggleNewGroupForm(true);
            const groupsCreateOpenHtml = renderToHtml(renderSystemGroupsView(store));
            store.newGroupName = "Patio Panels";
            await store.groups.createDeviceGroup();
            // Stage a Batch control change and apply it
            store.groups.stageBatchSetting("sync_device_area", true);
            await store.groups.applyBatchDraft();
            store.groups.openSaveGroupModal();
            store.saveGroupModal = { ...store.saveGroupModal, name: " Alex Carry ", description: "Personal handheld" };
            await store.groups.confirmSaveGroupModal();
            const overviewCustomHtml = renderToHtml(renderDeviceOverviewView(store));
            const sysToolsHtml = renderToHtml(renderSystemToolsView(store));
            // Active timer & stopwatch via UTC ISO anchors (`timer_ends_at`, `stopwatch_started_at`)
            store.liveClockNowMs = Date.parse("2026-11-19T00:00:00Z");
            store.state.config.device_group = "handhelds";
            store.state.live = {
              ...store.state.live,
              timer_running: true,
              timer_paused: false,
              timer_remaining_sec: 125,
              timer_ends_at: "2026-11-19T00:02:05Z",
              stopwatch_running: true,
              stopwatch_paused: false,
              stopwatch_elapsed_sec: 3665,
              stopwatch_started_at: "2026-11-18T22:58:55Z",
              alarm_ringing: true,
            };
            const overviewGroupHtml = renderToHtml(renderDeviceOverviewView(store));
            process.stdout.write(JSON.stringify({
              groupsHtml,
              groupsCreateOpenHtml,
              overviewCustomHtml,
              overviewGroupHtml,
              sysToolsHtml,
              sysCalls,
            }));
            """
        )
        self.assertIn('id="btn-open-create-group"', got["groupsHtml"])
        self.assertIn('id="group-box-pocket_carry"', got["groupsHtml"])
        self.assertIn('id="btn-reset-group-pocket_carry"', got["groupsHtml"])
        self.assertNotIn('id="btn-reset-group-guest_suites"', got["groupsHtml"])
        self.assertIn('id="group-box-custom"', got["groupsHtml"])
        self.assertIn('id="btn-batch-reset"', got["groupsHtml"])
        self.assertIn('id="btn-batch-apply"', got["groupsHtml"])
        self.assertIn('id="create-group-form"', got["groupsCreateOpenHtml"])
        self.assertIn('id="btn-save-custom-group"', got["overviewCustomHtml"])
        self.assertNotIn('id="btn-save-custom-group"', got["overviewGroupHtml"])
        self.assertIn('id="overview-ringing-alert"', got["overviewGroupHtml"])
        self.assertIn("02:05", got["overviewGroupHtml"])
        self.assertIn("01:01:05", got["overviewGroupHtml"])
        self.assertIn('id="card-support-diagnostics"', got["sysToolsHtml"])
        self.assertIn('id="btn-download-system-diagnostics"', got["sysToolsHtml"])
        self.assertIn('id="btn-copy-system-info"', got["sysToolsHtml"])
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

    def test_section_handoff_blue_highlights_vs_whole_page_navigation(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { STUDIO_STYLES } from "./src/styles/tokens.js";
            import { renderDeviceToolsView } from "./src/views/device-tools-view.js";
            import { renderSystemGroupsView } from "./src/views/system-groups-view.js";
            import { renderSystemPresenceView } from "./src/views/system-presence-view.js";
            import { renderSystemRemotesView } from "./src/views/system-remotes-view.js";
            import { renderSystemSharedView } from "./src/views/system-shared-view.js";
            globalThis.history = { pushState() {}, replaceState() {} };
            globalThis.requestAnimationFrame = (cb) => { cb(0); return 1; };
            const { store, scrolled } = makeFakeStore({
              activeSubentryId: "sub_1",
              deviceSelected: true,
              state: {
                device_groups: [{ id: "handhelds", name: "Handhelds", description: "Portable", builtin: true, device_config: {} }],
                system_devices: [{ subentry_id: "sub_1", title: "Alex Pocket", kind: "device", is_online: true, has_display: true, is_roaming: true, ble_tracked: true, active_area_name: "Living Room", device_group: "handhelds" }],
                live: { area_presence_grid: [{ area_id: "living", area_name: "Living Room", is_occupied: true, confidence_pct: 90, occupant_names: ["Alex"] }] },
                ble_area_signatures: [{ area_id: "living", area_name: "Living Room", has_ble_proxy: true, has_signature: false, scanner_count: 1, sample_count: 0, captured_at: "" }],
                system_config: { camera_entities: ["camera.front"], calendar_entities: ["calendar.home"], remotes_list: ["remote.tv"], remote_groups: [{ id: "rg1", name: "Living TV", area_id: "living", remotes: ["remote.tv"] }] },
                config: { kind: "device", device_slug: "alex_pocket", device_group: "handhelds" },
              },
            });
            store.openSystemSection("area_tracking", "area-box-living");
            store.applyRoute({ prefix: "/latter", path: "/system/presence" });
            store.hostUpdated();
            await Promise.resolve();
            const presenceHtml = renderToHtml(renderSystemPresenceView(store));
            store.openSystemSection("shared_entities", "card-cameras-doorbell", ["card-cameras-doorbell", "card-calendars"]);
            const sharedCamCalHtml = renderToHtml(renderSystemSharedView(store));
            store.openSystemSection("remotes");
            const remotesWholePageHtml = renderToHtml(renderSystemRemotesView(store));
            store.openManageGroups("handhelds");
            const groupsTargetedHtml = renderToHtml(renderSystemGroupsView(store));
            store.openDeviceSection("tools", "card-device-diagnostics");
            const devToolsHtml = renderToHtml(renderDeviceToolsView(store));
            store.hostUpdated();
            store.onMainFocusIn({
              target: { tagName: "BUTTON", id: "other-btn", parentElement: { id: "card-replace-hardware", parentElement: null } },
            });
            const devToolsClearedHtml = renderToHtml(renderDeviceToolsView(store));
            process.stdout.write(JSON.stringify({
              cssText: Array.isArray(STUDIO_STYLES) ? STUDIO_STYLES.map((s) => s.styleSheetText).join("\\n") : STUDIO_STYLES.styleSheetText,
              scrolled,
              presenceHtml,
              sharedCamCalHtml,
              remotesWholePageHtml,
              groupsTargetedHtml,
              devToolsHtml,
              devToolsClearedHtml,
            }));
            """
        )
        self.assertIn("--studio-handoff-surface:", got["cssText"])
        self.assertIn('id="area-box-living" class="area-presence-box handoff-active"', got["presenceHtml"])
        self.assertEqual(
            got["scrolled"][0],
            {"id": "area-box-living", "opts": {"behavior": "smooth", "block": "start"}},
        )
        self.assertEqual(got["sharedCamCalHtml"].count("handoff-active"), 2)
        self.assertNotIn("handoff-active", got["remotesWholePageHtml"])
        self.assertIn('id="group-box-handhelds" class="area-presence-box handoff-active"', got["groupsTargetedHtml"])
        self.assertIn('id="card-device-diagnostics" class="card handoff-active"', got["devToolsHtml"])
        self.assertNotIn("handoff-active", got["devToolsClearedHtml"])

    def test_device_power_bedtime_card_and_non_detaching_batch_preview(self) -> None:
        """Verify D-068: #card-bedtime-mode hides schedule hours until enabled and staging bedtime_active does not warn of group detachment."""
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDevicePowerView } from "./src/views/device-power-view.js";
            function buildPower(schedOn) {
              return makeFakeStore({
                activeSubentryId: "sub_1",
                state: {
                  device_prefs: [
                    { key: "tap_to_wake", label: "Tap to wake", section: "power", group_tier: "behavior", domain: "select", value: "Single Tap", options: ["Single Tap", "Disabled"] },
                    { key: "bedtime_active", label: "Bedtime mode", section: "power", group_tier: null, domain: "switch", value: false, options: [] },
                    { key: "bedtime_display", label: "Idle display in bedtime", section: "power", group_tier: "behavior", domain: "select", value: "Screen Off", options: ["Screen Off", "Ambient Clock"] },
                    { key: "bedtime_schedule", label: "Bedtime schedule", section: "power", group_tier: "behavior", domain: "switch", value: schedOn, options: [] },
                    { key: "bedtime_start_hour", label: "Bedtime starts", section: "power", group_tier: "behavior", domain: "number", value: 22, options: [], min: 0, max: 23, step: 1, unit: ":00" },
                    { key: "bedtime_end_hour", label: "Bedtime ends", section: "power", group_tier: "behavior", domain: "number", value: 7, options: [], min: 0, max: 23, step: 1, unit: ":00" },
                  ],
                  pref_specs: [
                    { key: "bedtime_active", label: "Bedtime mode", section: "power", group_tier: null, domain: "switch", default: false, options: [] },
                    { key: "bedtime_display", label: "Idle display in bedtime", section: "power", group_tier: "behavior", domain: "select", default: "Screen Off", options: ["Screen Off", "Ambient Clock"] },
                  ],
                  system_devices: [
                    { subentry_id: "sub_1", title: "Bedroom Desk", kind: "device", is_online: true, has_display: true, device_group: "wall_panels" },
                  ],
                },
              }).store;
            }
            const sOff = buildPower(false);
            const sOn = buildPower(true);
            sOn.groups.stageBatchSetting("bedtime_active", true);
            const detachBedtimeOnly = sOn.groups.previewBatchDetachmentCount();
            sOn.groups.stageBatchSetting("bedtime_display", "Ambient Clock");
            const detachWithPolicy = sOn.groups.previewBatchDetachmentCount();
            process.stdout.write(JSON.stringify({
              offHtml: renderToHtml(renderDevicePowerView(sOff)),
              onHtml: renderToHtml(renderDevicePowerView(sOn)),
              detachBedtimeOnly,
              detachWithPolicy,
            }));
            """
        )
        self.assertIn('id="card-bedtime-mode"', got["offHtml"])
        self.assertIn("Idle display in bedtime", got["offHtml"])
        self.assertIn("Screen off", got["offHtml"])
        self.assertNotIn("Bedtime starts", got["offHtml"])
        self.assertIn("Bedtime starts", got["onHtml"])
        self.assertIn("Bedtime ends", got["onHtml"])
        self.assertEqual(got["detachBedtimeOnly"], 0)
        self.assertEqual(got["detachWithPolicy"], 1)
