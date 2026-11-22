"""Music Assistant player linking, identity matching, and safe numeric parsers (`L1b`)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import logging
import math
import re
import time
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED, STATE_PLAYING, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from ..const import CONF_ESPHOME_DEVICE_ID, CONF_MA_PLAYER_ENTITY, DOMAIN, SUBENTRY_DEVICE
from ..hub_registry import iter_coordinators
from ..identity import device_entities, find_device_entity_by_suffix, get_bound_esphome_device
from ..repairs_keys import link_ma_player_issue_id

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry
    from homeassistant.helpers.entity_registry import RegistryEntry

_LOGGER = logging.getLogger(__name__)
_MAC_TOKEN_RE: Final = re.compile(
    r"(?:^|[^0-9a-fA-F])((?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12})(?:$|[^0-9a-fA-F])"
)
_STRICT_MAC_RE: Final = re.compile(
    r"^(?:bridge[-_])?((?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12})$"
)
_MA_RECONNECT_GRACE_SECONDS: Final[float] = 45.0
_MA_OFFLINE_CACHE_TTL_SECONDS: Final[float] = 5.0
_CACHE_TUPLE_LEN: Final[int] = 3
type CandidateRow = tuple["RegistryEntry", "DeviceEntry | None", set[str], set[str], set[str]]
_SPEAKER_REBIND_CALLBACK: Callable[[Any], None] | None = None


def register_speaker_rebind_callback(cb: Callable[[Any], None]) -> None:
    """Register the `L2a` coordinator speaker-listener rebind callback without upward imports."""
    global _SPEAKER_REBIND_CALLBACK
    _SPEAKER_REBIND_CALLBACK = cb


@dataclass(slots=True)
class _DeviceTargetIdentity:
    dev_ids: set[str]
    macs: set[str]
    ha_entities: set[str]
    protocol_ids: set[str]
    pending_sendspin: bool
    spk_dev: DeviceEntry | None


@dataclass(slots=True)
class _MaResolveCtx:
    hass: HomeAssistant
    speaker_entity_id: str
    spk_entry: RegistryEntry | None
    owner_coord: Any
    target: _DeviceTargetIdentity
    live_candidates: list[CandidateRow]
    offline_candidates: list[CandidateRow]
    raw_configured: str
    other_esp_macs: set[str]
    other_esp_protos: set[str]
    in_reconnect_grace: bool = False


def is_music_assistant_player(hass: HomeAssistant, state_obj: State) -> bool:
    """Return True if the `media_player` entity is provided by Music Assistant."""
    entry = er.async_get(hass).async_get(state_obj.entity_id)
    return entry is not None and entry.platform == "music_assistant"


def get_ma_mass_client(hass: HomeAssistant) -> Any | None:
    """Resolve the active Music Assistant runtime client (`ma_entry.runtime_data.mass`), or None."""
    for entry in sorted(
        hass.config_entries.async_entries("music_assistant"),
        key=lambda e: 0 if e.state is ConfigEntryState.LOADED else 1,
    ):
        if (runtime_data := getattr(entry, "runtime_data", None)) is None:
            continue
        if (mass := getattr(runtime_data, "mass", None)) is not None:
            return mass
        if hasattr(runtime_data, "player_queues") or hasattr(runtime_data, "music"):
            return runtime_data
    return None


def resolve_ma_queue_id_sync(hass: HomeAssistant, ma_target: str, mass: Any | None = None) -> str:
    """Synchronously resolve the Music Assistant `queue_id` for a `media_player` entity."""
    if not ma_target:
        return ""
    if (st := hass.states.get(ma_target)) is not None and (active_q := str(st.attributes.get("active_queue") or "").strip()):
        return active_q
    ent_entry = er.async_get(hass).async_get(ma_target)
    uid = str(ent_entry.unique_id or "").strip() if ent_entry is not None else ""
    if uid and (players := getattr(mass, "players", None)) is not None and hasattr(players, "get"):
        try:
            p_obj = players.get(uid)
            act_src = str(getattr(p_obj, "active_source", None) or getattr(p_obj, "active_group", None) or "").strip()
            pqs = getattr(mass, "player_queues", None)
            if act_src and pqs is not None and hasattr(pqs, "get") and pqs.get(act_src) is not None:
                return act_src
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as err:
            _LOGGER.debug("resolve_ma_queue_id_sync(%s) skipped: %s", ma_target, err)
    return uid


def safe_opt_float(val: Any) -> float | None:
    """Safely parse an optional finite float, returning `None` when absent or non-numeric."""
    if val is None or isinstance(val, bool):
        return None
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely parse a finite float without raising on `'unavailable'`/`'unknown'`/boolean values (`M-P1-38`)."""
    return parsed if (parsed := safe_opt_float(val)) is not None else default


def safe_int(val: Any, default: int = 0) -> int:
    """Safely parse an integer without raising on non-numeric strings, NaN/Inf, or booleans (`M-P2-22`)."""
    return round(parsed) if (parsed := safe_opt_float(val)) is not None else default


_safe_opt_float = safe_opt_float
_safe_float = safe_float
_safe_int = safe_int


def interpolate_speaker_position(state_obj: Any) -> float:
    """Calculate the live interpolated playback position in seconds for a `media_player` state."""
    if state_obj is None:
        return 0.0
    attrs = state_obj.attributes
    duration, pos = safe_float(attrs.get("media_duration"), 0.0), safe_float(attrs.get("media_position"), 0.0)
    updated_at = attrs.get("media_position_updated_at")
    if state_obj.state == STATE_PLAYING and isinstance(updated_at, datetime):
        elapsed = (dt_util.utcnow() - updated_at).total_seconds()
        if elapsed > 0:
            pos = min(pos + elapsed, duration) if duration > 0 else (pos + elapsed)
    return max(0.0, pos)


def configured_link(configured: str | None, ma_player_entities_iter: Iterable[str]) -> str | None:
    """Return the Device's configured Music Assistant player if it is a current MA `media_player`, else None."""
    target = str(configured or "").strip()
    return target if (target and target in set(ma_player_entities_iter)) else None


def suggest_ma_player(
    device_identity: tuple[str | None, str | None],
    candidates: Iterable[tuple[str, str | None, str | None]],
) -> str | None:
    """Suggest the MA player whose device has the exact same manufacturer AND model (unique match only)."""
    manufacturer, model = device_identity
    if not manufacturer or not model:
        return None
    matches = [eid for eid, c_mfr, c_mod in candidates if c_mfr == manufacturer and c_mod == model]
    return matches[0] if len(matches) == 1 else None


def _extract_macs_from_string(raw: str | None) -> set[str]:
    return (
        {dr.format_mac(tok) for m in _MAC_TOKEN_RE.finditer(str(raw)) if (tok := m.group(1))}
        if raw
        else set()
    )


def _extract_strict_mac(raw: str | None) -> str | None:
    match = _STRICT_MAC_RE.match(str(raw).strip()) if raw else None
    return dr.format_mac(match.group(1)) if match else None


def _attr_or_key(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)


def _extract_macs_from_device_or_entry(dev: DeviceEntry | None, ent: RegistryEntry | None = None) -> set[str]:
    macs: set[str] = set()
    if dev is not None:
        for _t, val in (*dev.connections, *dev.identifiers):
            if val:
                macs.update(_extract_macs_from_string(str(val)))
    if ent is not None and ent.unique_id:
        macs.update(_extract_macs_from_string(str(ent.unique_id)))
    return macs


def _lookup_mass_player(mass: Any, player_id: str) -> Any | None:
    players = getattr(mass, "players", None) if (mass is not None and player_id) else None
    if players is None:
        return None
    if hasattr(players, "get"):
        try:
            if (found := players.get(player_id)) is not None:
                return found
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as err:
            _LOGGER.debug("mass.players.get(%s) skipped: %s", player_id, err)
    if isinstance(players, Iterable) and not isinstance(players, (str, bytes, Mapping)):
        for item in players:
            if str(_attr_or_key(item, "player_id") or "").strip() == player_id:
                return item
    return None


def _collect_sendspin_from_config_entries(
    hass: HomeAssistant, cfg_entries: Iterable[Any]
) -> tuple[set[str], bool]:
    client_ids, entry_ids = set[str](), set[str]()
    pending_pairing = False
    ss_domain_map = getattr(hass.data.get("esphome"), "sendspin_client_ids", None)
    for cfg_entry in cfg_entries:
        if cfg_entry is None or getattr(cfg_entry, "domain", None) != "esphome":
            continue
        if not (cfg_id := str(getattr(cfg_entry, "entry_id", "") or "").strip()) or cfg_id in entry_ids:
            continue
        entry_ids.add(cfg_id)
        dev_caps = getattr(getattr(cfg_entry, "runtime_data", None), "device_capabilities", None)
        if (ss_cap := _attr_or_key(dev_caps, "sendspin")) is not None:
            if cid := str(_attr_or_key(ss_cap, "client_id") or "").strip():
                client_ids.add(cid)
            elif isinstance(flags := _attr_or_key(ss_cap, "feature_flags"), int) and flags > 0:
                pending_pairing = True
    if entry_ids and isinstance(ss_domain_map, Mapping):
        client_ids.update(
            str(mcid).strip() for mcid, meid in ss_domain_map.items() if meid in entry_ids and mcid
        )
    return client_ids, (False if client_ids else pending_pairing)


def _extract_esphome_sendspin_info(hass: HomeAssistant, dev_ids: Iterable[str]) -> tuple[set[str], bool]:
    dev_reg = dr.async_get(hass)
    seen_entries: set[str] = set()
    cfg_entries: list[Any] = []
    for did in dev_ids:
        if (d_obj := dev_reg.async_get(did)) is None:
            continue
        cfg_id = getattr(d_obj, "config_entry_id", None) or getattr(d_obj, "primary_config_entry", None)
        if cfg_id and cfg_id not in seen_entries:
            seen_entries.add(cfg_id)
            if (cfg_entry := hass.config_entries.async_get_entry(cfg_id)) is not None:
                cfg_entries.append(cfg_entry)
    return _collect_sendspin_from_config_entries(hass, cfg_entries)


def _record_protocol_or_entity(
    raw_id: str, domain_str: str, buckets: tuple[set[str], set[str], set[str]]
) -> None:
    if not raw_id or raw_id == "native":
        return
    macs, ha_entities, protocol_ids = buckets
    if domain_str == "hass_players" or raw_id.startswith("media_player."):
        ha_entities.add(raw_id)
        return
    protocol_ids.add(raw_id)
    if strict_mac := _extract_strict_mac(raw_id):
        macs.add(strict_mac)


def _collect_mass_device_info(dev_info: Any, macs: set[str], protocol_ids: set[str]) -> None:
    if dev_info is None:
        return
    if raw_mac := _attr_or_key(dev_info, "mac_address"):
        macs.update(_extract_macs_from_string(str(raw_mac)))
    if not isinstance(raw_idents := _attr_or_key(dev_info, "identifiers"), Mapping):
        return
    for id_key, id_val in raw_idents.items():
        key_name = str(getattr(id_key, "value", id_key) or "").strip().lower()
        if not (val_str := str(id_val or "").strip()):
            continue
        if "mac" in key_name:
            macs.update(_extract_macs_from_string(val_str))
        elif "uuid" in key_name:
            protocol_ids.add(val_str)


def _extract_mass_player_identity(
    hass: HomeAssistant, ent: RegistryEntry | None
) -> tuple[set[str], set[str], set[str]]:
    if ent is None or not ent.unique_id:
        return set(), set(), set()
    if (p_obj := _lookup_mass_player(get_ma_mass_client(hass), str(ent.unique_id).strip())) is None:
        return set(), set(), set()

    macs, ha_entities, protocol_ids = set[str](), set[str](), set[str]()
    buckets = (macs, ha_entities, protocol_ids)
    if (raw_pid := str(_attr_or_key(p_obj, "player_id") or "").strip()) and str(
        _attr_or_key(p_obj, "provider") or ""
    ).strip().lower().startswith("sendspin"):
        protocol_ids.add(raw_pid)
        if strict_mac := _extract_strict_mac(raw_pid):
            macs.add(strict_mac)

    _collect_mass_device_info(_attr_or_key(p_obj, "device_info"), macs, protocol_ids)
    if isinstance(protocols := _attr_or_key(p_obj, "protocols"), Iterable) and not isinstance(
        protocols, (str, bytes, Mapping)
    ):
        for proto in protocols:
            _record_protocol_or_entity(
                str(_attr_or_key(proto, "protocol_id") or "").strip(),
                str(_attr_or_key(proto, "domain") or "").strip().lower(),
                buckets,
            )
    if isinstance(out_protocols := _attr_or_key(p_obj, "output_protocols"), Iterable) and not isinstance(
        out_protocols, (str, bytes, Mapping)
    ):
        for out_p in out_protocols:
            _record_protocol_or_entity(
                str(_attr_or_key(out_p, "output_protocol_id") or "").strip(),
                str(_attr_or_key(out_p, "protocol_domain") or "").strip().lower(),
                buckets,
            )
            if (derived := str(_attr_or_key(out_p, "derived_from") or "").strip()) and derived != "native":
                protocol_ids.add(derived)
                if strict_mac := _extract_strict_mac(derived):
                    macs.add(strict_mac)
    return macs, ha_entities, protocol_ids


def _candidate_identity(
    hass: HomeAssistant, c_entry: RegistryEntry, c_dev: DeviceEntry | None
) -> tuple[set[str], set[str], set[str]]:
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


def _collect_other_esphome_identities(hass: HomeAssistant, exclude_dev_ids: set[str]) -> tuple[set[str], set[str]]:
    dev_reg = dr.async_get(hass)
    macs: set[str] = set()
    other_entries: list[Any] = []
    for esp_ce in hass.config_entries.async_entries("esphome"):
        other_devs = [
            d for d in dr.async_entries_for_config_entry(dev_reg, esp_ce.entry_id) if d.id not in exclude_dev_ids
        ]
        for d_esp in other_devs:
            macs.update(_extract_macs_from_device_or_entry(d_esp, None))
        if other_devs:
            other_entries.append(esp_ce)
    protos, _ = _collect_sendspin_from_config_entries(hass, other_entries)
    return macs, protos


@callback
def clear_ma_counterpart_cache(hass: HomeAssistant) -> None:
    """Clear cached speaker -> Music Assistant counterpart mappings and unsubscribe listeners on unload."""
    if not isinstance(domain_data := hass.data.get(DOMAIN), dict):
        return
    for key in ("_ma_counterpart_cache", "_ma_known_macs", "_ma_known_protocols", "_ma_reconnect_until"):
        if isinstance(bucket := domain_data.get(key), dict):
            bucket.clear()
    if callable(reconnect_timer := domain_data.pop("_ma_reconnect_timer", None)):
        reconnect_timer()
    if isinstance(unsubs := domain_data.pop("_ma_cache_unsubs", None), (list, tuple)):
        for unsub in unsubs:
            if callable(unsub):
                unsub()


def _is_entity_live(hass: HomeAssistant, entity_id: str | None) -> bool:
    return bool(
        entity_id and (st := hass.states.get(entity_id)) is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    )


@callback
def _arm_ma_reconnect_grace(hass: HomeAssistant, entity_id: str) -> None:
    if not entity_id:
        return
    domain_data = hass.data.setdefault(DOMAIN, {})
    reconnect_until: dict[str, float] = domain_data.setdefault("_ma_reconnect_until", {})
    reconnect_until[entity_id] = time.monotonic() + _MA_RECONNECT_GRACE_SECONDS
    if callable(prev_timer := domain_data.pop("_ma_reconnect_timer", None)):
        prev_timer()

    @callback
    def _on_grace_expired(_now: Any) -> None:
        domain_data.pop("_ma_reconnect_timer", None)
        now_mono = time.monotonic()
        for k in [k for k, ts in reconnect_until.items() if ts <= now_mono]:
            reconnect_until.pop(k, None)
        if isinstance(cache := domain_data.get("_ma_counterpart_cache"), dict):
            cache.clear()
        async_heal_coordinator_ma_links(hass)

    domain_data["_ma_reconnect_timer"] = async_call_later(
        hass, _MA_RECONNECT_GRACE_SECONDS + 0.5, _on_grace_expired
    )


def _in_ma_reconnect_grace(hass: HomeAssistant, *entity_ids: str) -> bool:
    if not isinstance(domain_data := hass.data.get(DOMAIN), dict):
        return False
    if not isinstance(reconnect_until := domain_data.get("_ma_reconnect_until"), dict) or not reconnect_until:
        return False
    now_mono = time.monotonic()
    return any(bool(eid and now_mono < reconnect_until.get(eid, 0.0)) for eid in entity_ids)


@callback
def _ensure_ma_cache_listeners(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "_ma_cache_unsubs" in domain_data:
        return

    @callback
    def _on_registry_updated(_event: Event[Any]) -> None:
        if isinstance(cache := domain_data.get("_ma_counterpart_cache"), dict):
            cache.clear()

    @callback
    def _on_ma_state_changed(event: Event[Any]) -> None:
        if not (entity_id := str(event.data.get("entity_id") or "")).startswith("media_player."):
            return
        old_st, new_st = event.data.get("old_state"), event.data.get("new_state")
        old_live = old_st is not None and old_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        new_live = new_st is not None and new_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        if old_live == new_live:
            return
        if (ent := er.async_get(hass).async_get(entity_id)) is None or ent.platform not in (
            "music_assistant",
            "esphome",
        ):
            return
        if ent.platform == "esphome" and old_st is not None and not old_live and new_live:
            _arm_ma_reconnect_grace(hass, entity_id)
        elif ent.platform == "music_assistant":
            if old_live and not new_live:
                _arm_ma_reconnect_grace(hass, entity_id)
            elif new_live and isinstance(rec := domain_data.get("_ma_reconnect_until"), dict):
                rec.pop(entity_id, None)
        if isinstance(cache := domain_data.get("_ma_counterpart_cache"), dict):
            cache.clear()
        async_heal_coordinator_ma_links(hass)

    domain_data["_ma_cache_unsubs"] = (
        hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _on_registry_updated),
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_registry_updated),
        hass.bus.async_listen(EVENT_STATE_CHANGED, _on_ma_state_changed),
    )


def resolve_esphome_local_speaker(hass: HomeAssistant, esphome_device_id: str | None) -> str:
    """Resolve the on-device `media_player` entity for the bound ESPHome node, or `''`."""
    if (dev := get_bound_esphome_device(hass, esphome_device_id)) is None:
        return ""
    if by_suffix := find_device_entity_by_suffix(hass, dev.id, "media_player", ("_music",)):
        return by_suffix
    return next(
        (str(e.entity_id) for e in device_entities(hass, dev.id, domain="media_player") if e.platform == "esphome"),
        "",
    )


@callback
def _update_ma_link_issue(hass: HomeAssistant, coordinator: Any, speaker_entity_id: str, matched: bool) -> None:
    issue_id = link_ma_player_issue_id(str(getattr(coordinator, "subentry_id", "")))
    if matched or not hass.config_entries.async_entries("music_assistant"):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    placeholders = {
        "device_slug": str(getattr(coordinator, "device_slug", "") or ""),
        "speaker_entity": speaker_entity_id,
    }
    ir.async_create_issue(
        hass, DOMAIN, issue_id, is_fixable=True, severity=ir.IssueSeverity.WARNING,
        translation_key="link_ma_player", translation_placeholders=placeholders,
        config_entry_id=getattr(getattr(coordinator, "entry", None), "entry_id", None),
        data={"subentry_id": str(getattr(coordinator, "subentry_id", ""))},
    )


def ma_player_entities(hass: HomeAssistant) -> list[RegistryEntry]:
    """Return the enabled Music Assistant `media_player` registry entries."""
    ent_reg = er.async_get(hass)
    return [
        entry
        for ma_cfg in hass.config_entries.async_entries("music_assistant")
        for entry in er.async_entries_for_config_entry(ent_reg, ma_cfg.entry_id)
        if entry.domain == "media_player" and entry.platform == "music_assistant" and not entry.disabled_by
    ]


def _collect_device_target_identity(
    hass: HomeAssistant, *, speaker_entity_id: str = "", owner_coord: Any = None, esphome_device_id: str | None = None
) -> _DeviceTargetIdentity:
    ent_reg, dev_reg = er.async_get(hass), dr.async_get(hass)
    target_dev_ids = {str(esphome_device_id)} if esphome_device_id else set[str]()
    target_macs, target_ha_entities = set[str](), ({speaker_entity_id} if speaker_entity_id else set[str]())
    spk_dev: DeviceEntry | None = None
    if speaker_entity_id and (spk_entry := ent_reg.async_get(speaker_entity_id)) is not None:
        if spk_entry.device_id:
            target_dev_ids.add(spk_entry.device_id)
            spk_dev = dev_reg.async_get(spk_entry.device_id)
        target_macs.update(_extract_macs_from_device_or_entry(spk_dev, spk_entry))
    if owner_coord is not None:
        if esp_dev_id := getattr(owner_coord, "esphome_device_id", None):
            target_dev_ids.add(str(esp_dev_id))
        if coord_mac := getattr(owner_coord, "device_mac", None):
            target_macs.add(dr.format_mac(str(coord_mac)))
    for did in list(target_dev_ids):
        if (d_obj := dev_reg.async_get(did)) is not None:
            if d_obj.via_device_id:
                target_dev_ids.add(d_obj.via_device_id)
            target_macs.update(_extract_macs_from_device_or_entry(d_obj, None))
        target_ha_entities.update(
            e.entity_id for e in device_entities(hass, did, domain="media_player") if e.platform == "esphome"
        )
    target_protos, pending_ss = _extract_esphome_sendspin_info(hass, target_dev_ids)
    return _DeviceTargetIdentity(target_dev_ids, target_macs, target_ha_entities, target_protos, pending_ss, spk_dev)


def _match_ma_by_identity(candidates: Iterable[CandidateRow], target: _DeviceTargetIdentity) -> str | None:
    cand_list = list(candidates)
    checks: tuple[tuple[bool, Callable[[CandidateRow], bool]], ...] = (
        (bool(target.dev_ids), lambda r: bool(r[0].device_id and (r[0].device_id in target.dev_ids or (r[1] and r[1].via_device_id in target.dev_ids)))),
        (bool(target.ha_entities), lambda r: bool(target.ha_entities & r[3])),
        (bool(target.protocol_ids), lambda r: bool(target.protocol_ids & r[4])),
        (bool(target.macs), lambda r: bool(target.macs & r[2])),
    )
    for enabled, pred in checks:
        if enabled:
            for row in cand_list:
                if pred(row):
                    return str(row[0].entity_id)
    return None


def _build_ma_candidates(hass: HomeAssistant) -> tuple[list[CandidateRow], list[CandidateRow]]:
    dev_reg = dr.async_get(hass)
    live, offline = list[CandidateRow](), list[CandidateRow]()
    for entry in ma_player_entities(hass):
        c_dev = dev_reg.async_get(entry.device_id) if entry.device_id else None
        c_macs, c_ha_ents, c_protos = _candidate_identity(hass, entry, c_dev)
        (live if _is_entity_live(hass, entry.entity_id) else offline).append(
            (entry, c_dev, c_macs, c_ha_ents, c_protos)
        )
    return live, offline


def _conflicts_with_target(
    c_macs: set[str], c_protos: set[str], target_macs: set[str], target_protos: set[str]
) -> bool:
    return bool(
        (c_macs and target_macs and not (c_macs & target_macs))
        or (c_protos and target_protos and not (c_protos & target_protos))
    )


def _belongs_to_other_esphome(
    c_macs: set[str], c_protos: set[str], target: _DeviceTargetIdentity, other_macs: set[str], other_protos: set[str]
) -> bool:
    return bool(
        (c_macs and target.macs and not (c_macs & target.macs) and (c_macs & other_macs))
        or (c_protos and target.protocol_ids and not (c_protos & target.protocol_ids) and (c_protos & other_protos))
    )


def _collect_bound_peer_ma_links(
    hass: HomeAssistant, exclude_esp_id: str | None, all_ma_ids: set[str], *, exclude_coord: Any = None
) -> tuple[set[str], set[str]]:
    claimed, bound_esp_ids, seen_esp_ids = set[str](), set[str](), set[str]()
    for c in iter_coordinators(hass):
        if c is exclude_coord:
            continue
        c_esp_id = str(getattr(c, "esphome_device_id", "") or "").strip()
        if exclude_esp_id and c_esp_id == exclude_esp_id:
            continue
        if c_esp_id:
            seen_esp_ids.add(c_esp_id)
        saved_ma = str(c.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip()
        if saved_ma and saved_ma in all_ma_ids and (
            _is_entity_live(hass, saved_ma) or not _is_entity_live(hass, str(getattr(c, "local_speaker", "") or ""))
        ):
            claimed.add(saved_ma)
            if c_esp_id:
                bound_esp_ids.add(c_esp_id)

    for entry in hass.config_entries.async_entries(DOMAIN):
        for sub in entry.subentries.values():
            if sub.subentry_type != SUBENTRY_DEVICE:
                continue
            s_esp_id = str(sub.data.get(CONF_ESPHOME_DEVICE_ID) or "").strip()
            if not s_esp_id or s_esp_id in seen_esp_ids or (exclude_esp_id and s_esp_id == exclude_esp_id):
                continue
            saved_ma = str(sub.data.get(CONF_MA_PLAYER_ENTITY) or "").strip()
            if saved_ma and saved_ma in all_ma_ids and (
                _is_entity_live(hass, saved_ma)
                or not _is_entity_live(hass, resolve_esphome_local_speaker(hass, s_esp_id))
            ):
                claimed.add(saved_ma)
                bound_esp_ids.add(s_esp_id)
    return claimed, bound_esp_ids


def _non_conflicting_model_tuples(
    rows: Sequence[CandidateRow], claimed: set[str], target: _DeviceTargetIdentity
) -> list[tuple[str, str | None, str | None]]:
    return [
        (c_entry.entity_id, c_dev.manufacturer if c_dev else None, c_dev.model if c_dev else None)
        for c_entry, c_dev, c_macs, _c_ha_ents, c_protos in rows
        if c_entry.entity_id not in claimed
        and not _conflicts_with_target(c_macs, c_protos, target.macs, target.protocol_ids)
    ]


def _match_unique_model_bijection(
    hass: HomeAssistant,
    esp_dev: DeviceEntry | None,
    target: _DeviceTargetIdentity,
    live_candidates: Sequence[CandidateRow],
    peers: tuple[set[str], set[str]],
) -> str | None:
    if esp_dev is None or not esp_dev.manufacturer or not esp_dev.model:
        return None
    claimed_by_others, bound_peer_esp_ids = peers
    dev_reg = dr.async_get(hass)
    same_model_esp_ids = {
        d_esp.id
        for esp_ce in hass.config_entries.async_entries("esphome")
        for d_esp in dr.async_entries_for_config_entry(dev_reg, esp_ce.entry_id)
        if d_esp.manufacturer == esp_dev.manufacturer and d_esp.model == esp_dev.model
    } | {esp_dev.id}
    if len(same_model_esp_ids - (bound_peer_esp_ids - {esp_dev.id})) != 1:
        return None
    return suggest_ma_player(
        (esp_dev.manufacturer, esp_dev.model),
        _non_conflicting_model_tuples(live_candidates, claimed_by_others, target),
    )


def discover_ma_player_for_device(hass: HomeAssistant, esphome_device_id: str | None) -> str:
    """Auto-discover the Music Assistant player for a bound ESPHome device during onboarding or reset."""
    esp_dev = get_bound_esphome_device(hass, esphome_device_id)
    if esp_dev is None or not hass.config_entries.async_entries("music_assistant"):
        return ""
    local_spk = resolve_esphome_local_speaker(hass, esp_dev.id)
    target = _collect_device_target_identity(hass, speaker_entity_id=local_spk, esphome_device_id=esp_dev.id)
    live_candidates, offline_candidates = _build_ma_candidates(hass)
    if matched := _match_ma_by_identity(live_candidates, target) or _match_ma_by_identity(offline_candidates, target):
        return matched
    all_ma_ids = {row[0].entity_id for row in [*live_candidates, *offline_candidates]}
    peers = _collect_bound_peer_ma_links(hass, esp_dev.id, all_ma_ids)
    return _match_unique_model_bijection(hass, esp_dev, target, live_candidates, peers) or ""


def suggest_ma_player_for(hass: HomeAssistant, coordinator: Any) -> str | None:
    """Suggest the MA player for one Coordinator by exact identity first, else unclaimed `(manufacturer, model)` (`M-P2-22`)."""
    if (esp_dev := get_bound_esphome_device(hass, getattr(coordinator, "esphome_device_id", None))) is None:
        return None
    local_spk = str(getattr(coordinator, "local_speaker", "") or "")
    target = _collect_device_target_identity(
        hass, speaker_entity_id=local_spk, owner_coord=coordinator, esphome_device_id=esp_dev.id
    )
    live_candidates, offline_candidates = _build_ma_candidates(hass)
    if exact := _match_ma_by_identity(live_candidates, target) or _match_ma_by_identity(offline_candidates, target):
        return exact
    all_ma_ids = {row[0].entity_id for row in [*live_candidates, *offline_candidates]}
    claimed_by_others, _ = _collect_bound_peer_ma_links(
        hass, esp_dev.id, all_ma_ids, exclude_coord=coordinator
    )
    pool = [r for r in live_candidates if r[0].entity_id not in claimed_by_others] or [
        r for r in offline_candidates if r[0].entity_id not in claimed_by_others
    ]
    return suggest_ma_player(
        (esp_dev.manufacturer, esp_dev.model),
        _non_conflicting_model_tuples(pool, claimed_by_others, target),
    )


@callback
def async_refresh_ma_link(hass: HomeAssistant, coordinator: Any) -> str:
    """Drop cached counterparts, re-resolve this Device's link, and rebind its speaker listener."""
    if isinstance(domain_data := hass.data.get(DOMAIN), dict) and isinstance(
        cache := domain_data.get("_ma_counterpart_cache"), dict
    ):
        cache.clear()
    local_spk = str(getattr(coordinator, "local_speaker", "") or "")
    resolved = (resolve_ma_counterpart_entity(hass, local_spk) or "") if local_spk else ""
    if (
        _SPEAKER_REBIND_CALLBACK is not None
        and hasattr(coordinator, "replace_speaker_state_unsub")
        and getattr(coordinator, "active_speaker", None)
    ):
        _SPEAKER_REBIND_CALLBACK(coordinator)
    return resolved


@callback
def async_set_ma_player_link(hass: HomeAssistant, coordinator: Any, ma_entity_id: str) -> None:
    """Save the Device's Music Assistant player link to its subentry and re-resolve."""
    coordinator.update_device_config({**coordinator.device_data, CONF_MA_PLAYER_ENTITY: ma_entity_id})
    async_refresh_ma_link(hass, coordinator)


@callback
def _heal_single_coordinator_ma_link(
    hass: HomeAssistant,
    coord: Any,
    live_candidates: list[CandidateRow],
    offline_candidates: list[CandidateRow],
    cand_ident_by_id: dict[str, tuple[set[str], set[str]]],
) -> None:
    if not (local_spk := str(getattr(coord, "local_speaker", "") or "")):
        return
    target = _collect_device_target_identity(hass, speaker_entity_id=local_spk, owner_coord=coord)
    exact_ma = _match_ma_by_identity(live_candidates, target) or _match_ma_by_identity(offline_candidates, target)
    resolved_ma = resolve_ma_counterpart_entity(hass, local_spk)
    saved_ma = str(coord.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip()
    saved_macs, saved_protos = cand_ident_by_id.get(saved_ma, (set(), set())) if saved_ma else (set(), set())
    other_esp_macs, other_esp_protos = (
        _collect_other_esphome_identities(hass, target.dev_ids)
        if (saved_macs and target.macs) or (saved_protos and target.protocol_ids)
        else (set(), set())
    )
    saved_cross_linked = _belongs_to_other_esphome(
        saved_macs, saved_protos, target, other_esp_macs, other_esp_protos
    )
    should_persist = bool(
        resolved_ma
        and (
            (not saved_ma and (resolved_ma == exact_ma or _is_entity_live(hass, resolved_ma)))
            or (
                saved_ma
                and saved_ma != resolved_ma
                and (_is_entity_live(hass, resolved_ma) or (saved_cross_linked and resolved_ma == exact_ma))
            )
        )
    )
    if should_persist and resolved_ma:
        _LOGGER.info("Updated Music Assistant player link for '%s': %s", getattr(coord, "device_slug", local_spk), resolved_ma)
        coord.update_device_config({**coord.device_data, CONF_MA_PLAYER_ENTITY: resolved_ma}, bump_prefs_seq=False)

    active_spk = str(getattr(coord, "active_speaker", "") or "")
    desired_tracked_ma = resolve_ma_counterpart_entity(hass, active_spk) if active_spk else None
    if (
        active_spk
        and _SPEAKER_REBIND_CALLBACK is not None
        and hasattr(coord, "replace_speaker_state_unsub")
        and getattr(coord, "tracked_ma_counterpart", None) != desired_tracked_ma
    ):
        _SPEAKER_REBIND_CALLBACK(coord)
        if hasattr(coord, "async_notify_listeners"):
            coord.async_notify_listeners()
    elif should_persist and hasattr(coord, "async_notify_listeners"):
        coord.async_notify_listeners()


@callback
def async_heal_coordinator_ma_links(hass: HomeAssistant) -> None:
    """Auto-persist newly discovered Sendspin/MAC-matched MA links and heal stale/cross-linked subentry links."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_healing_ma_links"):
        return
    domain_data["_healing_ma_links"] = True
    try:
        if isinstance(cache := domain_data.get("_ma_counterpart_cache"), dict):
            cache.clear()
        live_candidates, offline_candidates = _build_ma_candidates(hass)
        cand_ident_by_id = {
            c_entry.entity_id: (c_macs, c_protos)
            for c_entry, _c_dev, c_macs, _c_ha_ents, c_protos in [*live_candidates, *offline_candidates]
        }
        for coord in list(iter_coordinators(hass)):
            _heal_single_coordinator_ma_link(hass, coord, live_candidates, offline_candidates, cand_ident_by_id)
    finally:
        domain_data.pop("_healing_ma_links", None)


def _lookup_counterpart_cache(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    cache: dict[str, tuple[str | None, bool, float]],
    speaker_entity_id: str,
) -> tuple[bool, str | None]:
    cached_val = cache.get(speaker_entity_id)
    if not isinstance(cached_val, tuple) or len(cached_val) != _CACHE_TUPLE_LEN:
        cache.pop(speaker_entity_id, None)
        return False, None
    cached_ent, cached_live, cached_at = cached_val
    if cached_live:
        if cached_ent and ent_reg.async_get(cached_ent) is not None and _is_entity_live(hass, cached_ent):
            return True, cached_ent
    elif (time.monotonic() - cached_at) < _MA_OFFLINE_CACHE_TTL_SECONDS and (
        cached_ent is None or (ent_reg.async_get(cached_ent) is not None and not _is_entity_live(hass, cached_ent))
    ):
        return True, cached_ent
    cache.pop(speaker_entity_id, None)
    return False, None


def _resolve_live_ma_match(ctx: _MaResolveCtx) -> str | None:
    if ctx.raw_configured and (
        matched := configured_link(
            ctx.raw_configured,
            (
                c_entry.entity_id
                for c_entry, _c_dev, c_macs, _c_ha_ents, c_protos in ctx.live_candidates
                if not _belongs_to_other_esphome(c_macs, c_protos, ctx.target, ctx.other_esp_macs, ctx.other_esp_protos)
            ),
        )
    ):
        return matched
    if not ctx.live_candidates:
        return None
    if matched := _match_ma_by_identity(ctx.live_candidates, ctx.target):
        return matched
    esp_dev = (
        get_bound_esphome_device(ctx.hass, getattr(ctx.owner_coord, "esphome_device_id", None))
        if ctx.owner_coord is not None
        else (ctx.target.spk_dev if ctx.spk_entry is not None and ctx.spk_entry.platform == "esphome" else None)
    )
    all_ma_ids = {row[0].entity_id for row in [*ctx.live_candidates, *ctx.offline_candidates]}
    peers = _collect_bound_peer_ma_links(
        ctx.hass, esp_dev.id if esp_dev is not None else None, all_ma_ids, exclude_coord=ctx.owner_coord
    )
    return _match_unique_model_bijection(ctx.hass, esp_dev, ctx.target, ctx.live_candidates, peers)


def _resolve_offline_ma_match(ctx: _MaResolveCtx) -> str | None:
    if not ctx.offline_candidates:
        return None
    if ctx.raw_configured:
        both_online = _is_entity_live(ctx.hass, ctx.speaker_entity_id) and bool(ctx.live_candidates)
        fallback_pool = (
            [r for r in ctx.offline_candidates if ctx.hass.states.get(r[0].entity_id) is None or ctx.in_reconnect_grace]
            if both_online
            else ctx.offline_candidates
        )
        if matched := configured_link(
            ctx.raw_configured,
            (
                c_entry.entity_id
                for c_entry, _c_dev, c_macs, _c_ha_ents, c_protos in fallback_pool
                if not _belongs_to_other_esphome(c_macs, c_protos, ctx.target, ctx.other_esp_macs, ctx.other_esp_protos)
            ),
        ):
            return matched
    return _match_ma_by_identity(ctx.offline_candidates, ctx.target)


def resolve_ma_counterpart_entity(hass: HomeAssistant, speaker_entity_id: str) -> str | None:
    """Find the Music Assistant `media_player` for a speaker by explicit link, `device_id`, Sendspin/MAC, or bijection."""
    if not speaker_entity_id:
        return None
    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(speaker_entity_id)
    if spk_entry is not None and spk_entry.platform == "music_assistant":
        return speaker_entity_id

    _ensure_ma_cache_listeners(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    cache: dict[str, tuple[str | None, bool, float]] = domain_data.setdefault("_ma_counterpart_cache", {})
    if speaker_entity_id in cache:
        hit, cached_ent = _lookup_counterpart_cache(hass, ent_reg, cache, speaker_entity_id)
        if hit:
            return cached_ent

    owner_coord: Any = next(
        (coord for coord in iter_coordinators(hass) if getattr(coord, "local_speaker", None) == speaker_entity_id),
        None,
    )
    target = _collect_device_target_identity(hass, speaker_entity_id=speaker_entity_id, owner_coord=owner_coord)
    live_candidates, offline_candidates = _build_ma_candidates(hass)
    raw_configured = str(owner_coord.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip() if owner_coord is not None else ""
    other_esp_macs, other_esp_protos = (
        _collect_other_esphome_identities(hass, target.dev_ids)
        if raw_configured and (target.macs or target.protocol_ids)
        else (set(), set())
    )
    ctx = _MaResolveCtx(
        hass, speaker_entity_id, spk_entry, owner_coord, target, live_candidates, offline_candidates,
        raw_configured, other_esp_macs, other_esp_protos,
    )
    matched_entity = _resolve_live_ma_match(ctx)
    if matched_entity is None and target.pending_sendspin:
        _arm_ma_reconnect_grace(hass, speaker_entity_id)
    ctx.in_reconnect_grace = _in_ma_reconnect_grace(hass, speaker_entity_id, raw_configured)
    if matched_entity is None:
        matched_entity = _resolve_offline_ma_match(ctx)

    if owner_coord is not None:
        if matched_entity is not None or not hass.config_entries.async_entries("music_assistant"):
            _update_ma_link_issue(hass, owner_coord, speaker_entity_id, True)
        elif not ctx.in_reconnect_grace:
            _update_ma_link_issue(hass, owner_coord, speaker_entity_id, False)

    is_live = matched_entity is not None and _is_entity_live(hass, matched_entity)
    cache[speaker_entity_id] = (matched_entity, is_live, time.monotonic())
    return matched_entity
