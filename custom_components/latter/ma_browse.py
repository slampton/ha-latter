"""Pure helpers for browsing the Music Assistant library through media_player.browse_media.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

ARTIST_SEPARATOR = " - "


def choose_browse_entity(preferred: Iterable[str | None], ma_players: Iterable[str]) -> str | None:
    """Return the Music Assistant player to browse the library with, or None if there is none.

    Music Assistant's library is global: every player of its config entry browses the same library, so
    this only picks a handle for media_player.browse_media, never a device binding. The first preferred
    entity that is an available MA player wins (the Device's own MA player, then its default speaker's,
    then the active speaker's), else the first available MA player by entity_id, so the choice is stable.
    """
    available = sorted({p for p in ma_players if p})
    for ent in preferred:
        if ent and ent in available:
            return ent
    return available[0] if available else None


def _child_uri(child: Mapping[str, Any]) -> str:
    return str(child.get("media_content_id") or child.get("uri") or "")


def _child_title(child: Mapping[str, Any]) -> str:
    return str(child.get("title") or child.get("name") or "").strip()


def strip_artist_prefix(title: str, artist: str) -> str:
    """Drop a leading "<artist> - " (Music Assistant's browse titles) when it names the given artist."""
    prefix = f"{artist}{ARTIST_SEPARATOR}"
    if artist and title.lower().startswith(prefix.lower()) and len(title) > len(prefix):
        return title[len(prefix):].strip()
    return title


def common_artist(titles: Sequence[str]) -> str:
    """Return the artist every "<artist> - <title>" shares, or "" (compilations keep their prefixes)."""
    artists = {t.split(ARTIST_SEPARATOR, 1)[0] for t in titles if ARTIST_SEPARATOR in t}
    if len(artists) == 1 and all(ARTIST_SEPARATOR in t for t in titles):
        return artists.pop()
    return ""


def album_track_slots(children: Iterable[Mapping[str, Any]], current_title: str = "") -> list[dict[str, Any]]:
    """Browse slots for an album's tracks: Music Assistant's order (the album order), numbered 1..N.

    The shared "<album artist> - " prefix is stripped, so a track reads "1. Waiting Room"; tracks by
    different artists (a compilation) keep "<artist> - <title>".
    """
    tracks = [c for c in children if _child_uri(c) and _child_title(c)]
    artist = common_artist([_child_title(c) for c in tracks])
    cur = current_title.strip().lower()
    slots: list[dict[str, Any]] = []
    for num, child in enumerate(tracks, start=1):
        title = strip_artist_prefix(_child_title(child), artist)
        slots.append(
            {
                "name": f"{num}. {title}",
                "id": _child_uri(child),
                "type": "track",
                "active": bool(cur) and cur in (title.lower(), _child_title(child).lower()),
            }
        )
    return slots


def artist_album_slots(
    children: Iterable[Mapping[str, Any]],
    artist: str,
    sort: str,
    year_order: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Browse slots for an artist's albums (from browse_media on the artist).

    `sort` is the Device's setting: "name" sorts by album title; "year" and "year_desc" follow
    `year_order` (album URIs in Music Assistant's year order; browse results carry no year), and any
    album missing from it keeps Music Assistant's browse order after the others.
    """
    albums = [
        c for c in children
        if _child_uri(c) and _child_title(c)
        and ("album" in str(c.get("media_class") or c.get("media_content_type") or "").lower()
             or "://album/" in _child_uri(c))
    ]
    rows = [(strip_artist_prefix(_child_title(c), artist), _child_uri(c)) for c in albums]
    if sort == "name":
        rows.sort(key=lambda r: r[0].lower())
    elif year_order:
        rank = {uri: i for i, uri in enumerate(year_order)}
        rows = sorted(rows, key=lambda r: rank.get(r[1], len(rank)))
    return [{"name": name, "id": uri, "type": "album", "active": False} for name, uri in rows]


def text_slot(message: str) -> list[dict[str, Any]]:
    """One non-playable slot that tells the user why the list is empty."""
    return [{"name": message, "id": "", "type": "text", "active": False}]
