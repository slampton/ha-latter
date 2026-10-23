"""Constants for the Latter integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "latter"
PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]

# Config & Options keys
CONF_DEVICE_SLUG: Final = "device_slug"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_ALARM_ENTITY: Final = "alarm_entity"
CONF_DEFAULT_SPEAKER: Final = "default_speaker"
CONF_VOL_SPEAKER_1: Final = "vol_speaker_1"
CONF_VOL_TARGET_1: Final = "vol_target_1"
CONF_VOL_SPEAKER_2: Final = "vol_speaker_2"
CONF_VOL_TARGET_2: Final = "vol_target_2"
CONF_DEFAULT_AREA: Final = "default_area"
CONF_NATIVE_BLE_TRACKING: Final = "native_ble_tracking"
CONF_BLE_BEACON_UUID: Final = "ble_beacon_uuid"
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
CONF_ART_SIZE: Final = "art_size"

# Defaults
DEFAULT_DEVICE_SLUG: Final = "pocket_assistant"
DEFAULT_LOCAL_SPEAKER: Final = "media_player.pocket_assistant"
DEFAULT_NATIVE_BLE_TRACKING: Final = True
DEFAULT_BLE_BEACON_UUID: Final = "504F434B-4554-4153-5354-000000000210"
DEFAULT_BLE_AUTO_SWITCH: Final = True
DEFAULT_SYNC_DEVICE_AREA: Final = True
DEFAULT_AREA_HANDOFF: Final = True
DEFAULT_ART_SIZE: Final = 466

# Native Latter Entity Contract (Pocket Assistant v2.1.0+)
ENTITY_ACTIVE_MEDIA: Final = "sensor.pocket_assistant_active_media"
ENTITY_WEATHER_FORECAST: Final = "sensor.pocket_assistant_weather_forecast"
ENTITY_ROOM_CONTEXT: Final = "sensor.pocket_assistant_room_context"
ENTITY_CALENDAR_AGENDA: Final = "sensor.pocket_assistant_calendar_agenda"
ENTITY_REMOTE_CONFIG: Final = "sensor.pocket_assistant_remote_config"

# Native Latter Services
SERVICE_MUSIC_BROWSE: Final = "music_browse"
SERVICE_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
SERVICE_MEDIA_VOLUME: Final = "media_volume"
SERVICE_ROOM_BROWSE: Final = "room_browse"
SERVICE_ROOM_ACTION: Final = "room_action"
SERVICE_SET_ACTIVE_AREA: Final = "set_active_area"
SERVICE_REMOTE_ACTION: Final = "remote_action"
SERVICE_CALENDAR_FETCH: Final = "calendar_fetch"
SERVICE_CALENDAR_CREATE_EVENT: Final = "calendar_create_event"
SERVICE_INTERCOM_BROADCAST: Final = "intercom_broadcast"

# HTTP Image Proxy Endpoint
API_IMAGE_PROXY_PATH: Final = "/api/latter/image_proxy/{entry_id}"
DATA_HMAC_SECRET: Final = "hmac_secret"

# Timing & Recorder Idle-Guard
POSITION_UPDATE_INTERVAL_SECONDS: Final = 2
FORECAST_REFRESH_INTERVAL_MINUTES: Final = 30
CALENDAR_REFRESH_INTERVAL_MINUTES: Final = 15