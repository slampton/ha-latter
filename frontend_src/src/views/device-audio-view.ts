/**
 * Device Audio & Voice View (`audio_voice`, D-031 / D-036):
 * Voice Assistant, Wake Word, Voice Follows Me, Sound & Music Assistant.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderPrefControlRow,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { fmtNumber } from "../utils/format.js";

export function renderDeviceAudioView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const live = data?.live || {};

  const wwModePref = store.getPref("wake_word_mode");
  const wwDisabled = wwModePref ? String(wwModePref.value) === "Disabled" : false;

  const wakeScreenPref = store.getPref("wake_screen_on_assist");

  const voiceItems = store.getSectionItems("voice");
  const voicePrimary = voiceItems.filter((it) => {
    if (it.domain === "assist_satellite") return false;
    const k = it.key || it.pref_key || (it.entity_id ? it.entity_id.split(".").pop() || "" : "");
    if (k === "va_visual_profile" || k.endsWith("_visual_profile")) return false;
    if (k === "wake_word_mode" || k.endsWith("_wake_word_mode")) return false;
    if (k === "wake_screen_on_assist" || k.endsWith("_wake_screen_on_assist")) return false;
    if (k.startsWith("ww_sens_") || k.includes("_ww_sens_")) return false;
    if (
      wwDisabled &&
      (it.key === "wake_word" || it.key === "wake_word_n" || k.endsWith("_wake_word") || k.endsWith("_wake_word_n"))
    )
      return false;
    return true;
  });

  const sensitivityPrefs = wwDisabled
    ? []
    : store.getPrefs([
        "ww_sens_okay_nabu",
        "ww_sens_hey_luna",
        "ww_sens_hey_jarvis",
        "ww_sens_hey_mycroft",
        "ww_sens_alexa",
      ]);

  const soundPrefs = store.getPrefs([
    "alert_volume",
    "volume_step_size",
    "game_sound_effects",
  ]);
  const soundItems = store.getSectionItems("sound").filter((it) => !it.pref_key);

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
          heading: html`<h3 class="card-title">Voice Assistant &amp; Wake Word</h3>`,
          contentClass: "settings-list",
          body: html`${wwModePref ? renderPrefControlRow(store, wwModePref) : nothing}
            ${voicePrimary.map((it) => renderNativeControlRow(store, it))}
            ${wakeScreenPref ? renderPrefControlRow(store, wakeScreenPref) : nothing}
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
            ${sensitivityPrefs.length
              ? html`<details class="sub-collapsible">
                  <summary>Wake Word Sensitivity (Per Model)</summary>
                  <div class="card-content settings-list">
                    ${sensitivityPrefs.map((p) => renderPrefControlRow(store, p))}
                  </div>
                </details>`
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Sound &amp; Playback</h3>`,
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
            ${soundPrefs.map((p) => renderPrefControlRow(store, p))}
            ${soundItems.map((it) => renderNativeControlRow(store, it))}`,
        })}
      </div>
    </div>
  </section>`;
}
