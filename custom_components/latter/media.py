"""Music Assistant player linking, media playback, Sendspin queue recovery, and active_media v3 builder."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
import inspect
import logging
import math
import re
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ESPHOME_DEVICE_ID,
    CONF_MA_PLAYER_ENTITY,
    DOMAIN,
    SUBENTRY_DEVICE,
    TRANSFER_HOLD_WINDOW_SECONDS,
)
from .hub import get_area_state_index, is_media_position_only_tick, iter_coordinators
from .identity import (
    device_entities,
    esphome_service,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
)
from .media_browse import (
    MAX_LYRIC_LINES,
    _extract_item_dict,
    async_browse_media_items,
    async_fetch_track_lyrics,
    async_lookup_ma_track_uri,
    get_ma_mass_client,
    is_music_assistant_player,
    resolve_ma_queue_id_sync,
)
from .protocol import ha_value
from .repairs import link_ma_player_issue_id

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry
    from homeassistant.helpers.entity_registry import RegistryEntry

    from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

VOLUME_SET_FLAG: int = 4
VOLUME_MUTE_FLAG: int = 8
VOLUME_STEP_FLAG: int = 1024
VOLUME_FEATURE_FLAGS: int = VOLUME_SET_FLAG | VOLUME_MUTE_FLAG | VOLUME_STEP_FLAG

MEDIA_CAP_PAUSE: int = 1
MEDIA_CAP_SEEK: int = 2
MEDIA_CAP_VOLUME_SET: int = 4
MEDIA_CAP_VOLUME_MUTE: int = 8
MEDIA_CAP_PREVIOUS_TRACK: int = 16
MEDIA_CAP_NEXT_TRACK: int = 32
MEDIA_CAP_SHUFFLE_SET: int = 64
MEDIA_CAP_REPEAT_SET: int = 128
MEDIA_CAP_GROUPING: int = 256
MEDIA_CAP_MUSIC_ASSISTANT: int = 512
MEDIA_CAP_FAVORITE: int = 1024
MEDIA_CAP_DEFAULT_TRANSPORT: int = (
    MEDIA_CAP_PAUSE
    | MEDIA_CAP_SEEK
    | MEDIA_CAP_VOLUME_SET
    | MEDIA_CAP_VOLUME_MUTE
    | MEDIA_CAP_PREVIOUS_TRACK
    | MEDIA_CAP_NEXT_TRACK
)

_HA_FEATURE_PAUSE: int = 1
_HA_FEATURE_SEEK: int = 2
_HA_FEATURE_PREVIOUS_TRACK: int = 16
_HA_FEATURE_NEXT_TRACK: int = 32
_HA_FEATURE_SHUFFLE_SET: int = 16384
_HA_FEATURE_REPEAT_SET: int = 262144
_HA_FEATURE_GROUPING: int = 524288

VALID_MA_ENQUEUE_MODES: frozenset[str] = frozenset(
    {"play", "next", "add", "replace", "replace_next"}
)
LYRICS_CHUNK_SIZE: int = 32

_MAC_TOKEN_RE = re.compile(
    r"(?:^|[^0-9a-fA-F])((?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12})(?:$|[^0-9a-fA-F])"
)
_STRICT_MAC_RE = re.compile(
    r"^(?:bridge[-_])?((?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12})$"
)
_MA_RECONNECT_GRACE_SECONDS: float = 45.0
_MA_OFFLINE_CACHE_TTL_SECONDS: float = 5.0

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

__all__ = [
    "MEDIA_CAP_DEFAULT_TRANSPORT",
    "MEDIA_CAP_FAVORITE",
    "MEDIA_CAP_GROUPING",
    "MEDIA_CAP_MUSIC_ASSISTANT",
    "MEDIA_CAP_NEXT_TRACK",
    "MEDIA_CAP_PAUSE",
    "MEDIA_CAP_PREVIOUS_TRACK",
    "MEDIA_CAP_REPEAT_SET",
    "MEDIA_CAP_SEEK",
    "MEDIA_CAP_SHUFFLE_SET",
    "MEDIA_CAP_VOLUME_MUTE",
    "MEDIA_CAP_VOLUME_SET",
    "VOLUME_FEATURE_FLAGS",
    "VOLUME_MUTE_FLAG",
    "VOLUME_SET_FLAG",
    "VOLUME_STEP_FLAG",
    "async_announce_on_targets",
    "async_execute_ma_queue_transfer",
    "async_execute_volume_action",
    "async_fetch_and_push_music_lyrics",
    "async_find_queue_resume_item",
    "async_find_queue_resume_items",
    "async_heal_coordinator_ma_links",
    "async_play_media_with_ma_fallback",
    "async_push_music_lyrics",
    "async_refresh_ma_link",
    "async_resume_idle_speaker_queue",
    "async_set_ma_player_link",
    "bind_coordinator_speaker_listener",
    "build_active_media_payload",
    "clear_ma_counterpart_cache",
    "compute_media_caps",
    "configured_link",
    "discover_ma_player_for_device",
    "enforce_local_speaker_if_remote_idle",
    "execute_coordinator_media_command",
    "interpolate_speaker_position",
    "ma_player_entities",
    "read_volume_from_target",
    "resolve_assist_satellite_entity",
    "resolve_esphome_local_speaker",
    "resolve_ma_counterpart_entity",
    "set_coordinator_active_speaker",
    "suggest_ma_player",
    "suggest_ma_player_for",
]


def configured_link(
    configured: str | None, ma_player_entities_iter: Iterable[str]
) -> str | None:
    """Return the Device's configured Music Assistant player if it is a current MA media_player, else None."""
    target = str(configured or "").strip()
    if not target:
        return None
    return target if target in set(ma_player_entities_iter) else None


def suggest_ma_player(
    device_identity: tuple[str | None, str | None],
    candidates: Iterable[tuple[str, str | None, str | None]],
) -> str | None:
    """Suggest the MA player whose device has the exact same manufacturer AND model (unique match only)."""
    manufacturer, model = device_identity
    if not manufacturer or not model:
        return None
    matches = [
        entity_id
        for entity_id, c_manufacturer, c_model in candidates
        if c_manufacturer == manufacturer and c_model == model
    ]
    return matches[0] if len(matches) == 1 else None


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


def _extract_strict_mac(raw: str | None) -> str | None:
    """Return a normalized MAC when `raw` is a standalone MAC or `bridge-<mac>` protocol ID, else None."""
    if not raw:
        return None
    match = _STRICT_MAC_RE.match(str(raw).strip())
    return dr.format_mac(match.group(1)) if match else None


def _attr_or_key(obj: Any, key: str) -> Any:
    """Read `key` from either a Mapping or a model object attribute."""
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _extract_macs_from_device_or_entry(
    dev: DeviceEntry | None, ent: RegistryEntry | None = None
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


def _lookup_mass_player(mass: Any, player_id: str) -> Any | None:
    """Look up a Music Assistant Player model by `player_id` from `mass.players`."""
    if mass is None or not player_id:
        return None
    players = getattr(mass, "players", None)
    if players is None:
        return None
    if hasattr(players, "get"):
        try:
            found = players.get(player_id)
            if found is not None:
                return found
        except Exception:  # noqa: BLE001
            pass
    if isinstance(players, Iterable) and not isinstance(players, (str, bytes, Mapping)):
        for item in players:
            if str(_attr_or_key(item, "player_id") or "").strip() == player_id:
                return item
    return None


def _collect_sendspin_from_config_entries(
    hass: HomeAssistant, cfg_entries: Iterable[Any]
) -> tuple[set[str], bool]:
    """Return `(sendspin_client_ids, pending_client_id)` from ESPHome ConfigEntry objects."""
    client_ids: set[str] = set()
    pending_pairing = False
    esphome_dom = hass.data.get("esphome")
    ss_domain_map = getattr(esphome_dom, "sendspin_client_ids", None)
    entry_ids: set[str] = set()

    for cfg_entry in cfg_entries:
        if cfg_entry is None or getattr(cfg_entry, "domain", None) != "esphome":
            continue
        cfg_id = str(getattr(cfg_entry, "entry_id", "") or "").strip()
        if not cfg_id or cfg_id in entry_ids:
            continue
        entry_ids.add(cfg_id)
        runtime_data = getattr(cfg_entry, "runtime_data", None)
        dev_caps = getattr(runtime_data, "device_capabilities", None)
        ss_cap = _attr_or_key(dev_caps, "sendspin")
        if ss_cap is not None:
            cid = str(_attr_or_key(ss_cap, "client_id") or "").strip()
            flags = _attr_or_key(ss_cap, "feature_flags")
            if cid:
                client_ids.add(cid)
            elif isinstance(flags, int) and flags > 0:
                pending_pairing = True

    if entry_ids and isinstance(ss_domain_map, Mapping):
        for map_cid, map_entry_id in ss_domain_map.items():
            if map_entry_id in entry_ids and map_cid:
                client_ids.add(str(map_cid).strip())

    if client_ids:
        pending_pairing = False
    return client_ids, pending_pairing


def _extract_esphome_sendspin_info(
    hass: HomeAssistant, dev_ids: Iterable[str]
) -> tuple[set[str], bool]:
    """Return `(sendspin_client_ids, pending_client_id)` from bound ESPHome config entries."""
    dev_reg = dr.async_get(hass)
    seen_entries: set[str] = set()
    cfg_entries: list[Any] = []

    for did in dev_ids:
        d_obj = dev_reg.async_get(did)
        if d_obj is None:
            continue
        cfg_id = getattr(d_obj, "config_entry_id", None) or getattr(
            d_obj, "primary_config_entry", None
        )
        if not cfg_id or cfg_id in seen_entries:
            continue
        seen_entries.add(cfg_id)
        cfg_entry = hass.config_entries.async_get_entry(cfg_id)
        if cfg_entry is not None:
            cfg_entries.append(cfg_entry)

    return _collect_sendspin_from_config_entries(hass, cfg_entries)


def _extract_mass_player_identity(
    hass: HomeAssistant, ent: RegistryEntry | None
) -> tuple[set[str], set[str], set[str]]:
    """Extract `(macs, linked_ha_entities, protocol_ids)` from Music Assistant's runtime `Player` model."""
    if ent is None or not ent.unique_id:
        return set(), set(), set()
    p_obj = _lookup_mass_player(get_ma_mass_client(hass), str(ent.unique_id).strip())
    if p_obj is None:
        return set(), set(), set()

    macs: set[str] = set()
    ha_entities: set[str] = set()
    protocol_ids: set[str] = set()

    provider_str = str(_attr_or_key(p_obj, "provider") or "").strip().lower()
    raw_pid = str(_attr_or_key(p_obj, "player_id") or "").strip()
    if raw_pid and provider_str.startswith("sendspin"):
        protocol_ids.add(raw_pid)
        if strict_mac := _extract_strict_mac(raw_pid):
            macs.add(strict_mac)

    dev_info = _attr_or_key(p_obj, "device_info")
    if dev_info is not None:
        raw_mac = _attr_or_key(dev_info, "mac_address")
        if raw_mac:
            macs.update(_extract_macs_from_string(str(raw_mac)))
        raw_idents = _attr_or_key(dev_info, "identifiers")
        if isinstance(raw_idents, Mapping):
            for id_key, id_val in raw_idents.items():
                key_name = str(getattr(id_key, "value", id_key) or "").strip().lower()
                val_str = str(id_val or "").strip()
                if not val_str:
                    continue
                if "mac" in key_name:
                    macs.update(_extract_macs_from_string(val_str))
                elif "uuid" in key_name:
                    protocol_ids.add(val_str)

    protocols = _attr_or_key(p_obj, "protocols")
    if isinstance(protocols, Iterable) and not isinstance(protocols, (str, bytes, Mapping)):
        for proto in protocols:
            p_id = str(_attr_or_key(proto, "protocol_id") or "").strip()
            p_dom = str(_attr_or_key(proto, "domain") or "").strip().lower()
            if not p_id or p_id == "native":
                continue
            if p_dom == "hass_players" or p_id.startswith("media_player."):
                ha_entities.add(p_id)
            else:
                protocol_ids.add(p_id)
                if strict_mac := _extract_strict_mac(p_id):
                    macs.add(strict_mac)

    out_protocols = _attr_or_key(p_obj, "output_protocols")
    if isinstance(out_protocols, Iterable) and not isinstance(
        out_protocols, (str, bytes, Mapping)
    ):
        for out_p in out_protocols:
            op_id = str(_attr_or_key(out_p, "output_protocol_id") or "").strip()
            op_dom = str(_attr_or_key(out_p, "protocol_domain") or "").strip().lower()
            if op_id and op_id != "native":
                if op_dom == "hass_players" or op_id.startswith("media_player."):
                    ha_entities.add(op_id)
                else:
                    protocol_ids.add(op_id)
                    if strict_mac := _extract_strict_mac(op_id):
                        macs.add(strict_mac)
            derived = str(_attr_or_key(out_p, "derived_from") or "").strip()
            if derived and derived != "native":
                protocol_ids.add(derived)
                if strict_mac := _extract_strict_mac(derived):
                    macs.add(strict_mac)

    return macs, ha_entities, protocol_ids


def _candidate_identity(
    hass: HomeAssistant, c_entry: RegistryEntry, c_dev: DeviceEntry | None
) -> tuple[set[str], set[str], set[str]]:
    """Return `(macs, linked_ha_entities, protocol_ids)` for one MA candidate, retaining observed IDs across reboots."""
    macs = _extract_macs_from_device_or_entry(c_dev, c_entry)
    mass_macs, ha_entities, protocol_ids = _extract_mass_player_identity(hass, c_entry)
    macs.update(mass_macs)
    domain_data = hass.data.setdefault(DOMAIN, {})
    known_macs: dict[str, set[str]] = domain_data.setdefault("_ma_known_macs", {})
    known_protos: dict[str, set[str]] = domain_data.setdefault("_ma_known_protocols", {})
    if macs:
        known_macs[c_entry.entity_id] = set(macs)
    elif c_entry.entity_id in known_macs:
        macs = set(known_macs[c_entry.entity_id])
    if protocol_ids:
        known_protos[c_entry.entity_id] = set(protocol_ids)
    elif c_entry.entity_id in known_protos:
        protocol_ids = set(known_protos[c_entry.entity_id])
    return macs, ha_entities, protocol_ids


def _collect_other_esphome_identities(
    hass: HomeAssistant, exclude_dev_ids: set[str]
) -> tuple[set[str], set[str]]:
    """Return `(macs, sendspin_protocol_ids)` of all ESPHome devices in HA except `exclude_dev_ids`."""
    dev_reg = dr.async_get(hass)
    macs: set[str] = set()
    other_entries: list[Any] = []
    for esp_ce in hass.config_entries.async_entries("esphome"):
        has_other_dev = False
        for d_esp in dr.async_entries_for_config_entry(dev_reg, esp_ce.entry_id):
            if d_esp.id in exclude_dev_ids:
                continue
            has_other_dev = True
            macs.update(_extract_macs_from_device_or_entry(d_esp, None))
        if has_other_dev:
            other_entries.append(esp_ce)
    protos, _ = _collect_sendspin_from_config_entries(hass, other_entries)
    return macs, protos


@callback
def clear_ma_counterpart_cache(hass: HomeAssistant) -> None:
    """Clear the cached speaker -> Music Assistant counterpart mapping and unsubscribe listeners on unload."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return
    for key in (
        "_ma_counterpart_cache",
        "_ma_known_macs",
        "_ma_known_protocols",
        "_ma_reconnect_until",
    ):
        bucket = domain_data.get(key)
        if isinstance(bucket, dict):
            bucket.clear()
    reconnect_timer = domain_data.pop("_ma_reconnect_timer", None)
    if callable(reconnect_timer):
        reconnect_timer()
    unsubs = domain_data.pop("_ma_cache_unsubs", None)
    if isinstance(unsubs, (list, tuple)):
        for unsub in unsubs:
            if callable(unsub):
                unsub()


def _is_entity_live(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Return True when `entity_id` has a live Home Assistant state (not unavailable/unknown)."""
    if not entity_id:
        return False
    st = hass.states.get(entity_id)
    return st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


@callback
def _arm_ma_reconnect_grace(hass: HomeAssistant, entity_id: str) -> None:
    """Hold a 45 s reconnect grace window across ESPHome/Sendspin reboot & OTA transitions to prevent Repair churn."""
    if not entity_id:
        return
    domain_data = hass.data.setdefault(DOMAIN, {})
    reconnect_until: dict[str, float] = domain_data.setdefault("_ma_reconnect_until", {})
    reconnect_until[entity_id] = time.monotonic() + _MA_RECONNECT_GRACE_SECONDS

    prev_timer: Callable[[], None] | None = domain_data.pop("_ma_reconnect_timer", None)
    if callable(prev_timer):
        prev_timer()

    @callback
    def _on_grace_expired(_now: Any) -> None:
        domain_data.pop("_ma_reconnect_timer", None)
        now_mono = time.monotonic()
        expired = [k for k, ts in reconnect_until.items() if ts <= now_mono]
        for k in expired:
            reconnect_until.pop(k, None)
        cache = domain_data.get("_ma_counterpart_cache")
        if isinstance(cache, dict):
            cache.clear()
        async_heal_coordinator_ma_links(hass)

    domain_data["_ma_reconnect_timer"] = async_call_later(
        hass, _MA_RECONNECT_GRACE_SECONDS + 0.5, _on_grace_expired
    )


def _in_ma_reconnect_grace(hass: HomeAssistant, *entity_ids: str) -> bool:
    """Return True if any given speaker/MA entity is inside an active reboot/OTA reconnect grace window."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return False
    reconnect_until = domain_data.get("_ma_reconnect_until")
    if not isinstance(reconnect_until, dict) or not reconnect_until:
        return False
    now_mono = time.monotonic()
    return any(
        bool(eid and now_mono < reconnect_until.get(eid, 0.0)) for eid in entity_ids
    )


@callback
def _ensure_ma_cache_listeners(hass: HomeAssistant) -> None:
    """Subscribe once to registry and availability updates to invalidate the MA cache and heal stale links."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "_ma_cache_unsubs" in domain_data:
        return

    @callback
    def _on_registry_updated(_event: Event) -> None:
        cache = domain_data.get("_ma_counterpart_cache")
        if isinstance(cache, dict):
            cache.clear()

    @callback
    def _on_ma_state_changed(event: Event) -> None:
        entity_id = str(event.data.get("entity_id") or "")
        if not entity_id.startswith("media_player."):
            return
        old_st = event.data.get("old_state")
        new_st = event.data.get("new_state")
        old_live = old_st is not None and old_st.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        )
        new_live = new_st is not None and new_st.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        )
        if old_live == new_live:
            return
        ent = er.async_get(hass).async_get(entity_id)
        if ent is None or ent.platform not in ("music_assistant", "esphome"):
            return
        if ent.platform == "esphome" and old_st is not None and not old_live and new_live:
            _arm_ma_reconnect_grace(hass, entity_id)
        elif ent.platform == "music_assistant":
            if old_live and not new_live:
                _arm_ma_reconnect_grace(hass, entity_id)
            elif new_live:
                reconnect_until = domain_data.get("_ma_reconnect_until")
                if isinstance(reconnect_until, dict):
                    reconnect_until.pop(entity_id, None)
        cache = domain_data.get("_ma_counterpart_cache")
        if isinstance(cache, dict):
            cache.clear()
        async_heal_coordinator_ma_links(hass)

    unsub_ent = hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED, _on_registry_updated
    )
    unsub_dev = hass.bus.async_listen(
        dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_registry_updated
    )
    unsub_state = hass.bus.async_listen(EVENT_STATE_CHANGED, _on_ma_state_changed)
    domain_data["_ma_cache_unsubs"] = (unsub_ent, unsub_dev, unsub_state)


def resolve_esphome_local_speaker(
    hass: HomeAssistant, esphome_device_id: str | None
) -> str:
    """Resolve the on-device media_player entity for the bound ESPHome node, or '' if the device has no speaker."""
    dev = get_bound_esphome_device(hass, esphome_device_id)
    if dev is None:
        return ""
    by_suffix = find_device_entity_by_suffix(
        hass, dev.id, "media_player", ("_music",)
    )
    if by_suffix:
        return by_suffix
    for entry in device_entities(hass, dev.id, domain="media_player"):
        if entry.platform == "esphome":
            return entry.entity_id
    return ""


@callback
def _update_ma_link_issue(
    hass: HomeAssistant, coordinator: Any, speaker_entity_id: str, matched: bool
) -> None:
    """Raise the `link_ma_player` repair when a Latter Device's speaker has no Music Assistant counterpart; clear it otherwise."""
    issue_id = link_ma_player_issue_id(str(getattr(coordinator, "subentry_id", "")))
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
        data={"subentry_id": str(getattr(coordinator, "subentry_id", ""))},
    )


def ma_player_entities(hass: HomeAssistant) -> list[RegistryEntry]:
    """Return the enabled Music Assistant media_player registry entries."""
    ent_reg = er.async_get(hass)
    out: list[RegistryEntry] = []
    for ma_cfg in hass.config_entries.async_entries("music_assistant"):
        for entry in er.async_entries_for_config_entry(ent_reg, ma_cfg.entry_id):
            if (
                entry.domain == "media_player"
                and entry.platform == "music_assistant"
                and not entry.disabled_by
            ):
                out.append(entry)
    return out


def _collect_device_target_identity(
    hass: HomeAssistant,
    *,
    speaker_entity_id: str = "",
    owner_coord: Any = None,
    esphome_device_id: str | None = None,
) -> tuple[set[str], set[str], set[str], set[str], bool, DeviceEntry | None]:
    """Collect `(target_dev_ids, target_macs, target_ha_entities, target_protocol_ids, pending_sendspin, spk_dev)`."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    target_dev_ids: set[str] = set()
    target_macs: set[str] = set()
    target_ha_entities: set[str] = set()
    spk_dev: DeviceEntry | None = None

    spk_entry = ent_reg.async_get(speaker_entity_id) if speaker_entity_id else None
    if speaker_entity_id:
        target_ha_entities.add(speaker_entity_id)
    if spk_entry is not None:
        if spk_entry.device_id:
            target_dev_ids.add(spk_entry.device_id)
        spk_dev = (
            dev_reg.async_get(spk_entry.device_id) if spk_entry.device_id else None
        )
        target_macs.update(_extract_macs_from_device_or_entry(spk_dev, spk_entry))

    if esphome_device_id:
        target_dev_ids.add(str(esphome_device_id))

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
        for d_ent in device_entities(hass, did, domain="media_player"):
            if d_ent.platform == "esphome":
                target_ha_entities.add(d_ent.entity_id)

    target_protocol_ids, pending_sendspin = _extract_esphome_sendspin_info(
        hass, target_dev_ids
    )
    return (
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protocol_ids,
        pending_sendspin,
        spk_dev,
    )


def _match_ma_by_identity(
    candidates: Iterable[
        tuple[RegistryEntry, DeviceEntry | None, set[str], set[str], set[str]]
    ],
    target_dev_ids: set[str],
    target_macs: set[str],
    target_ha_entities: set[str] | None = None,
    target_protocol_ids: set[str] | None = None,
) -> str | None:
    """Match a Music Assistant candidate by exact device_id/via_device_id, linked HA entity, Sendspin protocol_id, or MAC."""
    cand_list = list(candidates)
    if target_dev_ids:
        for c_entry, c_dev, _c_macs, _c_ha_ents, _c_protos in cand_list:
            if c_entry.device_id and (
                c_entry.device_id in target_dev_ids
                or (c_dev is not None and c_dev.via_device_id in target_dev_ids)
            ):
                return c_entry.entity_id
    if target_ha_entities:
        for c_entry, _c_dev, _c_macs, c_ha_ents, _c_protos in cand_list:
            if target_ha_entities & c_ha_ents:
                return c_entry.entity_id
    if target_protocol_ids:
        for c_entry, _c_dev, _c_macs, _c_ha_ents, c_protos in cand_list:
            if target_protocol_ids & c_protos:
                return c_entry.entity_id
    if target_macs:
        for c_entry, _c_dev, c_macs, _c_ha_ents, _c_protos in cand_list:
            if target_macs & c_macs:
                return c_entry.entity_id
    return None


def _build_ma_candidates(
    hass: HomeAssistant,
) -> tuple[
    list[tuple[RegistryEntry, DeviceEntry | None, set[str], set[str], set[str]]],
    list[tuple[RegistryEntry, DeviceEntry | None, set[str], set[str], set[str]]],
]:
    """Partition enabled MA players into `(live_candidates, offline_candidates)` with extracted identity."""
    dev_reg = dr.async_get(hass)
    live_candidates: list[
        tuple[RegistryEntry, DeviceEntry | None, set[str], set[str], set[str]]
    ] = []
    offline_candidates: list[
        tuple[RegistryEntry, DeviceEntry | None, set[str], set[str], set[str]]
    ] = []
    for entry in ma_player_entities(hass):
        c_dev = dev_reg.async_get(entry.device_id) if entry.device_id else None
        c_macs, c_ha_ents, c_protos = _candidate_identity(hass, entry, c_dev)
        row = (entry, c_dev, c_macs, c_ha_ents, c_protos)
        if _is_entity_live(hass, entry.entity_id):
            live_candidates.append(row)
        else:
            offline_candidates.append(row)
    return live_candidates, offline_candidates


def _conflicts_with_target(
    c_macs: set[str],
    c_protos: set[str],
    target_macs: set[str],
    target_protos: set[str],
) -> bool:
    """Return True if a candidate reports MAC or Sendspin protocol IDs that conflict with the target device."""
    return bool(
        (c_macs and target_macs and not (c_macs & target_macs))
        or (c_protos and target_protos and not (c_protos & target_protos))
    )


def _collect_bound_peer_ma_links(
    hass: HomeAssistant,
    exclude_esp_id: str | None,
    all_ma_ids: set[str],
    *,
    exclude_coord: Any = None,
) -> tuple[set[str], set[str]]:
    """Return `(claimed_ma_entities, bound_peer_esp_ids)` across active/sleeping peer Latter Devices."""
    claimed: set[str] = set()
    bound_esp_ids: set[str] = set()
    seen_esp_ids: set[str] = set()

    for c in iter_coordinators(hass):
        if c is exclude_coord:
            continue
        c_esp_id = str(getattr(c, "esphome_device_id", "") or "").strip()
        if exclude_esp_id and c_esp_id == exclude_esp_id:
            continue
        if c_esp_id:
            seen_esp_ids.add(c_esp_id)
        saved_ma = str(c.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip()
        if not saved_ma or saved_ma not in all_ma_ids:
            continue
        c_local_spk = str(getattr(c, "local_speaker", "") or "")
        if _is_entity_live(hass, saved_ma) or not _is_entity_live(hass, c_local_spk):
            claimed.add(saved_ma)
            if c_esp_id:
                bound_esp_ids.add(c_esp_id)

    for entry in hass.config_entries.async_entries(DOMAIN):
        for sub in entry.subentries.values():
            if sub.subentry_type != SUBENTRY_DEVICE:
                continue
            s_esp_id = str(sub.data.get(CONF_ESPHOME_DEVICE_ID) or "").strip()
            if (
                not s_esp_id
                or s_esp_id in seen_esp_ids
                or (exclude_esp_id and s_esp_id == exclude_esp_id)
            ):
                continue
            saved_ma = str(sub.data.get(CONF_MA_PLAYER_ENTITY) or "").strip()
            if not saved_ma or saved_ma not in all_ma_ids:
                continue
            s_local_spk = resolve_esphome_local_speaker(hass, s_esp_id)
            if _is_entity_live(hass, saved_ma) or not _is_entity_live(hass, s_local_spk):
                claimed.add(saved_ma)
                bound_esp_ids.add(s_esp_id)

    return claimed, bound_esp_ids


def _match_unique_model_bijection(
    hass: HomeAssistant,
    esp_dev: DeviceEntry | None,
    target_macs: set[str],
    target_protos: set[str],
    live_candidates: Sequence[
        tuple[RegistryEntry, DeviceEntry | None, set[str], set[str], set[str]]
    ],
    claimed_by_others: set[str],
    bound_peer_esp_ids: set[str],
) -> str | None:
    """Match by 1-to-1 `(manufacturer, model)` when only one unbound ESPHome node of that model remains."""
    if esp_dev is None or not esp_dev.manufacturer or not esp_dev.model:
        return None
    dev_reg = dr.async_get(hass)
    same_model_esp_ids: set[str] = {esp_dev.id}
    for esp_ce in hass.config_entries.async_entries("esphome"):
        for d_esp in dr.async_entries_for_config_entry(dev_reg, esp_ce.entry_id):
            if (
                d_esp.manufacturer == esp_dev.manufacturer
                and d_esp.model == esp_dev.model
            ):
                same_model_esp_ids.add(d_esp.id)
    unbound_same_model = same_model_esp_ids - (bound_peer_esp_ids - {esp_dev.id})
    if len(unbound_same_model) != 1:
        return None
    return suggest_ma_player(
        (esp_dev.manufacturer, esp_dev.model),
        [
            (
                c_entry.entity_id,
                c_dev.manufacturer if c_dev is not None else None,
                c_dev.model if c_dev is not None else None,
            )
            for c_entry, c_dev, c_macs, _c_ha_ents, c_protos in live_candidates
            if c_entry.entity_id not in claimed_by_others
            and not _conflicts_with_target(
                c_macs, c_protos, target_macs, target_protos
            )
        ],
    )


def discover_ma_player_for_device(
    hass: HomeAssistant, esphome_device_id: str | None
) -> str:
    """Auto-discover the Music Assistant player for a bound ESPHome device during onboarding or defaults reset."""
    esp_dev = get_bound_esphome_device(hass, esphome_device_id)
    if esp_dev is None or not hass.config_entries.async_entries("music_assistant"):
        return ""
    local_spk = resolve_esphome_local_speaker(hass, esp_dev.id)
    (
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protos,
        _pending_ss,
        _,
    ) = _collect_device_target_identity(
        hass,
        speaker_entity_id=local_spk,
        esphome_device_id=esp_dev.id,
    )
    live_candidates, offline_candidates = _build_ma_candidates(hass)
    matched = _match_ma_by_identity(
        live_candidates,
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protos,
    )
    if matched:
        return matched
    matched = _match_ma_by_identity(
        offline_candidates,
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protos,
    )
    if matched:
        return matched
    all_ma_ids = {
        row[0].entity_id for row in [*live_candidates, *offline_candidates]
    }
    claimed_by_others, bound_peer_esp_ids = _collect_bound_peer_ma_links(
        hass, esp_dev.id, all_ma_ids
    )
    return (
        _match_unique_model_bijection(
            hass,
            esp_dev,
            target_macs,
            target_protos,
            live_candidates,
            claimed_by_others,
            bound_peer_esp_ids,
        )
        or ""
    )


def suggest_ma_player_for(hass: HomeAssistant, coordinator: Any) -> str | None:
    """Suggest the MA player for one Coordinator by exact identity first, else unique (manufacturer, model)."""
    esp_dev = get_bound_esphome_device(
        hass, getattr(coordinator, "esphome_device_id", None)
    )
    if esp_dev is None:
        return None
    local_spk = str(getattr(coordinator, "local_speaker", "") or "")
    (
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protos,
        _pending_ss,
        _,
    ) = _collect_device_target_identity(
        hass,
        speaker_entity_id=local_spk,
        owner_coord=coordinator,
        esphome_device_id=esp_dev.id,
    )
    live_candidates, offline_candidates = _build_ma_candidates(hass)
    exact_live = _match_ma_by_identity(
        live_candidates,
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protos,
    )
    if exact_live:
        return exact_live
    exact_offline = _match_ma_by_identity(
        offline_candidates,
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protos,
    )
    if exact_offline:
        return exact_offline

    all_ma_ids = {
        row[0].entity_id for row in [*live_candidates, *offline_candidates]
    }
    claimed_by_others, _ = _collect_bound_peer_ma_links(
        hass, esp_dev.id, all_ma_ids, exclude_coord=coordinator
    )
    unclaimed_live = [
        row for row in live_candidates if row[0].entity_id not in claimed_by_others
    ]
    pool = unclaimed_live if unclaimed_live else [*live_candidates, *offline_candidates]
    candidates: list[tuple[str, str | None, str | None]] = [
        (
            c_entry.entity_id,
            c_dev.manufacturer if c_dev is not None else None,
            c_dev.model if c_dev is not None else None,
        )
        for c_entry, c_dev, c_macs, _c_ha_ents, c_protos in pool
        if not _conflicts_with_target(
            c_macs, c_protos, target_macs, target_protos
        )
    ]
    return suggest_ma_player((esp_dev.manufacturer, esp_dev.model), candidates)


@callback
def async_refresh_ma_link(hass: HomeAssistant, coordinator: Any) -> str:
    """Drop cached counterparts, re-resolve this Device's link, and rebind its speaker listener."""
    domain_data = hass.data.get(DOMAIN, {})
    cache = (
        domain_data.get("_ma_counterpart_cache")
        if isinstance(domain_data, dict)
        else None
    )
    if isinstance(cache, dict):
        cache.clear()
    local_spk = str(getattr(coordinator, "local_speaker", "") or "")
    resolved = (
        (resolve_ma_counterpart_entity(hass, local_spk) or "") if local_spk else ""
    )
    if hasattr(coordinator, "_unsub_speaker_state") and getattr(
        coordinator, "active_speaker", None
    ):
        bind_coordinator_speaker_listener(coordinator)
    return resolved


@callback
def async_set_ma_player_link(
    hass: HomeAssistant, coordinator: Any, ma_entity_id: str
) -> None:
    """Save the Device's Music Assistant player link to its subentry and re-resolve."""
    coordinator.update_device_config(
        {**coordinator.device_data, CONF_MA_PLAYER_ENTITY: ma_entity_id}
    )
    async_refresh_ma_link(hass, coordinator)


@callback
def async_heal_coordinator_ma_links(hass: HomeAssistant) -> None:
    """Auto-persist newly discovered Sendspin/MAC-matched MA links and heal stale/cross-linked subentry links."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_healing_ma_links"):
        return
    domain_data["_healing_ma_links"] = True
    try:
        cache = domain_data.get("_ma_counterpart_cache")
        if isinstance(cache, dict):
            cache.clear()
        live_candidates, offline_candidates = _build_ma_candidates(hass)
        all_candidates = [*live_candidates, *offline_candidates]
        cand_ident_by_id = {
            c_entry.entity_id: (c_macs, c_protos)
            for c_entry, _c_dev, c_macs, _c_ha_ents, c_protos in all_candidates
        }
        for coord in list(iter_coordinators(hass)):
            local_spk = str(getattr(coord, "local_speaker", "") or "")
            if not local_spk:
                continue
            (
                target_dev_ids,
                target_macs,
                target_ha_entities,
                target_protos,
                _pending_ss,
                _,
            ) = _collect_device_target_identity(
                hass, speaker_entity_id=local_spk, owner_coord=coord
            )
            exact_ma = _match_ma_by_identity(
                live_candidates,
                target_dev_ids,
                target_macs,
                target_ha_entities,
                target_protos,
            ) or _match_ma_by_identity(
                offline_candidates,
                target_dev_ids,
                target_macs,
                target_ha_entities,
                target_protos,
            )
            resolved_ma = resolve_ma_counterpart_entity(hass, local_spk)
            saved_ma = str(coord.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip()
            saved_macs, saved_protos = (
                cand_ident_by_id.get(saved_ma, (set(), set()))
                if saved_ma
                else (set(), set())
            )
            other_esp_macs, other_esp_protos = (
                _collect_other_esphome_identities(hass, target_dev_ids)
                if (saved_macs and target_macs) or (saved_protos and target_protos)
                else (set(), set())
            )
            saved_cross_linked = bool(
                (
                    saved_macs
                    and target_macs
                    and not (saved_macs & target_macs)
                    and (saved_macs & other_esp_macs)
                )
                or (
                    saved_protos
                    and target_protos
                    and not (saved_protos & target_protos)
                    and (saved_protos & other_esp_protos)
                )
            )
            healed_cfg = False
            if not saved_ma and resolved_ma and (
                resolved_ma == exact_ma or _is_entity_live(hass, resolved_ma)
            ):
                _LOGGER.info(
                    "Auto-linked Music Assistant player for '%s': %s",
                    getattr(coord, "device_slug", local_spk),
                    resolved_ma,
                )
                coord.update_device_config(
                    {**coord.device_data, CONF_MA_PLAYER_ENTITY: resolved_ma},
                    bump_prefs_seq=False,
                )
                healed_cfg = True
            elif (
                resolved_ma
                and saved_ma
                and saved_ma != resolved_ma
                and (
                    _is_entity_live(hass, resolved_ma)
                    or (saved_cross_linked and resolved_ma == exact_ma)
                )
            ):
                _LOGGER.info(
                    "Healed stale Music Assistant player link for '%s': %s -> %s",
                    getattr(coord, "device_slug", local_spk),
                    saved_ma,
                    resolved_ma,
                )
                coord.update_device_config(
                    {**coord.device_data, CONF_MA_PLAYER_ENTITY: resolved_ma},
                    bump_prefs_seq=False,
                )
                healed_cfg = True
            active_spk = str(getattr(coord, "active_speaker", "") or "")
            desired_tracked_ma = (
                resolve_ma_counterpart_entity(hass, active_spk) if active_spk else None
            )
            if (
                active_spk
                and hasattr(coord, "_unsub_speaker_state")
                and getattr(coord, "_tracked_ma_counterpart", None) != desired_tracked_ma
            ):
                bind_coordinator_speaker_listener(coord)
                if hasattr(coord, "async_notify_listeners"):
                    coord.async_notify_listeners()
            elif healed_cfg and hasattr(coord, "async_notify_listeners"):
                coord.async_notify_listeners()
    finally:
        domain_data.pop("_healing_ma_links", None)


def resolve_ma_counterpart_entity(
    hass: HomeAssistant, speaker_entity_id: str
) -> str | None:
    """Find the Music Assistant media_player for a speaker by explicit link, device_id, Sendspin/MAC identity, or unique hardware model."""
    if not speaker_entity_id:
        return None

    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(speaker_entity_id)
    if spk_entry is not None and spk_entry.platform == "music_assistant":
        return speaker_entity_id

    _ensure_ma_cache_listeners(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    cache: dict[str, tuple[str | None, bool, float]] = domain_data.setdefault(
        "_ma_counterpart_cache", {}
    )
    if speaker_entity_id in cache:
        cached_val = cache[speaker_entity_id]
        if isinstance(cached_val, tuple) and len(cached_val) == 3:
            cached_ent, cached_live, cached_at = cached_val
            if cached_live:
                if (
                    cached_ent is not None
                    and ent_reg.async_get(cached_ent) is not None
                    and _is_entity_live(hass, cached_ent)
                ):
                    return cached_ent
            elif (time.monotonic() - cached_at) < _MA_OFFLINE_CACHE_TTL_SECONDS:
                if cached_ent is None:
                    return None
                if ent_reg.async_get(cached_ent) is not None and not _is_entity_live(
                    hass, cached_ent
                ):
                    return cached_ent
        cache.pop(speaker_entity_id, None)

    owner_coord: Any = next(
        (
            coord
            for coord in iter_coordinators(hass)
            if getattr(coord, "local_speaker", None) == speaker_entity_id
        ),
        None,
    )

    (
        target_dev_ids,
        target_macs,
        target_ha_entities,
        target_protos,
        pending_sendspin,
        spk_dev,
    ) = _collect_device_target_identity(
        hass, speaker_entity_id=speaker_entity_id, owner_coord=owner_coord
    )
    live_candidates, offline_candidates = _build_ma_candidates(hass)

    raw_configured = (
        str(owner_coord.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip()
        if owner_coord is not None
        else ""
    )
    other_esp_macs, other_esp_protos = (
        _collect_other_esphome_identities(hass, target_dev_ids)
        if raw_configured and (target_macs or target_protos)
        else (set(), set())
    )

    def _belongs_to_other_esphome(c_macs: set[str], c_protos: set[str]) -> bool:
        return bool(
            (
                c_macs
                and target_macs
                and not (c_macs & target_macs)
                and (c_macs & other_esp_macs)
            )
            or (
                c_protos
                and target_protos
                and not (c_protos & target_protos)
                and (c_protos & other_esp_protos)
            )
        )

    matched_entity: str | None = None

    # Pass 0: live explicit configured link on the Device subentry (guarded against cross-linked ESPHome MAC/Sendspin IDs)
    if raw_configured:
        matched_entity = configured_link(
            raw_configured,
            (
                c_entry.entity_id
                for c_entry, _c_dev, c_macs, _c_ha_ents, c_protos in live_candidates
                if not _belongs_to_other_esphome(c_macs, c_protos)
            ),
        )

    # Pass 1 & 2: live exact device_id/via_device_id, linked HA entity, Sendspin protocol_id, or MAC match
    if matched_entity is None and live_candidates:
        matched_entity = _match_ma_by_identity(
            live_candidates,
            target_dev_ids,
            target_macs,
            target_ha_entities,
            target_protos,
        )

    # Pass 3: live 1-to-1 hardware (manufacturer, model) bijection across unbound ESPHome Devices
    if matched_entity is None and live_candidates:
        esp_dev = (
            get_bound_esphome_device(
                hass, getattr(owner_coord, "esphome_device_id", None)
            )
            if owner_coord is not None
            else (
                spk_dev
                if spk_entry is not None and spk_entry.platform == "esphome"
                else None
            )
        )
        all_ma_ids = {
            row[0].entity_id for row in [*live_candidates, *offline_candidates]
        }
        claimed_by_others, bound_peer_esp_ids = _collect_bound_peer_ma_links(
            hass,
            esp_dev.id if esp_dev is not None else None,
            all_ma_ids,
            exclude_coord=owner_coord,
        )
        matched_entity = _match_unique_model_bijection(
            hass,
            esp_dev,
            target_macs,
            target_protos,
            live_candidates,
            claimed_by_others,
            bound_peer_esp_ids,
        )

    # If ESPHome has reported Sendspin pairing capability (`feature_flags > 0`) while its `client_id`
    # refresh + Music Assistant `HassAutoPairer` handshake is still in flight, arm the reconnect grace window.
    if matched_entity is None and pending_sendspin and speaker_entity_id:
        _arm_ma_reconnect_grace(hass, speaker_entity_id)

    # Offline fallback:
    # 1) Non-conflicting configured links are preserved while sleeping, while MA starts, or during the 45 s
    #    reboot/OTA reconnect grace window, while still catching permanently orphaned ghosts.
    # 2) Exact hardware identity (Sendspin protocol_id / MAC / device_id / hass_players) ALWAYS resolves
    #    its own offline player across firmware flashes, reboots, and sleep without Repair churn.
    in_reconnect_grace = _in_ma_reconnect_grace(hass, speaker_entity_id, raw_configured)
    if matched_entity is None and offline_candidates:
        if raw_configured:
            both_speaker_and_ma_online = _is_entity_live(
                hass, speaker_entity_id
            ) and bool(live_candidates)
            fallback_pool = (
                [
                    row
                    for row in offline_candidates
                    if hass.states.get(row[0].entity_id) is None or in_reconnect_grace
                ]
                if both_speaker_and_ma_online
                else offline_candidates
            )
            matched_entity = configured_link(
                raw_configured,
                (
                    c_entry.entity_id
                    for c_entry, _c_dev, c_macs, _c_ha_ents, c_protos in fallback_pool
                    if not _belongs_to_other_esphome(c_macs, c_protos)
                ),
            )
        if matched_entity is None:
            matched_entity = _match_ma_by_identity(
                offline_candidates,
                target_dev_ids,
                target_macs,
                target_ha_entities,
                target_protos,
            )

    if owner_coord is not None:
        if matched_entity is not None or not hass.config_entries.async_entries(
            "music_assistant"
        ):
            _update_ma_link_issue(hass, owner_coord, speaker_entity_id, True)
        elif not in_reconnect_grace:
            _update_ma_link_issue(hass, owner_coord, speaker_entity_id, False)

    is_live = matched_entity is not None and _is_entity_live(hass, matched_entity)
    cache[speaker_entity_id] = (matched_entity, is_live, time.monotonic())
    return matched_entity


def _parse_media_uri_type(media_id: str) -> str:
    """Extract canonical media_type from a provider://type/id URI without substring guessing."""
    raw = str(media_id or "").strip()
    if "://" not in raw:
        return ""
    scheme, rest = raw.split("://", 1)
    if scheme.lower() in ("http", "https", "rtsp", "rtsps", "media-source"):
        return ""
    type_segment = rest.split("/", 1)[0].strip().lower()
    if type_segment.endswith("s") and type_segment[:-1] in _KNOWN_URI_MEDIA_TYPES:
        type_segment = type_segment[:-1]
    if type_segment == "podcast_episode":
        return "track"
    if type_segment in _KNOWN_URI_MEDIA_TYPES:
        return type_segment
    return ""


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


def read_volume_from_target(
    hass: HomeAssistant, vol_target: str, fallback_attrs: dict[str, Any]
) -> float | None:
    """Read normalized 0.0..1.0 volume from media_player, number, or input_number, or None when unknown."""
    vol_state = hass.states.get(vol_target)
    if vol_state is not None and vol_state.state not in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        if vol_state.domain in ("number", "input_number"):
            try:
                val = float(vol_state.state)
                min_v = float(vol_state.attributes.get("min", 0.0))
                max_v = float(vol_state.attributes.get("max", 100.0))
                if max_v > min_v:
                    return max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))
            except ValueError:
                pass
        else:
            v_lvl = vol_state.attributes.get("volume_level")
            if v_lvl is not None:
                return float(v_lvl)

    if fallback_attrs.get("volume_level") is not None:
        return float(fallback_attrs["volume_level"])
    return None


async def async_execute_volume_action(
    hass: HomeAssistant,
    vol_target: str,
    action: str,
    volume_level: float | None = None,
) -> bool:
    """Execute a volume action ('set', 'up', 'down', 'mute') on a media_player, number, or input_number."""
    if not vol_target:
        return False
    state_obj = hass.states.get(vol_target)
    target_domain = state_obj.domain if state_obj else vol_target.split(".", 1)[0]
    norm_action = action.strip().lower()
    if norm_action == "volume_up":
        norm_action = "up"
    elif norm_action == "volume_down":
        norm_action = "down"
    elif norm_action == "volume_mute":
        norm_action = "mute"

    if target_domain in ("number", "input_number"):
        cur_val = (
            float(state_obj.state)
            if (state_obj and state_obj.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN))
            else 50.0
        )
        min_v = float(state_obj.attributes.get("min", 0.0)) if state_obj else 0.0
        max_v = float(state_obj.attributes.get("max", 100.0)) if state_obj else 100.0
        native_step = state_obj.attributes.get("step") if state_obj else None
        step = float(native_step) if native_step else max(1.0, (max_v - min_v) * 0.05)

        if norm_action == "up":
            new_val = min(max_v, cur_val + step)
        elif norm_action == "down":
            new_val = max(min_v, cur_val - step)
        elif volume_level is not None:
            lvl = volume_level / 100.0 if volume_level > 1.0 else volume_level
            new_val = min_v + max(0.0, min(1.0, lvl)) * (max_v - min_v)
        else:
            return False

        await hass.services.async_call(
            target_domain,
            "set_value",
            {ATTR_ENTITY_ID: vol_target, "value": round(new_val, 2)},
            blocking=False,
        )
        return True

    if target_domain != "media_player":
        return False

    raw_sf = (
        state_obj.attributes.get("supported_features")
        if state_obj is not None
        else None
    )
    sf: int | None = None
    if raw_sf is not None:
        try:
            sf = int(raw_sf)
        except (ValueError, TypeError):
            sf = None
    can_set = (sf & VOLUME_SET_FLAG) != 0 if sf is not None else True
    can_mute = (sf & VOLUME_MUTE_FLAG) != 0 if sf is not None else True
    can_step = (sf & VOLUME_STEP_FLAG) != 0 if sf is not None else True

    supports_vol_set = bool(
        can_set
        and state_obj is not None
        and state_obj.attributes.get("volume_level") is not None
    )
    if norm_action in ("up", "down") and volume_level is not None and supports_vol_set:
        lvl = volume_level / 100.0 if volume_level > 1.0 else volume_level
        lvl = max(0.0, min(1.0, lvl))
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {ATTR_ENTITY_ID: vol_target, "volume_level": round(lvl, 2)},
            blocking=False,
        )
        return True
    if norm_action == "up":
        if not can_step:
            return False
        await hass.services.async_call(
            "media_player", "volume_up", {ATTR_ENTITY_ID: vol_target}, blocking=False
        )
        return True
    if norm_action == "down":
        if not can_step:
            return False
        await hass.services.async_call(
            "media_player", "volume_down", {ATTR_ENTITY_ID: vol_target}, blocking=False
        )
        return True
    if norm_action == "mute":
        if not can_mute:
            return False
        is_muted = (
            bool(state_obj.attributes.get("is_volume_muted", False))
            if state_obj
            else False
        )
        await hass.services.async_call(
            "media_player",
            "volume_mute",
            {ATTR_ENTITY_ID: vol_target, "is_volume_muted": not is_muted},
            blocking=False,
        )
        return True
    if volume_level is not None:
        if not can_set:
            return False
        lvl = volume_level / 100.0 if volume_level > 1.0 else volume_level
        lvl = max(0.0, min(1.0, lvl))
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {ATTR_ENTITY_ID: vol_target, "volume_level": round(lvl, 2)},
            blocking=False,
        )
        return True
    return False


def _is_ephemeral_announcement_uri(uri: str) -> bool:
    """Return True for one-shot TTS, chime, or signed Latter stream URLs that must not overwrite media history."""
    low = str(uri or "").strip().lower()
    if not low:
        return False
    return (
        "/api/tts_proxy/" in low
        or low.startswith("media-source://tts")
        or "/api/latter/" in low
        or "/local/sounds/" in low
    )


def _extract_queue_entry_uri(entry: Any) -> str:
    """Extract canonical media URI from a Music Assistant queue entry dict."""
    if not isinstance(entry, dict):
        return ""
    media_item = entry.get("media_item")
    if isinstance(media_item, dict) and media_item.get("uri"):
        cand = str(media_item["uri"]).strip()
        if not _is_ephemeral_announcement_uri(cand):
            return cand
    cand = str(entry.get("uri") or entry.get("media_content_id") or "").strip()
    return "" if _is_ephemeral_announcement_uri(cand) else cand


def _extract_queue_entry_album_ref(entry: Any) -> str:
    """Extract album URI or album name from a Music Assistant queue entry dict."""
    if not isinstance(entry, dict):
        return ""
    media_item = entry.get("media_item")
    if isinstance(media_item, dict):
        album = media_item.get("album")
        if isinstance(album, dict):
            return str(album.get("uri") or album.get("name") or "").strip()
        if isinstance(album, str) and album.strip():
            return album.strip()
    return str(entry.get("media_album_name") or "").strip()


async def async_find_queue_resume_items(
    hass: HomeAssistant,
    speaker_entity_id: str,
    last_media_uri: str,
    last_media_position: float,
    *,
    last_media_title: str = "",
    last_media_artist: str = "",
    last_media_album: str = "",
) -> tuple[list[str], float]:
    """Query Music Assistant queue or album context to preserve upcoming tracks on cold resume."""
    ma_entity = resolve_ma_counterpart_entity(hass, speaker_entity_id)
    ma_st = hass.states.get(ma_entity) if ma_entity else None
    ma_usable = bool(
        ma_entity
        and (ma_st is None or ma_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN))
    )
    cur_uri = ""
    next_uri = ""
    album_ref = ""
    pos = last_media_position

    if ma_usable and hass.services.has_service("music_assistant", "get_queue"):
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
                    cur_item = (
                        q_data.get("current_item") or q_data.get("next_item") or {}
                    )
                    cur_uri = _extract_queue_entry_uri(cur_item)
                    if q_data.get("current_item") and isinstance(
                        q_data.get("next_item"), dict
                    ):
                        next_uri = _extract_queue_entry_uri(q_data.get("next_item"))
                    album_ref = _extract_queue_entry_album_ref(cur_item)
                    pos = float(
                        q_data.get("elapsed_time") or last_media_position or 0.0
                    )
                    items_cand = q_data.get("items") or q_data.get("queue_items")
                    if isinstance(items_cand, list):
                        list_uris = [
                            u
                            for u in (_extract_queue_entry_uri(x) for x in items_cand)
                            if u
                        ]
                        if len(list_uris) > 1:
                            cur_idx = q_data.get("current_index")
                            if isinstance(cur_idx, int) and 0 <= cur_idx < len(
                                list_uris
                            ):
                                start_idx = cur_idx
                            elif cur_uri and cur_uri in list_uris:
                                start_idx = list_uris.index(cur_uri)
                            else:
                                start_idx = 0
                            return list_uris[start_idx:], pos
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue resume lookup failed: %s", err)

    if not cur_uri and last_media_uri and not _is_ephemeral_announcement_uri(last_media_uri):
        cur_uri = last_media_uri
        pos = last_media_position

    if not cur_uri and last_media_title:
        looked_up_uri = await async_lookup_ma_track_uri(
            hass, last_media_title, last_media_artist
        )
        if looked_up_uri:
            cur_uri = looked_up_uri
            pos = last_media_position

    if not cur_uri:
        return [], last_media_position

    eff_album_ref = album_ref or last_media_album.strip()
    if eff_album_ref and _parse_media_uri_type(cur_uri) in ("", "track"):
        try:
            raw_tracks = await async_browse_media_items(
                hass,
                "album_tracks",
                speaker_entity_id,
                speaker_entity_id,
                speaker_entity_id,
                search=eff_album_ref,
                fallback_title=last_media_title,
                fallback_artist=last_media_artist,
                fallback_album=last_media_album,
            )
            track_slots = [
                s
                for s in (raw_tracks or [])
                if isinstance(s, dict) and s.get("type") == "track" and s.get("id")
            ]
            if len(track_slots) > 1:
                track_uris = [str(s["id"]) for s in track_slots]
                start_idx = -1
                if cur_uri in track_uris:
                    start_idx = track_uris.index(cur_uri)
                else:
                    active_indices = [
                        i for i, s in enumerate(track_slots) if s.get("active")
                    ]
                    if active_indices:
                        start_idx = active_indices[0]
                if start_idx >= 0:
                    return track_uris[start_idx:], pos
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "Album tail expansion on resume for '%s' failed: %s",
                eff_album_ref,
                err,
            )

    if next_uri and next_uri != cur_uri:
        return [cur_uri, next_uri], pos
    return [cur_uri], pos


async def async_find_queue_resume_item(
    hass: HomeAssistant,
    speaker_entity_id: str,
    last_media_uri: str,
    last_media_position: float,
    *,
    last_media_title: str = "",
    last_media_artist: str = "",
    last_media_album: str = "",
) -> tuple[str, float]:
    """Query Music Assistant get_queue for the primary resume URI and position."""
    uris, pos = await async_find_queue_resume_items(
        hass,
        speaker_entity_id,
        last_media_uri,
        last_media_position,
        last_media_title=last_media_title,
        last_media_artist=last_media_artist,
        last_media_album=last_media_album,
    )
    return (uris[0] if uris else ""), pos


async def async_play_media_with_ma_fallback(
    hass: HomeAssistant,
    target_spk: str,
    media_id: str | list[str],
    media_type: str | None = None,
    enqueue: str | None = None,
    radio_mode: bool = False,
) -> None:
    """Play media via Music Assistant (expanding artist/album containers into tracks when needed)."""
    if isinstance(media_id, list):
        cleaned_ids = [str(x).strip() for x in media_id if str(x or "").strip()]
        if not cleaned_ids:
            return
        media_id = cleaned_ids[0] if len(cleaned_ids) == 1 else cleaned_ids

    first_uri = media_id[0] if isinstance(media_id, list) else media_id
    ma_target = resolve_ma_counterpart_entity(hass, target_spk)
    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(target_spk) if target_spk else None
    is_esphome_sendspin = bool(spk_entry and spk_entry.platform == "esphome")

    eff_type = (media_type or "").strip().lower()
    if isinstance(media_id, list):
        eff_type = "track"
    elif not eff_type or eff_type == "music":
        parsed_uri_type = _parse_media_uri_type(first_uri)
        if parsed_uri_type:
            eff_type = parsed_uri_type

    norm_enqueue = (enqueue or "").strip().lower()
    if norm_enqueue and norm_enqueue not in VALID_MA_ENQUEUE_MODES:
        norm_enqueue = ""

    ma_st = hass.states.get(ma_target) if ma_target else None
    ma_usable = bool(
        ma_target
        and (ma_st is None or ma_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN))
    )
    if ma_usable and hass.services.has_service("music_assistant", "play_media"):
        payload: dict[str, Any] = {
            ATTR_ENTITY_ID: ma_target,
            "media_id": media_id,
        }
        if eff_type:
            payload["media_type"] = eff_type
        if norm_enqueue:
            payload["enqueue"] = norm_enqueue
        if radio_mode:
            payload["radio_mode"] = True
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
            if isinstance(media_id, str) and eff_type in ("artist", "album"):
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
                            fb_payload: dict[str, Any] = {
                                ATTR_ENTITY_ID: ma_target,
                                "media_id": track_uris[0] if radio_mode else track_uris,
                                "media_type": "track",
                                "enqueue": norm_enqueue or "replace",
                            }
                            if radio_mode:
                                fb_payload["radio_mode"] = True
                            await hass.services.async_call(
                                "music_assistant",
                                "play_media",
                                fb_payload,
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

    if is_esphome_sendspin:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="ma_counterpart_required",
            translation_placeholders={"speaker": target_spk},
        )

    ha_play_payload: dict[str, Any] = {
        ATTR_ENTITY_ID: target_spk,
        "media_content_id": first_uri,
        "media_content_type": eff_type or "music",
    }
    if norm_enqueue in ("play", "next", "add", "replace"):
        ha_play_payload["enqueue"] = norm_enqueue
    await hass.services.async_call(
        "media_player",
        "play_media",
        ha_play_payload,
        blocking=False,
    )


async def async_push_music_lyrics(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
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

    clean_key = (
        str(track_key or "")[:160]
        .replace("\x1f", " ")
        .replace("\x1e", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )
    capped = list(lines)[:MAX_LYRIC_LINES]
    encoded_rows: list[str] = []
    for row in capped:
        t_ms = int(row.get("t_ms", -1))
        txt = (
            str(row.get("text") or "")[:200]
            .replace("\x1f", " ")
            .replace("\x1e", " ")
            .replace("\r", " ")
            .replace("\n", " ")
            .strip()
        )
        if not txt:
            continue
        encoded_rows.append(f"{t_ms}\x1f{txt}")

    chunk_count = max(1, math.ceil(len(encoded_rows) / LYRICS_CHUNK_SIZE))
    safe_req_id = max(0, int(req_id))
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
        _LOGGER.debug("esphome.%s failed for '%s': %s", esphome_action, coordinator.device_slug, err)
        return False
    return True


async def async_fetch_and_push_music_lyrics(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    *,
    req_id: int = 0,
    speaker: str | None = None,
    search: str = "",
    max_lines: int = MAX_LYRIC_LINES,
) -> tuple[str, bool, list[dict[str, Any]]]:
    """Fetch lyrics (cached in 64-entry LRU) and push them to `latter_set_music_lyrics`."""
    eff_spk = (
        str(speaker or coordinator.active_speaker or coordinator.local_speaker).strip()
    )
    track_key, synced, parsed_lines = await async_fetch_track_lyrics(
        hass,
        eff_spk,
        search,
        fallback_title=coordinator.last_media_title,
        fallback_artist=coordinator.last_media_artist,
        fallback_album=coordinator.last_media_album,
        max_lines=max_lines,
    )
    coordinator._lyrics_watch_active = True
    coordinator._last_pushed_lyrics_key = track_key
    await async_push_music_lyrics(
        hass,
        coordinator,
        req_id=req_id,
        track_key=track_key,
        synced=synced,
        lines=parsed_lines,
    )
    return track_key, synced, parsed_lines


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
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return target

    if target.startswith("media_player."):
        reg_ent = ent_reg.async_get(target)
        if reg_ent and reg_ent.device_id and reg_ent.device_id not in cand_dev_ids:
            cand_dev_ids.append(reg_ent.device_id)
        for val in iter_coordinators(hass):
            local_spk = getattr(val, "local_speaker", None)
            if (
                local_spk == target
                or getattr(val, "active_speaker", None) == target
                or (
                    local_spk
                    and resolve_ma_counterpart_entity(hass, str(local_spk)) == target
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
                if st is not None and st.state not in (
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ):
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
            resolve_assist_satellite_entity(hass, spk) if has_sat_announce else None
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
            _LOGGER.debug(
                "assist_satellite.announce failed on %s, falling back: %s",
                satellites,
                err,
            )
            for spk in speakers:
                if (
                    spk
                    and not spk.startswith("assist_satellite.")
                    and spk not in fallback_speakers
                ):
                    fallback_speakers.append(spk)

    if not fallback_speakers:
        return

    if media_url:
        ma_speakers = [
            s
            for s in fallback_speakers
            if (st := hass.states.get(s)) is not None
            and is_music_assistant_player(hass, st)
        ]
        other_speakers = [s for s in fallback_speakers if s not in ma_speakers]

        if ma_speakers and hass.services.has_service(
            "music_assistant", "play_announcement"
        ):
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
            tts_states = get_area_state_index(hass).states_for_domain("tts")
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


async def async_execute_ma_queue_transfer(
    hass: HomeAssistant,
    local_speaker: str,
    source_speaker: str,
    target_speaker: str,
    was_playing: bool,
    handoff_position: float,
    media_content_id: str,
    media_content_type: str,
) -> None:
    """Execute Music Assistant 2.10.8+ queue transfer, quiesce local Sendspin speaker, and verify position handoff."""
    src_ma = resolve_ma_counterpart_entity(hass, source_speaker)
    tgt_ma = resolve_ma_counterpart_entity(hass, target_speaker)
    local_ma = resolve_ma_counterpart_entity(hass, local_speaker) if local_speaker else None
    cmd_target = tgt_ma or target_speaker
    is_from_local = bool(
        local_speaker
        and (
            source_speaker == local_speaker
            or (local_ma and (source_speaker == local_ma or src_ma == local_ma))
        )
    )

    transferred_via_ma = False
    if (
        src_ma
        and tgt_ma
        and src_ma != tgt_ma
        and hass.services.has_service("music_assistant", "transfer_queue")
    ):
        try:
            await hass.services.async_call(
                "music_assistant",
                "transfer_queue",
                {
                    ATTR_ENTITY_ID: tgt_ma,
                    "source_player": src_ma,
                    "auto_play": bool(was_playing),
                },
                blocking=True,
            )
            transferred_via_ma = True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.transfer_queue failed: %s", err)

    if (
        is_from_local
        and source_speaker != target_speaker
        and target_speaker != local_speaker
        and (not local_ma or tgt_ma != local_ma)
    ):
        try:
            await hass.services.async_call(
                "media_player",
                "media_pause",
                {ATTR_ENTITY_ID: local_speaker},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed quiescing local speaker %s: %s", local_speaker, err)

    if not transferred_via_ma and media_content_id:
        try:
            if not is_from_local:
                await hass.services.async_call(
                    "media_player",
                    "media_pause",
                    {ATTR_ENTITY_ID: src_ma or source_speaker},
                    blocking=False,
                )
            await async_play_media_with_ma_fallback(
                hass,
                target_speaker,
                media_content_id,
                media_type=media_content_type or "music",
                enqueue="replace",
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fallback play_media handoff failed: %s", err)

    try:
        async with asyncio.timeout(4.5):
            await asyncio.sleep(1.2)
            updated_tgt = hass.states.get(cmd_target) or hass.states.get(target_speaker)
            if updated_tgt is None:
                return

            if was_playing and updated_tgt.state in (STATE_PAUSED, STATE_IDLE):
                try:
                    await hass.services.async_call(
                        "media_player",
                        "media_play",
                        {ATTR_ENTITY_ID: cmd_target},
                        blocking=False,
                    )
                except Exception:  # noqa: BLE001
                    pass

            tgt_pos = float(updated_tgt.attributes.get("media_position") or 0.0)
            if handoff_position > 5.0 and abs(tgt_pos - handoff_position) > 4.0:
                try:
                    await hass.services.async_call(
                        "media_player",
                        "media_seek",
                        {
                            ATTR_ENTITY_ID: cmd_target,
                            "seek_position": round(handoff_position, 1),
                        },
                        blocking=False,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Position handoff media_seek failed: %s", err)
    except TimeoutError:
        _LOGGER.debug("Queue transfer handoff timed out for %s", target_speaker)


async def async_resume_idle_speaker_queue(
    hass: HomeAssistant,
    speaker_entity_id: str,
    last_media_uri: str,
    last_media_position: float,
    last_media_type: str,
    *,
    last_media_title: str = "",
    last_media_artist: str = "",
    last_media_album: str = "",
    immediate: bool = False,
    already_tried_ma: bool = False,
) -> bool:
    """Resume playback on an idle speaker when native media_play has no active queue stream."""
    ma_entity = resolve_ma_counterpart_entity(hass, speaker_entity_id)

    def _is_playing_or_buffering() -> bool:
        return any(
            ent_id
            and (st := hass.states.get(ent_id)) is not None
            and st.state in (STATE_PLAYING, STATE_BUFFERING)
            for ent_id in (speaker_entity_id, ma_entity)
        )

    if not immediate:
        for _ in range(10):
            await asyncio.sleep(0.25)
            if _is_playing_or_buffering():
                return True
        if ma_entity and ma_entity != speaker_entity_id and not already_tried_ma:
            try:
                await hass.services.async_call(
                    "media_player",
                    "media_play",
                    {ATTR_ENTITY_ID: ma_entity},
                    blocking=True,
                )
                for _ in range(6):
                    await asyncio.sleep(0.25)
                    if _is_playing_or_buffering():
                        return True
            except Exception:  # noqa: BLE001
                pass

    cur_state = hass.states.get(speaker_entity_id)
    resume_uris, resume_pos = await async_find_queue_resume_items(
        hass,
        speaker_entity_id,
        last_media_uri,
        last_media_position,
        last_media_title=last_media_title,
        last_media_artist=last_media_artist,
        last_media_album=last_media_album,
    )
    if not resume_uris:
        _LOGGER.debug(
            "No resumable queue URI found for idle speaker '%s'", speaker_entity_id
        )
        return False

    play_payload: str | list[str] = (
        resume_uris[0] if len(resume_uris) == 1 else resume_uris
    )
    eff_media_type = "track" if len(resume_uris) > 1 else (last_media_type or "music")
    play_target = ma_entity or speaker_entity_id
    try:
        if hass.services.has_service("music_assistant", "play_media") and (
            ma_entity
            or (is_music_assistant_player(hass, cur_state) if cur_state else False)
        ):
            await async_play_media_with_ma_fallback(
                hass,
                play_target,
                play_payload,
                media_type=eff_media_type,
                enqueue="replace" if len(resume_uris) > 1 else None,
            )
        else:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: play_target,
                    "media_content_id": resume_uris[0],
                    "media_content_type": last_media_type or "music",
                },
                blocking=True,
            )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Post-reboot play_media failed on %s: %s", play_target, err)
        return False

    if resume_pos > 5.0:
        await asyncio.sleep(1.2)
        try:
            await hass.services.async_call(
                "media_player",
                "media_seek",
                {
                    ATTR_ENTITY_ID: play_target,
                    "seek_position": round(resume_pos, 1),
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            pass
    return True


def _resolve_speaker_media_snapshot(
    coordinator: LatterCoordinator,
) -> tuple[
    State | None,
    State | None,
    str | None,
    str,
    dict[str, Any],
    dict[str, Any],
    str,
    str,
    str,
    float,
    float,
    str,
    int,
]:
    """Resolve live speaker state, counterpart attributes, and active track metadata without side effects."""
    hass = coordinator.hass
    state_obj = hass.states.get(coordinator.active_speaker)
    ma_counterpart = resolve_ma_counterpart_entity(hass, coordinator.active_speaker)
    ma_st = (
        hass.states.get(ma_counterpart)
        if ma_counterpart and ma_counterpart != coordinator.active_speaker
        else None
    )
    if (
        state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    ) and ma_st is not None:
        state_obj = ma_st

    is_local_flag = (
        1 if coordinator.is_local_speaker_entity(coordinator.active_speaker) else 0
    )
    if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return (
            None,
            ma_st,
            ma_counterpart,
            "",
            {},
            {},
            "",
            "",
            "",
            0.0,
            0.0,
            "",
            is_local_flag,
        )

    state = state_obj.state
    if (
        state in (STATE_IDLE, STATE_OFF)
        and ma_st is not None
        and ma_st.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
    ):
        state = ma_st.state
    if state not in (
        STATE_PLAYING,
        STATE_PAUSED,
        STATE_IDLE,
        STATE_BUFFERING,
        STATE_OFF,
    ):
        state = STATE_IDLE

    attrs: dict[str, Any] = dict(state_obj.attributes)
    m_attrs: dict[str, Any] = dict(ma_st.attributes) if ma_st is not None else {}

    title = str(attrs.get("media_title") or "")
    artist = str(
        attrs.get("media_artist")
        or attrs.get("media_series_title")
        or attrs.get("media_album_artist")
        or ""
    )
    album = str(attrs.get("media_album_name") or "")
    duration = float(attrs.get("media_duration") or 0.0)
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
        duration = float(m_attrs.get("media_duration") or duration)
    if position <= 0 and ma_st is not None:
        position = interpolate_speaker_position(ma_st) or position

    if not title and bool(is_local_flag):
        t_st = coordinator.device_state("sensor", "_now_playing_title")
        a_st = coordinator.device_state("sensor", "_now_playing_artist")
        al_st = coordinator.device_state("sensor", "_now_playing_album")
        if t_st is not None and ha_value(t_st.state):
            title = str(t_st.state)
            if a_st is not None and ha_value(a_st.state):
                artist = str(a_st.state)
            if al_st is not None and ha_value(al_st.state):
                album = str(al_st.state)

    raw_type = str(
        attrs.get("media_content_type") or m_attrs.get("media_content_type") or ""
    ).lower()
    if not raw_type:
        media_type = ""
    elif "podcast" in raw_type:
        media_type = "podcast"
    elif "audiobook" in raw_type or "book" in raw_type:
        media_type = "audiobook"
    else:
        media_type = "music"

    return (
        state_obj,
        ma_st,
        ma_counterpart,
        state,
        attrs,
        m_attrs,
        title,
        artist,
        album,
        duration,
        position,
        media_type,
        is_local_flag,
    )


@callback
def _sync_active_speaker_media_snapshot(coordinator: LatterCoordinator) -> None:
    """Update persisted last_media_* fields when the active speaker is playing, paused, or buffering."""
    (
        state_obj,
        _ma_st,
        _ma_counterpart,
        state,
        attrs,
        m_attrs,
        title,
        artist,
        album,
        duration,
        position,
        media_type,
        _is_local_flag,
    ) = _resolve_speaker_media_snapshot(coordinator)
    if state_obj is None or not title or state not in (
        STATE_PLAYING,
        STATE_PAUSED,
        STATE_BUFFERING,
    ):
        return
    local_cid = str(attrs.get("media_content_id") or "")
    ma_cid = str(m_attrs.get("media_content_id") or "")
    if _is_ephemeral_announcement_uri(local_cid):
        return
    cid = ""
    for cand in (ma_cid, local_cid):
        if cand and not _is_ephemeral_announcement_uri(cand):
            cid = cand
            break
    if cid:
        coordinator.last_media_uri = cid
    coordinator.last_media_type = media_type
    coordinator.last_media_title = title
    coordinator.last_media_artist = artist
    coordinator.last_media_album = album
    if duration > 0:
        coordinator.last_media_duration = duration
    if position > 0:
        coordinator.last_media_position = position


@callback
def bind_coordinator_speaker_listener(coordinator: LatterCoordinator) -> None:
    """Subscribe to state changes on the active media_player (and its volume override entity)."""
    if coordinator._unsub_speaker_state is not None:
        coordinator._unsub_speaker_state()
        coordinator._unsub_speaker_state = None
    coordinator._tracked_ma_counterpart = None

    if not coordinator.active_speaker:
        return

    tracked = [coordinator.active_speaker]
    vol_target = coordinator.get_volume_target_entity(coordinator.active_speaker)
    if vol_target and vol_target != coordinator.active_speaker:
        tracked.append(vol_target)
    ma_counterpart = resolve_ma_counterpart_entity(
        coordinator.hass, coordinator.active_speaker
    )
    coordinator._tracked_ma_counterpart = ma_counterpart
    if ma_counterpart and ma_counterpart not in tracked:
        tracked.append(ma_counterpart)
    if coordinator.is_local_speaker_entity(coordinator.active_speaker):
        np_title = coordinator.device_entity("sensor", "_now_playing_title")
        if np_title and np_title not in tracked:
            tracked.append(np_title)

    _sync_active_speaker_media_snapshot(coordinator)

    @callback
    def _on_speaker_state_change(event: Event[EventStateChangedData]) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        prev_lyr_key = (
            f"{coordinator.last_media_title}|{coordinator.last_media_artist}"
            if coordinator.last_media_title
            else ""
        )
        coordinator._cached_media_anchor = None
        coordinator._cached_media_payload = None
        _sync_active_speaker_media_snapshot(coordinator)
        new_lyr_key = (
            f"{coordinator.last_media_title}|{coordinator.last_media_artist}"
            if coordinator.last_media_title
            else ""
        )
        if (
            getattr(coordinator, "_lyrics_watch_active", False)
            and new_lyr_key
            and new_lyr_key != prev_lyr_key
            and new_lyr_key != getattr(coordinator, "_last_pushed_lyrics_key", "")
            and not coordinator._rpc_receiver.is_device_unavailable()
        ):
            coordinator._last_pushed_lyrics_key = new_lyr_key
            coordinator.entry.async_create_background_task(
                coordinator.hass,
                async_fetch_and_push_music_lyrics(
                    coordinator.hass,
                    coordinator,
                    req_id=0,
                    search=new_lyr_key,
                ),
                f"latter_lyrics_autopush_{coordinator.device_slug}",
            )
        if is_media_position_only_tick(old_state, new_state):
            coordinator._cached_media_payload = None
            coordinator._notify_debouncer.async_schedule_call()
            return
        coordinator.async_notify_listeners()

    coordinator._unsub_speaker_state = async_track_state_change_event(
        coordinator.hass,
        tracked,
        _on_speaker_state_change,
    )


@callback
def enforce_local_speaker_if_remote_idle(
    coordinator: LatterCoordinator, reason: str
) -> None:
    """Reset active_speaker to local_speaker on boot/wake unless the remote speaker is actively playing."""
    local_spk = coordinator.local_speaker
    if not local_spk:
        return
    if coordinator.is_local_speaker_entity(coordinator.active_speaker):
        if coordinator.active_speaker != local_spk:
            coordinator.active_speaker = local_spk
            bind_coordinator_speaker_listener(coordinator)
            coordinator._schedule_persist_runtime_state()
        return

    remote_state = coordinator.hass.states.get(coordinator.active_speaker)
    is_remote_playing = bool(
        remote_state and remote_state.state in (STATE_PLAYING, STATE_BUFFERING)
    )
    if not is_remote_playing:
        _LOGGER.info(
            "Resetting active_speaker from idle remote '%s' (state=%s) to local_speaker '%s' (%s)",
            coordinator.active_speaker,
            remote_state.state if remote_state else "missing",
            local_spk,
            reason,
        )
        coordinator.last_speaker = coordinator.active_speaker
        coordinator.active_speaker = local_spk
        bind_coordinator_speaker_listener(coordinator)
        coordinator._schedule_persist_runtime_state()


@callback
def set_coordinator_active_speaker(
    coordinator: LatterCoordinator, speaker_entity_id: str, transfer_queue: bool = True
) -> None:
    """Switch the active target speaker, persist to Store, and optionally transfer active queue."""
    speaker_entity_id = speaker_entity_id.strip()
    if not speaker_entity_id:
        return

    prev_speaker = coordinator.active_speaker
    if speaker_entity_id != prev_speaker:
        prev_state = coordinator.hass.states.get(prev_speaker)
        prev_ma = resolve_ma_counterpart_entity(coordinator.hass, prev_speaker)
        prev_ma_st = (
            coordinator.hass.states.get(prev_ma)
            if prev_ma and prev_ma != prev_speaker
            else None
        )
        was_playing = bool(
            (prev_state and prev_state.state in (STATE_PLAYING, STATE_BUFFERING))
            or (prev_ma_st and prev_ma_st.state in (STATE_PLAYING, STATE_BUFFERING))
        )
        was_active = bool(
            (
                prev_state
                and prev_state.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
            )
            or (
                prev_ma_st
                and prev_ma_st.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
            )
        )
        handoff_src = (
            prev_ma_st
            if (
                prev_ma_st is not None
                and (
                    prev_state is None
                    or prev_state.attributes.get("media_position") is None
                )
            )
            else prev_state
        )
        handoff_pos = interpolate_speaker_position(handoff_src)
        coordinator._transfer_hold_spinup_until = (
            time.monotonic() + 2.5 if (transfer_queue and was_playing) else 0.0
        )

        if was_active and (prev_state is not None or prev_ma_st is not None):
            p_attrs = dict(prev_ma_st.attributes) if prev_ma_st is not None else {}
            if prev_state is not None:
                for k, v in prev_state.attributes.items():
                    if v not in (None, "") or k not in p_attrs:
                        p_attrs[k] = v
            prev_is_local = coordinator.is_local_speaker_entity(prev_speaker)
            coordinator._transfer_hold_until = (
                time.monotonic() + TRANSFER_HOLD_WINDOW_SECONDS
            )
            coordinator._transfer_hold_position = handoff_pos or (
                coordinator.last_media_position if prev_is_local else 0.0
            )
            coordinator._transfer_hold_title = str(
                p_attrs.get("media_title")
                or (coordinator.last_media_title if prev_is_local else "")
                or ""
            )
            coordinator._transfer_hold_artist = str(
                p_attrs.get("media_artist")
                or p_attrs.get("media_series_title")
                or p_attrs.get("media_album_artist")
                or (coordinator.last_media_artist if prev_is_local else "")
                or ""
            )
            coordinator._transfer_hold_album = str(
                p_attrs.get("media_album_name")
                or (coordinator.last_media_album if prev_is_local else "")
                or ""
            )
            coordinator._transfer_hold_duration = float(
                p_attrs.get("media_duration")
                or (coordinator.last_media_duration if prev_is_local else 0.0)
                or 0.0
            )

            if transfer_queue:
                raw_prev_cid = str(p_attrs.get("media_content_id") or "")
                media_cid = str(
                    (
                        ""
                        if _is_ephemeral_announcement_uri(raw_prev_cid)
                        else raw_prev_cid
                    )
                    or coordinator.last_media_uri
                    or ""
                )
                media_ctype = str(
                    p_attrs.get("media_content_type")
                    or coordinator.last_media_type
                    or "music"
                )

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

                coordinator.entry.async_create_background_task(
                    coordinator.hass,
                    _do_transfer(),
                    f"latter_queue_transfer_{coordinator.device_slug}",
                )

        coordinator.last_speaker = prev_speaker
        coordinator.active_speaker = speaker_entity_id
        coordinator._schedule_persist_runtime_state()

    bind_coordinator_speaker_listener(coordinator)
    coordinator.async_notify_listeners()


def _normalize_repeat_mode(val: Any) -> str:
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
    if raw in ("off", "none", "false", "0"):
        return "off"
    return ""


def _parse_int_features(state_obj: State | None) -> int | None:
    """Parse `supported_features` integer from a Home Assistant State, or None if absent."""
    if state_obj is None:
        return None
    raw = state_obj.attributes.get("supported_features")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


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
        if sf & _HA_FEATURE_PAUSE:
            caps |= MEDIA_CAP_PAUSE
        if sf & _HA_FEATURE_SEEK:
            caps |= MEDIA_CAP_SEEK
        if sf & VOLUME_SET_FLAG:
            caps |= MEDIA_CAP_VOLUME_SET
        if sf & VOLUME_MUTE_FLAG:
            caps |= MEDIA_CAP_VOLUME_MUTE
        if sf & _HA_FEATURE_PREVIOUS_TRACK:
            caps |= MEDIA_CAP_PREVIOUS_TRACK
        if sf & _HA_FEATURE_NEXT_TRACK:
            caps |= MEDIA_CAP_NEXT_TRACK
        if sf & _HA_FEATURE_SHUFFLE_SET:
            caps |= MEDIA_CAP_SHUFFLE_SET
        if sf & _HA_FEATURE_REPEAT_SET:
            caps |= MEDIA_CAP_REPEAT_SET
        if sf & _HA_FEATURE_GROUPING:
            caps |= MEDIA_CAP_GROUPING

    if vol_st is not None and vol_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        if vol_st.domain in ("number", "input_number"):
            caps |= MEDIA_CAP_VOLUME_SET
        elif vol_st.domain == "media_player":
            sf_vol = _parse_int_features(vol_st)
            if sf_vol is None:
                caps |= MEDIA_CAP_VOLUME_SET | MEDIA_CAP_VOLUME_MUTE
            else:
                if sf_vol & VOLUME_SET_FLAG:
                    caps |= MEDIA_CAP_VOLUME_SET
                if sf_vol & VOLUME_MUTE_FLAG:
                    caps |= MEDIA_CAP_VOLUME_MUTE

    if has_ma:
        caps |= MEDIA_CAP_MUSIC_ASSISTANT | MEDIA_CAP_FAVORITE
        if not dynamic_queue:
            caps |= MEDIA_CAP_SHUFFLE_SET | MEDIA_CAP_REPEAT_SET
    if dynamic_queue:
        caps &= ~(MEDIA_CAP_SHUFFLE_SET | MEDIA_CAP_REPEAT_SET)
    return caps & 0xFFFF


def _read_muted_from_targets(
    hass: HomeAssistant,
    vol_target: str,
    attrs: dict[str, Any],
    m_attrs: dict[str, Any],
) -> bool:
    """Read `is_volume_muted` from the volume target entity first, falling back to speaker/MA attributes."""
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


def _read_live_ma_queue_state(
    hass: HomeAssistant, ma_target: str | None
) -> tuple[bool | None, str, bool | None, int | None, str, bool]:
    """Read `(shuffle, repeat, favorite, queue_count, current_uri, is_dynamic)` from in-memory `mass.player_queues`."""
    if not ma_target:
        return None, "", None, None, "", False
    mass = get_ma_mass_client(hass)
    if mass is None or not hasattr(mass, "player_queues"):
        return None, "", None, None, "", False
    qid = resolve_ma_queue_id_sync(hass, ma_target, mass) or ma_target
    pqs = mass.player_queues
    q_obj: Any = None
    try:
        if hasattr(pqs, "get") or isinstance(pqs, dict):
            q_obj = pqs.get(qid)
    except Exception:  # noqa: BLE001
        q_obj = None
    if q_obj is None:
        return None, "", None, None, "", False

    q_dict = _extract_item_dict(q_obj) if isinstance(q_obj, dict) else None
    raw_shuf = (
        q_dict.get("shuffle_enabled")
        if q_dict is not None
        else getattr(q_obj, "shuffle_enabled", None)
    )
    shuf = bool(raw_shuf) if raw_shuf is not None else None

    raw_rep = (
        q_dict.get("repeat_mode")
        if q_dict is not None
        else getattr(q_obj, "repeat_mode", None)
    )
    rep = _normalize_repeat_mode(raw_rep)

    raw_items = (
        q_dict.get("items")
        if q_dict is not None
        else getattr(q_obj, "items", None)
    )
    q_cnt: int | None = None
    if isinstance(raw_items, int) and not isinstance(raw_items, bool):
        q_cnt = max(0, raw_items)
    elif isinstance(raw_items, list):
        q_cnt = len(raw_items)

    cur_item = (
        q_dict.get("current_item")
        if q_dict is not None
        else getattr(q_obj, "current_item", None)
    )
    fav: bool | None = None
    cur_uri = ""
    if cur_item is not None:
        cur_d = _extract_item_dict(cur_item)
        m_item = _extract_item_dict(cur_d.get("media_item") or {})
        raw_fav = m_item.get("favorite")
        if raw_fav is None:
            raw_fav = cur_d.get("favorite")
        if raw_fav is not None:
            fav = bool(raw_fav)
        cur_uri = str(
            m_item.get("uri")
            or cur_d.get("uri")
            or cur_d.get("media_content_id")
            or ""
        ).strip()
    raw_dyn = (
        q_dict.get("is_dynamic")
        if q_dict is not None
        else getattr(q_obj, "is_dynamic", None)
    )
    is_dynamic = bool(raw_dyn) if raw_dyn is not None else False
    return shuf, rep, fav, q_cnt, cur_uri, is_dynamic


def _resolve_raw_source_favorite(
    attrs: dict[str, Any],
    m_attrs: dict[str, Any],
    live_q_fav: bool | None,
) -> bool | None:
    """Extract raw `favorite` boolean from MA state/queue attributes, or None when unreported."""
    for d in (m_attrs, attrs):
        for key in ("favorite", "media_favorite", "is_favorite"):
            val = d.get(key)
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, str)) and str(val).strip().lower() in (
                "true",
                "false",
                "1",
                "0",
            ):
                return str(val).strip().lower() in ("true", "1")
    return live_q_fav


def _resolve_effective_favorite(
    coordinator: LatterCoordinator,
    title: str,
    artist: str,
    media_uri: str,
    raw_source_fav: bool | None,
) -> bool:
    """Resolve current track `favorite` state, honoring optimistic toggles until source updates."""
    overrides: dict[str, tuple[bool, bool | None]] = getattr(
        coordinator, "_media_favorite_overrides", {}
    )
    keys = [
        k
        for k in (
            media_uri.strip(),
            f"{title.strip().lower()}|{artist.strip().lower()}" if title.strip() else "",
        )
        if k
    ]
    for k in keys:
        entry = overrides.get(k)
        if entry is not None:
            opt_val, snap_val = entry
            if raw_source_fav is not None and raw_source_fav != snap_val:
                overrides.pop(k, None)
                return bool(raw_source_fav)
            return bool(opt_val)
    return bool(raw_source_fav) if raw_source_fav is not None else False


async def _async_resolve_ma_queue_context(
    hass: HomeAssistant, ma_target: str
) -> tuple[Any | None, str, dict[str, Any]]:
    """Resolve `(mass_client, queue_id, get_queue_dict)` for Music Assistant queue commands."""
    mass = get_ma_mass_client(hass)
    q_data: dict[str, Any] = {}
    queue_id = ""
    if ma_target and hass.services.has_service("music_assistant", "get_queue"):
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_target},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict):
                cand = resp.get(ma_target) or resp
                if isinstance(cand, dict):
                    q_data = cand
                    queue_id = str(q_data.get("queue_id") or "").strip()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue context lookup failed: %s", err)
    if not queue_id:
        queue_id = resolve_ma_queue_id_sync(hass, ma_target, mass) or ma_target
    return mass, queue_id, q_data


async def _async_execute_favorite_toggle(
    coordinator: LatterCoordinator,
    target_spk: str,
    ma_target: str | None,
    state_obj: State | None,
    ma_state_obj: State | None,
    explicit_media_id: str | None,
) -> None:
    """Toggle Music Assistant favorite state for the specified or active track."""
    hass = coordinator.hass
    attrs = dict(state_obj.attributes) if state_obj is not None else {}
    m_attrs = dict(ma_state_obj.attributes) if ma_state_obj is not None else {}
    title = str(
        m_attrs.get("media_title")
        or attrs.get("media_title")
        or coordinator.last_media_title
        or ""
    ).strip()
    artist = str(
        m_attrs.get("media_artist")
        or attrs.get("media_artist")
        or coordinator.last_media_artist
        or ""
    ).strip()

    _shuf, _rep, live_q_fav, _q_cnt, live_q_uri, _is_dyn = _read_live_ma_queue_state(
        hass, ma_target
    )
    raw_explicit = str(explicit_media_id or "").strip()
    item_uri = raw_explicit if "://" in raw_explicit else ""
    if raw_explicit and not item_uri and not title:
        title = raw_explicit
    if not item_uri:
        for cand_uri in (
            live_q_uri,
            str(m_attrs.get("media_content_id") or "").strip(),
            str(attrs.get("media_content_id") or "").strip(),
            coordinator.last_media_uri.strip(),
        ):
            if (
                cand_uri
                and "://" in cand_uri
                and not _is_ephemeral_announcement_uri(cand_uri)
            ):
                item_uri = cand_uri
                break
    if not item_uri and title:
        item_uri = await async_lookup_ma_track_uri(hass, title, artist)

    raw_source_fav = _resolve_raw_source_favorite(attrs, m_attrs, live_q_fav)
    cur_fav = _resolve_effective_favorite(
        coordinator, title, artist, item_uri, raw_source_fav
    )
    target_fav = not cur_fav

    overrides: dict[str, tuple[bool, bool | None]] = getattr(
        coordinator, "_media_favorite_overrides", None
    )
    if overrides is None:
        overrides = {}
        coordinator._media_favorite_overrides = overrides
    for k in (
        item_uri,
        f"{title.lower()}|{artist.lower()}" if title else "",
    ):
        if k:
            overrides[k] = (target_fav, raw_source_fav)

    mass = get_ma_mass_client(hass)
    music_ctrl = getattr(mass, "music", None) if mass is not None else None
    handled = False
    if music_ctrl is not None and item_uri:
        try:
            if target_fav and hasattr(music_ctrl, "add_item_to_favorites"):
                await music_ctrl.add_item_to_favorites(item_uri)
                handled = True
            elif not target_fav and hasattr(music_ctrl, "remove_item_from_favorites"):
                rem_fn = music_ctrl.remove_item_from_favorites
                mtype = _parse_media_uri_type(item_uri) or "track"
                item_id: str | int = ""
                if item_uri.startswith("library://") and "/" in item_uri[10:]:
                    item_id = item_uri.rsplit("/", 1)[-1]
                elif hasattr(music_ctrl, "get_item_by_uri"):
                    fetched_item = await music_ctrl.get_item_by_uri(item_uri)
                    item_d = _extract_item_dict(fetched_item)
                    if item_d.get("item_id") is not None:
                        item_id = item_d["item_id"]
                    if item_d.get("media_type"):
                        mtype = str(item_d["media_type"])
                if not item_id and "://" in item_uri:
                    item_id = item_uri.rsplit("/", 1)[-1]
                params = list(inspect.signature(rem_fn).parameters.values())
                pos_params = [
                    p
                    for p in params
                    if p.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                ]
                if len(pos_params) == 1:
                    await rem_fn(item_uri)
                else:
                    await rem_fn(mtype, item_id or item_uri)
                handled = True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("mass.music favorite toggle for '%s' failed: %s", item_uri, err)

    if not handled:
        cmd_entity = ma_target or target_spk
        svc_name = "add_to_favorites" if target_fav else "remove_from_favorites"
        if hass.services.has_service("music_assistant", svc_name):
            svc_payload: dict[str, Any] = {ATTR_ENTITY_ID: cmd_entity}
            if item_uri:
                svc_payload["media_id"] = item_uri
            await hass.services.async_call(
                "music_assistant", svc_name, svc_payload, blocking=True
            )

    coordinator.async_notify_listeners()


async def execute_coordinator_media_command(
    coordinator: LatterCoordinator,
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
    target_spk = (
        speaker or coordinator.active_speaker or coordinator.local_speaker
    ).strip()
    if not target_spk and command.strip().lower() != "lyrics_fetch":
        return

    cmd = command.strip().lower()
    ma_target = resolve_ma_counterpart_entity(hass, target_spk) if target_spk else None
    cmd_target = ma_target or target_spk
    state_obj = hass.states.get(target_spk) if target_spk else None
    ma_state_obj = (
        hass.states.get(ma_target)
        if ma_target and ma_target != target_spk
        else None
    )
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
        coordinator._local_needs_cold_resume = False
        coordinator._resuming_guard_until = 0.0
        play_payload_id: str | list[str] = media_id
        if (
            not radio_mode
            and (media_type or "").strip().lower() == "track"
            and (enqueue or "replace").strip().lower() == "replace"
            and media_id in coordinator._browsed_album_track_uris
        ):
            idx = coordinator._browsed_album_track_uris.index(media_id)
            remaining = coordinator._browsed_album_track_uris[idx:]
            if len(remaining) > 1:
                play_payload_id = remaining
        await async_play_media_with_ma_fallback(
            hass,
            target_spk,
            play_payload_id,
            media_type=media_type,
            enqueue=enqueue,
            radio_mode=radio_mode,
        )
        return

    if cmd == "queue_play":
        clean_qid = str(queue_item_id or "").strip()
        if not clean_qid or not ma_target:
            return
        mass, queue_id, _q_data = await _async_resolve_ma_queue_context(hass, ma_target)
        if mass is not None and hasattr(mass, "player_queues") and queue_id:
            await mass.player_queues.play_index(queue_id, clean_qid)
            coordinator.async_notify_listeners()
        return

    if cmd == "queue_move":
        clean_qid = str(queue_item_id or "").strip()
        if not clean_qid or pos_shift is None or not ma_target:
            return
        mass, queue_id, q_data = await _async_resolve_ma_queue_context(hass, ma_target)
        if mass is None or not hasattr(mass, "player_queues") or not queue_id:
            return
        pqs = mass.player_queues
        raw_shift_str = str(pos_shift).strip().lower()
        shift_int = 0
        if raw_shift_str == "next":
            items_list: list[dict[str, Any]] = []
            if hasattr(pqs, "fetch_player_queue_items"):
                fetched = await pqs.fetch_player_queue_items(
                    queue_id, limit=50, offset=0
                )
                if isinstance(fetched, Sequence) and not isinstance(
                    fetched, (str, bytes)
                ):
                    items_list = [_extract_item_dict(x) for x in fetched]
            if not items_list:
                for list_key in ("queue_items", "items"):
                    cand_l = q_data.get(list_key)
                    if isinstance(cand_l, list):
                        items_list = [_extract_item_dict(x) for x in cand_l]
                        break
            item_index = next(
                (
                    idx
                    for idx, it in enumerate(items_list)
                    if str(it.get("queue_item_id") or "").strip() == clean_qid
                ),
                -1,
            )
            if item_index < 0:
                return
            current_index: int | None = None
            raw_cur_idx = q_data.get("current_index")
            if isinstance(raw_cur_idx, int) and not isinstance(raw_cur_idx, bool):
                current_index = raw_cur_idx
            elif hasattr(pqs, "get"):
                q_obj = pqs.get(queue_id)
                cand_idx = getattr(q_obj, "current_index", None) if q_obj is not None else None
                if isinstance(cand_idx, int) and not isinstance(cand_idx, bool):
                    current_index = cand_idx
            if current_index is None:
                cur_item_raw = q_data.get("current_item")
                cur_qid = (
                    str(_extract_item_dict(cur_item_raw).get("queue_item_id") or "").strip()
                    if cur_item_raw is not None
                    else ""
                )
                current_index = next(
                    (
                        idx
                        for idx, it in enumerate(items_list)
                        if cur_qid and str(it.get("queue_item_id") or "").strip() == cur_qid
                    ),
                    0,
                )
            shift_int = (current_index + 1) - item_index
        else:
            try:
                shift_int = int(raw_shift_str)
            except ValueError:
                return
        if shift_int != 0:
            await pqs.move_item(queue_id, clean_qid, pos_shift=shift_int)
            coordinator.async_notify_listeners()
        return

    if cmd == "queue_delete":
        clean_qid = str(queue_item_id or "").strip()
        if not clean_qid or not ma_target:
            return
        mass, queue_id, _q_data = await _async_resolve_ma_queue_context(hass, ma_target)
        if mass is not None and hasattr(mass, "player_queues") and queue_id:
            await mass.player_queues.delete_item(
                queue_id, item_id_or_index=clean_qid
            )
            q_counts = hass.data.get(DOMAIN, {}).get("_ma_queue_counts")
            if isinstance(q_counts, dict) and q_counts.get(ma_target, 0) > 0:
                q_counts[ma_target] = q_counts[ma_target] - 1
            coordinator.async_notify_listeners()
        return

    if cmd == "mute_toggle":
        vol_target = coordinator.get_volume_target_entity(target_spk)
        mute_entity = vol_target or cmd_target
        mute_st = hass.states.get(mute_entity)
        if (
            (mute_st is None or mute_st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN))
            and mute_entity == target_spk
            and ma_target
        ):
            mute_entity = ma_target
        await async_execute_volume_action(hass, mute_entity, "mute")
        return

    if cmd == "shuffle_toggle":
        m_attrs = dict(ma_state_obj.attributes) if ma_state_obj is not None else {}
        s_attrs = dict(state_obj.attributes) if state_obj is not None else {}
        live_shuf, _, _, _, _, live_is_dynamic = _read_live_ma_queue_state(
            hass, ma_target
        )
        if live_is_dynamic:
            _LOGGER.debug(
                "Ignoring shuffle_toggle on %s: Music Assistant queue is in dynamic mode",
                cmd_target,
            )
            return
        if "shuffle" in m_attrs and m_attrs.get("shuffle") is not None:
            cur_shuf = bool(m_attrs.get("shuffle"))
        elif "shuffle" in s_attrs and s_attrs.get("shuffle") is not None:
            cur_shuf = bool(s_attrs.get("shuffle"))
        elif live_shuf is not None:
            cur_shuf = live_shuf
        else:
            cur_shuf = False
        await hass.services.async_call(
            "media_player",
            "shuffle_set",
            {ATTR_ENTITY_ID: cmd_target, "shuffle": not cur_shuf},
            blocking=False,
        )
        return

    if cmd == "repeat_cycle":
        m_attrs = dict(ma_state_obj.attributes) if ma_state_obj is not None else {}
        s_attrs = dict(state_obj.attributes) if state_obj is not None else {}
        _, live_rep, _, _, _, live_is_dynamic = _read_live_ma_queue_state(
            hass, ma_target
        )
        if live_is_dynamic:
            _LOGGER.debug(
                "Ignoring repeat_cycle on %s: Music Assistant queue is in dynamic mode",
                cmd_target,
            )
            return
        cur_rep = (
            _normalize_repeat_mode(m_attrs.get("repeat"))
            or _normalize_repeat_mode(s_attrs.get("repeat"))
            or live_rep
            or "off"
        )
        next_rep = {"off": "all", "all": "one", "one": "off"}.get(cur_rep, "all")
        await hass.services.async_call(
            "media_player",
            "repeat_set",
            {ATTR_ENTITY_ID: cmd_target, "repeat": next_rep},
            blocking=False,
        )
        return

    if cmd == "favorite_toggle":
        await _async_execute_favorite_toggle(
            coordinator,
            target_spk,
            ma_target,
            state_obj,
            ma_state_obj,
            media_id,
        )
        return

    if cmd == "lyrics_fetch":
        await async_fetch_and_push_music_lyrics(
            hass,
            coordinator,
            req_id=0,
            speaker=target_spk,
            search=str(media_id or "").strip(),
        )
        return

    if cmd == "play":
        now = time.monotonic()
        if now < coordinator._resuming_guard_until:
            return
        coordinator._resuming_guard_until = now + 2.5
        cmd_target_st = hass.states.get(cmd_target)
        has_loaded_media = bool(
            (
                ma_state_obj
                and (
                    ma_state_obj.attributes.get("media_content_id")
                    or ma_state_obj.attributes.get("media_title")
                )
            )
            or (
                state_obj
                and (
                    state_obj.attributes.get("media_content_id")
                    or state_obj.attributes.get("media_title")
                )
            )
        )
        play_failed_empty = False
        if cmd_target_st is not None and cmd_target_st.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            play_failed_empty = True
        else:
            try:
                await hass.services.async_call(
                    "media_player",
                    "media_play",
                    {ATTR_ENTITY_ID: cmd_target},
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.debug(
                    "media_play on %s failed (%s); attempting queue fallback",
                    cmd_target,
                    err,
                )
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
                and (
                    not has_loaded_media
                    or (is_local and coordinator._local_needs_cold_resume)
                )
            )
        ):
            coordinator._resuming_guard_until = time.monotonic() + 3.5
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
                coordinator._local_needs_cold_resume = False
                _sync_active_speaker_media_snapshot(coordinator)
                coordinator.async_notify_listeners()
        return

    if cmd == "pause":
        coordinator._transfer_hold_spinup_until = 0.0
        coordinator._resuming_guard_until = 0.0
        await hass.services.async_call(
            "media_player", "media_pause", {ATTR_ENTITY_ID: cmd_target}, blocking=False
        )
        return

    if cmd in ("next", "next_track", "media_next_track"):
        await hass.services.async_call(
            "media_player",
            "media_next_track",
            {ATTR_ENTITY_ID: cmd_target},
            blocking=False,
        )
        return

    if cmd in ("previous", "previous_track", "media_previous_track"):
        await hass.services.async_call(
            "media_player",
            "media_previous_track",
            {ATTR_ENTITY_ID: cmd_target},
            blocking=False,
        )
        return

    if cmd == "stop":
        coordinator._transfer_hold_spinup_until = 0.0
        coordinator._resuming_guard_until = 0.0
        await hass.services.async_call(
            "media_player", "media_stop", {ATTR_ENTITY_ID: cmd_target}, blocking=False
        )
        return

    if cmd == "clear_queue":
        coordinator._transfer_hold_spinup_until = 0.0
        if ma_target:
            q_counts = hass.data.get(DOMAIN, {}).get("_ma_queue_counts")
            if isinstance(q_counts, dict):
                q_counts[ma_target] = 0
        await hass.services.async_call(
            "media_player",
            "clear_playlist",
            {ATTR_ENTITY_ID: cmd_target},
            blocking=False,
        )
        return

    if cmd == "seek" and seek_position is not None:
        await hass.services.async_call(
            "media_player",
            "media_seek",
            {
                ATTR_ENTITY_ID: cmd_target,
                "seek_position": round(float(seek_position), 1),
            },
            blocking=False,
        )
        return

    if cmd == "join":
        raw_members = (
            [group_members]
            if isinstance(group_members, str)
            else list(group_members or [])
        )
        resolved_members: list[str] = []
        for item in raw_members:
            cand = str(item or "").strip()
            if not cand or not cand.startswith("media_player."):
                continue
            if ma_target:
                cand = resolve_ma_counterpart_entity(hass, cand) or cand
            if cand != cmd_target and cand not in resolved_members:
                resolved_members.append(cand)
        if resolved_members:
            await hass.services.async_call(
                "media_player",
                "join",
                {
                    ATTR_ENTITY_ID: cmd_target,
                    "group_members": resolved_members,
                },
                blocking=False,
            )
        return

    if cmd == "unjoin":
        await hass.services.async_call(
            "media_player", "unjoin", {ATTR_ENTITY_ID: cmd_target}, blocking=False
        )


def build_active_media_payload(
    coordinator: LatterCoordinator,
) -> tuple[str | None, dict[str, Any]]:
    """Compute state and attributes for sensor.<device_slug>_active_media."""
    now_m = time.monotonic()
    if (
        coordinator._cached_media_payload is not None
        and (now_m - coordinator._cached_media_payload[0]) < 0.15
    ):
        return coordinator._cached_media_payload[1]
    (
        state_obj,
        ma_st,
        ma_counterpart,
        state,
        attrs,
        m_attrs,
        title,
        artist,
        album,
        duration,
        position,
        media_type,
        is_local_flag,
    ) = _resolve_speaker_media_snapshot(coordinator)

    vol_target = coordinator.get_volume_target_entity(coordinator.active_speaker)
    fallback_spk_name = (
        coordinator.device_title
        if is_local_flag
        else (
            coordinator.active_speaker.split(".", 1)[-1].replace("_", " ").title()
            if coordinator.active_speaker
            else ""
        )
    )

    if state_obj is None:
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
            round(max(0.0, min(1.0, idle_vol)) * 100.0)
            if idle_vol is not None
            else None
        )
        idle_muted = _read_muted_from_targets(coordinator.hass, vol_target, {}, {})
        idle_caps = compute_media_caps(
            coordinator.hass, None, ma_st, ma_counterpart, vol_target
        )
        med_rev, med_payload = coordinator._pack_domain_payload(
            "active_media",
            "",
            idle_title,
            idle_artist,
            idle_album,
            idle_dur,
            idle_pos,
            None,
            idle_vol_pct,
            idle_type,
            "",
            coordinator.active_speaker,
            fallback_spk_name,
            coordinator.last_speaker,
            coordinator.local_speaker,
            is_local_flag,
            False,
            "",
            idle_muted,
            False,
            0,
            idle_caps,
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
                "is_local": bool(is_local_flag),
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
        coordinator._cached_media_payload = (time.monotonic(), res)
        return res

    if coordinator._transfer_hold_spinup_until > 0.0:
        if state in (STATE_PLAYING, STATE_PAUSED):
            coordinator._transfer_hold_spinup_until = 0.0
        elif now_m < coordinator._transfer_hold_spinup_until and state in (
            STATE_IDLE,
            STATE_OFF,
        ):
            state = STATE_PLAYING

    in_transfer_window = now_m < coordinator._transfer_hold_until
    if in_transfer_window:
        if not title and coordinator._transfer_hold_title:
            title = coordinator._transfer_hold_title
            artist = coordinator._transfer_hold_artist or artist
            album = coordinator._transfer_hold_album or album
            duration = coordinator._transfer_hold_duration or duration
        if position < 1.0 and coordinator._transfer_hold_position > 1.0:
            position = coordinator._transfer_hold_position
    elif (
        not title
        and state == STATE_IDLE
        and coordinator.last_media_title
        and bool(is_local_flag)
    ):
        title = coordinator.last_media_title
        artist = coordinator.last_media_artist
        album = coordinator.last_media_album
        duration = coordinator.last_media_duration
        position = coordinator.last_media_position
        media_type = coordinator.last_media_type

    volume = read_volume_from_target(coordinator.hass, vol_target, attrs)
    if volume is None and m_attrs:
        volume = read_volume_from_target(coordinator.hass, vol_target, m_attrs)

    raw_pic = str(
        attrs.get("entity_picture_local")
        or attrs.get("entity_picture")
        or attrs.get("media_image_url")
        or m_attrs.get("entity_picture_local")
        or m_attrs.get("entity_picture")
        or m_attrs.get("media_image_url")
        or ""
    )
    track_key = f"{title}|{artist}|{album}"

    if state == STATE_OFF or not title:
        art_url = ""
    elif raw_pic:
        coordinator.last_valid_raw_pic = raw_pic
        coordinator._last_art_track_key = track_key
        coordinator._last_art_proxy_url = coordinator.build_proxy_art_url(
            f"{track_key}|{raw_pic}"
        )
        art_url = coordinator._last_art_proxy_url
    elif (
        track_key == coordinator._last_art_track_key or in_transfer_window
    ) and coordinator._last_art_proxy_url:
        art_url = coordinator._last_art_proxy_url
    else:
        art_url = ""

    speaker_name = (
        coordinator.device_title
        if is_local_flag
        else str(attrs.get("friendly_name") or fallback_spk_name)
    )

    raw_updated_at = attrs.get("media_position_updated_at") or m_attrs.get(
        "media_position_updated_at"
    )
    if isinstance(raw_updated_at, datetime):
        pos_updated_at = int(raw_updated_at.timestamp())
    elif raw_updated_at:
        parsed_ua = dt_util.parse_datetime(str(raw_updated_at))
        pos_updated_at = int(parsed_ua.timestamp()) if parsed_ua else 0
    else:
        pos_updated_at = 0

    (
        live_shuf,
        live_rep,
        live_fav,
        live_q_cnt,
        live_q_uri,
        live_is_dynamic,
    ) = _read_live_ma_queue_state(coordinator.hass, ma_counterpart)
    if "shuffle" in m_attrs and m_attrs.get("shuffle") is not None:
        shuffle_flag = bool(m_attrs.get("shuffle"))
    elif "shuffle" in attrs and attrs.get("shuffle") is not None:
        shuffle_flag = bool(attrs.get("shuffle"))
    elif live_shuf is not None:
        shuffle_flag = live_shuf
    else:
        shuffle_flag = False

    repeat_str = (
        _normalize_repeat_mode(m_attrs.get("repeat"))
        or _normalize_repeat_mode(attrs.get("repeat"))
        or live_rep
        or "off"
    )
    muted_flag = _read_muted_from_targets(coordinator.hass, vol_target, attrs, m_attrs)

    active_media_uri = ""
    for cand_cid in (
        live_q_uri,
        str(m_attrs.get("media_content_id") or "").strip(),
        str(attrs.get("media_content_id") or "").strip(),
        coordinator.last_media_uri.strip(),
    ):
        if cand_cid and not _is_ephemeral_announcement_uri(cand_cid):
            active_media_uri = cand_cid
            break
    raw_source_fav = _resolve_raw_source_favorite(attrs, m_attrs, live_fav)
    favorite_flag = (
        _resolve_effective_favorite(
            coordinator, title, artist, active_media_uri, raw_source_fav
        )
        if title
        else False
    )

    queue_count = 0
    if live_q_cnt is not None:
        queue_count = live_q_cnt
    else:
        found_attr_q = False
        for q_src in (m_attrs, attrs):
            for q_key in ("queue_count", "items"):
                q_val = q_src.get(q_key)
                if isinstance(q_val, int) and not isinstance(q_val, bool):
                    queue_count = max(0, q_val)
                    found_attr_q = True
                    break
                if isinstance(q_val, list):
                    queue_count = len(q_val)
                    found_attr_q = True
                    break
            if found_attr_q:
                break
        if not found_attr_q and ma_counterpart:
            cached_q_counts = coordinator.hass.data.get(DOMAIN, {}).get(
                "_ma_queue_counts"
            )
            if isinstance(cached_q_counts, dict):
                queue_count = max(0, int(cached_q_counts.get(ma_counterpart, 0)))
    queue_count = max(0, min(65535, int(queue_count)))

    media_caps = compute_media_caps(
        coordinator.hass,
        state_obj,
        ma_st,
        ma_counterpart,
        vol_target,
        dynamic_queue=live_is_dynamic,
    )

    dur_r = round(duration, 1) if duration > 0 else None
    vol_r = round(volume, 2) if volume is not None else None
    vol_pct = (
        round(max(0.0, min(1.0, volume)) * 100.0)
        if volume is not None
        else None
    )
    raw_pos = float(attrs.get("media_position") or m_attrs.get("media_position") or 0.0)
    media_anchor = (
        state,
        title,
        artist,
        album,
        dur_r,
        round(raw_pos, 1),
        pos_updated_at,
        vol_pct,
        media_type,
        art_url,
        coordinator.active_speaker,
        speaker_name,
        coordinator.last_speaker,
        coordinator.local_speaker,
        is_local_flag,
        shuffle_flag,
        repeat_str,
        muted_flag,
        favorite_flag,
        queue_count,
        media_caps,
    )
    if (
        coordinator._cached_media_anchor is not None
        and coordinator._cached_media_anchor[0] == media_anchor
    ):
        pos_r = coordinator._cached_media_anchor[1]
    else:
        pos_r = round(position, 1)
        coordinator._cached_media_anchor = (media_anchor, pos_r)

    med_rev, med_payload = coordinator._pack_domain_payload(
        "active_media",
        state,
        title,
        artist,
        album,
        dur_r,
        pos_r,
        pos_updated_at or None,
        vol_pct,
        media_type,
        art_url,
        coordinator.active_speaker,
        speaker_name,
        coordinator.last_speaker,
        coordinator.local_speaker,
        is_local_flag,
        shuffle_flag,
        repeat_str,
        muted_flag,
        favorite_flag,
        queue_count,
        media_caps,
    )
    res = (
        state,
        {
            "title": title,
            "artist": artist,
            "album": album,
            "duration": dur_r,
            "position": pos_r,
            "position_updated_at": pos_updated_at,
            "volume": vol_r,
            "media_type": media_type,
            "art_url": art_url,
            "active_speaker": coordinator.active_speaker,
            "speaker_name": speaker_name,
            "last_speaker": coordinator.last_speaker,
            "local_speaker": coordinator.local_speaker,
            "is_local": bool(is_local_flag),
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
    coordinator._cached_media_payload = (time.monotonic(), res)
    return res
