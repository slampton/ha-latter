"""Per-Device persisted runtime store and typed coordinator state base (`L3`)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import date
import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.storage import Store

from ..const import STORAGE_KEY_PREFIX, STORAGE_VERSION

if TYPE_CHECKING:
    from ..http.signing import UrlSigner
    from ..presence.ble_tracker_calibration import LatterNativeBleTracker
    from ..protocol_codec import DomainPayloadPacker, V3Records
    from ..protocol_policy import PinLockoutTracker

_LOGGER = logging.getLogger(__name__)

_UNSET: Any = object()

_RPC_RECEIVER_FACTORY: Callable[[HomeAssistant, Any], Any] | None = None


def register_rpc_receiver_factory(
    factory: Callable[[HomeAssistant, Any], Any],
) -> None:
    """Register the `LatterRpcReceiver` constructor from `services.rpc_receiver` (acyclic hook)."""
    global _RPC_RECEIVER_FACTORY
    _RPC_RECEIVER_FACTORY = factory


def get_rpc_receiver_factory() -> Callable[[HomeAssistant, Any], Any] | None:
    """Return the registered `LatterRpcReceiver` factory, if loaded."""
    return _RPC_RECEIVER_FACTORY


class LatterDeviceRuntime:
    """Manages change-gated `.storage/latter.runtime.<entry_id>` persistence and `device_hello` state."""

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
        """Parse `device_hello` handshake and return `(is_new_boot, parsed_manifest_or_none)`."""
        parsed_manifest: dict[str, Any] | None = None
        if manifest_raw and manifest_raw.strip().startswith("{"):
            try:
                parsed = json.loads(manifest_raw)
                if isinstance(parsed, dict) and (
                    ("w" in parsed and "h" in parsed) or "sdk" in parsed
                ):
                    self.hello_manifest = parsed
                    parsed_manifest = parsed
            except (ValueError, TypeError):
                pass

        clean_boot_id = str(boot_id or "").strip()
        is_new_boot = bool(clean_boot_id and clean_boot_id != self.last_boot_id)
        if clean_boot_id:
            self.last_boot_id = clean_boot_id
        return is_new_boot, parsed_manifest


class CoordinatorStateBase:
    """Typed state container and public mutator surface shared across coordinator mixins."""

    hass: HomeAssistant
    entry: ConfigEntry[Any]
    config_entry: ConfigEntry[Any]
    subentry: ConfigSubentry
    subentry_id: str
    name: str
    _listeners: dict[Callable[[], None], None]
    _timer_tick_listeners: dict[Callable[[], None], None]
    _background_tasks: set[asyncio.Task[Any]]
    config_lock: asyncio.Lock
    device_config_rev: int
    _hmac_secret: bytes
    _runtime: LatterDeviceRuntime
    _url_signer: UrlSigner
    _packer: DomainPayloadPacker
    _cached_esphome_device_id: str | None
    rev: int
    _notify_debouncer: Debouncer[Coroutine[Any, Any, None]]
    _rpc_receiver: Any

    _cached_media_payload: tuple[float, tuple[str | None, dict[str, Any]]] | None
    _cached_media_anchor: tuple[tuple[Any, ...], float] | None
    _cached_area_payload: tuple[float, tuple[str, dict[str, Any]]] | None
    _last_ambient_light: tuple[str, int | None, str]
    _cached_remote_payload: tuple[float, tuple[str | None, dict[str, Any]]] | None
    _cached_prefs_payload: tuple[int, dict[str, Any]] | None
    _cached_shortcuts_payload: tuple[int, tuple[str, ...]] | None

    prefs_seq: int
    prefs_key_seq: dict[str, int]
    timer_running: bool
    timer_paused: bool
    timer_remaining_sec: int
    _timer_anchor_mono: float
    timer_ends_at_utc: str
    stopwatch_running: bool
    stopwatch_paused: bool
    stopwatch_elapsed_sec: int
    _stopwatch_anchor_mono: float
    stopwatch_started_at_utc: str
    alarm_ringing: bool

    _unsub_timer_tick: Callable[[], None] | None
    _unsub_core_config: Callable[[], None] | None
    _unsub_speaker_state: Callable[[], None] | None
    _tracked_ma_counterpart: str | None
    _unsub_alarm_state: Callable[[], None] | None
    _unsub_remotes_state: Callable[[], None] | None
    _unsub_shortcuts_state: Callable[[], None] | None
    _unsub_area_entities_state: Callable[[], None] | None
    _unsub_area_debounce: Callable[[], None] | None
    _unsub_wallpaper_timer: Callable[[], None] | None
    _unsub_screensaver_timer: Callable[[], None] | None
    _unsub_doorbell_ring_state: Callable[[], None] | None
    _unsub_link_report_state: Callable[[], None] | None
    _unsub_ble_radio_state: Callable[[], None] | None
    _unsub_reconnect_post_delay: Callable[[], None] | None

    _entered_hibernate: bool
    _pin_key_id: str
    _pin_key_bytes: bytes
    _pin_last_nonce: int
    pin_lockout: PinLockoutTracker
    display_power_state: int
    display_brightness_pct: int
    device_telemetry: dict[str, Any]
    _matched_ble_addresses: list[str]
    _doorbell_ring_map: dict[str, str]
    _doorbell_ring_cooldown_until: dict[str, float]
    _ble_tracker: LatterNativeBleTracker | None
    _last_pushed_v3: dict[str, str]

    active_speaker: str
    last_speaker: str
    active_area_id: str | None
    active_remote_slot: int
    last_area_filter: str
    last_area_page: int
    on_area_changed_push_slots: Callable[[Any], Any] | None

    last_media_uri: str
    last_media_type: str
    last_media_title: str
    last_media_artist: str
    last_media_album: str
    last_media_duration: float
    last_media_position: float
    _resuming_guard_until: float
    _local_needs_cold_resume: bool
    _browsed_album_track_uris: list[str]
    _lyrics_watch_active: bool
    _last_pushed_lyrics_key: str
    _media_favorite_overrides: dict[str, tuple[bool, bool | None]]
    last_valid_raw_pic: str
    _last_art_track_key: str
    _last_art_proxy_url: str
    _transfer_hold_until: float
    _transfer_hold_spinup_until: float
    _transfer_hold_position: float
    _transfer_hold_title: str
    _transfer_hold_artist: str
    _transfer_hold_album: str
    _transfer_hold_duration: float
    _transfer_hold_track_key: str

    forecast_records: V3Records
    weather_attributes: dict[str, Any]
    calendar_records: V3Records
    calendar_events: list[dict[str, Any]]
    _last_cal_window: tuple[date, date] | None

    alert_id: int
    alert_title: str
    alert_message: str
    alert_priority: str
    alert_duration: int
    alert_chime: bool
    alert_camera_url: str
    alert_camera_entity: str
    active_carousel_camera: str
    doorbell_talk_state: str
    last_device_health: dict[str, Any] | None
    _doorbell_reply_task: asyncio.Task[Any] | None
    _doorbell_reply_resume_listen: bool
    doorbell_noise_reduction: str
    _configured_wallpaper_source: str
    _configured_default_area: str
    _configured_ble_tracking: bool
    _last_esp_area: str
    _last_latter_area: str
    current_wallpaper: str
    current_screensaver_photo: str
    _doorbell_talk_lock: asyncio.Lock
    _structural_snapshot: dict[str, Any]
    _applied_options_snapshot: dict[str, Any]

    def _live_subentry(self) -> ConfigSubentry:
        live_sub = self.entry.subentries.get(self.subentry_id)
        if live_sub is not None:
            self.subentry = live_sub
        return self.subentry

    def _build_persisted_snapshot(self) -> dict[str, Any]:
        raise NotImplementedError

    def _capture_options_snapshot(self) -> dict[str, Any]:
        raise NotImplementedError

    @callback
    def schedule_persist_runtime_state(self) -> None:
        """Schedule change-gated persistence of the Device runtime snapshot."""
        self._runtime.schedule_save(self._build_persisted_snapshot)

    @callback
    def _schedule_persist_runtime_state(self) -> None:
        self.schedule_persist_runtime_state()

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
    def async_update_listeners(self) -> None:
        """Notify all registered push listeners."""
        for cb in list(self._listeners):
            cb()

    @callback
    def _notify_timer_tick_listeners(self) -> None:
        """Notify dedicated 1 Hz timer countdown listeners."""
        for cb in list(self._timer_tick_listeners):
            cb()

    @callback
    def async_notify_listeners(self) -> None:
        raise NotImplementedError

    @callback
    def schedule_debounced_notify(self) -> None:
        raise NotImplementedError

    def is_device_away(self) -> bool:
        raise NotImplementedError

    def get_remote_slots(self) -> list[dict[str, str]]:
        raise NotImplementedError

    @callback
    def async_set_active_speaker(
        self, speaker_entity_id: str, transfer_queue: bool = True
    ) -> None:
        raise NotImplementedError

    @callback
    def force_republish_all_domains(self) -> None:
        raise NotImplementedError

    async def async_push_beacon_uuid(self) -> None:
        raise NotImplementedError

    @callback
    def sync_ble_tracker(self) -> None:
        raise NotImplementedError

    @callback
    def _bind_link_report_listener(self) -> None:
        raise NotImplementedError

    @callback
    def _bind_ble_radio_listener(self) -> None:
        raise NotImplementedError

    async def async_apply_options(self) -> None:
        raise NotImplementedError

    # -----------------------------------------------------------------------
    # Public Typed Runtime State Properties & Listener Slot Mutators (`M-P1-19`)
    # -----------------------------------------------------------------------

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
