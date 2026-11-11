"""Pure push state coordinator for one Latter Device (Home Assistant side of Protocol v3)."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer

from ..areas.calendar import (
    apply_coordinator_calendar_snapshot,
    apply_coordinator_weather_snapshot,
    async_refresh_coordinator_calendar,
    async_refresh_coordinator_weather,
    build_calendar_agenda_payload,
)
from ..areas.context_builder import (
    bind_coordinator_area_listeners,
    build_area_context_payload,
    build_remote_config_payload,
    resolve_active_area_entry,
    resolve_remote_slot_pair,
)
from ..areas.controller import (
    LatterAreaFollowController,
    apply_coordinator_device_health,
    async_handle_coordinator_reconnect,
    async_sync_coordinator_presence_beacon,
    bind_coordinator_wallpaper_cycle_timer,
    compute_current_area_and_distance,
    compute_is_device_away,
    on_native_ble_area_detected,
    resolve_effective_remote_entities,
    resolve_person_area_and_distance,
    set_coordinator_active_area,
    sync_coordinator_ble_tracker,
)
from ..areas.doorbell import bind_coordinator_doorbell_listener
from ..const import (
    CONF_CALENDAR_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_SYSTEM_BLE_UUID,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DEFAULT_DOORBELL_NOISE_REDUCTION,
    DOMAIN,
    normalize_noise_reduction,
)
from ..http.url_signer import UrlSigner
from ..media.player_controller import (
    bind_coordinator_speaker_listener,
    build_active_media_payload,
    enforce_local_speaker_if_remote_idle,
    execute_coordinator_media_command,
    resolve_esphome_local_speaker,
    resolve_ma_counterpart_entity,
    set_coordinator_active_speaker,
)
from ..presence.area_follow import Trigger
from ..presence.ble_fabric import get_ble_fabric, get_ble_proxy_area_ids
from .device_runtime import (
    LatterCoordinatorConfigMixin,
    LatterDeviceRuntime,
    apply_stored_runtime_to_coordinator,
    async_push_coordinator_v3_domains,
    build_coordinator_persisted_snapshot,
    dispatch_coordinator_notification,
    force_republish_coordinator_domains,
    init_coordinator_runtime_fields,
    match_coordinator_target,
)
from .hub import get_latter_system
from .identity import esphome_service, get_bound_esphome_device
from .payloads import DomainPayloadPacker, V3Records
from .rpc_receiver import LatterRpcReceiver

_LOGGER = logging.getLogger(__name__)


def resolve_coordinator(
    hass: HomeAssistant, target: str | None = None
) -> LatterCoordinator | None:
    """Resolve a loaded LatterCoordinator by subentry_id, Latter or ESPHome device_id, or exact slug."""
    domain_data = hass.data.get(DOMAIN, {})
    sys_obj = get_latter_system(hass)
    coords = (
        list(sys_obj.coordinators.values())
        if sys_obj and sys_obj.coordinators
        else [v for v in domain_data.values() if isinstance(v, LatterCoordinator)]
    )
    return match_coordinator_target(hass, coords, target)


class LatterCoordinator(LatterCoordinatorConfigMixin):
    """Pure push coordinator managing Protocol v3 domains, BLE presence, media, and Area state for one Device."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, hmac_secret: bytes, subentry: ConfigSubentry
    ) -> None:
        """Initialize the push LatterCoordinator for one Device subentry."""
        self.hass, self.entry, self.config_entry, self.subentry = hass, entry, entry, subentry
        self.subentry_id: str = subentry.subentry_id
        self.name: str = f"{DOMAIN}_{self.subentry_id}"
        self._listeners: dict[Callable[[], None], None] = {}
        self._hmac_secret = hmac_secret
        self._runtime = LatterDeviceRuntime(hass, self.subentry_id)
        self._store = self._runtime.store
        self._url_signer = UrlSigner(hass, self.subentry_id, hmac_secret)
        self._packer = DomainPayloadPacker()
        self._area_follow = LatterAreaFollowController(hass)
        self._cached_esphome_device_id: str | None = None
        self.rev: int = 1
        self._notify_debouncer: Debouncer[None] = Debouncer(
            hass, _LOGGER, cooldown=0.2, immediate=False, function=self._async_debounced_notify
        )
        self._rpc_receiver = LatterRpcReceiver(hass, self)
        init_coordinator_runtime_fields(self)

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

    @property
    def epoch(self) -> int:
        return self._packer.epoch

    @property
    def last_area_follow_write(self) -> dict[str, Any] | None:
        return self._area_follow.last_area_follow_write

    @property
    def local_speaker(self) -> str:
        return resolve_esphome_local_speaker(self.hass, self.esphome_device_id)

    @property
    def local_ma_speaker(self) -> str:
        return resolve_ma_counterpart_entity(self.hass, self.local_speaker) or ""

    def is_local_speaker_entity(self, speaker_entity_id: str | None) -> bool:
        spk = str(speaker_entity_id or "").strip()
        return bool(spk and spk in (self.local_speaker, self.local_ma_speaker))

    @callback
    def _async_on_core_config_update(self, _event: Event) -> None:
        self._url_signer.invalidate_lan_base_url()
        self.hass.async_create_task(
            self._url_signer.async_prime_lan_base_url(), f"latter_lan_url_{self.device_slug}"
        )
        self.async_notify_listeners()

    @callback
    def async_dispatch_notification(
        self, title: str, message: str, priority: str = "normal",
        duration: int = 8, chime: bool = True, camera_entity: str | None = None,
    ) -> None:
        dispatch_coordinator_notification(self, title, message, priority, duration, chime, camera_entity)

    def _build_persisted_snapshot(self) -> dict[str, Any]:
        return build_coordinator_persisted_snapshot(self)

    @callback
    def _schedule_persist_runtime_state(self) -> None:
        self._runtime.schedule_save(self._build_persisted_snapshot)

    async def async_setup(self) -> None:
        await self._url_signer.async_prime_lan_base_url()
        apply_stored_runtime_to_coordinator(self, await self._runtime.async_load())
        self._structural_snapshot = self._capture_structural_snapshot()
        self._runtime.seed_snapshot(self._build_persisted_snapshot())
        local_spk = self.local_speaker
        if not (local_spk or esphome_service(self.hass, self.esphome_device_id, "set_browse_slots")):
            self.active_speaker = self.last_speaker = ""
        else:
            if not self.active_speaker:
                self.active_speaker = local_spk
            enforce_local_speaker_if_remote_idle(self, "ha_startup")
            if not self.last_speaker:
                self.last_speaker = self.active_speaker
        proxy_areas = get_ble_proxy_area_ids(self.hass)
        if self.native_ble_tracking_enabled and not str(self.get_opt(CONF_DEFAULT_AREA) or "").strip():
            if self.active_area_id and proxy_areas and self.active_area_id not in proxy_areas:
                self.active_area_id = None
        elif not self.active_area_id and (dev := get_bound_esphome_device(self.hass, self.esphome_device_id)) and dev.area_id:
            self.active_area_id = dev.area_id
        self._bind_all_listeners()
        self._unsub_core_config = self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, self._async_on_core_config_update)
        sync_coordinator_ble_tracker(self)
        if not self.is_ble_tag:
            self._rpc_receiver.start()
            await self.async_push_beacon_uuid()
            if (sys_obj := get_latter_system(self.hass)) is not None:
                sys_obj.bind_feed_listeners()
                if sys_obj.weather_loaded:
                    self.apply_weather_snapshot(sys_obj.weather_entity, sys_obj.weather_snapshot)
                else:
                    await self.async_refresh_weather_forecast()
                if sys_obj.calendar_loaded:
                    self.apply_calendar_snapshot(sys_obj.calendar_records, sys_obj.calendar_raw_rows)
                else:
                    await self.async_refresh_calendar_agenda()
            else:
                await self.async_refresh_weather_forecast()
                await self.async_refresh_calendar_agenda()
        await self.async_sync_presence_beacon("options")
        try:
            from .repairs import async_audit_coordinator_health

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
            self.get_opt(CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION)
        )
        sync_coordinator_ble_tracker(self)
        target_def_spk = str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() or self.local_speaker
        if self.local_speaker and target_def_spk and self.is_local_speaker_entity(target_def_spk):
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

    async def async_on_global_config_updated(self, changed_keys: set[str] | None = None) -> None:
        if self._ble_tracker is not None:
            self._ble_tracker.set_area_offsets(self.ble_area_offsets)
        self._bind_all_listeners()
        if not self.is_ble_tag:
            if changed_keys is None or CONF_SYSTEM_BLE_UUID in changed_keys:
                await self.async_push_beacon_uuid()
            sys_obj = get_latter_system(self.hass)
            if changed_keys is None or CONF_WEATHER_ENTITY in changed_keys:
                await (sys_obj.async_refresh_weather_forecast(coalesce=True) if sys_obj else self.async_refresh_weather_forecast())
            if changed_keys is None or CONF_CALENDAR_ENTITIES in changed_keys:
                await (sys_obj.async_refresh_calendar_agenda(coalesce=True) if sys_obj else self.async_refresh_calendar_agenda())
        self.async_notify_listeners()

    @callback
    def _bind_all_listeners(self) -> None:
        if self.is_ble_tag:
            return
        bind_coordinator_speaker_listener(self)
        bind_coordinator_area_listeners(self)
        bind_coordinator_doorbell_listener(self)
        bind_coordinator_wallpaper_cycle_timer(self)

    @callback
    def _bind_wallpaper_cycle_timer(self) -> None:
        bind_coordinator_wallpaper_cycle_timer(self)

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
            "_unsub_core_config", "_unsub_speaker_state", "_unsub_alarm_state", "_unsub_remotes_state",
            "_unsub_area_entities_state", "_unsub_area_debounce", "_unsub_wallpaper_timer", "_unsub_doorbell_ring_state",
        ):
            if (unsub := getattr(self, attr, None)) is not None:
                unsub()
                setattr(self, attr, None)

    @property
    def doorbell_ring_map(self) -> dict[str, str]:
        return dict(self._doorbell_ring_map)

    async def async_sync_presence_beacon(self, trigger: Trigger) -> None:
        await async_sync_coordinator_presence_beacon(self, trigger)

    async def async_handle_device_hello(self, contract: int, boot_id: str, manifest_raw: str) -> None:
        _ = contract
        is_new_boot, parsed = self._runtime.apply_device_hello(boot_id, manifest_raw)
        if parsed is not None:
            if self._ble_tracker is not None:
                self._ble_tracker.update_manifest_beacon(parsed.get("beacon"))
            apply_coordinator_device_health(self, parsed, str(boot_id or "").strip())
        if is_new_boot:
            self._local_needs_cold_resume = True
        self._last_pushed_v3.clear()
        self.force_republish_all_domains()
        await self.async_push_beacon_uuid()
        await async_handle_coordinator_reconnect(self)
        await self.async_sync_presence_beacon("hello")

    async def async_execute_media_command(
        self, command: str, speaker: str | None = None, seek_position: float | None = None, media_id: str | None = None,
        media_type: str | None = None, enqueue: str | None = None, group_members: list[str] | str | None = None,
    ) -> None:
        await execute_coordinator_media_command(self, command, speaker, seek_position, media_id, media_type, enqueue, group_members)

    @callback
    def async_set_active_speaker(self, speaker_entity_id: str, transfer_queue: bool = True) -> None:
        set_coordinator_active_speaker(self, speaker_entity_id, transfer_queue=transfer_queue)

    def is_device_away(self) -> bool:
        return compute_is_device_away(
            self.hass, native_ble_tracking_enabled=self.native_ble_tracking_enabled,
            ble_tracker=self._ble_tracker, is_ble_tag=self.is_ble_tag, esphome_device_id=self.esphome_device_id,
        )

    def get_current_area_and_distance(self) -> tuple[str, dict[str, Any]]:
        return compute_current_area_and_distance(
            self.hass, away=self.is_device_away(), native_ble_tracking_enabled=self.native_ble_tracking_enabled,
            ble_tracker=self._ble_tracker, active_area_id=self.active_area_id,
            explicit_default_area=str(self.get_opt(CONF_DEFAULT_AREA) or "").strip(), assigned_person=self.assigned_person,
        )

    @callback
    def _async_on_native_ble_area_detected(self, area_id: str, scanner_source: str) -> None:
        on_native_ble_area_detected(self, area_id, scanner_source)

    def get_person_area_and_distance(self, person_entity: str) -> tuple[str, dict[str, Any]]:
        return resolve_person_area_and_distance(self.hass, person_entity)

    def _pack_domain_payload(self, domain: str, *fields: Any) -> tuple[int, str]:
        cur_rev, packed = self._packer.pack(domain, *fields)
        self.rev = max(self.rev, self._packer.rev)
        return cur_rev, packed

    async def async_push_beacon_uuid(self) -> None:
        if self.is_ble_tag or not (svc := esphome_service(self.hass, self.esphome_device_id, "latter_set_beacon_uuid")):
            return
        try:
            await self.hass.services.async_call("esphome", svc, {"uuid": self.ble_beacon_uuid}, blocking=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("esphome.%s failed: %s", svc, err)

    async def async_push_dirty_v3_domains(self) -> None:
        await async_push_coordinator_v3_domains(self)

    @callback
    def force_republish_all_domains(self) -> None:
        force_republish_coordinator_domains(self)

    async def _async_debounced_notify(self) -> None:
        self.async_update_listeners()
        await self.async_push_dirty_v3_domains()

    @callback
    def async_notify_listeners(self) -> None:
        self._cached_media_payload = self._cached_area_payload = self._cached_remote_payload = None
        self._schedule_persist_runtime_state()
        self._notify_debouncer.async_schedule_call()

    @callback
    def async_set_active_area(
        self, area_id_or_name: str, handoff_media: bool | None = None, sync_device_registry: bool = False, ble_driven: bool = False
    ) -> None:
        set_coordinator_active_area(
            self, area_id_or_name, handoff_media=handoff_media, sync_device_registry=sync_device_registry, ble_driven=ble_driven
        )

    def get_effective_remote_entities_for_device(self) -> list[str]:
        return resolve_effective_remote_entities(
            self.hass, all_inventory=self.get_remote_entities_list(), groups=self.remote_groups,
            mode=self.device_remote_group, cur_area=(self.active_area_id or str(self.get_opt(CONF_DEFAULT_AREA) or "")).strip(),
        )

    def get_remote_slots(self) -> list[dict[str, str]]:
        return [resolve_remote_slot_pair(self.hass, eid) for eid in self.get_effective_remote_entities_for_device()[:10]]

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
    def apply_calendar_snapshot(self, records: V3Records, raw_rows: list[dict[str, Any]]) -> None:
        apply_coordinator_calendar_snapshot(self, records, raw_rows)

    async def async_refresh_calendar_agenda(self, days: int = 30) -> None:
        await async_refresh_coordinator_calendar(self, days=days)

    def get_calendar_agenda_payload(self) -> tuple[int, dict[str, Any]]:
        return build_calendar_agenda_payload(self)

    @callback
    def apply_weather_snapshot(self, weather_ent: str | None, snap: tuple[V3Records, dict[str, Any]] | None) -> None:
        apply_coordinator_weather_snapshot(self, weather_ent, snap)

    async def async_refresh_weather_forecast(self) -> None:
        await async_refresh_coordinator_weather(self)
