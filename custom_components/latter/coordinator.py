"""State coordinator for Latter (Universal ESPHome Companion & Entity Middleware)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import hashlib
import hmac
import logging
import time
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .ble_engine import (
    LatterNativeBleTracker,
    _iter_devices,
    _iter_entities,
    get_all_scanners_diagnostic_map,
    get_ble_proxy_area_ids,
)
from .browse_engine import _get_mass_client, is_music_assistant_player
from .calendar_engine import async_fetch_calendar_agenda
from .const import (
    CALENDAR_REFRESH_INTERVAL_MINUTES,
    CONF_ALARM_ENTITY,
    CONF_CAMERA_ENTITY,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_ROOM_OFFSETS,
    CONF_CALENDAR_ENTITIES,
    CONF_COMPANION_BASE_URL,
    CONF_CUSTOM_BINDINGS,
    CONF_CUSTOM_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_SLUG,
    CONF_SITE_ID,
    CONF_VPN_CLIENT_IP,
    CONF_VPN_ENABLED,
    CONF_VPN_ENDPOINT,
    CONF_VPN_HA_IP,
    CONF_VPN_HOTSPOT_SSID,
    CONF_VPN_PRESHARED_KEY,
    CONF_VPN_PRIVATE_KEY,
    CONF_VPN_PUBLIC_KEY,
    CONF_VPN_SERVER_PUBLIC_KEY,
    CONF_VPN_SUBNET,
    DEFAULT_SITE_ID,
    CONF_DISPLAY_SHAPE,
    CONF_DOCK_APPS,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_REMOTE_1,
    CONF_REMOTE_2,
    CONF_REMOTE_3,
    CONF_REMOTE_4,
    CONF_SYNC_DEVICE_AREA,
    CONF_VOL_SPEAKER_1,
    CONF_VOL_SPEAKER_2,
    CONF_VOL_TARGET_1,
    CONF_VOL_TARGET_2,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_DOCK_APPS,
    DEFAULT_NATIVE_BLE_TRACKING,
    DEFAULT_PAGE_SIZE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_SYNC_DEVICE_AREA,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DOMAIN,
    FORECAST_REFRESH_INTERVAL_MINUTES,
    GLOBAL_CONFIG_KEYS,
    POSITION_UPDATE_INTERVAL_SECONDS,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    normalize_device_slug,
)
from .room_engine import (
    find_area_media_entities,
    get_area_climate_telemetry,
    get_area_entities,
    get_areas_summary,
    get_home_alarm_summary,
    match_area_by_name_or_id,
    protect_handheld_sensors_from_area_dashboards,
    resolve_remote_slot_pair,
    sync_esphome_device_area,
)

_LOGGER = logging.getLogger(__name__)

DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
TRANSFER_HOLD_WINDOW_SECONDS = 4.5
VOLUME_FEATURE_FLAGS = 4 | 8 | 1024  # VOLUME_SET | VOLUME_MUTE | VOLUME_STEP


def _resolve_esphome_local_speaker(
    hass: HomeAssistant, device_slug: str
) -> str:
    """Automatically resolve the on-device media_player entity for the configured ESPHome node."""
    slug_norm = normalize_device_slug(device_slug)
    direct_candidate = f"media_player.{slug_norm}"
    if hass.states.get(direct_candidate) is not None:
        return direct_candidate

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    for entry in _iter_entities(ent_reg):
        if entry.domain == "media_player" and entry.platform == "esphome":
            if slug_norm in entry.entity_id and not entry.disabled_by:
                return entry.entity_id

    for dev in _iter_devices(dev_reg):
        dev_name = (
            str(dev.name_by_user or dev.name or "")
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if slug_norm and slug_norm in dev_name:
            for entry in er.async_entries_for_device(ent_reg, dev.id):
                if entry.domain == "media_player" and not entry.disabled_by:
                    return entry.entity_id

    return direct_candidate


def _resolve_ma_counterpart_entity(
    hass: HomeAssistant, speaker_entity_id: str, device_slug: str
) -> str | None:
    """Find the Music Assistant media_player entity corresponding to an ESPHome speaker (if wrapped by MA)."""
    state_obj = hass.states.get(speaker_entity_id)
    if state_obj and is_music_assistant_player(hass, state_obj):
        return speaker_entity_id

    slug_norm = normalize_device_slug(device_slug)
    spk_short = speaker_entity_id.replace("media_player.", "").lower()

    for candidate in hass.states.async_all("media_player"):
        if candidate.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if not is_music_assistant_player(hass, candidate):
            continue
        cid_low = candidate.entity_id.lower()
        friendly_low = (
            str(candidate.attributes.get("friendly_name") or "")
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if slug_norm in cid_low or spk_short in cid_low or slug_norm in friendly_low:
            return candidate.entity_id

    return None


def _get_esphome_device_current_area(
    hass: HomeAssistant, device_slug: str
) -> str | None:
    """Return the current area_id assigned to the ESPHome device in HA Device Registry."""
    dev_reg = dr.async_get(hass)
    slug_norm = normalize_device_slug(device_slug)
    for dev in _iter_devices(dev_reg):
        dev_name = (
            str(dev.name_by_user or dev.name or "")
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if slug_norm and slug_norm in dev_name and dev.area_id:
            return dev.area_id
    return None


def _interpolate_speaker_position(state_obj: Any) -> float:
    """Calculate the live interpolated playback position in seconds for a media_player state."""
    if state_obj is None:
        return 0.0
    attrs = state_obj.attributes
    duration = float(attrs.get("media_duration") or 0.0)
    base_pos = float(attrs.get("media_position") or 0.0)
    updated_at = attrs.get("media_position_updated_at")
    pos = base_pos
    if state_obj.state == STATE_PLAYING and isinstance(updated_at, datetime):
        elapsed = (dt_util.utcnow() - updated_at).total_seconds()
        if elapsed > 0:
            pos = base_pos + elapsed
            if duration > 0:
                pos = min(pos, duration)
    return max(0.0, pos)


class LatterCoordinator:
    """Manages active speaker, BLE room context, 4-slot remotes, custom bindings, wallpapers, alarm, calendar, and weather."""

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
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )

        self._listeners: list[callable] = []
        self._unsub_speaker_state: callable | None = None
        self._unsub_local_reconnect: callable | None = None
        self._unsub_play_interceptor: callable | None = None
        self._unsub_weather_state: callable | None = None
        self._unsub_alarm_state: callable | None = None
        self._unsub_presence_state: callable | None = None
        self._unsub_remotes_state: callable | None = None
        self._unsub_room_entities_state: callable | None = None
        self._unsub_room_debounce: callable | None = None
        self._unsub_position_timer: callable | None = None
        self._unsub_forecast_timer: callable | None = None
        self._unsub_calendar_timer: callable | None = None
        self._unsub_wallpaper_timer: callable | None = None
        self._ble_tracker: LatterNativeBleTracker | None = None

        self.active_speaker: str = (
            str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip()
            or self.local_speaker
        )
        self.last_speaker: str = self.active_speaker
        self.active_area_id: str | None = self.get_opt(CONF_DEFAULT_AREA)
        self.active_remote: str = ""
        self.active_remote_slot: int = 1
        self.last_room_filter: str = "all"
        self.last_room_page: int = 1
        self.on_area_changed_push_slots: callable | None = None

        # Persisted track metadata & URI for post-reboot Sendspin queue resumption
        self.last_media_uri: str = ""
        self.last_media_type: str = "music"
        self.last_media_title: str = ""
        self.last_media_artist: str = ""
        self.last_media_album: str = ""
        self.last_media_duration: float = 0.0
        self.last_media_position: float = 0.0
        self._resuming_guard_until: float = 0.0
        self._local_needs_cold_resume: bool = True

        # Sticky artwork and transfer position handoff cache (for MA 2.10.8 transfer window)
        self.last_valid_raw_pic: str = ""
        self._last_art_track_key: str = ""
        self._last_art_proxy_url: str = "none"
        self._transfer_hold_until: float = 0.0
        self._transfer_hold_position: float = 0.0
        self._transfer_hold_title: str = ""
        self._transfer_hold_artist: str = ""
        self._transfer_hold_album: str = ""
        self._transfer_hold_duration: float = 0.0

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

        # Smart Device Notification & Camera Peephole Alert State
        self.alert_id: int = 0
        self.alert_title: str = ""
        self.alert_message: str = ""
        self.alert_priority: str = "normal"
        self.alert_duration: int = 8
        self.alert_chime: bool = True
        self.alert_camera_url: str = "none"

        # Smart Device Notification & Camera Peephole Alert State
        self.alert_id: int = 0
        self.alert_title: str = ""
        self.alert_message: str = ""
        self.alert_priority: str = "normal"
        self.alert_duration: int = 8
        self.alert_chime: bool = True
        self.alert_camera_url: str = "none"

    def get_opt(self, key: str, default: Any = None) -> Any:
        """Retrieve a setting, prioritizing Global Household config for shared keys and entry options/data for device keys."""
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
        if key in GLOBAL_CONFIG_KEYS and isinstance(global_cfg, dict) and key in global_cfg:
            val = global_cfg[key]
            if val is not None and val != "":
                return val
        if self.entry.options and key in self.entry.options:
            return self.entry.options[key]
        if key in self.entry.data:
            return self.entry.data[key]
        if isinstance(global_cfg, dict) and key in global_cfg:
            return global_cfg[key]
        return default

    async def async_on_global_config_updated(self) -> None:
        """Refresh listeners, BLE offsets, weather, and calendar when Global Household config changes."""
        if self._ble_tracker is not None:
            self._ble_tracker.set_room_offsets(self.ble_room_offsets)
        self._bind_speaker_listener()
        self._bind_weather_listener()
        self._bind_alarm_listener()
        self._bind_remotes_listener()
        self._bind_room_entities_listener()
        await self.async_refresh_weather_forecast()
        await self.async_refresh_calendar_agenda()
        self._notify_listeners()

    @property
    def device_slug(self) -> str:
        """Return normalized ESPHome device slug (underscores)."""
        raw = str(self.get_opt(CONF_DEVICE_SLUG, "esphome_device"))
        return normalize_device_slug(raw)

    @property
    def site_id(self) -> str:
        """Return the logical site identifier for this device (defaults to 'primary' for single-site homes)."""
        return str(self.get_opt(CONF_SITE_ID, DEFAULT_SITE_ID) or DEFAULT_SITE_ID).strip()

    @property
    def vpn_enabled(self) -> bool:
        """Return True if Roaming WireGuard VPN is enabled for this device."""
        return bool(self.get_opt(CONF_VPN_ENABLED, False))

    @property
    def vpn_client_ip(self) -> str:
        """Return the assigned WireGuard tunnel IP for this device."""
        return str(self.get_opt(CONF_VPN_CLIENT_IP, "") or "").strip()

    @property
    def device_profile(self) -> str:
        """Return device archetype (mobile_display, stationary_display, headless_node)."""
        return str(
            self.get_opt(CONF_DEVICE_PROFILE, DEFAULT_DEVICE_PROFILE)
        ).strip()

    @property
    def display_shape(self) -> str:
        """Return display geometry ('circle' or 'square')."""
        return str(
            self.get_opt(CONF_DISPLAY_SHAPE, DEFAULT_DISPLAY_SHAPE)
        ).strip().lower()

    @property
    def default_page_size(self) -> int:
        """Return default room/entity pagination page size for this device's GUI."""
        return max(
            1,
            min(20, int(self.get_opt(CONF_DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE))),
        )

    @property
    def dock_apps_csv(self) -> str:
        """Return comma-separated Home Dock app order."""
        return str(self.get_opt(CONF_DOCK_APPS, DEFAULT_DOCK_APPS)).strip()

    @property
    def companion_base_url(self) -> str:
        """Return optional user-configured reverse proxy base URL (e.g. https://home.lamptons.com)."""
        return str(self.get_opt(CONF_COMPANION_BASE_URL, "") or "").strip().rstrip("/")

    @property
    def wallpaper_source(self) -> str:
        """Return configured photo wallpaper URL, preset ID, or /local/ path."""
        return str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()

    @property
    def wallpaper_favorites(self) -> list[str]:
        """Return list of favorite wallpaper source IDs for rotation."""
        val = self.get_opt(CONF_WALLPAPER_FAVORITES, [])
        return [str(x) for x in val] if isinstance(val, (list, tuple)) else []

    @property
    def wallpaper_cycle_minutes(self) -> int:
        """Return wallpaper rotation interval in minutes (0 = disabled)."""
        try:
            return max(
                0,
                int(
                    self.get_opt(
                        CONF_WALLPAPER_CYCLE_MINUTES,
                        DEFAULT_WALLPAPER_CYCLE_MINUTES,
                    )
                ),
            )
        except (ValueError, TypeError):
            return 0

    @property
    def custom_bindings(self) -> list[dict[str, str]]:
        """Return universal hardware trigger / slot bindings configured in the Web Companion."""
        val = self.get_opt(CONF_CUSTOM_BINDINGS, [])
        return list(val) if isinstance(val, list) else []

    def _build_custom_bindings_summary(self) -> str:
        """Build a semicolon-delimited 5-slot summary ('slot|Friendly Name|action;...') for on-device Macro UIs."""
        rows: list[str] = []
        for b in self.custom_bindings[:5]:
            if not isinstance(b, dict):
                continue
            slot_id = str(b.get("slot") or "").strip().replace(";", "").replace("|", "")
            ent_id = str(b.get("entity_id") or "").strip()
            act = str(b.get("action") or "toggle").strip()
            if not slot_id or not ent_id:
                continue
            st = self.hass.states.get(ent_id)
            friendly = (
                str(st.attributes.get("friendly_name") if st else "")
                or ent_id.split(".", 1)[-1].replace("_", " ").title()
            )
            friendly = friendly.replace(";", "").replace("|", "")[:32]
            rows.append(f"{slot_id}|{friendly}|{act}")
        if not rows and self.custom_entities:
            for idx, ent_id in enumerate(self.custom_entities[:5], start=1):
                st = self.hass.states.get(ent_id)
                friendly = (
                    str(st.attributes.get("friendly_name") if st else "")
                    or ent_id.split(".", 1)[-1].replace("_", " ").title()
                )
                friendly = friendly.replace(";", "").replace("|", "")[:32]
                rows.append(f"macro_{idx}|{friendly}|toggle")
        return ";".join(rows) if rows else "NONE"

    @property
    def local_speaker(self) -> str:
        """Automatically resolve the on-device media_player entity from device_slug."""
        return _resolve_esphome_local_speaker(self.hass, self.device_slug)

    @property
    def weather_entity(self) -> str | None:
        """Return configured weather entity_id."""
        val = self.get_opt(CONF_WEATHER_ENTITY)
        return str(val) if val else None

    @property
    def alarm_entity(self) -> str | None:
        """Return configured alarm_control_panel entity_id (or auto-discovered)."""
        val = self.get_opt(CONF_ALARM_ENTITY)
        if val:
            return str(val)
        info = get_home_alarm_summary(self.hass)
        return info["entity_id"] or None

    @property
    def camera_entity(self) -> str | None:
        """Return configured primary doorbell/security camera entity_id."""
        val = self.get_opt(CONF_CAMERA_ENTITY)
        return str(val).strip() if val else None

    @property
    def native_ble_tracking_enabled(self) -> bool:
        """Return True if native ESPHome BLE proxy tracking is enabled."""
        return bool(
            self.get_opt(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)
        )

    @property
    def ble_beacon_uuid(self) -> str:
        """Return the iBeacon UUID broadcast by the device."""
        return str(
            self.get_opt(CONF_BLE_BEACON_UUID, DEFAULT_BLE_BEACON_UUID)
        ).strip()

    @property
    def ble_room_offsets(self) -> dict[str, float]:
        """Return per-room BLE RSSI calibration offsets (area_id -> dB bias)."""
        raw = self.get_opt(CONF_BLE_ROOM_OFFSETS, {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            try:
                val = round(max(-25.0, min(25.0, float(v))), 1)
                if val != 0.0:
                    out[str(k)] = val
            except (ValueError, TypeError):
                pass
        return out

    @property
    def presence_entity(self) -> str | None:
        """Return configured external BLE room presence entity_id (e.g. Bermuda)."""
        val = self.get_opt(CONF_PRESENCE_ENTITY)
        return str(val) if val else None

    @property
    def ble_auto_switch_enabled(self) -> bool:
        """Return True if BLE presence changes should auto-switch active room."""
        return bool(self.get_opt(CONF_BLE_AUTO_SWITCH, DEFAULT_BLE_AUTO_SWITCH))

    @property
    def sync_device_area_enabled(self) -> bool:
        """Return True if active room should sync to ESPHome Device Registry for Voice Assistant."""
        return bool(self.get_opt(CONF_SYNC_DEVICE_AREA, DEFAULT_SYNC_DEVICE_AREA))

    @property
    def volume_overrides(self) -> dict[str, str]:
        """Build speaker -> volume target dictionary from visual override selectors 1 & 2."""
        mapping: dict[str, str] = {}
        s1 = self.get_opt(CONF_VOL_SPEAKER_1)
        t1 = self.get_opt(CONF_VOL_TARGET_1)
        if s1 and t1:
            mapping[str(s1).strip()] = str(t1).strip()

        s2 = self.get_opt(CONF_VOL_SPEAKER_2)
        t2 = self.get_opt(CONF_VOL_TARGET_2)
        if s2 and t2:
            mapping[str(s2).strip()] = str(t2).strip()

        return mapping

    def get_volume_target_entity(self, speaker_entity_id: str | None = None) -> str:
        """Return the volume control target entity (AVR/number override if mapped, else active speaker)."""
        spk = speaker_entity_id or self.active_speaker
        return self.volume_overrides.get(spk, spk)

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

    def get_signed_token(self) -> str:
        """Generate an HMAC-SHA256 token for this config entry's companion UI."""
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

    def build_companion_url(self) -> str:
        """Build the authenticated Web Companion Studio URL, preferring the local internal HA URL over remote Nabu Casa."""
        base_url = self.companion_base_url
        if not base_url:
            try:
                base_url = get_url(self.hass, allow_internal=True, prefer_external=False)
            except Exception:  # noqa: BLE001
                try:
                    base_url = get_url(self.hass, allow_internal=True, prefer_external=True)
                except Exception:  # noqa: BLE001
                    base_url = "http://homeassistant.local:8123"
        token = self.get_signed_token()
        return f"{base_url.rstrip('/')}/api/latter/companion/{self.entry.entry_id}?token={token}"

    def build_camera_snapshot_url(
        self, camera_entity_id: str | None = None, cache_bust: str = ""
    ) -> str:
        """Build the local LAN HTTP Baseline-JPEG camera snapshot URL for ESP32 online_image."""
        cam_ent = (camera_entity_id or self.camera_entity or "").strip()
        if not cam_ent:
            return "none"
        try:
            base_url = get_url(self.hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            base_url = "http://homeassistant.local:8123"
        size = self.art_size
        v_tag = cache_bust or str(int(time.time()))
        return (
            f"{base_url}/api/latter/camera/{self.device_slug}"
            f"?entity_id={cam_ent}&w={size}&h={size}&shape={self.display_shape}&v={v_tag}"
        )

    @callback
    def async_dispatch_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        duration: int = 8,
        chime: bool = True,
        camera_entity: str | None = None,
    ) -> None:
        """Update device alert state & camera snapshot URL and notify listeners."""
        self.alert_id += 1
        self.alert_title = title.strip() or "Notification"
        self.alert_message = message.strip()
        self.alert_priority = priority.strip().lower() or "normal"
        self.alert_duration = max(2, min(60, int(duration)))
        self.alert_chime = bool(chime)
        if camera_entity:
            self.alert_camera_url = self.build_camera_snapshot_url(
                camera_entity, cache_bust=f"{self.alert_id}_{int(time.time())}"
            )
        else:
            self.alert_camera_url = "none"
        self._notify_listeners()

    def build_wallpaper_url(self) -> str:
        """Build the device-scoped baseline-JPEG photo wallpaper URL (always local LAN HTTP for ESP32 online_image)."""
        if not self.wallpaper_source:
            return "none"
        try:
            base_url = get_url(self.hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            base_url = "http://homeassistant.local:8123"
        size = self.art_size
        digest = hashlib.md5(
            f"{self.wallpaper_source}|{self.display_shape}|{size}".encode("utf-8")
        ).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/wallpaper/{self.device_slug}"
            f"?w={size}&h={size}&shape={self.display_shape}&v={digest}"
        )

    def build_proxy_art_url(self, cache_bust: str) -> str:
        """Build the universal Baseline-JPEG artwork URL (/api/latter/artwork/<device_slug>?w=...&h=...&v=...)."""
        try:
            base_url = get_url(self.hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            base_url = "http://homeassistant.local:8123"
        size = self.art_size
        digest = hashlib.md5(cache_bust.encode("utf-8")).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/artwork/{self.device_slug}"
            f"?w={size}&h={size}&v={digest}"
        )

    @callback
    def _schedule_persist_runtime_state(self) -> None:
        """Persist runtime speaker, area, remote slot, and last active track metadata to HA Store."""
        self._store.async_delay_save(
            lambda: {
                "active_speaker": self.active_speaker,
                "last_speaker": self.last_speaker,
                "active_area_id": self.active_area_id or "",
                "active_remote_slot": self.active_remote_slot,
                "last_media_uri": self.last_media_uri,
                "last_media_type": self.last_media_type,
                "last_media_title": self.last_media_title,
                "last_media_artist": self.last_media_artist,
                "last_media_album": self.last_media_album,
                "last_media_duration": self.last_media_duration,
                "last_media_position": round(self.last_media_position, 1),
            },
            delay=1.5,
        )

    async def async_setup(self) -> None:
        """Restore persisted state, set up subscriptions, start BLE tracker, and sync initial states."""
        try:
            stored = await self._store.async_load()
            if isinstance(stored, dict):
                saved_spk = str(stored.get("active_speaker") or "").strip()
                if saved_spk:
                    self.active_speaker = saved_spk
                saved_last = str(stored.get("last_speaker") or "").strip()
                if saved_last:
                    self.last_speaker = saved_last
                saved_area = str(stored.get("active_area_id") or "").strip()
                if saved_area and not self.active_area_id:
                    self.active_area_id = saved_area
                saved_slot = stored.get("active_remote_slot")
                if isinstance(saved_slot, int) and 1 <= saved_slot <= 4:
                    self.active_remote_slot = saved_slot
                self.last_media_uri = str(stored.get("last_media_uri") or "")
                self.last_media_type = str(stored.get("last_media_type") or "music")
                self.last_media_title = str(stored.get("last_media_title") or "")
                self.last_media_artist = str(stored.get("last_media_artist") or "")
                self.last_media_album = str(stored.get("last_media_album") or "")
                self.last_media_duration = float(stored.get("last_media_duration") or 0.0)
                self.last_media_position = float(stored.get("last_media_position") or 0.0)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed loading Latter runtime store: %s", err)

        if not self.active_speaker:
            self.active_speaker = self.local_speaker
        if not self.last_speaker:
            self.last_speaker = self.active_speaker

        # Enforce Strict Boot Rule: Never restore an idle/off remote speaker on startup
        self._enforce_local_speaker_if_remote_idle("ha_startup")

        if self.device_profile == "mobile_display":
            protect_handheld_sensors_from_area_dashboards(
                self.hass, self.device_slug
            )

        proxy_areas = get_ble_proxy_area_ids(self.hass)

        pres_ent = self.presence_entity
        if pres_ent and self.ble_auto_switch_enabled:
            pres_state = self.hass.states.get(pres_ent)
            if pres_state is not None:
                matched = match_area_by_name_or_id(self.hass, pres_state.state)
                if matched:
                    self.active_area_id = matched

        if not self.active_area_id:
            dev_area = _get_esphome_device_current_area(
                self.hass, self.device_slug
            )
            if dev_area and (not proxy_areas or dev_area in proxy_areas):
                self.active_area_id = dev_area

        if not self.active_area_id:
            areas = get_areas_summary(
                self.hass,
                local_speaker=self.local_speaker,
                device_slug=self.device_slug,
            )
            for area_item in areas:
                if not proxy_areas or str(area_item["id"]) in proxy_areas:
                    self.active_area_id = str(area_item["id"])
                    break
            if not self.active_area_id and areas:
                self.active_area_id = str(areas[0]["id"])

        self._bind_speaker_listener()
        self._bind_local_reconnect_listener()
        self._bind_weather_listener()
        self._bind_alarm_listener()
        self._bind_presence_listener()
        self._bind_remotes_listener()
        self._bind_room_entities_listener()

        self._unsub_play_interceptor = self.hass.bus.async_listen(
            EVENT_CALL_SERVICE, self._async_on_service_call_event
        )

        if self.native_ble_tracking_enabled:
            self._ble_tracker = LatterNativeBleTracker(
                hass=self.hass,
                beacon_uuid=self.ble_beacon_uuid,
                device_slug=self.device_slug,
                on_area_detected=self._async_on_native_ble_area_detected,
                room_offsets=self.ble_room_offsets,
            )
            self._ble_tracker.async_start()

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
        self._bind_wallpaper_cycle_timer()
        try:
            from .repairs import async_audit_coordinator_health

            async_audit_coordinator_health(self.hass, self)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Repairs audit skipped: %s", err)
        try:
            from .repairs import async_audit_coordinator_health

            async_audit_coordinator_health(self.hass, self)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Repairs audit skipped: %s", err)

    async def async_shutdown(self) -> None:
        """Clean up all subscriptions and timers."""
        if self._ble_tracker is not None:
            self._ble_tracker.async_stop()
            self._ble_tracker = None

        for unsub in (
            self._unsub_speaker_state,
            self._unsub_local_reconnect,
            self._unsub_play_interceptor,
            self._unsub_weather_state,
            self._unsub_alarm_state,
            self._unsub_presence_state,
            self._unsub_remotes_state,
            self._unsub_room_entities_state,
            self._unsub_room_debounce,
            self._unsub_position_timer,
            self._unsub_forecast_timer,
            self._unsub_calendar_timer,
            self._unsub_wallpaper_timer,
        ):
            if unsub is not None:
                unsub()
        self._unsub_speaker_state = None
        self._unsub_local_reconnect = None
        self._unsub_play_interceptor = None
        self._unsub_weather_state = None
        self._unsub_alarm_state = None
        self._unsub_presence_state = None
        self._unsub_remotes_state = None
        self._unsub_room_entities_state = None
        self._unsub_room_debounce = None
        self._unsub_position_timer = None
        self._unsub_forecast_timer = None
        self._unsub_calendar_timer = None
        self._unsub_wallpaper_timer = None
        self._listeners.clear()

    @callback
    def _bind_room_entities_listener(self) -> None:
        """Subscribe to state changes on all curated entities in the active room for live two-way sync."""
        if self._unsub_room_entities_state is not None:
            self._unsub_room_entities_state()
            self._unsub_room_entities_state = None

        room_items = get_area_entities(
            self.hass,
            area_id=self.active_area_id,
            domain_filter="all",
            custom_entities=self.custom_entities,
            local_speaker=self.local_speaker,
        )
        tracked_ids = [str(it["id"]) for it in room_items if it.get("id")]
        if not tracked_ids:
            return

        self._unsub_room_entities_state = async_track_state_change_event(
            self.hass,
            tracked_ids,
            self._async_on_room_entity_state_change,
        )

    @callback
    def _async_on_room_entity_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Debounce active room entity state changes (250ms) and push updated room slots to ESPHome."""
        self._notify_listeners()
        if self._unsub_room_debounce is not None:
            self._unsub_room_debounce()
            self._unsub_room_debounce = None

        @callback
        def _push_room_update(_now: datetime) -> None:
            self._unsub_room_debounce = None
            if self.on_area_changed_push_slots is not None:
                self.hass.async_create_task(
                    self.on_area_changed_push_slots(self)
                )

        self._unsub_room_debounce = async_call_later(
            self.hass, 0.25, _push_room_update
        )

    @callback
    def _bind_local_reconnect_listener(self) -> None:
        """Watch the ESPHome device's local media_player for unavailable -> online transitions (OTA / Hibernate wake)."""
        if self._unsub_local_reconnect is not None:
            self._unsub_local_reconnect()
            self._unsub_local_reconnect = None

        local_spk = self.local_speaker
        if not local_spk:
            return

        self._unsub_local_reconnect = async_track_state_change_event(
            self.hass,
            [local_spk],
            self._async_on_local_device_state_change,
        )

    @callback
    def _async_on_local_device_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Trigger automatic full state resync when the ESPHome device reconnects from unavailable."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if new_state.state in (STATE_PLAYING, STATE_BUFFERING):
            self._local_needs_cold_resume = False

        was_offline = old_state is None or old_state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        )
        is_now_online = new_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        )
        if was_offline and is_now_online:
            self._local_needs_cold_resume = True
            _LOGGER.info(
                "ESPHome device '%s' (%s) reconnected (%s -> %s); scheduling full state & slot resync",
                self.device_slug,
                event.data.get("entity_id"),
                old_state.state if old_state else "none",
                new_state.state,
            )
            self.hass.async_create_task(self._async_handle_device_reconnect())

    @callback
    def _enforce_local_speaker_if_remote_idle(self, reason: str) -> None:
        """Reset active_speaker to local_speaker on boot/wake unless the remote speaker is actively playing."""
        local_spk = self.local_speaker
        if not local_spk or self.active_speaker == local_spk:
            return

        remote_state = self.hass.states.get(self.active_speaker)
        is_remote_playing = bool(
            remote_state and remote_state.state in (STATE_PLAYING, STATE_BUFFERING)
        )
        if not is_remote_playing:
            _LOGGER.info(
                "Resetting active_speaker from idle remote '%s' (state=%s) to local_speaker '%s' (%s)",
                self.active_speaker,
                remote_state.state if remote_state else "none",
                local_spk,
                reason,
            )
            self.last_speaker = self.active_speaker
            self.active_speaker = local_spk
            self._bind_speaker_listener()
            self._schedule_persist_runtime_state()

    async def _async_handle_device_reconnect(self) -> None:
        """Reset idle remote speaker, sync BLE room lock, and push active room slots after ESPHome boot/wake."""
        self._enforce_local_speaker_if_remote_idle("device_reconnect")
        if self._ble_tracker is not None:
            self._ble_tracker.reset_for_device_wake()
            if (
                self._ble_tracker.current_area_id
                and self._ble_tracker.current_area_id != self.active_area_id
            ):
                self.async_set_active_area(
                    self._ble_tracker.current_area_id,
                    handoff_media=False,
                    sync_device_registry=True,
                )
        self._notify_listeners()
        await asyncio.sleep(1.5)
        self._enforce_local_speaker_if_remote_idle("device_reconnect_post_delay")
        if (
            self._ble_tracker is not None
            and self._ble_tracker.current_area_id
            and self._ble_tracker.current_area_id != self.active_area_id
        ):
            self.async_set_active_area(
                self._ble_tracker.current_area_id,
                handoff_media=False,
                sync_device_registry=True,
            )
        self._notify_listeners()
        if self.on_area_changed_push_slots is not None:
            await self.on_area_changed_push_slots(self)
        await asyncio.sleep(2.0)
        if self.on_area_changed_push_slots is not None:
            await self.on_area_changed_push_slots(self)

    @callback
    def _async_on_service_call_event(self, event: Event) -> None:
        """Intercept direct media_player.media_play / media_play_pause on an idle local Sendspin speaker after cold boot."""
        if not self._local_needs_cold_resume:
            return
        if time.monotonic() < self._resuming_guard_until:
            return
        if event.data.get("domain") != "media_player":
            return
        service = event.data.get("service")
        if service not in ("media_play", "media_play_pause"):
            return

        sdata = event.data.get("service_data") or {}
        targets = sdata.get(ATTR_ENTITY_ID)
        if isinstance(targets, str):
            targets = [targets]
        elif not isinstance(targets, list):
            return

        local_spk = self.local_speaker
        if local_spk not in targets and f"media_player.{self.device_slug}" not in targets:
            return

        target_spk = local_spk if local_spk in targets else f"media_player.{self.device_slug}"
        state_obj = self.hass.states.get(target_spk)
        if state_obj is not None and state_obj.state in (STATE_IDLE, STATE_OFF):
            self._resuming_guard_until = time.monotonic() + 3.0
            self.hass.async_create_task(
                self._async_resume_idle_speaker_queue(target_spk)
            )

    async def _async_find_queue_resume_item(
        self, speaker_entity_id: str
    ) -> tuple[str, float]:
        """Query Music Assistant (controller or get_queue) for the current queue item URI and position, falling back to persisted store."""
        ma_entity = (
            _resolve_ma_counterpart_entity(
                self.hass, speaker_entity_id, self.device_slug
            )
            or speaker_entity_id
        )

        mass = _get_mass_client(self.hass)
        if mass is not None and hasattr(mass, "player_queues"):
            try:
                for q in mass.player_queues.all() if callable(getattr(mass.player_queues, "all", None)) else []:
                    q_dict = q.to_dict() if hasattr(q, "to_dict") else {}
                    q_name = str(q_dict.get("display_name") or "").lower().replace("-", "_")
                    if self.device_slug in q_name or q_dict.get("queue_id") in ma_entity:
                        cur_item = q_dict.get("current_item") or {}
                        media_item = cur_item.get("media_item") or {}
                        uri = str(media_item.get("uri") or cur_item.get("uri") or "")
                        pos = float(q_dict.get("elapsed_time") or self.last_media_position or 0.0)
                        if uri:
                            return uri, pos
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Direct mass.player_queues resume lookup failed: %s", err)

        if self.hass.services.has_service("music_assistant", "get_queue"):
            try:
                resp = await self.hass.services.async_call(
                    "music_assistant",
                    "get_queue",
                    {ATTR_ENTITY_ID: ma_entity},
                    blocking=True,
                    return_response=True,
                )
                if isinstance(resp, dict):
                    q_data = resp.get(ma_entity) or resp
                    if isinstance(q_data, dict):
                        cur_item = q_data.get("current_item") or q_data.get("next_item") or {}
                        if isinstance(cur_item, dict):
                            media_item = cur_item.get("media_item") or {}
                            uri = str(
                                (media_item.get("uri") if isinstance(media_item, dict) else "")
                                or cur_item.get("uri")
                                or cur_item.get("media_content_id")
                                or ""
                            )
                            pos = float(
                                q_data.get("elapsed_time")
                                or self.last_media_position
                                or 0.0
                            )
                            if uri:
                                return uri, pos
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("music_assistant.get_queue resume lookup failed: %s", err)

        return self.last_media_uri, self.last_media_position

    async def _async_resume_idle_speaker_queue(
        self, speaker_entity_id: str
    ) -> None:
        """Resume playback on an idle speaker only if native media_play does not start within 2.2s after cold boot."""
        self._resuming_guard_until = time.monotonic() + 3.5

        await asyncio.sleep(2.2)
        cur_state = self.hass.states.get(speaker_entity_id)
        if cur_state is not None and cur_state.state in (STATE_PLAYING, STATE_BUFFERING):
            self._local_needs_cold_resume = False
            return

        ma_entity = _resolve_ma_counterpart_entity(
            self.hass, speaker_entity_id, self.device_slug
        )

        if ma_entity and ma_entity != speaker_entity_id:
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "media_play",
                    {ATTR_ENTITY_ID: ma_entity},
                    blocking=True,
                )
                await asyncio.sleep(1.0)
                cur_state = self.hass.states.get(speaker_entity_id)
                if cur_state is not None and cur_state.state in (STATE_PLAYING, STATE_BUFFERING):
                    self._local_needs_cold_resume = False
                    return
            except Exception:  # noqa: BLE001
                pass

        resume_uri, resume_pos = await self._async_find_queue_resume_item(
            speaker_entity_id
        )
        if not resume_uri:
            _LOGGER.debug(
                "No resumable queue URI found for idle speaker '%s'",
                speaker_entity_id,
            )
            return

        play_target = ma_entity or speaker_entity_id
        self._local_needs_cold_resume = False
        _LOGGER.info(
            "Re-streaming post-reboot queue URI '%s' (pos=%.1fs) to '%s'",
            resume_uri,
            resume_pos,
            play_target,
        )

        try:
            if self.hass.services.has_service("music_assistant", "play_media") and (
                ma_entity or (is_music_assistant_player(self.hass, cur_state) if cur_state else False)
            ):
                await self.hass.services.async_call(
                    "music_assistant",
                    "play_media",
                    {
                        ATTR_ENTITY_ID: play_target,
                        "media_id": resume_uri,
                    },
                    blocking=True,
                )
            else:
                await self.hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        ATTR_ENTITY_ID: play_target,
                        "media_content_id": resume_uri,
                        "media_content_type": self.last_media_type or "music",
                    },
                    blocking=True,
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Post-reboot play_media failed on %s: %s", play_target, err)
            return

        if resume_pos > 5.0:
            await asyncio.sleep(1.2)
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "media_seek",
                    {
                        ATTR_ENTITY_ID: speaker_entity_id,
                        "seek_position": round(resume_pos, 1),
                    },
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                pass

        self._notify_listeners()

    async def async_execute_media_command(
        self,
        command: str,
        speaker: str | None = None,
        seek_position: float | None = None,
        media_id: str | None = None,
        media_type: str | None = None,
        enqueue: str | None = None,
    ) -> None:
        """Execute a unified media playback command with 2.5s play debounce and post-reboot Sendspin queue recovery."""
        target_spk = (speaker or self.active_speaker or self.local_speaker).strip()
        if not target_spk:
            return

        cmd = command.strip().lower()
        state_obj = self.hass.states.get(target_spk)
        cur_state = state_obj.state if state_obj else STATE_IDLE

        if cmd == "toggle":
            cmd = (
                "pause"
                if cur_state in (STATE_PLAYING, STATE_BUFFERING)
                else "play"
            )

        if cmd == "play_media" and media_id:
            self._local_needs_cold_resume = False
            ma_target = _resolve_ma_counterpart_entity(
                self.hass, target_spk, self.device_slug
            )
            if (
                ma_target
                and self.hass.services.has_service("music_assistant", "play_media")
            ):
                payload: dict[str, Any] = {
                    ATTR_ENTITY_ID: ma_target,
                    "media_id": media_id,
                }
                if media_type:
                    payload["media_type"] = media_type
                if enqueue:
                    payload["enqueue"] = enqueue
                await self.hass.services.async_call(
                    "music_assistant", "play_media", payload, blocking=False
                )
            else:
                await self.hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        ATTR_ENTITY_ID: target_spk,
                        "media_content_id": media_id,
                        "media_content_type": media_type or "music",
                    },
                    blocking=False,
                )
            return

        if cmd == "play":
            now = time.monotonic()
            if now < self._resuming_guard_until:
                return
            self._resuming_guard_until = now + 2.5
            await self.hass.services.async_call(
                "media_player",
                "media_play",
                {ATTR_ENTITY_ID: target_spk},
                blocking=False,
            )
            is_local = target_spk in (
                self.local_speaker,
                f"media_player.{self.device_slug}",
            )
            if is_local and self._local_needs_cold_resume and cur_state in (
                STATE_IDLE,
                STATE_OFF,
                "stopped",
            ):
                await self._async_resume_idle_speaker_queue(target_spk)
            return

        if cmd == "pause":
            await self.hass.services.async_call(
                "media_player",
                "media_pause",
                {ATTR_ENTITY_ID: target_spk},
                blocking=False,
            )
            return

        if cmd in ("next", "next_track", "media_next_track"):
            await self.hass.services.async_call(
                "media_player",
                "media_next_track",
                {ATTR_ENTITY_ID: target_spk},
                blocking=False,
            )
            return

        if cmd in ("previous", "previous_track", "media_previous_track"):
            await self.hass.services.async_call(
                "media_player",
                "media_previous_track",
                {ATTR_ENTITY_ID: target_spk},
                blocking=False,
            )
            return

        if cmd == "stop":
            await self.hass.services.async_call(
                "media_player",
                "media_stop",
                {ATTR_ENTITY_ID: target_spk},
                blocking=False,
            )
            return

        if cmd == "clear_queue":
            await self.hass.services.async_call(
                "media_player",
                "clear_playlist",
                {ATTR_ENTITY_ID: target_spk},
                blocking=False,
            )
            return

        if cmd == "seek" and seek_position is not None:
            await self.hass.services.async_call(
                "media_player",
                "media_seek",
                {
                    ATTR_ENTITY_ID: target_spk,
                    "seek_position": round(float(seek_position), 1),
                },
                blocking=False,
            )

    @callback
    def _async_on_native_ble_area_detected(
        self, area_id: str, scanner_source: str
    ) -> None:
        """Handle room transition detected by Latter's native ESPHome BLE proxy tracker."""
        if not self.ble_auto_switch_enabled:
            self._notify_listeners()
            return
        if area_id and area_id != self.active_area_id:
            _LOGGER.info(
                "Native BLE Proxy ('%s') detected '%s' in area '%s' (was '%s')",
                scanner_source,
                self.device_slug,
                area_id,
                self.active_area_id,
            )
            self.async_set_active_area(
                area_id, handoff_media=False, sync_device_registry=True
            )
        else:
            self._notify_listeners()

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

    async def _async_execute_ma_queue_transfer(
        self,
        source_speaker: str,
        target_speaker: str,
        was_playing: bool,
        handoff_position: float,
        media_content_id: str,
        media_content_type: str,
    ) -> None:
        """Execute Music Assistant 2.10.8+ queue transfer, quiesce local Sendspin speaker, and verify position handoff."""
        src_state = self.hass.states.get(source_speaker)
        tgt_state = self.hass.states.get(target_speaker)
        src_is_ma = bool(src_state and is_music_assistant_player(self.hass, src_state))
        tgt_is_ma = bool(tgt_state and is_music_assistant_player(self.hass, tgt_state))
        is_from_local = source_speaker in (
            self.local_speaker,
            f"media_player.{self.device_slug}",
        )

        transferred_via_ma = False
        if src_is_ma and tgt_is_ma and self.hass.services.has_service("music_assistant", "transfer_queue"):
            try:
                await self.hass.services.async_call(
                    "music_assistant",
                    "transfer_queue",
                    {
                        ATTR_ENTITY_ID: target_speaker,
                        "source_player": source_speaker,
                        "auto_play": bool(was_playing),
                    },
                    blocking=True,
                )
                transferred_via_ma = True
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("music_assistant.transfer_queue failed: %s", err)

        if is_from_local and source_speaker != target_speaker:
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "media_pause",
                    {ATTR_ENTITY_ID: source_speaker},
                    blocking=False,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Failed quiescing local speaker %s: %s", source_speaker, err)

        if not transferred_via_ma and media_content_id:
            try:
                if not is_from_local:
                    await self.hass.services.async_call(
                        "media_player",
                        "media_pause",
                        {ATTR_ENTITY_ID: source_speaker},
                        blocking=False,
                    )
                if tgt_is_ma and self.hass.services.has_service("music_assistant", "play_media"):
                    await self.hass.services.async_call(
                        "music_assistant",
                        "play_media",
                        {
                            ATTR_ENTITY_ID: target_speaker,
                            "media_id": media_content_id,
                            "enqueue": "replace",
                        },
                        blocking=True,
                    )
                else:
                    await self.hass.services.async_call(
                        "media_player",
                        "play_media",
                        {
                            ATTR_ENTITY_ID: target_speaker,
                            "media_content_id": media_content_id,
                            "media_content_type": media_content_type or "music",
                        },
                        blocking=True,
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Fallback play_media handoff failed: %s", err)

        await asyncio.sleep(1.2)
        updated_tgt = self.hass.states.get(target_speaker)
        if updated_tgt is None:
            return

        if was_playing and updated_tgt.state in (STATE_PAUSED, STATE_IDLE):
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "media_play",
                    {ATTR_ENTITY_ID: target_speaker},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                pass

        tgt_pos = float(updated_tgt.attributes.get("media_position") or 0.0)
        if handoff_position > 5.0 and abs(tgt_pos - handoff_position) > 4.0:
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "media_seek",
                    {
                        ATTR_ENTITY_ID: target_speaker,
                        "seek_position": round(handoff_position, 1),
                    },
                    blocking=False,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Position handoff media_seek failed: %s", err)

        self._notify_listeners()

    @callback
    def async_set_active_speaker(
        self, speaker_entity_id: str, transfer_queue: bool = True
    ) -> None:
        """Switch the active target speaker, persist to Store, and optionally transfer active queue."""
        speaker_entity_id = speaker_entity_id.strip()
        if not speaker_entity_id:
            return

        prev_speaker = self.active_speaker
        if speaker_entity_id != prev_speaker:
            prev_state = self.hass.states.get(prev_speaker)
            was_playing = bool(
                prev_state and prev_state.state in (STATE_PLAYING, STATE_BUFFERING)
            )
            was_active = bool(
                prev_state and prev_state.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
            )
            handoff_pos = _interpolate_speaker_position(prev_state)

            if was_active and prev_state is not None:
                p_attrs = prev_state.attributes
                self._transfer_hold_until = time.monotonic() + TRANSFER_HOLD_WINDOW_SECONDS
                self._transfer_hold_position = handoff_pos
                self._transfer_hold_title = str(p_attrs.get("media_title") or "")
                self._transfer_hold_artist = str(
                    p_attrs.get("media_artist")
                    or p_attrs.get("media_series_title")
                    or p_attrs.get("media_album_artist")
                    or ""
                )
                self._transfer_hold_album = str(p_attrs.get("media_album_name") or "")
                self._transfer_hold_duration = float(p_attrs.get("media_duration") or 0.0)

                if transfer_queue:
                    media_cid = str(p_attrs.get("media_content_id") or self.last_media_uri or "")
                    media_ctype = str(p_attrs.get("media_content_type") or self.last_media_type or "music")
                    self.hass.async_create_task(
                        self._async_execute_ma_queue_transfer(
                            source_speaker=prev_speaker,
                            target_speaker=speaker_entity_id,
                            was_playing=was_playing,
                            handoff_position=handoff_pos,
                            media_content_id=media_cid,
                            media_content_type=media_ctype,
                        )
                    )

            self.last_speaker = prev_speaker
            self.active_speaker = speaker_entity_id
            self._schedule_persist_runtime_state()
            _LOGGER.debug(
                "Latter active speaker changed: %s -> %s (transfer_queue=%s, pos=%.1fs)",
                self.last_speaker,
                self.active_speaker,
                transfer_queue,
                handoff_pos,
            )

        self._bind_speaker_listener()
        self._notify_listeners()

    @callback
    def async_set_active_area(
        self,
        area_id_or_name: str,
        handoff_media: bool | None = None,
        sync_device_registry: bool = False,
    ) -> None:
        """Switch active room area, persist to Store, sync ESPHome device area, and hand off media."""
        matched_id = match_area_by_name_or_id(self.hass, area_id_or_name)
        if not matched_id:
            return
        self.active_area_id = matched_id
        self._bind_room_entities_listener()

        if sync_device_registry and self.sync_device_area_enabled:
            sync_esphome_device_area(
                self.hass,
                self.device_slug,
                matched_id,
                require_ble_proxy_area=True,
            )

        media_map = find_area_media_entities(
            self.hass, matched_id, self.local_speaker
        )
        if media_map["remote"]:
            self.active_remote = media_map["remote"]

        for slot_idx, slot_info in enumerate(self.get_remote_slots(), start=1):
            if slot_info["area_id"] == matched_id:
                self.active_remote_slot = slot_idx
                break

        self._schedule_persist_runtime_state()

        do_handoff = (
            self.area_handoff_enabled
            if handoff_media is None
            else bool(handoff_media)
        )
        if do_handoff and media_map["speaker"]:
            prev_state = self.hass.states.get(self.active_speaker)
            auto_transfer = bool(
                sync_device_registry
                and prev_state
                and prev_state.state == STATE_PLAYING
                and self.active_speaker != self.local_speaker
            )
            self.async_set_active_speaker(
                media_map["speaker"], transfer_queue=auto_transfer
            )
        else:
            self._notify_listeners()

        if self.on_area_changed_push_slots is not None:
            self.hass.async_create_task(
                self.on_area_changed_push_slots(self)
            )

    def get_remote_slots(self) -> list[dict[str, str]]:
        """Return the 4 resolved TV/Media Remote slot dictionaries."""
        keys = (CONF_REMOTE_1, CONF_REMOTE_2, CONF_REMOTE_3, CONF_REMOTE_4)
        return [
            resolve_remote_slot_pair(self.hass, self.get_opt(k))
            for k in keys
        ]

    def get_remote_config_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_remote_config."""
        slots = self.get_remote_slots()
        populated_count = sum(
            1 for s in slots if s["remote_entity"] or s["media_player_entity"]
        )
        attrs: dict[str, Any] = {
            "active_slot": self.active_remote_slot,
            "configured_count": populated_count,
        }
        summary_parts: list[str] = []
        for idx, slot in enumerate(slots, start=1):
            attrs[f"slot_{idx}_name"] = slot["name"]
            attrs[f"slot_{idx}_remote"] = slot["remote_entity"]
            attrs[f"slot_{idx}_media_player"] = slot["media_player_entity"]
            attrs[f"slot_{idx}_area_id"] = slot["area_id"]
            attrs[f"slot_{idx}_state"] = slot["state"]
            summary_parts.append(
                f"{idx}:{slot['name']}:{slot['remote_entity']}:{slot['media_player_entity']}:{slot['state']}"
            )

        active_slot_data = slots[max(0, min(3, self.active_remote_slot - 1))]
        state_str = active_slot_data["name"] if populated_count > 0 else "None"
        attrs["slots_summary"] = ";".join(summary_parts)
        return state_str, attrs

    def get_room_context_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_room_context."""
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
            local_speaker=self.local_speaker,
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
        climate_telemetry = get_area_climate_telemetry(
            self.hass, self.active_area_id, self.device_slug
        )
        alarm_info = get_home_alarm_summary(
            self.hass, self.get_opt(CONF_ALARM_ENTITY)
        )

        summary_items = [
            f"{e['id']}:{e['name']}:{int(e['active'])}:{e['level']}"
            for e in entities[:8]
        ]

        pres_ent = self.presence_entity
        if pres_ent and self.hass.states.get(pres_ent):
            pres_state = self.hass.states.get(pres_ent).state
        elif self._ble_tracker and self._ble_tracker.current_area_id:
            pres_state = f"native_ble:{self._ble_tracker.current_area_id}"
        else:
            pres_state = "none"

        return area_name, {
            "site_id": self.site_id,
            "area_id": self.active_area_id or "",
            "area_name": area_name,
            "device_profile": self.device_profile,
            "vpn_enabled": self.vpn_enabled,
            "vpn_client_ip": self.vpn_client_ip,
            "display_shape": self.display_shape,
            "default_page_size": self.default_page_size,
            "dock_apps": self.dock_apps_csv,
            "wallpaper_url": self.build_wallpaper_url(),
            "companion_url": self.build_companion_url(),
            "entity_count": len(entities),
            "lights_on": lights_on,
            "covers_open": covers_open,
            "room_temp": climate_telemetry["temperature"],
            "room_humidity": climate_telemetry["humidity"],
            "area_speaker": media_map["speaker"] or self.active_speaker,
            "area_remote": media_map["remote"] or self.active_remote,
            "alarm_entity": alarm_info["entity_id"],
            "alarm_state": alarm_info["state"],
            "alarm_name": alarm_info["name"],
            "alarm_code_required": alarm_info["code_arm_required"],
            "native_ble_tracking": self.native_ble_tracking_enabled,
            "ble_beacon_uuid": self.ble_beacon_uuid,
            "ble_closest_proxy": self._ble_tracker.closest_scanner if self._ble_tracker else "",
            "ble_packets_seen": self._ble_tracker.packets_seen if self._ble_tracker else 0,
            "ble_rssi_by_room": self._ble_tracker.get_live_rssi_summary() if self._ble_tracker else {},
            "ble_room_offsets": self.ble_room_offsets,
            "ble_scanners_map": get_all_scanners_diagnostic_map(self.hass),
            "ble_target_macs": self._ble_tracker.target_macs_formatted if self._ble_tracker else [],
            "presence_entity": pres_ent or "",
            "presence_state": pres_state,
            "ble_auto_switch": self.ble_auto_switch_enabled,
            "voice_area_synced": self.sync_device_area_enabled,
            "entities_summary": ";".join(summary_items) if summary_items else "NONE",
            "camera_entity": self.camera_entity or "",
            "camera_snapshot_url": self.build_camera_snapshot_url() if self.camera_entity else "none",
            "alert_id": self.alert_id,
            "alert_title": self.alert_title,
            "alert_message": self.alert_message,
            "alert_priority": self.alert_priority,
            "alert_duration": self.alert_duration,
            "alert_chime": self.alert_chime,
            "alert_camera_url": self.alert_camera_url,
            "custom_entities": self.custom_entities,
            "custom_bindings": self.custom_bindings,
            "custom_bindings_summary": self._build_custom_bindings_summary(),
        }

    @callback
    def _bind_speaker_listener(self) -> None:
        """Subscribe to state changes on the active media_player (and its volume override entity)."""
        if self._unsub_speaker_state is not None:
            self._unsub_speaker_state()
            self._unsub_speaker_state = None

        if not self.active_speaker:
            return

        tracked = [self.active_speaker]
        vol_target = self.get_volume_target_entity(self.active_speaker)
        if vol_target and vol_target != self.active_speaker:
            tracked.append(vol_target)

        self._unsub_speaker_state = async_track_state_change_event(
            self.hass,
            tracked,
            self._async_on_speaker_state_change,
        )
        self._update_position_timer_state()

    @callback
    def _bind_alarm_listener(self) -> None:
        """Subscribe to state changes on the home security alarm_control_panel entity."""
        if self._unsub_alarm_state is not None:
            self._unsub_alarm_state()
            self._unsub_alarm_state = None

        alarm_ent = self.alarm_entity
        if not alarm_ent:
            return

        self._unsub_alarm_state = async_track_state_change_event(
            self.hass,
            [alarm_ent],
            self._async_on_generic_state_change,
        )

    @callback
    def _bind_presence_listener(self) -> None:
        """Subscribe to external BLE trilateration room presence entity changes."""
        if self._unsub_presence_state is not None:
            self._unsub_presence_state()
            self._unsub_presence_state = None

        pres_ent = self.presence_entity
        if not pres_ent:
            return

        self._unsub_presence_state = async_track_state_change_event(
            self.hass,
            [pres_ent],
            self._async_on_presence_state_change,
        )

    @callback
    def _bind_remotes_listener(self) -> None:
        """Subscribe to state changes on the 4 configured TV remote slots."""
        if self._unsub_remotes_state is not None:
            self._unsub_remotes_state()
            self._unsub_remotes_state = None

        tracked: list[str] = []
        for slot in self.get_remote_slots():
            for key in ("remote_entity", "media_player_entity"):
                ent = slot.get(key)
                if ent and ent not in tracked:
                    tracked.append(ent)

        if not tracked:
            return

        self._unsub_remotes_state = async_track_state_change_event(
            self.hass,
            tracked,
            self._async_on_generic_state_change,
        )

    @callback
    def _async_on_generic_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Notify sensors when alarm or remote entities change state."""
        self._notify_listeners()

    @callback
    def _async_on_presence_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Auto-switch active room when external BLE presence sensor reports a new area."""
        new_state = event.data.get("new_state")
        if new_state is None or not self.ble_auto_switch_enabled:
            self._notify_listeners()
            return

        matched_area = match_area_by_name_or_id(self.hass, new_state.state)
        if matched_area and matched_area != self.active_area_id:
            _LOGGER.info(
                "BLE Presence ('%s' -> '%s') auto-switching '%s' to area '%s'",
                event.data.get("entity_id"),
                new_state.state,
                self.device_slug,
                matched_area,
            )
            self.async_set_active_area(
                matched_area, sync_device_registry=True
            )
        else:
            self._notify_listeners()

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

    def _read_volume_from_target(self, vol_target: str, fallback_attrs: dict[str, Any]) -> float:
        """Read normalized 0.0..1.0 volume from media_player, number, or input_number."""
        vol_state = self.hass.states.get(vol_target)
        if vol_state is not None and vol_state.state not in ("unavailable", "unknown"):
            if vol_state.domain in ("number", "input_number"):
                try:
                    val = float(vol_state.state)
                    min_v = float(vol_state.attributes.get("min", 0.0))
                    max_v = float(vol_state.attributes.get("max", 100.0))
                    if max_v > min_v:
                        return max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))
                except ValueError:
                    pass
            else:
                v_lvl = vol_state.attributes.get("volume_level")
                if v_lvl is not None:
                    return float(v_lvl)

        if fallback_attrs.get("volume_level") is not None:
            return float(fallback_attrs["volume_level"])
        return 0.7

    def get_active_media_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_active_media."""
        state_obj = self.hass.states.get(self.active_speaker)
        vol_target = self.get_volume_target_entity(self.active_speaker)

        if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return STATE_OFF, {
                "title": self.last_media_title or "Idle",
                "artist": self.last_media_artist or "None",
                "album": self.last_media_album or "None",
                "duration": round(self.last_media_duration, 1),
                "position": round(self.last_media_position, 1),
                "volume": 0.7,
                "media_type": self.last_media_type or "music",
                "supported_features": 0,
                "art_url": "none",
                "active_speaker": self.active_speaker,
                "last_speaker": self.last_speaker,
                "local_speaker": self.local_speaker,
                "volume_entity": vol_target,
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
        position = _interpolate_speaker_position(state_obj)

        raw_type = str(attrs.get("media_content_type") or "music").lower()
        if "podcast" in raw_type:
            media_type = "podcast"
        elif "audiobook" in raw_type or "book" in raw_type:
            media_type = "audiobook"
        else:
            media_type = "music"

        if title != "Idle" and state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING):
            cid = str(attrs.get("media_content_id") or "")
            if cid:
                self.last_media_uri = cid
            self.last_media_type = media_type
            self.last_media_title = title
            self.last_media_artist = artist
            self.last_media_album = album
            if duration > 0:
                self.last_media_duration = duration
            if position > 0:
                self.last_media_position = position
            self._schedule_persist_runtime_state()

        in_transfer_window = time.monotonic() < self._transfer_hold_until
        if in_transfer_window:
            if title == "Idle" and self._transfer_hold_title:
                title = self._transfer_hold_title
                artist = self._transfer_hold_artist or artist
                album = self._transfer_hold_album or album
                duration = self._transfer_hold_duration or duration
            if position < 1.0 and self._transfer_hold_position > 1.0:
                position = self._transfer_hold_position
        elif (
            title == "Idle"
            and state == STATE_IDLE
            and self.last_media_title
            and self.active_speaker == self.local_speaker
        ):
            title = self.last_media_title
            artist = self.last_media_artist or "None"
            album = self.last_media_album or "None"
            duration = self.last_media_duration
            position = self.last_media_position
            media_type = self.last_media_type or "music"

        volume = self._read_volume_from_target(vol_target, attrs)
        supported_features = int(attrs.get("supported_features") or 0)
        if vol_target != self.active_speaker:
            vol_state = self.hass.states.get(vol_target)
            if vol_state is not None:
                if vol_state.domain in ("number", "input_number"):
                    supported_features |= VOLUME_FEATURE_FLAGS
                else:
                    vol_feat = int(vol_state.attributes.get("supported_features") or 0)
                    supported_features |= vol_feat & VOLUME_FEATURE_FLAGS

        raw_pic = str(
            attrs.get("entity_picture_local")
            or attrs.get("entity_picture")
            or attrs.get("media_image_url")
            or ""
        )
        track_key = f"{title}|{artist}|{album}"

        if self.active_speaker == self.local_speaker or state == STATE_OFF or title == "Idle":
            art_url = "none"
        elif raw_pic:
            self.last_valid_raw_pic = raw_pic
            self._last_art_track_key = track_key
            self._last_art_proxy_url = self.build_proxy_art_url(
                f"{track_key}|{raw_pic}"
            )
            art_url = self._last_art_proxy_url
        elif (track_key == self._last_art_track_key or in_transfer_window) and self._last_art_proxy_url != "none":
            art_url = self._last_art_proxy_url
        else:
            art_url = "none"

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
            "last_speaker": self.last_speaker,
            "local_speaker": self.local_speaker,
            "volume_entity": vol_target,
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

    @callback
    def _bind_wallpaper_cycle_timer(self) -> None:
        """Start or stop the automatic favorite wallpaper rotation timer."""
        if self._unsub_wallpaper_timer is not None:
            self._unsub_wallpaper_timer()
            self._unsub_wallpaper_timer = None

        mins = self.wallpaper_cycle_minutes
        if mins > 0 and len(self.wallpaper_favorites) >= 2:
            self._unsub_wallpaper_timer = async_track_time_interval(
                self.hass,
                self._async_on_wallpaper_cycle_tick,
                timedelta(minutes=mins),
            )

    @callback
    def _async_on_wallpaper_cycle_tick(self, _now: datetime) -> None:
        """Advance to the next favorite wallpaper and notify listeners."""
        favs = self.wallpaper_favorites
        if len(favs) < 2:
            return
        cur = self.wallpaper_source
        try:
            idx = (favs.index(cur) + 1) % len(favs)
        except ValueError:
            idx = 0
        next_wp = favs[idx]
        merged = {
            **self.entry.data,
            **(self.entry.options or {}),
            CONF_WALLPAPER_SOURCE: next_wp,
        }
        self.hass.config_entries.async_update_entry(
            self.entry, data=merged, options=merged
        )
        self._notify_listeners()

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
        """Fetch daily weather forecast via weather.get_forecasts and format semicolon string."""
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