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
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util

from .browse_engine import (
    async_browse_media_items,
    is_music_assistant_player,
)
from .const import DOMAIN, normalize_device_slug
from .identity import (
    device_entities,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
)

_LOGGER = logging.getLogger(__name__)

_MAC_TOKEN_RE = re.compile(
    r"(?:^|[^0-9a-fA-F])((?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12})(?:$|[^0-9a-fA-F])"
)
_KNOWN_URI_MEDIA_TYPES: frozenset[str] = frozenset(
    {
        "artist",
        "album",
        "playlist",
        "track",
        "radio",
        "podcast",
        "audiobook",
        "podcast_episode",
    }
)


def _extract_macs_from_string(raw: str | None) -> set[str]:
    """Extract normalized MAC addresses from an identifier, connection value, or unique_id."""
    if not raw:
        return set()
    out: set[str] = set()
    for match in _MAC_TOKEN_RE.finditer(str(raw)):
        token = match.group(1)
        if token:
            out.add(dr.format_mac(token))
    return out


def _extract_macs_from_device_or_entry(
    dev: dr.DeviceEntry | None, ent: er.RegistryEntry | None = None
) -> set[str]:
    """Collect all normalized MAC addresses associated with a DeviceEntry and/or RegistryEntry."""
    macs: set[str] = set()
    if dev is not None:
        for _conn_type, conn_val in dev.connections:
            if conn_val:
                macs.update(_extract_macs_from_string(str(conn_val)))
        for _ident_domain, ident_val in dev.identifiers:
            if ident_val:
                macs.update(_extract_macs_from_string(str(ident_val)))
    if ent is not None and ent.unique_id:
        macs.update(_extract_macs_from_string(str(ent.unique_id)))
    return macs


@callback
def clear_ma_counterpart_cache(hass: HomeAssistant) -> None:
    """Clear the cached speaker -> Music Assistant counterpart mapping and unsubscribe listeners on unload."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return
    cache = domain_data.get("_ma_counterpart_cache")
    if isinstance(cache, dict):
        cache.clear()
    unsubs = domain_data.pop("_ma_cache_unsubs", None)
    if isinstance(unsubs, (list, tuple)):
        for unsub in unsubs:
            if callable(unsub):
                unsub()


@callback
def _ensure_ma_cache_listeners(hass: HomeAssistant) -> None:
    """Subscribe once to entity and device registry updates to invalidate the MA counterpart cache."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "_ma_cache_unsubs" in domain_data:
        return

    @callback
    def _on_registry_updated(_event: Event) -> None:
        cache = domain_data.get("_ma_counterpart_cache")
        if isinstance(cache, dict):
            cache.clear()

    unsub_ent = hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED, _on_registry_updated
    )
    unsub_dev = hass.bus.async_listen(
        dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_registry_updated
    )
    domain_data["_ma_cache_unsubs"] = (unsub_ent, unsub_dev)


def _parse_media_uri_type(media_id: str) -> str:
    """Extract canonical media_type from a provider://type/id URI without substring guessing."""
    raw = str(media_id or "").strip()
    if "://" not in raw:
        return ""
    scheme, rest = raw.split("://", 1)
    if scheme.lower() in ("http", "https", "rtsp", "rtsps", "media-source"):
        return ""
    type_segment = rest.split("/", 1)[0].strip().lower()
    if (
        type_segment.endswith("s")
        and type_segment[:-1] in _KNOWN_URI_MEDIA_TYPES
    ):
        type_segment = type_segment[:-1]
    if type_segment == "podcast_episode":
        return "track"
    if type_segment in _KNOWN_URI_MEDIA_TYPES:
        return type_segment
    return ""


def resolve_esphome_local_speaker(
    hass: HomeAssistant, device_slug: str, esphome_device_id: str | None = None
) -> str:
    """Resolve the on-device media_player entity for the bound ESPHome node, or '' if the device has no speaker."""
    dev = get_bound_esphome_device(hass, esphome_device_id, fallback_slug=device_slug)
    if dev is not None:
        by_suffix = find_device_entity_by_suffix(
            hass, dev.id, "media_player", ("_music", "_speaker", "_media_player")
        )
        if by_suffix:
            return by_suffix
        for entry in device_entities(hass, dev.id, domain="media_player"):
            if entry.platform == "esphome":
                return entry.entity_id

    slug_norm = normalize_device_slug(device_slug)
    for cand in (f"media_player.{slug_norm}", f"media_player.{slug_norm}_music"):
        if hass.states.get(cand) is not None:
            return cand

    return ""


def _ma_link_issue_id(coordinator: Any) -> str:
    """Return the per-Device `link_ma_player` repair issue ID (scoped by config subentry)."""
    return f"link_ma_player_{getattr(coordinator, 'subentry_id', '')}"


@callback
def _update_ma_link_issue(
    hass: HomeAssistant, coordinator: Any, speaker_entity_id: str, matched: bool
) -> None:
    """Raise the `link_ma_player` repair when a Latter Device's speaker has no Music Assistant counterpart; clear it otherwise."""
    issue_id = _ma_link_issue_id(coordinator)
    if matched or not hass.config_entries.async_entries("music_assistant"):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    entry = getattr(coordinator, "entry", None)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="link_ma_player",
        translation_placeholders={
            "device_slug": str(getattr(coordinator, "device_slug", "") or ""),
            "speaker_entity": speaker_entity_id,
        },
        config_entry_id=getattr(entry, "entry_id", None),
    )


def resolve_ma_counterpart_entity(
    hass: HomeAssistant, speaker_entity_id: str
) -> str | None:
    """Find the Music Assistant media_player for a speaker by exact device_id, then by MAC; else None.

    When the speaker is a Latter Device's own speaker and no counterpart exists, the
    `link_ma_player` repair is raised for that Device (and cleared once a match is found).
    """
    if not speaker_entity_id:
        return None

    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(speaker_entity_id)
    if spk_entry is not None and spk_entry.platform == "music_assistant":
        return speaker_entity_id

    _ensure_ma_cache_listeners(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    cache: dict[str, str | None] = domain_data.setdefault(
        "_ma_counterpart_cache", {}
    )
    if speaker_entity_id in cache:
        cached_ent = cache[speaker_entity_id]
        if cached_ent is None or ent_reg.async_get(cached_ent) is not None:
            return cached_ent

    dev_reg = dr.async_get(hass)
    target_dev_ids: set[str] = set()
    target_macs: set[str] = set()

    # The Latter Device whose bound ESPHome speaker this is (exact entity_id equality only).
    owner_coord: Any = next(
        (
            val
            for val in domain_data.values()
            if hasattr(val, "device_slug")
            and getattr(val, "local_speaker", None) == speaker_entity_id
        ),
        None,
    )

    if spk_entry is not None:
        if spk_entry.device_id:
            target_dev_ids.add(spk_entry.device_id)
        spk_dev = (
            dev_reg.async_get(spk_entry.device_id)
            if spk_entry.device_id
            else None
        )
        target_macs.update(
            _extract_macs_from_device_or_entry(spk_dev, spk_entry)
        )

    if owner_coord is not None:
        esp_dev_id = getattr(owner_coord, "esphome_device_id", None)
        if esp_dev_id:
            target_dev_ids.add(str(esp_dev_id))
        coord_mac = getattr(owner_coord, "device_mac", None)
        if coord_mac:
            target_macs.add(dr.format_mac(str(coord_mac)))

    for did in list(target_dev_ids):
        d_obj = dev_reg.async_get(did)
        if d_obj is not None:
            if d_obj.via_device_id:
                target_dev_ids.add(d_obj.via_device_id)
            target_macs.update(_extract_macs_from_device_or_entry(d_obj, None))

    ma_candidates: list[tuple[er.RegistryEntry, dr.DeviceEntry | None]] = []
    for ma_cfg in hass.config_entries.async_entries("music_assistant"):
        for entry in er.async_entries_for_config_entry(ent_reg, ma_cfg.entry_id):
            if (
                entry.domain != "media_player"
                or entry.platform != "music_assistant"
                or entry.disabled_by
            ):
                continue
            c_dev = dev_reg.async_get(entry.device_id) if entry.device_id else None
            st = hass.states.get(entry.entity_id)
            if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                ma_candidates.insert(0, (entry, c_dev))
            else:
                ma_candidates.append((entry, c_dev))

    matched_entity: str | None = None

    # Pass 1: exact device_id match in the entity/device registry
    if target_dev_ids:
        for c_entry, c_dev in ma_candidates:
            if c_entry.device_id and (
                c_entry.device_id in target_dev_ids
                or (c_dev is not None and c_dev.via_device_id in target_dev_ids)
            ):
                matched_entity = c_entry.entity_id
                break

    # Pass 2: exact MAC / player_id match
    if matched_entity is None and target_macs:
        for c_entry, c_dev in ma_candidates:
            cand_macs = _extract_macs_from_device_or_entry(c_dev, c_entry)
            if target_macs & cand_macs:
                matched_entity = c_entry.entity_id
                break

    if owner_coord is not None:
        _update_ma_link_issue(
            hass, owner_coord, speaker_entity_id, matched_entity is not None
        )

    cache[speaker_entity_id] = matched_entity
    return matched_entity


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
    last_media_uri: str,
    last_media_position: float,
) -> tuple[str, float]:
    """Query Music Assistant get_queue for the current queue item URI and position, falling back to persisted store."""
    ma_entity = resolve_ma_counterpart_entity(
        hass, speaker_entity_id
    )
    if ma_entity and hass.services.has_service("music_assistant", "get_queue"):
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
    media_id: str,
    media_type: str | None = None,
    enqueue: str | None = None,
) -> None:
    """Play media via Music Assistant (expanding artist/album containers into tracks when needed)."""
    ma_target = resolve_ma_counterpart_entity(hass, target_spk)
    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(target_spk) if target_spk else None
    is_esphome_sendspin = bool(spk_entry and spk_entry.platform == "esphome")

    eff_type = (media_type or "").strip().lower()
    if not eff_type or eff_type == "music":
        parsed_uri_type = _parse_media_uri_type(media_id)
        if parsed_uri_type:
            eff_type = parsed_uri_type

    if ma_target and hass.services.has_service("music_assistant", "play_media"):
        payload: dict[str, Any] = {
            ATTR_ENTITY_ID: ma_target,
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
                ma_target,
                err,
            )
            # If artist or album container playback failed, resolve playable tracks from the browse engine and enqueue them.
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
                                    ATTR_ENTITY_ID: ma_target,
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

    if is_esphome_sendspin or not ma_target:
        if is_esphome_sendspin:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="ma_counterpart_required",
                translation_placeholders={"speaker": target_spk},
            )

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: target_spk,
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
            if not hasattr(val, "device_slug"):
                continue
            local_spk = getattr(val, "local_speaker", None)
            if (
                local_spk == target
                or getattr(val, "active_speaker", None) == target
                or (
                    local_spk
                    and resolve_ma_counterpart_entity(
                        hass, str(local_spk)
                    )
                    == target
                )
            ):
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
    """Route announcements through assist_satellite.announce first, deduplicating by physical device_id."""
    if not speakers or (not message and not media_url):
        return

    ent_reg = er.async_get(hass)
    satellites: list[str] = []
    fallback_speakers: list[str] = []
    seen_device_ids: set[str] = set()
    has_sat_announce = hass.services.has_service("assist_satellite", "announce")

    for spk in speakers:
        if not spk:
            continue
        sat_ent = (
            resolve_assist_satellite_entity(hass, spk)
            if has_sat_announce
            else None
        )
        if sat_ent:
            sat_reg = ent_reg.async_get(sat_ent)
            sat_dev_id = sat_reg.device_id if sat_reg and sat_reg.device_id else sat_ent
            if sat_dev_id in seen_device_ids:
                continue
            seen_device_ids.add(sat_dev_id)
            spk_reg = ent_reg.async_get(spk)
            if spk_reg and spk_reg.device_id:
                seen_device_ids.add(spk_reg.device_id)
            if sat_ent not in satellites:
                satellites.append(sat_ent)
        else:
            spk_reg = ent_reg.async_get(spk)
            spk_dev_id = spk_reg.device_id if spk_reg and spk_reg.device_id else spk
            if spk_dev_id in seen_device_ids:
                continue
            seen_device_ids.add(spk_dev_id)
            if spk not in fallback_speakers:
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
                if spk and not spk.startswith("assist_satellite.") and spk not in fallback_speakers:
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

