"""Coordinator speaker listeners, active-speaker handoff, volume control, and unified media command dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import inspect
import logging
import time
from typing import Any, Final

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event

from ..const import CONF_DEFAULT_SPEAKER, CONF_MUSIC_AUTO_OPEN, TRANSFER_HOLD_WINDOW_SECONDS
from ..hub_registry import is_media_position_only_tick, peek_domain_data
from .browse import async_lookup_ma_track_uri, extract_item_dict
from .linking import (
    get_ma_mass_client,
    interpolate_speaker_position,
    register_speaker_rebind_callback,
    resolve_ma_counterpart_entity,
    resolve_ma_queue_id_sync,
    safe_float,
    safe_opt_float,
)
from .lyrics import async_fetch_and_push_music_lyrics, build_lyrics_track_key
from .tts_queue import (
    async_execute_ma_queue_transfer,
    async_handle_queue_mutation_command,
    async_play_media_with_ma_fallback as async_play_media_with_ma_fallback,
    async_resume_idle_speaker_queue,
    is_ephemeral_announcement_uri,
    parse_media_uri_type,
)

_LOGGER = logging.getLogger(__name__)
VOLUME_SET_FLAG: Final[int] = 4
VOLUME_MUTE_FLAG: Final[int] = 8
VOLUME_STEP_FLAG: Final[int] = 1024
VOLUME_FEATURE_FLAGS: Final[int] = VOLUME_SET_FLAG | VOLUME_MUTE_FLAG | VOLUME_STEP_FLAG

_DEFAULT_NUMBER_MIDPOINT: Final[float] = 50.0
_DEFAULT_NUMBER_MAX: Final[float] = 100.0
_DEFAULT_STEP_FRACTION: Final[float] = 0.05
_LIBRARY_URI_PREFIX_LEN: Final[int] = 10
_SPINUP_GUARD_S: Final[float] = 2.5
_PLAY_GUARD_S: Final[float] = 2.5
_COLD_RESUME_GUARD_S: Final[float] = 3.5
_UNSET: Final = object()


def read_volume_from_target(
    hass: HomeAssistant, vol_target: str, fallback_attrs: Mapping[str, Any]
) -> float | None:
    """Read normalized `0.0..1.0` volume from `media_player`, `number`, or `input_number`, or `None`."""
    vol_state = hass.states.get(vol_target)
    if vol_state is not None and vol_state.state not in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        if vol_state.domain in ("number", "input_number"):
            val = safe_opt_float(vol_state.state)
            min_v = safe_float(vol_state.attributes.get("min"), 0.0)
            max_v = safe_float(vol_state.attributes.get("max"), _DEFAULT_NUMBER_MAX)
            if val is not None and max_v > min_v:
                return max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))
        else:
            parsed_lvl = safe_opt_float(vol_state.attributes.get("volume_level"))
            if parsed_lvl is not None:
                return max(0.0, min(1.0, parsed_lvl))

    fb_lvl = safe_opt_float(fallback_attrs.get("volume_level"))
    if fb_lvl is not None:
        return max(0.0, min(1.0, fb_lvl))
    return None


def resolve_canonical_volume(
    volume_level: float | None, volume_pct: float | int | None
) -> float | None:
    """Resolve explicit `volume_pct` (`0..100`) or canonical `volume_level` (`0.0..1.0`) without discontinuity."""
    if volume_pct is not None:
        pct = safe_opt_float(volume_pct)
        if pct is None:
            return None
        return max(0.0, min(1.0, pct / 100.0))
    if volume_level is not None:
        lvl = safe_opt_float(volume_level)
        if lvl is None:
            return None
        return max(0.0, min(1.0, lvl))
    return None


def _normalize_volume_action_token(action: str) -> str:
    norm_action = action.strip().lower()
    if norm_action == "volume_up":
        return "up"
    if norm_action == "volume_down":
        return "down"
    if norm_action == "volume_mute":
        return "mute"
    return norm_action


async def _async_execute_number_volume(
    hass: HomeAssistant,
    vol_target: str,
    state_obj: State | None,
    norm_action: str,
    resolved_lvl: float | None,
) -> bool:
    target_domain = state_obj.domain if state_obj else vol_target.split(".", 1)[0]
    cur_val = (
        safe_float(state_obj.state, _DEFAULT_NUMBER_MIDPOINT)
        if (state_obj and state_obj.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN))
        else _DEFAULT_NUMBER_MIDPOINT
    )
    min_v = safe_float(state_obj.attributes.get("min"), 0.0) if state_obj else 0.0
    max_v = (
        safe_float(state_obj.attributes.get("max"), _DEFAULT_NUMBER_MAX)
        if state_obj
        else _DEFAULT_NUMBER_MAX
    )
    native_step = (
        safe_opt_float(state_obj.attributes.get("step")) if state_obj else None
    )
    step = (
        native_step
        if (native_step is not None and native_step > 0)
        else max(1.0, (max_v - min_v) * _DEFAULT_STEP_FRACTION)
    )

    if norm_action == "up":
        new_val = min(max_v, cur_val + step)
    elif norm_action == "down":
        new_val = max(min_v, cur_val - step)
    elif resolved_lvl is not None:
        new_val = min_v + resolved_lvl * (max_v - min_v)
    else:
        return False

    await hass.services.async_call(
        target_domain,
        "set_value",
        {ATTR_ENTITY_ID: vol_target, "value": round(new_val, 2)},
        blocking=False,
    )
    return True


def _parse_volume_feature_flags(state_obj: State | None) -> tuple[bool, bool, bool]:
    raw_sf = state_obj.attributes.get("supported_features") if state_obj else None
    sf: int | None = None
    if raw_sf is not None and not isinstance(raw_sf, bool):
        try:
            sf = int(raw_sf)
        except (ValueError, TypeError):
            sf = None
    if sf is None:
        return True, True, True
    return (
        (sf & VOLUME_SET_FLAG) != 0,
        (sf & VOLUME_MUTE_FLAG) != 0,
        (sf & VOLUME_STEP_FLAG) != 0,
    )


async def _async_execute_media_player_volume(
    hass: HomeAssistant,
    vol_target: str,
    state_obj: State | None,
    norm_action: str,
    resolved_lvl: float | None,
) -> bool:
    can_set, can_mute, can_step = _parse_volume_feature_flags(state_obj)
    supports_vol_set = bool(
        can_set
        and state_obj is not None
        and safe_opt_float(state_obj.attributes.get("volume_level")) is not None
    )
    svc_name = ""
    svc_data: dict[str, Any] = {ATTR_ENTITY_ID: vol_target}
    if norm_action in ("up", "down") and resolved_lvl is not None and supports_vol_set:
        svc_name = "volume_set"
        svc_data["volume_level"] = round(resolved_lvl, 2)
    elif norm_action in ("up", "down"):
        if can_step:
            svc_name = "volume_up" if norm_action == "up" else "volume_down"
    elif norm_action == "mute":
        if can_mute:
            is_muted = bool(state_obj.attributes.get("is_volume_muted", False)) if state_obj else False
            svc_name = "volume_mute"
            svc_data["is_volume_muted"] = not is_muted
    elif resolved_lvl is not None and can_set:
        svc_name = "volume_set"
        svc_data["volume_level"] = round(resolved_lvl, 2)

    if not svc_name:
        return False
    await hass.services.async_call("media_player", svc_name, svc_data, blocking=False)
    return True


async def async_execute_volume_action(
    hass: HomeAssistant,
    vol_target: str,
    action: str,
    volume_level: float | None = None,
    *,
    volume_pct: float | int | None = None,
) -> bool:
    """Execute a volume action (`'set'`, `'up'`, `'down'`, `'mute'`) on `media_player`, `number`, or `input_number`."""
    if not vol_target:
        return False
    state_obj = hass.states.get(vol_target)
    target_domain = state_obj.domain if state_obj else vol_target.split(".", 1)[0]
    norm_action = _normalize_volume_action_token(action)
    resolved_lvl = resolve_canonical_volume(volume_level, volume_pct)

    if target_domain in ("number", "input_number"):
        return await _async_execute_number_volume(
            hass, vol_target, state_obj, norm_action, resolved_lvl
        )
    if target_domain == "media_player":
        return await _async_execute_media_player_volume(
            hass, vol_target, state_obj, norm_action, resolved_lvl
        )
    return False


@dataclass(slots=True)
class SpeakerMediaSnapshot:
    """Resolved live speaker state, Music Assistant counterpart attributes, and active track metadata."""

    state_obj: State | None
    ma_st: State | None
    ma_counterpart: str | None
    state: str
    attrs: dict[str, Any]
    m_attrs: dict[str, Any]
    title: str
    artist: str
    album: str
    duration: float
    position: float
    media_type: str
    is_local_flag: int


def resolve_speaker_media_snapshot(
    coordinator: Any,
    *,
    ma_counterpart: str | object | None = _UNSET,
) -> SpeakerMediaSnapshot:
    """Resolve live speaker state, counterpart attributes, and active track metadata without side effects."""
    hass = coordinator.hass
    active_spk = coordinator.active_speaker
    state_obj = hass.states.get(active_spk)
    resolved_ma = (
        resolve_ma_counterpart_entity(hass, active_spk)
        if ma_counterpart is _UNSET
        else (ma_counterpart if isinstance(ma_counterpart, str) else None)
    )
    ma_st = hass.states.get(resolved_ma) if resolved_ma and resolved_ma != active_spk else None
    if (state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)) and ma_st is not None:
        state_obj = ma_st

    is_local_flag = 1 if coordinator.is_local_speaker_entity(active_spk) else 0
    if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return SpeakerMediaSnapshot(
            None, ma_st, resolved_ma, "", {}, {}, "", "", "", 0.0, 0.0, "", is_local_flag
        )

    state = state_obj.state
    if (
        state in (STATE_IDLE, STATE_OFF)
        and ma_st is not None
        and ma_st.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
    ):
        state = ma_st.state
    if state not in (STATE_PLAYING, STATE_PAUSED, STATE_IDLE, STATE_BUFFERING, STATE_OFF):
        state = STATE_IDLE

    attrs: dict[str, Any] = dict(state_obj.attributes)
    m_attrs: dict[str, Any] = dict(ma_st.attributes) if ma_st is not None else {}
    title = str(attrs.get("media_title") or "")
    artist = str(
        attrs.get("media_artist") or attrs.get("media_series_title") or attrs.get("media_album_artist") or ""
    )
    album = str(attrs.get("media_album_name") or "")
    duration = safe_float(attrs.get("media_duration"), 0.0)
    position = interpolate_speaker_position(state_obj)

    if not title and m_attrs.get("media_title"):
        title = str(m_attrs.get("media_title") or title)
        artist = str(
            m_attrs.get("media_artist")
            or m_attrs.get("media_series_title")
            or m_attrs.get("media_album_artist")
            or artist
        )
        album = str(m_attrs.get("media_album_name") or album)
    if duration <= 0 and m_attrs.get("media_duration"):
        duration = safe_float(m_attrs.get("media_duration"), duration)
    if position <= 0 and ma_st is not None:
        position = interpolate_speaker_position(ma_st) or position

    raw_type = str(attrs.get("media_content_type") or m_attrs.get("media_content_type") or "").lower()
    if not raw_type:
        media_type = ""
    elif "podcast" in raw_type:
        media_type = "podcast"
    elif "audiobook" in raw_type or "book" in raw_type:
        media_type = "audiobook"
    else:
        media_type = "music"

    return SpeakerMediaSnapshot(
        state_obj, ma_st, resolved_ma, state, attrs, m_attrs, title, artist, album, duration, position, media_type, is_local_flag
    )


@callback
def _sync_active_speaker_media_snapshot(coordinator: Any) -> None:
    snap = resolve_speaker_media_snapshot(coordinator)
    if (
        snap.state_obj is None
        or not snap.title
        or snap.state not in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
    ):
        return
    local_cid = str(snap.attrs.get("media_content_id") or "")
    ma_cid = str(snap.m_attrs.get("media_content_id") or "")
    if is_ephemeral_announcement_uri(local_cid):
        return
    for cand in (ma_cid, local_cid):
        if cand and not is_ephemeral_announcement_uri(cand):
            coordinator.last_media_uri = cand
            break
    coordinator.last_media_type = snap.media_type
    coordinator.last_media_title = snap.title
    coordinator.last_media_artist = snap.artist
    coordinator.last_media_album = snap.album
    if snap.duration > 0:
        coordinator.last_media_duration = snap.duration
    if snap.position > 0:
        coordinator.last_media_position = snap.position


_SPEECH_MEDIA_TYPES: Final[frozenset[str]] = frozenset(
    {"podcast", "podcast_episode", "audiobook"}
)


def resolve_default_speaker_entity(coordinator: Any) -> str:
    """Return the Device's configured default speaker, falling back to `local_speaker`."""
    raw = str(coordinator.get_opt(CONF_DEFAULT_SPEAKER) or "").strip()
    return raw or str(coordinator.local_speaker or "").strip()


def is_default_speaker_entity(coordinator: Any, entity_id: str | None) -> bool:
    """Return True when `entity_id` matches the Device's default speaker or its MA counterpart."""
    ent = str(entity_id or "").strip()
    default_spk = resolve_default_speaker_entity(coordinator)
    if not ent or not default_spk:
        return False
    if ent == default_spk:
        return True
    if coordinator.is_local_speaker_entity(default_spk) and coordinator.is_local_speaker_entity(ent):
        return True
    ma_def = resolve_ma_counterpart_entity(coordinator.hass, default_spk)
    if ma_def and ent == ma_def:
        return True
    ma_ent = resolve_ma_counterpart_entity(coordinator.hass, ent)
    return bool(ma_ent and ma_ent == default_spk)


@callback
def _maybe_schedule_proactive_lyrics_push(
    coordinator: Any, prev_lyr_key: str, new_state: State | None
) -> None:
    new_lyr_key = build_lyrics_track_key(
        coordinator.last_media_title, coordinator.last_media_artist
    )
    if not new_lyr_key or coordinator.is_rpc_outbox_unavailable():
        return
    is_lyrics_auto = (
        is_default_speaker_entity(coordinator, coordinator.active_speaker)
        and str(coordinator.get_device_pref(CONF_MUSIC_AUTO_OPEN) or "") == "Lyrics"
        and new_state is not None
        and new_state.state == STATE_PLAYING
        and coordinator.last_media_type not in _SPEECH_MEDIA_TYPES
        and getattr(coordinator, "display_power_state", 0) != 2
        and not bool(coordinator.get_device_pref("bedtime_active"))
    )
    if coordinator.lyrics_watch_active:
        if new_lyr_key in (prev_lyr_key, coordinator.last_pushed_lyrics_key):
            return
    elif is_lyrics_auto:
        if new_lyr_key == coordinator.last_pushed_lyrics_key:
            return
    else:
        return
    coordinator.last_pushed_lyrics_key = new_lyr_key
    coordinator.create_background_task(
        async_fetch_and_push_music_lyrics(
            coordinator.hass, coordinator, req_id=0, search=new_lyr_key
        ),
        f"latter_lyrics_autopush_{coordinator.device_slug}",
    )


@callback
def _maybe_auto_switch_to_default_speaker(
    coordinator: Any,
    default_spk: str,
    old_state: State | None,
    new_state: State | None,
) -> bool:
    if new_state is None or new_state.state != STATE_PLAYING:
        return False
    if old_state is not None and old_state.state == STATE_PLAYING:
        return False
    if str(coordinator.get_device_pref(CONF_MUSIC_AUTO_OPEN) or "") == "Off":
        return False
    if is_ephemeral_announcement_uri(
        str(new_state.attributes.get("media_content_id") or "")
    ):
        return False
    cur_st = coordinator.hass.states.get(coordinator.active_speaker)
    if cur_st is not None and cur_st.state in (STATE_PLAYING, STATE_BUFFERING):
        return False
    _LOGGER.debug(
        "Switching %s active_speaker from idle '%s' to playing default_speaker '%s'",
        coordinator.device_slug,
        coordinator.active_speaker,
        default_spk,
    )
    coordinator.last_speaker = coordinator.active_speaker
    coordinator.active_speaker = default_spk
    coordinator.cached_media_anchor = None
    coordinator.cached_media_payload = None
    bind_coordinator_speaker_listener(coordinator)
    coordinator.schedule_persist_runtime_state()
    _maybe_schedule_proactive_lyrics_push(coordinator, "", new_state)
    coordinator.async_notify_listeners()
    return True


@callback
def bind_coordinator_speaker_listener(coordinator: Any) -> None:
    """Subscribe to state changes on the active `media_player`, its volume/MA counterparts, and the default speaker."""
    coordinator.replace_speaker_state_unsub(None)
    coordinator.tracked_ma_counterpart = None
    if not coordinator.active_speaker:
        return

    tracked = [coordinator.active_speaker]
    vol_target = coordinator.get_volume_target_entity(coordinator.active_speaker)
    if vol_target and vol_target != coordinator.active_speaker:
        tracked.append(vol_target)
    ma_counterpart = resolve_ma_counterpart_entity(coordinator.hass, coordinator.active_speaker)
    coordinator.tracked_ma_counterpart = ma_counterpart
    if ma_counterpart and ma_counterpart not in tracked:
        tracked.append(ma_counterpart)

    default_spk = resolve_default_speaker_entity(coordinator)
    default_watched: set[str] = set()
    if default_spk and not is_default_speaker_entity(coordinator, coordinator.active_speaker):
        if default_spk not in tracked:
            tracked.append(default_spk)
            default_watched.add(default_spk)
        ma_default = resolve_ma_counterpart_entity(coordinator.hass, default_spk)
        if ma_default and ma_default not in tracked:
            tracked.append(ma_default)
            default_watched.add(ma_default)

    _sync_active_speaker_media_snapshot(coordinator)

    @callback
    def _on_speaker_state_change(event: Event[EventStateChangedData]) -> None:
        changed_eid = str(event.data.get("entity_id") or "")
        old_state, new_state = event.data.get("old_state"), event.data.get("new_state")
        if changed_eid in default_watched:
            _maybe_auto_switch_to_default_speaker(coordinator, default_spk, old_state, new_state)
            return

        prev_lyr_key = build_lyrics_track_key(
            coordinator.last_media_title, coordinator.last_media_artist
        )
        coordinator.cached_media_anchor = None
        coordinator.cached_media_payload = None
        _sync_active_speaker_media_snapshot(coordinator)
        _maybe_schedule_proactive_lyrics_push(coordinator, prev_lyr_key, new_state)
        if is_media_position_only_tick(old_state, new_state):
            coordinator.cached_media_payload = None
            coordinator.schedule_debounced_notify()
            return
        coordinator.async_notify_listeners()

    coordinator.replace_speaker_state_unsub(
        async_track_state_change_event(coordinator.hass, tracked, _on_speaker_state_change)
    )


@callback
def enforce_local_speaker_if_remote_idle(coordinator: Any, reason: str) -> None:
    """Reset `active_speaker` to the Device's default speaker on boot/wake unless a non-default speaker is playing."""
    default_spk = resolve_default_speaker_entity(coordinator)
    if not default_spk:
        return
    if is_default_speaker_entity(coordinator, coordinator.active_speaker):
        if (
            coordinator.local_speaker
            and coordinator.is_local_speaker_entity(default_spk)
            and coordinator.active_speaker != coordinator.local_speaker
        ):
            coordinator.active_speaker = coordinator.local_speaker
            bind_coordinator_speaker_listener(coordinator)
            coordinator.schedule_persist_runtime_state()
        return

    remote_state = coordinator.hass.states.get(coordinator.active_speaker)
    if not (remote_state and remote_state.state in (STATE_PLAYING, STATE_BUFFERING)):
        _LOGGER.debug(
            "Resetting active_speaker from idle '%s' (state=%s) to default_speaker '%s' (%s)",
            coordinator.active_speaker,
            remote_state.state if remote_state else "missing",
            default_spk,
            reason,
        )
        coordinator.last_speaker = coordinator.active_speaker
        coordinator.active_speaker = default_spk
        bind_coordinator_speaker_listener(coordinator)
        coordinator.schedule_persist_runtime_state()


@callback
def _populate_transfer_hold_state(
    coordinator: Any,
    prev_speaker: str,
    prev_state: State | None,
    prev_ma_st: State | None,
    handoff_pos: float,
) -> dict[str, Any]:
    p_attrs = dict(prev_ma_st.attributes) if prev_ma_st is not None else {}
    if prev_state is not None:
        for k, v in prev_state.attributes.items():
            if v not in (None, "") or k not in p_attrs:
                p_attrs[k] = v
    prev_is_local = coordinator.is_local_speaker_entity(prev_speaker)
    coordinator.transfer_hold_until = time.monotonic() + TRANSFER_HOLD_WINDOW_SECONDS
    coordinator.transfer_hold_position = handoff_pos or (
        coordinator.last_media_position if prev_is_local else 0.0
    )
    coordinator.transfer_hold_title = str(
        p_attrs.get("media_title") or (coordinator.last_media_title if prev_is_local else "") or ""
    )
    coordinator.transfer_hold_artist = str(
        p_attrs.get("media_artist")
        or p_attrs.get("media_series_title")
        or p_attrs.get("media_album_artist")
        or (coordinator.last_media_artist if prev_is_local else "")
        or ""
    )
    coordinator.transfer_hold_album = str(
        p_attrs.get("media_album_name") or (coordinator.last_media_album if prev_is_local else "") or ""
    )
    coordinator.transfer_hold_duration = safe_float(
        p_attrs.get("media_duration"), coordinator.last_media_duration if prev_is_local else 0.0
    )
    coordinator.transfer_hold_track_key = (
        f"{coordinator.transfer_hold_title}|{coordinator.transfer_hold_artist}|{coordinator.transfer_hold_album}"
        if coordinator.transfer_hold_title
        else ""
    )
    return p_attrs


@callback
def set_coordinator_active_speaker(
    coordinator: Any, speaker_entity_id: str, transfer_queue: bool = True
) -> None:
    """Switch the active target speaker, persist to Store, and optionally transfer active queue."""
    speaker_entity_id = speaker_entity_id.strip()
    if not speaker_entity_id:
        return

    prev_speaker = coordinator.active_speaker
    if speaker_entity_id != prev_speaker:
        prev_state = coordinator.hass.states.get(prev_speaker)
        prev_ma = resolve_ma_counterpart_entity(coordinator.hass, prev_speaker)
        prev_ma_st = coordinator.hass.states.get(prev_ma) if prev_ma and prev_ma != prev_speaker else None
        active_states = (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
        was_playing = bool(
            (prev_state and prev_state.state in (STATE_PLAYING, STATE_BUFFERING))
            or (prev_ma_st and prev_ma_st.state in (STATE_PLAYING, STATE_BUFFERING))
        )
        was_active = bool(
            (prev_state and prev_state.state in active_states)
            or (prev_ma_st and prev_ma_st.state in active_states)
        )
        handoff_src = (
            prev_ma_st
            if prev_ma_st is not None and (prev_state is None or prev_state.attributes.get("media_position") is None)
            else prev_state
        )
        handoff_pos = interpolate_speaker_position(handoff_src)
        coordinator.transfer_hold_spinup_until = (
            time.monotonic() + _SPINUP_GUARD_S if (transfer_queue and was_playing) else 0.0
        )

        if was_active and (prev_state is not None or prev_ma_st is not None):
            p_attrs = _populate_transfer_hold_state(
                coordinator, prev_speaker, prev_state, prev_ma_st, handoff_pos
            )
            if transfer_queue:
                raw_prev_cid = str(p_attrs.get("media_content_id") or "")
                media_cid = str(
                    ("" if is_ephemeral_announcement_uri(raw_prev_cid) else raw_prev_cid)
                    or coordinator.last_media_uri
                    or ""
                )
                media_ctype = str(p_attrs.get("media_content_type") or coordinator.last_media_type or "music")

                async def _do_transfer() -> None:
                    await async_execute_ma_queue_transfer(
                        coordinator.hass,
                        coordinator.local_speaker,
                        prev_speaker,
                        speaker_entity_id,
                        was_playing,
                        handoff_pos,
                        media_cid,
                        media_ctype,
                    )
                    coordinator.async_notify_listeners()

                coordinator.create_background_task(
                    _do_transfer(), f"latter_queue_transfer_{coordinator.device_slug}"
                )

        coordinator.last_speaker = prev_speaker
        coordinator.active_speaker = speaker_entity_id
        coordinator.schedule_persist_runtime_state()

    bind_coordinator_speaker_listener(coordinator)
    coordinator.async_notify_listeners()


def normalize_repeat_mode(val: Any) -> str:
    """Normalize HA / Music Assistant repeat mode to `'off'`, `'all'`, `'one'`, or `''`."""
    if val is None:
        return ""
    if hasattr(val, "value"):
        val = val.value
    if isinstance(val, bool):
        return "all" if val else "off"
    raw = str(val).strip().lower()
    if raw in ("one", "repeat_one", "single"):
        return "one"
    if raw in ("all", "repeat_all"):
        return "all"
    return "off" if raw in ("off", "none", "false", "0") else ""


def read_live_ma_queue_state(
    hass: HomeAssistant, ma_target: str | None
) -> tuple[bool | None, str, bool | None, int | None, str, bool]:
    """Read `(shuffle, repeat, favorite, queue_count, current_uri, is_dynamic)` from `mass.player_queues`."""
    if not ma_target:
        return None, "", None, None, "", False
    mass = get_ma_mass_client(hass)
    pqs = getattr(mass, "player_queues", None) if mass is not None else None
    if pqs is None:
        return None, "", None, None, "", False
    qid = resolve_ma_queue_id_sync(hass, ma_target, mass) or ma_target
    q_obj: Any = None
    try:
        if hasattr(pqs, "get") or isinstance(pqs, dict):
            q_obj = pqs.get(qid)
    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as err:
        _LOGGER.debug("mass.player_queues.get(%s) skipped: %s", qid, err)
    if q_obj is None:
        return None, "", None, None, "", False

    q_dict = extract_item_dict(q_obj) if isinstance(q_obj, dict) else None
    raw_shuf = q_dict.get("shuffle_enabled") if q_dict is not None else getattr(q_obj, "shuffle_enabled", None)
    shuf = bool(raw_shuf) if raw_shuf is not None else None
    raw_rep = q_dict.get("repeat_mode") if q_dict is not None else getattr(q_obj, "repeat_mode", None)
    rep = normalize_repeat_mode(raw_rep)

    raw_items = q_dict.get("items") if q_dict is not None else getattr(q_obj, "items", None)
    q_cnt: int | None = None
    if isinstance(raw_items, int) and not isinstance(raw_items, bool):
        q_cnt = max(0, raw_items)
    elif isinstance(raw_items, list):
        q_cnt = len(raw_items)

    cur_item = q_dict.get("current_item") if q_dict is not None else getattr(q_obj, "current_item", None)
    fav: bool | None = None
    cur_uri = ""
    if cur_item is not None:
        cur_d = extract_item_dict(cur_item)
        m_item = extract_item_dict(cur_d.get("media_item") or {})
        raw_fav = m_item.get("favorite")
        if raw_fav is None:
            raw_fav = cur_d.get("favorite")
        if raw_fav is not None:
            fav = bool(raw_fav)
        cur_uri = str(m_item.get("uri") or cur_d.get("uri") or cur_d.get("media_content_id") or "").strip()
    raw_dyn = q_dict.get("is_dynamic") if q_dict is not None else getattr(q_obj, "is_dynamic", None)
    return shuf, rep, fav, q_cnt, cur_uri, (bool(raw_dyn) if raw_dyn is not None else False)


def resolve_raw_source_favorite(
    attrs: dict[str, Any], m_attrs: dict[str, Any], live_q_fav: bool | None
) -> bool | None:
    """Extract raw `favorite` boolean from MA state/queue attributes, or `None` when unreported."""
    for d in (m_attrs, attrs):
        for key in ("favorite", "media_favorite", "is_favorite"):
            val = d.get(key)
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, str)) and str(val).strip().lower() in ("true", "false", "1", "0"):
                return str(val).strip().lower() in ("true", "1")
    return live_q_fav


def resolve_effective_favorite(
    coordinator: Any,
    title: str,
    artist: str,
    media_uri: str,
    raw_source_fav: bool | None,
) -> bool:
    """Resolve current track `favorite` state, honoring optimistic toggles until source updates."""
    overrides = coordinator.media_favorite_overrides
    keys = [
        k
        for k in (
            media_uri.strip(),
            f"{title.strip().lower()}|{artist.strip().lower()}" if title.strip() else "",
        )
        if k
    ]
    for k in keys:
        if (entry := overrides.get(k)) is not None:
            opt_val, snap_val = entry
            if raw_source_fav is not None and raw_source_fav != snap_val:
                overrides.pop(k, None)
                return bool(raw_source_fav)
            return bool(opt_val)
    return bool(raw_source_fav) if raw_source_fav is not None else False


async def _async_apply_mass_favorite_mutation(
    music_ctrl: Any, item_uri: str, *, target_fav: bool
) -> bool:
    if music_ctrl is None or not item_uri:
        return False
    try:
        if target_fav and hasattr(music_ctrl, "add_item_to_favorites"):
            await music_ctrl.add_item_to_favorites(item_uri)
            return True
        if not target_fav and hasattr(music_ctrl, "remove_item_from_favorites"):
            rem_fn = music_ctrl.remove_item_from_favorites
            mtype = parse_media_uri_type(item_uri) or "track"
            item_id: str | int = ""
            if item_uri.startswith("library://") and "/" in item_uri[_LIBRARY_URI_PREFIX_LEN:]:
                item_id = item_uri.rsplit("/", 1)[-1]
            elif hasattr(music_ctrl, "get_item_by_uri"):
                item_d = extract_item_dict(await music_ctrl.get_item_by_uri(item_uri))
                if item_d.get("item_id") is not None:
                    item_id = item_d["item_id"]
                if item_d.get("media_type"):
                    mtype = str(item_d["media_type"])
            if not item_id and "://" in item_uri:
                item_id = item_uri.rsplit("/", 1)[-1]
            pos_params = [
                p
                for p in inspect.signature(rem_fn).parameters.values()
                if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            ]
            if len(pos_params) == 1:
                await rem_fn(item_uri)
            else:
                await rem_fn(mtype, item_id or item_uri)
            return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("mass.music favorite toggle for '%s' failed: %s", item_uri, err)
    return False


async def _async_execute_favorite_toggle(
    coordinator: Any,
    targets: tuple[str, str | None],
    states: tuple[State | None, State | None],
    explicit_media_id: str | None,
) -> None:
    target_spk, ma_target = targets
    state_obj, ma_state_obj = states
    hass = coordinator.hass
    attrs = dict(state_obj.attributes) if state_obj is not None else {}
    m_attrs = dict(ma_state_obj.attributes) if ma_state_obj is not None else {}
    title = str(
        m_attrs.get("media_title") or attrs.get("media_title") or coordinator.last_media_title or ""
    ).strip()
    artist = str(
        m_attrs.get("media_artist") or attrs.get("media_artist") or coordinator.last_media_artist or ""
    ).strip()

    _shuf, _rep, live_q_fav, _q_cnt, live_q_uri, _is_dyn = read_live_ma_queue_state(hass, ma_target)
    raw_explicit = str(explicit_media_id or "").strip()
    item_uri = raw_explicit if "://" in raw_explicit else ""
    if raw_explicit and not item_uri and not title:
        title = raw_explicit
    if not item_uri:
        item_uri = next(
            (
                cand_uri
                for cand_uri in (
                    live_q_uri,
                    str(m_attrs.get("media_content_id") or "").strip(),
                    str(attrs.get("media_content_id") or "").strip(),
                    coordinator.last_media_uri.strip(),
                )
                if cand_uri and "://" in cand_uri and not is_ephemeral_announcement_uri(cand_uri)
            ),
            "",
        )
    if not item_uri and title:
        item_uri = await async_lookup_ma_track_uri(hass, title, artist)

    raw_source_fav = resolve_raw_source_favorite(attrs, m_attrs, live_q_fav)
    target_fav = not resolve_effective_favorite(coordinator, title, artist, item_uri, raw_source_fav)
    for k in (item_uri, f"{title.lower()}|{artist.lower()}" if title else ""):
        if k:
            coordinator.media_favorite_overrides[k] = (target_fav, raw_source_fav)

    mass = get_ma_mass_client(hass)
    handled = await _async_apply_mass_favorite_mutation(
        getattr(mass, "music", None), item_uri, target_fav=target_fav
    )
    if not handled:
        svc_name = "add_to_favorites" if target_fav else "remove_from_favorites"
        if hass.services.has_service("music_assistant", svc_name):
            svc_payload: dict[str, Any] = {
                ATTR_ENTITY_ID: ma_target or target_spk,
                **({"media_id": item_uri} if item_uri else {}),
            }
            await hass.services.async_call("music_assistant", svc_name, svc_payload, blocking=True)
    coordinator.async_notify_listeners()


async def _async_handle_shuffle_or_repeat_command(
    hass: HomeAssistant,
    cmd: str,
    cmd_target: str,
    ma_target: str | None,
    states: tuple[State | None, State | None],
) -> None:
    state_obj, ma_state_obj = states
    m_attrs = dict(ma_state_obj.attributes) if ma_state_obj is not None else {}
    s_attrs = dict(state_obj.attributes) if state_obj is not None else {}
    live_shuf, live_rep, _, _, _, live_is_dynamic = read_live_ma_queue_state(hass, ma_target)
    if live_is_dynamic:
        _LOGGER.debug("Ignoring %s on %s: MA queue is in dynamic mode", cmd, cmd_target)
        return
    if cmd == "shuffle_toggle":
        if "shuffle" in m_attrs and m_attrs.get("shuffle") is not None:
            cur_shuf = bool(m_attrs.get("shuffle"))
        elif "shuffle" in s_attrs and s_attrs.get("shuffle") is not None:
            cur_shuf = bool(s_attrs.get("shuffle"))
        else:
            cur_shuf = bool(live_shuf) if live_shuf is not None else False
        await hass.services.async_call(
            "media_player", "shuffle_set", {ATTR_ENTITY_ID: cmd_target, "shuffle": not cur_shuf}, blocking=False
        )
        return

    cur_rep = (
        normalize_repeat_mode(m_attrs.get("repeat"))
        or normalize_repeat_mode(s_attrs.get("repeat"))
        or live_rep
        or "off"
    )
    next_rep = {"off": "all", "all": "one", "one": "off"}.get(cur_rep, "all")
    await hass.services.async_call(
        "media_player", "repeat_set", {ATTR_ENTITY_ID: cmd_target, "repeat": next_rep}, blocking=False
    )


async def _async_handle_play_resume_command(
    coordinator: Any,
    targets: tuple[str, str | None, str],
    states: tuple[State | None, State | None, str],
) -> None:
    target_spk, ma_target, cmd_target = targets
    state_obj, ma_state_obj, cur_state = states
    hass = coordinator.hass
    now = time.monotonic()
    if now < coordinator.resuming_guard_until:
        return
    coordinator.resuming_guard_until = now + _PLAY_GUARD_S

    cmd_target_st = hass.states.get(cmd_target)
    has_loaded_media = bool(
        (ma_state_obj and (ma_state_obj.attributes.get("media_content_id") or ma_state_obj.attributes.get("media_title")))
        or (state_obj and (state_obj.attributes.get("media_content_id") or state_obj.attributes.get("media_title")))
    )
    play_failed_empty = bool(
        cmd_target_st is not None and cmd_target_st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    )
    if not play_failed_empty:
        try:
            await hass.services.async_call(
                "media_player", "media_play", {ATTR_ENTITY_ID: cmd_target}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.debug("media_play on %s failed (%s); attempting queue fallback", cmd_target, err)
            play_failed_empty = True

    is_local = coordinator.is_local_speaker_entity(target_spk)
    has_resumable_context = bool(
        coordinator.last_media_uri
        or coordinator.last_media_title
        or (ma_target and hass.services.has_service("music_assistant", "get_queue"))
    )
    if has_resumable_context and (
        play_failed_empty
        or (
            cur_state in (STATE_IDLE, STATE_OFF, "stopped")
            and (not has_loaded_media or (is_local and coordinator.local_needs_cold_resume))
        )
    ):
        coordinator.resuming_guard_until = time.monotonic() + _COLD_RESUME_GUARD_S
        resumed = await async_resume_idle_speaker_queue(
            hass,
            target_spk,
            coordinator.last_media_uri,
            coordinator.last_media_position,
            coordinator.last_media_type,
            last_media_title=coordinator.last_media_title,
            last_media_artist=coordinator.last_media_artist,
            last_media_album=coordinator.last_media_album,
            immediate=play_failed_empty,
            already_tried_ma=bool(ma_target and cmd_target == ma_target),
        )
        if resumed:
            coordinator.local_needs_cold_resume = False
            _sync_active_speaker_media_snapshot(coordinator)
            coordinator.async_notify_listeners()


async def _async_execute_mute_toggle(
    coordinator: Any,
    target_spk: str,
    ma_target: str | None,
    cmd_target: str,
) -> None:
    vol_target = coordinator.get_volume_target_entity(target_spk)
    mute_entity = vol_target or cmd_target
    mute_st = coordinator.hass.states.get(mute_entity)
    if (
        (mute_st is None or mute_st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN))
        and mute_entity == target_spk
        and ma_target
    ):
        mute_entity = ma_target
    await async_execute_volume_action(coordinator.hass, mute_entity, "mute")


async def _async_execute_join_command(
    hass: HomeAssistant,
    cmd_target: str,
    ma_target: str | None,
    group_members: list[str] | str | None,
) -> None:
    raw_members = [group_members] if isinstance(group_members, str) else list(group_members or [])
    resolved_members: list[str] = []
    for item in raw_members:
        cand = str(item or "").strip()
        if not cand.startswith("media_player."):
            continue
        if ma_target:
            cand = resolve_ma_counterpart_entity(hass, cand) or cand
        if cand != cmd_target and cand not in resolved_members:
            resolved_members.append(cand)
    if resolved_members:
        await hass.services.async_call(
            "media_player", "join", {ATTR_ENTITY_ID: cmd_target, "group_members": resolved_members}, blocking=False
        )


async def _async_handle_group_or_transport_tail(
    coordinator: Any,
    cmd: str,
    targets: tuple[str, str | None, str],
    seek_position: float | None,
    group_members: list[str] | str | None,
) -> None:
    target_spk, ma_target, cmd_target = targets
    hass = coordinator.hass
    if cmd == "mute_toggle":
        await _async_execute_mute_toggle(coordinator, target_spk, ma_target, cmd_target)
        return
    simple_services = {
        "pause": "media_pause",
        "next": "media_next_track",
        "next_track": "media_next_track",
        "media_next_track": "media_next_track",
        "previous": "media_previous_track",
        "previous_track": "media_previous_track",
        "media_previous_track": "media_previous_track",
        "stop": "media_stop",
        "unjoin": "unjoin",
    }
    if cmd in ("pause", "stop"):
        coordinator.transfer_hold_spinup_until = 0.0
        coordinator.resuming_guard_until = 0.0
    if svc_name := simple_services.get(cmd):
        await hass.services.async_call("media_player", svc_name, {ATTR_ENTITY_ID: cmd_target}, blocking=False)
    elif cmd == "clear_queue":
        coordinator.transfer_hold_spinup_until = 0.0
        if ma_target and (domain_data := peek_domain_data(hass)) is not None:
            domain_data.ma_queue_counts[ma_target] = 0
        await hass.services.async_call("media_player", "clear_playlist", {ATTR_ENTITY_ID: cmd_target}, blocking=False)
    elif cmd == "seek" and seek_position is not None:
        safe_seek = safe_opt_float(seek_position)
        if safe_seek is not None and safe_seek >= 0.0:
            await hass.services.async_call(
                "media_player", "media_seek", {ATTR_ENTITY_ID: cmd_target, "seek_position": round(safe_seek, 1)}, blocking=False
            )
    elif cmd == "join":
        await _async_execute_join_command(hass, cmd_target, ma_target, group_members)


async def _async_execute_play_slot_command(
    coordinator: Any,
    target_spk: str,
    media_id: str,
    opts: tuple[str | None, str | None, bool],
) -> None:
    media_type, enqueue, radio_mode = opts
    coordinator.local_needs_cold_resume = False
    coordinator.resuming_guard_until = 0.0
    play_payload_id: str | list[str] = media_id
    browsed_uris = coordinator.browsed_album_track_uris
    if (
        not radio_mode
        and (media_type or "").strip().lower() == "track"
        and (enqueue or "replace").strip().lower() == "replace"
        and media_id in browsed_uris
    ):
        remaining = browsed_uris[browsed_uris.index(media_id) :]
        if len(remaining) > 1:
            play_payload_id = remaining
    await async_play_media_with_ma_fallback(
        coordinator.hass,
        target_spk,
        play_payload_id,
        media_type=media_type,
        enqueue=enqueue,
        radio_mode=radio_mode,
    )


async def execute_coordinator_media_command(
    coordinator: Any,
    command: str,
    speaker: str | None = None,
    seek_position: float | None = None,
    media_id: str | None = None,
    media_type: str | None = None,
    enqueue: str | None = None,
    group_members: list[str] | str | None = None,
    *,
    radio_mode: bool = False,
    queue_item_id: str | None = None,
    pos_shift: int | str | None = None,
) -> None:
    """Execute a unified media playback, queue, or player toggle command."""
    hass = coordinator.hass
    target_spk = (speaker or coordinator.active_speaker or coordinator.local_speaker).strip()
    cmd = command.strip().lower()
    if not target_spk and cmd != "lyrics_fetch":
        return

    ma_target = resolve_ma_counterpart_entity(hass, target_spk) if target_spk else None
    cmd_target = ma_target or target_spk
    state_obj = hass.states.get(target_spk) if target_spk else None
    ma_state_obj = hass.states.get(ma_target) if ma_target and ma_target != target_spk else None
    cur_state = state_obj.state if state_obj else STATE_IDLE
    if (
        cur_state in (STATE_IDLE, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)
        and ma_state_obj is not None
        and ma_state_obj.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
    ):
        cur_state = ma_state_obj.state
    if cmd == "toggle":
        cmd = "pause" if cur_state in (STATE_PLAYING, STATE_BUFFERING) else "play"

    if cmd in ("play_media", "play_slot") and media_id:
        await _async_execute_play_slot_command(
            coordinator, target_spk, media_id, (media_type, enqueue, radio_mode)
        )
        return

    handled_q, should_notify_q = await async_handle_queue_mutation_command(
        hass, cmd, ma_target, queue_item_id, pos_shift
    )
    if handled_q:
        if should_notify_q:
            coordinator.async_notify_listeners()
        return

    if cmd in ("shuffle_toggle", "repeat_cycle"):
        await _async_handle_shuffle_or_repeat_command(
            hass, cmd, cmd_target, ma_target, (state_obj, ma_state_obj)
        )
    elif cmd == "favorite_toggle":
        await _async_execute_favorite_toggle(
            coordinator, (target_spk, ma_target), (state_obj, ma_state_obj), media_id
        )
    elif cmd == "lyrics_fetch":
        await async_fetch_and_push_music_lyrics(
            hass, coordinator, req_id=0, speaker=target_spk, search=str(media_id or "").strip()
        )
    elif cmd == "play":
        await _async_handle_play_resume_command(
            coordinator, (target_spk, ma_target, cmd_target), (state_obj, ma_state_obj, cur_state)
        )
    else:
        await _async_handle_group_or_transport_tail(
            coordinator, cmd, (target_spk, ma_target, cmd_target), seek_position, group_members
        )


register_speaker_rebind_callback(bind_coordinator_speaker_listener)
