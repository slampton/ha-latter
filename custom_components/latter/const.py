"""Constants for the Latter universal ESPHome companion middleware integration."""

from __future__ import annotations

import re
from typing import Any, Final

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "latter"
LATTER_DATA_KEY: HassKey[dict[str, Any]] = HassKey(DOMAIN)
INTEGRATION_VERSION: Final = "2.2.1"
PLATFORMS: Final[list[Platform]] = [Platform.SENSOR, Platform.BINARY_SENSOR]

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = "latter.runtime"

# Config & Options keys
CONF_DEVICE_SLUG: Final = "device_slug"
CONF_ESPHOME_DEVICE_ID: Final = "esphome_device_id"
CONF_DEVICE_PROFILE: Final = "device_profile"
CONF_DISPLAY_SHAPE: Final = "display_shape"
CONF_DEFAULT_PAGE_SIZE: Final = "default_page_size"
CONF_WEB_THEME: Final = "web_theme"
CONF_COMPANION_BASE_URL: Final = "companion_base_url"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_ALARM_ENTITY: Final = "alarm_entity"
CONF_CAMERA_ENTITY: Final = "camera_entity"
CONF_CAMERA_ENTITIES: Final = "camera_entities"
CONF_THERMOSTAT_ENTITY: Final = "thermostat_entity"
CONF_LOCK_ENTITY: Final = "lock_entity"
CONF_GARAGE_ENTITY: Final = "garage_entity"
CONF_VACUUM_ENTITY: Final = "vacuum_entity"
CONF_DEFAULT_SPEAKER: Final = "default_speaker"
CONF_VOLUME_OVERRIDES: Final = "volume_overrides"
CONF_DEFAULT_AREA: Final = "default_area"
CONF_NATIVE_BLE_TRACKING: Final = "native_ble_tracking"
CONF_BLE_BEACON_UUID: Final = "ble_beacon_uuid"
CONF_BLE_TARGET_ADDRESS: Final = "ble_target_address"
CONF_BLE_AREA_OFFSETS: Final = "ble_area_offsets"
CONF_PRESENCE_ENTITY: Final = "presence_entity"
CONF_ASSIGNED_PERSON: Final = "assigned_person"
CONF_ASSIGNED_ROLE: Final = "assigned_role"
DEFAULT_ASSIGNED_ROLE: Final = "admin"
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
CONF_WALLPAPER_SOURCE: Final = "wallpaper_source"
CONF_WALLPAPER_FAVORITES: Final = "wallpaper_favorites"
CONF_WALLPAPER_CYCLE_MINUTES: Final = "wallpaper_cycle_minutes"
CONF_ART_SIZE: Final = "art_size"
CONF_CUSTOM_PALETTES: Final = "custom_palettes"
CONF_DEVICE_CUSTOM_COLOR: Final = "device_custom_color"
CONF_DOORBELL_ANC_MODE: Final = "doorbell_anc_mode"
CONF_SIP_ENABLED: Final = "sip_enabled"
CONF_SIP_SERVER: Final = "sip_server"
CONF_SIP_PORT: Final = "sip_port"
CONF_SIP_USERNAME: Final = "sip_username"
CONF_SIP_PASSWORD: Final = "sip_password"
CONF_SIP_EXTENSION: Final = "sip_extension"
CONF_SIP_DTMF_CODE: Final = "sip_dtmf_code"
CONF_SIP_SPEED_DIALS: Final = "sip_speed_dials"

# Defaults
DEFAULT_DOORBELL_ANC_MODE: Final = "ultra"
DEFAULT_SIP_PORT: Final = 5060
DEFAULT_SIP_DTMF_CODE: Final = "#9"
DEFAULT_DEVICE_PROFILE: Final = "mobile_display"
DEFAULT_DISPLAY_SHAPE: Final = "circle"
DEFAULT_PAGE_SIZE: Final = 3
DEFAULT_WEB_THEME: Final = "ha_auto"
DEFAULT_NATIVE_BLE_TRACKING: Final = True
DEFAULT_BLE_BEACON_UUID: Final = "4C415454-4552-434F-5245-000000000220"
DEFAULT_BLE_AUTO_SWITCH: Final = True
DEFAULT_SYNC_DEVICE_AREA: Final = True
DEFAULT_AREA_FOLLOW_DWELL_S: Final = 10
DEFAULT_AREA_HANDOFF: Final = False
DEFAULT_DOCK_APPS: Final = "music,alarm,area,remote,games,tools"
DEFAULT_WALLPAPER_CYCLE_MINUTES: Final = 0
DEFAULT_ART_SIZE: Final = 466

# Native Latter Services
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
SERVICE_DOORBELL_INTERCOM: Final = "doorbell_intercom"

# HTTP Endpoints (Artwork, Wallpaper, Camera Peephole, Doorbell Audio & Web Companion Studio)
API_ARTWORK_PROXY_PATH: Final = "/api/latter/artwork/{target_device}"
API_WALLPAPER_PROXY_PATH: Final = "/api/latter/wallpaper/{target_device}"
API_CAMERA_PROXY_PATH: Final = "/api/latter/camera/{target_device}"
API_CAMERA_AUDIO_STREAM_PATH: Final = "/api/latter/camera_audio/{target_device}"
API_DOORBELL_TALKBACK_PATH: Final = "/api/latter/doorbell_talkback/{target_device}"
API_MAP_PROXY_PATH: Final = "/api/latter/map/{target_device}"
API_COMPANION_UI_PATH: Final = "/api/latter/companion/{entry_id}"
API_COMPANION_API_PATH: Final = "/api/latter/companion/{entry_id}/api"
API_BRAND_ICON_PATH: Final = "/api/latter/brand/icon.png"
API_STUDIO_ROOT_PATH: Final = "/api/latter/studio"
API_SIDEBAR_ICON_JS_PATH: Final = "/api/latter/brand/sidebar_icon.js"
DATA_HMAC_SECRET: Final = "hmac_secret"
DATA_DISCOVERY_UNSUB: Final = "discovery_unsub"

# Timing & Recorder Idle-Guard (MCU interpolates progress locally via millis(); 15s sync cuts Wi-Fi wakeups by 87%)
POSITION_UPDATE_INTERVAL_SECONDS: Final = 15
FORECAST_REFRESH_INTERVAL_MINUTES: Final = 30
CALENDAR_REFRESH_INTERVAL_MINUTES: Final = 15


GLOBAL_STORAGE_KEY: Final = "latter.site"
BACKUPS_STORAGE_KEY: Final = "latter.backups"
DATA_GLOBAL_CONFIG: Final = "global_config"
DATA_GLOBAL_STORE: Final = "global_store"
DATA_BACKUPS_STORE: Final = "backups_store"

# Multi-Site, Device Groups, Reusable Profiles & Roaming WireGuard VPN Keys
CONF_SITE_ID: Final = "site_id"
DEFAULT_SITE_ID: Final = "primary"
CONF_SITES_REGISTRY: Final = "sites"
CONF_DEVICE_GROUP: Final = "device_group"
DEFAULT_DEVICE_GROUP: Final = "unassigned"
CONF_DEVICE_GROUPS: Final = "device_groups"
CONF_SAVED_PROFILES: Final = "saved_profiles"

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

# Forward-Compatible Extensibility Envelopes (v2.2+ -> v3.0 Site-to-Site, RBAC, Identity & Tile-Grid GUI)
CONF_CAPABILITIES_MANIFEST: Final = "capabilities_manifest"
CONF_GUI_LAYOUT: Final = "gui_layout"
CONF_FEDERATION_CONFIG: Final = "federation_config"
CONF_AREA_FUSION_CONFIG: Final = "area_fusion_config"
CONF_RBAC_POLICY: Final = "rbac_policy"
CONF_IDENTITY_PROFILES: Final = "identity_profiles"
EVENT_LATTER: Final = "latter_event"

GLOBAL_CONFIG_KEYS: Final[tuple[str, ...]] = (
    CONF_WEB_THEME,
    CONF_COMPANION_BASE_URL,
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
    CONF_DOORBELL_ANC_MODE,
    CONF_SIP_ENABLED,
    CONF_SIP_SERVER,
    CONF_SIP_PORT,
    CONF_SIP_USERNAME,
    CONF_SIP_PASSWORD,
    CONF_SIP_EXTENSION,
    CONF_SIP_DTMF_CODE,
    CONF_SIP_SPEED_DIALS,
    CONF_SITES_REGISTRY,
    CONF_DEVICE_GROUPS,
    CONF_SAVED_PROFILES,
    CONF_VPN_ENDPOINT,
    CONF_VPN_SERVER_PUBLIC_KEY,
    CONF_VPN_SUBNET,
    CONF_VPN_HA_IP,
    CONF_FEDERATION_CONFIG,
    CONF_AREA_FUSION_CONFIG,
    CONF_RBAC_POLICY,
    CONF_IDENTITY_PROFILES,
)


def normalize_device_slug(raw_slug: str) -> str:
    """Normalize an ESPHome device name or slug to lowercase underscore format."""
    norm = re.sub(r"[^a-z0-9]+", "_", raw_slug.strip().lower()).strip("_")
    return norm or "esphome_device"


def build_device_entity_id(device_slug: str, suffix: str) -> str:
    """Build a device-scoped sensor entity_id (`sensor.<device_slug>_<suffix>`)."""
    norm = normalize_device_slug(device_slug)
    return f"sensor.{norm}_{suffix}"