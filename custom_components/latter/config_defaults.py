"""Pure-stdlib Device Group preset defaults, hardware trait defaults, and BLE tag defaults."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any, Final

from .const import (
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_CATEGORY,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_PINNED_PAGE_TITLES,
    CONF_SYNC_DEVICE_AREA,
    CONF_TOOLS_ITEMS,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES,
    DEFAULT_TOOLS_ITEMS,
    normalize_device_slug,
)
from .protocol_specs import ShortcutItemDict, default_dock_items

DEFAULT_DEVICE_GROUPS: Final[list[dict[str, Any]]] = [
    {
        "id": "pocket_carry",
        "name": "Pocket Carry",
        "description": "Compact pocket-carried displays with docked-only tap/wake-word, pickup wake disabled, and 15 min battery hibernate",
        "builtin": True,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Docked Only",
            "pickup_to_wake": "Disabled",
            "battery_screen_timeout": "30s",
            "docked_idle_timeout": "1 min",
            "battery_hibernate_timeout": "15 min",
            "screensaver_mode": "Docked Only",
            "wake_word_mode": "Docked Only",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 90,
            "night_brightness": 35,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld + Screen Off",
        },
    },
    {
        "id": "handhelds",
        "name": "Handhelds",
        "description": "Battery-powered roaming displays with pickup and single-tap wake",
        "builtin": True,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Single Tap",
            "pickup_to_wake": "Always On",
            "battery_screen_timeout": "30s",
            "docked_idle_timeout": "1 min",
            "battery_hibernate_timeout": "30 min",
            "screensaver_mode": "Docked Only",
            "wake_word_mode": "Docked Only",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 90,
            "night_brightness": 35,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld + Screen Off",
        },
    },
    {
        "id": "wearables",
        "name": "Wearables",
        "description": "Compact wearable displays with double-tap wake on battery and 15s screen timeout",
        "builtin": True,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Double Tap",
            "pickup_to_wake": "Always On",
            "battery_screen_timeout": "15s",
            "docked_idle_timeout": "1 min",
            "battery_hibernate_timeout": "15 min",
            "screensaver_mode": "Docked Only",
            "wake_word_mode": "Docked Only",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 80,
            "night_brightness": 25,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld + Screen Off",
        },
    },
    {
        "id": "wall_panels",
        "name": "Wall & Desk Panels",
        "description": "Stationary mains-powered panels with always-on Home screen, Always-On wake word, and no battery hibernate",
        "builtin": True,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Single Tap",
            "pickup_to_wake": "Disabled",
            "battery_screen_timeout": "Never",
            "docked_idle_timeout": "Never",
            "battery_hibernate_timeout": "Disabled",
            "screensaver_mode": "Never",
            "wake_word_mode": "Always On",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 90,
            "night_brightness": 35,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld Only",
        },
    },
]

_ALNUM_RE: Final = re.compile(r"[A-Za-z0-9]")
_BLE_CATEGORY_SET: Final[frozenset[str]] = frozenset({"auto", "phone", "ble_tag"})


def _manifest_int(manifest: Mapping[str, object], key: str) -> int:
    val = manifest.get(key)
    if isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def compute_hardware_defaults(
    manifest: Mapping[str, object] | None,
    *,
    esp_area_id: str = "",
    has_native_slots: bool = False,
    has_ble_beacon: bool = False,
    dock_items: list[ShortcutItemDict] | None = None,
) -> dict[str, Any]:
    """Compute onboarding defaults purely from hardware manifest traits and Area/slot flags."""
    m = manifest or {}
    clean_area = str(esp_area_id or "").strip()
    has_display = _manifest_int(m, "display") != 0 if "display" in m else True
    is_stationary = _manifest_int(m, "stationary") == 1
    if m and has_display and _manifest_int(m, "w") > 0 and _manifest_int(m, "h") > 0:
        is_wearable = _manifest_int(m, "wearable") == 1
        is_round_battery = (
            str(m.get("shape") or "").strip().lower() == "circle"
            and _manifest_int(m, "battery") == 1
        )
        default_grp = (
            "wall_panels"
            if is_stationary
            else (
                "wearables"
                if is_wearable
                else ("pocket_carry" if is_round_battery else "handhelds")
            )
        )
        default_roaming = not is_stationary
        return {
            CONF_DEVICE_GROUP: default_grp,
            CONF_NATIVE_BLE_TRACKING: default_roaming,
            CONF_BLE_AUTO_SWITCH: default_roaming,
            CONF_SYNC_DEVICE_AREA: default_roaming and not is_stationary,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "" if default_roaming else clean_area,
            CONF_DOCK_ITEMS: list(dock_items) if dock_items is not None else default_dock_items(),
            CONF_PINNED_ITEMS: [],
            CONF_PINNED_PAGE_TITLES: {},
            CONF_AREA_CATEGORIES: DEFAULT_AREA_CATEGORIES,
            CONF_HOME_CATEGORIES: DEFAULT_HOME_CATEGORIES,
            CONF_TOOLS_ITEMS: DEFAULT_TOOLS_ITEMS,
            CONF_GAMES_ITEMS: DEFAULT_GAMES_ITEMS,
        }

    if has_native_slots and has_display:
        return {
            CONF_DEVICE_GROUP: "handhelds",
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: DEFAULT_AREA_HANDOFF,
            CONF_DEFAULT_AREA: "",
            CONF_DOCK_ITEMS: list(dock_items) if dock_items is not None else default_dock_items(),
            CONF_PINNED_ITEMS: [],
            CONF_PINNED_PAGE_TITLES: {},
            CONF_AREA_CATEGORIES: DEFAULT_AREA_CATEGORIES,
            CONF_HOME_CATEGORIES: DEFAULT_HOME_CATEGORIES,
            CONF_TOOLS_ITEMS: DEFAULT_TOOLS_ITEMS,
            CONF_GAMES_ITEMS: DEFAULT_GAMES_ITEMS,
        }

    can_roam = has_ble_beacon and not is_stationary
    return {
        CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP,
        CONF_NATIVE_BLE_TRACKING: can_roam,
        CONF_BLE_AUTO_SWITCH: can_roam,
        CONF_SYNC_DEVICE_AREA: can_roam,
        CONF_AREA_HANDOFF: False,
        CONF_DEFAULT_AREA: clean_area,
    }


def merge_device_option_defaults(
    hw_defaults: Mapping[str, Any],
    matched_group: Mapping[str, Any] | None,
    enforced_keys: Iterable[str],
    *,
    default_speaker: str = "",
    ma_player_entity: str | None = None,
) -> dict[str, Any]:
    """Merge hardware defaults with the matched group baseline and discovered speaker/MA links."""
    group_defs: dict[str, Any] = {}
    raw_dev_cfg = matched_group.get("device_config") if matched_group else None
    if isinstance(raw_dev_cfg, Mapping):
        for k in enforced_keys:
            if k in (
                CONF_NATIVE_BLE_TRACKING,
                CONF_BLE_AUTO_SWITCH,
                CONF_SYNC_DEVICE_AREA,
            ):
                continue
            if k in raw_dev_cfg and raw_dev_cfg[k] is not None:
                group_defs[k] = raw_dev_cfg[k]
    defaults: dict[str, Any] = {
        **hw_defaults,
        **group_defs,
        CONF_DEFAULT_SPEAKER: default_speaker,
    }
    if ma_player_entity:
        defaults[CONF_MA_PLAYER_ENTITY] = ma_player_entity
    return defaults


def build_ble_tag_data(user_input: Mapping[str, object]) -> dict[str, Any] | None:
    """Return subentry data for a BLE tag (phone, watch, tag), or `None` if name or address is invalid."""
    raw_name = str(user_input.get("name") or "").strip()
    target = str(user_input.get(CONF_BLE_TARGET_ADDRESS) or "").strip()
    if (
        not raw_name
        or not target
        or not _ALNUM_RE.search(raw_name)
        or raw_name.lower() == "esphome device"
    ):
        return None
    slug = normalize_device_slug(raw_name)
    if slug == "esphome_device":
        return None
    raw_cat = (
        str(user_input.get(CONF_BLE_CATEGORY) or DEFAULT_BLE_CATEGORY).strip().lower()
    )
    if raw_cat not in _BLE_CATEGORY_SET:
        raw_cat = DEFAULT_BLE_CATEGORY
    return {
        CONF_DEVICE_SLUG: slug,
        CONF_BLE_TARGET_ADDRESS: target,
        CONF_BLE_CATEGORY: raw_cat,
        CONF_ASSIGNED_PERSON: str(user_input.get(CONF_ASSIGNED_PERSON) or "").strip(),
        CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP,
        CONF_DEFAULT_SPEAKER: "",
        CONF_NATIVE_BLE_TRACKING: True,
        CONF_BLE_AUTO_SWITCH: True,
        CONF_SYNC_DEVICE_AREA: False,
    }


def ble_tag_option_defaults(slug: str, target_address: str) -> dict[str, Any]:
    """Return the data a newly added BLE tag gets for this name and address (used by Reset to defaults)."""
    return (
        build_ble_tag_data({"name": slug, CONF_BLE_TARGET_ADDRESS: target_address})
        or {}
    )
