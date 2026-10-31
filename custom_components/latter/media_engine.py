"""Music Assistant counterpart resolution, Sendspin queue recovery, and media command execution engine for Latter."""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .browse_engine import (
    _get_mass_client,
    async_browse_media_items,
    is_music_assistant_player,
)
from .const import DOMAIN, normalize_device_slug
from .identity import device_entities, find_device_entity_by_suffix, get_bound_esphome_device

_LOGGER = logging.getLogger(__name__)


def resolve_esphome_local_speaker(
    hass: HomeAssistant, device_slug: str, esphome_device_id: str | None = None
) -> str:
    """Resolve the on-device media_player entity for the bound ESPHome node, or '' if the device has no speaker."""
    dev_id = get_bound_esphome_device(hass, esphome_device_id, fallback_slug=device_slug)
    if dev_id:
        by_suffix = find_device_entity_by_suffix(
            hass, dev_id, "media_player", ("music", "speaker", "media_player")
        )
        if by_suffix:
            return by_suffix
        for entry in device_entities(hass, dev_id, domain="media_player"):
            if entry.platform == "esphome":
                return entry.entity_id

    slug_norm = normalize_device_slug(device_slug)
    for cand in (f"media_player.{slug_norm}", f"media_player.{slug_norm}_music"):
        if hass.states.get(cand) is not None:
            return cand

    return ""


def resolve_ma_counterpart_entity(
    hass: HomeAssistant, speaker_entity_id: str, device_slug: str
) -> str | None:
    """Find the Music Assistant media_player entity corresponding to a target speaker (or device slug fallback)."""
    state_obj = hass.states.get(speaker_entity_id)
    if state_obj and is_music_assistant_player(hass, state_obj):
        return speaker_entity_id

    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(speaker_entity_id) if speaker_entity_id else None
    spk_dev_id = spk_entry.device_id if spk_entry else None

    spk_short = speaker_entity_id.replace("media_player.", "").lower()
    core_slug = re.sub(r"(_media_player|_music|_speaker|_ma|_mass)$", "", spk_short)
    core_slug_no_prefix = re.sub(r"^latter_", "", core_slug)

    slug_norm = normalize_device_slug(device_slug)
    slug_no_prefix = re.sub(r"^latter_", "", slug_norm)

    ma_candidates: list[tuple[str, str, str | None]] = []
    for candidate in hass.states.async_all("media_player"):
        if not is_music_assistant_player(hass, candidate):
            continue
        c_entry = ent_reg.async_get(candidate.entity_id)
        c_dev_id = c_entry.device_id if c_entry else None
        cid_low = candidate.entity_id.lower()
        friendly_low = (
            str(
                candidate.attributes.get("friendly_name")
                or (c_entry.original_name if c_entry else "")
                or ""
            )
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        # Prefer available/online MA players over unavailable ones
        if candidate.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            ma_candidates.append((cid_low, friendly_low, c_dev_id))
        else:
            ma_candidates.insert(0, (cid_low, friendly_low, c_dev_id))

    # Pass 1: Match the target speaker_entity_id specifically (device_id, entity_id, or friendly_name)
    for cid_low, friendly_low, c_dev_id in ma_candidates:
        if spk_dev_id and c_dev_id and spk_dev_id == c_dev_id:
            return cid_low
        if (
            (spk_short and (spk_short in cid_low or spk_short in friendly_low))
            or (core_slug and (core_slug in cid_low or core_slug in friendly_low))
            or (
                core_slug_no_prefix
                and len(core_slug_no_prefix) >= 4
                and (
                    core_slug_no_prefix in cid_low
                    or core_slug_no_prefix in friendly_low
                )
            )
        ):
            return cid_low

    # Pass 2: Fallback to matching device_slug if target_spk is the local companion speaker
    for cid_low, friendly_low, _c_dev_id in ma_candidates:
        if (
            (slug_norm and (slug_norm in cid_low or slug_norm in friendly_low))
            or (
                slug_no_prefix
                and len(slug_no_prefix) >= 4
                and (slug_no_prefix in cid_low or slug_no_prefix in friendly_low)
            )
        ):
            return cid_low

    return None


def interpolate_speaker_position(state_obj: Any) -> float:
    """Calculate the live interpolated playback position in seconds for a media_player state."""
    if state_obj is None:
        return 0.0
    attrs = state_obj.attributes
    duration = float(attrs.get("media_duration") or 0.0)
    base_pos = float(attrs.get("media_position") or 0.0)
    updated_at = attrs.get("media_position_updated_at")
    pos = base_pos
    if state_obj.state == STATE_PLAYING and isinstance(updated_at, datetime):
        elapsed = (dt_util.utcnow() - updated_at).total_seconds()
        if elapsed > 0:
            pos = base_pos + elapsed
            if duration > 0:
                pos = min(pos, duration)
    return max(0.0, pos)


async def async_find_queue_resume_item(
    hass: HomeAssistant,
    speaker_entity_id: str,
    device_slug: str,
    last_media_uri: str,
    last_media_position: float,
) -> tuple[str, float]:
    """Query Music Assistant (controller or get_queue) for the current queue item URI and position, falling back to persisted store."""
    ma_entity = (
        resolve_ma_counterpart_entity(hass, speaker_entity_id, device_slug)
        or speaker_entity_id
    )

    mass = _get_mass_client(hass)
    if mass is not None and hasattr(mass, "player_queues"):
        try:
            for q in mass.player_queues.all() if callable(getattr(mass.player_queues, "all", None)) else []:
                q_dict = q.to_dict() if hasattr(q, "to_dict") else {}
                q_name = str(q_dict.get("display_name") or "").lower().replace("-", "_")
                if device_slug in q_name or q_dict.get("queue_id") in ma_entity:
                    cur_item = q_dict.get("current_item") or {}
                    media_item = cur_item.get("media_item") or {}
                    uri = str(media_item.get("uri") or cur_item.get("uri") or "")
                    pos = float(q_dict.get("elapsed_time") or last_media_position or 0.0)
                    if uri:
                        return uri, pos
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct mass.player_queues resume lookup failed: %s", err)

    if hass.services.has_service("music_assistant", "get_queue"):
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_entity},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict):
                q_data = resp.get(ma_entity) or resp
                if isinstance(q_data, dict):
                    cur_item = q_data.get("current_item") or q_data.get("next_item") or {}
                    if isinstance(cur_item, dict):
                        media_item = cur_item.get("media_item") or {}
                        uri = str(
                            (media_item.get("uri") if isinstance(media_item, dict) else "")
                            or cur_item.get("uri")
                            or cur_item.get("media_content_id")
                            or ""
                        )
                        pos = float(
                            q_data.get("elapsed_time")
                            or last_media_position
                            or 0.0
                        )
                        if uri:
                            return uri, pos
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue resume lookup failed: %s", err)

    return last_media_uri, last_media_position


async def async_play_media_with_ma_fallback(
    hass: HomeAssistant,
    target_spk: str,
    device_slug: str,
    media_id: str,
    media_type: str | None = None,
    enqueue: str | None = None,
) -> None:
    """Play media via Music Assistant (expanding artist/album containers into tracks when needed) or fallback to media_player.play_media."""
    ma_target = resolve_ma_counterpart_entity(hass, target_spk, device_slug)
    play_entity = ma_target or target_spk
    eff_type = (media_type or "").strip().lower()
    if not eff_type or eff_type == "music":
        if "artist" in media_id.lower():
            eff_type = "artist"
        elif "album" in media_id.lower():
            eff_type = "album"
        elif "playlist" in media_id.lower():
            eff_type = "playlist"
        elif "track" in media_id.lower():
            eff_type = "track"
        elif "radio" in media_id.lower():
            eff_type = "radio"

    if hass.services.has_service("music_assistant", "play_media"):
        payload: dict[str, Any] = {
            ATTR_ENTITY_ID: play_entity,
            "media_id": media_id,
        }
        if eff_type:
            payload["media_type"] = eff_type
        if enqueue:
            payload["enqueue"] = enqueue
        try:
            await hass.services.async_call(
                "music_assistant", "play_media", payload, blocking=True
            )
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "music_assistant.play_media(%s, %s) on %s failed: %s",
                media_id,
                eff_type,
                play_entity,
                err,
            )
            # If artist or album container playback failed (e.g., native Sendspin player or MA container resolution),
            # resolve the first playable album/track from the browse engine and play it.
            if eff_type in ("artist", "album"):
                try:
                    resolved_id = ""
                    resolved_type = "track"
                    if eff_type == "artist":
                        album_slots = await async_browse_media_items(
                            hass,
                            "artist_albums",
                            target_spk,
                            target_spk,
                            target_spk,
                            search=media_id,
                        )
                        if album_slots and album_slots[0].get("id"):
                            resolved_id = str(album_slots[0]["id"])
                            resolved_type = "album"
                    if eff_type == "album" or resolved_type == "album":
                        alb_uri = resolved_id or media_id
                        raw_tracks = await async_browse_media_items(
                            hass,
                            "album_tracks",
                            target_spk,
                            target_spk,
                            target_spk,
                            search=alb_uri,
                        )
                        track_slots = [
                            s for s in (raw_tracks or [])[:25] if s.get("id")
                        ]
                        if track_slots:
                            track_uris = [str(s["id"]) for s in track_slots]
                            await hass.services.async_call(
                                "music_assistant",
                                "play_media",
                                {
                                    ATTR_ENTITY_ID: play_entity,
                                    "media_id": track_uris,
                                    "media_type": "track",
                                    "enqueue": enqueue or "replace",
                                },
                                blocking=True,
                            )
                            return
                except Exception as inner_err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Fallback container track expansion for %s (%s) failed: %s",
                        media_id,
                        eff_type,
                        inner_err,
                    )

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: play_entity,
            "media_content_id": media_id,
            "media_content_type": eff_type or "music",
        },
        blocking=False,
    )


def resolve_assist_satellite_entity(
    hass: HomeAssistant,
    speaker_or_device_id: str | None = None,
    coordinator: Any = None,
) -> str | None:
    """Resolve an assist_satellite.* entity for a speaker entity, HA device_id, or LatterCoordinator."""
    ent_reg = er.async_get(hass)
    cand_dev_ids: list[str] = []

    if coordinator is not None:
        esp_dev_id = getattr(coordinator, "esphome_device_id", None)
        if esp_dev_id:
            cand_dev_ids.append(str(esp_dev_id))

    target = str(speaker_or_device_id or "").strip()
    if target.startswith("assist_satellite."):
        st = hass.states.get(target)
        if st is not None and st.state not in ("unavailable", "unknown"):
            return target

    if target.startswith("media_player."):
        reg_ent = ent_reg.async_get(target)
        if reg_ent and reg_ent.device_id and reg_ent.device_id not in cand_dev_ids:
            cand_dev_ids.append(reg_ent.device_id)
        for val in hass.data.get(DOMAIN, {}).values():
            if getattr(val, "local_speaker", None) == target or getattr(val, "active_speaker", None) == target:
                c_dev_id = getattr(val, "esphome_device_id", None)
                if c_dev_id and str(c_dev_id) not in cand_dev_ids:
                    cand_dev_ids.append(str(c_dev_id))
    elif target and "." not in target and target not in cand_dev_ids:
        cand_dev_ids.append(target)

    for dev_id in cand_dev_ids:
        for entry in er.async_entries_for_device(ent_reg, dev_id):
            if entry.domain == "assist_satellite" and not entry.disabled_by:
                st = hass.states.get(entry.entity_id)
                if st is not None and st.state not in ("unavailable", "unknown"):
                    return entry.entity_id
    return None


async def async_announce_on_targets(
    hass: HomeAssistant,
    speakers: list[str],
    message: str = "",
    media_url: str = "",
    tts_entity: str = "",
    blocking: bool = False,
) -> None:
    """Route announcements through assist_satellite.announce first, falling back to media_player/tts for non-satellites."""
    if not speakers or (not message and not media_url):
        return

    satellites: list[str] = []
    fallback_speakers: list[str] = []
    has_sat_announce = hass.services.has_service("assist_satellite", "announce")

    for spk in speakers:
        sat_ent = resolve_assist_satellite_entity(hass, spk) if has_sat_announce else None
        if sat_ent:
            if sat_ent not in satellites:
                satellites.append(sat_ent)
        elif spk not in fallback_speakers:
            fallback_speakers.append(spk)

    if satellites and has_sat_announce:
        sat_payload: dict[str, Any] = {ATTR_ENTITY_ID: satellites}
        if media_url:
            sat_payload["media_id"] = media_url
        else:
            sat_payload["message"] = message
        try:
            await hass.services.async_call(
                "assist_satellite",
                "announce",
                sat_payload,
                blocking=blocking,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("assist_satellite.announce failed on %s, falling back: %s", satellites, err)
            for spk in speakers:
                if spk not in fallback_speakers:
                    fallback_speakers.append(spk)

    if not fallback_speakers:
        return

    if media_url:
        ma_speakers = [
            s
            for s in fallback_speakers
            if hass.states.get(s) and is_music_assistant_player(hass, hass.states.get(s))
        ]
        other_speakers = [s for s in fallback_speakers if s not in ma_speakers]

        if ma_speakers and hass.services.has_service("music_assistant", "play_announcement"):
            await hass.services.async_call(
                "music_assistant",
                "play_announcement",
                {
                    ATTR_ENTITY_ID: ma_speakers,
                    "url": media_url,
                },
                blocking=blocking,
            )
        else:
            other_speakers = fallback_speakers

        if other_speakers:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: other_speakers,
                    "media_content_id": media_url,
                    "media_content_type": "music",
                    "announce": True,
                },
                blocking=blocking,
            )
        return

    if message:
        if not tts_entity:
            tts_states = hass.states.async_all("tts")
            if tts_states:
                tts_entity = tts_states[0].entity_id

        if tts_entity and hass.services.has_service("tts", "speak"):
            await hass.services.async_call(
                "tts",
                "speak",
                {
                    ATTR_ENTITY_ID: tts_entity,
                    "media_player_entity_id": fallback_speakers,
                    "message": message,
                    "cache": False,
                },
                blocking=blocking,
            )
        elif hass.services.has_service("tts", "cloud_say"):
            await hass.services.async_call(
                "tts",
                "cloud_say",
                {ATTR_ENTITY_ID: fallback_speakers, "message": message},
                blocking=blocking,
            )

