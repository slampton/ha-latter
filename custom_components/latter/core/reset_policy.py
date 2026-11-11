"""Reset to defaults: which Device subentry fields are kept and which go back to their defaults.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Identity and binding of an ESPHome Latter Device: kept by a reset.
DEVICE_IDENTITY_KEYS: tuple[str, ...] = (
    "esphome_device_id",
    "mac",
    "device_slug",
    "ma_player_entity",
)

# Identity of a BLE tag: its name (slug) and the address/UUID/entity it tracks.
BLE_TAG_IDENTITY_KEYS: tuple[str, ...] = (
    "device_slug",
    "ble_target_address",
)

# User options a Device subentry can hold.
DEVICE_OPTION_KEYS: tuple[str, ...] = (
    "device_group",
    "device_remote_group",
    "site_id",
    "default_page_size",
    "dock_apps",
    "activity_card",
    "activity_sources",
    "default_speaker",
    "default_area",
    "area_handoff",
    "native_ble_tracking",
    "ble_auto_switch",
    "sync_device_area",
    "area_follow_dwell_s",
    "ble_beacon_uuid",
    "ble_target_address",
    "assigned_person",
    "wallpaper_source",
    "wallpaper_favorites",
    "wallpaper_cycle_minutes",
    "device_custom_color",
    "security_pin_policy",
    "security_pin_hash",
    "security_pin",
    "clear_security_pin",
)


def reset_flags_error(
    device_settings: bool, latter_options: bool, *, is_ble_tag: bool
) -> str | None:
    """Return the translation key of the reason a reset request is invalid, or None if it's valid."""
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
    """Return the subentry data after a reset: the defaults, plus the identity keys from `current`."""
    out = {k: v for k, v in defaults.items() if k not in identity_keys}
    for key in identity_keys:
        if key in current:
            out[key] = current[key]
    return out
