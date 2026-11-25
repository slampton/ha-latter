"""Constants and target classifiers for the Latter integration (pure Python stdlib)."""

from __future__ import annotations

import re
from typing import Final, Literal
import uuid

from .protocol_specs import (
    DEFAULT_GAMES_ITEMS as DEFAULT_GAMES_ITEMS,
    DEFAULT_TOOLS_ITEMS as DEFAULT_TOOLS_ITEMS,
    PROTOCOL_V3_DATA,
    STUDIO_CONTRACT,
)

DOMAIN: Final = "latter"
INTEGRATION_VERSION: Final = "3.0.0"
STUDIO_REV: Final[int] = 52
if int(STUDIO_CONTRACT["studio_rev"]) != STUDIO_REV:
    raise RuntimeError("const.py STUDIO_REV is out of sync with studio_contract.json")

MIN_FIRMWARE_CORE_REV: Final = 2026112404
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
CONF_PINNED_PAGE_TITLES: Final = "pinned_page_titles"
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

# Active Device Preference Keys imported directly by integration modules
# (full 65-key catalog lives canonically in `protocol_specs.DEVICE_PREF_KEYS`)
CONF_DO_NOT_DISTURB: Final = "do_not_disturb"
CONF_WORLD_CLOCKS: Final = "world_clocks"
CONF_MUSIC_AUTO_OPEN: Final = "music_auto_open"
CONF_GLASS_STYLE: Final = "glass_style"

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
WALLPAPER_MAX_DIM: Final = 1280  # native wallpaper ceiling for 1280x800 / 1024x600 high-resolution displays
DAY_NIGHT_SKY_PRESET_ID: Final = "preset:day_night_sky"
DAY_NIGHT_SKY_NATIVE_URL: Final = "latter://day_night_sky"

# Public Home Assistant Services (`latter.<service>` — strictly matches services.yaml)
SERVICE_NOTIFY: Final = "notify"
SERVICE_INTERCOM_BROADCAST: Final = "intercom_broadcast"
SERVICE_SET_ACTIVE_AREA: Final = "set_active_area"
SERVICE_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
SERVICE_RESET_DEVICE: Final = "reset_device"
SERVICE_NAVIGATE: Final = "navigate"
PUBLIC_SERVICES: Final[tuple[str, ...]] = (
    SERVICE_NOTIFY,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    SERVICE_RESET_DEVICE,
    SERVICE_NAVIGATE,
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
if set(ALL_RPC_METHODS) != set(PROTOCOL_V3_DATA["rpc_methods"].keys()):
    raise RuntimeError("const.py ALL_RPC_METHODS is out of sync with protocol_v3.json rpc_methods")

# HTTP Endpoints (Artwork, Wallpaper, Wallpaper Upload, Camera Snapshot, Camera Stream/Grid/Audio)
API_ARTWORK_PROXY_PATH: Final = "/api/latter/artwork/{target_device}"
API_WALLPAPER_PROXY_PATH: Final = "/api/latter/wallpaper/{target_device}"
API_WALLPAPER_UPLOAD_PATH: Final = "/api/latter/wallpaper/upload"
API_CAMERA_PROXY_PATH: Final = "/api/latter/camera/{target_device}"
API_CAMERA_STREAM_PATH: Final = "/api/latter/camera_stream/{target_device}"
API_CAMERA_GRID_PATH: Final = "/api/latter/camera_grid/{target_device}"
API_CAMERA_AUDIO_STREAM_PATH: Final = "/api/latter/camera_audio/{target_device}"

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

# Special values for `target_device` in `latter.notify`, `latter.intercom_broadcast`, and `latter.navigate`
TARGET_ALL: Final = "all"
TARGET_OCCUPIED_AREAS: Final = "occupied_areas"
PERSON_PREFIX: Final = "person."

TargetKind = Literal["none", "all", "occupied_areas", "person", "device"]


def derive_device_beacon_uuid(system_uuid: str, device_seed: str) -> str:
    """Derive a deterministic per-Device UUIDv5 from the System BLE UUID and a Device seed."""
    clean_sys = str(system_uuid or "").strip()
    clean_seed = str(device_seed or "").strip().lower()
    if not clean_sys:
        return DEFAULT_BLE_BEACON_UUID
    if clean_sys.upper() == DEFAULT_BLE_BEACON_UUID or not clean_seed:
        return clean_sys.upper()
    try:
        namespace = uuid.UUID(clean_sys)
    except ValueError:
        return clean_sys.upper()
    if str(namespace).upper() == DEFAULT_BLE_BEACON_UUID:
        return DEFAULT_BLE_BEACON_UUID
    return str(uuid.uuid5(namespace, f"latter-device:{clean_seed}")).upper()


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
