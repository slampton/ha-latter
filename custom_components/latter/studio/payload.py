"""Cohesive state payload, entity catalog, shared controls, locale overlay, and log builder for Latter Studio."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Final, NotRequired, TypedDict, Unpack
from urllib.parse import quote
from weakref import WeakKeyDictionary

import homeassistant.const as ha_const
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util

from ..areas.registry import resolve_area_ambient_light
from ..cameras.capabilities import resolve_camera_capabilities
from ..const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_CATEGORY,
    CONF_BLE_REF_POWER,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_PINNED_PAGE_TITLES,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SYNC_DEVICE_AREA,
    CONF_SYSTEM_BLE_UUID,
    CONF_TOOLS_ITEMS,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    INTEGRATION_VERSION,
    MIN_FIRMWARE_CORE_REV,
    STUDIO_REV,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..doorbell import resolve_doorbell_ring_entities
from ..groups.device_groups import (
    coordinator_supports_pref,
    get_device_groups,
    resolve_behavior_key_value,
    resolve_effective_device_group,
)
from ..groups.esphome_inspector import (
    get_esphome_device_entities,
    present_section_ids,
)
from ..hub_registry import (
    get_area_state_index,
    get_domain_data,
    get_latter_system,
    get_system_config_rev,
    iter_coordinators,
    peek_domain_data,
    peek_global_config,
)
from ..identity import esphome_service, get_discovered_latter_devices
from ..media.linking import is_music_assistant_player, ma_player_entities
from ..presence.ble_discovery import (
    describe_ble_target_model,
    get_discovered_ble_candidates,
    inspect_companion_ble_transmitter,
)
from ..presence.ble_fabric import get_all_areas_presence_summary
from ..presence.ble_registry import (
    count_area_ble_proxies,
    get_area_signatures_summary,
)
from ..protocol_policy import resolve_shortcut_entity_icon
from ..protocol_specs import (
    ACTIVITY_SOURCES_CATALOG,
    AREA_CATEGORIES_CATALOG,
    DEVICE_PREF_SPECS,
    GAMES_ITEMS_CATALOG,
    HOME_CATEGORIES_CATALOG,
    SHORTCUT_SUPPORTED_DOMAINS,
    TOOLS_ITEMS_CATALOG,
    WORLD_CLOCK_ZONES,
    humanize_device_model_label,
    resolve_device_pref_value,
)
from ..repairs_keys import parse_device_issue_id
from ..wallpapers.models import (
    PRESET_BY_ID,
    VIRTUAL_COLLECTION_ALL,
    VIRTUAL_COLLECTION_DEFAULTS,
    VIRTUAL_COLLECTION_UNCATEGORIZED,
    VIRTUAL_COLLECTION_UPLOADS,
    PhotoLibrarySnapshot,
)
from ..wallpapers.pools import (
    known_wallpaper_ids,
    list_photo_collections,
    list_wallpaper_catalog,
)
from ..wallpapers.store import get_photo_library_snapshot
from .settings_cleaners import system_settings_view
from .state_gates import find_by_subentry_id

_LOGGER = logging.getLogger(__name__)

MAX_INTERNAL_LOGS: Final = 150
_MAX_SYSLOG_SCAN: Final = 200
_MAX_SYSLOG_MSG_CHARS: Final = 600
_MUSIC_SUFFIX_LEN: Final = 6
_SHARED_SECTION_FALLBACK_ORDER: Final = 99
_DEFAULT_BLE_REF_POWER_DBM: Final = -59
_DEFAULT_BRIGHTNESS_PCT: Final = 80

STUDIO_BULK_CONTROL_DOMAINS: Final[frozenset[str]] = frozenset(
    {"select", "switch", "number"}
)

_SYSLOG_KEYWORDS: Final[tuple[str, ...]] = (
    "latter",
    "esphome",
    "aioesphomeapi",
    "sendspin",
    "music_assistant",
    "assist_satellite",
)

_CATALOG_DOMAINS: Final[tuple[str, ...]] = (
    "media_player",
    "remote",
    "number",
    "input_number",
    "alarm_control_panel",
    "camera",
    "climate",
    "lock",
    "cover",
    "vacuum",
    "weather",
    "calendar",
    "person",
)

_SHARED_SECTION_TITLES: Final[dict[str, str]] = {
    "display": "Display",
    "interface": "Interface",
    "audio": "Audio",
    "power": "Power",
    "presence": "Presence",
    "security": "Security",
}

_SHARED_SECTION_ORDER: Final[dict[str, int]] = {
    "display": 0,
    "interface": 1,
    "audio": 2,
    "power": 3,
    "presence": 4,
    "security": 5,
}

_LOCALE_OVERLAYS_CACHE: dict[str, dict[str, str]] = {}
_LOCALES_LOADED: bool = False
_LOCALES_PRELOAD_SCHEDULED: bool = False
_LOCALES_PRELOAD_TASKS: set[asyncio.Task[None]] = set()

_BLE_MODEL_CACHE: WeakKeyDictionary[Any, tuple[str, str, float, str]] = WeakKeyDictionary()
_BLE_MODEL_TTL_CONCRETE_S: Final = 60.0
_BLE_MODEL_TTL_FALLBACK_S: Final = 5.0
_BLE_GENERIC_MODEL_LABELS: Final[frozenset[str]] = frozenset(
    {"BLE beacon or tag", "Private BLE (phone or watch)"}
)
_CONN_SENSOR_SUFFIXES: Final[tuple[str, ...]] = (
    "_system_wi_fi_signal",
    "_wi_fi_signal",
    "_ip_address",
)

_CoordMeta = list[tuple[LatterCoordinator, bool, bool, str]]


@dataclass(slots=True)
class _DeviceEntityLookup:
    """Per-push index of a bound ESPHome device's registry entries grouped by domain."""

    all_entries: list[er.RegistryEntry]
    by_domain: dict[str, list[er.RegistryEntry]]

    @classmethod
    def for_device(
        cls, ent_reg: er.EntityRegistry, esphome_device_id: str | None
    ) -> _DeviceEntityLookup:
        """Build a per-push domain index with a single `er.async_entries_for_device` scan."""
        if not esphome_device_id:
            return cls([], {})
        all_entries = list(er.async_entries_for_device(ent_reg, esphome_device_id))
        by_domain: dict[str, list[er.RegistryEntry]] = {}
        for entry in all_entries:
            if not entry.disabled_by:
                by_domain.setdefault(entry.domain, []).append(entry)
        return cls(all_entries, by_domain)

    def find_entity(self, domain: str, *suffixes: str) -> str | None:
        """Find the first enabled entity in `domain` matching any suffix in order."""
        entries = self.by_domain.get(domain)
        if not entries:
            return None
        for sfx in suffixes:
            for entry in entries:
                if not sfx or entry.entity_id.endswith(sfx):
                    return str(entry.entity_id)
        return None

    def find_state(self, hass: HomeAssistant, domain: str, *suffixes: str) -> Any:
        """Return live `State` for the first matching enabled entity in `domain`, else `None`."""
        eid = self.find_entity(domain, *suffixes)
        return hass.states.get(eid) if eid else None


def build_device_entity_lookups(
    hass: HomeAssistant,
    coords: list[LatterCoordinator],
    ent_reg: er.EntityRegistry | None = None,
) -> dict[str, _DeviceEntityLookup]:
    """Build per-coordinator `_DeviceEntityLookup` maps with at most one registry scan per device."""
    reg = ent_reg if ent_reg is not None else er.async_get(hass)
    return {
        c.subentry_id: _DeviceEntityLookup.for_device(reg, c.esphome_device_id)
        for c in coords
        if not c.is_ble_tag
    }


class StudioCommandError(Exception):
    """A Studio command rejected its input; sent to the panel as a websocket error with `code`."""

    def __init__(self, code: str, message: str) -> None:
        """Store the websocket error code alongside the message."""
        super().__init__(message)
        self.code = code


class StudioLogEntry(TypedDict):
    """Single Studio or Home Assistant `system_log` diagnostic entry."""

    ts: str
    level: str
    source: str
    message: str


class StudioSystemInfo(TypedDict):
    """System-level version and protocol lockstep metadata."""

    ha_version: str
    integration_version: str
    min_firmware_core_rev: int
    studio_rev: int


class StudioIssueItem(TypedDict):
    """Active Home Assistant repair issue attributed to a Latter Device or System."""

    issue_id: str
    kind: str
    severity: str
    subentry_id: str
    device_title: str
    detail: str


class StudioDiscoveredDevice(TypedDict):
    """Unbound Latter ESPHome device available for Studio adoption."""

    esphome_device_id: str
    node_name: str
    title: str
    model_label: str
    area_name: str
    default_group: str


class StudioDevicePrefItem(TypedDict):
    """Typed native `device_prefs` descriptor for a Latter Device."""

    key: str
    label: str
    section: str
    group_tier: str | None
    domain: str
    value: Any
    options: list[str]
    min: int | float | None
    max: int | float | None
    step: int | float | None
    unit: str


class StudioSpeakerVolumePayload(TypedDict):
    """Local speaker volume control descriptor outside `esphome.sections`."""

    entity_id: str
    name: str
    domain: str
    state: str
    min: int
    max: int
    step: int
    unit: str


class StudioQuickActionItem(TypedDict):
    """Quick action button descriptor outside `esphome.sections`."""

    key: str
    device_command: str
    label: str
    domain: str
    state: str
    device_class: str


class StudioSharedControlTarget(TypedDict):
    """Per-Device state entry inside a System batch control."""

    device_slug: str
    device_group: str
    is_online: bool
    is_roaming: bool
    pref_key: str
    state: str


class StudioSharedControlItem(TypedDict):
    """Tab-aligned System batch control descriptor."""

    key: str
    pref_key: str
    tier: str | None
    section: str
    section_title: str
    name: str
    domain: str
    state: str
    options: list[str]
    option_labels: NotRequired[dict[str, str]]
    min: int | float | None
    max: int | float | None
    step: int | float | None
    unit: str
    targets: list[StudioSharedControlTarget]


class StudioEntityOption(TypedDict):
    """Generic entity option entry in Studio's entity catalog."""

    id: str
    name: str
    area_name: NotRequired[str]
    stream_kind: NotRequired[str]
    has_audio: NotRequired[bool]
    has_talkback: NotRequired[bool]
    is_doorbell: NotRequired[bool]


class StudioShortcutEntityItem(TypedDict):
    """Entity option for Dock and Pinned shortcut pickers."""

    id: str
    name: str
    domain: str
    device_class: str
    icon: str
    area_name: str


class StudioEntityCatalog(TypedDict):
    """Domain-grouped entity catalog for Studio pickers."""

    areas: list[dict[str, str]]
    ma_speakers: list[dict[str, Any]]
    ma_players: list[dict[str, str]]
    volume_targets: list[dict[str, str]]
    remotes: list[dict[str, str]]
    alarms: list[dict[str, Any]]
    cameras: list[dict[str, Any]]
    climates: list[dict[str, Any]]
    locks: list[dict[str, Any]]
    garages: list[dict[str, Any]]
    vacuums: list[dict[str, Any]]
    weathers: list[dict[str, Any]]
    calendars: list[dict[str, str]]
    persons: list[dict[str, str]]
    shortcut_entities: list[StudioShortcutEntityItem]


class StudioSystemDeviceItem(TypedDict):
    """Per-Device summary row in `system_devices`."""

    subentry_id: str
    device_slug: str
    title: str
    model_label: str
    area_id: str
    has_assigned_area: bool
    area_label: str
    status_code: str
    status_label: str
    is_online: bool
    kind: str
    ble_category: str
    has_display: bool
    has_battery: bool
    has_imu: bool
    is_roaming: bool
    hw_jpeg: bool
    device_group: str
    device_remote_group: str
    device_group_name: str
    assigned_person: str
    active_area_name: str
    is_latter_native: bool
    battery_level: int | None
    is_charging: bool
    is_usb_connected: bool
    wifi_rssi: int | None
    ip_address: str
    has_ble: bool
    ble_tracked: bool
    ble_survey_rows: list[dict[str, Any]]
    ble_packets_seen: int
    is_current: bool


class StudioDeviceCapabilities(TypedDict):
    """Capability traits exposed to Studio for the selected Device."""

    has_display: bool
    has_touch: bool
    has_imu: bool
    is_round: bool
    has_battery: bool
    has_power: bool
    has_voice: bool
    has_audio: bool
    has_ble_beacon: bool
    is_roaming_device: bool
    hw_jpeg: bool
    video_max_fps: int
    video_grid_fps: int
    screen_w: int
    screen_h: int
    grid_cols: int
    grid_rows: int


class StudioLinksPayload(TypedDict):
    """Home Assistant registry link identifiers for the selected Device."""

    entry_id: str
    esphome_device_id: str
    latter_device_id: str


class StudioPrefSpecItem(TypedDict):
    """Serialized `DevicePrefSpec` entry for Studio runtime consumers."""

    key: str
    label: str
    domain: str
    default: Any
    section: str
    group_tier: str | None
    options: list[str]
    min: int | float | None
    max: int | float | None
    step: int | float | None
    unit: str
    capability: str | None


class _ControlExtraOpts(TypedDict, total=False):
    state: str
    options: list[str]
    option_labels: dict[str, str]
    min_val: int | float | None
    max_val: int | float | None
    step: int | float | None
    unit: str


# ---------------------------------------------------------------------------
# Locale Overlays, Diagnostic Ring Buffer, and Device Target Helpers
# ---------------------------------------------------------------------------


def load_studio_locales_sync() -> dict[str, dict[str, str]]:
    """Load optional `<lang>.json` Studio translation overlays from `studio/locales/` (executor)."""
    global _LOCALES_LOADED
    locales_dir = Path(__file__).resolve().parent / "locales"
    loaded: dict[str, dict[str, str]] = {}
    if locales_dir.is_dir():
        for path in sorted(locales_dir.glob("*.json")):
            code = path.stem.strip().lower().replace("_", "-")
            if not code or code == "en":
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(raw, dict):
                loaded[code] = {
                    str(k): str(v)
                    for k, v in raw.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
    _LOCALE_OVERLAYS_CACHE.clear()
    _LOCALE_OVERLAYS_CACHE.update(loaded)
    _LOCALES_LOADED = True
    return loaded


async def _async_preload_studio_locales(hass: HomeAssistant) -> None:
    """Populate `_LOCALE_OVERLAYS_CACHE` on the executor without blocking the event loop."""
    global _LOCALES_PRELOAD_SCHEDULED
    try:
        await hass.async_add_executor_job(load_studio_locales_sync)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Studio locale overlay preload skipped: %s", err)
    finally:
        _LOCALES_PRELOAD_SCHEDULED = False


def _schedule_locale_preload_if_needed(hass: HomeAssistant) -> None:
    """Ensure Studio locale overlays load off the event loop when not yet cached."""
    global _LOCALES_PRELOAD_SCHEDULED
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        load_studio_locales_sync()
        return

    if _LOCALES_PRELOAD_SCHEDULED:
        return
    _LOCALES_PRELOAD_SCHEDULED = True
    if hasattr(hass, "async_create_task"):
        hass.async_create_task(
            _async_preload_studio_locales(hass),
            "latter_studio_locales_preload",
        )
    else:
        task = running_loop.create_task(_async_preload_studio_locales(hass))
        _LOCALES_PRELOAD_TASKS.add(task)
        task.add_done_callback(_LOCALES_PRELOAD_TASKS.discard)


def studio_language(hass: HomeAssistant) -> str:
    """Return the normalized Home Assistant language code for Studio localization."""
    return (
        str(getattr(getattr(hass, "config", None), "language", "") or "en")
        .strip()
        .lower()
        .replace("_", "-")
    )


def studio_locales_loaded() -> bool:
    """Return True once non-English Studio locale overlays have been loaded."""
    return _LOCALES_LOADED


def resolve_studio_locale_strings(hass: HomeAssistant) -> dict[str, str]:
    """Return cached non-English Studio translation strings for `hass.config.language`, or `{}`."""
    lang = studio_language(hass)
    if not lang or lang == "en" or lang.startswith("en-"):
        return {}
    if not _LOCALES_LOADED:
        _schedule_locale_preload_if_needed(hass)
        if not _LOCALES_LOADED:
            return {}
    exact = _LOCALE_OVERLAYS_CACHE.get(lang)
    if exact is not None:
        return dict(exact)
    base = lang.split("-", 1)[0]
    fallback = _LOCALE_OVERLAYS_CACHE.get(base)
    return dict(fallback) if fallback is not None else {}


def log_studio_event(
    hass: HomeAssistant, level: str, source: str, message: str
) -> None:
    """Append a diagnostic event (UTC ISO timestamp; Studio formats it for the user) to the Studio ring buffer."""
    logs = get_domain_data(hass).internal_logs
    ts = dt_util.utcnow().isoformat(timespec="seconds")
    logs.insert(
        0,
        {
            "ts": ts,
            "level": level.upper(),
            "source": source,
            "message": str(message),
        },
    )
    del logs[MAX_INTERNAL_LOGS:]


def _extract_system_log_entry(rec: Any) -> dict[str, str] | None:
    """Convert one Home Assistant `system_log` record into a `StudioLogEntry` if Latter-related."""
    d = rec.to_dict() if hasattr(rec, "to_dict") else {}
    logger_name = str(d.get("name") or "")
    msgs = d.get("message")
    msg_str = str(msgs[0] if isinstance(msgs, list) and msgs else (msgs or ""))
    exc_str = str(d.get("exception") or "").strip()
    haystack = f"{logger_name} {msg_str} {exc_str}".lower()
    if not any(k in haystack for k in _SYSLOG_KEYWORDS):
        return None
    ts_val = d.get("timestamp")
    ts_str = (
        datetime.fromtimestamp(float(ts_val), tz=UTC).isoformat(timespec="seconds")
        if ts_val
        else ""
    )
    full_msg = f"{msg_str}\n{exc_str}".strip() if exc_str else msg_str
    return {
        "ts": ts_str,
        "level": str(d.get("level") or "ERROR").upper(),
        "source": f"ha:{logger_name}",
        "message": full_msg[:_MAX_SYSLOG_MSG_CHARS],
    }


def get_combined_system_and_studio_logs(hass: HomeAssistant) -> list[dict[str, str]]:
    """Combine Latter Studio events with live entries from Home Assistant's native `system_log` handler."""
    domain_data = peek_domain_data(hass)
    combined: list[dict[str, str]] = (
        list(domain_data.internal_logs) if domain_data is not None else []
    )
    try:
        sys_log = hass.data.get("system_log")
        records = getattr(sys_log, "records", None)
        if records is not None:
            raw_list = (
                list(records.values())
                if hasattr(records, "values")
                else list(records)
            )
            for rec in reversed(raw_list[-_MAX_SYSLOG_SCAN:]):
                entry = _extract_system_log_entry(rec)
                if entry is not None:
                    combined.append(entry)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Reading system_log records skipped: %s", err)

    combined.sort(key=lambda x: x.get("ts") or "", reverse=True)
    return combined[:MAX_INTERNAL_LOGS]


def resolve_target_coordinator(
    hass: HomeAssistant, subentry_id: str | None
) -> LatterCoordinator | None:
    """Return the Device coordinator whose `subentry_id` equals `subentry_id` exactly, else `None`."""
    return find_by_subentry_id(iter_coordinators(hass), subentry_id)


def _has_active_esphome_entity(
    hass: HomeAssistant,
    esphome_device_id: str,
    *,
    entries: list[er.RegistryEntry] | None = None,
) -> bool:
    """Fallback online check across non-restore ESPHome entities when Wi-Fi/IP sensors are absent."""
    reg_entries = (
        entries
        if entries is not None
        else er.async_entries_for_device(er.async_get(hass), esphome_device_id)
    )
    for e_reg in reg_entries:
        if e_reg.platform != "esphome" or e_reg.domain in (
            "select",
            "update",
            "button",
        ):
            continue
        st_e = hass.states.get(e_reg.entity_id)
        if st_e is None or st_e.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            continue
        if (
            e_reg.domain == "binary_sensor"
            and (
                st_e.attributes.get("device_class") or e_reg.original_device_class
            )
            == "connectivity"
        ):
            if st_e.state == "on":
                return True
            continue
        return True
    return False


def _probe_conn_sensor_online(
    hass: HomeAssistant, lookup: _DeviceEntityLookup
) -> bool | None:
    """Check Wi-Fi/IP sensors in `lookup`; return True/False if any exist, else None."""
    saw_conn = False
    for sfx in _CONN_SENSOR_SUFFIXES:
        ent_id = lookup.find_entity("sensor", sfx)
        if not ent_id:
            continue
        saw_conn = True
        st = hass.states.get(ent_id)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            return True
    return False if saw_conn else None


def is_coordinator_online_for_studio(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    *,
    lookup: _DeviceEntityLookup | None = None,
) -> bool:
    """Return True when `coord` is online using Studio's unified connection state check."""
    if coord.is_ble_tag:
        tracker = coord.ble_tracker
        return bool(
            tracker is not None
            and tracker.packets_seen > 0
            and coord.is_online
        )
    if coord.is_rpc_outbox_unavailable():
        return False
    if lookup is not None:
        conn_probe = _probe_conn_sensor_online(hass, lookup)
        if conn_probe is not None:
            return conn_probe
        if coord.is_online:
            return True
        c_dev_id = coord.esphome_device_id
        return (
            _has_active_esphome_entity(hass, c_dev_id, entries=lookup.all_entries)
            if c_dev_id
            else False
        )
    if coord.is_online:
        return True
    if coord.device_entity("sensor", *_CONN_SENSOR_SUFFIXES):
        return False
    c_dev_id = coord.esphome_device_id
    return _has_active_esphome_entity(hass, c_dev_id) if c_dev_id else False


def compute_controls_signature(
    hass: HomeAssistant,
    coords: list[LatterCoordinator],
    *,
    lookups_by_sub: dict[str, _DeviceEntityLookup] | None = None,
) -> tuple[
    tuple[tuple[str, int, bool, bool, bool, str], ...],
    dict[str, bool],
    dict[str, _DeviceEntityLookup],
]:
    """Compute O(N) `system_controls` token tuple plus reusable per-device online/entity lookups."""
    lookups = (
        lookups_by_sub
        if lookups_by_sub is not None
        else build_device_entity_lookups(hass, coords)
    )
    online_by_sub: dict[str, bool] = {}
    sig_rows: list[tuple[str, int, bool, bool, bool, str]] = []
    for coord in coords:
        is_online = is_coordinator_online_for_studio(
            hass, coord, lookup=lookups.get(coord.subentry_id)
        )
        online_by_sub[coord.subentry_id] = is_online
        if not coord.is_ble_tag:
            sig_rows.append(
                (
                    coord.subentry_id,
                    coord.device_config_rev,
                    is_online,
                    coord.is_roaming_device,
                    coord.has_display,
                    coord.current_wallpaper,
                )
            )
    return tuple(sig_rows), online_by_sub, lookups


def build_device_prefs_payload(
    coordinator: LatterCoordinator,
) -> list[dict[str, Any]]:
    """Build the clean native typed `device_prefs` list for a `LatterCoordinator`."""
    if coordinator.is_ble_tag:
        return []

    dev_data = coordinator.device_data
    prefs: list[dict[str, Any]] = []
    for spec in DEVICE_PREF_SPECS:
        if not coordinator_supports_pref(coordinator, spec):
            continue
        val = resolve_device_pref_value(dev_data, spec.key)
        opts = list(spec.options)
        if (
            spec.key == "start_screen"
            and not resolve_device_pref_value(dev_data, "home_screen_enabled")
            and val == "Home"
        ):
            val = "Time App"
        elif spec.key == "clock_face" and not coordinator.is_round_display:
            opts = [o for o in opts if o != "Modern Analog"]
            if val == "Modern Analog":
                val = "Minimal Digital"
        prefs.append(
            {
                "key": spec.key,
                "label": spec.label,
                "section": spec.section,
                "group_tier": spec.group_tier,
                "domain": spec.domain,
                "value": val,
                "options": opts,
                "min": spec.min_val,
                "max": spec.max_val,
                "step": spec.step,
                "unit": spec.unit,
            }
        )
    return prefs


def build_speaker_volume_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
) -> dict[str, Any] | None:
    """Return local speaker volume metadata outside `esphome.sections`."""
    if coordinator.is_ble_tag or not coordinator.has_speaker:
        return None
    local_spk = coordinator.local_speaker
    if not local_spk:
        return None
    spk_st = hass.states.get(local_spk)
    vol_raw = (
        spk_st.attributes.get("volume_level")
        if spk_st is not None and spk_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        else None
    )
    vol_pct = (
        round(float(vol_raw) * 100)
        if isinstance(vol_raw, (int, float))
        else None
    )
    return {
        "entity_id": local_spk,
        "name": "Speaker Volume",
        "domain": "number",
        "state": str(vol_pct) if vol_pct is not None else "unavailable",
        "min": 0,
        "max": 100,
        "step": int(resolve_device_pref_value(coordinator.device_data, "volume_step_size")),
        "unit": "%",
    }


def build_quick_actions_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    *,
    is_online: bool | None = None,
) -> list[dict[str, Any]]:
    """Return quick action buttons outside `esphome.sections`."""
    if coordinator.is_ble_tag:
        return []
    online = (
        is_online
        if is_online is not None
        else is_coordinator_online_for_studio(hass, coordinator)
    )
    can_run_cmd = online and bool(
        coordinator.is_online
        or esphome_service(hass, coordinator.esphome_device_id, "latter_device_command")
    )
    cmd_state = "unknown" if can_run_cmd else "unavailable"
    action_specs: list[tuple[str, str, str]] = []
    if coordinator.has_speaker:
        action_specs.append(("find_my", "Find My Device", "identify"))
    if coordinator.has_mic:
        action_specs.append(("trigger_va", "Trigger Voice Assistant", ""))
    if coordinator.has_display:
        if bool(getattr(coordinator, "screensaver_active", False)):
            action_specs.append(("deactivate_screensaver", "Exit Screensaver", ""))
        else:
            action_specs.append(("activate_screensaver", "Activate Screensaver", ""))
    action_specs.append(("restart", "Restart Device", "restart"))

    return [
        {
            "key": cmd_key,
            "device_command": cmd_key,
            "label": label,
            "domain": "button",
            "state": cmd_state,
            "device_class": dclass,
        }
        for cmd_key, label, dclass in action_specs
    ]


def build_pref_specs_catalog() -> list[dict[str, Any]]:
    """Serialize canonical `DevicePrefSpec` metadata for Studio runtime consumers."""
    return [
        {
            "key": spec.key,
            "label": spec.label,
            "domain": spec.domain,
            "default": spec.default,
            "section": spec.section,
            "group_tier": spec.group_tier,
            "options": list(spec.options),
            "min": spec.min_val,
            "max": spec.max_val,
            "step": spec.step,
            "unit": spec.unit,
            "capability": spec.capability,
        }
        for spec in DEVICE_PREF_SPECS
    ]


def build_issues(
    hass: HomeAssistant, coords: list[LatterCoordinator]
) -> list[dict[str, str]]:
    """Return Latter's active Home Assistant repairs (the same ones Settings -> Repairs shows)."""
    by_sub = {c.subentry_id: c for c in coords}
    out: list[dict[str, str]] = []
    for issue in ir.async_get(hass).issues.values():
        if (
            issue.domain != DOMAIN
            or not issue.active
            or issue.dismissed_version is not None
        ):
            continue
        parsed = parse_device_issue_id(issue.issue_id, set(by_sub))
        kind, sub_id = (
            parsed if parsed else (str(issue.translation_key or issue.issue_id), "")
        )
        placeholders = issue.translation_placeholders or {}
        severity = getattr(issue.severity, "value", issue.severity)
        detail = str(
            placeholders.get("reason")
            or placeholders.get("missing_list")
            or (
                f"Core rev {placeholders['core_rev']} < {placeholders['min_core_rev']}"
                if kind == "outdated_firmware"
                and "core_rev" in placeholders
                and "min_core_rev" in placeholders
                else ""
            )
        )
        out.append(
            {
                "issue_id": issue.issue_id,
                "kind": kind,
                "severity": str(severity or "warning"),
                "subentry_id": sub_id,
                "device_title": by_sub[sub_id].device_title if sub_id else "",
                "detail": detail,
            }
        )
    out.sort(key=lambda i: (i["device_title"].lower(), i["kind"]))
    return out


# ---------------------------------------------------------------------------
# System Shared Controls & Entity Catalog Builders
# ---------------------------------------------------------------------------


def _make_shared_control(
    ident: tuple[str, str | None, str, str],
    name: str,
    targets: list[dict[str, Any]],
    **opts: Unpack[_ControlExtraOpts],
) -> dict[str, Any]:
    """Construct a canonical `StudioSharedControlItem` entry."""
    pref_key, tier, section, domain = ident
    entry: dict[str, Any] = {
        "key": f"{section}:{domain}:{name.lower()}",
        "pref_key": pref_key,
        "tier": tier,
        "section": section,
        "section_title": _SHARED_SECTION_TITLES.get(section, section.title()),
        "name": name,
        "domain": domain,
        "state": opts.get("state", ""),
        "options": opts.get("options", []),
        "min": opts.get("min_val"),
        "max": opts.get("max_val"),
        "step": opts.get("step"),
        "unit": opts.get("unit", ""),
        "targets": targets,
    }
    if "option_labels" in opts:
        entry["option_labels"] = opts["option_labels"]
    return entry


def _targets_for_shared_control(
    coord_meta: _CoordMeta,
    conf_key: str,
    state_fn: Callable[[LatterCoordinator], str],
    *,
    roaming_only: bool = False,
    display_only: bool = False,
) -> list[dict[str, Any]]:
    """Collect per-Device state targets for a shared System control."""
    return [
        {
            "device_slug": coord.device_slug,
            "device_group": device_group,
            "is_online": is_online,
            "is_roaming": is_roaming,
            "pref_key": conf_key,
            "state": str(state_fn(coord)),
        }
        for coord, is_online, is_roaming, device_group in coord_meta
        if (not roaming_only or is_roaming)
        and (not display_only or coord.has_display)
    ]


def _append_pref_spec_shared_controls(
    controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append native `DEVICE_PREF_SPECS` entries into `controls`."""
    for spec in DEVICE_PREF_SPECS:
        if (
            spec.group_tier is None
            and spec.key not in ("bedtime_active", "do_not_disturb")
        ) or spec.domain not in STUDIO_BULK_CONTROL_DOMAINS:
            continue
        targets: list[dict[str, Any]] = []
        for coord, is_online, is_roaming, device_group in coord_meta:
            if not coordinator_supports_pref(coord, spec):
                continue
            cur_val = resolve_device_pref_value(coord.device_data, spec.key)
            if (
                spec.key == "clock_face"
                and not coord.is_round_display
                and cur_val == "Modern Analog"
            ):
                cur_val = "Minimal Digital"
            state_val = (
                ("on" if cur_val else "off")
                if spec.domain == "switch"
                else str(cur_val)
            )
            targets.append(
                {
                    "device_slug": coord.device_slug,
                    "device_group": device_group,
                    "is_online": is_online,
                    "is_roaming": is_roaming,
                    "pref_key": spec.key,
                    "state": state_val,
                }
            )
        if targets:
            def_state = (
                ("on" if spec.default else "off")
                if spec.domain == "switch"
                else str(spec.default)
            )
            controls.append(
                _make_shared_control(
                    (spec.key, spec.group_tier, spec.section, spec.domain),
                    spec.label,
                    targets,
                    state=def_state,
                    options=list(spec.options),
                    min_val=spec.min_val,
                    max_val=spec.max_val,
                    step=spec.step,
                    unit=spec.unit,
                )
            )


def _append_behavior_shared_controls(
    controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append presence, audio handoff, dwell, and perimeter security controls."""
    for conf_key, label, sec_id, roaming_only in (
        (CONF_NATIVE_BLE_TRACKING, "Track the Area with BLE Proxies", "presence", False),
        (CONF_BLE_AUTO_SWITCH, "Auto-Switch Active Area", "presence", False),
        (CONF_SYNC_DEVICE_AREA, "Voice Follows Me", "audio", True),
        (CONF_AREA_HANDOFF, "Media Follows Device to New Area", "audio", False),
    ):
        def _switch_val(
            coord: LatterCoordinator, ck: str = conf_key
        ) -> str:
            return (
                "on"
                if bool(resolve_behavior_key_value(coord.device_data, ck))
                else "off"
            )

        targets = _targets_for_shared_control(
            coord_meta,
            conf_key,
            _switch_val,
            roaming_only=roaming_only,
        )
        if targets:
            controls.append(
                _make_shared_control(
                    (conf_key, "behavior", sec_id, "switch"),
                    label,
                    targets,
                    state="off",
                )
            )

    dwell_targets = _targets_for_shared_control(
        coord_meta,
        CONF_AREA_FOLLOW_DWELL_S,
        lambda c: str(resolve_behavior_key_value(c.device_data, CONF_AREA_FOLLOW_DWELL_S)),
        roaming_only=True,
    )
    if dwell_targets:
        controls.append(
            _make_shared_control(
                (CONF_AREA_FOLLOW_DWELL_S, "behavior", "audio", "number"),
                "Area Follow Dwell",
                dwell_targets,
                state="10",
                min_val=3,
                max_val=60,
                step=1,
                unit="s",
            )
        )

    pin_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SECURITY_PIN_POLICY,
        lambda c: str(resolve_behavior_key_value(c.device_data, CONF_SECURITY_PIN_POLICY)),
    )
    if pin_targets:
        controls.append(
            _make_shared_control(
                (CONF_SECURITY_PIN_POLICY, "behavior", "security", "select"),
                "Perimeter Security Policy",
                pin_targets,
                state="auto",
                options=["auto", "allow", "require_pin", "block"],
                option_labels={
                    "auto": "Auto (Roaming Requires PIN)",
                    "allow": "Allow Without PIN",
                    "require_pin": "Always Require PIN",
                    "block": "Block Sensitive Actions",
                },
            )
        )


def _build_wallpaper_option_pairs(
    hass: HomeAssistant,
) -> tuple[list[str], dict[str, str]]:
    """Build `(options, option_labels)` for the shared System Wallpaper select."""
    sys_wps = list_wallpaper_catalog(
        hass, "system", "", [], sign_resource=None, display_shape="square"
    )
    wp_opts: list[str] = [""]
    wp_labels: dict[str, str] = {"": "None (Weather / Solid)"}
    for wp in sys_wps:
        sid = str(wp.get("id") or "").strip()
        if sid and sid not in wp_labels:
            wp_opts.append(sid)
            wp_labels[sid] = str(wp.get("name") or wp.get("label") or sid)
    return wp_opts, wp_labels


def _build_collection_option_pairs() -> tuple[list[str], dict[str, str]]:
    """Build `(options, option_labels)` for the shared System Photo Collection select."""
    col_opts = [
        VIRTUAL_COLLECTION_ALL,
        VIRTUAL_COLLECTION_DEFAULTS,
        VIRTUAL_COLLECTION_UPLOADS,
        VIRTUAL_COLLECTION_UNCATEGORIZED,
    ]
    col_labels: dict[str, str] = {
        VIRTUAL_COLLECTION_ALL: "All photos",
        VIRTUAL_COLLECTION_DEFAULTS: "Defaults",
        VIRTUAL_COLLECTION_UPLOADS: "My photos",
        VIRTUAL_COLLECTION_UNCATEGORIZED: "Uncategorized",
    }
    for col in list_photo_collections():
        cid = str(col.get("id") or "").strip()
        if cid and cid not in col_labels:
            col_opts.append(cid)
            col_labels[cid] = str(col.get("name") or cid)
    return col_opts, col_labels


def _append_display_shared_controls(
    hass: HomeAssistant, controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append custom color, wallpaper, and Photo Frame screensaver controls."""
    color_targets = _targets_for_shared_control(
        coord_meta, CONF_DEVICE_CUSTOM_COLOR, lambda c: c.device_custom_color, display_only=True
    )
    if color_targets:
        controls.append(
            _make_shared_control(
                (CONF_DEVICE_CUSTOM_COLOR, "display", "display", "color"),
                "Custom Accent Color",
                color_targets,
                state="#3898FF",
            )
        )

    wp_targets = _targets_for_shared_control(
        coord_meta, CONF_WALLPAPER_SOURCE, lambda c: c.wallpaper_source, display_only=True
    )
    if wp_targets:
        wp_opts, wp_labels = _build_wallpaper_option_pairs(hass)
        controls.append(
            _make_shared_control(
                (CONF_WALLPAPER_SOURCE, "display", "display", "select"),
                "Wallpaper",
                wp_targets,
                options=wp_opts,
                option_labels=wp_labels,
            )
        )

    wp_rot_targets = _targets_for_shared_control(
        coord_meta,
        CONF_WALLPAPER_CYCLE_MINUTES,
        lambda c: str(c.wallpaper_cycle_minutes),
        display_only=True,
    )
    if wp_rot_targets:
        controls.append(
            _make_shared_control(
                (CONF_WALLPAPER_CYCLE_MINUTES, "display", "display", "select"),
                "Wallpaper Rotation",
                wp_rot_targets,
                state="0",
                options=["0", "5", "15", "30", "60", "360", "1440"],
                option_labels={
                    "0": "Off (Static)",
                    "5": "Every 5 min",
                    "15": "Every 15 min",
                    "30": "Every 30 min",
                    "60": "Every 1 hr",
                    "360": "Every 6 hr",
                    "1440": "Every 24 hr",
                },
            )
        )

    col_opts, col_labels = _build_collection_option_pairs()

    wp_col_targets = _targets_for_shared_control(
        coord_meta, CONF_WALLPAPER_COLLECTION, lambda c: c.wallpaper_collection, display_only=True
    )
    if wp_col_targets:
        controls.append(
            _make_shared_control(
                (CONF_WALLPAPER_COLLECTION, "display", "display", "select"),
                "Wallpaper collection",
                wp_col_targets,
                options=["", *col_opts],
                option_labels={"": "Not using a collection", **col_labels},
            )
        )

    ss_col_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SCREENSAVER_PHOTO_COLLECTION,
        lambda c: c.screensaver_photo_collection,
        display_only=True,
    )
    if ss_col_targets:
        controls.append(
            _make_shared_control(
                (CONF_SCREENSAVER_PHOTO_COLLECTION, "display", "display", "select"),
                "Photo Frame collection",
                ss_col_targets,
                state=VIRTUAL_COLLECTION_ALL,
                options=col_opts,
                option_labels=col_labels,
            )
        )

    ss_rot_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SCREENSAVER_CYCLE_MINUTES,
        lambda c: str(c.screensaver_cycle_minutes),
        display_only=True,
    )
    if ss_rot_targets:
        controls.append(
            _make_shared_control(
                (CONF_SCREENSAVER_CYCLE_MINUTES, "display", "display", "select"),
                "Photo Frame rotation",
                ss_rot_targets,
                state="5",
                options=["0", "1", "5", "15", "30", "60"],
                option_labels={
                    "0": "Off (Static)",
                    "1": "Every 1 min",
                    "5": "Every 5 min",
                    "15": "Every 15 min",
                    "30": "Every 30 min",
                    "60": "Every 1 hr",
                },
            )
        )

    ss_shuf_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SCREENSAVER_SHUFFLE,
        lambda c: "on" if c.screensaver_shuffle else "off",
        display_only=True,
    )
    if ss_shuf_targets:
        controls.append(
            _make_shared_control(
                (CONF_SCREENSAVER_SHUFFLE, "display", "display", "switch"),
                "Shuffle Photo Frame photos",
                ss_shuf_targets,
                state="off",
            )
        )


def _append_interface_shared_controls(
    hass: HomeAssistant, controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append interface pill catalogs and remote control scope controls."""
    act_card_targets = _targets_for_shared_control(
        coord_meta,
        CONF_ACTIVITY_CARD,
        lambda c: "on" if c.activity_card_enabled else "off",
        display_only=True,
    )
    if act_card_targets:
        controls.append(
            _make_shared_control(
                (CONF_ACTIVITY_CARD, "interface", "interface", "switch"),
                "Home Activity Card",
                act_card_targets,
                state="on",
            )
        )

    for conf_key, label, min_count, catalog, getter in (
        (
            CONF_ACTIVITY_SOURCES,
            "Activity Card Sources",
            0,
            ACTIVITY_SOURCES_CATALOG,
            lambda c: c.activity_sources_csv,
        ),
        (
            CONF_HOME_CATEGORIES,
            "Home Hub Categories",
            1,
            HOME_CATEGORIES_CATALOG,
            lambda c: c.home_categories_csv,
        ),
        (
            CONF_AREA_CATEGORIES,
            "Area Control Categories",
            1,
            AREA_CATEGORIES_CATALOG,
            lambda c: c.area_categories_csv,
        ),
        (CONF_TOOLS_ITEMS, "Tools", 1, TOOLS_ITEMS_CATALOG, lambda c: c.tools_items_csv),
        (CONF_GAMES_ITEMS, "Games", 1, GAMES_ITEMS_CATALOG, lambda c: c.games_items_csv),
    ):
        targets = _targets_for_shared_control(coord_meta, conf_key, getter, display_only=True)
        if targets:
            controls.append(
                _make_shared_control(
                    (conf_key, "interface", "interface", "pills"),
                    label,
                    targets,
                    options=[str(c["token"]) for c in catalog],
                    option_labels={str(c["token"]): str(c["label"]) for c in catalog},
                    min_val=min_count,
                )
            )

    rem_targets = _targets_for_shared_control(
        coord_meta, CONF_DEVICE_REMOTE_GROUP, lambda c: c.device_remote_group, display_only=True
    )
    if rem_targets:
        raw_global_cfg = peek_global_config(hass)
        rem_groups = system_settings_view(raw_global_cfg).get("remote_groups") or []
        rem_opts: list[str] = ["area_auto"]
        rem_labels: dict[str, str] = {"area_auto": "Match Active Area"}
        for rg in rem_groups:
            rg_id = f"group:{rg['id']}"
            rem_opts.append(rg_id)
            rem_labels[rg_id] = f"Group: {rg['name']}"
        rem_opts.append("all")
        rem_labels["all"] = "All System Remotes"
        controls.append(
            _make_shared_control(
                (CONF_DEVICE_REMOTE_GROUP, "interface", "interface", "select"),
                "Remote Control Scope",
                rem_targets,
                state="area_auto",
                options=rem_opts,
                option_labels=rem_labels,
            )
        )


def build_system_shared_controls(
    hass: HomeAssistant,
    coords: list[LatterCoordinator] | None = None,
    *,
    device_groups: list[dict[str, Any]] | None = None,
    precomputed_meta: _CoordMeta | None = None,
) -> list[dict[str, Any]]:
    """Build tab-aligned shared controls across all onboarded Latter Devices."""
    if precomputed_meta is not None:
        coord_meta = precomputed_meta
    else:
        all_coords = [
            c
            for c in (coords if coords is not None else iter_coordinators(hass))
            if not c.is_ble_tag
        ]
        groups = (
            device_groups if device_groups is not None else get_device_groups(hass)
        )
        lookups = build_device_entity_lookups(hass, all_coords)
        coord_meta = [
            (
                c,
                is_coordinator_online_for_studio(
                    hass, c, lookup=lookups.get(c.subentry_id)
                ),
                c.is_roaming_device,
                resolve_effective_device_group(hass, c, groups),
            )
            for c in all_coords
        ]
    controls: list[dict[str, Any]] = []
    _append_pref_spec_shared_controls(controls, coord_meta)
    _append_behavior_shared_controls(controls, coord_meta)
    _append_display_shared_controls(hass, controls, coord_meta)
    _append_interface_shared_controls(hass, controls, coord_meta)

    return sorted(
        controls,
        key=lambda x: (
            _SHARED_SECTION_ORDER.get(x["section"], _SHARED_SECTION_FALLBACK_ORDER),
            x["name"].lower(),
        ),
    )


def _is_garage_cover_state(state_obj: Any) -> bool:
    """Return True strictly for garage door `cover.*` entities."""
    dev_class = str(state_obj.attributes.get("device_class") or "").strip().lower()
    if dev_class == "garage":
        return True
    if dev_class != "":
        return False
    friendly = str(state_obj.attributes.get("friendly_name") or "")
    return "garage" in f"{state_obj.entity_id} {friendly}".lower()


def _enrich_hub_catalog_item(
    base_item: dict[str, str], state_obj: Any, idx: Any, area_reg: ar.AreaRegistry
) -> dict[str, Any]:
    """Attach `area_name` for Studio Home Hub & Camera catalog entries."""
    enriched: dict[str, Any] = dict(base_item)
    area_id = idx.resolve_entity_area_id(state_obj.entity_id) or ""
    area_entry = area_reg.async_get_area(area_id) if area_id else None
    if area_entry is not None:
        enriched["area_name"] = area_entry.name
    return enriched


def _extract_volume_overrides_map(hass: HomeAssistant) -> dict[str, str]:
    """Read System `volume_overrides` into a `{speaker_entity: target_entity}` map."""
    global_cfg = peek_global_config(hass)
    raw_vol_ov = global_cfg.get("volume_overrides")
    vol_overrides_map: dict[str, str] = {}
    if isinstance(raw_vol_ov, list):
        for ov in raw_vol_ov:
            if isinstance(ov, dict):
                spk = str(ov.get("speaker") or "").strip()
                tgt = str(ov.get("target") or "").strip()
                if spk and tgt:
                    vol_overrides_map[spk] = tgt
    elif isinstance(raw_vol_ov, dict):
        for k, v in raw_vol_ov.items():
            if k and v:
                vol_overrides_map[str(k).strip()] = str(v).strip()
    return vol_overrides_map


def _build_ma_players_catalog(hass: HomeAssistant) -> list[dict[str, str]]:
    """Build sorted Music Assistant player entity options."""
    ma_players: list[dict[str, str]] = []
    for ma_entry in ma_player_entities(hass):
        ma_st = hass.states.get(ma_entry.entity_id)
        ma_name = str(
            (ma_st.attributes.get("friendly_name") if ma_st else None)
            or ma_entry.name
            or ma_entry.original_name
            or ma_entry.entity_id
        )
        ma_suffix = (
            " (unavailable)"
            if ma_st is not None and ma_st.state == STATE_UNAVAILABLE
            else ""
        )
        ma_players.append(
            {
                "id": ma_entry.entity_id,
                "name": f"{ma_name} ({ma_entry.entity_id}){ma_suffix}",
            }
        )
    ma_players.sort(key=lambda item: item["name"].lower())
    return ma_players


def _build_shortcut_entities_catalog(
    idx: Any, area_name_by_id: dict[str, str]
) -> list[dict[str, str]]:
    """Build sorted shortcut entity picker entries from `AreaStateIndex`."""
    shortcut_entities: list[dict[str, str]] = []
    seen_sc_ids: set[str] = set()
    for sc_dom in sorted(SHORTCUT_SUPPORTED_DOMAINS):
        for st_obj in idx.states_for_domain(sc_dom):
            eid = st_obj.entity_id
            if eid in seen_sc_ids:
                continue
            seen_sc_ids.add(eid)
            friendly_lbl = str(st_obj.attributes.get("friendly_name") or eid)
            dclass = str(st_obj.attributes.get("device_class") or "")
            ent_icon = resolve_shortcut_entity_icon(
                sc_dom,
                device_class=dclass,
                entity_icon=str(st_obj.attributes.get("icon") or ""),
                state=str(st_obj.state or ""),
            )
            aid = idx.resolve_entity_area_id(eid) or ""
            shortcut_entities.append(
                {
                    "id": eid,
                    "name": friendly_lbl,
                    "domain": sc_dom,
                    "device_class": dclass,
                    "icon": ent_icon,
                    "area_name": area_name_by_id.get(aid, ""),
                }
            )
    shortcut_entities.sort(
        key=lambda item: (
            item["area_name"] == "",
            item["area_name"].lower(),
            item["name"].lower(),
            item["id"],
        )
    )
    return shortcut_entities


def _append_media_player_catalog_entry(
    hass: HomeAssistant,
    state_obj: Any,
    item: dict[str, str],
    ctx: tuple[str, str, Any, ar.AreaRegistry, list[dict[str, Any]]],
) -> None:
    """Append MA or local built-in speaker options for a `media_player` state."""
    local_spk_id, local_ma_id, idx, area_reg, ma_speakers = ctx
    ent_id = state_obj.entity_id
    if (
        local_spk_id
        and local_ma_id
        and ent_id == local_ma_id
        and local_ma_id != local_spk_id
    ):
        return
    if ent_id == local_spk_id:
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        suffix_state = " (unavailable)" if state_obj.state == STATE_UNAVAILABLE else ""
        clean_lbl = (
            friendly[:-_MUSIC_SUFFIX_LEN].strip()
            if friendly.lower().endswith(" music") and len(friendly) > _MUSIC_SUFFIX_LEN
            else friendly
        )
        ma_speakers.append(
            _enrich_hub_catalog_item(
                {
                    "id": ent_id,
                    "name": f"{clean_lbl} — built-in speaker ({ent_id}){suffix_state}",
                },
                state_obj,
                idx,
                area_reg,
            )
        )
    elif is_music_assistant_player(hass, state_obj):
        ma_speakers.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))


def build_entity_catalog(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    all_coords: list[LatterCoordinator] | None = None,
) -> dict[str, Any]:
    """Build the entity pickers for Studio using `AreaStateIndex` (zero full-state scans)."""
    _ = all_coords
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    areas_list = [
        {"id": a.id, "name": a.name}
        for a in sorted(area_reg.async_list_areas(), key=lambda x: x.name.lower())
    ]

    buckets: dict[str, list[Any]] = {
        "ma_speakers": [],
        "remotes": [],
        "volume_targets": [],
        "alarms": [],
        "cameras": [],
        "climates": [],
        "locks": [],
        "garages": [],
        "vacuums": [],
        "weathers": [],
        "calendars": [],
        "persons": [],
    }
    enriched_domain_map: dict[str, str] = {
        "alarm_control_panel": "alarms",
        "climate": "climates",
        "lock": "locks",
        "vacuum": "vacuums",
        "weather": "weathers",
    }

    local_spk_id = coordinator.local_speaker if coordinator is not None else ""
    local_ma_id = coordinator.local_ma_speaker if coordinator is not None else ""
    idx = get_area_state_index(hass)
    catalog_states = [
        st_obj for dom in _CATALOG_DOMAINS for st_obj in idx.states_for_domain(dom)
    ]
    all_cam_ids = [s.entity_id for s in catalog_states if s.domain == "camera"]
    doorbell_ring_map = (
        resolve_doorbell_ring_entities(hass, all_cam_ids) if all_cam_ids else {}
    )
    vol_overrides_map = _extract_volume_overrides_map(hass)
    mp_ctx = (local_spk_id, local_ma_id, idx, area_reg, buckets["ma_speakers"])

    for state_obj in sorted(catalog_states, key=lambda s: s.entity_id):
        ent_id = state_obj.entity_id
        domain = state_obj.domain
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        suffix_state = " (unavailable)" if state_obj.state == STATE_UNAVAILABLE else ""
        item = {"id": ent_id, "name": f"{friendly} ({ent_id}){suffix_state}"}

        if domain == "media_player":
            buckets["remotes"].append(item)
            buckets["volume_targets"].append(item)
            _append_media_player_catalog_entry(hass, state_obj, item, mp_ctx)
        elif domain == "remote":
            buckets["remotes"].append(item)
        elif domain in ("number", "input_number"):
            buckets["volume_targets"].append(item)
        elif domain in enriched_domain_map:
            buckets[enriched_domain_map[domain]].append(
                _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
            )
        elif domain == "camera":
            enriched_cam = _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
            cam_caps = resolve_camera_capabilities(
                hass,
                ent_id,
                doorbell_ring_map=doorbell_ring_map,
                volume_overrides=vol_overrides_map,
            )
            enriched_cam["stream_kind"] = cam_caps["stream_kind"]
            enriched_cam["has_audio"] = cam_caps["has_audio"]
            enriched_cam["has_talkback"] = cam_caps["has_talkback"]
            enriched_cam["is_doorbell"] = cam_caps["is_doorbell"]
            buckets["cameras"].append(enriched_cam)
        elif domain == "cover" and _is_garage_cover_state(state_obj):
            buckets["garages"].append(
                _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
            )
        elif domain == "calendar":
            buckets["calendars"].append(item)
        elif domain == "person":
            p_slug = re.sub(
                r"[^a-z0-9]+", "_", ent_id.split(".", 1)[-1].lower()
            ).strip("_")
            p_area_eid = (
                ent_reg.async_get_entity_id(
                    "sensor", DOMAIN, f"{DOMAIN}_person_{p_slug}_current_area"
                )
                or f"sensor.latter_system_{p_slug}_current_area"
            )
            buckets["persons"].append(
                {"id": ent_id, "name": f"{friendly} ({p_area_eid})"}
            )

    area_name_by_id = {a["id"]: a["name"] for a in areas_list}
    return {
        "areas": areas_list,
        "ma_speakers": buckets["ma_speakers"],
        "ma_players": _build_ma_players_catalog(hass),
        "volume_targets": buckets["volume_targets"],
        "remotes": buckets["remotes"],
        "alarms": buckets["alarms"],
        "cameras": buckets["cameras"],
        "climates": buckets["climates"],
        "locks": buckets["locks"],
        "garages": buckets["garages"],
        "vacuums": buckets["vacuums"],
        "weathers": buckets["weathers"],
        "calendars": buckets["calendars"],
        "persons": buckets["persons"],
        "shortcut_entities": _build_shortcut_entities_catalog(idx, area_name_by_id),
    }


# ---------------------------------------------------------------------------
# System & Device Studio State Payload Builders
# ---------------------------------------------------------------------------


def _parse_rounded_sensor_int(state_obj: Any) -> int | None:
    """Parse an integer sensor reading from an entity state, or `None` when unavailable."""
    if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        return None
    try:
        return round(float(state_obj.state))
    except ValueError:
        return None


def _select_primary_fw_update_entity(update_items: list[dict[str, Any]]) -> str:
    """Prefer the Latter Project Firmware `update` entity ahead of co-processor updates (ESP32-P4 C6)."""
    if not update_items:
        return ""
    for item in update_items:
        eid = str(item.get("entity_id") or "")
        if eid.endswith("_project_firmware"):
            return eid
    for item in update_items:
        eid = str(item.get("entity_id") or "")
        if "c6_co_processor" not in eid.lower():
            return eid
    return str(update_items[0].get("entity_id") or "")


def _has_esphome_firmware_update(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    coord: LatterCoordinator,
    *,
    lookup: _DeviceEntityLookup | None = None,
) -> bool:
    """Return True when the bound ESPHome device has an active firmware update entity."""
    c_upd_st = (
        lookup.find_state(hass, "update", "_project_firmware")
        if lookup is not None
        else coord.device_state("update", "_project_firmware")
    )
    if c_upd_st is not None and c_upd_st.state == "on":
        return True
    c_dev_id = coord.esphome_device_id
    if not c_dev_id:
        return False
    entries = (
        lookup.all_entries
        if lookup is not None
        else er.async_entries_for_device(ent_reg, c_dev_id)
    )
    return any(
        e_reg.platform == "esphome"
        and e_reg.domain == "update"
        and (st_e := hass.states.get(e_reg.entity_id)) is not None
        and st_e.state == "on"
        for e_reg in entries
    )


def _cached_ble_target_model(
    hass: HomeAssistant, coord: LatterCoordinator, target_addr: str
) -> str:
    """Return cached BLE tag model label, avoiding redundant full Bluetooth scanner scans."""
    cur_mac = ""
    if "." in target_addr:
        st = hass.states.get(target_addr)
        if st is not None:
            cur_mac = str(st.attributes.get("current_address") or "").strip().upper()
    now_mono = time.monotonic()
    cached = _BLE_MODEL_CACHE.get(coord)
    if (
        cached is not None
        and cached[0] == target_addr
        and cached[1] == cur_mac
        and now_mono < cached[2]
    ):
        return cached[3]
    label = describe_ble_target_model(hass, target_addr)
    ttl = (
        _BLE_MODEL_TTL_FALLBACK_S
        if label in _BLE_GENERIC_MODEL_LABELS
        else _BLE_MODEL_TTL_CONCRETE_S
    )
    try:
        _BLE_MODEL_CACHE[coord] = (target_addr, cur_mac, now_mono + ttl, label)
    except TypeError:
        pass
    return label


def _resolve_ble_tag_model_and_category(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    ent_reg: er.EntityRegistry,
) -> tuple[str, str]:
    """Resolve `(model_label, effective_ble_category)` for a BLE tag with a single cached lookup."""
    addr = coord.ble_target_address
    model_label = _cached_ble_target_model(hass, coord, addr)
    cfg_norm = coord.configured_ble_category
    if cfg_norm in ("phone", "ble_tag"):
        return model_label, cfg_norm
    if "." not in addr:
        return model_label, "ble_tag"
    ent_entry = ent_reg.async_get(addr)
    st = hass.states.get(addr)
    low = addr.lower()
    uid_low = str(ent_entry.unique_id or "").lower() if ent_entry is not None else ""
    if (
        (ent_entry is not None and ent_entry.platform == "mobile_app")
        or low.endswith(("_ble_transmitter", "_ble_emitter"))
        or uid_low.endswith("_ble_emitter")
    ):
        return model_label, "phone"
    if (
        (ent_entry is not None and ent_entry.platform == "private_ble_device")
        or "private_ble" in low
        or (st is not None and st.attributes.get("current_address"))
    ):
        return model_label, ("ble_tag" if "airpods" in model_label.lower() else "phone")
    return model_label, "ble_tag"


def _resolve_system_device_area(
    area_reg: ar.AreaRegistry,
    coord: LatterCoordinator,
    c_dev_entry: dr.DeviceEntry | None,
    live_area_state: str,
    *,
    is_online: bool,
) -> tuple[str, str, bool]:
    """Resolve `(area_id, area_label, has_assigned_area)` for a `system_devices` row."""
    static_area_id = (
        str(coord.get_opt(CONF_DEFAULT_AREA) or "").strip()
        or (str(c_dev_entry.area_id or "").strip() if c_dev_entry else "")
        if (not coord.is_ble_tag and not coord.native_ble_tracking_enabled)
        else ""
    )
    a_obj = area_reg.async_get_area(static_area_id) if static_area_id else None
    if a_obj is not None:
        return static_area_id, a_obj.name, True
    if not (coord.native_ble_tracking_enabled or coord.is_ble_tag):
        return "", "", False

    c_away = coord.is_device_away()
    tracker = coord.ble_tracker
    roaming_aid = (
        str(tracker.current_area_id or "").strip()
        if coord.is_ble_tag and tracker is not None
        else str(coord.active_area_id or "").strip()
    )
    roaming_area_obj = (
        area_reg.async_get_area(roaming_aid) if roaming_aid and not c_away else None
    )
    area_id = roaming_aid if roaming_area_obj is not None else ""
    if (
        not c_away
        and (not coord.is_ble_tag or is_online)
        and live_area_state not in ("", "Away", "Unassigned")
    ):
        return area_id, f"{live_area_state} (Roaming)", False
    return area_id, "Roaming", False


def _resolve_system_device_status(
    coord: LatterCoordinator, *, is_online: bool, has_update: bool
) -> tuple[str, str]:
    """Resolve `(status_code, status_label)` for a `system_devices` row."""
    if coord.is_ble_tag:
        if is_online:
            return "online", "Online"
        return ("away", "Away") if coord.is_device_away() else ("scanning", "Scanning")
    if has_update:
        return "update", "Update available"
    if is_online:
        return "online", "Online"
    return (
        ("offline", "Sleeping")
        if coord.is_ble_sleep_expected()
        else ("offline", "Offline")
    )


def _build_system_device_item(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    current_subentry_id: str,
    group_name_map: dict[str, str],
    registries: tuple[ar.AreaRegistry, dr.DeviceRegistry, er.EntityRegistry],
    *,
    is_online: bool | None = None,
    device_group: str | None = None,
    lookup: _DeviceEntityLookup | None = None,
) -> dict[str, Any]:
    """Build one Device/BLE-tag summary dict for `system_devices`."""
    area_reg, dev_reg, ent_reg = registries
    c_area_name = coord.active_area_name
    live_area_state, _ = coord.get_current_area_and_distance()
    c_grp = device_group if device_group is not None else coord.device_group
    c_manifest = coord.hardware_manifest
    c_dev_id = coord.esphome_device_id
    c_has_native_svc = bool(
        esphome_service(hass, c_dev_id, "latter_set_slots")
        or esphome_service(hass, c_dev_id, "latter_show_notification")
        or c_manifest
    )
    tracker = coord.ble_tracker
    c_survey_rows = (
        tracker.get_scanner_calibration_telemetry()
        if tracker is not None and hasattr(tracker, "get_scanner_calibration_telemetry")
        else []
    )
    got_dev = dev_reg.async_get(c_dev_id) if c_dev_id else None
    c_dev_entry = got_dev if isinstance(got_dev, dr.DeviceEntry) else None
    if coord.is_ble_tag:
        c_model_label, c_ble_cat = _resolve_ble_tag_model_and_category(
            hass, coord, ent_reg
        )
    else:
        raw_model = str((c_dev_entry.model if c_dev_entry else "") or "").strip()
        c_model_label = humanize_device_model_label(raw_model, c_manifest)
        c_ble_cat = ""

    def _state(domain: str, *suffixes: str) -> Any:
        if lookup is not None:
            return lookup.find_state(hass, domain, *suffixes)
        return coord.device_state(domain, *suffixes)

    def _entity(domain: str, *suffixes: str) -> str | None:
        if lookup is not None:
            return lookup.find_entity(domain, *suffixes)
        return coord.device_entity(domain, *suffixes)

    c_ip_st = _state("sensor", "_ip_address")
    c_ip_val = (
        str(c_ip_st.state)
        if (c_ip_st and c_ip_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""))
        else ""
    )
    c_is_online = (
        is_online
        if is_online is not None
        else is_coordinator_online_for_studio(hass, coord, lookup=lookup)
    )
    c_has_update = (
        False
        if coord.is_ble_tag
        else _has_esphome_firmware_update(hass, ent_reg, coord, lookup=lookup)
    )
    c_area_id, c_area_label, c_has_assigned_area = _resolve_system_device_area(
        area_reg, coord, c_dev_entry, live_area_state, is_online=c_is_online
    )
    c_status_code, c_status_label = _resolve_system_device_status(
        coord, is_online=c_is_online, has_update=c_has_update
    )
    c_chg_st = _state("binary_sensor", "_battery_charging")
    c_usb_st = _state("binary_sensor", "_usb_power_connected")
    c_has_fw_upd_ent = (
        False if coord.is_ble_tag else (_entity("update", "_project_firmware") is not None)
    )
    c_has_ble = bool(
        coord.native_ble_tracking_enabled
        or tracker is not None
        or c_has_native_svc
        or coord.has_ble_beacon
    )

    return {
        "subentry_id": coord.subentry_id,
        "device_slug": coord.device_slug,
        "title": coord.device_title,
        "model_label": c_model_label,
        "area_id": c_area_id,
        "has_assigned_area": c_has_assigned_area,
        "area_label": c_area_label,
        "status_code": c_status_code,
        "status_label": c_status_label,
        "is_online": c_is_online,
        "kind": "ble_tag" if coord.is_ble_tag else "device",
        "ble_category": c_ble_cat,
        "has_display": coord.has_display,
        "has_battery": coord.has_battery,
        "has_imu": coord.has_imu,
        "is_roaming": coord.is_roaming_device,
        "hw_jpeg": coord.supports_hw_jpeg,
        "device_group": c_grp,
        "device_remote_group": coord.device_remote_group,
        "device_group_name": (
            ("Phones" if c_ble_cat == "phone" else "BLE tags")
            if coord.is_ble_tag
            else (
                "Custom"
                if c_grp == DEFAULT_DEVICE_GROUP
                else group_name_map.get(c_grp, c_grp.replace("_", " ").title())
            )
        ),
        "assigned_person": coord.assigned_person,
        "active_area_name": live_area_state if coord.is_ble_tag else c_area_name,
        "is_latter_native": bool(
            not coord.is_ble_tag and (c_has_native_svc or c_has_fw_upd_ent)
        ),
        "battery_level": _parse_rounded_sensor_int(_state("sensor", "_battery_level")),
        "is_charging": bool(c_chg_st and c_chg_st.state == "on"),
        "is_usb_connected": bool(c_usb_st and c_usb_st.state == "on"),
        "wifi_rssi": _parse_rounded_sensor_int(
            _state("sensor", "_system_wi_fi_signal", "_wi_fi_signal")
        ),
        "ip_address": c_ip_val,
        "has_ble": c_has_ble,
        "ble_tracked": bool(coord.is_ble_tag or coord.native_ble_tracking_enabled),
        "ble_survey_rows": c_survey_rows,
        "ble_packets_seen": tracker.packets_seen if tracker is not None else 0,
        "is_current": coord.subentry_id == current_subentry_id,
    }


def _populate_optional_system_sections(
    hass: HomeAssistant,
    section: dict[str, Any],
    coords: list[LatterCoordinator],
    raw_global_cfg: Mapping[str, Any],
    *,
    coord_meta: _CoordMeta,
    skip_sections: Collection[str],
) -> None:
    """Populate gated heavy System sections only when absent from `skip_sections`."""
    if "locale_strings" not in skip_sections:
        section["locale_strings"] = resolve_studio_locale_strings(hass)
    if "discovered_latter_devices" not in skip_sections:
        section["discovered_latter_devices"] = get_discovered_latter_devices(hass)
    if "ignored_latter_devices" not in skip_sections:
        section["ignored_latter_devices"] = get_discovered_latter_devices(
            hass, only_ignored=True
        )
    if "system_controls" not in skip_sections:
        section["system_controls"] = build_system_shared_controls(
            hass, coords, precomputed_meta=coord_meta
        )
    if "ble_area_signatures" not in skip_sections:
        section["ble_area_signatures"] = get_area_signatures_summary(hass)
    if "discovered_ble_devices" not in skip_sections:
        onboarded_slugs = {c.device_slug for c in coords}
        onboarded_ble_addrs = (
            {c.ble_target_address for c in coords if c.ble_target_address}
            | {
                c.ble_beacon_uuid
                for c in coords
                if not c.is_ble_tag and c.ble_beacon_uuid
            }
            | {DEFAULT_BLE_BEACON_UUID}
        )
        if sys_ble_uuid := str(raw_global_cfg.get(CONF_SYSTEM_BLE_UUID) or "").strip():
            onboarded_ble_addrs.add(sys_ble_uuid)
        section["discovered_ble_devices"] = get_discovered_ble_candidates(
            hass,
            onboarded_slugs,
            onboarded_ble_addrs,
        )
    if "photo_collections" not in skip_sections:
        section["photo_collections"] = list_photo_collections()
    if "system_wallpapers" not in skip_sections:
        sys_obj = get_latter_system(hass)
        sign_fn = (
            sys_obj.url_signer.sign_payload_resource if sys_obj is not None else None
        )
        section["system_wallpapers"] = list_wallpaper_catalog(
            hass,
            "system",
            "",
            [],
            sign_resource=sign_fn,
            display_shape="square",
        )


def build_system_section(
    hass: HomeAssistant,
    current_subentry_id: str,
    *,
    all_coords: list[LatterCoordinator] | None = None,
    include_logs: bool = False,
    skip_sections: Collection[str] = (),
    online_by_sub: Mapping[str, bool] | None = None,
    lookups_by_sub: Mapping[str, _DeviceEntityLookup] | None = None,
    registries: tuple[ar.AreaRegistry, dr.DeviceRegistry, er.EntityRegistry] | None = None,
) -> dict[str, Any]:
    """Build the System-scoped part of the Studio payload (no Device needed)."""
    device_groups = get_device_groups(hass)
    group_name_map = {
        g["id"]: g["name"]
        for g in device_groups
        if isinstance(g, dict) and g.get("id")
    }
    regs = (
        registries
        if registries is not None
        else (ar.async_get(hass), dr.async_get(hass), er.async_get(hass))
    )
    coords = all_coords if all_coords is not None else list(iter_coordinators(hass))
    lookups = (
        lookups_by_sub
        if lookups_by_sub is not None
        else build_device_entity_lookups(hass, coords, regs[2])
    )
    system_devices: list[dict[str, Any]] = []
    coord_meta: _CoordMeta = []
    for coord in coords:
        lookup = lookups.get(coord.subentry_id)
        is_online = (
            online_by_sub[coord.subentry_id]
            if online_by_sub is not None and coord.subentry_id in online_by_sub
            else is_coordinator_online_for_studio(hass, coord, lookup=lookup)
        )
        dev_grp = (
            ""
            if coord.is_ble_tag
            else resolve_effective_device_group(hass, coord, device_groups)
        )
        if not coord.is_ble_tag:
            coord_meta.append((coord, is_online, coord.is_roaming_device, dev_grp))
        system_devices.append(
            _build_system_device_item(
                hass,
                coord,
                current_subentry_id,
                group_name_map,
                regs,
                is_online=is_online,
                device_group=dev_grp,
                lookup=lookup,
            )
        )
    raw_global_cfg = peek_global_config(hass)
    section: dict[str, Any] = {
        "internal_logs": (
            get_combined_system_and_studio_logs(hass) if include_logs else []
        ),
        "system_info": {
            "ha_version": str(
                getattr(ha_const, "__version__", "")
                or getattr(getattr(hass, "config", None), "version", "")
                or ""
            ),
            "integration_version": INTEGRATION_VERSION,
            "min_firmware_core_rev": MIN_FIRMWARE_CORE_REV,
            "studio_rev": STUDIO_REV,
        },
        "system_devices": system_devices,
        "issues": build_issues(hass, coords),
        "ble_proxy_count": count_area_ble_proxies(hass),
        "device_groups": device_groups,
        "system_config": system_settings_view(raw_global_cfg),
        "has_security_pin": bool(raw_global_cfg.get(CONF_SECURITY_PIN_HASH)),
    }
    _populate_optional_system_sections(
        hass,
        section,
        coords,
        raw_global_cfg,
        coord_meta=coord_meta,
        skip_sections=skip_sections,
    )
    return section


def _build_device_capabilities(
    coordinator: LatterCoordinator,
    sec_ids: set[str],
    local_spk_id: str,
) -> dict[str, Any]:
    """Build capability flags for the targeted `coordinator`."""
    return {
        "has_display": coordinator.has_display,
        "has_touch": coordinator.has_touch,
        "has_imu": coordinator.has_imu,
        "is_round": coordinator.is_round_display,
        "has_battery": coordinator.has_battery,
        "has_power": not coordinator.is_ble_tag
        and (
            coordinator.has_display
            or coordinator.has_battery
            or ("sleep" in sec_ids)
            or ("battery" in sec_ids)
        ),
        "has_voice": not coordinator.is_ble_tag
        and (coordinator.has_mic or ("voice" in sec_ids)),
        "has_audio": (
            not coordinator.is_ble_tag
            and (
                coordinator.has_audio
                or bool(local_spk_id)
                or ("sound" in sec_ids)
                or ("music" in sec_ids)
            )
        ),
        "has_ble_beacon": coordinator.has_ble_beacon,
        "is_roaming_device": coordinator.is_roaming_device,
        "hw_jpeg": coordinator.supports_hw_jpeg,
        "video_max_fps": coordinator.video_max_fps,
        "video_grid_fps": coordinator.video_grid_fps,
        "screen_w": coordinator.screen_width,
        "screen_h": coordinator.screen_height,
        "grid_cols": coordinator.grid_cols,
        "grid_rows": coordinator.grid_rows,
    }


def _build_device_config_data(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    clean_wallpaper_favorites: list[str],
    clean_screensaver_photo_ids: list[str],
    *,
    dev_reg: dr.DeviceRegistry | None = None,
    resolved_device_group: str | None = None,
    resolved_ble_category: str | None = None,
) -> dict[str, Any]:
    """Build the Device `config` view dictionary for Studio."""
    local_spk_id = coordinator.local_speaker
    local_ma_id = coordinator.local_ma_speaker
    raw_def_spk = str(coordinator.get_opt(CONF_DEFAULT_SPEAKER, "") or "").strip()
    if (
        raw_def_spk
        and local_spk_id
        and local_ma_id
        and raw_def_spk == local_ma_id
    ):
        raw_def_spk = local_spk_id

    dev_pref_data = coordinator.device_data
    effective_default_area = str(
        coordinator.get_opt(CONF_DEFAULT_AREA, "") or ""
    ).strip()
    if (
        not coordinator.is_ble_tag
        and not coordinator.native_ble_tracking_enabled
        and not effective_default_area
        and coordinator.esphome_device_id
    ):
        reg = dev_reg if dev_reg is not None else dr.async_get(hass)
        esp_entry = reg.async_get(coordinator.esphome_device_id)
        if esp_entry and esp_entry.area_id:
            effective_default_area = str(esp_entry.area_id).strip()

    config_data: dict[str, Any] = {
        CONF_DEVICE_SLUG: coordinator.device_slug,
        "kind": "ble_tag" if coordinator.is_ble_tag else "device",
        "is_roaming": coordinator.is_roaming_device,
        "display_shape": coordinator.display_shape,
        CONF_DEVICE_GROUP: (
            resolved_device_group
            if resolved_device_group is not None
            else coordinator.device_group
        ),
        CONF_DEVICE_REMOTE_GROUP: coordinator.device_remote_group,
        CONF_DEFAULT_SPEAKER: raw_def_spk,
        CONF_MA_PLAYER_ENTITY: str(coordinator.get_opt(CONF_MA_PLAYER_ENTITY, "") or ""),
        CONF_DEFAULT_AREA: effective_default_area,
        CONF_NATIVE_BLE_TRACKING: coordinator.native_ble_tracking_enabled,
        CONF_BLE_BEACON_UUID: coordinator.ble_beacon_uuid,
        CONF_BLE_TARGET_ADDRESS: coordinator.ble_target_address,
        CONF_BLE_CATEGORY: coordinator.configured_ble_category,
        "effective_ble_category": (
            resolved_ble_category
            if resolved_ble_category is not None
            else coordinator.effective_ble_category
        ),
        CONF_BLE_REF_POWER: (
            round(coordinator.ble_ref_power)
            if coordinator.ble_ref_power is not None
            else None
        ),
        CONF_ASSIGNED_PERSON: coordinator.assigned_person,
        CONF_BLE_AUTO_SWITCH: coordinator.ble_auto_switch_enabled,
        CONF_SYNC_DEVICE_AREA: coordinator.sync_device_area_enabled,
        CONF_AREA_FOLLOW_DWELL_S: coordinator.area_follow_dwell_s,
        CONF_AREA_HANDOFF: coordinator.area_handoff_enabled,
        CONF_DEVICE_CUSTOM_COLOR: coordinator.device_custom_color,
        CONF_DOCK_ITEMS: coordinator.dock_items,
        CONF_PINNED_ITEMS: coordinator.pinned_items,
        CONF_PINNED_PAGE_TITLES: coordinator.pinned_page_titles,
        CONF_AREA_CATEGORIES: coordinator.area_categories_csv,
        CONF_HOME_CATEGORIES: coordinator.home_categories_csv,
        CONF_BROADCAST_SPEAKER_ENTITIES: coordinator.configured_broadcast_speaker_entities,
        CONF_CAMERA_VISIBLE_ENTITIES: coordinator.configured_camera_visible_entities,
        CONF_CAMERA_CAROUSEL_ENTITIES: coordinator.configured_camera_carousel_entities,
        CONF_TOOLS_ITEMS: coordinator.tools_items_csv,
        CONF_GAMES_ITEMS: coordinator.games_items_csv,
        CONF_ACTIVITY_CARD: coordinator.activity_card_enabled,
        CONF_ACTIVITY_SOURCES: coordinator.activity_sources_csv,
        CONF_WALLPAPER_MODE: coordinator.wallpaper_mode,
        CONF_WALLPAPER_SOURCE: coordinator.wallpaper_source,
        CONF_WALLPAPER_COLLECTION: coordinator.wallpaper_collection,
        CONF_WALLPAPER_FAVORITES: clean_wallpaper_favorites,
        CONF_WALLPAPER_CYCLE_MINUTES: coordinator.wallpaper_cycle_minutes,
        CONF_SCREENSAVER_PHOTO_MODE: coordinator.screensaver_photo_mode,
        CONF_SCREENSAVER_PHOTO_SOURCE: coordinator.configured_screensaver_photo_source,
        CONF_SCREENSAVER_PHOTO_COLLECTION: coordinator.screensaver_photo_collection,
        CONF_SCREENSAVER_PHOTO_IDS: clean_screensaver_photo_ids,
        CONF_SCREENSAVER_CYCLE_MINUTES: coordinator.screensaver_cycle_minutes,
        CONF_SCREENSAVER_SHUFFLE: coordinator.screensaver_shuffle,
        CONF_SECURITY_PIN_POLICY: coordinator.configured_security_pin_policy,
        "has_security_pin": coordinator.has_security_pin,
        **{
            spec.key: resolve_device_pref_value(dev_pref_data, spec.key)
            for spec in DEVICE_PREF_SPECS
        },
    }
    if (
        not config_data.get("home_screen_enabled", True)
        and config_data.get("start_screen") == "Home"
    ):
        config_data["start_screen"] = "Time App"
    if (
        not coordinator.supports_hw_jpeg
        and config_data.get("camera_doorbell_popup") == "Live Video"
    ):
        config_data["camera_doorbell_popup"] = "Snapshot"
    return config_data


def _build_single_wallpaper_thumb_url(
    coordinator: LatterCoordinator,
    source_id: str,
    snap: PhotoLibrarySnapshot,
) -> str:
    """Sign a single active photo thumbnail URL without building the full wallpaper catalog."""
    if not source_id:
        return ""
    wp_shape = "square" if coordinator.display_shape == "square" else "circle"
    slug = normalize_device_slug(coordinator.device_slug or "system")
    preset = PRESET_BY_ID.get(source_id)
    if preset is not None:
        mode = "wallpaper" if preset["kind"] == "dynamic_preset" else "screensaver"
        crop_tag = ""
    elif (rec := snap.photos.get(source_id)) is not None:
        mode = "screensaver"
        crop_tag = rec.crop.crop_hash()
    else:
        return ""
    sig = coordinator.sign_payload_resource(
        f"wallpaper:{source_id}|240|240|{wp_shape}|{mode}"
    )
    v_q = f"&v={crop_tag}" if crop_tag else ""
    return (
        f"/api/latter/wallpaper/{slug}"
        f"?w=240&h=240&shape={wp_shape}&mode={mode}"
        f"&src={quote(source_id, safe='')}&sig={sig}{v_q}"
    )


def _resolve_active_photo_thumb_urls(
    coordinator: LatterCoordinator,
    wallpapers_catalog: list[dict[str, Any]] | None,
    active_wp_id: str,
    active_ss_id: str,
) -> tuple[str, str]:
    """Return `(active_wallpaper_thumb_url, active_screensaver_photo_thumb_url)`."""
    if wallpapers_catalog is not None:
        wp_thumb_by_id = {
            str(item.get("id") or ""): str(item.get("thumb_url") or "")
            for item in wallpapers_catalog
        }
        return wp_thumb_by_id.get(active_wp_id, ""), wp_thumb_by_id.get(active_ss_id, "")
    snap = get_photo_library_snapshot()
    wp_url = _build_single_wallpaper_thumb_url(coordinator, active_wp_id, snap)
    ss_url = (
        wp_url
        if active_ss_id and active_ss_id == active_wp_id
        else _build_single_wallpaper_thumb_url(coordinator, active_ss_id, snap)
    )
    return wp_url, ss_url


def _build_device_live_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    esphome_inspector: dict[str, Any],
    wallpapers_catalog: list[dict[str, Any]] | None,
    presence_grid: list[dict[str, Any]],
    *,
    lookup: _DeviceEntityLookup | None = None,
    is_online: bool | None = None,
) -> dict[str, Any]:
    """Build the `live` telemetry and status dictionary for the selected Device."""
    all_esp_items: list[dict[str, Any]] = [
        item
        for sec in esphome_inspector.get("sections", [])
        for item in (sec.get("items") or [])
    ]
    fw_st = (
        lookup.find_state(hass, "sensor", "_firmware_version")
        if lookup is not None
        else coordinator.device_state("sensor", "_firmware_version")
    )
    fw_version = (
        str(fw_st.state)
        if fw_st is not None and fw_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "")
        else str(esphome_inspector.get("device", {}).get("sw_version") or "")
    )
    update_items = [
        it
        for it in all_esp_items
        if it.get("domain") == "update" and it.get("entity_id")
    ]
    fw_update_entity = _select_primary_fw_update_entity(update_items)

    wp_pool = coordinator.resolve_wallpaper_rotation_pool()
    ss_pool = coordinator.resolve_screensaver_photo_pool()
    active_wp_id = coordinator.wallpaper_source
    active_ss_id = coordinator.screensaver_photo_source
    active_wp_thumb, active_ss_thumb = _resolve_active_photo_thumb_urls(
        coordinator, wallpapers_catalog, active_wp_id, active_ss_id
    )
    active_ambient = (
        resolve_area_ambient_light(hass, coordinator.active_area_id or None)
        if not coordinator.is_ble_tag
        else {
            "resolved_entity": "",
            "resolved_name": "",
            "lux_display": "",
            "ambient_pct": None,
        }
    )
    active_area_name = (
        coordinator.get_current_area_and_distance()[0]
        if coordinator.is_ble_tag
        else coordinator.active_area_name
    )
    local_spk_id = coordinator.local_speaker
    local_ma_id = coordinator.local_ma_speaker
    tracker = coordinator.ble_tracker

    live: dict[str, Any] = {
        "active_wallpaper_id": active_wp_id,
        "active_wallpaper_thumb_url": active_wp_thumb,
        "wallpaper_pool_count": len(wp_pool),
        "active_screensaver_photo_id": active_ss_id,
        "active_screensaver_photo_thumb_url": active_ss_thumb,
        "screensaver_pool_count": len(ss_pool),
        "active_area_name": active_area_name,
        "active_area_lux_display": active_ambient["lux_display"],
        "active_area_ambient_pct": active_ambient["ambient_pct"],
        "active_area_illuminance_entity": active_ambient["resolved_entity"],
        "active_area_illuminance_name": active_ambient["resolved_name"],
        "ma_link_matched": bool(
            local_ma_id
            or not local_spk_id
            or not hass.config_entries.async_entries("music_assistant")
        ),
        "ble_closest_proxy": tracker.closest_scanner if tracker is not None else "",
        "ble_detected_ref_power": (
            round(float(getattr(tracker, "effective_ref_power_dbm", _DEFAULT_BLE_REF_POWER_DBM)))
            if tracker is not None
            else _DEFAULT_BLE_REF_POWER_DBM
        ),
        "ble_transmitter_status": (
            inspect_companion_ble_transmitter(hass, coordinator.ble_target_address)
            if coordinator.is_ble_tag
            else None
        ),
        "area_presence_grid": presence_grid,
        "device_sw_version": fw_version,
        "core_rev": str(coordinator.hardware_manifest.get("core_rev") or ""),
        "firmware_outdated": bool(coordinator.firmware_outdated),
        "fw_update_entity": fw_update_entity,
        "fw_update_available": any(it.get("state") == "on" for it in update_items),
        "effective_security_pin_policy": coordinator.security_pin_policy,
        "has_security_pin": coordinator.has_security_pin,
        "is_ble_sleep_expected": bool(coordinator.is_ble_sleep_expected()),
    }
    if not coordinator.is_ble_tag:
        online_fallback = (
            is_online
            if is_online is not None
            else is_coordinator_online_for_studio(hass, coordinator, lookup=lookup)
        )
        live.update(
            {
                "radio_connected": bool(
                    getattr(coordinator, "radio_connected", online_fallback)
                ),
                "display_power_state": int(
                    getattr(coordinator, "display_power_state", 0)
                ),
                "display_brightness_pct": int(
                    getattr(
                        coordinator,
                        "display_brightness_pct",
                        _DEFAULT_BRIGHTNESS_PCT,
                    )
                ),
                "screensaver_active": bool(
                    getattr(coordinator, "screensaver_active", False)
                ),
                "telemetry": getattr(coordinator, "device_telemetry", None),
                "timer_running": bool(coordinator.timer_running),
                "timer_paused": bool(coordinator.timer_paused),
                "timer_remaining_sec": int(coordinator.current_timer_remaining_sec),
                "timer_ends_at": (
                    coordinator.timer_ends_at_utc if coordinator.timer_running else ""
                ),
                "stopwatch_running": bool(coordinator.stopwatch_running),
                "stopwatch_paused": bool(coordinator.stopwatch_paused),
                "stopwatch_elapsed_sec": int(coordinator.current_stopwatch_elapsed_sec),
                "stopwatch_started_at": (
                    coordinator.stopwatch_started_at_utc
                    if coordinator.stopwatch_running
                    else ""
                ),
                "alarm_ringing": bool(coordinator.alarm_ringing),
            }
        )
    return live


def _resolve_device_wallpapers_and_pools(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    skip_wallpapers: bool,
) -> tuple[list[dict[str, Any]] | None, list[str], list[str]]:
    """Build or skip the device wallpaper catalog and return clean favorite/screensaver ID lists."""
    if skip_wallpapers:
        wallpapers_catalog: list[dict[str, Any]] | None = None
        valid_wp_ids = known_wallpaper_ids(include_dynamic=True)
        valid_ss_ids = known_wallpaper_ids(include_dynamic=False)
    else:
        wallpapers_catalog = list_wallpaper_catalog(
            hass,
            coordinator.device_slug,
            coordinator.wallpaper_source,
            coordinator.wallpaper_favorites,
            sign_resource=coordinator.sign_payload_resource,
            display_shape=coordinator.display_shape,
        )
        valid_wp_ids = {str(item.get("id") or "") for item in wallpapers_catalog}
        valid_ss_ids = {
            str(item.get("id") or "")
            for item in wallpapers_catalog
            if item.get("kind") != "dynamic_preset"
        }
    clean_wallpaper_favorites = list(
        dict.fromkeys(
            pid for pid in coordinator.wallpaper_favorites if pid in valid_wp_ids
        )
    )
    clean_screensaver_photo_ids = list(
        dict.fromkeys(
            pid for pid in coordinator.screensaver_photo_ids if pid in valid_ss_ids
        )
    )
    return wallpapers_catalog, clean_wallpaper_favorites, clean_screensaver_photo_ids


def _extract_selected_device_meta(
    system_devices: Any, subentry_id: str
) -> tuple[str | None, str | None, bool | None]:
    """Reuse `(device_group, ble_category, is_online)` already computed in `system_devices`."""
    if not isinstance(system_devices, list):
        return None, None, None
    for row in system_devices:
        if isinstance(row, Mapping) and row.get("subentry_id") == subentry_id:
            raw_grp = row.get("device_group")
            raw_cat = row.get("ble_category")
            raw_online = row.get("is_online")
            return (
                str(raw_grp) if raw_grp is not None else None,
                str(raw_cat) if raw_cat is not None else None,
                bool(raw_online) if raw_online is not None else None,
            )
    return None, None, None


def build_studio_state_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    *,
    include_catalog: bool = True,
    include_logs: bool = False,
    skip_sections: Collection[str] = (),
    online_by_sub: Mapping[str, bool] | None = None,
    lookups_by_sub: Mapping[str, _DeviceEntityLookup] | None = None,
    system_section_override: Mapping[str, Any] | None = None,
    presence_grid_override: list[dict[str, Any]] | None = None,
    catalog_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Studio payload: the System part always, plus the Device part when a Device is targeted."""
    all_coords = list(iter_coordinators(hass))
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    lookups = (
        lookups_by_sub
        if lookups_by_sub is not None
        else (
            {}
            if system_section_override is not None
            else build_device_entity_lookups(hass, all_coords, ent_reg)
        )
    )
    target_sub_id = coordinator.subentry_id if coordinator is not None else ""
    if system_section_override is not None:
        system_part: dict[str, Any] = dict(system_section_override)
        if isinstance(system_part.get("system_devices"), list):
            system_part["system_devices"] = [
                {**d, "is_current": d.get("subentry_id") == target_sub_id}
                for d in system_part["system_devices"]
            ]
    else:
        system_part = build_system_section(
            hass,
            target_sub_id,
            all_coords=all_coords,
            include_logs=include_logs,
            skip_sections=skip_sections,
            online_by_sub=online_by_sub,
            lookups_by_sub=lookups,
            registries=(ar.async_get(hass), dev_reg, ent_reg),
        )
    base: dict[str, Any] = {
        "type": "state",
        "subentry_id": target_sub_id,
        "title": coordinator.device_title if coordinator is not None else "",
        "version": INTEGRATION_VERSION,
        "studio_rev": STUDIO_REV,
        "system_config_rev": get_system_config_rev(hass),
        "device_config_rev": (
            coordinator.device_config_rev if coordinator is not None else 0
        ),
        **system_part,
    }
    if include_catalog:
        base["catalog"] = (
            dict(catalog_override)
            if catalog_override is not None
            else build_entity_catalog(hass, coordinator, all_coords=all_coords)
        )
        if "pref_specs" not in skip_sections:
            base["pref_specs"] = build_pref_specs_catalog()
        if "world_clock_zones" not in skip_sections:
            base["world_clock_zones"] = list(WORLD_CLOCK_ZONES)
    presence_grid = (
        presence_grid_override
        if presence_grid_override is not None
        else get_all_areas_presence_summary(hass)
    )
    if coordinator is None:
        out_sys: dict[str, Any] = {
            **base,
            "capabilities": {},
            "config": {},
            "device_prefs": [],
            "quick_actions": [],
            "speaker_volume": None,
            "esphome": {"device": {}, "sections": []},
            "live": {"area_presence_grid": presence_grid},
        }
        if "wallpapers" not in skip_sections:
            out_sys["wallpapers"] = []
        return out_sys

    esphome_inspector = get_esphome_device_entities(
        hass, coordinator.esphome_device_id, coordinator.device_slug
    )
    wallpapers_catalog, clean_wp_favs, clean_ss_ids = _resolve_device_wallpapers_and_pools(
        hass, coordinator, skip_wallpapers=("wallpapers" in skip_sections)
    )
    sec_ids = present_section_ids(esphome_inspector.get("sections"))
    latter_idents = coordinator.get_device_info()["identifiers"]
    latter_dev = None
    get_by_ident = getattr(dev_reg, "async_get_device_by_identifier", None)
    if callable(get_by_ident):
        for ident in latter_idents:
            latter_dev = get_by_ident(ident, coordinator.entry.entry_id)
            if latter_dev is not None:
                break
    else:
        latter_dev = next(
            (
                d
                for d in dr.async_entries_for_config_entry(
                    dev_reg, coordinator.entry.entry_id
                )
                if d.identifiers & latter_idents
            ),
            None,
        )
    sel_grp, sel_ble_cat, sel_online = _extract_selected_device_meta(
        base.get("system_devices"), target_sub_id
    )
    sel_lookup = lookups.get(target_sub_id)

    payload: dict[str, Any] = {
        **base,
        "capabilities": _build_device_capabilities(
            coordinator, sec_ids, coordinator.local_speaker
        ),
        "config": _build_device_config_data(
            hass,
            coordinator,
            clean_wp_favs,
            clean_ss_ids,
            dev_reg=dev_reg,
            resolved_device_group=sel_grp,
            resolved_ble_category=sel_ble_cat,
        ),
        "device_prefs": build_device_prefs_payload(coordinator),
        "quick_actions": build_quick_actions_payload(
            hass, coordinator, is_online=sel_online
        ),
        "speaker_volume": build_speaker_volume_payload(hass, coordinator),
        "esphome": esphome_inspector,
        "links": {
            "entry_id": coordinator.entry.entry_id,
            "esphome_device_id": coordinator.esphome_device_id or "",
            "latter_device_id": latter_dev.id if latter_dev is not None else "",
        },
        "live": _build_device_live_payload(
            hass,
            coordinator,
            esphome_inspector,
            wallpapers_catalog,
            presence_grid,
            lookup=sel_lookup,
            is_online=sel_online,
        ),
    }
    if wallpapers_catalog is not None:
        payload["wallpapers"] = wallpapers_catalog
    return payload


__all__ = [
    "MAX_INTERNAL_LOGS",
    "STUDIO_BULK_CONTROL_DOMAINS",
    "StudioCommandError",
    "StudioDeviceCapabilities",
    "StudioDevicePrefItem",
    "StudioDiscoveredDevice",
    "StudioEntityCatalog",
    "StudioEntityOption",
    "StudioIssueItem",
    "StudioLinksPayload",
    "StudioLogEntry",
    "StudioPrefSpecItem",
    "StudioQuickActionItem",
    "StudioSharedControlItem",
    "StudioSharedControlTarget",
    "StudioShortcutEntityItem",
    "StudioSpeakerVolumePayload",
    "StudioSystemDeviceItem",
    "StudioSystemInfo",
    "build_device_entity_lookups",
    "build_device_prefs_payload",
    "build_entity_catalog",
    "build_issues",
    "build_pref_specs_catalog",
    "build_quick_actions_payload",
    "build_speaker_volume_payload",
    "build_studio_state_payload",
    "build_system_section",
    "build_system_shared_controls",
    "compute_controls_signature",
    "get_combined_system_and_studio_logs",
    "is_coordinator_online_for_studio",
    "load_studio_locales_sync",
    "log_studio_event",
    "resolve_studio_locale_strings",
    "resolve_target_coordinator",
    "studio_language",
    "studio_locales_loaded",
]
