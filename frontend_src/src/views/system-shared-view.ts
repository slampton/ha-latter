/**
 * System Shared Entities View (`shared_entities`): Home Hub & Weather, Calendars, Cameras & Doorbell Audio, Custom Colors & Wallpapers (D-022 / D-059).
 */

import {
  renderCard,
  renderEntitySlotList,
  renderSelectOptions,
  renderSelectRow,
  renderSettingsRow,
  renderSvgIcon,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadProgress,
  renderWallpaperUploadTrigger,
} from "../components/wallpaper-gallery.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StringListKey } from "../state/entity-config-ops.js";
import type { StudioStore } from "../state/store.js";
import type { CatalogChoice, SystemConfig } from "../types.js";
import { entityLabel, fmtAgo, fmtNumber } from "../utils/format.js";

const ICON_THERMOSTAT =
  "M15,13V5A3,3 0 0,0 9,5V13A5,5 0 1,0 15,13M12,4A1,1 0 0,1 13,5V8H11V5A1,1 0 0,1 12,4Z";
const ICON_LOCK =
  "M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z";
const ICON_GARAGE =
  "M19,20H17V11H7V20H5V9L12,5L19,9V20M8,12H16V14H8V12M8,15H16V17H8V15M16,18V20H8V18H16Z";
const ICON_VACUUM =
  "M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M12,4A8,8 0 0,0 4,12C4,13.38 4.35,14.68 4.97,15.81L18.81,7.82C17.34,5.53 14.84,4 12,4M19.56,9.5L5.72,17.5C7.19,19.62 9.45,21 12,21A8,8 0 0,0 20,13C20,11.75 19.84,10.58 19.56,9.5M12,11A2,2 0 0,1 14,13A2,2 0 0,1 12,15A2,2 0 0,1 10,13A2,2 0 0,1 12,11Z";
const ICON_ARROW_UP = "M7.41,15.41L12,10.83L16.59,15.41L18,14L12,8L6,14L7.41,15.41Z";
const ICON_ARROW_DOWN = "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z";

function toneChipClass(tone: string | undefined): string {
  if (tone === "primary") return "chip chip-primary";
  if (tone === "success") return "chip chip-success";
  if (tone === "warning") return "chip chip-warning";
  if (tone === "error") return "chip chip-error";
  return "chip";
}

function findCatalogChoice(
  choices: readonly CatalogChoice[] | undefined,
  id: string | undefined,
): CatalogChoice | undefined {
  const clean = String(id || "").trim();
  if (!clean || !choices) return undefined;
  return choices.find((c) => c.id === clean);
}

const TALK_STATE_TEXT: Record<string, string> = {
  listening: "listening",
  talking: "replying",
};

const DOORBELL_FILTER_OPTIONS = [
  { value: "strong", label: "Strong" },
  { value: "light", label: "Light" },
  { value: "off", label: "Off" },
] as const;

export function renderSystemSharedView(store: StudioStore): TemplateResult {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const cameras = sc?.camera_entities || [];
  const calendars = sc?.calendar_entities || [];
  const palettes = sc?.custom_palettes || [];
  const doorbells = data?.doorbells || [];
  const wallpapers = data?.system_wallpapers || [];
  const noiseRed = sc?.doorbell_noise_reduction || "strong";

  const singletonFields: ReadonlyArray<{
    key: keyof Pick<SystemConfig, "weather_entity" | "alarm_entity">;
    label: string;
    choices: readonly CatalogChoice[] | undefined;
  }> = [
    { key: "weather_entity", label: "Weather", choices: cat.weathers },
    { key: "alarm_entity", label: "Security Alarm", choices: cat.alarms },
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
      title: "Thermostat Zones",
      addLabel: "Add Zone",
      emptyPlaceholder: "— Choose a thermostat —",
      selectAriaLabel: "Thermostat zone",
      removeAriaLabel: "Remove thermostat zone",
      icon: ICON_THERMOSTAT,
      maxItems: 8,
      items: sc?.thermostat_entities || [],
      choices: cat.climates,
    },
    {
      key: "lock_entities",
      title: "Door Locks",
      addLabel: "Add Lock",
      emptyPlaceholder: "— Choose a door lock —",
      selectAriaLabel: "Door lock",
      removeAriaLabel: "Remove door lock",
      icon: ICON_LOCK,
      maxItems: 8,
      items: sc?.lock_entities || [],
      choices: cat.locks,
    },
    {
      key: "garage_entities",
      title: "Garage Doors",
      addLabel: "Add Garage Door",
      emptyPlaceholder: "— Choose a garage door —",
      selectAriaLabel: "Garage door",
      removeAriaLabel: "Remove garage door",
      icon: ICON_GARAGE,
      maxItems: 6,
      items: sc?.garage_entities || [],
      choices: cat.garages,
    },
    {
      key: "vacuum_entities",
      title: "Robot Vacuums",
      addLabel: "Add Vacuum",
      emptyPlaceholder: "— Choose a robot vacuum —",
      selectAriaLabel: "Robot vacuum",
      removeAriaLabel: "Remove robot vacuum",
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
          handoffActive: Boolean(store.isHandoffTarget?.("card-whole-home")),
          heading: html`<h3 class="card-title">Home Hub &amp; Weather</h3>`,
          subtitle:
            "Shared climate zones, entry controls, vacuums, security, and weather across every Device.",
          contentClass: "stack",
          body: html`<div class="settings-list">
              ${singletonFields.map((f) => {
                const curVal = String(sc?.[f.key] || "");
                const meta = findCatalogChoice(f.choices, curVal);
                const selectId = `cfg-${f.key}`;
                return renderSettingsRow({
                  label: f.label,
                  forId: selectId,
                  control: html`${meta?.state_label
                      ? html`<span class=${toneChipClass(meta.state_tone)}>
                          ${meta.state_label}
                        </span>`
                      : nothing}
                    <select
                      id=${selectId}
                      .value=${curVal}
                      @change=${(ev: Event) =>
                        store.stageSystemSetting(
                          f.key,
                          (ev.currentTarget as HTMLSelectElement).value,
                          selectId,
                        )}
                    >
                      ${renderSelectOptions(f.choices, curVal, "— None —")}
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
                      : html`<span class="hub-domain-empty">None configured</span>`}
                  </span>
                  <button
                    type="button"
                    ?disabled=${g.items.length >= g.maxItems}
                    @click=${() => store.addStringListRow(g.key, "", g.maxItems)}
                    class="btn btn-secondary btn-compact"
                  >
                    ${g.addLabel}
                  </button>
                </div>
                ${g.items.length
                  ? g.items.map((val, idx) => {
                      const meta = findCatalogChoice(g.choices, val);
                      return html`<div class="hub-slot-row">
                        <select
                          aria-label=${g.selectAriaLabel}
                          .value=${val}
                          @change=${(ev: Event) =>
                            store.updateStringListRow(
                              g.key,
                              idx,
                              (ev.currentTarget as HTMLSelectElement).value,
                            )}
                        >
                          ${renderSelectOptions(g.choices, val, g.emptyPlaceholder)}
                        </select>
                        ${meta?.area_name || meta?.state_label
                          ? html`<span class="hub-slot-meta">
                              ${meta.area_name
                                ? html`<span class="chip">${meta.area_name}</span>`
                                : nothing}
                              ${meta.state_label
                                ? html`<span class=${toneChipClass(meta.state_tone)}>
                                    ${meta.state_label}
                                  </span>`
                                : nothing}
                            </span>`
                          : nothing}
                        ${g.items.length > 1
                          ? html`<button
                                type="button"
                                aria-label="Move up"
                                ?disabled=${idx === 0}
                                @click=${() => store.moveStringListRow(g.key, idx, -1)}
                                class="btn-icon"
                              >
                                ${renderSvgIcon(ICON_ARROW_UP)}
                              </button>
                              <button
                                type="button"
                                aria-label="Move down"
                                ?disabled=${idx === g.items.length - 1}
                                @click=${() => store.moveStringListRow(g.key, idx, 1)}
                                class="btn-icon"
                              >
                                ${renderSvgIcon(ICON_ARROW_DOWN)}
                              </button>`
                          : nothing}
                        ${renderTrashIconButton(g.removeAriaLabel, () =>
                          store.removeStringListRow(g.key, idx),
                        )}
                      </div>`;
                    })
                  : nothing}
              </div>`;
            })}`,
        })}

        ${renderCard({
          id: "card-calendars",
          handoffActive: Boolean(store.isHandoffTarget?.("card-calendars")),
          heading: html`<h3 class="card-title">Calendars</h3>`,
          subtitle: "Upcoming events merged into the Activity Card and agenda feed.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("calendar_entities", "", 50)}
            class="btn btn-secondary btn-compact"
          >
            Add Calendar
          </button>`,
          body: renderEntitySlotList({
            id: "calendars-list",
            items: calendars,
            choices: cat.calendars,
            emptyOptionLabel: "— Choose a calendar —",
            emptyStateText: "No calendars configured yet.",
            selectAriaLabel: "Calendar",
            removeAriaLabel: "Remove calendar",
            onChange: (idx, val) => store.updateStringListRow("calendar_entities", idx, val),
            onRemove: (idx) => store.removeStringListRow("calendar_entities", idx),
          }),
        })}

        ${renderCard({
          id: "card-system-wallpapers",
          handoffActive: Boolean(store.isHandoffTarget?.("card-system-wallpapers")),
          heading: html`<h3 class="card-title">Wallpapers</h3>`,
          subtitle: "Shared System wallpapers and presets available to every Latter display.",
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
          handoffActive: Boolean(store.isHandoffTarget?.("card-cameras-doorbell")),
          heading: html`<h3 class="card-title">Cameras &amp; Doorbell Audio</h3>`,
          subtitle:
            "Up to 10 cameras. Doorbell ring sensors wake displays automatically with listen audio and push-to-talk TTS replies.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("camera_entities", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            Add Camera
          </button>`,
          contentClass: "stack",
          body: html`<div class="settings-list">
              ${renderSelectRow({
                id: "cfg-doorbell_noise_reduction",
                label: "Doorbell Audio Filter",
                description:
                  "FFmpeg noise-reduction preset applied when listening to camera audio.",
                value: noiseRed,
                rawOptions: DOORBELL_FILTER_OPTIONS,
                onChange: (val) =>
                  store.stageSystemSetting(
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
              emptyOptionLabel: "— Choose a camera —",
              emptyStateText: "No cameras configured yet.",
              selectAriaLabel: "Camera",
              removeAriaLabel: "Remove camera",
              slotLabel: (idx) => (idx === 0 ? "Camera 1 (Primary)" : `Camera ${idx + 1}`),
              extraActions: (camId) => html`<button
                type="button"
                ?disabled=${!camId}
                @click=${() => void store.previewCamera(camId)}
                class="btn btn-text btn-compact"
              >
                Preview
              </button>`,
              onChange: (idx, val) => store.updateStringListRow("camera_entities", idx, val),
              onRemove: (idx) => store.removeStringListRow("camera_entities", idx),
            })}

            ${store.cameraPreviewUrl
              ? html`<div id="cam-preview-box" class="cam-preview">
                  <div class="input-action-row">
                    <span class="field-label">Preview: ${store.activeCameraPreviewEntity}</span>
                    <button
                      type="button"
                      @click=${() => void store.previewCamera(store.activeCameraPreviewEntity, true)}
                      class="btn btn-secondary btn-compact"
                    >
                      Refresh
                    </button>
                    <button
                      type="button"
                      @click=${() => store.closeCameraPreview()}
                      class="btn btn-text btn-compact"
                    >
                      Close
                    </button>
                  </div>
                  <img
                    id="cam-preview-img"
                    src=${store.cameraPreviewUrl}
                    alt="Camera preview"
                  />
                </div>`
              : nothing}

            ${doorbells.length
              ? html`<div id="doorbell-status" class="stack">
                  <h4 class="subsection-title">Doorbells</h4>
                  <div id="doorbell-status-list" class="kv-list">
                    ${doorbells.map((b) => {
                      let ring = "No ring sensor found";
                      const ringEnt = b.ring_entity || "";
                      if (ringEnt) {
                        const when = b.ring_at
                          ? fmtAgo((Date.now() - Date.parse(b.ring_at)) / 1000, store.hass)
                          : "";
                        const st = ringEnt.startsWith("event.")
                          ? when
                            ? `last ring ${when}`
                            : "no ring yet"
                          : b.ring_state === "on"
                            ? "ringing"
                            : b.ring_state
                              ? `idle${when ? `, changed ${when}` : ""}`
                              : "unavailable";
                        ring = `${b.ring_name || ringEnt}: ${st}`;
                      }
                      const talk = (b.talk || [])
                        .map((t) => `${t.device_title} ${TALK_STATE_TEXT[t.state] || t.state}`)
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
          handoffActive: Boolean(store.isHandoffTarget?.("card-custom-colors")),
          heading: html`<h3 class="card-title">Custom Colors</h3>`,
          subtitle: "Shared 24-swatch accent library available across all Devices.",
          headerActions: html`<button
            type="button"
            @click=${() => store.openColorWheelModal("system")}
            class="btn btn-secondary btn-compact"
          >
            Add Color
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
                    control: renderTrashIconButton(`Delete color ${p.name || h}`, () =>
                      store.deleteCustomPalette(h),
                    ),
                  });
                })
              : html`<p class="empty-state">No custom colors saved yet.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}
