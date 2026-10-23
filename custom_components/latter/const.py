"""Constants for the Latter (ESPHome Companion & Entity Middleware) integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "latter"
PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]

# Config & Options keys
CONF_DEVICE_SLUG: Final = "device_slug"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_DEFAULT_SPEAKER: Final = "default_speaker"
CONF_LOCAL_SPEAKER: Final = "local_speaker"
CONF_DEFAULT_AREA: Final = "default_area"
CONF_AREA_HANDOFF: Final = "area_handoff"
CONF_CALENDAR_ENTITIES: Final = "calendar_entities"
CONF_CUSTOM_ENTITIES: Final = "custom_entities"
CONF_ART_SIZE: Final = "art_size"

# Defaults
DEFAULT_DEVICE_SLUG: Final = "pocket_assistant"
DEFAULT_LOCAL_SPEAKER: Final = "media_player.pocket_assistant"
DEFAULT_AREA_HANDOFF: Final = True
DEFAULT_ART_SIZE: Final = 466

# Native Latter Entity Contract (Pocket Assistant v2.1.0+)
ENTITY_ACTIVE_MEDIA: Final = "sensor.pocket_assistant_active_media"
ENTITY_WEATHER_FORECAST: Final = "sensor.pocket_assistant_weather_forecast"
ENTITY_ROOM_CONTEXT: Final = "sensor.pocket_assistant_room_context"
ENTITY_CALENDAR_AGENDA: Final = "sensor.pocket_assistant_calendar_agenda"

# Native Latter Services
SERVICE_MUSIC_BROWSE: Final = "music_browse"
SERVICE_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
SERVICE_ROOM_BROWSE: Final = "room_browse"
SERVICE_ROOM_ACTION: Final = "room_action"
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