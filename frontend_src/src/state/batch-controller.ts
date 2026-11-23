/**
 * Staged `Batch controls` Draft Controller (`BatchController`, `D-064`).
 *
 * - Preserves untouched per-Device tokens during `Mixed` pill toggling (`batchPillDrafts`).
 * - Applies `expected_config_rev` per Device, clears committed drafts incrementally, and
 *   resyncs via `refreshState()` on partial/conflict failures.
 */

import { formatWsError, isConflictError } from "../api/ws-client.js";
import {
  type CatalogItem,
  GAMES_ITEMS_CATALOG,
  TOOLS_ITEMS_CATALOG,
} from "../constants.js";
import type {
  DeviceCapabilities,
  SharedControlItem,
  SharedControlTarget,
  SystemDeviceEntry,
} from "../types.js";
import { isValidHexColor } from "../utils/format.js";
import {
  type BatchPillState,
  isCatalogItemSupported,
  type StudioStoreContext,
} from "./store-types.js";

const PILL_CATALOG_BY_PREF: Readonly<Record<string, ReadonlyArray<CatalogItem>>> = {
  games_items: GAMES_ITEMS_CATALOG,
  tools_items: TOOLS_ITEMS_CATALOG,
};

function parseCsvTokens(raw: string | undefined | null): string[] {
  return String(raw || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export class BatchController {
  private readonly store: StudioStoreContext;

  /** Per-`pref_key` token delta map (`{ [token]: true | false }`) preserving untouched per-Device tokens. */
  readonly batchPillDrafts = new Map<string, Record<string, boolean>>();
  batchBusy = false;

  constructor(store: StudioStoreContext) {
    this.store = store;
  }

  get batchDraft(): Map<string, unknown> {
    return this.store.batchDraft;
  }

  get batchDraftCount(): number {
    const keys = new Set<string>(this.store.batchDraft.keys());
    for (const [pk, deltas] of this.batchPillDrafts.entries()) {
      if (Object.keys(deltas).length > 0) {
        keys.add(pk);
      }
    }
    return keys.size;
  }

  get hasBatchDraft(): boolean {
    return this.batchDraftCount > 0;
  }

  resolvedBatchTargetId(): string {
    const filter = this.store.batchTargetFilter || "all";
    if (filter.startsWith("group:")) return filter.slice(6);
    return filter;
  }

  setBatchTargetFilter(nextFilter: string): void {
    const cleaned = String(nextFilter || "all").trim() || "all";
    if (this.store.batchTargetFilter === cleaned) return;
    this.store.batchTargetFilter = cleaned;
    this.resetBatchDraft();
  }

  matchingBatchDevices(): SystemDeviceEntry[] {
    const filter = this.store.batchTargetFilter || "all";
    const devs = (this.store.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    return devs.filter((d) => {
      if (filter === "all") return true;
      if (filter === "online") return Boolean(d.is_online);
      if (filter === "roaming") return Boolean(d.is_roaming);
      if (filter === "stationary") return !d.is_roaming;
      const grpId = filter.startsWith("group:") ? filter.slice(6) : filter;
      return (d.device_group || "custom") === grpId;
    });
  }

  filteredControlTargets(ctrl: SharedControlItem): SharedControlTarget[] {
    const filter = this.store.batchTargetFilter || "all";
    return (ctrl.targets || []).filter((t) => {
      if (filter === "all") return true;
      if (filter === "online") return Boolean(t.is_online);
      if (filter === "roaming") return Boolean(t.is_roaming);
      if (filter === "stationary") return !t.is_roaming;
      const grpId = filter.startsWith("group:") ? filter.slice(6) : filter;
      return (t.device_group || "custom") === grpId;
    });
  }

  getEffectiveBatchValue(ctrl: SharedControlItem): {
    value: string;
    mixed: boolean;
    staged: boolean;
  } {
    const prefKey = ctrl.pref_key || "";
    if (prefKey && this.store.batchDraft.has(prefKey)) {
      const raw = this.store.batchDraft.get(prefKey);
      const valStr = ctrl.domain === "switch" ? (raw ? "on" : "off") : String(raw ?? "");
      return { value: valStr, mixed: false, staged: true };
    }
    const targets = this.filteredControlTargets(ctrl);
    const firstTarget = targets[0];
    if (!firstTarget) {
      return { value: String(ctrl.state ?? ""), mixed: false, staged: false };
    }
    const unique = new Set(targets.map((t) => String(t.state ?? "")));
    if (unique.size > 1) {
      return { value: String(firstTarget.state ?? ""), mixed: true, staged: false };
    }
    return { value: String(firstTarget.state ?? ""), mixed: false, staged: false };
  }

  private applyTokenDeltasToCsv(
    baseCsv: string,
    deltas: Record<string, boolean>,
    canonicalOrder: readonly string[],
  ): string {
    const current = parseCsvTokens(baseCsv);
    const active = new Set(current);
    for (const [tok, wantOn] of Object.entries(deltas)) {
      if (wantOn) active.add(tok);
      else active.delete(tok);
    }
    const preserved = current.filter((tok) => active.has(tok));
    const preservedSet = new Set(preserved);
    const appended = canonicalOrder.filter((tok) => active.has(tok) && !preservedSet.has(tok));
    const extras = Array.from(active).filter(
      (tok) => !preservedSet.has(tok) && !appended.includes(tok),
    );
    return [...preserved, ...appended, ...extras].join(",");
  }

  private targetDeviceCaps(target: SharedControlTarget): DeviceCapabilities | undefined {
    const devs = this.store.state?.system_devices || [];
    const dev = devs.find(
      (d) =>
        (target.subentry_id && d.subentry_id === target.subentry_id) ||
        (target.device_slug && d.device_slug === target.device_slug),
    );
    if (!dev) return undefined;
    return {
      has_display: dev.has_display,
      has_imu: dev.has_imu,
      has_battery: dev.has_battery,
      has_ble_beacon: dev.has_ble,
      is_roaming_device: dev.is_roaming,
      hw_jpeg: dev.hw_jpeg,
    };
  }

  private pillCatalogMap(prefKey: string): Map<string, CatalogItem> | null {
    const catalog = PILL_CATALOG_BY_PREF[prefKey];
    return catalog ? new Map(catalog.map((c) => [c.token, c])) : null;
  }

  getEffectiveBatchPillStates(ctrl: SharedControlItem): BatchPillState[] {
    const prefKey = ctrl.pref_key || "";
    const options = ctrl.options || [];
    const labels = ctrl.option_labels || {};
    const targets = this.filteredControlTargets(ctrl);
    const deltas = (prefKey && this.batchPillDrafts.get(prefKey)) || {};
    const explicitCsv =
      prefKey && this.store.batchDraft.has(prefKey)
        ? String(this.store.batchDraft.get(prefKey) ?? "")
        : null;
    const capByToken = this.pillCatalogMap(prefKey);
    const targetEntries = capByToken
      ? targets.map((target) => ({ target, caps: this.targetDeviceCaps(target) }))
      : null;

    const out: BatchPillState[] = [];
    for (const token of options) {
      const catItem = capByToken?.get(token);
      let capableTargets = targets;
      if (catItem?.capability && targetEntries && targetEntries.length > 0) {
        capableTargets = targetEntries
          .filter((e) => isCatalogItemSupported(catItem, e.caps))
          .map((e) => e.target);
        if (capableTargets.length === 0) {
          continue;
        }
      }
      const label = labels[token] || token;
      if (explicitCsv !== null) {
        const set = new Set(parseCsvTokens(explicitCsv));
        out.push({
          token,
          label,
          state: set.has(token) ? "on" : "off",
          staged: true,
        });
        continue;
      }
      if (token in deltas) {
        out.push({
          token,
          label,
          state: deltas[token] ? "on" : "off",
          staged: true,
        });
        continue;
      }
      if (capableTargets.length === 0) {
        out.push({ token, label, state: "off", staged: false });
        continue;
      }
      let onCount = 0;
      for (const t of capableTargets) {
        if (parseCsvTokens(t.state).includes(token)) {
          onCount += 1;
        }
      }
      const state: "on" | "off" | "mixed" =
        onCount === 0 ? "off" : onCount === capableTargets.length ? "on" : "mixed";
      out.push({ token, label, state, staged: false });
    }
    return out;
  }

  stageBatchSetting(key: string, value: unknown): void {
    const cleanKey = String(key || "").trim();
    if (!cleanKey) return;
    this.batchPillDrafts.delete(cleanKey);
    this.store.batchDraft.set(cleanKey, value);
    this.store.host.requestUpdate();
  }

  stageBatchColor(ctrl: SharedControlItem, hex: string): void {
    const cleaned = String(hex || "").trim().toUpperCase();
    if (!ctrl.pref_key || !isValidHexColor(cleaned)) return;
    this.store.batchDraft.set(ctrl.pref_key, cleaned);
    this.store.batchDraft.set("color_profile", "Custom");
    this.store.host.requestUpdate();
  }

  stageBatchPillToggle(
    ctrl: SharedControlItem,
    rawToken: string,
    forceEnabled?: boolean,
  ): void {
    const prefKey = ctrl.pref_key || "";
    const token = String(rawToken || "").trim();
    if (!prefKey || !token) return;

    const pillStates = this.getEffectiveBatchPillStates(ctrl);
    const currentPill = pillStates.find((p) => p.token === token);
    const wantOn =
      forceEnabled !== undefined ? Boolean(forceEnabled) : currentPill?.state !== "on";

    const targets = this.filteredControlTargets(ctrl);
    const order = ctrl.options || [];
    const existingDeltas = { ...(this.batchPillDrafts.get(prefKey) || {}) };

    if (this.store.batchDraft.has(prefKey)) {
      const fullSet = new Set(parseCsvTokens(String(this.store.batchDraft.get(prefKey) ?? "")));
      for (const opt of order) {
        existingDeltas[opt] = fullSet.has(opt);
      }
      this.store.batchDraft.delete(prefKey);
    }

    const candidateDeltas: Record<string, boolean> = {
      ...existingDeltas,
      [token]: wantOn,
    };

    const capByToken = this.pillCatalogMap(prefKey);
    const clickedItem = capByToken?.get(token);

    const minRequired = ctrl.min ?? 0;
    if (!wantOn && minRequired > 0 && targets.length > 0) {
      const violatesMin = targets.some((t) => {
        const nextTokens = parseCsvTokens(
          this.applyTokenDeltasToCsv(t.state, candidateDeltas, order),
        );
        if (nextTokens.length < minRequired) return true;
        if (!capByToken) return false;
        const tCaps = this.targetDeviceCaps(t);
        if (clickedItem && !isCatalogItemSupported(clickedItem, tCaps)) {
          return false;
        }
        const supportedNext = nextTokens.filter((tok) => {
          const item = capByToken.get(tok);
          return item ? isCatalogItemSupported(item, tCaps) : true;
        });
        return supportedNext.length < minRequired;
      });
      if (violatesMin) {
        const noun =
          prefKey === "tools_items"
            ? "tool"
            : prefKey === "games_items"
              ? "game"
              : "category";
        this.store.showToast(this.store.t("common.keep_one_enabled", { noun }), true);
        return;
      }
    }

    const relevantTargets =
      clickedItem?.capability && targets.length > 0
        ? targets.filter((t) => isCatalogItemSupported(clickedItem, this.targetDeviceCaps(t)))
        : targets;
    if (
      relevantTargets.length > 0 &&
      relevantTargets.every((t) => parseCsvTokens(t.state).includes(token) === wantOn)
    ) {
      delete candidateDeltas[token];
    }

    if (Object.keys(candidateDeltas).length === 0) {
      this.batchPillDrafts.delete(prefKey);
    } else {
      this.batchPillDrafts.set(prefKey, candidateDeltas);
    }
    this.store.host.requestUpdate();
  }

  resetBatchDraft(): void {
    this.store.batchDraft.clear();
    this.batchPillDrafts.clear();
    this.store.host.requestUpdate();
  }

  previewBatchDetachmentCount(): number {
    if (!this.hasBatchDraft) return 0;
    const hasDetachingKey =
      this.batchPillDrafts.size > 0 ||
      Array.from(this.store.batchDraft.keys()).some((key) => {
        const spec = this.store.entity.getPrefSpec(key);
        return !spec || spec.group_tier !== null;
      });
    if (!hasDetachingKey) return 0;
    return this.matchingBatchDevices().filter(
      (d) => Boolean(d.device_group && d.device_group !== "custom"),
    ).length;
  }

  requestApplyBatchDraft(): void {
    if (!this.hasBatchDraft || this.batchBusy) return;
    const targets = this.matchingBatchDevices();
    if (targets.length === 0) {
      this.store.showToast(this.store.t("batch.no_targets"), true);
      return;
    }
    if (targets.length === 1) {
      void this.applyBatchDraft();
      return;
    }
    const count = targets.length;
    const settingCount = this.batchDraftCount;
    this.store.openConfirm({
      kind: "apply_batch",
      title: this.store.t("confirm.apply_batch.title", { count }),
      consequence: this.store.t("confirm.apply_batch.body", {
        settingCount,
        count,
      }),
      confirmLabel: this.store.t("confirm.apply_batch.confirm"),
      danger: false,
      blastRadiusCount: count,
      onConfirm: async () => {
        await this.applyBatchDraft();
      },
    });
  }

  async applyBatchDraft(): Promise<void> {
    if (!this.hasBatchDraft || this.batchBusy) return;
    const matchedDevices = this.matchingBatchDevices();
    if (matchedDevices.length === 0) {
      this.store.showToast(this.store.t("batch.no_targets"), true);
      return;
    }

    const beforeGroups = new Map<string, { title: string; group: string }>();
    const subentryBySlug = new Map<string, string>();
    for (const d of matchedDevices) {
      subentryBySlug.set(d.device_slug, d.subentry_id);
      if (d.device_group && d.device_group !== "custom") {
        beforeGroups.set(d.subentry_id, { title: d.title, group: d.device_group });
      }
    }

    const uniformPatch: Record<string, unknown> = Object.fromEntries(
      this.store.batchDraft.entries(),
    );
    const foldedPillKeys = new Set<string>();
    const perDevicePatches = new Map<string, Record<string, unknown>>();

    const controls = this.store.state?.system_controls || [];
    for (const [prefKey, deltas] of this.batchPillDrafts.entries()) {
      if (Object.keys(deltas).length === 0) continue;
      const ctrl = controls.find((c) => c.pref_key === prefKey);
      const order = ctrl?.options || [];
      const targets = ctrl ? this.filteredControlTargets(ctrl) : [];
      if (targets.length === 0) continue;

      const resolvedPerTarget: Array<{ subentryId: string; csv: string }> = [];
      for (const t of targets) {
        const subId =
          t.subentry_id || (t.device_slug ? subentryBySlug.get(t.device_slug) : "") || "";
        const csv = this.applyTokenDeltasToCsv(t.state, deltas, order);
        if (subId) {
          resolvedPerTarget.push({ subentryId: subId, csv });
        }
      }
      const firstResolved = resolvedPerTarget[0];
      if (!firstResolved) continue;

      const distinctCsvs = new Set(resolvedPerTarget.map((r) => r.csv));
      if (distinctCsvs.size === 1) {
        uniformPatch[prefKey] = firstResolved.csv;
        foldedPillKeys.add(prefKey);
      } else {
        for (const item of resolvedPerTarget) {
          const cur = perDevicePatches.get(item.subentryId) || {};
          cur[prefKey] = item.csv;
          perDevicePatches.set(item.subentryId, cur);
        }
      }
    }

    this.batchBusy = true;
    this.store.host.requestUpdate();

    let anyApplied = false;
    try {
      let lastRes = null;
      if (Object.keys(uniformPatch).length > 0) {
        lastRes = await this.store.ws.runSystemCommand(
          "apply_batch_device_setting",
          {
            target: this.store.batchTargetFilter || "all",
            config: uniformPatch,
          },
          this.store.activeSubentryId || null,
        );
        anyApplied = true;
        for (const k of Object.keys(uniformPatch)) {
          this.store.batchDraft.delete(k);
        }
        for (const pk of foldedPillKeys) {
          this.batchPillDrafts.delete(pk);
        }
      }

      const remainingPerDevice = new Set<string>(perDevicePatches.keys());
      for (const [subentryId, devPatch] of perDevicePatches.entries()) {
        const expectedRev = this.store.getKnownDeviceConfigRev(subentryId);
        const reqPayload: Record<string, unknown> = { config: devPatch };
        if (expectedRev > 0) {
          reqPayload.expected_config_rev = expectedRev;
        }
        const devRes = await this.store.ws.runDeviceCommand(
          subentryId,
          "save_device_config",
          reqPayload,
        );
        anyApplied = true;
        remainingPerDevice.delete(subentryId);
        if (devRes) {
          if (devRes.subentry_id === subentryId && devRes.device_config_rev > 0) {
            this.store.recordKnownDeviceConfigRev(subentryId, devRes.device_config_rev);
          }
          lastRes = devRes;
        }
      }

      this.store.batchDraft.clear();
      if (remainingPerDevice.size === 0) {
        this.batchPillDrafts.clear();
      }

      if (lastRes) {
        this.store.ingestPayload(lastRes, false);
      }

      const afterDevs = this.store.state?.system_devices || [];
      const detachedTitles: string[] = [];
      for (const [subId, prev] of beforeGroups.entries()) {
        const cur = afterDevs.find((d) => d.subentry_id === subId);
        if (cur && cur.device_group === "custom" && prev.group !== "custom") {
          detachedTitles.push(prev.title);
        }
      }

      const singleDetached = detachedTitles[0];
      if (detachedTitles.length === 1 && singleDetached !== undefined) {
        this.store.showToast(
          this.store.t("groups.detached_toast", { title: singleDetached }),
        );
      } else if (detachedTitles.length > 1) {
        this.store.showToast(
          this.store.t("groups.detached_many_toast", { count: detachedTitles.length }),
        );
      } else {
        const count = matchedDevices.length;
        this.store.showToast(
          count === 1
            ? this.store.t("batch.applied_to_one")
            : this.store.t("batch.applied_to_n", { count }),
        );
      }
    } catch (err) {
      if (anyApplied || isConflictError(err)) {
        await this.store.refreshState();
      }
      if (isConflictError(err)) {
        this.store.showToast(this.store.t("sync.conflict_reloaded"), true);
      } else {
        this.store.showToast(formatWsError(err, "Could not apply staged batch settings"), true);
      }
    } finally {
      this.batchBusy = false;
      this.store.host.requestUpdate();
    }
  }

  async applyBatchCopyFromDevice(sourceSubentryId: string, copyKeys: string[]): Promise<void> {
    if (!sourceSubentryId || !copyKeys.length) {
      this.store.showToast("Choose a template Device first", true);
      return;
    }
    try {
      const res = await this.store.ws.runSystemCommand(
        "apply_batch_device_setting",
        {
          target: this.store.batchTargetFilter || "all",
          source_subentry_id: sourceSubentryId,
          copy_keys: copyKeys,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Pushed list from template Device");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not copy list across target Devices"), true);
    }
  }
}
