"""Per-device area resolution, BLE dwell ('Voice Follows Me'), and remote slot controller."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import time
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.event import async_call_later

from .area_engine import resolve_remote_slot_pair, sync_esphome_device_area
from .area_follow import AreaFollowDwell, FollowAction
from .ble_engine import LatterNativeBleTracker
from .identity import find_device_entity_by_suffix


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
    device_profile: str,
    esphome_device_id: str | None,
    device_slug: str,
) -> bool:
    """Return True if a roaming BLE device has timed out across all proxies and is not awake on Wi-Fi."""
    if not native_ble_tracking_enabled or ble_tracker is None:
        return False
    if not ble_tracker.is_away:
        return False
    if device_profile == "ble_beacon":
        return True
    wifi_ent_id = find_device_entity_by_suffix(
        hass,
        esphome_device_id,
        "sensor",
        ("_wi_fi_signal", "_wifi_signal", "_ip_address"),
    )
    wifi_st = (
        hass.states.get(wifi_ent_id)
        if wifi_ent_id
        else (
            hass.states.get(f"sensor.{device_slug}_wi_fi_signal")
            or hass.states.get(f"sensor.{device_slug}_wifi_signal")
            or hass.states.get(f"sensor.{device_slug}_ip_address")
        )
    )
    if wifi_st is not None and wifi_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        return False
    return True


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
                for eid, r in zip(all_inventory, resolved_all)
                if r.get("area_id") == cur_area
            ][:10]

    if not groups:
        return all_inventory[:10]
    return []
