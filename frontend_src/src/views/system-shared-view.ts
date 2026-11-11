/**
 * System Shared Entities View (`shared_entities`): Whole-Home Entities, Calendars, Cameras & Doorbell Audio, Custom Colors & Wallpapers (D-022).
 */

import { renderSelectOptions, renderTrashIconButton } from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadBar,
} from "../components/wallpaper-gallery.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { entityLabel, fmtAgo } from "../utils/format.js";

const TALK_STATE_TEXT: Record<string, string> = {
  listening: "listening",
  talking: "replying",
};

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

  const weatherChoices = cat.weathers || cat.weather;
  const climateChoices = cat.climates || cat.thermostats;
  const noiseRed = sc?.doorbell_noise_reduction || "strong";

  return html`<section id="view-shared_entities">
    <div class="columns">
      <div class="column">
        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Whole-Home Entities</h3>
              <p class="card-subtitle">
                Shared entities shown across Home Hub, Weather, and Area views on every Device.
              </p>
            </div>
          </div>
          <div class="card-content settings-list">
            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-weather_entity" class="row-label">Weather</label>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-weather_entity"
                  .value=${String(sc?.weather_entity || "")}
                  @change=${(ev: Event) =>
                    store.stageSystemSetting(
                      "weather_entity",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-weather_entity",
                    )}
                >
                  ${renderSelectOptions(weatherChoices, sc?.weather_entity, "— None —")}
                </select>
              </div>
            </div>

            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-alarm_entity" class="row-label">Alarm Control Panel</label>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-alarm_entity"
                  .value=${String(sc?.alarm_entity || "")}
                  @change=${(ev: Event) =>
                    store.stageSystemSetting(
                      "alarm_entity",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-alarm_entity",
                    )}
                >
                  ${renderSelectOptions(cat.alarms, sc?.alarm_entity, "— None —")}
                </select>
              </div>
            </div>

            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-thermostat_entity" class="row-label">Primary Thermostat</label>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-thermostat_entity"
                  .value=${String(sc?.thermostat_entity || "")}
                  @change=${(ev: Event) =>
                    store.stageSystemSetting(
                      "thermostat_entity",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-thermostat_entity",
                    )}
                >
                  ${renderSelectOptions(climateChoices, sc?.thermostat_entity, "— None —")}
                </select>
              </div>
            </div>

            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-lock_entity" class="row-label">Primary Door Lock</label>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-lock_entity"
                  .value=${String(sc?.lock_entity || "")}
                  @change=${(ev: Event) =>
                    store.stageSystemSetting(
                      "lock_entity",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-lock_entity",
                    )}
                >
                  ${renderSelectOptions(cat.locks, sc?.lock_entity, "— None —")}
                </select>
              </div>
            </div>

            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-garage_entity" class="row-label">Garage or Gate Cover</label>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-garage_entity"
                  .value=${String(sc?.garage_entity || "")}
                  @change=${(ev: Event) =>
                    store.stageSystemSetting(
                      "garage_entity",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-garage_entity",
                    )}
                >
                  ${renderSelectOptions(cat.garages, sc?.garage_entity, "— None —")}
                </select>
              </div>
            </div>

            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-vacuum_entity" class="row-label">Robot Vacuum</label>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-vacuum_entity"
                  .value=${String(sc?.vacuum_entity || "")}
                  @change=${(ev: Event) =>
                    store.stageSystemSetting(
                      "vacuum_entity",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-vacuum_entity",
                    )}
                >
                  ${renderSelectOptions(cat.vacuums, sc?.vacuum_entity, "— None —")}
                </select>
              </div>
            </div>
          </div>
        </div>

        <div id="card-calendars" class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Calendars</h3>
              <p class="card-subtitle">
                Upcoming events merged into the Activity Card and agenda feed.
              </p>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => store.addStringListRow("calendar_entities", "", 50)}
                class="btn btn-secondary btn-compact"
              >
                Add Calendar
              </button>
            </div>
          </div>
          <div id="calendars-list" class="card-content stack">
            ${calendars.length
              ? calendars.map(
                  (calId, idx) => html`<div class="list-row calendar-row-item">
                    <div class="stacked-field list-row-grow">
                      <select
                        aria-label="Calendar"
                        .value=${calId}
                        @change=${(ev: Event) =>
                          store.updateStringListRow(
                            "calendar_entities",
                            idx,
                            (ev.currentTarget as HTMLSelectElement).value,
                          )}
                        class="cal-ent-sel"
                      >
                        ${renderSelectOptions(cat.calendars, calId, "— Choose a calendar —")}
                      </select>
                    </div>
                    ${renderTrashIconButton("Remove calendar", () =>
                      store.removeStringListRow("calendar_entities", idx),
                    )}
                  </div>`,
                )
              : html`<p class="empty-state">No calendars configured yet.</p>`}
          </div>
        </div>

        <div id="card-system-wallpapers" class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Wallpapers</h3>
              <p class="card-subtitle">
                Shared System wallpapers and presets available to every Latter display.
              </p>
            </div>
          </div>
          <div class="card-content stack">
            ${renderWallpaperUploadBar(store, "system")}
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(store, "system", wallpapers, "square")}
            </div>
          </div>
        </div>
      </div>

      <div class="column">
        <div id="card-cameras-doorbell" class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Cameras &amp; Doorbell Audio</h3>
              <p class="card-subtitle">
                Up to 10 cameras. Doorbell ring sensors wake displays automatically with listen audio and push-to-talk TTS replies.
              </p>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => store.addStringListRow("camera_entities", "", 10)}
                class="btn btn-secondary btn-compact"
              >
                Add Camera
              </button>
            </div>
          </div>
          <div class="card-content stack">
            <div class="settings-list">
              <div class="settings-row">
                <div class="settings-row-text">
                  <label for="cfg-doorbell_noise_reduction" class="row-label">Doorbell Audio Filter</label>
                  <p class="row-description">
                    FFmpeg noise-reduction preset applied when listening to camera audio.
                  </p>
                </div>
                <div class="settings-row-control">
                  <select
                    id="cfg-doorbell_noise_reduction"
                    .value=${noiseRed}
                    @change=${(ev: Event) =>
                      store.stageSystemSetting(
                        "doorbell_noise_reduction",
                        (ev.currentTarget as HTMLSelectElement).value,
                        "cfg-doorbell_noise_reduction",
                      )}
                  >
                    <option value="strong" ?selected=${noiseRed === "strong"}>Strong</option>
                    <option value="light" ?selected=${noiseRed === "light"}>Light</option>
                    <option value="off" ?selected=${noiseRed === "off"}>Off</option>
                  </select>
                </div>
              </div>

              ${displayDevs.length && cameras.length
                ? html`<div class="settings-row">
                    <div class="settings-row-text">
                      <span class="row-label">Test Door Speaker Reply</span>
                      <p class="row-description">
                        Plays a short TTS phrase on Camera 1's bound media player.
                      </p>
                    </div>
                    <div class="settings-row-control">
                      <select
                        aria-label="Source Device for door speaker test"
                        .value=${store.doorbellTestSubentryId}
                        @change=${(ev: Event) => {
                          store.doorbellTestSubentryId = (ev.currentTarget as HTMLSelectElement).value;
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
                      </button>
                    </div>
                  </div>`
                : nothing}
            </div>

            <div id="cameras-list" class="stack">
              ${cameras.length
                ? cameras.map(
                    (camId, idx) => html`<div class="list-row camera-row-item">
                      <div class="stacked-field list-row-grow">
                        <span class="field-label cam-slot-lbl">
                          ${idx === 0 ? "Camera 1 (Primary)" : `Camera ${idx + 1}`}
                        </span>
                        <select
                          aria-label="Camera"
                          .value=${camId}
                          @change=${(ev: Event) =>
                            store.updateStringListRow(
                              "camera_entities",
                              idx,
                              (ev.currentTarget as HTMLSelectElement).value,
                            )}
                          class="cam-ent-sel"
                        >
                          ${renderSelectOptions(cat.cameras, camId, "— Choose a camera —")}
                        </select>
                      </div>
                      <button
                        type="button"
                        ?disabled=${!camId}
                        @click=${() => void store.previewCamera(camId)}
                        class="btn btn-text btn-compact"
                      >
                        Preview
                      </button>
                      ${renderTrashIconButton("Remove camera", () =>
                        store.removeStringListRow("camera_entities", idx),
                      )}
                    </div>`,
                  )
                : html`<p class="empty-state">No cameras configured yet.</p>`}
            </div>

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
                      const ringEnt = b.ring_entity || b.ring_sensor || "";
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
                        <span>${entityLabel(b.camera_name || b.name || b.camera_entity)}</span>
                        <strong>${ring}${talk ? ` • ${talk}` : ""}</strong>
                      </div>`;
                    })}
                  </div>
                </div>`
              : nothing}
          </div>
        </div>

        <div id="card-custom-colors" class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Custom Colors</h3>
              <p class="card-subtitle">Shared 24-swatch accent library available across all Devices.</p>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => store.openColorWheelModal("system")}
                class="btn btn-secondary btn-compact"
              >
                Add Color
              </button>
            </div>
          </div>
          <div id="sys-custom-palettes-list" class="card-content settings-list">
            ${palettes.length
              ? palettes.map((p) => {
                  const h = p.hex.toUpperCase();
                  const swStyle = `--swatch-color:${h}`;
                  return html`<div class="settings-row">
                    <div class="settings-row-text">
                      <span class="row-label">
                        <span class="swatch" style=${swStyle} aria-hidden="true"></span>
                        ${p.name || h}
                      </span>
                      <p class="row-description"><code>${h}</code></p>
                    </div>
                    <div class="settings-row-control">
                      ${renderTrashIconButton(`Delete color ${p.name || h}`, () =>
                        store.deleteCustomPalette(h),
                      )}
                    </div>
                  </div>`;
                })
              : html`<p class="empty-state">No custom colors saved yet.</p>`}
          </div>
        </div>
      </div>
    </div>
  </section>`;
}
