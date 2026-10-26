"""Music Assistant & Home Assistant Media Browse Engine for Latter."""

from __future__ import annotations

import logging
import re
import textwrap
from typing import Any
from urllib.parse import quote

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

_LOGGER = logging.getLogger(__name__)

LIBRARY_MEDIA_TYPES: set[str] = {
    "playlist",
    "artist",
    "album",
    "radio",
    "podcast",
    "audiobook",
    "track",
}


def is_music_assistant_player(hass: HomeAssistant, state_obj: State) -> bool:
    """Return True if the media_player entity is provided by Music Assistant."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(state_obj.entity_id)
    if entry is not None and entry.platform == "music_assistant":
        return True
    attrs = state_obj.attributes
    if "mass_player_id" in attrs or "mass_player_type" in attrs:
        return True
    return False


def _get_ma_config_entry_id(hass: HomeAssistant) -> str | None:
    """Auto-discover the loaded Music Assistant config_entry_id."""
    entries = hass.config_entries.async_entries("music_assistant")
    for entry in entries:
        if entry.state is ConfigEntryState.LOADED:
            return entry.entry_id
    if entries:
        return entries[0].entry_id
    return None


def _get_mass_client(hass: HomeAssistant) -> Any | None:
    """Retrieve the in-process MusicAssistantClient instance from HA."""
    entries = hass.config_entries.async_entries("music_assistant")
    for entry in entries:
        runtime_data = getattr(entry, "runtime_data", None)
        if runtime_data is not None:
            mass = getattr(runtime_data, "mass", runtime_data)
            if mass is not None:
                return mass

    ma_data = hass.data.get("music_assistant", {})
    if isinstance(ma_data, dict):
        for val in ma_data.values():
            mass = getattr(val, "mass", val)
            if hasattr(mass, "player_queues") or hasattr(mass, "music"):
                return mass
    return None


def _find_ma_media_player_entity(
    hass: HomeAssistant, preferred_speaker: str
) -> str | None:
    """Return a Music Assistant media_player entity_id capable of browsing MA URIs."""
    pref_state = hass.states.get(preferred_speaker)
    if (
        pref_state is not None
        and pref_state.state not in ("unavailable", "unknown")
        and is_music_assistant_player(hass, pref_state)
    ):
        return preferred_speaker

    for state_obj in hass.states.async_all("media_player"):
        if state_obj.state in ("unavailable", "unknown"):
            continue
        if is_music_assistant_player(hass, state_obj):
            return state_obj.entity_id

    return preferred_speaker


def _extract_item_dict(raw: Any) -> dict[str, Any]:
    """Convert a Music Assistant model, BrowseMedia dict, or object into a normalized dict."""
    if isinstance(raw, dict):
        return raw
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
        "year",
        "position",
        "track_number",
        "disc_number",
        "artists",
        "artist_str",
        "album",
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


def _parse_uri(uri: str) -> tuple[str, str]:
    """Extract (provider, item_id) from a URI like library://album/123 or provider://type/id."""
    if "://" in uri:
        provider, rest = uri.split("://", 1)
        if "/" in rest:
            _media_type, item_id = rest.split("/", 1)
            return provider, item_id
    return "library", uri


async def _browse_ma_media_children(
    hass: HomeAssistant,
    speaker: str,
    media_content_type: str,
    media_content_id: str,
) -> list[dict[str, Any]]:
    """Use Home Assistant's media_player.browse_media on a Music Assistant player to get child items."""
    if not hass.services.has_service("media_player", "browse_media"):
        return []

    ma_entity = _find_ma_media_player_entity(hass, speaker)
    if not ma_entity:
        return []

    try:
        resp = await hass.services.async_call(
            "media_player",
            "browse_media",
            {
                "entity_id": ma_entity,
                "media_content_type": media_content_type,
                "media_content_id": media_content_id,
            },
            blocking=True,
            return_response=True,
        )
        if isinstance(resp, dict):
            node = resp.get(ma_entity) or resp
            if isinstance(node, dict):
                children = node.get("children") or []
                return [_extract_item_dict(c) for c in children]
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "media_player.browse_media(%s, %s) on %s failed: %s",
            media_content_type,
            media_content_id,
            ma_entity,
            err,
        )
    return []


async def _call_ma_get_library(
    hass: HomeAssistant,
    config_entry_id: str,
    media_type: str,
    favorite: bool | None = None,
    search: str | None = None,
    limit: int = 500,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    """Call music_assistant.get_library with automatic schema fallback and in-process MASS controller fallback."""
    if hass.services.has_service("music_assistant", "get_library"):
        base_payload: dict[str, Any] = {
            "config_entry_id": config_entry_id,
            "media_type": media_type,
            "limit": limit,
        }
        if favorite is not None:
            base_payload["favorite"] = favorite
        if search:
            base_payload["search"] = search

        attempts: list[dict[str, Any]] = []
        if order_by:
            attempts.append({**base_payload, "order_by": order_by})
        attempts.append(base_payload)

        for payload in attempts:
            try:
                resp = await hass.services.async_call(
                    "music_assistant",
                    "get_library",
                    payload,
                    blocking=True,
                    return_response=True,
                )
                if isinstance(resp, dict):
                    raw_items = resp.get("items")
                    if raw_items is None and len(resp) == 1:
                        first_val = next(iter(resp.values()))
                        if isinstance(first_val, dict):
                            raw_items = first_val.get("items")
                    if isinstance(raw_items, list):
                        return [_extract_item_dict(x) for x in raw_items]
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "music_assistant.get_library(%s, order_by=%s) attempt failed: %s",
                    media_type,
                    payload.get("order_by"),
                    err,
                )

    # Fallback: Query in-process MusicAssistantClient controller directly
    mass = _get_mass_client(hass)
    if mass is not None and hasattr(mass, "music"):
        ctrl_map = {
            "playlist": "playlists",
            "artist": "artists",
            "album": "albums",
            "track": "tracks",
            "radio": "radio",
            "podcast": "podcasts",
            "audiobook": "audiobooks",
        }
        ctrl_name = ctrl_map.get(media_type)
        ctrl = getattr(mass.music, ctrl_name, None) if ctrl_name else None
        if ctrl is not None and hasattr(ctrl, "library_items"):
            try:
                kwargs: dict[str, Any] = {"limit": limit}
                if favorite is not None:
                    kwargs["favorite"] = favorite
                if search:
                    kwargs["search"] = search
                res = await ctrl.library_items(**kwargs)
                raw_list = getattr(res, "items", res) if res is not None else []
                if isinstance(raw_list, list):
                    return [_extract_item_dict(x) for x in raw_list]
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "In-process MASS library_items(%s) fallback failed: %s",
                    media_type,
                    err,
                )

    return []


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
            if dev_name and dev_name.lower() not in friendly.lower():
                return f"{dev_name} ({friendly})"
    return friendly


async def _browse_speakers(
    hass: HomeAssistant,
    active_speaker: str,
    last_speaker: str,
    local_speaker: str,
) -> list[dict[str, Any]]:
    """Build sorted speaker list restricted strictly to Music Assistant players (+ local speaker)."""
    items: list[dict[str, Any]] = []
    for state_obj in hass.states.async_all("media_player"):
        if state_obj.state in ("unavailable", "unknown"):
            continue
        ent_id = state_obj.entity_id
        is_local = ent_id == local_speaker

        if not is_local and not is_music_assistant_player(hass, state_obj):
            continue

        friendly = (
            _format_local_speaker_name(hass, state_obj)
            if is_local
            else str(state_obj.attributes.get("friendly_name") or ent_id)
        )

        items.append(
            {
                "name": friendly,
                "id": ent_id,
                "type": "speaker",
                "active": ent_id == active_speaker,
                "_is_local": is_local,
                "_is_last": ent_id == last_speaker,
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
    return items


async def _browse_favorites(
    hass: HomeAssistant, config_entry_id: str
) -> list[dict[str, Any]]:
    """Aggregate favorite playlists, artists, albums, radio, podcasts, audiobooks, tracks."""
    results: list[dict[str, Any]] = []
    for mtype in (
        "playlist",
        "artist",
        "album",
        "radio",
        "podcast",
        "audiobook",
        "track",
    ):
        raw_items = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type=mtype,
            favorite=True,
            limit=100,
        )
        for item in raw_items:
            uri = str(item.get("uri") or item.get("media_content_id") or "")
            name = str(item.get("name") or item.get("title") or "")
            if not uri or not name:
                continue
            results.append(
                {
                    "name": name,
                    "id": uri,
                    "type": str(item.get("media_type") or mtype),
                    "active": False,
                }
            )
    return results


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
                key=lambda x: (int(x.get("year") or 0), str(x.get("name") or "").lower()),
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
    speaker: str,
    artist_search: str,
    artist_album_sort: str,
) -> list[dict[str, Any]]:
    """Fetch albums belonging to a specific artist (by URI or artist name)."""
    artist_query = artist_search.strip()
    if not artist_query:
        return []

    filtered: list[dict[str, Any]] = []

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
        for art in artists:
            if str(art.get("name") or "").strip().lower() == q_low:
                artist_uri = str(art.get("uri") or "")
                break
        if not artist_uri and artists:
            artist_uri = str(artists[0].get("uri") or "")

    mass = _get_mass_client(hass)
    if mass is not None and artist_uri and hasattr(mass, "music"):
        provider, item_id = _parse_uri(artist_uri)
        try:
            if hasattr(mass.music, "get_artist_albums"):
                raw_albums = await mass.music.get_artist_albums(item_id, provider)
                filtered = [_extract_item_dict(a) for a in (raw_albums or [])]
            elif hasattr(mass.music, "artists") and hasattr(mass.music.artists, "albums"):
                raw_albums = await mass.music.artists.albums(item_id, provider)
                filtered = [_extract_item_dict(a) for a in (raw_albums or [])]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct MA get_artist_albums failed: %s", err)

    if not filtered and artist_uri:
        children = await _browse_ma_media_children(
            hass, speaker, "artist", artist_uri
        )
        for child in children:
            ctype = str(child.get("media_content_type") or child.get("media_type") or "").lower()
            cid = str(child.get("media_content_id") or child.get("uri") or "")
            if "album" in ctype or "://album/" in cid:
                filtered.append(child)

    if not filtered:
        raw_items = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="album",
            search=artist_query,
            limit=250,
        )
        query_lower = artist_query.lower()
        for item in raw_items:
            artist_name = _extract_artist_name(item).lower()
            if query_lower in artist_name or not artist_name:
                filtered.append(item)
        if not filtered:
            filtered = raw_items

    if artist_album_sort == "year_desc":
        filtered.sort(
            key=lambda x: (
                int(x.get("year") or 0),
                str(x.get("name") or x.get("title") or "").lower(),
            ),
            reverse=True,
        )
    elif artist_album_sort == "name":
        filtered.sort(
            key=lambda x: str(x.get("name") or x.get("title") or "").lower()
        )
    else:
        filtered.sort(
            key=lambda x: (
                int(x.get("year") or 9999),
                str(x.get("name") or x.get("title") or "").lower(),
            )
        )

    results: list[dict[str, Any]] = []
    for item in filtered:
        uri = str(item.get("uri") or item.get("media_content_id") or "")
        name = str(item.get("name") or item.get("title") or "")
        if not uri or not name:
            continue
        year = item.get("year")
        display_name = f"{name} ({year})" if year else name
        results.append(
            {
                "name": display_name,
                "id": uri,
                "type": "album",
                "active": False,
            }
        )
    return results


async def _browse_album_tracks(
    hass: HomeAssistant,
    config_entry_id: str,
    speaker: str,
    album_ref: str,
    current_track_title: str,
) -> list[dict[str, Any]]:
    """Browse tracks of an album by URI or album title across the entire library."""
    album_ref = album_ref.strip()
    if not album_ref:
        return []

    tracks: list[dict[str, Any]] = []

    album_uri = album_ref if "://" in album_ref else ""
    if not album_uri:
        matched_albums = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="album",
            search=album_ref,
            limit=50,
        )
        ref_lower = album_ref.lower()
        for alb in matched_albums:
            if str(alb.get("name") or "").strip().lower() == ref_lower:
                album_uri = str(alb.get("uri") or "")
                break
        if not album_uri and matched_albums:
            album_uri = str(matched_albums[0].get("uri") or "")

    mass = _get_mass_client(hass)
    if mass is not None and album_uri and hasattr(mass, "music"):
        provider, item_id = _parse_uri(album_uri)
        try:
            if hasattr(mass.music, "get_album_tracks"):
                raw_tracks = await mass.music.get_album_tracks(item_id, provider)
                tracks = [_extract_item_dict(t) for t in (raw_tracks or [])]
            elif hasattr(mass.music, "albums") and hasattr(mass.music.albums, "tracks"):
                raw_tracks = await mass.music.albums.tracks(item_id, provider)
                tracks = [_extract_item_dict(t) for t in (raw_tracks or [])]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct MA get_album_tracks(%s) failed: %s", album_uri, err)

    if not tracks and album_uri:
        children = await _browse_ma_media_children(
            hass, speaker, "album", album_uri
        )
        if children:
            tracks = children

    if not tracks and not ("library://" in album_ref):
        raw_tracks = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="track",
            search=album_ref,
            limit=200,
        )
        tracks = raw_tracks

    has_track_numbers = any(
        x.get("track_number") is not None or x.get("position") is not None
        for x in tracks
    )
    if has_track_numbers:
        tracks.sort(
            key=lambda x: (
                int(x.get("disc_number") or 1),
                int(x.get("track_number") or x.get("position") or 999),
                str(x.get("name") or x.get("title") or "").lower(),
            )
        )

    cur_lower = current_track_title.strip().lower()
    results: list[dict[str, Any]] = []
    for idx, trk in enumerate(tracks, start=1):
        uri = str(trk.get("uri") or trk.get("media_content_id") or "")
        name = str(trk.get("name") or trk.get("title") or "")
        if not uri or not name:
            continue
        t_num = trk.get("track_number") or idx
        if re.match(r"^\d+\.\s+", name):
            display_name = name
            clean_compare = re.sub(r"^\d+\.\s+", "", name).strip().lower()
        else:
            display_name = f"{t_num}. {name}"
            clean_compare = name.strip().lower()

        is_active = bool(
            cur_lower and (clean_compare == cur_lower or name.strip().lower() == cur_lower)
        )
        results.append(
            {
                "name": display_name,
                "id": uri,
                "type": "track",
                "active": is_active,
            }
        )
    return results


async def _browse_active_queue(
    hass: HomeAssistant,
    speaker: str,
    current_track_title: str,
) -> list[dict[str, Any]]:
    """Fetch upcoming queue items natively from Music Assistant 2.10.8+."""
    raw_queue_items: list[dict[str, Any]] = []

    mass = _get_mass_client(hass)
    state_obj = hass.states.get(speaker)
    if mass is not None and hasattr(mass, "player_queues"):
        try:
            queue_id = None
            if state_obj:
                queue_id = state_obj.attributes.get("mass_player_id")
            if not queue_id and hasattr(mass, "players"):
                all_players = (
                    mass.players.all()
                    if callable(getattr(mass.players, "all", None))
                    else getattr(mass.players, "players", [])
                )
                for player in all_players:
                    p_dict = _extract_item_dict(player)
                    p_name = str(p_dict.get("display_name") or p_dict.get("name") or "")
                    if state_obj and p_name.lower() == str(
                        state_obj.attributes.get("friendly_name", "")
                    ).lower():
                        queue_id = p_dict.get("player_id")
                        break
            if queue_id:
                if hasattr(mass.player_queues, "get_queue_items"):
                    q_items = await mass.player_queues.get_queue_items(queue_id, limit=100)
                elif hasattr(mass.player_queues, "items"):
                    q_items = await mass.player_queues.items(queue_id, limit=100)
                else:
                    q_items = []
                raw_queue_items = [_extract_item_dict(x) for x in (q_items or [])]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct mass.player_queues failed: %s", err)

    if not raw_queue_items and hass.services.has_service("music_assistant", "get_queue"):
        ma_target = _find_ma_media_player_entity(hass, speaker) or speaker
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
                    items_candidate = (
                        q_data.get("items")
                        or q_data.get("queue_items")
                        or q_data.get("next_item")
                    )
                    if isinstance(items_candidate, list):
                        raw_queue_items = [
                            _extract_item_dict(x) for x in items_candidate
                        ]
                    elif isinstance(items_candidate, dict):
                        raw_queue_items = [_extract_item_dict(items_candidate)]
                        if isinstance(q_data.get("current_item"), dict):
                            raw_queue_items.insert(
                                0, _extract_item_dict(q_data["current_item"])
                            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue failed: %s", err)

    cur_lower = current_track_title.strip().lower()
    results: list[dict[str, Any]] = []
    for item in raw_queue_items:
        media_item = _extract_item_dict(item.get("media_item") or {})
        name = str(
            item.get("media_title")
            or item.get("name")
            or media_item.get("name")
            or ""
        )
        uri = str(
            media_item.get("uri")
            or item.get("media_content_id")
            or item.get("uri")
            or item.get("queue_item_id")
            or ""
        )
        artist = (
            str(item.get("media_artist") or "")
            or _extract_artist_name(media_item)
        )
        if not name or not uri:
            continue

        display = f"{name} - {artist}" if artist else name
        is_active = bool(cur_lower and name.strip().lower() == cur_lower)
        results.append(
            {
                "name": display,
                "id": uri,
                "type": "track",
                "active": is_active,
            }
        )
    return results


async def _browse_podcast_episodes(
    hass: HomeAssistant,
    config_entry_id: str | None,
    speaker: str,
    podcast_ref: str,
    podcast_sort: str,
    current_track_title: str,
) -> list[dict[str, Any]]:
    """Fetch podcast episodes natively via MA client or media_player.browse_media."""
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

    raw_episodes: list[dict[str, Any]] = []

    mass = _get_mass_client(hass)
    if mass is not None and hasattr(mass, "music"):
        provider, item_id = _parse_uri(podcast_uri)
        try:
            if hasattr(mass.music, "get_podcast_episodes"):
                eps = await mass.music.get_podcast_episodes(item_id, provider)
                raw_episodes = [_extract_item_dict(e) for e in (eps or [])]
            elif hasattr(mass.music, "podcasts") and hasattr(mass.music.podcasts, "episodes"):
                eps = await mass.music.podcasts.episodes(item_id, provider)
                raw_episodes = [_extract_item_dict(e) for e in (eps or [])]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct MA get_podcast_episodes(%s) failed: %s", podcast_uri, err)

    if not raw_episodes:
        raw_episodes = await _browse_ma_media_children(
            hass, speaker, "podcast", podcast_uri
        )

    has_positions = any(
        x.get("position") is not None or x.get("track_number") is not None
        for x in raw_episodes
    )
    if has_positions:
        if podcast_sort == "oldest":
            raw_episodes.sort(
                key=lambda x: int(x.get("position") or x.get("track_number") or 0)
            )
        else:
            raw_episodes.sort(
                key=lambda x: int(x.get("position") or x.get("track_number") or 0),
                reverse=True,
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


async def async_browse_media_items(
    hass: HomeAssistant,
    mode: str,
    speaker: str,
    last_speaker: str,
    local_speaker: str,
    search: str = "",
    album_sort: str = "name",
    artist_album_sort: str = "year",
    podcast_sort: str = "newest",
) -> list[dict[str, Any]]:
    """Execute the requested browse mode and return a flat list of slot dicts."""
    mode = mode.strip().lower()

    if mode == "speakers":
        return await _browse_speakers(hass, speaker, last_speaker, local_speaker)

    state_obj = hass.states.get(speaker)
    current_title = (
        str(state_obj.attributes.get("media_title") or "") if state_obj else ""
    )
    current_album = (
        str(state_obj.attributes.get("media_album_name") or "") if state_obj else ""
    )

    if mode == "active_queue":
        return await _browse_active_queue(hass, speaker, current_title)

    config_entry_id = _get_ma_config_entry_id(hass)

    if mode == "podcast_episodes":
        return await _browse_podcast_episodes(
            hass, config_entry_id, speaker, search, podcast_sort, current_title
        )

    if not config_entry_id:
        _LOGGER.warning(
            "Music Assistant integration not found or not loaded in Home Assistant."
        )
        return []

    if mode == "favorites":
        return await _browse_favorites(hass, config_entry_id)

    if mode in LIBRARY_MEDIA_TYPES:
        return await _browse_library_category(
            hass, config_entry_id, mode, album_sort
        )

    if mode == "artist_albums":
        return await _browse_artist_albums(
            hass, config_entry_id, speaker, search, artist_album_sort
        )

    if mode == "album_tracks":
        return await _browse_album_tracks(
            hass, config_entry_id, speaker, search, current_title
        )

    if mode == "current_album_tracks":
        album_ref = search.strip() or current_album
        return await _browse_album_tracks(
            hass, config_entry_id, speaker, album_ref, current_title
        )

    if mode in ("lyrics", "bio"):
        return await _browse_track_lyrics_or_bio(
            hass, config_entry_id, speaker, mode, search, current_title
        )

    _LOGGER.warning("Unknown Latter music_browse mode: %s", mode)
    return []


_BROWSE_LYRICS_BIO_CACHE: dict[str, dict[str, list[str]]] = {}
_LRC_STRIP_RE = re.compile(r"\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]")


def _wrap_text_to_slot_lines(raw_text: str, width: int = 32) -> list[str]:
    """Word-wrap raw multi-line text into clean 32-char display lines for ESPHome browse slots."""
    out: list[str] = []
    for para in raw_text.splitlines():
        clean_p = _LRC_STRIP_RE.sub("", para).strip()
        if not clean_p:
            continue
        wrapped = textwrap.wrap(
            clean_p, width=width, break_long_words=True, replace_whitespace=True
        )
        out.extend(wrapped)
    return out


async def _browse_track_lyrics_or_bio(
    hass: HomeAssistant,
    config_entry_id: str | None,
    speaker: str,
    mode: str,
    search: str,
    fallback_title: str,
) -> list[dict[str, Any]]:
    """Fetch lyrics or artist/album bio from Music Assistant + LRCLIB/Wikipedia and return wrapped slot lines."""
    parts = [p.strip() for p in search.split("|")]
    title = parts[0] if len(parts) >= 1 and parts[0] else fallback_title
    artist = parts[1] if len(parts) >= 2 else ""
    album = parts[2] if len(parts) >= 3 else ""

    state_obj = hass.states.get(speaker)
    if state_obj is not None:
        if not title or title == "None":
            title = str(state_obj.attributes.get("media_title") or "")
        if not artist or artist == "None":
            artist = str(
                state_obj.attributes.get("media_artist")
                or state_obj.attributes.get("media_album_artist")
                or ""
            )
        if not album or album == "None":
            album = str(state_obj.attributes.get("media_album_name") or "")

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

    cache_key = f"{clean_title.lower()}|{artist.lower()}|{clean_album.lower()}"
    cached = _BROWSE_LYRICS_BIO_CACHE.get(cache_key)
    if cached and cached.get(mode):
        return [
            {"name": ln, "id": "", "type": "text", "active": False}
            for ln in cached[mode]
        ]

    raw_lyrics = ""
    raw_artist_bio = ""
    raw_album_bio = ""

    def _extract_meta_strings(obj: Any) -> tuple[str, str]:
        """Return (lyrics_text, description_text) from a MA item or metadata object."""
        d = _extract_item_dict(obj)
        meta = d.get("metadata") if "metadata" in d else d
        if hasattr(meta, "to_dict") and callable(meta.to_dict):
            meta = meta.to_dict()
        if not isinstance(meta, dict):
            meta = _extract_item_dict(meta)
        lyr = str(meta.get("lyrics") or meta.get("lrc_lyrics") or "").strip()
        desc = str(meta.get("description") or "").strip()
        return lyr, desc

    # 1. Query Music Assistant in-process queues, library controllers, and metadata provider
    mass = _get_mass_client(hass)
    if mass is not None:
        try:
            if hasattr(mass, "player_queues"):
                queues = (
                    mass.player_queues.all()
                    if callable(getattr(mass.player_queues, "all", None))
                    else []
                )
                for q in queues:
                    q_dict = _extract_item_dict(q)
                    cur_item = q_dict.get("current_item") or {}
                    m_item = (
                        cur_item.get("media_item")
                        if isinstance(cur_item, dict)
                        else getattr(cur_item, "media_item", None)
                    )
                    if m_item is not None:
                        lyr, desc = _extract_meta_strings(m_item)
                        if lyr and not raw_lyrics:
                            raw_lyrics = lyr
                        if desc and not raw_album_bio:
                            raw_album_bio = desc

            if hasattr(mass, "music"):
                # Search Track in MA Library
                if not raw_lyrics and clean_title and hasattr(mass.music, "tracks"):
                    t_ctrl = mass.music.tracks
                    if hasattr(t_ctrl, "library_items"):
                        t_res = await t_ctrl.library_items(search=clean_title, limit=10)
                        t_list = getattr(t_res, "items", t_res) if t_res is not None else []
                        for trk in (t_list if isinstance(t_list, list) else []):
                            lyr, _ = _extract_meta_strings(trk)
                            if not lyr and hasattr( t_ctrl, "get_item" ):
                                try:
                                    full_t = await t_ctrl.get_item(
                                        getattr(trk, "item_id", ""),
                                        getattr(trk, "provider", "library"),
                                    )
                                    lyr, _ = _extract_meta_strings(full_t)
                                except Exception:  # noqa: BLE001
                                    pass
                            if not lyr and hasattr(mass, "metadata") and hasattr(mass.metadata, "get_track_lyrics"):
                                try:
                                    res_l = await mass.metadata.get_track_lyrics(trk)
                                    if isinstance(res_l, tuple) and res_l[0]:
                                        lyr = str(res_l[0]).strip()
                                    elif isinstance(res_l, str) and res_l.strip():
                                        lyr = res_l.strip()
                                except Exception:  # noqa: BLE001
                                    pass
                            if lyr:
                                raw_lyrics = lyr
                                break

                # Search Artist in MA Library for Artist Bio
                if artist and artist != "None" and hasattr(mass.music, "artists"):
                    ar_ctrl = mass.music.artists
                    if hasattr(ar_ctrl, "library_items"):
                        ar_res = await ar_ctrl.library_items(search=artist, limit=5)
                        ar_list = getattr(ar_res, "items", ar_res) if ar_res is not None else []
                        for ar_obj in (ar_list if isinstance(ar_list, list) else []):
                            _, desc = _extract_meta_strings(ar_obj)
                            if not desc and hasattr(ar_ctrl, "get_item"):
                                try:
                                    full_ar = await ar_ctrl.get_item(
                                        getattr(ar_obj, "item_id", ""),
                                        getattr(ar_obj, "provider", "library"),
                                    )
                                    _, desc = _extract_meta_strings(full_ar)
                                except Exception:  # noqa: BLE001
                                    pass
                            if desc:
                                raw_artist_bio = desc
                                break

                # Search Album in MA Library for Album Bio
                if clean_album and clean_album != "None" and hasattr(mass.music, "albums"):
                    al_ctrl = mass.music.albums
                    if hasattr(al_ctrl, "library_items"):
                        al_res = await al_ctrl.library_items(search=clean_album, limit=5)
                        al_list = getattr(al_res, "items", al_res) if al_res is not None else []
                        for al_obj in (al_list if isinstance(al_list, list) else []):
                            _, desc = _extract_meta_strings(al_obj)
                            if not desc and hasattr(al_ctrl, "get_item"):
                                try:
                                    full_al = await al_ctrl.get_item(
                                        getattr(al_obj, "item_id", ""),
                                        getattr(al_obj, "provider", "library"),
                                    )
                                    _, desc = _extract_meta_strings(full_al)
                                except Exception:  # noqa: BLE001
                                    pass
                            if desc:
                                raw_album_bio = desc
                                break
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("MA direct lyrics/bio lookup error: %s", err)

    session = async_get_clientsession(hass)
    timeout = aiohttp.ClientTimeout(total=5.0)
    headers = {"User-Agent": "HomeAssistant-Latter/2.0 (https://github.com/slampton/ha-latter)"}

    # 2. Fallback to LRCLIB if MA didn't return lyrics
    if not raw_lyrics and clean_title:
        for s_title in ([title.strip(), clean_title] if clean_title.lower() != title.strip().lower() else [clean_title]):
            if raw_lyrics:
                break
            try:
                q_url = f"https://lrclib.net/api/search?track_name={quote(s_title)}"
                if artist and artist != "None":
                    q_url += f"&artist_name={quote(artist)}"
                async with session.get(q_url, timeout=timeout, headers=headers) as resp:
                    if resp.status == 200:
                        items = await resp.json()
                        if isinstance(items, list) and items:
                            first = items[0]
                            if isinstance(first, dict):
                                raw_lyrics = str(
                                    first.get("plainLyrics")
                                    or first.get("syncedLyrics")
                                    or ""
                                ).strip()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("LRCLIB fallback failed for '%s': %s", s_title, err)

    # 3. Fallback to Wikipedia REST API if MA didn't return Artist / Album Bio
    if not raw_artist_bio and not raw_album_bio and artist and artist != "None":
        for query_term in (
            f"{clean_album} ({artist} album)",
            f"{artist} (band)",
            f"{artist} (musician)",
            artist,
            clean_album,
        ):
            if not query_term or query_term == "None":
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

    combined_bio_parts: list[str] = []
    if raw_album_bio:
        combined_bio_parts.append(f"ALBUM: {raw_album_bio}")
    if raw_artist_bio and raw_artist_bio != raw_album_bio:
        combined_bio_parts.append(f"ARTIST: {raw_artist_bio}")
    combined_bio = "\n".join(combined_bio_parts).strip()
    if not combined_bio:
        combined_bio = f"{clean_title} by {artist or 'Unknown Artist'}" + (
            f" — Album: {clean_album}" if clean_album and clean_album != "None" else ""
        )

    lyrics_lines = _wrap_text_to_slot_lines(raw_lyrics, width=32) if raw_lyrics else ["No lyrics found for this track."]
    bio_lines = _wrap_text_to_slot_lines(combined_bio, width=32)

    if len(_BROWSE_LYRICS_BIO_CACHE) >= 32:
        _BROWSE_LYRICS_BIO_CACHE.pop(next(iter(_BROWSE_LYRICS_BIO_CACHE)), None)
    _BROWSE_LYRICS_BIO_CACHE[cache_key] = {
        "lyrics": lyrics_lines,
        "bio": bio_lines,
    }

    target_lines = lyrics_lines if mode == "lyrics" else bio_lines
    return [
        {"name": ln, "id": "", "type": "text", "active": False}
        for ln in target_lines
    ]