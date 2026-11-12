/**
 * System Shared Entities View (`shared_entities`): Whole-Home Entities, Calendars, Cameras & Doorbell Audio, Custom Colors & Wallpapers (D-022).
 */

import {
  renderCard,
  renderEntitySlotList,
  renderSelectRow,
  renderSettingsRow,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadBar,
} from "../components/wallpaper-gallery.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { CatalogChoice, SystemConfig } from "../types.js";
import { entityLabel, fmtAgo } from "../utils/format.js";

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
  const displayDevs = (data?.system_devices || []).filter((d) => d.kind !== "ble_tag");
  const noiseRed = sc?.doorbell_noise_reduction || "strong";

  const wholeHomeFields: ReadonlyArray<{
    key: keyof Pick<
      SystemConfig,
      | "weather_entity"
      | "alarm_entity"
      | "thermostat_entity"
      | "lock_entity"
      | "garage_entity"
      | "vacuum_entity"
    >;
    label: string;
    choices: readonly CatalogChoice[] | undefined;
  }> = [
    { key: "weather_entity", label: "Weather", choices: cat.weathers },
    { key: "alarm_entity", label: "Alarm Control Panel", choices: cat.alarms },
    { key: "thermostat_entity", label: "Primary Thermostat", choices: cat.climates },
    { key: "lock_entity", label: "Primary Door Lock", choices: cat.locks },
    { key: "garage_entity", label: "Garage or Gate Cover", choices: cat.garages },
    { key: "vacuum_entity", label: "Robot Vacuum", choices: cat.vacuums },
  ];

  return html`<section id="view-shared_entities">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Whole-Home Entities</h3>`,
          subtitle: "Shared entities shown across Home Hub, Weather, and Area views on every Device.",
          contentClass: "settings-list",
          body: wholeHomeFields.map((f) =>
            renderSelectRow({
              id: `cfg-${f.key}`,
              label: f.label,
              value: sc?.[f.key],
              choices: f.choices,
              emptyOptionLabel: "— None —",
              onChange: (val) => store.stageSystemSetting(f.key, val, `cfg-${f.key}`),
            }),
          ),
        })}

        ${renderCard({
          id: "card-calendars",
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
          heading: html`<h3 class="card-title">Wallpapers</h3>`,
          subtitle: "Shared System wallpapers and presets available to every Latter display.",
          contentClass: "stack",
          body: html`${renderWallpaperUploadBar(store, "system")}
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(store, "system", wallpapers, "square")}
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-cameras-doorbell",
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
              ${displayDevs.length && cameras.length
                ? renderSettingsRow({
                    label: "Test Door Speaker Reply",
                    description: "Plays a short TTS phrase on Camera 1's bound media player.",
                    control: html`<select
                        aria-label="Source Device for door speaker test"
                        .value=${store.doorbellTestSubentryId}
                        @change=${(ev: Event) => {
                          store.doorbellTestSubentryId = (
                            ev.currentTarget as HTMLSelectElement
                          ).value;
                          store.host.requestUpdate();
                        }}
                      >
                        ${displayDevs.map(
                          (d) =>
                            html`<option
                              value=${d.subentry_id}
                              ?selected=${d.subentry_id === store.doorbellTestSubentryId}
                            >
                              ${d.title}
                            </option>`,
                        )}
                      </select>
                      <button
                        type="button"
                        @click=${() => void store.testDoorbellSpeaker()}
                        class="btn btn-secondary btn-compact"
                      >
                        Test Speaker
                      </button>`,
                  })
                : nothing}
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
