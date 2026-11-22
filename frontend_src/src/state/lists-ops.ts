/**
 * System String-List Slots, Volume Overrides, Remote Control Groups, & Per-Device
 * Broadcast/Camera List Operations (`L2` leaf).
 */

import type { RemoteGroup, VolumeOverride } from "../types.js";
import {
  cleanPersistedStringList,
  mergePersistedWithBlankSlots,
  STRING_LIST_MAX_ITEMS,
  type StringListKey,
  type StudioStoreContext,
} from "./store-types.js";

export function updateStringListRowOp(
  store: StudioStoreContext,
  key: StringListKey,
  index: number,
  value: string,
): void {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const prevUiList = [...(store.state?.system_config?.[key] || [])];
  if (index < 0 || index >= prevUiList.length) return;

  const prevPersisted = cleanPersistedStringList(prevUiList, maxItems);
  const nextRaw = [...prevUiList];
  nextRaw[index] = String(value || "").trim();

  const seen = new Set<string>();
  const nextUiList: string[] = [];
  for (const item of nextRaw) {
    const ent = String(item || "").trim();
    if (!ent) {
      nextUiList.push("");
    } else if (!seen.has(ent)) {
      seen.add(ent);
      nextUiList.push(ent);
    }
    if (nextUiList.length >= maxItems) break;
  }

  const nextPersisted = nextUiList.filter(Boolean);
  store.pendingBlankListSlots[key] = nextUiList.length - nextPersisted.length;

  const persistedChanged =
    prevPersisted.length !== nextPersisted.length ||
    prevPersisted.some((v, i) => v !== nextPersisted[i]);

  if (persistedChanged) {
    store.entity.stageSystemSetting(key, nextPersisted);
    if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: nextUiList,
        },
      };
      store.host.requestUpdate();
    }
  } else if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: nextUiList,
      },
    };
    store.host.requestUpdate();
  }
}

export function addStringListRowOp(
  store: StudioStoreContext,
  key: StringListKey,
  defaultEntity = "",
  maxLen = STRING_LIST_MAX_ITEMS[key],
): void {
  const cap = Math.min(maxLen, STRING_LIST_MAX_ITEMS[key]);
  const list = [...(store.state?.system_config?.[key] || [])];
  if (list.length >= cap) {
    store.showToast(`Maximum of ${cap} entries reached`, true);
    return;
  }
  const cleanDefault = String(defaultEntity || "").trim();
  if (!cleanDefault) {
    list.push("");
    store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;
    if (store.state?.system_config) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
    }
    store.host.requestUpdate();
    return;
  }
  const nextPersisted = cleanPersistedStringList([...list, cleanDefault], cap);
  const wantBlanks = Math.max(
    0,
    Math.min(store.pendingBlankListSlots[key] || 0, cap - nextPersisted.length),
  );
  store.pendingBlankListSlots[key] = wantBlanks;
  store.entity.stageSystemSetting(key, nextPersisted);
  if (store.state?.system_config && wantBlanks > 0) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: [...nextPersisted, ...Array<string>(wantBlanks).fill("")],
      },
    };
    store.host.requestUpdate();
  }
}

export function removeStringListRowOp(
  store: StudioStoreContext,
  key: StringListKey,
  index: number,
): void {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const list = [...(store.state?.system_config?.[key] || [])];
  if (index < 0 || index >= list.length) return;
  const [removed] = list.splice(index, 1);
  const wasBlank = !String(removed || "").trim();
  store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;

  if (wasBlank) {
    if (store.state?.system_config) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
    }
    store.host.requestUpdate();
    return;
  }

  const nextPersisted = cleanPersistedStringList(list, maxItems);
  store.entity.stageSystemSetting(key, nextPersisted);
  if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
    const { uiList, clampedBlankCount } = mergePersistedWithBlankSlots(
      nextPersisted,
      store.pendingBlankListSlots[key],
      maxItems,
      list,
    );
    store.pendingBlankListSlots[key] = clampedBlankCount;
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: uiList,
      },
    };
    store.host.requestUpdate();
  }
}

export function reorderStringListRowsOp(
  store: StudioStoreContext,
  key: StringListKey,
  fromIndex: number,
  toIndex: number,
): void {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const list = [...(store.state?.system_config?.[key] || [])];
  if (
    fromIndex < 0 ||
    fromIndex >= list.length ||
    toIndex < 0 ||
    toIndex >= list.length ||
    fromIndex === toIndex
  ) {
    return;
  }
  const prevPersisted = cleanPersistedStringList(list, maxItems);
  const [moved] = list.splice(fromIndex, 1);
  if (moved === undefined) return;
  list.splice(toIndex, 0, moved);
  const nextPersisted = cleanPersistedStringList(list, maxItems);
  store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;

  const persistedChanged =
    prevPersisted.length !== nextPersisted.length ||
    prevPersisted.some((v, i) => v !== nextPersisted[i]);

  if (persistedChanged) {
    store.entity.stageSystemSetting(key, nextPersisted);
    if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
      store.host.requestUpdate();
    }
  } else if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: list,
      },
    };
    store.host.requestUpdate();
  }
}

export function addVolumeOverrideRowOp(store: StudioStoreContext): void {
  const list: VolumeOverride[] = [...(store.state?.system_config?.volume_overrides || [])];
  if (list.length >= 10) {
    store.showToast("Maximum of 10 volume overrides reached", true);
    return;
  }
  const speakers = store.state?.catalog?.ma_speakers || [];
  const targets = store.state?.catalog?.volume_targets || store.state?.catalog?.remotes || [];
  list.push({
    speaker: speakers[0]?.id || "",
    target: targets[0]?.id || speakers[0]?.id || "",
  });
  store.entity.stageSystemSetting("volume_overrides", list);
}

export function updateVolumeOverrideRowOp(
  store: StudioStoreContext,
  index: number,
  field: "speaker" | "target",
  value: string,
): void {
  const list: VolumeOverride[] = (store.state?.system_config?.volume_overrides || []).map((v) => ({
    ...v,
  }));
  const row = list[index];
  if (!row) return;
  row[field] = value;
  store.entity.stageSystemSetting("volume_overrides", list);
}

export function removeVolumeOverrideRowOp(store: StudioStoreContext, index: number): void {
  const list: VolumeOverride[] = [...(store.state?.system_config?.volume_overrides || [])];
  list.splice(index, 1);
  store.entity.stageSystemSetting("volume_overrides", list);
}

export function addRemoteGroupRowOp(store: StudioStoreContext): void {
  const groups: RemoteGroup[] = (store.state?.system_config?.remote_groups || []).map((g) => ({
    ...g,
    remotes: [...(g.remotes || [])],
  }));
  const id = `group_${Date.now().toString(36)}`;
  groups.push({ id, name: "New remote group", area_id: "", remotes: [] });
  store.entity.stageSystemSetting("remote_groups", groups);
}

export function updateRemoteGroupFieldOp(
  store: StudioStoreContext,
  groupId: string,
  field: "name" | "area_id",
  value: string,
): void {
  const groups: RemoteGroup[] = (store.state?.system_config?.remote_groups || []).map((g) =>
    g.id === groupId ? { ...g, [field]: value } : { ...g, remotes: [...(g.remotes || [])] },
  );
  store.entity.stageSystemSetting("remote_groups", groups);
}

export function toggleRemoteInGroupOp(
  store: StudioStoreContext,
  groupId: string,
  remoteEntity: string,
): void {
  const groups: RemoteGroup[] = (store.state?.system_config?.remote_groups || []).map((g) => {
    if (g.id !== groupId) return { ...g, remotes: [...(g.remotes || [])] };
    const remotes = [...(g.remotes || [])];
    const idx = remotes.indexOf(remoteEntity);
    if (idx >= 0) remotes.splice(idx, 1);
    else remotes.push(remoteEntity);
    return { ...g, remotes };
  });
  store.entity.stageSystemSetting("remote_groups", groups);
}

export function removeRemoteGroupRowOp(store: StudioStoreContext, groupId: string): void {
  const groups = (store.state?.system_config?.remote_groups || []).filter((g) => g.id !== groupId);
  store.entity.stageSystemSetting("remote_groups", groups);
}

// ---------- Per-Device Broadcast Speakers & Visible/Carousel Camera Lists ----------

export function getSystemBroadcastSpeakersOp(store: StudioStoreContext): string[] {
  const out: string[] = [];
  for (const raw of store.state?.system_config?.broadcast_speakers || []) {
    const id = String(raw || "").trim();
    if (id && !out.includes(id)) {
      out.push(id);
    }
  }
  return out;
}

export function getBroadcastSpeakersOp(store: StudioStoreContext): string[] {
  const sys = getSystemBroadcastSpeakersOp(store);
  if (sys.length === 0) return [];
  const raw = store.state?.config?.broadcast_speaker_entities;
  if (!Array.isArray(raw) || raw.length === 0) {
    return [...sys];
  }
  const filtered: string[] = [];
  for (const item of raw) {
    const id = String(item || "").trim();
    if (id && sys.includes(id) && !filtered.includes(id)) {
      filtered.push(id);
    }
  }
  return filtered.length > 0 ? filtered : [...sys];
}

export function toggleBroadcastSpeakerOp(
  store: StudioStoreContext,
  entityId: string,
  forceEnabled?: boolean,
): void {
  const cleanId = String(entityId || "").trim();
  const sys = getSystemBroadcastSpeakersOp(store);
  if (!cleanId || !sys.includes(cleanId)) return;
  const current = getBroadcastSpeakersOp(store);
  const idx = current.indexOf(cleanId);
  const currentlyOn = idx >= 0;
  const wantOn = forceEnabled !== undefined ? Boolean(forceEnabled) : !currentlyOn;
  if (wantOn === currentlyOn) return;

  let next: string[];
  if (!wantOn) {
    if (current.length <= 1) {
      store.showToast(store.t("common.keep_one_enabled", { noun: "speaker" }), true);
      return;
    }
    next = current.filter((id) => id !== cleanId);
  } else {
    next = [...current, cleanId];
  }
  const sameAsSys = next.length === sys.length && next.every((id, i) => id === sys[i]);
  store.entity.stageDeviceSetting("broadcast_speaker_entities", sameAsSys ? [] : next);
}

export function reorderBroadcastSpeakersOp(
  store: StudioStoreContext,
  fromIndex: number,
  toIndex: number,
): void {
  const sys = getSystemBroadcastSpeakersOp(store);
  const current = getBroadcastSpeakersOp(store);
  if (
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= current.length ||
    toIndex >= current.length ||
    fromIndex === toIndex
  ) {
    return;
  }
  const next = [...current];
  const [moved] = next.splice(fromIndex, 1);
  if (moved === undefined) return;
  next.splice(toIndex, 0, moved);
  const sameAsSys = next.length === sys.length && next.every((id, i) => id === sys[i]);
  store.entity.stageDeviceSetting("broadcast_speaker_entities", sameAsSys ? [] : next);
}

export function getSystemCameraEntitiesOp(store: StudioStoreContext): string[] {
  const out: string[] = [];
  for (const raw of store.state?.system_config?.camera_entities || []) {
    const id = String(raw || "").trim();
    if (id && !out.includes(id)) {
      out.push(id);
    }
  }
  return out;
}

export function getVisibleCamerasOp(store: StudioStoreContext): string[] {
  const sys = getSystemCameraEntitiesOp(store);
  if (sys.length === 0) return [];
  const raw = store.state?.config?.camera_visible_entities;
  if (!Array.isArray(raw) || raw.length === 0) {
    return [...sys];
  }
  const filtered: string[] = [];
  for (const item of raw) {
    const id = String(item || "").trim();
    if (id && sys.includes(id) && !filtered.includes(id)) {
      filtered.push(id);
    }
  }
  return filtered.length > 0 ? filtered : [...sys];
}

export function toggleVisibleCameraOp(
  store: StudioStoreContext,
  entityId: string,
  forceEnabled?: boolean,
): void {
  const cleanId = String(entityId || "").trim();
  const sys = getSystemCameraEntitiesOp(store);
  if (!cleanId || !sys.includes(cleanId)) return;
  const current = getVisibleCamerasOp(store);
  const idx = current.indexOf(cleanId);
  const currentlyOn = idx >= 0;
  const wantOn = forceEnabled !== undefined ? Boolean(forceEnabled) : !currentlyOn;
  if (wantOn === currentlyOn) return;

  let next: string[];
  if (!wantOn) {
    if (current.length <= 1) {
      store.showToast(store.t("common.keep_one_enabled", { noun: "camera" }), true);
      return;
    }
    next = current.filter((id) => id !== cleanId);
  } else {
    next = [...current, cleanId];
  }
  const sameAsSys = next.length === sys.length && next.every((id, i) => id === sys[i]);
  store.entity.stageDeviceSetting("camera_visible_entities", sameAsSys ? [] : next);

  if (!wantOn) {
    const rawCarousel = Array.isArray(store.state?.config?.camera_carousel_entities)
      ? store.state.config.camera_carousel_entities
          .map((c) => String(c || "").trim())
          .filter(Boolean)
      : [];
    if (rawCarousel.length > 0 && rawCarousel.includes(cleanId)) {
      const pruned = rawCarousel.filter((id) => next.includes(id));
      const sameAsVisible =
        pruned.length === next.length && pruned.every((id, i) => id === next[i]);
      store.entity.stageDeviceSetting(
        "camera_carousel_entities",
        pruned.length === 0 || sameAsVisible ? [] : pruned,
      );
    }
  }
}

export function reorderVisibleCamerasOp(
  store: StudioStoreContext,
  fromIndex: number,
  toIndex: number,
): void {
  const sys = getSystemCameraEntitiesOp(store);
  const current = getVisibleCamerasOp(store);
  if (
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= current.length ||
    toIndex >= current.length ||
    fromIndex === toIndex
  ) {
    return;
  }
  const next = [...current];
  const [moved] = next.splice(fromIndex, 1);
  if (moved === undefined) return;
  next.splice(toIndex, 0, moved);
  const sameAsSys = next.length === sys.length && next.every((id, i) => id === sys[i]);
  store.entity.stageDeviceSetting("camera_visible_entities", sameAsSys ? [] : next);
}

export function getCarouselCamerasOp(store: StudioStoreContext): string[] {
  const visible = getVisibleCamerasOp(store);
  if (visible.length === 0) return [];
  const raw = store.state?.config?.camera_carousel_entities;
  if (!Array.isArray(raw) || raw.length === 0) {
    return [...visible];
  }
  const filtered: string[] = [];
  for (const item of raw) {
    const id = String(item || "").trim();
    if (id && visible.includes(id) && !filtered.includes(id)) {
      filtered.push(id);
    }
  }
  return filtered.length > 0 ? filtered : [...visible];
}

export function toggleCarouselCameraOp(
  store: StudioStoreContext,
  entityId: string,
  forceEnabled?: boolean,
): void {
  const cleanId = String(entityId || "").trim();
  const visible = getVisibleCamerasOp(store);
  if (!cleanId || !visible.includes(cleanId)) return;
  const current = getCarouselCamerasOp(store);
  const idx = current.indexOf(cleanId);
  const currentlyOn = idx >= 0;
  const wantOn = forceEnabled !== undefined ? Boolean(forceEnabled) : !currentlyOn;
  if (wantOn === currentlyOn) return;

  let next: string[];
  if (!wantOn) {
    if (current.length <= 1) {
      store.showToast(store.t("common.keep_one_enabled", { noun: "camera" }), true);
      return;
    }
    next = current.filter((id) => id !== cleanId);
  } else {
    next = [...current, cleanId];
  }
  const sameAsVisible =
    next.length === visible.length && next.every((id, i) => id === visible[i]);
  store.entity.stageDeviceSetting("camera_carousel_entities", sameAsVisible ? [] : next);
}

export function reorderCarouselCamerasOp(
  store: StudioStoreContext,
  fromIndex: number,
  toIndex: number,
): void {
  const visible = getVisibleCamerasOp(store);
  const current = getCarouselCamerasOp(store);
  if (
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= current.length ||
    toIndex >= current.length ||
    fromIndex === toIndex
  ) {
    return;
  }
  const next = [...current];
  const [moved] = next.splice(fromIndex, 1);
  if (moved === undefined) return;
  next.splice(toIndex, 0, moved);
  const sameAsVisible =
    next.length === visible.length && next.every((id, i) => id === visible[i]);
  store.entity.stageDeviceSetting("camera_carousel_entities", sameAsVisible ? [] : next);
}
