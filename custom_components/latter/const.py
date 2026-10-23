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
CONF_CALENDAR_ENTITIES: Final = "calendar_entities"
CONF_ART_SIZE: Final = "art_size"
CONF_ENABLE_V20_COMPAT: Final = "enable_v20_compat"

# Defaults
DEFAULT_DEVICE_SLUG: Final = "pocket_assistant"
DEFAULT_LOCAL_SPEAKER: Final = "media_player.pocket_assistant"
DEFAULT_ART_SIZE: Final = 466
DEFAULT_ENABLE_V20_COMPAT: Final = True

# v2.0 Backward-Compatible Entity & Service Contract
V20_ACTIVE_MEDIA_ENTITY: Final = "sensor.pocket_assistant_active_media"
V20_WEATHER_FORECAST_ENTITY: Final = "sensor.pocket_assistant_weather_forecast"
V20_ACTIVE_SPEAKER_ENTITY: Final = "input_text.pocket_assistant_active_speaker"
V20_MUSIC_BROWSE_SCRIPT: Final = "pocket_assistant_music_browse"

# Native Latter v2.1 Services
SERVICE_MUSIC_BROWSE: Final = "music_browse"
SERVICE_SET_ACTIVE_SPEAKER: Final = "set_active_speaker"
SERVICE_ROOM_ACTION: Final = "room_action"
SERVICE_CALENDAR_FETCH: Final = "calendar_fetch"

# HTTP Image Proxy Endpoint
API_IMAGE_PROXY_PATH: Final = "/api/latter/image_proxy/{entry_id}"
DATA_HMAC_SECRET: Final = "hmac_secret"

# Timing & Recorder Idle-Guard
POSITION_UPDATE_INTERVAL_SECONDS: Final = 2
FORECAST_REFRESH_INTERVAL_MINUTES: Final = 30