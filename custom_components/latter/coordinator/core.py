"""Unified push `LatterCoordinator` orchestrator for one Latter Device or BLE Tag."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping, Sequence
from datetime import date, datetime, timedelta
import json
import logging
import secrets
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_CORE_CONFIG_UPDATE,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from ..areas.catalogs import find_area_media_entities
from ..areas.registry import match_area_by_name_or_id, resolve_active_area_entry
from ..areas.sync import sync_esphome_device_area
from ..areas.telemetry import (
    bind_coordinator_area_listeners,
    build_area_context_payload,
)
from ..const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_ALARM_ENTITY,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_ATTENUATION,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_AWAY_TIMEOUT_S,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_CATEGORY,
    CONF_BLE_MAX_RADIUS_M,
    CONF_BLE_MAX_VELOCITY_MPS,
    CONF_BLE_REF_POWER,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BROADCAST_PHRASES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_BROADCAST_SPEAKERS,
    CONF_CALENDAR_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_CONFIGS,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_CUSTOM_PALETTES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DO_NOT_DISTURB,
    CONF_DOCK_ITEMS,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_ESPHOME_DEVICE_ID,
    CONF_GAMES_ITEMS,
    CONF_GARAGE_ENTITIES,
    CONF_HOME_CATEGORIES,
    CONF_LOCK_ENTITIES,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_PINNED_PAGE_TITLES,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_SYSTEM_BLE_UUID,
    CONF_THERMOSTAT_ENTITIES,
    CONF_TOOLS_ITEMS,
    CONF_VACUUM_ENTITIES,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DAY_NIGHT_SKY_NATIVE_URL,
    DAY_NIGHT_SKY_PRESET_ID,
    DEFAULT_ACTIVITY_CARD,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_AREA_FOLLOW_DWELL_S,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_ATTENUATION,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_BLE_AWAY_TIMEOUT_S,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_BLE_MAX_RADIUS_M,
    DEFAULT_BLE_MAX_VELOCITY_MPS,
    DEFAULT_BROADCAST_PHRASES,
    DEFAULT_CARD_SLOT_COUNT,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_DOORBELL_NOISE_REDUCTION,
    DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES,
    DEFAULT_LIST_SLOT_COUNT,
    DEFAULT_NATIVE_BLE_TRACKING,
    DEFAULT_SCREENSAVER_CYCLE_MINUTES,
    DEFAULT_SCREENSAVER_PHOTO_COLLECTION,
    DEFAULT_SCREENSAVER_PHOTO_MODE,
    DEFAULT_SCREENSAVER_SHUFFLE,
    DEFAULT_SECURITY_PIN_POLICY,
    DEFAULT_SITE_ID,
    DEFAULT_SYNC_DEVICE_AREA,
    DEFAULT_TOOLS_ITEMS,
    DEFAULT_WALLPAPER_COLLECTION,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DEFAULT_WALLPAPER_MODE,
    DOMAIN,
    EVENT_LATTER,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    MIN_FIRMWARE_CORE_REV,
    SUBENTRY_BLE_TAG,
    WALLPAPER_MAX_DIM,
    derive_device_beacon_uuid,
    normalize_device_slug,
    normalize_noise_reduction,
)
from ..doorbell import bind_coordinator_doorbell_listener
from ..feeds import (
    apply_coordinator_calendar_snapshot,
    apply_coordinator_weather_snapshot,
    async_refresh_coordinator_calendar,
    async_refresh_coordinator_weather,
    build_calendar_agenda_payload,
    init_weather_attributes,
)
from ..groups.device_groups import resolve_effective_device_group
from ..http.signing import UrlSigner
from ..hub_registry import (
    get_area_state_index,
    get_latter_system,
    iter_coordinators,
    peek_global_config,
)
from ..identity import (
    device_entities,
    esphome_service,
    get_bound_esphome_device,
    manifest_flag,
    manifest_has_audio,
    manifest_has_battery,
    manifest_has_display,
    manifest_has_imu,
    manifest_has_mic,
    manifest_has_speaker,
    manifest_has_touch,
    manifest_is_roaming,
    manifest_is_round,
    manifest_is_wearable,
    manifest_supports_hw_jpeg,
    manifest_video_caps,
    read_device_hardware_manifest,
    resolve_bound_esphome_device_id,
)
from ..media.linking import resolve_esphome_local_speaker, resolve_ma_counterpart_entity
from ..media.playback import (
    bind_coordinator_speaker_listener,
    enforce_local_speaker_if_remote_idle,
    execute_coordinator_media_command,
    set_coordinator_active_speaker,
)
from ..media.state_payload import build_active_media_payload
from ..presence.ble_discovery import classify_ble_target_category
from ..presence.ble_fabric import get_ble_fabric
from ..presence.ble_math import TX_POWER_1M_DBM
from ..presence.ble_registry import (
    get_ble_proxy_area_ids,
    get_ble_signature_area_ids,
    normalize_uuid_hex,
    resolve_floor_info,
)
from ..presence.ble_tracker import LatterNativeBleTracker
from ..protocol_codec import (
    DomainPayloadPacker,
    V3Records,
    pack_device_prefs_fields,
    pack_weather_forecast_fields,
    parse_dirty_prefs_records,
)
from ..protocol_policy import (
    PinLockoutTracker,
    effective_security_pin_policy,
    mint_pin_session_key,
    normalize_security_pin_policy,
    pinned_page_title_records,
    resolve_shortcut_entity_icon,
    resolve_shortcut_live_state,
    shortcut_records,
)
from ..protocol_specs import (
    DEVICE_PREF_KEYS,
    MAX_DOCK_ITEMS,
    MAX_GRID_COLS,
    MAX_GRID_ROWS,
    MAX_PINNED_ITEMS,
    normalize_activity_sources,
    normalize_area_categories,
    normalize_dock_items,
    normalize_games_items,
    normalize_home_categories,
    normalize_pinned_items,
    normalize_pinned_page_titles,
    normalize_tools_items,
    resolve_device_pref_value,
    sanitize_shortcut_label,
    tile_grid_dims_for_screen,
)
from ..remotes import (
    build_remote_config_payload,
    resolve_effective_remote_entities,
    resolve_remote_slot_pair,
)
from ..repairs import async_audit_coordinator_health
from ..repairs_keys import (
    ISSUE_OUTDATED_FIRMWARE,
    ISSUE_ROLLED_BACK,
    device_health_issue_id,
    evaluate_device_health,
    outdated_firmware_issue_id,
    parse_device_health,
    parse_firmware_core_rev,
)
from ..studio.settings_cleaners import clean_device_settings
from ..wallpapers.pools import resolve_photo_pool
from .area_follow import LatterAreaFollowController
from .runtime import LatterDeviceRuntime, get_rpc_receiver_factory

_LOGGER = logging.getLogger(__name__)

_UNSET: Any = object()
_MAC_COLON_LEN = 17
_MAC_COLON_COUNT = 5
_HEX_COLOR_LEN = 7
_MIN_MEDIA_DIM = 64
_MAX_MEDIA_DIM = 1920
_MAX_SLOT_CAPACITY = 20
_MIN_ROTATION_POOL_LEN = 2
_BLE_REF_MIN_DBM = -90
_BLE_REF_MAX_DBM = -30
_BLE_OFFSET_MAX_DB = 25.0
_BLE_ATTEN_MIN = 1.5
_BLE_ATTEN_MAX = 4.5
_BLE_RADIUS_MIN_M = 2.0
_BLE_RADIUS_MAX_M = 50.0
_BLE_VEL_MIN_MPS = 0.5
_BLE_VEL_MAX_MPS = 15.0
_BLE_AWAY_MIN_S = 30
_BLE_AWAY_MAX_S = 900
_DWELL_MIN_S = 3
_DWELL_MAX_S = 60
_RPC_OUTBOX_SUFFIXES: tuple[str, ...] = ("_system_rpc_outbox", "_rpc_outbox")
_RPC_OUTBOX_NAMES: tuple[str, ...] = ("System: RPC Outbox", "RPC Outbox")
_RPC_OUTBOX_UID_SUFFIXES: tuple[str, ...] = ("/text_sensor/System: RPC Outbox",)
_MIN_ALERT_DURATION_S = 2
_RECONNECT_SYNC_DEDUP_S = 5.0
_DISPLAY_SHAPE_MAP: dict[str, str] = {
    "circle": "circle",
    "square": "square",
    "rect": "square",
    "rectangle": "square",
    "none": "none",
}
_CAPABILITY_GATED_ENTITIES: tuple[tuple[str, str, str], ...] = (
    ("sensor", "timer_ends", "display"),
    ("binary_sensor", "timer_active", "display"),
    ("binary_sensor", "alarm_ringing", "display"),
    ("light", "screen", "display"),
    ("button", "dismiss_alert", "display"),
    ("select", "glass_style", "display"),
    ("switch", "bedtime_mode", "display"),
    ("switch", "screensaver", "display"),
    ("select", "wake_word_mode", "mic"),
    ("button", "find_my_device", "speaker"),
    ("number", "alert_volume", "speaker"),
    ("switch", "do_not_disturb", "display_or_speaker"),
)
_MAX_ALERT_DURATION_S = 60
_MAX_REMOTE_SLOTS = 10


def _normalize_hmac_secret(raw: bytes | str) -> bytes:
    if isinstance(raw, bytes):
        return raw
    clean = str(raw).strip()
    try:
        return bytes.fromhex(clean)
    except ValueError:
        return clean.encode("utf-8")


def _parse_bool_flag(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _parse_opt_bool(val: Any) -> bool | None:
    if val is None or str(val).strip() == "":
        return None
    return _parse_bool_flag(val)


def _parse_kb(val: Any) -> int | None:
    if val is None or isinstance(val, bool) or str(val).strip() == "":
        return None
    try:
        iv = round(float(val))
        return iv if iv >= 0 else None
    except (TypeError, ValueError):
        return None


class _TaskReentrantLock:
    """Asyncio lock re-entrant within the same `asyncio.Task`, mutually exclusive across tasks."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task[Any] | None = None
        self._depth: int = 0

    def locked(self) -> bool:
        return self._lock.locked()

    async def acquire(self) -> bool:
        cur_task = asyncio.current_task()
        if cur_task is not None and self._owner is cur_task:
            self._depth += 1
            return True
        await self._lock.acquire()
        self._owner = cur_task
        self._depth = 1
        return True

    def release(self) -> None:
        self._depth -= 1
        if self._depth <= 0:
            self._depth = 0
            self._owner = None
            self._lock.release()

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.release()


_PRESENCE_OPTION_KEYS: tuple[str, ...] = (
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_DEFAULT_AREA,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BLE_CATEGORY,
    CONF_BLE_REF_POWER,
    CONF_AREA_FOLLOW_DWELL_S,
)


def _presence_options_changed(
    prev_snap: Mapping[str, Any], new_snap: Mapping[str, Any]
) -> bool:
    """Return True when title or presence/BLE/Area subentry options changed."""
    if prev_snap.get("title") != new_snap.get("title"):
        return True
    prev_data = prev_snap.get("data")
    new_data = new_snap.get("data")
    if not isinstance(prev_data, Mapping) or not isinstance(new_data, Mapping):
        return True
    return any(prev_data.get(k) != new_data.get(k) for k in _PRESENCE_OPTION_KEYS)


class LatterCoordinator:
    """Pure push coordinator managing Protocol v3 domains, BLE presence, media, and Area state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        hmac_secret: bytes | str,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the push `LatterCoordinator` for one Device or BLE Tag subentry."""
        secret_bytes = _normalize_hmac_secret(hmac_secret)
        self.hass = hass
        self.entry = entry
        self.config_entry = entry
        self.subentry = subentry
        self.subentry_id = subentry.subentry_id
        self.name = f"{DOMAIN}_{self.subentry_id}"
        self._listeners: dict[Callable[[], None], None] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self.config_lock = _TaskReentrantLock()
        self.device_config_rev = 1
        self._hmac_secret = secret_bytes
        self._runtime = LatterDeviceRuntime(hass, self.subentry_id)
        self._url_signer = UrlSigner(hass, self.subentry_id, secret_bytes)
        self._packer = DomainPayloadPacker()
        self._area_follow = LatterAreaFollowController(hass)
        self._cached_esphome_device_id: str | None = None
        self._bound_entities_cache: dict[str, tuple[er.RegistryEntry, ...]] | None = None
        self._bound_entities_cache_key: tuple[str, int] | None = None
        self.rev = 1
        self._notify_debouncer: Debouncer[Coroutine[Any, Any, None]] = Debouncer(
            hass,
            _LOGGER,
            cooldown=0.2,
            immediate=False,
            function=self._async_debounced_notify,
        )
        rpc_factory = get_rpc_receiver_factory()
        self._rpc_receiver: Any = (
            rpc_factory(hass, self) if rpc_factory is not None else None
        )
        self._init_caches_and_timers()
        self._init_telemetry_and_ble()
        self._init_media_state()
        self._init_feeds_and_alerts()
        self._structural_snapshot = self._capture_structural_snapshot()
        self._applied_options_snapshot = self._capture_options_snapshot()
        self._suppress_update_listener_apply: bool = False

    def _init_caches_and_timers(self) -> None:
        self._cached_media_payload: tuple[float, tuple[str | None, dict[str, Any]]] | None = None
        self._cached_media_anchor: tuple[tuple[Any, ...], float] | None = None
        self._cached_area_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._last_ambient_light: tuple[str, int | None, str] = ("", None, "")
        self._cached_remote_payload: tuple[float, tuple[str | None, dict[str, Any]]] | None = None
        self._cached_prefs_payload: tuple[int, dict[str, Any]] | None = None
        self._cached_shortcuts_payload: tuple[int, tuple[str, ...]] | None = None
        self.prefs_seq: int = 0
        self.prefs_key_seq: dict[str, int] = {}
        self.timer_running: bool = False
        self.timer_paused: bool = False
        self.timer_remaining_sec: int = 0
        self._timer_anchor_mono: float = 0.0
        self.timer_ends_at_dt: datetime | None = None
        self.timer_ends_at_utc: str = ""
        self.stopwatch_running: bool = False
        self.stopwatch_paused: bool = False
        self.stopwatch_elapsed_sec: int = 0
        self._stopwatch_anchor_mono: float = 0.0
        self.stopwatch_started_at_utc: str = ""
        self.alarm_ringing: bool = False
        self._unsub_core_config: Callable[[], None] | None = None
        self._unsub_speaker_state: Callable[[], None] | None = None
        self._tracked_ma_counterpart: str | None = None
        self._unsub_alarm_state: Callable[[], None] | None = None
        self._unsub_remotes_state: Callable[[], None] | None = None
        self._unsub_shortcuts_state: Callable[[], None] | None = None
        self._unsub_area_entities_state: Callable[[], None] | None = None
        self._unsub_area_debounce: Callable[[], None] | None = None
        self._unsub_wallpaper_timer: Callable[[], None] | None = None
        self._unsub_screensaver_timer: Callable[[], None] | None = None
        self._unsub_doorbell_ring_state: Callable[[], None] | None = None
        self._unsub_reconnect_post_delay: Callable[[], None] | None = None
        self._transport_reconnect_sync_mono: float = 0.0

    def _init_telemetry_and_ble(self) -> None:
        self._entered_hibernate: bool = False
        self._pin_key_id: str = ""
        self._pin_key_bytes: bytes = b""
        self._pin_last_nonce: int = 0
        self.pin_lockout = PinLockoutTracker()
        self.display_power_state: int = 0
        self.display_brightness_pct: int = self._initial_brightness_pct()
        self.device_telemetry: dict[str, Any] = {
            "link": {},
            "int_ram_free_kb": None,
            "int_ram_min_kb": None,
            "int_ram_largest_kb": None,
            "psram_min_kb": None,
            "ble_active": None,
            "profiler_on": False,
            "updated_at": None,
        }
        self._matched_ble_addresses: list[str] = []
        self._doorbell_ring_map: dict[str, str] = {}
        self._doorbell_ring_cooldown_until: dict[str, float] = {}
        self._ble_tracker: LatterNativeBleTracker | None = None
        self._last_pushed_v3: dict[str, str] = {}
        self.active_speaker: str = (
            str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() or self.local_speaker
        )
        self.last_speaker: str = self.active_speaker
        self.active_area_id: str | None = self.get_opt(CONF_DEFAULT_AREA)
        self.active_remote_slot: int = 1
        self.last_area_filter: str = "scene"
        self.last_area_page: int = 1
        self.on_area_changed_push_slots: Callable[[Any], Any] | None = None

    def _init_media_state(self) -> None:
        self.last_media_uri: str = ""
        self.last_media_type: str = "music"
        self.last_media_title: str = ""
        self.last_media_artist: str = ""
        self.last_media_album: str = ""
        self.last_media_duration: float = 0.0
        self.last_media_position: float = 0.0
        self._persisted_media_position: float = 0.0
        self._resuming_guard_until: float = 0.0
        self._local_needs_cold_resume: bool = True
        self._browsed_album_track_uris: list[str] = []
        self._lyrics_watch_active: bool = False
        self._last_pushed_lyrics_key: str = ""
        self._media_favorite_overrides: dict[str, tuple[bool, bool | None]] = {}
        self.last_valid_raw_pic: str = ""
        self._last_art_track_key: str = ""
        self._last_art_proxy_url: str = ""
        self._transfer_hold_until: float = 0.0
        self._transfer_hold_spinup_until: float = 0.0
        self._transfer_hold_position: float = 0.0
        self._transfer_hold_title: str = ""
        self._transfer_hold_artist: str = ""
        self._transfer_hold_album: str = ""
        self._transfer_hold_duration: float = 0.0
        self._transfer_hold_track_key: str = ""

    def _init_feeds_and_alerts(self) -> None:
        self.forecast_records: V3Records = V3Records()
        self.weather_attributes: dict[str, Any] = init_weather_attributes(
            self.pack_domain_payload
        )
        self.calendar_records: V3Records = V3Records()
        self.calendar_events: list[dict[str, Any]] = []
        self._last_cal_window: tuple[date, date] | None = None
        self.alert_id: int = 0
        self.alert_title: str = ""
        self.alert_message: str = ""
        self.alert_priority: str = "normal"
        self.alert_duration: int = 8
        self.alert_chime: bool = True
        self.alert_camera_url: str = ""
        self.alert_camera_entity: str = ""
        self.active_carousel_camera: str = ""
        self.doorbell_talk_state: str = "idle"
        self.last_device_health: dict[str, Any] | None = None
        self._doorbell_reply_task: asyncio.Task[Any] | None = None
        self._doorbell_reply_resume_listen: bool = False
        self.doorbell_noise_reduction: str = normalize_noise_reduction(
            self.get_opt(
                CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION
            )
        )
        self._configured_wallpaper_source: str = str(
            self.get_opt(CONF_WALLPAPER_SOURCE, "") or ""
        ).strip()
        self._configured_default_area: str = str(
            self.get_opt(CONF_DEFAULT_AREA, "") or ""
        ).strip()
        self._configured_ble_tracking: bool = self.native_ble_tracking_enabled
        self._configured_default_speaker: str = (
            self._resolved_configured_default_speaker()
        )
        self._last_esp_area: str = ""
        self._last_latter_area: str = ""
        self.current_wallpaper: str = ""
        self.current_screensaver_photo: str = ""
        self._doorbell_talk_lock: asyncio.Lock = asyncio.Lock()

    def _resolved_configured_default_speaker(self) -> str:
        target = (
            str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() or self.local_speaker
        )
        if self.local_speaker and target and self.is_local_speaker_entity(target):
            return self.local_speaker
        return target

    def _initial_brightness_pct(self) -> int:
        raw_bri = resolve_device_pref_value(
            self._live_subentry().data, "manual_brightness"
        )
        try:
            return max(1, min(100, round(float(raw_bri))))
        except (TypeError, ValueError):
            return 80

    # -----------------------------------------------------------------------
    # Live Subentry, Persistence, Tasks, Listeners & Typed Runtime Properties
    # -----------------------------------------------------------------------

    def _live_subentry(self) -> ConfigSubentry:
        live_sub = self.entry.subentries.get(self.subentry_id)
        if live_sub is not None:
            self.subentry = live_sub
        return self.subentry

    @callback
    def schedule_persist_runtime_state(self) -> None:
        """Schedule change-gated persistence of the Device runtime snapshot."""
        self._runtime.schedule_save(self._build_persisted_snapshot)

    @callback
    def create_background_task(
        self, coro: Coroutine[Any, Any, Any], name: str
    ) -> asyncio.Task[Any]:
        """Spawn a tracked background task cancelled automatically on `async_cleanup()`."""
        if hasattr(self.entry, "async_create_background_task"):
            task: asyncio.Task[Any] = self.entry.async_create_background_task(
                self.hass, coro, name
            )
        else:
            task = self.hass.async_create_task(coro, name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    @callback
    def cancel_background_tasks(self) -> None:
        """Cancel all in-flight coordinator background tasks."""
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        self._background_tasks.clear()

    @callback
    def sync_persisted_media_position(self) -> None:
        """Snapshot the current in-memory media position for `.storage` persistence."""
        self._persisted_media_position = self.last_media_position

    @callback
    def async_update_listeners(self) -> None:
        """Notify all registered push listeners."""
        for cb in list(self._listeners):
            cb()

    @callback
    def async_add_listener(
        self, update_callback: Callable[[], None], context: Any = None
    ) -> Callable[[], None]:
        """Register an entity or Studio push listener and return its unsubscribe callback."""
        _ = context
        self._listeners[update_callback] = None

        @callback
        def _remove() -> None:
            self._listeners.pop(update_callback, None)

        unsub: Callable[[], None] = _remove
        return unsub

    @property
    def ble_tracker(self) -> LatterNativeBleTracker | None:
        """Return the active `LatterNativeBleTracker` instance, if BLE tracking is enabled."""
        return self._ble_tracker

    @property
    def rpc_receiver(self) -> Any:
        """Return the attached `LatterRpcReceiver`, if any."""
        return self._rpc_receiver

    @callback
    def attach_rpc_receiver(self, receiver: Any) -> None:
        """Attach a `LatterRpcReceiver` instance to this coordinator."""
        self._rpc_receiver = receiver

    @property
    def cached_area_payload(
        self,
    ) -> tuple[float, tuple[str, dict[str, Any]]] | None:
        return self._cached_area_payload

    @cached_area_payload.setter
    def cached_area_payload(
        self, value: tuple[float, tuple[str, dict[str, Any]]] | None
    ) -> None:
        self._cached_area_payload = value

    @property
    def last_ambient_light(self) -> tuple[str, int | None, str]:
        return self._last_ambient_light

    @last_ambient_light.setter
    def last_ambient_light(self, value: tuple[str, int | None, str]) -> None:
        self._last_ambient_light = value

    @callback
    def replace_area_debounce_unsub(
        self, unsub: Callable[[], None] | None
    ) -> None:
        """Cancel any pending Area slot push debounce timer and record `unsub`."""
        prev = self._unsub_area_debounce
        self._unsub_area_debounce = unsub
        if prev is not None and prev is not unsub:
            prev()

    @callback
    def replace_area_listener_unsubs(
        self,
        *,
        area_entities: Any = _UNSET,
        alarm: Any = _UNSET,
        remotes: Any = _UNSET,
        shortcuts: Any = _UNSET,
    ) -> None:
        """Replace one or all Area/Home/Remotes/Shortcuts state listener unsubscribe callbacks."""
        if (
            area_entities is _UNSET
            and alarm is _UNSET
            and remotes is _UNSET
            and shortcuts is _UNSET
        ):
            area_entities = alarm = remotes = shortcuts = None
        for attr, new_unsub in (
            ("_unsub_area_entities_state", area_entities),
            ("_unsub_alarm_state", alarm),
            ("_unsub_remotes_state", remotes),
            ("_unsub_shortcuts_state", shortcuts),
        ):
            if new_unsub is _UNSET:
                continue
            prev = getattr(self, attr, None)
            setattr(self, attr, new_unsub)
            if prev is not None and prev is not new_unsub:
                prev()

    @property
    def cached_remote_payload(
        self,
    ) -> tuple[float, tuple[str | None, dict[str, Any]]] | None:
        return self._cached_remote_payload

    @cached_remote_payload.setter
    def cached_remote_payload(
        self, value: tuple[float, tuple[str | None, dict[str, Any]]] | None
    ) -> None:
        self._cached_remote_payload = value

    @property
    def doorbell_talk_lock(self) -> asyncio.Lock:
        return self._doorbell_talk_lock

    @property
    def doorbell_reply_task(self) -> asyncio.Task[Any] | None:
        return self._doorbell_reply_task

    @doorbell_reply_task.setter
    def doorbell_reply_task(self, value: asyncio.Task[Any] | None) -> None:
        self._doorbell_reply_task = value

    @property
    def doorbell_reply_resume_listen(self) -> bool:
        return self._doorbell_reply_resume_listen

    @doorbell_reply_resume_listen.setter
    def doorbell_reply_resume_listen(self, value: bool) -> None:
        self._doorbell_reply_resume_listen = bool(value)

    @property
    def doorbell_ring_cooldown_until(self) -> dict[str, float]:
        return self._doorbell_ring_cooldown_until

    @property
    def doorbell_ring_map(self) -> dict[str, str]:
        return dict(self._doorbell_ring_map)

    @callback
    def set_doorbell_ring_map(self, ring_map: dict[str, str]) -> None:
        self._doorbell_ring_map = dict(ring_map)

    @callback
    def replace_doorbell_ring_unsub(
        self, unsub: Callable[[], None] | None
    ) -> None:
        prev = self._unsub_doorbell_ring_state
        self._unsub_doorbell_ring_state = unsub
        if prev is not None and prev is not unsub:
            prev()

    @property
    def cached_media_payload(
        self,
    ) -> tuple[float, tuple[str | None, dict[str, Any]]] | None:
        return self._cached_media_payload

    @cached_media_payload.setter
    def cached_media_payload(
        self, value: tuple[float, tuple[str | None, dict[str, Any]]] | None
    ) -> None:
        self._cached_media_payload = value

    @property
    def cached_media_anchor(self) -> tuple[tuple[Any, ...], float] | None:
        return self._cached_media_anchor

    @cached_media_anchor.setter
    def cached_media_anchor(
        self, value: tuple[tuple[Any, ...], float] | None
    ) -> None:
        self._cached_media_anchor = value

    @callback
    def replace_speaker_state_unsub(
        self, unsub: Callable[[], None] | None
    ) -> None:
        prev = self._unsub_speaker_state
        self._unsub_speaker_state = unsub
        if prev is not None and prev is not unsub:
            prev()

    @property
    def tracked_ma_counterpart(self) -> str | None:
        return self._tracked_ma_counterpart

    @tracked_ma_counterpart.setter
    def tracked_ma_counterpart(self, value: str | None) -> None:
        self._tracked_ma_counterpart = value

    @property
    def lyrics_watch_active(self) -> bool:
        return self._lyrics_watch_active

    @lyrics_watch_active.setter
    def lyrics_watch_active(self, value: bool) -> None:
        self._lyrics_watch_active = bool(value)

    @property
    def last_pushed_lyrics_key(self) -> str:
        return self._last_pushed_lyrics_key

    @last_pushed_lyrics_key.setter
    def last_pushed_lyrics_key(self, value: str) -> None:
        self._last_pushed_lyrics_key = value

    @property
    def media_favorite_overrides(self) -> dict[str, tuple[bool, bool | None]]:
        return self._media_favorite_overrides

    @property
    def local_needs_cold_resume(self) -> bool:
        return self._local_needs_cold_resume

    @local_needs_cold_resume.setter
    def local_needs_cold_resume(self, value: bool) -> None:
        self._local_needs_cold_resume = bool(value)

    @property
    def resuming_guard_until(self) -> float:
        return self._resuming_guard_until

    @resuming_guard_until.setter
    def resuming_guard_until(self, value: float) -> None:
        self._resuming_guard_until = float(value)

    @property
    def browsed_album_track_uris(self) -> list[str]:
        return self._browsed_album_track_uris

    @browsed_album_track_uris.setter
    def browsed_album_track_uris(self, value: list[str]) -> None:
        self._browsed_album_track_uris = list(value)

    @property
    def last_art_track_key(self) -> str:
        return self._last_art_track_key

    @last_art_track_key.setter
    def last_art_track_key(self, value: str) -> None:
        self._last_art_track_key = value

    @property
    def last_art_proxy_url(self) -> str:
        return self._last_art_proxy_url

    @last_art_proxy_url.setter
    def last_art_proxy_url(self, value: str) -> None:
        self._last_art_proxy_url = value

    @property
    def transfer_hold_until(self) -> float:
        return self._transfer_hold_until

    @transfer_hold_until.setter
    def transfer_hold_until(self, value: float) -> None:
        self._transfer_hold_until = float(value)

    @property
    def transfer_hold_spinup_until(self) -> float:
        return self._transfer_hold_spinup_until

    @transfer_hold_spinup_until.setter
    def transfer_hold_spinup_until(self, value: float) -> None:
        self._transfer_hold_spinup_until = float(value)

    @property
    def transfer_hold_position(self) -> float:
        return self._transfer_hold_position

    @transfer_hold_position.setter
    def transfer_hold_position(self, value: float) -> None:
        self._transfer_hold_position = float(value)

    @property
    def transfer_hold_title(self) -> str:
        return self._transfer_hold_title

    @transfer_hold_title.setter
    def transfer_hold_title(self, value: str) -> None:
        self._transfer_hold_title = value

    @property
    def transfer_hold_artist(self) -> str:
        return self._transfer_hold_artist

    @transfer_hold_artist.setter
    def transfer_hold_artist(self, value: str) -> None:
        self._transfer_hold_artist = value

    @property
    def transfer_hold_album(self) -> str:
        return self._transfer_hold_album

    @transfer_hold_album.setter
    def transfer_hold_album(self, value: str) -> None:
        self._transfer_hold_album = value

    @property
    def transfer_hold_duration(self) -> float:
        return self._transfer_hold_duration

    @transfer_hold_duration.setter
    def transfer_hold_duration(self, value: float) -> None:
        self._transfer_hold_duration = float(value)

    @property
    def transfer_hold_track_key(self) -> str:
        return self._transfer_hold_track_key

    @transfer_hold_track_key.setter
    def transfer_hold_track_key(self, value: str) -> None:
        self._transfer_hold_track_key = value

    @property
    def pin_session_key_id(self) -> str:
        return self._pin_key_id

    @property
    def pin_session_key_bytes(self) -> bytes:
        return self._pin_key_bytes

    @property
    def pin_last_nonce(self) -> int:
        return self._pin_last_nonce

    @callback
    def record_pin_nonce(self, nonce: int) -> None:
        self._pin_last_nonce = max(self._pin_last_nonce, int(nonce))

    @property
    def last_cal_window(self) -> tuple[date, date] | None:
        return self._last_cal_window

    @last_cal_window.setter
    def last_cal_window(self, value: tuple[date, date] | None) -> None:
        self._last_cal_window = value

    # -----------------------------------------------------------------------
    # Device Identity, Hardware Manifest Traits, Option Getters & Signed URLs
    # -----------------------------------------------------------------------

    @property
    def device_data(self) -> dict[str, Any]:
        """Return a shallow copy of the live subentry option dictionary."""
        return dict(self._live_subentry().data)

    def update_device_config(
        self,
        merged_data: dict[str, Any],
        *,
        bump_prefs_seq: bool = True,
        preserve_group: bool = False,
        mark_applied: bool = False,
        defer_apply: bool = False,
    ) -> None:
        """Persist updated subentry data and advance `prefs_seq` / `device_config_rev`."""
        live_sub = self._live_subentry()
        prev = live_sub.data
        if not self.is_ble_tag and not preserve_group:
            eff_grp = resolve_effective_device_group(
                self.hass, self, candidate_data=merged_data
            )
            if merged_data.get(CONF_DEVICE_GROUP) != eff_grp:
                merged_data = {**merged_data, CONF_DEVICE_GROUP: eff_grp}
        if dict(prev) == merged_data:
            return
        if bump_prefs_seq:
            changed_pref_keys = self._compute_changed_pref_keys(prev, merged_data)
            if changed_pref_keys:
                self.prefs_seq = max(1, self.prefs_seq + 1)
                for key in changed_pref_keys:
                    self.prefs_key_seq[key] = self.prefs_seq
                self._cached_prefs_payload = None
                if "world_clocks" in changed_pref_keys:
                    self._cached_area_payload = None
        if mark_applied:
            self._applied_options_snapshot = {
                "title": str(live_sub.title or ""),
                "data": dict(merged_data),
            }
        prev_suppress = self._suppress_update_listener_apply
        if defer_apply:
            # Stay suppressed until the caller's `async_apply_options()` runs so concurrent
            # batch updates on sibling subentries cannot trigger a duplicate listener apply.
            self._suppress_update_listener_apply = True
        try:
            self.hass.config_entries.async_update_subentry(
                self.entry, live_sub, data=merged_data
            )
        except Exception:
            self._suppress_update_listener_apply = prev_suppress
            raise
        if (
            prev.get(CONF_DOCK_ITEMS) != merged_data.get(CONF_DOCK_ITEMS)
            or prev.get(CONF_PINNED_ITEMS) != merged_data.get(CONF_PINNED_ITEMS)
            or prev.get(CONF_PINNED_PAGE_TITLES)
            != merged_data.get(CONF_PINNED_PAGE_TITLES)
        ):
            self._cached_shortcuts_payload = None
        self._live_subentry()
        self.device_config_rev = max(1, self.device_config_rev + 1)
        self.schedule_persist_runtime_state()

    @staticmethod
    def _compute_changed_pref_keys(
        prev: Any, merged_data: dict[str, Any]
    ) -> list[str]:
        changed: list[str] = [
            key
            for key in DEVICE_PREF_KEYS
            if resolve_device_pref_value(merged_data, key)
            != resolve_device_pref_value(prev, key)
        ]
        if bool(
            merged_data.get(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)
        ) != bool(prev.get(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)):
            changed.append(CONF_NATIVE_BLE_TRACKING)
        if (
            str(merged_data.get(CONF_DEVICE_CUSTOM_COLOR) or "").strip().upper()
            != str(prev.get(CONF_DEVICE_CUSTOM_COLOR) or "").strip().upper()
        ):
            changed.append(CONF_DEVICE_CUSTOM_COLOR)
        for csv_key, csv_default, csv_norm in (
            (CONF_TOOLS_ITEMS, DEFAULT_TOOLS_ITEMS, normalize_tools_items),
            (CONF_GAMES_ITEMS, DEFAULT_GAMES_ITEMS, normalize_games_items),
        ):
            try:
                new_csv = csv_norm(merged_data.get(csv_key, csv_default))
            except ValueError:
                new_csv = csv_default
            try:
                old_csv = csv_norm(prev.get(csv_key, csv_default))
            except ValueError:
                old_csv = csv_default
            if new_csv != old_csv:
                changed.append(csv_key)
        return changed

    def get_opt(self, key: str, default: Any = None) -> Any:
        """Read a System-scoped (`GLOBAL_CONFIG_KEYS`) or Device-scoped option value."""
        if key in GLOBAL_CONFIG_KEYS:
            global_cfg = peek_global_config(self.hass)
            if key in global_cfg and global_cfg[key] is not None:
                return global_cfg[key]
            return default
        sub_data = self._live_subentry().data
        if key in sub_data:
            return sub_data[key]
        return default

    @property
    def device_slug(self) -> str:
        return normalize_device_slug(
            str(self._live_subentry().data.get(CONF_DEVICE_SLUG) or "")
        )

    @property
    def device_mac(self) -> str | None:
        stored_mac = str(self.get_opt("mac", "") or "").strip()
        if stored_mac:
            return str(dr.format_mac(stored_mac))
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        if esp_dev is not None:
            for ctype, cval in esp_dev.connections:
                if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                    return str(dr.format_mac(str(cval)))
        ble_addr = str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()
        return (
            str(dr.format_mac(ble_addr))
            if len(ble_addr) == _MAC_COLON_LEN and ble_addr.count(":") == _MAC_COLON_COUNT
            else None
        )

    @property
    def device_title(self) -> str:
        if not self.is_ble_tag and self.esphome_device_id:
            esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
            if esp_dev is not None:
                live_name = str(esp_dev.name_by_user or esp_dev.name or "").strip()
                if live_name:
                    return live_name
        return (
            self.subentry.title
            if self._live_subentry().title
            else self.device_slug.replace("_", " ").title()
        )

    @property
    def esphome_device_id(self) -> str | None:
        dev_reg = dr.async_get(self.hass)
        if (
            self._cached_esphome_device_id
            and dev_reg.async_get(self._cached_esphome_device_id) is not None
        ):
            return self._cached_esphome_device_id
        stored = str(self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or "").strip() or None
        stored_mac = str(self.get_opt("mac", "") or "").strip() or None
        self._cached_esphome_device_id = resolve_bound_esphome_device_id(
            self.hass, stored, stored_mac
        )
        return self._cached_esphome_device_id

    @callback
    def invalidate_bound_entity_cache(self) -> None:
        """Clear the cached bound ESPHome entity lookup map."""
        self._bound_entities_cache = None
        self._bound_entities_cache_key = None

    def _bound_esphome_entities(self, domain: str) -> tuple[er.RegistryEntry, ...]:
        esp_dev_id = self.esphome_device_id
        if not esp_dev_id:
            return ()
        idx = get_area_state_index(self.hass)
        if idx.started:
            cache_key = (esp_dev_id, idx.registry_rev)
            if (
                self._bound_entities_cache is not None
                and self._bound_entities_cache_key == cache_key
            ):
                return self._bound_entities_cache.get(domain, ())
            by_domain: dict[str, list[er.RegistryEntry]] = {}
            for entry in device_entities(self.hass, esp_dev_id):
                by_domain.setdefault(entry.domain, []).append(entry)
            self._bound_entities_cache = {
                dom: tuple(items) for dom, items in by_domain.items()
            }
            self._bound_entities_cache_key = cache_key
            return self._bound_entities_cache.get(domain, ())
        return tuple(device_entities(self.hass, esp_dev_id, domain=domain))

    def device_entity(
        self,
        domain: str,
        *suffixes: str,
        original_names: tuple[str, ...] = (),
        unique_id_suffixes: tuple[str, ...] = (),
    ) -> str | None:
        entries = self._bound_esphome_entities(domain)
        for sfx in suffixes:
            for entry in entries:
                if not sfx or entry.entity_id.endswith(sfx):
                    return str(entry.entity_id)
        for orig in original_names:
            for entry in entries:
                if (entry.original_name or "") == orig:
                    return str(entry.entity_id)
        for uid_sfx in unique_id_suffixes:
            for entry in entries:
                if uid_sfx and (entry.unique_id or "").endswith(uid_sfx):
                    return str(entry.entity_id)
        return None

    def device_state(self, domain: str, *suffixes: str) -> State | None:
        ent_id = self.device_entity(domain, *suffixes)
        return self.hass.states.get(ent_id) if ent_id else None

    @property
    def url_signer(self) -> UrlSigner:
        return self._url_signer

    @property
    def device_identifiers(self) -> set[tuple[str, str]]:
        """Return canonical Device Registry identifiers for this bound Latter Device."""
        mac = self.device_mac
        ident_key = dr.format_mac(mac) if mac else self.subentry_id
        return {(DOMAIN, ident_key)}

    def get_device_info(self) -> DeviceInfo:
        esp_dev_id = self.esphome_device_id
        info = DeviceInfo(
            identifiers=self.device_identifiers,
            name=self.device_title,
            manufacturer="Latter",
            model="Latter ESPHome Companion Middleware",
            sw_version=INTEGRATION_VERSION,
            configuration_url=f"homeassistant://latter/devices/{self.subentry_id}",
        )
        if esp_dev_id:
            info.via_device_id = esp_dev_id
        return info

    @property
    def local_speaker(self) -> str:
        return resolve_esphome_local_speaker(self.hass, self.esphome_device_id)

    @property
    def local_ma_speaker(self) -> str:
        return resolve_ma_counterpart_entity(self.hass, self.local_speaker) or ""

    def is_local_speaker_entity(self, speaker_entity_id: str | None) -> bool:
        spk = str(speaker_entity_id or "").strip()
        return bool(spk and spk in (self.local_speaker, self.local_ma_speaker))

    @property
    def site_id(self) -> str:
        return str(self.get_opt(CONF_SITE_ID, DEFAULT_SITE_ID) or DEFAULT_SITE_ID).strip()

    @property
    def hardware_manifest(self) -> dict[str, Any]:
        return read_device_hardware_manifest(
            self.hass,
            self.esphome_device_id,
            cached_manifest=self._runtime.hello_manifest,
        )

    @property
    def is_ble_tag(self) -> bool:
        return bool(self.subentry.subentry_type == SUBENTRY_BLE_TAG)

    @property
    def has_display(self) -> bool:
        return not self.is_ble_tag and manifest_has_display(self.hardware_manifest)

    @property
    def has_touch(self) -> bool:
        return not self.is_ble_tag and manifest_has_touch(self.hardware_manifest)

    @property
    def has_mic(self) -> bool:
        return not self.is_ble_tag and manifest_has_mic(self.hardware_manifest)

    @property
    def has_speaker(self) -> bool:
        return not self.is_ble_tag and manifest_has_speaker(self.hardware_manifest)

    @property
    def has_audio(self) -> bool:
        return not self.is_ble_tag and manifest_has_audio(self.hardware_manifest)

    @property
    def has_imu(self) -> bool:
        return not self.is_ble_tag and manifest_has_imu(self.hardware_manifest)

    @property
    def has_battery(self) -> bool:
        return not self.is_ble_tag and manifest_has_battery(self.hardware_manifest)

    @property
    def has_ble_beacon(self) -> bool:
        if self.is_ble_tag:
            return False
        hw = self.hardware_manifest
        if not hw:
            return True
        return (
            isinstance(hw.get("beacon"), dict)
            or hw.get("minor") is not None
            or self.device_telemetry.get("ble_active") is not None
        )

    @property
    def screensaver_active(self) -> bool:
        """Return True when the Device display is currently in screensaver power state (`1`)."""
        return self.display_power_state == 1

    @property
    def do_not_disturb(self) -> bool:
        """Return True when Do Not Disturb is active on this Device."""
        return bool(self.get_device_pref(CONF_DO_NOT_DISTURB))

    @property
    def is_round_display(self) -> bool:
        return self.has_display and manifest_is_round(self.hardware_manifest)

    @property
    def screen_width(self) -> int:
        if self.is_ble_tag or not self.has_display:
            return 0
        val = manifest_flag(self.hardware_manifest, "w")
        return val if val is not None and val > 0 else 0

    @property
    def screen_height(self) -> int:
        if self.is_ble_tag or not self.has_display:
            return 0
        val = manifest_flag(self.hardware_manifest, "h")
        return val if val is not None and val > 0 else 0

    def _resolved_grid_dims(self) -> tuple[int, int]:
        if self.is_ble_tag or not self.has_display:
            return (2, 3)
        hw = self.hardware_manifest
        w, h = self.screen_width, self.screen_height
        fb_cols, fb_rows = (
            tile_grid_dims_for_screen(w, h, is_round=self.is_round_display)
            if (w > 0 and h > 0)
            else (2, 3)
        )
        raw_cols = manifest_flag(hw, "grid_cols")
        raw_rows = manifest_flag(hw, "grid_rows")
        cols = (
            raw_cols
            if raw_cols is not None and 1 <= raw_cols <= MAX_GRID_COLS
            else fb_cols
        )
        rows = (
            raw_rows
            if raw_rows is not None and 1 <= raw_rows <= MAX_GRID_ROWS
            else fb_rows
        )
        return (cols, rows)

    @property
    def grid_cols(self) -> int:
        return self._resolved_grid_dims()[0]

    @property
    def grid_rows(self) -> int:
        return self._resolved_grid_dims()[1]

    @property
    def supports_hw_jpeg(self) -> bool:
        return not self.is_ble_tag and manifest_supports_hw_jpeg(self.hardware_manifest)

    @property
    def video_max_dims(self) -> tuple[int, int]:
        if self.is_ble_tag or not self.has_display:
            return (0, 0)
        caps = manifest_video_caps(self.hardware_manifest)
        return (int(caps["max_w"]), int(caps["max_h"]))

    @property
    def video_max_fps(self) -> int:
        if self.is_ble_tag or not self.has_display:
            return 0
        return int(manifest_video_caps(self.hardware_manifest)["max_fps"])

    @property
    def video_grid_fps(self) -> int:
        if self.is_ble_tag or not self.has_display:
            return 0
        return int(manifest_video_caps(self.hardware_manifest)["grid_fps"])

    def get_device_pref(self, key: str) -> Any:
        return resolve_device_pref_value(self._live_subentry().data, key)

    @property
    def current_timer_remaining_sec(self) -> int:
        if not self.timer_running and not self.timer_paused:
            return 0
        if self.timer_paused or not self.timer_running:
            return max(0, int(self.timer_remaining_sec))
        elapsed = max(0.0, time.monotonic() - self._timer_anchor_mono)
        return max(0, round(self.timer_remaining_sec - elapsed))

    @property
    def current_stopwatch_elapsed_sec(self) -> int:
        if not self.stopwatch_running and not self.stopwatch_paused:
            return 0
        base = max(0, int(self.stopwatch_elapsed_sec))
        if not self.stopwatch_running:
            return base
        elapsed = max(0, int(time.monotonic() - self._stopwatch_anchor_mono))
        return base + elapsed

    @property
    def is_wearable(self) -> bool:
        return manifest_is_wearable(self.hardware_manifest)

    @property
    def is_roaming_device(self) -> bool:
        return manifest_is_roaming(self.hardware_manifest)

    @property
    def device_group(self) -> str:
        return resolve_effective_device_group(self.hass, self)

    @property
    def core_rev(self) -> str:
        """Return the reported Latter Core revision string from `device_hello`, or `''`."""
        raw = self.hardware_manifest.get("core_rev")
        return str(raw) if raw not in (None, "") else ""

    @property
    def firmware_outdated(self) -> bool:
        """Return True when the Device reports a positive `core_rev` below `MIN_FIRMWARE_CORE_REV`."""
        if self.is_ble_tag:
            return False
        rev = parse_firmware_core_rev(self.hardware_manifest)
        return rev is not None and 0 < rev < MIN_FIRMWARE_CORE_REV

    @property
    def display_shape(self) -> str:
        if not self.has_display:
            return _DISPLAY_SHAPE_MAP["none"]
        hw_shape = str(self.hardware_manifest.get("shape") or "").strip().lower()
        return _DISPLAY_SHAPE_MAP.get(hw_shape, DEFAULT_DISPLAY_SHAPE)

    @property
    def list_slot_capacity(self) -> int:
        try:
            raw = self.hardware_manifest.get("slot_count")
            val = int(raw) if raw is not None else DEFAULT_LIST_SLOT_COUNT
        except (TypeError, ValueError):
            val = DEFAULT_LIST_SLOT_COUNT
        return max(1, min(_MAX_SLOT_CAPACITY, val))

    @property
    def card_slot_capacity(self) -> int:
        try:
            raw = self.hardware_manifest.get("card_slot_count")
            val = int(raw) if raw is not None else DEFAULT_CARD_SLOT_COUNT
        except (TypeError, ValueError):
            val = DEFAULT_CARD_SLOT_COUNT
        return max(1, min(_MAX_SLOT_CAPACITY, val))

    @property
    def dock_items(self) -> list[Any]:
        return list(
            normalize_dock_items(
                self._live_subentry().data.get(CONF_DOCK_ITEMS), strict=False
            )
        )

    @property
    def pinned_items(self) -> list[Any]:
        return list(
            normalize_pinned_items(
                self._live_subentry().data.get(CONF_PINNED_ITEMS), strict=False
            )
        )

    @property
    def pinned_page_titles(self) -> dict[str, str]:
        return normalize_pinned_page_titles(
            self._live_subentry().data.get(CONF_PINNED_PAGE_TITLES), strict=False
        )

    @property
    def area_categories_csv(self) -> str:
        try:
            return normalize_area_categories(
                self.get_opt(CONF_AREA_CATEGORIES, DEFAULT_AREA_CATEGORIES)
            )
        except ValueError:
            return DEFAULT_AREA_CATEGORIES

    @property
    def home_categories_csv(self) -> str:
        try:
            return normalize_home_categories(
                self.get_opt(CONF_HOME_CATEGORIES, DEFAULT_HOME_CATEGORIES)
            )
        except ValueError:
            return DEFAULT_HOME_CATEGORIES

    @property
    def tools_items_csv(self) -> str:
        try:
            return normalize_tools_items(
                self.get_opt(CONF_TOOLS_ITEMS, DEFAULT_TOOLS_ITEMS)
            )
        except ValueError:
            return DEFAULT_TOOLS_ITEMS

    @property
    def games_items_csv(self) -> str:
        try:
            return normalize_games_items(
                self.get_opt(CONF_GAMES_ITEMS, DEFAULT_GAMES_ITEMS)
            )
        except ValueError:
            return DEFAULT_GAMES_ITEMS

    @property
    def activity_card_enabled(self) -> bool:
        return bool(self.get_opt(CONF_ACTIVITY_CARD, DEFAULT_ACTIVITY_CARD))

    @property
    def activity_sources_csv(self) -> str:
        try:
            return normalize_activity_sources(
                self.get_opt(CONF_ACTIVITY_SOURCES, DEFAULT_ACTIVITY_SOURCES)
            )
        except ValueError:
            return DEFAULT_ACTIVITY_SOURCES

    @property
    def custom_palettes(self) -> list[dict[str, str]]:
        val = self.get_opt(CONF_CUSTOM_PALETTES, [])
        if not isinstance(val, list):
            return []
        return [
            {
                "name": str(it.get("name") or it["hex"]).strip(),
                "hex": str(it["hex"]).strip().upper(),
            }
            for it in val
            if isinstance(it, dict) and it.get("hex")
        ]

    @property
    def device_custom_color(self) -> str:
        raw = str(self.get_opt(CONF_DEVICE_CUSTOM_COLOR, "") or "").strip().upper()
        if raw.startswith("#") and len(raw) == _HEX_COLOR_LEN:
            return raw
        return self.custom_palettes[0]["hex"] if self.custom_palettes else "#3898FF"

    @property
    def weather_entity(self) -> str | None:
        val = self.get_opt(CONF_WEATHER_ENTITY)
        return str(val) if val else None

    @property
    def alarm_entity(self) -> str | None:
        return str(self.get_opt(CONF_ALARM_ENTITY) or "").strip() or None

    @property
    def camera_entities(self) -> list[str]:
        raw_list = self.get_opt(CONF_CAMERA_ENTITIES)
        return (
            [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
            if isinstance(raw_list, list)
            else []
        )

    @property
    def camera_configs(self) -> dict[str, dict[str, Any]]:
        """Return sanitized per-camera configuration map (`label`, action toggles, `unlock_entity`)."""
        raw = self.get_opt(CONF_CAMERA_CONFIGS)
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for cam_id, entry in raw.items():
            cid = str(cam_id or "").strip()
            if cid.startswith("camera.") and isinstance(entry, dict):
                out[cid] = dict(entry)
        return out

    @staticmethod
    def _dedup_scoped_ids(
        raw: Any, allowed: set[str], limit: int
    ) -> list[str]:
        if not isinstance(raw, (list, tuple)):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in raw:
            cid = str(item or "").strip()
            if cid and cid in allowed and cid not in seen:
                seen.add(cid)
                out.append(cid)
        return out[:limit]

    @property
    def configured_camera_visible_entities(self) -> list[str]:
        return self._dedup_scoped_ids(
            self._live_subentry().data.get(CONF_CAMERA_VISIBLE_ENTITIES),
            set(self.camera_entities),
            10,
        )

    @property
    def visible_camera_entities(self) -> list[str]:
        configured = self.configured_camera_visible_entities
        return configured if configured else self.camera_entities

    @property
    def configured_camera_carousel_entities(self) -> list[str]:
        return self._dedup_scoped_ids(
            self._live_subentry().data.get(CONF_CAMERA_CAROUSEL_ENTITIES),
            set(self.visible_camera_entities),
            10,
        )

    @property
    def carousel_camera_entities(self) -> list[str]:
        configured = self.configured_camera_carousel_entities
        return configured if configured else self.visible_camera_entities

    @property
    def system_broadcast_speakers(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_BROADCAST_SPEAKERS, "media_player.", 32)

    @property
    def configured_broadcast_speaker_entities(self) -> list[str]:
        return self._dedup_scoped_ids(
            self._live_subentry().data.get(CONF_BROADCAST_SPEAKER_ENTITIES),
            set(self.system_broadcast_speakers),
            32,
        )

    @property
    def effective_broadcast_speakers(self) -> list[str]:
        configured = self.configured_broadcast_speaker_entities
        return configured if configured else self.system_broadcast_speakers

    @property
    def broadcast_phrases(self) -> list[str]:
        global_cfg = peek_global_config(self.hass) if self.hass is not None else {}
        if CONF_BROADCAST_PHRASES not in global_cfg:
            return list(DEFAULT_BROADCAST_PHRASES)
        raw = global_cfg.get(CONF_BROADCAST_PHRASES)
        if not isinstance(raw, (list, tuple)):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in raw:
            clean = str(item or "").strip()[:64]
            if clean and clean not in seen:
                seen.add(clean)
                out.append(clean)
        return out[:12]

    @property
    def camera_entity(self) -> str | None:
        cams = self.visible_camera_entities
        return cams[0] if cams else None

    def _clean_entity_list_opt(self, key: str, prefix: str, limit: int) -> list[str]:
        raw_list = self.get_opt(key)
        if not isinstance(raw_list, (list, tuple)):
            return []
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in raw_list:
            s = str(item or "").strip()
            if s.startswith(prefix) and s not in seen:
                seen.add(s)
                cleaned.append(s)
        return cleaned[:limit]

    @property
    def thermostat_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_THERMOSTAT_ENTITIES, "climate.", 8)

    @property
    def lock_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_LOCK_ENTITIES, "lock.", 8)

    @property
    def garage_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_GARAGE_ENTITIES, "cover.", 6)

    @property
    def vacuum_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_VACUUM_ENTITIES, "vacuum.", 6)

    @property
    def native_ble_tracking_enabled(self) -> bool:
        return bool(self.get_opt(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING))

    @property
    def derived_ble_beacon_uuid(self) -> str:
        """Return the auto-derived per-Device UUIDv5 from `CONF_SYSTEM_BLE_UUID` (or fallback)."""
        sub = self._live_subentry()
        sys_raw = str(self.get_opt(CONF_SYSTEM_BLE_UUID) or "").strip()
        if sys_raw and not self.is_ble_tag:
            seed = str(sub.unique_id or sub.subentry_id or self.device_slug).strip()
            return derive_device_beacon_uuid(sys_raw, seed)
        return (sys_raw or DEFAULT_BLE_BEACON_UUID).upper()

    @property
    def ble_beacon_uuid(self) -> str:
        sub = self._live_subentry()
        sub_raw = str(sub.data.get(CONF_BLE_BEACON_UUID) or "").strip()
        if sub_raw and normalize_uuid_hex(sub_raw) != normalize_uuid_hex(
            DEFAULT_BLE_BEACON_UUID
        ):
            return sub_raw.upper()
        return self.derived_ble_beacon_uuid

    @property
    def configured_security_pin_policy(self) -> str:
        return normalize_security_pin_policy(
            self.get_opt(CONF_SECURITY_PIN_POLICY, DEFAULT_SECURITY_PIN_POLICY)
        )

    @property
    def security_pin_policy(self) -> str:
        alarm_st = self.hass.states.get(self.alarm_entity) if self.alarm_entity else None
        return effective_security_pin_policy(
            self.configured_security_pin_policy,
            is_roaming=self.is_roaming_device,
            alarm_has_code=bool(
                alarm_st is not None and alarm_st.attributes.get("code_format")
            ),
        )

    @property
    def device_security_pin_hash(self) -> str | None:
        return (
            str(self._live_subentry().data.get(CONF_SECURITY_PIN_HASH) or "").strip()
            or None
        )

    @property
    def security_pin_hash(self) -> str | None:
        if self.device_security_pin_hash:
            return self.device_security_pin_hash
        global_cfg = peek_global_config(self.hass)
        return str(global_cfg.get(CONF_SECURITY_PIN_HASH) or "").strip() or None

    @property
    def has_security_pin(self) -> bool:
        return bool(self.security_pin_hash)

    @callback
    def update_hmac_secret(self, new_secret: bytes) -> None:
        self._hmac_secret = new_secret
        self._url_signer = UrlSigner(self.hass, self.subentry_id, new_secret)
        self._last_art_proxy_url = ""

    @property
    def volume_overrides(self) -> dict[str, str]:
        raw_list = self.get_opt(CONF_VOLUME_OVERRIDES)
        if not isinstance(raw_list, list):
            return {}
        return {
            str(it["speaker"]).strip(): str(it["target"]).strip()
            for it in raw_list[:10]
            if isinstance(it, dict)
            and str(it.get("speaker") or "").strip()
            and str(it.get("target") or "").strip()
        }

    def get_volume_target_entity(self, speaker_entity_id: str | None = None) -> str:
        spk = speaker_entity_id or self.active_speaker
        return self.volume_overrides.get(spk, spk)

    @property
    def calendar_entities(self) -> list[str]:
        val = self.get_opt(CONF_CALENDAR_ENTITIES, [])
        return list(val) if isinstance(val, (list, tuple)) else []

    def _scaled_media_dimensions(self) -> tuple[int, int]:
        """Compute bounded panel artwork/wallpaper dimensions."""
        hw = self.hardware_manifest
        try:
            width, height = int(hw.get("w") or 0), int(hw.get("h") or 0)
        except (ValueError, TypeError):
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        if width < _MIN_MEDIA_DIM or height < _MIN_MEDIA_DIM:
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        width = max(_MIN_MEDIA_DIM, min(_MAX_MEDIA_DIM, width))
        height = max(_MIN_MEDIA_DIM, min(_MAX_MEDIA_DIM, height))
        peak = max(width, height)
        if peak <= WALLPAPER_MAX_DIM:
            return width, height
        return (
            max(_MIN_MEDIA_DIM, round(width * float(WALLPAPER_MAX_DIM) / peak)),
            max(_MIN_MEDIA_DIM, round(height * float(WALLPAPER_MAX_DIM) / peak)),
        )

    @property
    def art_dimensions(self) -> tuple[int, int]:
        """Compute bounded square 1:1 album-art dimensions (`art_edge` or `min(w, h)`)."""
        hw = self.hardware_manifest
        try:
            raw_edge = int(hw.get("art_edge") or 0)
        except (ValueError, TypeError):
            raw_edge = 0
        if raw_edge >= _MIN_MEDIA_DIM:
            edge = min(WALLPAPER_MAX_DIM, raw_edge)
            return edge, edge
        width, height = self._scaled_media_dimensions()
        edge = min(width, height)
        return edge, edge

    @property
    def wallpaper_dimensions(self) -> tuple[int, int]:
        return self._scaled_media_dimensions()

    @property
    def remote_groups(self) -> list[dict[str, Any]]:
        raw = self.get_opt(CONF_REMOTE_GROUPS, [])
        if not isinstance(raw, list):
            return []
        return [
            {
                "id": str(it["id"]).strip(),
                "name": str(it["name"]).strip(),
                "area_id": str(it.get("area_id") or "").strip(),
                "remotes": [
                    str(r).strip()
                    for r in (it.get("remotes") or [])[:10]
                    if str(r or "").strip()
                ],
            }
            for it in raw[:20]
            if isinstance(it, dict) and it.get("id") and it.get("name")
        ]

    @property
    def device_remote_group(self) -> str:
        return (
            str(
                self.get_opt(CONF_DEVICE_REMOTE_GROUP, DEFAULT_DEVICE_REMOTE_GROUP)
                or DEFAULT_DEVICE_REMOTE_GROUP
            ).strip()
            or DEFAULT_DEVICE_REMOTE_GROUP
        )

    def get_remote_entities_list(self) -> list[str]:
        raw_list = self.get_opt(CONF_REMOTES_LIST)
        return (
            [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
            if isinstance(raw_list, list)
            else []
        )

    def sign_payload_resource(self, resource: str) -> str:
        return self._url_signer.sign_payload_resource(resource)

    def sign_on_demand_resource(self, resource: str) -> str:
        return self._url_signer.sign_on_demand_resource(resource)

    def verify_resource(self, resource: str, sig: str | None = None) -> bool:
        return self._url_signer.verify_resource(resource, sig)

    def get_lan_base_url(self) -> str:
        return self._url_signer.get_lan_base_url()

    def build_camera_snapshot_url(
        self, camera_entity_id: str | None = None, cache_bust: str = ""
    ) -> str:
        width, height = self.wallpaper_dimensions
        return self._url_signer.build_camera_snapshot_url(
            self.device_slug,
            (camera_entity_id or self.camera_entity or "").strip(),
            width,
            height,
            self.display_shape,
            cache_bust=cache_bust,
        )

    def build_camera_allowlist_snapshot_url(
        self, camera_entity_id: str | None = None, cache_bust: str = ""
    ) -> str:
        width, height = self.wallpaper_dimensions
        return self._url_signer.build_camera_allowlist_snapshot_url(
            self.device_slug,
            self.visible_camera_entities,
            (camera_entity_id or self.camera_entity or "").strip(),
            width,
            height,
            self.display_shape,
            cache_bust=cache_bust,
        )

    def build_camera_stream_url(self) -> str:
        max_w, max_h = self.video_max_dims
        return self._url_signer.build_camera_stream_url(
            self.device_slug,
            self.visible_camera_entities,
            max_w,
            max_h,
            self.video_max_fps,
        )

    def build_camera_audio_url(
        self,
        camera_entity_id: str | None = None,
        nr_level: str | None = None,
        fmt: str = "flac",
    ) -> str:
        return self._url_signer.build_camera_audio_url(
            self.device_slug,
            (camera_entity_id or self.camera_entity or "").strip(),
            nr_level or self.doorbell_noise_reduction,
            fmt,
        )

    def build_proxy_art_url(self, cache_bust: str) -> str:
        width, height = self.art_dimensions
        return self._url_signer.build_proxy_art_url(
            self.device_slug, width, height, self.display_shape, cache_bust
        )

    # -----------------------------------------------------------------------
    # Wallpaper & Photo Frame Screensaver Pools & Rotation Timers
    # -----------------------------------------------------------------------

    @property
    def wallpaper_mode(self) -> str:
        raw = str(self.get_opt(CONF_WALLPAPER_MODE, "") or "").strip().lower()
        if raw in ("off", "single", "collection", "custom"):
            return raw
        if str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip():
            return "single"
        return DEFAULT_WALLPAPER_MODE

    @property
    def wallpaper_collection(self) -> str:
        return str(
            self.get_opt(CONF_WALLPAPER_COLLECTION, DEFAULT_WALLPAPER_COLLECTION) or ""
        ).strip()

    @property
    def configured_wallpaper_source(self) -> str:
        return str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()

    @configured_wallpaper_source.setter
    def configured_wallpaper_source(self, value: str) -> None:
        self._configured_wallpaper_source = str(value or "").strip()

    @callback
    def set_configured_wallpaper_source(self, value: str) -> None:
        """Record the last applied configured wallpaper source ID."""
        self._configured_wallpaper_source = str(value or "").strip()

    @property
    def wallpaper_source(self) -> str:
        if self.wallpaper_mode == "off":
            return ""
        pool = self.resolve_wallpaper_rotation_pool()
        if not pool:
            return ""
        if self.current_wallpaper in pool:
            return self.current_wallpaper
        cfg_src = self.configured_wallpaper_source
        if cfg_src in pool:
            return cfg_src
        return pool[0]

    @property
    def wallpaper_favorites(self) -> list[str]:
        val = self.get_opt(CONF_WALLPAPER_FAVORITES, [])
        return [str(x) for x in val] if isinstance(val, (list, tuple)) else []

    @property
    def wallpaper_cycle_minutes(self) -> int:
        try:
            return max(
                0,
                int(
                    self.get_opt(
                        CONF_WALLPAPER_CYCLE_MINUTES, DEFAULT_WALLPAPER_CYCLE_MINUTES
                    )
                ),
            )
        except (ValueError, TypeError):
            return 0

    @property
    def screensaver_photo_mode(self) -> str:
        raw = str(self.get_opt(CONF_SCREENSAVER_PHOTO_MODE, "") or "").strip().lower()
        if raw in ("off", "single", "collection", "custom"):
            return raw
        return DEFAULT_SCREENSAVER_PHOTO_MODE

    @property
    def screensaver_photo_collection(self) -> str:
        return str(
            self.get_opt(
                CONF_SCREENSAVER_PHOTO_COLLECTION, DEFAULT_SCREENSAVER_PHOTO_COLLECTION
            )
            or DEFAULT_SCREENSAVER_PHOTO_COLLECTION
        ).strip()

    @property
    def configured_screensaver_photo_source(self) -> str:
        return str(self.get_opt(CONF_SCREENSAVER_PHOTO_SOURCE, "") or "").strip()

    @property
    def screensaver_photo_ids(self) -> list[str]:
        val = self.get_opt(CONF_SCREENSAVER_PHOTO_IDS, [])
        return [str(x) for x in val] if isinstance(val, (list, tuple)) else []

    @property
    def screensaver_cycle_minutes(self) -> int:
        try:
            return max(
                0,
                int(
                    self.get_opt(
                        CONF_SCREENSAVER_CYCLE_MINUTES,
                        DEFAULT_SCREENSAVER_CYCLE_MINUTES,
                    )
                ),
            )
        except (ValueError, TypeError):
            return DEFAULT_SCREENSAVER_CYCLE_MINUTES

    @property
    def screensaver_shuffle(self) -> bool:
        return bool(
            self.get_opt(CONF_SCREENSAVER_SHUFFLE, DEFAULT_SCREENSAVER_SHUFFLE)
        )

    @property
    def screensaver_photo_frame_active(self) -> bool:
        return bool(
            self.has_display
            and self.get_device_pref("screensaver_style") == "Photo Frame"
            and self.get_device_pref("screensaver_mode") != "Never"
        )

    @property
    def screensaver_photo_source(self) -> str:
        pool = self.resolve_screensaver_photo_pool()
        if not pool:
            return ""
        if self.current_screensaver_photo in pool:
            return self.current_screensaver_photo
        cfg_src = self.configured_screensaver_photo_source
        if cfg_src in pool:
            return cfg_src
        return pool[0]

    def build_wallpaper_url(self) -> str:
        src = self.wallpaper_source
        if not src:
            return ""
        if src == DAY_NIGHT_SKY_PRESET_ID:
            return DAY_NIGHT_SKY_NATIVE_URL
        width, height = self.wallpaper_dimensions
        return self._url_signer.build_wallpaper_url(
            self.device_slug, src, width, height, self.display_shape, mode="wallpaper"
        )

    def build_screensaver_photo_url(self) -> str:
        if not self.screensaver_photo_frame_active:
            return ""
        src = self.screensaver_photo_source
        if not src:
            return ""
        width, height = self.wallpaper_dimensions
        return self._url_signer.build_wallpaper_url(
            self.device_slug, src, width, height, self.display_shape, mode="screensaver"
        )

    def resolve_wallpaper_rotation_pool(self) -> list[str]:
        """Return valid photo IDs in the Device's active Wallpaper pool."""
        return resolve_photo_pool(
            self.wallpaper_mode,
            self.configured_wallpaper_source,
            self.wallpaper_collection,
            self.wallpaper_favorites,
            include_dynamic=True,
        )

    def resolve_screensaver_photo_pool(self) -> list[str]:
        """Return valid photo IDs in the Device's Photo Frame Screensaver pool (dynamic presets excluded)."""
        return resolve_photo_pool(
            self.screensaver_photo_mode,
            self.configured_screensaver_photo_source,
            self.screensaver_photo_collection,
            self.screensaver_photo_ids,
            include_dynamic=False,
        )

    @callback
    def ensure_active_wallpaper_for_rotation(self) -> bool:
        """Seed an active wallpaper from the configured wallpaper pool."""
        if self.is_ble_tag:
            return False
        pool = self.resolve_wallpaper_rotation_pool()
        if not pool:
            if self.current_wallpaper:
                self.current_wallpaper = ""
                self.schedule_persist_runtime_state()
            return False
        if self.current_wallpaper in pool:
            return False
        cfg_src = self.configured_wallpaper_source
        self.current_wallpaper = cfg_src if cfg_src in pool else pool[0]
        self.schedule_persist_runtime_state()
        return True

    @callback
    def ensure_active_screensaver_photo(self) -> bool:
        """Seed or prune the active Photo Frame screensaver photo from the configured pool."""
        if self.is_ble_tag:
            return False
        pool = self.resolve_screensaver_photo_pool()
        if not pool or not self.screensaver_photo_frame_active:
            if self.current_screensaver_photo and self.current_screensaver_photo not in pool:
                self.current_screensaver_photo = ""
                self.schedule_persist_runtime_state()
            return False
        if self.current_screensaver_photo in pool:
            return False
        cfg_src = self.configured_screensaver_photo_source
        if cfg_src in pool:
            picked = cfg_src
        elif self.screensaver_shuffle and len(pool) >= _MIN_ROTATION_POOL_LEN:
            picked = secrets.choice(pool)
        else:
            picked = pool[0]
        self.current_screensaver_photo = picked
        self.schedule_persist_runtime_state()
        return True

    @callback
    def bind_wallpaper_cycle_timer(self) -> None:
        """Bind or refresh the periodic Wallpaper rotation interval timer."""
        if self._unsub_wallpaper_timer is not None:
            self._unsub_wallpaper_timer()
            self._unsub_wallpaper_timer = None

        self.ensure_active_wallpaper_for_rotation()
        mins = self.wallpaper_cycle_minutes
        if mins <= 0:
            return

        pool = self.resolve_wallpaper_rotation_pool()
        if self.wallpaper_source and len(pool) >= _MIN_ROTATION_POOL_LEN:

            @callback
            def _on_wallpaper_tick(_now: datetime) -> None:
                tick_pool = self.resolve_wallpaper_rotation_pool()
                if len(tick_pool) < _MIN_ROTATION_POOL_LEN:
                    return
                cur = self.wallpaper_source
                try:
                    idx = (tick_pool.index(cur) + 1) % len(tick_pool)
                except ValueError:
                    idx = 0
                self.current_wallpaper = tick_pool[idx]
                self.schedule_persist_runtime_state()
                self.async_notify_listeners()

            self._unsub_wallpaper_timer = async_track_time_interval(
                self.hass, _on_wallpaper_tick, timedelta(minutes=mins)
            )

    @callback
    def bind_screensaver_cycle_timer(self) -> None:
        """Bind or refresh the periodic Photo Frame Screensaver rotation interval timer."""
        if self._unsub_screensaver_timer is not None:
            self._unsub_screensaver_timer()
            self._unsub_screensaver_timer = None

        if not self.screensaver_photo_frame_active:
            if self.current_screensaver_photo and (
                self.current_screensaver_photo not in self.resolve_screensaver_photo_pool()
            ):
                self.current_screensaver_photo = ""
                self.schedule_persist_runtime_state()
            return

        self.ensure_active_screensaver_photo()
        mins = self.screensaver_cycle_minutes
        if mins <= 0:
            return

        pool = self.resolve_screensaver_photo_pool()
        if self.screensaver_photo_source and len(pool) >= _MIN_ROTATION_POOL_LEN:

            @callback
            def _on_screensaver_tick(_now: datetime) -> None:
                if not self.screensaver_photo_frame_active:
                    return
                tick_pool = self.resolve_screensaver_photo_pool()
                if len(tick_pool) < _MIN_ROTATION_POOL_LEN:
                    return
                cur = self.screensaver_photo_source
                if self.screensaver_shuffle:
                    candidates = [p for p in tick_pool if p != cur]
                    self.current_screensaver_photo = secrets.choice(
                        candidates or tick_pool
                    )
                else:
                    try:
                        idx = (tick_pool.index(cur) + 1) % len(tick_pool)
                    except ValueError:
                        idx = 0
                    self.current_screensaver_photo = tick_pool[idx]
                self.schedule_persist_runtime_state()
                self.async_notify_listeners()

            self._unsub_screensaver_timer = async_track_time_interval(
                self.hass, _on_screensaver_tick, timedelta(minutes=mins)
            )

    # -----------------------------------------------------------------------
    # BLE Spatial Options, Active Area State & Voice Follows Me Handoff
    # -----------------------------------------------------------------------

    @property
    def ble_target_address(self) -> str:
        return str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()

    @property
    def configured_ble_category(self) -> str:
        raw = (
            str(
                self.get_opt(CONF_BLE_CATEGORY, DEFAULT_BLE_CATEGORY)
                or DEFAULT_BLE_CATEGORY
            )
            .strip()
            .lower()
        )
        return raw if raw in ("auto", "phone", "ble_tag") else DEFAULT_BLE_CATEGORY

    @property
    def effective_ble_category(self) -> str:
        if not self.is_ble_tag:
            return ""
        return classify_ble_target_category(
            self.hass, self.ble_target_address, self.configured_ble_category
        )

    @property
    def ble_scanner_offsets(self) -> dict[str, float]:
        raw = self.get_opt(CONF_BLE_SCANNER_OFFSETS, {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for key, val_raw in raw.items():
            src_k = str(key or "").strip().upper()
            if not src_k:
                continue
            try:
                val = round(
                    max(-_BLE_OFFSET_MAX_DB, min(_BLE_OFFSET_MAX_DB, float(val_raw))),
                    1,
                )
                if val != 0.0:
                    out[src_k] = val
            except (ValueError, TypeError):
                pass
        return out

    @property
    def ble_area_signatures(self) -> dict[str, dict[str, Any]]:
        raw = self.get_opt(CONF_BLE_AREA_SIGNATURES, {})
        if not isinstance(raw, dict):
            return {}
        return {
            str(area_id): sig
            for area_id, sig in raw.items()
            if area_id
            and isinstance(sig, dict)
            and isinstance(sig.get("scanners"), dict)
            and sig["scanners"]
        }

    @property
    def ble_ref_power(self) -> int | None:
        raw = self._live_subentry().data.get(CONF_BLE_REF_POWER)
        if raw is None or raw == "":
            return None
        try:
            return max(_BLE_REF_MIN_DBM, min(_BLE_REF_MAX_DBM, round(float(raw))))
        except (ValueError, TypeError):
            return None

    @property
    def ble_attenuation(self) -> float:
        try:
            return round(
                max(
                    _BLE_ATTEN_MIN,
                    min(
                        _BLE_ATTEN_MAX,
                        float(
                            self.get_opt(CONF_BLE_ATTENUATION, DEFAULT_BLE_ATTENUATION)
                        ),
                    ),
                ),
                2,
            )
        except (ValueError, TypeError):
            return DEFAULT_BLE_ATTENUATION

    @property
    def ble_max_radius_m(self) -> float:
        try:
            return round(
                max(
                    _BLE_RADIUS_MIN_M,
                    min(
                        _BLE_RADIUS_MAX_M,
                        float(
                            self.get_opt(
                                CONF_BLE_MAX_RADIUS_M, DEFAULT_BLE_MAX_RADIUS_M
                            )
                        ),
                    ),
                ),
                1,
            )
        except (ValueError, TypeError):
            return DEFAULT_BLE_MAX_RADIUS_M

    @property
    def ble_max_velocity_mps(self) -> float:
        try:
            return round(
                max(
                    _BLE_VEL_MIN_MPS,
                    min(
                        _BLE_VEL_MAX_MPS,
                        float(
                            self.get_opt(
                                CONF_BLE_MAX_VELOCITY_MPS, DEFAULT_BLE_MAX_VELOCITY_MPS
                            )
                        ),
                    ),
                ),
                1,
            )
        except (ValueError, TypeError):
            return DEFAULT_BLE_MAX_VELOCITY_MPS

    @property
    def ble_away_timeout_s(self) -> int:
        try:
            return max(
                _BLE_AWAY_MIN_S,
                min(
                    _BLE_AWAY_MAX_S,
                    int(
                        self.get_opt(
                            CONF_BLE_AWAY_TIMEOUT_S, DEFAULT_BLE_AWAY_TIMEOUT_S
                        )
                    ),
                ),
            )
        except (ValueError, TypeError):
            return DEFAULT_BLE_AWAY_TIMEOUT_S

    @property
    def assigned_person(self) -> str:
        return str(self.get_opt(CONF_ASSIGNED_PERSON, "") or "").strip()

    @property
    def ble_auto_switch_enabled(self) -> bool:
        return bool(self.get_opt(CONF_BLE_AUTO_SWITCH, DEFAULT_BLE_AUTO_SWITCH))

    @property
    def sync_device_area_enabled(self) -> bool:
        return self.is_roaming_device and bool(
            self.get_opt(CONF_SYNC_DEVICE_AREA, DEFAULT_SYNC_DEVICE_AREA)
        )

    @property
    def area_follow_dwell_s(self) -> int:
        try:
            return max(
                _DWELL_MIN_S,
                min(
                    _DWELL_MAX_S,
                    int(
                        self.get_opt(
                            CONF_AREA_FOLLOW_DWELL_S, DEFAULT_AREA_FOLLOW_DWELL_S
                        )
                    ),
                ),
            )
        except (ValueError, TypeError):
            return DEFAULT_AREA_FOLLOW_DWELL_S

    @property
    def area_handoff_enabled(self) -> bool:
        return bool(self.get_opt(CONF_AREA_HANDOFF, DEFAULT_AREA_HANDOFF))

    @property
    def last_area_follow_write(self) -> dict[str, Any] | None:
        return self._area_follow.last_area_follow_write

    @property
    def active_area_name(self) -> str:
        area_entry = resolve_active_area_entry(self)
        return area_entry.name if area_entry else "Unassigned"

    def _resolve_effective_area_state(
        self, *, away: bool
    ) -> tuple[str, str, ar.AreaEntry | None]:
        explicit_default = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        esp_default = ""
        if not self.is_ble_tag and self.esphome_device_id:
            esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
            esp_default = str(esp_dev.area_id or "").strip() if esp_dev else ""
        if away:
            return "", "Away", None
        ble_candidate = (
            self._ble_tracker.current_area_id
            if (self.native_ble_tracking_enabled and self._ble_tracker is not None)
            else None
        )
        eff_area_id = (
            ble_candidate or self.active_area_id or explicit_default or esp_default
        )
        area_reg = ar.async_get(self.hass)
        area_entry = area_reg.async_get_area(eff_area_id) if eff_area_id else None
        area_state = area_entry.name if area_entry is not None else "Unassigned"
        return eff_area_id or "", area_state, area_entry

    def get_current_area_and_distance(self) -> tuple[str, dict[str, Any]]:
        """Return `(area_state_name, metric_presence_attributes)` for entities & Studio."""
        away = self.is_device_away()
        eff_area_id, area_state, area_entry = self._resolve_effective_area_state(
            away=away
        )
        floor_raw = (
            getattr(area_entry, "floor_id", None)
            if (area_entry is not None and not away)
            else None
        )
        floor_id, resolved_floor_name = resolve_floor_info(self.hass, floor_raw)
        if away:
            floor_id = ""
            floor_name = "Away"
        elif floor_id:
            floor_name = resolved_floor_name
        else:
            floor_name = "Unassigned"

        bt = self._ble_tracker
        valid_bt = bt is not None and not away and bool(eff_area_id)
        eff_ref_dbm: int | float = (
            round(bt.effective_ref_power_dbm, 1)
            if bt is not None
            else (
                self.ble_ref_power
                if self.ble_ref_power is not None
                else int(TX_POWER_1M_DBM)
            )
        )
        if isinstance(eff_ref_dbm, float) and eff_ref_dbm.is_integer():
            eff_ref_dbm = int(eff_ref_dbm)

        if away or not eff_area_id:
            match_method = ""
        elif bt is not None and self.native_ble_tracking_enabled and bt.current_area_id:
            match_method = bt.match_method or "distance"
        else:
            match_method = "static"

        return area_state, {
            "area_id": eff_area_id,
            "area_name": area_state,
            "floor_id": floor_id,
            "floor_name": floor_name,
            "is_home": not away,
            "closest_proxy": bt.closest_scanner if (valid_bt and bt) else "",
            "distance_m": bt.winning_distance_m if (valid_bt and bt) else None,
            "rssi": bt.winning_rssi if (valid_bt and bt) else None,
            "raw_rssi": bt.winning_raw_rssi if (valid_bt and bt) else None,
            "ref_power_dbm": eff_ref_dbm,
            "match_method": match_method,
            "assigned_person": self.assigned_person,
        }

    @callback
    def _async_on_native_ble_area_detected(
        self, area_id: str, scanner_source: str
    ) -> None:
        if area_id == "away":
            self._area_follow.cancel()
            self.async_notify_listeners()
            return
        if not self.ble_auto_switch_enabled:
            self.async_notify_listeners()
            return
        if area_id and area_id != self.active_area_id:
            _LOGGER.debug(
                "Native BLE Proxy ('%s') detected '%s' in area '%s' (was '%s')",
                scanner_source,
                self.device_slug,
                area_id,
                self.active_area_id,
            )
            self.async_set_active_area(
                area_id,
                sync_device_registry=True,
                ble_driven=True,
            )
        else:
            self.async_notify_listeners()

    @callback
    def _clear_active_area(self) -> None:
        self._area_follow.cancel()
        prev_area = self.active_area_id
        self.active_area_id = None
        if prev_area is not None:
            self.hass.bus.async_fire(
                EVENT_LATTER,
                {
                    "type": "area_changed",
                    "device_slug": self.device_slug,
                    "previous_area_id": prev_area,
                    "area_id": "",
                    "assigned_person": self.assigned_person,
                },
            )
            if not self.is_ble_tag:
                bind_coordinator_area_listeners(self)
            self.schedule_persist_runtime_state()
            self.async_notify_listeners()
            if not self.is_ble_tag and self.on_area_changed_push_slots is not None:
                self.create_background_task(
                    self.on_area_changed_push_slots(self),
                    f"latter_area_change_slots_{self.device_slug}",
                )
        else:
            self.async_notify_listeners()

    @callback
    def async_set_active_area(
        self,
        area_id_or_name: str,
        handoff_media: bool | None = None,
        sync_device_registry: bool = False,
        ble_driven: bool = False,
    ) -> None:
        matched_id = match_area_by_name_or_id(self.hass, area_id_or_name)
        if not matched_id:
            return
        prev_area = self.active_area_id
        self.active_area_id = matched_id
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

        if self.is_ble_tag:
            self.schedule_persist_runtime_state()
            self.async_notify_listeners()
            return

        if sync_device_registry:
            self._area_follow.schedule_or_commit(
                esphome_device_id=self.esphome_device_id,
                target_area_id=matched_id,
                ble_driven=ble_driven,
                dwell_s=self.area_follow_dwell_s,
                is_allowed_cb=lambda: (
                    self.active_area_id == matched_id
                    and not self.is_device_away()
                    and self.sync_device_area_enabled
                    and bool(self.esphome_device_id)
                ),
            )
        else:
            self._area_follow.cancel()

        media_map = find_area_media_entities(
            self.hass, matched_id, self.local_speaker
        )
        self.active_remote_slot = 1
        for slot_idx, slot_info in enumerate(self.get_remote_slots(), start=1):
            if slot_info["area_id"] == matched_id:
                self.active_remote_slot = slot_idx
                break
        bind_coordinator_area_listeners(self)
        self.schedule_persist_runtime_state()

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
            self.async_notify_listeners()

        if self.on_area_changed_push_slots is not None:
            self.create_background_task(
                self.on_area_changed_push_slots(self),
                f"latter_area_change_slots_{self.device_slug}",
            )

    # -----------------------------------------------------------------------
    # Home Assistant Device Registry & Entity Registry Synchronization
    # -----------------------------------------------------------------------

    def _find_latter_device_entry(self) -> dr.DeviceEntry | None:
        dev_reg = dr.async_get(self.hass)
        idents = self.device_identifiers
        esp_id = self.esphome_device_id
        for dev in dr.async_entries_for_config_entry(dev_reg, self.entry.entry_id):
            if (DOMAIN, "system") in dev.identifiers:
                continue
            if (dev.identifiers & idents) or (esp_id and dev.via_device_id == esp_id):
                return dev
        return None

    @callback
    def async_record_own_area_write(self, device_id: str, area_id: str) -> None:
        """Record an internal Device Registry Area write so external change tracking stays aligned."""
        if device_id == self.esphome_device_id:
            self._last_esp_area = area_id
        else:
            latter_dev = self._find_latter_device_entry()
            if latter_dev is not None and latter_dev.id == device_id:
                self._last_latter_area = area_id

    @callback
    def async_sync_ha_device_name(self) -> bool:
        """Mirror the bound ESPHome Device's live name onto the Latter subentry and child Latter Device."""
        if self.is_ble_tag or not self.esphome_device_id:
            return False
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        if esp_dev is None:
            return False
        live_name = str(esp_dev.name_by_user or esp_dev.name or "").strip()
        if not live_name:
            return False
        self.async_heal_renamed_local_speaker()
        changed = False
        live_sub = self._live_subentry()
        if live_sub.title != live_name:
            self.hass.config_entries.async_update_subentry(
                self.entry, live_sub, title=live_name
            )
            self._live_subentry()
            changed = True
        latter_dev = self._find_latter_device_entry()
        if latter_dev is not None and latter_dev.name != live_name:
            dr.async_get(self.hass).async_update_device(latter_dev.id, name=live_name)
            changed = True
        if changed:
            self._cached_media_payload = None
            for coord in iter_coordinators(self.hass):
                coord.cached_area_payload = None
                coord.async_notify_listeners()
        return changed

    @callback
    def async_heal_renamed_local_speaker(self) -> bool:
        """Heal stale built-in speaker refs when the bound ESPHome node was renamed before/offline."""
        if self.is_ble_tag:
            return False
        local_spk = self.local_speaker
        if not local_spk:
            return False
        prior_slugs = {
            slug
            for slug in (
                self.device_slug,
                normalize_device_slug(str(self._live_subentry().title or "")),
            )
            if slug
        }
        old_local_candidates = {
            f"media_player.{slug}{sfx}"
            for slug in prior_slugs
            for sfx in ("", "_music", "_media_player")
        }
        old_local_candidates.discard(local_spk)
        if not old_local_candidates:
            return False

        ent_reg = er.async_get(self.hass)

        def _is_stale_local(entity_id: str) -> bool:
            return (
                bool(entity_id)
                and entity_id in old_local_candidates
                and self.hass.states.get(entity_id) is None
                and ent_reg.async_get(entity_id) is None
            )

        healed = False
        raw_def_spk = str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip()
        if _is_stale_local(raw_def_spk):
            _LOGGER.info(
                "Healed renamed built-in default_speaker for '%s': %s -> %s",
                self.device_slug,
                raw_def_spk,
                local_spk,
            )
            self.update_device_config(
                {**self.device_data, CONF_DEFAULT_SPEAKER: local_spk},
                bump_prefs_seq=False,
            )
            self._configured_default_speaker = (
                self._resolved_configured_default_speaker()
            )
            healed = True

        runtime_changed = False
        if _is_stale_local(self.active_speaker):
            self.active_speaker = local_spk
            runtime_changed = True
        if _is_stale_local(self.last_speaker):
            self.last_speaker = local_spk
            runtime_changed = True
        if runtime_changed:
            self._cached_media_payload = None
            self.schedule_persist_runtime_state()
            healed = True
        return healed

    @callback
    def async_on_ha_entity_renamed(
        self,
        old_entity_id: str,
        new_entity_id: str,
        entity_device_id: str | None = None,
    ) -> bool:
        """Migrate Device speaker/MA references and rebind listeners when an HA entity is renamed."""
        if (
            self.is_ble_tag
            or not old_entity_id
            or not new_entity_id
            or old_entity_id == new_entity_id
        ):
            return False
        changed = self._migrate_renamed_speaker_refs(old_entity_id, new_entity_id)
        is_own_device = bool(
            entity_device_id
            and self.esphome_device_id
            and entity_device_id == self.esphome_device_id
        )
        if changed or is_own_device:
            self.invalidate_bound_entity_cache()
            self._cached_media_payload = None
            bind_coordinator_speaker_listener(self)
            try:
                async_audit_coordinator_health(self.hass, self)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Repairs audit after rename skipped: %s", err)
            self.async_notify_listeners()
        return changed or is_own_device

    def _migrate_renamed_speaker_refs(
        self, old_entity_id: str, new_entity_id: str
    ) -> bool:
        changed = False
        cfg_updates: dict[str, Any] = {}
        if str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() == old_entity_id:
            cfg_updates[CONF_DEFAULT_SPEAKER] = new_entity_id
        if str(self.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip() == old_entity_id:
            cfg_updates[CONF_MA_PLAYER_ENTITY] = new_entity_id
        if cfg_updates:
            self.update_device_config(
                {**self.device_data, **cfg_updates},
                bump_prefs_seq=False,
            )
            if CONF_DEFAULT_SPEAKER in cfg_updates:
                self._configured_default_speaker = (
                    self._resolved_configured_default_speaker()
                )
            changed = True

        runtime_changed = False
        if self.active_speaker == old_entity_id:
            self.active_speaker = new_entity_id
            runtime_changed = True
        if self.last_speaker == old_entity_id:
            self.last_speaker = new_entity_id
            runtime_changed = True
        if runtime_changed:
            self.schedule_persist_runtime_state()
            changed = True
        return changed

    @callback
    def async_sync_ha_device_areas(self) -> None:
        """Mirror the authoritative Area across the bound ESPHome Device and child Latter Device."""
        if self.is_ble_tag:
            return
        esp_id = self.esphome_device_id
        esp_dev = get_bound_esphome_device(self.hass, esp_id)
        esp_area = str(esp_dev.area_id or "").strip() if esp_dev else ""
        latter_dev = self._find_latter_device_entry()
        latter_area = str(latter_dev.area_id or "").strip() if latter_dev else ""
        if esp_id:
            if not self.native_ble_tracking_enabled:
                target = (
                    str(self.get_opt(CONF_DEFAULT_AREA) or "").strip() or esp_area
                )
                if target:
                    sync_esphome_device_area(
                        self.hass, esp_id, target, require_ble_proxy_area=False
                    )
                    esp_area = latter_area = target
            elif esp_area and latter_dev is not None and latter_area != esp_area:
                sync_esphome_device_area(
                    self.hass, esp_id, esp_area, require_ble_proxy_area=False
                )
                latter_area = esp_area
        self._last_esp_area = esp_area
        self._last_latter_area = latter_area

    @callback
    def async_on_ha_device_area_updated(
        self, updated_device_id: str, new_area_id: str
    ) -> None:
        """React live when an administrator reassigns the ESPHome or Latter Device Area in Home Assistant."""
        if self.is_ble_tag:
            return
        clean_area = str(new_area_id or "").strip()
        expected_prev = (
            self._last_esp_area
            if updated_device_id == self.esphome_device_id
            else self._last_latter_area
        )
        if clean_area == expected_prev:
            return
        self._last_esp_area = clean_area
        self._last_latter_area = clean_area
        if self.esphome_device_id:
            sync_esphome_device_area(
                self.hass,
                self.esphome_device_id,
                clean_area,
                require_ble_proxy_area=False,
                allow_clear=True,
            )
        if not self.native_ble_tracking_enabled:
            cur_conf = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
            if clean_area != cur_conf:
                self.update_device_config(
                    {**self.device_data, CONF_DEFAULT_AREA: clean_area},
                    bump_prefs_seq=False,
                )
            self._configured_default_area = clean_area
            if clean_area:
                self.async_set_active_area(clean_area, sync_device_registry=False)
            else:
                self._clear_active_area()
            return
        has_ble_lock = bool(
            self._ble_tracker and self._ble_tracker.current_area_id
        )
        explicit_default = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        if not has_ble_lock and not explicit_default:
            if clean_area:
                self.async_set_active_area(clean_area, sync_device_registry=False)
            else:
                self._clear_active_area()
        else:
            self.async_notify_listeners()

    # -----------------------------------------------------------------------
    # Connection Predicates, `device_hello`, Prefs Convergence & Commands
    # -----------------------------------------------------------------------

    def _resolve_rpc_outbox_entity_id(self) -> str | None:
        if self._rpc_receiver is not None:
            tracked = getattr(
                self._rpc_receiver,
                "tracked_entity_id",
                getattr(self._rpc_receiver, "_tracked_entity_id", None),
            )
            if tracked:
                return str(tracked)
        if not self.esphome_device_id:
            return None
        return self.device_entity(
            "sensor",
            *_RPC_OUTBOX_SUFFIXES,
            original_names=_RPC_OUTBOX_NAMES,
            unique_id_suffixes=_RPC_OUTBOX_UID_SUFFIXES,
        )

    def is_rpc_outbox_unavailable(self) -> bool:
        """Return True when the bound RPC outbox entity exists in HA and reports `unavailable`."""
        if self._rpc_receiver is not None and hasattr(
            self._rpc_receiver, "is_device_unavailable"
        ):
            return bool(self._rpc_receiver.is_device_unavailable())
        ent_id = self._resolve_rpc_outbox_entity_id()
        if not ent_id:
            return False
        st = self.hass.states.get(ent_id)
        return st is not None and st.state == STATE_UNAVAILABLE

    @property
    def is_online(self) -> bool:
        """Single canonical online predicate across ESPHome Devices and BLE Tags."""
        if self.is_ble_tag:
            return not self.is_device_away()
        return self.is_device_online()

    @property
    def radio_connected(self) -> bool:
        """Return True when the bound ESPHome Device has an active online API connection and is not hibernating."""
        return (
            not self.is_ble_tag
            and not self._entered_hibernate
            and self.is_device_online()
        )

    def is_device_online(self) -> bool:
        """Return True when the bound ESPHome Device has an active connection in Home Assistant."""
        if self.is_ble_tag or self.is_rpc_outbox_unavailable():
            return False
        saw_conn_sensor = False
        for sfx in ("_system_wi_fi_signal", "_wi_fi_signal", "_ip_address"):
            ent_id = self.device_entity("sensor", sfx)
            if not ent_id:
                continue
            saw_conn_sensor = True
            st = self.hass.states.get(ent_id)
            if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
                return True
        if saw_conn_sensor or self._entered_hibernate:
            return False
        if (
            self.device_telemetry.get("updated_at") is not None
            or bool(self._runtime.last_boot_id)
        ):
            outbox_id = self._resolve_rpc_outbox_entity_id()
            if outbox_id:
                st = self.hass.states.get(outbox_id)
                return st is not None and st.state != STATE_UNAVAILABLE
        return False

    def is_ble_sleep_expected(self) -> bool:
        """Pure query: return True when BLE silence is intentional (light sleep/docked pause or hibernate)."""
        if self.is_ble_tag:
            return False
        if self.is_device_online():
            telem_ble = self.device_telemetry.get("ble_active")
            return isinstance(telem_ble, bool) and not telem_ble
        return bool(
            self._entered_hibernate
            and int(self.hardware_manifest.get("battery", 0) or 0) == 1
        )

    def is_device_away(self) -> bool:
        """Return True when native BLE tracking confirms the Device or BLE Tag is away."""
        if not self.native_ble_tracking_enabled or self._ble_tracker is None:
            return False
        if not self._ble_tracker.is_away:
            return False
        if self.is_ble_tag:
            return True
        if not self.is_device_online():
            return not self.is_ble_sleep_expected()
        return self.device_telemetry.get("ble_active") is True

    async def async_sync_presence_beacon(self, trigger: str = "options") -> None:
        _ = trigger
        if self.is_ble_tag:
            return
        self._cached_prefs_payload = None

    @callback
    def _apply_device_health(
        self, manifest: dict[str, Any], boot_id: str
    ) -> None:
        if (
            boot_id
            and self.last_device_health is not None
            and self.last_device_health.get("boot_id") == boot_id
        ):
            return
        health = parse_device_health(manifest)
        reported_at = dt_util.now().isoformat(timespec="seconds")
        self.last_device_health = {
            "boot_id": boot_id,
            "core_rev": health.core_rev,
            "reset": health.reset,
            "crash": health.crash,
            "rollback": health.rollback,
            "reported_at": reported_at,
        }
        self.schedule_persist_runtime_state()
        actions = evaluate_device_health(health)
        for kind in actions.delete_issues:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                device_health_issue_id(kind, self.subentry_id),
            )
        for kind, extra in actions.raise_issues.items():
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                device_health_issue_id(kind, self.subentry_id),
                is_fixable=True,
                severity=(
                    ir.IssueSeverity.ERROR
                    if kind == ISSUE_ROLLED_BACK
                    else ir.IssueSeverity.WARNING
                ),
                translation_key=kind,
                translation_placeholders={
                    "device": self.device_title,
                    "time": reported_at,
                    **extra,
                },
            )

    async def _async_finish_reconnect_post_delay(self) -> None:
        enforce_local_speaker_if_remote_idle(self, "device_reconnect_post_delay")
        if (
            self._ble_tracker is not None
            and self._ble_tracker.current_area_id
            and self._ble_tracker.current_area_id != self.active_area_id
        ):
            self.async_set_active_area(
                self._ble_tracker.current_area_id,
                handoff_media=False,
                sync_device_registry=True,
                ble_driven=True,
            )
        self.async_notify_listeners()
        if self.on_area_changed_push_slots is not None:
            await self.on_area_changed_push_slots(self)

    async def _async_handle_reconnect(self) -> None:
        if self._unsub_reconnect_post_delay is not None:
            self._unsub_reconnect_post_delay()
            self._unsub_reconnect_post_delay = None
        enforce_local_speaker_if_remote_idle(self, "device_reconnect")
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
                    ble_driven=True,
                )
        self.async_notify_listeners()

        @callback
        def _on_post_delay(_now: datetime) -> None:
            self._unsub_reconnect_post_delay = None
            self.create_background_task(
                self._async_finish_reconnect_post_delay(),
                f"latter_reconnect_post_delay_{self.device_slug}",
            )

        self._unsub_reconnect_post_delay = async_call_later(
            self.hass, 1.5, _on_post_delay
        )

    async def async_provision_pin_session_key(self) -> bool:
        """Mint a fresh per-boot/reconnect HMAC PIN session key in RAM and push to firmware."""
        if self.is_ble_tag:
            return False
        key_id, key_bytes = mint_pin_session_key()
        self._pin_key_id = key_id
        self._pin_key_bytes = key_bytes
        self._pin_last_nonce = 0
        return await self.async_send_device_command(
            f"set_pin_key:{key_id}:{key_bytes.hex()}"
        )

    def _resolve_next_display_power(
        self, power_state: Any, screensaver_active: Any
    ) -> int:
        next_power = self.display_power_state
        if power_state is not None and not isinstance(power_state, bool):
            try:
                parsed_p = int(float(power_state))
                if parsed_p in (0, 1, 2):
                    next_power = parsed_p
            except (TypeError, ValueError):
                pass
        elif screensaver_active is not None:
            next_power = 1 if _parse_bool_flag(screensaver_active) else 0
        if (
            screensaver_active is not None
            and next_power == 0
            and _parse_bool_flag(screensaver_active)
        ):
            next_power = 1
        return next_power

    @callback
    def apply_display_state(
        self,
        power_state: Any,
        brightness_pct: Any,
        screensaver_active: Any = None,
    ) -> None:
        """Apply live `display_state` RPC telemetry (`0`=awake, `1`=screensaver, `2`=off)."""
        next_power = self._resolve_next_display_power(power_state, screensaver_active)
        next_bri = self.display_brightness_pct
        if brightness_pct is not None and not isinstance(brightness_pct, bool):
            try:
                parsed_b = round(float(brightness_pct))
                if parsed_b > 0:
                    next_bri = max(1, min(100, parsed_b))
            except (TypeError, ValueError):
                pass

        self.display_power_state = next_power
        self.display_brightness_pct = next_bri
        self.async_update_listeners()

    @callback
    def apply_device_telemetry(self, payload: Mapping[str, Any]) -> None:
        """Apply live `device_telemetry` RPC diagnostics and update hibernate/BLE state."""
        raw_link = payload.get("link_json", payload.get("link"))
        link_dict: dict[str, Any] = {}
        if isinstance(raw_link, Mapping):
            link_dict = dict(raw_link)
        elif isinstance(raw_link, str) and raw_link.strip().startswith("{"):
            try:
                parsed_link = json.loads(raw_link)
                if isinstance(parsed_link, dict):
                    link_dict = parsed_link
            except (TypeError, ValueError):
                link_dict = {}

        link_state = str(
            link_dict.get("state")
            or link_dict.get("status")
            or payload.get("link_state")
            or ""
        ).strip().lower()
        if link_state == "hibernating":
            if not self._entered_hibernate:
                self._entered_hibernate = True
                self.schedule_persist_runtime_state()
        elif link_dict and self._entered_hibernate:
            self._entered_hibernate = False
            self.schedule_persist_runtime_state()

        prev_ble = self.device_telemetry.get("ble_active")
        ble_active = _parse_opt_bool(payload.get("ble_active"))
        if prev_ble is not True and ble_active is True and self._ble_tracker is not None:
            self._ble_tracker.note_ble_radio_active(time.monotonic())

        self.device_telemetry = {
            "link": link_dict,
            "int_ram_free_kb": _parse_kb(payload.get("int_ram_free_kb")),
            "int_ram_min_kb": _parse_kb(payload.get("int_ram_min_kb")),
            "int_ram_largest_kb": _parse_kb(payload.get("int_ram_largest_kb")),
            "psram_min_kb": _parse_kb(payload.get("psram_min_kb")),
            "ble_active": ble_active,
            "profiler_on": bool(_parse_opt_bool(payload.get("profiler_on"))),
            "updated_at": dt_util.now().isoformat(timespec="seconds"),
        }
        self.async_update_listeners()

    def _merge_hello_device_prefs(
        self, dev_seq: int, incoming_prefs: dict[str, Any]
    ) -> bool:
        ble_tracking_changed = False
        if self.prefs_seq == 0:
            raw_sub = self._live_subentry().data
            seeded = {k: v for k, v in incoming_prefs.items() if k not in raw_sub}
            if seeded:
                cleaned = clean_device_settings(
                    seeded,
                    current=self.device_data,
                    is_round_display=self.is_round_display,
                    supports_hw_jpeg=self.supports_hw_jpeg,
                )
                if cleaned:
                    self.update_device_config(
                        {**self.device_data, **cleaned}, bump_prefs_seq=False
                    )
                    ble_tracking_changed = CONF_NATIVE_BLE_TRACKING in cleaned
                    if not ble_tracking_changed:
                        self._applied_options_snapshot = self._capture_options_snapshot()
            self.prefs_seq = max(
                1, dev_seq + (1 if incoming_prefs and dev_seq > 0 else 0)
            )
            cur_sub = self._live_subentry().data
            for key in (
                *DEVICE_PREF_KEYS,
                CONF_NATIVE_BLE_TRACKING,
                CONF_DEVICE_CUSTOM_COLOR,
                CONF_TOOLS_ITEMS,
                CONF_GAMES_ITEMS,
            ):
                if key in cur_sub:
                    self.prefs_key_seq.setdefault(key, self.prefs_seq)
            return ble_tracking_changed

        if dev_seq <= 0:
            return False
        if not incoming_prefs:
            self.prefs_seq = max(self.prefs_seq, dev_seq)
            return False

        accepted = {
            k: v
            for k, v in incoming_prefs.items()
            if self.prefs_key_seq.get(k, 0) <= dev_seq
        }
        new_seq = max(self.prefs_seq, dev_seq) + 1
        if accepted:
            cleaned = clean_device_settings(
                accepted,
                current=self.device_data,
                is_round_display=self.is_round_display,
                supports_hw_jpeg=self.supports_hw_jpeg,
            )
            if cleaned:
                self.update_device_config(
                    {**self.device_data, **cleaned}, bump_prefs_seq=False
                )
                for key in cleaned:
                    self.prefs_key_seq[key] = new_seq
                ble_tracking_changed = CONF_NATIVE_BLE_TRACKING in cleaned
                if not ble_tracking_changed:
                    self._applied_options_snapshot = self._capture_options_snapshot()
        self.prefs_seq = new_seq
        return ble_tracking_changed

    @callback
    def _sync_outdated_firmware_issue(self) -> None:
        """Create or auto-clear the non-blocking outdated firmware HA Repair for this Device."""
        if self.is_ble_tag:
            return
        issue_id = outdated_firmware_issue_id(self.subentry_id)
        rev = parse_firmware_core_rev(self.hardware_manifest)
        if rev is not None and 0 < rev < MIN_FIRMWARE_CORE_REV:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_OUTDATED_FIRMWARE,
                translation_placeholders={
                    "device": self.device_title,
                    "core_rev": str(rev),
                    "min_core_rev": str(MIN_FIRMWARE_CORE_REV),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _capability_fingerprint(self) -> tuple[bool, bool, bool, bool, bool]:
        return (
            self.has_display,
            self.has_mic,
            self.has_speaker,
            self.has_imu,
            self.has_battery,
        )

    def _supports_entity_capability(self, cap: str) -> bool:
        if cap == "display":
            return self.has_display
        if cap == "mic":
            return self.has_mic
        if cap == "speaker":
            return self.has_speaker
        if cap == "display_or_speaker":
            return self.has_display or self.has_speaker
        return True

    @callback
    def reconcile_capability_entities(self) -> list[str]:
        """Prune stale capability-gated Latter entities once `device_hello` reports real capabilities."""
        if self.is_ble_tag or not self.hardware_manifest:
            return []
        ent_reg = er.async_get(self.hass)
        pruned: list[str] = []
        for domain, suffix, cap in _CAPABILITY_GATED_ENTITIES:
            if self._supports_entity_capability(cap):
                continue
            eid = ent_reg.async_get_entity_id(
                domain, DOMAIN, f"{self.subentry_id}_{suffix}"
            )
            if eid is not None:
                ent_reg.async_remove(eid)
                pruned.append(eid)
        return pruned

    @callback
    def on_transport_disconnected(self) -> None:
        """Handle bound ESPHome outbox transitioning to `unavailable`."""
        self._transport_reconnect_sync_mono = 0.0
        self.clear_last_pushed_v3()
        self.async_update_listeners()

    @callback
    def on_transport_reconnected(self) -> None:
        """Handle bound ESPHome outbox recovering from `unavailable` without a simultaneous `device_hello`."""
        self._transport_reconnect_sync_mono = time.monotonic()
        self.clear_last_pushed_v3()
        self.create_background_task(
            self.async_provision_pin_session_key(),
            f"latter_pin_key_{self.device_slug}",
        )
        self.force_republish_all_domains()
        self.async_update_listeners()

    async def async_handle_device_hello(
        self,
        boot_id: str,
        manifest_raw: str,
        prefs_seq: int = 0,
        dirty_prefs: str = "",
    ) -> None:
        """Process firmware `device_hello`, reset boot-scoped timers on reboot, and converge prefs."""
        self._entered_hibernate = False
        had_manifest = bool(self.hardware_manifest)
        prev_caps = self._capability_fingerprint()
        is_new_boot, parsed = self._runtime.apply_device_hello(boot_id, manifest_raw)
        if parsed is not None:
            if self._ble_tracker is not None:
                manifest_beacon = parsed.get("beacon")
                if not isinstance(manifest_beacon, dict) and parsed.get("minor") is not None:
                    manifest_beacon = {
                        "major": parsed.get("major", 1),
                        "minor": parsed["minor"],
                    }
                self._ble_tracker.update_manifest_beacon(manifest_beacon)
            self._apply_device_health(parsed, str(boot_id or "").strip())
            self._sync_outdated_firmware_issue()
            self.reconcile_capability_entities()
            if had_manifest and any(
                now_has and not prev_has
                for prev_has, now_has in zip(
                    prev_caps[:3], self._capability_fingerprint()[:3], strict=True
                )
            ):
                self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
        if is_new_boot:
            self._local_needs_cold_resume = True
            self.handle_timer_alarm_state(False, False, 0, False)

        dev_seq = max(0, int(prefs_seq or 0))
        incoming_prefs = parse_dirty_prefs_records(dirty_prefs)
        if self._merge_hello_device_prefs(dev_seq, incoming_prefs):
            self.sync_ble_tracker()
            self._applied_options_snapshot = self._capture_options_snapshot()
            get_ble_fabric(self.hass).notify_occupancy_listeners()

        self._cached_prefs_payload = None
        self.schedule_persist_runtime_state()
        transport_just_synced = (
            self._transport_reconnect_sync_mono > 0.0
            and (time.monotonic() - self._transport_reconnect_sync_mono)
            < _RECONNECT_SYNC_DEDUP_S
        )
        self._transport_reconnect_sync_mono = 0.0
        if not transport_just_synced:
            self._notify_debouncer.async_cancel()
            self._last_pushed_v3.clear()
            await self.async_provision_pin_session_key()
            self.force_republish_all_domains()
        await self.async_push_beacon_uuid()
        await self._async_handle_reconnect()
        await self.async_sync_presence_beacon("hello")

    async def async_update_device_prefs(
        self,
        updates: Mapping[str, Any],
        *,
        min_next_seq: int | None = None,
        force_bump: bool = False,
    ) -> dict[str, Any]:
        """Validate, persist, and push subentry device preferences (sleep-safe when offline)."""
        cleaned = clean_device_settings(
            dict(updates),
            current=self.device_data,
            is_round_display=self.is_round_display,
            supports_hw_jpeg=self.supports_hw_jpeg,
        )
        if not cleaned and not force_bump:
            return {}
        prev_seq = self.prefs_seq
        if cleaned:
            needs_apply = CONF_NATIVE_BLE_TRACKING in cleaned
            self.update_device_config(
                {**self.device_data, **cleaned},
                bump_prefs_seq=True,
                mark_applied=not needs_apply,
                defer_apply=needs_apply,
            )
        if (force_bump and self.prefs_seq == prev_seq) or (
            min_next_seq is not None and self.prefs_seq < min_next_seq
        ):
            target_seq = max(
                self.prefs_seq + (1 if self.prefs_seq == prev_seq else 0),
                min_next_seq or 1,
            )
            self.prefs_seq = max(1, target_seq)
            for key in cleaned:
                self.prefs_key_seq[key] = self.prefs_seq
            self._cached_prefs_payload = None
            self.schedule_persist_runtime_state()
        self._cached_prefs_payload = None
        if "screensaver_mode" in cleaned or "screensaver_style" in cleaned:
            self.bind_screensaver_cycle_timer()
        if CONF_NATIVE_BLE_TRACKING in cleaned:
            await self.async_apply_options()
            self.async_update_listeners()
        else:
            self._applied_options_snapshot = self._capture_options_snapshot()
            self.async_update_listeners()
            self.async_notify_listeners()
        return cleaned

    async def async_handle_set_device_prefs(
        self, base_seq: int, changes_raw: str
    ) -> None:
        """Apply live touchscreen preference edits and echo canonical `device_prefs` back to clear `dirty_mask`."""
        incoming = parse_dirty_prefs_records(changes_raw)
        if not incoming:
            return
        await self.async_update_device_prefs(
            incoming,
            min_next_seq=max(self.prefs_seq, max(0, int(base_seq or 0))) + 1,
            force_bump=True,
        )

    @callback
    def handle_timer_alarm_state(
        self,
        timer_running: bool,
        timer_paused: bool,
        remaining_sec: int,
        ringing: bool,
        stopwatch_running: bool = False,
        stopwatch_paused: bool = False,
        stopwatch_elapsed_sec: int = 0,
    ) -> None:
        """Update event-driven timer, stopwatch, and alarm state without 1 Hz polling."""
        now_mono = time.monotonic()
        now_utc = dt_util.utcnow()
        self.timer_running = bool(timer_running)
        self.timer_paused = bool(timer_paused) and not self.timer_running
        self.timer_remaining_sec = max(0, int(remaining_sec or 0))
        self._timer_anchor_mono = now_mono
        if self.timer_running and self.timer_remaining_sec > 0:
            ends_dt = (now_utc + timedelta(seconds=self.timer_remaining_sec)).replace(
                microsecond=0
            )
            self.timer_ends_at_dt = ends_dt
            self.timer_ends_at_utc = ends_dt.isoformat(timespec="seconds")
        else:
            self.timer_ends_at_dt = None
            self.timer_ends_at_utc = ""
        self.alarm_ringing = bool(ringing)
        self.stopwatch_running = bool(stopwatch_running)
        self.stopwatch_paused = bool(stopwatch_paused) and not self.stopwatch_running
        self.stopwatch_elapsed_sec = max(0, int(stopwatch_elapsed_sec or 0))
        self._stopwatch_anchor_mono = now_mono
        self.stopwatch_started_at_utc = (
            (now_utc - timedelta(seconds=self.stopwatch_elapsed_sec)).isoformat(
                timespec="seconds"
            )
            if self.stopwatch_running
            else ""
        )

        self.async_update_listeners()

    async def async_set_screen_light(
        self, *, turn_on: bool, brightness_pct: int | None = None
    ) -> None:
        """Control the Device's display power & brightness via `latter_device_command`."""
        if turn_on:
            if brightness_pct is not None and not isinstance(brightness_pct, bool):
                pct = max(1, min(100, round(float(brightness_pct))))
                await self.async_send_device_command(f"set_screen_bri:{pct}")
                self.display_brightness_pct = pct
            else:
                await self.async_send_device_command("wake_screen")
            self.display_power_state = 0
        else:
            await self.async_send_device_command("screen_off")
            self.display_power_state = 2
        self.async_update_listeners()

    async def async_set_screensaver(self, active: bool) -> None:
        """Activate or deactivate the Device screensaver via `latter_device_command`."""
        await self.async_send_device_command(
            "activate_screensaver" if active else "deactivate_screensaver"
        )
        self.display_power_state = 1 if active else 0
        self.async_update_listeners()

    async def async_dismiss_alert(self) -> None:
        """Dismiss any active ringing alarm/timer/alert on the Device."""
        await self.async_send_device_command("dismiss_ringing")

    @callback
    def _apply_device_command_side_effects(self, cmd: str) -> None:
        if cmd == "dismiss_ringing":
            self.alarm_ringing = False
            self.async_update_listeners()
        elif cmd == "cancel_timer":
            self.timer_running = False
            self.timer_paused = False
            self.timer_remaining_sec = 0
            self.timer_ends_at_dt = None
            self.timer_ends_at_utc = ""
            self.async_update_listeners()
        elif cmd == "reset_stopwatch":
            self.stopwatch_running = False
            self.stopwatch_paused = False
            self.stopwatch_elapsed_sec = 0
            self.stopwatch_started_at_utc = ""
            self.async_update_listeners()

    async def async_send_device_command(
        self, command: str, *, raise_if_offline: bool = False
    ) -> bool:
        """Send an immediate action (`restart`, `find_my`, `activate_screensaver`, `trigger_va`, etc.) to the Device."""
        cmd = str(command or "").strip().lower()
        safe_cmd_label = "set_pin_key" if cmd.startswith("set_pin_key:") else cmd
        if self.is_ble_tag:
            if raise_if_offline:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="ble_tag_no_commands",
                )
            return False

        wifi_st = self.device_state(
            "sensor", "_system_wi_fi_signal", "_wi_fi_signal", "_ip_address"
        )
        wifi_offline = wifi_st is not None and wifi_st.state == STATE_UNAVAILABLE
        svc = esphome_service(
            self.hass, self.esphome_device_id, "latter_device_command"
        )

        if not wifi_offline and not self.is_rpc_outbox_unavailable():
            if svc:
                try:
                    await self.hass.services.async_call(
                        "esphome", svc, {"command": cmd}, blocking=True
                    )
                    self._apply_device_command_side_effects(cmd)
                    return True
                except Exception as err:
                    if raise_if_offline:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="device_command_failed",
                            translation_placeholders={
                                "command": safe_cmd_label,
                                "device": self.device_title,
                                "error": str(err),
                            },
                        ) from err
                    return False
            if cmd == "restart" and (
                restart_ent := self.device_entity(
                    "button", "_actions_restart_device", "_restart_device"
                )
            ):
                rst_st = self.hass.states.get(restart_ent)
                if rst_st is None or rst_st.state != STATE_UNAVAILABLE:
                    await self.hass.services.async_call(
                        "button",
                        "press",
                        {ATTR_ENTITY_ID: restart_ent},
                        blocking=True,
                    )
                    return True

        if raise_if_offline:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_offline_or_sleeping",
                translation_placeholders={"device": self.device_title},
            )
        return False

    async def async_execute_media_command(
        self,
        command: str,
        speaker: str | None = None,
        seek_position: float | None = None,
        media_id: str | None = None,
        media_type: str | None = None,
        enqueue: str | None = None,
        group_members: list[str] | str | None = None,
        *,
        radio_mode: bool = False,
        queue_item_id: str | None = None,
        pos_shift: int | str | None = None,
    ) -> None:
        await execute_coordinator_media_command(
            self,
            command,
            speaker,
            seek_position,
            media_id,
            media_type,
            enqueue,
            group_members,
            radio_mode=radio_mode,
            queue_item_id=queue_item_id,
            pos_shift=pos_shift,
        )

    @callback
    def async_set_active_speaker(
        self, speaker_entity_id: str, transfer_queue: bool = True
    ) -> None:
        set_coordinator_active_speaker(
            self, speaker_entity_id, transfer_queue=transfer_queue
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
        self.alert_id += 1
        self.alert_title = title.strip() or "Notification"
        self.alert_message = message.strip()
        self.alert_priority = priority.strip().lower() or "normal"
        self.alert_duration = max(
            _MIN_ALERT_DURATION_S, min(_MAX_ALERT_DURATION_S, int(duration))
        )
        self.alert_chime = bool(chime)
        clean_cam = str(camera_entity or "").strip()
        self.alert_camera_entity = clean_cam
        self.alert_camera_url = (
            self.build_camera_snapshot_url(
                clean_cam, cache_bust=f"{self.alert_id}_{int(time.time())}"
            )
            if clean_cam
            else ""
        )
        self.hass.bus.async_fire(
            EVENT_LATTER,
            {
                "type": "notification_dispatched",
                "device_slug": self.device_slug,
                "title": self.alert_title,
                "message": self.alert_message,
                "priority": self.alert_priority,
                "camera_url": self.alert_camera_url,
                "camera_entity": self.alert_camera_entity,
            },
        )
        self.schedule_persist_runtime_state()
        self.async_notify_listeners()

    # -----------------------------------------------------------------------
    # Protocol v3 Domain Packing & Dirty-Domain Push Transport
    # -----------------------------------------------------------------------

    @property
    def epoch(self) -> int:
        return self._packer.epoch

    def pack_domain_payload(self, domain: str, *fields: Any) -> tuple[int, str]:
        """Pack a Protocol v3 domain payload and advance coordinator `rev`."""
        cur_rev, packed = self._packer.pack(domain, *fields)
        self.rev = max(self.rev, self._packer.rev)
        return cur_rev, packed

    @callback
    def clear_last_pushed_v3(self) -> None:
        """Clear last-pushed Protocol v3 domain digest cache."""
        self._last_pushed_v3.clear()

    async def async_push_beacon_uuid(self) -> None:
        """Push the configured System/Device BLE Beacon UUID to ESPHome."""
        if (
            self.is_ble_tag
            or self.is_rpc_outbox_unavailable()
            or not (
                svc := esphome_service(
                    self.hass, self.esphome_device_id, "latter_set_beacon_uuid"
                )
            )
        ):
            return
        try:
            await self.hass.services.async_call(
                "esphome", svc, {"uuid": self.ble_beacon_uuid}, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("esphome.%s failed: %s", svc, err)

    def _collect_domain_payload_pairs(self) -> tuple[tuple[str, str], ...]:
        prefs_pair = (
            "device_prefs",
            str(self.get_device_prefs_payload()[1].get("payload") or ""),
        )
        if not self.has_display:
            return (prefs_pair,)
        return (
            ("active_media", str(self.get_active_media_payload()[1].get("payload") or "")),
            ("weather_forecast", str(self.weather_attributes.get("payload") or "")),
            ("area_context", str(self.get_area_context_payload()[1].get("payload") or "")),
            ("calendar_agenda", str(self.get_calendar_agenda_payload()[1].get("payload") or "")),
            ("remote_config", str(self.get_remote_config_payload()[1].get("payload") or "")),
            prefs_pair,
        )

    async def _async_push_shortcuts_frames(
        self, svc: str, shortcuts_frames: tuple[str, ...]
    ) -> None:
        shortcuts_sig = "\n".join(shortcuts_frames)
        if not shortcuts_frames or self._last_pushed_v3.get("shortcuts") == shortcuts_sig:
            return
        try:
            for frame in shortcuts_frames:
                if self.is_rpc_outbox_unavailable():
                    self._last_pushed_v3.clear()
                    return
                await self.hass.services.async_call(
                    "esphome",
                    svc,
                    {"domain": "shortcuts", "payload": frame},
                    blocking=True,
                )
            self._last_pushed_v3["shortcuts"] = shortcuts_sig
        except Exception as err:  # noqa: BLE001
            self._last_pushed_v3.pop("shortcuts", None)
            _LOGGER.debug("esphome.%s (shortcuts) failed: %s", svc, err)

    async def async_push_dirty_v3_domains(self) -> None:
        """Push dirty Protocol v3 domain frames, aborting immediately on disconnect."""
        if self.is_ble_tag or not (
            svc := esphome_service(
                self.hass, self.esphome_device_id, "latter_push_v3"
            )
        ):
            return
        if self.is_rpc_outbox_unavailable():
            self._last_pushed_v3.clear()
            return
        if self._rpc_receiver is not None and self._rpc_receiver.is_reconnect_deferred:
            return

        for dom, payload in self._collect_domain_payload_pairs():
            if self.is_rpc_outbox_unavailable():
                self._last_pushed_v3.clear()
                return
            if not payload or self._last_pushed_v3.get(dom) == payload:
                continue
            try:
                await self.hass.services.async_call(
                    "esphome", svc, {"domain": dom, "payload": payload}, blocking=True
                )
                self._last_pushed_v3[dom] = payload
            except Exception as err:  # noqa: BLE001
                self._last_pushed_v3.pop(dom, None)
                _LOGGER.debug("esphome.%s (%s) failed: %s", svc, dom, err)
                if self.is_rpc_outbox_unavailable():
                    self._last_pushed_v3.clear()
                    return

        if self.has_display:
            _, shortcuts_frames = self.get_shortcuts_payload()
            await self._async_push_shortcuts_frames(svc, shortcuts_frames)

    @callback
    def force_republish_all_domains(self) -> None:
        """Bump packer epoch, invalidate cached frames, and schedule a full Protocol v3 republish."""
        self._notify_debouncer.async_cancel()
        self._packer.force_republish_all_domains()
        self.rev = max(self.rev, self._packer.rev)
        self._last_pushed_v3.clear()
        self._cached_media_payload = None
        self._cached_media_anchor = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._cached_prefs_payload = None
        self._cached_shortcuts_payload = None
        if self.weather_attributes and "condition" in self.weather_attributes:
            wa = self.weather_attributes
            wa["rev"], wa["payload"] = self.pack_domain_payload(
                "weather_forecast",
                *pack_weather_forecast_fields(
                    wa.get("condition"),
                    wa.get("temperature"),
                    wa.get("humidity"),
                    wa.get("wind_speed"),
                    wa.get("wind_bearing"),
                    wa.get("high"),
                    wa.get("low"),
                    self.forecast_records,
                    wa.get("sun_state"),
                    wa.get("sun_elevation"),
                    wa.get("sun_azimuth"),
                    wa.get("sun_next_rising"),
                    wa.get("sun_next_setting"),
                    wa.get("moon_phase"),
                    wa.get("temp_unit", ""),
                ),
            )
        self.async_update_listeners()
        if not self.is_ble_tag:
            self.create_background_task(
                self.async_push_dirty_v3_domains(),
                f"latter_push_v3_republish_{self.device_slug}",
            )

    async def _async_debounced_notify(self) -> None:
        self.async_update_listeners()
        await self.async_push_dirty_v3_domains()

    @callback
    def schedule_debounced_notify(self) -> None:
        """Schedule a debounced entity/Studio listener update and dirty-domain push."""
        self._notify_debouncer.async_schedule_call()

    @callback
    def async_notify_listeners(self) -> None:
        """Invalidate domain payload caches, persist runtime state, and schedule debounced push."""
        self._cached_media_payload = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._cached_prefs_payload = None
        self._cached_shortcuts_payload = None
        self.schedule_persist_runtime_state()
        self.schedule_debounced_notify()

    def _resolve_shortcut_wire_items(
        self, items: list[dict[str, Any]], *, max_len: int
    ) -> list[dict[str, Any]]:
        grid_keys = ("page", "col", "row", "col_span", "row_span")
        resolved: list[dict[str, Any]] = []
        for item in items[:max_len]:
            grid_extras = {k: item[k] for k in grid_keys if k in item}
            if item.get("kind") == "route":
                resolved.append(
                    {
                        "kind": "route",
                        "target": item["target"],
                        "action": "",
                        "label": item.get("label") or "",
                        "icon": item.get("icon") or "",
                        "confirm": False,
                        "state": -1,
                        "badge_style": str(item.get("badge_style") or ""),
                        "accent": str(item.get("accent") or ""),
                        **grid_extras,
                    }
                )
                continue
            target = str(item.get("target") or "").strip().lower()
            domain = target.split(".", 1)[0] if "." in target else ""
            st = self.hass.states.get(target)
            raw_state = st.state if st is not None else None
            live_state = resolve_shortcut_live_state(
                domain, raw_state, action=str(item.get("action") or "")
            )
            eff_label = str(item.get("label") or "") or sanitize_shortcut_label(
                (st.attributes.get("friendly_name") if st is not None else None)
                or target
            )
            eff_icon = str(item.get("icon") or "") or resolve_shortcut_entity_icon(
                domain,
                device_class=(
                    str(st.attributes.get("device_class") or "")
                    if st is not None
                    else ""
                ),
                entity_icon=(
                    str(st.attributes.get("icon") or "") if st is not None else ""
                ),
                state=str(raw_state or ""),
            )
            resolved.append(
                {
                    "kind": "entity",
                    "target": target,
                    "action": item.get("action") or "",
                    "label": eff_label,
                    "icon": eff_icon,
                    "confirm": bool(item.get("confirm", False)),
                    "state": live_state,
                    "badge_style": str(item.get("badge_style") or ""),
                    "accent": str(item.get("accent") or ""),
                    **grid_extras,
                }
            )
        return resolved

    def get_shortcuts_payload(self) -> tuple[int, tuple[str, ...]]:
        if self._cached_shortcuts_payload is not None:
            return self._cached_shortcuts_payload
        dock_wire = self._resolve_shortcut_wire_items(
            self.dock_items, max_len=MAX_DOCK_ITEMS
        )
        pinned_wire = self._resolve_shortcut_wire_items(
            self.pinned_items, max_len=MAX_PINNED_ITEMS
        )
        dock_recs = shortcut_records(dock_wire, max_records=MAX_DOCK_ITEMS)
        pinned_recs = shortcut_records(pinned_wire, max_records=MAX_PINNED_ITEMS)
        title_recs = pinned_page_title_records(self.pinned_page_titles)
        cur_rev, frames = self._packer.pack_shortcuts(
            dock_recs, pinned_recs, pinned_page_titles=title_recs
        )
        self.rev = max(self.rev, self._packer.rev)
        res = (cur_rev, frames)
        self._cached_shortcuts_payload = res
        return res

    def get_device_prefs_payload(self) -> tuple[int, dict[str, Any]]:
        if self._cached_prefs_payload is not None:
            return self._cached_prefs_payload
        sub_data = self._live_subentry().data
        eff_seq = max(1, self.prefs_seq)
        fields = pack_device_prefs_fields(
            eff_seq,
            sub_data,
            native_ble_tracking=self.native_ble_tracking_enabled,
            custom_color_hex=self.device_custom_color,
            is_round_display=self.is_round_display,
            supports_hw_jpeg=self.supports_hw_jpeg,
            do_not_disturb=self.do_not_disturb,
        )
        cur_rev, packed = self.pack_domain_payload("device_prefs", *fields)
        res = (
            eff_seq,
            {
                "prefs_seq": eff_seq,
                "device_group": self.device_group,
                "wake_word_mode": self.get_device_pref("wake_word_mode"),
                "alert_volume": self.get_device_pref("alert_volume"),
                "ble_beacon_enabled": self.native_ble_tracking_enabled,
                "rev": cur_rev,
                "payload": packed,
            },
        )
        self._cached_prefs_payload = res
        return res

    def get_effective_remote_entities_for_device(self) -> list[str]:
        return resolve_effective_remote_entities(
            self.hass,
            all_inventory=self.get_remote_entities_list(),
            groups=self.remote_groups,
            mode=self.device_remote_group,
            cur_area=(
                self.active_area_id or str(self.get_opt(CONF_DEFAULT_AREA) or "")
            ).strip(),
        )

    def get_remote_slots(self) -> list[dict[str, str]]:
        return [
            resolve_remote_slot_pair(self.hass, eid)
            for eid in self.get_effective_remote_entities_for_device()[:10]
        ]

    def get_remote_config_payload(self) -> tuple[str | None, dict[str, Any]]:
        return build_remote_config_payload(self)

    def get_area_context_payload(self) -> tuple[str, dict[str, Any]]:
        return build_area_context_payload(self)

    def get_active_media_payload(self) -> tuple[str | None, dict[str, Any]]:
        return build_active_media_payload(self)

    @callback
    def apply_calendar_snapshot(
        self, records: V3Records, raw_rows: list[dict[str, Any]]
    ) -> None:
        apply_coordinator_calendar_snapshot(self, records, raw_rows)

    async def async_refresh_calendar_agenda(self, days: int = 30) -> None:
        await async_refresh_coordinator_calendar(self, days=days)

    def get_calendar_agenda_payload(self) -> tuple[int, dict[str, Any]]:
        return build_calendar_agenda_payload(self)

    @callback
    def apply_weather_snapshot(
        self, weather_ent: str | None, snap: tuple[V3Records, dict[str, Any]] | None
    ) -> None:
        apply_coordinator_weather_snapshot(self, weather_ent, snap)

    async def async_refresh_weather_forecast(self) -> None:
        await async_refresh_coordinator_weather(self)

    # -----------------------------------------------------------------------
    # Setup, Options Reconciliation, Listeners, BLE Tracker Sync & Cleanup
    # -----------------------------------------------------------------------

    def _capture_structural_snapshot(self) -> dict[str, Any]:
        return {
            CONF_DEVICE_SLUG: self.device_slug,
            CONF_ESPHOME_DEVICE_ID: str(
                self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or ""
            ).strip(),
        }

    def has_structural_changes(self) -> bool:
        return self._capture_structural_snapshot() != self._structural_snapshot

    def _capture_options_snapshot(self) -> dict[str, Any]:
        sub = self._live_subentry()
        return {
            "title": str(sub.title or ""),
            "data": dict(sub.data),
        }

    def has_option_changes(self) -> bool:
        if self._suppress_update_listener_apply:
            return False
        return self._capture_options_snapshot() != self._applied_options_snapshot

    def _build_persisted_snapshot(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "active_speaker": self.active_speaker,
            "last_speaker": self.last_speaker,
            "active_area_id": self.active_area_id or "",
            "active_remote_slot": self.active_remote_slot,
            "current_wallpaper": self.current_wallpaper,
            "current_screensaver_photo": self.current_screensaver_photo,
            "last_media_uri": self.last_media_uri,
            "last_media_type": self.last_media_type,
            "last_media_title": self.last_media_title,
            "last_media_artist": self.last_media_artist,
            "last_media_album": self.last_media_album,
            "last_media_duration": round(self.last_media_duration, 1),
            "last_media_position": round(self._persisted_media_position, 1),
            "last_device_health": self.last_device_health,
            "hello_manifest": self._runtime.hello_manifest,
            "last_boot_id": self._runtime.last_boot_id,
            "entered_hibernate": self._entered_hibernate,
            "matched_ble_addresses": list(self._matched_ble_addresses[:8]),
            "prefs_seq": self.prefs_seq,
            "prefs_key_seq": dict(self.prefs_key_seq),
            "device_config_rev": self.device_config_rev,
        }

    def _apply_stored_media_and_visuals(self, stored: dict[str, Any]) -> None:
        if saved_spk := str(stored.get("active_speaker") or "").strip():
            self.active_speaker = saved_spk
        if saved_last := str(stored.get("last_speaker") or "").strip():
            self.last_speaker = saved_last
        if (saved_area := str(stored.get("active_area_id") or "").strip()) and not self.active_area_id:
            self.active_area_id = saved_area
        saved_slot = stored.get("active_remote_slot")
        if isinstance(saved_slot, int) and 1 <= saved_slot <= _MAX_REMOTE_SLOTS:
            self.active_remote_slot = saved_slot
        if saved_wp := str(stored.get("current_wallpaper") or "").strip():
            self.current_wallpaper = saved_wp
        if saved_ss := str(stored.get("current_screensaver_photo") or "").strip():
            self.current_screensaver_photo = saved_ss
        self.last_media_uri = str(stored.get("last_media_uri") or "")
        self.last_media_type = str(stored.get("last_media_type") or "music")
        self.last_media_title = str(stored.get("last_media_title") or "")
        self.last_media_artist = str(stored.get("last_media_artist") or "")
        self.last_media_album = str(stored.get("last_media_album") or "")
        self.last_media_duration = float(stored.get("last_media_duration") or 0.0)
        self.last_media_position = float(stored.get("last_media_position") or 0.0)
        self._persisted_media_position = self.last_media_position

    def _apply_stored_runtime(self, stored: dict[str, Any]) -> None:
        if not stored:
            return
        self.rev = max(1, int(stored.get("rev") or 1))
        self.alert_id = max(0, int(stored.get("alert_id") or 0))
        self._apply_stored_media_and_visuals(stored)
        saved_health = stored.get("last_device_health")
        self.last_device_health = (
            saved_health if isinstance(saved_health, dict) else None
        )
        saved_manifest = stored.get("hello_manifest")
        if isinstance(saved_manifest, dict) and (
            ("w" in saved_manifest and "h" in saved_manifest)
            or "core_rev" in saved_manifest
            or "display" in saved_manifest
        ):
            self._runtime.hello_manifest = dict(saved_manifest)
        if saved_boot_id := str(stored.get("last_boot_id") or "").strip():
            self._runtime.last_boot_id = saved_boot_id
        self._entered_hibernate = bool(stored.get("entered_hibernate"))
        raw_matched = stored.get("matched_ble_addresses")
        if isinstance(raw_matched, list):
            self._matched_ble_addresses = [
                norm
                for item in raw_matched[:8]
                if (norm := str(item or "").strip().upper())
            ]
        self.prefs_seq = max(0, int(stored.get("prefs_seq") or 0))
        self.device_config_rev = max(1, int(stored.get("device_config_rev") or 1))
        raw_key_seq = stored.get("prefs_key_seq")
        if isinstance(raw_key_seq, dict):
            self.prefs_key_seq = {
                str(k): max(0, int(v))
                for k, v in raw_key_seq.items()
                if isinstance(v, (int, float))
            }

    async def async_flush_runtime_state(self) -> None:
        """Flush persisted runtime state immediately before a Home Assistant backup."""
        self.sync_persisted_media_position()
        await self._runtime.async_flush(self._build_persisted_snapshot())

    @callback
    def _async_on_core_config_update(self, _event: Event[Any]) -> None:
        self._url_signer.invalidate_lan_base_url()
        self.create_background_task(
            self._url_signer.async_prime_lan_base_url(),
            f"latter_lan_url_{self.device_slug}",
        )
        self.async_notify_listeners()

    def _init_startup_speaker_and_area(self) -> None:
        self.async_heal_renamed_local_speaker()
        self._configured_default_speaker = self._resolved_configured_default_speaker()
        local_spk = self.local_speaker
        if not (
            local_spk
            or esphome_service(self.hass, self.esphome_device_id, "latter_set_slots")
        ):
            self.active_speaker = self.last_speaker = ""
        else:
            if not self.active_speaker:
                self.active_speaker = self._configured_default_speaker
            enforce_local_speaker_if_remote_idle(self, "ha_startup")
            if not self.last_speaker:
                self.last_speaker = self.active_speaker

        prev_stored_active = self.active_area_id
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        esp_area = str(esp_dev.area_id or "").strip() if esp_dev else ""
        conf_area = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        if not self.is_ble_tag and not self.native_ble_tracking_enabled:
            static_area = esp_area or conf_area
            self.active_area_id = static_area or None
            if static_area != conf_area:
                self.update_device_config(
                    {**self.device_data, CONF_DEFAULT_AREA: static_area},
                    bump_prefs_seq=False,
                )
            self._configured_default_area = static_area
            self._configured_ble_tracking = False
            if static_area and self.esphome_device_id:
                sync_esphome_device_area(
                    self.hass,
                    self.esphome_device_id,
                    static_area,
                    require_ble_proxy_area=False,
                )
        else:
            proxy_areas = get_ble_proxy_area_ids(self.hass) | get_ble_signature_area_ids(
                self.hass
            )
            if (
                not conf_area
                and self.active_area_id
                and proxy_areas
                and self.active_area_id not in proxy_areas
            ):
                self.active_area_id = None
            if not self.active_area_id:
                self.active_area_id = (conf_area or esp_area) or None
            self._configured_default_area = conf_area
            self._configured_ble_tracking = self.native_ble_tracking_enabled
        if self.active_area_id != prev_stored_active:
            self.schedule_persist_runtime_state()

    async def _async_sync_startup_feeds(self) -> None:
        if (sys_obj := get_latter_system(self.hass)) is not None:
            sys_obj.bind_feed_listeners()
            if sys_obj.weather_loaded:
                self.apply_weather_snapshot(
                    sys_obj.weather_entity, sys_obj.weather_snapshot
                )
            else:
                await self.async_refresh_weather_forecast()
            if sys_obj.calendar_loaded:
                self.apply_calendar_snapshot(
                    sys_obj.calendar_records, sys_obj.calendar_raw_rows
                )
            else:
                await self.async_refresh_calendar_agenda()
            return
        await self.async_refresh_weather_forecast()
        await self.async_refresh_calendar_agenda()

    async def async_setup(self) -> None:
        """Load persisted runtime state, bind listeners, and seed Protocol v3 domains."""
        if self._rpc_receiver is None and (
            rpc_factory := get_rpc_receiver_factory()
        ) is not None:
            self._rpc_receiver = rpc_factory(self.hass, self)

        await self._url_signer.async_prime_lan_base_url()
        self._apply_stored_runtime(await self._runtime.async_load())
        self._sync_outdated_firmware_issue()
        self.reconcile_capability_entities()
        self._structural_snapshot = self._capture_structural_snapshot()
        self._runtime.seed_snapshot(self._build_persisted_snapshot())
        self._init_startup_speaker_and_area()
        self.async_sync_ha_device_areas()
        self._bind_all_listeners()
        self._unsub_core_config = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._async_on_core_config_update
        )
        self.sync_ble_tracker()
        if not self.is_ble_tag:
            if self._rpc_receiver is not None:
                self._rpc_receiver.start()
            await self.async_provision_pin_session_key()
            await self.async_push_beacon_uuid()
            await self._async_sync_startup_feeds()
        await self.async_sync_presence_beacon("options")
        self._applied_options_snapshot = self._capture_options_snapshot()
        try:
            async_audit_coordinator_health(self.hass, self)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Repairs audit skipped: %s", err)

    def _apply_ble_and_area_option_changes(self) -> None:
        new_ble = self.native_ble_tracking_enabled
        new_def_area = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        ble_changed = new_ble != self._configured_ble_tracking
        area_changed = new_def_area != self._configured_default_area
        if self.is_ble_tag or not (ble_changed or area_changed):
            return
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        esp_area = str(esp_dev.area_id or "").strip() if esp_dev else ""
        if not new_ble:
            self._area_follow.cancel()
            if ble_changed and not area_changed and not new_def_area:
                pinned = str(self.active_area_id or esp_area or "").strip()
                if pinned:
                    new_def_area = pinned
                    self.update_device_config(
                        {**self.device_data, CONF_DEFAULT_AREA: new_def_area},
                        bump_prefs_seq=False,
                    )
            if self.esphome_device_id:
                sync_esphome_device_area(
                    self.hass,
                    self.esphome_device_id,
                    new_def_area,
                    require_ble_proxy_area=False,
                    allow_clear=True,
                )
            self._last_esp_area = new_def_area
            self._last_latter_area = new_def_area
            if new_def_area:
                self.async_set_active_area(new_def_area, sync_device_registry=False)
            else:
                self._clear_active_area()
        else:
            has_ble_lock = bool(
                self._ble_tracker and self._ble_tracker.current_area_id
            )
            if area_changed and not has_ble_lock:
                fallback_target = new_def_area or esp_area
                if fallback_target:
                    self.async_set_active_area(
                        fallback_target, sync_device_registry=False
                    )
                else:
                    self._clear_active_area()
        self._configured_ble_tracking = new_ble
        self._configured_default_area = new_def_area

    async def async_apply_options(self) -> None:
        """Apply updated subentry options in-place without reloading the config entry."""
        try:
            prev_snap = self._applied_options_snapshot
            new_snap = self._capture_options_snapshot()
            self._applied_options_snapshot = new_snap
            self._suppress_update_listener_apply = False
            presence_changed = _presence_options_changed(prev_snap, new_snap)
            self.invalidate_bound_entity_cache()
            new_conf_wp = str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()
            wp_pool = self.resolve_wallpaper_rotation_pool()
            if new_conf_wp != self._configured_wallpaper_source or (
                self.current_wallpaper and self.current_wallpaper not in wp_pool
            ):
                self._configured_wallpaper_source = new_conf_wp
                self.current_wallpaper = (
                    new_conf_wp
                    if new_conf_wp in wp_pool
                    else (wp_pool[0] if wp_pool else "")
                )
                self.schedule_persist_runtime_state()
            ss_pool = self.resolve_screensaver_photo_pool()
            if self.current_screensaver_photo and self.current_screensaver_photo not in ss_pool:
                self.current_screensaver_photo = ss_pool[0] if ss_pool else ""
                self.schedule_persist_runtime_state()
            self.doorbell_noise_reduction = normalize_noise_reduction(
                self.get_opt(
                    CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION
                )
            )
            self.sync_ble_tracker()
            self._apply_ble_and_area_option_changes()
            self._applied_options_snapshot = self._capture_options_snapshot()

            target_def_spk = self._resolved_configured_default_speaker()
            def_spk_changed = target_def_spk != self._configured_default_speaker
            self._configured_default_speaker = target_def_spk
            if (
                target_def_spk
                and target_def_spk != self.active_speaker
                and (def_spk_changed or not self.active_speaker)
            ):
                self.last_speaker, self.active_speaker = self.active_speaker, target_def_spk
                self.schedule_persist_runtime_state()
            self._bind_all_listeners()
            if self._rpc_receiver is not None:
                self._rpc_receiver.rebind()
            await self.async_push_beacon_uuid()
            await self.async_sync_presence_beacon("options")
            if presence_changed:
                get_ble_fabric(self.hass).notify_occupancy_listeners()
            self.async_notify_listeners()
        finally:
            self._suppress_update_listener_apply = False

    async def async_on_global_config_updated(
        self, changed_keys: set[str] | None = None
    ) -> None:
        """Refresh BLE spatial engine, listeners, and shared feeds after a System config save."""
        if (
            changed_keys is None or CONF_SYSTEM_BLE_UUID in changed_keys
        ) and not self.is_ble_tag:
            self.sync_ble_tracker()
        elif self._ble_tracker is not None:
            self._ble_tracker.configure_spatial_engine(
                scanner_offsets=self.ble_scanner_offsets,
                area_signatures=self.ble_area_signatures,
                ref_power_dbm=self.ble_ref_power,
                attenuation=self.ble_attenuation,
                max_radius_m=self.ble_max_radius_m,
                max_velocity_mps=self.ble_max_velocity_mps,
                away_timeout_s=float(self.ble_away_timeout_s),
            )
        self._bind_all_listeners()
        if not self.is_ble_tag:
            if changed_keys is None or CONF_SYSTEM_BLE_UUID in changed_keys:
                await self.async_push_beacon_uuid()
            sys_obj = get_latter_system(self.hass)
            if changed_keys is None or CONF_WEATHER_ENTITY in changed_keys:
                await (
                    sys_obj.async_refresh_weather_forecast(coalesce=True)
                    if sys_obj
                    else self.async_refresh_weather_forecast()
                )
            if changed_keys is None or CONF_CALENDAR_ENTITIES in changed_keys:
                await (
                    sys_obj.async_refresh_calendar_agenda(coalesce=True)
                    if sys_obj
                    else self.async_refresh_calendar_agenda()
                )
        self.async_notify_listeners()

    @callback
    def _on_ble_address_matched(self, addr: str) -> None:
        norm = str(addr or "").strip().upper()
        if not norm:
            return
        if self._matched_ble_addresses and self._matched_ble_addresses[0] == norm:
            return
        self._matched_ble_addresses = [
            norm,
            *(a for a in self._matched_ble_addresses if a != norm),
        ][:8]
        self.schedule_persist_runtime_state()

    @callback
    def _bind_all_listeners(self) -> None:
        if self.is_ble_tag:
            return
        bind_coordinator_speaker_listener(self)
        bind_coordinator_area_listeners(self)
        bind_coordinator_doorbell_listener(self)
        self.bind_wallpaper_cycle_timer()
        self.bind_screensaver_cycle_timer()

    @callback
    def sync_ble_tracker(self) -> None:
        """Start, stop, or reconfigure the native BLE spatial tracker from current options."""
        if not self.native_ble_tracking_enabled:
            if self._ble_tracker is not None:
                self._ble_tracker.async_stop()
                self._ble_tracker = None
            return

        if self._ble_tracker is not None:
            if (
                getattr(self._ble_tracker, "beacon_uuid", self.ble_beacon_uuid)
                != self.ble_beacon_uuid
                or getattr(
                    self._ble_tracker, "target_address", self.ble_target_address
                )
                != self.ble_target_address
            ):
                self._ble_tracker.async_stop()
                self._ble_tracker = None
            else:
                self._ble_tracker.configure_spatial_engine(
                    scanner_offsets=self.ble_scanner_offsets,
                    area_signatures=self.ble_area_signatures,
                    ref_power_dbm=self.ble_ref_power,
                    attenuation=self.ble_attenuation,
                    max_radius_m=self.ble_max_radius_m,
                    max_velocity_mps=self.ble_max_velocity_mps,
                    away_timeout_s=float(self.ble_away_timeout_s),
                )
        if self._ble_tracker is None:
            hw_manifest = self.hardware_manifest
            manifest_beacon = hw_manifest.get("beacon")
            if not isinstance(manifest_beacon, dict) and hw_manifest.get("minor") is not None:
                manifest_beacon = {
                    "major": hw_manifest.get("major", 1),
                    "minor": hw_manifest["minor"],
                }
            self._ble_tracker = LatterNativeBleTracker(
                hass=self.hass,
                beacon_uuid=self.ble_beacon_uuid,
                device_slug=self.device_slug,
                on_area_detected=self._async_on_native_ble_area_detected,
                scanner_offsets=self.ble_scanner_offsets,
                area_signatures=self.ble_area_signatures,
                ref_power_dbm=self.ble_ref_power,
                attenuation=self.ble_attenuation,
                max_radius_m=self.ble_max_radius_m,
                max_velocity_mps=self.ble_max_velocity_mps,
                away_timeout_s=float(self.ble_away_timeout_s),
                target_address=self.ble_target_address,
                esphome_device_id=self.esphome_device_id,
                manifest_beacon=manifest_beacon,
                should_hold_during_ble_sleep=self.is_ble_sleep_expected,
                initial_matched_addresses=self._matched_ble_addresses,
                on_address_matched=self._on_ble_address_matched,
                subentry_id=self.subentry_id,
            )
            self._ble_tracker.async_start()

    @callback
    def async_cleanup(self) -> None:
        """Cancel all debouncers, background tasks, BLE trackers, and state listeners."""
        self._notify_debouncer.async_cancel()
        self.cancel_background_tasks()
        self._area_follow.cancel()
        self.invalidate_bound_entity_cache()
        if not self.is_ble_tag:
            ir.async_delete_issue(
                self.hass, DOMAIN, outdated_firmware_issue_id(self.subentry_id)
            )
        if self._rpc_receiver is not None:
            self._rpc_receiver.stop()
        if self._doorbell_reply_task is not None and not self._doorbell_reply_task.done():
            self._doorbell_reply_task.cancel()
        self._doorbell_reply_task = None
        if self._ble_tracker is not None:
            self._ble_tracker.async_stop()
            self._ble_tracker = None
        for attr in (
            "_unsub_core_config",
            "_unsub_speaker_state",
            "_unsub_alarm_state",
            "_unsub_remotes_state",
            "_unsub_shortcuts_state",
            "_unsub_area_entities_state",
            "_unsub_area_debounce",
            "_unsub_wallpaper_timer",
            "_unsub_screensaver_timer",
            "_unsub_doorbell_ring_state",
            "_unsub_reconnect_post_delay",
        ):
            if (unsub := getattr(self, attr, None)) is not None:
                unsub()
                setattr(self, attr, None)


def match_coordinator_target(
    hass: HomeAssistant,
    coords: Sequence[LatterCoordinator],
    target: str | None,
) -> LatterCoordinator | None:
    """Match a loaded `LatterCoordinator` by `subentry_id`, Latter or ESPHome `device_id`, or exact slug."""
    if not coords:
        return None
    if not target or not str(target).strip():
        return coords[0] if len(coords) == 1 else None
    raw = str(target).strip()
    norm = normalize_device_slug(raw)
    target_dev = dr.async_get(hass).async_get(raw)
    for coord in coords:
        if (
            coord.subentry_id == raw
            or coord.device_slug == norm
            or (coord.esphome_device_id and coord.esphome_device_id == raw)
        ):
            return coord
        if isinstance(target_dev, dr.DeviceEntry):
            mac = coord.device_mac
            if (DOMAIN, coord.subentry_id) in target_dev.identifiers or (
                mac and (DOMAIN, dr.format_mac(mac)) in target_dev.identifiers
            ):
                return coord
            if (
                target_dev.via_device_id
                and coord.esphome_device_id
                and target_dev.via_device_id == coord.esphome_device_id
            ):
                return coord
    return None


def resolve_coordinator(
    hass: HomeAssistant, target: str | None = None
) -> LatterCoordinator | None:
    """Resolve a loaded `LatterCoordinator` by `subentry_id`, `device_id`, or exact slug."""
    coords: list[LatterCoordinator] = list(iter_coordinators(hass))
    return match_coordinator_target(hass, coords, target)
