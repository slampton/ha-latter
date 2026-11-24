"""Chunked `System: RPC Outbox` wire-frame parser, reassembler, and bound listener."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
import json
import logging
import time

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from ..coordinator import LatterCoordinator, register_rpc_receiver_factory
from ..identity import find_device_entity_by_suffix
from .rpc_dispatcher import async_dispatch_bound_rpc

_LOGGER = logging.getLogger(__name__)

MAX_RPC_PARTS: int = 32
MAX_RPC_BYTES: int = 8192
PARTIAL_TTL_SECONDS: float = 15.0
DEDUP_HISTORY_LIMIT: int = 64

_HEADER_PARTS_COUNT: int = 3
_MAX_BOOT_ID_HEX_LEN: int = 16
_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdefABCDEF")

RPC_OUTBOX_SUFFIXES: tuple[str, ...] = ("_system_rpc_outbox", "_rpc_outbox")
RPC_OUTBOX_ORIGINAL_NAMES: tuple[str, ...] = ("System: RPC Outbox", "RPC Outbox")
RPC_OUTBOX_UNIQUE_ID_SUFFIXES: tuple[str, ...] = ("/text_sensor/System: RPC Outbox",)


@dataclass(slots=True)
class RpcFrame:
    """One parsed chunk from `System: RPC Outbox`."""

    boot_id: str
    seq: int
    part: int
    total: int
    payload_slice: str


@dataclass(slots=True)
class _PartialMessage:
    """In-flight multi-part RPC envelope awaiting remaining chunks."""

    total: int
    created_mono: float
    byte_len: int = 0
    parts: dict[int, str] = field(default_factory=dict)


def _parse_header_fields(header: str) -> tuple[str, int, int, int] | None:
    """Parse `<boot_hex>:<seq>:<part>/<total>` header fields, or return None on malformed input."""
    hparts = header.split(":")
    if len(hparts) != _HEADER_PARTS_COUNT:
        return None
    boot_id, seq_s, frac_s = hparts
    if (
        not boot_id
        or len(boot_id) > _MAX_BOOT_ID_HEX_LEN
        or "/" not in frac_s
        or not all(c in _HEX_CHARS for c in boot_id)
    ):
        return None
    part_s, total_s = frac_s.split("/", 1)
    if not (seq_s.isdigit() and part_s.isdigit() and total_s.isdigit()):
        return None
    seq, part, total = int(seq_s), int(part_s), int(total_s)
    if seq <= 0 or total < 1 or total > MAX_RPC_PARTS or part < 1 or part > total:
        return None
    return boot_id.lower(), seq, part, total


def parse_rpc_frame(raw: str | None) -> RpcFrame | None:
    """Parse `<boot_hex>:<seq>:<part>/<total>|<json_slice>`, or return None on malformed input."""
    if not raw or not isinstance(raw, str) or "|" not in raw:
        return None
    header, body = raw.split("|", 1)
    parsed_hdr = _parse_header_fields(header)
    if parsed_hdr is None or len(body.encode("utf-8")) > MAX_RPC_BYTES:
        return None
    boot_id, seq, part, total = parsed_hdr
    return RpcFrame(
        boot_id=boot_id,
        seq=seq,
        part=part,
        total=total,
        payload_slice=body,
    )


def _decode_envelope(assembled: str) -> tuple[str, dict[str, object]] | None:
    """Decode `{"s": "<service>", "d": {...}}` into `(service_name, data_dict)`."""
    try:
        parsed = json.loads(assembled)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    svc = str(parsed.get("s") or "").strip()
    if not svc or not svc.isascii():
        return None
    svc = svc.removeprefix("latter.")
    data = parsed.get("d")
    if data is None:
        return svc, {}
    if not isinstance(data, dict):
        return None
    return svc, dict(data)


class RpcReassembler:
    """Per-Device bounded multi-part RPC reassembler with `(boot_id, seq)` replay protection."""

    def __init__(self) -> None:
        self._inflight: dict[tuple[str, int], _PartialMessage] = {}
        self._completed: OrderedDict[tuple[str, int], None] = OrderedDict()
        self._last_boot_id: str = ""

    def _prune(self, now_mono: float) -> None:
        expired = [
            key
            for key, partial in self._inflight.items()
            if (now_mono - partial.created_mono) > PARTIAL_TTL_SECONDS
        ]
        for key in expired:
            self._inflight.pop(key, None)

    def _ingest_multipart(
        self, frame: RpcFrame, msg_key: tuple[str, int], now: float
    ) -> str | None:
        """Accumulate one multipart slice and return the assembled payload when complete."""
        partial = self._inflight.get(msg_key)
        if partial is None or partial.total != frame.total:
            partial = _PartialMessage(total=frame.total, created_mono=now)
            self._inflight[msg_key] = partial

        if frame.part not in partial.parts:
            slice_bytes = len(frame.payload_slice.encode("utf-8"))
            if partial.byte_len + slice_bytes > MAX_RPC_BYTES:
                self._inflight.pop(msg_key, None)
                return None
            partial.parts[frame.part] = frame.payload_slice
            partial.byte_len += slice_bytes

        if len(partial.parts) < partial.total:
            return None

        self._inflight.pop(msg_key, None)
        return "".join(partial.parts[idx] for idx in range(1, partial.total + 1))

    def feed(
        self, raw: str | None, *, now_mono: float | None = None
    ) -> tuple[str, dict[str, object]] | None:
        """Ingest one `text_sensor` state string; return `(service, data)` once complete and valid."""
        frame = parse_rpc_frame(raw)
        if frame is None:
            return None

        now = time.monotonic() if now_mono is None else float(now_mono)
        if self._last_boot_id and frame.boot_id != self._last_boot_id:
            self._inflight.clear()
        self._last_boot_id = frame.boot_id
        self._prune(now)

        msg_key = (frame.boot_id, frame.seq)
        if msg_key in self._completed:
            return None

        if frame.total == 1:
            assembled: str | None = frame.payload_slice
        else:
            assembled = self._ingest_multipart(frame, msg_key, now)

        if assembled is None or len(assembled.encode("utf-8")) > MAX_RPC_BYTES:
            return None
        self._record_completed(msg_key)
        return _decode_envelope(assembled)

    def seed_silent(self, raw: str | None, *, now_mono: float | None = None) -> None:
        """Seed current `(boot_id, seq)` silently on `rebind()` without dispatching.

        Only final frames (`part == total`) mark `(boot_id, seq)` completed; mid-multipart
        slices (`part < total`) are staged in `_inflight` so remaining parts still reassemble.
        """
        frame = parse_rpc_frame(raw)
        if frame is None:
            return
        if self._last_boot_id and frame.boot_id != self._last_boot_id:
            self._inflight.clear()
            self._completed.clear()
        self._last_boot_id = frame.boot_id
        msg_key = (frame.boot_id, frame.seq)
        if msg_key in self._completed:
            return
        if frame.part < frame.total:
            now = time.monotonic() if now_mono is None else float(now_mono)
            self._ingest_multipart(frame, msg_key, now)
            return
        self._record_completed(msg_key)

    def _record_completed(self, key: tuple[str, int]) -> None:
        self._completed[key] = None
        while len(self._completed) > DEDUP_HISTORY_LIMIT:
            self._completed.popitem(last=False)


class LatterRpcReceiver:
    """Watches a bound ESPHome Device's `System: RPC Outbox` entity and dispatches authenticated RPCs."""

    def __init__(self, hass: HomeAssistant, coordinator: LatterCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._reassembler = RpcReassembler()
        self._tracked_entity_id: str | None = None
        self._was_unavailable: bool = False
        self._unsub_state: Callable[[], None] | None = None
        self._unsub_ent_reg: Callable[[], None] | None = None
        coordinator.attach_rpc_receiver(self)

    @property
    def tracked_entity_id(self) -> str | None:
        """Return the currently bound `System: RPC Outbox` entity_id, or None."""
        return self._tracked_entity_id

    def is_device_unavailable(self) -> bool:
        """Return True when the bound RPC outbox entity exists in HA and reports `unavailable`."""
        if not self._tracked_entity_id:
            return False
        st = self.hass.states.get(self._tracked_entity_id)
        return st is not None and st.state == STATE_UNAVAILABLE

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
        self._was_unavailable = False

    @callback
    def rebind(self) -> None:
        """Resolve the bound ESPHome Device's RPC outbox `sensor` entity and subscribe if changed."""
        if self.coordinator.is_ble_tag:
            self.stop()
            return
        dev_id = self.coordinator.esphome_device_id
        ent_id = (
            find_device_entity_by_suffix(
                self.hass,
                dev_id,
                "sensor",
                RPC_OUTBOX_SUFFIXES,
                original_names=RPC_OUTBOX_ORIGINAL_NAMES,
                unique_id_suffixes=RPC_OUTBOX_UNIQUE_ID_SUFFIXES,
            )
            if dev_id
            else None
        )
        if ent_id:
            ent_reg = er.async_get(self.hass)
            reg_entry = ent_reg.async_get(ent_id)
            if reg_entry is not None and reg_entry.hidden_by is None:
                ent_reg.async_update_entity(
                    ent_id, hidden_by=er.RegistryEntryHider.INTEGRATION
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
        if st is not None:
            self._was_unavailable = st.state == STATE_UNAVAILABLE
            if st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
                self._reassembler.seed_silent(st.state)

    @callback
    def _async_on_entity_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        action = event.data.get("action")
        if action not in ("create", "update", "remove"):
            return
        ent_id = str(event.data.get("entity_id") or "")
        old_ent_id = str(event.data.get("old_entity_id") or "")
        if (
            self._tracked_entity_id is None
            or ent_id == self._tracked_entity_id
            or (old_ent_id and old_ent_id == self._tracked_entity_id)
            or ent_id.endswith(RPC_OUTBOX_SUFFIXES)
        ):
            self.rebind()

    @callback
    def _async_on_outbox_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        if new_state.state == STATE_UNAVAILABLE:
            if not self._was_unavailable:
                self._was_unavailable = True
                _LOGGER.info(
                    "Latter device '%s' is unavailable",
                    self.coordinator.device_slug,
                )
            self.coordinator.on_transport_disconnected()
            return
        was_unavail = self._was_unavailable or (
            old_state is not None and old_state.state == STATE_UNAVAILABLE
        )
        decoded: tuple[str, dict[str, object]] | None = None
        if new_state.state not in (STATE_UNKNOWN, ""):
            decoded = self._reassembler.feed(new_state.state)
        if was_unavail:
            self._was_unavailable = False
            _LOGGER.info(
                "Latter device '%s' reconnected",
                self.coordinator.device_slug,
            )
            if decoded is not None and decoded[0] == "device_hello":
                self.coordinator.clear_last_pushed_v3()
                self.coordinator.async_update_listeners()
            else:
                self.coordinator.on_transport_reconnected()
        if decoded is not None:
            self._dispatch_decoded(decoded)

    @callback
    def _dispatch_decoded(self, decoded: tuple[str, dict[str, object]]) -> None:
        svc_name, data = decoded
        self.coordinator.create_background_task(
            self._async_safe_dispatch(svc_name, data),
            f"latter_rpc_{self.coordinator.device_slug}_{svc_name}",
        )

    @callback
    def _ingest_raw_state(self, raw: str) -> None:
        decoded = self._reassembler.feed(raw)
        if decoded is not None:
            self._dispatch_decoded(decoded)

    async def _async_safe_dispatch(
        self,
        svc_name: str,
        data: dict[str, object],
    ) -> None:
        try:
            await async_dispatch_bound_rpc(self.hass, self.coordinator, svc_name, data)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Bound RPC '%s' from device '%s' failed: %s",
                svc_name,
                self.coordinator.device_slug,
                err,
            )


register_rpc_receiver_factory(LatterRpcReceiver)
