/**
 * Group Baseline Drawer — Display Section (`views/groups/baseline-display-section.ts`, `D-072`):
 * - Wallpaper & Photo Frame Screensaver pool selectors, rotation, shuffle, clock overlay
 * - Color profile, custom accent hex, & voice visual profile
 */

import { renderSettingsRow, renderSwitchRow } from "../../components/controls.js";
import {
  VIRTUAL_COLLECTION_ALL,
  VIRTUAL_COLLECTION_DEFAULTS,
  VIRTUAL_COLLECTION_UPLOADS,
} from "../../constants.js";
import { WALLPAPER_ROTATION_OPTIONS } from "../../i18n/index.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import { isPhotoDynamic } from "../../state/photo-ops.js";
import type { StudioStore } from "../../state/store.js";
import type { DeviceCapabilities, DeviceGroup } from "../../types.js";
import { isValidHexColor } from "../../utils/format.js";

export interface BaselineDisplayHelpers {
  readonly caps: DeviceCapabilities;
  renderSpecSelect(key: string, currentVal: unknown): TemplateResult | typeof nothing;
  renderSpecSwitch(
    key: string,
    currentVal: unknown,
    extraGate?: boolean,
  ): TemplateResult | typeof nothing;
  renderLabeledSelect(
    key: string,
    currentVal: unknown,
    options: ReadonlyArray<{ value: string; label: string }>,
    defaultVal: string,
    asNumber?: boolean,
  ): TemplateResult;
}

function encodePoolSelectValue(modeVal: unknown, sourceVal: unknown, colVal: unknown): string {
  const mode = String(modeVal || "");
  const src = String(sourceVal || "");
  const col = String(colVal || "");
  if (mode === "collection" && col) return `collection:${col}`;
  if (mode === "single" && src) return `single:${src}`;
  if (!mode && src) return `single:${src}`;
  return "off";
}

export function renderBaselineDisplaySection(
  store: StudioStore,
  group: DeviceGroup,
  h: BaselineDisplayHelpers,
): TemplateResult | typeof nothing {
  if (!group.include_display || h.caps.has_display === false) {
    return nothing;
  }

  const gid = group.id;
  const cfg = group.device_config || {};
  const colorProfile = String(cfg.color_profile || "Steel Blue");
  const rawCustomHex =
    typeof cfg.device_custom_color === "string" ? cfg.device_custom_color : null;
  const customHex = isValidHexColor(rawCustomHex)
    ? String(rawCustomHex).toUpperCase()
    : "#3898FF";
  const groupSsStyle = String(cfg.screensaver_style ?? "Ambient Clock");

  const sysWallpapers = store.state?.system_wallpapers || [];
  const photoCollections = store.state?.photo_collections || [];

  const buildCompactPoolOptions = (
    excludeDynamic: boolean,
  ): Array<{ value: string; label: string }> => {
    const photos = excludeDynamic
      ? sysWallpapers.filter((wp) => !isPhotoDynamic(wp))
      : sysWallpapers;
    return [
      { value: "off", label: store.t("groups.pool_off") },
      { value: `collection:${VIRTUAL_COLLECTION_ALL}`, label: store.t("groups.pool_all") },
      {
        value: `collection:${VIRTUAL_COLLECTION_DEFAULTS}`,
        label: store.t("groups.pool_defaults"),
      },
      {
        value: `collection:${VIRTUAL_COLLECTION_UPLOADS}`,
        label: store.t("groups.pool_uploads"),
      },
      ...photoCollections.map((c) => ({
        value: `collection:${c.id}`,
        label: store.t("groups.pool_collection_prefix", { name: c.name }),
      })),
      ...photos.map((wp) => ({
        value: `single:${wp.id}`,
        label: store.t("groups.pool_photo_prefix", { name: wp.name || wp.id }),
      })),
    ];
  };

  const wpPoolOptions = buildCompactPoolOptions(false);
  const wpPoolCurrent = encodePoolSelectValue(
    cfg.wallpaper_mode,
    cfg.wallpaper_source,
    cfg.wallpaper_collection,
  );
  const ssPoolOptions = buildCompactPoolOptions(true);
  const ssPoolCurrent = encodePoolSelectValue(
    cfg.screensaver_photo_mode,
    cfg.screensaver_photo_source,
    cfg.screensaver_photo_collection,
  );
  const rotationOptions: Array<{ value: string; label: string }> = WALLPAPER_ROTATION_OPTIONS.map(
    (o) => ({ value: String(o.value), label: o.label }),
  );

  return html`<details class="sub-collapsible" open>
    <summary>${store.t("groups.section_display")}</summary>
    <div class="card-content settings-list">
      ${renderSettingsRow({
        label: store.t("groups.wallpaper_pool_label"),
        control: html`<select
          aria-label=${store.t("groups.for_group_aria", {
            label: store.t("groups.wallpaper_pool_label"),
            group: group.name,
          })}
          .value=${wpPoolCurrent}
          @change=${(ev: Event) => {
            const raw = (ev.currentTarget as HTMLSelectElement).value;
            if (raw.startsWith("collection:")) {
              void store.groups.updateGroupBaseline(gid, {
                wallpaper_mode: "collection",
                wallpaper_collection: raw.slice(11),
                wallpaper_source: "",
              });
            } else if (raw.startsWith("single:")) {
              void store.groups.updateGroupBaseline(gid, {
                wallpaper_mode: "single",
                wallpaper_source: raw.slice(7),
                wallpaper_collection: "",
              });
            } else {
              void store.groups.updateGroupBaseline(gid, {
                wallpaper_mode: "off",
                wallpaper_source: "",
                wallpaper_collection: "",
              });
            }
          }}
        >
          ${wpPoolOptions.map(
            (opt) => html`<option value=${opt.value} ?selected=${opt.value === wpPoolCurrent}>
              ${opt.label}
            </option>`,
          )}
        </select>`,
      })}
      ${h.renderLabeledSelect(
        "wallpaper_cycle_minutes",
        cfg.wallpaper_cycle_minutes,
        rotationOptions,
        "0",
        true,
      )}
      ${h.renderSpecSelect("screensaver_style", cfg.screensaver_style)}
      ${groupSsStyle === "Photo Frame"
        ? html`${renderSettingsRow({
              label: store.t("groups.screensaver_pool_label"),
              control: html`<select
                aria-label=${store.t("groups.for_group_aria", {
                  label: store.t("groups.screensaver_pool_label"),
                  group: group.name,
                })}
                .value=${ssPoolCurrent}
                @change=${(ev: Event) => {
                  const raw = (ev.currentTarget as HTMLSelectElement).value;
                  if (raw.startsWith("collection:")) {
                    void store.groups.updateGroupBaseline(gid, {
                      screensaver_photo_mode: "collection",
                      screensaver_photo_collection: raw.slice(11),
                      screensaver_photo_source: "",
                    });
                  } else if (raw.startsWith("single:")) {
                    void store.groups.updateGroupBaseline(gid, {
                      screensaver_photo_mode: "single",
                      screensaver_photo_source: raw.slice(7),
                      screensaver_photo_collection: "",
                    });
                  } else {
                    void store.groups.updateGroupBaseline(gid, {
                      screensaver_photo_mode: "off",
                      screensaver_photo_source: "",
                      screensaver_photo_collection: "",
                    });
                  }
                }}
              >
                ${ssPoolOptions.map(
                  (opt) => html`<option
                    value=${opt.value}
                    ?selected=${opt.value === ssPoolCurrent}
                  >
                    ${opt.label}
                  </option>`,
                )}
              </select>`,
            })}
            ${h.renderLabeledSelect(
              "screensaver_cycle_minutes",
              cfg.screensaver_cycle_minutes,
              rotationOptions,
              "15",
              true,
            )}
            ${renderSwitchRow({
              label: store.tPrefLabel("screensaver_shuffle"),
              ariaLabel: store.t("groups.for_group_aria", {
                label: store.tPrefLabel("screensaver_shuffle"),
                group: group.name,
              }),
              checked: Boolean(cfg.screensaver_shuffle),
              onChange: (checked) =>
                void store.groups.updateGroupBaseline(gid, {
                  screensaver_shuffle: checked,
                }),
            })}
            ${h.renderSpecSwitch("screensaver_photo_clock", cfg.screensaver_photo_clock)}`
        : nothing}
      ${h.renderSpecSelect("color_profile", cfg.color_profile)}
      ${colorProfile === "Custom"
        ? renderSettingsRow({
            label: store.tPrefLabel("device_custom_color"),
            control: html`<input
                type="color"
                aria-label=${store.t("groups.for_group_aria", {
                  label: store.tPrefLabel("device_custom_color"),
                  group: group.name,
                })}
                .value=${customHex}
                @change=${(ev: Event) => {
                  const raw = (ev.currentTarget as HTMLInputElement).value.toUpperCase();
                  if (isValidHexColor(raw)) {
                    void store.groups.updateGroupBaseline(gid, {
                      device_custom_color: raw,
                    });
                  }
                }}
              />
              <span class="chip">${customHex}</span>`,
          })
        : nothing}
      ${h.renderSpecSelect("va_visual_profile", cfg.va_visual_profile)}
    </div>
  </details>`;
}
