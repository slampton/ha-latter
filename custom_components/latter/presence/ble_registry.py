"""BLE scanner-to-Area resolution, iBeacon identity parsing, Floor helpers, and Area signatures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
import re
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ..const import CONF_BLE_AREA_SIGNATURES
from ..hub_registry import get_domain_data, peek_domain_data, peek_global_config
from .ble_math import EDDYSTONE_UUID_PREFIX

_LOGGER = logging.getLogger(__name__)

APPLE_COMPANY_ID: Final = 0x004C
MICROSOFT_COMPANY_ID: Final = 0x0006
SAMSUNG_COMPANY_ID: Final = 0x0075
GOOGLE_COMPANY_ID: Final = 0x00E0
RUUVI_COMPANY_ID: Final = 0x0499
SHELLY_COMPANY_ID: Final = 0x0B9A
IBEACON_PREFIX: Final = b"\x02\x15"
SURVEY_RETENTION_SECONDS: Final = 180.0
WAKE_GAP_SECONDS: Final = 8.0
AWAY_CHECK_INTERVAL_SECONDS: Final = 15.0
AWAY_TIMEOUT_SECONDS: Final = 180.0
MATCHED_BLE_ADDRESS_TTL_SECONDS: Final = 900.0

_UNMAPPED: Final = "__unmapped__"
_UUID_HEX_LEN: Final = 32
_UUID16_HEX_LEN: Final = 4
_UUID32_PREFIX_LEN: Final = 8
_MAC_HEX_LEN: Final = 12
_MAX_UINT16: Final = 65535
_ESP_MAC_ADJACENT_DELTA: Final = 2
_APPLE_AIRPODS_TYPE: Final = 0x07
_IBEACON_TX_MIN_LEN: Final = 23
_EDDYSTONE_TX_MIN_LEN: Final = 2
_EDDYSTONE_UID_URL_EID_MASK: Final = 0xF0
_EDDYSTONE_TX_FRAMES: Final[frozenset[int]] = frozenset({0x00, 0x10, 0x30})
_SIGNED_BYTE_SPLIT: Final = 128
_SIGNED_BYTE_MOD: Final = 256
_EDDYSTONE_0M_TO_1M_DB: Final = 41
_MIN_REF_DBM: Final = -90
_MAX_REF_DBM: Final = -30
_MIN_RAW_TX_DBM: Final = -20.0
_MAX_RAW_TX_DBM: Final = 20.0
_RAW_TX_TO_1M_OFFSET_DB: Final = 59.0
_HEX_CHARS: Final = "0123456789abcdef"

_IBEACON_IDENTITY_RE: Final = re.compile(
    r"^(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})"
    r"(?:[-:_](?P<major>\d{1,5})[-:_](?P<minor>\d{1,5}))?$",
    re.IGNORECASE,
)
_IBEACON_ENTITY_PREFIX_RE: Final = re.compile(
    r"^(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})"
    r"[-:_](?P<major>\d{1,5})[-:_](?P<minor>\d{1,5})(?:[-_].+)?$",
    re.IGNORECASE,
)
TRAILING_ROTATING_HEX4_RE: Final = re.compile(r"\s+[0-9A-Fa-f]{4}$")


def iter_devices(dev_reg: dr.DeviceRegistry) -> list[dr.DeviceEntry]:
    """Return active `DeviceEntry` objects in the Home Assistant `DeviceRegistry`."""
    return list(dev_reg.devices)


def iter_entities(ent_reg: er.EntityRegistry) -> list[er.RegistryEntry]:
    """Return active `RegistryEntry` objects in the Home Assistant `EntityRegistry`."""
    return list(ent_reg.entities.values())


def normalize_uuid_hex(uuid_str: str) -> str:
    """Normalize a UUID string to 32 lowercase hex chars without dashes."""
    return uuid_str.strip().lower().replace("-", "")


def format_uuid_dashed(uuid_hex: str) -> str:
    """Format a 32-char lowercase hex UUID as an `8-4-4-4-12` dashed string."""
    clean = normalize_uuid_hex(uuid_hex)
    if len(clean) != _UUID_HEX_LEN:
        return uuid_hex.strip()
    return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"


def coerce_uint16(val: object) -> int | None:
    """Return an integer in `0..65535` when `val` is a valid uint16, else `None`."""
    if val is None or isinstance(val, bool) or val == "" or not isinstance(val, (int, float, str)):
        return None
    if isinstance(val, float) and not val.is_integer():
        return None
    try:
        parsed = int(val)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed <= _MAX_UINT16 else None


def mac_to_int(mac_str: str) -> int | None:
    """Convert a 12-hex-char MAC address into an integer for ESP32 Wi-Fi/BLE `+/-2` comparison."""
    clean = mac_str.strip().lower().replace(":", "").replace("-", "").replace("_", "")
    if len(clean) != _MAC_HEX_LEN:
        return None
    try:
        return int(clean, 16)
    except ValueError:
        return None


def int_to_mac(mac_int: int) -> str:
    """Format a 48-bit integer as an uppercase colon-delimited MAC string."""
    hex_str = f"{mac_int:012X}"
    return ":".join(hex_str[i : i + 2] for i in range(0, _MAC_HEX_LEN, 2))


def _get_floor_registry(hass: HomeAssistant) -> Any | None:
    """Return Home Assistant's `FloorRegistry` when available."""
    try:
        from homeassistant.helpers import floor_registry as fr

        return fr.async_get(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("FloorRegistry lookup unavailable: %s", err)
        return None


def has_configured_floors(hass: HomeAssistant) -> bool:
    """Return True if Home Assistant has any configured Floor entries or Area floor assignments."""
    floor_reg = _get_floor_registry(hass)
    if floor_reg is not None and hasattr(floor_reg, "async_list_floors"):
        try:
            if list(floor_reg.async_list_floors()):
                return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("FloorRegistry.async_list_floors skipped: %s", err)
    area_reg = ar.async_get(hass)
    return any(
        bool(str(getattr(area, "floor_id", "") or "").strip())
        for area in area_reg.async_list_areas()
    )


def resolve_floor_info(hass: HomeAssistant, floor_id: str | None) -> tuple[str, str]:
    """Return `(clean_floor_id, floor_name)` for a Home Assistant Floor ID, or `('', '')` when unset."""
    clean_id = str(floor_id or "").strip()
    if not clean_id:
        return "", ""
    floor_reg = _get_floor_registry(hass)
    if floor_reg is not None and hasattr(floor_reg, "async_get_floor"):
        try:
            floor_entry = floor_reg.async_get_floor(clean_id)
            if floor_entry is not None:
                fname = str(getattr(floor_entry, "name", "") or "").strip()
                if fname:
                    return clean_id, fname
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("FloorRegistry.async_get_floor skipped: %s", err)
    humanized = clean_id.replace("_", " ").replace("-", " ").strip().title()
    return clean_id, humanized or clean_id


def parse_ibeacon_identity(
    raw: str, major_attr: object = None, minor_attr: object = None
) -> tuple[str, int | None, int | None] | None:
    """Parse `<uuid>[-/:]<major>[-/:]<minor>` or `<uuid>` + optional major/minor attributes."""
    text = str(raw or "").strip()
    low = text.lower()
    if not text or low.startswith(("eddystone:", "bthome:")):
        return None
    if low.startswith("ibeacon:"):
        text = text[8:].strip()
    match = _IBEACON_IDENTITY_RE.match(text)
    uuid_hex = normalize_uuid_hex(match.group("uuid")) if match is not None else ""
    if match is None or len(uuid_hex) != _UUID_HEX_LEN:
        return None
    maj_grp = match.group("major")
    min_grp = match.group("minor")
    if maj_grp is not None or min_grp is not None:
        maj = coerce_uint16(maj_grp)
        min_ = coerce_uint16(min_grp)
        return (uuid_hex, maj, min_) if (maj is not None and min_ is not None) else None
    return uuid_hex, coerce_uint16(major_attr), coerce_uint16(minor_attr)


def extract_ibeacon_entity_identity(
    hass: HomeAssistant,
    entry: er.RegistryEntry | None,
    st: Any,
) -> tuple[str, int | None, int | None] | None:
    """Extract `(uuid_hex, major, minor)` from an entity's state attributes, `unique_id`, or parent device."""
    if st is not None:
        raw_attr = str(
            st.attributes.get("id") or st.attributes.get("uuid") or ""
        ).strip()
        if raw_attr:
            parsed = parse_ibeacon_identity(
                raw_attr,
                st.attributes.get("major"),
                st.attributes.get("minor"),
            )
            if parsed is not None:
                return parsed

    raw_candidates: list[str] = []
    if entry is not None:
        if entry.unique_id:
            raw_candidates.append(str(entry.unique_id).strip())
        if entry.device_id:
            dev_entry = dr.async_get(hass).async_get(entry.device_id)
            if dev_entry is not None:
                raw_candidates.extend(
                    str(ident_val).strip()
                    for _dom, ident_val in dev_entry.identifiers
                    if ident_val
                )

    for cand in raw_candidates:
        direct = parse_ibeacon_identity(cand)
        if direct is not None:
            return direct
        m_pref = _IBEACON_ENTITY_PREFIX_RE.match(cand)
        if m_pref is not None:
            u_hex = normalize_uuid_hex(m_pref.group("uuid"))
            maj = coerce_uint16(m_pref.group("major"))
            min_ = coerce_uint16(m_pref.group("minor"))
            if len(u_hex) == _UUID_HEX_LEN and maj is not None and min_ is not None:
                return u_hex, maj, min_
    return None


def extract_uuid16(raw_uuid: str) -> str:
    """Extract lowercase 4-hex Bluetooth SIG 16-bit UUID from 16/32/128-bit representations."""
    u = str(raw_uuid or "").strip().lower()
    if u.startswith("0x"):
        u = u[2:]
    if len(u) == _UUID16_HEX_LEN and all(ch in _HEX_CHARS for ch in u):
        return u
    if (
        len(u) >= _UUID32_PREFIX_LEN
        and u.startswith("0000")
        and (len(u) == _UUID32_PREFIX_LEN or u[8] == "-")
        and all(ch in _HEX_CHARS for ch in u[4:8])
    ):
        return u[4:8]
    return ""


def normalize_mfg_map(mfg_data: Mapping[int, bytes] | None) -> dict[int, bytes]:
    """Normalize `manufacturer_data` dictionary keys to `int` and payloads to `bytes`."""
    out: dict[int, bytes] = {}
    for raw_k, raw_v in (mfg_data or {}).items():
        if not isinstance(raw_v, (bytes, bytearray)):
            continue
        try:
            cid = int(raw_k, 0) if isinstance(raw_k, str) else int(raw_k)
        except (TypeError, ValueError):
            continue
        out[cid] = bytes(raw_v)
    return out


def _classify_private_ble_adv(
    mfg_map: Mapping[int, bytes],
    svc_all_16: set[str],
    all_raw_uuids: tuple[str, ...],
) -> str:
    if APPLE_COMPANY_ID in mfg_map:
        apple_payload = mfg_map[APPLE_COMPANY_ID]
        if apple_payload and apple_payload[0] == _APPLE_AIRPODS_TYPE:
            return "Apple AirPods or Beats (Private BLE)"
        return "Apple iPhone, Watch, or iPad (Private BLE)"
    if SAMSUNG_COMPANY_ID in mfg_map:
        return "Samsung Galaxy Phone or Watch (Private BLE)"
    if (
        GOOGLE_COMPANY_ID in mfg_map
        or "fe2c" in svc_all_16
        or any("fe2c" in raw_u for raw_u in all_raw_uuids)
    ):
        return "Android / Pixel Phone (Private BLE)"
    if MICROSOFT_COMPANY_ID in mfg_map:
        return "Windows PC or Surface (Private BLE)"
    return "Phone or Watch (Private BLE / IRK)"


def _has_eddystone_uid_service(service_data: Mapping[str, bytes] | None) -> bool:
    for raw_k, raw_v in (service_data or {}).items():
        if (
            extract_uuid16(str(raw_k)) == "feaa"
            and isinstance(raw_v, (bytes, bytearray))
            and len(raw_v) >= 1
            and (raw_v[0] & _EDDYSTONE_UID_URL_EID_MASK) == 0x00
        ):
            return True
    return False


def _classify_vendor_named_ble(mfg_map: Mapping[int, bytes]) -> str:
    if APPLE_COMPANY_ID in mfg_map:
        return "Named BLE device (Apple)"
    if SAMSUNG_COMPANY_ID in mfg_map:
        return "Named BLE device (Samsung)"
    if MICROSOFT_COMPANY_ID in mfg_map:
        return "Named BLE device (Windows PC)"
    if GOOGLE_COMPANY_ID in mfg_map:
        return "Named BLE device (Google)"
    return "Named BLE device"


def classify_ble_advertisement_kind(
    local_name: str,
    mfg_data: Mapping[int, bytes],
    service_data: Mapping[str, bytes],
    service_uuids: Iterable[str],
    *,
    is_private_ble: bool = False,
) -> str:
    """Classify a BLE advertisement into a friendly vendor/device-type or local tag label."""
    mfg_map = normalize_mfg_map(mfg_data)
    svc_data_keys = [str(k or "").strip().lower() for k in (service_data or {})]
    svc_uuid_list = [str(u or "").strip().lower() for u in (service_uuids or ())]
    all_raw_uuids = (*svc_data_keys, *svc_uuid_list)
    svc_all_16 = {
        u16 for raw_u in all_raw_uuids if (u16 := extract_uuid16(raw_u))
    }

    if is_private_ble:
        return _classify_private_ble_adv(mfg_map, svc_all_16, all_raw_uuids)

    name_low = str(local_name or "").strip().lower()
    if "feed" in svc_all_16 or name_low.startswith("tile"):
        return "Tile Tracker"
    if name_low.startswith("itag") or ("ffe0" in svc_all_16 and "tag" in name_low):
        return "iTag Keychain Tag"
    if "fcd2" in svc_all_16:
        is_shelly = SHELLY_COMPANY_ID in mfg_map or name_low.startswith(
            ("shelly", "sbbt", "sbdw", "sbmv", "sbht")
        )
        return "Shelly BLU Tag (BTHome v2)" if is_shelly else "BTHome v2 Tag"
    if RUUVI_COMPANY_ID in mfg_map or name_low.startswith("ruuvi"):
        return "RuuviTag Beacon"
    return (
        "Eddystone-UID Beacon"
        if _has_eddystone_uid_service(service_data)
        else _classify_vendor_named_ble(mfg_map)
    )


def extract_adv_ref_power_dbm(
    service_info: object | None,
    mfg_data: Mapping[int, bytes],
    service_data: Mapping[str, bytes],
) -> float | None:
    """Extract calibrated 1 m reference RSSI (dBm) from iBeacon, Eddystone, or advertisement TX power."""
    apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
    if (
        apple_bytes
        and len(apple_bytes) >= _IBEACON_TX_MIN_LEN
        and apple_bytes[:2] == IBEACON_PREFIX
    ):
        raw_b = apple_bytes[22]
        val = raw_b - _SIGNED_BYTE_MOD if raw_b >= _SIGNED_BYTE_SPLIT else raw_b
        if _MIN_REF_DBM <= val <= _MAX_REF_DBM:
            return float(val)

    for svc_key, payload in service_data.items():
        k_low = str(svc_key).lower()
        if (
            (k_low.startswith(EDDYSTONE_UUID_PREFIX) or k_low == "feaa")
            and isinstance(payload, (bytes, bytearray))
            and len(payload) >= _EDDYSTONE_TX_MIN_LEN
            and (payload[0] & _EDDYSTONE_UID_URL_EID_MASK) in _EDDYSTONE_TX_FRAMES
        ):
            raw_b = payload[1]
            tx_0m = raw_b - _SIGNED_BYTE_MOD if raw_b >= _SIGNED_BYTE_SPLIT else raw_b
            val_1m = tx_0m - _EDDYSTONE_0M_TO_1M_DB
            if _MIN_REF_DBM <= val_1m <= _MAX_REF_DBM:
                return float(val_1m)

    if service_info is not None:
        tx_p = getattr(service_info, "tx_power", None)
        if isinstance(tx_p, (int, float)) and not isinstance(tx_p, bool):
            tx_f = float(tx_p)
            if _MIN_REF_DBM <= tx_f <= _MAX_REF_DBM:
                return tx_f
            if _MIN_RAW_TX_DBM <= tx_f <= _MAX_RAW_TX_DBM:
                val_1m_f = tx_f - _RAW_TX_TO_1M_OFFSET_DB
                if _MIN_REF_DBM <= val_1m_f <= _MAX_REF_DBM:
                    return val_1m_f
    return None


def current_ble_scanners(hass: HomeAssistant) -> list[Any]:
    """Return active Home Assistant Bluetooth scanners, or `[]` when `bluetooth` is unavailable."""
    try:
        from homeassistant.components import bluetooth

        return list(bluetooth.async_current_scanners(hass))
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Bluetooth scanner enumeration unavailable: %s", err)
        return []


def _lookup_scanner_metadata(
    hass: HomeAssistant, scanner_source: str, src_low: str, src_int: int | None
) -> tuple[str, int | None]:
    scanner_name = ""
    try:
        from homeassistant.components import bluetooth

        scanner = bluetooth.async_scanner_by_source(
            hass, scanner_source
        ) or bluetooth.async_scanner_by_source(hass, scanner_source.upper())
        if scanner is not None:
            scanner_name = str(getattr(scanner, "name", "") or "").strip().lower()
            details = getattr(scanner, "details", None)
            if isinstance(details, dict) and details.get("source"):
                alt_src = str(details["source"]).lower()
                if alt_src != src_low and src_int is None:
                    src_int = mac_to_int(alt_src)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Scanner source lookup unavailable: %s", err)
    return scanner_name, src_int


def _resolve_device_area_or_entity_area(
    dev: dr.DeviceEntry,
    ent_reg: er.EntityRegistry,
    areas_sorted: list[ar.AreaEntry],
) -> str | None:
    """Return a device's `area_id`, falling back to its entities' `area_id` or Area name in device label."""
    if dev.area_id:
        return str(dev.area_id)

    for entry in er.async_entries_for_device(ent_reg, dev.id):
        if entry.area_id:
            return str(entry.area_id)

    for raw_label in (dev.name_by_user, dev.name):
        if not raw_label:
            continue
        dev_label = str(raw_label).lower().replace("-", " ").replace("_", " ")
        for area in areas_sorted:
            a_norm = area.name.lower().replace("-", " ").replace("_", " ").strip()
            if a_norm and a_norm in dev_label:
                return str(area.id)
    return None


def _device_mac_candidates(device: dr.DeviceEntry) -> list[tuple[str, int | None]]:
    pairs: list[tuple[str, int | None]] = []
    for _conn_type, conn_val in device.connections:
        c_low = str(conn_val).lower()
        pairs.append((c_low, mac_to_int(c_low)))
    for _domain, ident_val in device.identifiers:
        i_low = str(ident_val).lower()
        pairs.append((i_low, mac_to_int(i_low)))
    return pairs


def _match_device_by_exact_or_adjacent_mac(
    all_devices: list[dr.DeviceEntry],
    src_low: str,
    src_int: int | None,
    ent_reg: er.EntityRegistry,
    areas_sorted: list[ar.AreaEntry],
) -> str | None:
    for device in all_devices:
        for val_low, val_int in _device_mac_candidates(device):
            if val_low == src_low or (
                src_int is not None and val_int is not None and src_int == val_int
            ):
                resolved = _resolve_device_area_or_entity_area(
                    device, ent_reg, areas_sorted
                )
                if resolved:
                    return resolved

    if src_int is None:
        return None

    for device in all_devices:
        for _val_low, val_int in _device_mac_candidates(device):
            if val_int is not None and 0 < abs(src_int - val_int) <= _ESP_MAC_ADJACENT_DELTA:
                resolved = _resolve_device_area_or_entity_area(
                    device, ent_reg, areas_sorted
                )
                if resolved:
                    return resolved
    return None


def _match_device_or_area_by_name(
    all_devices: list[dr.DeviceEntry],
    src_low: str,
    scanner_name: str,
    ent_reg: er.EntityRegistry,
    areas_sorted: list[ar.AreaEntry],
) -> str | None:
    for device in all_devices:
        for candidate_name in (device.name_by_user, device.name):
            if not candidate_name:
                continue
            d_low = str(candidate_name).strip().lower()
            d_slug = d_low.replace(" ", "-").replace("_", "-")
            for target_n in (src_low, scanner_name):
                if not target_n:
                    continue
                t_slug = target_n.replace(" ", "-").replace("_", "-")
                if d_low == target_n or d_slug == t_slug:
                    resolved = _resolve_device_area_or_entity_area(
                        device, ent_reg, areas_sorted
                    )
                    if resolved:
                        return resolved

    for raw_text in (scanner_name, src_low):
        if not raw_text:
            continue
        scan_norm = raw_text.replace("-", " ").replace("_", " ")
        for area in areas_sorted:
            a_norm = area.name.lower().replace("-", " ").replace("_", " ").strip()
            if a_norm and a_norm in scan_norm:
                return str(area.id)
    return None


def _resolve_scanner_area_id_uncached(
    hass: HomeAssistant, scanner_source: str
) -> str | None:
    """Resolve an ESPHome BLE Proxy source (MAC or name) to its Home Assistant `area_id`."""
    if not scanner_source:
        return None

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)
    src_low = scanner_source.strip().lower()
    scanner_name, src_int = _lookup_scanner_metadata(
        hass, scanner_source, src_low, mac_to_int(src_low)
    )
    all_devices = iter_devices(dev_reg)
    areas_sorted = sorted(
        area_reg.async_list_areas(),
        key=lambda a: len(a.name),
        reverse=True,
    )

    by_mac = _match_device_by_exact_or_adjacent_mac(
        all_devices, src_low, src_int, ent_reg, areas_sorted
    )
    if by_mac:
        return by_mac
    return _match_device_or_area_by_name(
        all_devices, src_low, scanner_name, ent_reg, areas_sorted
    )


def set_scanner_area_cache_active(hass: HomeAssistant, active: bool) -> None:
    """Enable or disable domain-scoped scanner-to-Area caching while `LatterBleFabric` is active."""
    domain_data = get_domain_data(hass)
    domain_data.ble_scanner_cache_active = bool(active)
    if not active:
        domain_data.ble_scanner_cache.clear()


def clear_scanner_area_cache(hass: HomeAssistant) -> None:
    """Clear the cached scanner-source -> `area_id` map on registry updates or wake resets."""
    domain_data = peek_domain_data(hass)
    if domain_data is not None:
        domain_data.ble_scanner_cache.clear()


def resolve_scanner_area_id(hass: HomeAssistant, scanner_source: str) -> str | None:
    """Resolve an ESPHome BLE Proxy source to its Home Assistant `area_id` (cached when active)."""
    if not scanner_source:
        return None
    domain_data = peek_domain_data(hass)
    if domain_data is not None and domain_data.ble_scanner_cache_active:
        cache = domain_data.ble_scanner_cache
        cached = cache.get(scanner_source)
        if cached is not None:
            return None if cached == _UNMAPPED else cached
        resolved = _resolve_scanner_area_id_uncached(hass, scanner_source)
        cache[scanner_source] = resolved if resolved else _UNMAPPED
        return resolved
    return _resolve_scanner_area_id_uncached(hass, scanner_source)


def get_ble_proxy_area_ids(hass: HomeAssistant) -> set[str]:
    """Return the set of Home Assistant `area_ids` that have an active Bluetooth proxy/scanner."""
    proxy_areas: set[str] = set()
    for scanner in current_ble_scanners(hass):
        source = str(getattr(scanner, "source", "") or "")
        if source and (a_id := resolve_scanner_area_id(hass, source)):
            proxy_areas.add(a_id)
    return proxy_areas


def count_area_ble_proxies(hass: HomeAssistant) -> int:
    """Return how many Bluetooth proxies/scanners resolve to a Home Assistant Area."""
    count = 0
    for scanner in current_ble_scanners(hass):
        source = str(getattr(scanner, "source", "") or "")
        if source and resolve_scanner_area_id(hass, source):
            count += 1
    return count


def get_all_scanners_diagnostic_map(hass: HomeAssistant) -> dict[str, str]:
    """Return a diagnostic dictionary of all registered HA Bluetooth scanners -> resolved Area name."""
    out: dict[str, str] = {}
    area_reg = ar.async_get(hass)
    for scanner in current_ble_scanners(hass):
        source = str(getattr(scanner, "source", "") or "")
        name = str(getattr(scanner, "name", "") or source)
        a_id = resolve_scanner_area_id(hass, source) if source else None
        area_obj = area_reg.async_get_area(a_id) if a_id else None
        area_label = f"{area_obj.name} ({a_id})" if area_obj else "UNMAPPED"
        out[f"{name} [{source}]"] = area_label
    return out


def get_ble_signature_area_ids(hass: HomeAssistant) -> set[str]:
    """Return Home Assistant `area_ids` that have a learned multi-scanner BLE signature."""
    raw_sigs = peek_global_config(hass).get(CONF_BLE_AREA_SIGNATURES, {})
    if not isinstance(raw_sigs, dict):
        return set()
    return {
        str(area_id)
        for area_id, sig in raw_sigs.items()
        if area_id
        and isinstance(sig, dict)
        and isinstance(sig.get("scanners"), dict)
        and bool(sig["scanners"])
    }


def get_area_signatures_summary(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return learned BLE signature status for every Area in Home Assistant sorted by Area name."""
    area_reg = ar.async_get(hass)
    proxy_areas = get_ble_proxy_area_ids(hass)
    raw_sigs = peek_global_config(hass).get(CONF_BLE_AREA_SIGNATURES, {})
    sig_map = raw_sigs if isinstance(raw_sigs, dict) else {}

    rows: list[dict[str, Any]] = []
    for area in sorted(area_reg.async_list_areas(), key=lambda a: a.name.lower()):
        sig = sig_map.get(area.id)
        raw_scanners = sig.get("scanners") if isinstance(sig, dict) else None
        scanners_dict: dict[str, Any] = (
            raw_scanners if isinstance(raw_scanners, dict) else {}
        )
        has_sig = len(scanners_dict) > 0
        sample_count = (
            int(
                sig.get("sample_count")
                or sum(
                    int(v.get("n", 1))
                    for v in scanners_dict.values()
                    if isinstance(v, dict)
                )
            )
            if (has_sig and isinstance(sig, dict))
            else 0
        )
        captured_at = (
            str(sig.get("captured_at") or "")
            if (has_sig and isinstance(sig, dict))
            else ""
        )
        rows.append(
            {
                "area_id": area.id,
                "area_name": area.name,
                "floor_id": str(getattr(area, "floor_id", "") or ""),
                "has_ble_proxy": area.id in proxy_areas,
                "has_signature": has_sig,
                "scanner_count": len(scanners_dict) if has_sig else 0,
                "sample_count": sample_count,
                "captured_at": captured_at,
            }
        )
    return rows
