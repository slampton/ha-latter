/**
 * Device Audio & Voice View (`audio_voice`): Voice Assistant, Wake Word, Voice Follows Me, Sound & Music Assistant.
 */

import { renderNativeControlRow, renderSelectOptions } from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { EspHomeEntityItem } from "../types.js";
import { fmtNumber } from "../utils/format.js";

export function renderDeviceAudioView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const live = data?.live || {};

  const voiceItems = store.getSectionItems("voice");
  const wwModeItem = voiceItems.find((it) =>
    (it.name || "").toLowerCase().includes("wake word mode"),
  );
  const wwDisabled = wwModeItem ? wwModeItem.state === "Disabled" : false;
  const isWakeWordChoice = (it: EspHomeEntityItem): boolean =>
    it.key === "wake_word" || it.key === "wake_word_n";
  const voicePrimary = voiceItems.filter((it) => {
    const low = (it.name || "").toLowerCase();
    if (low.includes("cutoff") || low.includes("sensitivity")) return false;
    if (wwDisabled && isWakeWordChoice(it)) return false;
    return true;
  });
  const sensitivityVoiceItems = wwDisabled
    ? []
    : voiceItems.filter(
        (it) =>
          (it.name || "").toLowerCase().includes("cutoff") ||
          (it.name || "").toLowerCase().includes("sensitivity"),
      );

  const soundItems = store.getSectionItems("sound");
  const musicItems = store.getSectionItems("music");
  const primaryMusicItems = musicItems.filter(
    (it) => !(it.name || "").toLowerCase().includes("sort"),
  );
  const sortMusicItems = musicItems.filter((it) =>
    (it.name || "").toLowerCase().includes("sort"),
  );

  const isRoaming = caps.is_roaming_device !== false;
  const dwellSeconds = Number(cfg.area_follow_dwell_s ?? 10);

  const autoMaEntity = cfg.device_slug ? `media_player.${cfg.device_slug}` : "";
  const savedMa = String(cfg.ma_player_entity || "").trim();
  const maUnmatched = live.ma_link_matched === false;
  const hasCustomMaOverride = Boolean(savedMa && savedMa !== autoMaEntity);
  const showMaOverrideRow = maUnmatched || hasCustomMaOverride;
  const maDescription = maUnmatched
    ? `Automatic match did not find ${autoMaEntity || "this Device's player"} in Music Assistant. Choose this Device's player for library playback, queues and lyrics.`
    : `Linked manually (${autoMaEntity || "default slug"} was not used). Clear to return to automatic matching.`;

  const speakerChoices = data?.catalog?.ma_speakers || data?.catalog?.speakers;

  return html`<section id="view-audio_voice">
    <div class="columns">
      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Voice Assistant &amp; Wake Word</h3>
          </div>
          <div class="card-content settings-list">
            ${voicePrimary.map((it) => renderNativeControlRow(store, it))}

            ${isRoaming
              ? html`<div id="row-sync-device-area" class="settings-row">
                    <div class="settings-row-text">
                      <label for="cfg-sync_device_area" class="row-label">Voice Follows Me</label>
                      <p class="row-description">
                        Updates this roaming Device's Home Assistant Area when BLE presence settles in a new Area, so Area-less voice commands target where you are.
                      </p>
                    </div>
                    <div class="settings-row-control">
                      <input
                        type="checkbox"
                        id="cfg-sync_device_area"
                        role="switch"
                        .checked=${Boolean(cfg.sync_device_area)}
                        @change=${(ev: Event) =>
                          store.stageDeviceSetting(
                            "sync_device_area",
                            (ev.currentTarget as HTMLInputElement).checked,
                            "cfg-sync_device_area",
                          )}
                        class="switch"
                      />
                    </div>
                  </div>
                  <div id="row-area-follow-dwell" class="settings-row">
                    <div class="settings-row-text">
                      <label for="cfg-area_follow_dwell_s" class="row-label">Voice Follows Me Delay</label>
                      <p class="row-description">
                        How long a BLE-detected Area stays stable before moving the Device (3 to 60 seconds).
                      </p>
                    </div>
                    <div class="settings-row-control">
                      <input
                        type="range"
                        id="cfg-area_follow_dwell_s"
                        min="3"
                        max="60"
                        step="1"
                        .value=${String(dwellSeconds)}
                        @change=${(ev: Event) =>
                          store.stageDeviceSetting(
                            "area_follow_dwell_s",
                            Number((ev.currentTarget as HTMLInputElement).value) || 10,
                            "cfg-area_follow_dwell_s",
                          )}
                      />
                      <span id="dwell-value" class="chip">${fmtNumber(dwellSeconds, store.hass, 0)} s</span>
                    </div>
                  </div>`
              : nothing}

            ${sensitivityVoiceItems.length
              ? html`<details class="sub-collapsible">
                  <summary>Wake Word Sensitivity (Per Model)</summary>
                  <div class="card-content settings-list">
                    ${sensitivityVoiceItems.map((it) => renderNativeControlRow(store, it))}
                  </div>
                </details>`
              : nothing}
          </div>
        </div>
      </div>

      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Sound &amp; Media Player</h3>
          </div>
          <div class="card-content settings-list">
            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-default_speaker" class="row-label">Default Speaker</label>
                <p class="row-description">
                  Primary speaker controlled from Music and Home when this Device starts up.
                </p>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-default_speaker"
                  .value=${String(cfg.default_speaker || "")}
                  @change=${(ev: Event) =>
                    store.stageDeviceSetting(
                      "default_speaker",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-default_speaker",
                    )}
                >
                  ${renderSelectOptions(
                    speakerChoices,
                    cfg.default_speaker,
                    "— Automatic (Built-in or Area) —",
                  )}
                </select>
              </div>
            </div>

            ${showMaOverrideRow
              ? html`<div id="row-ma-player-entity" class="settings-row">
                  <div class="settings-row-text">
                    <label for="cfg-ma_player_entity" class="row-label">Music Assistant Player</label>
                    <p id="desc-ma-player-entity" class="row-description">${maDescription}</p>
                  </div>
                  <div class="settings-row-control">
                    <select
                      id="cfg-ma_player_entity"
                      .value=${savedMa}
                      @change=${(ev: Event) =>
                        store.stageDeviceSetting(
                          "ma_player_entity",
                          (ev.currentTarget as HTMLSelectElement).value,
                          "cfg-ma_player_entity",
                        )}
                    >
                      ${renderSelectOptions(
                        data?.catalog?.ma_players,
                        savedMa,
                        "— Automatic Match —",
                      )}
                    </select>
                  </div>
                </div>`
              : nothing}

            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-area_handoff" class="row-label">Media Follows This Device to Its New Area</label>
                <p class="row-description">
                  Transfers active Music Assistant playback when this Device moves to another Area.
                </p>
              </div>
              <div class="settings-row-control">
                <input
                  type="checkbox"
                  id="cfg-area_handoff"
                  role="switch"
                  .checked=${Boolean(cfg.area_handoff)}
                  @change=${(ev: Event) =>
                    store.stageDeviceSetting(
                      "area_handoff",
                      (ev.currentTarget as HTMLInputElement).checked,
                      "cfg-area_handoff",
                    )}
                  class="switch"
                />
              </div>
            </div>

            ${soundItems.map((it) => renderNativeControlRow(store, it))}
            ${primaryMusicItems.map((it) => renderNativeControlRow(store, it))}

            ${sortMusicItems.length
              ? html`<details class="sub-collapsible">
                  <summary>Library Sorting</summary>
                  <div class="card-content settings-list">
                    ${sortMusicItems.map((it) => renderNativeControlRow(store, it))}
                  </div>
                </details>`
              : nothing}
          </div>
        </div>
      </div>
    </div>
  </section>`;
}
