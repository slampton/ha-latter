"""Shared Studio payload types, locale overlays, diagnostic ring buffer, and device helpers (`L3`)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any, Final, NotRequired, TypedDict

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..coordinator import LatterCoordinator
from ..groups.device_groups import coordinator_supports_pref
from ..hub_registry import iter_coordinators
from ..identity import (
    bound_elsewhere,
    device_title,
    device_unique_id,
    esphome_service,
    get_discovered_latter_devices,
    get_ignored_discovered_device_ids,
)
from ..protocol_specs import DEVICE_PREF_SPECS, resolve_device_pref_value
from ..repairs_keys import parse_device_issue_id
from .state_gates import find_by_subentry_id

_LOGGER = logging.getLogger(__name__)

MAX_INTERNAL_LOGS: Final = 150
_MAX_SYSLOG_SCAN: Final = 200
_MAX_SYSLOG_MSG_CHARS: Final = 600
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

_LOCALE_OVERLAYS_CACHE: dict[str, dict[str, str]] = {}
_LOCALES_LOADED: bool = False
_LOCALES_PRELOAD_SCHEDULED: bool = False
_LOCALES_PRELOAD_TASKS: set[asyncio.Task[None]] = set()


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
    min_firmware_sdk_rev: int
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
    volume_pct: int | None
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
    """Ensure Studio locale overlays load off the event loop when not yet cached (`M-P2-25`)."""
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


def resolve_studio_locale_strings(hass: HomeAssistant) -> dict[str, str]:
    """Return cached non-English Studio translation strings for `hass.config.language`, or `{}`."""
    lang = (
        str(getattr(getattr(hass, "config", None), "language", "") or "en")
        .strip()
        .lower()
        .replace("_", "-")
    )
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
    domain_data = hass.data.setdefault(DOMAIN, {})
    logs: list[dict[str, str]] = domain_data.setdefault("internal_logs", [])
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
    combined: list[dict[str, str]] = list(
        hass.data.get(DOMAIN, {}).get("internal_logs", [])
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


_get_combined_system_and_studio_logs = get_combined_system_and_studio_logs


def resolve_target_coordinator(
    hass: HomeAssistant, subentry_id: str | None
) -> LatterCoordinator | None:
    """Return the Device coordinator whose `subentry_id` equals `subentry_id` exactly, else `None`."""
    return find_by_subentry_id(iter_coordinators(hass), subentry_id)


def _has_active_esphome_entity(hass: HomeAssistant, esphome_device_id: str) -> bool:
    """Fallback online check across non-restore ESPHome entities when Wi-Fi/IP sensors are absent."""
    ent_reg = er.async_get(hass)
    for e_reg in er.async_entries_for_device(ent_reg, esphome_device_id):
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


def is_coordinator_online_for_studio(
    hass: HomeAssistant,
    coord: LatterCoordinator,
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
    if coord.is_online:
        return True
    if coord.device_entity(
        "sensor", "_system_wi_fi_signal", "_wi_fi_signal", "_ip_address"
    ):
        return False
    c_dev_id = coord.esphome_device_id
    return _has_active_esphome_entity(hass, c_dev_id) if c_dev_id else False


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
        "volume_pct": vol_pct,
        "state": str(vol_pct) if vol_pct is not None else "unavailable",
        "min": 0,
        "max": 100,
        "step": int(resolve_device_pref_value(coordinator.device_data, "volume_step_size")),
        "unit": "%",
    }


def build_quick_actions_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
) -> list[dict[str, Any]]:
    """Return quick action buttons outside `esphome.sections`."""
    if coordinator.is_ble_tag:
        return []
    can_run_cmd = is_coordinator_online_for_studio(hass, coordinator) and bool(
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
        out.append(
            {
                "issue_id": issue.issue_id,
                "kind": kind,
                "severity": str(severity or "warning"),
                "subentry_id": sub_id,
                "device_title": by_sub[sub_id].device_title if sub_id else "",
                "detail": str(
                    placeholders.get("reason")
                    or placeholders.get("missing_list")
                    or ""
                ),
            }
        )
    out.sort(key=lambda i: (i["device_title"].lower(), i["kind"]))
    return out


_build_issues = build_issues


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
    "_build_issues",
    "bound_elsewhere",
    "build_device_prefs_payload",
    "build_issues",
    "build_pref_specs_catalog",
    "build_quick_actions_payload",
    "build_speaker_volume_payload",
    "device_title",
    "device_unique_id",
    "get_combined_system_and_studio_logs",
    "get_discovered_latter_devices",
    "get_ignored_discovered_device_ids",
    "is_coordinator_online_for_studio",
    "load_studio_locales_sync",
    "log_studio_event",
    "resolve_studio_locale_strings",
    "resolve_target_coordinator",
]
