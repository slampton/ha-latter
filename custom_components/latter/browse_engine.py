"""Music Assistant & Home Assistant Media Browse Engine for Latter."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Direct library categories supported by music_assistant.get_library
LIBRARY_MEDIA_TYPES: set[str] = {
    "playlist",
    "artist",
    "album",
    "radio",
    "podcast",
    "audiobook",
    "track",
}


def _get_ma_config_entry_id(hass: HomeAssistant) -> str | None:
    """Auto-discover the loaded Music Assistant config_entry_id."""
    entries = hass.config_entries.async_entries("music_assistant")
    for entry in entries:
        if entry.state.name == "LOADED":
            return entry.entry_id
    if entries:
        return entries[0].entry_id
    return None


def _get_mass_client(hass: HomeAssistant) -> Any | None:
    """Attempt to retrieve the in-process MusicAssistantClient instance from HA."""
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


def _extract_item_dict(raw: Any) -> dict[str, Any]:
    """Convert a Music Assistant model or dict into a normalized dictionary."""
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
        "media_type",
        "media_content_id",
        "media_content_type",
        "year",
        "position",
        "track_number",
        "artists",
        "artist_str",
        "album",
        "queue_item_id",
        "media_item",
    ):
        if hasattr(raw, attr):
            result[attr] = getattr(raw, attr)
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


async def _call_ma_get_library(
    hass: HomeAssistant,
    config_entry_id: str,
    media_type: str,
    favorite: bool | None = None,
    search: str | None = None,
    limit: int = 250,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    """Call music_assistant.get_library and return normalized item dicts."""
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
        if isinstance(resp, dict):
            raw_items = resp.get("items") or []
            return [_extract_item_dict(x) for x in raw_items]
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("music_assistant.get_library(%s) failed: %s", media_type, err)
    return []


async def _browse_speakers(
    hass: HomeAssistant,
    active_speaker: str,
    last_speaker: str,
    local_speaker: str,
) -> list[dict[str, Any]]:
    """Build sorted speaker list matching Pocket Assistant v2.0 priority rules."""
    items: list[dict[str, Any]] = []
    for state_obj in hass.states.async_all("media_player"):
        if state_obj.state in ("unavailable", "unknown"):
            continue
        ent_id = state_obj.entity_id
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        is_local = ent_id == local_speaker
        if is_local and "pocket assistant" not in friendly.lower():
            friendly = f"Pocket Assistant ({friendly})"

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
            limit=50,
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
        limit=250,
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
        uri = str(item.get("uri") or "")
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
    artist_search: str,
    artist_album_sort: str,
) -> list[dict[str, Any]]:
    """Fetch albums belonging to a specific artist (by name or URI)."""
    artist_query = artist_search.strip()
    if not artist_query:
        return []

    raw_items = await _call_ma_get_library(
        hass,
        config_entry_id=config_entry_id,
        media_type="album",
        search=artist_query,
        limit=200,
    )

    query_lower = artist_query.lower()
    filtered: list[dict[str, Any]] = []
    for item in raw_items:
        artist_name = _extract_artist_name(item).lower()
        if query_lower in artist_name or not artist_name:
            filtered.append(item)

    if not filtered:
        filtered = raw_items

    if artist_album_sort == "year_desc":
        filtered.sort(
            key=lambda x: (int(x.get("year") or 0), str(x.get("name") or "").lower()),
            reverse=True,
        )
    elif artist_album_sort == "name":
        filtered.sort(key=lambda x: str(x.get("name") or "").lower())
    else:
        filtered.sort(
            key=lambda x: (
                int(x.get("year") or 9999),
                str(x.get("name") or "").lower(),
            )
        )

    results: list[dict[str, Any]] = []
    for item in filtered:
        uri = str(item.get("uri") or "")
        name = str(item.get("name") or "")
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
    album_ref: str,
    current_track_title: str,
) -> list[dict[str, Any]]:
    """Browse tracks of an album by URI or album title."""
    album_ref = album_ref.strip()
    if not album_ref:
        return []

    tracks: list[dict[str, Any]] = []

    # 1. Try direct Music Assistant controller album_tracks if URI is provided
    mass = _get_mass_client(hass)
    if mass is not None and "://" in album_ref and hasattr(mass, "music"):
        provider, item_id = _parse_uri(album_ref)
        try:
            albums_ctrl = getattr(mass.music, "albums", None)
            if albums_ctrl and hasattr(albums_ctrl, "tracks"):
                raw_tracks = await albums_ctrl.tracks(item_id, provider)
                tracks = [_extract_item_dict(t) for t in (raw_tracks or [])]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct mass.music.albums.tracks failed: %s", err)

    # 2. Fallback: search tracks via music_assistant.get_library
    if not tracks:
        album_name = album_ref
        if "://" in album_ref:
            # Resolve album name from library first
            albums = await _call_ma_get_library(
                hass, config_entry_id=config_entry_id, media_type="album", limit=250
            )
            for alb in albums:
                if str(alb.get("uri")) == album_ref:
                    album_name = str(alb.get("name") or album_ref)
                    break

        raw_tracks = await _call_ma_get_library(
            hass,
            config_entry_id=config_entry_id,
            media_type="track",
            search=album_name,
            limit=200,
        )
        album_lower = album_name.lower()
        for trk in raw_tracks:
            alb_Field = trk.get("album")
            alb_dict = _extract_item_dict(alb_Field) if alb_Field else {}
            trk_alb_name = str(alb_dict.get("name") or "").lower()
            trk_alb_uri = str(alb_dict.get("uri") or "")
            if (
                trk_alb_uri == album_ref
                or trk_alb_name == album_lower
                or album_lower in trk_alb_name
            ):
                tracks.append(trk)
        if not tracks:
            tracks = raw_tracks

    tracks.sort(
        key=lambda x: (
            int(x.get("disc_number") or 1),
            int(x.get("track_number") or x.get("position") or 999),
            str(x.get("name") or "").lower(),
        )
    )

    cur_lower = current_track_title.strip().lower()
    results: list[dict[str, Any]] = []
    for idx, trk in enumerate(tracks, start=1):
        uri = str(trk.get("uri") or "")
        name = str(trk.get("name") or trk.get("title") or "")
        if not uri or not name:
            continue
        t_num = trk.get("track_number") or idx
        is_active = bool(cur_lower and name.strip().lower() == cur_lower)
        results.append(
            {
                "name": f"{t_num}. {name}",
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
    """Fetch upcoming queue items natively from Music Assistant (zero mass_queue needed)."""
    raw_queue_items: list[dict[str, Any]] = []

    # 1. Native in-process Music Assistant player_queues controller
    mass = _get_mass_client(hass)
    state_obj = hass.states.get(speaker)
    if mass is not None and hasattr(mass, "player_queues"):
        try:
            # Find matching queue_id (often matches player_id or entity attribute)
            queue_id = None
            if state_obj:
                queue_id = state_obj.attributes.get("mass_player_id")
            if not queue_id and hasattr(mass, "players"):
                for player in mass.players.all():
                    p_dict = _extract_item_dict(player)
                    p_name = str(p_dict.get("display_name") or p_dict.get("name") or "")
                    if state_obj and p_name.lower() == str(
                        state_obj.attributes.get("friendly_name", "")
                    ).lower():
                        queue_id = p_dict.get("player_id")
                        break
            if queue_id:
                q_items = await mass.player_queues.items(queue_id, limit=100)
                raw_queue_items = [_extract_item_dict(x) for x in (q_items or [])]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct mass.player_queues.items failed: %s", err)

    # 2. Fallback: mass_queue.get_queue_items if user happens to have mass_queue installed
    if not raw_queue_items and hass.services.has_service("mass_queue", "get_queue_items"):
        try:
            resp = await hass.services.async_call(
                "mass_queue",
                "get_queue_items",
                {"entity": speaker, "limit": 100},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict) and speaker in resp:
                raw_queue_items = [
                    _extract_item_dict(x) for x in (resp[speaker] or [])
                ]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fallback mass_queue.get_queue_items failed: %s", err)

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
            item.get("queue_item_id")
            or item.get("media_content_id")
            or media_item.get("uri")
            or item.get("uri")
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
    speaker: str,
    podcast_uri: str,
    podcast_sort: str,
    current_track_title: str,
) -> list[dict[str, Any]]:
    """Fetch podcast episodes natively via MA controller or media_player.browse_media."""
    podcast_uri = podcast_uri.strip()
    if not podcast_uri:
        return []

    raw_episodes: list[dict[str, Any]] = []

    # 1. Native in-process Music Assistant podcasts.episodes controller
    mass = _get_mass_client(hass)
    if mass is not None and hasattr(mass, "music"):
        provider, item_id = _parse_uri(podcast_uri)
        try:
            podcasts_ctrl = getattr(mass.music, "podcasts", None)
            if podcasts_ctrl and hasattr(podcasts_ctrl, "episodes"):
                eps = await podcasts_ctrl.episodes(item_id, provider)
                raw_episodes = [_extract_item_dict(e) for e in (eps or [])]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct mass.music.podcasts.episodes failed: %s", err)

    # 2. Standard Home Assistant media_player.browse_media service (HA 2024.7+)
    if not raw_episodes and hass.services.has_service("media_player", "browse_media"):
        try:
            resp = await hass.services.async_call(
                "media_player",
                "browse_media",
                {
                    "entity_id": speaker,
                    "media_content_type": "podcast",
                    "media_content_id": podcast_uri,
                },
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict):
                player_browse = resp.get(speaker) or resp
                children = player_browse.get("children") or []
                raw_episodes = [_extract_item_dict(c) for c in children]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("media_player.browse_media podcast failed: %s", err)

    # 3. Fallback: mass_queue.get_podcast_episodes if installed
    if not raw_episodes and hass.services.has_service(
        "mass_queue", "get_podcast_episodes"
    ):
        try:
            resp = await hass.services.async_call(
                "mass_queue",
                "get_podcast_episodes",
                {" podcast_id": podcast_uri},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict):
                eps = resp.get("episodes") or resp.get("items") or []
                raw_episodes = [_extract_item_dict(e) for e in eps]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fallback mass_queue.get_podcast_episodes failed: %s", err)

    if podcast_sort == "oldest":
        raw_episodes.sort(
            key=lambda x: int(x.get("position") or x.get("track_number") or 0)
        )
    else:
        raw_episodes.sort(
            key=lambda x: int(x.get("position") or x.get("track_number") or 0),
            reverse=True,
        )

    cur_lower = current_track_title.strip().lower()
    results: list[dict[str, Any]] = []
    for ep in raw_episodes:
        name = str(ep.get("name") or ep.get("title") or "")
        uri = str(ep.get("uri") or ep.get("media_content_id") or "")
        if not name or not uri:
            continue
        # Strip leading dates if overly verbose
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

    if mode == "podcast_episodes":
        return await _browse_podcast_episodes(
            hass, speaker, search, podcast_sort, current_title
        )

    config_entry_id = _get_ma_config_entry_id(hass)
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
            hass, config_entry_id, search, artist_album_sort
        )

    if mode == "album_tracks":
        return await _browse_album_tracks(
            hass, config_entry_id, search, current_title
        )

    if mode == "current_album_tracks":
        album_ref = search.strip() or current_album
        return await _browse_album_tracks(
            hass, config_entry_id, album_ref, current_title
        )

    _LOGGER.warning("Unknown Latter music_browse mode: %s", mode)
    return []