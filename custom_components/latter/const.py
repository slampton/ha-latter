"""Constants for the Latter universal ESPHome companion middleware integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "latter"
INTEGRATION_VERSION: Final = "1.8.2"
PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = "latter.runtime"

# Config & Options keys
CONF_DEVICE_SLUG: Final = "device_slug"
CONF_DEVICE_PROFILE: Final = "device_profile"
CONF_DISPLAY_SHAPE: Final = "display_shape"
CONF_DEFAULT_PAGE_SIZE: Final = "default_page_size"
CONF_WEB_THEME: Final = "web_theme"
CONF_COMPANION_BASE_URL: Final = "companion_base_url"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_ALARM_ENTITY: Final = "alarm_entity"
CONF_CAMERA_ENTITY: Final = "camera_entity"
CONF_DEFAULT_SPEAKER: Final = "default_speaker"
CONF_VOL_SPEAKER_1: Final = "vol_speaker_1"
CONF_VOL_TARGET_1: Final = "vol_target_1"
CONF_VOL_SPEAKER_2: Final = "vol_speaker_2"
CONF_VOL_TARGET_2: Final = "vol_target_2"
CONF_DEFAULT_AREA: Final = "default_area"
CONF_NATIVE_BLE_TRACKING: Final = "native_ble_tracking"
CONF_BLE_BEACON_UUID: Final = "ble_beacon_uuid"
CONF_BLE_ROOM_OFFSETS: Final = "ble_room_offsets"
CONF_PRESENCE_ENTITY: Final = "presence_entity"
CONF_BLE_AUTO_SWITCH: Final = "ble_auto_switch"
CONF_SYNC_DEVICE_AREA: Final = "sync_device_area"
CONF_AREA_HANDOFF: Final = "area_handoff"
CONF_REMOTE_1: Final = "remote_1"
CONF_REMOTE_2: Final = "remote_2"
CONF_REMOTE_3: Final = "remote_3"
CONF_REMOTE_4: Final = "remote_4"
CONF_CALENDAR_ENTITIES: Final = "calendar_entities"
CONF_CUSTOM_ENTITIES: Final = "custom_entities"
CONF_CUSTOM_BINDINGS: Final = "custom_bindings"
CONF_DOCK_APPS: Final = "dock_apps"
CONF_WALLPAPER_SOURCE: Final = "wallpaper_source"
CONF_WALLPAPER_FAVORITES: Final = "wallpaper_favorites"
CONF_WALLPAPER_CYCLE_MINUTES: Final = "wallpaper_cycle_minutes"
CONF_ART_SIZE: Final = "art_size"

# Defaults
DEFAULT_DEVICE_PROFILE: Final = "mobile_display"
DEFAULT_DISPLAY_SHAPE: Final = "circle"
DEFAULT_PAGE_SIZE: Final = 3
DEFAULT_WEB_THEME: Final = "dark"
DEFAULT_NATIVE_BLE_TRACKING: Final = True
DEFAULT_BLE_BEACON_UUID: Final = "504F434B-4554-4153-5354-000000000210"
DEFAULT_BLE_AUTO_SWITCH: Final = True
DEFAULT_SYNC_DEVICE_AREA: Final = True
DEFAULT_AREA_HANDOFF: Final = False
DEFAULT_DOCK_APPS: Final = "music,room,remote,games,tools"
DEFAULT_WALLPAPER_CYCLE_MINUTES: Final = 0
DEFAULT_ART_SIZE: Final = 466

# Native Latter Services
SERVICE_MUSIC_BROWSE: Final = "music_browse"
SERVICE_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
SERVICE_MEDIA_COMMAND: Final = "media_command"
SERVICE_MEDIA_VOLUME: Final = "media_volume"
SERVICE_ROOM_BROWSE: Final = "room_browse"
SERVICE_ROOM_ACTION: Final = "room_action"
SERVICE_SET_ACTIVE_AREA: Final = "set_active_area"
SERVICE_REMOTE_ACTION: Final = "remote_action"
SERVICE_TRIGGER_BINDING: Final = "trigger_binding"
SERVICE_CALENDAR_FETCH: Final = "calendar_fetch"
SERVICE_CALENDAR_CREATE_EVENT: Final = "calendar_create_event"
SERVICE_INTERCOM_BROADCAST: Final = "intercom_broadcast"
SERVICE_NOTIFY_DEVICE: Final = "notify_device"

# HTTP Endpoints (Artwork, Wallpaper, Camera Peephole & Web Companion Studio)
API_ARTWORK_PROXY_PATH: Final = "/api/latter/artwork/{target_device}"
API_WALLPAPER_PROXY_PATH: Final = "/api/latter/wallpaper/{target_device}"
API_CAMERA_PROXY_PATH: Final = "/api/latter/camera/{target_device}"
API_COMPANION_UI_PATH: Final = "/api/latter/companion/{entry_id}"
API_COMPANION_API_PATH: Final = "/api/latter/companion/{entry_id}/api"
API_BRAND_ICON_PATH: Final = "/api/latter/brand/icon.png"
DATA_HMAC_SECRET: Final = "hmac_secret"
DATA_DISCOVERY_UNSUB: Final = "discovery_unsub"

# Timing & Recorder Idle-Guard
POSITION_UPDATE_INTERVAL_SECONDS: Final = 2
FORECAST_REFRESH_INTERVAL_MINUTES: Final = 30
CALENDAR_REFRESH_INTERVAL_MINUTES: Final = 15


GLOBAL_STORAGE_KEY: Final = "latter.household"
DATA_GLOBAL_CONFIG: Final = "global_config"
DATA_GLOBAL_STORE: Final = "global_store"

# Multi-Site & Roaming WireGuard VPN Keys (Phase 1 & Phase 2 Foundation)
CONF_SITE_ID: Final = "site_id"
DEFAULT_SITE_ID: Final = "primary"
CONF_SITES_REGISTRY: Final = "sites"

CONF_VPN_ENDPOINT: Final = "vpn_endpoint"
CONF_VPN_SERVER_PUBLIC_KEY: Final = "vpn_server_public_key"
CONF_VPN_SUBNET: Final = "vpn_subnet"
CONF_VPN_HA_IP: Final = "vpn_ha_ip"

CONF_VPN_ENABLED: Final = "vpn_enabled"
CONF_VPN_CLIENT_IP: Final = "vpn_client_ip"
CONF_VPN_PRIVATE_KEY: Final = "vpn_private_key"
CONF_VPN_PUBLIC_KEY: Final = "vpn_public_key"
CONF_VPN_PRESHARED_KEY: Final = "vpn_preshared_key"
CONF_VPN_HOTSPOT_SSID: Final = "vpn_hotspot_ssid"

GLOBAL_CONFIG_KEYS: Final[tuple[str, ...]] = (
    CONF_WEB_THEME,
    CONF_COMPANION_BASE_URL,
    CONF_WEATHER_ENTITY,
    CONF_ALARM_ENTITY,
    CONF_CAMERA_ENTITY,
    CONF_VOL_SPEAKER_1,
    CONF_VOL_TARGET_1,
    CONF_VOL_SPEAKER_2,
    CONF_VOL_TARGET_2,
    CONF_BLE_ROOM_OFFSETS,
    CONF_REMOTE_1,
    CONF_REMOTE_2,
    CONF_REMOTE_3,
    CONF_REMOTE_4,
    CONF_CALENDAR_ENTITIES,
    CONF_CUSTOM_ENTITIES,
    CONF_CUSTOM_BINDINGS,
    CONF_SITES_REGISTRY,
    CONF_VPN_ENDPOINT,
    CONF_VPN_SERVER_PUBLIC_KEY,
    CONF_VPN_SUBNET,
    CONF_VPN_HA_IP,
)


def normalize_device_slug(raw_slug: str) -> str:
    """Normalize an ESPHome device name or slug to lowercase underscore format."""
    norm = raw_slug.strip().lower().replace("-", "_").replace(" ", "_")
    return norm or "esphome_device"


def build_device_entity_id(device_slug: str, suffix: str) -> str:
    """Build a device-scoped sensor entity_id (`sensor.<device_slug>_<suffix>`)."""
    norm = normalize_device_slug(device_slug)
    return f"sensor.{norm}_{suffix}"