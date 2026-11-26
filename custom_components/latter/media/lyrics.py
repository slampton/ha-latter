"""Zero-WAN Music Assistant LRC/plain lyrics parser, 64-entry LRU cache, and chunk pusher."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Sequence
import logging
import math
import re
import time
from typing import Any, Final

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from ..identity import esphome_service
from ..protocol_codec import escape_v3_subfield, unescape_v3_subfield, utf8_safe_truncate
from .linking import (
    get_ma_mass_client,
    resolve_ma_counterpart_entity,
    resolve_ma_queue_id_sync,
    safe_int,
)

_LOGGER = logging.getLogger(__name__)

LYRICS_CHUNK_SIZE: Final[int] = 32
MAX_LYRIC_LINES: Final[int] = 128
NEGATIVE_CACHE_TTL_SECONDS: Final[float] = 300.0
_MAX_LYRICS_CACHE_ENTRIES: Final[int] = 64
_MIN_RELEASE_YEAR: Final[int] = 1000
_MAX_RELEASE_YEAR: Final[int] = 2999
_MAX_TRACK_KEY_BYTES: Final[int] = 160
_MAX_LYRIC_LINE_BYTES: Final[int] = 200
_SEARCH_ARTIST_IDX: Final[int] = 2
_SEARCH_ALBUM_IDX: Final[int] = 3
_FRAC_TWO_DIGITS: Final[int] = 2

BROWSE_LYRICS_BIO_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_LRC_TAG_RE: Final = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
_LRC_WORD_TAG_RE: Final = re.compile(r"<\d{1,3}:\d{2}(?:[.:]\d{1,3})?>")
_LRC_META_TAG_RE: Final = re.compile(
    r"^\[(?:ar|ti|al|au|by|length|offset|re|ve|tool|id|la):[^\]]*\]$",
    re.IGNORECASE,
)
_LRC_EMPTY_MARKER_RE: Final = re.compile(r"^[\s♪♫♬♩·•…\-\u2013\u2014~*._|/\\]+$")
_UNSAFE_CTRL_RE: Final = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]+")

_ITEM_DICT_ATTRS: Final[tuple[str, ...]] = (
    "name",
    "title",
    "uri",
    "item_id",
    "provider",
    "provider_instance",
    "provider_domain",
    "provider_mappings",
    "stream_details",
    "available",
    "priority",
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
)


def clear_lyrics_cache() -> None:
    """Clear the bounded 64-entry LRU lyrics and artist/album metadata cache."""
    BROWSE_LYRICS_BIO_CACHE.clear()


def cache_get(cache_key: str) -> dict[str, Any] | None:
    """Fetch an entry from the bounded 64-entry LRU lyrics/bio cache."""
    cached = BROWSE_LYRICS_BIO_CACHE.get(cache_key)
    if cached is not None:
        BROWSE_LYRICS_BIO_CACHE.move_to_end(cache_key)
    return cached


def cache_put(cache_key: str, entry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Insert or touch an entry in the bounded 64-entry LRU lyrics/bio cache."""
    if entry is not None:
        BROWSE_LYRICS_BIO_CACHE[cache_key] = entry
    bucket = BROWSE_LYRICS_BIO_CACHE.setdefault(cache_key, {})
    BROWSE_LYRICS_BIO_CACHE.move_to_end(cache_key)
    while len(BROWSE_LYRICS_BIO_CACHE) > _MAX_LYRICS_CACHE_ENTRIES:
        BROWSE_LYRICS_BIO_CACHE.popitem(last=False)
    return bucket


def extract_item_dict(raw: Any) -> dict[str, Any]:
    """Convert a Music Assistant model, `BrowseMedia` dict, or object into a normalized dict."""
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "as_dict") and callable(raw.as_dict):
        as_dict_res = raw.as_dict()
        if isinstance(as_dict_res, dict):
            return as_dict_res
    if hasattr(raw, "to_dict") and callable(raw.to_dict):
        try:
            to_dict_res = raw.to_dict()
            if isinstance(to_dict_res, dict):
                return to_dict_res
        except (AttributeError, TypeError, ValueError, RuntimeError) as err:
            _LOGGER.debug("to_dict() conversion skipped: %s", err)
    result: dict[str, Any] = {}
    for attr in _ITEM_DICT_ATTRS:
        if hasattr(raw, attr):
            val = getattr(raw, attr)
            if hasattr(val, "value"):
                val = val.value
            result[attr] = val
    return result


def extract_artist_name(item: dict[str, Any]) -> str:
    """Extract primary artist name from a Music Assistant item dict."""
    if item.get("artist_str"):
        return str(item["artist_str"])
    artists = item.get("artists")
    if isinstance(artists, list) and artists:
        first = extract_item_dict(artists[0])
        if first.get("name"):
            return str(first["name"])
    artist = item.get("artist")
    if isinstance(artist, dict) and artist.get("name"):
        return str(artist["name"])
    return artist if isinstance(artist, str) and artist else ""


def get_ma_config_entry_id(hass: HomeAssistant) -> str | None:
    """Auto-discover the loaded Music Assistant `config_entry_id`."""
    entries = hass.config_entries.async_entries("music_assistant")
    for entry in entries:
        if entry.state is ConfigEntryState.LOADED:
            return str(entry.entry_id)
    return str(entries[0].entry_id) if entries else None


async def call_ma_get_library(
    hass: HomeAssistant,
    config_entry_id: str,
    media_type: str,
    *,
    favorite: bool | None = None,
    search: str | None = None,
    limit: int = 500,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    """Call `music_assistant.get_library` and return normalized item dicts."""
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
    return [extract_item_dict(x) for x in raw_items] if isinstance(raw_items, list) else []


def resolve_speaker_playing_metadata(
    hass: HomeAssistant, speaker: str
) -> tuple[str, str, str]:
    """Resolve `(title, artist, album)` for a speaker, falling back to its MA counterpart."""
    state_obj = hass.states.get(speaker) if speaker else None
    attrs = state_obj.attributes if state_obj is not None else {}
    title = str(attrs.get("media_title") or "")
    artist = str(attrs.get("media_artist") or attrs.get("media_album_artist") or "")
    album = str(attrs.get("media_album_name") or "")

    if speaker and (not title or not artist or not album):
        ma_target = resolve_ma_counterpart_entity(hass, speaker)
        ma_st = (
            hass.states.get(ma_target)
            if ma_target and ma_target != speaker
            else None
        )
        if ma_st is not None:
            m_attrs = ma_st.attributes
            title = title or str(m_attrs.get("media_title") or "")
            artist = artist or str(
                m_attrs.get("media_artist") or m_attrs.get("media_album_artist") or ""
            )
            album = album or str(m_attrs.get("media_album_name") or "")
    return title, artist, album


def _unwrap_logical_lines(raw_text: str) -> list[str]:
    out: list[str] = []
    for raw_line in raw_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or _LRC_META_TAG_RE.match(stripped):
            continue
        cleaned = " ".join(_LRC_WORD_TAG_RE.sub("", _LRC_TAG_RE.sub("", stripped)).split())
        if cleaned:
            out.append(cleaned)
    return out


def _lrc_match_to_ms(match: re.Match[str]) -> int:
    mins = int(match.group(1))
    secs = int(match.group(2))
    frac = match.group(3)
    if frac is None:
        ms = 0
    elif len(frac) == 1:
        ms = int(frac) * 100
    elif len(frac) == _FRAC_TWO_DIGITS:
        ms = int(frac) * 10
    else:
        ms = int(frac[:3])
    return max(0, (mins * 60 + secs) * 1000 + ms)


def parse_lrc_lyrics(
    raw_lyrics: str, max_lines: int = MAX_LYRIC_LINES
) -> tuple[bool, list[dict[str, Any]]]:
    """Parse LRC timestamped lyrics (`[mm:ss.xx]` / `[mm:ss.xxx]` / `[mm:ss]`) or plain lines."""
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
        lyric_body = " ".join(_LRC_WORD_TAG_RE.sub("", _LRC_TAG_RE.sub("", stripped)).split())
        if not lyric_body or _LRC_EMPTY_MARKER_RE.match(lyric_body):
            continue
        for match in matches:
            synced_entries.append((_lrc_match_to_ms(match), order_seq, lyric_body))
            order_seq += 1

    if synced_entries:
        synced_entries.sort(key=lambda row: (row[0], row[1]))
        return True, [{"t_ms": t_ms, "text": txt} for t_ms, _seq, txt in synced_entries[:cap]]

    plain_lines = _unwrap_logical_lines(text)
    if not plain_lines:
        return False, []
    return False, [{"t_ms": -1, "text": ln} for ln in plain_lines[:cap]]


def _extract_meta_strings(obj: Any) -> tuple[str, str]:
    d = extract_item_dict(obj)
    raw_meta = d.get("metadata")
    meta: Any = raw_meta if raw_meta is not None else d
    if hasattr(meta, "to_dict") and callable(meta.to_dict):
        meta = meta.to_dict()
    if not isinstance(meta, dict):
        meta = extract_item_dict(meta)
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
    d = extract_item_dict(obj)
    for cand in (d.get("year"), extract_item_dict(d.get("album") or {}).get("year")):
        if cand is None or isinstance(cand, bool):
            continue
        yr = safe_int(cand, 0)
        if _MIN_RELEASE_YEAR <= yr <= _MAX_RELEASE_YEAR:
            return yr
    return None


def _strip_title_tags(title: str) -> str:
    clean = re.sub(
        r"\s*[\(\[][^\)\]]*(?:remaster|edition|version|mix|live|deluxe|mono|stereo)[^\)\]]*[\)\]]",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    return (
        re.sub(
            r"\s*-\s*.*(?:remaster|edition|version|mix|live|deluxe).*$",
            "",
            clean,
            flags=re.IGNORECASE,
        ).strip()
        or title.strip()
    )


def _normalize_search_metadata(
    hass: HomeAssistant,
    speaker: str,
    search: str,
    fallbacks: tuple[str, str, str],
) -> tuple[str, str, str, str, str, str]:
    fallback_title, fallback_artist, fallback_album = fallbacks
    parts = [unescape_v3_subfield(p.strip()) for p in search.split("|")]
    title = parts[0] if len(parts) >= 1 and parts[0] else ""
    artist = parts[1] if len(parts) >= _SEARCH_ARTIST_IDX and parts[1] else ""
    album = parts[2] if len(parts) >= _SEARCH_ALBUM_IDX and parts[2] else ""

    if not title or not artist or not album:
        cur_title, cur_artist, cur_album = resolve_speaker_playing_metadata(hass, speaker)
        title = title or cur_title or fallback_title
        artist = artist or cur_artist or fallback_artist
        album = album or cur_album or fallback_album

    clean_title = _strip_title_tags(title)
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


def _parse_ma_lyrics_response(res: Any) -> str:
    if isinstance(res, (tuple, list)):
        plain_str = str(res[0] or "").strip() if len(res) >= 1 else ""
        lrc_str = str(res[1] or "").strip() if len(res) >= _FRAC_TWO_DIGITS else ""
        return lrc_str or plain_str
    return res.strip() if isinstance(res, str) else ""


def _is_full_ma_item(item: dict[str, Any] | None) -> bool:
    return bool(item and item.get("item_id") and item.get("provider"))


def _titles_conflict(requested_clean: str, candidate_name: str) -> bool:
    req_norm = " ".join(
        re.sub(r"[^\w\s]", "", _strip_title_tags(requested_clean).lower()).split()
    )
    cand_norm = " ".join(
        re.sub(r"[^\w\s]", "", _strip_title_tags(candidate_name).lower()).split()
    )
    return bool(
        req_norm
        and cand_norm
        and req_norm not in cand_norm
        and cand_norm not in req_norm
    )


async def _hydrate_ma_item_by_uri(mass: Any, uri: str) -> dict[str, Any] | None:
    if mass is None or "://" not in uri:
        return None
    get_by_uri = getattr(getattr(mass, "music", None), "get_item_by_uri", None)
    send_cmd = getattr(mass, "send_command", None)
    try:
        if callable(get_by_uri):
            raw = await get_by_uri(uri)
        elif callable(send_cmd):
            raw = await send_cmd("music/item_by_uri", uri=uri)
        else:
            return None
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("MA item hydration failed for %s: %s", uri, err)
        return None
    d = extract_item_dict(raw)
    return d or None


def _extract_provider_track_ref(item: dict[str, Any]) -> tuple[str, str] | None:
    raw_mappings = item.get("provider_mappings")
    if not isinstance(raw_mappings, Iterable) or isinstance(
        raw_mappings, (str, bytes, dict)
    ):
        return None
    candidates: list[tuple[int, str, str]] = []
    for mapping in raw_mappings:
        md = extract_item_dict(mapping)
        if md.get("available") is False:
            continue
        prov_inst = str(
            md.get("provider_instance") or md.get("provider_domain") or ""
        ).strip()
        item_id = str(md.get("item_id") or "").strip()
        if not prov_inst or prov_inst == "library" or not item_id:
            continue
        candidates.append((safe_int(md.get("priority"), 0), prov_inst, item_id))
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0], reverse=True)
    return candidates[0][1], candidates[0][2]


async def _fetch_provider_track_dict(
    mass: Any, provider_instance: str, item_id: str
) -> dict[str, Any] | None:
    if mass is None or not provider_instance or not item_id:
        return None
    get_track = getattr(getattr(mass, "music", None), "get_track", None)
    send_cmd = getattr(mass, "send_command", None)
    try:
        if callable(get_track):
            raw = await get_track(item_id, provider_instance)
        elif callable(send_cmd):
            raw = await send_cmd(
                "music/tracks/get",
                item_id=item_id,
                provider_instance_id_or_domain=provider_instance,
            )
        else:
            return None
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "MA provider track fetch failed (%s/%s): %s",
            provider_instance,
            item_id,
            err,
        )
        return None
    d = extract_item_dict(raw)
    return d or None


async def _call_ma_get_track_lyrics(mass: Any, track_item: dict[str, Any]) -> str:
    get_lyr = getattr(getattr(mass, "metadata", None), "get_track_lyrics", None)
    if callable(get_lyr):
        try:
            return _parse_ma_lyrics_response(await get_lyr(track_item))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("mass.metadata.get_track_lyrics skipped: %s", err)

    send_cmd = getattr(mass, "send_command", None)
    if callable(send_cmd):
        try:
            return _parse_ma_lyrics_response(
                await send_cmd("metadata/get_track_lyrics", track=track_item)
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("mass.send_command('metadata/get_track_lyrics') skipped: %s", err)
    return ""


async def _hydrate_if_slim(
    mass: Any, item: dict[str, Any]
) -> dict[str, Any]:
    if _is_full_ma_item(item):
        return item
    uri = str(item.get("uri") or "").strip()
    if not uri or (hydrated := await _hydrate_ma_item_by_uri(mass, uri)) is None:
        return item
    if item.get("metadata") and not hydrated.get("metadata"):
        hydrated["metadata"] = item["metadata"]
    if item.get("year") and not hydrated.get("year"):
        hydrated["year"] = item["year"]
    return hydrated


async def _read_current_queue_media_item(
    hass: HomeAssistant, speaker: str
) -> dict[str, Any] | None:
    ma_target = resolve_ma_counterpart_entity(hass, speaker)
    if not ma_target:
        return None

    mass = get_ma_mass_client(hass)
    mem_dict: dict[str, Any] | None = None
    pqs = getattr(mass, "player_queues", None) if mass is not None else None
    if pqs is not None and hasattr(pqs, "get"):
        qid = resolve_ma_queue_id_sync(hass, ma_target, mass) or ma_target
        try:
            q_obj = pqs.get(qid)
            cur_obj = getattr(q_obj, "current_item", None) if q_obj is not None else None
            m_obj = getattr(cur_obj, "media_item", None) if cur_obj is not None else None
            if m_obj is not None:
                mem_dict = extract_item_dict(m_obj)
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as err:
            _LOGGER.debug("Reading in-memory queue media_item for %s skipped: %s", qid, err)

    if _is_full_ma_item(mem_dict):
        return mem_dict

    if hass.services.has_service("music_assistant", "get_queue"):
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_target},
                blocking=True,
                return_response=True,
            )
            q_data = (resp.get(ma_target) or resp) if isinstance(resp, dict) else None
            if isinstance(q_data, dict) and (cur_item := q_data.get("current_item")) is not None:
                m_item = extract_item_dict(cur_item).get("media_item")
                if m_item is not None:
                    return await _hydrate_if_slim(mass, extract_item_dict(m_item))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue metadata lookup failed: %s", err)

    if mem_dict is not None:
        return await _hydrate_if_slim(mass, mem_dict)
    return None


def _pick_better_lyrics(current: str, candidate: str) -> str:
    if not candidate:
        return current
    if not current or _LRC_TAG_RE.search(candidate):
        return candidate
    return current


async def _fetch_local_ma_controller_lyrics(
    hass: HomeAssistant, media_item: dict[str, Any] | None
) -> str:
    if not media_item or (mass := get_ma_mass_client(hass)) is None:
        return ""

    track_item = dict(media_item)
    best = ""
    if (
        not _is_full_ma_item(track_item)
        and (uri := str(track_item.get("uri") or "").strip())
        and (hydrated := await _hydrate_ma_item_by_uri(mass, uri)) is not None
    ):
        track_item = hydrated
        hyd_lyr, _ = _extract_meta_strings(track_item)
        if hyd_lyr and _LRC_TAG_RE.search(hyd_lyr):
            return hyd_lyr
        best = hyd_lyr

    best = _pick_better_lyrics(best, await _call_ma_get_track_lyrics(mass, track_item))
    if (
        (not best or not _LRC_TAG_RE.search(best))
        and str(track_item.get("provider") or "") == "library"
        and (prov_ref := _extract_provider_track_ref(track_item)) is not None
        and (
            prov_track := await _fetch_provider_track_dict(
                mass, prov_ref[0], prov_ref[1]
            )
        )
        is not None
    ):
        prov_meta_lyr, _ = _extract_meta_strings(prov_track)
        best = _pick_better_lyrics(best, prov_meta_lyr)
        if not best or not _LRC_TAG_RE.search(best):
            best = _pick_better_lyrics(
                best, await _call_ma_get_track_lyrics(mass, prov_track)
            )
    return best


async def _fetch_ma_library_items(
    hass: HomeAssistant,
    config_entry_id: str | None,
    media_type: str,
    search: str,
    limit: int,
) -> list[dict[str, Any]]:
    mass = get_ma_mass_client(hass)
    music = getattr(mass, "music", None) if mass is not None else None
    method_name = {
        "track": "get_library_tracks",
        "artist": "get_library_artists",
        "album": "get_library_albums",
    }.get(media_type, "")
    if method_name and callable(fn := getattr(music, method_name, None)):
        try:
            res = await fn(search=search, limit=limit)
            if (
                isinstance(res, Sequence)
                and not isinstance(res, (str, bytes))
                and res
            ):
                return [extract_item_dict(x) for x in res]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("mass.music.%s(%r) failed: %s", method_name, search, err)
    if not config_entry_id:
        return []
    return await call_ma_get_library(
        hass, config_entry_id, media_type, search=search, limit=limit
    )


def _artist_match_rank(trk: dict[str, Any], artist_lower: str) -> int:
    trk_artist = extract_artist_name(trk).strip().lower()
    if not trk_artist:
        return 1
    if artist_lower in trk_artist or trk_artist in artist_lower:
        return 0
    return 2


async def _search_library_track_lyrics(
    hass: HomeAssistant,
    config_entry_id: str | None,
    clean_title: str,
    seed_lyrics: str,
    *,
    artist: str = "",
) -> tuple[str, dict[str, Any] | None]:
    if not config_entry_id or (seed_lyrics and "[" in seed_lyrics) or not clean_title:
        return seed_lyrics, None
    tracks = await _fetch_ma_library_items(
        hass, config_entry_id, "track", clean_title, 10
    )
    if artist_lower := artist.strip().lower():
        tracks.sort(key=lambda trk: _artist_match_rank(trk, artist_lower))
    raw_lyrics = seed_lyrics
    fallback_plain = seed_lyrics
    matched_track: dict[str, Any] | None = None
    for trk in tracks:
        if matched_track is None:
            matched_track = trk
        lyr, _ = _extract_meta_strings(trk)
        if not lyr:
            continue
        if "[" in lyr and _LRC_TAG_RE.search(lyr):
            return lyr, matched_track
        if not fallback_plain:
            fallback_plain = lyr
    return (raw_lyrics or fallback_plain), matched_track


def build_lyrics_track_key(title: str, artist: str) -> str:
    """Build an escaped `title|artist` track key matching firmware `build_music_track_key()`."""
    clean_title = str(title or "").strip()
    if not clean_title:
        return ""
    clean_artist = str(artist or "").strip()
    return f"{escape_v3_subfield(clean_title)}|{escape_v3_subfield(clean_artist)}"


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
    """Fetch full-track LRC or plain lyrics strictly from local Music Assistant."""
    title, artist, album, clean_title, _clean_album, cache_key = _normalize_search_metadata(
        hass, speaker, search, (fallback_title, fallback_artist, fallback_album)
    )
    track_key = build_lyrics_track_key(title, artist)
    if not clean_title:
        return track_key, False, []

    cap = max(1, int(max_lines))
    now_m = time.monotonic()
    if (cached := cache_get(cache_key)) is not None:
        if isinstance(payload := cached.get("lyrics_payload"), dict):
            return track_key, bool(payload.get("synced")), list(payload.get("lines") or [])[:cap]
        if now_m < float(cached.get("lyrics_miss_until") or 0.0):
            return track_key, False, []

    raw_lyrics = ""
    raw_album_bio = ""
    release_year: int | None = None
    if (m_item := await _read_current_queue_media_item(hass, speaker)) is not None:
        cand_name = str(m_item.get("name") or m_item.get("title") or "")
        if _titles_conflict(clean_title, cand_name):
            m_item = None
        else:
            raw_lyrics, raw_album_bio = _extract_meta_strings(m_item)
            release_year = _extract_release_year(m_item)

    raw_lyrics, matched_track = await _search_library_track_lyrics(
        hass, get_ma_config_entry_id(hass), clean_title, raw_lyrics, artist=artist
    )
    if m_item is None and matched_track is not None:
        _, meta_bio = _extract_meta_strings(matched_track)
        raw_album_bio = raw_album_bio or meta_bio
        if release_year is None:
            release_year = _extract_release_year(matched_track)

    if not raw_lyrics or not _LRC_TAG_RE.search(raw_lyrics):
        raw_lyrics = _pick_better_lyrics(
            raw_lyrics,
            await _fetch_local_ma_controller_lyrics(hass, m_item or matched_track),
        )
        if (
            (not raw_lyrics or not _LRC_TAG_RE.search(raw_lyrics))
            and m_item is not None
            and matched_track is not None
            and (
                matched_track.get("uri") != m_item.get("uri")
                or not _is_full_ma_item(m_item)
            )
        ):
            raw_lyrics = _pick_better_lyrics(
                raw_lyrics,
                await _fetch_local_ma_controller_lyrics(hass, matched_track),
            )

    synced, parsed_lines = parse_lrc_lyrics(raw_lyrics, max_lines=MAX_LYRIC_LINES)
    cache_entry = cache_put(cache_key)
    if parsed_lines:
        cache_entry.pop("lyrics_miss_until", None)
        cache_entry["lyrics_payload"] = {"synced": synced, "lines": parsed_lines}
        if raw_album_bio and "bio" not in cache_entry:
            bio_seed = [
                *( [f"Artist: {artist}"] if artist else [] ),
                *( [f"Album: {album}"] if album else [] ),
                *( [f"Release: {release_year}"] if release_year else [] ),
                *_unwrap_logical_lines(f"Album: {raw_album_bio}"),
            ]
            cache_entry["bio"] = bio_seed
    else:
        cache_entry["lyrics_miss_until"] = time.monotonic() + NEGATIVE_CACHE_TTL_SECONDS

    return track_key, synced, parsed_lines[:cap]


async def _fetch_library_artist_album_bio(
    hass: HomeAssistant,
    config_entry_id: str | None,
    artist: str,
    clean_album: str,
    seed: tuple[str, int | None],
) -> tuple[str, str, int | None]:
    raw_album_bio, release_year = seed
    raw_artist_bio = ""
    if not config_entry_id:
        return raw_artist_bio, raw_album_bio, release_year

    mass = get_ma_mass_client(hass)
    if artist:
        ar_items = await _fetch_ma_library_items(
            hass, config_entry_id, "artist", artist, 5
        )
        for ar_obj in ar_items:
            _, desc = _extract_meta_strings(ar_obj)
            if desc:
                raw_artist_bio = desc
                break
        if (
            not raw_artist_bio
            and ar_items
            and (uri := str(ar_items[0].get("uri") or "").strip())
            and (hyd_ar := await _hydrate_ma_item_by_uri(mass, uri)) is not None
        ):
            _, raw_artist_bio = _extract_meta_strings(hyd_ar)

    if (not raw_album_bio or release_year is None) and clean_album:
        al_items = await _fetch_ma_library_items(
            hass, config_entry_id, "album", clean_album, 5
        )
        for al_obj in al_items:
            if release_year is None:
                release_year = _extract_release_year(al_obj)
            _, desc = _extract_meta_strings(al_obj)
            if desc and not raw_album_bio:
                raw_album_bio = desc
            if raw_album_bio and release_year is not None:
                break
        if (
            (not raw_album_bio or release_year is None)
            and al_items
            and (uri := str(al_items[0].get("uri") or "").strip())
            and (hyd_al := await _hydrate_ma_item_by_uri(mass, uri)) is not None
        ):
            if release_year is None:
                release_year = _extract_release_year(hyd_al)
            _, desc = _extract_meta_strings(hyd_al)
            if desc and not raw_album_bio:
                raw_album_bio = desc
    return raw_artist_bio, raw_album_bio, release_year


def _text_rows(lines: Sequence[str]) -> list[dict[str, Any]]:
    return [{"name": ln, "id": "", "type": "text", "active": False} for ln in lines]


def _format_and_cache_bio_lines(
    cache_key: str,
    meta_names: tuple[str, str, str, str],
    bio_data: tuple[str, str, int | None, str],
) -> list[str]:
    artist, album, clean_title, clean_album = meta_names
    raw_artist_bio, raw_album_bio, release_year, raw_lyrics = bio_data
    bio_lines = [
        *(
            [f"Artist: {artist}"] if artist else []
        ),
        *(
            [f"Album: {album or clean_album}"] if (album or clean_album) else []
        ),
        *(
            [f"Release: {release_year}"] if release_year is not None else []
        ),
    ]
    rich_paragraphs = [
        *(_unwrap_logical_lines(raw_album_bio) if raw_album_bio else []),
        *(
            _unwrap_logical_lines(raw_artist_bio)
            if raw_artist_bio and raw_artist_bio != raw_album_bio
            else []
        ),
    ]
    bio_lines.extend(rich_paragraphs)
    if not bio_lines:
        bio_lines = [
            f"{clean_title or 'Unknown Track'} by {artist or 'Unknown Artist'}"
            + (f" — {clean_album}" if clean_album else "")
        ]

    cache_entry = cache_put(cache_key)
    if rich_paragraphs:
        cache_entry.pop("bio_miss_until", None)
        cache_entry.pop("bio_fallback", None)
        cache_entry["bio"] = bio_lines
    else:
        cache_entry["bio_fallback"] = bio_lines
        cache_entry["bio_miss_until"] = time.monotonic() + NEGATIVE_CACHE_TTL_SECONDS
    if raw_lyrics and "lyrics_payload" not in cache_entry:
        synced, parsed_lines = parse_lrc_lyrics(raw_lyrics, max_lines=MAX_LYRIC_LINES)
        if parsed_lines:
            cache_entry.pop("lyrics_miss_until", None)
            cache_entry["lyrics_payload"] = {"synced": synced, "lines": parsed_lines}
    return bio_lines


async def browse_track_lyrics_or_bio(
    hass: HomeAssistant,
    config_entry_id: str | None,
    speaker: str,
    mode: str,
    search: str,
    fallback_title: str,
    fallback_artist: str = "",
    fallback_album: str = "",
) -> list[dict[str, Any]]:
    """Fetch unwrapped lyrics or artist/album metadata strictly from local Music Assistant."""
    if mode == "lyrics":
        _tkey, _synced, parsed_lines = await async_fetch_track_lyrics(
            hass,
            speaker,
            search,
            fallback_title=fallback_title,
            fallback_artist=fallback_artist,
            fallback_album=fallback_album,
        )
        return (
            _text_rows([str(row["text"]) for row in parsed_lines])
            if parsed_lines
            else _text_rows(("No lyrics found for this track.",))
        )

    _title, artist, album, clean_title, clean_album, cache_key = _normalize_search_metadata(
        hass, speaker, search, (fallback_title, fallback_artist, fallback_album)
    )
    now_m = time.monotonic()
    if (cached := cache_get(cache_key)) is not None:
        if cached.get("bio"):
            return _text_rows(cached["bio"])
        if now_m < float(cached.get("bio_miss_until") or 0.0) and isinstance(
            cached.get("bio_fallback"), list
        ):
            return _text_rows(cached["bio_fallback"])

    raw_lyrics = ""
    raw_album_bio = ""
    release_year: int | None = None
    if (m_item := await _read_current_queue_media_item(hass, speaker)) is not None:
        raw_lyrics, raw_album_bio = _extract_meta_strings(m_item)
        release_year = _extract_release_year(m_item)

    raw_artist_bio, raw_album_bio, release_year = await _fetch_library_artist_album_bio(
        hass, config_entry_id, artist, clean_album, (raw_album_bio, release_year)
    )
    bio_lines = _format_and_cache_bio_lines(
        cache_key,
        (artist, album, clean_title, clean_album),
        (raw_artist_bio, raw_album_bio, release_year, raw_lyrics),
    )
    return _text_rows(bio_lines)


async def async_push_music_lyrics(
    hass: HomeAssistant,
    coordinator: Any,
    *,
    req_id: int = 0,
    track_key: str = "",
    synced: bool = False,
    lines: Sequence[dict[str, Any]] = (),
) -> bool:
    """Push chunked LRC or plain lyrics to the Device's bound `latter_set_music_lyrics` action."""
    esphome_action = esphome_service(
        hass, coordinator.esphome_device_id, "latter_set_music_lyrics"
    )
    if esphome_action is None:
        return False

    clean_key = utf8_safe_truncate(
        _UNSAFE_CTRL_RE.sub(" ", str(track_key or "")).strip(), _MAX_TRACK_KEY_BYTES
    )
    encoded_rows: list[str] = []
    for row in list(lines)[:MAX_LYRIC_LINES]:
        t_ms = safe_int(row.get("t_ms", -1), -1)
        txt = utf8_safe_truncate(
            _UNSAFE_CTRL_RE.sub(" ", str(row.get("text") or "")).strip(),
            _MAX_LYRIC_LINE_BYTES,
        )
        if txt:
            encoded_rows.append(f"{t_ms}\x1f{txt}")

    chunk_count = max(1, math.ceil(len(encoded_rows) / LYRICS_CHUNK_SIZE))
    safe_req_id = max(0, safe_int(req_id, 0))
    try:
        for chunk_idx in range(chunk_count):
            chunk_slice = encoded_rows[
                chunk_idx * LYRICS_CHUNK_SIZE : (chunk_idx + 1) * LYRICS_CHUNK_SIZE
            ]
            await hass.services.async_call(
                "esphome",
                esphome_action,
                {
                    "req_id": safe_req_id,
                    "chunk_index": int(chunk_idx),
                    "chunk_count": int(chunk_count),
                    "track_key": clean_key,
                    "synced": bool(synced and encoded_rows),
                    "lines": "\x1e".join(chunk_slice),
                },
                blocking=True,
            )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "esphome.%s failed for '%s': %s", esphome_action, coordinator.device_slug, err
        )
        return False
    return True


async def async_fetch_and_push_music_lyrics(
    hass: HomeAssistant,
    coordinator: Any,
    *,
    req_id: int = 0,
    speaker: str | None = None,
    search: str = "",
    max_lines: int = MAX_LYRIC_LINES,
) -> tuple[str, bool, list[dict[str, Any]]]:
    """Fetch lyrics (cached in 64-entry LRU) and push them to `latter_set_music_lyrics`."""
    eff_spk = str(
        speaker or coordinator.active_speaker or coordinator.local_speaker
    ).strip()
    track_key, synced, parsed_lines = await async_fetch_track_lyrics(
        hass,
        eff_spk,
        search,
        fallback_title=coordinator.last_media_title,
        fallback_artist=coordinator.last_media_artist,
        fallback_album=coordinator.last_media_album,
        max_lines=max_lines,
    )
    coordinator.lyrics_watch_active = True
    coordinator.last_pushed_lyrics_key = track_key
    await async_push_music_lyrics(
        hass,
        coordinator,
        req_id=req_id,
        track_key=track_key,
        synced=synced,
        lines=parsed_lines,
    )
    return track_key, synced, parsed_lines
