"""Pure-stdlib Studio subscription token/digest gates, command scopes, and target guards."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Final, Literal, Protocol

from ..protocol_specs import (
    ALLOWED_DEVICE_ACTIONS as ALLOWED_DEVICE_ACTIONS,
    DEVICE_COMMANDS as DEVICE_COMMANDS,
    DEVICE_ENTITY_VERBS as DEVICE_ENTITY_VERBS,
    SYSTEM_COMMANDS as SYSTEM_COMMANDS,
)

HASH_GATED_SECTIONS: Final[tuple[str, ...]] = (
    "discovered_ble_devices",
    "ble_area_signatures",
    "discovered_latter_devices",
    "ignored_latter_devices",
)

HEAVY_SUBSCRIPTION_SECTIONS: Final[tuple[str, ...]] = (
    "discovered_ble_devices",
    "system_wallpapers",
    "photo_collections",
    "ble_area_signatures",
    "wallpapers",
    "system_controls",
    "discovered_latter_devices",
    "ignored_latter_devices",
    "locale_strings",
    "pref_specs",
    "world_clock_zones",
)

_STATIC_CATALOG_SECTIONS: Final[frozenset[str]] = frozenset(
    {"pref_specs", "world_clock_zones"}
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


@dataclass(frozen=True, slots=True)
class SubscriptionTokenSnapshot:
    """O(1) change-detection tokens for all heavy Studio subscription sections."""

    wallpaper_token: int
    hmac_secret: bytes
    utc_day: int
    system_config_rev: int
    subentry_id: str
    device_config_rev: int
    active_wallpaper_id: str
    display_shape: str
    language: str
    locales_loaded: bool
    registry_rev: int
    ble_dirty_rev: int
    coordinator_ids: tuple[str, ...]
    controls_signature: tuple[tuple[str, int, bool, bool, bool, str], ...]


class SectionTokenGate:
    """Per-subscription O(1) token gate deciding which heavy sections to skip before building."""

    def __init__(self) -> None:
        """Initialize empty sent-token map."""
        self._sent_tokens: dict[str, Any] = {}

    @staticmethod
    def section_tokens(snap: SubscriptionTokenSnapshot) -> dict[str, Any]:
        """Map every heavy subscription section to its O(1) invalidation token."""
        reg_sys_tok = (snap.registry_rev, snap.system_config_rev, snap.coordinator_ids)
        return {
            "pref_specs": 1,
            "world_clock_zones": 1,
            "locale_strings": (snap.language, snap.locales_loaded),
            "photo_collections": snap.wallpaper_token,
            "system_wallpapers": (snap.wallpaper_token, snap.hmac_secret, snap.utc_day),
            "wallpapers": (
                snap.subentry_id,
                snap.wallpaper_token,
                snap.hmac_secret,
                snap.utc_day,
                snap.device_config_rev,
                snap.active_wallpaper_id,
                snap.display_shape,
            ),
            "discovered_latter_devices": reg_sys_tok,
            "ignored_latter_devices": reg_sys_tok,
            "discovered_ble_devices": (snap.ble_dirty_rev, snap.coordinator_ids),
            "ble_area_signatures": (
                snap.system_config_rev,
                snap.ble_dirty_rev,
                snap.registry_rev,
            ),
            "system_controls": (
                snap.system_config_rev,
                snap.wallpaper_token,
                snap.controls_signature,
            ),
        }

    def has_sent(self, key: str) -> bool:
        """Return True if `key` has already been pushed on this subscription."""
        return key in self._sent_tokens

    def mark_dirty(self, *keys: str) -> None:
        """Force the next live push to rebuild and resend `keys` (or all when empty)."""
        if not keys:
            self._sent_tokens.clear()
            return
        for key in keys:
            self._sent_tokens.pop(key, None)

    def record_initial(
        self,
        snap: SubscriptionTokenSnapshot,
        payload: Mapping[str, Any],
    ) -> None:
        """Record baseline tokens for all sections present in the initial subscription payload."""
        for key, token in self.section_tokens(snap).items():
            if key in payload:
                self._sent_tokens[key] = token

    def compute_skip_sections(self, snap: SubscriptionTokenSnapshot) -> set[str]:
        """Return heavy sections proven unchanged by O(1) tokens so they are skipped before build."""
        return {
            key
            for key, token in self.section_tokens(snap).items()
            if key in self._sent_tokens and self._sent_tokens[key] == token
        }

    def commit(
        self,
        snap: SubscriptionTokenSnapshot,
        skipped: Collection[str],
        payload_keys: Collection[str] | None = None,
    ) -> None:
        """Record tokens for sections built on this push (including hash-filtered unchanged sections)."""
        for key, token in self.section_tokens(snap).items():
            if key in skipped:
                continue
            if key in _STATIC_CATALOG_SECTIONS and (
                payload_keys is None or key not in payload_keys
            ):
                continue
            self._sent_tokens[key] = token


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
