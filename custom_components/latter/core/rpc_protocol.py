"""Chunked RPC outbox wire-frame parser and bounded reassembler (`Device -> HA`).

Standard library only (no Home Assistant imports), so standalone unit tests exercise this exact code.
Wire format emitted by `latter_rpc::Outbox`:
    `<boot_hex>:<seq>:<part>/<total>|<json_slice>`
where `<json_slice>` reassembles into `{"s": "<service>", "d": {...}}`.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import json
import time
from typing import Any

MAX_RPC_PARTS: int = 16
MAX_RPC_BYTES: int = 8192
PARTIAL_TTL_SECONDS: float = 15.0
DEDUP_HISTORY_LIMIT: int = 64


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


def parse_rpc_frame(raw: str | None) -> RpcFrame | None:
    """Parse `<boot_hex>:<seq>:<part>/<total>|<json_slice>`, or return None on malformed input."""
    if not raw or not isinstance(raw, str) or "|" not in raw:
        return None
    header, body = raw.split("|", 1)
    hparts = header.split(":")
    if len(hparts) != 3:
        return None
    boot_id, seq_s, frac_s = hparts
    if not boot_id or len(boot_id) > 16 or "/" not in frac_s:
        return None
    if not all(c in "0123456789abcdefABCDEF" for c in boot_id):
        return None
    part_s, total_s = frac_s.split("/", 1)
    if not (seq_s.isdigit() and part_s.isdigit() and total_s.isdigit()):
        return None
    seq = int(seq_s)
    part = int(part_s)
    total = int(total_s)
    if seq <= 0 or total < 1 or total > MAX_RPC_PARTS or part < 1 or part > total:
        return None
    if len(body.encode("utf-8")) > MAX_RPC_BYTES:
        return None
    return RpcFrame(
        boot_id=boot_id.lower(),
        seq=seq,
        part=part,
        total=total,
        payload_slice=body,
    )


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

    def feed(
        self, raw: str | None, *, now_mono: float | None = None
    ) -> tuple[str, dict[str, Any]] | None:
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
            assembled = frame.payload_slice
            if len(assembled.encode("utf-8")) > MAX_RPC_BYTES:
                return None
            self._record_completed(msg_key)
            return _decode_envelope(assembled)

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
        assembled = "".join(partial.parts[idx] for idx in range(1, partial.total + 1))
        self._record_completed(msg_key)
        return _decode_envelope(assembled)

    def _record_completed(self, key: tuple[str, int]) -> None:
        self._completed[key] = None
        while len(self._completed) > DEDUP_HISTORY_LIMIT:
            self._completed.popitem(last=False)


def _decode_envelope(assembled: str) -> tuple[str, dict[str, Any]] | None:
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
    if svc.startswith("latter."):
        svc = svc.split(".", 1)[1]
    data = parsed.get("d")
    if data is None:
        return svc, {}
    if not isinstance(data, dict):
        return None
    return svc, dict(data)
