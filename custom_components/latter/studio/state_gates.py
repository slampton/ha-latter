"""Pure-stdlib Studio subscription content-digest gates, command scopes, and target guards."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
import hashlib
import json
from typing import Any, Final, Literal, Protocol

from ..protocol_specs import (
    ALLOWED_DEVICE_ACTIONS as ALLOWED_DEVICE_ACTIONS,
    DEVICE_COMMANDS as DEVICE_COMMANDS,
    DEVICE_ENTITY_VERBS as DEVICE_ENTITY_VERBS,
    SYSTEM_COMMANDS as SYSTEM_COMMANDS,
)

HEAVY_SUBSCRIPTION_SECTIONS: Final[tuple[str, ...]] = (
    "discovered_ble_devices",
    "system_wallpapers",
    "photo_collections",
    "ble_area_signatures",
)


class CatalogGate:
    """Per-subscription flag: does the next live push need the entity catalog?"""

    def __init__(self) -> None:
        """Start clean: the subscription's first answer already carried the catalog."""
        self._dirty = False

    def mark_dirty(self) -> None:
        """A registry changed; the next push carries the catalog."""
        self._dirty = True

    def take(self) -> bool:
        """Return True once after a registry change, then False until the next one."""
        dirty, self._dirty = self._dirty, False
        return dirty


class SectionHashGate:
    """Per-subscription content-digest gate omitting unchanged heavy System sections on live pushes."""

    def __init__(self) -> None:
        """Initialize empty section digest map."""
        self._digests: dict[str, str] = {}

    def mark_dirty(self, *keys: str) -> None:
        """Force the next live push to resend the specified sections (or all when empty)."""
        if not keys:
            self._digests.clear()
            return
        for k in keys:
            self._digests.pop(k, None)

    def has_sent(self, key: str) -> bool:
        """Return True if `key` has already been pushed on this subscription."""
        return key in self._digests

    def record_initial(
        self,
        payload: Mapping[str, Any],
        keys: Iterable[str] = HEAVY_SUBSCRIPTION_SECTIONS,
    ) -> None:
        """Record baseline section digests from the initial full subscription push without stripping."""
        for k in keys:
            if k in payload:
                raw = json.dumps(payload[k], sort_keys=True, separators=(",", ":"))
                self._digests[k] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def filter_sections(
        self,
        payload: dict[str, Any],
        keys: Iterable[str] = HEAVY_SUBSCRIPTION_SECTIONS,
    ) -> dict[str, Any]:
        """Strip sections whose content digest is unchanged since the previous push on this subscription."""
        for k in keys:
            if k not in payload:
                continue
            raw = json.dumps(payload[k], sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            if self._digests.get(k) == digest:
                payload.pop(k, None)
            else:
                self._digests[k] = digest
        return payload


# ---------------------------------------------------------------------------
# Studio Command Scopes & Target Checks
# ---------------------------------------------------------------------------

Scope = Literal["system", "device"]


class _HasSubentryId(Protocol):
    subentry_id: str


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


def find_by_subentry_id[T: _HasSubentryId](
    items: Iterable[T], subentry_id: str | None
) -> T | None:
    """Return the item whose `subentry_id` equals `subentry_id` exactly, else `None`."""
    target = str(subentry_id or "").strip()
    if not target:
        return None
    return next((item for item in items if item.subentry_id == target), None)


def allowed_entity_targets(
    requested: Iterable[object], allowed: Collection[str], what: str
) -> list[str]:
    """Return the requested entity IDs if every one of them is in `allowed`, else raise `TargetNotAllowed`."""
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


def checked_entity_verb(body: Mapping[str, object], verbs: Collection[str]) -> str:
    """Return the action verb of an entity action; option/level verbs must be empty or known."""
    action = str(body.get("action") or "").strip().lower()
    if body.get("option") is not None or body.get("level") is not None:
        allowed_param_verbs = {"", *verbs, "select_option", "set_value", "set_level"}
        if action not in allowed_param_verbs:
            raise TargetNotAllowed(f"Unsupported action '{action}'")
        return action
    if action not in verbs:
        raise TargetNotAllowed(f"Unsupported action '{action or '(none)'}'")
    return action
