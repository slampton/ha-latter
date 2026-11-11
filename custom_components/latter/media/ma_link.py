"""Linking a Latter Device to its Music Assistant counterpart player.

Matches strictly by:
0. Explicit `ma_player_entity` configured on the Device subentry
1. Exact `device_id` (or `via_device_id`) match in the Home Assistant registry
2. Exact MAC address match in device connections / identifiers
Else returns `None` and raises the `link_ma_player` Repair for a Latter Device's speaker.
Never matches by slug or substring.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import TYPE_CHECKING, Any

from ..const import CONF_MA_PLAYER_ENTITY, DOMAIN
from ..core.issue_ids import link_ma_player_issue_id

try:
    from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
    from homeassistant.core import Event, HomeAssistant, callback
    from homeassistant.helpers import (
        device_registry as dr,
        entity_registry as er,
        issue_registry as ir,
    )
except ImportError:  # pragma: no cover - pure-stdlib unit test fallback
    STATE_UNAVAILABLE = "unavailable"
    STATE_UNKNOWN = "unknown"
    Event = Any  # type: ignore[misc,assignment]
    HomeAssistant = Any  # type: ignore[misc,assignment]
    dr = None  # type: ignore[assignment]
    er = None  # type: ignore[assignment]
    ir = None  # type: ignore[assignment]

    def callback(func: Any) -> Any:  # type: ignore[misc]
        """Fallback decorator when Home Assistant is not imported."""
        return func

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry
    from homeassistant.helpers.entity_registry import RegistryEntry

_MAC_TOKEN_RE = re.compile(
    r"(?:^|[^0-9a-fA-F])((?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12})(?:$|[^0-9a-fA-F])"
)


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
    if not raw or dr is None:
        return set()
    out: set[str] = set()
    for match in _MAC_TOKEN_RE.finditer(str(raw)):
        token = match.group(1)
        if token:
            out.add(dr.format_mac(token))
    return out


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


def resolve_esphome_local_speaker(
    hass: HomeAssistant, esphome_device_id: str | None
) -> str:
    """Resolve the on-device media_player entity for the bound ESPHome node, or '' if the device has no speaker."""
    from ..core.identity import (
        device_entities,
        find_device_entity_by_suffix,
        get_bound_esphome_device,
    )

    dev = get_bound_esphome_device(hass, esphome_device_id)
    if dev is None:
        return ""
    by_suffix = find_device_entity_by_suffix(
        hass, dev.id, "media_player", ("_music", "_speaker", "_media_player")
    )
    if by_suffix:
        return by_suffix
    for entry in device_entities(hass, dev.id, domain="media_player"):
        if entry.platform == "esphome":
            return entry.entity_id
    return ""


def _iter_coordinators(hass: HomeAssistant) -> list[Any]:
    """Return all active LatterCoordinator instances across hub and domain_data."""
    from ..core.hub import get_latter_system

    out: list[Any] = []
    seen: set[int] = set()
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        for coord in sys_obj.coordinators.values():
            seen.add(id(coord))
            out.append(coord)
    domain_data = hass.data.get(DOMAIN, {})
    if isinstance(domain_data, dict):
        for val in domain_data.values():
            if hasattr(val, "device_slug") and id(val) not in seen:
                seen.add(id(val))
                out.append(val)
    return out


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


def suggest_ma_player_for(hass: HomeAssistant, coordinator: Any) -> str | None:
    """Suggest the MA player whose device's manufacturer AND model equal the bound ESPHome device's."""
    from ..core.identity import get_bound_esphome_device

    esp_dev = get_bound_esphome_device(
        hass, getattr(coordinator, "esphome_device_id", None)
    )
    if esp_dev is None:
        return None
    dev_reg = dr.async_get(hass)
    candidates: list[tuple[str, str | None, str | None]] = []
    for entry in ma_player_entities(hass):
        c_dev = dev_reg.async_get(entry.device_id) if entry.device_id else None
        candidates.append(
            (
                entry.entity_id,
                c_dev.manufacturer if c_dev is not None else None,
                c_dev.model if c_dev is not None else None,
            )
        )
    return suggest_ma_player((esp_dev.manufacturer, esp_dev.model), candidates)


@callback
def async_refresh_ma_link(hass: HomeAssistant, coordinator: Any) -> str:
    """Drop cached counterparts and re-resolve this Device's link (raises or clears its repair)."""
    domain_data = hass.data.get(DOMAIN, {})
    cache = (
        domain_data.get("_ma_counterpart_cache")
        if isinstance(domain_data, dict)
        else None
    )
    if isinstance(cache, dict):
        cache.clear()
    local_spk = str(getattr(coordinator, "local_speaker", "") or "")
    return (resolve_ma_counterpart_entity(hass, local_spk) or "") if local_spk else ""


@callback
def async_set_ma_player_link(
    hass: HomeAssistant, coordinator: Any, ma_entity_id: str
) -> None:
    """Save the Device's Music Assistant player link to its subentry and re-resolve."""
    coordinator.update_device_config(
        {**coordinator.device_data, CONF_MA_PLAYER_ENTITY: ma_entity_id}
    )
    async_refresh_ma_link(hass, coordinator)


def resolve_ma_counterpart_entity(
    hass: HomeAssistant, speaker_entity_id: str
) -> str | None:
    """Find the Music Assistant media_player for a speaker by explicit link, exact device_id, or exact MAC; else None."""
    if not speaker_entity_id:
        return None

    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(speaker_entity_id)
    if spk_entry is not None and spk_entry.platform == "music_assistant":
        return speaker_entity_id

    _ensure_ma_cache_listeners(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    cache: dict[str, str | None] = domain_data.setdefault("_ma_counterpart_cache", {})
    if speaker_entity_id in cache:
        cached_ent = cache[speaker_entity_id]
        if cached_ent is not None and ent_reg.async_get(cached_ent) is not None:
            return cached_ent
        cache.pop(speaker_entity_id, None)

    dev_reg = dr.async_get(hass)
    target_dev_ids: set[str] = set()
    target_macs: set[str] = set()

    owner_coord: Any = next(
        (
            coord
            for coord in _iter_coordinators(hass)
            if getattr(coord, "local_speaker", None) == speaker_entity_id
        ),
        None,
    )

    if spk_entry is not None:
        if spk_entry.device_id:
            target_dev_ids.add(spk_entry.device_id)
        spk_dev = (
            dev_reg.async_get(spk_entry.device_id) if spk_entry.device_id else None
        )
        target_macs.update(_extract_macs_from_device_or_entry(spk_dev, spk_entry))

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

    ma_candidates: list[tuple[RegistryEntry, DeviceEntry | None]] = []
    for entry in ma_player_entities(hass):
        c_dev = dev_reg.async_get(entry.device_id) if entry.device_id else None
        st = hass.states.get(entry.entity_id)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            ma_candidates.insert(0, (entry, c_dev))
        else:
            ma_candidates.append((entry, c_dev))

    matched_entity: str | None = None

    # Pass 0: explicit configured link on the Device subentry
    if owner_coord is not None:
        matched_entity = configured_link(
            owner_coord.get_opt(CONF_MA_PLAYER_ENTITY),
            (c_entry.entity_id for c_entry, _c_dev in ma_candidates),
        )

    # Pass 1: exact device_id (or via_device_id) match
    if matched_entity is None and target_dev_ids:
        for c_entry, c_dev in ma_candidates:
            if c_entry.device_id and (
                c_entry.device_id in target_dev_ids
                or (c_dev is not None and c_dev.via_device_id in target_dev_ids)
            ):
                matched_entity = c_entry.entity_id
                break

    # Pass 2: exact MAC match
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

    if matched_entity is not None:
        cache[speaker_entity_id] = matched_entity
    return matched_entity
