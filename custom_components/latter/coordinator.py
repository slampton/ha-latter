"""Unified push state coordinator, persisted runtime store, and Area follow controller for one Latter Device."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import json
import logging
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
    issue_registry as ir,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .areas import (
    bind_coordinator_area_listeners,
    build_area_context_payload,
    find_area_media_entities,
    get_home_alarm_summary,
    match_area_by_name_or_id,
    resolve_active_area_entry,
    sync_esphome_device_area,
)
from .const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_ALARM_ENTITY,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_OFFSETS,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_CALENDAR_ENTITIES,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_ENTITY,
    CONF_CUSTOM_PALETTES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_APPS,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_ESPHOME_DEVICE_ID,
    CONF_GARAGE_ENTITY,
    CONF_HOME_CATEGORIES,
    CONF_LOCK_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_SYSTEM_BLE_UUID,
    CONF_THERMOSTAT_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DEFAULT_ACTIVITY_CARD,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_AREA_FOLLOW_DWELL_S,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_CARD_SLOT_COUNT,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_DOCK_APPS,
    DEFAULT_DOORBELL_NOISE_REDUCTION,
    DEFAULT_HOME_CATEGORIES,
    DEFAULT_LIST_SLOT_COUNT,
    DEFAULT_NATIVE_BLE_TRACKING,
    DEFAULT_SECURITY_PIN_POLICY,
    DEFAULT_SITE_ID,
    DEFAULT_SYNC_DEVICE_AREA,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DOMAIN,
    EVENT_LATTER,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    SUBENTRY_BLE_TAG,
    WALLPAPER_MAX_DIM,
    normalize_device_slug,
    normalize_noise_reduction,
)
from .doorbell import bind_coordinator_doorbell_listener
from .feeds import (
    apply_coordinator_calendar_snapshot,
    apply_coordinator_weather_snapshot,
    async_refresh_coordinator_calendar,
    async_refresh_coordinator_weather,
    build_calendar_agenda_payload,
    init_weather_attributes,
)
from .http import UrlSigner
from .hub import get_latter_system, iter_coordinators
from .identity import (
    LatterRpcReceiver,
    esphome_service,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    manifest_has_audio,
    manifest_has_battery,
    manifest_has_display,
    manifest_has_imu,
    manifest_has_mic,
    manifest_has_speaker,
    manifest_is_roaming,
    manifest_is_round,
    manifest_is_wearable,
    read_device_hardware_manifest,
    resolve_bound_esphome_device_id,
)
from .media import (
    bind_coordinator_speaker_listener,
    build_active_media_payload,
    enforce_local_speaker_if_remote_idle,
    execute_coordinator_media_command,
    resolve_esphome_local_speaker,
    resolve_ma_counterpart_entity,
    set_coordinator_active_speaker,
)
from .presence import (
    AreaFollowDwell,
    FollowAction,
    LatterNativeBleTracker,
    get_ble_fabric,
    get_ble_proxy_area_ids,
)
from .protocol import (
    DomainPayloadPacker,
    V3Records,
    effective_security_pin_policy,
    normalize_activity_sources,
    normalize_area_categories,
    normalize_home_categories,
    normalize_security_pin_policy,
    pack_device_prefs_fields,
    parse_dirty_prefs_records,
)
from .remotes import (
    build_remote_config_payload,
    resolve_effective_remote_entities,
    resolve_remote_slot_pair,
)
from .repairs import (
    ISSUE_ROLLED_BACK,
    async_audit_coordinator_health,
    device_health_issue_id,
    evaluate_device_health,
    parse_device_health,
)
from .studio.settings import (
    DEVICE_PREF_KEYS,
    clean_device_settings,
    resolve_device_pref_value,
)
from .wallpapers import ordered_wallpaper_ids

_LOGGER = logging.getLogger(__name__)


class LatterDeviceRuntime:
    """Manages change-gated .storage/latter.runtime.<entry_id> persistence and device_hello state."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the per-device runtime store."""
        self.hass = hass
        self.entry_id = entry_id
        self.store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}"
        )
        self._last_persisted_snapshot: dict[str, Any] | None = None
        self.hello_manifest: dict[str, Any] = {}
        self.last_boot_id: str = ""

    async def async_load(self) -> dict[str, Any]:
        """Load persisted runtime state from disk."""
        try:
            stored = await self.store.async_load()
            if isinstance(stored, dict):
                return stored
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed loading Latter runtime store: %s", err)
        return {}

    @callback
    def schedule_save(self, snapshot_builder: Callable[[], dict[str, Any]]) -> None:
        """Persist runtime state to HA Store only when semantic values change."""
        snap = snapshot_builder()
        if snap == self._last_persisted_snapshot:
            return
        self._last_persisted_snapshot = dict(snap)
        self.store.async_delay_save(snapshot_builder, delay=1.5)

    async def async_flush(self, snapshot: dict[str, Any]) -> None:
        """Immediately persist a runtime snapshot to disk (used by pre-backup hook)."""
        self._last_persisted_snapshot = dict(snapshot)
        await self.store.async_save(snapshot)

    def seed_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Record the baseline snapshot after initial load."""
        self._last_persisted_snapshot = dict(snapshot)

    def apply_device_hello(
        self, boot_id: str, manifest_raw: str
    ) -> tuple[bool, dict[str, Any] | None]:
        """Parse device_hello handshake and return (is_new_boot, parsed_manifest_or_none)."""
        parsed_manifest: dict[str, Any] | None = None
        if manifest_raw and manifest_raw.strip().startswith("{"):
            try:
                parsed = json.loads(manifest_raw)
                if isinstance(parsed, dict) and "w" in parsed and "h" in parsed:
                    self.hello_manifest = parsed
                    parsed_manifest = parsed
            except (ValueError, TypeError):
                pass

        clean_boot_id = str(boot_id or "").strip()
        is_new_boot = bool(clean_boot_id and clean_boot_id != self.last_boot_id)
        if clean_boot_id:
            self.last_boot_id = clean_boot_id
        return is_new_boot, parsed_manifest


class LatterAreaFollowController:
    """Manages dwell-gated ESPHome device area updates for 'Voice Follows Me'."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Voice Follows Me dwell controller."""
        self.hass = hass
        self._unsub_dwell: Callable[[], None] | None = None
        self._dwell = AreaFollowDwell()
        self.last_area_follow_write: dict[str, Any] | None = None

    @property
    def pending_area_id(self) -> str | None:
        """Return the Area a BLE-driven move is waiting to commit, if any."""
        return self._dwell.pending_area_id

    @callback
    def _cancel_timer(self) -> None:
        if self._unsub_dwell is not None:
            self._unsub_dwell()
            self._unsub_dwell = None

    @callback
    def cancel(self) -> None:
        """Cancel any pending dwell timer."""
        self._cancel_timer()
        self._dwell.cancel()

    @callback
    def schedule_or_commit(
        self,
        *,
        esphome_device_id: str | None,
        target_area_id: str,
        ble_driven: bool,
        dwell_s: int,
        is_allowed_cb: Callable[[], bool],
    ) -> None:
        """Schedule a dwell-gated area update (for BLE moves) or apply immediately (for explicit picks)."""
        if not esphome_device_id or not is_allowed_cb():
            self.cancel()
            return

        action = self._dwell.request(
            target_area_id,
            ble_driven=ble_driven,
            dwell_s=dwell_s,
            now=time.monotonic(),
        )
        if action is FollowAction.PENDING:
            return
        self._cancel_timer()
        if action is FollowAction.IGNORE:
            return

        if action is FollowAction.DWELL:

            @callback
            def _commit_dwell_sync(_now: datetime) -> None:
                self._unsub_dwell = None
                if (
                    self._dwell.take_due(target_area_id, time.monotonic())
                    and is_allowed_cb()
                ):
                    rec = sync_esphome_device_area(
                        self.hass,
                        esphome_device_id,
                        target_area_id,
                        require_ble_proxy_area=True,
                    )
                    if rec is not None:
                        self.last_area_follow_write = rec

            self._unsub_dwell = async_call_later(
                self.hass, float(dwell_s), _commit_dwell_sync
            )
            return

        rec = sync_esphome_device_area(
            self.hass,
            esphome_device_id,
            target_area_id,
            require_ble_proxy_area=ble_driven,
        )
        if rec is not None:
            self.last_area_follow_write = rec


def match_coordinator_target(
    hass: HomeAssistant, coords: list[LatterCoordinator], target: str | None
) -> LatterCoordinator | None:
    """Match a loaded coordinator by subentry_id, Latter or ESPHome device_id, or exact slug."""
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
        if target_dev is not None:
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
    """Resolve a loaded LatterCoordinator by subentry_id, Latter or ESPHome device_id, or exact slug."""
    return match_coordinator_target(hass, iter_coordinators(hass), target)


class LatterCoordinator:
    """Pure push coordinator managing Protocol v3 domains, BLE presence, media, and Area state for one Device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hmac_secret: bytes,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the push LatterCoordinator for one Device subentry."""
        self.hass = hass
        self.entry = entry
        self.config_entry = entry
        self.subentry = subentry
        self.subentry_id: str = subentry.subentry_id
        self.name: str = f"{DOMAIN}_{self.subentry_id}"
        self._listeners: dict[Callable[[], None], None] = {}
        self._hmac_secret = hmac_secret
        self._runtime = LatterDeviceRuntime(hass, self.subentry_id)
        self._url_signer = UrlSigner(hass, self.subentry_id, hmac_secret)
        self._packer = DomainPayloadPacker()
        self._area_follow = LatterAreaFollowController(hass)
        self._cached_esphome_device_id: str | None = None
        self.rev: int = 1
        self._notify_debouncer: Debouncer[None] = Debouncer(
            hass,
            _LOGGER,
            cooldown=0.2,
            immediate=False,
            function=self._async_debounced_notify,
        )
        self._rpc_receiver = LatterRpcReceiver(hass, self)

        self._cached_media_payload: tuple[float, tuple[str | None, dict[str, Any]]] | None = None
        self._cached_media_anchor: tuple[tuple[Any, ...], float] | None = None
        self._cached_area_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._cached_remote_payload: tuple[float, tuple[str | None, dict[str, Any]]] | None = None
        self._cached_prefs_payload: tuple[int, dict[str, Any]] | None = None
        self.prefs_seq: int = 0
        self.prefs_key_seq: dict[str, int] = {}
        self.timer_running: bool = False
        self.timer_paused: bool = False
        self.timer_remaining_sec: int = 0
        self._timer_anchor_mono: float = 0.0
        self.alarm_ringing: bool = False
        self._unsub_timer_tick: Callable[[], None] | None = None
        self._unsub_core_config: Callable[[], None] | None = None
        self._unsub_speaker_state: Callable[[], None] | None = None
        self._tracked_ma_counterpart: str | None = None
        self._unsub_alarm_state: Callable[[], None] | None = None
        self._unsub_remotes_state: Callable[[], None] | None = None
        self._unsub_area_entities_state: Callable[[], None] | None = None
        self._unsub_area_debounce: Callable[[], None] | None = None
        self._unsub_wallpaper_timer: Callable[[], None] | None = None
        self._unsub_doorbell_ring_state: Callable[[], None] | None = None
        self._unsub_link_report_state: Callable[[], None] | None = None
        self._entered_hibernate: bool = False
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
        self.on_area_changed_push_slots: Callable[[LatterCoordinator], Any] | None = None
        self.last_media_uri: str = ""
        self.last_media_type: str = "music"
        self.last_media_title: str = ""
        self.last_media_artist: str = ""
        self.last_media_album: str = ""
        self.last_media_duration: float = 0.0
        self.last_media_position: float = 0.0
        self._resuming_guard_until: float = 0.0
        self._local_needs_cold_resume: bool = True
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
        self.forecast_records: V3Records = V3Records()
        self.weather_attributes: dict[str, Any] = init_weather_attributes(
            self._pack_domain_payload
        )
        self.calendar_records: V3Records = V3Records()
        self.calendar_events: list[dict[str, Any]] = []
        self.alert_id: int = 0
        self.alert_title: str = ""
        self.alert_message: str = ""
        self.alert_priority: str = "normal"
        self.alert_duration: int = 8
        self.alert_chime: bool = True
        self.alert_camera_url: str = ""
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
        self._last_esp_area: str = ""
        self._last_latter_area: str = ""
        self.current_wallpaper: str = ""
        self._structural_snapshot: dict[str, Any] = self._capture_structural_snapshot()

    # -----------------------------------------------------------------------
    # Listener & Subentry Configuration Accessors
    # -----------------------------------------------------------------------

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

        return _remove

    @callback
    def async_update_listeners(self) -> None:
        """Notify all registered push listeners."""
        for cb in list(self._listeners):
            cb()

    def _capture_structural_snapshot(self) -> dict[str, Any]:
        return {
            CONF_DEVICE_SLUG: self.device_slug,
            CONF_ESPHOME_DEVICE_ID: str(
                self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or ""
            ).strip(),
        }

    def has_structural_changes(self) -> bool:
        return self._capture_structural_snapshot() != self._structural_snapshot

    def _live_subentry(self) -> ConfigSubentry:
        live_sub = self.entry.subentries.get(self.subentry_id)
        if live_sub is not None:
            self.subentry = live_sub
        return self.subentry

    @property
    def device_data(self) -> dict[str, Any]:
        return dict(self._live_subentry().data)

    def update_device_config(
        self, merged_data: dict[str, Any], *, bump_prefs_seq: bool = True
    ) -> None:
        prev = self._live_subentry().data
        changed_pref_keys: list[str] = []
        if bump_prefs_seq:
            for k in DEVICE_PREF_KEYS:
                if resolve_device_pref_value(merged_data, k) != resolve_device_pref_value(prev, k):
                    changed_pref_keys.append(k)
            if bool(
                merged_data.get(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)
            ) != bool(prev.get(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)):
                changed_pref_keys.append(CONF_NATIVE_BLE_TRACKING)
            if (
                str(merged_data.get(CONF_DEVICE_CUSTOM_COLOR) or "").strip().upper()
                != str(prev.get(CONF_DEVICE_CUSTOM_COLOR) or "").strip().upper()
            ):
                changed_pref_keys.append(CONF_DEVICE_CUSTOM_COLOR)
            if changed_pref_keys:
                self.prefs_seq = max(1, self.prefs_seq + 1)
                for k in changed_pref_keys:
                    self.prefs_key_seq[k] = self.prefs_seq
                self._cached_prefs_payload = None
        self.hass.config_entries.async_update_subentry(
            self.entry, self._live_subentry(), data=merged_data
        )
        self._live_subentry()
        if changed_pref_keys:
            self._schedule_persist_runtime_state()

    def get_opt(self, key: str, default: Any = None) -> Any:
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
        if key in GLOBAL_CONFIG_KEYS:
            if (
                isinstance(global_cfg, dict)
                and key in global_cfg
                and global_cfg[key] is not None
            ):
                return global_cfg[key]
            return default
        sub_data = self._live_subentry().data
        if key in sub_data:
            return sub_data[key]
        if isinstance(global_cfg, dict) and key in global_cfg:
            return global_cfg[key]
        return default

    # -----------------------------------------------------------------------
    # Device Identity, Hardware Manifest Traits & Option Properties
    # -----------------------------------------------------------------------

    @property
    def epoch(self) -> int:
        return self._packer.epoch

    @property
    def last_area_follow_write(self) -> dict[str, Any] | None:
        return self._area_follow.last_area_follow_write

    @property
    def doorbell_ring_map(self) -> dict[str, str]:
        return dict(self._doorbell_ring_map)

    @property
    def device_slug(self) -> str:
        return normalize_device_slug(
            str(self._live_subentry().data.get(CONF_DEVICE_SLUG) or "")
        )

    @property
    def device_mac(self) -> str | None:
        stored_mac = str(self.get_opt("mac", "") or "").strip()
        if stored_mac:
            return dr.format_mac(stored_mac)
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        if esp_dev is not None:
            for ctype, cval in esp_dev.connections:
                if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                    return dr.format_mac(str(cval))
        ble_addr = str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()
        return (
            dr.format_mac(ble_addr)
            if len(ble_addr) == 17 and ble_addr.count(":") == 5
            else None
        )

    @property
    def device_title(self) -> str:
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

    def device_entity(self, domain: str, *suffixes: str) -> str | None:
        return find_device_entity_by_suffix(
            self.hass, self.esphome_device_id, domain, suffixes
        )

    def device_state(self, domain: str, *suffixes: str) -> State | None:
        ent_id = self.device_entity(domain, *suffixes)
        return self.hass.states.get(ent_id) if ent_id else None

    def get_device_info(self) -> DeviceInfo:
        esp_dev_id = self.esphome_device_id
        mac = self.device_mac
        ident_key = dr.format_mac(mac) if mac else self.subentry_id
        return DeviceInfo(
            identifiers={(DOMAIN, ident_key)},
            name=self.device_title,
            manufacturer="Lampton Labs",
            model="Latter ESPHome Companion Middleware",
            sw_version=INTEGRATION_VERSION,
            configuration_url=f"homeassistant://latter/devices/{self.subentry_id}",
            **({"via_device_id": esp_dev_id} if esp_dev_id else {}),
        )

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
        return self.subentry.subentry_type == SUBENTRY_BLE_TAG

    @property
    def has_display(self) -> bool:
        return not self.is_ble_tag and manifest_has_display(self.hardware_manifest)

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
            or bool(self.device_entity("binary_sensor", "_ble_radio_active"))
        )

    @property
    def is_round_display(self) -> bool:
        return self.has_display and manifest_is_round(self.hardware_manifest)

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
    def is_wearable(self) -> bool:
        return manifest_is_wearable(self.hardware_manifest)

    @property
    def is_roaming_device(self) -> bool:
        return manifest_is_roaming(self.hardware_manifest)

    @property
    def device_group(self) -> str:
        raw = str(
            self.get_opt(CONF_DEVICE_GROUP, DEFAULT_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP
        ).strip()
        return DEFAULT_DEVICE_GROUP if raw == "handhelds" and not self.has_display else raw

    @property
    def display_shape(self) -> str:
        hw_shape = str(self.hardware_manifest.get("shape") or "").strip().lower()
        return hw_shape if hw_shape in ("circle", "square") else DEFAULT_DISPLAY_SHAPE

    @property
    def list_slot_capacity(self) -> int:
        try:
            raw = self.hardware_manifest.get("slot_count")
            val = int(raw) if raw is not None else DEFAULT_LIST_SLOT_COUNT
        except (TypeError, ValueError):
            val = DEFAULT_LIST_SLOT_COUNT
        return max(1, min(20, val))

    @property
    def card_slot_capacity(self) -> int:
        try:
            raw = self.hardware_manifest.get("card_slot_count")
            val = int(raw) if raw is not None else DEFAULT_CARD_SLOT_COUNT
        except (TypeError, ValueError):
            val = DEFAULT_CARD_SLOT_COUNT
        return max(1, min(20, val))

    @property
    def dock_apps_csv(self) -> str:
        return str(self.get_opt(CONF_DOCK_APPS, DEFAULT_DOCK_APPS)).strip()

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
    def wallpaper_source(self) -> str:
        return (
            self.current_wallpaper
            or str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()
        )

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
        if raw.startswith("#") and len(raw) == 7:
            return raw
        return self.custom_palettes[0]["hex"] if self.custom_palettes else "#3898FF"

    @property
    def weather_entity(self) -> str | None:
        val = self.get_opt(CONF_WEATHER_ENTITY)
        return str(val) if val else None

    @property
    def alarm_entity(self) -> str | None:
        val = self.get_opt(CONF_ALARM_ENTITY)
        if val:
            return str(val)
        return get_home_alarm_summary(self.hass)["entity_id"] or None

    @property
    def camera_entities(self) -> list[str]:
        raw_list = self.get_opt(CONF_CAMERA_ENTITIES)
        cleaned = (
            [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
            if isinstance(raw_list, list)
            else []
        )
        if not cleaned and (
            single := str(self.get_opt(CONF_CAMERA_ENTITY) or "").strip()
        ):
            cleaned = [single]
        return cleaned[:10]

    @property
    def camera_entity(self) -> str | None:
        cams = self.camera_entities
        return (
            cams[0]
            if cams
            else (str(self.get_opt(CONF_CAMERA_ENTITY) or "").strip() or None)
        )

    @property
    def thermostat_entity(self) -> str | None:
        return str(self.get_opt(CONF_THERMOSTAT_ENTITY) or "").strip() or None

    @property
    def lock_entity(self) -> str | None:
        return str(self.get_opt(CONF_LOCK_ENTITY) or "").strip() or None

    @property
    def garage_entity(self) -> str | None:
        return str(self.get_opt(CONF_GARAGE_ENTITY) or "").strip() or None

    @property
    def vacuum_entity(self) -> str | None:
        return str(self.get_opt(CONF_VACUUM_ENTITY) or "").strip() or None

    @property
    def native_ble_tracking_enabled(self) -> bool:
        return bool(self.get_opt(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING))

    @property
    def ble_beacon_uuid(self) -> str:
        sub_raw = str(self._live_subentry().data.get(CONF_BLE_BEACON_UUID) or "").strip()
        if sub_raw and sub_raw.upper() != DEFAULT_BLE_BEACON_UUID:
            return sub_raw.upper()
        sys_raw = str(self.get_opt(CONF_SYSTEM_BLE_UUID) or "").strip()
        return (sys_raw or sub_raw or DEFAULT_BLE_BEACON_UUID).upper()

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
        global_cfg = self.hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG)
        if isinstance(global_cfg, dict):
            return str(global_cfg.get(CONF_SECURITY_PIN_HASH) or "").strip() or None
        return None

    @property
    def has_security_pin(self) -> bool:
        return bool(self.security_pin_hash)

    @callback
    def update_hmac_secret(self, new_secret: bytes) -> None:
        self._hmac_secret = new_secret
        self._url_signer = UrlSigner(self.hass, self.subentry_id, new_secret)
        self._last_art_proxy_url = ""

    @property
    def ble_target_address(self) -> str:
        return str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()

    @property
    def ble_area_offsets(self) -> dict[str, float]:
        raw = self.get_opt(CONF_BLE_AREA_OFFSETS, {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            try:
                if (val := round(max(-25.0, min(25.0, float(v))), 1)) != 0.0:
                    out[str(k)] = val
            except (ValueError, TypeError):
                pass
        return out

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
                3,
                min(
                    60,
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

    @property
    def area_handoff_enabled(self) -> bool:
        return bool(self.get_opt(CONF_AREA_HANDOFF, DEFAULT_AREA_HANDOFF))

    @property
    def art_dimensions(self) -> tuple[int, int]:
        hw = self.hardware_manifest
        try:
            w, h = int(hw.get("w") or 0), int(hw.get("h") or 0)
        except (ValueError, TypeError):
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        if w < 64 or h < 64:
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        w, h = max(64, min(1920, w)), max(64, min(1920, h))
        peak = max(w, h)
        return (
            (w, h)
            if peak <= 502
            else (max(64, round(w * 480.0 / peak)), max(64, round(h * 480.0 / peak)))
        )

    @property
    def wallpaper_dimensions(self) -> tuple[int, int]:
        hw = self.hardware_manifest
        try:
            w, h = int(hw.get("w") or 0), int(hw.get("h") or 0)
        except (ValueError, TypeError):
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        if w < 64 or h < 64:
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        w, h = max(64, min(1920, w)), max(64, min(1920, h))
        peak = max(w, h)
        return (
            (w, h)
            if peak <= WALLPAPER_MAX_DIM
            else (
                max(64, round(w * float(WALLPAPER_MAX_DIM) / peak)),
                max(64, round(h * float(WALLPAPER_MAX_DIM) / peak)),
            )
        )

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

    # -----------------------------------------------------------------------
    # Scoped HMAC Resource Signing & URL Builders
    # -----------------------------------------------------------------------

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
        w, h = self.art_dimensions
        return self._url_signer.build_camera_snapshot_url(
            self.device_slug,
            (camera_entity_id or self.camera_entity or "").strip(),
            w,
            h,
            self.display_shape,
            cache_bust=cache_bust,
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

    def build_map_snapshot_url(self, location: str) -> str:
        w, h = self.art_dimensions
        return self._url_signer.build_map_snapshot_url(
            self.device_slug, location, w, h, self.display_shape
        )

    def build_wallpaper_url(self) -> str:
        w, h = self.wallpaper_dimensions
        return self._url_signer.build_wallpaper_url(
            self.device_slug, self.wallpaper_source, w, h, self.display_shape
        )

    def build_proxy_art_url(self, cache_bust: str) -> str:
        w, h = self.art_dimensions
        return self._url_signer.build_proxy_art_url(
            self.device_slug, w, h, self.display_shape, cache_bust
        )

    # -----------------------------------------------------------------------
    # Runtime Persistence, Setup, Options & Lifecycle
    # -----------------------------------------------------------------------

    def _build_persisted_snapshot(self) -> dict[str, Any]:
        return {
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
            "last_media_duration": round(self.last_media_duration, 1),
            "last_media_position": round(self.last_media_position, 1),
            "last_device_health": self.last_device_health,
            "hello_manifest": self._runtime.hello_manifest,
            "last_boot_id": self._runtime.last_boot_id,
            "entered_hibernate": self._entered_hibernate,
            "prefs_seq": self.prefs_seq,
            "prefs_key_seq": dict(self.prefs_key_seq),
        }

    def _apply_stored_runtime(self, stored: dict[str, Any]) -> None:
        if not stored:
            return
        self.rev = max(1, int(stored.get("rev") or 1))
        self.alert_id = max(0, int(stored.get("alert_id") or 0))
        if saved_spk := str(stored.get("active_speaker") or "").strip():
            self.active_speaker = saved_spk
        if saved_last := str(stored.get("last_speaker") or "").strip():
            self.last_speaker = saved_last
        if (saved_area := str(stored.get("active_area_id") or "").strip()) and not self.active_area_id:
            self.active_area_id = saved_area
        saved_slot = stored.get("active_remote_slot")
        if isinstance(saved_slot, int) and 1 <= saved_slot <= 10:
            self.active_remote_slot = saved_slot
        if saved_wp := str(stored.get("current_wallpaper") or "").strip():
            self.current_wallpaper = saved_wp
        self.last_media_uri = str(stored.get("last_media_uri") or "")
        self.last_media_type = str(stored.get("last_media_type") or "music")
        self.last_media_title = str(stored.get("last_media_title") or "")
        self.last_media_artist = str(stored.get("last_media_artist") or "")
        self.last_media_album = str(stored.get("last_media_album") or "")
        self.last_media_duration = float(stored.get("last_media_duration") or 0.0)
        self.last_media_position = float(stored.get("last_media_position") or 0.0)
        saved_health = stored.get("last_device_health")
        self.last_device_health = (
            saved_health if isinstance(saved_health, dict) else None
        )
        saved_manifest = stored.get("hello_manifest")
        if isinstance(saved_manifest, dict) and "w" in saved_manifest and "h" in saved_manifest:
            self._runtime.hello_manifest = dict(saved_manifest)
        if saved_boot_id := str(stored.get("last_boot_id") or "").strip():
            self._runtime.last_boot_id = saved_boot_id
        self._entered_hibernate = bool(stored.get("entered_hibernate"))
        self.prefs_seq = max(0, int(stored.get("prefs_seq") or 0))
        raw_key_seq = stored.get("prefs_key_seq")
        if isinstance(raw_key_seq, dict):
            self.prefs_key_seq = {
                str(k): max(0, int(v))
                for k, v in raw_key_seq.items()
                if isinstance(v, (int, float))
            }

    @callback
    def _schedule_persist_runtime_state(self) -> None:
        self._runtime.schedule_save(self._build_persisted_snapshot)

    async def async_flush_runtime_state(self) -> None:
        """Flush persisted runtime state immediately before a Home Assistant backup."""
        await self._runtime.async_flush(self._build_persisted_snapshot())

    @callback
    def _async_on_core_config_update(self, _event: Event) -> None:
        self._url_signer.invalidate_lan_base_url()
        self.hass.async_create_task(
            self._url_signer.async_prime_lan_base_url(),
            f"latter_lan_url_{self.device_slug}",
        )
        self.async_notify_listeners()

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
        self.alert_duration = max(2, min(60, int(duration)))
        self.alert_chime = bool(chime)
        self.alert_camera_url = (
            self.build_camera_snapshot_url(
                camera_entity, cache_bust=f"{self.alert_id}_{int(time.time())}"
            )
            if camera_entity
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
            },
        )
        self._schedule_persist_runtime_state()
        self.async_notify_listeners()

    async def async_setup(self) -> None:
        await self._url_signer.async_prime_lan_base_url()
        self._apply_stored_runtime(await self._runtime.async_load())
        self._structural_snapshot = self._capture_structural_snapshot()
        self._runtime.seed_snapshot(self._build_persisted_snapshot())
        local_spk = self.local_speaker
        if not (
            local_spk
            or esphome_service(self.hass, self.esphome_device_id, "set_browse_slots")
        ):
            self.active_speaker = self.last_speaker = ""
        else:
            if not self.active_speaker:
                self.active_speaker = local_spk
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
            proxy_areas = get_ble_proxy_area_ids(self.hass)
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
            self._schedule_persist_runtime_state()
        self.async_sync_ha_device_areas()
        self._bind_all_listeners()
        self._unsub_core_config = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._async_on_core_config_update
        )
        self._sync_ble_tracker()
        if not self.is_ble_tag:
            self._rpc_receiver.start()
            await self.async_push_beacon_uuid()
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
            else:
                await self.async_refresh_weather_forecast()
                await self.async_refresh_calendar_agenda()
        await self.async_sync_presence_beacon("options")
        try:
            async_audit_coordinator_health(self.hass, self)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Repairs audit skipped: %s", err)

    async def async_apply_options(self) -> None:
        new_conf_wp = str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()
        if new_conf_wp != self._configured_wallpaper_source or (
            self.current_wallpaper
            and self.wallpaper_favorites
            and self.current_wallpaper not in self.wallpaper_favorites
            and self.current_wallpaper != new_conf_wp
        ):
            self._configured_wallpaper_source = self.current_wallpaper = new_conf_wp
            self._schedule_persist_runtime_state()
        self.doorbell_noise_reduction = normalize_noise_reduction(
            self.get_opt(
                CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION
            )
        )
        self._sync_ble_tracker()
        new_ble = self.native_ble_tracking_enabled
        new_def_area = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        ble_changed = new_ble != self._configured_ble_tracking
        area_changed = new_def_area != self._configured_default_area
        if not self.is_ble_tag and (ble_changed or area_changed):
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
                    self.async_set_active_area(
                        new_def_area, sync_device_registry=False
                    )
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
        target_def_spk = (
            str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() or self.local_speaker
        )
        if (
            self.local_speaker
            and target_def_spk
            and self.is_local_speaker_entity(target_def_spk)
        ):
            target_def_spk = self.local_speaker
        if target_def_spk and target_def_spk != self.active_speaker:
            self.last_speaker, self.active_speaker = self.active_speaker, target_def_spk
            self._schedule_persist_runtime_state()
        self._bind_all_listeners()
        self._rpc_receiver.rebind()
        await self.async_push_beacon_uuid()
        await self.async_sync_presence_beacon("options")
        get_ble_fabric(self.hass).notify_occupancy_listeners()
        self.async_notify_listeners()

    async def async_on_global_config_updated(
        self, changed_keys: set[str] | None = None
    ) -> None:
        if self._ble_tracker is not None:
            self._ble_tracker.set_area_offsets(self.ble_area_offsets)
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
    def _bind_link_report_listener(self) -> None:
        if self._unsub_link_report_state is not None:
            self._unsub_link_report_state()
            self._unsub_link_report_state = None
        link_ent = find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "sensor",
            ("_system_link_report",),
        )
        if not link_ent:
            return
        cur_st = self.hass.states.get(link_ent)
        if cur_st is not None and cur_st.state == "hibernating":
            self._entered_hibernate = True
        elif cur_st is not None and cur_st.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            "",
            "hibernating",
        ):
            self._entered_hibernate = False

        @callback
        def _on_link_report_change(event: Event) -> None:
            new_st: State | None = event.data.get("new_state")
            if new_st is None:
                return
            if new_st.state == "hibernating":
                if not self._entered_hibernate:
                    self._entered_hibernate = True
                    self._schedule_persist_runtime_state()
            elif (
                new_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "")
                and self._entered_hibernate
            ):
                self._entered_hibernate = False
                self._schedule_persist_runtime_state()

        self._unsub_link_report_state = async_track_state_change_event(
            self.hass, [link_ent], _on_link_report_change
        )

    @callback
    def _bind_all_listeners(self) -> None:
        if self.is_ble_tag:
            return
        bind_coordinator_speaker_listener(self)
        bind_coordinator_area_listeners(self)
        bind_coordinator_doorbell_listener(self)
        self._bind_link_report_listener()
        self._bind_wallpaper_cycle_timer()

    def resolve_wallpaper_rotation_pool(self) -> list[str]:
        """Return valid starred wallpaper IDs, or the full gallery when none are starred."""
        all_ids = ordered_wallpaper_ids(self.device_slug)
        known = set(all_ids)
        valid_favs = [f for f in self.wallpaper_favorites if f in known]
        return valid_favs if valid_favs else all_ids

    @callback
    def ensure_active_wallpaper_for_rotation(self) -> bool:
        """Seed an active wallpaper from the rotation pool when rotation is enabled."""
        if self.is_ble_tag or self.wallpaper_cycle_minutes <= 0:
            return False
        all_ids = ordered_wallpaper_ids(self.device_slug)
        known = set(all_ids)
        valid_favs = [f for f in self.wallpaper_favorites if f in known]
        pool = valid_favs if valid_favs else all_ids
        if not pool:
            return False
        cur = self.wallpaper_source
        if cur and cur in known and (not valid_favs or cur in valid_favs):
            return False
        picked = pool[0]
        self.current_wallpaper = picked
        self._configured_wallpaper_source = picked
        merged = dict(self.device_data)
        if merged.get(CONF_WALLPAPER_SOURCE) != picked:
            merged[CONF_WALLPAPER_SOURCE] = picked
            self.update_device_config(merged)
        self._schedule_persist_runtime_state()
        return True

    @callback
    def _bind_wallpaper_cycle_timer(self) -> None:
        if self._unsub_wallpaper_timer is not None:
            self._unsub_wallpaper_timer()
            self._unsub_wallpaper_timer = None

        mins = self.wallpaper_cycle_minutes
        if mins <= 0:
            return

        self.ensure_active_wallpaper_for_rotation()
        pool = self.resolve_wallpaper_rotation_pool()
        if self.wallpaper_source and len(pool) >= 2:

            @callback
            def _on_wallpaper_tick(_now: datetime) -> None:
                tick_pool = self.resolve_wallpaper_rotation_pool()
                if len(tick_pool) < 2:
                    return
                cur = self.wallpaper_source
                try:
                    idx = (tick_pool.index(cur) + 1) % len(tick_pool)
                except ValueError:
                    idx = 0
                self.current_wallpaper = tick_pool[idx]
                self._schedule_persist_runtime_state()
                self.async_notify_listeners()

            self._unsub_wallpaper_timer = async_track_time_interval(
                self.hass, _on_wallpaper_tick, timedelta(minutes=mins)
            )

    @callback
    def _sync_ble_tracker(self) -> None:
        if self.native_ble_tracking_enabled:
            if self._ble_tracker is not None:
                if (
                    getattr(
                        self._ble_tracker,
                        "beacon_uuid",
                        self.ble_beacon_uuid,
                    )
                    != self.ble_beacon_uuid
                    or getattr(
                        self._ble_tracker,
                        "target_address",
                        self.ble_target_address,
                    )
                    != self.ble_target_address
                ):
                    self._ble_tracker.async_stop()
                    self._ble_tracker = None
                else:
                    self._ble_tracker.set_area_offsets(self.ble_area_offsets)
            if self._ble_tracker is None:
                self._ble_tracker = LatterNativeBleTracker(
                    hass=self.hass,
                    beacon_uuid=self.ble_beacon_uuid,
                    device_slug=self.device_slug,
                    on_area_detected=self._async_on_native_ble_area_detected,
                    area_offsets=self.ble_area_offsets,
                    target_address=self.ble_target_address,
                    esphome_device_id=self.esphome_device_id,
                    manifest_beacon=self.hardware_manifest.get("beacon"),
                    should_hold_during_ble_sleep=self.is_ble_sleep_expected,
                )
                self._ble_tracker.async_start()
        elif self._ble_tracker is not None:
            self._ble_tracker.async_stop()
            self._ble_tracker = None

    @callback
    def async_cleanup(self) -> None:
        self._notify_debouncer.async_cancel()
        self._area_follow.cancel()
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
            "_unsub_area_entities_state",
            "_unsub_area_debounce",
            "_unsub_wallpaper_timer",
            "_unsub_doorbell_ring_state",
            "_unsub_link_report_state",
            "_unsub_timer_tick",
        ):
            if (unsub := getattr(self, attr, None)) is not None:
                unsub()
                setattr(self, attr, None)

    # -----------------------------------------------------------------------
    # BLE Presence, Handshake, Health Repairs & Area Handoff
    # -----------------------------------------------------------------------

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
            "sdk": health.sdk,
            "reset": health.reset,
            "crash": health.crash,
            "rollback": health.rollback,
            "reported_at": reported_at,
        }
        self._schedule_persist_runtime_state()
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
                config_entry_id=self.entry.entry_id,
            )

    async def _async_handle_reconnect(self) -> None:
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
        await asyncio.sleep(1.5)
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

    async def async_handle_device_hello(
        self,
        contract: int,
        boot_id: str,
        manifest_raw: str,
        prefs_seq: int = 0,
        dirty_prefs: str = "",
    ) -> None:
        _ = contract
        self._entered_hibernate = False
        is_new_boot, parsed = self._runtime.apply_device_hello(boot_id, manifest_raw)
        if parsed is not None:
            if self._ble_tracker is not None:
                self._ble_tracker.update_manifest_beacon(parsed.get("beacon"))
            self._apply_device_health(parsed, str(boot_id or "").strip())
        if is_new_boot:
            self._local_needs_cold_resume = True
            self.handle_timer_alarm_state(False, False, 0, False)

        dev_seq = max(0, int(prefs_seq or 0))
        incoming_prefs = parse_dirty_prefs_records(dirty_prefs)
        ble_tracking_changed = False
        if self.prefs_seq == 0:
            raw_sub = self._live_subentry().data
            seeded = {k: v for k, v in incoming_prefs.items() if k not in raw_sub}
            if seeded:
                cleaned = clean_device_settings(seeded, current=self.device_data)
                if cleaned:
                    merged = {**self.device_data, **cleaned}
                    self.update_device_config(merged, bump_prefs_seq=False)
                    ble_tracking_changed = CONF_NATIVE_BLE_TRACKING in cleaned
            self.prefs_seq = max(
                1, dev_seq + (1 if incoming_prefs and dev_seq > 0 else 0)
            )
            cur_sub = self._live_subentry().data
            for k in (
                *DEVICE_PREF_KEYS,
                CONF_NATIVE_BLE_TRACKING,
                CONF_DEVICE_CUSTOM_COLOR,
            ):
                if k in cur_sub:
                    self.prefs_key_seq.setdefault(k, self.prefs_seq)
        elif dev_seq > 0:
            if incoming_prefs:
                accepted = {
                    k: v
                    for k, v in incoming_prefs.items()
                    if self.prefs_key_seq.get(k, 0) <= dev_seq
                }
                new_seq = max(self.prefs_seq, dev_seq) + 1
                if accepted:
                    cleaned = clean_device_settings(accepted, current=self.device_data)
                    if cleaned:
                        merged = {**self.device_data, **cleaned}
                        self.update_device_config(merged, bump_prefs_seq=False)
                        for k in cleaned:
                            self.prefs_key_seq[k] = new_seq
                        ble_tracking_changed = CONF_NATIVE_BLE_TRACKING in cleaned
                self.prefs_seq = new_seq
            elif dev_seq > self.prefs_seq:
                self.prefs_seq = dev_seq

        if ble_tracking_changed:
            self._sync_ble_tracker()
            get_ble_fabric(self.hass).notify_occupancy_listeners()

        self._cached_prefs_payload = None
        self._schedule_persist_runtime_state()
        self._last_pushed_v3.clear()
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
        cleaned = clean_device_settings(dict(updates), current=self.device_data)
        if not cleaned and not force_bump:
            return {}
        prev_seq = self.prefs_seq
        if cleaned:
            merged = {**self.device_data, **cleaned}
            self.update_device_config(merged, bump_prefs_seq=True)
        if (force_bump and self.prefs_seq == prev_seq) or (
            min_next_seq is not None and self.prefs_seq < min_next_seq
        ):
            target_seq = max(
                self.prefs_seq + (1 if self.prefs_seq == prev_seq else 0),
                min_next_seq or 1,
            )
            self.prefs_seq = max(1, target_seq)
            for k in cleaned:
                self.prefs_key_seq[k] = self.prefs_seq
            self._cached_prefs_payload = None
            self._schedule_persist_runtime_state()
        self._cached_prefs_payload = None
        if CONF_NATIVE_BLE_TRACKING in cleaned:
            await self.async_apply_options()
            self.async_update_listeners()
        else:
            self.async_update_listeners()
            self.async_notify_listeners()
        return cleaned

    async def async_handle_set_device_prefs(
        self, base_seq: int, changes_raw: str
    ) -> None:
        """Apply live touchscreen preference edits and echo canonical `device_prefs` back to clear dirty_mask."""
        incoming = parse_dirty_prefs_records(changes_raw)
        if not incoming:
            return
        await self.async_update_device_prefs(
            incoming,
            min_next_seq=max(self.prefs_seq, max(0, int(base_seq or 0))) + 1,
            force_bump=True,
        )

    @callback
    def _stop_timer_tick(self) -> None:
        if self._unsub_timer_tick is not None:
            self._unsub_timer_tick()
            self._unsub_timer_tick = None

    @callback
    def handle_timer_alarm_state(
        self,
        timer_running: bool,
        timer_paused: bool,
        remaining_sec: int,
        ringing: bool,
    ) -> None:
        """Update event-driven timer and alarm state and manage the local 1 Hz countdown tick."""
        self.timer_running = bool(timer_running)
        self.timer_paused = bool(timer_paused) and not self.timer_running
        self.timer_remaining_sec = max(0, int(remaining_sec or 0))
        self._timer_anchor_mono = time.monotonic()
        self.alarm_ringing = bool(ringing)

        if self.timer_running and self.timer_remaining_sec > 0:
            if self._unsub_timer_tick is None:

                @callback
                def _on_timer_tick(_now: datetime) -> None:
                    if not self.timer_running or self.current_timer_remaining_sec <= 0:
                        self._stop_timer_tick()
                    self.async_update_listeners()

                self._unsub_timer_tick = async_track_time_interval(
                    self.hass, _on_timer_tick, timedelta(seconds=1)
                )
        else:
            self._stop_timer_tick()

        self.async_update_listeners()

    async def async_send_device_command(
        self, command: str, *, raise_if_offline: bool = False
    ) -> bool:
        """Send an immediate action (`restart`, `find_my`, `activate_screensaver`, `trigger_va`, `log_memory_report`) to the Device."""
        cmd = str(command or "").strip().lower()
        if self.is_ble_tag:
            if raise_if_offline:
                raise HomeAssistantError("BLE tags do not accept device commands")
            return False

        wifi_ent_id = find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "sensor",
            ("_wi_fi_signal", "_wifi_signal", "_ip_address"),
        )
        wifi_st = self.hass.states.get(wifi_ent_id) if wifi_ent_id else None
        wifi_offline = wifi_st is not None and wifi_st.state == STATE_UNAVAILABLE
        svc = esphome_service(
            self.hass, self.esphome_device_id, "latter_device_command"
        )

        if not wifi_offline and not self._rpc_receiver.is_device_unavailable():
            if svc:
                try:
                    await self.hass.services.async_call(
                        "esphome", svc, {"command": cmd}, blocking=True
                    )
                    return True
                except Exception as err:
                    if raise_if_offline:
                        raise HomeAssistantError(
                            f"Failed to send '{cmd}' to {self.device_title}: {err}"
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
                f"{self.device_title} is currently offline or sleeping"
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
        )

    @callback
    def async_set_active_speaker(
        self, speaker_entity_id: str, transfer_queue: bool = True
    ) -> None:
        set_coordinator_active_speaker(
            self, speaker_entity_id, transfer_queue=transfer_queue
        )

    def is_device_online(self) -> bool:
        """Return True when the bound ESPHome device has an active Wi-Fi/IP state in Home Assistant."""
        if self.is_ble_tag:
            return False
        wifi_ent_id = find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "sensor",
            ("_wi_fi_signal", "_wifi_signal", "_ip_address"),
        )
        wifi_st = self.hass.states.get(wifi_ent_id) if wifi_ent_id else None
        return bool(
            wifi_st is not None
            and wifi_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "")
        )

    def is_ble_sleep_expected(self) -> bool:
        """Return True when BLE silence is intentional (screen-off light sleep/docked pause or battery hibernate)."""
        if self.is_ble_tag:
            return False
        if self.is_device_online():
            if self._entered_hibernate:
                self._entered_hibernate = False
                self._schedule_persist_runtime_state()
            ble_ent_id = find_device_entity_by_suffix(
                self.hass,
                self.esphome_device_id,
                "binary_sensor",
                ("_ble_radio_active",),
            )
            ble_st = self.hass.states.get(ble_ent_id) if ble_ent_id else None
            return bool(ble_st is not None and ble_st.state == "off")
        return bool(
            self._entered_hibernate
            and int(self.hardware_manifest.get("battery", 0) or 0) == 1
        )

    def is_device_away(self) -> bool:
        if not self.native_ble_tracking_enabled or self._ble_tracker is None:
            return False
        if not self._ble_tracker.is_away:
            return False
        if self.is_ble_tag:
            return True
        if not self.is_device_online():
            return not self.is_ble_sleep_expected()
        ble_ent_id = find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "binary_sensor",
            ("_ble_radio_active",),
        )
        ble_st = self.hass.states.get(ble_ent_id) if ble_ent_id else None
        return bool(ble_st is not None and ble_st.state == "on")

    def _find_latter_device_entry(self) -> dr.DeviceEntry | None:
        dev_reg = dr.async_get(self.hass)
        idents = self.get_device_info()["identifiers"]
        esp_id = self.esphome_device_id
        for d in dr.async_entries_for_config_entry(dev_reg, self.entry.entry_id):
            if (DOMAIN, "system") in d.identifiers:
                continue
            if (d.identifiers & idents) or (esp_id and d.via_device_id == esp_id):
                return d
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
            self._schedule_persist_runtime_state()
            self.async_notify_listeners()
            if not self.is_ble_tag and self.on_area_changed_push_slots is not None:
                self.entry.async_create_background_task(
                    self.hass,
                    self.on_area_changed_push_slots(self),
                    f"latter_area_change_slots_{self.device_slug}",
                )
        else:
            self.async_notify_listeners()

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

    def get_current_area_and_distance(self) -> tuple[str, dict[str, Any]]:
        away = self.is_device_away()
        explicit_default = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        esp_default = ""
        if not self.is_ble_tag and self.esphome_device_id:
            esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
            esp_default = str(esp_dev.area_id or "").strip() if esp_dev else ""
        area_reg = ar.async_get(self.hass)
        if self.native_ble_tracking_enabled:
            ble_area_id = (
                (
                    self._ble_tracker.current_area_id
                    if self._ble_tracker is not None
                    else None
                )
                or self.active_area_id
                or explicit_default
                or esp_default
                if not away
                else None
            )
            area_entry = area_reg.async_get_area(ble_area_id) if ble_area_id else None
            if away:
                area_state = "Away"
            elif area_entry is not None:
                area_state = area_entry.name
            else:
                area_state = "Unassigned"
            eff_area_id = ble_area_id or ""
        else:
            eff_area_id = (
                ""
                if away
                else (self.active_area_id or explicit_default or esp_default)
            )
            area_entry = area_reg.async_get_area(eff_area_id) if eff_area_id else None
            area_state = (
                "Away" if away else (area_entry.name if area_entry else "Unassigned")
            )

        bt = self._ble_tracker
        valid_bt = bt is not None and not away and bool(eff_area_id)
        return area_state, {
            "area_id": eff_area_id,
            "area_name": area_state,
            "is_home": not away,
            "closest_proxy": bt.closest_scanner if (valid_bt and bt) else "",
            "distance_ft": bt.winning_distance_ft if (valid_bt and bt) else None,
            "distance_m": bt.winning_distance_m if (valid_bt and bt) else None,
            "rssi": bt.winning_rssi if (valid_bt and bt) else None,
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
            _LOGGER.info(
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
            self._schedule_persist_runtime_state()
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
            self.async_notify_listeners()

        if self.on_area_changed_push_slots is not None:
            self.entry.async_create_background_task(
                self.hass,
                self.on_area_changed_push_slots(self),
                f"latter_area_change_slots_{self.device_slug}",
            )

    # -----------------------------------------------------------------------
    # Protocol v3 Domain Payloads & Push Transport
    # -----------------------------------------------------------------------

    def _pack_domain_payload(self, domain: str, *fields: Any) -> tuple[int, str]:
        cur_rev, packed = self._packer.pack(domain, *fields)
        self.rev = max(self.rev, self._packer.rev)
        return cur_rev, packed

    async def async_push_beacon_uuid(self) -> None:
        if (
            self.is_ble_tag
            or self._rpc_receiver.is_device_unavailable()
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

    async def async_push_dirty_v3_domains(self) -> None:
        if self.is_ble_tag or not (
            svc := esphome_service(
                self.hass, self.esphome_device_id, "latter_push_v3"
            )
        ):
            return
        if self._rpc_receiver.is_device_unavailable():
            self._last_pushed_v3.clear()
            return
        for dom, payload in (
            ("active_media", str(self.get_active_media_payload()[1].get("payload") or "")),
            ("weather_forecast", str(self.weather_attributes.get("payload") or "")),
            ("area_context", str(self.get_area_context_payload()[1].get("payload") or "")),
            (
                "calendar_agenda",
                str(self.get_calendar_agenda_payload()[1].get("payload") or ""),
            ),
            (
                "remote_config",
                str(self.get_remote_config_payload()[1].get("payload") or ""),
            ),
            (
                "device_prefs",
                str(self.get_device_prefs_payload()[1].get("payload") or ""),
            ),
        ):
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

    @callback
    def force_republish_all_domains(self) -> None:
        self._packer.force_republish_all_domains()
        self.rev = max(self.rev, self._packer.rev)
        self._last_pushed_v3.clear()
        self._cached_media_payload = None
        self._cached_media_anchor = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._cached_prefs_payload = None
        if self.weather_attributes and "condition" in self.weather_attributes:
            wa = self.weather_attributes
            wa["rev"], wa["payload"] = self._pack_domain_payload(
                "weather_forecast",
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
            )
        self.async_update_listeners()
        if not self.is_ble_tag:
            self.entry.async_create_background_task(
                self.hass,
                self.async_push_dirty_v3_domains(),
                f"latter_push_v3_republish_{self.device_slug}",
            )

    async def _async_debounced_notify(self) -> None:
        self.async_update_listeners()
        await self.async_push_dirty_v3_domains()

    @callback
    def async_notify_listeners(self) -> None:
        self._cached_media_payload = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._cached_prefs_payload = None
        self._schedule_persist_runtime_state()
        self._notify_debouncer.async_schedule_call()

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
        )
        cur_rev, packed = self._pack_domain_payload("device_prefs", *fields)
        res = (
            eff_seq,
            {
                "prefs_seq": eff_seq,
                "power_profile": self.get_device_pref("power_profile"),
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

    @property
    def active_area_name(self) -> str:
        area_entry = resolve_active_area_entry(self)
        return area_entry.name if area_entry else "Unassigned"

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
