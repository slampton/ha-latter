/**
 * Photo Library, Collections, Non-Destructive Crop, HA Media Import, & Device Photo Pool
 * operations (`D-072`, `STUDIO_REV = 39`).
 */

import { formatWsError } from "../api/ws-client.js";
import {
  MAX_WALLPAPER_UPLOAD_BYTES,
  VIRTUAL_COLLECTION_ALL,
  VIRTUAL_COLLECTION_DEFAULTS,
  VIRTUAL_COLLECTION_UNCATEGORIZED,
  VIRTUAL_COLLECTION_UPLOADS,
} from "../constants.js";
import type {
  PhotoItem,
  PhotoPoolMode,
  PhotoPoolTarget,
} from "../types.js";
import { DEFAULT_PHOTO_CROP, normalizePhotoCrop } from "../utils/crop-math.js";
import {
  emptyMediaImportModalState,
  emptyPhotoEditModalState,
  emptyPhotoPickerModalState,
  emptyPhotoUploadModalState,
  type MediaImportModalState,
  type PhotoEditModalState,
  type PhotoPickerModalState,
  type PhotoUploadModalState,
  type StagedUploadPhoto,
  type StudioStoreContext,
} from "./store-types.js";

export {
  emptyMediaImportModalState,
  emptyPhotoEditModalState,
  emptyPhotoPickerModalState,
  emptyPhotoUploadModalState,
  type MediaImportModalState,
  type PhotoEditModalState,
  type PhotoPickerModalState,
  type PhotoUploadModalState,
  type StagedUploadPhoto,
};

export function isPhotoUploaded(photo: PhotoItem): boolean {
  return (
    photo.kind === "uploaded" ||
    photo.kind === "upload" ||
    photo.source_kind === "upload" ||
    photo.source_kind === "media_import" ||
    Boolean(photo.deletable)
  );
}

export function isPhotoDynamic(photo: PhotoItem): boolean {
  return photo.kind === "dynamic_preset" || photo.source_kind === "dynamic_preset";
}

export function filterEligiblePhotoIds(
  ids: readonly string[] | undefined,
  photos: readonly PhotoItem[],
  excludeDynamic = false,
): string[] {
  const eligible = new Set(
    photos.filter((p) => !excludeDynamic || !isPhotoDynamic(p)).map((p) => p.id),
  );
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of ids || []) {
    const id = String(raw || "").trim();
    if (!id || seen.has(id) || !eligible.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

export function derivePhotoBaseName(filename: string): string {
  const clean = String(filename || "")
    .replace(/^.*[\\/]/, "")
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .trim();
  return clean || "Photo";
}

export function filterLibraryPhotos(
  photos: readonly PhotoItem[],
  filterCollection: string,
  search: string,
  options?: { excludeDynamic?: boolean },
): PhotoItem[] {
  const q = String(search || "").trim().toLowerCase();
  return photos.filter((p) => {
    if (options?.excludeDynamic && isPhotoDynamic(p)) {
      return false;
    }
    if (filterCollection === VIRTUAL_COLLECTION_DEFAULTS) {
      if (isPhotoUploaded(p)) return false;
    } else if (filterCollection === VIRTUAL_COLLECTION_UPLOADS) {
      if (!isPhotoUploaded(p)) return false;
    } else if (filterCollection === VIRTUAL_COLLECTION_UNCATEGORIZED) {
      if ((p.collections || []).length > 0) return false;
    } else if (filterCollection && filterCollection !== VIRTUAL_COLLECTION_ALL) {
      if (!(p.collections || []).includes(filterCollection)) return false;
    }
    if (q) {
      const hay = `${p.name || ""} ${p.id || ""} ${p.media_source_path || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export function resolveCollectionDisplayName(store: StudioStoreContext, collectionId: string): string {
  if (!collectionId || collectionId === VIRTUAL_COLLECTION_ALL) {
    return store.t("photos.filter_all");
  }
  if (collectionId === VIRTUAL_COLLECTION_DEFAULTS) {
    return store.t("photos.filter_defaults");
  }
  if (collectionId === VIRTUAL_COLLECTION_UPLOADS) {
    return store.t("photos.filter_my_photos");
  }
  if (collectionId === VIRTUAL_COLLECTION_UNCATEGORIZED) {
    return store.t("photos.filter_uncategorized");
  }
  const found = (store.state?.photo_collections || []).find((c) => c.id === collectionId);
  return found?.name || collectionId;
}

export function resolvePoolPhotos(
  photos: readonly PhotoItem[],
  mode: string,
  singleSource: string,
  collectionId: string,
  customIds: readonly string[],
  options?: { excludeDynamic?: boolean },
): PhotoItem[] {
  const pool = options?.excludeDynamic ? photos.filter((p) => !isPhotoDynamic(p)) : [...photos];
  if (mode === "off") return [];
  if (mode === "single") {
    const found = pool.find((p) => p.id === singleSource);
    return found ? [found] : [];
  }
  if (mode === "collection") {
    return filterLibraryPhotos(pool, collectionId || VIRTUAL_COLLECTION_ALL, "", options);
  }
  if (mode === "custom") {
    const byId = new Map(pool.map((p) => [p.id, p]));
    const out: PhotoItem[] = [];
    for (const id of customIds) {
      const item = byId.get(id);
      if (item && !out.includes(item)) out.push(item);
    }
    return out;
  }
  return [];
}

export interface PhotoImageCacheEvictor {
  evict(url: string): void;
  clear(): void;
}

let photoImageEvictor: PhotoImageCacheEvictor | null = null;

export function registerPhotoImageEvictor(evictor: PhotoImageCacheEvictor | null): void {
  photoImageEvictor = evictor;
}

export function evictPhotoImageCache(url: string): void {
  if (url) {
    photoImageEvictor?.evict(url);
  }
}

export function clearPhotoImageCache(): void {
  photoImageEvictor?.clear();
}

function revokeStagedUrls(files: readonly StagedUploadPhoto[]): void {
  const canRevoke = typeof URL !== "undefined" && typeof URL.revokeObjectURL === "function";
  for (const f of files) {
    if (f.objectUrl) {
      evictPhotoImageCache(f.objectUrl);
      if (canRevoke) {
        try {
          URL.revokeObjectURL(f.objectUrl);
        } catch {
          // Ignore revoke errors in test shims.
        }
      }
    }
  }
}

export function revokeAllStagedPhotoUploads(files: readonly StagedUploadPhoto[]): void {
  revokeStagedUrls(files);
}

let stagedUploadSeq = 0;

export function openPhotoUploadModalOp(
  store: StudioStoreContext,
  options?: { defaultCollectionId?: string; onComplete?: (uploadedIds: string[]) => void },
): void {
  revokeStagedUrls(store.photoUploadModal.files);
  const defaultCol =
    options?.defaultCollectionId ??
    (store.photosFilterCollection.startsWith("col_") ? store.photosFilterCollection : "");
  store.photoUploadModal = {
    ...emptyPhotoUploadModalState(),
    open: true,
    collectionId: defaultCol,
    onComplete: options?.onComplete ?? null,
  };
  store.host.requestUpdate();
}

export function closePhotoUploadModalOp(store: StudioStoreContext): void {
  if (store.photoUploadModal.uploading) return;
  revokeStagedUrls(store.photoUploadModal.files);
  store.photoUploadModal = emptyPhotoUploadModalState();
  store.host.requestUpdate();
}

export function stageUploadFilesOp(store: StudioStoreContext, fileList: FileList | readonly File[]): void {
  const incoming = Array.from(fileList || []);
  if (!incoming.length) return;
  const nextFiles = [...store.photoUploadModal.files];
  for (const file of incoming) {
    if (!file) continue;
    if (file.size > MAX_WALLPAPER_UPLOAD_BYTES) {
      store.showToast(
        store.t("photo_upload.file_too_large", { name: file.name || "image" }),
        true,
      );
      continue;
    }
    const id = `staged_${++stagedUploadSeq}`;
    const objectUrl =
      typeof URL !== "undefined" && typeof URL.createObjectURL === "function"
        ? URL.createObjectURL(file)
        : "";
    nextFiles.push({
      id,
      file,
      name: derivePhotoBaseName(file.name),
      crop: { ...DEFAULT_PHOTO_CROP },
      objectUrl,
      width: 0,
      height: 0,
    });
  }
  const activeIdx =
    store.photoUploadModal.files.length === 0 && nextFiles.length > 0
      ? 0
      : Math.min(store.photoUploadModal.activeIndex, Math.max(0, nextFiles.length - 1));
  store.photoUploadModal = {
    ...store.photoUploadModal,
    files: nextFiles,
    activeIndex: activeIdx,
    draggingFiles: false,
  };
  store.host.requestUpdate();
}

export function removeStagedUploadOp(store: StudioStoreContext, index: number): void {
  const files = store.photoUploadModal.files;
  if (index < 0 || index >= files.length || store.photoUploadModal.uploading) return;
  const removed = files[index];
  if (removed) revokeStagedUrls([removed]);
  const next = files.filter((_, i) => i !== index);
  const nextActive = Math.min(store.photoUploadModal.activeIndex, Math.max(0, next.length - 1));
  store.photoUploadModal = {
    ...store.photoUploadModal,
    files: next,
    activeIndex: nextActive,
  };
  store.host.requestUpdate();
}

export async function uploadAllStagedPhotosOp(store: StudioStoreContext): Promise<void> {
  let modal = store.photoUploadModal;
  if (modal.uploading || modal.creatingCollection || modal.files.length === 0) return;

  if (modal.newCollectionOpen && modal.newCollectionName.trim()) {
    const createdId = await createUploadCollectionOp(store);
    if (!createdId) return;
    modal = store.photoUploadModal;
  }

  store.photoUploadModal = {
    ...modal,
    uploading: true,
    currentIndex: 0,
    currentPercent: 0,
  };
  store.host.requestUpdate();

  const uploadedIds: string[] = [];
  const total = modal.files.length;
  const colId = modal.collectionId || "";
  const onComplete = modal.onComplete;

  try {
    for (let i = 0; i < total; i += 1) {
      const item = modal.files[i];
      if (!item) continue;
      store.photoUploadModal = {
        ...store.photoUploadModal,
        currentIndex: i + 1,
        currentPercent: 0,
      };
      store.host.requestUpdate();

      const res = await store.ws.uploadWallpaperMultipart({
        scope: "system",
        file: item.file,
        name: item.name.trim() || derivePhotoBaseName(item.file.name),
        crop: normalizePhotoCrop(item.crop),
        collectionId: colId || undefined,
        onProgress: (pct) => {
          store.photoUploadModal = {
            ...store.photoUploadModal,
            currentPercent: pct,
          };
          store.host.requestUpdate();
        },
      });
      const createdId = res.photo_id || res.source_id || res.photo?.id || "";
      if (createdId) uploadedIds.push(createdId);
      if (store.state) {
        if (res.system_wallpapers) {
          store.state = {
            ...store.state,
            system_wallpapers: res.system_wallpapers,
            photo_collections: res.photo_collections ?? store.state.photo_collections,
          };
        }
      }
    }

    revokeStagedUrls(store.photoUploadModal.files);
    store.photoUploadModal = emptyPhotoUploadModalState();
    await store.refreshState();
    store.showToast(
      uploadedIds.length === 1
        ? store.t("photo_upload.uploaded_one_toast")
        : store.t("photo_upload.uploaded_many_toast", { count: uploadedIds.length }),
    );
    if (onComplete) {
      onComplete(uploadedIds);
    }
  } catch (err) {
    store.photoUploadModal = {
      ...store.photoUploadModal,
      uploading: false,
    };
    store.host.requestUpdate();
    store.showToast(formatWsError(err, "Photo upload failed"), true);
  }
}

// ---------- Photo Editor & Crop Modal ----------

export function openPhotoEditModalOp(store: StudioStoreContext, photo: PhotoItem): void {
  store.photoEditModal = {
    open: true,
    photoId: photo.id,
    name: photo.name || photo.id,
    crop: normalizePhotoCrop(photo.crop),
    collections: [...(photo.collections || [])],
    previewAspect: "square",
    busy: false,
  };
  store.host.requestUpdate();
}

export function closePhotoEditModalOp(store: StudioStoreContext): void {
  if (store.photoEditModal.busy) return;
  const photo = (store.state?.system_wallpapers || []).find(
    (p) => p.id === store.photoEditModal.photoId,
  );
  const srcUrl = photo?.orig_url || photo?.thumb_url || photo?.preview_url || "";
  if (srcUrl) {
    evictPhotoImageCache(srcUrl);
  }
  store.photoEditModal = emptyPhotoEditModalState();
  store.host.requestUpdate();
}

export async function savePhotoEditModalOp(store: StudioStoreContext): Promise<void> {
  const modal = store.photoEditModal;
  if (!modal.open || !modal.photoId || modal.busy) return;

  const photo = (store.state?.system_wallpapers || []).find((p) => p.id === modal.photoId);
  const uploaded = photo ? isPhotoUploaded(photo) : modal.photoId.startsWith("photo:");

  store.photoEditModal = { ...modal, busy: true };
  store.host.requestUpdate();

  try {
    const payload: Record<string, unknown> = {
      photo_id: modal.photoId,
      collections: [...modal.collections],
    };
    if (uploaded) {
      const cleanName = modal.name.trim();
      if (cleanName) payload.name = cleanName;
      payload.crop = normalizePhotoCrop(modal.crop);
    }
    const res = await store.ws.runSystemCommand(
      "update_photo_metadata",
      payload,
      store.activeSubentryId || null,
    );
    const srcUrl = photo?.orig_url || photo?.thumb_url || photo?.preview_url || "";
    if (srcUrl) {
      evictPhotoImageCache(srcUrl);
    }
    store.photoEditModal = emptyPhotoEditModalState();
    if (res) store.ingestPayload(res, false);
    else store.host.requestUpdate();
    store.showToast(store.t("photos.updated_photo_toast"));
  } catch (err) {
    store.photoEditModal = { ...store.photoEditModal, busy: false };
    store.host.requestUpdate();
    store.showToast(formatWsError(err, "Could not update photo"), true);
  }
}

// ---------- Photo Library Collections & Bulk Actions ----------

export async function createPhotoCollectionOp(
  store: StudioStoreContext,
  rawName: string,
): Promise<string | null> {
  const name = String(rawName || "").trim();
  if (!name) return null;
  try {
    const res = await store.ws.runSystemCommand(
      "create_photo_collection",
      { name },
      store.activeSubentryId || null,
    );
    store.photosNewCollectionOpen = false;
    store.photosNewCollectionName = "";
    if (res) store.ingestPayload(res, false);
    store.showToast(store.t("photos.created_collection_toast", { name }));
    const createdId = String(res?.collection?.id || "").trim();
    return createdId || null;
  } catch (err) {
    store.showToast(formatWsError(err, "Could not create collection"), true);
    return null;
  }
}

export async function createUploadCollectionOp(store: StudioStoreContext): Promise<string | null> {
  const modal = store.photoUploadModal;
  const name = modal.newCollectionName.trim();
  if (!modal.open || modal.uploading || modal.creatingCollection || !name) return null;
  store.photoUploadModal = { ...modal, creatingCollection: true };
  store.host.requestUpdate();
  const createdId = await createPhotoCollectionOp(store, name);
  if (createdId) {
    store.photoUploadModal = {
      ...store.photoUploadModal,
      collectionId: createdId,
      newCollectionOpen: false,
      newCollectionName: "",
      creatingCollection: false,
    };
  } else {
    store.photoUploadModal = {
      ...store.photoUploadModal,
      creatingCollection: false,
    };
  }
  store.host.requestUpdate();
  return createdId;
}

export async function renamePhotoCollectionOp(
  store: StudioStoreContext,
  collectionId: string,
  rawName: string,
): Promise<void> {
  const cleanId = String(collectionId || "").trim();
  const name = String(rawName || "").trim();
  if (!cleanId || !name) return;
  try {
    const res = await store.ws.runSystemCommand(
      "rename_photo_collection",
      { collection_id: cleanId, name },
      store.activeSubentryId || null,
    );
    store.photosRenamingCollectionId = "";
    store.photosRenamingCollectionName = "";
    if (res) store.ingestPayload(res, false);
    store.showToast(store.t("photos.renamed_collection_toast", { name }));
  } catch (err) {
    store.showToast(formatWsError(err, "Could not rename collection"), true);
  }
}

export function requestDeletePhotoCollectionOp(
  store: StudioStoreContext,
  collectionId: string,
  name: string,
): void {
  const cleanId = String(collectionId || "").trim();
  if (!cleanId) return;
  store.openConfirm({
    kind: "delete_collection",
    title: store.t("confirm.delete_collection.title", { name }),
    consequence: store.t("confirm.delete_collection.body"),
    confirmLabel: store.t("confirm.delete_collection.confirm"),
    danger: true,
    onConfirm: async () => {
      try {
        const res = await store.ws.runSystemCommand(
          "delete_photo_collection",
          { collection_id: cleanId },
          store.activeSubentryId || null,
        );
        if (store.photosFilterCollection === cleanId) {
          store.photosFilterCollection = VIRTUAL_COLLECTION_ALL;
          store.photosPage = 1;
        }
        if (res) store.ingestPayload(res, false);
        store.showToast(store.t("photos.deleted_collection_toast"));
      } catch (err) {
        store.showToast(formatWsError(err, "Could not delete collection"), true);
      }
    },
  });
}

export async function deletePhotoOp(store: StudioStoreContext, photoId: string): Promise<void> {
  const cleanId = String(photoId || "").trim();
  if (!cleanId) return;
  try {
    const res = await store.ws.runSystemCommand(
      "delete_photo",
      { photo_id: cleanId },
      store.activeSubentryId || null,
    );
    store.photosSelectedIds.delete(cleanId);
    if (store.photoEditModal.open && store.photoEditModal.photoId === cleanId) {
      store.photoEditModal = emptyPhotoEditModalState();
    }
    if (res) store.ingestPayload(res, false);
    store.showToast(store.t("photos.deleted_photo_toast"));
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete photo"), true);
  }
}

export function requestDeletePhotoOp(store: StudioStoreContext, photoId: string, name?: string): void {
  const cleanId = String(photoId || "").trim();
  if (!cleanId) return;
  const label = String(name || cleanId).trim();
  store.openConfirm({
    kind: "delete_photo",
    title: store.t("confirm.delete_photo.title", { name: label }),
    consequence: store.t("confirm.delete_photo.body"),
    confirmLabel: store.t("confirm.delete_photo.confirm"),
    danger: true,
    onConfirm: async () => {
      await deletePhotoOp(store, cleanId);
    },
  });
}

export async function bulkUpdatePhotosOp(
  store: StudioStoreContext,
  options: { addCollection?: string; removeCollection?: string; deletePhotos?: boolean },
): Promise<void> {
  const ids = Array.from(store.photosSelectedIds);
  if (ids.length === 0) return;
  const payload: Record<string, unknown> = { photo_ids: ids };
  if (options.addCollection) payload.add_collection = options.addCollection;
  if (options.removeCollection) payload.remove_collection = options.removeCollection;
  if (options.deletePhotos) payload.delete = true;
  try {
    const res = await store.ws.runSystemCommand(
      "bulk_update_photos",
      payload,
      store.activeSubentryId || null,
    );
    store.photosSelectedIds.clear();
    if (options.deletePhotos) {
      store.photosSelectMode = false;
    }
    if (res) store.ingestPayload(res, false);
    const deletedCount = res?.bulk_result?.deleted_ids?.length ?? 0;
    const updatedCount = res?.bulk_result?.updated ?? ids.length;
    store.showToast(
      options.deletePhotos
        ? store.t("photos.bulk_deleted_toast", { count: deletedCount || ids.length })
        : store.t("photos.bulk_updated_toast", { count: updatedCount }),
    );
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update selected photos"), true);
  }
}

export function requestBulkDeletePhotosOp(store: StudioStoreContext): void {
  const deletableSelected = Array.from(store.photosSelectedIds).filter((id) => {
    const item = (store.state?.system_wallpapers || []).find((p) => p.id === id);
    return item ? isPhotoUploaded(item) : false;
  });
  if (deletableSelected.length === 0) return;
  store.openConfirm({
    kind: "bulk_delete_photos",
    title: store.t("confirm.delete_photos_bulk.title", { count: deletableSelected.length }),
    consequence: store.t("confirm.delete_photos_bulk.body"),
    confirmLabel: store.t("confirm.delete_photos_bulk.confirm"),
    danger: true,
    onConfirm: async () => {
      store.photosSelectedIds.clear();
      for (const id of deletableSelected) {
        store.photosSelectedIds.add(id);
      }
      await bulkUpdatePhotosOp(store, { deletePhotos: true });
    },
  });
}

// ---------- HA Media Folder Import Modal ----------

export async function browseMediaFolderOp(
  store: StudioStoreContext,
  root?: string,
  subpath?: string,
): Promise<void> {
  store.mediaImportModal = {
    ...store.mediaImportModal,
    loading: true,
    error: "",
    selectedPaths: [],
  };
  store.host.requestUpdate();
  try {
    const res = await store.ws.browseMediaFolder(root, subpath);
    const folderLeaf = (res.subpath || "").split("/").filter(Boolean).pop() || res.root || "";
    store.mediaImportModal = {
      ...store.mediaImportModal,
      loading: false,
      error: "",
      roots: res.roots || [],
      root: res.root || "",
      subpath: res.subpath || "",
      parentSubpath: res.parent_subpath ?? null,
      folders: res.folders || [],
      images: res.images || [],
      selectedPaths: [],
      newCollectionName: store.mediaImportModal.useNewFolderCollection
        ? folderLeaf
        : store.mediaImportModal.newCollectionName,
    };
  } catch (err) {
    store.mediaImportModal = {
      ...store.mediaImportModal,
      loading: false,
      error: formatWsError(err, "Could not browse Home Assistant Media"),
    };
  }
  store.host.requestUpdate();
}

export function openMediaImportModalOp(store: StudioStoreContext): void {
  const defaultCol = store.photosFilterCollection.startsWith("col_")
    ? store.photosFilterCollection
    : "";
  store.mediaImportModal = {
    ...emptyMediaImportModalState(),
    open: true,
    collectionId: defaultCol,
  };
  store.host.requestUpdate();
  void browseMediaFolderOp(store);
}

export function closeMediaImportModalOp(store: StudioStoreContext): void {
  if (store.mediaImportModal.importing) return;
  store.mediaImportModal = emptyMediaImportModalState();
  store.host.requestUpdate();
}

export async function importSelectedMediaOp(store: StudioStoreContext): Promise<void> {
  const modal = store.mediaImportModal;
  if (modal.importing || !modal.root || modal.selectedPaths.length === 0) return;

  store.mediaImportModal = { ...modal, importing: true };
  store.host.requestUpdate();

  try {
    const payload: Record<string, unknown> = {
      root: modal.root,
      paths: [...modal.selectedPaths],
      deduplicate: modal.deduplicate,
    };
    if (modal.useNewFolderCollection && modal.newCollectionName.trim()) {
      payload.new_collection_name = modal.newCollectionName.trim();
    } else if (modal.collectionId) {
      payload.collection_id = modal.collectionId;
    }

    const res = await store.ws.runSystemCommand(
      "import_media_photos",
      payload,
      store.activeSubentryId || null,
    );
    store.mediaImportModal = emptyMediaImportModalState();
    if (res) store.ingestPayload(res, false);
    else store.host.requestUpdate();

    const imp = res?.import_result;
    const imported = imp?.imported ?? modal.selectedPaths.length;
    const skipped = imp?.skipped ?? 0;
    const failed = imp?.failed?.length ?? 0;
    store.showToast(
      store.t("media_import.summary_toast", {
        imported,
        skippedSuffix: skipped > 0 ? store.t("media_import.skipped_suffix", { count: skipped }) : "",
        failedSuffix: failed > 0 ? store.t("media_import.failed_suffix", { count: failed }) : "",
      }),
    );
  } catch (err) {
    store.mediaImportModal = { ...store.mediaImportModal, importing: false };
    store.host.requestUpdate();
    store.showToast(formatWsError(err, "Media import failed"), true);
  }
}

// ---------- Device Photo Pool Picker & Command ----------

export async function setDevicePhotoPoolOp(
  store: StudioStoreContext,
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
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return false;
  const payload: Record<string, unknown> = {
    target: options.target,
    mode: options.mode,
  };
  if (options.sourceId !== undefined) payload.source_id = options.sourceId;
  if (options.collectionId !== undefined) payload.collection_id = options.collectionId;
  if (options.photoIds !== undefined) payload.photo_ids = [...options.photoIds];
  if (options.cycleMinutes !== undefined) payload.cycle_minutes = options.cycleMinutes;
  if (options.shuffle !== undefined) payload.shuffle = options.shuffle;

  try {
    const res = await store.ws.runDeviceCommand(
      targetSubentryId,
      "set_device_photo_pool",
      payload,
    );
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    if (toastMessage) {
      store.showToast(toastMessage);
    } else {
      store.announcePolite(store.t("shell.saved_status"));
    }
    return true;
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update photo pool"), true);
    return false;
  }
}

export function openPhotoPickerModalOp(store: StudioStoreContext, target: PhotoPoolTarget): void {
  const cfg = store.state?.config || {};
  const isScreensaver = target === "screensaver";
  const allPhotos =
    (store.state?.wallpapers && store.state.wallpapers.length > 0
      ? store.state.wallpapers
      : store.state?.system_wallpapers) || [];
  const rawMode = String(
    isScreensaver ? cfg.screensaver_photo_mode || "off" : cfg.wallpaper_mode || "off",
  );
  const mode: "photos" | "collection" = rawMode === "collection" ? "collection" : "photos";
  const rawSingleSource = String(
    isScreensaver ? cfg.screensaver_photo_source || "" : cfg.wallpaper_source || "",
  );
  const collectionId = String(
    isScreensaver
      ? cfg.screensaver_photo_collection || VIRTUAL_COLLECTION_ALL
      : cfg.wallpaper_collection || VIRTUAL_COLLECTION_ALL,
  );
  const rawCustomIds = Array.isArray(
    isScreensaver ? cfg.screensaver_photo_ids : cfg.wallpaper_favorites,
  )
    ? ((isScreensaver ? cfg.screensaver_photo_ids : cfg.wallpaper_favorites) as string[])
    : [];
  const initialIds =
    rawMode === "single"
      ? rawSingleSource
        ? [rawSingleSource]
        : []
      : rawMode === "custom"
        ? rawCustomIds
        : rawCustomIds.length > 0
          ? rawCustomIds
          : rawSingleSource
            ? [rawSingleSource]
            : [];
  const selectedIds = filterEligiblePhotoIds(initialIds, allPhotos, isScreensaver);

  store.photoPickerModal = {
    open: true,
    target,
    mode,
    collectionId: collectionId || VIRTUAL_COLLECTION_ALL,
    selectedIds,
    search: "",
    filterCollection: VIRTUAL_COLLECTION_ALL,
    busy: false,
  };
  store.host.requestUpdate();
}

export function closePhotoPickerModalOp(store: StudioStoreContext): void {
  if (store.photoPickerModal.busy) return;
  store.photoPickerModal = emptyPhotoPickerModalState();
  store.host.requestUpdate();
}

export async function applyPhotoPickerModalOp(store: StudioStoreContext): Promise<void> {
  const modal = store.photoPickerModal;
  if (!modal.open || modal.busy) return;

  const isScreensaver = modal.target === "screensaver";
  const allPhotos =
    (store.state?.wallpapers && store.state.wallpapers.length > 0
      ? store.state.wallpapers
      : store.state?.system_wallpapers) || [];
  const cleanSelectedIds = filterEligiblePhotoIds(modal.selectedIds, allPhotos, isScreensaver);

  store.photoPickerModal = { ...modal, selectedIds: cleanSelectedIds, busy: true };
  store.host.requestUpdate();

  const cfg = store.state?.config || {};
  const currentCycle = Number(
    isScreensaver ? cfg.screensaver_cycle_minutes ?? 15 : cfg.wallpaper_cycle_minutes ?? 0,
  );
  const wireMode: Exclude<PhotoPoolMode, "off"> =
    modal.mode === "collection"
      ? "collection"
      : cleanSelectedIds.length === 1
        ? "single"
        : "custom";
  // Picking 1 photo sets a static image (0 min); picking a Collection or 2+ photos defaults to 15 min if off.
  const nextCycle =
    wireMode === "single"
      ? 0
      : currentCycle > 0
        ? currentCycle
        : 15;

  const ok = await setDevicePhotoPoolOp(store, {
    target: modal.target,
    mode: wireMode,
    sourceId: wireMode === "single" ? cleanSelectedIds[0] : undefined,
    collectionId: wireMode === "collection" ? modal.collectionId : undefined,
    photoIds: wireMode === "custom" ? cleanSelectedIds : undefined,
    cycleMinutes: nextCycle,
    shuffle: isScreensaver ? Boolean(cfg.screensaver_shuffle) : undefined,
  });

  if (ok) {
    store.photoPickerModal = emptyPhotoPickerModalState();
  } else {
    store.photoPickerModal = { ...store.photoPickerModal, busy: false };
  }
  store.host.requestUpdate();
}
