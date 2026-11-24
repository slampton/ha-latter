"""Per-Device persisted runtime store and RPC receiver factory registry."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from ..const import STORAGE_KEY_PREFIX, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

_RPC_RECEIVER_FACTORY: Callable[[HomeAssistant, Any], Any] | None = None


def register_rpc_receiver_factory(
    factory: Callable[[HomeAssistant, Any], Any],
) -> None:
    """Register the `LatterRpcReceiver` constructor from `services.rpc_receiver` (acyclic hook)."""
    global _RPC_RECEIVER_FACTORY
    _RPC_RECEIVER_FACTORY = factory


def get_rpc_receiver_factory() -> Callable[[HomeAssistant, Any], Any] | None:
    """Return the registered `LatterRpcReceiver` factory, if loaded."""
    return _RPC_RECEIVER_FACTORY


class LatterDeviceRuntime:
    """Manages change-gated `.storage/latter.runtime.<entry_id>` persistence and `device_hello` state."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the per-device runtime store."""
        self.hass = hass
        self.entry_id = entry_id
        self.store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}"
        )
        self._last_persisted_snapshot: dict[str, Any] | None = None
        self.hello_manifest: dict[str, Any] = {}
        self.last_boot_id: str = ""

    async def async_load(self) -> dict[str, Any]:
        """Load persisted runtime state from disk."""
        try:
            stored = await self.store.async_load()
            if isinstance(stored, dict):
                return stored
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed loading Latter runtime store: %s", err)
        return {}

    @callback
    def schedule_save(self, snapshot_builder: Callable[[], dict[str, Any]]) -> None:
        """Persist runtime state to HA Store only when semantic values change."""
        snap = snapshot_builder()
        if snap == self._last_persisted_snapshot:
            return
        self._last_persisted_snapshot = dict(snap)
        self.store.async_delay_save(snapshot_builder, delay=1.5)

    async def async_flush(self, snapshot: dict[str, Any]) -> None:
        """Immediately persist a runtime snapshot to disk (used by pre-backup hook)."""
        self._last_persisted_snapshot = dict(snapshot)
        await self.store.async_save(snapshot)

    def seed_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Record the baseline snapshot after initial load."""
        self._last_persisted_snapshot = dict(snapshot)

    def apply_device_hello(
        self, boot_id: str, manifest_raw: str
    ) -> tuple[bool, dict[str, Any] | None]:
        """Parse `device_hello` handshake and return `(is_new_boot, parsed_manifest_or_none)`."""
        parsed_manifest: dict[str, Any] | None = None
        if manifest_raw and manifest_raw.strip().startswith("{"):
            try:
                parsed = json.loads(manifest_raw)
                if isinstance(parsed, dict) and (
                    ("w" in parsed and "h" in parsed)
                    or "core_rev" in parsed
                    or "display" in parsed
                ):
                    self.hello_manifest = parsed
                    parsed_manifest = parsed
            except (ValueError, TypeError):
                pass

        clean_boot_id = str(boot_id or "").strip()
        is_new_boot = bool(clean_boot_id and clean_boot_id != self.last_boot_id)
        if clean_boot_id:
            self.last_boot_id = clean_boot_id
        return is_new_boot, parsed_manifest
