"""Music Assistant & Home Assistant media browse engine."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping, Sequence
import logging
import re
from typing import Any, Final

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..hub_registry import get_area_state_index, get_domain_data
from .linking import (
    get_ma_mass_client,
    resolve_ma_counterpart_entity,
    resolve_ma_queue_id_sync,
    safe_int,
)
from .lyrics import (
    BROWSE_LYRICS_BIO_CACHE as BROWSE_LYRICS_BIO_CACHE,
    browse_track_lyrics_or_bio,
    cache_get as cache_get,
    cache_put as cache_put,
    call_ma_get_library,
    clear_lyrics_cache,
    extract_artist_name,
    extract_item_dict as extract_item_dict,
    get_ma_config_entry_id,
    resolve_speaker_playing_metadata,
)

_LOGGER = logging.getLogger(__name__)

ARTIST_SEPARATOR: Final = " - "
NO_MA_PLAYER_TEXT: Final = "No Music Assistant player to browse with"
_UNKNOWN_YEAR_SORT_FALLBACK: Final[int] = 9999
_MUSIC_SUFFIX_LEN: Final[int] = 6

LIBRARY_MEDIA_TYPES: set[str] = {
    "playlist",
    "artist",
    "album",
    "radio",
    "podcast",
    "audiobook",
    "track",
}

_FAVORITE_MEDIA_TYPES: Final[tuple[str, ...]] = (
    "playlist",
    "artist",
    "album",
    "radio",
    "podcast",
    "audiobook",
    "track",
)


def clear_browse_cache() -> None:
    """Clear the bounded LRU browse & lyrics caches on unload."""
    clear_lyrics_cache()


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
    """Return a `media_player.browse_media` result as a dict, or None."""
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
    """Drop a leading `'<artist> - '` when it names the given artist."""
    prefix = f"{artist}{ARTIST_SEPARATOR}"
    if artist and title.lower().startswith(prefix.lower()) and len(title) > len(prefix):
        return title[len(prefix) :].strip()
    return title


def common_artist(titles: Sequence[str]) -> str:
    """Return the artist every `'<artist> - <title>'` shares, or `''`."""
    artists = {t.split(ARTIST_SEPARATOR, 1)[0] for t in titles if ARTIST_SEPARATOR in t}
    if len(artists) == 1 and all(ARTIST_SEPARATOR in t for t in titles):
        return artists.pop()
    return ""


def album_track_slots(
    children: Iterable[Mapping[str, Any]], current_title: str = ""
) -> list[dict[str, Any]]:
    """Browse slots for an album's tracks in Music Assistant's full order, numbered 1..N."""
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
    """Browse slots for an artist's albums."""
    albums = [
        c
        for c in children
        if _child_uri(c)
        and _child_title(c)
        and (
            "album"
            in str(c.get("media_class") or c.get("media_content_type") or "").lower()
            or "://album/" in _child_uri(c)
        )
    ]
    rows = [(strip_artist_prefix(_child_title(c), artist), _child_uri(c)) for c in albums]
    if sort == "name":
        rows.sort(key=lambda r: r[0].lower())
    elif year_order:
        rank = {uri: i for i, uri in enumerate(year_order)}
        rows = sorted(rows, key=lambda r: rank.get(r[1], len(rank)))
    return [
        {"name": name, "id": uri, "type": "album", "active": False} for name, uri in rows
    ]


def text_slot(message: str) -> list[dict[str, Any]]:
    """One non-playable slot that tells the user why the list is empty."""
    return [{"name": message, "id": "", "type": "text", "active": False}]


def _ma_browse_entity(hass: HomeAssistant, preferred_speakers: list[str]) -> str | None:
    entry_id = get_ma_config_entry_id(hass)
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
    node["children"] = [extract_item_dict(c) for c in node.get("children") or []]
    return node


async def async_lookup_ma_track_uri(
    hass: HomeAssistant, title: str, artist: str = ""
) -> str:
    """Resolve a track URI from the Music Assistant library by exact case-insensitive title."""
    want_title = title.strip().lower()
    if not want_title:
        return ""
    entry_id = get_ma_config_entry_id(hass)
    if not entry_id:
        return ""
    items = await call_ma_get_library(
        hass, entry_id, "track", search=title.strip(), limit=25
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
        cand_artist = extract_artist_name(item).strip().lower()
        if want_artist and cand_artist == want_artist:
            return uri
        if not fallback_uri:
            fallback_uri = uri
    return fallback_uri


def _format_local_speaker_name(hass: HomeAssistant, state_obj: State) -> str:
    friendly = str(state_obj.attributes.get("friendly_name") or state_obj.entity_id)
    entry = er.async_get(hass).async_get(state_obj.entity_id)
    if entry and entry.device_id:
        dev = dr.async_get(hass).async_get(entry.device_id)
        if dev and (dev_name := str(dev.name_by_user or dev.name or "").strip()):
            return dev_name
    if friendly.lower().endswith(" music") and len(friendly) > _MUSIC_SUFFIX_LEN:
        return friendly[:-_MUSIC_SUFFIX_LEN].strip()
    return friendly


async def _browse_speakers(
    hass: HomeAssistant, active_speaker: str, last_speaker: str, local_speaker: str
) -> list[dict[str, Any]]:
    local_ma = resolve_ma_counterpart_entity(hass, local_speaker) if local_speaker else None
    local_ids = {s for s in (local_speaker, local_ma) if s}
    has_local_esphome = bool(
        local_speaker
        and (st_loc := hass.states.get(local_speaker)) is not None
        and st_loc.state not in ("unavailable", "unknown")
    )

    ent_reg = er.async_get(hass)
    ranked_rows: list[tuple[tuple[bool, bool, bool, str], dict[str, Any]]] = []
    for state_obj in get_area_state_index(hass).states_for_domain("media_player"):
        if state_obj.state in ("unavailable", "unknown"):
            continue
        ent_id = state_obj.entity_id
        if has_local_esphome and local_ma and ent_id == local_ma and local_ma != local_speaker:
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
        is_active = (active_speaker in local_ids) if is_local else (ent_id == active_speaker)
        is_last = (last_speaker in local_ids) if is_local else (ent_id == last_speaker)
        sort_key = (not is_local, not is_active, not is_last, friendly.lower())
        ranked_rows.append(
            (
                sort_key,
                {
                    "name": friendly,
                    "id": local_speaker if (is_local and local_speaker) else ent_id,
                    "type": "speaker",
                    "active": is_active,
                },
            )
        )

    ranked_rows.sort(key=lambda pair: pair[0])
    return [slot for _key, slot in ranked_rows]


async def _browse_favorites(
    hass: HomeAssistant, config_entry_id: str
) -> list[dict[str, Any]]:
    batches = await asyncio.gather(
        *(
            call_ma_get_library(hass, config_entry_id, mtype, favorite=True, limit=100)
            for mtype in _FAVORITE_MEDIA_TYPES
        )
    )
    out: list[dict[str, Any]] = []
    for mtype, raw_items in zip(_FAVORITE_MEDIA_TYPES, batches, strict=True):
        for item in raw_items:
            uri = str(item.get("uri") or item.get("media_content_id") or "")
            name = str(item.get("name") or item.get("title") or "")
            if uri and name:
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
    hass: HomeAssistant, config_entry_id: str, mode: str, album_sort: str
) -> list[dict[str, Any]]:
    order_by = (
        album_sort
        if (mode == "album" and album_sort in ("year_desc", "year"))
        else "name"
    )
    raw_items = await call_ma_get_library(
        hass, config_entry_id, mode, limit=500, order_by=order_by
    )

    if mode == "album":
        if album_sort == "year_desc":
            raw_items.sort(
                key=lambda x: (safe_int(x.get("year"), 0), str(x.get("name") or "").lower()),
                reverse=True,
            )
        elif album_sort == "year":
            raw_items.sort(
                key=lambda x: (
                    safe_int(x.get("year") or _UNKNOWN_YEAR_SORT_FALLBACK, _UNKNOWN_YEAR_SORT_FALLBACK),
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
        results.append({"name": display_name, "id": uri, "type": mode, "active": False})
    return results


async def _browse_artist_albums(
    hass: HomeAssistant,
    config_entry_id: str,
    browse_entity: str,
    artist_search: str,
    artist_album_sort: str,
) -> list[dict[str, Any]]:
    artist_query = artist_search.strip()
    if not artist_query:
        return []
    artist_uri = artist_query if "://" in artist_query else ""
    if not artist_uri:
        artists = await call_ma_get_library(
            hass, config_entry_id, "artist", search=artist_query, limit=25
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
        ranked = await call_ma_get_library(
            hass,
            config_entry_id,
            "album",
            search=artist_name,
            limit=500,
            order_by=artist_album_sort,
        )
        year_order = [
            str(a.get("uri") or "")
            for a in ranked
            if any(extract_item_dict(x).get("uri") == artist_uri for x in a.get("artists") or [])
        ]
    return artist_album_slots(node["children"], artist_name, artist_album_sort, year_order)


async def _browse_album_tracks(
    hass: HomeAssistant,
    config_entry_id: str,
    browse_entity: str,
    album_ref: str,
    current_meta: tuple[str, str],
) -> list[dict[str, Any]]:
    current_track_title, current_artist = current_meta
    album_ref = album_ref.strip()
    if not album_ref:
        return []
    album_uri = album_ref if "://" in album_ref else ""
    if not album_uri:
        matches = [
            alb
            for alb in await call_ma_get_library(
                hass, config_entry_id, "album", search=album_ref, limit=50
            )
            if str(alb.get("name") or "").strip().lower() == album_ref.lower()
        ]
        artist_low = current_artist.strip().lower()
        by_artist = [
            a
            for a in matches
            if artist_low and extract_artist_name(a).strip().lower() == artist_low
        ]
        chosen = (by_artist or matches)[:1]
        album_uri = str(chosen[0].get("uri") or "") if chosen else ""
        if not album_uri:
            return text_slot("Album not found in the library")

    node = await _browse_ma_node(hass, browse_entity, "album", album_uri)
    return album_track_slots(node["children"], current_track_title) if node else []


async def _fetch_ma_queue_metadata_and_items(
    hass: HomeAssistant, ma_target: str, mass: Any | None, limit: int, offset: int
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    q_data: dict[str, Any] = {}
    current_queue_item_id = ""
    queue_id = ""
    if hass.services.has_service("music_assistant", "get_queue"):
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_target},
                blocking=True,
                return_response=True,
            )
            cand_q = (resp.get(ma_target) or resp) if isinstance(resp, dict) else None
            if isinstance(cand_q, dict):
                q_data = cand_q
                queue_id = str(q_data.get("queue_id") or "").strip()
                if (cur_raw := q_data.get("current_item")) is not None:
                    current_queue_item_id = str(
                        extract_item_dict(cur_raw).get("queue_item_id") or ""
                    ).strip()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue failed: %s", err)

    queue_id = queue_id or resolve_ma_queue_id_sync(hass, ma_target, mass)
    raw_queue_items: list[dict[str, Any]] = []
    pqs = getattr(mass, "player_queues", None) if mass is not None else None
    if pqs is not None:
        eff_qid = queue_id or ma_target
        if not current_queue_item_id and hasattr(pqs, "get"):
            try:
                q_obj = pqs.get(eff_qid)
                cur_obj = getattr(q_obj, "current_item", None) if q_obj is not None else None
                if cur_obj is not None:
                    current_queue_item_id = str(
                        extract_item_dict(cur_obj).get("queue_item_id") or ""
                    ).strip()
            except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as err:
                _LOGGER.debug("Reading current queue item for %s skipped: %s", eff_qid, err)
        if eff_qid and hasattr(pqs, "fetch_player_queue_items"):
            try:
                fetched = await pqs.fetch_player_queue_items(eff_qid, limit=limit, offset=offset)
                if isinstance(fetched, Sequence) and not isinstance(fetched, (str, bytes)):
                    raw_queue_items = [extract_item_dict(x) for x in fetched]
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "mass.player_queues.fetch_player_queue_items(%s) failed: %s", eff_qid, err
                )
    return q_data, current_queue_item_id, raw_queue_items


def _fallback_queue_items_from_get_queue(q_data: dict[str, Any]) -> list[dict[str, Any]]:
    for list_key in ("queue_items", "items"):
        cand_list = q_data.get(list_key)
        if isinstance(cand_list, list) and cand_list:
            return [extract_item_dict(x) for x in cand_list]
    out: list[dict[str, Any]] = []
    if (cur_raw := q_data.get("current_item")) is not None and (
        cur_d := extract_item_dict(cur_raw)
    ):
        out.append(cur_d)
    if (
        (nxt_raw := q_data.get("next_item")) is not None
        and (nxt_d := extract_item_dict(nxt_raw))
        and (
            not out
            or not nxt_d.get("queue_item_id")
            or nxt_d.get("queue_item_id") != out[0].get("queue_item_id")
        )
    ):
        out.append(nxt_d)
    return out


async def _browse_active_queue(
    hass: HomeAssistant,
    speaker: str,
    current_track_title: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    ma_target = resolve_ma_counterpart_entity(hass, speaker)
    if not ma_target:
        return []
    mass = get_ma_mass_client(hass)
    if not hass.services.has_service("music_assistant", "get_queue") and mass is None:
        return []

    q_data, current_queue_item_id, raw_queue_items = await _fetch_ma_queue_metadata_and_items(
        hass, ma_target, mass, limit, offset
    )
    if not raw_queue_items and q_data:
        raw_queue_items = _fallback_queue_items_from_get_queue(q_data)

    raw_count = q_data.get("items")
    q_counts = get_domain_data(hass).ma_queue_counts
    if isinstance(raw_count, int) and not isinstance(raw_count, bool):
        q_counts[ma_target] = max(0, raw_count)
    elif offset == 0:
        q_counts[ma_target] = len(raw_queue_items)

    cur_lower = current_track_title.strip().lower()
    results: list[dict[str, Any]] = []
    for item in raw_queue_items:
        media_item = extract_item_dict(item.get("media_item") or {})
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
            or extract_artist_name(media_item).strip()
            or extract_artist_name(item).strip()
        )
        if not name or not uri:
            continue
        queue_item_id = str(item.get("queue_item_id") or "").strip()
        is_current = (
            bool(queue_item_id and queue_item_id == current_queue_item_id)
            if current_queue_item_id
            else bool(cur_lower and name.lower() == cur_lower)
        )
        results.append(
            {
                "name": f"{name} — {artist}" if artist else name,
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
    sort_and_title: tuple[str, str],
) -> list[dict[str, Any]]:
    podcast_sort, current_track_title = sort_and_title
    podcast_ref = podcast_ref.strip()
    if not podcast_ref:
        return []
    podcast_uri = podcast_ref if "://" in podcast_ref else ""
    if not podcast_uri and config_entry_id:
        podcasts = await call_ma_get_library(
            hass, config_entry_id, "podcast", search=podcast_ref, limit=25
        )
        ref_low = podcast_ref.lower()
        podcast_uri = next(
            (
                str(pod.get("uri") or "")
                for pod in podcasts
                if str(pod.get("name") or "").strip().lower() == ref_low
            ),
            str(podcasts[0].get("uri") or "") if podcasts else "",
        )
    podcast_uri = podcast_uri or podcast_ref

    node = await _browse_ma_node(hass, browse_entity, "podcast", podcast_uri)
    raw_episodes = node["children"] if node else []
    if any(
        x.get("position") is not None or x.get("track_number") is not None
        for x in raw_episodes
    ):
        raw_episodes.sort(
            key=lambda x: safe_int(x.get("position") or x.get("track_number"), 0),
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
        results.append(
            {
                "name": re.sub(r"^\d{4}-\d{2}-\d{2}\s*[-:]\s*", "", name),
                "id": uri,
                "type": "podcast_episode",
                "active": bool(cur_lower and name.strip().lower() == cur_lower),
            }
        )
    return results


async def _dispatch_library_browse_mode(
    hass: HomeAssistant,
    mode: str,
    config_entry_id: str,
    browse_entity: str,
    params: tuple[str, str, str, str, str],
) -> list[dict[str, Any]]:
    search, album_sort, artist_album_sort, current_title, current_artist = params
    if mode == "favorites":
        return await _browse_favorites(hass, config_entry_id)
    if mode in LIBRARY_MEDIA_TYPES:
        return await _browse_library_category(hass, config_entry_id, mode, album_sort)
    if mode == "artist_albums":
        return await _browse_artist_albums(
            hass, config_entry_id, browse_entity, search, artist_album_sort
        )
    if mode in ("album_tracks", "current_album_tracks"):
        return await _browse_album_tracks(
            hass,
            config_entry_id,
            browse_entity,
            search,
            (current_title, current_artist),
        )
    _LOGGER.warning("Unknown Latter music_browse mode: %s", mode)
    return []


async def _dispatch_ma_browse_tail(
    hass: HomeAssistant,
    mode: str,
    config_entry_id: str | None,
    speakers: tuple[str, str, str],
    params: tuple[str, str, str, str, str, str, str],
) -> list[dict[str, Any]]:
    local_speaker, default_speaker, speaker = speakers
    search, album_sort, artist_album_sort, podcast_sort, cur_title, cur_artist, cur_album = params
    browse_entity = ""
    if mode in ("podcast_episodes", "artist_albums", "album_tracks", "current_album_tracks"):
        browse_entity = _ma_browse_entity(hass, [local_speaker, default_speaker, speaker]) or ""
        if not browse_entity:
            return text_slot(NO_MA_PLAYER_TEXT)
    if mode == "podcast_episodes":
        return await _browse_podcast_episodes(
            hass, config_entry_id, browse_entity, search, (podcast_sort, cur_title)
        )
    if not config_entry_id:
        _LOGGER.warning("Music Assistant integration not found or not loaded in Home Assistant.")
        return []
    eff_search = (search.strip() or cur_album) if mode == "current_album_tracks" else search
    return await _dispatch_library_browse_mode(
        hass,
        mode,
        config_entry_id,
        browse_entity,
        (eff_search, album_sort, artist_album_sort, cur_title, cur_artist),
    )


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

    cur_title, cur_artist, cur_album = resolve_speaker_playing_metadata(hass, speaker)
    current_title = cur_title or fallback_title
    current_artist = cur_artist or fallback_artist
    current_album = cur_album or fallback_album

    if mode == "active_queue":
        return await _browse_active_queue(
            hass, speaker, current_title, limit=50, offset=max(0, safe_int(offset, 0))
        )

    config_entry_id = get_ma_config_entry_id(hass)
    if mode in ("lyrics", "bio", "track_info"):
        return await browse_track_lyrics_or_bio(
            hass,
            config_entry_id,
            speaker,
            "bio" if mode == "track_info" else mode,
            search,
            current_title,
            current_artist,
            current_album,
        )

    return await _dispatch_ma_browse_tail(
        hass,
        mode,
        config_entry_id,
        (local_speaker, default_speaker, speaker),
        (
            search,
            album_sort,
            artist_album_sort,
            podcast_sort,
            current_title,
            current_artist,
            current_album,
        ),
    )
