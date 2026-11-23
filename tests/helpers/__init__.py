"""Shared real Home Assistant 2026.11+ helpers for `ha-latter` test suites."""

from __future__ import annotations

import importlib
from typing import Any

from tests.helpers.paths import (
    FRONTEND_DIR,
    FRONTEND_SRC,
    LATTER_DIR,
    NODE_BIN,
    REPO_ROOT,
    read_py_tree,
    read_ts_tree,
    run_studio_node_esm,
)

_LAZY_EXPORTS: dict[str, str] = {
    "RealWsCapture": "tests.helpers.ble_and_ws",
    "call_ws": "tests.helpers.ble_and_ws",
    "ensure_bluetooth_manager": "tests.helpers.ble_and_ws",
    "inject_ble_adv": "tests.helpers.ble_and_ws",
    "install_camera_mocks": "tests.helpers.ble_and_ws",
    "make_ibeacon_service_info": "tests.helpers.ble_and_ws",
    "make_jpeg_bytes": "tests.helpers.ble_and_ws",
    "make_ws_connection": "tests.helpers.ble_and_ws",
    "mock_clientsession_get": "tests.helpers.ble_and_ws",
    "seed_ble_proxies": "tests.helpers.ble_and_ws",
    "RecordedServiceCall": "tests.helpers.ha_setup",
    "add_mock_entry": "tests.helpers.ha_setup",
    "ensure_area": "tests.helpers.ha_setup",
    "ensure_floor": "tests.helpers.ha_setup",
    "find_entity_instance": "tests.helpers.ha_setup",
    "flush_debouncers": "tests.helpers.ha_setup",
    "get_extra_js_urls": "tests.helpers.ha_setup",
    "get_platform_entities": "tests.helpers.ha_setup",
    "get_registered_panels": "tests.helpers.ha_setup",
    "get_service_calls": "tests.helpers.ha_setup",
    "get_static_paths": "tests.helpers.ha_setup",
    "install_service_call_recorder": "tests.helpers.ha_setup",
    "make_subentry": "tests.helpers.ha_setup",
    "make_subentry_dict": "tests.helpers.ha_setup",
    "mock_service": "tests.helpers.ha_setup",
    "prepare_latter_dependencies": "tests.helpers.ha_setup",
    "register_common_target_services": "tests.helpers.ha_setup",
    "register_device": "tests.helpers.ha_setup",
    "register_entity": "tests.helpers.ha_setup",
    "seed_esphome_device": "tests.helpers.ha_setup",
}


def __getattr__(name: str) -> Any:
    mod_path = _LAZY_EXPORTS.get(name)
    if mod_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod = importlib.import_module(mod_path)
    return getattr(mod, name)


__all__ = [
    "FRONTEND_DIR",
    "FRONTEND_SRC",
    "LATTER_DIR",
    "NODE_BIN",
    "REPO_ROOT",
    *_LAZY_EXPORTS.keys(),
    "read_py_tree",
    "read_ts_tree",
    "run_studio_node_esm",
]
