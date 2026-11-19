/**
 * `store.groups` Controller (`GroupsController`, `D-050`, `D-064` / `Q6`):
 * - Device Groups CRUD, scope toggles (`include_display`, `include_interface`), & baseline updates
 * - Staged `Batch controls` draft state (`batchDraft` + per-Device `Mixed`-safe `batchPillDrafts`)
 *   with **Apply to N Devices** / **Reset** and automatic `Custom` detachment toast
 * - Walk-Around BLE calibration, scanner antenna trim, & Area sensor fusion
 */

import { formatWsError } from "../api/ws-client.js";
import type { SharedControlItem, SharedControlTarget, SystemDeviceEntry } from "../types.js";
import { isValidHexColor } from "../utils/format.js";
import type { StudioStore } from "./store.js";

function slugifyGroupName(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function parseCsvTokens(raw: string | undefined | null): string[] {
  return String(raw || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export interface BatchPillState {
  token: string;
  label: string;
  state: "on" | "off" | "mixed";
  staged: boolean;
}

interface StagedBatchEntityAction {
  ctrl: SharedControlItem;
  action?: string;
  option?: string;
  level?: number;
}

export class GroupsController {
  private readonly store: StudioStore;

  /** Per-`pref_key` token delta map (`{ [token]: true | false }`) preserving untouched per-Device tokens (`Q6`). */
  readonly batchPillDrafts = new Map<string, Record<string, boolean>>();
  private readonly batchEntityDrafts = new Map<string, StagedBatchEntityAction>();
  batchBusy = false;

  constructor(store: StudioStore) {
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
    for (const ek of this.batchEntityDrafts.keys()) {
      keys.add(`entity:${ek}`);
    }
    return keys.size;
  }

  get hasBatchDraft(): boolean {
    return this.batchDraftCount > 0;
  }

  // ---------- Device Groups CRUD & Baseline Updates ----------

  toggleNewGroupForm(open?: boolean): void {
    const nextOpen = open !== undefined ? Boolean(open) : !this.store.newGroupFormOpen;
    this.store.newGroupFormOpen = nextOpen;
    if (!nextOpen) {
      this.store.newGroupName = "";
      this.store.newGroupDesc = "";
      this.store.newGroupSourceSubentryId = "";
      this.store.newGroupIncludeDisplay = false;
      this.store.newGroupIncludeInterface = false;
    }
    this.store.host.requestUpdate();
    if (nextOpen && typeof globalThis.requestAnimationFrame === "function") {
      globalThis.requestAnimationFrame(() => {
        const root =
          (this.store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
          this.store.host.shadowRoot;
        const inputEl = root?.getElementById("new-group-name") as HTMLInputElement | null;
        if (inputEl && typeof inputEl.focus === "function") {
          try {
            inputEl.focus({ preventScroll: true });
          } catch {
            inputEl.focus();
          }
        }
      });
    }
  }

  async createDeviceGroup(): Promise<void> {
    const name = this.store.newGroupName.trim();
    const description = this.store.newGroupDesc.trim();
    const sourceSubentryId = this.store.newGroupSourceSubentryId.trim();
    if (!name) {
      this.store.showToast("Enter a Device group name", true);
      return;
    }
    try {
      const payload: Record<string, unknown> = { name, description };
      if (sourceSubentryId) {
        payload.source_subentry_id = sourceSubentryId;
      }
      if (this.store.newGroupIncludeDisplay) {
        payload.include_display = true;
      }
      if (this.store.newGroupIncludeInterface) {
        payload.include_interface = true;
      }
      const res = await this.store.ws.runSystemCommand(
        "create_device_group",
        payload,
        this.store.activeSubentryId || null,
      );
      const createdId = slugifyGroupName(name) || "group";
      this.store.newGroupFormOpen = false;
      this.store.newGroupName = "";
      this.store.newGroupDesc = "";
      this.store.newGroupSourceSubentryId = "";
      this.store.newGroupIncludeDisplay = false;
      this.store.newGroupIncludeInterface = false;
      this.store.openGroupIds.add(createdId);
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(`Created group "${name}"`);
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not create Device group"), true);
    }
  }

  openSaveGroupModal(): void {
    if (!this.store.activeSubentryId) return;
    const devTitle = this.store.state?.title || "";
    this.store.saveGroupModal = {
      open: true,
      subentryId: this.store.activeSubentryId,
      name: "",
      description: devTitle ? `Saved from ${devTitle}` : "",
      includeDisplay: false,
      includeInterface: false,
      busy: false,
    };
    this.store.host.requestUpdate();
  }

  closeSaveGroupModal(): void {
    this.store.saveGroupModal = { ...this.store.saveGroupModal, open: false, busy: false };
    this.store.host.requestUpdate();
  }

  async confirmSaveGroupModal(): Promise<void> {
    const name = this.store.saveGroupModal.name.trim();
    const description = this.store.saveGroupModal.description.trim();
    const sourceSubentryId = this.store.saveGroupModal.subentryId || this.store.activeSubentryId;
    const includeDisplay = Boolean(this.store.saveGroupModal.includeDisplay);
    const includeInterface = Boolean(this.store.saveGroupModal.includeInterface);
    if (!name) {
      this.store.showToast("Enter a Device group name", true);
      return;
    }
    if (!sourceSubentryId) {
      this.store.showToast("Choose a Device first", true);
      return;
    }
    this.store.saveGroupModal = { ...this.store.saveGroupModal, busy: true };
    this.store.host.requestUpdate();
    try {
      const payload: Record<string, unknown> = {
        name,
        description,
        source_subentry_id: sourceSubentryId,
        assign_source: true,
      };
      if (includeDisplay) payload.include_display = true;
      if (includeInterface) payload.include_interface = true;
      const res = await this.store.ws.runSystemCommand(
        "create_device_group",
        payload,
        this.store.activeSubentryId || null,
      );
      this.store.saveGroupModal = {
        open: false,
        subentryId: "",
        name: "",
        description: "",
        includeDisplay: false,
        includeInterface: false,
        busy: false,
      };
      if (res) this.store.ingestPayload(res, false);
      else this.store.host.requestUpdate();
      this.store.showToast(`Saved custom group "${name}"`);
    } catch (err) {
      this.store.saveGroupModal = { ...this.store.saveGroupModal, busy: false };
      this.store.host.requestUpdate();
      this.store.showToast(formatWsError(err, "Could not save custom Device group"), true);
    }
  }

  async deleteDeviceGroup(groupId: string): Promise<void> {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "delete_device_group",
        { group_id: cleanId },
        this.store.activeSubentryId || null,
      );
      this.store.openGroupIds.delete(cleanId);
      this.store.groupCopySourceDrafts.delete(cleanId);
      if (this.store.batchTargetFilter === `group:${cleanId}`) {
        this.store.batchTargetFilter = "all";
        this.resetBatchDraft();
      }
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Deleted Device group");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not delete Device group"), true);
    }
  }

  requestDeleteDeviceGroup(groupId: string, groupName?: string, memberCount?: number): void {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    const grp = this.store.state?.device_groups?.find((g) => g.id === cleanId);
    const name = groupName || grp?.name || cleanId;
    const count =
      memberCount ??
      (this.store.state?.system_devices || []).filter(
        (d) => d.kind !== "ble_tag" && d.device_group === cleanId,
      ).length;
    this.store.openConfirm({
      kind: "delete_group",
      title: this.store.t("confirm.delete_group.title", { name }),
      consequence: this.store.t("confirm.delete_group.body"),
      confirmLabel: this.store.t("confirm.delete_group.confirm"),
      danger: true,
      blastRadiusCount: count > 0 ? count : null,
      onConfirm: async () => {
        await this.deleteDeviceGroup(cleanId);
      },
    });
  }

  async resetDeviceGroupPreset(groupId: string, groupName?: string): Promise<void> {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    const grp = this.store.state?.device_groups?.find((g) => g.id === cleanId);
    const name = groupName || grp?.name || cleanId;
    try {
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        {
          group_id: cleanId,
          reset_to_default: true,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(this.store.t("groups.reset_preset_toast", { name }));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not reset group preset"), true);
    }
  }

  requestResetDeviceGroup(groupId: string, groupName?: string, memberCount?: number): void {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    const grp = this.store.state?.device_groups?.find((g) => g.id === cleanId);
    const name = groupName || grp?.name || cleanId;
    const count =
      memberCount ??
      (this.store.state?.system_devices || []).filter(
        (d) => d.kind !== "ble_tag" && d.device_group === cleanId,
      ).length;
    this.store.openConfirm({
      kind: "reset_group",
      title: this.store.t("confirm.reset_group.title", { name }),
      consequence: this.store.t("confirm.reset_group.body"),
      confirmLabel: this.store.t("confirm.reset_group.confirm"),
      danger: false,
      blastRadiusCount: count > 0 ? count : null,
      onConfirm: async () => {
        await this.resetDeviceGroupPreset(cleanId, name);
      },
    });
  }

  async updateGroupBaseline(groupId: string, patch: Record<string, unknown>): Promise<void> {
    if (!groupId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        {
          group_id: groupId,
          config: patch,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.announcePolite(this.store.t("shell.saved_status"));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not update group baseline"), true);
    }
  }

  async updateGroupScope(
    groupId: string,
    scope: { include_display?: boolean; include_interface?: boolean },
  ): Promise<void> {
    if (!groupId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        {
          group_id: groupId,
          ...scope,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.announcePolite(this.store.t("shell.saved_status"));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not update group scope"), true);
    }
  }

  async copyDeviceToGroupBaseline(
    groupId: string,
    sourceSubentryId: string,
    copyKeys?: string[],
  ): Promise<void> {
    if (!groupId || !sourceSubentryId) {
      this.store.showToast("Choose a Device to copy settings from", true);
      return;
    }
    try {
      const payload: Record<string, unknown> = {
        group_id: groupId,
        source_subentry_id: sourceSubentryId,
      };
      if (copyKeys && copyKeys.length) {
        payload.copy_keys = copyKeys;
      }
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        payload,
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Copied Device settings into group baseline");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not copy Device settings"), true);
    }
  }

  // ---------- Staged Batch Controls (`Q6` / `D-064`) ----------

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

  filteredControlEntityIds(ctrl: SharedControlItem): string[] {
    return this.filteredControlTargets(ctrl)
      .map((t) => t.entity_id || "")
      .filter(Boolean);
  }

  getEffectiveBatchValue(ctrl: SharedControlItem): {
    value: string;
    mixed: boolean;
    staged: boolean;
  } {
    const prefKey = ctrl.pref_key || "";
    if (prefKey && this.store.batchDraft.has(prefKey)) {
      const raw = this.store.batchDraft.get(prefKey);
      const valStr =
        ctrl.domain === "switch" ? (raw ? "on" : "off") : String(raw ?? "");
      return { value: valStr, mixed: false, staged: true };
    }
    const entKey = ctrl.key || ctrl.canonical_key || "";
    if (!prefKey && entKey && this.batchEntityDrafts.has(entKey)) {
      const entDraft = this.batchEntityDrafts.get(entKey)!;
      const valStr =
        entDraft.action === "turn_on"
          ? "on"
          : entDraft.action === "turn_off"
            ? "off"
            : entDraft.option !== undefined
              ? entDraft.option
              : String(entDraft.level ?? "");
      return { value: valStr, mixed: false, staged: true };
    }
    const targets = this.filteredControlTargets(ctrl);
    if (targets.length === 0) {
      return { value: String(ctrl.state ?? ""), mixed: false, staged: false };
    }
    const unique = new Set(targets.map((t) => String(t.state ?? "")));
    if (unique.size > 1) {
      return { value: String(targets[0].state ?? ""), mixed: true, staged: false };
    }
    return { value: String(targets[0].state ?? ""), mixed: false, staged: false };
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
    // Preserve each target Device's existing relative token order first, appending newly enabled tokens in canonical order.
    const preserved = current.filter((tok) => active.has(tok));
    const preservedSet = new Set(preserved);
    const appended = canonicalOrder.filter((tok) => active.has(tok) && !preservedSet.has(tok));
    const extras = Array.from(active).filter(
      (tok) => !preservedSet.has(tok) && !appended.includes(tok),
    );
    return [...preserved, ...appended, ...extras].join(",");
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

    return options.map((token) => {
      const label = labels[token] || token;
      if (explicitCsv !== null) {
        const set = new Set(parseCsvTokens(explicitCsv));
        return {
          token,
          label,
          state: set.has(token) ? "on" : "off",
          staged: true,
        };
      }
      if (token in deltas) {
        return {
          token,
          label,
          state: deltas[token] ? "on" : "off",
          staged: true,
        };
      }
      if (targets.length === 0) {
        return { token, label, state: "off", staged: false };
      }
      let onCount = 0;
      for (const t of targets) {
        if (parseCsvTokens(t.state).includes(token)) {
          onCount += 1;
        }
      }
      const state: "on" | "off" | "mixed" =
        onCount === 0 ? "off" : onCount === targets.length ? "on" : "mixed";
      return { token, label, state, staged: false };
    });
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

  stageBatchEntityControl(
    ctrl: SharedControlItem,
    mutation: { action?: string; option?: string; level?: number },
  ): void {
    if (ctrl.pref_key) {
      if (mutation.action !== undefined) {
        this.stageBatchSetting(ctrl.pref_key, mutation.action === "turn_on");
      } else if (mutation.option !== undefined) {
        this.stageBatchSetting(ctrl.pref_key, mutation.option);
      } else if (mutation.level !== undefined && Number.isFinite(mutation.level)) {
        this.stageBatchSetting(ctrl.pref_key, mutation.level);
      }
      return;
    }
    const entKey = ctrl.key || ctrl.canonical_key || ctrl.name;
    if (!entKey) return;
    this.batchEntityDrafts.set(entKey, { ctrl, ...mutation });
    this.store.host.requestUpdate();
  }

  /**
   * Stages a per-token pill toggle across matching target Devices (`Q6`).
   * Never copies `states[0]` over `Mixed` target Devices: untouched tokens stay intact per Device.
   */
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
      forceEnabled !== undefined
        ? Boolean(forceEnabled)
        : currentPill?.state !== "on";

    const targets = this.filteredControlTargets(ctrl);
    const order = ctrl.options || [];
    const existingDeltas = { ...(this.batchPillDrafts.get(prefKey) || {}) };

    // If a full CSV override was previously staged on `batchDraft`, fold it into per-token deltas first.
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

    const minRequired = ctrl.min ?? 0;
    if (!wantOn && minRequired > 0 && targets.length > 0) {
      const violatesMin = targets.some((t) => {
        const nextCsv = this.applyTokenDeltasToCsv(t.state, candidateDeltas, order);
        return parseCsvTokens(nextCsv).length < minRequired;
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

    // Prune delta if it matches the server's unmodified state on every matching target Device.
    if (
      targets.length > 0 &&
      targets.every((t) => parseCsvTokens(t.state).includes(token) === wantOn)
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
    this.batchEntityDrafts.clear();
    this.store.host.requestUpdate();
  }

  previewBatchDetachmentCount(): number {
    if (!this.hasBatchDraft) return 0;
    const hasDetachingKey =
      this.batchPillDrafts.size > 0 ||
      this.batchEntityDrafts.size > 0 ||
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
        const subId = t.subentry_id || (t.device_slug ? subentryBySlug.get(t.device_slug) : "") || "";
        const csv = this.applyTokenDeltasToCsv(t.state, deltas, order);
        if (subId) {
          resolvedPerTarget.push({ subentryId: subId, csv });
        }
      }
      if (resolvedPerTarget.length === 0) continue;

      const distinctCsvs = new Set(resolvedPerTarget.map((r) => r.csv));
      if (distinctCsvs.size === 1) {
        uniformPatch[prefKey] = resolvedPerTarget[0].csv;
      } else {
        for (const item of resolvedPerTarget) {
          const cur = perDevicePatches.get(item.subentryId) || {};
          cur[prefKey] = item.csv;
          perDevicePatches.set(item.subentryId, cur);
        }
      }
    }

    const entityActions = Array.from(this.batchEntityDrafts.values());

    this.batchBusy = true;
    this.store.host.requestUpdate();

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
      }

      for (const [subentryId, devPatch] of perDevicePatches.entries()) {
        const devRes = await this.store.ws.runDeviceCommand(subentryId, "save_device_config", {
          config: devPatch,
        });
        if (devRes) {
          lastRes = devRes;
        }
      }

      for (const entAct of entityActions) {
        const entityIds = this.filteredControlEntityIds(entAct.ctrl);
        if (!entityIds.length) continue;
        const body: Record<string, unknown> = { entity_ids: entityIds };
        if (entAct.action !== undefined) body.action = entAct.action;
        if (entAct.option !== undefined) body.option = entAct.option;
        if (entAct.level !== undefined) body.level = entAct.level;
        const entRes = await this.store.ws.runSystemCommand(
          "system_entity_action",
          body,
          this.store.activeSubentryId || null,
        );
        if (entRes) {
          lastRes = entRes;
        }
      }

      this.store.batchDraft.clear();
      this.batchPillDrafts.clear();
      this.batchEntityDrafts.clear();

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

      if (detachedTitles.length === 1) {
        this.store.showToast(
          this.store.t("groups.detached_toast", { title: detachedTitles[0] }),
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
      this.store.showToast(formatWsError(err, "Could not apply staged batch settings"), true);
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

  // ---------- Walk-Around BLE Calibration & Area Sensor Fusion ----------

  selectBleSurveyDevice(subentryId: string): void {
    this.store.bleSurveySubentryId = subentryId;
    this.store.host.requestUpdate();
    void this.store.ensureSubscription(false);
  }

  selectBleCalibrateArea(areaId: string, fromAreaCard = false): void {
    this.store.bleCalibrateAreaId = String(areaId || "");
    if (fromAreaCard) {
      this.store.handoffTargetIds.clear();
      this.store.bleCalibrateHandoffActive = true;
    }
    this.store.host.requestUpdate();
    if (fromAreaCard && typeof globalThis.requestAnimationFrame === "function") {
      globalThis.requestAnimationFrame(() => {
        const root =
          (this.store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
          this.store.host.shadowRoot;
        const cardEl =
          root?.getElementById("card-ble-calibration") ||
          root?.getElementById("ble-calibrate-target-box");
        if (cardEl && typeof cardEl.scrollIntoView === "function") {
          cardEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        const selectEl = root?.getElementById(
          "ble-calibrate-area-select",
        ) as HTMLSelectElement | null;
        if (selectEl && typeof selectEl.focus === "function") {
          try {
            selectEl.focus({ preventScroll: true });
          } catch {
            selectEl.focus();
          }
        }
      });
    }
  }

  toggleBleLiveStream(enabled: boolean): void {
    if (!enabled) {
      this.store.bleSurveyFrozen.clear();
      for (const dev of this.store.state?.system_devices || []) {
        if (!dev.subentry_id) continue;
        this.store.bleSurveyFrozen.set(dev.subentry_id, {
          rows: (dev.ble_survey_rows || []).map((r) => ({ ...r })),
          packetsSeen: dev.ble_packets_seen ?? 0,
          activeAreaName: dev.active_area_name || "",
        });
      }
      this.store.bleLiveStreamActive = false;
      this.store.host.requestUpdate();
      void this.store.ensureSubscription(false);
      return;
    }
    this.store.bleSurveyFrozen.clear();
    this.store.bleLiveStreamActive = true;
    this.store.host.requestUpdate();
    void this.store.ensureSubscription(false);
  }

  getActiveSurveyDevice(): SystemDeviceEntry | undefined {
    const devs = this.store.state?.system_devices || [];
    const bleDevs = devs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
    return bleDevs.find((d) => d.subentry_id === this.store.bleSurveySubentryId);
  }

  async setBleScannerOffset(scannerSource: string, offsetDb: number): Promise<void> {
    const source = String(scannerSource || "").trim();
    if (!source) {
      this.store.showToast("Missing BLE scanner source", true);
      return;
    }
    try {
      const res = await this.store.ws.runSystemCommand(
        "set_ble_scanner_offset",
        { scanner_source: source, offset_db: offsetDb },
        this.store.activeSubentryId || null,
      );
      if (res) {
        if (!this.store.bleLiveStreamActive && Array.isArray(res.system_devices)) {
          const sourceNorm = source.toLowerCase();
          for (const incomingDev of res.system_devices) {
            if (!incomingDev.subentry_id) continue;
            const frozen = this.store.bleSurveyFrozen.get(incomingDev.subentry_id);
            if (!frozen) continue;
            const incomingRow = (incomingDev.ble_survey_rows || []).find(
              (r) => String(r.scanner_source || "").trim().toLowerCase() === sourceNorm,
            );
            if (!incomingRow) continue;
            frozen.rows = frozen.rows.map((r) => {
              if (String(r.scanner_source || "").trim().toLowerCase() !== sourceNorm) {
                return r;
              }
              return {
                ...r,
                offset_db: incomingRow.offset_db,
                effective_rssi: incomingRow.effective_rssi,
              };
            });
          }
        }
        this.store.ingestPayload(res, false);
      }
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not update BLE scanner offset"), true);
    }
  }

  async captureBleAreaSignature(areaId: string): Promise<void> {
    const sysDevs = this.store.state?.system_devices;
    const activeDev = Array.isArray(sysDevs)
      ? this.getActiveSurveyDevice() ||
        sysDevs.find((d) => d.ble_tracked || d.kind === "ble_tag")
      : undefined;
    const surveySubentryId = Array.isArray(sysDevs)
      ? activeDev?.subentry_id || ""
      : this.store.bleSurveySubentryId;
    if (!surveySubentryId) {
      this.store.showToast("Select a calibration Device first", true);
      return;
    }
    try {
      const res = await this.store.ws.runSystemCommand(
        "capture_ble_area_signature",
        { area_id: areaId, survey_subentry_id: surveySubentryId },
        this.store.activeSubentryId || null,
      );
      this.store.bleCalibrateHandoffActive = false;
      if (res) this.store.ingestPayload(res, false);
      else this.store.host?.requestUpdate?.();
      this.store.showToast("Captured Area signature");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Signature capture failed"), true);
    }
  }

  async clearBleAreaSignature(areaId: string): Promise<void> {
    const cleanId = String(areaId || "").trim();
    if (!cleanId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "clear_ble_area_signature",
        { area_id: cleanId },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Cleared Area signature");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not clear Area signature"), true);
    }
  }

  requestClearBleAreaSignature(areaId: string, areaName?: string): void {
    const cleanId = String(areaId || "").trim();
    if (!cleanId) return;
    const area = areaName || cleanId;
    this.store.openConfirm({
      kind: "clear_ble_signature",
      title: this.store.t("confirm.clear_ble_signature.title", { area }),
      consequence: this.store.t("confirm.clear_ble_signature.body", { area }),
      confirmLabel: this.store.t("confirm.clear_ble_signature.confirm"),
      danger: true,
      onConfirm: async () => {
        await this.clearBleAreaSignature(cleanId);
      },
    });
  }

  async setAreaFusion(
    areaId: string,
    update: { mode?: string; threshold_pct?: number; sensors?: string[] },
  ): Promise<void> {
    try {
      const res = await this.store.ws.runSystemCommand(
        "set_area_fusion",
        { area_id: areaId, ...update },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.announcePolite(this.store.t("shell.saved_status"));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not update Area fusion"), true);
    }
  }
}
