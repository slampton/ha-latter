"""Constants and target classifiers for the Latter integration."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any, Final, Literal

from homeassistant.const import Platform

DOMAIN: Final = "latter"
INTEGRATION_VERSION: Final = "3.0.0"
STUDIO_REV: Final = 8
MIN_FIRMWARE_SDK_REV: Final = 2026111306
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = "latter.runtime"

# Config subentry types: an ESPHome Latter device, or a Studio-adopted BLE tag (phone, watch, tag)
SUBENTRY_DEVICE: Final = "device"
SUBENTRY_BLE_TAG: Final = "ble_tag"
DEVICE_SUBENTRY_TYPES: Final[tuple[str, ...]] = (SUBENTRY_DEVICE, SUBENTRY_BLE_TAG)

# Config & Options keys
CONF_DEVICE_SLUG: Final = "device_slug"
CONF_ESPHOME_DEVICE_ID: Final = "esphome_device_id"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_ALARM_ENTITY: Final = "alarm_entity"
CONF_CAMERA_ENTITY: Final = "camera_entity"
CONF_CAMERA_ENTITIES: Final = "camera_entities"
CONF_THERMOSTAT_ENTITY: Final = "thermostat_entity"
CONF_LOCK_ENTITY: Final = "lock_entity"
CONF_GARAGE_ENTITY: Final = "garage_entity"
CONF_VACUUM_ENTITY: Final = "vacuum_entity"
CONF_DEFAULT_SPEAKER: Final = "default_speaker"
# The Device's own Music Assistant player (explicit link: MA reports neither its device nor its MAC)
CONF_MA_PLAYER_ENTITY: Final = "ma_player_entity"
CONF_VOLUME_OVERRIDES: Final = "volume_overrides"
CONF_DEFAULT_AREA: Final = "default_area"
CONF_NATIVE_BLE_TRACKING: Final = "native_ble_tracking"
CONF_BLE_BEACON_UUID: Final = "ble_beacon_uuid"
CONF_BLE_TARGET_ADDRESS: Final = "ble_target_address"
CONF_BLE_AREA_OFFSETS: Final = "ble_area_offsets"
CONF_ASSIGNED_PERSON: Final = "assigned_person"
CONF_BLE_AUTO_SWITCH: Final = "ble_auto_switch"
CONF_SYNC_DEVICE_AREA: Final = "sync_device_area"
CONF_AREA_FOLLOW_DWELL_S: Final = "area_follow_dwell_s"
CONF_AREA_HANDOFF: Final = "area_handoff"
CONF_REMOTES_LIST: Final = "remotes_list"
CONF_REMOTE_GROUPS: Final = "remote_groups"
CONF_DEVICE_REMOTE_GROUP: Final = "device_remote_group"
DEFAULT_DEVICE_REMOTE_GROUP: Final = "area_auto"
CONF_CALENDAR_ENTITIES: Final = "calendar_entities"
CONF_DOCK_APPS: Final = "dock_apps"
CONF_AREA_CATEGORIES: Final = "area_categories"
CONF_HOME_CATEGORIES: Final = "home_categories"
CONF_ACTIVITY_CARD: Final = "activity_card"
CONF_ACTIVITY_SOURCES: Final = "activity_sources"
CONF_WALLPAPER_SOURCE: Final = "wallpaper_source"
CONF_WALLPAPER_FAVORITES: Final = "wallpaper_favorites"
CONF_WALLPAPER_CYCLE_MINUTES: Final = "wallpaper_cycle_minutes"
CONF_CUSTOM_PALETTES: Final = "custom_palettes"
CONF_DEVICE_CUSTOM_COLOR: Final = "device_custom_color"
CONF_DOORBELL_NOISE_REDUCTION: Final = "doorbell_noise_reduction"
CONF_SECURITY_PIN_POLICY: Final = "security_pin_policy"
CONF_SECURITY_PIN_HASH: Final = "security_pin_hash"
CONF_SECURITY_PIN: Final = "security_pin"
CONF_SYSTEM_BLE_UUID: Final = "system_ble_uuid"

# Device Preference Keys (Protocol v3 `device_prefs` domain)
CONF_POWER_PROFILE: Final = "power_profile"
CONF_WAKE_WORD_MODE: Final = "wake_word_mode"
CONF_TAP_TO_WAKE: Final = "tap_to_wake"
CONF_PICKUP_TO_WAKE: Final = "pickup_to_wake"
CONF_BATTERY_SCREEN_TIMEOUT: Final = "battery_screen_timeout"
CONF_DOCKED_IDLE_TIMEOUT: Final = "docked_idle_timeout"
CONF_BATTERY_HIBERNATE_TIMEOUT: Final = "battery_hibernate_timeout"
CONF_DOCKED_SCREENSAVER: Final = "docked_screensaver"
CONF_SCREENSAVER_STYLE: Final = "screensaver_style"
CONF_HOLD_CROWN_POWER_OFF: Final = "hold_crown_power_off"
CONF_AUTO_BRIGHTNESS_MODE: Final = "auto_brightness_mode"
CONF_MANUAL_BRIGHTNESS: Final = "manual_brightness"
CONF_DAY_BRIGHTNESS: Final = "day_brightness"
CONF_NIGHT_BRIGHTNESS: Final = "night_brightness"
CONF_DAY_START_HOUR: Final = "day_start_hour"
CONF_NIGHT_START_HOUR: Final = "night_start_hour"
CONF_COLOR_PROFILE: Final = "color_profile"
CONF_VA_VISUAL_PROFILE: Final = "va_visual_profile"
CONF_HOME_SCREEN_ENABLED: Final = "home_screen_enabled"
CONF_START_SCREEN: Final = "start_screen"
CONF_RETURN_TO_HOME_TIMEOUT: Final = "return_to_home_timeout"
CONF_CLOCK_FACE: Final = "clock_face"
CONF_TIME_FORMAT: Final = "time_format"
CONF_WEATHER_BACKGROUND: Final = "weather_background"
CONF_HOME_SUN: Final = "home_sun"
CONF_HOME_MOON: Final = "home_moon"
CONF_WAKE_GREETING: Final = "wake_greeting"
CONF_ALBUM_ART_STYLE: Final = "album_art_style"
CONF_MUSIC_OVERLAY_STYLE: Final = "music_overlay_style"
CONF_SHOW_SPEAKER_SHORTCUT: Final = "show_speaker_shortcut"
CONF_SHOW_LIBRARY_SHORTCUT: Final = "show_library_shortcut"
CONF_ALBUM_SORT_ORDER: Final = "album_sort_order"
CONF_ARTIST_ALBUM_SORT_ORDER: Final = "artist_album_sort_order"
CONF_PODCAST_SORT_ORDER: Final = "podcast_sort_order"
CONF_WW_SENS_OKAY_NABU: Final = "ww_sens_okay_nabu"
CONF_WW_SENS_HEY_LUNA: Final = "ww_sens_hey_luna"
CONF_WW_SENS_HEY_JARVIS: Final = "ww_sens_hey_jarvis"
CONF_WW_SENS_HEY_MYCROFT: Final = "ww_sens_hey_mycroft"
CONF_WW_SENS_ALEXA: Final = "ww_sens_alexa"
CONF_WAKE_SCREEN_ON_ASSIST: Final = "wake_screen_on_assist"
CONF_ALERT_VOLUME: Final = "alert_volume"
CONF_VOLUME_STEP_SIZE: Final = "volume_step_size"
CONF_GAME_SOUND_EFFECTS: Final = "game_sound_effects"
CONF_BLE_BEACON_MODE: Final = "ble_beacon_mode"
CONF_WEATHER_SIM_CONDITION: Final = "weather_sim_condition"

# Defaults
DEFAULT_SECURITY_PIN_POLICY: Final = "auto"
DEFAULT_DOORBELL_NOISE_REDUCTION: Final = "strong"
DOORBELL_NOISE_REDUCTION_LEVELS: Final[tuple[str, ...]] = ("strong", "light", "off")
# Used only until the Device reports its hardware manifest (screen shape and size live there)
DEFAULT_DISPLAY_SHAPE: Final = "circle"
DEFAULT_LIST_SLOT_COUNT: Final = 5
DEFAULT_CARD_SLOT_COUNT: Final = 3
DEFAULT_NATIVE_BLE_TRACKING: Final = True
DEFAULT_BLE_BEACON_UUID: Final = "4C415454-4552-434F-5245-000000000220"
DEFAULT_BLE_AUTO_SWITCH: Final = True
DEFAULT_SYNC_DEVICE_AREA: Final = True
DEFAULT_AREA_FOLLOW_DWELL_S: Final = 10
DEFAULT_AREA_HANDOFF: Final = False
DEFAULT_DOCK_APPS: Final = "music,alarm,area,remote,games,tools"
DEFAULT_AREA_CATEGORIES: Final = "scene,light,cover,fan,switch,climate,media"
DEFAULT_HOME_CATEGORIES: Final = "alarm,thermostat,entry,vacuum"
# Home Activity Card: protocol_v3.json defaults.activity_card / defaults.activity_sources (checked by the tests)
DEFAULT_ACTIVITY_CARD: Final = True
DEFAULT_ACTIVITY_SOURCES: Final = "calendar,music_queue,stopwatch,alarms,timers"
DEFAULT_WALLPAPER_CYCLE_MINUTES: Final = 0
DEFAULT_ART_SIZE: Final = 466  # artwork edge until the Device reports its hardware manifest
WALLPAPER_MAX_DIM: Final = 720  # native wallpaper ceiling for 720x720 high-resolution displays

# Native Latter Services
SERVICE_DEVICE_HELLO: Final = "device_hello"
SERVICE_SET_DEVICE_PREFS: Final = "set_device_prefs"
SERVICE_TIMER_ALARM_STATE: Final = "timer_alarm_state"
SERVICE_MUSIC_BROWSE: Final = "music_browse"
SERVICE_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
SERVICE_MEDIA_COMMAND: Final = "media_command"
SERVICE_MEDIA_VOLUME: Final = "media_volume"
SERVICE_AREA_BROWSE: Final = "area_browse"
SERVICE_AREA_ACTION: Final = "area_action"
SERVICE_SET_ACTIVE_AREA: Final = "set_active_area"
SERVICE_REMOTE_ACTION: Final = "remote_action"
SERVICE_CALENDAR_FETCH: Final = "calendar_fetch"
SERVICE_CALENDAR_CREATE_EVENT: Final = "calendar_create_event"
SERVICE_INTERCOM_BROADCAST: Final = "intercom_broadcast"
SERVICE_NOTIFY: Final = "notify"
SERVICE_SAVE_CUSTOM_COLOR: Final = "save_custom_color"
SERVICE_SET_DOCK_APPS: Final = "set_dock_apps"
SERVICE_DOORBELL_INTERCOM: Final = "doorbell_intercom"
SERVICE_RESET_DEVICE: Final = "reset_device"

# HTTP Endpoints (Artwork, Wallpaper, Wallpaper Upload, Camera Snapshot, Camera Audio, Map & Brand)
API_ARTWORK_PROXY_PATH: Final = "/api/latter/artwork/{target_device}"
API_WALLPAPER_PROXY_PATH: Final = "/api/latter/wallpaper/{target_device}"
API_WALLPAPER_UPLOAD_PATH: Final = "/api/latter/wallpaper/upload"
API_CAMERA_PROXY_PATH: Final = "/api/latter/camera/{target_device}"
API_CAMERA_AUDIO_STREAM_PATH: Final = "/api/latter/camera_audio/{target_device}"
API_MAP_PROXY_PATH: Final = "/api/latter/map/{target_device}"
API_BRAND_ICON_PATH: Final = "/api/latter/brand/icon.png"
DATA_HMAC_SECRET: Final = "hmac_secret"
DATA_DISCOVERY_UNSUB: Final = "discovery_unsub"

# Feed refresh intervals
FORECAST_REFRESH_INTERVAL_MINUTES: Final = 30
CALENDAR_REFRESH_INTERVAL_MINUTES: Final = 15

GLOBAL_STORAGE_KEY: Final = "latter.site"
DATA_GLOBAL_CONFIG: Final = "global_config"
DATA_GLOBAL_STORE: Final = "global_store"

# Multi-Site & Device Groups
CONF_SITE_ID: Final = "site_id"
DEFAULT_SITE_ID: Final = "primary"
CONF_DEVICE_GROUP: Final = "device_group"
DEFAULT_DEVICE_GROUP: Final = "unassigned"
CONF_DEVICE_GROUPS: Final = "device_groups"

# Area Sensor Fusion & Event Bus
CONF_AREA_FUSION_CONFIG: Final = "area_fusion_config"
EVENT_LATTER: Final = "latter_event"
TRANSFER_HOLD_WINDOW_SECONDS: Final = 6.0

GLOBAL_CONFIG_KEYS: Final[tuple[str, ...]] = (
    CONF_WEATHER_ENTITY,
    CONF_ALARM_ENTITY,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_ENTITIES,
    CONF_THERMOSTAT_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_GARAGE_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_VOLUME_OVERRIDES,
    CONF_BLE_AREA_OFFSETS,
    CONF_REMOTES_LIST,
    CONF_REMOTE_GROUPS,
    CONF_CALENDAR_ENTITIES,
    CONF_CUSTOM_PALETTES,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_DEVICE_GROUPS,
    CONF_AREA_FUSION_CONFIG,
    CONF_SYSTEM_BLE_UUID,
)

# Special values for `target_device` in `latter.notify` and `latter.intercom_broadcast`
TARGET_ALL: Final = "all"
TARGET_OCCUPIED_AREAS: Final = "occupied_areas"
PERSON_PREFIX: Final = "person."

TargetKind = Literal["none", "all", "occupied_areas", "person", "device"]


def normalize_device_slug(raw_slug: str) -> str:
    """Normalize an ESPHome device name or slug to lowercase underscore format."""
    norm = re.sub(r"[^a-z0-9]+", "_", raw_slug.strip().lower()).strip("_")
    return norm or "esphome_device"


def normalize_noise_reduction(level: str | None) -> str:
    """Return a valid doorbell noise-reduction level (`strong`, `light`, `off`), else the default."""
    val = str(level or "").strip().lower()
    return val if val in DOORBELL_NOISE_REDUCTION_LEVELS else DEFAULT_DOORBELL_NOISE_REDUCTION


def build_device_entity_id(
    device_slug: str, suffix: str, domain: str = "sensor"
) -> str:
    """Build a device-scoped entity_id (`<domain>.<device_slug>_<suffix>`)."""
    norm = normalize_device_slug(device_slug)
    return f"{domain}.{norm}_{suffix}"


def target_kind(value: Any) -> TargetKind:
    """Classify a `target_device` value."""
    text = str(value or "").strip().lower()
    if not text:
        return "none"
    if text == TARGET_ALL:
        return "all"
    if text == TARGET_OCCUPIED_AREAS:
        return "occupied_areas"
    if text.startswith(PERSON_PREFIX):
        return "person"
    return "device"


def other_latter_devices(candidates: Iterable[Any], caller_slug: str) -> list[Any]:
    """Return the Latter Devices other than the caller: objects with a `device_slug` that aren't BLE tags."""
    return [
        c
        for c in candidates
        if getattr(c, "device_slug", None)
        and not getattr(c, "is_ble_tag", False)
        and c.device_slug != caller_slug
    ]


def call_target_slugs(candidates: Iterable[Any], caller_slug: str, target: Any) -> list[str]:
    """Return the slugs `call_target` rings: every other Latter Device for `all` (or empty), else the named one."""
    others = other_latter_devices(candidates, caller_slug)
    text = str(target or "").strip()
    if text.lower() in ("", TARGET_ALL):
        return [c.device_slug for c in others]
    return [c.device_slug for c in others if c.device_slug == text]
