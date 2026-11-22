"""Dwell-gated Voice Follows Me controller for bound ESPHome Device Area updates."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import time
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from ..areas.sync import sync_esphome_device_area
from ..presence.ble_math import AreaFollowDwell, FollowAction


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
