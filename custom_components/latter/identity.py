"""Canonical ESPHome device identity, hardware traits, and chunked RPC Outbox receiver for Latter.

Every lookup starts from a bound ESPHome device ID (stored in the Device subentry), or from the
Device's stored MAC when the ESPHome device was re-created. Nothing is resolved from names,
slugs or entity_id patterns.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .const import DEFAULT_BLE_BEACON_UUID, DOMAIN, normalize_device_slug

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardware Manifest Traits
# ---------------------------------------------------------------------------


def manifest_flag(manifest: Mapping[str, Any], key: str) -> int | None:
    """Return an integer hardware-manifest trait, or None when it is missing or malformed."""
    if key not in manifest:
        return None
    try:
        return int(manifest[key])
    except (TypeError, ValueError):
        return None


def manifest_is_roaming(manifest: Mapping[str, Any]) -> bool:
    """Return True for roaming hardware: `stationary == 0`, or `wearable == 1`. Unknown traits are not roaming."""
    return (
        manifest_flag(manifest, "stationary") == 0
        or manifest_flag(manifest, "wearable") == 1
    )


def manifest_is_wearable(manifest: Mapping[str, Any]) -> bool:
    """Return True only when the manifest reports `wearable == 1`."""
    return manifest_flag(manifest, "wearable") == 1


def manifest_has_display(manifest: Mapping[str, Any]) -> bool:
    """Return False only when the manifest reports `display == 0` (a headless node)."""
    return manifest_flag(manifest, "display") != 0


def manifest_has_mic(manifest: Mapping[str, Any]) -> bool:
    """Return False only when the manifest reports `mic == 0`."""
    return manifest_flag(manifest, "mic") != 0


def manifest_has_speaker(manifest: Mapping[str, Any]) -> bool:
    """Return False only when the manifest reports `spk == 0`."""
    return manifest_flag(manifest, "spk") != 0


def manifest_has_audio(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware exposes a microphone or speaker."""
    return manifest_has_mic(manifest) or manifest_has_speaker(manifest)


def manifest_has_imu(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware exposes an active motion IMU (non-stationary `imu == 1`)."""
    if not manifest:
        return True
    return manifest_flag(manifest, "imu") == 1 and manifest_flag(manifest, "stationary") != 1


def manifest_has_battery(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware has a rechargeable battery (`battery == 1` or non-stationary pre-hello)."""
    if not manifest:
        return True
    return manifest_flag(manifest, "battery") == 1


def manifest_is_round(manifest: Mapping[str, Any]) -> bool:
    """Return True when the hardware display shape is circular."""
    if not manifest_has_display(manifest):
        return False
    return str(manifest.get("shape") or "circle").strip().lower() != "square"


# ---------------------------------------------------------------------------
# Bound ESPHome Device Identity & Service Resolution
# ---------------------------------------------------------------------------

LATTER_CONTRACT_ACTION_SUFFIXES: tuple[str, ...] = (
    "_latter_push_v3",
    "_latter_device_command",
    "_set_browse_slots",
    "_set_area_slots",
    "_show_notification",
    "_latter_ping",
)


def _esphome_entry_for_device(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> Any | None:
    """Return the ESPHome config entry that owns `device`, or None if it isn't an ESPHome device."""
    dev_reg = dr.async_get(hass)
    for ce in hass.config_entries.async_entries("esphome"):
        if any(
            d.id == device.id
            for d in dr.async_entries_for_config_entry(dev_reg, ce.entry_id)
        ):
            return ce
    return None


def is_esphome_device(hass: HomeAssistant, device: dr.DeviceEntry) -> bool:
    """Return True if `device` belongs to an ESPHome config entry."""
    return _esphome_entry_for_device(hass, device) is not None


def esphome_node_name(
    hass: HomeAssistant, device_or_id: dr.DeviceEntry | str | None
) -> str:
    """Return the ESPHome node name (`device_name` of its ESPHome config entry), normalized for `esphome.<node>_*` services."""
    dev = get_bound_esphome_device(hass, device_or_id)
    if dev is None:
        return ""
    ce = _esphome_entry_for_device(hass, dev)
    if ce is None:
        return ""
    node = str(ce.data.get("device_name") or "").strip()
    return normalize_device_slug(node) if node else ""


def is_latter_compatible_esphome_device(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> bool:
    """Return True ONLY if the ESPHome device implements the Latter API contract or runs Latter firmware."""
    node = esphome_node_name(hass, device)
    if node:
        esphome_services = hass.services.async_services_for_domain("esphome")
        if any(f"{node}{sfx}" in esphome_services for sfx in LATTER_CONTRACT_ACTION_SUFFIXES):
            return True

    model_str = f"{device.model or ''} {device.sw_version or ''}".lower()
    if "latter" in model_str:
        return True
    return (
        find_device_entity_by_suffix(hass, device, "update", ("_project_firmware",))
        is not None
    )


def get_bound_esphome_device(
    hass: HomeAssistant, device_or_id: dr.DeviceEntry | str | None
) -> dr.DeviceEntry | None:
    """Return the ESPHome DeviceEntry for an ESPHome device ID, or for a Latter device ID (followed via `via_device_id`)."""
    dev_reg = dr.async_get(hass)
    if isinstance(device_or_id, dr.DeviceEntry):
        dev: dr.DeviceEntry | None = device_or_id
    elif isinstance(device_or_id, str) and device_or_id.strip():
        dev = dev_reg.async_get(device_or_id.strip())
    else:
        return None
    if dev is None:
        return None
    if (
        any(ident[0] == DOMAIN for ident in dev.identifiers)
        and not is_esphome_device(hass, dev)
        and dev.via_device_id
    ):
        return dev_reg.async_get(dev.via_device_id)
    return dev


def find_esphome_device_by_mac(
    hass: HomeAssistant, mac: str | None
) -> dr.DeviceEntry | None:
    """Return the ESPHome device whose network MAC connection equals `mac` exactly, or None."""
    if not mac:
        return None
    target = (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
    dev_reg = dr.async_get(hass)
    for ce in hass.config_entries.async_entries("esphome"):
        for dev in dr.async_entries_for_config_entry(dev_reg, ce.entry_id):
            if target in dev.connections:
                return dev
    return None


def resolve_bound_esphome_device_id(
    hass: HomeAssistant, esphome_device_id: str | None, mac: str | None
) -> str | None:
    """Resolve a Device's ESPHome device: the stored device ID, else the ESPHome device carrying the stored MAC."""
    dev = get_bound_esphome_device(hass, esphome_device_id)
    if dev is None:
        dev = find_esphome_device_by_mac(hass, mac)
    return dev.id if dev is not None else None


def device_entities(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    domain: str | None = None,
    include_disabled: bool = False,
) -> list[er.RegistryEntry]:
    """Return all entity registry entries belonging to the bound ESPHome device."""
    dev = get_bound_esphome_device(hass, device_or_id)
    if dev is None:
        return []
    entries = [
        e
        for e in er.async_entries_for_device(er.async_get(hass), dev.id)
        if include_disabled or not e.disabled_by
    ]
    if domain:
        return [e for e in entries if e.domain == domain]
    return entries


def find_device_entity_by_suffix(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    domain: str,
    suffixes: tuple[str, ...] | list[str],
    original_names: tuple[str, ...] = (),
    unique_id_suffixes: tuple[str, ...] = (),
) -> str | None:
    """Find an enabled entity on the bound device in `domain` matching `suffixes` (or `original_names` / `unique_id_suffixes` if renamed)."""
    entries = device_entities(hass, device_or_id, domain=domain)
    for sfx in suffixes:
        for entry in entries:
            if not sfx or entry.entity_id.endswith(sfx):
                return entry.entity_id
    for orig in original_names:
        for entry in entries:
            if (entry.original_name or "") == orig:
                return entry.entity_id
    for uid_sfx in unique_id_suffixes:
        for entry in entries:
            if uid_sfx and (entry.unique_id or "").endswith(uid_sfx):
                return entry.entity_id
    return None


def esphome_service(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    action: str,
) -> str | None:
    """Resolve the registered `esphome.<node>_<action>` service name for a bound device, or None if unavailable."""
    node = esphome_node_name(hass, device_or_id)
    if not node:
        return None
    svc = f"{node}_{action}"
    return svc if hass.services.has_service("esphome", svc) else None


def read_device_hardware_manifest(
    hass: HomeAssistant,
    device_or_id: dr.DeviceEntry | str | None,
    cached_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read and merge the parsed JSON hardware manifest from `device_hello` and the bound device's manifest sensor."""
    merged: dict[str, Any] = {}
    manifest_ent_id = find_device_entity_by_suffix(
        hass,
        device_or_id,
        "sensor",
        ("_system_hardware_manifest", "_hardware_manifest"),
        original_names=("System: Hardware Manifest", "Hardware Manifest"),
        unique_id_suffixes=("/text_sensor/System: Hardware Manifest",),
    )
    if manifest_ent_id:
        st = hass.states.get(manifest_ent_id)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            try:
                parsed = json.loads(st.state)
                if isinstance(parsed, dict) and "w" in parsed and "h" in parsed:
                    merged.update(parsed)
            except (ValueError, TypeError):
                pass

    if isinstance(cached_manifest, dict) and "w" in cached_manifest and "h" in cached_manifest:
        merged.update(cached_manifest)

    if merged and "beacon" not in merged and int(merged.get("minor") or 0) > 0:
        merged["beacon"] = {
            "uuid": DEFAULT_BLE_BEACON_UUID,
            "major": 1,
            "minor": int(merged["minor"]),
        }
    return merged


# ---------------------------------------------------------------------------
# Chunked RPC Outbox Wire-Frame Parser & Reassembler (`Device -> HA`)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Bound ESPHome RPC Outbox Listener
# ---------------------------------------------------------------------------

RPC_OUTBOX_SUFFIXES: tuple[str, ...] = ("_system_rpc_outbox", "_rpc_outbox")
RPC_OUTBOX_ORIGINAL_NAMES: tuple[str, ...] = ("System: RPC Outbox", "RPC Outbox")
RPC_OUTBOX_UNIQUE_ID_SUFFIXES: tuple[str, ...] = ("/text_sensor/System: RPC Outbox",)


class LatterRpcReceiver:
    """Watches a bound ESPHome Device's `System: RPC Outbox` entity and dispatches authenticated RPCs."""

    def __init__(self, hass: HomeAssistant, coordinator: LatterCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._reassembler = RpcReassembler()
        self._tracked_entity_id: str | None = None
        self._unsub_state: Callable[[], None] | None = None
        self._unsub_ent_reg: Callable[[], None] | None = None

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
        if (
            self._tracked_entity_id is None
            or ent_id == self._tracked_entity_id
            or any(ent_id.endswith(sfx) for sfx in RPC_OUTBOX_SUFFIXES)
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
            self.coordinator._last_pushed_v3.clear()
            return
        if old_state is not None and old_state.state == STATE_UNAVAILABLE:
            self.coordinator._last_pushed_v3.clear()
            self.coordinator.force_republish_all_domains()
        if new_state.state in (STATE_UNKNOWN, ""):
            return
        self._ingest_raw_state(new_state.state)

    @callback
    def _ingest_raw_state(self, raw: str) -> None:
        decoded = self._reassembler.feed(raw)
        if decoded is None:
            return
        svc_name, data = decoded
        from .services import async_dispatch_bound_rpc

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
