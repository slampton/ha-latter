"""Home Assistant Diagnostics platform entrypoint for Latter."""

from __future__ import annotations

from .core.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

__all__ = [
    "TO_REDACT",
    "async_get_config_entry_diagnostics",
    "async_get_device_diagnostics",
]
