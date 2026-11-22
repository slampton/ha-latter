"""Assist Satellite and multi-speaker TTS / clip announcement routing (`L2a`)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..hub_registry import get_area_state_index, iter_coordinators
from .linking import is_music_assistant_player, resolve_ma_counterpart_entity

_LOGGER = logging.getLogger(__name__)


def _collect_candidate_device_ids(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    target: str,
    coordinator: Any,
) -> list[str]:
    cand_dev_ids: list[str] = []
    if coordinator is not None and (esp_dev_id := getattr(coordinator, "esphome_device_id", None)):
        cand_dev_ids.append(str(esp_dev_id))

    if target.startswith("media_player."):
        reg_ent = ent_reg.async_get(target)
        if reg_ent and reg_ent.device_id and reg_ent.device_id not in cand_dev_ids:
            cand_dev_ids.append(reg_ent.device_id)
        for val in iter_coordinators(hass):
            local_spk = getattr(val, "local_speaker", None)
            matches_coord = (
                local_spk == target
                or getattr(val, "active_speaker", None) == target
                or bool(local_spk and resolve_ma_counterpart_entity(hass, str(local_spk)) == target)
            )
            if (
                matches_coord
                and (c_dev_id := getattr(val, "esphome_device_id", None))
                and str(c_dev_id) not in cand_dev_ids
            ):
                cand_dev_ids.append(str(c_dev_id))
    elif target and "." not in target and target not in cand_dev_ids:
        cand_dev_ids.append(target)
    return cand_dev_ids


def resolve_assist_satellite_entity(
    hass: HomeAssistant,
    speaker_or_device_id: str | None = None,
    coordinator: Any = None,
) -> str | None:
    """Resolve an `assist_satellite.*` entity for a speaker entity, HA `device_id`, or coordinator."""
    target = str(speaker_or_device_id or "").strip()
    if target.startswith("assist_satellite."):
        st = hass.states.get(target)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return target

    ent_reg = er.async_get(hass)
    for dev_id in _collect_candidate_device_ids(hass, ent_reg, target, coordinator):
        for entry in er.async_entries_for_device(ent_reg, dev_id):
            if entry.domain == "assist_satellite" and not entry.disabled_by:
                st = hass.states.get(entry.entity_id)
                if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    return str(entry.entity_id)
    return None


def _partition_announce_targets(
    hass: HomeAssistant, speakers: list[str], *, has_sat_announce: bool
) -> tuple[list[str], list[str]]:
    ent_reg = er.async_get(hass)
    satellites: list[str] = []
    fallback_speakers: list[str] = []
    seen_device_ids: set[str] = set()

    for spk in speakers:
        if not spk:
            continue
        sat_ent = resolve_assist_satellite_entity(hass, spk) if has_sat_announce else None
        if sat_ent:
            sat_reg = ent_reg.async_get(sat_ent)
            sat_dev_id = sat_reg.device_id if sat_reg and sat_reg.device_id else sat_ent
            if sat_dev_id in seen_device_ids:
                continue
            seen_device_ids.add(sat_dev_id)
            if (spk_reg := ent_reg.async_get(spk)) and spk_reg.device_id:
                seen_device_ids.add(spk_reg.device_id)
            if sat_ent not in satellites:
                satellites.append(sat_ent)
            continue

        spk_reg = ent_reg.async_get(spk)
        spk_dev_id = spk_reg.device_id if spk_reg and spk_reg.device_id else spk
        if spk_dev_id in seen_device_ids:
            continue
        seen_device_ids.add(spk_dev_id)
        if spk not in fallback_speakers:
            fallback_speakers.append(spk)
    return satellites, fallback_speakers


async def _async_announce_media_url_on_fallbacks(
    hass: HomeAssistant, fallback_speakers: list[str], media_url: str, *, blocking: bool
) -> None:
    ma_speakers = [
        s
        for s in fallback_speakers
        if (st := hass.states.get(s)) is not None and is_music_assistant_player(hass, st)
    ]
    other_speakers = [s for s in fallback_speakers if s not in ma_speakers]

    if ma_speakers and hass.services.has_service("music_assistant", "play_announcement"):
        await hass.services.async_call(
            "music_assistant",
            "play_announcement",
            {ATTR_ENTITY_ID: ma_speakers, "url": media_url},
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


async def _async_speak_tts_on_fallbacks(
    hass: HomeAssistant,
    fallback_speakers: list[str],
    message: str,
    tts_entity: str,
    *,
    blocking: bool,
) -> None:
    eff_tts = tts_entity
    if not eff_tts:
        tts_states = get_area_state_index(hass).states_for_domain("tts")
        if tts_states:
            eff_tts = tts_states[0].entity_id
    if eff_tts and hass.services.has_service("tts", "speak"):
        await hass.services.async_call(
            "tts",
            "speak",
            {
                ATTR_ENTITY_ID: eff_tts,
                "media_player_entity_id": fallback_speakers,
                "message": message,
                "cache": False,
            },
            blocking=blocking,
        )


async def async_announce_on_targets(  # noqa: PLR0913, PLR0917
    hass: HomeAssistant,
    speakers: list[str],
    message: str = "",
    media_url: str = "",
    tts_entity: str = "",
    blocking: bool = False,
) -> None:
    """Route announcements through `assist_satellite.announce` first, deduplicating by `device_id`."""
    if not speakers or (not message and not media_url):
        return

    has_sat_announce = hass.services.has_service("assist_satellite", "announce")
    satellites, fallback_speakers = _partition_announce_targets(
        hass, speakers, has_sat_announce=has_sat_announce
    )

    if satellites and has_sat_announce:
        sat_payload: dict[str, Any] = {
            ATTR_ENTITY_ID: satellites,
            **({"media_id": media_url} if media_url else {"message": message}),
        }
        try:
            await hass.services.async_call(
                "assist_satellite", "announce", sat_payload, blocking=blocking
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "assist_satellite.announce failed on %s, falling back: %s", satellites, err
            )
            fallback_speakers.extend(
                spk
                for spk in speakers
                if spk and not spk.startswith("assist_satellite.") and spk not in fallback_speakers
            )

    if not fallback_speakers:
        return
    if media_url:
        await _async_announce_media_url_on_fallbacks(
            hass, fallback_speakers, media_url, blocking=blocking
        )
    elif message:
        await _async_speak_tts_on_fallbacks(
            hass, fallback_speakers, message, tts_entity, blocking=blocking
        )
