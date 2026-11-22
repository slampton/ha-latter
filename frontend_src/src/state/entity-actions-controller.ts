/**
 * `store.entity` Controller (`EntityController`, `D-062`, `D-064`, `D-065`):
 * - Delegates serialized System & per-Device settings persistence to `SettingsSaveController`
 * - Optimistic ESPHome entity actions, unified `tokenListOps`, shortcuts, photos, & 600 s camera signing
 */

import { formatWsError } from "../api/ws-client.js";
import {
  ALLOWED_DEVICE_ACTIONS,
  DEVICE_PREF_SPECS_MAP,
  type DevicePrefSpecItem,
  MAX_DOCK_ITEMS,
  NATIVE_DOCK_APP_TOKENS,
} from "../constants.js";
import type {
  ConfigurableAppId,
  CustomPalette,
  DeviceCapabilities,
  DevicePrefItem,
  EspHomeEntityItem,
  PhotoItem,
  PhotoPoolMode,
  PhotoPoolTarget,
  ShortcutItem,
  StudioStatePayload,
  SystemConfig,
} from "../types.js";
import { isValidHexColor } from "../utils/format.js";
import { isCatalogItemSupported, overlayPendingEntityStates } from "./group-overlay.js";
import {
  addRemoteGroupRowOp,
  addStringListRowOp,
  addVolumeOverrideRowOp,
  getBroadcastSpeakersOp,
  getCarouselCamerasOp,
  getSystemBroadcastSpeakersOp,
  getSystemCameraEntitiesOp,
  getVisibleCamerasOp,
  removeRemoteGroupRowOp,
  removeStringListRowOp,
  removeVolumeOverrideRowOp,
  reorderBroadcastSpeakersOp,
  reorderCarouselCamerasOp,
  reorderStringListRowsOp,
  reorderVisibleCamerasOp,
  toggleBroadcastSpeakerOp,
  toggleCarouselCameraOp,
  toggleRemoteInGroupOp,
  toggleVisibleCameraOp,
  updateRemoteGroupFieldOp,
  updateStringListRowOp,
  updateVolumeOverrideRowOp,
} from "./lists-ops.js";
import {
  applyPhotoPickerModalOp,
  browseMediaFolderOp,
  bulkUpdatePhotosOp,
  closeMediaImportModalOp,
  closePhotoEditModalOp,
  closePhotoPickerModalOp,
  closePhotoUploadModalOp,
  createPhotoCollectionOp,
  createUploadCollectionOp,
  deletePhotoOp,
  importSelectedMediaOp,
  openMediaImportModalOp,
  openPhotoEditModalOp,
  openPhotoPickerModalOp,
  openPhotoUploadModalOp,
  removeStagedUploadOp,
  renamePhotoCollectionOp,
  requestBulkDeletePhotosOp,
  requestDeletePhotoCollectionOp,
  requestDeletePhotoOp,
  savePhotoEditModalOp,
  setDevicePhotoPoolOp,
  stageUploadFilesOp,
  uploadAllStagedPhotosOp,
} from "./photo-ops.js";
import { SettingsSaveController } from "./settings-save-controller.js";
import {
  createTokenListOps,
  defaultDockShortcutItems,
  normalizeShortcutArray,
  openShortcutModalOp,
  saveShortcutModalOp,
  TOKEN_LIST_SPECS,
} from "./shortcuts-ops.js";
import type {
  EntityControllerContract,
  StringListKey,
  StudioStoreContext,
  TokenListKey,
  TokenListOps,
} from "./store-types.js";

const ENTITY_OPTIMISTIC_TTL_MS = 8000;
const ALLOWED_DEVICE_ACTION_SET = new Set<string>(ALLOWED_DEVICE_ACTIONS);

export class EntityController implements EntityControllerContract {
  private readonly store: StudioStoreContext;
  private readonly saves: SettingsSaveController;
  private readonly cameraPreviewCache = new Map<string, { url: string; expiresAtMs: number }>();

  readonly tokenLists: Readonly<Record<TokenListKey, TokenListOps>>;

  constructor(store: StudioStoreContext) {
    this.store = store;
    this.saves = new SettingsSaveController(store);
    this.tokenLists = {
      area_categories: createTokenListOps(store, TOKEN_LIST_SPECS.area_categories),
      home_categories: createTokenListOps(store, TOKEN_LIST_SPECS.home_categories),
      tools_items: createTokenListOps(store, TOKEN_LIST_SPECS.tools_items),
      games_items: createTokenListOps(store, TOKEN_LIST_SPECS.games_items),
      activity_sources: createTokenListOps(store, TOKEN_LIST_SPECS.activity_sources),
    };
  }

  isCatalogItemSupported(item: { capability?: string }, caps?: DeviceCapabilities): boolean {
    return isCatalogItemSupported(item, caps ?? this.store.state?.capabilities);
  }

  // ---------- Settings Staging & Flushing Delegation ----------

  getEffectiveSystemPatch(): Record<string, unknown> {
    return this.saves.getEffectiveSystemPatch();
  }

  getEffectiveDevicePatch(subentryId: string): Record<string, unknown> {
    return this.saves.getEffectiveDevicePatch(subentryId);
  }

  discardDeviceBucket(subentryId: string): void {
    this.saves.discardDeviceBucket(subentryId);
  }

  stageDeviceSetting(
    key: string,
    value: unknown,
    controlDomId?: string,
    debounceMs?: number,
  ): void {
    this.saves.stageDeviceSetting(key, value, controlDomId, debounceMs);
  }

  flushDeviceBucket(targetSubentryId: string): Promise<void> {
    return this.saves.flushDeviceBucket(targetSubentryId);
  }

  stageSystemSetting<K extends keyof SystemConfig>(
    key: K,
    value: SystemConfig[K],
    controlDomId?: string,
    debounceMs?: number,
  ): void {
    this.saves.stageSystemSetting(key, value, controlDomId, debounceMs);
  }

  flushSystemSettings(): Promise<void> {
    return this.saves.flushSystemSettings();
  }

  flushAllPendingSettings(): Promise<void> {
    return this.saves.flushAllPendingSettings();
  }

  // ---------- Device Preferences & ESPHome Entity Actions ----------

  getPref(key: string): DevicePrefItem | undefined {
    return (this.store.state?.device_prefs || []).find((p) => p.key === key);
  }

  getPrefs(keys?: readonly string[]): DevicePrefItem[] {
    const all = this.store.state?.device_prefs || [];
    if (!keys || keys.length === 0) return all;
    const keySet = new Set(keys);
    return all.filter((p) => keySet.has(p.key));
  }

  getPrefSpec(key: string): DevicePrefSpecItem | undefined {
    const fromPayload = this.store.state?.pref_specs?.find((s) => s.key === key);
    return fromPayload ?? DEVICE_PREF_SPECS_MAP[key];
  }

  getSectionItems(sectionId: string): EspHomeEntityItem[] {
    const sec = (this.store.state?.esphome?.sections || []).find((s) => s.id === sectionId);
    return sec?.items || [];
  }

  private currentEntityState(entityId: string): string {
    for (const sec of this.store.state?.esphome?.sections || []) {
      for (const it of sec.items || []) {
        if (it.entity_id === entityId) return it.state;
      }
    }
    return "";
  }

  private applyOptimisticEntity(entityId: string, nextState: string): string {
    const prev = this.currentEntityState(entityId);
    this.store.pendingEntityStates.set(entityId, {
      state: nextState,
      previousValue: prev,
      expires: Date.now() + ENTITY_OPTIMISTIC_TTL_MS,
    });
    if (this.store.state?.esphome?.sections) {
      const nextPayload: StudioStatePayload = { ...this.store.state };
      overlayPendingEntityStates(nextPayload, this.store.pendingEntityStates);
      this.store.state = nextPayload;
      this.store.host.requestUpdate();
    }
    return prev;
  }

  private rollbackOptimisticEntity(entityId: string, prev: string): void {
    this.store.pendingEntityStates.delete(entityId);
    if (this.store.state?.esphome?.sections) {
      this.store.state = {
        ...this.store.state,
        esphome: {
          ...this.store.state.esphome,
          sections: this.store.state.esphome.sections.map((sec) => ({
            ...sec,
            items: (sec.items || []).map((it) =>
              it.entity_id === entityId ? { ...it, state: prev } : it,
            ),
          })),
        },
      };
    }
    this.store.host.requestUpdate();
  }

  async executeEntityAction(
    entityId: string,
    optimisticState: string | undefined,
    body: Record<string, unknown>,
    errorPrefix: string,
  ): Promise<boolean> {
    const targetSubentryId = this.store.activeSubentryId;
    if (!targetSubentryId || !entityId) return false;
    const prev =
      optimisticState !== undefined ? this.applyOptimisticEntity(entityId, optimisticState) : "";
    try {
      const res = await this.store.ws.runDeviceCommand(targetSubentryId, "esphome_entity_action", {
        entity_id: entityId,
        ...body,
      });
      if (res && this.store.activeSubentryId === targetSubentryId) {
        this.store.ingestPayload(res, false);
      }
      return true;
    } catch (err) {
      if (optimisticState !== undefined) this.rollbackOptimisticEntity(entityId, prev);
      this.store.showToast(formatWsError(err, errorPrefix), true);
      return false;
    }
  }

  async espAction(
    entityId: string,
    action: string,
    optimisticState?: string,
    toastMessage?: string,
  ): Promise<boolean> {
    const ok = await this.executeEntityAction(
      entityId,
      optimisticState,
      { action },
      "Device action failed",
    );
    if (ok && toastMessage) {
      this.store.showToast(toastMessage);
    }
    return ok;
  }

  async espSelect(entityId: string, option: string): Promise<void> {
    await this.executeEntityAction(entityId, option, { option }, "Could not update option");
  }

  async espNumber(entityId: string, level: number): Promise<void> {
    if (!Number.isFinite(level)) return;
    await this.executeEntityAction(
      entityId,
      String(level),
      { level },
      "Could not update level",
    );
  }

  async runDeviceAction(action: string, toastMessage?: string): Promise<boolean> {
    const targetSubentryId = this.store.activeSubentryId;
    const cleanAction = String(action || "").trim().toLowerCase();
    if (!targetSubentryId || !cleanAction) return false;
    if (!ALLOWED_DEVICE_ACTION_SET.has(cleanAction)) {
      this.store.showToast(`Unsupported Device action: ${cleanAction}`, true);
      return false;
    }
    try {
      const res = await this.store.ws.runDeviceCommand(targetSubentryId, "device_action", {
        action: cleanAction,
      });
      if (res && this.store.activeSubentryId === targetSubentryId) {
        this.store.ingestPayload(res, false);
      }
      if (toastMessage) {
        this.store.showToast(toastMessage);
      }
      return true;
    } catch (err) {
      this.store.showToast(formatWsError(err, "Device action failed"), true);
      return false;
    }
  }

  async triggerHeaderFirmwareUpdate(): Promise<void> {
    const updEntity = this.store.state?.live?.fw_update_entity || "";
    if (!updEntity) return;
    if (await this.espAction(updEntity, "install")) {
      this.store.showToast("Firmware update started");
    }
  }

  // ---------- Token Lists ----------

  getEnabledAreaCategories(): string[] {
    return this.tokenLists.area_categories.getEnabled();
  }
  toggleAreaCategoryToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.area_categories.toggle(token, forceEnabled);
  }
  moveAreaCategoryToken(token: string, delta: -1 | 1): void {
    this.tokenLists.area_categories.move(token, delta);
  }
  reorderAreaCategories(fromIndex: number, toIndex: number): void {
    this.tokenLists.area_categories.reorder(fromIndex, toIndex);
  }

  getEnabledHomeCategories(): string[] {
    return this.tokenLists.home_categories.getEnabled();
  }
  toggleHomeCategoryToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.home_categories.toggle(token, forceEnabled);
  }
  moveHomeCategoryToken(token: string, delta: -1 | 1): void {
    this.tokenLists.home_categories.move(token, delta);
  }
  reorderHomeCategories(fromIndex: number, toIndex: number): void {
    this.tokenLists.home_categories.reorder(fromIndex, toIndex);
  }

  getEnabledToolsItems(): string[] {
    return this.tokenLists.tools_items.getEnabled();
  }
  toggleToolItemToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.tools_items.toggle(token, forceEnabled);
  }
  moveToolItemToken(token: string, delta: -1 | 1): void {
    this.tokenLists.tools_items.move(token, delta);
  }
  reorderToolsItems(fromIndex: number, toIndex: number): void {
    this.tokenLists.tools_items.reorder(fromIndex, toIndex);
  }

  getEnabledGamesItems(): string[] {
    return this.tokenLists.games_items.getEnabled();
  }
  toggleGameItemToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.games_items.toggle(token, forceEnabled);
  }
  moveGameItemToken(token: string, delta: -1 | 1): void {
    this.tokenLists.games_items.move(token, delta);
  }
  reorderGamesItems(fromIndex: number, toIndex: number): void {
    this.tokenLists.games_items.reorder(fromIndex, toIndex);
  }

  getEnabledActivitySources(): string[] {
    return this.tokenLists.activity_sources.getEnabled();
  }
  toggleActivitySource(sourceId: string, forceEnabled?: boolean): void {
    this.tokenLists.activity_sources.toggle(sourceId, forceEnabled);
  }
  reorderActivitySources(fromIndex: number, toIndex: number): void {
    this.tokenLists.activity_sources.reorder(fromIndex, toIndex);
  }

  // ---------- Per-Device Broadcast Speakers & Cameras ----------

  getSystemBroadcastSpeakers(): string[] {
    return getSystemBroadcastSpeakersOp(this.store);
  }
  getBroadcastSpeakers(): string[] {
    return getBroadcastSpeakersOp(this.store);
  }
  toggleBroadcastSpeaker(entityId: string, forceEnabled?: boolean): void {
    toggleBroadcastSpeakerOp(this.store, entityId, forceEnabled);
  }
  reorderBroadcastSpeakers(fromIndex: number, toIndex: number): void {
    reorderBroadcastSpeakersOp(this.store, fromIndex, toIndex);
  }

  getSystemCameraEntities(): string[] {
    return getSystemCameraEntitiesOp(this.store);
  }
  getVisibleCameras(): string[] {
    return getVisibleCamerasOp(this.store);
  }
  toggleVisibleCamera(entityId: string, forceEnabled?: boolean): void {
    toggleVisibleCameraOp(this.store, entityId, forceEnabled);
  }
  reorderVisibleCameras(fromIndex: number, toIndex: number): void {
    reorderVisibleCamerasOp(this.store, fromIndex, toIndex);
  }

  getCarouselCameras(): string[] {
    return getCarouselCamerasOp(this.store);
  }
  toggleCarouselCamera(entityId: string, forceEnabled?: boolean): void {
    toggleCarouselCameraOp(this.store, entityId, forceEnabled);
  }
  reorderCarouselCameras(fromIndex: number, toIndex: number): void {
    reorderCarouselCamerasOp(this.store, fromIndex, toIndex);
  }

  // ---------- Shortcuts & App Config Modal ----------

  getDockItems(): ShortcutItem[] {
    const raw = this.store.state?.config?.dock_items;
    return raw === undefined || raw === null
      ? defaultDockShortcutItems()
      : normalizeShortcutArray(raw, true);
  }

  getPinnedItems(): ShortcutItem[] {
    const raw = this.store.state?.config?.pinned_items;
    return raw === undefined || raw === null ? [] : normalizeShortcutArray(raw, false);
  }

  moveShortcutItem(listKey: "dock_items" | "pinned_items", idx: number, delta: -1 | 1): void {
    this.reorderShortcutItems(listKey, idx, idx + delta);
  }

  reorderShortcutItems(
    listKey: "dock_items" | "pinned_items",
    fromIndex: number,
    toIndex: number,
  ): void {
    const current = listKey === "dock_items" ? this.getDockItems() : this.getPinnedItems();
    if (
      fromIndex < 0 ||
      toIndex < 0 ||
      fromIndex >= current.length ||
      toIndex >= current.length ||
      fromIndex === toIndex
    ) {
      return;
    }
    const next = current.map((it) => ({ ...it }));
    const [moved] = next.splice(fromIndex, 1);
    if (!moved) return;
    next.splice(toIndex, 0, moved);
    this.stageDeviceSetting(listKey, next);
  }

  removeShortcutItem(listKey: "dock_items" | "pinned_items", idx: number): void {
    const current = listKey === "dock_items" ? this.getDockItems() : this.getPinnedItems();
    if (idx < 0 || idx >= current.length) return;
    const next = current.filter((_, i) => i !== idx).map((it) => ({ ...it }));
    this.stageDeviceSetting(listKey, next);
  }

  resetDockItemsToDefault(): void {
    this.stageDeviceSetting("dock_items", defaultDockShortcutItems());
    this.store.showToast("Restored default App Dock");
  }

  requestResetDockItems(): void {
    this.store.openConfirm({
      kind: "reset_dock",
      title: this.store.t("confirm.reset_dock.title"),
      consequence: this.store.t("confirm.reset_dock.body"),
      confirmLabel: this.store.t("confirm.reset_dock.confirm"),
      danger: true,
      blastRadiusCount: 1,
      onConfirm: () => {
        this.resetDockItemsToDefault();
      },
    });
  }

  toggleNativeDockApp(routeToken: string, enabled: boolean): void {
    const target = String(routeToken || "").trim().toLowerCase();
    if (!NATIVE_DOCK_APP_TOKENS.includes(target)) return;
    const current = this.getDockItems().map((it) => ({ ...it }));
    if (!enabled) {
      const next = current.filter((it) => !(it.kind === "route" && it.target === target));
      this.stageDeviceSetting("dock_items", next);
      return;
    }
    if (current.some((it) => it.kind === "route" && it.target === target)) {
      return;
    }
    if (current.length >= MAX_DOCK_ITEMS) {
      this.store.showToast(`App Dock supports up to ${MAX_DOCK_ITEMS} shortcuts`, true);
      return;
    }
    current.push({
      kind: "route",
      target,
      action: "",
      label: "",
      icon: "",
      confirm: false,
    });
    this.stageDeviceSetting("dock_items", current);
  }

  openAppConfigModal(app: ConfigurableAppId): void {
    this.store.returnToPinnedModal = false;
    if (this.store.shortcutModal.open) {
      this.store.shortcutModal = { ...this.store.shortcutModal, open: false };
    }
    this.store.appConfigModal = { open: true, app };
    this.store.host.requestUpdate();
  }

  closeAppConfigModal(): void {
    this.store.appConfigModal = { open: false, app: null };
    this.store.host.requestUpdate();
  }

  openShortcutModal(
    listKey: "dock_items" | "pinned_items",
    editIndex: number | null = null,
  ): void {
    openShortcutModalOp(this.store, listKey, editIndex);
  }

  closeShortcutModal(): void {
    const reopenPinned = this.store.returnToPinnedModal;
    this.store.returnToPinnedModal = false;
    this.store.shortcutModal = { ...this.store.shortcutModal, open: false };
    if (reopenPinned) {
      this.store.appConfigModal = { open: true, app: "pinned" };
    }
    this.store.host.requestUpdate();
  }

  saveShortcutModal(): void {
    saveShortcutModalOp(this.store);
  }

  // ---------- Colors, Photo Library, Media Import & Device Photo Pools ----------

  applyDeviceCustomColor(hex: string, switchColorProfile = true): void {
    if (!isValidHexColor(hex)) return;
    this.stageDeviceSetting("device_custom_color", hex.toUpperCase());
    if (switchColorProfile) {
      this.stageDeviceSetting("color_profile", "Custom");
    }
  }

  deleteCustomPalette(hex: string): void {
    const target = hex.toUpperCase();
    const next: CustomPalette[] = (this.store.state?.system_config?.custom_palettes || []).filter(
      (p) => p.hex.toUpperCase() !== target,
    );
    this.stageSystemSetting("custom_palettes", next);
  }

  openPhotoUploadModal(options?: {
    defaultCollectionId?: string;
    onComplete?: (uploadedIds: string[]) => void;
  }): void {
    openPhotoUploadModalOp(this.store, options);
  }
  closePhotoUploadModal(): void {
    closePhotoUploadModalOp(this.store);
  }
  stageUploadFiles(fileList: FileList | readonly File[]): void {
    stageUploadFilesOp(this.store, fileList);
  }
  removeStagedUpload(index: number): void {
    removeStagedUploadOp(this.store, index);
  }
  async uploadAllStagedPhotos(): Promise<void> {
    await uploadAllStagedPhotosOp(this.store);
  }
  openPhotoEditModal(photo: PhotoItem): void {
    openPhotoEditModalOp(this.store, photo);
  }
  closePhotoEditModal(): void {
    closePhotoEditModalOp(this.store);
  }
  async savePhotoEditModal(): Promise<void> {
    await savePhotoEditModalOp(this.store);
  }
  async createPhotoCollection(name: string): Promise<string | null> {
    return createPhotoCollectionOp(this.store, name);
  }
  async createUploadCollection(): Promise<string | null> {
    return createUploadCollectionOp(this.store);
  }
  async renamePhotoCollection(collectionId: string, name: string): Promise<void> {
    await renamePhotoCollectionOp(this.store, collectionId, name);
  }
  requestDeletePhotoCollection(collectionId: string, name: string): void {
    requestDeletePhotoCollectionOp(this.store, collectionId, name);
  }
  async deletePhoto(photoId: string): Promise<void> {
    await deletePhotoOp(this.store, photoId);
  }
  requestDeletePhoto(photoId: string, name?: string): void {
    requestDeletePhotoOp(this.store, photoId, name);
  }
  async bulkUpdatePhotos(options: {
    addCollection?: string;
    removeCollection?: string;
    deletePhotos?: boolean;
  }): Promise<void> {
    await bulkUpdatePhotosOp(this.store, options);
  }
  requestBulkDeletePhotos(): void {
    requestBulkDeletePhotosOp(this.store);
  }
  openMediaImportModal(): void {
    openMediaImportModalOp(this.store);
  }
  closeMediaImportModal(): void {
    closeMediaImportModalOp(this.store);
  }
  async browseMediaFolder(root?: string, subpath?: string): Promise<void> {
    await browseMediaFolderOp(this.store, root, subpath);
  }
  async importSelectedMedia(): Promise<void> {
    await importSelectedMediaOp(this.store);
  }
  openPhotoPickerModal(target: PhotoPoolTarget): void {
    openPhotoPickerModalOp(this.store, target);
  }
  closePhotoPickerModal(): void {
    closePhotoPickerModalOp(this.store);
  }
  async applyPhotoPickerModal(): Promise<void> {
    await applyPhotoPickerModalOp(this.store);
  }
  async setDevicePhotoPool(
    options: {
      target: PhotoPoolTarget;
      mode: PhotoPoolMode;
      sourceId?: string;
      collectionId?: string;
      photoIds?: readonly string[];
      cycleMinutes?: number;
      shuffle?: boolean;
    },
    toastMessage?: string,
  ): Promise<boolean> {
    return setDevicePhotoPoolOp(this.store, options, toastMessage);
  }

  async setWallpaperRotation(minutes: number): Promise<void> {
    const cfg = this.store.state?.config || {};
    const cleanMins = Math.max(0, Math.round(Number(minutes) || 0));
    const mode = String(cfg.wallpaper_mode || "off") as PhotoPoolMode;
    await setDevicePhotoPoolOp(this.store, {
      target: "wallpaper",
      mode,
      sourceId: String(cfg.wallpaper_source || ""),
      collectionId: String(cfg.wallpaper_collection || ""),
      photoIds: Array.isArray(cfg.wallpaper_favorites) ? cfg.wallpaper_favorites : [],
      cycleMinutes: cleanMins,
    });
  }

  async setScreensaverRotation(minutes: number, shuffle?: boolean): Promise<void> {
    const cfg = this.store.state?.config || {};
    const cleanMins = Math.max(0, Math.round(Number(minutes) || 0));
    const mode = String(cfg.screensaver_photo_mode || "off") as PhotoPoolMode;
    await setDevicePhotoPoolOp(this.store, {
      target: "screensaver",
      mode,
      sourceId: String(cfg.screensaver_photo_source || ""),
      collectionId: String(cfg.screensaver_photo_collection || ""),
      photoIds: Array.isArray(cfg.screensaver_photo_ids) ? cfg.screensaver_photo_ids : [],
      cycleMinutes: cleanMins,
      shuffle: shuffle !== undefined ? shuffle : Boolean(cfg.screensaver_shuffle),
    });
  }

  // ---------- System String Lists, Volume Overrides, Remote Groups & Camera Preview ----------

  updateStringListRow(key: StringListKey, index: number, value: string): void {
    updateStringListRowOp(this.store, key, index, value);
  }
  addStringListRow(key: StringListKey, defaultEntity = "", maxLen?: number): void {
    addStringListRowOp(this.store, key, defaultEntity, maxLen);
  }
  removeStringListRow(key: StringListKey, index: number): void {
    removeStringListRowOp(this.store, key, index);
  }
  moveStringListRow(key: StringListKey, index: number, direction: -1 | 1): void {
    reorderStringListRowsOp(this.store, key, index, index + direction);
  }
  reorderStringListRows(key: StringListKey, fromIndex: number, toIndex: number): void {
    reorderStringListRowsOp(this.store, key, fromIndex, toIndex);
  }

  addVolumeOverrideRow(): void {
    addVolumeOverrideRowOp(this.store);
  }
  updateVolumeOverrideRow(index: number, field: "speaker" | "target", value: string): void {
    updateVolumeOverrideRowOp(this.store, index, field, value);
  }
  removeVolumeOverrideRow(index: number): void {
    removeVolumeOverrideRowOp(this.store, index);
  }

  addRemoteGroupRow(): void {
    addRemoteGroupRowOp(this.store);
  }
  updateRemoteGroupField(groupId: string, field: "name" | "area_id", value: string): void {
    updateRemoteGroupFieldOp(this.store, groupId, field, value);
  }
  toggleRemoteInGroup(groupId: string, remoteEntity: string): void {
    toggleRemoteInGroupOp(this.store, groupId, remoteEntity);
  }
  removeRemoteGroupRow(groupId: string): void {
    removeRemoteGroupRowOp(this.store, groupId);
  }

  clearCameraPreviewCache(): void {
    this.cameraPreviewCache.clear();
  }

  async previewCamera(cameraEntity: string, bustCache = false): Promise<void> {
    const cleanEntity = String(cameraEntity || "").trim();
    if (!cleanEntity) {
      this.closeCameraPreview();
      return;
    }
    const now = Date.now();
    const cached = this.cameraPreviewCache.get(cleanEntity);
    if (!bustCache && cached && cached.expiresAtMs > now) {
      this.store.activeCameraPreviewEntity = cleanEntity;
      this.store.cameraPreviewUrl = cached.url;
      this.store.host.requestUpdate();
      return;
    }
    try {
      const minted = await this.store.ws.mintCameraPreviewUrl(cleanEntity);
      const ttlSec = Math.max(30, Number(minted.expires_in || 600) - 30);
      this.cameraPreviewCache.set(cleanEntity, {
        url: minted.preview_url,
        expiresAtMs: now + ttlSec * 1000,
      });
      const sep = minted.preview_url.includes("?") ? "&" : "?";
      this.store.activeCameraPreviewEntity = cleanEntity;
      this.store.cameraPreviewUrl = bustCache
        ? `${minted.preview_url}${sep}_ts=${now}`
        : minted.preview_url;
      this.store.host.requestUpdate();
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not load camera preview"), true);
    }
  }

  closeCameraPreview(): void {
    this.store.activeCameraPreviewEntity = "";
    this.store.cameraPreviewUrl = "";
    this.store.host.requestUpdate();
  }

  async testDoorbellSpeaker(): Promise<void> {
    const cams = (this.store.state?.system_config?.camera_entities || [])
      .map((c) => String(c || "").trim())
      .filter(Boolean);
    const firstCam = cams[0];
    if (!firstCam) {
      this.store.showToast("Add a camera in Shared entities first", true);
      return;
    }
    if (!this.store.doorbellTestSubentryId) {
      this.store.showToast("Choose a Device to test from", true);
      return;
    }
    const message = this.store.doorbellTestReply.trim() || "Testing Latter doorbell audio.";
    await this.flushSystemSettings();
    try {
      const res = await this.store.ws.runSystemCommand(
        "test_doorbell_speaker",
        {
          subentry_id: this.store.doorbellTestSubentryId,
          camera_entity: firstCam,
          message,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Played test message on door speaker");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Door speaker test failed"), true);
    }
  }
}
