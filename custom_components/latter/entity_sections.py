"""Which Studio section an ESPHome device's entity belongs to.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
`entity_category` is the entity's category value ("config", "diagnostic" or None); Home Assistant's
EntityCategory is a string enum, so it can be passed as is.
"""

from __future__ import annotations

import re

ASSIST_SATELLITE_TRANSLATION_KEYS: frozenset[str] = frozenset(
    {"pipeline", "pipeline_n", "vad_sensitivity", "wake_word", "wake_word_n"}
)


def classify_esphome_entity_section(
    entity_id: str,
    friendly_name: str,
    domain: str,
    device_class: str,
    entity_category: str | None,
    translation_key: str | None = None,
    device_object_prefixes: tuple[str, ...] = (),
) -> tuple[str, str | None]:
    """Classify an ESPHome entity into a focused section; returns (section_id, custom_section_title_or_None).

    `device_object_prefixes` are the device's own object-id prefixes (its slug and slugified name), stripped
    from the entity ID first so a device named, say, "Desk Display" doesn't put every entity in Display.
    """
    name_clean = friendly_name.strip()
    dev_cls = device_class.lower()

    # 0. Home Assistant's own Assist satellite entities (pipeline, finished speaking detection, wake words).
    if domain == "assist_satellite" or (
        domain == "select" and (translation_key or "") in ASSIST_SATELLITE_TRANSLATION_KEYS
    ):
        return "voice", None

    # 1. Explicit "Prefix: Name" Convention (Highest Priority)
    if ":" in name_clean:
        prefix_raw = name_clean.split(":", 1)[0].strip()
        prefix_low = prefix_raw.lower()
        if prefix_low in ("home", "home screen", "clock"):
            return "home", None
        if prefix_low in ("display", "ui", "screen", "theme", "appearance", "weather"):
            return "display", None
        if prefix_low in ("sleep & wake", "sleep", "wake"):
            return "sleep", None
        if prefix_low in ("voice", "wake word", "assist", "mic", "microphone"):
            return "voice", None
        if prefix_low in ("sound", "audio", "chime", "alerts"):
            return "sound", None
        if prefix_low in ("music", "media", "player"):
            return "music", None
        if prefix_low in ("ble", "area", "presence"):
            return "area", None
        if prefix_low in ("remote", "tv"):
            return "remote", None
        if prefix_low in ("battery", "power", "pmic"):
            return "battery", None
        if prefix_low in ("action", "actions"):
            return "actions", None
        if prefix_low in ("system", "network", "wifi", "diagnostics"):
            return "network", None
        if 2 <= len(prefix_raw) <= 24:
            sec_slug = "custom_" + re.sub(r"[^a-z0-9]+", "_", prefix_low).strip("_")
            return sec_slug, prefix_raw

    # 2. Semantic fallback classification (clean friendly_name + entity suffix without the device's own prefix,
    # so words in the device's name or slug don't false-match)
    ent_suffix = entity_id.split(".", 1)[-1].lower()
    for prefix in device_object_prefixes:
        if prefix and ent_suffix.startswith(prefix + "_"):
            ent_suffix = ent_suffix[len(prefix) + 1 :]
            break
    clean_low = name_clean.lower()

    if domain == "button" or dev_cls in ("restart", "identify"):
        return "actions", None

    if any(k in ent_suffix for k in ("timer_remaining", "timer_active", "alarm_ringing")):
        return "sleep", None

    if dev_cls in ("battery", "voltage", "current", "power", "energy") or any(
        k in clean_low or k in ent_suffix
        for k in ("battery", "charging", "charger", "vbus", "axp2101", "pmic", "voltage", "internal_temp", "die_temp", "imu_temp")
    ):
        return "battery", None

    # Check Network & System Diagnostics BEFORE generic words so Wi-Fi/IP/MAC/Uptime/Version/Diagnostic entities always land in "network"
    if (
        domain == "update"
        or dev_cls in ("signal_strength", "timestamp", "duration")
        or any(
            k in clean_low or k in ent_suffix
            for k in (
                "wifi",
                "wi-fi",
                "wi_fi",
                "rssi",
                "signal",
                "ip_address",
                "ip address",
                "mac_address",
                "mac address",
                "ssid",
                "bssid",
                "uptime",
                "free_heap",
                "heap",
                "psram",
                "memory",
                "cpu",
                "firmware",
                "version",
                "esphome",
                "status",
                "online",
                "connected",
                "safe_mode",
            )
        )
        or (entity_category == "diagnostic" and domain in ("sensor", "binary_sensor", "text_sensor"))
    ):
        return "network", None

    if any(k in clean_low or k in ent_suffix for k in ("clock", "weather_background", "shortcut_", "dock", "home_")):
        return "home", None

    if any(k in clean_low or k in ent_suffix for k in ("sleep", "wake_on", "pickup_to_wake", "tap_to_wake", "screensaver", "hibernate", "stay_awake", "timeout")):
        return "sleep", None

    if any(k in clean_low or k in ent_suffix for k in ("display", "screen", "brightness", "backlight", "amoled", "theme", "color_profile", "boot")):
        return "display", None

    if any(k in clean_low or k in ent_suffix for k in ("voice", "wake_word", "micro_wake", "mic", "microphone", "sensitivity", "assist")):
        return "voice", None

    if any(k in clean_low or k in ent_suffix for k in ("sound", "chime", "beep", "ringtone", "alert_volume", "volume_step", "dac", "es8311")):
        return "sound", None

    if any(k in clean_low or k in ent_suffix for k in ("ble", "beacon", "ibeacon", "presence", "area")):
        return "area", None

    if any(k in clean_low or k in ent_suffix for k in ("remote", "slot_1", "slot_2", "slot_3", "slot_4")):
        return "remote", None

    if domain == "media_player" or any(k in clean_low or k in ent_suffix for k in ("music", "album", "artist", "podcast", "queue", "playlist", "sort", "track", "speaker")):
        return "music", None

    if entity_category == "diagnostic":
        return "network", None

    return "other", None
