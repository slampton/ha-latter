"""Latter Studio command scopes, Device target resolution and entity-target checks.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
The websocket type is the scope. `latter/system/command` runs System commands: they never use the
Studio's selected Device, and a System command that acts on one Device names it in its own payload
(survey Device, removed Device, profile source, ...). `latter/device/command` runs Device commands on
the Device named by the message's `subentry_id`, and fails when it is missing or unknown. Nothing
ever falls back to another Device.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any, Literal, Protocol, TypeVar

# Commands that act on the whole System (Site config, BLE fabric, groups, profiles, logs), or on a
# Device the payload names explicitly.
SYSTEM_COMMANDS: frozenset[str] = frozenset(
    {
        "set_ble_area_offset",
        "set_area_fusion",
        "auto_calibrate_here",
        "system_entity_action",
        "send_announcement",
        "check_system_updates",
        "clear_internal_logs",
        "remove_device",
        "add_ble_device",
        "set_device_remote_group",
        "create_device_group",
        "delete_device_group",
        "capture_profile",
        "delete_profile",
        "apply_profile",
        "test_doorbell_speaker",
        "save_system_config",
    }
)

# Commands that always act on the Device named by the message's subentry_id.
DEVICE_COMMANDS: frozenset[str] = frozenset(
    {
        "esphome_entity_action",
        "upload_wallpaper",
        "select_wallpaper",
        "toggle_wallpaper_favorite",
        "delete_wallpaper",
        "save_device_config",
    }
)

# Verbs a Studio entity action may send without an option or level.
DEVICE_ENTITY_VERBS: frozenset[str] = frozenset(
    {"press", "install", "check", "toggle", "turn_on", "turn_off"}
)
SYSTEM_ENTITY_VERBS: frozenset[str] = frozenset({"turn_on", "turn_off"})

Scope = Literal["system", "device"]


class _HasSubentryId(Protocol):
    subentry_id: str


T = TypeVar("T", bound=_HasSubentryId)


class UnknownStudioCommand(KeyError):
    """The Studio sent a command this integration doesn't implement."""


class TargetNotAllowed(ValueError):
    """A Studio entity action named an entity or verb outside what the command may touch."""


def command_scope(cmd: str) -> Scope:
    """Return the scope (`system` or `device`) whose websocket type runs `cmd`."""
    if cmd in DEVICE_COMMANDS:
        return "device"
    if cmd in SYSTEM_COMMANDS:
        return "system"
    raise UnknownStudioCommand(cmd)


def find_by_subentry_id(items: Iterable[T], subentry_id: str | None) -> T | None:
    """Return the item whose `subentry_id` equals `subentry_id` exactly, else None (no other matching)."""
    target = str(subentry_id or "").strip()
    if not target:
        return None
    return next((item for item in items if item.subentry_id == target), None)


def allowed_entity_targets(
    requested: Iterable[Any], allowed: Collection[str], what: str
) -> list[str]:
    """Return the requested entity IDs if every one of them is in `allowed`, else raise TargetNotAllowed."""
    ids: list[str] = []
    for item in requested:
        ent = str(item or "").strip()
        if ent and ent not in ids:
            ids.append(ent)
    if not ids:
        raise TargetNotAllowed("No entity given")
    rejected = [ent for ent in ids if ent not in allowed]
    if rejected:
        raise TargetNotAllowed(f"Not {what}: {', '.join(rejected)}")
    return ids


def checked_entity_verb(
    body: Mapping[str, Any], verbs: Collection[str]
) -> str:
    """Return the action verb of an entity action; an option or level needs no verb, anything else must be in `verbs`."""
    action = str(body.get("action") or "").strip().lower()
    if body.get("option") is not None or body.get("level") is not None:
        return action
    if action not in verbs:
        raise TargetNotAllowed(f"Unsupported action '{action or '(none)'}'")
    return action
