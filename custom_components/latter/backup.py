"""Home Assistant native Backup agent callbacks for the Latter integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DATA_GLOBAL_CONFIG, DATA_GLOBAL_STORE, DOMAIN


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Flush in-memory Site configuration and per-device runtime stores to disk before HA creates a backup."""
    domain_data: dict[str, Any] = hass.data.get(DOMAIN, {})
    if not isinstance(domain_data, dict):
        return

    global_store = domain_data.get(DATA_GLOBAL_STORE)
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
    if global_store is not None and isinstance(global_cfg, dict):
        await global_store.async_save(global_cfg)

    for item in list(domain_data.values()):
        runtime = getattr(item, "_runtime", None)
        store = getattr(runtime, "store", None)
        build_snap = getattr(item, "_build_persisted_snapshot", None)
        if store is not None and callable(build_snap):
            snap = build_snap()
            if hasattr(runtime, "seed_snapshot"):
                runtime.seed_snapshot(snap)
            await store.async_save(snap)


async def async_post_backup(hass: HomeAssistant) -> None:
    """Resume normal operation after Home Assistant completes its backup archive."""
