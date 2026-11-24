/**
 * Pure Node TypeScript unit tests for Studio i18n catalogs, UTF-8 byte truncation,
 * locale-aware formatting, Sentence-case humanizers, and telemetry row parsers.
 */

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  buildStudioEnLocaleCatalog,
  EN_STRINGS,
  formatHaEntityState,
  localizeRepairIssue,
  PREF_LABELS,
  PREF_OPTION_LABELS,
  t,
  tPrefLabel,
  tPrefOption,
} from "../../src/i18n/index.js";
import type { HomeAssistant } from "../../src/types.js";
import {
  defaultLocaleTimeFormat,
  entityLabel,
  fmtAgo,
  fmtDateTime,
  fmtDistance,
  fmtNumber,
  fmtPercent,
  formatClockHhMm,
  formatHourSlot,
  hassFirstWeekday,
  hsvToHex,
  issueMessage,
  isValidHexColor,
  rssiToPercent,
  truncateUtf8Bytes,
} from "../../src/utils/format.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const EN_LOCALE_JSON_PATH = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  "custom_components",
  "latter",
  "studio",
  "locales",
  "en.json",
);

function utf8ByteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

describe("i18n catalogs, UTF-8 byte bounds, locale formatters & telemetry parsers", () => {
  it("keeps EN_STRINGS non-empty, collision-free, and in 1:1 parity with studio/locales/en.json", () => {
    const enKeys = Object.keys(EN_STRINGS);
    assert.ok(enKeys.length > 0);
    for (const [k, v] of Object.entries(EN_STRINGS)) {
      assert.ok(k.length > 0, "Empty key in EN_STRINGS");
      assert.equal(typeof v, "string", `Non-string value in EN_STRINGS for ${k}`);
      assert.ok(v.length > 0, `Empty translation string in EN_STRINGS for ${k}`);
      assert.equal(
        k.startsWith("pref.") || k.startsWith("pref_option."),
        false,
        `EN_STRINGS key must not collide with pref/pref_option namespace: ${k}`,
      );
    }

    const expectedCatalog = buildStudioEnLocaleCatalog();
    assert.equal(
      Object.keys(expectedCatalog).length,
      enKeys.length + Object.keys(PREF_LABELS).length + Object.keys(PREF_OPTION_LABELS).length,
    );
    const diskCatalog = JSON.parse(fs.readFileSync(EN_LOCALE_JSON_PATH, "utf8")) as Record<
      string,
      string
    >;
    assert.deepEqual(diskCatalog, expectedCatalog);
  });

  it("interpolates t(), tPrefLabel(), and tPrefOption() with runtime overlays and Sentence case", () => {
    const frOverlay = {
      "action.cancel": "Annuler",
      "confirm.blast_radius_many": "Affecte {count} appareils",
      "pref.clock_face": "Cadran d'horloge",
      "pref_option.Minimal Digital": "Numérique minimal",
      "pref_option.clock_face.Minimal Digital": "Cadran numérique épuré",
    };

    assert.equal(t("action.cancel"), "Cancel");
    assert.equal(t("support.core_rev"), "Minimum firmware core");
    assert.equal(t("status.firmware_update_required"), "Firmware update required");
    assert.equal(t("dev_tools.firmware_core"), "Firmware core");
    assert.equal(t("sys_overview.screenless_one"), "1 screenless");
    assert.equal(
      t("dev_tools.profiler_desc"),
      "Streams frame, power, and link diagnostics to ESPHome logs. Automatically turns off after 24 hours.",
    );
    assert.equal(t("action.cancel", undefined, frOverlay), "Annuler");
    assert.equal(
      t("confirm.blast_radius_many", { count: 4 }, frOverlay),
      "Affecte 4 appareils",
    );
    assert.equal(
      t("presence_sys.lux_chip", { lux: "18.5", level: 64 }),
      "18.5 lx (64%)",
    );

    assert.equal(tPrefLabel("clock_face"), "Clock face");
    assert.equal(tPrefLabel("clock_face", "Fallback", frOverlay), "Cadran d'horloge");
    assert.equal(tPrefLabel("bedtime_brightness"), "Bedtime brightness");
    assert.equal(tPrefLabel("screensaver_mode"), "Screensaver mode");
    assert.equal(tPrefLabel("screensaver_photo_clock"), "Show subtle clock");
    assert.equal(tPrefLabel("weather_background"), "Live weather background on Home");
    assert.equal(tPrefLabel("weather_app_background"), "Live weather background");
    assert.equal(tPrefLabel("camera_default_view"), "Default view");
    assert.equal(tPrefLabel("camera_doorbell_popup"), "Doorbell ring popup");
    assert.equal(tPrefLabel("do_not_disturb"), "Do not disturb");
    assert.equal(tPrefLabel("music_auto_open"), "Auto-open on play");
    assert.equal(tPrefLabel("glass_style"), "Glass style");
    assert.equal(tPrefLabel("custom_unknown_pref"), "Custom unknown pref");
    assert.equal(tPrefLabel("", "Fallback label"), "Fallback label");

    assert.equal(
      tPrefOption("clock_face", "Minimal Digital", frOverlay),
      "Cadran numérique épuré",
    );
    assert.equal(tPrefOption("other_pref", "Minimal Digital", frOverlay), "Numérique minimal");
    assert.equal(tPrefOption("clock_face", "Minimal Digital"), "Minimal digital");
    assert.equal(tPrefOption("screensaver_style", "Photo Frame"), "Photo frame");
    assert.equal(tPrefOption("screensaver_mode", "Docked Only"), "Docked only");
    assert.equal(tPrefOption("camera_stream_mode", "Low Bandwidth"), "Low bandwidth");
    assert.equal(tPrefOption("camera_carousel_interval", "60s"), "60 seconds");
    assert.equal(tPrefOption("auto_brightness_mode", "Ambient Light"), "Ambient light");
    assert.equal(tPrefOption("music_auto_open", "Now Playing"), "Now playing");
    assert.equal(tPrefOption("music_auto_open", "Lyrics"), "Lyrics");
    assert.equal(tPrefOption("music_auto_open", "Off"), "Off");
    assert.equal(tPrefOption("glass_style", "Auto"), "Auto");
    assert.equal(tPrefOption("glass_style", "Clear"), "Clear");
    assert.equal(tPrefOption("glass_style", "Dark"), "Dark");
  });

  it("truncates UTF-8 strings strictly on codepoint boundaries across ASCII, Latin, CJK, and surrogates", () => {
    assert.equal(truncateUtf8Bytes("", 16), "");
    assert.equal(truncateUtf8Bytes("Harbor Studio", 0), "");
    assert.equal(truncateUtf8Bytes("Harbor Studio", -4), "");
    assert.equal(truncateUtf8Bytes("Harbor Studio", 13), "Harbor Studio");
    assert.equal(truncateUtf8Bytes("Harbor Studio", 6), "Harbor");

    // 2-byte accented Latin ("Café" = 5 bytes: C, a, f, C3 A9)
    assert.equal(truncateUtf8Bytes("Café", 4), "Caf");
    assert.equal(truncateUtf8Bytes("Café", 5), "Café");

    // 3-byte CJK ("東京タワー" = 5 * 3 = 15 bytes)
    const cjk = "東京タワー";
    for (let cap = 1; cap <= 16; cap += 1) {
      const cut = truncateUtf8Bytes(cjk, cap);
      assert.ok(utf8ByteLength(cut) <= cap);
      assert.equal(/[\uD800-\uDFFF\uFFFD]/.test(cut), false);
    }
    assert.equal(truncateUtf8Bytes(cjk, 6), "東京");
    assert.equal(truncateUtf8Bytes(cjk, 8), "東京");
    assert.equal(truncateUtf8Bytes(cjk, 9), "東京タ");

    // 4-byte astral emoji & surrogate pairs ("🎵🎧🎹" = 12 bytes)
    const emoji = "🎵🎧🎹";
    assert.equal(truncateUtf8Bytes(emoji, 3), "");
    assert.equal(truncateUtf8Bytes(emoji, 4), "🎵");
    assert.equal(truncateUtf8Bytes(emoji, 7), "🎵");
    assert.equal(truncateUtf8Bytes(emoji, 8), "🎵🎧");
    assert.equal(/[\uD800-\uDFFF]/.test(truncateUtf8Bytes("A🎵B", 4)), false);
    assert.equal(truncateUtf8Bytes("A🎵B", 4), "A");
    assert.equal(truncateUtf8Bytes("A🎵B", 5), "A🎵");
  });

  it("resolves defaultLocaleTimeFormat, formatClockHhMm, formatHourSlot, and hassFirstWeekday", () => {
    const hass24 = { locale: { time_format: "24" } } as unknown as HomeAssistant;
    const hass12 = { locale: { time_format: "am_pm" } } as unknown as HomeAssistant;
    const hassDe = { locale: { language: "de-DE", time_format: "language" } } as unknown as HomeAssistant;
    const hassUs = { locale: { language: "en-US", time_format: "language" } } as unknown as HomeAssistant;

    assert.equal(defaultLocaleTimeFormat(hass24), "24-Hour");
    assert.equal(defaultLocaleTimeFormat(hass12), "12-Hour (AM/PM)");
    assert.equal(defaultLocaleTimeFormat(hassDe), "24-Hour");
    assert.equal(defaultLocaleTimeFormat(hassUs), "12-Hour (AM/PM)");
    assert.equal(defaultLocaleTimeFormat(null), "12-Hour (AM/PM)");

    assert.equal(formatClockHhMm("00:05", false), "12:05 AM");
    assert.equal(formatClockHhMm("12:30", false), "12:30 PM");
    assert.equal(formatClockHhMm("19:45", false), "7:45 PM");
    assert.equal(formatClockHhMm("7:05", true), "07:05");
    assert.equal(formatClockHhMm("", false), "—");
    assert.equal(formatClockHhMm("99:00", true), "99:00");

    assert.equal(formatHourSlot(0, false), "12:00 AM");
    assert.equal(formatHourSlot(12, false), "12:00 PM");
    assert.equal(formatHourSlot(22, false), "10:00 PM");
    assert.equal(formatHourSlot(7, true), "07:00");
    assert.equal(formatHourSlot(undefined, true), "—");
    assert.equal(formatHourSlot("invalid", true), "—");

    assert.equal(
      hassFirstWeekday({ locale: { first_weekday: "monday" } } as unknown as HomeAssistant),
      "Monday",
    );
    assert.equal(
      hassFirstWeekday({ locale: { first_weekday: "sunday" } } as unknown as HomeAssistant),
      "Sunday",
    );
  });

  it("formats numbers, distances (metric/imperial), relative times, entity labels, and issue messages", () => {
    const metricHass = {
      locale: { language: "en-US", number_format: "comma_decimal" },
      config: { unit_system: { length: "km" }, time_zone: "UTC" },
    } as unknown as HomeAssistant;
    const imperialHass = {
      locale: { language: "en-US", number_format: "comma_decimal" },
      config: { unit_system: { length: "mi" }, time_zone: "UTC" },
    } as unknown as HomeAssistant;

    assert.equal(fmtNumber(1234.56, metricHass, 1), "1,234.6");
    assert.equal(fmtNumber(null, metricHass), "—");
    assert.equal(fmtPercent(82, metricHass), "82%");
    assert.equal(fmtDistance(3.0, metricHass), "3 m");
    assert.match(fmtDistance(3.0, imperialHass), /9\.8\s*ft/);
    assert.equal(fmtDistance(null, imperialHass), "—");
    assert.ok(fmtAgo(120, metricHass).includes("2"));
    assert.ok(fmtDateTime("2026-11-20T15:04:05Z", metricHass).length > 8);

    assert.equal(entityLabel("ble signal strength (dBm)"), "BLE signal strength (dBm)");
    assert.equal(entityLabel("wi-fi reconnect delay (ms)"), "Wi-Fi reconnect delay (ms)");
    assert.equal(entityLabel("esphome pin code"), "ESPHome PIN code");
    assert.equal(entityLabel(""), "—");

    assert.equal(rssiToPercent(-35), 100);
    assert.equal(rssiToPercent(-65), 50);
    assert.equal(rssiToPercent(-95), 0);
    assert.equal(rssiToPercent(null), 0);

    assert.equal(isValidHexColor("#38BDF8"), true);
    assert.equal(isValidHexColor("#38bdf8"), true);
    assert.equal(isValidHexColor("38bdf8"), false);
    assert.equal(isValidHexColor("#12345G"), false);
    assert.equal(hsvToHex(0, 1, 1), "#FF0000");

    const repairHass = {
      states: {
        "lock.front_entry": {
          entity_id: "lock.front_entry",
          state: "locked",
          attributes: {},
        },
      },
      localize: (key: string, ...args: unknown[]) => {
        if (key === "component.latter.issues.outdated_firmware.description") {
          const vars = (args[0] || {}) as Record<string, string>;
          return `Update firmware (${vars.detail || "outdated"})`;
        }
        return "";
      },
      formatEntityState: () => "Locked",
    } as unknown as HomeAssistant;

    assert.equal(
      issueMessage(
        { kind: "outdated_firmware", detail: "Core rev 2026112202 < 2026112401" },
        repairHass,
      ),
      "Update firmware (Core rev 2026112202 < 2026112401)",
    );
    assert.equal(
      localizeRepairIssue(null, "outdated_firmware", {
        detail: "Core rev 2026112202 < 2026112401",
      }),
      "Firmware update required (Core rev 2026112202 < 2026112401). Update the Device firmware in ESPHome.",
    );
    assert.equal(
      localizeRepairIssue(null, "outdated_firmware"),
      "Firmware core revision is below the minimum required by this Latter release. Update the Device firmware in ESPHome.",
    );
    assert.equal(
      localizeRepairIssue(null, "ble_no_proxies"),
      "BLE Area tracking is on, but no Bluetooth proxy is assigned to an Area.",
    );
    assert.equal(formatHaEntityState(repairHass, "lock.front_entry"), "Locked");
    assert.equal(formatHaEntityState(null, "lock.missing"), "—");
  });
});
