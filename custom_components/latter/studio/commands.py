"""Admin-gated WebSocket API endpoints and scope-based command dispatch router for Latter Studio.

The websocket type is the scope (`studio/state_gates.py`): `latter/system/*` commands never act on the
Studio's selected Device (a System command that acts on one Device names it in its own payload), and
`latter/device/*` commands act on the Device named by the message's required `subentry_id`.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
import logging
import time
from typing import Any, Final
from weakref import WeakKeyDictionary

from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import (
    async_response,
    require_admin,
    websocket_command,
)
from homeassistant.components.websocket_api.messages import event_message
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
import probatio as vol

from ..backup import async_restore_backup_bundle, build_backup_bundle
from ..const import (
    INTEGRATION_VERSION,
    STUDIO_REV,
)
from ..coordinator import LatterCoordinator
from ..groups.device_groups import async_reset_device
from ..hub_registry import (
    _is_irrelevant_registry_update,
    get_domain_data,
    get_latter_system,
    get_system_config_rev,
    iter_coordinators,
    peek_global_config,
    register_studio_subscriber,
)
from ..identity import device_entities
from ..presence.ble_fabric import (
    build_survey_delta_payload,
    get_all_areas_presence_summary,
    get_ble_fabric,
)
from ..wallpapers.store import wallpaper_snapshot_token
from .device_commands import (
    DEVICE_COMMAND_HANDLERS,
    DEVICE_COMMAND_SCHEMAS,
    CommandHandler,
)
from .payload import (
    STUDIO_BULK_CONTROL_DOMAINS,
    StudioCommandError,
    build_entity_catalog,
    build_studio_state_payload,
    build_system_section,
    compute_controls_signature,
    log_studio_event,
    resolve_target_coordinator,
    studio_language,
    studio_locales_loaded,
)
from .settings_cleaners import SettingsScopeError
from .state_gates import (
    HASH_GATED_SECTIONS,
    HEAVY_SUBSCRIPTION_SECTIONS,
    CatalogGate,
    Scope,
    SectionHashGate,
    SectionTokenGate,
    SubscriptionTokenSnapshot,
    TargetNotAllowed,
    UnknownStudioCommand,
    command_scope,
)
from .system_commands import SYSTEM_COMMAND_HANDLERS, SYSTEM_COMMAND_SCHEMAS

_LOGGER = logging.getLogger(__name__)
_SURVEY_COALESCE_INTERVAL_S: Final = 0.25
_PUSH_DEBOUNCE_S: Final = 0.4
_SHARED_SNAPSHOT_TTL_S: Final = 0.05
_MAX_MEMO_ENTRIES: Final = 16
_SECONDS_PER_DAY: Final = 86400

_EXCLUDED_STATUS_WATCH_SUFFIXES: Final[tuple[str, ...]] = (
    "_system_rpc_outbox",
    "_rpc_outbox",
)

_STUDIO_STATUS_WATCH_SUFFIXES: Final[tuple[str, ...]] = (
    "_system_wi_fi_signal",
    "_wi_fi_signal",
    "_ip_address",
    "_battery_level",
    "_battery_charging",
    "_usb_power_connected",
    "_project_firmware",
)

_COMMAND_BASE_SKIP_SECTIONS: Final[frozenset[str]] = frozenset(
    HEAVY_SUBSCRIPTION_SECTIONS
)

_COMMAND_KEEP_SECTIONS: Final[dict[str, frozenset[str]]] = {
    "save_device_config": frozenset({"system_controls"}),
    "device_action": frozenset({"system_controls"}),
    "set_device_photo_pool": frozenset({"wallpapers", "system_controls"}),
    "save_system_config": frozenset({"system_controls"}),
    "create_device_group": frozenset({"system_controls"}),
    "delete_device_group": frozenset({"system_controls"}),
    "update_group_baseline": frozenset({"system_controls", "wallpapers"}),
    "apply_batch_device_setting": frozenset({"system_controls", "wallpapers"}),
    "capture_ble_area_signature": frozenset({"ble_area_signatures"}),
    "clear_ble_area_signature": frozenset({"ble_area_signatures"}),
    "set_ble_scanner_offset": frozenset({"ble_area_signatures"}),
    "ignore_discovered_device": frozenset(
        {"discovered_latter_devices", "ignored_latter_devices"}
    ),
    "unignore_discovered_device": frozenset(
        {"discovered_latter_devices", "ignored_latter_devices"}
    ),
    "add_latter_device": frozenset(
        {
            "discovered_latter_devices",
            "ignored_latter_devices",
            "system_controls",
            "wallpapers",
        }
    ),
    "add_ble_device": frozenset({"discovered_ble_devices"}),
    "remove_device": frozenset(
        {
            "discovered_latter_devices",
            "discovered_ble_devices",
            "system_controls",
        }
    ),
    "create_photo_collection": frozenset({"photo_collections", "system_controls"}),
    "rename_photo_collection": frozenset({"photo_collections", "system_controls"}),
    "delete_photo_collection": frozenset(
        {"photo_collections", "system_wallpapers", "wallpapers", "system_controls"}
    ),
    "update_photo_metadata": frozenset(
        {"photo_collections", "system_wallpapers", "wallpapers", "system_controls"}
    ),
    "bulk_update_photos": frozenset(
        {"photo_collections", "system_wallpapers", "wallpapers", "system_controls"}
    ),
    "delete_photo": frozenset(
        {"photo_collections", "system_wallpapers", "wallpapers", "system_controls"}
    ),
    "import_media_photos": frozenset(
        {"photo_collections", "system_wallpapers", "wallpapers", "system_controls"}
    ),
    "rotate_signing_key": frozenset({"system_wallpapers", "wallpapers"}),
}

_WALLPAPER_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "device_group",
        "wallpaper_mode",
        "wallpaper_source",
        "wallpaper_collection",
        "wallpaper_favorites",
    }
)

_RESTORE_OR_RESET_SKIP_SECTIONS: Final[frozenset[str]] = frozenset(
    {
        "locale_strings",
        "pref_specs",
        "world_clock_zones",
        "discovered_ble_devices",
        "discovered_latter_devices",
        "ignored_latter_devices",
    }
)


@dataclass(slots=True)
class _SharedSystemMemo:
    """Per-`hass` short-lived memo sharing System/Catalog builds across concurrent Studio tabs."""

    generation: int = 0
    registry_rev: int = 0
    ble_dirty_rev: int = 0
    last_registry_event: Any = None
    system_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = field(
        default_factory=dict
    )
    presence_cache: dict[tuple[Any, ...], tuple[float, list[dict[str, Any]]]] = field(
        default_factory=dict
    )
    catalog_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = field(
        default_factory=dict
    )

    def invalidate_if_populated(self) -> None:
        if self.system_cache or self.presence_cache or self.catalog_cache:
            self.invalidate()

    def invalidate(self) -> None:
        self.generation += 1
        self.system_cache.clear()
        self.presence_cache.clear()
        self.catalog_cache.clear()

    def record_registry_event(self, event: Any) -> None:
        if event is not self.last_registry_event:
            self.last_registry_event = event
            self.registry_rev += 1
            self.ble_dirty_rev += 1
            self.invalidate()


_SHARED_SYSTEM_MEMOS: WeakKeyDictionary[HomeAssistant, _SharedSystemMemo] = (
    WeakKeyDictionary()
)


def _get_shared_memo(hass: HomeAssistant) -> _SharedSystemMemo:
    memo = _SHARED_SYSTEM_MEMOS.get(hass)
    if memo is None:
        memo = _SharedSystemMemo()
        _SHARED_SYSTEM_MEMOS[hass] = memo
    return memo


def _command_response_skip_sections(
    cmd: str, body: Mapping[str, Any]
) -> frozenset[str]:
    """Return heavy unmutated sections to skip in a command response while keeping D-064 revs."""
    keep = _COMMAND_KEEP_SECTIONS.get(cmd, frozenset())
    if cmd == "save_device_config":
        raw_cfg = body.get("config")
        if isinstance(raw_cfg, Mapping) and (raw_cfg.keys() & _WALLPAPER_CONFIG_KEYS):
            keep = keep | {"wallpapers"}
    return _COMMAND_BASE_SKIP_SECTIONS - keep


def _check_studio_rev(
    connection: ActiveConnection, msg: dict[str, Any]
) -> bool:
    """Validate mandatory `studio_rev`; send `studio_rev_mismatch` and return False on mismatch."""
    rev = msg.get("studio_rev")
    if rev != STUDIO_REV:
        connection.send_error(
            msg["id"],
            "studio_rev_mismatch",
            f"Studio client revision ({rev}) does not match backend revision ({STUDIO_REV}); reload Latter Studio.",
        )
        return False
    return True


async def _async_dispatch_scoped_command(
    hass: HomeAssistant,
    scope: Scope,
    coordinator: LatterCoordinator | None,
    cmd: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Validate payload schema and dispatch `cmd` to `system_commands` or `device_commands`."""
    handlers: dict[str, CommandHandler] = (
        DEVICE_COMMAND_HANDLERS if scope == "device" else SYSTEM_COMMAND_HANDLERS
    )
    schemas: dict[str, vol.Schema] = (
        DEVICE_COMMAND_SCHEMAS if scope == "device" else SYSTEM_COMMAND_SCHEMAS
    )
    handler = handlers.get(cmd)
    if handler is None:
        raise StudioCommandError("unknown_command", f"Unsupported Studio command: {cmd}")
    schema = schemas.get(cmd)
    if schema is not None:
        try:
            body = dict(schema(body))
        except vol.Invalid as err:
            raise StudioCommandError("invalid_format", str(err)) from err
    extra: dict[str, Any] = {}
    global_cfg = peek_global_config(hass)
    await handler(hass, coordinator, body, global_cfg, extra)
    return extra


async def async_execute_studio_command(
    hass: HomeAssistant,
    command: str,
    payload: Mapping[str, Any] | None = None,
    *,
    scope: Scope | None = None,
    subentry_id: str | None = None,
    coordinator: LatterCoordinator | None = None,
) -> dict[str, Any]:
    """Validate scope, target, and schema and execute a transport-agnostic Studio command."""
    cmd = str(command or "").strip()
    try:
        cmd_scope = command_scope(cmd)
    except UnknownStudioCommand:
        raise StudioCommandError(
            "unknown_command", f"Unsupported Studio command: {cmd}"
        ) from None
    if scope is not None and cmd_scope != scope:
        raise StudioCommandError(
            "wrong_scope", f"'{cmd}' is a {cmd_scope} command, not a {scope} command"
        )
    target = coordinator
    if cmd_scope == "device" and target is None:
        target = resolve_target_coordinator(hass, subentry_id)
    if cmd_scope == "device" and target is None:
        raise StudioCommandError(
            "not_found", f"No Latter Device with subentry_id '{subentry_id}'"
        )
    return await _async_dispatch_scoped_command(
        hass,
        cmd_scope,
        target if cmd_scope == "device" else None,
        cmd,
        dict(payload or {}),
    )


@require_admin
@websocket_command({
    vol.Required("type"): "latter/system/get_state",
    vol.Optional("subentry_id"): vol.Any(str, None),
    vol.Optional("include_logs", default=False): bool,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_get_state(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current Latter Studio state payload."""
    if not _check_studio_rev(connection, msg):
        return
    coord = resolve_target_coordinator(hass, msg.get("subentry_id"))
    connection.send_result(
        msg["id"],
        build_studio_state_payload(
            hass, coord, include_logs=bool(msg.get("include_logs", False))
        ),
    )


def _register_ble_survey_listener(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg_id: int,
    survey_sub_id: str,
    ble_fabric: Any,
) -> tuple[Callable[[], None], Callable[[], None]]:
    """Attach a scoped 4 Hz coalesced BLE survey listener and return `(unsub, cancel_timer)`."""
    survey_timer_cancel: list[Any] = [None]
    pending_tracker: list[Any] = [None]

    @callback
    def _flush_pending_survey(_now: Any = None) -> None:
        survey_timer_cancel[0] = None
        tracker = pending_tracker[0]
        pending_tracker[0] = None
        if tracker is None or hass.is_stopping:
            return
        delta = build_survey_delta_payload(tracker)
        connection.send_message(event_message(msg_id, delta))

    @callback
    def _on_survey_delta(tracker: Any) -> None:
        if hass.is_stopping:
            return
        pending_tracker[0] = tracker
        if survey_timer_cancel[0] is None:
            survey_timer_cancel[0] = async_call_later(
                hass, _SURVEY_COALESCE_INTERVAL_S, _flush_pending_survey
            )

    @callback
    def _cancel_timer() -> None:
        if callable(survey_timer_cancel[0]):
            survey_timer_cancel[0]()
            survey_timer_cancel[0] = None
        pending_tracker[0] = None

    return (
        ble_fabric.register_survey_listener(
            _on_survey_delta, subentry_id=survey_sub_id
        ),
        _cancel_timer,
    )


def _memo_get[T](
    cache: Mapping[tuple[Any, ...], tuple[float, T]],
    key: tuple[Any, ...],
    now: float,
) -> T | None:
    """Return a cached value when still within `_SHARED_SNAPSHOT_TTL_S`."""
    hit = cache.get(key)
    if hit is not None and (now - hit[0]) <= _SHARED_SNAPSHOT_TTL_S:
        return hit[1]
    return None


def _memo_put[T](
    cache: dict[tuple[Any, ...], tuple[float, T]],
    key: tuple[Any, ...],
    now: float,
    value: T,
) -> T:
    """Store `value` in a bounded short-lived memo cache."""
    if len(cache) >= _MAX_MEMO_ENTRIES:
        cache.clear()
    cache[key] = (now, value)
    return value


def _capture_token_snapshot(
    hass: HomeAssistant,
    all_coords: list[LatterCoordinator],
    target: LatterCoordinator | None,
    *,
    memo: _SharedSystemMemo,
) -> tuple[SubscriptionTokenSnapshot, dict[str, bool], dict[str, Any]]:
    """Capture O(1) section invalidation tokens and reusable per-device lookups."""
    cur_sys = get_latter_system(hass)
    controls_sig, online_by_sub, lookups = compute_controls_signature(hass, all_coords)
    snap = SubscriptionTokenSnapshot(
        wallpaper_token=wallpaper_snapshot_token(),
        hmac_secret=cur_sys.hmac_secret if cur_sys is not None else b"",
        utc_day=int(time.time() // _SECONDS_PER_DAY),
        system_config_rev=get_system_config_rev(hass),
        subentry_id=target.subentry_id if target is not None else "",
        device_config_rev=target.device_config_rev if target is not None else 0,
        active_wallpaper_id=target.current_wallpaper if target is not None else "",
        display_shape=target.display_shape if target is not None else "",
        language=studio_language(hass),
        locales_loaded=studio_locales_loaded(),
        registry_rev=memo.registry_rev,
        ble_dirty_rev=memo.ble_dirty_rev,
        coordinator_ids=tuple(c.subentry_id for c in all_coords),
        controls_signature=controls_sig,
    )
    return snap, online_by_sub, lookups


def _build_shared_subscribe_payload(
    hass: HomeAssistant,
    target: LatterCoordinator | None,
    *,
    all_coords: list[LatterCoordinator],
    snap: SubscriptionTokenSnapshot,
    memo: _SharedSystemMemo,
    include_catalog: bool,
    include_logs: bool,
    skip_sections: Collection[str],
    online_by_sub: Mapping[str, bool],
    lookups_by_sub: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a subscription state payload sharing System/Catalog sections across concurrent tabs."""
    now = time.monotonic()
    sys_skip = frozenset(
        s
        for s in skip_sections
        if s not in ("wallpapers", "pref_specs", "world_clock_zones")
    )
    sys_key = (
        memo.generation,
        snap.system_config_rev,
        snap.wallpaper_token,
        snap.hmac_secret,
        snap.utc_day,
        snap.ble_dirty_rev,
        snap.registry_rev,
        snap.coordinator_ids,
        snap.controls_signature,
        snap.language,
        snap.locales_loaded,
        include_logs,
        sys_skip,
    )
    sys_section = _memo_get(memo.system_cache, sys_key, now)
    if sys_section is None:
        sys_section = _memo_put(
            memo.system_cache,
            sys_key,
            now,
            build_system_section(
                hass,
                target.subentry_id if target is not None else "",
                all_coords=all_coords,
                include_logs=include_logs,
                skip_sections=skip_sections,
                online_by_sub=online_by_sub,
                lookups_by_sub=lookups_by_sub,
            ),
        )

    pres_key = (
        memo.generation,
        snap.system_config_rev,
        snap.ble_dirty_rev,
        snap.registry_rev,
        snap.coordinator_ids,
    )
    presence_grid = _memo_get(memo.presence_cache, pres_key, now)
    if presence_grid is None:
        presence_grid = _memo_put(
            memo.presence_cache,
            pres_key,
            now,
            get_all_areas_presence_summary(hass),
        )

    catalog_override: dict[str, Any] | None = None
    if include_catalog:
        local_spk = target.local_speaker if target is not None else ""
        local_ma = target.local_ma_speaker if target is not None else ""
        cat_key = (
            memo.generation,
            snap.registry_rev,
            snap.system_config_rev,
            local_spk,
            local_ma,
        )
        catalog_override = _memo_get(memo.catalog_cache, cat_key, now)
        if catalog_override is None:
            catalog_override = _memo_put(
                memo.catalog_cache,
                cat_key,
                now,
                build_entity_catalog(hass, target, all_coords=all_coords),
            )

    return build_studio_state_payload(
        hass,
        target,
        include_catalog=include_catalog,
        include_logs=include_logs,
        skip_sections=skip_sections,
        online_by_sub=online_by_sub,
        lookups_by_sub=lookups_by_sub,
        system_section_override=sys_section,
        presence_grid_override=presence_grid,
        catalog_override=catalog_override,
    )


def _sync_subscribed_coordinators(
    hass: HomeAssistant,
    coord_unsubs: dict[int, Any],
    schedule_push: Callable[[], None],
) -> bool:
    """Reconcile coordinator listeners in `coord_unsubs`, returning True when roster changed."""
    current = list(iter_coordinators(hass))
    current_ids = {id(c) for c in current}
    changed = False
    for cid in list(coord_unsubs):
        if cid not in current_ids:
            changed = True
            u = coord_unsubs.pop(cid)
            if callable(u):
                u()
    for c in current:
        cid = id(c)
        if cid not in coord_unsubs:
            changed = True
            coord_unsubs[cid] = c.async_add_listener(schedule_push)
    return changed


def _rebind_subscribed_entity_states(
    hass: HomeAssistant,
    sub_id: str | None,
    state_unsub: list[Any],
    schedule_push: Callable[[], None],
) -> None:
    """Rebind `async_track_state_change_event` across watched Device entities."""
    if callable(state_unsub[0]):
        state_unsub[0]()
        state_unsub[0] = None
    target = resolve_target_coordinator(hass, sub_id) if sub_id else None
    entity_ids = sorted({
        e.entity_id
        for c in iter_coordinators(hass)
        for e in device_entities(hass, c.esphome_device_id)
        if not e.entity_id.endswith(_EXCLUDED_STATUS_WATCH_SUFFIXES)
        and (
            (target is not None and c is target)
            or e.domain in STUDIO_BULK_CONTROL_DOMAINS
            or e.domain == "update"
            or e.entity_id.endswith(_STUDIO_STATUS_WATCH_SUFFIXES)
        )
    })

    @callback
    def _entity_changed(_ev: Any) -> None:
        schedule_push()

    if entity_ids:
        state_unsub[0] = async_track_state_change_event(
            hass, entity_ids, _entity_changed
        )


def _cleanup_subscription_handles(
    debounce_cancel: list[Any],
    state_unsub: list[Any],
    coord_unsubs: dict[int, Any],
    unsubs: list[Any],
) -> None:
    """Cancel all timers and listeners attached to a Studio WebSocket subscription."""
    for slot in (debounce_cancel, state_unsub):
        if callable(slot[0]):
            slot[0]()
            slot[0] = None
    for u in coord_unsubs.values():
        if callable(u):
            u()
    coord_unsubs.clear()
    for u in unsubs:
        if callable(u):
            u()
    unsubs.clear()


@callback
def _bind_subscription_cleanup(
    hass: HomeAssistant,
    debounce_cancel: list[Any],
    state_unsub: list[Any],
    coord_unsubs: dict[int, Any],
    unsubs: list[Any],
) -> Callable[[], None]:
    """Build an idempotent subscription cleanup callback that also fires on HA stop."""
    stop_unsub: list[Any] = [None]

    @callback
    def _cleanup_all() -> None:
        if callable(stop_unsub[0]):
            unsub_fn = stop_unsub[0]
            stop_unsub[0] = None
            if not hass.is_stopping:
                unsub_fn()
        _cleanup_subscription_handles(
            debounce_cancel, state_unsub, coord_unsubs, unsubs
        )

    @callback
    def _on_ha_stop(_ev: Any) -> None:
        stop_unsub[0] = None
        _cleanup_subscription_handles(
            debounce_cancel, state_unsub, coord_unsubs, unsubs
        )

    stop_unsub[0] = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_ha_stop)
    return _cleanup_all


def _attach_subscription_listeners(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg_id: int,
    survey_sub_id: str,
    schedule_push: Callable[[], None],
    registry_changed: Callable[[Any], None],
    unsubs: list[Any],
) -> None:
    """Attach occupancy, Studio subscriber, optional 4 Hz BLE survey, and registry listeners."""
    ble_fabric = get_ble_fabric(hass)
    unsubs.append(ble_fabric.register_occupancy_listener(schedule_push))
    unsubs.append(register_studio_subscriber(hass, schedule_push))
    if survey_sub_id:
        unsubs.extend(
            _register_ble_survey_listener(
                hass, connection, msg_id, survey_sub_id, ble_fabric
            )
        )
    unsubs.extend(
        (
            hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, registry_changed),
            hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, registry_changed),
            hass.bus.async_listen(ar.EVENT_AREA_REGISTRY_UPDATED, registry_changed),
        )
    )


@require_admin
@websocket_command({
    vol.Required("type"): "latter/system/subscribe",
    vol.Optional("subentry_id"): vol.Any(str, None),
    vol.Optional("survey_subentry_id"): vol.Any(str, None),
    vol.Optional("include_logs", default=False): bool,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_subscribe(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to live Latter Studio state and scoped 4 Hz BLE survey updates."""
    if not _check_studio_rev(connection, msg):
        return
    sub_id = msg.get("subentry_id")
    survey_sub_id = str(msg.get("survey_subentry_id") or "").strip()
    include_logs = bool(msg.get("include_logs", False))
    unsubs: list[Any] = []
    debounce_cancel: list[Any] = [None]
    state_unsub: list[Any] = [None]
    coord_unsubs: dict[int, Any] = {}
    memo = _get_shared_memo(hass)
    catalog_gate = CatalogGate()
    token_gate = SectionTokenGate()
    section_gate = SectionHashGate()

    init_coords = list(iter_coordinators(hass))
    init_target = resolve_target_coordinator(hass, sub_id)
    init_snap, init_online, init_lookups = _capture_token_snapshot(
        hass, init_coords, init_target, memo=memo
    )
    initial_payload = build_studio_state_payload(
        hass,
        init_target,
        include_catalog=True,
        include_logs=include_logs,
        online_by_sub=init_online,
        lookups_by_sub=init_lookups,
    )
    token_gate.record_initial(init_snap, initial_payload)
    section_gate.record_initial(initial_payload, keys=HASH_GATED_SECTIONS)

    @callback
    def _push_now(_now: Any = None) -> None:
        debounce_cancel[0] = None
        all_coords = list(iter_coordinators(hass))
        target = resolve_target_coordinator(hass, sub_id)
        snap, online_by_sub, lookups_by_sub = _capture_token_snapshot(
            hass, all_coords, target, memo=memo
        )
        skip = token_gate.compute_skip_sections(snap)
        payload = _build_shared_subscribe_payload(
            hass,
            target,
            all_coords=all_coords,
            snap=snap,
            memo=memo,
            include_catalog=catalog_gate.take(),
            include_logs=include_logs,
            skip_sections=skip,
            online_by_sub=online_by_sub,
            lookups_by_sub=lookups_by_sub,
        )
        section_gate.filter_sections(payload, keys=HASH_GATED_SECTIONS)
        token_gate.commit(snap, skip, payload_keys=payload.keys())
        connection.send_message(event_message(msg["id"], payload))

    @callback
    def _schedule_push() -> None:
        if hass.is_stopping:
            return
        memo.invalidate_if_populated()
        if debounce_cancel[0] is None:
            debounce_cancel[0] = async_call_later(hass, _PUSH_DEBOUNCE_S, _push_now)

    @callback
    def _track_coordinators() -> None:
        _sync_subscribed_coordinators(hass, coord_unsubs, _schedule_push)

    @callback
    def _track_device_states() -> None:
        _rebind_subscribed_entity_states(hass, sub_id, state_unsub, _schedule_push)

    @callback
    def _registry_changed(event: Any) -> None:
        if _is_irrelevant_registry_update(
            str(getattr(event, "event_type", "") or ""),
            getattr(event, "data", None),
        ):
            return
        memo.record_registry_event(event)
        catalog_gate.mark_dirty()
        _track_coordinators()
        _track_device_states()
        _schedule_push()

    _track_coordinators()
    _track_device_states()
    _attach_subscription_listeners(
        hass, connection, msg["id"], survey_sub_id, _schedule_push, _registry_changed, unsubs
    )

    connection.subscriptions[msg["id"]] = _bind_subscription_cleanup(
        hass, debounce_cancel, state_unsub, coord_unsubs, unsubs
    )
    connection.send_result(msg["id"], {"subscribed": True})
    connection.send_message(event_message(msg["id"], initial_payload))


def _resolve_post_command_target(
    hass: HomeAssistant,
    selected: LatterCoordinator | None,
    extra: Mapping[str, Any],
) -> LatterCoordinator | None:
    """Resolve the post-command selected coordinator after device removal or adoption."""
    if selected is not None and extra.get("removed_subentry_id") == selected.subentry_id:
        return None
    if selected is None and extra.get("adopted_subentry_id"):
        return resolve_target_coordinator(hass, str(extra["adopted_subentry_id"]))
    return selected


async def _async_handle_ws_command_impl(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    scope: Scope,
) -> None:
    """Run a Studio command on its own websocket type and answer with the Studio state."""
    if not _check_studio_rev(connection, msg):
        return
    cmd = str(msg["command"]).strip()
    body = dict(msg.get("payload") or {})
    selected = resolve_target_coordinator(hass, msg.get("subentry_id"))
    try:
        extra = await async_execute_studio_command(
            hass,
            cmd,
            body,
            scope=scope,
            subentry_id=msg.get("subentry_id"),
            coordinator=selected,
        )
    except StudioCommandError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    except TargetNotAllowed as err:
        connection.send_error(msg["id"], "not_allowed", str(err))
        return
    except SettingsScopeError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except Exception as err:
        _LOGGER.exception("Latter Studio command '%s' failed: %s", cmd, err)
        connection.send_error(msg["id"], "command_failed", str(err))
        return

    if cmd in ("mint_camera_preview_url", "browse_media_folder"):
        connection.send_result(msg["id"], extra)
        return

    _get_shared_memo(hass).invalidate()
    post_selected = _resolve_post_command_target(hass, selected, extra)
    skip_sections = _command_response_skip_sections(cmd, body)
    if post_selected is not selected:
        skip_sections = skip_sections - {"wallpapers"}
    connection.send_result(
        msg["id"],
        {
            **build_studio_state_payload(
                hass,
                post_selected,
                include_catalog=False,
                include_logs=(cmd == "clear_internal_logs"),
                skip_sections=skip_sections,
            ),
            **extra,
        },
    )


@require_admin
@websocket_command({
    vol.Required("type"): "latter/system/command",
    vol.Required("command"): str,
    vol.Optional("subentry_id"): vol.Any(str, None),
    vol.Optional("payload", default={}): dict,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_system_command(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Execute an admin-gated System command from Latter Studio."""
    await _async_handle_ws_command_impl(hass, connection, msg, "system")


@require_admin
@websocket_command({
    vol.Required("type"): "latter/device/command",
    vol.Required("command"): str,
    vol.Required("subentry_id"): str,
    vol.Optional("payload", default={}): dict,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_device_command(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Execute an admin-gated Device command from Latter Studio."""
    await _async_handle_ws_command_impl(hass, connection, msg, "device")


@require_admin
@websocket_command({
    vol.Required("type"): "latter/system/export",
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_system_export(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export the System's non-secret settings and every Device's settings as JSON."""
    if not _check_studio_rev(connection, msg):
        return
    bundle = build_backup_bundle(
        hass=hass, scope="system", coordinators=iter_coordinators(hass)
    )
    connection.send_result(msg["id"], {"bundle": bundle})


@require_admin
@websocket_command({
    vol.Required("type"): "latter/device/export",
    vol.Required("subentry_id"): str,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_device_export(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export one Device's non-secret settings as JSON."""
    if not _check_studio_rev(connection, msg):
        return
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No Latter Device with subentry_id '{msg['subentry_id']}'",
        )
        return
    bundle = build_backup_bundle(
        hass=hass,
        scope="device",
        coordinators=iter_coordinators(hass),
        target_coordinator=coord,
    )
    connection.send_result(msg["id"], {"bundle": bundle})


async def _async_restore_bundle(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    target: LatterCoordinator | None,
) -> None:
    """Restore a backup bundle and answer with the Studio state."""
    try:
        await async_restore_backup_bundle(
            hass,
            bundle=msg["bundle"],
            coordinators=iter_coordinators(hass),
            target_coordinator=target,
        )
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    _get_shared_memo(hass).invalidate()
    connection.send_result(
        msg["id"],
        build_studio_state_payload(
            hass,
            resolve_target_coordinator(hass, msg.get("subentry_id")),
            include_catalog=False,
            skip_sections=_RESTORE_OR_RESET_SKIP_SECTIONS,
        ),
    )


@require_admin
@websocket_command({
    vol.Required("type"): "latter/system/import",
    vol.Optional("subentry_id"): vol.Any(str, None),
    vol.Required("bundle"): dict,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_system_import(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Restore a System backup (System settings and every Device it names)."""
    if not _check_studio_rev(connection, msg):
        return
    if str(msg["bundle"].get("scope") or "") != "system":
        connection.send_error(
            msg["id"],
            "invalid_format",
            "This is a Device backup: choose the Device to restore it onto",
        )
        return
    await _async_restore_bundle(hass, connection, msg, None)


@require_admin
@websocket_command({
    vol.Required("type"): "latter/device/import",
    vol.Required("subentry_id"): str,
    vol.Required("bundle"): dict,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_device_import(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Restore a Device backup onto the Device named by `subentry_id`."""
    if not _check_studio_rev(connection, msg):
        return
    if str(msg["bundle"].get("scope") or "") != "device":
        connection.send_error(
            msg["id"],
            "invalid_format",
            "This is a System backup: restore it without choosing a Device",
        )
        return
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No Latter Device with subentry_id '{msg['subentry_id']}'",
        )
        return
    await _async_restore_bundle(hass, connection, msg, coord)


@require_admin
@websocket_command({
    vol.Required("type"): "latter/device/reset",
    vol.Required("subentry_id"): str,
    vol.Optional("device_settings", default=True): bool,
    vol.Optional("latter_options", default=True): bool,
    vol.Required("studio_rev"): int,
})
@async_response
async def ws_handle_device_reset(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Reset a Device to defaults through the same path as `latter.reset_device`."""
    if not _check_studio_rev(connection, msg):
        return
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No Latter device with subentry_id '{msg['subentry_id']}'",
        )
        return
    try:
        await async_reset_device(
            hass,
            coord,
            device_settings=msg["device_settings"],
            latter_options=msg["latter_options"],
        )
    except ServiceValidationError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "command_failed", str(err))
        return
    parts = [
        p
        for p, on in (
            ("device settings", msg["device_settings"]),
            ("Latter options", msg["latter_options"]),
        )
        if on
    ]
    log_studio_event(
        hass, "INFO", coord.device_slug, f"Reset to defaults ({', '.join(parts)})"
    )
    _get_shared_memo(hass).invalidate()
    connection.send_result(
        msg["id"],
        build_studio_state_payload(
            hass,
            coord,
            include_catalog=False,
            skip_sections=_RESTORE_OR_RESET_SKIP_SECTIONS,
        ),
    )


@callback
def async_register_studio_ws_commands(hass: HomeAssistant) -> None:
    """Register all Latter Studio WebSocket API commands."""
    domain_data = get_domain_data(hass)
    if domain_data.studio_ws_registered_version == INTEGRATION_VERSION:
        return
    domain_data.studio_ws_registered_version = INTEGRATION_VERSION
    for handler in (
        ws_handle_get_state,
        ws_handle_subscribe,
        ws_handle_system_command,
        ws_handle_device_command,
        ws_handle_system_export,
        ws_handle_device_export,
        ws_handle_system_import,
        ws_handle_device_import,
        ws_handle_device_reset,
    ):
        async_register_command(hass, handler)


__all__ = [
    "STUDIO_REV",
    "StudioCommandError",
    "_async_dispatch_scoped_command",
    "async_execute_studio_command",
    "async_register_studio_ws_commands",
    "ws_handle_device_command",
    "ws_handle_device_export",
    "ws_handle_device_import",
    "ws_handle_device_reset",
    "ws_handle_get_state",
    "ws_handle_subscribe",
    "ws_handle_system_command",
    "ws_handle_system_export",
    "ws_handle_system_import",
]
