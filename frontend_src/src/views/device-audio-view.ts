/**
 * Device Audio View (`audio_voice`, `D-008`, `D-031`, `D-036`, `D-066`, `Q7`, `Q8`):
 * - Column 1: Voice assistant & wake word (hides `Voice Follows Me` & delay when `native_ble_tracking` is Off).
 * - Column 2: Sound & playback (keeps `area_handoff` visible in both Static and BLE modes per `D-008`,
 *   using unified `store.tPrefLabel("area_handoff")` matching System Groups).
 */

import {
  renderCard,
  renderPrefControlRow,
  renderRangeRow,
  renderSelectRow,
  renderSwitchRow,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { renderDeviceEntityRow, renderDeviceOfflineBanner } from "./device-overview-view.js";

export function renderDeviceAudioView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const live = data?.live || {};

  const wwModePref = store.entity.getPref("wake_word_mode");
  const wwDisabled = wwModePref ? String(wwModePref.value) === "Disabled" : false;

  const wakeScreenPref = store.entity.getPref("wake_screen_on_assist");

  const voiceItems = store.entity.getSectionItems("voice");
  const voicePrimary = voiceItems.filter((it) => {
    if (it.domain === "assist_satellite") return false;
    const k = it.key || it.pref_key || (it.entity_id ? it.entity_id.split(".").pop() || "" : "");
    if (k === "va_visual_profile" || k.endsWith("_visual_profile")) return false;
    if (k === "wake_word_mode" || k.endsWith("_wake_word_mode")) return false;
    if (k === "wake_screen_on_assist" || k.endsWith("_wake_screen_on_assist")) return false;
    if (k.startsWith("ww_sens_") || k.includes("_ww_sens_")) return false;
    if (
      wwDisabled &&
      (it.key === "wake_word" ||
        it.key === "wake_word_n" ||
        k.endsWith("_wake_word") ||
        k.endsWith("_wake_word_n"))
    ) {
      return false;
    }
    return true;
  });

  const sensitivityPrefs = wwDisabled
    ? []
    : store.entity.getPrefs([
        "ww_sens_okay_nabu",
        "ww_sens_hey_luna",
        "ww_sens_hey_jarvis",
        "ww_sens_hey_mycroft",
        "ww_sens_alexa",
      ]);

  const soundPrefs = store.entity.getPrefs([
    "alert_volume",
    "volume_step_size",
    "game_sound_effects",
  ]);
  const soundItems = store.entity.getSectionItems("sound").filter((it) => !it.pref_key);

  // Hide `Voice Follows Me` & dwell delay when `native_ble_tracking` is Off (Static mode, `Q8` / `E-13`)
  const showVoiceFollowsMe =
    Boolean(cfg.native_ble_tracking) && caps.is_roaming_device !== false;
  const dwellSeconds = Number(cfg.area_follow_dwell_s ?? 10);

  const espNode = data?.esphome?.device?.node_name || cfg.device_slug || "";
  const autoMaEntity = espNode ? `media_player.${espNode}` : "";
  const savedMa = String(cfg.ma_player_entity || "").trim();
  const maUnmatched = live.ma_link_matched === false;
  const hasCustomMaOverride = Boolean(savedMa && savedMa !== autoMaEntity);
  const showMaOverrideRow = maUnmatched || hasCustomMaOverride;
  const maTargetName = autoMaEntity || store.t("dev_audio.ma_player_fallback_target");
  const maDescription = maUnmatched
    ? store.t("dev_audio.ma_player_unmatched_desc", { entity: maTargetName })
    : store.t("dev_audio.ma_player_manual_desc", { entity: maTargetName });

  const speakerChoices = data?.catalog?.ma_speakers;

  return html`<section id="view-audio_voice">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">${store.t("dev_audio.card_voice_wake")}</h3>`,
          contentClass: "settings-list",
          body: html`${wwModePref ? renderPrefControlRow(store, wwModePref) : nothing}
            ${voicePrimary.map((it) => renderDeviceEntityRow(store, it))}
            ${wakeScreenPref ? renderPrefControlRow(store, wakeScreenPref) : nothing}
            ${showVoiceFollowsMe
              ? html`${renderSwitchRow({
                    rowId: "row-sync-device-area",
                    id: "cfg-sync_device_area",
                    label: store.tPrefLabel("sync_device_area"),
                    description: store.t("dev_audio.vfm_desc"),
                    checked: Boolean(cfg.sync_device_area),
                    onChange: (checked) =>
                      store.entity.stageDeviceSetting(
                        "sync_device_area",
                        checked,
                        "cfg-sync_device_area",
                      ),
                  })}
                  ${renderRangeRow({
                    rowId: "row-area-follow-dwell",
                    id: "cfg-area_follow_dwell_s",
                    label: store.t("dev_audio.vfm_delay_label"),
                    ariaLabel: store.t("dev_audio.vfm_delay_label"),
                    description: store.t("dev_audio.vfm_delay_desc"),
                    value: dwellSeconds,
                    min: 3,
                    max: 60,
                    step: 1,
                    unit: "s",
                    hass: store.hass,
                    onCommit: (val) =>
                      store.entity.stageDeviceSetting(
                        "area_follow_dwell_s",
                        val || 10,
                        "cfg-area_follow_dwell_s",
                      ),
                  })}`
              : nothing}
            ${sensitivityPrefs.length
              ? html`<details class="sub-collapsible">
                  <summary>${store.t("dev_audio.ww_sensitivity_summary")}</summary>
                  <div class="card-content settings-list">
                    ${sensitivityPrefs.map((p) => renderPrefControlRow(store, p))}
                  </div>
                </details>`
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">
            ${store.t("dev_audio.card_sound_playback")}
          </h3>`,
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-default_speaker",
              label: store.t("dev_audio.default_speaker_label"),
              description: store.t("dev_audio.default_speaker_desc"),
              value: cfg.default_speaker,
              choices: speakerChoices,
              emptyOptionLabel: store.t("dev_audio.default_speaker_auto"),
              onChange: (val) =>
                store.entity.stageDeviceSetting("default_speaker", val, "cfg-default_speaker"),
            })}
            ${showMaOverrideRow
              ? renderSelectRow({
                  rowId: "row-ma-player-entity",
                  id: "cfg-ma_player_entity",
                  label: store.t("dev_audio.ma_player_label"),
                  description: maDescription,
                  descId: "desc-ma-player-entity",
                  value: savedMa,
                  choices: data?.catalog?.ma_players,
                  emptyOptionLabel: store.t("dev_audio.ma_player_auto"),
                  onChange: (val) =>
                    store.entity.stageDeviceSetting(
                      "ma_player_entity",
                      val,
                      "cfg-ma_player_entity",
                    ),
                })
              : nothing}
            ${renderSwitchRow({
              id: "cfg-area_handoff",
              label: store.tPrefLabel("area_handoff"),
              description: store.t("dev_audio.area_handoff_desc"),
              checked: Boolean(cfg.area_handoff),
              onChange: (checked) =>
                store.entity.stageDeviceSetting("area_handoff", checked, "cfg-area_handoff"),
            })}
            ${soundPrefs.map((p) => renderPrefControlRow(store, p))}
            ${soundItems.map((it) => renderDeviceEntityRow(store, it))}`,
        })}
      </div>
    </div>
  </section>`;
}
