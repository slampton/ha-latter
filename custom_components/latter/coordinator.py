"""State coordinator for one Latter device (Home Assistant side of Protocol v3)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_CORE_CONFIG_UPDATE,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .activity_policy import activity_payload, normalize_activity_sources
from .area_controller import (
    LatterAreaFollowController,
    compute_current_area_and_distance,
    compute_is_device_away,
    resolve_effective_remote_entities,
)
from .area_engine import (
    find_area_media_entities,
    get_area_available_domains,
    get_area_climate_telemetry,
    get_area_entities,
    get_home_alarm_summary,
    get_whole_home_summary,
    match_area_by_name_or_id,
    resolve_entity_area_id,
    resolve_remote_slot_pair,
)
from .ble_engine import (
    LatterNativeBleTracker,
    get_ble_fabric,
    get_ble_proxy_area_ids,
)
from .const import (
    CALENDAR_REFRESH_INTERVAL_MINUTES,
    CONF_ALARM_ENTITY,
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
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_DOCK_APPS,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_ESPHOME_DEVICE_ID,
    CONF_GARAGE_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_THERMOSTAT_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DEFAULT_AREA_FOLLOW_DWELL_S,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_ACTIVITY_CARD,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_DOCK_APPS,
    DEFAULT_DOORBELL_NOISE_REDUCTION,
    DEFAULT_NATIVE_BLE_TRACKING,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SITE_ID,
    DEFAULT_SYNC_DEVICE_AREA,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DOMAIN,
    EVENT_LATTER,
    FORECAST_REFRESH_INTERVAL_MINUTES,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    SUBENTRY_BLE_TAG,
    normalize_device_slug,
    normalize_noise_reduction,
)
from .device_runtime import LatterDeviceRuntime
from .health import (
    ISSUE_ROLLED_BACK,
    evaluate_device_health,
    parse_device_health,
)
from .identity import (
    esphome_service,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    read_device_hardware_manifest,
    resolve_bound_esphome_device_id,
)
from .media_controller import (
    VOLUME_FEATURE_FLAGS,
    async_execute_ma_queue_transfer,
    async_resume_idle_speaker_queue,
    read_volume_from_target,
)
from .issue_ids import device_health_issue_id
from .media_engine import (
    async_play_media_with_ma_fallback,
    interpolate_speaker_position as _interpolate_speaker_position,
    resolve_esphome_local_speaker as _resolve_esphome_local_speaker,
    resolve_ma_counterpart_entity as _resolve_ma_counterpart_entity,
)
from .payloads import (
    CAMERAS_MAX_RECORDS,
    DomainPayloadPacker,
    V3Records,
    camera_records,
    ha_value,
    intercom_target_records,
    remote_slot_records,
)
from .presence_beacon import Trigger, decide_beacon_action
from .site_feeds import async_fetch_calendar_snapshot, async_fetch_weather_snapshot
from .targets import other_latter_devices
from .traits import manifest_has_display, manifest_is_roaming, manifest_is_wearable
from .url_signer import UrlSigner

_LOGGER = logging.getLogger(__name__)

TRANSFER_HOLD_WINDOW_SECONDS = 4.5


def _get_esphome_device_current_area(
    hass: HomeAssistant, esphome_device_id: str | None
) -> str | None:
    """Return the current area_id assigned to the bound ESPHome device in HA Device Registry."""
    dev = get_bound_esphome_device(hass, esphome_device_id)
    return dev.area_id if dev and dev.area_id else None


def resolve_coordinator(
    hass: HomeAssistant,
    target: str | None = None,
) -> LatterCoordinator | None:
    """Resolve a loaded LatterCoordinator by subentry_id, Latter or ESPHome device_id, or the Device's own slug (exact)."""
    from .system import get_latter_system

    domain_data = hass.data.get(DOMAIN, {})
    sys_obj = get_latter_system(hass)
    coords = (
        list(sys_obj.coordinators.values())
        if sys_obj and sys_obj.coordinators
        else [v for v in domain_data.values() if isinstance(v, LatterCoordinator)]
    )
    if not coords:
        return None
    if not target or not str(target).strip():
        return coords[0] if len(coords) == 1 else None

    raw = str(target).strip()
    norm = normalize_device_slug(raw)
    dev_reg = dr.async_get(hass)
    target_dev = dev_reg.async_get(raw)

    for coord in coords:
        if (
            coord.subentry_id == raw
            or coord.device_slug == norm
            or (coord.esphome_device_id and coord.esphome_device_id == raw)
        ):
            return coord
        if target_dev is not None:
            mac = coord.device_mac
            if (
                (DOMAIN, coord.subentry_id) in target_dev.identifiers
                or (mac and (DOMAIN, dr.format_mac(mac)) in target_dev.identifiers)
            ):
                return coord
            if (
                target_dev.via_device_id
                and coord.esphome_device_id
                and target_dev.via_device_id == coord.esphome_device_id
            ):
                return coord
    return None


def resolve_person_area_and_distance(
    hass: HomeAssistant, person_entity: str
) -> tuple[str, dict[str, Any]]:
    """Resolve the freshest area and BLE distance across all Latter devices carried by a person."""
    domain_data = hass.data.get(DOMAIN, {})
    target_low = str(person_entity or "").strip().lower()
    p_coords = [
        v
        for v in domain_data.values()
        if isinstance(v, LatterCoordinator)
        and v.assigned_person.lower() == target_low
    ]
    if not p_coords:
        return "Unassigned", {
            "person_entity": person_entity,
            "area_id": "",
            "area_name": "Unassigned",
            "is_home": False,
            "distance_ft": None,
            "distance_m": None,
            "closest_proxy": "",
            "source_device": "",
        }
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


class LatterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages active speaker, BLE area context, 4-slot remotes, wallpapers, alarm, calendar, and weather."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hmac_secret: bytes,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the Latter coordinator for one Device subentry."""
        self.entry = entry
        self.subentry = subentry
        self.subentry_id: str = subentry.subentry_id
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.subentry_id}",
            config_entry=entry,
        )
        self._hmac_secret = hmac_secret
        self._runtime = LatterDeviceRuntime(hass, self.subentry_id)
        self._store = self._runtime.store
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
        self._cached_media_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._cached_media_anchor: tuple[tuple[Any, ...], float] | None = None
        self._cached_area_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._cached_remote_payload: tuple[float, tuple[str, dict[str, Any]]] | None = None
        self._unsub_core_config: Callable[[], None] | None = None
        self._unsub_speaker_state: Callable[[], None] | None = None
        self._unsub_weather_state: Callable[[], None] | None = None
        self._unsub_alarm_state: Callable[[], None] | None = None
        self._unsub_remotes_state: Callable[[], None] | None = None
        self._unsub_area_entities_state: Callable[[], None] | None = None
        self._unsub_area_debounce: Callable[[], None] | None = None
        self._unsub_forecast_timer: Callable[[], None] | None = None
        self._unsub_calendar_timer: Callable[[], None] | None = None
        self._unsub_wallpaper_timer: Callable[[], None] | None = None
        self._unsub_doorbell_ring_state: Callable[[], None] | None = None
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
        self._last_art_proxy_url: str = ""
        self._transfer_hold_until: float = 0.0
        self._transfer_hold_position: float = 0.0
        self._transfer_hold_title: str = ""
        self._transfer_hold_artist: str = ""
        self._transfer_hold_album: str = ""
        self._transfer_hold_duration: float = 0.0

        # Cached weather forecast state & attributes
        init_w_rev, init_w_payload = self._pack_domain_payload(
            "weather_forecast",
            "",
            None,
            None,
            None,
            None,
            None,
            None,
            V3Records(),
        )
        self.forecast_records: V3Records = V3Records()
        self.weather_attributes: dict[str, Any] = {
            "condition": "",
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "wind_bearing": None,
            "high": None,
            "low": None,
            "rev": init_w_rev,
            "payload": init_w_payload,
        }

        # Cached calendar agenda state & attributes
        self.calendar_records: V3Records = V3Records()
        self.calendar_events: list[dict[str, Any]] = []

        # Smart Device Notification & Camera Peephole Alert State
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
        self._doorbell_reply_task: asyncio.Task[None] | None = None
        self._doorbell_reply_resume_listen: bool = False
        self.doorbell_noise_reduction: str = normalize_noise_reduction(
            self.get_opt(CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION)
        )
        self._configured_wallpaper_source: str = str(
            self.get_opt(CONF_WALLPAPER_SOURCE, "") or ""
        ).strip()
        self.current_wallpaper: str = ""
        self._structural_snapshot: dict[str, Any] = self._capture_structural_snapshot()

    @property
    def epoch(self) -> int:
        """Return the current 31-bit Protocol v3 session epoch."""
        return self._packer.epoch

    @property
    def last_area_follow_write(self) -> dict[str, Any] | None:
        """Return diagnostics record of the most recent Voice Follows Me area write."""
        return self._area_follow.last_area_follow_write

    def _capture_structural_snapshot(self) -> dict[str, Any]:
        """Capture a snapshot of structural config keys that require an entry reload when changed."""
        return {
            CONF_DEVICE_SLUG: self.device_slug,
            CONF_ESPHOME_DEVICE_ID: str(self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or "").strip(),
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

        self.doorbell_noise_reduction = normalize_noise_reduction(
            self.get_opt(CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION)
        )
        if self.native_ble_tracking_enabled:
            if self._ble_tracker is not None:
                if (
                    getattr(self._ble_tracker, "beacon_uuid", self.ble_beacon_uuid) != self.ble_beacon_uuid
                    or getattr(self._ble_tracker, "target_address", self.ble_target_address) != self.ble_target_address
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
                )
                self._ble_tracker.async_start()
        elif self._ble_tracker is not None:
            self._ble_tracker.async_stop()
            self._ble_tracker = None

        conf_def_spk = str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip()
        target_def_spk = conf_def_spk or self.local_speaker
        if (
            self.local_speaker
            and target_def_spk
            and self.is_local_speaker_entity(target_def_spk)
        ):
            target_def_spk = self.local_speaker
        if target_def_spk and target_def_spk != self.active_speaker:
            self.last_speaker = self.active_speaker
            self.active_speaker = target_def_spk
            self._schedule_persist_runtime_state()

        self._bind_all_listeners()
        await self.async_sync_presence_beacon("options")
        get_ble_fabric(self.hass).notify_occupancy_listeners()
        self.async_notify_listeners()

    async def async_sync_presence_beacon(self, trigger: Trigger) -> None:
        """Turn the bound device's BLE presence beacon switch on or off per `presence_beacon.decide_beacon_action`.

        The switch is found only on the bound ESPHome device. BLE tags and devices without a
        beacon switch are left alone.
        """
        if self.is_ble_tag:
            return
        switch_ent = self.device_entity(
            "switch", "_area_ble_presence_beacon", "_ble_presence_beacon"
        )
        if not switch_ent:
            return
        state = self.hass.states.get(switch_ent)
        action = decide_beacon_action(
            self.native_ble_tracking_enabled,
            state.state if state is not None else None,
            trigger,
        )
        if action is None:
            return
        try:
            await self.hass.services.async_call(
                "switch", action, {ATTR_ENTITY_ID: switch_ent}, blocking=True
            )
            _LOGGER.info(
                "Presence beacon of '%s': %s (%s, native BLE tracking %s)",
                self.device_slug,
                action,
                trigger,
                "on" if self.native_ble_tracking_enabled else "off",
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Couldn't %s the presence beacon of '%s': %s",
                action.replace("_", " "),
                self.device_slug,
                err,
            )

    def _live_subentry(self) -> ConfigSubentry:
        """Return the current ConfigSubentry object for this Device (subentries are replaced on update)."""
        live_sub = self.entry.subentries.get(self.subentry_id)
        if live_sub is not None:
            self.subentry = live_sub
        return self.subentry

    @property
    def device_data(self) -> dict[str, Any]:
        """Return a mutable copy of this device's persisted configuration dictionary."""
        return dict(self._live_subentry().data)

    def update_device_config(self, merged_data: dict[str, Any]) -> None:
        """Persist updated device settings to the Device's ConfigSubentry."""
        self.hass.config_entries.async_update_subentry(
            self.entry, self._live_subentry(), data=merged_data
        )
        self._live_subentry()

    def get_opt(self, key: str, default: Any = None) -> Any:
        """Retrieve a setting, prioritizing System-Wide config for shared keys and subentry/entry data for device keys."""
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
        if key in GLOBAL_CONFIG_KEYS:
            if isinstance(global_cfg, dict) and key in global_cfg:
                val = global_cfg[key]
                if val is not None:
                    return val
            return default
        sub_data = self._live_subentry().data
        if key in sub_data:
            return sub_data[key]
        if isinstance(global_cfg, dict) and key in global_cfg:
            return global_cfg[key]
        return default

    async def async_on_global_config_updated(
        self, changed_keys: set[str] | None = None
    ) -> None:
        """Refresh listeners, BLE offsets, weather, and calendar when System-Wide config changes."""
        if self._ble_tracker is not None:
            self._ble_tracker.set_area_offsets(self.ble_area_offsets)
        self._bind_all_listeners()
        if not self.is_ble_tag:
            if changed_keys is None or CONF_WEATHER_ENTITY in changed_keys:
                await self.async_refresh_weather_forecast()
            if changed_keys is None or CONF_CALENDAR_ENTITIES in changed_keys:
                await self.async_refresh_calendar_agenda()
        self.async_notify_listeners()

    @property
    def device_slug(self) -> str:
        """Return the Device's slug as stored in its subentry (set once at onboarding)."""
        return normalize_device_slug(
            str(self._live_subentry().data.get(CONF_DEVICE_SLUG) or "")
        )

    @property
    def device_mac(self) -> str | None:
        """Return the MAC stored for this Device at onboarding, else the bound ESPHome device's MAC connection."""
        stored_mac = str(self.get_opt("mac", "") or "").strip()
        if stored_mac:
            return dr.format_mac(stored_mac)
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        if esp_dev is not None:
            for ctype, cval in esp_dev.connections:
                if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                    return dr.format_mac(str(cval))
        ble_addr = str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()
        if len(ble_addr) == 17 and ble_addr.count(":") == 5:
            return dr.format_mac(ble_addr)
        return None

    @property
    def device_title(self) -> str:
        """Return the friendly device title from the ConfigSubentry or formatted slug."""
        if self._live_subentry().title:
            return self.subentry.title
        return self.device_slug.replace("_", " ").title()

    @property
    def esphome_device_id(self) -> str | None:
        """Return the bound ESPHome device ID: the stored ID, else the ESPHome device carrying the stored MAC."""
        dev_reg = dr.async_get(self.hass)
        if (
            self._cached_esphome_device_id
            and dev_reg.async_get(self._cached_esphome_device_id) is not None
        ):
            return self._cached_esphome_device_id
        stored = str(self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or "").strip()
        stored_mac = str(self.get_opt("mac", "") or "").strip()
        resolved = resolve_bound_esphome_device_id(self.hass, stored or None, stored_mac or None)
        self._cached_esphome_device_id = resolved
        return resolved

    def device_entity(self, domain: str, *suffixes: str) -> str | None:
        """Return the bound ESPHome device's enabled domain entity whose entity_id ends with the first matching suffix."""
        return find_device_entity_by_suffix(
            self.hass, self.esphome_device_id, domain, suffixes
        )

    def device_state(self, domain: str, *suffixes: str) -> State | None:
        """Return the state of device_entity(domain, *suffixes), or None."""
        ent_id = self.device_entity(domain, *suffixes)
        return self.hass.states.get(ent_id) if ent_id else None

    def get_device_info(self) -> DeviceInfo:
        """Return canonical Latter DeviceInfo keyed by MAC (or subentry_id) and linked via via_device_id to ESPHome."""
        esp_dev_id = self.esphome_device_id
        mac = self.device_mac
        ident_key = dr.format_mac(mac) if mac else self.subentry_id
        return DeviceInfo(
            identifiers={(DOMAIN, ident_key)},
            name=self.device_title,
            manufacturer="Lampton Labs",
            model="Latter ESPHome Companion Middleware",
            sw_version=INTEGRATION_VERSION,
            # Visit opens this Device in Latter Studio
            configuration_url=f"homeassistant://latter/devices/{self.subentry_id}",
            **({"via_device_id": esp_dev_id} if esp_dev_id else {}),
        )

    @property
    def site_id(self) -> str:
        """Return the logical site identifier for this device (defaults to 'primary' for single-site homes)."""
        return str(self.get_opt(CONF_SITE_ID, DEFAULT_SITE_ID) or DEFAULT_SITE_ID).strip()

    def _read_device_hardware_manifest(self) -> dict[str, Any]:
        """Read compile-time hardware capability manifest reported by the bound ESPHome device."""
        return read_device_hardware_manifest(
            self.hass,
            self.esphome_device_id,
            cached_manifest=self._runtime.hello_manifest,
        )

    @property
    def hardware_manifest(self) -> dict[str, Any]:
        """Return parsed hardware capability manifest from the ESPHome device (or empty dict if offline)."""
        return self._read_device_hardware_manifest()

    @property
    def is_ble_tag(self) -> bool:
        """Return True for a Studio-adopted BLE tag (phone, watch, tag) rather than an ESPHome Latter device."""
        return self.subentry.subentry_type == SUBENTRY_BLE_TAG

    @property
    def has_display(self) -> bool:
        """Return False only for an ESPHome device whose manifest reports `display == 0` (headless node)."""
        return not self.is_ble_tag and manifest_has_display(self.hardware_manifest)

    @property
    def is_wearable(self) -> bool:
        """Return True when the hardware manifest reports `wearable == 1`."""
        return manifest_is_wearable(self.hardware_manifest)

    @property
    def device_group(self) -> str:
        """Return logical device group ID (defaults to 'unassigned' so no profile is assumed)."""
        raw = str(self.get_opt(CONF_DEVICE_GROUP, DEFAULT_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP).strip()
        if raw == "handhelds" and not self.has_display:
            return DEFAULT_DEVICE_GROUP
        return raw

    @property
    def display_shape(self) -> str:
        """Return display geometry ('circle' or 'square') from the hardware manifest (the default until it reports)."""
        hw_shape = str(self._read_device_hardware_manifest().get("shape") or "").strip().lower()
        return hw_shape if hw_shape in ("circle", "square") else DEFAULT_DISPLAY_SHAPE

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
    def activity_card_enabled(self) -> bool:
        """Return whether the Home Activity Card is switched on."""
        return bool(self.get_opt(CONF_ACTIVITY_CARD, DEFAULT_ACTIVITY_CARD))

    @property
    def activity_sources_csv(self) -> str:
        """Return the Activity Card sources that are on, as canonical CSV ("" = every source off)."""
        try:
            return normalize_activity_sources(self.get_opt(CONF_ACTIVITY_SOURCES, DEFAULT_ACTIVITY_SOURCES))
        except ValueError:
            return DEFAULT_ACTIVITY_SOURCES

    @property
    def wallpaper_source(self) -> str:
        """Return the active runtime wallpaper, else the configured one (a `preset:` ID or an `upload:` ID)."""
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
        """Automatically resolve the on-device media_player entity from the bound ESPHome device."""
        return _resolve_esphome_local_speaker(self.hass, self.esphome_device_id)

    @property
    def local_ma_speaker(self) -> str:
        """Return the Music Assistant Sendspin media_player entity corresponding to this device's local speaker."""
        local_spk = self.local_speaker
        return (
            _resolve_ma_counterpart_entity(
                self.hass, local_spk
            )
            or ""
        )

    def is_local_speaker_entity(self, speaker_entity_id: str | None) -> bool:
        """Return True if speaker_entity_id is this device's ESPHome speaker or its Music Assistant Sendspin counterpart."""
        spk = str(speaker_entity_id or "").strip()
        if not spk:
            return False
        local_spk = self.local_speaker
        if local_spk and spk == local_spk:
            return True
        local_ma = self.local_ma_speaker
        return bool(local_ma and spk == local_ma)

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
        """Return the configured list of up to 10 camera entity_ids."""
        cleaned: list[str] = []
        raw_list = self.get_opt(CONF_CAMERA_ENTITIES)
        if isinstance(raw_list, list):
            cleaned = [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
        if not cleaned:
            single = str(self.get_opt(CONF_CAMERA_ENTITY) or "").strip()
            if single:
                cleaned = [single]
        return cleaned[:10]

    def _build_intercom_targets_summary(self) -> V3Records:
        """Records of what this Device can ring with call_target: all other Latter Devices, then each by title."""
        others = other_latter_devices(self.hass.data.get(DOMAIN, {}).values(), self.device_slug)
        others.sort(key=lambda c: (c.device_title.lower(), c.device_slug))
        targets: list[dict[str, str]] = (
            [{"target_id": "all", "label": "All Devices", "kind": "all"}] if others else []
        )
        targets += [
            {"target_id": c.device_slug, "label": c.device_title, "kind": "device"} for c in others
        ]
        return intercom_target_records(targets)

    @property
    def camera_entity(self) -> str | None:
        """Return configured primary doorbell/security camera entity_id (Slot 1)."""
        cams = self.camera_entities
        if cams:
            return cams[0]
        val = self.get_opt(CONF_CAMERA_ENTITY)
        return str(val).strip() if val else None

    def _build_cameras_summary(self) -> V3Records:
        """Records (entity_id, name, area_id, signed snapshot URL) for up to 10 configured cameras, in order."""
        rows: list[dict[str, str]] = []
        for ent_id in self.camera_entities[:CAMERAS_MAX_RECORDS]:
            st = self.hass.states.get(ent_id)
            friendly = str(st.attributes.get("friendly_name") or "") if st else ""
            rows.append(
                {
                    "entity_id": ent_id,
                    "name": friendly or ent_id.split(".", 1)[-1].replace("_", " ").title(),
                    "area_id": resolve_entity_area_id(self.hass, ent_id) or "",
                    "snapshot_url": self.build_camera_snapshot_url(ent_id),
                }
            )
        return camera_records(rows)

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
        """Return the iBeacon UUID broadcast by the device."""
        raw = str(
            self.get_opt(CONF_BLE_BEACON_UUID, DEFAULT_BLE_BEACON_UUID)
        ).strip()
        return raw or DEFAULT_BLE_BEACON_UUID

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
    def assigned_person(self) -> str:
        """Return optional person.* entity_id assigned to this device."""
        val = self.get_opt(CONF_ASSIGNED_PERSON, "")
        return str(val or "").strip()

    @property
    def ble_auto_switch_enabled(self) -> bool:
        """Return True if BLE presence changes should auto-switch active area."""
        return bool(self.get_opt(CONF_BLE_AUTO_SWITCH, DEFAULT_BLE_AUTO_SWITCH))

    @property
    def is_roaming_device(self) -> bool:
        """Return True only for roaming hardware (manifest `stationary == 0` or `wearable == 1`)."""
        return manifest_is_roaming(self.hardware_manifest)

    @property
    def sync_device_area_enabled(self) -> bool:
        """Return True if Voice Follows Me is enabled and this is a roaming device."""
        if not self.is_roaming_device:
            return False
        return bool(self.get_opt(CONF_SYNC_DEVICE_AREA, DEFAULT_SYNC_DEVICE_AREA))

    @property
    def area_follow_dwell_s(self) -> int:
        """Return this Device's Voice Follows Me dwell: seconds a BLE-detected Area must stay stable (3-60)."""
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

    @staticmethod
    def _cap_stream_dimensions(w: int, h: int, max_dim: int = 480) -> tuple[int, int]:
        """Cap network-streamed artwork/image dimensions at max_dim (480px) while preserving aspect ratio."""
        w = max(64, min(1920, w))
        h = max(64, min(1920, h))
        peak = max(w, h)
        if peak <= 502:
            return w, h
        scale = float(max_dim) / float(peak)
        return max(64, round(w * scale)), max(64, round(h * scale))

    @property
    def art_dimensions(self) -> tuple[int, int]:
        """Return (width, height) in pixels for Baseline-JPEG transcoders, from the hardware manifest (capped at 480px)."""
        hw = self._read_device_hardware_manifest()
        try:
            hw_w = int(hw.get("w") or 0)
            hw_h = int(hw.get("h") or 0)
        except (ValueError, TypeError):
            hw_w = hw_h = 0
        if hw_w >= 64 and hw_h >= 64:
            return self._cap_stream_dimensions(hw_w, hw_h)
        return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE

    def sign_payload_resource(self, resource: str) -> str:
        """Sign a payload-embedded or Studio-preview resource (day-bucketed, deterministic within a UTC day)."""
        return self._url_signer.sign_payload_resource(resource)

    def sign_on_demand_resource(self, resource: str) -> str:
        """Sign a resource minted on demand and never embedded in a payload (exact 10-minute expiry)."""
        return self._url_signer.sign_on_demand_resource(resource)

    def verify_resource(
        self,
        resource: str,
        sig: str | None = None,
    ) -> bool:
        """Verify a resource-scoped expiring signature."""
        return self._url_signer.verify_resource(resource, sig)

    def get_lan_base_url(self) -> str:
        """Resolve the numeric-IP LAN HTTP base URL and actual active HTTP port for ESP32 online_image clients."""
        return self._url_signer.get_lan_base_url()

    @callback
    def _async_on_core_config_update(self, _event: Event) -> None:
        """Invalidate cached LAN base URL when Home Assistant core network configuration updates."""
        self._url_signer.invalidate_lan_base_url()
        self.async_notify_listeners()

    def build_camera_snapshot_url(
        self, camera_entity_id: str | None = None, cache_bust: str = ""
    ) -> str:
        """Build the local LAN HTTP Baseline-JPEG camera snapshot URL for ESP32 online_image."""
        cam_ent = (camera_entity_id or self.camera_entity or "").strip()
        w, h = self.art_dimensions
        return self._url_signer.build_camera_snapshot_url(
            self.device_slug, cam_ent, w, h, self.display_shape, cache_bust=cache_bust
        )

    def build_map_snapshot_url(self, location: str) -> str:
        """Build the local LAN HTTP Baseline-JPEG map snapshot URL for a calendar event location."""
        w, h = self.art_dimensions
        return self._url_signer.build_map_snapshot_url(
            self.device_slug, location, w, h, self.display_shape
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
            self.alert_camera_url = ""
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

    def build_wallpaper_url(self) -> str:
        """Build the device-scoped baseline-JPEG photo wallpaper URL (always local LAN HTTP for ESP32 online_image)."""
        w, h = self.art_dimensions
        return self._url_signer.build_wallpaper_url(
            self.device_slug, self.wallpaper_source, w, h, self.display_shape
        )

    def build_proxy_art_url(self, cache_bust: str) -> str:
        """Build the universal Baseline-JPEG artwork URL (/api/latter/artwork/<device_slug>?w=...&h=...&shape=...&sig=...&v=...)."""
        w, h = self.art_dimensions
        return self._url_signer.build_proxy_art_url(
            self.device_slug, w, h, self.display_shape, cache_bust
        )

    def _build_persisted_snapshot(self) -> dict[str, Any]:
        """Build the semantic runtime dictionary for change-gated Store persistence."""
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
        }

    @callback
    def _schedule_persist_runtime_state(self) -> None:
        """Persist runtime state to HA Store only when semantic values change."""
        self._runtime.schedule_save(self._build_persisted_snapshot)

    async def async_setup(self) -> None:
        """Restore persisted state, set up subscriptions, start BLE tracker, and sync initial states."""
        stored = await self._runtime.async_load()
        if stored:
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
            saved_health = stored.get("last_device_health")
            self.last_device_health = saved_health if isinstance(saved_health, dict) else None
        self._structural_snapshot = self._capture_structural_snapshot()
        self._runtime.seed_snapshot(self._build_persisted_snapshot())

        local_spk = self.local_speaker
        has_media_ui = bool(local_spk) or bool(
            esphome_service(
                self.hass,
                self.esphome_device_id,
                "set_browse_slots",
            )
        )
        if not has_media_ui:
            # Headless / sensor-only device (e.g. Bed Presence): clear any accidentally inherited speaker
            self.active_speaker = ""
            self.last_speaker = ""
        else:
            if not self.active_speaker:
                self.active_speaker = local_spk
            self._enforce_local_speaker_if_remote_idle("ha_startup")
            if not self.last_speaker:
                self.last_speaker = self.active_speaker

        proxy_areas = get_ble_proxy_area_ids(self.hass)

        explicit_default_area = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        if self.native_ble_tracking_enabled and not explicit_default_area:
            if self.active_area_id and proxy_areas and self.active_area_id not in proxy_areas:
                self.active_area_id = None
        elif not self.active_area_id:
            dev_area = _get_esphome_device_current_area(
                self.hass, self.esphome_device_id
            )
            if dev_area:
                self.active_area_id = dev_area

        self._bind_all_listeners()

        self._unsub_core_config = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._async_on_core_config_update
        )

        if self.native_ble_tracking_enabled:
            self._ble_tracker = LatterNativeBleTracker(
                hass=self.hass,
                beacon_uuid=self.ble_beacon_uuid,
                device_slug=self.device_slug,
                on_area_detected=self._async_on_native_ble_area_detected,
                area_offsets=self.ble_area_offsets,
                target_address=self.ble_target_address,
                esphome_device_id=self.esphome_device_id,
                manifest_beacon=self.hardware_manifest.get("beacon"),
            )
            self._ble_tracker.async_start()

        if not self.is_ble_tag:
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
        # Onboarding / reload: mirror the tracking option (no-op until the device's switch is available).
        await self.async_sync_presence_beacon("options")
        try:
            from .repairs import async_audit_coordinator_health

            async_audit_coordinator_health(self.hass, self)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Repairs audit skipped: %s", err)

    @callback
    def _bind_all_listeners(self) -> None:
        """Bind or rebind all entity state listeners and the wallpaper timer (skipped for BLE tags)."""
        if self.is_ble_tag:
            return
        self._bind_speaker_listener()
        self._bind_weather_listener()
        self._bind_alarm_listener()
        self._bind_remotes_listener()
        self._bind_area_entities_listener()
        self._bind_doorbell_ring_listener()
        self._bind_wallpaper_cycle_timer()

    @callback
    def async_cleanup(self) -> None:
        """Clean up all Latter subscriptions and timers on entry unload."""
        self._notify_debouncer.async_cancel()
        self._area_follow.cancel()
        if self._doorbell_reply_task is not None and not self._doorbell_reply_task.done():
            self._doorbell_reply_task.cancel()
        self._doorbell_reply_task = None
        if self._ble_tracker is not None:
            self._ble_tracker.async_stop()
            self._ble_tracker = None

        for unsub in (
            self._unsub_core_config,
            self._unsub_speaker_state,
            self._unsub_weather_state,
            self._unsub_alarm_state,
            self._unsub_remotes_state,
            self._unsub_area_entities_state,
            self._unsub_area_debounce,
            self._unsub_forecast_timer,
            self._unsub_calendar_timer,
            self._unsub_wallpaper_timer,
            self._unsub_doorbell_ring_state,
        ):
            if unsub is not None:
                unsub()
        self._unsub_core_config = None
        self._unsub_speaker_state = None
        self._unsub_weather_state = None
        self._unsub_alarm_state = None
        self._unsub_remotes_state = None
        self._unsub_area_entities_state = None
        self._unsub_area_debounce = None
        self._unsub_forecast_timer = None
        self._unsub_calendar_timer = None
        self._unsub_wallpaper_timer = None
        self._unsub_doorbell_ring_state = None

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
        self.async_notify_listeners()
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

    @property
    def doorbell_ring_map(self) -> dict[str, str]:
        """Return the doorbell ring entities this Device watches (`ring_entity_id -> camera_entity_id`)."""
        return dict(self._doorbell_ring_map)

    @callback
    def _bind_doorbell_ring_listener(self) -> None:
        """Auto-detect sibling doorbell ring / visitor entities on configured cameras and subscribe."""
        if self._unsub_doorbell_ring_state is not None:
            self._unsub_doorbell_ring_state()
            self._unsub_doorbell_ring_state = None

        if self.is_ble_tag or not self.has_display:
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

        esp_notify_svc = esphome_service(
            self.hass,
            self.esphome_device_id,
            "show_notification",
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
                        "alert_id": self.alert_id,
                    },
                    blocking=False,
                ),
                f"latter_doorbell_notify_{self.device_slug}",
            )

    async def async_handle_device_hello(
        self,
        contract: int,
        boot_id: str,
        manifest_raw: str,
    ) -> None:
        """Handle device-initiated handshake on ESPHome API connection."""
        is_new_boot, parsed = self._runtime.apply_device_hello(boot_id, manifest_raw)
        if parsed is not None:
            if self._ble_tracker is not None:
                self._ble_tracker.update_manifest_beacon(parsed.get("beacon"))
            self._apply_device_health(parsed, str(boot_id or "").strip())
        if is_new_boot:
            self._local_needs_cold_resume = True

        _LOGGER.info(
            "Received latter.device_hello from '%s' (contract=v%s, boot_id=%s, new_boot=%s)",
            self.device_slug,
            contract,
            str(boot_id or "").strip() or "none",
            is_new_boot,
        )
        self.force_republish_all_domains()
        await self._async_handle_device_reconnect()
        # After the reconnect delay the device's entities have their states; turn the beacon on if tracked.
        await self.async_sync_presence_beacon("hello")

    @callback
    def _apply_device_health(self, manifest: dict[str, Any], boot_id: str) -> None:
        """Raise or clear this Device's crash, brownout and rollback repairs, once per boot (survives HA restarts)."""
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
                self.hass, DOMAIN, device_health_issue_id(kind, self.subentry_id)
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

    @callback
    def _enforce_local_speaker_if_remote_idle(self, reason: str) -> None:
        """Reset active_speaker to local_speaker on boot/wake unless the remote speaker is actively playing."""
        local_spk = self.local_speaker
        if not local_spk:
            return
        if self.is_local_speaker_entity(self.active_speaker):
            if self.active_speaker != local_spk:
                self.active_speaker = local_spk
                self._bind_speaker_listener()
                self._schedule_persist_runtime_state()
            return

        remote_state = self.hass.states.get(self.active_speaker)
        is_remote_playing = bool(
            remote_state and remote_state.state in (STATE_PLAYING, STATE_BUFFERING)
        )
        if not is_remote_playing:
            _LOGGER.info(
                "Resetting active_speaker from idle remote '%s' (state=%s) to local_speaker '%s' (%s)",
                self.active_speaker,
                remote_state.state if remote_state else "missing",
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
                    ble_driven=True,
                )
        self.async_notify_listeners()
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
                ble_driven=True,
            )
        self.async_notify_listeners()
        if self.on_area_changed_push_slots is not None:
            await self.on_area_changed_push_slots(self)

    async def _async_resume_idle_speaker_queue(
        self, speaker_entity_id: str
    ) -> None:
        """Resume playback on an idle speaker only if native media_play does not start within 2.2s after cold boot."""
        self._resuming_guard_until = time.monotonic() + 3.5
        resumed = await async_resume_idle_speaker_queue(
            self.hass,
            speaker_entity_id,
            self.last_media_uri,
            self.last_media_position,
            self.last_media_type,
        )
        if resumed:
            self._local_needs_cold_resume = False
            self.async_notify_listeners()

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
        ma_target = _resolve_ma_counterpart_entity(
            self.hass, target_spk
        )
        cmd_target = ma_target or target_spk
        state_obj = self.hass.states.get(target_spk)
        ma_state_obj = (
            self.hass.states.get(ma_target)
            if ma_target and ma_target != target_spk
            else None
        )
        cur_state = state_obj.state if state_obj else STATE_IDLE
        if (
            cur_state in (STATE_IDLE, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)
            and ma_state_obj is not None
            and ma_state_obj.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
        ):
            cur_state = ma_state_obj.state

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
                {ATTR_ENTITY_ID: cmd_target},
                blocking=False,
            )
            is_local = self.is_local_speaker_entity(target_spk)
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
                {ATTR_ENTITY_ID: cmd_target},
                blocking=False,
            )
            return

        if cmd in ("next", "next_track", "media_next_track"):
            await self.hass.services.async_call(
                "media_player",
                "media_next_track",
                {ATTR_ENTITY_ID: cmd_target},
                blocking=False,
            )
            return

        if cmd in ("previous", "previous_track", "media_previous_track"):
            await self.hass.services.async_call(
                "media_player",
                "media_previous_track",
                {ATTR_ENTITY_ID: cmd_target},
                blocking=False,
            )
            return

        if cmd == "stop":
            await self.hass.services.async_call(
                "media_player",
                "media_stop",
                {ATTR_ENTITY_ID: cmd_target},
                blocking=False,
            )
            return

        if cmd == "clear_queue":
            await self.hass.services.async_call(
                "media_player",
                "clear_playlist",
                {ATTR_ENTITY_ID: cmd_target},
                blocking=False,
            )
            return

        if cmd == "seek" and seek_position is not None:
            await self.hass.services.async_call(
                "media_player",
                "media_seek",
                {
                    ATTR_ENTITY_ID: cmd_target,
                    "seek_position": round(float(seek_position), 1),
                },
                blocking=False,
            )

    def is_device_away(self) -> bool:
        """Return True if a roaming BLE device has timed out across all proxies (and is not awake on local Wi-Fi)."""
        return compute_is_device_away(
            self.hass,
            native_ble_tracking_enabled=self.native_ble_tracking_enabled,
            ble_tracker=self._ble_tracker,
            is_ble_tag=self.is_ble_tag,
            esphome_device_id=self.esphome_device_id,
        )

    def get_current_area_and_distance(self) -> tuple[str, dict[str, Any]]:
        """Return (area_or_away_state, attributes) for sensor.<slug>_current_area and sensor.<slug>_ble_distance."""
        return compute_current_area_and_distance(
            self.hass,
            away=self.is_device_away(),
            native_ble_tracking_enabled=self.native_ble_tracking_enabled,
            ble_tracker=self._ble_tracker,
            active_area_id=self.active_area_id,
            explicit_default_area=str(self.get_opt(CONF_DEFAULT_AREA) or "").strip(),
            assigned_person=self.assigned_person,
        )

    @callback
    def _async_on_native_ble_area_detected(
        self, area_id: str, scanner_source: str
    ) -> None:
        """Handle area transition or Away timeout detected by Latter's BLE proxy tracker."""
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
            # Media follows per the Device's setting (area_handoff), as for an on-device Area pick.
            self.async_set_active_area(
                area_id,
                sync_device_registry=True,
                ble_driven=True,
            )
        else:
            self.async_notify_listeners()

    def get_person_area_and_distance(self, person_entity: str) -> tuple[str, dict[str, Any]]:
        """Resolve the freshest area and BLE distance across all Latter devices carried by a person."""
        return resolve_person_area_and_distance(self.hass, person_entity)

    def _pack_domain_payload(self, domain: str, *fields: Any) -> tuple[int, str]:
        """Pack domain fields with content-hashed per-domain revision ('v3\\x1f<epoch>\\x1f<rev>\\x1f...')."""
        cur_rev, packed = self._packer.pack(domain, *fields)
        self.rev = max(self.rev, self._packer.rev)
        return cur_rev, packed

    @callback
    def force_republish_all_domains(self) -> None:
        """Bump per-domain revisions across all 5 domains so a reconnected/rebooted device receives a full snapshot."""
        self._packer.force_republish_all_domains()
        self.rev = max(self.rev, self._packer.rev)
        self._cached_media_payload = None
        self._cached_media_anchor = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        if self.weather_attributes and "condition" in self.weather_attributes:
            w_rev, w_payload = self._pack_domain_payload(
                "weather_forecast",
                self.weather_attributes.get("condition"),
                self.weather_attributes.get("temperature"),
                self.weather_attributes.get("humidity"),
                self.weather_attributes.get("wind_speed"),
                self.weather_attributes.get("wind_bearing"),
                self.weather_attributes.get("high"),
                self.weather_attributes.get("low"),
                self.forecast_records,
            )
            self.weather_attributes["rev"] = w_rev
            self.weather_attributes["payload"] = w_payload
        self.async_update_listeners()

    async def _async_debounced_notify(self) -> None:
        """Flush coalesced coordinator listener updates."""
        self.async_update_listeners()

    @callback
    def async_notify_listeners(self) -> None:
        """Invalidate per-tick payload caches, schedule change-gated Store save, and coalesce listener updates."""
        self._cached_media_payload = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._schedule_persist_runtime_state()
        self._notify_debouncer.async_schedule_call()

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
        await async_execute_ma_queue_transfer(
            self.hass,
            self.local_speaker,
            source_speaker,
            target_speaker,
            was_playing,
            handoff_position,
            media_content_id,
            media_content_type,
        )
        self.async_notify_listeners()

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
        self.async_notify_listeners()

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

        self._bind_area_entities_listener()

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
        if media_map["remote"]:
            self.active_remote = media_map["remote"]

        self.active_remote_slot = 1
        for slot_idx, slot_info in enumerate(self.get_remote_slots(), start=1):
            if slot_info["area_id"] == matched_id:
                self.active_remote_slot = slot_idx
                break
        self._bind_remotes_listener()

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
        return resolve_effective_remote_entities(
            self.hass,
            all_inventory=self.get_remote_entities_list(),
            groups=self.remote_groups,
            mode=self.device_remote_group,
            cur_area=(self.active_area_id or str(self.get_opt(CONF_DEFAULT_AREA) or "")).strip(),
        )

    def get_remote_slots(self) -> list[dict[str, str]]:
        """Return up to 10 resolved TV/Media Remote slot dictionaries for this device's current context."""
        ent_ids = self.get_effective_remote_entities_for_device()
        if not ent_ids:
            return []
        return [resolve_remote_slot_pair(self.hass, eid) for eid in ent_ids[:10]]

    def get_remote_config_payload(self) -> tuple[str | None, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_remote_config (supports 0..10 slots)."""
        now_m = time.monotonic()
        if self._cached_remote_payload is not None and (now_m - self._cached_remote_payload[0]) < 0.05:
            return self._cached_remote_payload[1]
        slots = self.get_remote_slots()
        slot_rows: list[dict[str, Any]] = []
        for idx, slot in enumerate(slots, start=1):
            # The remote entity when the slot has one, else its media player (what the device controls).
            ent = slot["remote_entity"] if slot["remote_entity"].startswith("remote.") else slot["media_player_entity"]
            if ent.startswith(("remote.", "media_player.")):
                slot_rows.append(
                    {"index": idx, "label": slot["name"], "entity_id": ent, "area_id": slot["area_id"], "state": ha_value(slot["state"])}
                )
        populated_count = len(slot_rows)
        clamped_active = max(1, min(max(1, len(slots)), self.active_remote_slot))
        active_slot = clamped_active if populated_count else None
        slots_summary = remote_slot_records(slot_rows) if populated_count else V3Records()
        state_str = (slots[clamped_active - 1]["name"] or None) if populated_count else None
        rem_rev, rem_payload = self._pack_domain_payload(
            "remote_config",
            active_slot,
            populated_count,
            slots_summary,
        )
        attrs: dict[str, Any] = {
            "active_slot": active_slot,
            "configured_count": populated_count,
            "slots_summary": slots_summary,
            "rev": rem_rev,
            "payload": rem_payload,
        }
        res = (state_str, attrs)
        self._cached_remote_payload = (now_m, res)
        return res

    def _resolve_active_area_entry(self) -> ar.AreaEntry | None:
        """Resolve the current AreaEntry for this device from BLE lock, active_area_id, or explicit default."""
        area_reg = ar.async_get(self.hass)
        explicit_default = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        has_ble_lock = bool(
            self._ble_tracker is not None and self._ble_tracker.current_area_id
        )
        if self.native_ble_tracking_enabled and not has_ble_lock and not explicit_default:
            return None
        eff_id = (
            self._ble_tracker.current_area_id
            if (self.native_ble_tracking_enabled and has_ble_lock and self._ble_tracker)
            else (self.active_area_id or explicit_default)
        )
        return area_reg.async_get_area(eff_id) if eff_id else None

    @property
    def active_area_name(self) -> str:
        """Return the friendly name of the device's effective active area, or 'Unassigned'."""
        area_entry = self._resolve_active_area_entry()
        return area_entry.name if area_entry else "Unassigned"

    def get_area_context_payload(self) -> tuple[str, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_area_context."""
        now_m = time.monotonic()
        if self._cached_area_payload is not None and (now_m - self._cached_area_payload[0]) < 0.05:
            return self._cached_area_payload[1]
        area_entry = self._resolve_active_area_entry()
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
            entities=entities,
        )
        lights_on = sum(
            1 for e in entities if e["type"] == "light" and e["active"]
        )
        covers_open = sum(
            1 for e in entities if e["type"] == "cover" and e["active"]
        )
        climate_telemetry = get_area_climate_telemetry(
            self.hass, self.active_area_id
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
        active_cam = self.active_carousel_camera or self.camera_entity
        camera_snapshot_url = (
            self.build_camera_snapshot_url(active_cam) if active_cam else ""
        )

        area_attrs: dict[str, Any] = {
            "site_id": self.site_id,
            "area_id": self.active_area_id or "",
            "area_name": area_name,
            "ble_closest_proxy": self._ble_tracker.closest_scanner if self._ble_tracker else "",
            "dock_apps": self.dock_apps_csv,
            "activity_card": self.activity_card_enabled,
            "activity_sources": self.activity_sources_csv,
            "wallpaper_url": self.build_wallpaper_url(),
            "theme_color_hex": self.device_custom_color,
            "available_domains": avail_domains,
            "area_temp": climate_telemetry["temperature"],
            "area_humidity": climate_telemetry["humidity"],
            "lights_on": lights_on,
            "covers_open": covers_open,
            "alarm_entity": alarm_info["entity_id"],
            "alarm_state": alarm_info["state"],
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
            "camera_snapshot_url": camera_snapshot_url,
            "cameras_summary": self._build_cameras_summary(),
            "doorbell_talk_state": self.doorbell_talk_state,
            "intercom_targets_summary": self._build_intercom_targets_summary(),
            "alert_id": self.alert_id,
            "alert_title": self.alert_title,
            "alert_message": self.alert_message,
            "alert_priority": self.alert_priority,
            "alert_duration": self.alert_duration,
            "alert_chime": self.alert_chime,
            "alert_camera_url": self.alert_camera_url,
        }
        area_rev, area_payload = self._pack_domain_payload(
            "area_context",
            area_attrs["area_id"],
            area_entry.name if area_entry else "",
            area_attrs["site_id"],
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
            # Until the first alert (alert_id 0) there is no alert: its fields are empty.
            *(
                (
                    self.alert_id,
                    self.alert_title,
                    self.alert_message,
                    self.alert_priority,
                    self.alert_duration,
                    1 if self.alert_chime else 0,
                    self.alert_camera_url,
                )
                if self.alert_id
                else (0, "", "", "", None, None, "")
            ),
            *activity_payload(self.activity_card_enabled, self.activity_sources_csv),
        )
        area_attrs["rev"] = area_rev
        area_attrs["payload"] = area_payload
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
            self.hass, self.active_speaker
        )
        if ma_counterpart and ma_counterpart not in tracked:
            tracked.append(ma_counterpart)
        if self.is_local_speaker_entity(self.active_speaker):
            np_title = self.device_entity("sensor", "_now_playing_title")
            if np_title and np_title not in tracked:
                tracked.append(np_title)

        self._sync_active_speaker_media_snapshot()
        self._unsub_speaker_state = async_track_state_change_event(
            self.hass,
            tracked,
            self._async_on_speaker_state_change,
        )

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
        self.async_notify_listeners()

    @callback
    def _async_on_speaker_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle target media_player state/attribute updates."""
        self._cached_media_anchor = None
        self._sync_active_speaker_media_snapshot()
        self.async_notify_listeners()

    def _read_volume_from_target(
        self, vol_target: str, fallback_attrs: dict[str, Any]
    ) -> float | None:
        """Read normalized 0.0..1.0 volume from media_player, number, or input_number, or None when unknown."""
        return read_volume_from_target(self.hass, vol_target, fallback_attrs)

    def _resolve_speaker_media_snapshot(
        self,
    ) -> tuple[
        State | None,
        State | None,
        str,
        dict[str, Any],
        dict[str, Any],
        str,
        str,
        str,
        float,
        float,
        str,
        int,
    ]:
        """Resolve live speaker state, counterpart attributes, and active track metadata without side effects."""
        state_obj = self.hass.states.get(self.active_speaker)
        ma_counterpart = _resolve_ma_counterpart_entity(
            self.hass, self.active_speaker
        )
        ma_st = (
            self.hass.states.get(ma_counterpart)
            if ma_counterpart and ma_counterpart != self.active_speaker
            else None
        )
        if (
            state_obj is None
            or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ) and ma_st is not None:
            state_obj = ma_st

        is_local_flag = 1 if self.is_local_speaker_entity(self.active_speaker) else 0
        if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None, ma_st, "", {}, {}, "", "", "", 0.0, 0.0, "", is_local_flag

        state = state_obj.state
        if (
            state in (STATE_IDLE, STATE_OFF)
            and ma_st is not None
            and ma_st.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
        ):
            state = ma_st.state
        if state not in (
            STATE_PLAYING,
            STATE_PAUSED,
            STATE_IDLE,
            STATE_BUFFERING,
            STATE_OFF,
        ):
            state = STATE_IDLE

        attrs: dict[str, Any] = dict(state_obj.attributes)
        m_attrs: dict[str, Any] = dict(ma_st.attributes) if ma_st is not None else {}

        title = str(attrs.get("media_title") or "")
        artist = str(
            attrs.get("media_artist")
            or attrs.get("media_series_title")
            or attrs.get("media_album_artist")
            or ""
        )
        album = str(attrs.get("media_album_name") or "")
        duration = float(attrs.get("media_duration") or 0.0)
        position = _interpolate_speaker_position(state_obj)

        # When playing on the local ESPHome Sendspin speaker, media_player.<slug>_music often omits media_title
        # and entity_picture in HA; fall back to the Music Assistant counterpart entity or ESPHome text_sensors.
        if not title and m_attrs.get("media_title"):
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

        if not title and bool(is_local_flag):
            t_st = self.device_state("sensor", "_now_playing_title")
            a_st = self.device_state("sensor", "_now_playing_artist")
            al_st = self.device_state("sensor", "_now_playing_album")
            if t_st is not None and ha_value(t_st.state):
                title = str(t_st.state)
                if a_st is not None and ha_value(a_st.state):
                    artist = str(a_st.state)
                if al_st is not None and ha_value(al_st.state):
                    album = str(al_st.state)

        raw_type = str(
            attrs.get("media_content_type") or m_attrs.get("media_content_type") or ""
        ).lower()
        if not raw_type:
            media_type = ""
        elif "podcast" in raw_type:
            media_type = "podcast"
        elif "audiobook" in raw_type or "book" in raw_type:
            media_type = "audiobook"
        else:
            media_type = "music"

        return (
            state_obj,
            ma_st,
            state,
            attrs,
            m_attrs,
            title,
            artist,
            album,
            duration,
            position,
            media_type,
            is_local_flag,
        )

    @callback
    def _sync_active_speaker_media_snapshot(self) -> None:
        """Update persisted last_media_* fields when the active speaker is playing, paused, or buffering."""
        (
            state_obj,
            _ma_st,
            state,
            attrs,
            m_attrs,
            title,
            artist,
            album,
            duration,
            position,
            media_type,
            _is_local_flag,
        ) = self._resolve_speaker_media_snapshot()
        if state_obj is None or not title or state not in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING):
            return
        cid = str(attrs.get("media_content_id") or m_attrs.get("media_content_id") or "")
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

    def get_active_media_payload(self) -> tuple[str | None, dict[str, Any]]:
        """Compute state and attributes for sensor.<device_slug>_active_media."""
        now_m = time.monotonic()
        if self._cached_media_payload is not None and (now_m - self._cached_media_payload[0]) < 0.05:
            return self._cached_media_payload[1]
        (
            state_obj,
            _ma_st,
            state,
            attrs,
            m_attrs,
            title,
            artist,
            album,
            duration,
            position,
            media_type,
            is_local_flag,
        ) = self._resolve_speaker_media_snapshot()

        vol_target = self.get_volume_target_entity(self.active_speaker)
        fallback_spk_name = (
            self.device_title
            if is_local_flag
            else (
                self.active_speaker.split(".", 1)[-1].replace("_", " ").title()
                if self.active_speaker
                else ""
            )
        )

        if state_obj is None:
            # The speaker is missing or unavailable: its state is unknown (""); the last track stays on screen.
            idle_title = self.last_media_title
            idle_artist = self.last_media_artist
            idle_album = self.last_media_album
            idle_dur = round(self.last_media_duration, 1) if self.last_media_duration > 0 else None
            idle_pos = round(self.last_media_position, 1)
            idle_type = self.last_media_type if self.last_media_title else ""
            idle_vol = self._read_volume_from_target(vol_target, {})
            idle_vol_r = round(idle_vol, 2) if idle_vol is not None else None
            idle_vol_pct = (
                int(round(max(0.0, min(1.0, idle_vol)) * 100.0))
                if idle_vol is not None
                else None
            )
            med_rev, med_payload = self._pack_domain_payload(
                "active_media",
                "",
                idle_title,
                idle_artist,
                idle_album,
                idle_dur,
                idle_pos,
                None,
                idle_vol_pct,
                idle_type,
                0,
                "",
                self.active_speaker,
                fallback_spk_name,
                self.last_speaker,
                self.local_speaker,
                vol_target,
                is_local_flag,
            )
            res = (
                None,
                {
                    "title": idle_title,
                    "artist": idle_artist,
                    "album": idle_album,
                    "duration": idle_dur,
                    "position": idle_pos,
                    "position_updated_at": None,
                    "volume": idle_vol_r,
                    "media_type": idle_type,
                    "supported_features": 0,
                    "art_url": "",
                    "active_speaker": self.active_speaker,
                    "speaker_name": fallback_spk_name,
                    "last_speaker": self.last_speaker,
                    "local_speaker": self.local_speaker,
                    "volume_entity": vol_target,
                    "is_local": bool(is_local_flag),
                    "rev": med_rev,
                    "payload": med_payload,
                },
            )
            self._cached_media_payload = (now_m, res)
            return res

        in_transfer_window = time.monotonic() < self._transfer_hold_until
        if in_transfer_window:
            if not title and self._transfer_hold_title:
                title = self._transfer_hold_title
                artist = self._transfer_hold_artist or artist
                album = self._transfer_hold_album or album
                duration = self._transfer_hold_duration or duration
            if position < 1.0 and self._transfer_hold_position > 1.0:
                position = self._transfer_hold_position
        elif (
            not title
            and state == STATE_IDLE
            and self.last_media_title
            and bool(is_local_flag)
        ):
            title = self.last_media_title
            artist = self.last_media_artist
            album = self.last_media_album
            duration = self.last_media_duration
            position = self.last_media_position
            media_type = self.last_media_type

        volume = self._read_volume_from_target(vol_target, attrs)
        if volume is None and m_attrs:
            volume = self._read_volume_from_target(vol_target, m_attrs)
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

        if state == STATE_OFF or not title:
            art_url = ""
        elif raw_pic:
            self.last_valid_raw_pic = raw_pic
            self._last_art_track_key = track_key
            self._last_art_proxy_url = self.build_proxy_art_url(
                f"{track_key}|{raw_pic}"
            )
            art_url = self._last_art_proxy_url
        elif (track_key == self._last_art_track_key or in_transfer_window) and self._last_art_proxy_url:
            art_url = self._last_art_proxy_url
        else:
            art_url = ""

        speaker_name = (
            self.device_title
            if is_local_flag
            else str(attrs.get("friendly_name") or fallback_spk_name)
        )

        raw_updated_at = attrs.get("media_position_updated_at") or m_attrs.get(
            "media_position_updated_at"
        )
        if isinstance(raw_updated_at, datetime):
            pos_updated_at = int(raw_updated_at.timestamp())
        elif raw_updated_at:
            parsed_ua = dt_util.parse_datetime(str(raw_updated_at))
            pos_updated_at = int(parsed_ua.timestamp()) if parsed_ua else 0
        else:
            pos_updated_at = 0

        dur_r = round(duration, 1) if duration > 0 else None
        vol_r = round(volume, 2) if volume is not None else None
        vol_pct = (
            int(round(max(0.0, min(1.0, volume)) * 100.0))
            if volume is not None
            else None
        )
        raw_pos = float(
            attrs.get("media_position")
            or m_attrs.get("media_position")
            or 0.0
        )
        media_anchor = (
            state,
            title,
            artist,
            album,
            dur_r,
            round(raw_pos, 1),
            pos_updated_at,
            vol_pct,
            media_type,
            supported_features,
            art_url,
            self.active_speaker,
            speaker_name,
            self.last_speaker,
            self.local_speaker,
            vol_target,
            is_local_flag,
        )
        if (
            self._cached_media_anchor is not None
            and self._cached_media_anchor[0] == media_anchor
        ):
            pos_r = self._cached_media_anchor[1]
        else:
            pos_r = round(position, 1)
            self._cached_media_anchor = (media_anchor, pos_r)

        med_rev, med_payload = self._pack_domain_payload(
            "active_media",
            state,
            title,
            artist,
            album,
            dur_r,
            pos_r,
            pos_updated_at or None,
            vol_pct,
            media_type,
            supported_features,
            art_url,
            self.active_speaker,
            speaker_name,
            self.last_speaker,
            self.local_speaker,
            vol_target,
            is_local_flag,
        )
        res = (
            state,
            {
                "title": title,
                "artist": artist,
                "album": album,
                "duration": dur_r,
                "position": pos_r,
                "position_updated_at": pos_updated_at,
                "volume": vol_r,
                "media_type": media_type,
                "supported_features": supported_features,
                "art_url": art_url,
                "active_speaker": self.active_speaker,
                "speaker_name": speaker_name,
                "last_speaker": self.last_speaker,
                "local_speaker": self.local_speaker,
                "volume_entity": vol_target,
                "is_local": bool(is_local_flag),
                "rev": med_rev,
                "payload": med_payload,
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
        self.async_notify_listeners()

    async def _async_periodic_calendar_refresh(self, _now: datetime) -> None:
        """Refresh system calendar agenda every 15 minutes."""
        await self.async_refresh_calendar_agenda()

    async def async_refresh_calendar_agenda(self, days: int = 30) -> None:
        """Fetch upcoming calendar events and update sensor state."""
        records, events = await async_fetch_calendar_snapshot(
            self.hass,
            self.calendar_entities,
            days=days,
            map_url_builder=self.build_map_snapshot_url,
        )
        self.calendar_records = records
        self.calendar_events = events
        self.async_notify_listeners()

    def get_calendar_agenda_payload(self) -> tuple[int, dict[str, Any]]:
        """Return the upcoming event count (the sensor state) and the Protocol v3 calendar_agenda payload."""
        count = len(self.calendar_events)
        next_event = str(self.calendar_events[0].get("name") or "") if self.calendar_events else ""
        cal_rev, cal_payload = self._pack_domain_payload(
            "calendar_agenda",
            self.calendar_records,
            count,
            next_event,
        )
        return count, {
            "event_count": count,
            "next_event": next_event,
            "events": self.calendar_events,
            "calendars": self.calendar_entities,
            "rev": cal_rev,
            "payload": cal_payload,
        }

    async def async_refresh_weather_forecast(self) -> None:
        """Fetch the daily forecast via weather.get_forecasts and pack the weather_forecast payload."""
        weather_ent = self.weather_entity
        if not weather_ent:
            # No weather entity: everything is unknown (empty fields; the device shows "—").
            self.forecast_records = V3Records()
            w_rev, w_payload = self._pack_domain_payload(
                "weather_forecast", "", None, None, None, None, None, None, self.forecast_records
            )
            self.weather_attributes = {
                "condition": "",
                "temperature": None,
                "humidity": None,
                "wind_speed": None,
                "wind_bearing": None,
                "high": None,
                "low": None,
                "weather_entity": "",
                "rev": w_rev,
                "payload": w_payload,
            }
            self.async_notify_listeners()
            return
        snap = await async_fetch_weather_snapshot(self.hass, weather_ent)
        if snap is None:
            return
        records, w_fields = snap
        self.forecast_records = records
        w_rev, w_payload = self._pack_domain_payload(
            "weather_forecast",
            w_fields["condition"],
            w_fields["temperature"],
            w_fields["humidity"],
            w_fields["wind_speed"],
            w_fields["wind_bearing"],
            w_fields["high"],
            w_fields["low"],
            self.forecast_records,
        )
        self.weather_attributes = {
            **w_fields,
            "weather_entity": weather_ent,
            "rev": w_rev,
            "payload": w_payload,
        }
        self.async_notify_listeners()