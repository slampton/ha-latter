/**
 * Shared Store Context & Modal/Pending Contracts (`StudioStoreContext`).
 *
 * Keeps `state/` strictly acyclic by providing a contract interface that every
 * `state/` sub-controller imports instead of importing `state/store.ts`.
 */

import type { StudioWsClient } from "../api/ws-client.js";
import {
  type DevicePrefSpecItem,
  VIRTUAL_COLLECTION_ALL,
} from "../constants.js";
import type { StudioTranslationKey } from "../i18n/index.js";
import type { ReactiveControllerHost } from "../lib/lit.js";
import type { MdiIconStyleFilter } from "../mdi-catalog.js";
import type {
  BleSurveyDeltaEvent,
  BleSurveyRow,
  ConfigurableAppId,
  CropPreviewAspect,
  DeviceCapabilities,
  DevicePrefItem,
  DeviceViewId,
  DiscoveredBleCandidate,
  HomeAssistant,
  MediaBrowseFolder,
  MediaBrowseImage,
  MediaBrowseRoot,
  PhotoCrop,
  PhotoPoolTarget,
  ShortcutAccent,
  ShortcutBadgeStyle,
  ShortcutItem,
  StudioScope,
  StudioStatePayload,
  StudioViewId,
  SystemConfig,
  SystemViewId,
} from "../types.js";
import { DEFAULT_PHOTO_CROP } from "../utils/crop-math.js";

/**
 * Single canonical trait-driven capability gate.
 * Never hides or rejects items when `caps` or an individual trait is `undefined` (unknown).
 */
export function isCatalogItemSupported(
  item: { capability?: string },
  caps?: DeviceCapabilities,
): boolean {
  const cap = item.capability;
  if (!cap || !caps) return true;
  switch (cap) {
    case "round":
      return caps.is_round !== false;
    case "imu":
      return caps.has_imu !== false;
    case "no_imu":
      return caps.has_imu !== true;
    case "display_imu":
      return caps.has_display !== false && caps.has_imu !== false;
    case "display":
      return caps.has_display !== false;
    case "display_or_audio":
      return caps.has_display !== false || caps.has_audio !== false;
    case "battery":
      return caps.has_battery !== false;
    case "display_battery":
      return caps.has_display !== false && caps.has_battery !== false;
    case "beacon":
      return caps.has_ble_beacon !== false;
    case "beacon_battery":
      return caps.has_ble_beacon !== false && caps.has_battery !== false;
    case "mic":
      return caps.has_voice !== false;
    case "speaker":
      return caps.has_audio !== false;
    case "hw_jpeg":
      return caps.hw_jpeg === true;
    default:
      return true;
  }
}

export type TokenListKey =
  | "area_categories"
  | "home_categories"
  | "tools_items"
  | "games_items"
  | "activity_sources";

export interface TokenListOps {
  getEnabled(): string[];
  toggle(token: string, forceEnabled?: boolean): void;
  move(token: string, delta: -1 | 1): void;
  reorder(fromEnabledIndex: number, toEnabledIndex: number): void;
}

export const STRING_LIST_KEYS = [
  "calendar_entities",
  "camera_entities",
  "remotes_list",
  "thermostat_entities",
  "lock_entities",
  "garage_entities",
  "vacuum_entities",
  "broadcast_speakers",
  "broadcast_phrases",
] as const;

export type StringListKey = (typeof STRING_LIST_KEYS)[number];

export const STRING_LIST_MAX_ITEMS: Readonly<Record<StringListKey, number>> = {
  camera_entities: 10,
  remotes_list: 10,
  calendar_entities: 50,
  thermostat_entities: 8,
  lock_entities: 8,
  garage_entities: 6,
  vacuum_entities: 6,
  broadcast_speakers: 32,
  broadcast_phrases: 12,
};

export function isStringListKey(key: string): key is StringListKey {
  return (
    key === "calendar_entities" ||
    key === "camera_entities" ||
    key === "remotes_list" ||
    key === "thermostat_entities" ||
    key === "lock_entities" ||
    key === "garage_entities" ||
    key === "vacuum_entities" ||
    key === "broadcast_speakers" ||
    key === "broadcast_phrases"
  );
}

export function cleanPersistedStringList(items: readonly unknown[], maxItems: number): string[] {
  const out: string[] = [];
  for (const raw of items) {
    const ent = String(raw || "").trim();
    if (ent && !out.includes(ent)) {
      out.push(ent);
      if (out.length >= maxItems) break;
    }
  }
  return out;
}

export function mergePersistedWithBlankSlots(
  persisted: readonly string[],
  blankCount: number,
  maxItems: number,
  prevUiList?: readonly string[],
): { uiList: string[]; clampedBlankCount: number } {
  const cleaned = cleanPersistedStringList(persisted, maxItems);
  const clampedBlankCount = Math.max(0, Math.min(blankCount, maxItems - cleaned.length));
  if (clampedBlankCount === 0) {
    return { uiList: cleaned, clampedBlankCount: 0 };
  }
  if (prevUiList && prevUiList.some((v) => !String(v || "").trim())) {
    const uiList: string[] = [];
    let cleanIdx = 0;
    let blanksPlaced = 0;
    for (const slot of prevUiList) {
      if (uiList.length >= maxItems) break;
      if (!String(slot || "").trim()) {
        if (blanksPlaced < clampedBlankCount) {
          uiList.push("");
          blanksPlaced += 1;
        }
      } else if (cleanIdx < cleaned.length) {
        const cleanItem = cleaned[cleanIdx];
        if (cleanItem !== undefined) {
          uiList.push(cleanItem);
        }
        cleanIdx += 1;
      }
    }
    while (cleanIdx < cleaned.length && uiList.length < maxItems) {
      const cleanItem = cleaned[cleanIdx];
      if (cleanItem !== undefined) {
        uiList.push(cleanItem);
      }
      cleanIdx += 1;
    }
    while (blanksPlaced < clampedBlankCount && uiList.length < maxItems) {
      uiList.push("");
      blanksPlaced += 1;
    }
    return { uiList, clampedBlankCount: blanksPlaced };
  }
  return {
    uiList: [...cleaned, ...Array<string>(clampedBlankCount).fill("")],
    clampedBlankCount,
  };
}

export interface DevicePendingBucket {
  targetSubentryId: string;
  targetTitle: string;
  patch: Record<string, unknown>;
  previousValues: Record<string, unknown>;
  keySeqs: Record<string, number>;
  timer: ReturnType<typeof setTimeout> | null;
}

export interface PendingEntityEntry {
  state: string;
  previousValue?: string;
  expires: number;
}

export interface PendingDomRevert {
  controlIds: Record<string, string | boolean>;
}

export interface BatchPillState {
  token: string;
  label: string;
  state: "on" | "off" | "mixed";
  staged: boolean;
}

export interface StagedUploadPhoto {
  id: string;
  file: File;
  name: string;
  crop: PhotoCrop;
  objectUrl: string;
  width: number;
  height: number;
}

export interface PhotoUploadModalState {
  open: boolean;
  files: StagedUploadPhoto[];
  activeIndex: number;
  collectionId: string;
  newCollectionOpen: boolean;
  newCollectionName: string;
  creatingCollection: boolean;
  previewAspect: CropPreviewAspect;
  uploading: boolean;
  currentIndex: number;
  currentPercent: number;
  draggingFiles: boolean;
  onComplete: ((uploadedIds: string[]) => void) | null;
}

export interface PhotoEditModalState {
  open: boolean;
  photoId: string;
  name: string;
  crop: PhotoCrop;
  collections: string[];
  previewAspect: CropPreviewAspect;
  busy: boolean;
}

export interface MediaImportModalState {
  open: boolean;
  loading: boolean;
  importing: boolean;
  error: string;
  roots: MediaBrowseRoot[];
  root: string;
  subpath: string;
  parentSubpath: string | null;
  folders: MediaBrowseFolder[];
  images: MediaBrowseImage[];
  selectedPaths: string[];
  collectionId: string;
  useNewFolderCollection: boolean;
  newCollectionName: string;
  deduplicate: boolean;
}

export interface PhotoPickerModalState {
  open: boolean;
  target: PhotoPoolTarget;
  mode: "photos" | "collection";
  collectionId: string;
  selectedIds: string[];
  search: string;
  filterCollection: string;
  busy: boolean;
}

export interface ConfirmModalState {
  open: boolean;
  kind: string;
  title: string;
  consequence: string;
  confirmLabel: string;
  cancelLabel: string;
  danger: boolean;
  blastRadiusCount: number | null;
  blastRadiusLabel: string;
  busy: boolean;
  onConfirm: (() => Promise<void> | void) | null;
  onDownloadBackupFirst: (() => Promise<void> | void) | null;
}

export interface OpenConfirmOptions {
  kind?: string;
  title: string;
  consequence: string;
  confirmLabel: string;
  cancelLabel?: string;
  danger?: boolean;
  blastRadiusCount?: number | null;
  blastRadiusLabel?: string;
  onConfirm: () => Promise<void> | void;
  onDownloadBackupFirst?: (() => Promise<void> | void) | null;
}

export function emptyPhotoUploadModalState(): PhotoUploadModalState {
  return {
    open: false,
    files: [],
    activeIndex: 0,
    collectionId: "",
    newCollectionOpen: false,
    newCollectionName: "",
    creatingCollection: false,
    previewAspect: "square",
    uploading: false,
    currentIndex: 0,
    currentPercent: 0,
    draggingFiles: false,
    onComplete: null,
  };
}

export function emptyPhotoEditModalState(): PhotoEditModalState {
  return {
    open: false,
    photoId: "",
    name: "",
    crop: { ...DEFAULT_PHOTO_CROP },
    collections: [],
    previewAspect: "square",
    busy: false,
  };
}

export function emptyMediaImportModalState(): MediaImportModalState {
  return {
    open: false,
    loading: false,
    importing: false,
    error: "",
    roots: [],
    root: "",
    subpath: "",
    parentSubpath: null,
    folders: [],
    images: [],
    selectedPaths: [],
    collectionId: "",
    useNewFolderCollection: false,
    newCollectionName: "",
    deduplicate: true,
  };
}

export function emptyPhotoPickerModalState(): PhotoPickerModalState {
  return {
    open: false,
    target: "wallpaper",
    mode: "photos",
    collectionId: VIRTUAL_COLLECTION_ALL,
    selectedIds: [],
    search: "",
    filterCollection: VIRTUAL_COLLECTION_ALL,
    busy: false,
  };
}

export function emptyConfirmModalState(): ConfirmModalState {
  return {
    open: false,
    kind: "",
    title: "",
    consequence: "",
    confirmLabel: "",
    cancelLabel: "",
    danger: true,
    blastRadiusCount: null,
    blastRadiusLabel: "",
    busy: false,
    onConfirm: null,
    onDownloadBackupFirst: null,
  };
}

export interface EntityControllerContract {
  getPref(key: string): DevicePrefItem | undefined;
  getPrefSpec(key: string): DevicePrefSpecItem | undefined;
  getEffectiveSystemPatch(): Record<string, unknown>;
  getEffectiveDevicePatch(subentryId: string): Record<string, unknown>;
  stageDeviceSetting(
    key: string,
    value: unknown,
    controlDomId?: string,
    debounceMs?: number,
  ): void;
  flushDeviceBucket(subentryId: string): Promise<void>;
  discardDeviceBucket(subentryId: string): void;
  stageSystemSetting<K extends keyof SystemConfig>(
    key: K,
    value: SystemConfig[K],
    controlDomId?: string,
    debounceMs?: number,
  ): void;
  flushSystemSettings(): Promise<void>;
  flushAllPendingSettings(): Promise<void>;
  getDockItems(): ShortcutItem[];
  getPinnedItems(): ShortcutItem[];
  applyDeviceCustomColor(hex: string, switchColorProfile?: boolean): void;
  clearCameraPreviewCache(): void;
}

export interface GroupsControllerContract {
  resetBatchDraft(): void;
}

export interface ToolsControllerContract {
  openConfirm(opts: OpenConfirmOptions): void;
  closeConfirm(): void;
  runConfirmedAction(): Promise<void>;
}

export interface StudioStoreContext {
  readonly host: ReactiveControllerHost & HTMLElement;
  readonly ws: StudioWsClient;
  readonly hass: HomeAssistant | null;
  readonly localeOverlay: Readonly<Record<string, string>> | null;
  readonly entity: EntityControllerContract;
  readonly groups: GroupsControllerContract;
  readonly tools: ToolsControllerContract;

  currentScope: StudioScope;
  currentViewId: StudioViewId;
  activeSubentryId: string;
  deviceSelected: boolean;
  deviceLoading: boolean;

  state: StudioStatePayload | null;
  loading: boolean;
  loadError: string;
  studioRevMismatch: boolean;

  toastMessage: string;
  toastIsError: boolean;
  politeAnnouncement: string;
  assertiveAnnouncement: string;
  liveClockNowMs: number;
  selectedBackupFile: File | null;

  deviceSortField: "title" | "model" | "area" | "group" | "status";
  deviceSortAsc: boolean;
  deviceCategoryFilter: string;
  discoveredBleSearch: string;
  discoveredBleKindFilter: "all" | "tracker" | "named";
  discoveredBleSort: "name" | "rssi" | "area";
  discoveredBlePaused: boolean;
  discoveredBleFrozenSnapshot: DiscoveredBleCandidate[] | null;
  discoveredIgnoredOpen: boolean;
  readonly discoveredBlePersonDrafts: Map<string, string>;
  readonly discoveredLatterGroupDrafts: Map<string, string>;
  readonly discoveredLatterPersonDrafts: Map<string, string>;
  readonly discoveredBleSeenCache: Map<
    string,
    { candidate: DiscoveredBleCandidate; lastSeenMs: number }
  >;

  devicePinDraft: string;
  systemPinDraft: string;
  pinBusy: boolean;
  worldClockNewLabel: string;
  worldClockNewZone: string;
  worldClockRowKeys: string[];
  worldClockRowSeq: number;
  overviewAlarmsOpen: boolean;

  activeCameraPreviewEntity: string;
  cameraPreviewUrl: string;
  photosFilterCollection: string;
  photosSearch: string;
  photosPage: number;
  photosSelectMode: boolean;
  readonly photosSelectedIds: Set<string>;
  photosNewCollectionOpen: boolean;
  photosNewCollectionName: string;
  photosRenamingCollectionId: string;
  photosRenamingCollectionName: string;
  photosBulkTargetCollectionId: string;

  newGroupFormOpen: boolean;
  newGroupName: string;
  newGroupDesc: string;
  newGroupSourceSubentryId: string;
  newGroupIncludeDisplay: boolean;
  newGroupIncludeInterface: boolean;
  readonly openGroupIds: Set<string>;
  readonly groupCopySourceDrafts: Map<string, string>;
  batchTargetFilter: string;
  batchCategoryFilter: string;
  batchCopySourceSubentryId: string;
  readonly openBatchCategories: Set<string>;
  readonly batchDraft: Map<string, unknown>;

  bleSurveySubentryId: string;
  bleCalibrateAreaId: string;
  bleCalibrateHandoffActive: boolean;
  bleLiveStreamActive: boolean;
  readonly bleSurveyFrozen: Map<
    string,
    { rows: BleSurveyRow[]; packetsSeen: number; activeAreaName: string }
  >;
  readonly openProxyTrims: Set<string>;
  advancedBleOpen: boolean;
  readonly openFusionAreas: Set<string>;

  announceMode: "notify" | "broadcast";
  announceTarget: string;
  announceTitle: string;
  announceMessage: string;
  announcePriority: "normal" | "warning" | "critical";
  announceIncludeCamera: boolean;
  doorbellTestSubentryId: string;
  doorbellTestReply: string;
  backupExportScope: string;
  backupRestoreSubentryId: string;
  logsOpen: boolean;
  logFilter: string;

  confirmModal: ConfirmModalState;
  removeModal: { open: boolean; subentryId: string; title: string; busy: boolean };
  resetModal: {
    open: boolean;
    deviceSettings: boolean;
    latterOptions: boolean;
    busy: boolean;
  };
  addBleModal: {
    open: boolean;
    candidateAddr: string;
    name: string;
    address: string;
    assignedPerson: string;
    bleCategory: string;
    busy: boolean;
  };
  colorWheelModal: {
    open: boolean;
    targetScope: StudioScope;
    hex: string;
    name: string;
    busy: boolean;
    painted: boolean;
  };
  saveGroupModal: {
    open: boolean;
    subentryId: string;
    name: string;
    description: string;
    includeDisplay: boolean;
    includeInterface: boolean;
    busy: boolean;
  };
  shortcutModal: {
    open: boolean;
    listKey: "dock_items" | "pinned_items";
    editIndex: number | null;
    kind: "route" | "entity";
    routeTarget: string;
    entityDomainFilter: string;
    entitySearch: string;
    entityTarget: string;
    action: string;
    label: string;
    icon: string;
    iconSearch: string;
    iconStyleFilter: MdiIconStyleFilter;
    badgeStyle: ShortcutBadgeStyle;
    accent: ShortcutAccent;
    confirm: boolean;
  };
  appConfigModal: { open: boolean; app: ConfigurableAppId | null };
  cameraConfigModal: {
    open: boolean;
    cameraId: string;
    label: string;
    showListen: boolean;
    showTalk: boolean;
    showReply: boolean;
    unlockEntity: string;
  };
  photoUploadModal: PhotoUploadModalState;
  photoEditModal: PhotoEditModalState;
  mediaImportModal: MediaImportModalState;
  photoPickerModal: PhotoPickerModalState;
  returnToPinnedModal: boolean;

  pendingScrollCardId: string;
  readonly handoffTargetIds: Set<string>;
  pendingDomRevert: PendingDomRevert | null;
  pendingSystemPatch: Record<string, unknown>;
  pendingSystemPrevious: Record<string, unknown>;
  systemSaveTimer: ReturnType<typeof setTimeout> | null;
  readonly pendingBlankListSlots: Record<StringListKey, number>;
  readonly pendingDeviceBuckets: Map<string, DevicePendingBucket>;
  readonly pendingEntityStates: Map<string, PendingEntityEntry>;

  t(key: StudioTranslationKey, vars?: Readonly<Record<string, string | number>>): string;
  tPrefLabel(key: string, fallback?: string): string;
  tPrefOption(prefKey: string, opt: string): string;
  openConfirm(opts: OpenConfirmOptions): void;
  closeConfirm(): void;
  runConfirmedAction(): Promise<void>;
  getKnownDeviceConfigRev(subentryId: string): number;
  recordKnownDeviceConfigRev(subentryId: string, rev: number): void;
  syncLiveClockTimer(): void;
  mergeDomRevert(controlIds: Record<string, string | boolean>): void;
  isHandoffTarget(targetId: string): boolean;
  clearHandoffTargets(): void;
  applySectionHandoff(scrollId?: string, highlightIds?: readonly string[]): void;
  handleStudioRevMismatch(): void;
  announcePolite(message: string): void;
  announceAssertive(message: string): void;
  showToast(message: string, isError?: boolean): void;
  dismissToast(): void;
  shouldIncludeLogs(): boolean;
  deviceHasView(viewId: DeviceViewId): boolean;
  onActiveDeviceChanged(
    prevId: string,
    nextId: string,
    options?: { discardPrevPending?: boolean },
  ): void;
  redirectInvalidDeviceRoute(invalidId?: string): void;
  syncUrl(replace?: boolean): void;
  openDevicesLanding(): void;
  openDiscoveredDevices(cardId?: string): void;
  switchView(viewId: StudioViewId): void;
  openSystemSection(
    viewId: SystemViewId,
    cardId?: string,
    highlightIds?: readonly string[],
  ): void;
  openDeviceSection(
    viewId: Exclude<DeviceViewId, "select_device_prompt" | "discovered_devices">,
    cardId?: string,
    highlightIds?: readonly string[],
  ): void;
  switchSystemDevice(nextSubentryId: string, targetView?: DeviceViewId): Promise<void>;
  teardownSubscription(): void;
  desiredSubscriptionKey(): string;
  ensureSubscription(forceResubscribe?: boolean): Promise<void>;
  refreshState(options?: { includeLogs?: boolean }): Promise<void>;
  applyBleSurveyDelta(delta: BleSurveyDeltaEvent): void;
  ingestPayload(incoming: StudioStatePayload, logsWereRequested: boolean): void;
  evictAdoptedBleCandidate(targetAddress: string): void;
  ensureDefaultSurveyDevice(): void;
  ensureDefaultDoorbellTester(): void;
  ensureValidBatchTargetFilter(): void;
}
