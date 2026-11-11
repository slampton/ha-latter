"""Per-device Area controller, Voice Follows Me dwell, BLE tracker sync, and health audit."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, EVENT_LATTER
from ..core.health import ISSUE_ROLLED_BACK, evaluate_device_health, parse_device_health
from ..core.identity import find_device_entity_by_suffix
from ..core.issue_ids import device_health_issue_id
from ..presence.area_follow import (
    AreaFollowDwell,
    FollowAction,
    Trigger,
    decide_beacon_action,
)
from ..presence.ble_fabric import LatterNativeBleTracker
from .context_builder import (
    bind_coordinator_area_listeners,
    find_area_media_entities,
    match_area_by_name_or_id,
    resolve_remote_slot_pair,
    sync_esphome_device_area,
)

_LOGGER = logging.getLogger(__name__)


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
                if self._dwell.take_due(target_area_id, time.monotonic()) and is_allowed_cb():
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


def compute_is_device_away(
    hass: HomeAssistant,
    *,
    native_ble_tracking_enabled: bool,
    ble_tracker: LatterNativeBleTracker | None,
    is_ble_tag: bool,
    esphome_device_id: str | None,
) -> bool:
    """Return True if a roaming BLE device has timed out across all proxies and is not awake on Wi-Fi."""
    if not native_ble_tracking_enabled or ble_tracker is None:
        return False
    if not ble_tracker.is_away:
        return False
    if is_ble_tag:
        return True
    wifi_ent_id = find_device_entity_by_suffix(
        hass,
        esphome_device_id,
        "sensor",
        ("_wi_fi_signal", "_wifi_signal", "_ip_address"),
    )
    wifi_st = hass.states.get(wifi_ent_id) if wifi_ent_id else None
    return not (wifi_st is not None and wifi_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""))


def compute_current_area_and_distance(
    hass: HomeAssistant,
    *,
    away: bool,
    native_ble_tracking_enabled: bool,
    ble_tracker: LatterNativeBleTracker | None,
    active_area_id: str | None,
    explicit_default_area: str,
    assigned_person: str,
) -> tuple[str, dict[str, Any]]:
    """Return (area_or_away_state, attributes) for sensor.<slug>_current_area and sensor.<slug>_ble_distance."""
    area_reg = ar.async_get(hass)
    if native_ble_tracking_enabled:
        ble_area_id = (
            ble_tracker.current_area_id
            if (ble_tracker is not None and not away)
            else None
        ) or (explicit_default_area if not away else None)
        area_entry = area_reg.async_get_area(ble_area_id) if ble_area_id else None
        if away:
            area_state = "Away"
        elif area_entry is not None:
            area_state = area_entry.name
        else:
            area_state = "Unassigned"
        eff_area_id = ble_area_id or ""
    else:
        eff_area_id = "" if away else (active_area_id or explicit_default_area)
        area_entry = area_reg.async_get_area(eff_area_id) if eff_area_id else None
        area_state = "Away" if away else (area_entry.name if area_entry else "Unassigned")

    dist_ft = ble_tracker.winning_distance_ft if (ble_tracker and not away and eff_area_id) else None
    dist_m = ble_tracker.winning_distance_m if (ble_tracker and not away and eff_area_id) else None
    rssi = ble_tracker.winning_rssi if (ble_tracker and not away and eff_area_id) else None
    proxy = ble_tracker.closest_scanner if (ble_tracker and not away and eff_area_id) else ""
    return area_state, {
        "area_id": eff_area_id,
        "area_name": area_state,
        "is_home": not away,
        "closest_proxy": proxy,
        "distance_ft": dist_ft,
        "distance_m": dist_m,
        "rssi": rssi,
        "assigned_person": assigned_person,
    }


def resolve_effective_remote_entities(
    hass: HomeAssistant,
    *,
    all_inventory: list[str],
    groups: list[dict[str, Any]],
    mode: str,
    cur_area: str,
) -> list[str]:
    """Resolve the ordered list of remote entities for a device (Static Group vs Active Area vs All)."""
    if mode.startswith("group:"):
        gid = mode.split(":", 1)[1].strip()
        matched_grp = next((g for g in groups if g["id"] == gid), None)
        if matched_grp is not None:
            return list(matched_grp.get("remotes") or [])[:10]
        return []

    if mode == "all":
        return all_inventory[:10]

    if cur_area:
        area_group_remotes: list[str] = []
        for grp in groups:
            if grp.get("area_id") == cur_area:
                for rem_id in grp.get("remotes") or []:
                    if rem_id not in area_group_remotes:
                        area_group_remotes.append(rem_id)
        if area_group_remotes:
            return area_group_remotes[:10]

        if groups:
            return []

        resolved_all = [resolve_remote_slot_pair(hass, eid) for eid in all_inventory]
        any_has_area = any(bool(r.get("area_id")) for r in resolved_all)
        if any_has_area:
            return [
                eid
                for eid, r in zip(all_inventory, resolved_all, strict=False)
                if r.get("area_id") == cur_area
            ][:10]

    if not groups:
        return all_inventory[:10]
    return []


def resolve_person_area_and_distance(
    hass: HomeAssistant, person_entity: str
) -> tuple[str, dict[str, Any]]:
    """Resolve the freshest area and BLE distance across all Latter devices carried by a person."""
    from ..core.device_coordinator import LatterCoordinator
    from ..core.hub import get_latter_system

    sys_obj = get_latter_system(hass)
    domain_data = hass.data.get(DOMAIN, {})
    pool_raw = (
        list(sys_obj.coordinators.values())
        if sys_obj is not None and sys_obj.coordinators
        else (list(domain_data.values()) if isinstance(domain_data, dict) else [])
    )
    target_low = str(person_entity or "").strip().lower()
    p_coords = [
        v
        for v in pool_raw
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


@callback
def set_coordinator_active_area(
    coordinator: Any,
    area_id_or_name: str,
    handoff_media: bool | None = None,
    sync_device_registry: bool = False,
    ble_driven: bool = False,
) -> None:
    """Switch active area, persist to Store, sync ESPHome device area, and hand off media."""
    matched_id = match_area_by_name_or_id(coordinator.hass, area_id_or_name)
    if not matched_id:
        return
    prev_area = coordinator.active_area_id
    coordinator.active_area_id = matched_id
    if prev_area != matched_id:
        coordinator.hass.bus.async_fire(
            EVENT_LATTER,
            {
                "type": "area_changed",
                "device_slug": coordinator.device_slug,
                "previous_area_id": prev_area or "",
                "area_id": matched_id,
                "assigned_person": coordinator.assigned_person,
            },
        )

    if coordinator.is_ble_tag:
        coordinator._schedule_persist_runtime_state()
        coordinator.async_notify_listeners()
        return

    if sync_device_registry:
        coordinator._area_follow.schedule_or_commit(
            esphome_device_id=coordinator.esphome_device_id,
            target_area_id=matched_id,
            ble_driven=ble_driven,
            dwell_s=coordinator.area_follow_dwell_s,
            is_allowed_cb=lambda: (
                coordinator.active_area_id == matched_id
                and not coordinator.is_device_away()
                and coordinator.sync_device_area_enabled
                and bool(coordinator.esphome_device_id)
            ),
        )
    else:
        coordinator._area_follow.cancel()

    media_map = find_area_media_entities(
        coordinator.hass, matched_id, coordinator.local_speaker
    )
    if media_map["remote"]:
        coordinator.active_remote = media_map["remote"]

    coordinator.active_remote_slot = 1
    for slot_idx, slot_info in enumerate(coordinator.get_remote_slots(), start=1):
        if slot_info["area_id"] == matched_id:
            coordinator.active_remote_slot = slot_idx
            break
    bind_coordinator_area_listeners(coordinator)
    coordinator._schedule_persist_runtime_state()

    do_handoff = (
        coordinator.area_handoff_enabled
        if handoff_media is None
        else bool(handoff_media)
    )
    if do_handoff and media_map["speaker"]:
        prev_state = coordinator.hass.states.get(coordinator.active_speaker)
        auto_transfer = bool(
            sync_device_registry
            and prev_state
            and prev_state.state == STATE_PLAYING
            and coordinator.active_speaker != coordinator.local_speaker
        )
        coordinator.async_set_active_speaker(
            media_map["speaker"], transfer_queue=auto_transfer
        )
    else:
        coordinator.async_notify_listeners()

    if coordinator.on_area_changed_push_slots is not None:
        coordinator.entry.async_create_background_task(
            coordinator.hass,
            coordinator.on_area_changed_push_slots(coordinator),
            f"latter_area_change_slots_{coordinator.device_slug}",
        )


async def async_handle_coordinator_reconnect(coordinator: Any) -> None:
    """Reset idle remote speaker, sync BLE area lock, and push active area slots after ESPHome boot/wake."""
    from ..media.player_controller import enforce_local_speaker_if_remote_idle

    enforce_local_speaker_if_remote_idle(coordinator, "device_reconnect")
    if coordinator._ble_tracker is not None:
        coordinator._ble_tracker.reset_for_device_wake()
        if (
            coordinator._ble_tracker.current_area_id
            and coordinator._ble_tracker.current_area_id != coordinator.active_area_id
        ):
            coordinator.async_set_active_area(
                coordinator._ble_tracker.current_area_id,
                handoff_media=False,
                sync_device_registry=True,
                ble_driven=True,
            )
    coordinator.async_notify_listeners()
    await asyncio.sleep(1.5)
    enforce_local_speaker_if_remote_idle(coordinator, "device_reconnect_post_delay")
    if (
        coordinator._ble_tracker is not None
        and coordinator._ble_tracker.current_area_id
        and coordinator._ble_tracker.current_area_id != coordinator.active_area_id
    ):
        coordinator.async_set_active_area(
            coordinator._ble_tracker.current_area_id,
            handoff_media=False,
            sync_device_registry=True,
            ble_driven=True,
        )
    coordinator.async_notify_listeners()
    if coordinator.on_area_changed_push_slots is not None:
        await coordinator.on_area_changed_push_slots(coordinator)


@callback
def on_native_ble_area_detected(
    coordinator: Any, area_id: str, scanner_source: str
) -> None:
    """Handle area transition or Away timeout detected by Latter's BLE proxy tracker."""
    if area_id == "away":
        coordinator._area_follow.cancel()
        coordinator.async_notify_listeners()
        return
    if not coordinator.ble_auto_switch_enabled:
        coordinator.async_notify_listeners()
        return
    if area_id and area_id != coordinator.active_area_id:
        _LOGGER.info(
            "Native BLE Proxy ('%s') detected '%s' in area '%s' (was '%s')",
            scanner_source,
            coordinator.device_slug,
            area_id,
            coordinator.active_area_id,
        )
        coordinator.async_set_active_area(
            area_id,
            sync_device_registry=True,
            ble_driven=True,
        )
    else:
        coordinator.async_notify_listeners()


async def async_sync_coordinator_presence_beacon(
    coordinator: Any, trigger: Trigger
) -> None:
    """Turn the bound device's BLE presence beacon switch on or off per `decide_beacon_action`."""
    if coordinator.is_ble_tag:
        return
    switch_ent = coordinator.device_entity(
        "switch", "_area_ble_presence_beacon", "_ble_presence_beacon"
    )
    if not switch_ent:
        return
    state = coordinator.hass.states.get(switch_ent)
    action = decide_beacon_action(
        coordinator.native_ble_tracking_enabled,
        state.state if state is not None else None,
        trigger,
    )
    if action is None:
        return
    try:
        await coordinator.hass.services.async_call(
            "switch", action, {ATTR_ENTITY_ID: switch_ent}, blocking=True
        )
        _LOGGER.info(
            "Presence beacon of '%s': %s (%s, native BLE tracking %s)",
            coordinator.device_slug,
            action,
            trigger,
            "on" if coordinator.native_ble_tracking_enabled else "off",
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Couldn't %s the presence beacon of '%s': %s",
            action.replace("_", " "),
            coordinator.device_slug,
            err,
        )


@callback
def sync_coordinator_ble_tracker(coordinator: Any) -> None:
    """Start, reconfigure, or stop `coordinator._ble_tracker` per current device options."""
    if coordinator.native_ble_tracking_enabled:
        if coordinator._ble_tracker is not None:
            if (
                getattr(
                    coordinator._ble_tracker,
                    "beacon_uuid",
                    coordinator.ble_beacon_uuid,
                )
                != coordinator.ble_beacon_uuid
                or getattr(
                    coordinator._ble_tracker,
                    "target_address",
                    coordinator.ble_target_address,
                )
                != coordinator.ble_target_address
            ):
                coordinator._ble_tracker.async_stop()
                coordinator._ble_tracker = None
            else:
                coordinator._ble_tracker.set_area_offsets(coordinator.ble_area_offsets)
        if coordinator._ble_tracker is None:
            coordinator._ble_tracker = LatterNativeBleTracker(
                hass=coordinator.hass,
                beacon_uuid=coordinator.ble_beacon_uuid,
                device_slug=coordinator.device_slug,
                on_area_detected=coordinator._async_on_native_ble_area_detected,
                area_offsets=coordinator.ble_area_offsets,
                target_address=coordinator.ble_target_address,
                esphome_device_id=coordinator.esphome_device_id,
                manifest_beacon=coordinator.hardware_manifest.get("beacon"),
            )
            coordinator._ble_tracker.async_start()
    elif coordinator._ble_tracker is not None:
        coordinator._ble_tracker.async_stop()
        coordinator._ble_tracker = None


@callback
def bind_coordinator_wallpaper_cycle_timer(coordinator: Any) -> None:
    """Start or stop the automatic favorite wallpaper rotation timer."""
    if coordinator._unsub_wallpaper_timer is not None:
        coordinator._unsub_wallpaper_timer()
        coordinator._unsub_wallpaper_timer = None

    mins = coordinator.wallpaper_cycle_minutes
    if (
        mins > 0
        and coordinator.wallpaper_source
        and len(coordinator.wallpaper_favorites) >= 2
    ):

        @callback
        def _on_wallpaper_tick(_now: datetime) -> None:
            favs = coordinator.wallpaper_favorites
            cur = coordinator.wallpaper_source
            if not cur or len(favs) < 2:
                return
            try:
                idx = (favs.index(cur) + 1) % len(favs)
            except ValueError:
                idx = 0
            coordinator.current_wallpaper = favs[idx]
            coordinator._schedule_persist_runtime_state()
            coordinator.async_notify_listeners()

        coordinator._unsub_wallpaper_timer = async_track_time_interval(
            coordinator.hass, _on_wallpaper_tick, timedelta(minutes=mins)
        )


@callback
def apply_coordinator_device_health(
    coordinator: Any, manifest: dict[str, Any], boot_id: str
) -> None:
    """Raise or clear crash, brownout, and rollback Repairs once per boot."""
    if (
        boot_id
        and coordinator.last_device_health is not None
        and coordinator.last_device_health.get("boot_id") == boot_id
    ):
        return
    health = parse_device_health(manifest)
    reported_at = dt_util.now().isoformat(timespec="seconds")
    coordinator.last_device_health = {
        "boot_id": boot_id,
        "sdk": health.sdk,
        "reset": health.reset,
        "crash": health.crash,
        "rollback": health.rollback,
        "reported_at": reported_at,
    }
    coordinator._schedule_persist_runtime_state()
    actions = evaluate_device_health(health)
    for kind in actions.delete_issues:
        ir.async_delete_issue(
            coordinator.hass,
            DOMAIN,
            device_health_issue_id(kind, coordinator.subentry_id),
        )
    for kind, extra in actions.raise_issues.items():
        ir.async_create_issue(
            coordinator.hass,
            DOMAIN,
            device_health_issue_id(kind, coordinator.subentry_id),
            is_fixable=True,
            severity=(
                ir.IssueSeverity.ERROR
                if kind == ISSUE_ROLLED_BACK
                else ir.IssueSeverity.WARNING
            ),
            translation_key=kind,
            translation_placeholders={
                "device": coordinator.device_title,
                "time": reported_at,
                **extra,
            },
            config_entry_id=coordinator.entry.entry_id,
        )
