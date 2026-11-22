"""Single-pass BLE advertisement indexing and phone/tag candidate discovery (`L1b`, `M-P2-19`)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from ..const import normalize_device_slug
from .ble_math import safe_rssi_int
from .ble_registry import (
    APPLE_COMPANY_ID,
    IBEACON_PREFIX,
    TRAILING_ROTATING_HEX4_RE,
    classify_ble_advertisement_kind,
    current_ble_scanners,
    extract_ibeacon_entity_identity,
    extract_uuid16,
    format_uuid_dashed,
    int_to_mac,
    iter_entities,
    mac_to_int,
    normalize_mfg_map,
    parse_ibeacon_identity,
    resolve_scanner_area_id,
)

_IBEACON_MIN_BYTES, _IBEACON_FULL_BYTES = 20, 22
_EDDYSTONE_UID_MIN_BYTES: Final = 18
_EDDYSTONE_FRAME_MASK, _EDDYSTONE_UID_FRAME, _GOOGLE_FMDN_FRAME = 0xF0, 0x00, 0x40
_APPLE_FIND_MY_TYPE: Final = 0x12
_UUID_HEX_LEN, _EDDYSTONE_NS_HEX_LEN = 32, 20
_PAIR_TUPLE_LEN, _MAX_DISCOVERED_CANDIDATES, _MISSING_RSSI_SENTINEL = 2, 60, -999
_HEX_CHARS: Final = "0123456789abcdef"

_SPECIFIC_LOCAL_TAG_LABELS: Final[frozenset[str]] = frozenset(
    {"Tile Tracker", "iTag Keychain Tag", "Shelly BLU Tag (BTHome v2)", "BTHome v2 Tag", "RuuviTag Beacon", "Eddystone-UID Beacon"}
)
_BTHOME_TAG_LABELS: Final[frozenset[str]] = frozenset({"Shelly BLU Tag (BTHome v2)", "BTHome v2 Tag"})
_COMPANION_INACTIVE_STATES: Final[frozenset[str]] = frozenset({"disabled", "stopped", "off", "unavailable"})
_ENTITY_FRIENDLY_SUFFIXES: Final[tuple[str, ...]] = (
    " Estimated Distance", " Signal Strength", "Signal Strength", " Battery", " Motion", " Button",
)
_RAW_PREFIX_LABELS: Final[tuple[tuple[str, str], ...]] = (
    ("bthome:", "BTHome v2 Tag"), ("eddystone:", "Eddystone-UID Beacon"), ("ibeacon:", "iBeacon Tag"),
)


@dataclass
class _LiveBleIndex:
    """Single-pass index of live advertisements across all Home Assistant Bluetooth scanners."""

    by_mac: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_ibeacon: dict[tuple[str, int | None, int | None], dict[str, Any]] = field(default_factory=dict)
    eddystone_uids: set[str] = field(default_factory=set)


@dataclass
class _DiscoveryCtx:
    """Shared registries, single-pass live index, and deduplication sets for BLE discovery."""

    hass: HomeAssistant
    dev_reg: dr.DeviceRegistry
    area_reg: ar.AreaRegistry
    live_index: _LiveBleIndex
    onboarded_slugs: set[str]
    seen_targets: set[str]
    onboarded_ibeacons: set[tuple[str, int | None, int | None]]
    onboarded_uuid_only: set[str]
    companion_beacons: set[tuple[str, int | None, int | None]] = field(default_factory=set)

    def ibeacon_covered(self, u_hex: str, maj: int | None, min_: int | None) -> bool:
        u_dashed = format_uuid_dashed(u_hex)
        return (
            (u_hex, maj, min_) in self.companion_beacons
            or (u_hex, None, None) in self.companion_beacons
            or (maj is None and min_ is None and any(cu == u_hex for cu, _, _ in self.companion_beacons))
            or (u_hex, maj, min_) in self.onboarded_ibeacons
            or u_hex in self.onboarded_uuid_only
            or u_hex in self.seen_targets
            or u_dashed.lower() in self.seen_targets
        )


def _is_excluded_cloud_find_adv(
    local_name: str, mfg_data: Mapping[int, bytes], service_data: Mapping[str, bytes]
) -> bool:
    for raw_k, raw_v in (service_data or {}).items():
        if (
            extract_uuid16(str(raw_k)) == "feaa"
            and isinstance(raw_v, (bytes, bytearray))
            and len(raw_v) >= 1
            and (raw_v[0] & _EDDYSTONE_FRAME_MASK) == _GOOGLE_FMDN_FRAME
        ):
            return True
    apple_payload = normalize_mfg_map(mfg_data).get(APPLE_COMPANY_ID)
    return bool(
        apple_payload is not None
        and len(apple_payload) >= 1
        and apple_payload[0] == _APPLE_FIND_MY_TYPE
        and not local_name
    )


def _extract_eddystone_uid_hex(service_data: Mapping[str, bytes]) -> str:
    for k_svc, v_svc in service_data.items():
        if (
            extract_uuid16(k_svc) == "feaa"
            and isinstance(v_svc, (bytes, bytearray))
            and len(v_svc) >= _EDDYSTONE_UID_MIN_BYTES
            and (v_svc[0] & _EDDYSTONE_FRAME_MASK) == _EDDYSTONE_UID_FRAME
        ):
            return bytes(v_svc[2:18]).hex().lower()
    return ""


def _record_mac_adv(
    by_mac: dict[str, dict[str, Any]], addr_str: str, entry_fields: dict[str, Any]
) -> None:
    rssi_int: int | None = entry_fields["rssi"]
    prev = by_mac.get(addr_str)
    if prev is None or (rssi_int is not None and (prev["rssi"] is None or rssi_int > prev["rssi"])):
        by_mac[addr_str] = {
            "mac": addr_str,
            "local_name": entry_fields["local_name"] or (prev["local_name"] if prev else ""),
            "mfg_data": entry_fields["mfg_data"] or (prev["mfg_data"] if prev else {}),
            "service_data": entry_fields["service_data"] or (prev["service_data"] if prev else {}),
            "service_uuids": entry_fields["service_uuids"] or (prev["service_uuids"] if prev else ()),
            "rssi": rssi_int,
            "area_name": entry_fields["area_name"],
            "scanner": entry_fields["scanner"],
            "source": entry_fields["source"],
        }
    elif prev is not None:
        for key in ("local_name", "mfg_data", "service_data", "service_uuids"):
            if entry_fields[key] and not prev[key]:
                prev[key] = entry_fields[key]


def _record_ibeacon_adv(
    by_ibeacon: dict[tuple[str, int | None, int | None], dict[str, Any]],
    mfg_map: Mapping[int, bytes],
    ib_info: dict[str, Any],
) -> None:
    apple_b = mfg_map.get(APPLE_COMPANY_ID)
    if apple_b is None or len(apple_b) < _IBEACON_MIN_BYTES or apple_b[:2] != IBEACON_PREFIX:
        return
    ib_uuid = apple_b[2:18].hex().lower()
    ib_maj = (apple_b[18] << 8) | apple_b[19]
    ib_min = ((apple_b[20] << 8) | apple_b[21]) if len(apple_b) >= _IBEACON_FULL_BYTES else None
    rssi_int: int | None = ib_info["rssi"]
    for ib_k in ((ib_uuid, ib_maj, ib_min), (ib_uuid, None, None)):
        prev_ib = by_ibeacon.get(ib_k)
        if prev_ib is None or (
            rssi_int is not None and (prev_ib["rssi"] is None or rssi_int > prev_ib["rssi"])
        ):
            by_ibeacon[ib_k] = ib_info


def _index_live_ble_advertisements(hass: HomeAssistant) -> _LiveBleIndex:
    """Scan HA Bluetooth scanners in ONE single `O(Ads)` pass (`M-P2-19`)."""
    index = _LiveBleIndex()
    area_reg = ar.async_get(hass)
    scanner_area_memo: dict[str, str] = {}

    for scanner in current_ble_scanners(hass):
        source = str(getattr(scanner, "source", "") or "")
        scanner_name = str(getattr(scanner, "name", "") or source)
        if source in scanner_area_memo:
            area_name = scanner_area_memo[source]
        else:
            a_id = resolve_scanner_area_id(hass, source) if source else None
            a_obj = area_reg.async_get_area(a_id) if a_id else None
            area_name = a_obj.name if a_obj else ""
            if source:
                scanner_area_memo[source] = area_name

        dev_adv_map: dict[str, tuple[Any, Any]] = (
            getattr(scanner, "discovered_devices_and_advertisement_data", None) or {}
        )
        for addr, pair in dev_adv_map.items():
            if not isinstance(pair, tuple) or len(pair) != _PAIR_TUPLE_LEN:
                continue
            ble_dev, adv_data = pair
            addr_str = str(addr or "").strip().upper()
            if not addr_str:
                continue
            local_name = str(
                getattr(adv_data, "local_name", "") or getattr(ble_dev, "name", "") or ""
            ).strip()
            if local_name and (
                local_name.replace(":", "").replace("-", "").upper()
                == addr_str.replace(":", "").replace("-", "")
            ):
                local_name = ""

            mfg_map = normalize_mfg_map(getattr(adv_data, "manufacturer_data", None) or {})
            raw_svc = getattr(adv_data, "service_data", None) or {}
            svc_data = {str(k): bytes(v) for k, v in raw_svc.items() if isinstance(v, (bytes, bytearray))}
            svc_uuids = tuple(str(u) for u in (getattr(adv_data, "service_uuids", None) or ()) if u)
            rssi_raw = getattr(adv_data, "rssi", None)
            rssi_int = safe_rssi_int(rssi_raw if rssi_raw is not None else getattr(ble_dev, "rssi", None))

            _record_mac_adv(
                index.by_mac,
                addr_str,
                {
                    "local_name": local_name,
                    "mfg_data": mfg_map,
                    "service_data": svc_data,
                    "service_uuids": svc_uuids,
                    "rssi": rssi_int,
                    "area_name": area_name,
                    "scanner": scanner_name,
                    "source": source,
                },
            )
            _record_ibeacon_adv(
                index.by_ibeacon,
                mfg_map,
                {"rssi": rssi_int, "area_name": area_name, "scanner": scanner_name, "mac": addr_str},
            )
            if ed_uid := _extract_eddystone_uid_hex(svc_data):
                index.eddystone_uids.add(ed_uid)
    return index


def _is_mobile_app_ble_emitter(entry: er.RegistryEntry) -> bool:
    if entry.platform != "mobile_app" or entry.domain != "sensor":
        return False
    uid = str(entry.unique_id or "").lower()
    eid = entry.entity_id.lower()
    return uid.endswith(("_ble_emitter", "_ble_transmitter")) or eid.endswith(
        ("_ble_transmitter", "_ble_emitter")
    )


def _classify_live_adv(live_adv: Mapping[str, Any], *, is_private_ble: bool = False) -> str:
    return classify_ble_advertisement_kind(
        live_adv["local_name"],
        live_adv["mfg_data"],
        live_adv["service_data"],
        live_adv["service_uuids"],
        is_private_ble=is_private_ble,
    )


def _describe_bthome_entity(hass: HomeAssistant, dev_entry: dr.DeviceEntry | None) -> str:
    if dev_entry is None:
        return "BTHome v2 Tag"
    live_index: _LiveBleIndex | None = None
    for _ct, cv in dev_entry.connections:
        if (m_int := mac_to_int(str(cv))) is None:
            continue
        if live_index is None:
            live_index = _index_live_ble_advertisements(hass)
        if (
            (live_adv := live_index.by_mac.get(int_to_mac(m_int))) is not None
            and (classified := _classify_live_adv(live_adv)) in _BTHOME_TAG_LABELS
        ):
            return classified
    dev_text = " ".join(
        str(x or "") for x in (dev_entry.manufacturer, dev_entry.model, dev_entry.name_by_user, dev_entry.name)
    ).lower()
    return "Shelly BLU Tag (BTHome v2)" if "shelly" in dev_text else "BTHome v2 Tag"


def _describe_entity_ble_target(hass: HomeAssistant, addr: str) -> str:
    ent_entry = er.async_get(hass).async_get(addr)
    got_dev = (
        dr.async_get(hass).async_get(ent_entry.device_id) if (ent_entry and ent_entry.device_id) else None
    )
    dev_entry = got_dev if isinstance(got_dev, dr.DeviceEntry) else None
    st = hass.states.get(addr)
    low = addr.lower()
    uid_low = str(ent_entry.unique_id or "").lower() if ent_entry is not None else ""

    if (
        (ent_entry is not None and ent_entry.platform == "mobile_app")
        or low.endswith(("_ble_transmitter", "_ble_emitter"))
        or uid_low.endswith("_ble_emitter")
    ):
        model_str = str(dev_entry.model or "").strip() if dev_entry else ""
        return f"{model_str} (HA Companion App)" if model_str else "HA Companion App"

    if (
        (ent_entry is not None and ent_entry.platform == "private_ble_device")
        or "private_ble" in low
        or (st is not None and st.attributes.get("current_address"))
    ):
        cur_mac = str((st.attributes.get("current_address") if st else "") or "").strip().upper()
        live_adv = _index_live_ble_advertisements(hass).by_mac.get(cur_mac) if cur_mac else None
        if live_adv is not None and (
            classified := _classify_live_adv(live_adv, is_private_ble=True)
        ) != "Phone or Watch (Private BLE / IRK)":
            return classified
        return "Private BLE (phone or watch)"

    if (ent_entry is not None and ent_entry.platform == "bthome") or ("bthome" in low):
        return _describe_bthome_entity(hass, dev_entry)
    if (ent_entry is not None and ent_entry.platform == "ibeacon") or (
        extract_ibeacon_entity_identity(hass, ent_entry, st) is not None
    ):
        return "iBeacon Tag"
    return "Private BLE (phone or watch)"


def _describe_mac_ble_target(hass: HomeAssistant, m_int: int) -> str:
    live_adv = _index_live_ble_advertisements(hass).by_mac.get(int_to_mac(m_int))
    if live_adv is None:
        return "BLE beacon or tag"
    if (classified := _classify_live_adv(live_adv)) in _SPECIFIC_LOCAL_TAG_LABELS:
        return classified
    apple_b = live_adv["mfg_data"].get(APPLE_COMPANY_ID)
    if apple_b is not None and len(apple_b) >= _IBEACON_MIN_BYTES and apple_b[:2] == IBEACON_PREFIX:
        return "iBeacon Tag"
    return "BLE beacon or tag"


def _describe_raw_ble_target(hass: HomeAssistant, addr: str) -> str:
    low = addr.lower()
    for prefix, label in _RAW_PREFIX_LABELS:
        if low.startswith(prefix):
            return label
    if (m_int := mac_to_int(addr)) is not None:
        return _describe_mac_ble_target(hass, m_int)

    hex_clean = low.replace("-", "")
    is_hex = bool(hex_clean) and all(ch in _HEX_CHARS for ch in hex_clean)
    if is_hex and len(hex_clean) == _UUID_HEX_LEN:
        is_eddystone = hex_clean in _index_live_ble_advertisements(hass).eddystone_uids or (
            "-" not in addr and ":" not in addr and "_" not in addr and addr == addr.upper()
        )
        return "Eddystone-UID Beacon" if is_eddystone else "iBeacon Tag"
    if is_hex and len(hex_clean) == _EDDYSTONE_NS_HEX_LEN:
        return "Eddystone-UID Beacon"
    return "iBeacon Tag" if parse_ibeacon_identity(addr) is not None else "BLE beacon or tag"


def describe_ble_target_model(hass: HomeAssistant, target_address: str) -> str:
    """Return a human-friendly model / tag classification label for a managed BLE tag."""
    addr = str(target_address or "").strip()
    if not addr:
        return "BLE beacon or tag"
    return _describe_entity_ble_target(hass, addr) if "." in addr else _describe_raw_ble_target(hass, addr)


def inspect_companion_ble_transmitter(
    hass: HomeAssistant, target_address: str
) -> dict[str, str] | None:
    """Return live state, TX power, and advertise mode when `target_address` is a Companion App BLE Transmitter."""
    addr = str(target_address or "").strip()
    if "." not in addr:
        return None
    ent_entry = er.async_get(hass).async_get(addr)
    is_companion = (
        _is_mobile_app_ble_emitter(ent_entry)
        if ent_entry is not None
        else addr.lower().endswith(("_ble_transmitter", "_ble_emitter"))
    )
    st = hass.states.get(addr) if is_companion else None
    if st is None:
        return None
    return {
        "state": str(st.state or "").strip(),
        "tx_power": str(
            st.attributes.get("Transmitting power") or st.attributes.get("transmitting_power") or ""
        ).strip(),
        "advertise_mode": str(
            st.attributes.get("Advertise mode") or st.attributes.get("advertise_mode") or ""
        ).strip(),
    }


def classify_ble_target_category(
    hass: HomeAssistant, target_address: str, configured_category: str = "auto"
) -> str:
    """Resolve a managed BLE subentry's effective category (`phone` vs `ble_tag`)."""
    cfg_norm = str(configured_category or "auto").strip().lower()
    if cfg_norm in ("phone", "ble_tag"):
        return cfg_norm

    addr = str(target_address or "").strip()
    if "." in addr:
        ent_entry = er.async_get(hass).async_get(addr)
        st = hass.states.get(addr)
        low = addr.lower()
        uid_low = str(ent_entry.unique_id or "").lower() if ent_entry is not None else ""
        if (
            (ent_entry is not None and ent_entry.platform == "mobile_app")
            or low.endswith(("_ble_transmitter", "_ble_emitter"))
            or uid_low.endswith("_ble_emitter")
        ):
            return "phone"
        if (
            (ent_entry is not None and ent_entry.platform == "private_ble_device")
            or "private_ble" in low
            or (st is not None and st.attributes.get("current_address"))
        ):
            return "ble_tag" if "airpods" in describe_ble_target_model(hass, addr).lower() else "phone"
    return "ble_tag"


def _collect_onboarded_targets(
    hass: HomeAssistant, ent_reg: er.EntityRegistry, onboarded_addresses: set[str]
) -> tuple[set[str], set[tuple[str, int | None, int | None]], set[str]]:
    seen_targets = {str(a).strip().lower() for a in onboarded_addresses if a and str(a).strip()}
    onboarded_ibeacons: set[tuple[str, int | None, int | None]] = set()
    onboarded_uuid_only: set[str] = set()
    for raw_onb in onboarded_addresses:
        clean_onb = str(raw_onb or "").strip()
        if not clean_onb:
            continue
        if "." in clean_onb:
            st_onb = hass.states.get(clean_onb)
            if (ib_onb := extract_ibeacon_entity_identity(hass, ent_reg.async_get(clean_onb), st_onb)) is not None:
                onboarded_ibeacons.add(ib_onb)
            if st_onb is not None:
                cur_onb_mac = str(
                    st_onb.attributes.get("current_address")
                    or st_onb.attributes.get("mac")
                    or st_onb.attributes.get("address")
                    or ""
                ).strip()
                if cur_onb_mac:
                    seen_targets.add(cur_onb_mac.lower())
        elif (ib_onb := parse_ibeacon_identity(clean_onb)) is not None:
            onboarded_ibeacons.add(ib_onb)
            if ib_onb[1] is None and ib_onb[2] is None:
                onboarded_uuid_only.add(ib_onb[0])
    return seen_targets, onboarded_ibeacons, onboarded_uuid_only


def _format_candidate_item(
    slug: str,
    title: str,
    target_address: str,
    kind_lbl: str,
    telemetry: tuple[bool, int | None, str, str],
) -> dict[str, Any]:
    is_tracker, rssi_int, area_name, scanner = telemetry
    rssi_str = f" ({rssi_int} dBm)" if rssi_int is not None else ""
    area_str = f" • {area_name}" if area_name else ""
    return {
        "slug": slug,
        "title": title,
        "target_address": target_address,
        "kind": kind_lbl,
        "is_tracker": is_tracker,
        "rssi": rssi_int,
        "area_name": area_name,
        "scanner": scanner,
        "label": f"{title} [{kind_lbl}]{rssi_str}{area_str}",
    }


def _resolve_companion_friendly_name(
    dev_reg: dr.DeviceRegistry, entry: er.RegistryEntry, st: Any
) -> str:
    if (
        entry.device_id
        and (dev_entry := dev_reg.async_get(entry.device_id)) is not None
        and (friendly := str(dev_entry.name_by_user or dev_entry.name or "").strip())
    ):
        return friendly
    friendly = (
        str(st.attributes.get("friendly_name") or "")
        or entry.name
        or entry.original_name
        or entry.entity_id
    ).strip()
    for sfx in (" BLE Transmitter", " BLE Emitter"):
        if friendly.lower().endswith(sfx.lower()):
            return friendly[: -len(sfx)].strip()
    return friendly


def _discover_companion_candidates(
    ctx: _DiscoveryCtx, all_entities: list[er.RegistryEntry]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entry in all_entities:
        if entry.disabled_by or not _is_mobile_app_ble_emitter(entry):
            continue
        st = ctx.hass.states.get(entry.entity_id)
        if st is None or str(st.state or "").strip().lower() in _COMPANION_INACTIVE_STATES:
            continue
        raw_id = str(st.attributes.get("id") or st.attributes.get("uuid") or "").strip()
        parsed_ib = (
            parse_ibeacon_identity(raw_id, st.attributes.get("major"), st.attributes.get("minor"))
            if raw_id
            else None
        )
        if parsed_ib is None:
            continue
        uuid_hex, maj, min_ = parsed_ib
        ctx.companion_beacons.add((uuid_hex, maj, min_))

        live_hit = ctx.live_index.by_ibeacon.get(
            (uuid_hex, maj, min_) if (maj is not None or min_ is not None) else (uuid_hex, None, None)
        )
        if live_hit is not None and live_hit.get("mac"):
            ctx.seen_targets.add(str(live_hit["mac"]).lower())

        uuid_dashed = format_uuid_dashed(uuid_hex)
        already_seen = (
            entry.entity_id.lower() in ctx.seen_targets
            or uuid_hex in ctx.seen_targets
            or uuid_dashed.lower() in ctx.seen_targets
            or (uuid_hex, maj, min_) in ctx.onboarded_ibeacons
            or uuid_hex in ctx.onboarded_uuid_only
        )
        ctx.seen_targets.add(entry.entity_id.lower())
        if already_seen:
            continue

        friendly = _resolve_companion_friendly_name(ctx.dev_reg, entry, st)
        cand_slug = normalize_device_slug(friendly)
        if not cand_slug or cand_slug == "esphome_device" or cand_slug in ctx.onboarded_slugs:
            continue

        mm_suffix = f" • {maj}:{min_}" if maj is not None and min_ is not None else ""
        tel = (
            True,
            live_hit["rssi"] if live_hit is not None else None,
            str(live_hit["area_name"]) if live_hit is not None else "",
            str(live_hit["scanner"]) if live_hit is not None else "",
        )
        candidates.append(
            _format_candidate_item(
                cand_slug, friendly, entry.entity_id, f"HA Companion App ({uuid_dashed}{mm_suffix})", tel
            )
        )
    return candidates


def _domain_rank(ent: er.RegistryEntry) -> int:
    return 0 if ent.domain == "device_tracker" else (1 if ent.domain == "sensor" else 2)


def _clean_entity_friendly(dev_reg: dr.DeviceRegistry, ent: er.RegistryEntry, st_obj: Any) -> str:
    dev_entry = dev_reg.async_get(ent.device_id) if ent.device_id else None
    if dev_entry is not None and dev_entry.name_by_user:
        return str(dev_entry.name_by_user).strip()
    friendly_raw = (
        str(st_obj.attributes.get("friendly_name") if st_obj else "")
        or ent.name
        or ent.original_name
        or (str(dev_entry.name or "") if dev_entry else "")
        or ent.entity_id
    ).strip()
    for suffix in _ENTITY_FRIENDLY_SUFFIXES:
        if friendly_raw.endswith(suffix):
            friendly_raw = friendly_raw[: -len(suffix)].strip()
    return friendly_raw


def _filter_and_dedupe_ble_entities(
    ctx: _DiscoveryCtx, all_entities: list[er.RegistryEntry]
) -> list[er.RegistryEntry]:
    by_dev_id: dict[tuple[str, str], list[er.RegistryEntry]] = {}
    devless_entries: list[er.RegistryEntry] = []
    for entry in all_entities:
        if entry.disabled_by or entry.platform not in ("private_ble_device", "ibeacon", "bthome"):
            continue
        if entry.domain not in ("device_tracker", "sensor", "binary_sensor"):
            continue
        if entry.platform != "bthome":
            if entry.domain == "binary_sensor" or (
                entry.domain == "sensor" and not entry.entity_id.endswith("estimated_distance")
            ):
                continue
        elif entry.domain in ("sensor", "binary_sensor") and not entry.entity_id.endswith(
            ("signal_strength", "battery", "motion", "button")
        ):
            continue
        if entry.device_id:
            by_dev_id.setdefault((entry.platform, entry.device_id), []).append(entry)
        else:
            devless_entries.append(entry)

    deduped: list[er.RegistryEntry] = []
    for grp_entries in by_dev_id.values():
        if any(e.entity_id.lower() in ctx.seen_targets for e in grp_entries):
            ctx.seen_targets.update(e.entity_id.lower() for e in grp_entries)
            continue
        grp_entries.sort(
            key=lambda e: (_domain_rank(e), ctx.hass.states.get(e.entity_id) is None, e.entity_id)
        )
        deduped.append(grp_entries[0])
    deduped.extend(devless_entries)
    return deduped


def _consolidate_ibeacon_entities(
    ctx: _DiscoveryCtx, deduped_entries: list[er.RegistryEntry]
) -> list[tuple[er.RegistryEntry, bool]]:
    ibeacon_groups: dict[
        tuple[str, int | None, int | None], list[tuple[er.RegistryEntry, Any, str, int | None]]
    ] = {}
    final_items: list[tuple[er.RegistryEntry, bool]] = []

    for entry in deduped_entries:
        if entry.platform != "ibeacon":
            final_items.append((entry, False))
            continue
        st = ctx.hass.states.get(entry.entity_id)
        ib_key = extract_ibeacon_entity_identity(ctx.hass, entry, st)
        if ib_key is None:
            final_items.append((entry, False))
            continue
        u_hex, maj, min_ = ib_key
        if ctx.ibeacon_covered(u_hex, maj, min_):
            ctx.seen_targets.add(entry.entity_id.lower())
            continue
        friendly_lbl = _clean_entity_friendly(ctx.dev_reg, entry, st)
        rssi_num = safe_rssi_int(st.attributes.get("rssi")) if st else None
        if rssi_num is None:
            live_ib = ctx.live_index.by_ibeacon.get(
                (u_hex, maj, min_) if (maj is not None or min_ is not None) else (u_hex, None, None)
            )
            if live_ib is not None:
                rssi_num = live_ib["rssi"]
        ibeacon_groups.setdefault(ib_key, []).append((entry, st, friendly_lbl, rssi_num))

    for ib_items in ibeacon_groups.values():
        if any(it[0].entity_id.lower() in ctx.seen_targets for it in ib_items):
            ctx.seen_targets.update(it[0].entity_id.lower() for it in ib_items)
            continue
        ib_items.sort(
            key=lambda it: (
                _domain_rank(it[0]),
                1 if TRAILING_ROTATING_HEX4_RE.search(it[2]) else 0,
                -(it[3] if it[3] is not None else _MISSING_RSSI_SENTINEL),
                it[0].entity_id,
            )
        )
        final_items.append((ib_items[0][0], len(ib_items) > 1))
    return final_items


def _resolve_bthome_candidate_telemetry(
    ctx: _DiscoveryCtx,
    entry: er.RegistryEntry,
    rssi_int: int | None,
    area_name: str,
    src_scanner: str,
) -> tuple[str, int | None, str, str]:
    kind_lbl = "BTHome v2 Tag"
    got_dev = ctx.dev_reg.async_get(entry.device_id) if entry.device_id else None
    if not isinstance(got_dev, dr.DeviceEntry):
        return kind_lbl, rssi_int, area_name, src_scanner
    for _ct, cv in got_dev.connections:
        m_int = mac_to_int(str(cv))
        if m_int is None:
            continue
        mac_fmt = int_to_mac(m_int)
        ctx.seen_targets.add(mac_fmt.lower())
        live_adv = ctx.live_index.by_mac.get(mac_fmt)
        if live_adv is None:
            continue
        classified_bt = _classify_live_adv(live_adv)
        if classified_bt in _BTHOME_TAG_LABELS:
            kind_lbl = classified_bt
        if rssi_int is None:
            rssi_int = live_adv["rssi"]
        area_name = area_name or str(live_adv["area_name"] or "")
        src_scanner = src_scanner or str(live_adv["scanner"] or "")
    return kind_lbl, rssi_int, area_name, src_scanner


def _resolve_entity_candidate_telemetry(
    ctx: _DiscoveryCtx, entry: er.RegistryEntry, st: Any
) -> tuple[str, int | None, str, str]:
    rssi_int = safe_rssi_int(st.attributes.get("rssi")) if st else None
    src_scanner = str(st.attributes.get("source") or "").strip() if st else ""
    a_id = resolve_scanner_area_id(ctx.hass, src_scanner) if src_scanner else None
    a_obj = ctx.area_reg.async_get_area(a_id) if a_id else None
    area_name = a_obj.name if a_obj else ""

    if entry.platform == "private_ble_device":
        cur_mac = str((st.attributes.get("current_address") if st else "") or "").strip().upper()
        if cur_mac:
            ctx.seen_targets.add(cur_mac.lower())
        live_adv = ctx.live_index.by_mac.get(cur_mac) if cur_mac else None
        if live_adv is None:
            return (
                classify_ble_advertisement_kind("", {}, {}, (), is_private_ble=True),
                rssi_int,
                area_name,
                src_scanner,
            )
        return (
            _classify_live_adv(live_adv, is_private_ble=True),
            rssi_int if rssi_int is not None else live_adv["rssi"],
            area_name or str(live_adv["area_name"] or ""),
            src_scanner or str(live_adv["scanner"] or ""),
        )

    if entry.platform == "bthome":
        return _resolve_bthome_candidate_telemetry(ctx, entry, rssi_int, area_name, src_scanner)

    ib_key = extract_ibeacon_entity_identity(ctx.hass, entry, st)
    if ib_key is None:
        return "iBeacon Tag", rssi_int, area_name, src_scanner
    u_hex, maj, min_ = ib_key
    live_ib = ctx.live_index.by_ibeacon.get(
        (u_hex, maj, min_) if (maj is not None or min_ is not None) else (u_hex, None, None)
    )
    if live_ib is not None:
        if live_ib.get("mac"):
            ctx.seen_targets.add(str(live_ib["mac"]).lower())
        if rssi_int is None:
            rssi_int = live_ib["rssi"]
        area_name = area_name or str(live_ib["area_name"] or "")
        src_scanner = src_scanner or str(live_ib["scanner"] or "")
    u_dashed = format_uuid_dashed(u_hex)
    mm = f" • {maj}:{min_}" if maj is not None and min_ is not None else ""
    return f"iBeacon Tag ({u_dashed}{mm})", rssi_int, area_name, src_scanner


def _unnamed_ambient_tag_title(kind_lbl: str, addr_str: str, eddystone_uid_target: str) -> str:
    suffix = addr_str[-5:]
    title_map = {
        "Tile Tracker": f"Tile Tracker {suffix}",
        "Shelly BLU Tag (BTHome v2)": f"Shelly BLU {suffix}",
        "BTHome v2 Tag": f"BTHome {suffix}",
        "RuuviTag Beacon": f"RuuviTag {suffix}",
        "iTag Keychain Tag": f"iTag {suffix}",
    }
    if kind_lbl in title_map:
        return title_map[kind_lbl]
    return f"Eddystone {suffix}" if (kind_lbl == "Eddystone-UID Beacon" and eddystone_uid_target) else ""


def _discover_ambient_scanner_candidates(ctx: _DiscoveryCtx) -> list[dict[str, Any]]:
    best_by_addr: dict[str, dict[str, Any]] = {}
    for addr_str, adv_entry in ctx.live_index.by_mac.items():
        local_name = str(adv_entry["local_name"] or "").strip()
        mfg_data: Mapping[int, bytes] = adv_entry["mfg_data"]
        svc_data: Mapping[str, bytes] = adv_entry["service_data"]
        svc_uuids: Iterable[str] = adv_entry["service_uuids"]
        if _is_excluded_cloud_find_adv(local_name, mfg_data, svc_data):
            continue

        apple_b = mfg_data.get(APPLE_COMPANY_ID)
        if apple_b is not None and len(apple_b) >= _IBEACON_MIN_BYTES and apple_b[:2] == IBEACON_PREFIX:
            ib_u = apple_b[2:18].hex().lower()
            ib_maj = (apple_b[18] << 8) | apple_b[19]
            ib_min = ((apple_b[20] << 8) | apple_b[21]) if len(apple_b) >= _IBEACON_FULL_BYTES else None
            if (
                (ib_u, ib_maj, ib_min) in ctx.companion_beacons
                or (ib_u, ib_maj, ib_min) in ctx.onboarded_ibeacons
                or ib_u in ctx.onboarded_uuid_only
            ):
                continue

        ed_uid = _extract_eddystone_uid_hex(svc_data)
        eddystone_uid_target = ed_uid.upper() if ed_uid else ""
        target_key = eddystone_uid_target or addr_str
        if target_key.lower() in ctx.seen_targets or addr_str.lower() in ctx.seen_targets:
            continue

        kind_lbl = classify_ble_advertisement_kind(
            local_name, mfg_data, svc_data, svc_uuids, is_private_ble=False
        )
        title = local_name or _unnamed_ambient_tag_title(kind_lbl, addr_str, eddystone_uid_target)
        cand_slug = normalize_device_slug(title) if title else ""
        if not cand_slug or cand_slug == "esphome_device" or cand_slug in ctx.onboarded_slugs:
            continue

        rssi_int: int | None = adv_entry["rssi"]
        prev = best_by_addr.get(target_key)
        if prev is None or (rssi_int is not None and (prev["rssi"] is None or rssi_int > prev["rssi"])):
            tel = (
                not kind_lbl.startswith("Named BLE"),
                rssi_int,
                str(adv_entry["area_name"] or ""),
                str(adv_entry["scanner"] or ""),
            )
            best_by_addr[target_key] = _format_candidate_item(cand_slug, title, target_key, kind_lbl, tel)

    for addr_str in best_by_addr:
        ctx.seen_targets.add(addr_str.lower())
    return list(best_by_addr.values())


def get_discovered_ble_candidates(
    hass: HomeAssistant, onboarded_slugs: set[str], onboarded_addresses: set[str]
) -> list[dict[str, Any]]:
    """Discover phones and BLE tags across HA Companion App, Private BLE, iBeacon, BTHome, and live scanners."""
    ent_reg = er.async_get(hass)
    seen_targets, onboarded_ibeacons, onboarded_uuid_only = _collect_onboarded_targets(
        hass, ent_reg, onboarded_addresses
    )
    ctx = _DiscoveryCtx(
        hass=hass,
        dev_reg=dr.async_get(hass),
        area_reg=ar.async_get(hass),
        live_index=_index_live_ble_advertisements(hass),
        onboarded_slugs=onboarded_slugs,
        seen_targets=seen_targets,
        onboarded_ibeacons=onboarded_ibeacons,
        onboarded_uuid_only=onboarded_uuid_only,
    )
    all_entities = iter_entities(ent_reg)
    candidates = _discover_companion_candidates(ctx, all_entities)
    final_entity_items = _consolidate_ibeacon_entities(
        ctx, _filter_and_dedupe_ble_entities(ctx, all_entities)
    )

    for entry, consolidated_dup in final_entity_items:
        st = hass.states.get(entry.entity_id)
        friendly = _clean_entity_friendly(ctx.dev_reg, entry, st)
        if consolidated_dup:
            friendly = TRAILING_ROTATING_HEX4_RE.sub("", friendly).strip() or friendly
        cand_slug = normalize_device_slug(friendly)
        if (
            not cand_slug
            or cand_slug == "esphome_device"
            or cand_slug in onboarded_slugs
            or entry.entity_id.lower() in ctx.seen_targets
        ):
            continue
        ctx.seen_targets.add(entry.entity_id.lower())
        kind_lbl, rssi_int, area_name, src_scanner = _resolve_entity_candidate_telemetry(ctx, entry, st)
        candidates.append(
            _format_candidate_item(
                cand_slug, friendly, entry.entity_id, kind_lbl, (True, rssi_int, area_name, src_scanner)
            )
        )

    candidates.extend(_discover_ambient_scanner_candidates(ctx))
    candidates.sort(
        key=lambda x: (
            not bool(x.get("is_tracker", True)),
            x.get("rssi") is None,
            -(int(x["rssi"]) if x.get("rssi") is not None else _MISSING_RSSI_SENTINEL),
            str(x.get("title") or "").lower(),
        )
    )
    return candidates[:_MAX_DISCOVERED_CANDIDATES]
