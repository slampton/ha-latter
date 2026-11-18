"""Music Assistant & Home Assistant Media Browse Engine with bounded 64-entry LRU cache."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
import logging
import re
from typing import Any
from urllib.parse import quote

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

ARTIST_SEPARATOR = " - "
MAX_BROWSE_CACHE_ENTRIES: int = 64
NO_MA_PLAYER_TEXT = "No Music Assistant player to browse with"

LIBRARY_MEDIA_TYPES: set[str] = {
    "playlist",
    "artist",
    "album",
    "radio",
    "podcast",
    "audiobook",
    "track",
}

_FAVORITE_MEDIA_TYPES: tuple[str, ...] = (
    "playlist",
    "artist",
    "album",
    "radio",
    "podcast",
    "audiobook",
    "track",
)

# Bounded 64-entry LRU OrderedDict cache for lyrics & artist/album bio payloads
MAX_LYRIC_LINES: int = 128
_BROWSE_LYRICS_BIO_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_LRC_TAG_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
_LRC_WORD_TAG_RE = re.compile(r"<\d{1,3}:\d{2}(?:[.:]\d{1,3})?>")
_LRC_META_TAG_RE = re.compile(
    r"^\[(?:ar|ti|al|au|by|length|offset|re|ve|tool|id|la):[^\]]*\]$",
    re.IGNORECASE,
)
_LRC_EMPTY_MARKER_RE = re.compile(r"^[\s♪♫♬♩·•…\-\u2013\u2014~*._|/\\]+$")


def clear_browse_cache() -> None:
    """Clear the bounded LRU browse cache on unload."""
    _BROWSE_LYRICS_BIO_CACHE.clear()


def _cache_get(cache_key: str) -> dict[str, Any] | None:
    """Fetch a cached lyrics/bio dict and promote it to MRU, or return None."""
    cached = _BROWSE_LYRICS_BIO_CACHE.get(cache_key)
    if cached is not None:
        _BROWSE_LYRICS_BIO_CACHE.move_to_end(cache_key)
    return cached


def _cache_put(
    cache_key: str, entry: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Insert or promote a cache entry and evict LRU items beyond 64 entries."""
    if entry is not None:
        _BROWSE_LYRICS_BIO_CACHE[cache_key] = entry
    bucket = _BROWSE_LYRICS_BIO_CACHE.setdefault(cache_key, {})
    _BROWSE_LYRICS_BIO_CACHE.move_to_end(cache_key)
    while len(_BROWSE_LYRICS_BIO_CACHE) > MAX_BROWSE_CACHE_ENTRIES:
        _BROWSE_LYRICS_BIO_CACHE.popitem(last=False)
    return bucket


def choose_browse_entity(
    preferred: Iterable[str | None], ma_players: Iterable[str]
) -> str | None:
    """Return the Music Assistant player to browse the library with, or None if there is none."""
    available = sorted({p for p in ma_players if p})
    for ent in preferred:
        if ent and ent in available:
            return ent
    return available[0] if available else None


def browse_node_dict(node: Any) -> dict[str, Any] | None:
    """Return a media_player.browse_media result as a dict, or None."""
    if isinstance(node, Mapping):
        return dict(node)
    as_dict = getattr(node, "as_dict", None)
    if callable(as_dict):
        result = as_dict()
        return dict(result) if isinstance(result, Mapping) else None
    return None


def _child_uri(child: Mapping[str, Any]) -> str:
    return str(child.get("media_content_id") or child.get("uri") or "")


def _child_title(child: Mapping[str, Any]) -> str:
    return str(child.get("title") or child.get("name") or "").strip()


def strip_artist_prefix(title: str, artist: str) -> str:
    """Drop a leading '<artist> - ' when it names the given artist."""
    prefix = f"{artist}{ARTIST_SEPARATOR}"
    if artist and title.lower().startswith(prefix.lower()) and len(title) > len(prefix):
        return title[len(prefix) :].strip()
    return title


def common_artist(titles: Sequence[str]) -> str:
    """Return the artist every '<artist> - <title>' shares, or '' (compilations keep their prefixes)."""
    artists = {
        t.split(ARTIST_SEPARATOR, 1)[0] for t in titles if ARTIST_SEPARATOR in t
    }
    if len(artists) == 1 and all(ARTIST_SEPARATOR in t for t in titles):
        return artists.pop()
    return ""


def album_track_slots(
    children: Iterable[Mapping[str, Any]], current_title: str = ""
) -> list[dict[str, Any]]:
    """Browse slots for an album's tracks in Music Assistant's order, numbered 1..N."""
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
                "active": bool(cur)
                and cur in (title.lower(), _child_title(child).lower()),
            }
        )
    return slots


def artist_album_slots(
    children: Iterable[Mapping[str, Any]],
    artist: str,
    sort: str,
    year_order: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Browse slots for an artist's albums (from browse_media on the artist)."""
    albums = [
        c
        for c in children
        if _child_uri(c)
        and _child_title(c)
        and (
            "album"
            in str(
                c.get("media_class") or c.get("media_content_type") or ""
            ).lower()
            or "://album/" in _child_uri(c)
        )
    ]
    rows = [
        (strip_artist_prefix(_child_title(c), artist), _child_uri(c)) for c in albums
    ]
    if sort == "name":
        rows.sort(key=lambda r: r[0].lower())
    elif year_order:
        rank = {uri: i for i, uri in enumerate(year_order)}
        rows = sorted(rows, key=lambda r: rank.get(r[1], len(rank)))
    return [
        {"name": name, "id": uri, "type": "album", "active": False}
        for name, uri in rows
    ]


def text_slot(message: str) -> list[dict[str, Any]]:
    """One non-playable slot that tells the user why the list is empty."""
    return [{"name": message, "id": "", "type": "text", "active": False}]


def is_music_assistant_player(hass: HomeAssistant, state_obj: State) -> bool:
    """Return True if the media_player entity is provided by Music Assistant."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(state_obj.entity_id)
    return entry is not None and entry.platform == "music_assistant"


def _get_ma_config_entry(hass: HomeAssistant) -> Any | None:
    """Return the loaded Music Assistant ConfigEntry, or None."""
    entries = hass.config_entries.async_entries("music_assistant")
    for entry in entries:
        if entry.state is ConfigEntryState.LOADED:
            return entry
    if entries:
        return entries[0]
    return None


def _get_ma_config_entry_id(hass: HomeAssistant) -> str | None:
    """Auto-discover the loaded Music Assistant config_entry_id."""
    entry = _get_ma_config_entry(hass)
    return str(entry.entry_id) if entry is not None else None


def get_ma_mass_client(hass: HomeAssistant) -> Any | None:
    """Resolve the active Music Assistant runtime client (`ma_entry.runtime_data.mass`), or None."""
    entries = hass.config_entries.async_entries("music_assistant")
    ordered = sorted(
        entries,
        key=lambda e: 0 if e.state is ConfigEntryState.LOADED else 1,
    )
    for entry in ordered:
        runtime_data = getattr(entry, "runtime_data", None)
        if runtime_data is None:
            continue
        mass = getattr(runtime_data, "mass", None)
        if mass is not None:
            return mass
        if hasattr(runtime_data, "player_queues") or hasattr(runtime_data, "music"):
            return runtime_data
    return None


def resolve_ma_queue_id_sync(
    hass: HomeAssistant, ma_target: str, mass: Any | None = None
) -> str:
    """Synchronously resolve the Music Assistant queue_id for a `media_player` entity."""
    if not ma_target:
        return ""
    st = hass.states.get(ma_target)
    if st is not None:
        active_q = str(st.attributes.get("active_queue") or "").strip()
        if active_q:
            return active_q
    ent_entry = er.async_get(hass).async_get(ma_target)
    uid = str(ent_entry.unique_id or "").strip() if ent_entry is not None else ""
    if mass is not None:
        players = getattr(mass, "players", None)
        if uid and players is not None and hasattr(players, "get"):
            try:
                p_obj = players.get(uid)
                act_src = str(
                    getattr(p_obj, "active_source", None)
                    or getattr(p_obj, "active_group", None)
                    or ""
                ).strip()
                pqs = getattr(mass, "player_queues", None)
                if act_src and pqs is not None and hasattr(pqs, "get") and pqs.get(act_src) is not None:
                    return act_src
            except Exception:  # noqa: BLE001
                pass
    return uid


def _extract_item_dict(raw: Any) -> dict[str, Any]:
    """Convert a Music Assistant model, BrowseMedia dict, or object into a normalized dict."""
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "as_dict") and callable(raw.as_dict):
        result = raw.as_dict()
        if isinstance(result, dict):
            return result
    if hasattr(raw, "to_dict") and callable(raw.to_dict):
        try:
            return raw.to_dict()
        except Exception:  # noqa: BLE001
            pass
    result: dict[str, Any] = {}
    for attr in (
        "name",
        "title",
        "uri",
        "item_id",
        "provider",
        "media_type",
        "media_content_id",
        "media_content_type",
        "media_title",
        "media_artist",
        "media_album_name",
        "year",
        "position",
        "duration",
        "favorite",
        "track_number",
        "disc_number",
        "artists",
        "artist_str",
        "album",
        "metadata",
        "lrc_lyrics",
        "lyrics",
        "description",
        "queue_item_id",
        "media_item",
        "children",
    ):
        if hasattr(raw, attr):
            val = getattr(raw, attr)
            if hasattr(val, "value"):
                val = val.value
            result[attr] = val
    return result


def _extract_artist_name(item: dict[str, Any]) -> str:
    """Extract primary artist name from a Music Assistant item dict."""
    if item.get("artist_str"):
        return str(item["artist_str"])
    artists = item.get("artists")
    if isinstance(artists, list) and artists:
        first = _extract_item_dict(artists[0])
        if first.get("name"):
            return str(first["name"])
    artist = item.get("artist")
    if isinstance(artist, dict) and artist.get("name"):
        return str(artist["name"])
    if isinstance(artist, str) and artist:
        return artist
    return ""


def _ma_browse_entity(hass: HomeAssistant, preferred_speakers: list[str]) -> str | None:
    """Pick the Music Assistant player that media_player.browse_media runs on."""
    from .media import resolve_ma_counterpart_entity

    entry_id = _get_ma_config_entry_id(hass)
    if not entry_id:
        return None
    ma_players = [
        ent.entity_id
        for ent in er.async_entries_for_config_entry(er.async_get(hass), entry_id)
        if ent.domain == "media_player"
        and ent.disabled_by is None
        and (st := hass.states.get(ent.entity_id)) is not None
        and st.state not in ("unavailable", "unknown")
    ]
    preferred = [resolve_ma_counterpart_entity(hass, spk) for spk in preferred_speakers if spk]
    return choose_browse_entity(preferred, ma_players)


async def _browse_ma_node(
    hass: HomeAssistant,
    browse_entity: str,
    media_content_type: str,
    media_content_id: str,
) -> dict[str, Any] | None:
    """Return Music Assistant's browse node (title and children) for an item, or None if the call fails."""
    try:
        resp = await hass.services.async_call(
            "media_player",
            "browse_media",
            {
                "entity_id": browse_entity,
                "media_content_type": media_content_type,
                "media_content_id": media_content_id,
            },
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "media_player.browse_media(%s, %s) on %s failed: %s",
            media_content_type,
            media_content_id,
            browse_entity,
            err,
        )
        return None
    node = browse_node_dict(resp.get(browse_entity)) if isinstance(resp, dict) else None
    if node is None:
        return None
    node["children"] = [_extract_item_dict(c) for c in node.get("children") or []]
    return node


async def _call_ma_get_library(
    hass: HomeAssistant,
    config_entry_id: str,
    media_type: str,
    favorite: bool | None = None,
    search: str | None = None,
    limit: int = 500,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    """Call music_assistant.get_library and return its items."""
    if not hass.services.has_service("music_assistant", "get_library"):
        return []
    payload: dict[str, Any] = {
        "config_entry_id": config_entry_id,
        "media_type": media_type,
        "limit": limit,
    }
    if favorite is not None:
        payload["favorite"] = favorite
    if search:
        payload["search"] = search
    if order_by:
        payload["order_by"] = order_by
    try:
        resp = await hass.services.async_call(
            "music_assistant",
            "get_library",
            payload,
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "music_assistant.get_library(%s, order_by=%s) failed: %s",
            media_type,
            order_by,
            err,
        )
        return []
    raw_items = resp.get("items") if isinstance(resp, dict) else None
    if not isinstance(raw_items, list):
        return []
    return [_extract_item_dict(x) for x in raw_items]


async def async_lookup_ma_track_uri(
    hass: HomeAssistant,
    title: str,
    artist: str = "",
) -> str:
    """Resolve a track URI from the Music Assistant library by exact case-insensitive title (preferring matching artist)."""
    want_title = title.strip().lower()
    if not want_title:
        return ""
    entry_id = _get_ma_config_entry_id(hass)
    if not entry_id:
        return ""
    items = await _call_ma_get_library(
        hass,
        entry_id,
        "track",
        search=title.strip(),
        limit=25,
    )
    want_artist = artist.strip().lower()
    fallback_uri = ""
    for item in items:
        cand_title = str(item.get("name") or item.get("title") or "").strip().lower()
        if cand_title != want_title:
            continue
        uri = str(item.get("uri") or item.get("media_content_id") or "").strip()
        if not uri:
            continue
        cand_artist = _extract_artist_name(item).strip().lower()
        if want_artist and cand_artist == want_artist:
            return uri
        if not fallback_uri:
            fallback_uri = uri
    return fallback_uri


def _format_local_speaker_name(hass: HomeAssistant, state_obj: State) -> str:
    """Format the friendly display name for the on-device ESPHome speaker."""
    friendly = str(state_obj.attributes.get("friendly_name") or state_obj.entity_id)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entry = ent_reg.async_get(state_obj.entity_id)
    if entry and entry.device_id:
        dev = dev_reg.async_get(entry.device_id)
        if dev:
            dev_name = str(dev.name_by_user or dev.name or "").strip()
            if dev_name:
                return dev_name
    if friendly.lower().endswith(" music") and len(friendly) > 6:
        return friendly[:-6].strip()
    return friendly


async def _browse_speakers(
    hass: HomeAssistant,
    active_speaker: str,
    last_speaker: str,
    local_speaker: str,
) -> list[dict[str, Any]]:
    """Build sorted speaker list restricted strictly to Music Assistant players (+ deduplicated local speaker)."""
    from .hub import get_area_state_index
    from .media import resolve_ma_counterpart_entity

    local_ma = (
        resolve_ma_counterpart_entity(hass, local_speaker) if local_speaker else None
    )
    local_ids = {s for s in (local_speaker, local_ma) if s}
    has_local_esphome = bool(
        local_speaker
        and (st_loc := hass.states.get(local_speaker)) is not None
        and st_loc.state not in ("unavailable", "unknown")
    )

    ent_reg = er.async_get(hass)
    items: list[dict[str, Any]] = []
    for state_obj in get_area_state_index(hass).states_for_domain("media_player"):
        if state_obj.state in ("unavailable", "unknown"):
            continue
        ent_id = state_obj.entity_id
        if (
            has_local_esphome
            and local_ma
            and ent_id == local_ma
            and local_ma != local_speaker
        ):
            continue

        is_local = ent_id in local_ids
        if not is_local:
            reg_ent = ent_reg.async_get(ent_id)
            if reg_ent is None or reg_ent.platform != "music_assistant":
                continue

        friendly = (
            _format_local_speaker_name(hass, state_obj)
            if is_local
            else str(state_obj.attributes.get("friendly_name") or ent_id)
        )
        is_active = (
            (active_speaker in local_ids) if is_local else (ent_id == active_speaker)
        )
        is_last = (last_speaker in local_ids) if is_local else (ent_id == last_speaker)

        items.append(
            {
                "name": friendly,
                "id": local_speaker if (is_local and local_speaker) else ent_id,
                "type": "speaker",
                "active": is_active,
                "_is_local": is_local,
                "_is_last": is_last,
            }
        )

    items.sort(
        key=lambda x: (
            not x["_is_local"],
            not x["active"],
            not x["_is_last"],
            x["name"].lower(),
        )
    )
    for item in items:
        item.pop("_is_local", None)
        item.pop("_is_last", None)
    return items


async def _browse_favorites(
    hass: HomeAssistant, config_entry_id: str
) -> list[dict[str, Any]]:
    """Aggregate favorite playlists, artists, albums, radio, podcasts, audiobooks, tracks concurrently."""
    batches = await asyncio.gather(
        *(
            _call_ma_get_library(
                hass,
                config_entry_id=config_entry_id,
                media_type=mtype,
                favorite=True,
                limit=100,
            )
            for mtype in _FAVORITE_MEDIA_TYPES
        )
    )
    results: list[str | dict[str, Any]] = []
    out: list[dict[str, Any]] = []
    del results
    for mtype, raw_items in zip(_FAVORITE_MEDIA_TYPES, batches, strict=True):
        for item in raw_items:
            uri = str(item.get("uri") or item.get("media_content_id") or "")
            name = str(item.get("name") or item.get("title") or "")
            if not uri or not name:
                continue
            out.append(
                {
                    "name": name,
                    "id": uri,
                    "type": str(item.get("media_type") or mtype),
                    "active": False,
                }
            )
    return out


async def _browse_library_category(
    hass: HomeAssistant,
    config_entry_id: str,
    mode: str,
    album_sort: str,
) -> list[dict[str, Any]]:
    """Browse a top-level Music Assistant library category."""
    order_by: str | None = "name"
    if mode == "album":
        if album_sort == "year_desc":
            order_by = "year_desc"
        elif album_sort == "year":
            order_by = "year"

    raw_items = await _call_ma_get_library(
        hass,
        config_entry_id=config_entry_id,
        media_type=mode,
        limit=500,
        order_by=order_by,
    )

    if mode == "album":
        if album_sort == "year_desc":
            raw_items.sort(
                key=lambda x: (
                    int(x.get("year") or 0),
                    str(x.get("name") or "").lower(),
                ),
                reverse=True,
            )
        elif album_sort == "year":
            raw_items.sort(
                key=lambda x: (
                    int(x.get("year") or 9999),
                    str(x.get("name") or "").lower(),
                )
            )
        else:
            raw_items.sort(key=lambda x: str(x.get("name") or "").lower())

    results: list[dict[str, Any]] = []
    for item in raw_items:
        uri = str(item.get("uri") or item.get("media_content_id") or "")
        name = str(item.get("name") or item.get("title") or "")
        if not uri or not name:
            continue
        year = item.get("year")
        display_name = f"{name} ({year})" if (mode == "album" and year) else name
        results.append(
            {
                "name": display_name,
                "id": uri,
                "type": mode,
                "active": False,
            }
        )
    return results


async def _browse_artist_albums(
    hass: HomeAssistant,
    config_entry_id: str,
    browse_entity: str,
    artist_search: str,
    artist_album_sort: str,
) -> list[dict[str, Any]]:
    """An artist's albums: browse_media on the artist (by URI, or by exact library name)."""
    artist_query = artist_search.strip()
    if not artist_query:
        return []
    artist_uri = artist_query if "://" in artist_query else ""
    if not artist_uri:
        artists = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="artist",
            search=artist_query,
            limit=25,
        )
        q_low = artist_query.lower()
        artist_uri = next(
            (
                str(a.get("uri") or "")
                for a in artists
                if str(a.get("name") or "").strip().lower() == q_low
            ),
            "",
        )
        if not artist_uri:
            return text_slot("Artist not found in the library")

    node = await _browse_ma_node(hass, browse_entity, "artist", artist_uri)
    if node is None:
        return []
    artist_name = str(node.get("title") or "")
    year_order: list[str] = []
    if artist_album_sort in ("year", "year_desc") and artist_name:
        ranked = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="album",
            search=artist_name,
            limit=500,
            order_by=artist_album_sort,
        )
        year_order = [
            str(a.get("uri") or "")
            for a in ranked
            if any(
                _extract_item_dict(x).get("uri") == artist_uri
                for x in a.get("artists") or []
            )
        ]
    return artist_album_slots(node["children"], artist_name, artist_album_sort, year_order)


async def _browse_album_tracks(
    hass: HomeAssistant,
    config_entry_id: str,
    browse_entity: str,
    album_ref: str,
    current_track_title: str,
    current_artist: str = "",
) -> list[dict[str, Any]]:
    """An album's tracks in album order: browse_media on the album (by URI, or by exact library name)."""
    album_ref = album_ref.strip()
    if not album_ref:
        return []
    album_uri = album_ref if "://" in album_ref else ""
    if not album_uri:
        matches = [
            alb
            for alb in await _call_ma_get_library(
                hass,
                config_entry_id=config_entry_id,
                media_type="album",
                search=album_ref,
                limit=50,
            )
            if str(alb.get("name") or "").strip().lower() == album_ref.lower()
        ]
        artist_low = current_artist.strip().lower()
        by_artist = [
            a
            for a in matches
            if artist_low and _extract_artist_name(a).strip().lower() == artist_low
        ]
        chosen = (by_artist or matches)[:1]
        album_uri = str(chosen[0].get("uri") or "") if chosen else ""
        if not album_uri:
            return text_slot("Album not found in the library")

    node = await _browse_ma_node(hass, browse_entity, "album", album_uri)
    if node is None:
        return []
    return album_track_slots(node["children"], current_track_title)


async def _browse_active_queue(
    hass: HomeAssistant,
    speaker: str,
    current_track_title: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Fetch upcoming queue items natively from Music Assistant (`fetch_player_queue_items` + graceful fallback)."""
    from .media import resolve_ma_counterpart_entity

    ma_target = resolve_ma_counterpart_entity(hass, speaker)
    if not ma_target:
        return []

    mass = get_ma_mass_client(hass)
    has_get_queue = hass.services.has_service("music_assistant", "get_queue")
    if not has_get_queue and mass is None:
        return []

    q_data: dict[str, Any] = {}
    current_queue_item_id = ""
    queue_id = ""

    if has_get_queue:
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_target},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict):
                cand_q = resp.get(ma_target) or resp
                if isinstance(cand_q, dict):
                    q_data = cand_q
                    queue_id = str(q_data.get("queue_id") or "").strip()
                    cur_raw = q_data.get("current_item")
                    if cur_raw is not None:
                        cur_dict = _extract_item_dict(cur_raw)
                        current_queue_item_id = str(
                            cur_dict.get("queue_item_id") or ""
                        ).strip()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue failed: %s", err)

    if not queue_id:
        queue_id = resolve_ma_queue_id_sync(hass, ma_target, mass)

    raw_queue_items: list[dict[str, Any]] = []
    if mass is not None and hasattr(mass, "player_queues"):
        pqs = mass.player_queues
        eff_qid = queue_id or ma_target
        if not current_queue_item_id and hasattr(pqs, "get"):
            try:
                q_obj = pqs.get(eff_qid)
                cur_obj = getattr(q_obj, "current_item", None) if q_obj is not None else None
                if cur_obj is not None:
                    current_queue_item_id = str(
                        _extract_item_dict(cur_obj).get("queue_item_id") or ""
                    ).strip()
            except Exception:  # noqa: BLE001
                pass
        if eff_qid and hasattr(pqs, "fetch_player_queue_items"):
            try:
                fetched = await pqs.fetch_player_queue_items(
                    eff_qid, limit=limit, offset=offset
                )
                if isinstance(fetched, Sequence) and not isinstance(
                    fetched, (str, bytes)
                ):
                    raw_queue_items = [_extract_item_dict(x) for x in fetched]
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "mass.player_queues.fetch_player_queue_items(%s) failed: %s",
                    eff_qid,
                    err,
                )

    # Graceful fallback when `mass` runtime client isn't directly reachable.
    # Note: `q_data["items"]` in Music Assistant 2.x is an integer count (e.g. 15),
    # so NEVER use truthy `or` across `q_data.get("items")` without `isinstance(..., list)`.
    if not raw_queue_items and q_data:
        for list_key in ("queue_items", "items"):
            cand_list = q_data.get(list_key)
            if isinstance(cand_list, list) and cand_list:
                raw_queue_items = [_extract_item_dict(x) for x in cand_list]
                break
        if not raw_queue_items:
            cur_raw = q_data.get("current_item")
            if cur_raw is not None:
                cur_d = _extract_item_dict(cur_raw)
                if cur_d:
                    raw_queue_items.append(cur_d)
            nxt_raw = q_data.get("next_item")
            if nxt_raw is not None:
                nxt_d = _extract_item_dict(nxt_raw)
                if nxt_d and (
                    not raw_queue_items
                    or not nxt_d.get("queue_item_id")
                    or nxt_d.get("queue_item_id") != raw_queue_items[0].get("queue_item_id")
                ):
                    raw_queue_items.append(nxt_d)

    raw_count = q_data.get("items")
    q_counts: dict[str, int] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "_ma_queue_counts", {}
    )
    if isinstance(raw_count, int) and not isinstance(raw_count, bool):
        q_counts[ma_target] = max(0, raw_count)
    elif offset == 0:
        q_counts[ma_target] = len(raw_queue_items)

    cur_lower = current_track_title.strip().lower()
    results: list[dict[str, Any]] = []
    for item in raw_queue_items:
        media_item = _extract_item_dict(item.get("media_item") or {})
        name = str(
            item.get("media_title")
            or media_item.get("name")
            or media_item.get("title")
            or item.get("name")
            or item.get("title")
            or ""
        ).strip()
        uri = str(
            media_item.get("uri")
            or item.get("media_content_id")
            or item.get("uri")
            or item.get("queue_item_id")
            or ""
        ).strip()
        artist = (
            str(item.get("media_artist") or "").strip()
            or _extract_artist_name(media_item).strip()
            or _extract_artist_name(item).strip()
        )
        if not name or not uri:
            continue

        queue_item_id = str(item.get("queue_item_id") or "").strip()
        display = f"{name} — {artist}" if artist else name
        if current_queue_item_id:
            is_current = bool(queue_item_id and queue_item_id == current_queue_item_id)
        else:
            is_current = bool(cur_lower and name.lower() == cur_lower)
        results.append(
            {
                "name": display,
                "id": uri,
                "type": "track",
                "queue_item_id": queue_item_id,
                "is_current": is_current,
                "active": is_current,
            }
        )
    return results


async def _browse_podcast_episodes(
    hass: HomeAssistant,
    config_entry_id: str | None,
    browse_entity: str,
    podcast_ref: str,
    podcast_sort: str,
    current_track_title: str,
) -> list[dict[str, Any]]:
    """Fetch podcast episodes natively via MA library + media_player.browse_media."""
    podcast_ref = podcast_ref.strip()
    if not podcast_ref:
        return []

    podcast_uri = podcast_ref if "://" in podcast_ref else ""
    if not podcast_uri and config_entry_id:
        podcasts = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="podcast",
            search=podcast_ref,
            limit=25,
        )
        ref_low = podcast_ref.lower()
        for pod in podcasts:
            if str(pod.get("name") or "").strip().lower() == ref_low:
                podcast_uri = str(pod.get("uri") or "")
                break
        if not podcast_uri and podcasts:
            podcast_uri = str(podcasts[0].get("uri") or "")

    if not podcast_uri:
        podcast_uri = podcast_ref

    node = await _browse_ma_node(hass, browse_entity, "podcast", podcast_uri)
    raw_episodes = node["children"] if node else []

    has_positions = any(
        x.get("position") is not None or x.get("track_number") is not None
        for x in raw_episodes
    )
    if has_positions:
        raw_episodes.sort(
            key=lambda x: int(x.get("position") or x.get("track_number") or 0),
            reverse=(podcast_sort != "oldest"),
        )
    elif podcast_sort == "oldest":
        raw_episodes.reverse()

    cur_lower = current_track_title.strip().lower()
    results: list[dict[str, Any]] = []
    for ep in raw_episodes:
        name = str(ep.get("name") or ep.get("title") or "")
        uri = str(ep.get("uri") or ep.get("media_content_id") or "")
        if not name or not uri:
            continue
        clean_name = re.sub(r"^\d{4}-\d{2}-\d{2}\s*[-:]\s*", "", name)
        is_active = bool(cur_lower and name.strip().lower() == cur_lower)
        results.append(
            {
                "name": clean_name,
                "id": uri,
                "type": "podcast_episode",
                "active": is_active,
            }
        )
    return results


def _resolve_speaker_playing_metadata(
    hass: HomeAssistant, speaker: str
) -> tuple[str, str, str]:
    """Resolve (title, artist, album) for a speaker, falling back to its Music Assistant counterpart."""
    from .media import resolve_ma_counterpart_entity

    state_obj = hass.states.get(speaker) if speaker else None
    attrs = state_obj.attributes if state_obj is not None else {}
    title = str(attrs.get("media_title") or "")
    artist = str(attrs.get("media_artist") or attrs.get("media_album_artist") or "")
    album = str(attrs.get("media_album_name") or "")

    if speaker and (not title or not artist or not album):
        ma_target = resolve_ma_counterpart_entity(hass, speaker)
        if ma_target and ma_target != speaker:
            ma_st = hass.states.get(ma_target)
            if ma_st is not None:
                m_attrs = ma_st.attributes
                if not title:
                    title = str(m_attrs.get("media_title") or "")
                if not artist:
                    artist = str(
                        m_attrs.get("media_artist")
                        or m_attrs.get("media_album_artist")
                        or ""
                    )
                if not album:
                    album = str(m_attrs.get("media_album_name") or "")
    return title, artist, album


def _unwrap_logical_lines(raw_text: str) -> list[str]:
    """Split multi-line text into clean unwrapped logical paragraphs/lines for on-device wrapping."""
    out: list[str] = []
    for raw_line in raw_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or _LRC_META_TAG_RE.match(stripped):
            continue
        cleaned = _LRC_WORD_TAG_RE.sub("", _LRC_TAG_RE.sub("", stripped))
        cleaned = " ".join(cleaned.split())
        if cleaned:
            out.append(cleaned)
    return out


def parse_lrc_lyrics(
    raw_lyrics: str, max_lines: int = MAX_LYRIC_LINES
) -> tuple[bool, list[dict[str, Any]]]:
    """Parse LRC timestamped lyrics (`[mm:ss.xx]` / `[mm:ss.xxx]` / `[mm:ss]`) or plain unwrapped lines."""
    text = str(raw_lyrics or "").strip()
    if not text:
        return False, []

    cap = max(1, int(max_lines))
    synced_entries: list[tuple[int, int, str]] = []
    order_seq = 0

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or _LRC_META_TAG_RE.match(stripped):
            continue
        matches = list(_LRC_TAG_RE.finditer(stripped))
        if not matches:
            continue
        lyric_body = _LRC_WORD_TAG_RE.sub("", _LRC_TAG_RE.sub("", stripped))
        lyric_body = " ".join(lyric_body.split())
        if not lyric_body or _LRC_EMPTY_MARKER_RE.match(lyric_body):
            continue
        for match in matches:
            mins = int(match.group(1))
            secs = int(match.group(2))
            frac = match.group(3)
            if frac is None:
                ms = 0
            elif len(frac) == 1:
                ms = int(frac) * 100
            elif len(frac) == 2:
                ms = int(frac) * 10
            else:
                ms = int(frac[:3])
            t_ms = max(0, (mins * 60 + secs) * 1000 + ms)
            synced_entries.append((t_ms, order_seq, lyric_body))
            order_seq += 1

    if synced_entries:
        synced_entries.sort(key=lambda row: (row[0], row[1]))
        return True, [
            {"t_ms": t_ms, "text": line_text}
            for t_ms, _seq, line_text in synced_entries[:cap]
        ]

    plain_lines = _unwrap_logical_lines(text)
    if not plain_lines:
        return False, []
    return False, [{"t_ms": -1, "text": ln} for ln in plain_lines[:cap]]


def _extract_meta_strings(obj: Any) -> tuple[str, str]:
    """Extract `(lyrics_text, description_text)`, preferring LRC timestamps (`lrc_lyrics`) over plain `lyrics`."""
    d = _extract_item_dict(obj)
    meta = d.get("metadata") if "metadata" in d and d.get("metadata") is not None else d
    if hasattr(meta, "to_dict") and callable(meta.to_dict):
        meta = meta.to_dict()
    if not isinstance(meta, dict):
        meta = _extract_item_dict(meta)
    lyr = str(
        meta.get("lrc_lyrics")
        or meta.get("lyrics")
        or d.get("lrc_lyrics")
        or d.get("lyrics")
        or ""
    ).strip()
    desc = str(meta.get("description") or d.get("description") or "").strip()
    return lyr, desc


def _extract_release_year(obj: Any) -> int | None:
    """Extract a 4-digit release year from a Music Assistant track or album dict/object."""
    d = _extract_item_dict(obj)
    for cand in (
        d.get("year"),
        _extract_item_dict(d.get("album") or {}).get("year"),
    ):
        if cand is None or isinstance(cand, bool):
            continue
        try:
            yr = int(cand)
            if 1000 <= yr <= 2999:
                return yr
        except (TypeError, ValueError):
            continue
    return None


def _normalize_search_metadata(
    hass: HomeAssistant,
    speaker: str,
    search: str,
    fallback_title: str,
    fallback_artist: str = "",
    fallback_album: str = "",
) -> tuple[str, str, str, str, str, str]:
    """Resolve `(title, artist, album, clean_title, clean_album, cache_key)` for lyrics and info lookups."""
    parts = [p.strip() for p in search.split("|")]
    title = parts[0] if len(parts) >= 1 and parts[0] else ""
    artist = parts[1] if len(parts) >= 2 and parts[1] else ""
    album = parts[2] if len(parts) >= 3 and parts[2] else ""

    if not title or not artist or not album:
        cur_title, cur_artist, cur_album = _resolve_speaker_playing_metadata(
            hass, speaker
        )
        if not title:
            title = cur_title or fallback_title
        if not artist:
            artist = cur_artist or fallback_artist
        if not album:
            album = cur_album or fallback_album

    clean_title = re.sub(
        r"\s*[\(\[][^\)\]]*(?:remaster|edition|version|mix|live|deluxe|mono|stereo)[^\)\]]*[\)\]]",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    clean_title = (
        re.sub(
            r"\s*-\s*.*(?:remaster|edition|version|mix|live|deluxe).*$",
            "",
            clean_title,
            flags=re.IGNORECASE,
        ).strip()
        or title.strip()
    )
    clean_album = (
        re.sub(
            r"\s*[\(\[][^\)\]]*(?:remaster|edition|version|deluxe|expanded)[^\)\]]*[\)\]]",
            "",
            album,
            flags=re.IGNORECASE,
        ).strip()
        or album.strip()
    )
    cache_key = f"{clean_title.lower()}|{artist.strip().lower()}|{clean_album.lower()}"
    return title.strip(), artist.strip(), album.strip(), clean_title, clean_album, cache_key


async def _read_current_queue_media_item(
    hass: HomeAssistant, speaker: str
) -> dict[str, Any] | None:
    """Read the current queue item's `media_item` from Music Assistant (live runtime or `get_queue`)."""
    from .media import resolve_ma_counterpart_entity

    ma_target = resolve_ma_counterpart_entity(hass, speaker)
    if not ma_target:
        return None

    if hass.services.has_service("music_assistant", "get_queue"):
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_target},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict):
                q_data = resp.get(ma_target) or resp
                if isinstance(q_data, dict):
                    cur_item = q_data.get("current_item")
                    if cur_item is not None:
                        cur_d = _extract_item_dict(cur_item)
                        m_item = cur_d.get("media_item")
                        if m_item is not None:
                            return _extract_item_dict(m_item)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue metadata lookup failed: %s", err)

    mass = get_ma_mass_client(hass)
    if mass is not None and hasattr(mass, "player_queues"):
        qid = resolve_ma_queue_id_sync(hass, ma_target, mass) or ma_target
        pqs = mass.player_queues
        if hasattr(pqs, "get"):
            try:
                q_obj = pqs.get(qid)
                cur_obj = getattr(q_obj, "current_item", None) if q_obj is not None else None
                m_obj = getattr(cur_obj, "media_item", None) if cur_obj is not None else None
                if m_obj is not None:
                    return _extract_item_dict(m_obj)
            except Exception:  # noqa: BLE001
                pass
    return None


async def async_fetch_track_lyrics(
    hass: HomeAssistant,
    speaker: str,
    search: str = "",
    *,
    fallback_title: str = "",
    fallback_artist: str = "",
    fallback_album: str = "",
    max_lines: int = MAX_LYRIC_LINES,
) -> tuple[str, bool, list[dict[str, Any]]]:
    """Fetch full-track LRC or plain lyrics (`track_key`, `synced`, `lines`), cached in the 64-entry LRU cache."""
    title, artist, album, clean_title, _clean_album, cache_key = _normalize_search_metadata(
        hass,
        speaker,
        search,
        fallback_title=fallback_title,
        fallback_artist=fallback_artist,
        fallback_album=fallback_album,
    )
    track_key = f"{title}|{artist}" if title else ""
    if not clean_title:
        return track_key, False, []

    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached.get("lyrics_payload"), dict):
        payload = cached["lyrics_payload"]
        cached_lines = list(payload.get("lines") or [])[: max(1, int(max_lines))]
        return track_key, bool(payload.get("synced")), cached_lines

    raw_lyrics = ""
    raw_album_bio = ""
    release_year: int | None = None

    m_item = await _read_current_queue_media_item(hass, speaker)
    if m_item is not None:
        lyr, desc = _extract_meta_strings(m_item)
        if lyr:
            raw_lyrics = lyr
        if desc:
            raw_album_bio = desc
        release_year = _extract_release_year(m_item)

    config_entry_id = _get_ma_config_entry_id(hass)
    if config_entry_id and (not raw_lyrics or "[" not in raw_lyrics) and clean_title:
        tracks = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="track",
            search=clean_title,
            limit=10,
        )
        fallback_plain = raw_lyrics
        for trk in tracks:
            lyr, _ = _extract_meta_strings(trk)
            if not lyr:
                continue
            if "[" in lyr and _LRC_TAG_RE.search(lyr):
                raw_lyrics = lyr
                break
            if not fallback_plain:
                fallback_plain = lyr
        if not raw_lyrics and fallback_plain:
            raw_lyrics = fallback_plain

    if (not raw_lyrics or not _LRC_TAG_RE.search(raw_lyrics)) and clean_title:
        session = async_get_clientsession(hass)
        timeout = aiohttp.ClientTimeout(total=5.0)
        headers = {
            "User-Agent": f"HomeAssistant-Latter/{INTEGRATION_VERSION} (https://github.com/slampton/ha-latter)"
        }
        plain_fallback = raw_lyrics
        for s_title in (
            [title, clean_title]
            if clean_title.lower() != title.lower()
            else [clean_title]
        ):
            if raw_lyrics and _LRC_TAG_RE.search(raw_lyrics):
                break
            try:
                q_url = f"https://lrclib.net/api/search?track_name={quote(s_title)}"
                if artist:
                    q_url += f"&artist_name={quote(artist)}"
                async with session.get(
                    q_url, timeout=timeout, headers=headers
                ) as resp:
                    if resp.status == 200:
                        items = await resp.json()
                        if isinstance(items, list) and items:
                            synced_hit = next(
                                (
                                    str(cand.get("syncedLyrics") or "").strip()
                                    for cand in items[:5]
                                    if isinstance(cand, dict)
                                    and str(cand.get("syncedLyrics") or "").strip()
                                ),
                                "",
                            )
                            if synced_hit:
                                raw_lyrics = synced_hit
                                break
                            first = items[0]
                            if isinstance(first, dict) and not plain_fallback:
                                plain_fallback = str(
                                    first.get("syncedLyrics")
                                    or first.get("plainLyrics")
                                    or ""
                                ).strip()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("LRCLIB fallback failed for '%s': %s", s_title, err)
        if not raw_lyrics and plain_fallback:
            raw_lyrics = plain_fallback

    synced, parsed_lines = parse_lrc_lyrics(raw_lyrics, max_lines=MAX_LYRIC_LINES)
    if parsed_lines:
        cache_entry = _cache_put(cache_key)
        cache_entry["lyrics_payload"] = {"synced": synced, "lines": parsed_lines}
        cache_entry["lyrics"] = [str(row["text"]) for row in parsed_lines]
        if raw_album_bio and "bio" not in cache_entry:
            bio_seed: list[str] = []
            if artist:
                bio_seed.append(f"Artist: {artist}")
            if album:
                bio_seed.append(f"Album: {album}")
            if release_year:
                bio_seed.append(f"Release: {release_year}")
            bio_seed.extend(_unwrap_logical_lines(f"Album: {raw_album_bio}"))
            cache_entry["bio"] = bio_seed

    return track_key, synced, parsed_lines[: max(1, int(max_lines))]


async def _browse_track_lyrics_or_bio(
    hass: HomeAssistant,
    config_entry_id: str | None,
    speaker: str,
    mode: str,
    search: str,
    fallback_title: str,
    fallback_artist: str = "",
    fallback_album: str = "",
) -> list[dict[str, Any]]:
    """Fetch unwrapped lyrics or artist/album info from Music Assistant + LRCLIB/Wikipedia via 64-entry LRU cache."""
    if mode == "lyrics":
        _tkey, _synced, parsed_lines = await async_fetch_track_lyrics(
            hass,
            speaker,
            search,
            fallback_title=fallback_title,
            fallback_artist=fallback_artist,
            fallback_album=fallback_album,
        )
        if not parsed_lines:
            return [
                {
                    "name": "No lyrics found for this track.",
                    "id": "",
                    "type": "text",
                    "active": False,
                }
            ]
        return [
            {"name": str(row["text"]), "id": "", "type": "text", "active": False}
            for row in parsed_lines
        ]

    _title, artist, album, clean_title, clean_album, cache_key = _normalize_search_metadata(
        hass,
        speaker,
        search,
        fallback_title=fallback_title,
        fallback_artist=fallback_artist,
        fallback_album=fallback_album,
    )
    cached = _cache_get(cache_key)
    if cached is not None and cached.get("bio"):
        return [
            {"name": ln, "id": "", "type": "text", "active": False}
            for ln in cached["bio"]
        ]

    raw_lyrics = ""
    raw_artist_bio = ""
    raw_album_bio = ""
    release_year: int | None = None

    m_item = await _read_current_queue_media_item(hass, speaker)
    if m_item is not None:
        lyr, desc = _extract_meta_strings(m_item)
        if lyr:
            raw_lyrics = lyr
        if desc:
            raw_album_bio = desc
        release_year = _extract_release_year(m_item)

    if config_entry_id:
        if not raw_artist_bio and artist:
            artists = await _call_ma_get_library(
                hass,
                config_entry_id=config_entry_id,
                media_type="artist",
                search=artist,
                limit=5,
            )
            for ar_obj in artists:
                _, desc = _extract_meta_strings(ar_obj)
                if desc:
                    raw_artist_bio = desc
                    break

        if (not raw_album_bio or release_year is None) and clean_album:
            albums = await _call_ma_get_library(
                hass,
                config_entry_id=config_entry_id,
                media_type="album",
                search=clean_album,
                limit=5,
            )
            for al_obj in albums:
                if release_year is None:
                    release_year = _extract_release_year(al_obj)
                _, desc = _extract_meta_strings(al_obj)
                if desc and not raw_album_bio:
                    raw_album_bio = desc
                if raw_album_bio and release_year is not None:
                    break

    if not raw_artist_bio and not raw_album_bio and artist:
        session = async_get_clientsession(hass)
        timeout = aiohttp.ClientTimeout(total=5.0)
        headers = {
            "User-Agent": f"HomeAssistant-Latter/{INTEGRATION_VERSION} (https://github.com/slampton/ha-latter)"
        }
        for query_term in (
            f"{clean_album} ({artist} album)" if clean_album else "",
            f"{artist} (band)",
            f"{artist} (musician)",
            artist,
            clean_album,
        ):
            if not query_term:
                continue
            try:
                wiki_title = quote(query_term.replace(" ", "_"))
                w_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title}"
                async with session.get(w_url, timeout=timeout, headers=headers) as resp:
                    if resp.status == 200:
                        w_data = await resp.json()
                        extract = str(w_data.get("extract") or "").strip()
                        w_type = str(w_data.get("type") or "")
                        if extract and w_type != "disambiguation" and len(extract) > 40:
                            raw_artist_bio = extract
                            break
            except Exception:  # noqa: BLE001
                pass

    bio_lines: list[str] = []
    if artist:
        bio_lines.append(f"Artist: {artist}")
    if album or clean_album:
        bio_lines.append(f"Album: {album or clean_album}")
    if release_year is not None:
        bio_lines.append(f"Release: {release_year}")

    rich_paragraphs: list[str] = []
    if raw_album_bio:
        rich_paragraphs.extend(_unwrap_logical_lines(raw_album_bio))
    if raw_artist_bio and raw_artist_bio != raw_album_bio:
        rich_paragraphs.extend(_unwrap_logical_lines(raw_artist_bio))

    has_rich_bio = bool(rich_paragraphs)
    bio_lines.extend(rich_paragraphs)
    if not bio_lines:
        bio_lines = [
            f"{clean_title or 'Unknown Track'} by {artist or 'Unknown Artist'}"
            + (f" — {clean_album}" if clean_album else "")
        ]

    cache_entry = _cache_put(cache_key)
    if has_rich_bio:
        cache_entry["bio"] = bio_lines
    if raw_lyrics and "lyrics_payload" not in cache_entry:
        synced, parsed_lines = parse_lrc_lyrics(raw_lyrics, max_lines=MAX_LYRIC_LINES)
        if parsed_lines:
            cache_entry["lyrics_payload"] = {"synced": synced, "lines": parsed_lines}
            cache_entry["lyrics"] = [str(row["text"]) for row in parsed_lines]

    return [
        {"name": ln, "id": "", "type": "text", "active": False} for ln in bio_lines
    ]


async def async_browse_media_items(
    hass: HomeAssistant,
    mode: str,
    speaker: str,
    last_speaker: str,
    local_speaker: str,
    search: str = "",
    default_speaker: str = "",
    album_sort: str = "name",
    artist_album_sort: str = "year",
    podcast_sort: str = "newest",
    fallback_title: str = "",
    fallback_artist: str = "",
    fallback_album: str = "",
    *,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Execute the requested browse mode and return a flat list of slot dicts."""
    mode = mode.strip().lower()

    if mode == "speakers":
        return await _browse_speakers(hass, speaker, last_speaker, local_speaker)

    current_title, current_artist, current_album = _resolve_speaker_playing_metadata(
        hass, speaker
    )
    if not current_title and fallback_title:
        current_title = fallback_title
    if not current_artist and fallback_artist:
        current_artist = fallback_artist
    if not current_album and fallback_album:
        current_album = fallback_album

    if mode == "active_queue":
        return await _browse_active_queue(
            hass, speaker, current_title, limit=50, offset=max(0, int(offset))
        )

    config_entry_id = _get_ma_config_entry_id(hass)
    if mode in ("lyrics", "bio", "track_info"):
        return await _browse_track_lyrics_or_bio(
            hass,
            config_entry_id,
            speaker,
            "bio" if mode == "track_info" else mode,
            search,
            current_title,
            current_artist,
            current_album,
        )

    browse_entity = ""
    if mode in (
        "podcast_episodes",
        "artist_albums",
        "album_tracks",
        "current_album_tracks",
    ):
        browse_entity = (
            _ma_browse_entity(hass, [local_speaker, default_speaker, speaker]) or ""
        )
        if not browse_entity:
            return text_slot(NO_MA_PLAYER_TEXT)

    if mode == "podcast_episodes":
        return await _browse_podcast_episodes(
            hass, config_entry_id, browse_entity, search, podcast_sort, current_title
        )

    if not config_entry_id:
        _LOGGER.warning(
            "Music Assistant integration not found or not loaded in Home Assistant."
        )
        return []

    if mode == "favorites":
        return await _browse_favorites(hass, config_entry_id)

    if mode in LIBRARY_MEDIA_TYPES:
        return await _browse_library_category(hass, config_entry_id, mode, album_sort)

    if mode == "artist_albums":
        return await _browse_artist_albums(
            hass, config_entry_id, browse_entity, search, artist_album_sort
        )

    if mode == "album_tracks":
        return await _browse_album_tracks(
            hass,
            config_entry_id,
            browse_entity,
            search,
            current_title,
            current_artist,
        )

    if mode == "current_album_tracks":
        album_ref = search.strip() or current_album
        return await _browse_album_tracks(
            hass,
            config_entry_id,
            browse_entity,
            album_ref,
            current_title,
            current_artist,
        )

    _LOGGER.warning("Unknown Latter music_browse mode: %s", mode)
    return []
