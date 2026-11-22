"""Unified push state coordinator package for Latter Devices and BLE Tags (`L3`)."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .area_follow_controller import (
        LatterAreaFollowController as LatterAreaFollowController,
    )
    from .core import (
        LatterCoordinator as LatterCoordinator,
        match_coordinator_target as match_coordinator_target,
        resolve_coordinator as resolve_coordinator,
    )
    from .runtime_store import (
        LatterDeviceRuntime as LatterDeviceRuntime,
        register_rpc_receiver_factory as register_rpc_receiver_factory,
    )

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "LatterAreaFollowController": (
        ".area_follow_controller",
        "LatterAreaFollowController",
    ),
    "LatterCoordinator": (".core", "LatterCoordinator"),
    "LatterDeviceRuntime": (".runtime_store", "LatterDeviceRuntime"),
    "match_coordinator_target": (".core", "match_coordinator_target"),
    "register_rpc_receiver_factory": (
        ".runtime_store",
        "register_rpc_receiver_factory",
    ),
    "resolve_coordinator": (".core", "resolve_coordinator"),
}

__all__ = [
    "LatterAreaFollowController",
    "LatterCoordinator",
    "LatterDeviceRuntime",
    "match_coordinator_target",
    "register_rpc_receiver_factory",
    "resolve_coordinator",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve public `coordinator` symbols without forming a package-init import cycle."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_name, attr_name = target
    val = getattr(importlib.import_module(mod_name, __name__), attr_name)
    globals()[name] = val
    return val
