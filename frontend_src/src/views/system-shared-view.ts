/**
 * System Shared Entities View (`shared_entities`, `D-022`, `D-059`, `D-064`, `D-065`):
 * - Home hub & weather (singleton Weather/Alarm + multi-entity sortable domain boxes)
 * - Calendars & Cameras with pointer/keyboard reordering (`reorderStringListRows`) & combobox
 * - On-demand 600 s camera preview signing (`store.entity.previewCamera`, `Q4`)
 * - Custom colors (`isValidHexColor` swatch guard `A-07`) & shared System wallpapers
 */

import {
  renderCard,
  renderEntityCombobox,
  renderEntitySlotList,
  renderSelectOptions,
  renderSelectRow,
  renderSettingsRow,
  renderSortableList,
  renderSvgIcon,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadProgress,
  renderWallpaperUploadTrigger,
} from "../components/wallpaper-gallery.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StringListKey, StudioStore } from "../state/store.js";
import type { CatalogChoice, SystemConfig } from "../types.js";
import { entityLabel, fmtAgo, fmtNumber, isValidHexColor } from "../utils/format.js";

const ICON_THERMOSTAT =
  "M15,13V5A3,3 0 0,0 9,5V13A5,5 0 1,0 15,13M12,4A1,1 0 0,1 13,5V8H11V5A1,1 0 0,1 12,4Z";
const ICON_LOCK =
  "M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z";
const ICON_GARAGE =
  "M19,20H17V11H7V20H5V9L12,5L19,9V20M8,12H16V14H8V12M8,15H16V17H8V15M16,18V20H8V18H16Z";
const ICON_VACUUM =
  "M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M12,4A8,8 0 0,0 4,12C4,13.38 4.35,14.68 4.97,15.81L18.81,7.82C17.34,5.53 14.84,4 12,4M19.56,9.5L5.72,17.5C7.19,19.62 9.45,21 12,21A8,8 0 0,0 20,13C20,11.75 19.84,10.58 19.56,9.5M12,11A2,2 0 0,1 14,13A2,2 0 0,1 12,15A2,2 0 0,1 10,13A2,2 0 0,1 12,11Z";

function findCatalogChoice(
  choices: readonly CatalogChoice[] | undefined,
  id: string | undefined,
): CatalogChoice | undefined {
  const clean = String(id || "").trim();
  if (!clean || !choices) return undefined;
  return choices.find((c) => c.id === clean);
}

export function renderSystemSharedView(store: StudioStore): TemplateResult {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const cameras = sc?.camera_entities || [];
  const calendars = sc?.calendar_entities || [];
  const palettes = (sc?.custom_palettes || []).filter((p) => isValidHexColor(p.hex));
  const doorbells = data?.doorbells || [];
  const wallpapers = data?.system_wallpapers || [];
  const noiseRed = sc?.doorbell_noise_reduction || "strong";

  const doorbellFilterOptions = [
    { value: "strong", label: store.t("shared.filter_strong") },
    { value: "light", label: store.t("shared.filter_light") },
    { value: "off", label: store.t("shared.filter_off") },
  ];

  const singletonFields: ReadonlyArray<{
    key: keyof Pick<SystemConfig, "weather_entity" | "alarm_entity">;
    label: string;
    choices: readonly CatalogChoice[] | undefined;
  }> = [
    { key: "weather_entity", label: store.t("shared.weather_label"), choices: cat.weathers },
    { key: "alarm_entity", label: store.t("shared.security_alarm_label"), choices: cat.alarms },
  ];

  const multiDomainGroups: ReadonlyArray<{
    key: Extract<
      StringListKey,
      "thermostat_entities" | "lock_entities" | "garage_entities" | "vacuum_entities"
    >;
    title: string;
    addLabel: string;
    emptyPlaceholder: string;
    selectAriaLabel: string;
    removeAriaLabel: string;
    icon: string;
    maxItems: number;
    items: readonly string[];
    choices: readonly CatalogChoice[] | undefined;
  }> = [
    {
      key: "thermostat_entities",
      title: store.t("shared.thermostat_zones"),
      addLabel: store.t("shared.add_zone"),
      emptyPlaceholder: store.t("shared.choose_thermostat"),
      selectAriaLabel: store.t("shared.thermostat_aria"),
      removeAriaLabel: store.t("shared.remove_thermostat"),
      icon: ICON_THERMOSTAT,
      maxItems: 8,
      items: sc?.thermostat_entities || [],
      choices: cat.climates,
    },
    {
      key: "lock_entities",
      title: store.t("shared.door_locks"),
      addLabel: store.t("shared.add_lock"),
      emptyPlaceholder: store.t("shared.choose_lock"),
      selectAriaLabel: store.t("shared.lock_aria"),
      removeAriaLabel: store.t("shared.remove_lock"),
      icon: ICON_LOCK,
      maxItems: 8,
      items: sc?.lock_entities || [],
      choices: cat.locks,
    },
    {
      key: "garage_entities",
      title: store.t("shared.garage_doors"),
      addLabel: store.t("shared.add_garage"),
      emptyPlaceholder: store.t("shared.choose_garage"),
      selectAriaLabel: store.t("shared.garage_aria"),
      removeAriaLabel: store.t("shared.remove_garage"),
      icon: ICON_GARAGE,
      maxItems: 6,
      items: sc?.garage_entities || [],
      choices: cat.garages,
    },
    {
      key: "vacuum_entities",
      title: store.t("shared.robot_vacuums"),
      addLabel: store.t("shared.add_vacuum"),
      emptyPlaceholder: store.t("shared.choose_vacuum"),
      selectAriaLabel: store.t("shared.vacuum_aria"),
      removeAriaLabel: store.t("shared.remove_vacuum"),
      icon: ICON_VACUUM,
      maxItems: 6,
      items: sc?.vacuum_entities || [],
      choices: cat.vacuums,
    },
  ];

  return html`<section id="view-shared_entities">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-whole-home",
          handoffActive: store.isHandoffTarget("card-whole-home"),
          title: store.t("card.home_hub_weather"),
          subtitle: store.t("shared.home_hub_subtitle"),
          contentClass: "stack",
          body: html`<div class="settings-list">
              ${singletonFields.map((f) => {
                const curVal = String(sc?.[f.key] || "");
                const selectId = `cfg-${f.key}`;
                return renderSettingsRow({
                  label: f.label,
                  forId: selectId,
                  control: html`<select
                    id=${selectId}
                    .value=${curVal}
                    @change=${(ev: Event) =>
                      store.entity.stageSystemSetting(
                        f.key,
                        (ev.currentTarget as HTMLSelectElement).value,
                        selectId,
                      )}
                  >
                    ${renderSelectOptions(f.choices, curVal, store.t("common.none_option"))}
                  </select>`,
                });
              })}
            </div>

            ${multiDomainGroups.map((g) => {
              const configuredCount = g.items.filter((s) => Boolean(String(s || "").trim())).length;
              return html`<div id="hub-domain-${g.key}" class="hub-domain-box">
                <div class="hub-domain-head">
                  <span class="hub-domain-title">
                    ${renderSvgIcon(g.icon)}
                    <span>${g.title}</span>
                    ${configuredCount > 0
                      ? html`<span class="chip chip-primary">
                          ${fmtNumber(configuredCount, store.hass, 0)}
                        </span>`
                      : html`<span class="hub-domain-empty">
                          ${store.t("common.none_configured")}
                        </span>`}
                  </span>
                  <button
                    type="button"
                    ?disabled=${g.items.length >= g.maxItems}
                    @click=${() => store.entity.addStringListRow(g.key, "", g.maxItems)}
                    class="btn btn-secondary btn-compact"
                  >
                    ${g.addLabel}
                  </button>
                </div>
                ${g.items.length
                  ? renderSortableList({
                      id: `hub-list-${g.key}`,
                      ariaLabel: g.title,
                      items: g.items,
                      overlay: store.localeOverlay,
                      getKey: (val) => (val ? `ent:${val}` : "empty"),
                      getLabel: (val, idx) => {
                        const meta = findCatalogChoice(g.choices, val);
                        return meta?.name || val || `${g.selectAriaLabel} ${idx + 1}`;
                      },
                      onReorder: (fromIdx, toIdx) =>
                        store.entity.reorderStringListRows(g.key, fromIdx, toIdx),
                      renderContent: (val, idx) => {
                        const meta = findCatalogChoice(g.choices, val);
                        return html`<div class="hub-slot-row">
                          ${(g.choices?.length ?? 0) > 8
                            ? renderEntityCombobox({
                                id: `hub-combo-${g.key}-${idx}`,
                                value: val,
                                options: g.choices,
                                ariaLabel: g.selectAriaLabel,
                                emptyOptionLabel: g.emptyPlaceholder,
                                host: store.host,
                                overlay: store.localeOverlay,
                                onChange: (nextVal) =>
                                  store.entity.updateStringListRow(g.key, idx, nextVal),
                              })
                            : html`<select
                                aria-label=${g.selectAriaLabel}
                                .value=${val}
                                @change=${(ev: Event) =>
                                  store.entity.updateStringListRow(
                                    g.key,
                                    idx,
                                    (ev.currentTarget as HTMLSelectElement).value,
                                  )}
                              >
                                ${renderSelectOptions(g.choices, val, g.emptyPlaceholder)}
                              </select>`}
                          ${meta?.area_name
                            ? html`<span class="hub-slot-meta">
                                <span class="chip">${meta.area_name}</span>
                              </span>`
                            : nothing}
                        </div>`;
                      },
                      renderActions: (_val, idx) =>
                        renderTrashIconButton(g.removeAriaLabel, () =>
                          store.entity.removeStringListRow(g.key, idx),
                        ),
                    })
                  : nothing}
              </div>`;
            })}`,
        })}

        ${renderCard({
          id: "card-calendars",
          handoffActive: store.isHandoffTarget("card-calendars"),
          title: store.t("card.calendars"),
          subtitle: store.t("shared.calendars_subtitle"),
          headerActions: html`<button
            type="button"
            @click=${() => store.entity.addStringListRow("calendar_entities", "", 50)}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("shared.add_calendar")}
          </button>`,
          body: renderEntitySlotList({
            id: "calendars-list",
            items: calendars,
            choices: cat.calendars,
            emptyOptionLabel: store.t("shared.choose_calendar"),
            emptyStateText: store.t("shared.empty_calendars"),
            selectAriaLabel: store.t("shared.calendar_aria"),
            removeAriaLabel: store.t("shared.remove_calendar"),
            useCombobox: (cat.calendars?.length ?? 0) > 8,
            host: store.host,
            onReorder: (fromIdx, toIdx) =>
              store.entity.reorderStringListRows("calendar_entities", fromIdx, toIdx),
            onChange: (idx, val) =>
              store.entity.updateStringListRow("calendar_entities", idx, val),
            onRemove: (idx) => store.entity.removeStringListRow("calendar_entities", idx),
          }),
        })}

        ${renderCard({
          id: "card-system-wallpapers",
          handoffActive: store.isHandoffTarget("card-system-wallpapers"),
          title: store.t("card.wallpapers"),
          subtitle: store.t("shared.wallpapers_subtitle"),
          headerActions: renderWallpaperUploadTrigger(store, "system"),
          contentClass: "stack",
          body: html`${renderWallpaperUploadProgress(store, "system")}
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(store, "system", wallpapers, "square")}
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-cameras-doorbell",
          handoffActive: store.isHandoffTarget("card-cameras-doorbell"),
          title: store.t("card.cameras_doorbell"),
          subtitle: store.t("shared.cameras_subtitle"),
          headerActions: html`<button
            type="button"
            @click=${() => store.entity.addStringListRow("camera_entities", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("shared.add_camera")}
          </button>`,
          contentClass: "stack",
          body: html`<div class="settings-list">
              ${renderSelectRow({
                id: "cfg-doorbell_noise_reduction",
                label: store.t("shared.doorbell_filter_label"),
                description: store.t("shared.doorbell_filter_desc"),
                value: noiseRed,
                rawOptions: doorbellFilterOptions,
                onChange: (val) =>
                  store.entity.stageSystemSetting(
                    "doorbell_noise_reduction",
                    val,
                    "cfg-doorbell_noise_reduction",
                  ),
              })}
            </div>

            ${renderEntitySlotList({
              id: "cameras-list",
              items: cameras,
              choices: cat.cameras,
              emptyOptionLabel: store.t("shared.choose_camera"),
              emptyStateText: store.t("shared.empty_cameras"),
              selectAriaLabel: store.t("shared.camera_aria"),
              removeAriaLabel: store.t("shared.remove_camera"),
              useCombobox: (cat.cameras?.length ?? 0) > 8,
              host: store.host,
              slotLabel: (idx) =>
                idx === 0
                  ? store.t("shared.camera_slot_primary")
                  : store.t("shared.camera_slot_n", { index: idx + 1 }),
              slotMeta: (camId) => {
                const meta = findCatalogChoice(cat.cameras, camId);
                if (!meta) return nothing;
                const chips: TemplateResult[] = [];
                const kind = String(meta.stream_kind || "").trim().toLowerCase();
                if (kind === "rtsp") {
                  chips.push(
                    html`<span class="chip chip-primary">${store.t("shared.cam_cap_rtsp")}</span>`,
                  );
                } else if (kind === "mjpeg") {
                  chips.push(
                    html`<span class="chip chip-primary">${store.t("shared.cam_cap_mjpeg")}</span>`,
                  );
                } else if (kind === "snapshot") {
                  chips.push(
                    html`<span class="chip">${store.t("shared.cam_cap_snapshot")}</span>`,
                  );
                }
                if (meta.has_audio || meta.has_talkback) {
                  chips.push(html`<span class="chip">${store.t("shared.cam_cap_audio")}</span>`);
                }
                if (meta.is_doorbell) {
                  chips.push(
                    html`<span class="chip chip-primary">${store.t("shared.cam_cap_doorbell")}</span>`,
                  );
                }
                return chips.length > 0
                  ? html`<span class="hub-slot-meta">${chips}</span>`
                  : nothing;
              },
              extraActions: (camId) => html`<button
                type="button"
                ?disabled=${!camId}
                @click=${() => void store.entity.previewCamera(camId)}
                class="btn btn-text btn-compact"
              >
                ${store.t("shared.preview")}
              </button>`,
              onReorder: (fromIdx, toIdx) =>
                store.entity.reorderStringListRows("camera_entities", fromIdx, toIdx),
              onChange: (idx, val) =>
                store.entity.updateStringListRow("camera_entities", idx, val),
              onRemove: (idx) => store.entity.removeStringListRow("camera_entities", idx),
            })}

            ${store.cameraPreviewUrl
              ? html`<div id="cam-preview-box" class="cam-preview">
                  <div class="input-action-row">
                    <span class="field-label">
                      ${store.t("shared.preview_heading", {
                        entity: store.activeCameraPreviewEntity,
                      })}
                    </span>
                    <button
                      type="button"
                      @click=${() =>
                        void store.entity.previewCamera(store.activeCameraPreviewEntity, true)}
                      class="btn btn-secondary btn-compact"
                    >
                      ${store.t("action.refresh")}
                    </button>
                    <button
                      type="button"
                      @click=${() => store.entity.closeCameraPreview()}
                      class="btn btn-text btn-compact"
                    >
                      ${store.t("action.close")}
                    </button>
                  </div>
                  <img
                    id="cam-preview-img"
                    src=${store.cameraPreviewUrl}
                    alt=${store.t("shared.camera_preview_alt")}
                  />
                </div>`
              : nothing}

            ${doorbells.length
              ? html`<div id="doorbell-status" class="stack">
                  <h4 class="subsection-title">${store.t("shared.doorbells_heading")}</h4>
                  <div id="doorbell-status-list" class="kv-list">
                    ${doorbells.map((b) => {
                      let ring = store.t("shared.no_ring_sensor");
                      const ringEnt = b.ring_entity || "";
                      if (ringEnt) {
                        const when = b.ring_at
                          ? fmtAgo((Date.now() - Date.parse(b.ring_at)) / 1000, store.hass)
                          : "";
                        const st = ringEnt.startsWith("event.")
                          ? when
                            ? store.t("shared.last_ring", { when })
                            : store.t("shared.no_ring_yet")
                          : b.ring_state === "on"
                            ? store.t("shared.ringing")
                            : b.ring_state
                              ? when
                                ? store.t("shared.idle_changed", { when })
                                : store.t("shared.idle")
                              : store.t("shared.unavailable");
                        ring = `${b.ring_name || ringEnt}: ${st}`;
                      }
                      const talk = (b.talk || [])
                        .map((entry) => {
                          const stateWord =
                            entry.state === "listening"
                              ? store.t("shared.talk_listening")
                              : entry.state === "talking"
                                ? store.t("shared.talk_talking")
                                : entry.state;
                          return `${entry.device_title} ${stateWord}`;
                        })
                        .join(", ");
                      return html`<div class="kv-row">
                        <span>${entityLabel(b.camera_name || b.camera_entity)}</span>
                        <strong>${ring}${talk ? ` • ${talk}` : ""}</strong>
                      </div>`;
                    })}
                  </div>
                </div>`
              : nothing}`,
        })}

        ${renderCard({
          id: "card-custom-colors",
          handoffActive: store.isHandoffTarget("card-custom-colors"),
          title: store.t("card.custom_colors"),
          subtitle: store.t("shared.colors_subtitle"),
          headerActions: html`<button
            type="button"
            @click=${() => store.tools.openColorWheelModal("system")}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("shared.add_color")}
          </button>`,
          contentClass: "settings-list",
          body: html`<div id="sys-custom-palettes-list" class="settings-list">
            ${palettes.length
              ? palettes.map((p) => {
                  const h = p.hex.toUpperCase();
                  const swStyle = `--swatch-color:${h}`;
                  return renderSettingsRow({
                    labelHtml: html`<span class="row-label">
                      <span class="swatch" style=${swStyle} aria-hidden="true"></span>
                      ${p.name || h}
                    </span>`,
                    description: html`<code>${h}</code>`,
                    control: renderTrashIconButton(
                      store.t("shared.delete_color_aria", { name: p.name || h }),
                      () => store.entity.deleteCustomPalette(h),
                    ),
                  });
                })
              : html`<p class="empty-state">${store.t("shared.empty_colors")}</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}
