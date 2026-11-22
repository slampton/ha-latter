"""Device Groups, group baselines, hardware-detecting option defaults, batch apply, and factory/options reset."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..config_defaults import (
    BUILTIN_GROUP_PRESET_VERSION as BUILTIN_GROUP_PRESET_VERSION,
    CONF_BUILTIN_GROUP_PRESET_VERSION as CONF_BUILTIN_GROUP_PRESET_VERSION,
    DEFAULT_DEVICE_GROUPS as DEFAULT_DEVICE_GROUPS,
    ble_tag_option_defaults,
    compute_hardware_defaults,
    merge_device_option_defaults,
)
from ..const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DOCK_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN_POLICY,
    CONF_SYNC_DEVICE_AREA,
    CONF_TOOLS_ITEMS,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_ACTIVITY_CARD,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES,
    DEFAULT_SCREENSAVER_CYCLE_MINUTES,
    DEFAULT_SCREENSAVER_PHOTO_COLLECTION,
    DEFAULT_SCREENSAVER_PHOTO_MODE,
    DEFAULT_SCREENSAVER_SHUFFLE,
    DEFAULT_TOOLS_ITEMS,
    DEFAULT_WALLPAPER_COLLECTION,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DEFAULT_WALLPAPER_MODE,
    DOMAIN,
    MIN_FIRMWARE_SDK_REV,
)
from ..identity import (
    esphome_service,
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    read_device_hardware_manifest,
)
from ..media.linking import discover_ma_player_for_device
from ..protocol_specs import (
    DEVICE_PREF_KEYS,
    DEVICE_PREF_SPEC_MAP,
    DEVICE_PREF_SPECS,
    DevicePrefSpec,
    default_dock_items,
    normalize_activity_sources,
    normalize_area_categories,
    normalize_dock_items,
    normalize_games_items,
    normalize_home_categories,
    normalize_pinned_items,
    normalize_tools_items,
    resolve_device_pref_value,
)
from ..studio.settings_cleaners import clean_device_settings

if TYPE_CHECKING:
    from ..coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

DEVICE_IDENTITY_KEYS: Final[tuple[str, ...]] = (
    "esphome_device_id",
    "mac",
    "device_slug",
    "ma_player_entity",
)

BLE_TAG_IDENTITY_KEYS: Final[tuple[str, ...]] = (
    "device_slug",
    "ble_target_address",
)

FACTORY_RESET_MIN_SDK_REV: Final = MIN_FIRMWARE_SDK_REV

_FLAG_ERRORS: Final[dict[str, str]] = {
    "reset_nothing_selected": "Select what to reset: the device settings, the Latter options, or both.",
    "reset_ble_tag_has_no_device_settings": "A BLE tag has no device settings to reset. Reset only its Latter options.",
}

_DWELL_MIN_S: Final = 3
_DWELL_MAX_S: Final = 60
_HEX_COLOR_LEN: Final = 7
_MAX_BROADCAST_SPKS: Final = 32
_MAX_CAM_LIST: Final = 10
_FLOAT_EPSILON: Final = 1e-4

_CAPABILITY_ATTRS: Final[dict[str, tuple[tuple[str, bool], ...]]] = {
    "display": (("has_display", True),),
    "display_imu": (("has_display", True), ("has_imu", True)),
    "display_battery": (("has_display", True), ("has_battery", True)),
    "hw_jpeg": (("has_display", True), ("supports_hw_jpeg", False)),
    "mic": (("has_mic", True),),
    "speaker": (("has_speaker", True),),
    "beacon": (("has_ble_beacon", True),),
    "beacon_battery": (("has_ble_beacon", True), ("has_battery", True)),
}

GROUP_BEHAVIOR_DEVICE_KEYS: Final[tuple[str, ...]] = (
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_SECURITY_PIN_POLICY,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "behavior"),
)

GROUP_DISPLAY_DEVICE_KEYS: Final[tuple[str, ...]] = (
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_DEVICE_CUSTOM_COLOR,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "display"),
)

GROUP_INTERFACE_NON_PREF_KEYS: Final[tuple[str, ...]] = (
    CONF_DOCK_ITEMS,
    CONF_PINNED_ITEMS,
    CONF_AREA_CATEGORIES,
    CONF_HOME_CATEGORIES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_TOOLS_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_DEVICE_REMOTE_GROUP,
)

GROUP_INTERFACE_DEVICE_KEYS: Final[tuple[str, ...]] = (
    *GROUP_INTERFACE_NON_PREF_KEYS,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "interface"),
)

GROUP_APPEARANCE_DEVICE_KEYS: Final[tuple[str, ...]] = (
    *GROUP_DISPLAY_DEVICE_KEYS,
    *GROUP_INTERFACE_DEVICE_KEYS,
)

GROUP_ALL_DEVICE_KEYS: Final[tuple[str, ...]] = (
    *GROUP_BEHAVIOR_DEVICE_KEYS,
    *GROUP_DISPLAY_DEVICE_KEYS,
    *GROUP_INTERFACE_DEVICE_KEYS,
)

_DISPLAY_CAPABILITY_NON_PREF_KEYS: Final[frozenset[str]] = frozenset(
    {
        CONF_WALLPAPER_MODE,
        CONF_WALLPAPER_SOURCE,
        CONF_WALLPAPER_COLLECTION,
        CONF_WALLPAPER_CYCLE_MINUTES,
        CONF_SCREENSAVER_PHOTO_MODE,
        CONF_SCREENSAVER_PHOTO_SOURCE,
        CONF_SCREENSAVER_PHOTO_COLLECTION,
        CONF_SCREENSAVER_CYCLE_MINUTES,
        CONF_SCREENSAVER_SHUFFLE,
        CONF_DEVICE_CUSTOM_COLOR,
        *GROUP_INTERFACE_NON_PREF_KEYS,
    }
)

_BUILTIN_GROUPS_BY_ID: Final[dict[str, dict[str, Any]]] = {
    g["id"]: g for g in DEFAULT_DEVICE_GROUPS
}


def coordinator_supports_pref(coordinator: Any, spec: DevicePrefSpec) -> bool:
    """Return True when `coordinator`'s hardware supports preference `spec`."""
    if getattr(coordinator, "is_ble_tag", False):
        return False
    checks = _CAPABILITY_ATTRS.get(spec.capability)
    if checks is None:
        return True
    return all(bool(getattr(coordinator, attr, dflt)) for attr, dflt in checks)


def active_group_keys(group: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the baseline keys actively enforced by `group` based on its scope flags."""
    keys: list[str] = list(GROUP_BEHAVIOR_DEVICE_KEYS)
    if bool(group.get("include_display", False)):
        keys.extend(GROUP_DISPLAY_DEVICE_KEYS)
    if bool(group.get("include_interface", False)):
        keys.extend(GROUP_INTERFACE_DEVICE_KEYS)
    return tuple(keys)


def coordinator_supports_group_key(coordinator: Any, key: str) -> bool:
    """Return True when `coordinator`'s hardware supports group/batch setting `key`."""
    if getattr(coordinator, "is_ble_tag", False):
        return False
    if key in (CONF_SYNC_DEVICE_AREA, CONF_AREA_FOLLOW_DWELL_S) and not bool(
        getattr(coordinator, "is_roaming_device", True)
    ):
        return False
    if key in _DISPLAY_CAPABILITY_NON_PREF_KEYS:
        return bool(getattr(coordinator, "has_display", True))
    spec = DEVICE_PREF_SPEC_MAP.get(key)
    return coordinator_supports_pref(coordinator, spec) if spec is not None else True


def default_group_baseline_config(
    *, include_display: bool = False, include_interface: bool = False
) -> dict[str, Any]:
    """Return the canonical baseline dictionary for a Device Group."""
    base: dict[str, Any] = {
        CONF_NATIVE_BLE_TRACKING: False,
        CONF_BLE_AUTO_SWITCH: False,
        CONF_SYNC_DEVICE_AREA: False,
        CONF_AREA_FOLLOW_DWELL_S: 10,
        CONF_AREA_HANDOFF: False,
        CONF_SECURITY_PIN_POLICY: "auto",
    }
    for spec in DEVICE_PREF_SPECS:
        if spec.group_tier == "behavior":
            base[spec.key] = spec.default
    if include_display:
        base.update(
            {
                CONF_WALLPAPER_MODE: DEFAULT_WALLPAPER_MODE,
                CONF_WALLPAPER_SOURCE: "",
                CONF_WALLPAPER_COLLECTION: DEFAULT_WALLPAPER_COLLECTION,
                CONF_WALLPAPER_CYCLE_MINUTES: DEFAULT_WALLPAPER_CYCLE_MINUTES,
                CONF_SCREENSAVER_PHOTO_MODE: DEFAULT_SCREENSAVER_PHOTO_MODE,
                CONF_SCREENSAVER_PHOTO_SOURCE: "",
                CONF_SCREENSAVER_PHOTO_COLLECTION: DEFAULT_SCREENSAVER_PHOTO_COLLECTION,
                CONF_SCREENSAVER_CYCLE_MINUTES: DEFAULT_SCREENSAVER_CYCLE_MINUTES,
                CONF_SCREENSAVER_SHUFFLE: DEFAULT_SCREENSAVER_SHUFFLE,
                CONF_DEVICE_CUSTOM_COLOR: "#3898FF",
            }
        )
        for spec in DEVICE_PREF_SPECS:
            if spec.group_tier == "display":
                base[spec.key] = spec.default
    if include_interface:
        base.update(
            {
                CONF_DOCK_ITEMS: default_dock_items(),
                CONF_PINNED_ITEMS: [],
                CONF_AREA_CATEGORIES: DEFAULT_AREA_CATEGORIES,
                CONF_HOME_CATEGORIES: DEFAULT_HOME_CATEGORIES,
                CONF_BROADCAST_SPEAKER_ENTITIES: [],
                CONF_CAMERA_VISIBLE_ENTITIES: [],
                CONF_CAMERA_CAROUSEL_ENTITIES: [],
                CONF_TOOLS_ITEMS: DEFAULT_TOOLS_ITEMS,
                CONF_GAMES_ITEMS: DEFAULT_GAMES_ITEMS,
                CONF_ACTIVITY_CARD: DEFAULT_ACTIVITY_CARD,
                CONF_ACTIVITY_SOURCES: DEFAULT_ACTIVITY_SOURCES,
                CONF_DEVICE_REMOTE_GROUP: DEFAULT_DEVICE_REMOTE_GROUP,
            }
        )
        for spec in DEVICE_PREF_SPECS:
            if spec.group_tier == "interface":
                base[spec.key] = spec.default
    return base


def _coerce_bool_field(val: object) -> bool:
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "on", "yes")
    return bool(val)


def _safe_norm_csv(raw: object, norm_fn: Any, fallback: str) -> str:
    try:
        return str(norm_fn(raw))
    except ValueError:
        return fallback


def _dedup_prefixed_list(raw: object, prefix: str, limit: int) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    for item in raw:
        ent = str(item or "").strip()
        if ent.startswith(prefix) and ent not in out:
            out.append(ent)
    return out[:limit]


_CSV_KEY_NORMS: Final[dict[str, tuple[Any, str]]] = {
    CONF_AREA_CATEGORIES: (normalize_area_categories, DEFAULT_AREA_CATEGORIES),
    CONF_HOME_CATEGORIES: (normalize_home_categories, DEFAULT_HOME_CATEGORIES),
    CONF_TOOLS_ITEMS: (normalize_tools_items, DEFAULT_TOOLS_ITEMS),
    CONF_GAMES_ITEMS: (normalize_games_items, DEFAULT_GAMES_ITEMS),
    CONF_ACTIVITY_SOURCES: (normalize_activity_sources, DEFAULT_ACTIVITY_SOURCES),
}


def _resolve_display_key_value(data: Mapping[str, Any], key: str) -> tuple[bool, Any]:
    matched = True
    val: Any = None
    if key == CONF_WALLPAPER_MODE:
        raw_wm = str(data.get(CONF_WALLPAPER_MODE) or "").strip().lower()
        val = (
            raw_wm
            if raw_wm in ("off", "single", "collection", "custom")
            else ("single" if str(data.get(CONF_WALLPAPER_SOURCE) or "").strip() else DEFAULT_WALLPAPER_MODE)
        )
    elif key in (CONF_WALLPAPER_SOURCE, CONF_SCREENSAVER_PHOTO_SOURCE):
        val = str(data.get(key) or "").strip()
    elif key == CONF_WALLPAPER_COLLECTION:
        val = str(data.get(key) or DEFAULT_WALLPAPER_COLLECTION).strip()
    elif key == CONF_SCREENSAVER_PHOTO_COLLECTION:
        val = str(data.get(key, DEFAULT_SCREENSAVER_PHOTO_COLLECTION) or DEFAULT_SCREENSAVER_PHOTO_COLLECTION).strip()
    elif key in (CONF_WALLPAPER_CYCLE_MINUTES, CONF_SCREENSAVER_CYCLE_MINUTES):
        dflt = DEFAULT_WALLPAPER_CYCLE_MINUTES if key == CONF_WALLPAPER_CYCLE_MINUTES else DEFAULT_SCREENSAVER_CYCLE_MINUTES
        try:
            val = max(0, int(data.get(key, dflt) if key in data else dflt))
        except (TypeError, ValueError):
            val = 0 if key == CONF_WALLPAPER_CYCLE_MINUTES else DEFAULT_SCREENSAVER_CYCLE_MINUTES
    elif key == CONF_SCREENSAVER_PHOTO_MODE:
        raw_sm = str(data.get(key) or "").strip().lower()
        val = raw_sm if raw_sm in ("off", "single", "collection", "custom") else DEFAULT_SCREENSAVER_PHOTO_MODE
    elif key == CONF_SCREENSAVER_SHUFFLE:
        val = _coerce_bool_field(data.get(key, DEFAULT_SCREENSAVER_SHUFFLE))
    elif key == CONF_DEVICE_CUSTOM_COLOR:
        raw_c = str(data.get(key) or "").strip().upper()
        val = raw_c if raw_c.startswith("#") and len(raw_c) == _HEX_COLOR_LEN else "#3898FF"
    else:
        matched = False
    return matched, val


def _resolve_interface_key_value(data: Mapping[str, Any], key: str) -> tuple[bool, Any]:
    if key in _CSV_KEY_NORMS:
        norm_fn, fallback = _CSV_KEY_NORMS[key]
        return True, _safe_norm_csv(data.get(key, fallback), norm_fn, fallback)
    matched = True
    val: Any = None
    if key == CONF_DOCK_ITEMS:
        val = normalize_dock_items(data.get(CONF_DOCK_ITEMS), strict=False)
    elif key == CONF_PINNED_ITEMS:
        val = normalize_pinned_items(data.get(CONF_PINNED_ITEMS), strict=False)
    elif key == CONF_BROADCAST_SPEAKER_ENTITIES:
        val = _dedup_prefixed_list(data.get(key), "media_player.", _MAX_BROADCAST_SPKS)
    elif key in (CONF_CAMERA_VISIBLE_ENTITIES, CONF_CAMERA_CAROUSEL_ENTITIES):
        val = _dedup_prefixed_list(data.get(key), "camera.", _MAX_CAM_LIST)
    elif key == CONF_ACTIVITY_CARD:
        val = _coerce_bool_field(data.get(key, DEFAULT_ACTIVITY_CARD))
    elif key == CONF_DEVICE_REMOTE_GROUP:
        val = str(data.get(key) or DEFAULT_DEVICE_REMOTE_GROUP).strip() or DEFAULT_DEVICE_REMOTE_GROUP
    else:
        matched = False
    return matched, val


def _resolve_core_behavior_key(data: Mapping[str, Any], key: str) -> tuple[bool, Any]:
    if key in (CONF_NATIVE_BLE_TRACKING, CONF_SYNC_DEVICE_AREA, CONF_AREA_HANDOFF):
        return True, bool(data.get(key, False))
    if key == CONF_BLE_AUTO_SWITCH:
        return True, bool(data.get(CONF_BLE_AUTO_SWITCH, bool(data.get(CONF_NATIVE_BLE_TRACKING, False))))
    if key == CONF_AREA_FOLLOW_DWELL_S:
        try:
            val = int(data.get(CONF_AREA_FOLLOW_DWELL_S, 10))
        except (TypeError, ValueError):
            val = 10
        return True, max(_DWELL_MIN_S, min(_DWELL_MAX_S, val))
    if key == CONF_SECURITY_PIN_POLICY:
        pol = str(data.get(CONF_SECURITY_PIN_POLICY) or "auto").strip().lower()
        return True, (pol if pol in ("auto", "allow", "require_pin", "block") else "auto")
    return False, None


def resolve_behavior_key_value(data: Mapping[str, Any], key: str) -> Any:
    """Resolve the effective normalized value for any group/batch `key` from `data`."""
    if key in DEVICE_PREF_SPEC_MAP:
        return resolve_device_pref_value(data, key)
    for resolver in (_resolve_core_behavior_key, _resolve_display_key_value, _resolve_interface_key_value):
        matched, val = resolver(data, key)
        if matched:
            return val
    return data.get(key)


def _same_control_val(a: Any, b: Any) -> bool:
    """Compare two control values, treating structured lists, numeric strings, and booleans consistently."""
    if isinstance(a, (list, dict)) or isinstance(b, (list, dict)):
        return bool(a == b)
    sa, sb = str(a).strip(), str(b).strip()
    if sa == sb:
        return True
    if sa.lower() in ("on", "true", "1") and sb.lower() in ("on", "true", "1"):
        return True
    if sa.lower() in ("off", "false", "0") and sb.lower() in ("off", "false", "0"):
        return True
    try:
        return abs(float(sa) - float(sb)) < _FLOAT_EPSILON
    except (ValueError, TypeError):
        return False


def _normalize_group_entry(raw: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """Normalize a single Device Group entry onto a complete baseline dictionary."""
    gid = str(raw.get("id") or "").strip()
    builtin_def = _BUILTIN_GROUPS_BY_ID.get(gid)
    include_display = bool(
        raw.get("include_display", builtin_def.get("include_display", False) if builtin_def else False)
    )
    include_interface = bool(
        raw.get("include_interface", builtin_def.get("include_interface", False) if builtin_def else False)
    )
    base_dev = default_group_baseline_config(
        include_display=include_display, include_interface=include_interface
    )
    if builtin_def and isinstance(builtin_def.get("device_config"), dict):
        base_dev.update(builtin_def["device_config"])
    if isinstance(raw.get("device_config"), dict):
        for k, v in raw["device_config"].items():
            if k in GROUP_ALL_DEVICE_KEYS and v is not None:
                base_dev[k] = v
    out_entry: dict[str, Any] = {
        "id": gid,
        "name": str((builtin_def["name"] if builtin_def else raw.get("name")) or gid),
        "description": str((builtin_def["description"] if builtin_def else raw.get("description")) or ""),
        "builtin": gid in _BUILTIN_GROUPS_BY_ID,
        "include_display": include_display,
        "include_interface": include_interface,
        "device_config": base_dev,
    }
    if builtin_def is not None:
        out_entry["preset_version"] = BUILTIN_GROUP_PRESET_VERSION
    return out_entry


def reset_builtin_group_entry(group_id: str) -> dict[str, Any] | None:
    """Return a freshly normalized default baseline for built-in `group_id`, or `None` if custom."""
    bdef = _BUILTIN_GROUPS_BY_ID.get(str(group_id or "").strip())
    return _normalize_group_entry(bdef) if bdef is not None else None


def upgrade_stored_builtin_groups(global_cfg: dict[str, Any]) -> bool:
    """Refresh stored built-in groups when `builtin_group_preset_version` advances; preserve custom groups."""
    if global_cfg.get(CONF_BUILTIN_GROUP_PRESET_VERSION) == BUILTIN_GROUP_PRESET_VERSION:
        return False
    raw_groups = global_cfg.get(CONF_DEVICE_GROUPS)
    if isinstance(raw_groups, list) and raw_groups:
        custom_entries: list[dict[str, Any]] = []
        seen_custom: set[str] = set()
        for item in raw_groups:
            if not isinstance(item, dict) or item.get("builtin") is True:
                continue
            gid = str(item.get("id") or "").strip()
            if gid and gid != DEFAULT_DEVICE_GROUP and gid not in _BUILTIN_GROUPS_BY_ID and gid not in seen_custom:
                seen_custom.add(gid)
                custom_entries.append(_normalize_group_entry(item))
        global_cfg[CONF_DEVICE_GROUPS] = [
            _normalize_group_entry(g) for g in DEFAULT_DEVICE_GROUPS
        ] + custom_entries
    global_cfg[CONF_BUILTIN_GROUP_PRESET_VERSION] = BUILTIN_GROUP_PRESET_VERSION
    return True


async def async_sync_coordinators_to_builtin_presets(
    hass: HomeAssistant, coordinators: Iterable[Any]
) -> int:
    """Sync Devices currently assigned to built-in groups onto upgraded built-in baselines."""
    groups_by_id = {
        g["id"]: g for g in get_device_groups(hass) if g.get("id") in _BUILTIN_GROUPS_BY_ID
    }
    synced_total = 0
    for gid, grp in groups_by_id.items():
        matching = [
            c
            for c in coordinators
            if not getattr(c, "is_ble_tag", False)
            and str((getattr(c, "device_data", {}) or {}).get("device_group") or "").strip() == gid
        ]
        if matching:
            res = await async_apply_group_baseline_to_coordinators(hass, grp, matching)
            synced_total += int(res.get("updated_devices", 0))
    return synced_total


def get_device_groups(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return the normalized named Device Groups list from Global System Config."""
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG) or {}
    raw_groups = global_cfg.get(CONF_DEVICE_GROUPS)
    if not isinstance(raw_groups, list) or not raw_groups:
        return [_normalize_group_entry(g) for g in DEFAULT_DEVICE_GROUPS]

    by_id: dict[str, dict[str, Any]] = {}
    custom_order: list[str] = []
    for item in raw_groups:
        if not isinstance(item, dict):
            continue
        gid = str(item.get("id") or "").strip()
        if not gid or gid == DEFAULT_DEVICE_GROUP:
            continue
        if item.get("builtin") is True and gid not in _BUILTIN_GROUPS_BY_ID:
            continue
        by_id[gid] = _normalize_group_entry(item)
        if gid not in _BUILTIN_GROUPS_BY_ID and gid not in custom_order:
            custom_order.append(gid)

    out = [by_id.get(bdef["id"]) or _normalize_group_entry(bdef) for bdef in DEFAULT_DEVICE_GROUPS]
    out.extend(by_id[cid] for cid in custom_order)
    return out


def _matches_enforced_keys(
    coordinator: Any,
    dev_data: Mapping[str, Any],
    base_dev: Mapping[str, Any],
    enforced_keys: Iterable[str],
    *,
    use_runtime_wp: bool,
) -> bool:
    is_round = bool(getattr(coordinator, "is_round_display", True))
    for k in enforced_keys:
        if k not in base_dev or base_dev[k] is None or not coordinator_supports_group_key(coordinator, k):
            continue
        want_v = base_dev[k]
        if k == "clock_face" and want_v == "Modern Analog" and not is_round:
            want_v = "Minimal Digital"
        cur_v = resolve_behavior_key_value(dev_data, k)
        if k == CONF_WALLPAPER_SOURCE and use_runtime_wp:
            cur_v = str(getattr(coordinator, "configured_wallpaper_source", cur_v) or "").strip()
        if isinstance(want_v, bool):
            if bool(cur_v) != want_v:
                return False
        elif not _same_control_val(cur_v, want_v):
            return False
    return True


def device_matches_group_baseline(
    hass: HomeAssistant,
    coordinator: Any,
    groups: list[dict[str, Any]] | None = None,
    *,
    group_id: str | None = None,
    candidate_data: Mapping[str, Any] | None = None,
) -> bool:
    """Return True when `coordinator` (or `candidate_data`) matches all active keys of `group_id`."""
    if getattr(coordinator, "is_ble_tag", False):
        return False
    dev_data: Mapping[str, Any] = (
        candidate_data
        if candidate_data is not None
        else (getattr(coordinator, "device_data", {}) or {})
    )
    grp_id = str(
        group_id
        if group_id is not None
        else (
            dev_data.get("device_group")
            or getattr(coordinator, "raw_device_group", "")
            or DEFAULT_DEVICE_GROUP
        )
    ).strip()
    if not grp_id or grp_id == DEFAULT_DEVICE_GROUP:
        return False
    group_list = groups if groups is not None else get_device_groups(hass)
    grp = next((g for g in group_list if g.get("id") == grp_id), None)
    base_dev = (grp.get("device_config") or {}) if grp is not None else {}
    if not base_dev or grp is None:
        return False
    return _matches_enforced_keys(
        coordinator,
        dev_data,
        base_dev,
        active_group_keys(grp),
        use_runtime_wp=candidate_data is None,
    )


def resolve_effective_device_group(
    hass: HomeAssistant,
    coordinator: Any,
    groups: list[dict[str, Any]] | None = None,
    *,
    candidate_data: Mapping[str, Any] | None = None,
) -> str:
    """Return the Device's effective group ID, switching to `'custom'` if unknown or diverged."""
    if getattr(coordinator, "is_ble_tag", False):
        return ""
    dev_data: Mapping[str, Any] = (
        candidate_data
        if candidate_data is not None
        else (getattr(coordinator, "device_data", {}) or {})
    )
    raw_grp = str(dev_data.get("device_group") or DEFAULT_DEVICE_GROUP).strip()
    if not raw_grp or raw_grp == DEFAULT_DEVICE_GROUP:
        return DEFAULT_DEVICE_GROUP
    if raw_grp in ("pocket_carry", "handhelds", "wearables") and not bool(
        getattr(coordinator, "has_display", True)
    ):
        return DEFAULT_DEVICE_GROUP
    group_list = groups if groups is not None else get_device_groups(hass)
    if not device_matches_group_baseline(
        hass, coordinator, group_list, group_id=raw_grp, candidate_data=dev_data
    ):
        return DEFAULT_DEVICE_GROUP
    return raw_grp


def seed_group_baseline_from_coordinator(
    _hass: HomeAssistant,
    group: dict[str, Any],
    coordinator: Any,
    *,
    only_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Capture a Device's settings into `group` as its baseline (all supported keys or `only_keys`)."""
    dev_cfg = default_group_baseline_config(
        include_display=bool(group.get("include_display", False)),
        include_interface=bool(group.get("include_interface", False)),
    )
    if isinstance(existing_cfg := group.get("device_config"), dict):
        for k, v in existing_cfg.items():
            if k in GROUP_ALL_DEVICE_KEYS and v is not None:
                dev_cfg[k] = v
    dev_data = getattr(coordinator, "device_data", {}) or {}
    keys_to_copy = (
        tuple(k for k in only_keys if k in GROUP_ALL_DEVICE_KEYS)
        if only_keys is not None
        else active_group_keys(group)
    )
    for k in keys_to_copy:
        if not coordinator_supports_group_key(coordinator, k):
            continue
        if k == CONF_WALLPAPER_SOURCE:
            dev_cfg[k] = str(
                getattr(coordinator, "configured_wallpaper_source", resolve_behavior_key_value(dev_data, k))
                or ""
            ).strip()
        elif k == CONF_DEVICE_CUSTOM_COLOR:
            dev_cfg[k] = str(
                getattr(coordinator, "device_custom_color", resolve_behavior_key_value(dev_data, k))
                or "#3898FF"
            ).strip().upper()
        else:
            dev_cfg[k] = resolve_behavior_key_value(dev_data, k)
    group["device_config"] = dev_cfg
    return group


def _collect_coordinator_group_updates(
    coord: Any,
    cur_data: Mapping[str, Any],
    dev_cfg: Mapping[str, Any],
    enforced_keys: Iterable[str],
) -> dict[str, Any]:
    is_round = bool(getattr(coord, "is_round_display", True))
    updates: dict[str, Any] = {}
    for k in enforced_keys:
        if k not in dev_cfg or dev_cfg[k] is None or not coordinator_supports_group_key(coord, k):
            continue
        want_v = dev_cfg[k]
        if k == "clock_face" and want_v == "Modern Analog" and not is_round:
            want_v = "Minimal Digital"
        cur_v = resolve_behavior_key_value(cur_data, k)
        if k == CONF_WALLPAPER_SOURCE:
            cur_v = str(getattr(coord, "configured_wallpaper_source", cur_v) or "").strip()
        if not _same_control_val(cur_v, want_v) or k not in cur_data:
            updates[k] = want_v
    return updates


def _apply_wallpaper_override_and_timers(coord: Any, merged: Mapping[str, Any], *, wp_override: bool) -> None:
    if wp_override:
        wp_val = str(merged.get(CONF_WALLPAPER_SOURCE) or "").strip()
        coord.current_wallpaper = wp_val
        if hasattr(coord, "set_configured_wallpaper_source"):
            coord.set_configured_wallpaper_source(wp_val)
        else:
            coord.configured_wallpaper_source = wp_val


async def _async_apply_group_to_single_coord(
    coord: Any,
    grp_id: str,
    dev_cfg: Mapping[str, Any],
    enforced_keys: tuple[str, ...],
) -> int:
    cur_data: dict[str, Any] = dict(coord.device_data)
    updates = _collect_coordinator_group_updates(coord, cur_data, dev_cfg, enforced_keys)
    if updates:
        cleaned = clean_device_settings(
            updates,
            current=cur_data,
            is_round_display=bool(getattr(coord, "is_round_display", True)),
            supports_hw_jpeg=bool(getattr(coord, "supports_hw_jpeg", False)),
        )
        if not cleaned:
            raise ValueError("Group baseline contained no valid device settings")
    else:
        cleaned = {}

    merged = {**cur_data, **cleaned}
    if grp_id and grp_id != DEFAULT_DEVICE_GROUP:
        merged["device_group"] = grp_id
    wp_override = CONF_WALLPAPER_SOURCE in cleaned
    applied_count = 0
    if merged != cur_data or wp_override:
        _apply_wallpaper_override_and_timers(coord, merged, wp_override=wp_override)
        coord.update_device_config(merged, preserve_group=True)
        await coord.async_apply_options()
        if hasattr(coord, "bind_wallpaper_cycle_timer"):
            coord.bind_wallpaper_cycle_timer()
        if hasattr(coord, "bind_screensaver_cycle_timer"):
            coord.bind_screensaver_cycle_timer()
        applied_count = len(cleaned)
    if hasattr(coord, "async_update_listeners"):
        coord.async_update_listeners()
    coord.async_notify_listeners()
    return applied_count


async def async_apply_group_baseline_to_coordinators(
    _hass: HomeAssistant,
    group: dict[str, Any],
    targets: list[Any],
) -> dict[str, int]:
    """Apply a Device Group's active baseline across one or more target coordinators."""
    dev_cfg = group.get("device_config") or {}
    grp_id = str(group.get("id") or "").strip()
    enforced_keys = active_group_keys(group)
    updated_devices = 0
    updated_controls = 0
    for coord in targets:
        if getattr(coord, "is_ble_tag", False):
            continue
        updated_controls += await _async_apply_group_to_single_coord(
            coord, grp_id, dev_cfg, enforced_keys
        )
        updated_devices += 1
    return {"updated_devices": updated_devices, "updated_controls": updated_controls}


def detect_hardware_defaults(
    hass: HomeAssistant,
    dev: dr.DeviceEntry | None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Auto-detect group, area, and roaming BLE capability from the device's hardware manifest."""
    ent_reg = er.async_get(hass)
    dev_id = dev.id if dev is not None else None
    eff_manifest = manifest if manifest is not None else read_device_hardware_manifest(hass, dev_id)
    has_native_slots = bool(esphome_service(hass, dev_id, "latter_set_slots"))
    has_ble_beacon = isinstance(eff_manifest.get("beacon"), dict) or (
        dev is not None
        and any(e.entity_id.endswith("_ble_radio_active") for e in er.async_entries_for_device(ent_reg, dev.id))
    )
    esp_area = str(dev.area_id or "").strip() if dev is not None else ""
    return compute_hardware_defaults(
        eff_manifest,
        esp_area_id=esp_area,
        has_native_slots=has_native_slots,
        has_ble_beacon=has_ble_beacon,
    )


_detect_hardware_defaults = detect_hardware_defaults


def device_option_defaults(
    hass: HomeAssistant,
    dev: dr.DeviceEntry | None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the fresh-onboarding option defaults for a bound ESPHome device."""
    dev_id = dev.id if dev is not None else None
    hw_defaults = detect_hardware_defaults(hass, dev, manifest)
    grp_id = str(hw_defaults.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP)
    matched_grp = (
        None
        if grp_id in ("", DEFAULT_DEVICE_GROUP)
        else next((g for g in get_device_groups(hass) if g.get("id") == grp_id), None)
    )
    enforced_keys = active_group_keys(matched_grp) if matched_grp is not None else ()
    default_spk = (
        find_device_entity_by_suffix(
            hass, dev_id, "media_player", ("", "_music", "_media_player")
        )
        or ""
    )
    discovered_ma = discover_ma_player_for_device(hass, dev_id) if dev_id else None
    return merge_device_option_defaults(
        hw_defaults,
        matched_grp,
        enforced_keys,
        default_speaker=default_spk,
        ma_player_entity=discovered_ma,
    )


def reset_flags_error(
    device_settings: bool, latter_options: bool, *, is_ble_tag: bool
) -> str | None:
    """Return the translation key of the reason a reset request is invalid, or `None` if valid."""
    if not device_settings and not latter_options:
        return "reset_nothing_selected"
    if device_settings and is_ble_tag:
        return "reset_ble_tag_has_no_device_settings"
    return None


def reset_subentry_data(
    current: Mapping[str, Any],
    defaults: Mapping[str, Any],
    identity_keys: tuple[str, ...],
) -> dict[str, Any]:
    """Return the subentry data after a reset: defaults plus the identity keys from `current`."""
    out = {k: v for k, v in defaults.items() if k not in identity_keys}
    for key in identity_keys:
        if key in current:
            out[key] = current[key]
    return out


async def async_reset_device(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    *,
    device_settings: bool = True,
    latter_options: bool = True,
) -> None:
    """Reset a Latter Device's on-device NVS preferences and/or Home Assistant Latter options."""
    error_key = reset_flags_error(
        device_settings, latter_options, is_ble_tag=coordinator.is_ble_tag
    )
    if error_key is not None:
        raise ServiceValidationError(
            _FLAG_ERRORS[error_key],
            translation_domain=DOMAIN,
            translation_key=error_key,
        )

    reset_action: str | None = None
    if device_settings:
        reset_action = esphome_service(
            hass, coordinator.esphome_device_id, "latter_factory_reset"
        )
        if reset_action is None:
            raise ServiceValidationError(
                f"{coordinator.device_title} doesn't offer Reset to defaults. Update its firmware "
                f"to Latter SDK rev {FACTORY_RESET_MIN_SDK_REV} or later.",
                translation_domain=DOMAIN,
                translation_key="factory_reset_unsupported",
                translation_placeholders={
                    "device": coordinator.device_title,
                    "sdk_rev": str(FACTORY_RESET_MIN_SDK_REV),
                },
            )

    if latter_options:
        current = coordinator.device_data
        if coordinator.is_ble_tag:
            defaults = ble_tag_option_defaults(
                coordinator.device_slug, str(current.get(CONF_BLE_TARGET_ADDRESS) or "")
            )
            identity_keys = BLE_TAG_IDENTITY_KEYS
        else:
            defaults = device_option_defaults(
                hass,
                get_bound_esphome_device(hass, coordinator.esphome_device_id),
                coordinator.hardware_manifest,
            )
            identity_keys = DEVICE_IDENTITY_KEYS
        coordinator.update_device_config(reset_subentry_data(current, defaults, identity_keys))
        await coordinator.async_apply_options()
        coordinator.bind_wallpaper_cycle_timer()
        coordinator.bind_screensaver_cycle_timer()
        coordinator.async_notify_listeners()
        _LOGGER.info("Reset the Latter options of '%s' to defaults", coordinator.device_slug)
    elif device_settings and not coordinator.is_ble_tag:
        stripped = {
            k: v for k, v in coordinator.device_data.items() if k not in DEVICE_PREF_KEYS
        }
        if stripped != coordinator.device_data:
            coordinator.update_device_config(stripped)
            coordinator.async_notify_listeners()

    if reset_action is not None:
        try:
            await hass.services.async_call("esphome", reset_action, {}, blocking=True)
        except HomeAssistantError as err:
            raise HomeAssistantError(
                f"{coordinator.device_title} didn't accept Reset to defaults: {err}",
                translation_domain=DOMAIN,
                translation_key="factory_reset_failed",
                translation_placeholders={
                    "device": coordinator.device_title,
                    "error": str(err),
                },
            ) from err
        _LOGGER.info(
            "Sent latter_factory_reset to '%s'; the device erases its saved settings and restarts",
            coordinator.device_slug,
        )
