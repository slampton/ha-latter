"""Latter Studio command scopes and Device target resolution.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
A Studio request names its Device by `subentry_id`. System-scoped commands never need one;
Device-scoped commands fail when it is missing or unknown. Nothing ever falls back to
another Device.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol, TypeVar

# Commands that act on the whole System (Site config, BLE fabric, groups, profiles, logs).
# Commands that name their own target in the payload (survey Device, removed Device, ...) are
# System-scoped too: they never use the Studio's selected Device.
SYSTEM_COMMANDS: frozenset[str] = frozenset(
    {
        "set_ble_area_offset",
        "set_area_fusion_mode",
        "auto_calibrate_here",
        "system_entity_action",
        "esphome_entity_action",
        "send_test_notification",
        "check_system_updates",
        "log_client_error",
        "clear_internal_logs",
        "remove_device",
        "add_ble_device",
        "set_device_remote_group",
        "create_device_group",
        "delete_device_group",
        "delete_profile",
        "apply_profile",
        "export_backup_json",
        "restore_backup",
    }
)

# Commands that always act on the Studio's selected Device.
DEVICE_COMMANDS: frozenset[str] = frozenset(
    {
        "test_doorbell_speaker",
        "upload_wallpaper",
        "select_wallpaper",
        "toggle_wallpaper_favorite",
        "delete_wallpaper",
        "save_config",
        "capture_profile",
    }
)


class _HasSubentryId(Protocol):
    subentry_id: str


T = TypeVar("T", bound=_HasSubentryId)


class UnknownStudioCommand(KeyError):
    """The Studio sent a command this integration doesn't implement."""


def command_requires_device(cmd: str, body: Mapping[str, Any]) -> bool:
    """Return True if `cmd` (with this payload) must act on the Studio's selected Device.

    Some System commands need the selected Device only in one mode: applying a profile to
    the "current" Device, exporting or restoring a Device-scope backup, or attaching the
    selected Device's camera to a test notification.
    """
    if cmd in DEVICE_COMMANDS:
        return True
    if cmd not in SYSTEM_COMMANDS:
        raise UnknownStudioCommand(cmd)
    if cmd == "apply_profile":
        return str(body.get("target_scope") or "current") == "current"
    if cmd == "export_backup_json":
        return str(body.get("scope") or "device") != "system"
    if cmd == "restore_backup":
        bundle = body.get("bundle")
        scope = bundle.get("scope") if isinstance(bundle, Mapping) else None
        return str(scope or "device") != "system"
    if cmd == "send_test_notification":
        return bool(body.get("include_camera"))
    return False


def find_by_subentry_id(items: Iterable[T], subentry_id: str | None) -> T | None:
    """Return the item whose `subentry_id` equals `subentry_id` exactly, else None (no other matching)."""
    target = str(subentry_id or "").strip()
    if not target:
        return None
    return next((item for item in items if item.subentry_id == target), None)
