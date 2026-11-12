/**
 * Device Audio & Voice View (`audio_voice`): Voice Assistant, Wake Word, Voice Follows Me, Sound & Music Assistant.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../components/controls.js";
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

  const speakerChoices = data?.catalog?.ma_speakers;

  return html`<section id="view-audio_voice">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Voice Assistant & Wake Word",
          contentClass: "settings-list",
          body: html`${voicePrimary.map((it) => renderNativeControlRow(store, it))}
            ${isRoaming
              ? html`${renderSwitchRow({
                    rowId: "row-sync-device-area",
                    id: "cfg-sync_device_area",
                    label: "Voice Follows Me",
                    description:
                      "Updates this roaming Device's Home Assistant Area when BLE presence settles in a new Area, so Area-less voice commands target where you are.",
                    checked: Boolean(cfg.sync_device_area),
                    onChange: (checked) =>
                      store.stageDeviceSetting(
                        "sync_device_area",
                        checked,
                        "cfg-sync_device_area",
                      ),
                  })}
                  ${renderSettingsRow({
                    id: "row-area-follow-dwell",
                    label: "Voice Follows Me Delay",
                    forId: "cfg-area_follow_dwell_s",
                    description:
                      "How long a BLE-detected Area stays stable before moving the Device (3 to 60 seconds).",
                    control: html`<input
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
                      <span id="dwell-value" class="chip">${fmtNumber(dwellSeconds, store.hass, 0)} s</span>`,
                  })}`
              : nothing}
            ${sensitivityVoiceItems.length
              ? html`<details class="sub-collapsible">
                  <summary>Wake Word Sensitivity (Per Model)</summary>
                  <div class="card-content settings-list">
                    ${sensitivityVoiceItems.map((it) => renderNativeControlRow(store, it))}
                  </div>
                </details>`
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Sound & Media Player",
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-default_speaker",
              label: "Default Speaker",
              description: "Primary speaker controlled from Music and Home when this Device starts up.",
              value: cfg.default_speaker,
              choices: speakerChoices,
              emptyOptionLabel: "— Automatic (Built-in or Area) —",
              onChange: (val) =>
                store.stageDeviceSetting("default_speaker", val, "cfg-default_speaker"),
            })}
            ${showMaOverrideRow
              ? renderSelectRow({
                  rowId: "row-ma-player-entity",
                  id: "cfg-ma_player_entity",
                  label: "Music Assistant Player",
                  description: maDescription,
                  descId: "desc-ma-player-entity",
                  value: savedMa,
                  choices: data?.catalog?.ma_players,
                  emptyOptionLabel: "— Automatic Match —",
                  onChange: (val) =>
                    store.stageDeviceSetting("ma_player_entity", val, "cfg-ma_player_entity"),
                })
              : nothing}
            ${renderSwitchRow({
              id: "cfg-area_handoff",
              label: "Media Follows This Device to Its New Area",
              description:
                "Transfers active Music Assistant playback when this Device moves to another Area.",
              checked: Boolean(cfg.area_handoff),
              onChange: (checked) =>
                store.stageDeviceSetting("area_handoff", checked, "cfg-area_handoff"),
            })}
            ${soundItems.map((it) => renderNativeControlRow(store, it))}
            ${primaryMusicItems.map((it) => renderNativeControlRow(store, it))}
            ${sortMusicItems.length
              ? html`<details class="sub-collapsible">
                  <summary>Library Sorting</summary>
                  <div class="card-content settings-list">
                    ${sortMusicItems.map((it) => renderNativeControlRow(store, it))}
                  </div>
                </details>`
              : nothing}`,
        })}
      </div>
    </div>
  </section>`;
}
