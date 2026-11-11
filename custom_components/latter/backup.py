"""Home Assistant Core Backup platform entrypoint for Latter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .core.backup import async_post_backup as _core_post_backup, async_pre_backup as _core_pre_backup


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Flush runtime state before Home Assistant Core creates a system backup."""
    await _core_pre_backup(hass)


async def async_post_backup(hass: HomeAssistant) -> None:
    """Complete Home Assistant Core backup hook."""
    await _core_post_backup(hass)
