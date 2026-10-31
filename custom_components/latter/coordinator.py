"""State coordinator for Latter (Universal ESPHome Companion & Entity Middleware)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
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
    EVENT_CORE_CONFIG_UPDATE,
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
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .ble_engine import (
    LatterNativeBleTracker,
    get_all_scanners_diagnostic_map,
    get_ble_proxy_area_ids,
)
from .browse_engine import is_music_assistant_player
from .calendar_engine import async_fetch_calendar_agenda
from .const import (
    CALENDAR_REFRESH_INTERVAL_MINUTES,
    CONF_ALARM_ENTITY,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_ENTITY,
    CONF_GARAGE_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_THERMOSTAT_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_ASSIGNED_PERSON,
    CONF_ASSIGNED_ROLE,
    DEFAULT_ASSIGNED_ROLE,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BLE_AREA_OFFSETS,
    CONF_CALENDAR_ENTITIES,
    CONF_COMPANION_BASE_URL,
    CONF_CUSTOM_PALETTES,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DOORBELL_ANC_MODE,
    DEFAULT_DOORBELL_ANC_MODE,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    DEFAULT_DEVICE_GROUP,
    CONF_SITE_ID,
    CONF_VPN_CLIENT_IP,
    CONF_VPN_ENABLED,
    DEFAULT_SITE_ID,
    CONF_DISPLAY_SHAPE,
    CONF_DOCK_APPS,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    DEFAULT_DEVICE_REMOTE_GROUP,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_SYNC_DEVICE_AREA,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DEFAULT_AREA_FOLLOW_DWELL_S,
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
    EVENT_LATTER,
    FORECAST_REFRESH_INTERVAL_MINUTES,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    POSITION_UPDATE_INTERVAL_SECONDS,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    normalize_device_slug,
)
from .area_engine import (
    find_area_media_entities,
    find_esphome_device_id,
    get_area_available_domains,
    get_area_climate_telemetry,
    get_area_entities,
    get_home_alarm_summary,
    get_whole_home_summary,
    match_area_by_name_or_id,
    resolve_remote_slot_pair,
    sync_esphome_device_area,
)
from .media_engine import (
    async_find_queue_resume_item,
    async_play_media_with_ma_fallback,
    interpolate_speaker_position as _interpolate_speaker_position,
    resolve_esphome_local_speaker as _resolve_esphome_local_speaker,
    resolve_ma_counterpart_entity as _resolve_ma_counterpart_entity,
)

_LOGGER = logging.getLogger(__name__)

DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
TRANSFER_HOLD_WINDOW_SECONDS = 4.5
VOLUME_FEATURE_FLAGS = 4 | 8 | 1024  # VOLUME_SET | VOLUME_MUTE | VOLUME_STEP


def _pack_v3_payload(*fields: Any) -> str:
    """Pack domain state fields into an atomic Protocol v3 Unit-Separator ('\\x1f') string."""
    return "\x1f".join(
        ["v3"]
        + [
            str(f if f is not None else "").replace("\x1f", " ").replace("\x1e", " ")
            for f in fields
        ]
    )


def _get_esphome_device_current_area(
    hass: HomeAssistant, device_slug: str
) -> str | None:
    """Return the current area_id assigned to the ESPHome device in HA Device Registry."""
    dev_id = find_esphome_device_id(hass, device_slug)
    if not dev_id:
        return None
    dev = dr.async_get(hass).async_get(dev_id)
    return dev.area_id if dev and dev.area_id else None


def resolve_coordinator(
    hass: HomeAssistant,
    target: str | None = None,
    *,
    allow_fallback: bool = False,
) -> LatterCoordinator | None:
    """Resolve a loaded LatterCoordinator by entry_id, device_slug, or esphome_device_id."""
    domain_data = hass.data.get(DOMAIN, {})
    coords = [v for v in domain_data.values() if isinstance(v, LatterCoordinator)]
    if not coords:
        return None
    if target:
        raw = str(target).strip()
        norm = normalize_device_slug(raw)
        for coord in coords:
            if (
                coord.entry.entry_id == raw
                or coord.device_slug == norm
                or (coord.esphome_device_id and coord.esphome_device_id == raw)
            ):
                return coord
    if allow_fallback:
        return coords[0]
    return None


class LatterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages active speaker, BLE area context, 4-slot remotes, custom bindings, wallpapers, alarm, calendar, and weather."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hmac_secret: bytes,
    ) -> None:
        """Initialize the Latter coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            config_entry=entry,
        )
        self.entry = entry
        self._hmac_secret = hmac_secret
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )

        self._cached_lan_base_url: str | None = None
        self._cached_esphome_device_id: str | None = None
        self._cached_hw_manifest: tuple[str, dict[str, Any]] | None = None
        self._cached_media_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._cached_area_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._cached_remote_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._unsub_core_config: Callable[[], None] | None = None
        self._unsub_speaker_state: Callable[[], None] | None = None
        self._unsub_local_reconnect: Callable[[], None] | None = None
        self._unsub_play_interceptor: Callable[[], None] | None = None
        self._unsub_weather_state: Callable[[], None] | None = None
        self._unsub_alarm_state: Callable[[], None] | None = None
        self._unsub_presence_state: Callable[[], None] | None = None
        self._unsub_remotes_state: Callable[[], None] | None = None
        self._unsub_area_entities_state: Callable[[], None] | None = None
        self._unsub_area_debounce: Callable[[], None] | None = None
        self._unsub_position_timer: Callable[[], None] | None = None
        self._unsub_forecast_timer: Callable[[], None] | None = None
        self._unsub_calendar_timer: Callable[[], None] | None = None
        self._unsub_wallpaper_timer: Callable[[], None] | None = None
        self._unsub_doorbell_ring_state: Callable[[], None] | None = None
        self._unsub_area_follow_dwell: Callable[[], None] | None = None
        self._pending_follow_area_id: str | None = None
        self._doorbell_ring_map: dict[str, str] = {}
        self._doorbell_ring_cooldown_until: dict[str, float] = {}
        self._ble_tracker: LatterNativeBleTracker | None = None

        self.active_speaker: str = (
            str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip()
            or self.local_speaker
        )
        self.last_speaker: str = self.active_speaker
        self.active_area_id: str | None = self.get_opt(CONF_DEFAULT_AREA)
        self.active_remote: str = ""
        self.active_remote_slot: int = 1
        self.last_area_filter: str = "scene"
        self.last_area_page: int = 1
        self.on_area_changed_push_slots: Callable[[LatterCoordinator], Any] | None = None

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
        self.rev: int = 1
        self.alert_id: int = 0
        self.alert_title: str = ""
        self.alert_message: str = ""
        self.alert_priority: str = "normal"
        self.alert_duration: int = 8
        self.alert_chime: bool = True
        self.alert_camera_url: str = "none"
        self.active_camera_index: int = 0
        self.active_carousel_camera: str = ""
        self.doorbell_talk_state: str = "idle"
        self.doorbell_anc_mode: str = str(
            self.get_opt(CONF_DOORBELL_ANC_MODE, DEFAULT_DOORBELL_ANC_MODE) or DEFAULT_DOORBELL_ANC_MODE
        )
        self._configured_wallpaper_source: str = str(
            self.get_opt(CONF_WALLPAPER_SOURCE, "") or ""
        ).strip()
        self.current_wallpaper: str = ""
        self._structural_snapshot: dict[str, Any] = self._capture_structural_snapshot()

    def _capture_structural_snapshot(self) -> dict[str, Any]:
        """Capture a snapshot of structural config keys that require an entry reload when changed."""
        return {
            CONF_DEVICE_SLUG: self.device_slug,
            CONF_ESPHOME_DEVICE_ID: str(self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or "").strip(),
            CONF_DEVICE_PROFILE: self.device_profile,
            CONF_NATIVE_BLE_TRACKING: self.native_ble_tracking_enabled,
            CONF_BLE_BEACON_UUID: self.ble_beacon_uuid,
            CONF_BLE_TARGET_ADDRESS: self.ble_target_address,
            CONF_ASSIGNED_PERSON: self.assigned_person,
        }

    def has_structural_changes(self) -> bool:
        """Return True if any structural config key changed since setup."""
        return self._capture_structural_snapshot() != self._structural_snapshot

    async def async_apply_options(self) -> None:
        """Apply updated config entry options in-place without reloading the entry."""
        new_conf_wp = str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()
        if new_conf_wp != self._configured_wallpaper_source:
            self._configured_wallpaper_source = new_conf_wp
            self.current_wallpaper = new_conf_wp
            self._schedule_persist_runtime_state()
        elif self.current_wallpaper and self.wallpaper_favorites and self.current_wallpaper not in self.wallpaper_favorites and self.current_wallpaper != new_conf_wp:
            self.current_wallpaper = new_conf_wp
            self._schedule_persist_runtime_state()

        self.doorbell_anc_mode = str(
            self.get_opt(CONF_DOORBELL_ANC_MODE, DEFAULT_DOORBELL_ANC_MODE)
            or DEFAULT_DOORBELL_ANC_MODE
        )
        if self._ble_tracker is not None:
            self._ble_tracker.set_area_offsets(self.ble_area_offsets)
        self._bind_speaker_listener()
        self._bind_weather_listener()
        self._bind_alarm_listener()
        self._bind_presence_listener()
        self._bind_remotes_listener()
        self._bind_area_entities_listener()
        self._bind_doorbell_ring_listener()
        self._bind_wallpaper_cycle_timer()
        await self.async_refresh_weather_forecast()
        await self.async_refresh_calendar_agenda()
        self._notify_listeners()

    def get_opt(self, key: str, default: Any = None) -> Any:
        """Retrieve a setting, prioritizing System-Wide config for shared keys and entry options/data for device keys."""
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
        """Refresh listeners, BLE offsets, weather, and calendar when System-Wide config changes."""
        if self._ble_tracker is not None:
            self._ble_tracker.set_area_offsets(self.ble_area_offsets)
        self._bind_speaker_listener()
        self._bind_weather_listener()
        self._bind_alarm_listener()
        self._bind_remotes_listener()
        self._bind_area_entities_listener()
        self._bind_doorbell_ring_listener()
        await self.async_refresh_weather_forecast()
        await self.async_refresh_calendar_agenda()
        self._notify_listeners()

    @property
    def device_slug(self) -> str:
        """Return normalized ESPHome device slug, auto-healing from entry data or legacy unique_id if options were blanked."""
        raw = str(self.get_opt(CONF_DEVICE_SLUG, "") or "").strip()
        norm = normalize_device_slug(raw) if raw else "esphome_device"
        if norm == "esphome_device":
            orig_slug = str(self.entry.data.get(CONF_DEVICE_SLUG, "") or "").strip()
            if orig_slug and orig_slug != "esphome_device":
                return normalize_device_slug(orig_slug)
            uid = str(self.entry.unique_id or "")
            if uid.startswith(f"{DOMAIN}_") and ":" not in uid:
                recovered = normalize_device_slug(uid.removeprefix(f"{DOMAIN}_"))
                if recovered and recovered != "esphome_device":
                    return recovered
        return norm

    @property
    def esphome_device_id(self) -> str | None:
        """Return the Home Assistant Device Registry ID for the underlying ESPHome device."""
        dev_reg = dr.async_get(self.hass)
        if (
            self._cached_esphome_device_id
            and dev_reg.async_get(self._cached_esphome_device_id) is not None
        ):
            return self._cached_esphome_device_id
        stored = str(self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or "").strip()
        resolved = find_esphome_device_id(
            self.hass, self.device_slug, stored or None
        )
        self._cached_esphome_device_id = resolved
        return resolved

    def get_device_info(self) -> DeviceInfo:
        """Return canonical Latter DeviceInfo linked via via_device_id to the underlying ESPHome device."""
        esp_dev_id = self.esphome_device_id
        pretty_device = self.device_slug.replace("_", " ").title()
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=pretty_device,
            manufacturer="Lampton Labs",
            model="Latter ESPHome Companion Middleware",
            sw_version=INTEGRATION_VERSION,
            configuration_url="homeassistant://latter",
            **({"via_device_id": esp_dev_id} if esp_dev_id else {}),
        )

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

    def _read_device_hardware_manifest(self) -> dict[str, Any]:
        """Read compile-time hardware capability manifest reported by sensor.<slug>_system_hardware_manifest."""
        st = self.hass.states.get(f"sensor.{self.device_slug}_system_hardware_manifest")
        if st is not None and st.state and st.state.startswith("{"):
            raw_state = str(st.state)
            if self._cached_hw_manifest is not None and self._cached_hw_manifest[0] == raw_state:
                return self._cached_hw_manifest[1]
            try:
                import json

                parsed = json.loads(raw_state)
                if isinstance(parsed, dict):
                    self._cached_hw_manifest = (raw_state, parsed)
                    return parsed
            except Exception:  # noqa: BLE001
                pass
        return {}

    @property
    def hardware_manifest(self) -> dict[str, Any]:
        """Return parsed hardware capability manifest from the ESPHome device (or empty dict if offline)."""
        return self._read_device_hardware_manifest()

    @property
    def device_profile(self) -> str:
        """Return device archetype (auto-detected from hardware_manifest when unconfigured)."""
        hw_prof = str(self._read_device_hardware_manifest().get("profile") or "").strip()
        configured = str(self.get_opt(CONF_DEVICE_PROFILE, "") or "").strip()
        if hw_prof and (not configured or configured == DEFAULT_DEVICE_PROFILE):
            return hw_prof
        return configured or DEFAULT_DEVICE_PROFILE

    @property
    def device_group(self) -> str:
        """Return logical device group ID (defaults to 'unassigned' so no profile is assumed)."""
        raw = str(self.get_opt(CONF_DEVICE_GROUP, DEFAULT_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP).strip()
        if raw == "handhelds" and self.device_profile == "headless_node":
            return DEFAULT_DEVICE_GROUP
        return raw

    @property
    def display_shape(self) -> str:
        """Return display geometry ('circle' or 'square', auto-detected from hardware_manifest)."""
        hw_shape = str(self._read_device_hardware_manifest().get("shape") or "").strip().lower()
        if hw_shape in ("circle", "square"):
            return hw_shape
        return str(
            self.get_opt(CONF_DISPLAY_SHAPE, DEFAULT_DISPLAY_SHAPE)
        ).strip().lower()

    @property
    def default_page_size(self) -> int:
        """Return default area/entity pagination page size for this device's GUI."""
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
        """Return optional user-configured reverse proxy base URL (e.g. https://ha.example.com)."""
        return str(self.get_opt(CONF_COMPANION_BASE_URL, "") or "").strip().rstrip("/")

    @property
    def wallpaper_source(self) -> str:
        """Return active runtime wallpaper or configured photo wallpaper URL, preset ID, or /local/ path."""
        if self.current_wallpaper:
            return self.current_wallpaper
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
    def custom_palettes(self) -> list[dict[str, str]]:
        """Return system-wide custom color profiles saved in the System-Wide Color Library."""
        val = self.get_opt(CONF_CUSTOM_PALETTES, [])
        if not isinstance(val, list):
            return []
        out: list[dict[str, str]] = []
        for item in val:
            if isinstance(item, dict) and item.get("hex"):
                out.append(
                    {
                        "name": str(item.get("name") or item["hex"]).strip(),
                        "hex": str(item["hex"]).strip().upper(),
                    }
                )
        return out

    @property
    def device_custom_color(self) -> str:
        """Return the active custom hex color (#RRGGBB) for this device."""
        raw = str(self.get_opt(CONF_DEVICE_CUSTOM_COLOR, "") or "").strip().upper()
        if raw.startswith("#") and len(raw) == 7:
            return raw
        if self.custom_palettes:
            return self.custom_palettes[0]["hex"]
        return "#3898FF"

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
    def camera_entities(self) -> list[str]:
        """Return configured list of up to 10 camera entity_ids, plus any onboard ESPHome P4 cameras."""
        cleaned: list[str] = []
        raw_list = self.get_opt(CONF_CAMERA_ENTITIES)
        if isinstance(raw_list, list):
            cleaned = [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
        if not cleaned:
            single = str(self.get_opt(CONF_CAMERA_ENTITY) or "").strip()
            if single:
                cleaned = [single]
        # Auto-include any onboard ESPHome camera belonging to a Latter device (e.g. P4 Remote Assistant 5MP cam)
        domain_data = self.hass.data.get(DOMAIN, {})
        for val in domain_data.values():
            if hasattr(val, "device_slug"):
                for cand in (f"camera.{val.device_slug}", f"camera.{val.device_slug}_camera"):
                    if self.hass.states.get(cand) is not None and cand not in cleaned and len(cleaned) < 10:
                        cleaned.append(cand)
        return cleaned[:10]

    def _build_intercom_targets_summary(self) -> str:
        """Build semicolon-delimited 'target_id|Friendly Label;...' for Area-to-Area & SIP Speed-Dial calling."""
        rows: list[str] = ["all|Call All Areas"]
        domain_data = self.hass.data.get(DOMAIN, {})
        for val in domain_data.values():
            if hasattr(val, "device_slug") and getattr(val, "device_profile", "") != "ble_beacon":
                if val.device_slug != self.device_slug:
                    title = val.device_slug.replace("_", " ").title()[:24]
                    rows.append(f"{val.device_slug}|Call: {title}")
        raw_sd = str(self.get_opt("sip_speed_dials") or "").strip()
        if raw_sd:
            for item in raw_sd.split(","):
                item = item.strip()
                if not item:
                    continue
                if "|" in item:
                    lbl, uri = item.split("|", 1)
                    rows.append(f"{uri.strip()}|SIP: {lbl.strip()[:22]}")
                else:
                    rows.append(f"sip:{item}|SIP: {item[:22]}")
        return ";".join(rows[:10])

    @property
    def camera_entity(self) -> str | None:
        """Return configured primary doorbell/security camera entity_id (Slot 1)."""
        cams = self.camera_entities
        if cams:
            return cams[0]
        val = self.get_opt(CONF_CAMERA_ENTITY)
        return str(val).strip() if val else None

    def _build_cameras_summary(self) -> str:
        """Build semicolon-delimited 'entity_id|Friendly Name|signed_url;...' summary for up to 10 cameras."""
        rows: list[str] = []
        for ent_id in self.camera_entities[:10]:
            st = self.hass.states.get(ent_id)
            friendly = (
                str(st.attributes.get("friendly_name") if st else "")
                or ent_id.split(".", 1)[-1].replace("_", " ").title()
            )
            friendly = friendly.replace(";", "").replace("|", "")[:32]
            signed_url = self.build_camera_snapshot_url(ent_id)
            rows.append(f"{ent_id}|{friendly}|{signed_url}")
        return ";".join(rows) if rows else "NONE"

    @property
    def thermostat_entity(self) -> str | None:
        """Return configured primary system thermostat entity_id."""
        val = self.get_opt(CONF_THERMOSTAT_ENTITY)
        return str(val).strip() if val else None

    @property
    def lock_entity(self) -> str | None:
        """Return configured primary system lock entity_id."""
        val = self.get_opt(CONF_LOCK_ENTITY)
        return str(val).strip() if val else None

    @property
    def garage_entity(self) -> str | None:
        """Return configured primary garage door cover entity_id."""
        val = self.get_opt(CONF_GARAGE_ENTITY)
        return str(val).strip() if val else None

    @property
    def vacuum_entity(self) -> str | None:
        """Return configured primary robot vacuum entity_id."""
        val = self.get_opt(CONF_VACUUM_ENTITY)
        return str(val).strip() if val else None

    @property
    def native_ble_tracking_enabled(self) -> bool:
        """Return True if native ESPHome BLE proxy tracking is enabled."""
        return bool(
            self.get_opt(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)
        )

    @property
    def ble_beacon_uuid(self) -> str:
        """Return the iBeacon UUID broadcast by the device (migrating pre-v2.2 default UUIDs automatically)."""
        raw = str(
            self.get_opt(CONF_BLE_BEACON_UUID, DEFAULT_BLE_BEACON_UUID)
        ).strip()
        if not raw or raw.upper().startswith("504F434B-"):
            return DEFAULT_BLE_BEACON_UUID
        return raw

    @property
    def ble_target_address(self) -> str:
        """Return optional explicit BLE MAC, private_ble_device entity_id, or UUID for standalone BLE tracking."""
        return str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()

    @property
    def ble_area_offsets(self) -> dict[str, float]:
        """Return per-area BLE RSSI calibration offsets (area_id -> dB bias)."""
        raw = self.get_opt(CONF_BLE_AREA_OFFSETS, {})
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
        """Return configured external BLE area presence entity_id (e.g. Bermuda)."""
        val = self.get_opt(CONF_PRESENCE_ENTITY)
        return str(val) if val else None

    @property
    def assigned_person(self) -> str:
        """Return optional person.* entity_id assigned to this device."""
        val = self.get_opt(CONF_ASSIGNED_PERSON, "")
        return str(val or "").strip()

    @property
    def assigned_role(self) -> str:
        """Return RBAC role assigned to this device (admin, member, guest, kiosk_area_only)."""
        val = str(self.get_opt(CONF_ASSIGNED_ROLE, DEFAULT_ASSIGNED_ROLE) or DEFAULT_ASSIGNED_ROLE).strip().lower()
        return val if val in ("admin", "member", "guest", "kiosk_area_only") else DEFAULT_ASSIGNED_ROLE

    @property
    def ble_auto_switch_enabled(self) -> bool:
        """Return True if BLE presence changes should auto-switch active area."""
        return bool(self.get_opt(CONF_BLE_AUTO_SWITCH, DEFAULT_BLE_AUTO_SWITCH))

    @property
    def is_roaming_device(self) -> bool:
        """Return True only for portable/roaming displays (stationary == 0 in hardware manifest)."""
        hw = self.hardware_manifest
        if "stationary" in hw:
            try:
                return int(hw.get("stationary")) == 0
            except (ValueError, TypeError):
                pass
        return self.device_profile in ("mobile_display", "wearable_display")

    @property
    def sync_device_area_enabled(self) -> bool:
        """Return True if Voice Follows Me is enabled and this is a roaming device."""
        if not self.is_roaming_device:
            return False
        return bool(self.get_opt(CONF_SYNC_DEVICE_AREA, DEFAULT_SYNC_DEVICE_AREA))

    @property
    def area_follow_dwell_s(self) -> int:
        """Return required stability dwell time in seconds before BLE moves update ESPHome Device Area."""
        try:
            return max(
                0,
                int(
                    self.get_opt(
                        CONF_AREA_FOLLOW_DWELL_S, DEFAULT_AREA_FOLLOW_DWELL_S
                    )
                ),
            )
        except (ValueError, TypeError):
            return DEFAULT_AREA_FOLLOW_DWELL_S

    @property
    def volume_overrides(self) -> dict[str, str]:
        """Build speaker -> volume target dictionary from dynamic volume_overrides list."""
        mapping: dict[str, str] = {}
        raw_list = self.get_opt(CONF_VOLUME_OVERRIDES)
        if isinstance(raw_list, list):
            for item in raw_list[:10]:
                if isinstance(item, dict):
                    spk = str(item.get("speaker") or "").strip()
                    tgt = str(item.get("target") or "").strip()
                    if spk and tgt:
                        mapping[spk] = tgt
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
    def area_handoff_enabled(self) -> bool:
        """Return True if switching areas should hand off active speaker/remote context."""
        return bool(self.get_opt(CONF_AREA_HANDOFF, DEFAULT_AREA_HANDOFF))

    @property
    def art_size(self) -> str | int:
        """Return configured artwork resolution ('410x502' or integer square size like 466)."""
        raw = str(self.get_opt(CONF_ART_SIZE, DEFAULT_ART_SIZE) or DEFAULT_ART_SIZE).strip().lower()
        if "x" in raw:
            return raw
        try:
            return int(raw)
        except ValueError:
            return DEFAULT_ART_SIZE

    @property
    def art_dimensions(self) -> tuple[int, int]:
        """Return (width, height) in pixels for Baseline-JPEG transcoders (auto-detected from hardware_manifest or CONF_ART_SIZE)."""
        hw = self._read_device_hardware_manifest()
        try:
            hw_w = int(hw.get("w") or 0)
            hw_h = int(hw.get("h") or 0)
            if hw_w >= 64 and hw_h >= 64:
                return max(64, min(1920, hw_w)), max(64, min(1920, hw_h))
        except (ValueError, TypeError):
            pass
        raw = str(self.get_opt(CONF_ART_SIZE, DEFAULT_ART_SIZE) or DEFAULT_ART_SIZE).strip().lower()
        if "x" in raw:
            parts = raw.split("x", 1)
            try:
                w = max(64, min(1920, int(parts[0].strip())))
                h = max(64, min(1920, int(parts[1].strip())))
                return w, h
            except ValueError:
                return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        try:
            sq = max(64, min(1920, int(raw)))
            return sq, sq
        except ValueError:
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE

    _SIG_BUCKET_S = 86400

    def sign_resource(self, resource: str, ttl_s: int = 7 * 86400) -> str:
        """Generate a time-bounded, resource-scoped HMAC-SHA256 signature."""
        exp = ((int(time.time()) + ttl_s) // self._SIG_BUCKET_S + 1) * self._SIG_BUCKET_S
        msg = f"{self.entry.entry_id}|{resource}|{exp}".encode("utf-8")
        mac = hmac.new(self._hmac_secret, msg, hashlib.sha256).hexdigest()[:32]
        return f"{exp}.{mac}"

    def verify_resource(
        self,
        resource: str,
        sig: str | None = None,
    ) -> bool:
        """Verify a resource-scoped expiring signature."""
        if not sig:
            return False
        try:
            exp_s, mac = sig.split(".", 1)
            if int(exp_s) < int(time.time()):
                return False
        except ValueError:
            return False
        msg = f"{self.entry.entry_id}|{resource}|{exp_s}".encode("utf-8")
        expected = hmac.new(self._hmac_secret, msg, hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(mac, expected)

    def get_lan_base_url(self) -> str:
        """Resolve the numeric-IP LAN HTTP base URL and actual active HTTP port for ESP32 online_image clients."""
        if self._cached_lan_base_url:
            return self._cached_lan_base_url

        import socket
        from urllib.parse import urlparse

        active_port = getattr(getattr(self.hass, "http", None), "server_port", None)
        raw_url = ""
        try:
            raw_url = get_url(self.hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            raw_url = ""

        parsed = urlparse(raw_url) if raw_url else None
        host = (parsed.hostname or "") if parsed else ""
        port = parsed.port if (parsed and parsed.port) else active_port
        scheme = (parsed.scheme or "http") if parsed else "http"

        # ESP-IDF getaddrinfo cannot resolve .local mDNS hostnames without a DNS proxy;
        # always resolve .local or missing hosts to the HA server's numeric LAN IPv4 address.
        if not host or host.endswith(".local") or host == "localhost":
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("10.254.254.254", 1))
                    host = s.getsockname()[0]
            except Exception:  # noqa: BLE001
                host = host or "homeassistant.local"
            scheme = "http"
            port = active_port

        if port and not (
            (scheme == "http" and int(port) == 80)
            or (scheme == "https" and int(port) == 443)
        ):
            resolved = f"{scheme}://{host}:{int(port)}"
        else:
            resolved = f"{scheme}://{host}"
        self._cached_lan_base_url = resolved
        return resolved

    @callback
    def _async_on_core_config_update(self, _event: Event) -> None:
        """Invalidate cached LAN base URL when Home Assistant core network configuration updates."""
        self._cached_lan_base_url = None
        self.async_notify_listeners()

    def build_camera_snapshot_url(
        self, camera_entity_id: str | None = None, cache_bust: str = ""
    ) -> str:
        """Build the local LAN HTTP Baseline-JPEG camera snapshot URL for ESP32 online_image."""
        cam_ent = (camera_entity_id or self.camera_entity or "").strip()
        if not cam_ent:
            return "none"
        base_url = self.get_lan_base_url()
        w, h = self.art_dimensions
        sig = self.sign_resource(f"camera:{cam_ent}")
        v_tag = cache_bust or str(int(time.time()))
        return (
            f"{base_url}/api/latter/camera/{self.device_slug}"
            f"?entity_id={cam_ent}&w={w}&h={h}&shape={self.display_shape}&sig={sig}&v={v_tag}"
        )

    def build_map_snapshot_url(self, location: str) -> str:
        """Build the local LAN HTTP Baseline-JPEG map snapshot URL for a calendar event location."""
        from urllib.parse import quote_plus

        clean_loc = (location or "").strip()
        if not clean_loc:
            return "none"
        base_url = self.get_lan_base_url()
        w, h = self.art_dimensions
        sig = self.sign_resource(f"map:{clean_loc}")
        return (
            f"{base_url}/api/latter/map/{self.device_slug}"
            f"?w={w}&h={h}&shape={self.display_shape}&q={quote_plus(clean_loc)}&sig={sig}"
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
        self.hass.bus.async_fire(
            EVENT_LATTER,
            {
                "type": "notification_dispatched",
                "device_slug": self.device_slug,
                "title": self.alert_title,
                "message": self.alert_message,
                "priority": self.alert_priority,
                "camera_url": self.alert_camera_url,
            },
        )
        self._schedule_persist_runtime_state()
        self._notify_listeners()

    def build_wallpaper_url(self) -> str:
        """Build the device-scoped baseline-JPEG photo wallpaper URL (always local LAN HTTP for ESP32 online_image)."""
        if not self.wallpaper_source:
            return "none"
        base_url = self.get_lan_base_url()
        w, h = self.art_dimensions
        sig = self.sign_resource(f"wallpaper:{self.wallpaper_source}")
        digest = hashlib.md5(
            f"{self.wallpaper_source}|{self.display_shape}|{w}x{h}".encode("utf-8")
        ).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/wallpaper/{self.device_slug}"
            f"?w={w}&h={h}&shape={self.display_shape}&sig={sig}&v={digest}"
        )

    def build_proxy_art_url(self, cache_bust: str) -> str:
        """Build the universal Baseline-JPEG artwork URL (/api/latter/artwork/<device_slug>?w=...&h=...&sig=...&v=...)."""
        base_url = self.get_lan_base_url()
        w, h = self.art_dimensions
        sig = self.sign_resource("artwork")
        digest = hashlib.md5(cache_bust.encode("utf-8")).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/artwork/{self.device_slug}"
            f"?w={w}&h={h}&sig={sig}&v={digest}"
        )

    @callback
    def _schedule_persist_runtime_state(self) -> None:
        """Persist runtime speaker, area, remote slot, wallpaper, monotonic rev, alert_id, and last active track metadata to HA Store."""
        self._store.async_delay_save(
            lambda: {
                "rev": self.rev,
                "alert_id": self.alert_id,
                "active_speaker": self.active_speaker,
                "last_speaker": self.last_speaker,
                "active_area_id": self.active_area_id or "",
                "active_remote_slot": self.active_remote_slot,
                "current_wallpaper": self.current_wallpaper,
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
                self.rev = max(1, int(stored.get("rev") or 1))
                self.alert_id = max(0, int(stored.get("alert_id") or 0))
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
                if isinstance(saved_slot, int) and 1 <= saved_slot <= 10:
                    self.active_remote_slot = saved_slot
                saved_wp = str(stored.get("current_wallpaper") or "").strip()
                if saved_wp:
                    self.current_wallpaper = saved_wp
                self.last_media_uri = str(stored.get("last_media_uri") or "")
                self.last_media_type = str(stored.get("last_media_type") or "music")
                self.last_media_title = str(stored.get("last_media_title") or "")
                self.last_media_artist = str(stored.get("last_media_artist") or "")
                self.last_media_album = str(stored.get("last_media_album") or "")
                self.last_media_duration = float(stored.get("last_media_duration") or 0.0)
                self.last_media_position = float(stored.get("last_media_position") or 0.0)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed loading Latter runtime store: %s", err)
        self._structural_snapshot = self._capture_structural_snapshot()

        local_spk = self.local_speaker
        esphome_svcs = self.hass.services.async_services().get("esphome", {})
        has_media_ui = bool(local_spk) or any(
            s.endswith("_set_browse_slots") and self.device_slug in s
            for s in esphome_svcs
        )
        if not has_media_ui:
            # Headless / sensor-only device (e.g. Bed Presence): clear any accidentally inherited speaker
            self.active_speaker = ""
            self.last_speaker = ""
        else:
            if not self.active_speaker:
                self.active_speaker = local_spk
            # If CONF_DEFAULT_SPEAKER was previously auto-filled with an unrelated speaker (e.g. front_door_tablet)
            # while this device has its own local_speaker, reset to local_speaker when idle
            self._enforce_local_speaker_if_remote_idle("ha_startup")
            if not self.last_speaker:
                self.last_speaker = self.active_speaker

        proxy_areas = get_ble_proxy_area_ids(self.hass)

        pres_ent = self.presence_entity
        if pres_ent and self.ble_auto_switch_enabled:
            pres_state = self.hass.states.get(pres_ent)
            if pres_state is not None:
                matched = match_area_by_name_or_id(self.hass, pres_state.state)
                if matched:
                    self.active_area_id = matched

        explicit_default_area = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        if self.native_ble_tracking_enabled and not explicit_default_area:
            # Roaming BLE device without a fixed default area: never assume a non-proxy area from storage or alphabetical fallback!
            if self.active_area_id and proxy_areas and self.active_area_id not in proxy_areas:
                self.active_area_id = None
        elif not self.active_area_id:
            dev_area = _get_esphome_device_current_area(
                self.hass, self.device_slug
            )
            if dev_area:
                self.active_area_id = dev_area

        self._bind_speaker_listener()
        self._bind_local_reconnect_listener()
        self._bind_weather_listener()
        self._bind_alarm_listener()
        self._bind_presence_listener()
        self._bind_remotes_listener()
        self._bind_area_entities_listener()
        self._bind_doorbell_ring_listener()

        self._unsub_core_config = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._async_on_core_config_update
        )
        self._unsub_play_interceptor = self.hass.bus.async_listen(
            EVENT_CALL_SERVICE, self._async_on_service_call_event
        )

        if self.native_ble_tracking_enabled:
            self._ble_tracker = LatterNativeBleTracker(
                hass=self.hass,
                beacon_uuid=self.ble_beacon_uuid,
                device_slug=self.device_slug,
                on_area_detected=self._async_on_native_ble_area_detected,
                area_offsets=self.ble_area_offsets,
                target_address=self.ble_target_address,
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

    async def async_shutdown(self) -> None:
        """Clean up all subscriptions and timers."""
        if self._ble_tracker is not None:
            self._ble_tracker.async_stop()
            self._ble_tracker = None

        for unsub in (
            self._unsub_core_config,
            self._unsub_speaker_state,
            self._unsub_local_reconnect,
            self._unsub_play_interceptor,
            self._unsub_weather_state,
            self._unsub_alarm_state,
            self._unsub_presence_state,
            self._unsub_remotes_state,
            self._unsub_area_entities_state,
            self._unsub_area_debounce,
            self._unsub_position_timer,
            self._unsub_forecast_timer,
            self._unsub_calendar_timer,
            self._unsub_wallpaper_timer,
            self._unsub_doorbell_ring_state,
            self._unsub_area_follow_dwell,
        ):
            if unsub is not None:
                unsub()
        self._unsub_core_config = None
        self._unsub_speaker_state = None
        self._unsub_local_reconnect = None
        self._unsub_play_interceptor = None
        self._unsub_weather_state = None
        self._unsub_alarm_state = None
        self._unsub_presence_state = None
        self._unsub_remotes_state = None
        self._unsub_area_entities_state = None
        self._unsub_area_debounce = None
        self._unsub_position_timer = None
        self._unsub_forecast_timer = None
        self._unsub_calendar_timer = None
        self._unsub_wallpaper_timer = None
        self._unsub_doorbell_ring_state = None
        self._unsub_area_follow_dwell = None
        self._pending_follow_area_id = None
        self._listeners.clear()

    @callback
    def _bind_area_entities_listener(self) -> None:
        """Subscribe to state changes on all curated entities in the active area for live two-way sync."""
        if self._unsub_area_entities_state is not None:
            self._unsub_area_entities_state()
            self._unsub_area_entities_state = None

        area_items = get_area_entities(
            self.hass,
            area_id=self.active_area_id,
            domain_filter="all",
            local_speaker=self.local_speaker,
        )
        tracked_ids = [str(it["id"]) for it in area_items if it.get("id")]
        if not tracked_ids:
            return

        self._unsub_area_entities_state = async_track_state_change_event(
            self.hass,
            tracked_ids,
            self._async_on_area_entity_state_change,
        )

    @callback
    def _async_on_area_entity_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Debounce active area entity state changes (250ms) and push updated area slots to ESPHome."""
        self._notify_listeners()
        if self._unsub_area_debounce is not None:
            self._unsub_area_debounce()
            self._unsub_area_debounce = None

        @callback
        def _push_area_update(_now: datetime) -> None:
            self._unsub_area_debounce = None
            if self.on_area_changed_push_slots is not None:
                self.entry.async_create_background_task(
                    self.hass,
                    self.on_area_changed_push_slots(self),
                    f"latter_area_slots_{self.device_slug}",
                )

        self._unsub_area_debounce = async_call_later(
            self.hass, 0.25, _push_area_update
        )

    @callback
    def _bind_doorbell_ring_listener(self) -> None:
        """Auto-detect sibling doorbell ring / visitor entities on configured cameras and subscribe."""
        if self._unsub_doorbell_ring_state is not None:
            self._unsub_doorbell_ring_state()
            self._unsub_doorbell_ring_state = None

        if self.device_profile in ("ble_beacon", "headless_node"):
            return

        from .doorbell_engine import resolve_doorbell_ring_entities

        self._doorbell_ring_map = resolve_doorbell_ring_entities(
            self.hass, self.camera_entities
        )
        if not self._doorbell_ring_map:
            return

        self._unsub_doorbell_ring_state = async_track_state_change_event(
            self.hass,
            list(self._doorbell_ring_map.keys()),
            self._async_on_doorbell_ring_state_change,
        )

    @callback
    def _async_on_doorbell_ring_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Automatically wake the display with a live camera popup and chime when a doorbell rings."""
        entity_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if not entity_id or new_state is None or old_state is None:
            return
        if old_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, "off"):
            return
        if entity_id.startswith("binary_sensor.") and new_state.state != "on":
            return
        if old_state.state == new_state.state:
            return
        if entity_id.startswith("event."):
            ev_dt = dt_util.parse_datetime(new_state.state)
            if ev_dt is None or abs((dt_util.utcnow() - ev_dt).total_seconds()) > 15.0:
                return

        cam_ent = self._doorbell_ring_map.get(entity_id) or self.camera_entity
        if not cam_ent:
            return

        now_mono = time.monotonic()
        if now_mono < self._doorbell_ring_cooldown_until.get(cam_ent, 0.0):
            return
        self._doorbell_ring_cooldown_until[cam_ent] = now_mono + 15.0

        cam_st = self.hass.states.get(cam_ent)
        cam_friendly = (
            str(cam_st.attributes.get("friendly_name") if cam_st else "")
            or cam_ent.split(".", 1)[-1].replace("_", " ").title()
        )
        title = "Doorbell Ringing"
        message = f"Visitor at {cam_friendly}"

        self.async_dispatch_notification(
            title=title,
            message=message,
            priority="critical",
            duration=20,
            chime=True,
            camera_entity=cam_ent,
        )

        esphome_svcs = self.hass.services.async_services().get("esphome", {})
        expected_svc = f"{self.device_slug}_show_notification"
        esp_notify_svc = (
            expected_svc
            if expected_svc in esphome_svcs
            else next(
                (
                    s
                    for s in esphome_svcs
                    if s.endswith("_show_notification") and self.device_slug in s
                ),
                None,
            )
        )
        if esp_notify_svc:
            self.entry.async_create_background_task(
                self.hass,
                self.hass.services.async_call(
                    "esphome",
                    esp_notify_svc,
                    {
                        "title": title[:48],
                        "message": message[:160],
                        "priority": "critical",
                        "duration": 20,
                        "chime": True,
                        "camera_url": self.alert_camera_url,
                    },
                    blocking=False,
                ),
                f"latter_doorbell_notify_{self.device_slug}",
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
            self.entry.async_create_background_task(
                self.hass,
                self._async_handle_device_reconnect(),
                f"latter_reconnect_{self.device_slug}",
            )

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
        """Reset idle remote speaker, sync BLE area lock, and push active area slots after ESPHome boot/wake."""
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
            self.entry.async_create_background_task(
                self.hass,
                self._async_resume_idle_speaker_queue(target_spk),
                f"latter_cold_resume_{self.device_slug}",
            )

    async def _async_find_queue_resume_item(
        self, speaker_entity_id: str
    ) -> tuple[str, float]:
        """Query Music Assistant (controller or get_queue) for the current queue item URI and position, falling back to persisted store."""
        return await async_find_queue_resume_item(
            self.hass,
            speaker_entity_id,
            self.device_slug,
            self.last_media_uri,
            self.last_media_position,
        )

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
            await async_play_media_with_ma_fallback(
                self.hass,
                target_spk,
                self.device_slug,
                media_id,
                media_type=media_type,
                enqueue=enqueue,
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

    def is_device_away(self) -> bool:
        """Return True if a roaming BLE device has timed out across all proxies (and is not awake on local Wi-Fi)."""
        if not self.native_ble_tracking_enabled or self._ble_tracker is None:
            return False
        if not self._ble_tracker.is_away:
            return False
        if self.device_profile == "ble_beacon":
            return True
        # For ESPHome displays, if connected to local Wi-Fi (not away), keep last area when sleeping in Standby
        wifi_st = (
            self.hass.states.get(f"sensor.{self.device_slug}_wi_fi_signal")
            or self.hass.states.get(f"sensor.{self.device_slug}_wifi_signal")
            or self.hass.states.get(f"sensor.{self.device_slug}_ip_address")
        )
        if wifi_st is not None and wifi_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            return False
        return True

    def get_current_area_and_distance(self) -> tuple[str, dict[str, Any]]:
        """Return (area_or_away_state, attributes) for sensor.<slug>_current_area and sensor.<slug>_ble_distance."""
        away = self.is_device_away()
        area_reg = ar.async_get(self.hass)
        explicit_default = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()

        if self.native_ble_tracking_enabled:
            ble_area_id = (
                self._ble_tracker.current_area_id
                if (self._ble_tracker is not None and not away)
                else None
            ) or (explicit_default if not away else None)
            area_entry = area_reg.async_get_area(ble_area_id) if ble_area_id else None
            if away:
                area_state = "Away"
            elif area_entry is not None:
                area_state = area_entry.name
            else:
                area_state = "Unassigned"
            eff_area_id = ble_area_id or ""
        else:
            eff_area_id = "" if away else (self.active_area_id or explicit_default)
            area_entry = area_reg.async_get_area(eff_area_id) if eff_area_id else None
            area_state = "Away" if away else (area_entry.name if area_entry else "Unassigned")

        dist_ft = self._ble_tracker.winning_distance_ft if (self._ble_tracker and not away and eff_area_id) else None
        dist_m = self._ble_tracker.winning_distance_m if (self._ble_tracker and not away and eff_area_id) else None
        rssi = self._ble_tracker.winning_rssi if (self._ble_tracker and not away and eff_area_id) else None
        proxy = self._ble_tracker.closest_scanner if (self._ble_tracker and not away and eff_area_id) else ""
        return area_state, {
            "area_id": eff_area_id,
            "area_name": area_state,
            "is_home": not away,
            "closest_proxy": proxy,
            "distance_ft": dist_ft,
            "distance_m": dist_m,
            "rssi": rssi,
            "assigned_person": self.assigned_person,
        }

    @callback
    def _async_on_native_ble_area_detected(
        self, area_id: str, scanner_source: str
    ) -> None:
        """Handle area transition or Away timeout detected by Latter's BLE proxy tracker."""
        if area_id == "away":
            if self._unsub_area_follow_dwell is not None:
                self._unsub_area_follow_dwell()
                self._unsub_area_follow_dwell = None
            self._pending_follow_area_id = None
            self._notify_listeners()
            return
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
                area_id,
                handoff_media=False,
                sync_device_registry=True,
                ble_driven=True,
            )
        else:
            self._notify_listeners()

    @callback
    def async_add_listener(
        self, update_callback: Callable[[], None], context: Any = None
    ) -> Callable[[], None]:
        """Register an entity state update callback via DataUpdateCoordinator."""
        return super().async_add_listener(update_callback, context)

    def get_person_area_and_distance(self, person_entity: str) -> tuple[str, dict[str, Any]]:
        """Resolve the freshest area and BLE distance across all Latter devices carried by a person."""
        domain_data = self.hass.data.get(DOMAIN, {})
        p_coords = [
            v
            for v in domain_data.values()
            if isinstance(v, LatterCoordinator) and v.assigned_person == person_entity
        ]
        if not p_coords:
            p_coords = [self]
        home_coords = [c for c in p_coords if not c.is_device_away()]
        pool = home_coords if home_coords else p_coords
        best_c = max(
            pool,
            key=lambda x: (
                x._ble_tracker.last_packet_monotonic
                if x._ble_tracker is not None
                else 0.0
            ),
        )
        area_name, r_attrs = best_c.get_current_area_and_distance()
        return area_name, {
            "person_entity": person_entity,
            "area_id": r_attrs["area_id"],
            "area_name": area_name,
            "is_home": r_attrs["is_home"],
            "distance_ft": r_attrs["distance_ft"],
            "distance_m": r_attrs["distance_m"],
            "closest_proxy": r_attrs["closest_proxy"],
            "source_device": best_c.device_slug,
        }

    @callback
    def async_notify_listeners(self) -> None:
        """Advance monotonic revision, invalidate per-tick payload caches, and notify all registered listeners."""
        self.rev += 1
        self._cached_media_payload = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._schedule_persist_runtime_state()
        self.async_update_listeners()

    @callback
    def _notify_listeners(self) -> None:
        """Notify all registered sensors of a state update."""
        self.async_notify_listeners()

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

        try:
            async with asyncio.timeout(4.5):
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
        except TimeoutError:
            _LOGGER.debug("Queue transfer handoff timed out for %s", target_speaker)

        self._notify_listeners()

    @callback
    def async_set_active_speaker(
        self, speaker_entity_id: str, transfer_queue: bool = True
    ) -> None:
        """Switch the active target speaker, persist to Store, and optionally transfer active queue."""
        speaker_entity_id = speaker_entity_id.strip()
        if not speaker_entity_id:
            return
        if (
            self.local_speaker
            and speaker_entity_id
            in (
                f"media_player.{self.device_slug}",
                f"media_player.{self.device_slug}_music",
            )
        ):
            speaker_entity_id = self.local_speaker

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
                    self.entry.async_create_background_task(
                        self.hass,
                        self._async_execute_ma_queue_transfer(
                            source_speaker=prev_speaker,
                            target_speaker=speaker_entity_id,
                            was_playing=was_playing,
                            handoff_position=handoff_pos,
                            media_content_id=media_cid,
                            media_content_type=media_ctype,
                        ),
                        f"latter_queue_transfer_{self.device_slug}",
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
        ble_driven: bool = False,
    ) -> None:
        """Switch active area, persist to Store, sync ESPHome device area, and hand off media."""
        matched_id = match_area_by_name_or_id(self.hass, area_id_or_name)
        if not matched_id:
            return
        prev_area = self.active_area_id
        self.active_area_id = matched_id
        self._bind_area_entities_listener()
        if prev_area != matched_id:
            self.hass.bus.async_fire(
                EVENT_LATTER,
                {
                    "type": "area_changed",
                    "device_slug": self.device_slug,
                    "previous_area_id": prev_area or "",
                    "area_id": matched_id,
                    "assigned_person": self.assigned_person,
                },
            )

        if self._unsub_area_follow_dwell is not None:
            self._unsub_area_follow_dwell()
            self._unsub_area_follow_dwell = None
        self._pending_follow_area_id = None

        esp_dev_id = self.esphome_device_id
        if sync_device_registry and self.sync_device_area_enabled and esp_dev_id:
            dwell_s = self.area_follow_dwell_s
            if ble_driven and dwell_s > 0:
                self._pending_follow_area_id = matched_id

                @callback
                def _commit_dwell_sync(_now: datetime) -> None:
                    self._unsub_area_follow_dwell = None
                    if (
                        self._pending_follow_area_id == matched_id
                        and self.active_area_id == matched_id
                        and not self.is_device_away()
                        and self.sync_device_area_enabled
                        and self.esphome_device_id
                    ):
                        self._pending_follow_area_id = None
                        sync_esphome_device_area(
                            self.hass,
                            self.esphome_device_id,
                            matched_id,
                            require_ble_proxy_area=True,
                        )

                self._unsub_area_follow_dwell = async_call_later(
                    self.hass, float(dwell_s), _commit_dwell_sync
                )
            else:
                sync_esphome_device_area(
                    self.hass,
                    esp_dev_id,
                    matched_id,
                    require_ble_proxy_area=ble_driven,
                )

        media_map = find_area_media_entities(
            self.hass, matched_id, self.local_speaker
        )
        if media_map["remote"]:
            self.active_remote = media_map["remote"]

        self.active_remote_slot = 1
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
            self.entry.async_create_background_task(
                self.hass,
                self.on_area_changed_push_slots(self),
                f"latter_area_change_slots_{self.device_slug}",
            )

    @property
    def remote_groups(self) -> list[dict[str, Any]]:
        """Return system-wide Remote Control Groups ([{'id', 'name', 'area_id', 'remotes': [...]}, ...])."""
        raw = self.get_opt(CONF_REMOTE_GROUPS, [])
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw[:20]:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                rems = [
                    str(r).strip()
                    for r in (item.get("remotes") or [])[:10]
                    if str(r or "").strip()
                ]
                out.append(
                    {
                        "id": str(item["id"]).strip(),
                        "name": str(item["name"]).strip(),
                        "area_id": str(item.get("area_id") or "").strip(),
                        "remotes": rems,
                    }
                )
        return out

    @property
    def device_remote_group(self) -> str:
        """Return this device's remote assignment mode ('area_auto', 'all', or 'group:<id>')."""
        val = str(
            self.get_opt(CONF_DEVICE_REMOTE_GROUP, DEFAULT_DEVICE_REMOTE_GROUP)
            or DEFAULT_DEVICE_REMOTE_GROUP
        ).strip()
        return val or DEFAULT_DEVICE_REMOTE_GROUP

    def get_remote_entities_list(self) -> list[str]:
        """Return the system-wide inventory of up to 10 remote/media_player entity IDs."""
        raw_list = self.get_opt(CONF_REMOTES_LIST)
        if isinstance(raw_list, list):
            return [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
        return []

    def get_effective_remote_entities_for_device(self) -> list[str]:
        """Resolve the ordered list of remote entities for this device (Static Group vs Active Area vs All)."""
        all_inventory = self.get_remote_entities_list()
        groups = self.remote_groups
        mode = self.device_remote_group

        # 1. Explicit Static Remote Group assigned directly to this device
        if mode.startswith("group:"):
            gid = mode.split(":", 1)[1].strip()
            matched_grp = next((g for g in groups if g["id"] == gid), None)
            if matched_grp is not None:
                return list(matched_grp.get("remotes") or [])[:10]
            return []

        # 2. Explicit 'All System Remotes' mode
        if mode == "all":
            return all_inventory[:10]

        # 3. Default 'area_auto' mode: Follow the device's current Active Area!
        cur_area = (self.active_area_id or str(self.get_opt(CONF_DEFAULT_AREA) or "")).strip()
        if cur_area:
            # 3A. Check if any Remote Group is assigned to cur_area
            area_group_remotes: list[str] = []
            for grp in groups:
                if grp.get("area_id") == cur_area:
                    for r in grp.get("remotes") or []:
                        if r not in area_group_remotes:
                            area_group_remotes.append(r)
            if area_group_remotes:
                return area_group_remotes[:10]

            # 3B. If Remote Groups exist in the system, only show remotes explicitly assigned to cur_area
            if groups:
                return []

            # 3C. No Remote Groups defined yet: filter system inventory by HA entity area_id (if any remotes have areas)
            resolved_all = [resolve_remote_slot_pair(self.hass, eid) for eid in all_inventory]
            any_has_area = any(bool(r.get("area_id")) for r in resolved_all)
            if any_has_area:
                return [
                    eid
                    for eid, r in zip(all_inventory, resolved_all)
                    if r.get("area_id") == cur_area
                ][:10]

        # Fallback when no groups exist and no areas are assigned to remotes yet
        if not groups:
            return all_inventory[:10]
        return []

    def get_remote_slots(self) -> list[dict[str, str]]:
        """Return up to 10 resolved TV/Media Remote slot dictionaries for this device's current context."""
        ent_ids = self.get_effective_remote_entities_for_device()
        if not ent_ids:
            return []
        return [resolve_remote_slot_pair(self.hass, eid) for eid in ent_ids[:10]]

    def get_remote_config_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_remote_config (supports 0..10 slots)."""
        now_m = time.monotonic()
        if self._cached_remote_payload is not None and (now_m - self._cached_remote_payload[0]) < 0.05:
            return self._cached_remote_payload[1]
        slots = self.get_remote_slots()
        populated_count = sum(
            1 for s in slots if s["remote_entity"] or s["media_player_entity"]
        )
        clamped_active = max(1, min(max(1, len(slots)), self.active_remote_slot))
        attrs: dict[str, Any] = {
            "active_slot": clamped_active,
            "configured_count": populated_count,
            "device_remote_group": self.device_remote_group,
            "active_area_id": self.active_area_id or "",
        }
        if populated_count == 0 or not slots:
            attrs["slots_summary"] = "NONE"
            attrs["rev"] = self.rev
            attrs["payload"] = _pack_v3_payload(
                self.rev, clamped_active, 0, "NONE"
            )
            res = ("None", attrs)
            self._cached_remote_payload = (now_m, res)
            return res

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

        active_slot_data = slots[clamped_active - 1]
        state_str = active_slot_data["name"] if populated_count > 0 else "None"
        attrs["slots_summary"] = ";".join(summary_parts)
        attrs["rev"] = self.rev
        attrs["payload"] = _pack_v3_payload(
            self.rev, clamped_active, populated_count, attrs["slots_summary"]
        )
        res = (state_str, attrs)
        self._cached_remote_payload = (now_m, res)
        return res

    def get_area_context_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_area_context."""
        now_m = time.monotonic()
        if self._cached_area_payload is not None and (now_m - self._cached_area_payload[0]) < 0.05:
            return self._cached_area_payload[1]
        area_reg = ar.async_get(self.hass)
        explicit_default = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        has_ble_lock = bool(
            self._ble_tracker is not None and self._ble_tracker.current_area_id
        )
        if self.native_ble_tracking_enabled and not has_ble_lock and not explicit_default:
            area_entry = None
        else:
            eff_id = (
                self._ble_tracker.current_area_id
                if (self.native_ble_tracking_enabled and has_ble_lock and self._ble_tracker)
                else (self.active_area_id or explicit_default)
            )
            area_entry = area_reg.async_get_area(eff_id) if eff_id else None
        area_name = area_entry.name if area_entry else "Unassigned"

        entities = get_area_entities(
            self.hass,
            area_id=self.active_area_id,
            domain_filter="all",
            local_speaker=self.local_speaker,
        )
        avail_domains = get_area_available_domains(
            self.hass,
            area_id=self.active_area_id,
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
        wh_info = get_whole_home_summary(
            self.hass,
            thermostat_entity=self.thermostat_entity,
            lock_entity=self.lock_entity,
            garage_entity=self.garage_entity,
            vacuum_entity=self.vacuum_entity,
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

        area_attrs = {
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
            "entity_count": len(entities),
            "available_domains": avail_domains,
            "lights_on": lights_on,
            "covers_open": covers_open,
            "area_temp": climate_telemetry["temperature"],
            "area_humidity": climate_telemetry["humidity"],
            "area_speaker": media_map["speaker"] or self.active_speaker,
            "area_remote": media_map["remote"] or self.active_remote,
            "alarm_entity": alarm_info["entity_id"],
            "alarm_state": alarm_info["state"],
            "alarm_name": alarm_info["name"],
            "alarm_code_required": alarm_info["code_arm_required"],
            "thermostat_entity": wh_info["thermostat_entity"],
            "thermostat_state": wh_info["thermostat_state"],
            "thermostat_temp": wh_info["thermostat_temp"],
            "thermostat_current_temp": wh_info["thermostat_current_temp"],
            "lock_entity": wh_info["lock_entity"],
            "lock_state": wh_info["lock_state"],
            "garage_entity": wh_info["garage_entity"],
            "garage_state": wh_info["garage_state"],
            "vacuum_entity": wh_info["vacuum_entity"],
            "vacuum_state": wh_info["vacuum_state"],
            "native_ble_tracking": self.native_ble_tracking_enabled,
            "ble_beacon_uuid": self.ble_beacon_uuid,
            "ble_closest_proxy": self._ble_tracker.closest_scanner if self._ble_tracker else "",
            "ble_packets_seen": self._ble_tracker.packets_seen if self._ble_tracker else 0,
            "ble_rssi_by_area": self._ble_tracker.get_live_rssi_summary() if self._ble_tracker else {},
            "ble_area_offsets": self.ble_area_offsets,
            "ble_scanners_map": get_all_scanners_diagnostic_map(self.hass),
            "ble_target_macs": self._ble_tracker.target_macs_formatted if self._ble_tracker else [],
            "assigned_person": self.assigned_person,
            "assigned_role": self.assigned_role,
            "presence_entity": pres_ent or "",
            "presence_state": pres_state,
            "ble_auto_switch": self.ble_auto_switch_enabled,
            "voice_area_synced": self.sync_device_area_enabled,
            "entities_summary": ";".join(summary_items) if summary_items else "NONE",
            "camera_entity": self.camera_entity or "",
            "camera_entities": self.camera_entities,
            "cameras_summary": self._build_cameras_summary(),
            "camera_snapshot_url": self.build_camera_snapshot_url(
                self.active_carousel_camera or self.camera_entity
            ) if (self.active_carousel_camera or self.camera_entity) else "none",
            "doorbell_talk_state": self.doorbell_talk_state,
            "doorbell_anc_mode": self.doorbell_anc_mode,
            "intercom_targets_summary": self._build_intercom_targets_summary(),
            "alert_id": self.alert_id,
            "alert_title": self.alert_title,
            "alert_message": self.alert_message,
            "alert_priority": self.alert_priority,
            "alert_duration": self.alert_duration,
            "alert_chime": self.alert_chime,
            "alert_camera_url": self.alert_camera_url,
            "theme_color_hex": self.device_custom_color,
            "custom_palettes": self.custom_palettes,
            "hardware_manifest": self.hardware_manifest,
            "rev": self.rev,
        }
        area_attrs["payload"] = _pack_v3_payload(
            self.rev,
            area_attrs["area_id"],
            area_name,
            area_attrs["site_id"],
            1 if self.vpn_enabled else 0,
            area_attrs["vpn_client_ip"],
            area_attrs["ble_closest_proxy"],
            area_attrs["dock_apps"],
            area_attrs["wallpaper_url"],
            area_attrs["theme_color_hex"],
            area_attrs["available_domains"],
            area_attrs["area_temp"],
            area_attrs["area_humidity"],
            lights_on,
            covers_open,
            area_attrs["alarm_entity"],
            area_attrs["alarm_state"],
            area_attrs["thermostat_entity"],
            area_attrs["thermostat_state"],
            area_attrs["thermostat_temp"],
            area_attrs["thermostat_current_temp"],
            area_attrs["lock_entity"],
            area_attrs["lock_state"],
            area_attrs["garage_entity"],
            area_attrs["garage_state"],
            area_attrs["vacuum_entity"],
            area_attrs["vacuum_state"],
            area_attrs["camera_snapshot_url"],
            area_attrs["cameras_summary"],
            area_attrs["doorbell_talk_state"],
            area_attrs["intercom_targets_summary"],
            "",
            self.alert_id,
            self.alert_title,
            self.alert_message,
            self.alert_priority,
            self.alert_duration,
            1 if self.alert_chime else 0,
            self.alert_camera_url,
        )
        res = (area_name, area_attrs)
        self._cached_area_payload = (now_m, res)
        return res

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
        ma_counterpart = _resolve_ma_counterpart_entity(
            self.hass, self.active_speaker, self.device_slug
        )
        if ma_counterpart and ma_counterpart not in tracked:
            tracked.append(ma_counterpart)

        self._unsub_speaker_state = async_track_state_change_event(
            self.hass,
            tracked,
            self._async_on_speaker_state_change,
        )
        self._update_position_timer_state()

    @callback
    def _bind_alarm_listener(self) -> None:
        """Subscribe to state changes on shared whole-home entities (alarm, thermostat, lock, garage, vacuum)."""
        if self._unsub_alarm_state is not None:
            self._unsub_alarm_state()
            self._unsub_alarm_state = None

        wh_info = get_whole_home_summary(
            self.hass,
            thermostat_entity=self.thermostat_entity,
            lock_entity=self.lock_entity,
            garage_entity=self.garage_entity,
            vacuum_entity=self.vacuum_entity,
        )
        tracked: list[str] = []
        for cand in (
            self.alarm_entity,
            wh_info["thermostat_entity"],
            wh_info["lock_entity"],
            wh_info["garage_entity"],
            wh_info["vacuum_entity"],
        ):
            if cand and cand not in tracked:
                tracked.append(cand)

        if not tracked:
            return

        self._unsub_alarm_state = async_track_state_change_event(
            self.hass,
            tracked,
            self._async_on_generic_state_change,
        )

    @callback
    def _bind_presence_listener(self) -> None:
        """Subscribe to external BLE trilateration area presence entity changes."""
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
        """Auto-switch active area when external BLE presence sensor reports a new area."""
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
                matched_area, sync_device_registry=True, ble_driven=True
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
        """Idle-Guard: Run 15s position timer ONLY when speaker is playing/buffering."""
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
        now_m = time.monotonic()
        if self._cached_media_payload is not None and (now_m - self._cached_media_payload[0]) < 0.05:
            return self._cached_media_payload[1]
        state_obj = self.hass.states.get(self.active_speaker)
        vol_target = self.get_volume_target_entity(self.active_speaker)
        fallback_spk_name = (
            self.active_speaker.split(".", 1)[-1].replace("_", " ").title()
            if self.active_speaker
            else "Local Speaker"
        )

        if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            idle_title = self.last_media_title or "Idle"
            idle_artist = self.last_media_artist or "None"
            idle_album = self.last_media_album or "None"
            idle_dur = round(self.last_media_duration, 1)
            idle_pos = round(self.last_media_position, 1)
            idle_type = self.last_media_type or "music"
            res = (
                STATE_OFF,
                {
                    "title": idle_title,
                    "artist": idle_artist,
                    "album": idle_album,
                    "duration": idle_dur,
                    "position": idle_pos,
                    "volume": 0.7,
                    "media_type": idle_type,
                    "supported_features": 0,
                    "art_url": "none",
                    "active_speaker": self.active_speaker,
                    "speaker_name": fallback_spk_name,
                    "last_speaker": self.last_speaker,
                    "local_speaker": self.local_speaker,
                    "volume_entity": vol_target,
                    "rev": self.rev,
                    "payload": _pack_v3_payload(
                        self.rev,
                        STATE_OFF,
                        idle_title,
                        idle_artist,
                        idle_album,
                        idle_dur,
                        idle_pos,
                        0.7,
                        idle_type,
                        0,
                        "none",
                        self.active_speaker,
                        fallback_spk_name,
                        self.last_speaker,
                        self.local_speaker,
                        vol_target,
                    ),
                },
            )
            self._cached_media_payload = (now_m, res)
            return res

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

        # When playing on the local ESPHome Sendspin speaker, media_player.<slug>_music often omits media_title
        # and entity_picture in HA; fall back to the Music Assistant counterpart entity or ESPHome text_sensors.
        ma_counterpart = _resolve_ma_counterpart_entity(
            self.hass, self.active_speaker, self.device_slug
        )
        ma_st = (
            self.hass.states.get(ma_counterpart)
            if ma_counterpart and ma_counterpart != self.active_speaker
            else None
        )
        m_attrs: dict[str, Any] = dict(ma_st.attributes) if ma_st is not None else {}

        if title == "Idle" and m_attrs.get("media_title"):
            title = str(m_attrs.get("media_title") or title)
            artist = str(
                m_attrs.get("media_artist")
                or m_attrs.get("media_series_title")
                or m_attrs.get("media_album_artist")
                or artist
            )
            album = str(m_attrs.get("media_album_name") or album)
        if duration <= 0 and m_attrs.get("media_duration"):
            duration = float(m_attrs.get("media_duration") or duration)
        if position <= 0 and ma_st is not None:
            position = _interpolate_speaker_position(ma_st) or position

        if title == "Idle" and self.active_speaker == self.local_speaker:
            t_st = self.hass.states.get(f"sensor.{self.device_slug}_now_playing_title")
            a_st = self.hass.states.get(f"sensor.{self.device_slug}_now_playing_artist")
            al_st = self.hass.states.get(f"sensor.{self.device_slug}_now_playing_album")
            if t_st is not None and t_st.state not in ("", "None", "Idle", STATE_UNKNOWN, STATE_UNAVAILABLE):
                title = str(t_st.state)
                if a_st is not None and a_st.state not in ("", "None", STATE_UNKNOWN, STATE_UNAVAILABLE):
                    artist = str(a_st.state)
                if al_st is not None and al_st.state not in ("", "None", STATE_UNKNOWN, STATE_UNAVAILABLE):
                    album = str(al_st.state)

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
            or m_attrs.get("entity_picture_local")
            or m_attrs.get("entity_picture")
            or m_attrs.get("media_image_url")
            or ""
        )
        track_key = f"{title}|{artist}|{album}"

        if state == STATE_OFF or title == "Idle":
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

        speaker_name = str(attrs.get("friendly_name") or fallback_spk_name)

        dur_r = round(duration, 1)
        pos_r = round(position, 1)
        vol_r = round(volume, 2)
        res = (
            state,
            {
                "title": title,
                "artist": artist,
                "album": album,
                "duration": dur_r,
                "position": pos_r,
                "volume": vol_r,
                "media_type": media_type,
                "supported_features": supported_features,
                "art_url": art_url,
                "active_speaker": self.active_speaker,
                "speaker_name": speaker_name,
                "last_speaker": self.last_speaker,
                "local_speaker": self.local_speaker,
                "volume_entity": vol_target,
                "rev": self.rev,
                "payload": _pack_v3_payload(
                    self.rev,
                    state,
                    title,
                    artist,
                    album,
                    dur_r,
                    pos_r,
                    vol_r,
                    media_type,
                    supported_features,
                    art_url,
                    self.active_speaker,
                    speaker_name,
                    self.last_speaker,
                    self.local_speaker,
                    vol_target,
                ),
            },
        )
        self._cached_media_payload = (now_m, res)
        return res

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
        self.entry.async_create_background_task(
            self.hass,
            self.async_refresh_weather_forecast(),
            f"latter_weather_refresh_{self.device_slug}",
        )

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
        self.current_wallpaper = favs[idx]
        self._schedule_persist_runtime_state()
        self._notify_listeners()

    async def _async_periodic_calendar_refresh(self, _now: datetime) -> None:
        """Refresh system calendar agenda every 15 minutes."""
        await self.async_refresh_calendar_agenda()

    async def async_refresh_calendar_agenda(self, days: int = 30) -> None:
        """Fetch upcoming calendar events and update sensor state."""
        agenda_str, events = await async_fetch_calendar_agenda(
            self.hass,
            self.calendar_entities,
            days=days,
            map_url_builder=self.build_map_snapshot_url,
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
        cond_str = str(state_obj.state)
        temp_r = round(temp, 1)
        hum_r = round(humidity, 1)
        ws_r = round(wind_speed, 1)
        wb_r = round(wind_bearing, 1)
        hi_r = round(high, 1)
        lo_r = round(low, 1)
        self.weather_attributes = {
            "condition": cond_str,
            "temperature": temp_r,
            "humidity": hum_r,
            "wind_speed": ws_r,
            "wind_bearing": wb_r,
            "high": hi_r,
            "low": lo_r,
            "weather_entity": weather_ent,
            "rev": self.rev,
            "payload": _pack_v3_payload(
                self.rev,
                cond_str,
                temp_r,
                hum_r,
                ws_r,
                wb_r,
                hi_r,
                lo_r,
                self.forecast_string,
            ),
        }
        self._notify_listeners()