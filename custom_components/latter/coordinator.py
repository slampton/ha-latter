"""State coordinator and v2.0/v2.1 middleware bridge for Latter."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_CALL_SERVICE,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.network import get_url
from homeassistant.util import dt as dt_util

from .calendar_engine import async_fetch_calendar_agenda
from .const import (
    CALENDAR_REFRESH_INTERVAL_MINUTES,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_CALENDAR_ENTITIES,
    CONF_CUSTOM_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_ENABLE_V20_COMPAT,
    CONF_LOCAL_SPEAKER,
    CONF_WEATHER_ENTITY,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_DEVICE_SLUG,
    DEFAULT_ENABLE_V20_COMPAT,
    DEFAULT_LOCAL_SPEAKER,
    DOMAIN,
    FORECAST_REFRESH_INTERVAL_MINUTES,
    POSITION_UPDATE_INTERVAL_SECONDS,
    V20_ACTIVE_SPEAKER_ENTITY,
    V20_MUSIC_BROWSE_SCRIPT,
)
from .room_engine import (
    find_area_media_entities,
    get_area_entities,
    get_areas_summary,
)

_LOGGER = logging.getLogger(__name__)

DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


class LatterCoordinator:
    """Manages active speaker, room context, calendar agenda, and weather."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hmac_secret: bytes,
    ) -> None:
        """Initialize the Latter coordinator."""
        self.hass = hass
        self.entry = entry
        self._hmac_secret = hmac_secret

        self._listeners: list[callable] = []
        self._unsub_speaker_state: callable | None = None
        self._unsub_weather_state: callable | None = None
        self._unsub_position_timer: callable | None = None
        self._unsub_forecast_timer: callable | None = None
        self._unsub_calendar_timer: callable | None = None
        self._unsub_service_interceptor: callable | None = None

        self.active_speaker: str = self.get_opt(
            CONF_DEFAULT_SPEAKER, DEFAULT_LOCAL_SPEAKER
        )
        self.last_speaker: str = self.active_speaker
        self.active_area_id: str | None = self.get_opt(CONF_DEFAULT_AREA)
        self.active_remote: str = ""

        # Cached weather forecast state & attributes
        self.forecast_string: str = "NONE"
        self.weather_attributes: dict[str, Any] = {
            "condition": "unknown",
            "temperature": 0.0,
            "humidity": 0.0,
            "wind_speed": 0.0,
            "wind_bearing": 0.0,
            "high": 0.0,
            "low": 0.0,
        }

        # Cached calendar agenda state & attributes
        self.calendar_agenda_string: str = "NONE"
        self.calendar_events: list[dict[str, Any]] = []

    def get_opt(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from entry.options with fallback to entry.data."""
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)

    @property
    def device_slug(self) -> str:
        """Return normalized ESPHome device slug (underscores)."""
        raw = str(self.get_opt(CONF_DEVICE_SLUG, DEFAULT_DEVICE_SLUG))
        return raw.strip().lower().replace("-", "_")

    @property
    def local_speaker(self) -> str:
        """Return the on-device Sendspin media_player entity_id."""
        return str(self.get_opt(CONF_LOCAL_SPEAKER, DEFAULT_LOCAL_SPEAKER))

    @property
    def weather_entity(self) -> str | None:
        """Return configured weather entity_id."""
        val = self.get_opt(CONF_WEATHER_ENTITY)
        return str(val) if val else None

    @property
    def calendar_entities(self) -> list[str]:
        """Return configured calendar entity_ids."""
        val = self.get_opt(CONF_CALENDAR_ENTITIES, [])
        return list(val) if isinstance(val, (list, tuple)) else []

    @property
    def custom_entities(self) -> list[str]:
        """Return user-pinned custom entities for this device."""
        val = self.get_opt(CONF_CUSTOM_ENTITIES, [])
        return list(val) if isinstance(val, (list, tuple)) else []

    @property
    def area_handoff_enabled(self) -> bool:
        """Return True if switching rooms should hand off active speaker/remote context."""
        return bool(self.get_opt(CONF_AREA_HANDOFF, DEFAULT_AREA_HANDOFF))

    @property
    def art_size(self) -> int:
        """Return target square artwork dimension in pixels."""
        return int(self.get_opt(CONF_ART_SIZE, DEFAULT_ART_SIZE))

    @property
    def v20_compat_enabled(self) -> bool:
        """Return True if v2.0 entity & script compatibility is active."""
        return bool(self.get_opt(CONF_ENABLE_V20_COMPAT, DEFAULT_ENABLE_V20_COMPAT))

    def get_signed_token(self) -> str:
        """Generate an HMAC-SHA256 token for this config entry's image proxy."""
        return hmac.new(
            self._hmac_secret,
            self.entry.entry_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]

    def verify_token(self, token: str | None) -> bool:
        """Verify an incoming query token in constant time."""
        if not token:
            return False
        return hmac.compare_digest(token, self.get_signed_token())

    def build_proxy_art_url(self, cache_bust: str) -> str:
        """Build the full external/internal HTTP URL for the ESP32-S3 online_image."""
        try:
            base_url = get_url(self.hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            base_url = "http://homeassistant.local:8123"
        token = self.get_signed_token()
        digest = hashlib.md5(cache_bust.encode("utf-8")).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/image_proxy/{self.entry.entry_id}"
            f"?token={token}&v={digest}"
        )

    async def async_setup(self) -> None:
        """Set up state subscriptions, timers, and v2.0 compatibility hooks."""
        if not self.active_area_id:
            areas = get_areas_summary(self.hass)
            if areas:
                self.active_area_id = str(areas[0]["id"])

        if self.v20_compat_enabled:
            existing = self.hass.states.get(V20_ACTIVE_SPEAKER_ENTITY)
            if existing and existing.state not in ("unknown", "unavailable", ""):
                self.active_speaker = existing.state
            else:
                self._sync_v20_speaker_state()

            self._unsub_service_interceptor = self.hass.bus.async_listen(
                EVENT_CALL_SERVICE, self._async_handle_service_event
            )

        self._bind_speaker_listener()
        self._bind_weather_listener()
        await self.async_refresh_weather_forecast()
        await self.async_refresh_calendar_agenda()

        self._unsub_forecast_timer = async_track_time_interval(
            self.hass,
            self._async_periodic_weather_refresh,
            timedelta(minutes=FORECAST_REFRESH_INTERVAL_MINUTES),
        )
        self._unsub_calendar_timer = async_track_time_interval(
            self.hass,
            self._async_periodic_calendar_refresh,
            timedelta(minutes=CALENDAR_REFRESH_INTERVAL_MINUTES),
        )

    async def async_shutdown(self) -> None:
        """Clean up all subscriptions and timers."""
        for unsub in (
            self._unsub_speaker_state,
            self._unsub_weather_state,
            self._unsub_position_timer,
            self._unsub_forecast_timer,
            self._unsub_calendar_timer,
            self._unsub_service_interceptor,
        ):
            if unsub is not None:
                unsub()
        self._unsub_speaker_state = None
        self._unsub_weather_state = None
        self._unsub_position_timer = None
        self._unsub_forecast_timer = None
        self._unsub_calendar_timer = None
        self._unsub_service_interceptor = None
        self._listeners.clear()

    @callback
    def async_add_listener(self, update_callback: callable) -> callable:
        """Register an entity state update callback."""
        self._listeners.append(update_callback)

        @callback
        def _remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return _remove

    @callback
    def _notify_listeners(self) -> None:
        """Notify all registered sensors of a state update."""
        for update_callback in list(self._listeners):
            update_callback()

    @callback
    def _sync_v20_speaker_state(self) -> None:
        """Mirror active speaker into input_text.pocket_assistant_active_speaker."""
        if not self.v20_compat_enabled:
            return
        self.hass.states.async_set(
            V20_ACTIVE_SPEAKER_ENTITY,
            self.active_speaker,
            {
                "friendly_name": "Pocket Assistant Active Speaker",
                "icon": "mdi:speaker-wireless",
                "managed_by": DOMAIN,
            },
        )

    @callback
    def async_set_active_speaker(self, speaker_entity_id: str) -> None:
        """Switch the active target speaker and rebind state listeners."""
        speaker_entity_id = speaker_entity_id.strip()
        if not speaker_entity_id:
            return
        if speaker_entity_id != self.active_speaker:
            self.last_speaker = self.active_speaker
            self.active_speaker = speaker_entity_id
            _LOGGER.debug(
                "Latter active speaker changed: %s -> %s",
                self.last_speaker,
                self.active_speaker,
            )
        self._sync_v20_speaker_state()
        self._bind_speaker_listener()
        self._notify_listeners()

    @callback
    def async_set_active_area(
        self, area_id: str, handoff_media: bool | None = None
    ) -> None:
        """Switch active room area and optionally hand off speaker & TV remote context."""
        area_id = area_id.strip()
        if not area_id:
            return
        self.active_area_id = area_id
        media_map = find_area_media_entities(
            self.hass, area_id, self.local_speaker
        )
        if media_map["remote"]:
            self.active_remote = media_map["remote"]

        do_handoff = (
            self.area_handoff_enabled
            if handoff_media is None
            else bool(handoff_media)
        )
        if do_handoff and media_map["speaker"]:
            self.async_set_active_speaker(media_map["speaker"])
        else:
            self._notify_listeners()

    def get_room_context_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute state and attributes for sensor.pocket_assistant_room_context."""
        area_reg = ar.async_get(self.hass)
        area_entry = (
            area_reg.async_get_area(self.active_area_id)
            if self.active_area_id
            else None
        )
        area_name = area_entry.name if area_entry else "Home"

        entities = get_area_entities(
            self.hass,
            area_id=self.active_area_id,
            domain_filter="all",
            custom_entities=self.custom_entities,
        )
        lights_on = sum(
            1 for e in entities if e["type"] == "light" and e["active"]
        )
        covers_open = sum(
            1 for e in entities if e["type"] == "cover" and e["active"]
        )
        media_map = find_area_media_entities(
            self.hass, self.active_area_id, self.local_speaker
        )

        summary_items = [
            f"{e['id']}:{e['name']}:{int(e['active'])}:{e['level']}"
            for e in entities[:8]
        ]

        return area_name, {
            "area_id": self.active_area_id or "",
            "area_name": area_name,
            "entity_count": len(entities),
            "lights_on": lights_on,
            "covers_open": covers_open,
            "area_speaker": media_map["speaker"] or self.active_speaker,
            "area_remote": media_map["remote"] or self.active_remote,
            "entities_summary": ";".join(summary_items) if summary_items else "NONE",
            "custom_entities": self.custom_entities,
        }

    @callback
    def _async_handle_service_event(self, event: Event) -> None:
        """Intercept v2.0 firmware calls to input_text.set_value and script.pocket_assistant_music_browse."""
        domain = event.data.get("domain")
        service = event.data.get("service")
        service_data = event.data.get("service_data") or {}

        if domain == "input_text" and service == "set_value":
            target_entities = service_data.get(ATTR_ENTITY_ID)
            if isinstance(target_entities, str):
                target_entities = [target_entities]
            elif not isinstance(target_entities, list):
                target_entities = []

            if V20_ACTIVE_SPEAKER_ENTITY in target_entities:
                new_value = str(service_data.get("value", "")).strip()
                if new_value:
                    self.async_set_active_speaker(new_value)

        elif domain == "script":
            if service == V20_MUSIC_BROWSE_SCRIPT:
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        DOMAIN, "music_browse", dict(service_data), blocking=False
                    )
                )
            elif service == "turn_on":
                target_entities = service_data.get(ATTR_ENTITY_ID, "")
                if f"script.{V20_MUSIC_BROWSE_SCRIPT}" in str(target_entities):
                    variables = service_data.get("variables") or {}
                    self.hass.async_create_task(
                        self.hass.services.async_call(
                            DOMAIN, "music_browse", dict(variables), blocking=False
                        )
                    )

    @callback
    def _bind_speaker_listener(self) -> None:
        """Subscribe to state changes on the currently selected media_player."""
        if self._unsub_speaker_state is not None:
            self._unsub_speaker_state()
            self._unsub_speaker_state = None

        if not self.active_speaker:
            return

        self._unsub_speaker_state = async_track_state_change_event(
            self.hass,
            [self.active_speaker],
            self._async_on_speaker_state_change,
        )
        self._update_position_timer_state()

    @callback
    def _async_on_speaker_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle target media_player state/attribute updates."""
        self._update_position_timer_state()
        self._notify_listeners()

    @callback
    def _update_position_timer_state(self) -> None:
        """Idle-Guard: Run 2s position timer ONLY when speaker is playing/buffering."""
        state_obj = self.hass.states.get(self.active_speaker)
        is_active = state_obj is not None and state_obj.state in (
            STATE_PLAYING,
            STATE_BUFFERING,
        )

        if is_active and self._unsub_position_timer is None:
            self._unsub_position_timer = async_track_time_interval(
                self.hass,
                self._async_on_position_tick,
                timedelta(seconds=POSITION_UPDATE_INTERVAL_SECONDS),
            )
        elif not is_active and self._unsub_position_timer is not None:
            self._unsub_position_timer()
            self._unsub_position_timer = None

    @callback
    def _async_on_position_tick(self, _now: datetime) -> None:
        """Tick media position while actively playing."""
        self._notify_listeners()

    def get_active_media_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute exact v2.0 state and attributes for sensor.pocket_assistant_active_media."""
        state_obj = self.hass.states.get(self.active_speaker)
        if state_obj is None or state_obj.state in ("unavailable", "unknown"):
            return STATE_OFF, {
                "title": "Idle",
                "artist": "None",
                "album": "None",
                "duration": 0,
                "position": 0,
                "volume": 0.7,
                "media_type": "music",
                "supported_features": 0,
                "art_url": "none",
                "active_speaker": self.active_speaker,
            }

        state = state_obj.state
        if state not in (
            STATE_PLAYING,
            STATE_PAUSED,
            STATE_IDLE,
            STATE_BUFFERING,
            STATE_OFF,
        ):
            state = STATE_IDLE

        attrs = state_obj.attributes
        title = str(attrs.get("media_title") or "Idle")
        artist = str(
            attrs.get("media_artist")
            or attrs.get("media_series_title")
            or attrs.get("media_album_artist")
            or "None"
        )
        album = str(attrs.get("media_album_name") or "None")
        duration = float(attrs.get("media_duration") or 0)
        base_position = float(attrs.get("media_position") or 0)
        updated_at = attrs.get("media_position_updated_at")

        position = base_position
        if state == STATE_PLAYING and isinstance(updated_at, datetime):
            elapsed = (dt_util.utcnow() - updated_at).total_seconds()
            if elapsed > 0:
                position = base_position + elapsed
                if duration > 0:
                    position = min(position, duration)

        volume = float(
            attrs.get("volume_level")
            if attrs.get("volume_level") is not None
            else 0.7
        )
        raw_type = str(attrs.get("media_content_type") or "music").lower()
        if "podcast" in raw_type:
            media_type = "podcast"
        elif "audiobook" in raw_type or "book" in raw_type:
            media_type = "audiobook"
        else:
            media_type = "music"

        supported_features = int(attrs.get("supported_features") or 0)

        raw_pic = attrs.get("entity_picture_local") or attrs.get("entity_picture")
        if (
            self.active_speaker == self.local_speaker
            or not raw_pic
            or state in (STATE_IDLE, STATE_OFF)
        ):
            art_url = "none"
        else:
            cache_key = f"{self.active_speaker}|{title}|{album}|{raw_pic}"
            art_url = self.build_proxy_art_url(cache_key)

        return state, {
            "title": title,
            "artist": artist,
            "album": album,
            "duration": round(duration, 1),
            "position": round(position, 1),
            "volume": round(volume, 2),
            "media_type": media_type,
            "supported_features": supported_features,
            "art_url": art_url,
            "active_speaker": self.active_speaker,
        }

    @callback
    def _bind_weather_listener(self) -> None:
        """Subscribe to state changes on the configured weather entity."""
        if self._unsub_weather_state is not None:
            self._unsub_weather_state()
            self._unsub_weather_state = None

        weather_ent = self.weather_entity
        if not weather_ent:
            return

        self._unsub_weather_state = async_track_state_change_event(
            self.hass,
            [weather_ent],
            self._async_on_weather_state_change,
        )

    @callback
    def _async_on_weather_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Update current weather attributes and refresh forecast."""
        self.hass.async_create_task(self.async_refresh_weather_forecast())

    async def _async_periodic_weather_refresh(self, _now: datetime) -> None:
        """Refresh 5-day weather forecast every 30 minutes."""
        await self.async_refresh_weather_forecast()

    async def _async_periodic_calendar_refresh(self, _now: datetime) -> None:
        """Refresh family calendar agenda every 15 minutes."""
        await self.async_refresh_calendar_agenda()

    async def async_refresh_calendar_agenda(self) -> None:
        """Fetch upcoming calendar events and update sensor state."""
        agenda_str, events = await async_fetch_calendar_agenda(
            self.hass, self.calendar_entities
        )
        self.calendar_agenda_string = agenda_str
        self.calendar_events = events
        self._notify_listeners()

    async def async_refresh_weather_forecast(self) -> None:
        """Fetch daily weather forecast via weather.get_forecasts and format v2.0 string."""
        weather_ent = self.weather_entity
        if not weather_ent:
            return

        state_obj = self.hass.states.get(weather_ent)
        if state_obj is None:
            return

        attrs = state_obj.attributes
        temp = float(attrs.get("temperature") or 0.0)
        humidity = float(attrs.get("humidity") or 0.0)
        wind_speed = float(attrs.get("wind_speed") or 0.0)
        wind_bearing = float(attrs.get("wind_bearing") or 0.0)

        forecasts: list[dict[str, Any]] = []
        if self.hass.services.has_service("weather", "get_forecasts"):
            try:
                resp = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": weather_ent, "type": "daily"},
                    blocking=True,
                    return_response=True,
                )
                if isinstance(resp, dict) and weather_ent in resp:
                    forecasts = resp[weather_ent].get("forecast") or []
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("weather.get_forecasts failed for %s: %s", weather_ent, err)

        if not forecasts and isinstance(attrs.get("forecast"), list):
            forecasts = attrs.get("forecast")

        high = temp
        low = temp
        segments: list[str] = []

        for idx, item in enumerate(forecasts[:5]):
            f_high = item.get("temperature", temp)
            f_low = item.get("templow", f_high)
            f_cond = str(item.get("condition") or state_obj.state or "sunny")

            if idx == 0:
                high = float(f_high if f_high is not None else temp)
                low = float(f_low if f_low is not None else temp)

            dt_raw = item.get("datetime")
            day_label = "DAY"
            if dt_raw:
                parsed = dt_util.parse_datetime(str(dt_raw))
                if parsed is not None:
                    local_dt = dt_util.as_local(parsed)
                    day_label = DAY_ABBR[local_dt.weekday()]

            h_int = int(round(float(f_high if f_high is not None else temp)))
            l_int = int(round(float(f_low if f_low is not None else h_int)))
            segments.append(f"{day_label}:{h_int}:{l_int}:{f_cond}")

        self.forecast_string = ";".join(segments) if segments else "NONE"
        self.weather_attributes = {
            "condition": str(state_obj.state),
            "temperature": round(temp, 1),
            "humidity": round(humidity, 1),
            "wind_speed": round(wind_speed, 1),
            "wind_bearing": round(wind_bearing, 1),
            "high": round(high, 1),
            "low": round(low, 1),
            "weather_entity": weather_ent,
        }
        self._notify_listeners()