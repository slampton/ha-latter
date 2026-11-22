"""Protocol v3 `active_media` capability bitmask and payload builder."""

from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Final

from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..protocol_codec import pack_active_media_fields
from .linking import resolve_ma_counterpart_entity, safe_float
from .playback import (
    VOLUME_MUTE_FLAG,
    VOLUME_SET_FLAG,
    SpeakerMediaSnapshot,
    normalize_repeat_mode,
    read_live_ma_queue_state,
    read_volume_from_target,
    resolve_effective_favorite,
    resolve_raw_source_favorite,
    resolve_speaker_media_snapshot,
)
from .tts_queue import is_ephemeral_announcement_uri

MEDIA_CAP_PAUSE: Final[int] = 1
MEDIA_CAP_SEEK: Final[int] = 2
MEDIA_CAP_VOLUME_SET: Final[int] = 4
MEDIA_CAP_VOLUME_MUTE: Final[int] = 8
MEDIA_CAP_PREVIOUS_TRACK: Final[int] = 16
MEDIA_CAP_NEXT_TRACK: Final[int] = 32
MEDIA_CAP_SHUFFLE_SET: Final[int] = 64
MEDIA_CAP_REPEAT_SET: Final[int] = 128
MEDIA_CAP_GROUPING: Final[int] = 256
MEDIA_CAP_MUSIC_ASSISTANT: Final[int] = 512
MEDIA_CAP_FAVORITE: Final[int] = 1024
MEDIA_CAP_DEFAULT_TRANSPORT: Final[int] = (
    MEDIA_CAP_PAUSE
    | MEDIA_CAP_SEEK
    | MEDIA_CAP_VOLUME_SET
    | MEDIA_CAP_VOLUME_MUTE
    | MEDIA_CAP_PREVIOUS_TRACK
    | MEDIA_CAP_NEXT_TRACK
)

_HA_FEATURE_PAUSE: Final[int] = 1
_HA_FEATURE_SEEK: Final[int] = 2
_HA_FEATURE_PREVIOUS_TRACK: Final[int] = 16
_HA_FEATURE_NEXT_TRACK: Final[int] = 32
_HA_FEATURE_SHUFFLE_SET: Final[int] = 16384
_HA_FEATURE_REPEAT_SET: Final[int] = 262144
_HA_FEATURE_GROUPING: Final[int] = 524288
_CACHE_TTL_S: Final[float] = 0.15
_MAX_QUEUE_U16: Final[int] = 65535
_CAPS_MASK_U16: Final[int] = 0xFFFF

_FEATURE_CAP_PAIRS: Final[tuple[tuple[int, int], ...]] = (
    (_HA_FEATURE_PAUSE, MEDIA_CAP_PAUSE),
    (_HA_FEATURE_SEEK, MEDIA_CAP_SEEK),
    (VOLUME_SET_FLAG, MEDIA_CAP_VOLUME_SET),
    (VOLUME_MUTE_FLAG, MEDIA_CAP_VOLUME_MUTE),
    (_HA_FEATURE_PREVIOUS_TRACK, MEDIA_CAP_PREVIOUS_TRACK),
    (_HA_FEATURE_NEXT_TRACK, MEDIA_CAP_NEXT_TRACK),
    (_HA_FEATURE_SHUFFLE_SET, MEDIA_CAP_SHUFFLE_SET),
    (_HA_FEATURE_REPEAT_SET, MEDIA_CAP_REPEAT_SET),
    (_HA_FEATURE_GROUPING, MEDIA_CAP_GROUPING),
)


def _parse_int_features(state_obj: State | None) -> int | None:
    if state_obj is None:
        return None
    raw = state_obj.attributes.get("supported_features")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _apply_volume_entity_caps(caps: int, vol_st: State | None) -> int:
    if vol_st is None or vol_st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return caps
    if vol_st.domain in ("number", "input_number"):
        return caps | MEDIA_CAP_VOLUME_SET
    if vol_st.domain != "media_player":
        return caps
    sf_vol = _parse_int_features(vol_st)
    if sf_vol is None:
        return caps | MEDIA_CAP_VOLUME_SET | MEDIA_CAP_VOLUME_MUTE
    if sf_vol & VOLUME_SET_FLAG:
        caps |= MEDIA_CAP_VOLUME_SET
    if sf_vol & VOLUME_MUTE_FLAG:
        caps |= MEDIA_CAP_VOLUME_MUTE
    return caps


def compute_media_caps(
    hass: HomeAssistant,
    state_obj: State | None,
    ma_st: State | None,
    ma_counterpart: str | None,
    vol_target: str,
    *,
    dynamic_queue: bool = False,
) -> int:
    """Compute the 11-bit `active_media.media_caps` capability bitmask for the active speaker."""
    has_ma = bool(ma_counterpart)
    vol_st = hass.states.get(vol_target) if vol_target else None
    if state_obj is None and ma_st is None and not has_ma:
        if vol_st is not None and vol_st.domain in ("number", "input_number"):
            return MEDIA_CAP_VOLUME_SET
        return 0

    sf_spk = _parse_int_features(state_obj)
    sf_ma = _parse_int_features(ma_st)
    if sf_spk is None and sf_ma is None:
        caps = MEDIA_CAP_DEFAULT_TRANSPORT
    else:
        sf = (sf_spk or 0) | (sf_ma or 0)
        caps = 0
        for feat_bit, cap_bit in _FEATURE_CAP_PAIRS:
            if sf & feat_bit:
                caps |= cap_bit

    caps = _apply_volume_entity_caps(caps, vol_st)
    if has_ma:
        caps |= MEDIA_CAP_MUSIC_ASSISTANT | MEDIA_CAP_FAVORITE
        if not dynamic_queue:
            caps |= MEDIA_CAP_SHUFFLE_SET | MEDIA_CAP_REPEAT_SET
    if dynamic_queue:
        caps &= ~(MEDIA_CAP_SHUFFLE_SET | MEDIA_CAP_REPEAT_SET)
    return caps & _CAPS_MASK_U16


def _read_muted_from_targets(
    hass: HomeAssistant,
    vol_target: str,
    attrs: dict[str, Any],
    m_attrs: dict[str, Any],
) -> bool:
    if vol_target:
        vol_st = hass.states.get(vol_target)
        if (
            vol_st is not None
            and vol_st.domain == "media_player"
            and vol_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            and "is_volume_muted" in vol_st.attributes
        ):
            return bool(vol_st.attributes.get("is_volume_muted"))
    if "is_volume_muted" in attrs and attrs.get("is_volume_muted") is not None:
        return bool(attrs.get("is_volume_muted"))
    if "is_volume_muted" in m_attrs and m_attrs.get("is_volume_muted") is not None:
        return bool(m_attrs.get("is_volume_muted"))
    return False


def _build_idle_media_payload(
    coordinator: Any,
    snap: SpeakerMediaSnapshot,
    vol_target: str,
    fallback_spk_name: str,
) -> tuple[str | None, dict[str, Any]]:
    idle_title = coordinator.last_media_title
    idle_artist = coordinator.last_media_artist
    idle_album = coordinator.last_media_album
    idle_dur = (
        round(coordinator.last_media_duration, 1)
        if coordinator.last_media_duration > 0
        else None
    )
    idle_pos = round(coordinator.last_media_position, 1)
    idle_type = coordinator.last_media_type if coordinator.last_media_title else ""
    idle_vol = read_volume_from_target(coordinator.hass, vol_target, {})
    idle_vol_r = round(idle_vol, 2) if idle_vol is not None else None
    idle_vol_pct = (
        round(max(0.0, min(1.0, idle_vol)) * 100.0) if idle_vol is not None else None
    )
    idle_muted = _read_muted_from_targets(coordinator.hass, vol_target, {}, {})
    idle_caps = compute_media_caps(
        coordinator.hass, None, snap.ma_st, snap.ma_counterpart, vol_target
    )
    med_rev, med_payload = coordinator.pack_domain_payload(
        "active_media",
        *pack_active_media_fields(
            "",
            idle_title,
            idle_artist,
            idle_album,
            idle_dur,
            idle_pos,
            idle_vol_pct,
            idle_type,
            "",
            coordinator.active_speaker,
            fallback_spk_name,
            coordinator.last_speaker,
            coordinator.local_speaker,
            bool(snap.is_local_flag),
            False,
            "",
            idle_muted,
            False,
            0,
            idle_caps,
        ),
    )
    res: tuple[str | None, dict[str, Any]] = (
        None,
        {
            "title": idle_title,
            "artist": idle_artist,
            "album": idle_album,
            "duration": idle_dur,
            "position": idle_pos,
            "position_updated_at": None,
            "volume": idle_vol_r,
            "media_type": idle_type,
            "art_url": "",
            "active_speaker": coordinator.active_speaker,
            "speaker_name": fallback_spk_name,
            "last_speaker": coordinator.last_speaker,
            "local_speaker": coordinator.local_speaker,
            "is_local": bool(snap.is_local_flag),
            "shuffle": False,
            "repeat": "",
            "muted": idle_muted,
            "favorite": False,
            "queue_count": 0,
            "media_caps": idle_caps,
            "rev": med_rev,
            "payload": med_payload,
        },
    )
    coordinator.cached_media_payload = (time.monotonic(), res)
    return res


def _apply_transfer_and_idle_fallbacks(
    coordinator: Any, snap: SpeakerMediaSnapshot, now_m: float
) -> bool:
    if coordinator.transfer_hold_spinup_until > 0.0:
        if snap.state in (STATE_PLAYING, STATE_PAUSED):
            coordinator.transfer_hold_spinup_until = 0.0
        elif now_m < coordinator.transfer_hold_spinup_until and snap.state in (
            STATE_IDLE,
            STATE_OFF,
        ):
            snap.state = STATE_PLAYING

    in_transfer_window = bool(now_m < float(coordinator.transfer_hold_until))
    if in_transfer_window:
        cur_track_key = f"{snap.title}|{snap.artist}|{snap.album}" if snap.title else ""
        hold_key = coordinator.transfer_hold_track_key
        if not snap.title and coordinator.transfer_hold_title:
            snap.title = coordinator.transfer_hold_title
            snap.artist = coordinator.transfer_hold_artist or snap.artist
            snap.album = coordinator.transfer_hold_album or snap.album
            snap.duration = coordinator.transfer_hold_duration or snap.duration
            cur_track_key = f"{snap.title}|{snap.artist}|{snap.album}"
        if (
            (not hold_key or cur_track_key == hold_key)
            and snap.position < 1.0
            and coordinator.transfer_hold_position > 1.0
        ):
            snap.position = coordinator.transfer_hold_position
    elif (
        not snap.title
        and snap.state == STATE_IDLE
        and coordinator.last_media_title
        and bool(snap.is_local_flag)
    ):
        snap.title = coordinator.last_media_title
        snap.artist = coordinator.last_media_artist
        snap.album = coordinator.last_media_album
        snap.duration = coordinator.last_media_duration
        snap.position = coordinator.last_media_position
        snap.media_type = coordinator.last_media_type
    return in_transfer_window


def _resolve_artwork_proxy_url(
    coordinator: Any,
    snap: SpeakerMediaSnapshot,
    *,
    in_transfer_window: bool,
) -> str:
    raw_pic = str(
        snap.attrs.get("entity_picture_local")
        or snap.attrs.get("entity_picture")
        or snap.attrs.get("media_image_url")
        or snap.m_attrs.get("entity_picture_local")
        or snap.m_attrs.get("entity_picture")
        or snap.m_attrs.get("media_image_url")
        or ""
    )
    track_key = f"{snap.title}|{snap.artist}|{snap.album}"
    hold_track_key = coordinator.transfer_hold_track_key
    if snap.state == STATE_OFF or not snap.title:
        return ""
    if raw_pic:
        coordinator.last_valid_raw_pic = raw_pic
        coordinator.last_art_track_key = track_key
        proxy_url = str(coordinator.build_proxy_art_url(f"{track_key}|{raw_pic}"))
        coordinator.last_art_proxy_url = proxy_url
        return proxy_url
    if (
        track_key == coordinator.last_art_track_key
        or (in_transfer_window and bool(hold_track_key) and track_key == hold_track_key)
    ) and coordinator.last_art_proxy_url:
        return str(coordinator.last_art_proxy_url)
    coordinator.last_valid_raw_pic = ""
    return ""


def _resolve_queue_item_count(
    hass: HomeAssistant,
    snap: SpeakerMediaSnapshot,
    live_q_cnt: int | None,
) -> int:
    if live_q_cnt is not None:
        return max(0, min(_MAX_QUEUE_U16, int(live_q_cnt)))
    for q_src in (snap.m_attrs, snap.attrs):
        for q_key in ("queue_count", "items"):
            q_val = q_src.get(q_key)
            if isinstance(q_val, int) and not isinstance(q_val, bool):
                return max(0, min(_MAX_QUEUE_U16, q_val))
            if isinstance(q_val, list):
                return max(0, min(_MAX_QUEUE_U16, len(q_val)))
    if snap.ma_counterpart:
        cached_q_counts = hass.data.get(DOMAIN, {}).get("_ma_queue_counts")
        if isinstance(cached_q_counts, dict):
            return max(0, min(_MAX_QUEUE_U16, int(cached_q_counts.get(snap.ma_counterpart, 0))))
    return 0


def _parse_position_updated_at(attrs: dict[str, Any], m_attrs: dict[str, Any]) -> int:
    raw_updated_at = attrs.get("media_position_updated_at") or m_attrs.get(
        "media_position_updated_at"
    )
    if isinstance(raw_updated_at, datetime):
        return int(raw_updated_at.timestamp())
    if raw_updated_at:
        parsed_ua = dt_util.parse_datetime(str(raw_updated_at))
        return int(parsed_ua.timestamp()) if parsed_ua else 0
    return 0


def build_active_media_payload(
    coordinator: Any,
) -> tuple[str | None, dict[str, Any]]:
    """Compute state and Protocol v3 `active_media` payload for one coordinator."""
    now_m = time.monotonic()
    cached: tuple[float, tuple[str | None, dict[str, Any]]] | None = (
        coordinator.cached_media_payload
    )
    if cached is not None and (now_m - cached[0]) < _CACHE_TTL_S:
        return cached[1]

    ma_counterpart = resolve_ma_counterpart_entity(
        coordinator.hass, coordinator.active_speaker
    )
    snap = resolve_speaker_media_snapshot(coordinator, ma_counterpart=ma_counterpart)
    vol_target = coordinator.get_volume_target_entity(coordinator.active_speaker)
    fallback_spk_name = (
        coordinator.device_title
        if snap.is_local_flag
        else (
            coordinator.active_speaker.split(".", 1)[-1].replace("_", " ").title()
            if coordinator.active_speaker
            else ""
        )
    )
    if snap.state_obj is None:
        return _build_idle_media_payload(coordinator, snap, vol_target, fallback_spk_name)

    in_transfer_window = _apply_transfer_and_idle_fallbacks(coordinator, snap, now_m)
    volume = read_volume_from_target(coordinator.hass, vol_target, snap.attrs)
    if volume is None and snap.m_attrs:
        volume = read_volume_from_target(coordinator.hass, vol_target, snap.m_attrs)

    art_url = _resolve_artwork_proxy_url(
        coordinator, snap, in_transfer_window=in_transfer_window
    )
    speaker_name = (
        coordinator.device_title
        if snap.is_local_flag
        else str(snap.attrs.get("friendly_name") or fallback_spk_name)
    )
    pos_updated_at = _parse_position_updated_at(snap.attrs, snap.m_attrs)

    live_shuf, live_rep, live_fav, live_q_cnt, live_q_uri, live_is_dynamic = (
        read_live_ma_queue_state(coordinator.hass, snap.ma_counterpart)
    )
    if "shuffle" in snap.m_attrs and snap.m_attrs.get("shuffle") is not None:
        shuffle_flag = bool(snap.m_attrs.get("shuffle"))
    elif "shuffle" in snap.attrs and snap.attrs.get("shuffle") is not None:
        shuffle_flag = bool(snap.attrs.get("shuffle"))
    else:
        shuffle_flag = bool(live_shuf) if live_shuf is not None else False

    repeat_str = (
        normalize_repeat_mode(snap.m_attrs.get("repeat"))
        or normalize_repeat_mode(snap.attrs.get("repeat"))
        or live_rep
        or "off"
    )
    muted_flag = _read_muted_from_targets(
        coordinator.hass, vol_target, snap.attrs, snap.m_attrs
    )

    active_media_uri = next(
        (
            cand_cid
            for cand_cid in (
                live_q_uri,
                str(snap.m_attrs.get("media_content_id") or "").strip(),
                str(snap.attrs.get("media_content_id") or "").strip(),
                coordinator.last_media_uri.strip(),
            )
            if cand_cid and not is_ephemeral_announcement_uri(cand_cid)
        ),
        "",
    )
    raw_source_fav = resolve_raw_source_favorite(snap.attrs, snap.m_attrs, live_fav)
    favorite_flag = (
        resolve_effective_favorite(
            coordinator, snap.title, snap.artist, active_media_uri, raw_source_fav
        )
        if snap.title
        else False
    )
    queue_count = _resolve_queue_item_count(coordinator.hass, snap, live_q_cnt)
    media_caps = compute_media_caps(
        coordinator.hass,
        snap.state_obj,
        snap.ma_st,
        snap.ma_counterpart,
        vol_target,
        dynamic_queue=live_is_dynamic,
    )

    dur_r = round(snap.duration, 1) if snap.duration > 0 else None
    vol_r = round(volume, 2) if volume is not None else None
    vol_pct = round(max(0.0, min(1.0, volume)) * 100.0) if volume is not None else None
    raw_pos = safe_float(
        snap.attrs.get("media_position") or snap.m_attrs.get("media_position"), 0.0
    )
    media_anchor = (
        snap.state,
        snap.title,
        snap.artist,
        snap.album,
        dur_r,
        round(raw_pos, 1),
        pos_updated_at,
        vol_pct,
        snap.media_type,
        art_url,
        coordinator.active_speaker,
        speaker_name,
        coordinator.last_speaker,
        coordinator.local_speaker,
        snap.is_local_flag,
        shuffle_flag,
        repeat_str,
        muted_flag,
        favorite_flag,
        queue_count,
        media_caps,
    )
    prev_anchor = coordinator.cached_media_anchor
    if prev_anchor is not None and prev_anchor[0] == media_anchor:
        pos_r = prev_anchor[1]
    else:
        pos_r = round(snap.position, 1)
        coordinator.cached_media_anchor = (media_anchor, pos_r)

    med_rev, med_payload = coordinator.pack_domain_payload(
        "active_media",
        *pack_active_media_fields(
            snap.state,
            snap.title,
            snap.artist,
            snap.album,
            dur_r,
            pos_r,
            vol_pct,
            snap.media_type,
            art_url,
            coordinator.active_speaker,
            speaker_name,
            coordinator.last_speaker,
            coordinator.local_speaker,
            bool(snap.is_local_flag),
            shuffle_flag,
            repeat_str,
            muted_flag,
            favorite_flag,
            queue_count,
            media_caps,
        ),
    )
    res: tuple[str | None, dict[str, Any]] = (
        snap.state,
        {
            "title": snap.title,
            "artist": snap.artist,
            "album": snap.album,
            "duration": dur_r,
            "position": pos_r,
            "position_updated_at": pos_updated_at,
            "volume": vol_r,
            "media_type": snap.media_type,
            "art_url": art_url,
            "active_speaker": coordinator.active_speaker,
            "speaker_name": speaker_name,
            "last_speaker": coordinator.last_speaker,
            "local_speaker": coordinator.local_speaker,
            "is_local": bool(snap.is_local_flag),
            "shuffle": shuffle_flag,
            "repeat": repeat_str,
            "muted": muted_flag,
            "favorite": favorite_flag,
            "queue_count": queue_count,
            "media_caps": media_caps,
            "rev": med_rev,
            "payload": med_payload,
        },
    )
    coordinator.cached_media_payload = (time.monotonic(), res)
    return res
