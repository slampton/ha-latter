"""Dwell-gated Voice Follows Me controller and active Area resolution (`L3`)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
import time
from typing import Any

from homeassistant.const import STATE_PLAYING
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.event import async_call_later

from ..areas.catalogs import find_area_media_entities
from ..areas.registry import (
    match_area_by_name_or_id,
    resolve_active_area_entry,
)
from ..areas.sync import sync_esphome_device_area
from ..areas.telemetry import bind_coordinator_area_listeners
from ..const import (
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_ATTENUATION,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_AWAY_TIMEOUT_S,
    CONF_BLE_CATEGORY,
    CONF_BLE_MAX_RADIUS_M,
    CONF_BLE_MAX_VELOCITY_MPS,
    CONF_BLE_REF_POWER,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_SYNC_DEVICE_AREA,
    DEFAULT_AREA_FOLLOW_DWELL_S,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_BLE_ATTENUATION,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_BLE_AWAY_TIMEOUT_S,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_BLE_MAX_RADIUS_M,
    DEFAULT_BLE_MAX_VELOCITY_MPS,
    DEFAULT_SYNC_DEVICE_AREA,
    EVENT_LATTER,
)
from ..identity import get_bound_esphome_device
from ..presence.ble_discovery import classify_ble_target_category
from ..presence.ble_math import TX_POWER_1M_DBM, AreaFollowDwell, FollowAction
from ..presence.ble_registry import resolve_floor_info
from .wallpaper_scheduler import CoordinatorWallpaperMixin

_LOGGER = logging.getLogger(__name__)

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


class CoordinatorAreaFollowMixin(CoordinatorWallpaperMixin):
    """Active Area state, BLE spatial parameters, metric distance summary, and Area handoff."""

    _area_follow: LatterAreaFollowController

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
