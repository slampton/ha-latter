"""Core push `LatterCoordinator` orchestrator for one Latter Device or BLE Tag (`L3`)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_state_change_event

from ..areas.sync import sync_esphome_device_area
from ..areas.telemetry import bind_coordinator_area_listeners
from ..const import (
    CONF_CALENDAR_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_ESPHOME_DEVICE_ID,
    CONF_SYSTEM_BLE_UUID,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DEFAULT_DOORBELL_NOISE_REDUCTION,
    DOMAIN,
    normalize_noise_reduction,
)
from ..doorbell import bind_coordinator_doorbell_listener
from ..feeds import init_weather_attributes
from ..http.signing import UrlSigner
from ..hub_registry import get_latter_system, iter_coordinators
from ..identity import (
    esphome_service,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
)
from ..media.playback import (
    bind_coordinator_speaker_listener,
    enforce_local_speaker_if_remote_idle,
)
from ..presence.ble_fabric import get_ble_fabric
from ..presence.ble_registry import get_ble_proxy_area_ids, get_ble_signature_area_ids
from ..presence.ble_tracker_calibration import LatterNativeBleTracker
from ..protocol_codec import DomainPayloadPacker, V3Records
from ..protocol_policy import PinLockoutTracker
from ..protocol_specs import resolve_device_pref_value
from ..repairs import async_audit_coordinator_health
from .area_follow_controller import LatterAreaFollowController
from .ha_registry_sync import match_coordinator_target_generic
from .runtime_store import LatterDeviceRuntime, get_rpc_receiver_factory
from .v3_transport import CoordinatorV3TransportMixin

_LOGGER = logging.getLogger(__name__)

_MAX_REMOTE_SLOTS = 10


def _normalize_hmac_secret(raw: bytes | str) -> bytes:
    if isinstance(raw, bytes):
        return raw
    clean = str(raw).strip()
    try:
        return bytes.fromhex(clean)
    except ValueError:
        return clean.encode("utf-8")


class LatterCoordinator(CoordinatorV3TransportMixin):
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
        self._listeners = {}
        self._timer_tick_listeners = {}
        self._background_tasks = set()
        self.config_lock = asyncio.Lock()
        self.device_config_rev = 1
        self._hmac_secret = secret_bytes
        self._runtime = LatterDeviceRuntime(hass, self.subentry_id)
        self._url_signer = UrlSigner(hass, self.subentry_id, secret_bytes)
        self._packer = DomainPayloadPacker()
        self._area_follow = LatterAreaFollowController(hass)
        self._cached_esphome_device_id = None
        self.rev = 1
        self._notify_debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=0.2,
            immediate=False,
            function=self._async_debounced_notify,
        )
        rpc_factory = get_rpc_receiver_factory()
        self._rpc_receiver = (
            rpc_factory(hass, self) if rpc_factory is not None else None
        )
        self._init_caches_and_timers()
        self._init_telemetry_and_ble()
        self._init_media_state()
        self._init_feeds_and_alerts()
        self._structural_snapshot = self._capture_structural_snapshot()
        self._applied_options_snapshot = self._capture_options_snapshot()

    def _init_caches_and_timers(self) -> None:
        self._cached_media_payload = None
        self._cached_media_anchor = None
        self._cached_area_payload = None
        self._last_ambient_light = ("", None, "")
        self._cached_remote_payload = None
        self._cached_prefs_payload = None
        self._cached_shortcuts_payload = None
        self.prefs_seq = 0
        self.prefs_key_seq = {}
        self.timer_running = False
        self.timer_paused = False
        self.timer_remaining_sec = 0
        self._timer_anchor_mono = 0.0
        self.timer_ends_at_utc = ""
        self.stopwatch_running = False
        self.stopwatch_paused = False
        self.stopwatch_elapsed_sec = 0
        self._stopwatch_anchor_mono = 0.0
        self.stopwatch_started_at_utc = ""
        self.alarm_ringing = False
        self._unsub_timer_tick = None
        self._unsub_core_config = None
        self._unsub_speaker_state = None
        self._tracked_ma_counterpart = None
        self._unsub_alarm_state = None
        self._unsub_remotes_state = None
        self._unsub_shortcuts_state = None
        self._unsub_area_entities_state = None
        self._unsub_area_debounce = None
        self._unsub_wallpaper_timer = None
        self._unsub_screensaver_timer = None
        self._unsub_doorbell_ring_state = None
        self._unsub_link_report_state = None
        self._unsub_ble_radio_state = None
        self._unsub_reconnect_post_delay = None

    def _init_telemetry_and_ble(self) -> None:
        self._entered_hibernate = False
        self._pin_key_id = ""
        self._pin_key_bytes = b""
        self._pin_last_nonce = 0
        self.pin_lockout = PinLockoutTracker()
        self.display_power_state = 0
        self.display_brightness_pct = self._initial_brightness_pct()
        self.device_telemetry = {
            "link": {},
            "int_ram_free_kb": None,
            "int_ram_min_kb": None,
            "int_ram_largest_kb": None,
            "psram_min_kb": None,
            "ble_active": None,
            "profiler_on": False,
            "updated_at": None,
        }
        self._matched_ble_addresses = []
        self._doorbell_ring_map = {}
        self._doorbell_ring_cooldown_until = {}
        self._ble_tracker = None
        self._last_pushed_v3 = {}
        self.active_speaker = (
            str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() or self.local_speaker
        )
        self.last_speaker = self.active_speaker
        self.active_area_id = self.get_opt(CONF_DEFAULT_AREA)
        self.active_remote_slot = 1
        self.last_area_filter = "scene"
        self.last_area_page = 1
        self.on_area_changed_push_slots = None

    def _init_media_state(self) -> None:
        self.last_media_uri = ""
        self.last_media_type = "music"
        self.last_media_title = ""
        self.last_media_artist = ""
        self.last_media_album = ""
        self.last_media_duration = 0.0
        self.last_media_position = 0.0
        self._resuming_guard_until = 0.0
        self._local_needs_cold_resume = True
        self._browsed_album_track_uris = []
        self._lyrics_watch_active = False
        self._last_pushed_lyrics_key = ""
        self._media_favorite_overrides = {}
        self.last_valid_raw_pic = ""
        self._last_art_track_key = ""
        self._last_art_proxy_url = ""
        self._transfer_hold_until = 0.0
        self._transfer_hold_spinup_until = 0.0
        self._transfer_hold_position = 0.0
        self._transfer_hold_title = ""
        self._transfer_hold_artist = ""
        self._transfer_hold_album = ""
        self._transfer_hold_duration = 0.0
        self._transfer_hold_track_key = ""

    def _init_feeds_and_alerts(self) -> None:
        self.forecast_records = V3Records()
        self.weather_attributes = init_weather_attributes(self.pack_domain_payload)
        self.calendar_records = V3Records()
        self.calendar_events = []
        self._last_cal_window = None
        self.alert_id = 0
        self.alert_title = ""
        self.alert_message = ""
        self.alert_priority = "normal"
        self.alert_duration = 8
        self.alert_chime = True
        self.alert_camera_url = ""
        self.alert_camera_entity = ""
        self.active_carousel_camera = ""
        self.doorbell_talk_state = "idle"
        self.last_device_health = None
        self._doorbell_reply_task = None
        self._doorbell_reply_resume_listen = False
        self.doorbell_noise_reduction = normalize_noise_reduction(
            self.get_opt(
                CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION
            )
        )
        self._configured_wallpaper_source = str(
            self.get_opt(CONF_WALLPAPER_SOURCE, "") or ""
        ).strip()
        self._configured_default_area = str(
            self.get_opt(CONF_DEFAULT_AREA, "") or ""
        ).strip()
        self._configured_ble_tracking = self.native_ble_tracking_enabled
        self._last_esp_area = ""
        self._last_latter_area = ""
        self.current_wallpaper = ""
        self.current_screensaver_photo = ""
        self._doorbell_talk_lock = asyncio.Lock()

    def _initial_brightness_pct(self) -> int:
        raw_bri = resolve_device_pref_value(
            self._live_subentry().data, "manual_brightness"
        )
        try:
            return max(1, min(100, round(float(raw_bri))))
        except (TypeError, ValueError):
            return 80

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

    @callback
    def async_add_timer_tick_listener(
        self, tick_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a dedicated 1 Hz timer countdown listener (`LatterTimerRemainingSensor` only)."""
        self._timer_tick_listeners[tick_callback] = None

        @callback
        def _remove() -> None:
            self._timer_tick_listeners.pop(tick_callback, None)

        unsub: Callable[[], None] = _remove
        return unsub

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
        return self._capture_options_snapshot() != self._applied_options_snapshot

    def _build_persisted_snapshot(self) -> dict[str, Any]:
        return {
            "rev": self.rev,
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
            "last_media_position": round(self.last_media_position, 1),
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
        if isinstance(saved_manifest, dict) and "w" in saved_manifest and "h" in saved_manifest:
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
        local_spk = self.local_speaker
        if not (
            local_spk
            or esphome_service(self.hass, self.esphome_device_id, "latter_set_slots")
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
            self.schedule_persist_runtime_state()
        self._bind_all_listeners()
        if self._rpc_receiver is not None:
            self._rpc_receiver.rebind()
        await self.async_push_beacon_uuid()
        await self.async_sync_presence_beacon("options")
        self._applied_options_snapshot = self._capture_options_snapshot()
        get_ble_fabric(self.hass).notify_occupancy_listeners()
        self.async_notify_listeners()

    async def async_on_global_config_updated(
        self, changed_keys: set[str] | None = None
    ) -> None:
        """Refresh BLE spatial engine, listeners, and shared feeds after a System config save."""
        if self._ble_tracker is not None:
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
        def _on_link_report_change(event: Event[Any]) -> None:
            new_st: State | None = event.data.get("new_state")
            if new_st is None:
                return
            if new_st.state == "hibernating":
                if not self._entered_hibernate:
                    self._entered_hibernate = True
                    self.schedule_persist_runtime_state()
            elif (
                new_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "")
                and self._entered_hibernate
            ):
                self._entered_hibernate = False
                self.schedule_persist_runtime_state()

        self._unsub_link_report_state = async_track_state_change_event(
            self.hass, [link_ent], _on_link_report_change
        )

    @callback
    def _bind_ble_radio_listener(self) -> None:
        if self._unsub_ble_radio_state is not None:
            self._unsub_ble_radio_state()
            self._unsub_ble_radio_state = None
        ble_ent = find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "binary_sensor",
            ("_ble_radio_active",),
        )
        if not ble_ent:
            return

        @callback
        def _on_ble_radio_change(event: Event[Any]) -> None:
            old_st: State | None = event.data.get("old_state")
            new_st: State | None = event.data.get("new_state")
            if new_st is None or (old_st is not None and new_st.state == old_st.state):
                return
            if new_st.state == "on" and self._ble_tracker is not None:
                self._ble_tracker.note_ble_radio_active(time.monotonic())
            self.async_notify_listeners()

        self._unsub_ble_radio_state = async_track_state_change_event(
            self.hass, [ble_ent], _on_ble_radio_change
        )

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
        self._bind_link_report_listener()
        self._bind_ble_radio_listener()
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
            )
            self._ble_tracker.async_start()

    @callback
    def async_cleanup(self) -> None:
        """Cancel all debouncers, background tasks, BLE trackers, and state listeners."""
        self._notify_debouncer.async_cancel()
        self.cancel_background_tasks()
        self._area_follow.cancel()
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
            "_unsub_link_report_state",
            "_unsub_ble_radio_state",
            "_unsub_reconnect_post_delay",
            "_unsub_timer_tick",
        ):
            if (unsub := getattr(self, attr, None)) is not None:
                unsub()
                setattr(self, attr, None)


def match_coordinator_target(
    hass: HomeAssistant,
    coords: Sequence[LatterCoordinator],
    target: str | None,
) -> LatterCoordinator | None:
    """Match a loaded `LatterCoordinator` by `subentry_id`, `device_id`, or exact slug."""
    return match_coordinator_target_generic(hass, coords, target)


def resolve_coordinator(
    hass: HomeAssistant, target: str | None = None
) -> LatterCoordinator | None:
    """Resolve a loaded `LatterCoordinator` by `subentry_id`, `device_id`, or exact slug."""
    coords: list[LatterCoordinator] = list(iter_coordinators(hass))
    return match_coordinator_target_generic(hass, coords, target)
