"""Linking a Latter Device to its Music Assistant player.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.

Music Assistant identifies Sendspin players by a hash of the device's public key (ESPHome
2026.11+), not its MAC, and its player devices carry no connections. So neither device_id nor
MAC can match a Latter device's own player; the Device stores an explicit link instead
(`ma_player_entity`), chosen once in the `link_ma_player` repair or in Studio.
"""

from __future__ import annotations

from collections.abc import Iterable


def configured_link(configured: str | None, ma_player_entities: Iterable[str]) -> str | None:
    """Return the Device's configured Music Assistant player if it is a current MA media_player, else None."""
    target = str(configured or "").strip()
    if not target:
        return None
    return target if target in set(ma_player_entities) else None


def slug_matched_ma_player(device_slug: str | None, ma_player_entities: Iterable[str]) -> str | None:
    """Return `media_player.<device_slug>` when an exact-slug Music Assistant player exists."""
    slug = str(device_slug or "").strip().lower()
    if not slug:
        return None
    candidate = f"media_player.{slug}"
    return candidate if candidate in set(ma_player_entities) else None


def suggest_ma_player(
    device_identity: tuple[str | None, str | None],
    candidates: Iterable[tuple[str, str | None, str | None]],
) -> str | None:
    """Suggest the MA player whose device has exactly the same manufacturer AND model as the ESPHome device.

    `device_identity` is the bound ESPHome device's (manufacturer, model), i.e. the firmware
    project identity. `candidates` are (entity_id, manufacturer, model) of Music Assistant
    players. Returns the entity only when exactly one candidate matches; 0 or 2+ matches, or
    an unknown identity, suggest nothing.
    """
    manufacturer, model = device_identity
    if not manufacturer or not model:
        return None
    matches = [
        entity_id
        for entity_id, c_manufacturer, c_model in candidates
        if c_manufacturer == manufacturer and c_model == model
    ]
    return matches[0] if len(matches) == 1 else None
