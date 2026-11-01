"""System-level singleton holding shared site settings, HMAC secret, and active device coordinators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import (
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DATA_HMAC_SECRET,
    DOMAIN,
    INTEGRATION_VERSION,
)

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

DATA_SYSTEM = "system"


class LatterSystem:
    """Represents the shared Latter System state across all configured devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[dict[str, Any]],
        config: dict[str, Any],
        hmac_secret: bytes,
    ) -> None:
        """Initialize the shared LatterSystem instance."""
        self.hass = hass
        self.store = store
        self.config = config
        self.hmac_secret = hmac_secret
        self.coordinators: dict[str, LatterCoordinator] = {}


def get_latter_system(hass: HomeAssistant) -> LatterSystem | None:
    """Return the initialized LatterSystem instance if present."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return None
    sys_obj = domain_data.get(DATA_SYSTEM)
    if isinstance(sys_obj, LatterSystem):
        return sys_obj
    store = domain_data.get(DATA_GLOBAL_STORE)
    cfg = domain_data.get(DATA_GLOBAL_CONFIG)
    secret = domain_data.get(DATA_HMAC_SECRET)
    if isinstance(store, Store) and isinstance(cfg, dict) and isinstance(secret, bytes):
        sys_obj = LatterSystem(hass, store, cfg, secret)
        domain_data[DATA_SYSTEM] = sys_obj
        return sys_obj
    return None


def get_system_device_info() -> DeviceInfo:
    """Return canonical DeviceInfo for the System-level Latter service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, "system")},
        entry_type=dr.DeviceEntryType.SERVICE,
        name="Latter System",
        manufacturer="Lampton Labs",
        model="Latter Site & BLE Fabric Engine",
        sw_version=INTEGRATION_VERSION,
        configuration_url="homeassistant://latter",
    )
