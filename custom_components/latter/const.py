"""Constants and target classifiers for the Latter integration (pure Python stdlib)."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
import re
from typing import Any, Final, Literal

_PROTOCOL_SCHEMA: Final[dict[str, Any]] = json.loads(
    (Path(__file__).resolve().parent / "protocol_v3.json").read_text(encoding="utf-8")
)
_PROTOCOL_DEFAULTS: Final[dict[str, Any]] = _PROTOCOL_SCHEMA["defaults"]

DOMAIN: Final = "latter"
INTEGRATION_VERSION: Final = "3.0.0"
STUDIO_REV: Final[int] = 44
if int(_PROTOCOL_SCHEMA["studio_contract"]["studio_rev"]) != STUDIO_REV:
    raise RuntimeError("const.py STUDIO_REV is out of sync with protocol_v3.json")

MIN_FIRMWARE_SDK_REV: Final = 2026112007
PLATFORMS: Final[tuple[str, ...]] = (
    "sensor",
    "binary_sensor",
    "device_tracker",
    "select",
    "number",
    "button",
    "switch",
    "light",
)

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
CONF_CAMERA_ENTITIES: Final = "camera_entities"
CONF_CAMERA_CONFIGS: Final = "camera_configs"
CONF_THERMOSTAT_ENTITIES: Final = "thermostat_entities"
CONF_LOCK_ENTITIES: Final = "lock_entities"
CONF_GARAGE_ENTITIES: Final = "garage_entities"
CONF_VACUUM_ENTITIES: Final = "vacuum_entities"
CONF_DEFAULT_SPEAKER: Final = "default_speaker"
# The Device's own Music Assistant player (explicit link: MA reports neither its device nor its MAC)
CONF_MA_PLAYER_ENTITY: Final = "ma_player_entity"
CONF_VOLUME_OVERRIDES: Final = "volume_overrides"
CONF_DEFAULT_AREA: Final = "default_area"
CONF_NATIVE_BLE_TRACKING: Final = "native_ble_tracking"
CONF_BLE_BEACON_UUID: Final = "ble_beacon_uuid"
CONF_BLE_TARGET_ADDRESS: Final = "ble_target_address"
CONF_BLE_CATEGORY: Final = "ble_category"
DEFAULT_BLE_CATEGORY: Final = "auto"
CONF_BLE_SCANNER_OFFSETS: Final = "ble_scanner_offsets"
CONF_BLE_AREA_SIGNATURES: Final = "ble_area_signatures"
CONF_BLE_REF_POWER: Final = "ble_ref_power"
CONF_BLE_ATTENUATION: Final = "ble_attenuation"
CONF_BLE_MAX_RADIUS_M: Final = "ble_max_radius_m"
CONF_BLE_MAX_VELOCITY_MPS: Final = "ble_max_velocity_mps"
CONF_BLE_AWAY_TIMEOUT_S: Final = "ble_away_timeout_s"
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
CONF_DOCK_ITEMS: Final = "dock_items"
CONF_PINNED_ITEMS: Final = "pinned_items"
CONF_AREA_CATEGORIES: Final = "area_categories"
CONF_HOME_CATEGORIES: Final = "home_categories"
CONF_CAMERA_VISIBLE_ENTITIES: Final = "camera_visible_entities"
CONF_CAMERA_CAROUSEL_ENTITIES: Final = "camera_carousel_entities"
CONF_BROADCAST_SPEAKERS: Final = "broadcast_speakers"
CONF_BROADCAST_PHRASES: Final = "broadcast_phrases"
CONF_BROADCAST_SPEAKER_ENTITIES: Final = "broadcast_speaker_entities"
DEFAULT_BROADCAST_PHRASES: Final[tuple[str, ...]] = (
    "Dinner is ready",
    "Come upstairs",
    "Leaving soon",
)
CONF_TOOLS_ITEMS: Final = "tools_items"
CONF_GAMES_ITEMS: Final = "games_items"
CONF_ACTIVITY_CARD: Final = "activity_card"
CONF_ACTIVITY_SOURCES: Final = "activity_sources"
CONF_WALLPAPER_MODE: Final = "wallpaper_mode"
CONF_WALLPAPER_SOURCE: Final = "wallpaper_source"
CONF_WALLPAPER_COLLECTION: Final = "wallpaper_collection"
CONF_WALLPAPER_FAVORITES: Final = "wallpaper_favorites"
CONF_WALLPAPER_CYCLE_MINUTES: Final = "wallpaper_cycle_minutes"
CONF_SCREENSAVER_PHOTO_MODE: Final = "screensaver_photo_mode"
CONF_SCREENSAVER_PHOTO_SOURCE: Final = "screensaver_photo_source"
CONF_SCREENSAVER_PHOTO_COLLECTION: Final = "screensaver_photo_collection"
CONF_SCREENSAVER_PHOTO_IDS: Final = "screensaver_photo_ids"
CONF_SCREENSAVER_CYCLE_MINUTES: Final = "screensaver_cycle_minutes"
CONF_SCREENSAVER_SHUFFLE: Final = "screensaver_shuffle"
CONF_CUSTOM_PALETTES: Final = "custom_palettes"
CONF_DEVICE_CUSTOM_COLOR: Final = "device_custom_color"
CONF_DOORBELL_NOISE_REDUCTION: Final = "doorbell_noise_reduction"
CONF_SECURITY_PIN_POLICY: Final = "security_pin_policy"
CONF_SECURITY_PIN_HASH: Final = "security_pin_hash"
CONF_SECURITY_PIN: Final = "security_pin"
CONF_SYSTEM_BLE_UUID: Final = "system_ble_uuid"
CONF_IGNORED_DISCOVERED_DEVICES: Final = "ignored_discovered_devices"
CONF_SYSTEM_CONFIG_REV: Final = "system_config_rev"

# Device Preference Keys (Protocol v3 `device_prefs` domain)
CONF_WAKE_WORD_MODE: Final = "wake_word_mode"
CONF_TAP_TO_WAKE: Final = "tap_to_wake"
CONF_PICKUP_TO_WAKE: Final = "pickup_to_wake"
CONF_BATTERY_SCREEN_TIMEOUT: Final = "battery_screen_timeout"
CONF_DOCKED_IDLE_TIMEOUT: Final = "docked_idle_timeout"
CONF_BATTERY_HIBERNATE_TIMEOUT: Final = "battery_hibernate_timeout"
CONF_SCREENSAVER_MODE: Final = "screensaver_mode"
CONF_SCREENSAVER_STYLE: Final = "screensaver_style"
CONF_SCREENSAVER_PHOTO_CLOCK: Final = "screensaver_photo_clock"
CONF_BEDTIME_ACTIVE: Final = "bedtime_active"
CONF_BEDTIME_DISPLAY: Final = "bedtime_display"
CONF_BEDTIME_BRIGHTNESS: Final = "bedtime_brightness"
CONF_BEDTIME_SCHEDULE: Final = "bedtime_schedule"
CONF_BEDTIME_START_HOUR: Final = "bedtime_start_hour"
CONF_BEDTIME_END_HOUR: Final = "bedtime_end_hour"
CONF_DO_NOT_DISTURB: Final = "do_not_disturb"
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
CONF_HOME_CLOCK_TAP_ACTION: Final = "home_clock_tap_action"
CONF_HOME_DATE_TAP_ACTION: Final = "home_date_tap_action"
CONF_RETURN_TO_HOME_TIMEOUT: Final = "return_to_home_timeout"
CONF_CALENDAR_LOOKAHEAD_DAYS: Final = "calendar_lookahead_days"
CONF_CALENDAR_WEEK_START: Final = "calendar_week_start"
CONF_CLOCK_FACE: Final = "clock_face"
CONF_TIME_FORMAT: Final = "time_format"
CONF_SHOW_UTC_CLOCK: Final = "show_utc_clock"
CONF_WORLD_CLOCKS: Final = "world_clocks"
CONF_LOCAL_CLOCK_LABEL: Final = "local_clock_label"
CONF_ALARMS_SUMMARY: Final = "alarms_summary"
CONF_WEATHER_BACKGROUND: Final = "weather_background"
CONF_WEATHER_APP_BACKGROUND: Final = "weather_app_background"
CONF_HOME_SUN: Final = "home_sun"
CONF_HOME_MOON: Final = "home_moon"
CONF_WAKE_GREETING: Final = "wake_greeting"
CONF_ALBUM_ART_STYLE: Final = "album_art_style"
CONF_MUSIC_OVERLAY_STYLE: Final = "music_overlay_style"
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
CONF_CAMERA_DEFAULT_VIEW: Final = "camera_default_view"
CONF_CAMERA_CAROUSEL_INTERVAL: Final = "camera_carousel_interval"
CONF_CAMERA_FRAMING: Final = "camera_framing"
CONF_CAMERA_STREAM_MODE: Final = "camera_stream_mode"
CONF_CAMERA_DOORBELL_POPUP: Final = "camera_doorbell_popup"

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
DEFAULT_BLE_ATTENUATION: Final = 2.2
DEFAULT_BLE_MAX_RADIUS_M: Final = 12.0
DEFAULT_BLE_MAX_VELOCITY_MPS: Final = 3.5
DEFAULT_BLE_AWAY_TIMEOUT_S: Final = 180
DEFAULT_BLE_AUTO_SWITCH: Final = True
DEFAULT_SYNC_DEVICE_AREA: Final = True
DEFAULT_AREA_FOLLOW_DWELL_S: Final = 10
DEFAULT_AREA_HANDOFF: Final = False
DEFAULT_DOCK_ROUTES: Final = "app:pinned,app:music,app:home_hub,app:cameras,app:area,app:remote,app:games,app:tools"
DEFAULT_AREA_CATEGORIES: Final = "scene,light,cover,fan,switch,climate,media"
DEFAULT_HOME_CATEGORIES: Final = "alarm,intercom,thermostat,entry,vacuum"
DEFAULT_TOOLS_ITEMS: Final = str(_PROTOCOL_DEFAULTS["tools_items"])
DEFAULT_GAMES_ITEMS: Final = str(_PROTOCOL_DEFAULTS["games_items"])
# Home Activity Card: protocol_v3.json defaults.activity_card / defaults.activity_sources (checked by the tests)
DEFAULT_ACTIVITY_CARD: Final = True
DEFAULT_ACTIVITY_SOURCES: Final = "calendar,music_queue,stopwatch,alarms,timers"
DEFAULT_WALLPAPER_MODE: Final = "off"
DEFAULT_WALLPAPER_COLLECTION: Final = ""
DEFAULT_WALLPAPER_CYCLE_MINUTES: Final = 0
DEFAULT_SCREENSAVER_PHOTO_MODE: Final = "collection"
DEFAULT_SCREENSAVER_PHOTO_COLLECTION: Final = "__all__"
DEFAULT_SCREENSAVER_CYCLE_MINUTES: Final = 5
DEFAULT_SCREENSAVER_SHUFFLE: Final = False
DEFAULT_ART_SIZE: Final = 466  # artwork edge until the Device reports its hardware manifest
WALLPAPER_MAX_DIM: Final = 720  # native wallpaper ceiling for 720x720 high-resolution displays
DAY_NIGHT_SKY_PRESET_ID: Final = "preset:day_night_sky"
DAY_NIGHT_SKY_NATIVE_URL: Final = "latter://day_night_sky"

# Public Home Assistant Services (`latter.<service>` — strictly matches services.yaml)
SERVICE_NOTIFY: Final = "notify"
SERVICE_INTERCOM_BROADCAST: Final = "intercom_broadcast"
SERVICE_SET_ACTIVE_AREA: Final = "set_active_area"
SERVICE_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
SERVICE_RESET_DEVICE: Final = "reset_device"
PUBLIC_SERVICES: Final[tuple[str, ...]] = (
    SERVICE_NOTIFY,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    SERVICE_RESET_DEVICE,
)

# Private Bound Firmware Outbox RPC Methods (`latter_rpc_outbox` -> LatterRpcDispatcher)
RPC_DEVICE_HELLO: Final = "device_hello"
RPC_DEVICE_TELEMETRY: Final = "device_telemetry"
RPC_DISPLAY_STATE: Final = "display_state"
RPC_MUSIC_BROWSE: Final = "music_browse"
RPC_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
RPC_MEDIA_COMMAND: Final = "media_command"
RPC_MEDIA_VOLUME: Final = "media_volume"
RPC_AREA_BROWSE: Final = "area_browse"
RPC_AREA_ACTION: Final = "area_action"
RPC_SET_ACTIVE_AREA: Final = "set_active_area"
RPC_REMOTE_ACTION: Final = "remote_action"
RPC_CALENDAR_FETCH: Final = "calendar_fetch"
RPC_CALENDAR_CREATE_EVENT: Final = "calendar_create_event"
RPC_CALENDAR_DELETE_EVENT: Final = "calendar_delete_event"
RPC_INTERCOM_BROADCAST: Final = "intercom_broadcast"
RPC_DOORBELL_INTERCOM: Final = "doorbell_intercom"
RPC_SAVE_CUSTOM_COLOR: Final = "save_custom_color"
RPC_SHORTCUT_ACTION: Final = "shortcut_action"
RPC_SET_DEVICE_PREFS: Final = "set_device_prefs"
RPC_TIMER_ALARM_STATE: Final = "timer_alarm_state"

ALL_RPC_METHODS: Final[tuple[str, ...]] = (
    RPC_DEVICE_HELLO,
    RPC_DEVICE_TELEMETRY,
    RPC_DISPLAY_STATE,
    RPC_MUSIC_BROWSE,
    RPC_SET_ACTIVE_SPEAKER,
    RPC_MEDIA_COMMAND,
    RPC_MEDIA_VOLUME,
    RPC_AREA_BROWSE,
    RPC_AREA_ACTION,
    RPC_SET_ACTIVE_AREA,
    RPC_REMOTE_ACTION,
    RPC_CALENDAR_FETCH,
    RPC_CALENDAR_CREATE_EVENT,
    RPC_CALENDAR_DELETE_EVENT,
    RPC_INTERCOM_BROADCAST,
    RPC_DOORBELL_INTERCOM,
    RPC_SAVE_CUSTOM_COLOR,
    RPC_SHORTCUT_ACTION,
    RPC_SET_DEVICE_PREFS,
    RPC_TIMER_ALARM_STATE,
)
if set(ALL_RPC_METHODS) != set(_PROTOCOL_SCHEMA["rpc_methods"].keys()):
    raise RuntimeError("const.py ALL_RPC_METHODS is out of sync with protocol_v3.json rpc_methods")

# HTTP Endpoints (Artwork, Wallpaper, Wallpaper Upload, Camera Snapshot, Camera Stream/Grid/Audio)
API_ARTWORK_PROXY_PATH: Final = "/api/latter/artwork/{target_device}"
API_WALLPAPER_PROXY_PATH: Final = "/api/latter/wallpaper/{target_device}"
API_WALLPAPER_UPLOAD_PATH: Final = "/api/latter/wallpaper/upload"
API_CAMERA_PROXY_PATH: Final = "/api/latter/camera/{target_device}"
API_CAMERA_STREAM_PATH: Final = "/api/latter/camera_stream/{target_device}"
API_CAMERA_GRID_PATH: Final = "/api/latter/camera_grid/{target_device}"
API_CAMERA_AUDIO_STREAM_PATH: Final = "/api/latter/camera_audio/{target_device}"
API_MAP_PROXY_PATH: Final = "/api/latter/map/{target_device}"

# Feed refresh intervals
FORECAST_REFRESH_INTERVAL_MINUTES: Final = 30
CALENDAR_REFRESH_INTERVAL_MINUTES: Final = 15

GLOBAL_STORAGE_KEY: Final = "latter.site"

# Multi-Site & Device Groups
CONF_SITE_ID: Final = "site_id"
DEFAULT_SITE_ID: Final = "primary"
CONF_DEVICE_GROUP: Final = "device_group"
DEFAULT_DEVICE_GROUP: Final = "custom"
CONF_DEVICE_GROUPS: Final = "device_groups"

# Area Sensor Fusion, Ambient Light & Event Bus
CONF_AREA_FUSION_CONFIG: Final = "area_fusion_config"
CONF_AREA_ILLUMINANCE_CONFIG: Final = "area_illuminance_config"
DEFAULT_AREA_DARK_LUX: Final = 0.5
DEFAULT_AREA_BRIGHT_LUX: Final = 40.0
AMBIENT_LIGHT_DEADBAND_PCT: Final = 4
EVENT_LATTER: Final = "latter_event"
TRANSFER_HOLD_WINDOW_SECONDS: Final = 6.0

GLOBAL_CONFIG_KEYS: Final[tuple[str, ...]] = (
    CONF_WEATHER_ENTITY,
    CONF_ALARM_ENTITY,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_CONFIGS,
    CONF_THERMOSTAT_ENTITIES,
    CONF_LOCK_ENTITIES,
    CONF_GARAGE_ENTITIES,
    CONF_VACUUM_ENTITIES,
    CONF_BROADCAST_SPEAKERS,
    CONF_BROADCAST_PHRASES,
    CONF_VOLUME_OVERRIDES,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_ATTENUATION,
    CONF_BLE_MAX_RADIUS_M,
    CONF_BLE_MAX_VELOCITY_MPS,
    CONF_BLE_AWAY_TIMEOUT_S,
    CONF_REMOTES_LIST,
    CONF_REMOTE_GROUPS,
    CONF_CALENDAR_ENTITIES,
    CONF_CUSTOM_PALETTES,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_DEVICE_GROUPS,
    CONF_AREA_FUSION_CONFIG,
    CONF_AREA_ILLUMINANCE_CONFIG,
    CONF_SYSTEM_BLE_UUID,
    CONF_IGNORED_DISCOVERED_DEVICES,
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


def target_kind(value: object) -> TargetKind:
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


def other_latter_devices[T](candidates: Iterable[T], caller_slug: str) -> list[T]:
    """Return the Latter Devices other than the caller: objects with a `device_slug` that aren't BLE tags."""
    return [
        c
        for c in candidates
        if getattr(c, "device_slug", None)
        and not getattr(c, "is_ble_tag", False)
        and getattr(c, "device_slug", None) != caller_slug
    ]
