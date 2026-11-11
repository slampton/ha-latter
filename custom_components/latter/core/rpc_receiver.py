"""Bound ESPHome RPC Outbox listener (`System: RPC Outbox`) for zero-privilege Device -> HA RPC."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .identity import find_device_entity_by_suffix
from .rpc_protocol import RpcReassembler

if TYPE_CHECKING:
    from .device_coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

RPC_OUTBOX_SUFFIXES: tuple[str, ...] = ("_system_rpc_outbox", "_rpc_outbox")


class LatterRpcReceiver:
    """Watches a bound ESPHome Device's `System: RPC Outbox` entity and dispatches authenticated RPCs."""

    def __init__(self, hass: HomeAssistant, coordinator: LatterCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._reassembler = RpcReassembler()
        self._tracked_entity_id: str | None = None
        self._unsub_state: Callable[[], None] | None = None
        self._unsub_ent_reg: Callable[[], None] | None = None

    @callback
    def start(self) -> None:
        """Bind to the Device's RPC outbox entity and track entity-registry rebinds."""
        self.rebind()
        if self._unsub_ent_reg is None:
            self._unsub_ent_reg = self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                self._async_on_entity_registry_updated,
            )

    @callback
    def stop(self) -> None:
        """Unsubscribe all listeners."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_ent_reg is not None:
            self._unsub_ent_reg()
            self._unsub_ent_reg = None
        self._tracked_entity_id = None

    @callback
    def rebind(self) -> None:
        """Resolve the bound ESPHome Device's RPC outbox `text_sensor` and subscribe if changed."""
        if self.coordinator.is_ble_tag:
            self.stop()
            return
        dev_id = self.coordinator.esphome_device_id
        ent_id = (
            find_device_entity_by_suffix(
                self.hass,
                dev_id,
                "text_sensor",
                RPC_OUTBOX_SUFFIXES,
            )
            if dev_id
            else None
        )
        if ent_id == self._tracked_entity_id:
            return
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        self._tracked_entity_id = ent_id
        if not ent_id:
            return

        self._unsub_state = async_track_state_change_event(
            self.hass,
            [ent_id],
            self._async_on_outbox_state_change,
        )
        st = self.hass.states.get(ent_id)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            self._ingest_raw_state(st.state)

    @callback
    def _async_on_entity_registry_updated(self, event: Event[Any]) -> None:
        action = event.data.get("action")
        if action not in ("create", "update", "remove"):
            return
        ent_id = str(event.data.get("entity_id") or "")
        if ent_id == self._tracked_entity_id or any(
            ent_id.endswith(sfx) for sfx in RPC_OUTBOX_SUFFIXES
        ):
            self.rebind()

    @callback
    def _async_on_outbox_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            return
        self._ingest_raw_state(new_state.state)

    @callback
    def _ingest_raw_state(self, raw: str) -> None:
        decoded = self._reassembler.feed(raw)
        if decoded is None:
            return
        svc_name, data = decoded
        from ..services import async_dispatch_bound_rpc

        self.hass.async_create_task(
            self._async_safe_dispatch(async_dispatch_bound_rpc, svc_name, data),
            f"latter_rpc_{self.coordinator.device_slug}_{svc_name}",
        )

    async def _async_safe_dispatch(
        self,
        dispatcher: Callable[..., Any],
        svc_name: str,
        data: dict[str, Any],
    ) -> None:
        try:
            await dispatcher(self.hass, self.coordinator, svc_name, data)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Bound RPC '%s' from device '%s' failed: %s",
                svc_name,
                self.coordinator.device_slug,
                err,
            )
