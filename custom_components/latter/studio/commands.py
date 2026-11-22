"""Admin-gated WebSocket API endpoints and scope-based command dispatch router for Latter Studio (`L3`).

The websocket type is the scope (`studio/state_gates.py`): `latter/system/*` commands never act on the
Studio's selected Device (a System command that acts on one Device names it in its own payload), and
`latter/device/*` commands act on the Device named by the message's required `subentry_id`.
"""

from __future__ import annotations

from collections.abc import Callable
import copy
import logging
import time
from typing import Any, Final

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
    CONF_BLE_AREA_SIGNATURES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    INTEGRATION_VERSION,
    STUDIO_REV,
)
from ..coordinator import LatterCoordinator
from ..groups.device_reset import async_reset_device
from ..hub_registry import get_latter_system, iter_coordinators
from ..identity import device_entities
from ..presence.ble_fabric import get_all_areas_presence_summary, get_ble_fabric
from ..presence.ble_registry import get_area_signatures_summary
from ..wallpapers.store import wallpaper_snapshot_token
from .device_commands import (
    DEVICE_COMMAND_HANDLERS,
    DEVICE_COMMAND_SCHEMAS,
    CommandHandler,
)
from .payload import (
    STUDIO_BULK_CONTROL_DOMAINS,
    StudioCommandError,
    build_studio_state_payload,
    log_studio_event,
    resolve_target_coordinator,
)
from .settings_cleaners import SettingsScopeError
from .state_gates import (
    CatalogGate,
    Scope,
    SectionHashGate,
    TargetNotAllowed,
    UnknownStudioCommand,
    command_scope,
    find_by_subentry_id,
)
from .system_commands import SYSTEM_COMMAND_HANDLERS, SYSTEM_COMMAND_SCHEMAS

_LOGGER = logging.getLogger(__name__)
_SURVEY_COALESCE_INTERVAL_S: Final = 0.25
_MIN_SURVEY_DELAY_S: Final = 0.05
_PUSH_DEBOUNCE_S: Final = 0.4

_STUDIO_STATUS_WATCH_SUFFIXES: Final[tuple[str, ...]] = (
    "_system_rpc_outbox",
    "_rpc_outbox",
    "_system_wi_fi_signal",
    "_wi_fi_signal",
    "_ip_address",
    "_battery_level",
    "_battery_charging",
    "_usb_power_connected",
    "_project_firmware",
)


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
    global_cfg: dict[str, Any] = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
    await handler(hass, coordinator, body, global_cfg, extra)
    return extra


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
    """Attach a 4 Hz coalesced BLE survey listener and return `(unsub, cancel_timer)`."""
    survey_timer_cancel: list[Any] = [None]
    last_survey_sent_mono: list[float] = [0.0]
    pending_survey_event: list[dict[str, Any] | None] = [None]

    @callback
    def _flush_pending_survey(_now: Any = None) -> None:
        survey_timer_cancel[0] = None
        ev = pending_survey_event[0]
        pending_survey_event[0] = None
        if ev is not None:
            last_survey_sent_mono[0] = time.monotonic()
            connection.send_message(event_message(msg_id, ev))

    @callback
    def _on_survey_delta(delta: dict[str, Any]) -> None:
        if hass.is_stopping:
            return
        target_coord = find_by_subentry_id(iter_coordinators(hass), survey_sub_id)
        tracker = target_coord.ble_tracker if target_coord is not None else None
        if target_coord is None or tracker is None:
            return
        tracker_slug = str(getattr(tracker, "raw_slug", target_coord.device_slug) or "")
        if str(delta.get("device_slug") or "") != tracker_slug:
            return
        raw_packets = delta.get("packets_seen")
        ev_payload = {
            "type": "ble_survey_delta",
            "subentry_id": target_coord.subentry_id,
            "ble_packets_seen": int(
                raw_packets if raw_packets is not None else tracker.packets_seen
            ),
            "ble_closest_proxy": str(
                delta.get("closest_scanner")
                if delta.get("closest_scanner") is not None
                else tracker.closest_scanner
            ),
            "ble_survey_rows": (
                delta["calibration"]
                if isinstance(delta.get("calibration"), list)
                else tracker.get_scanner_calibration_telemetry()
            ),
            "ble_area_signatures": (
                delta["area_signatures"]
                if isinstance(delta.get("area_signatures"), list)
                else get_area_signatures_summary(hass)
            ),
            "area_presence_grid": get_all_areas_presence_summary(hass),
        }
        now_m = time.monotonic()
        elapsed = now_m - last_survey_sent_mono[0]
        if elapsed >= _SURVEY_COALESCE_INTERVAL_S and survey_timer_cancel[0] is None:
            last_survey_sent_mono[0] = now_m
            connection.send_message(event_message(msg_id, ev_payload))
        else:
            pending_survey_event[0] = ev_payload
            if survey_timer_cancel[0] is None:
                delay = max(_MIN_SURVEY_DELAY_S, _SURVEY_COALESCE_INTERVAL_S - max(0.0, elapsed))
                survey_timer_cancel[0] = async_call_later(hass, delay, _flush_pending_survey)

    @callback
    def _cancel_timer() -> None:
        if callable(survey_timer_cancel[0]):
            survey_timer_cancel[0]()
            survey_timer_cancel[0] = None
        pending_survey_event[0] = None

    return ble_fabric.register_survey_listener(_on_survey_delta), _cancel_timer


def _compute_subscribe_skip_sections(
    hass: HomeAssistant,
    section_gate: SectionHashGate,
    tokens: list[Any],
    *,
    ble_is_dirty: bool,
) -> set[str]:
    """Determine unchanged system sections to omit before building a subscription push."""
    cur_sys = get_latter_system(hass)
    cur_wp_tok = wallpaper_snapshot_token()
    cur_hmac = cur_sys.hmac_secret if cur_sys is not None else b""
    cur_raw_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
    cur_sigs = cur_raw_cfg.get(CONF_BLE_AREA_SIGNATURES)

    skip: set[str] = set()
    if not ble_is_dirty and section_gate.has_sent("discovered_ble_devices"):
        skip.add("discovered_ble_devices")
    if (
        cur_wp_tok == tokens[0]
        and cur_hmac == tokens[1]
        and section_gate.has_sent("system_wallpapers")
        and section_gate.has_sent("photo_collections")
    ):
        skip.update(("system_wallpapers", "photo_collections"))
    else:
        tokens[0] = cur_wp_tok
        tokens[1] = cur_hmac
    if (
        not ble_is_dirty
        and cur_sigs == tokens[2]
        and section_gate.has_sent("ble_area_signatures")
    ):
        skip.add("ble_area_signatures")
    else:
        tokens[2] = copy.deepcopy(cur_sigs)
    return skip


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
        if (target is not None and c is target)
        or e.domain in STUDIO_BULK_CONTROL_DOMAINS
        or e.domain == "update"
        or e.entity_id.endswith(_STUDIO_STATUS_WATCH_SUFFIXES)
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
            stop_unsub[0]()
            stop_unsub[0] = None
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
    ble_dirty: list[bool] = [False]
    catalog_gate = CatalogGate()
    section_gate = SectionHashGate()

    init_sys = get_latter_system(hass)
    init_raw_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
    tokens: list[Any] = [
        wallpaper_snapshot_token(),
        init_sys.hmac_secret if init_sys is not None else b"",
        copy.deepcopy(init_raw_cfg.get(CONF_BLE_AREA_SIGNATURES)),
    ]
    initial_payload = build_studio_state_payload(
        hass,
        resolve_target_coordinator(hass, sub_id),
        include_catalog=True,
        include_logs=include_logs,
    )
    section_gate.record_initial(initial_payload)

    @callback
    def _push_now(_now: Any = None) -> None:
        debounce_cancel[0] = None
        skip = _compute_subscribe_skip_sections(
            hass, section_gate, tokens, ble_is_dirty=ble_dirty[0]
        )
        ble_dirty[0] = False
        payload = build_studio_state_payload(
            hass,
            resolve_target_coordinator(hass, sub_id),
            include_catalog=catalog_gate.take(),
            include_logs=include_logs,
            skip_sections=skip,
        )
        section_gate.filter_sections(payload)
        connection.send_message(event_message(msg["id"], payload))

    @callback
    def _schedule_push() -> None:
        if hass.is_stopping:
            return
        if debounce_cancel[0] is None:
            debounce_cancel[0] = async_call_later(hass, _PUSH_DEBOUNCE_S, _push_now)

    @callback
    def _track_coordinators() -> None:
        if _sync_subscribed_coordinators(hass, coord_unsubs, _schedule_push):
            ble_dirty[0] = True

    @callback
    def _track_device_states() -> None:
        _rebind_subscribed_entity_states(hass, sub_id, state_unsub, _schedule_push)

    @callback
    def _registry_changed(_event: Any) -> None:
        catalog_gate.mark_dirty()
        ble_dirty[0] = True
        _track_coordinators()
        _track_device_states()
        _schedule_push()

    _track_coordinators()
    ble_dirty[0] = False
    _track_device_states()

    ble_fabric = get_ble_fabric(hass)
    unsubs.append(ble_fabric.register_occupancy_listener(_schedule_push))
    if survey_sub_id:
        unsubs.extend(
            _register_ble_survey_listener(
                hass, connection, msg["id"], survey_sub_id, ble_fabric
            )
        )
    unsubs.extend(
        (
            hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _registry_changed),
            hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _registry_changed),
            hass.bus.async_listen(ar.EVENT_AREA_REGISTRY_UPDATED, _registry_changed),
        )
    )

    connection.subscriptions[msg["id"]] = _bind_subscription_cleanup(
        hass, debounce_cancel, state_unsub, coord_unsubs, unsubs
    )
    connection.send_result(msg["id"], {"subscribed": True})
    connection.send_message(event_message(msg["id"], initial_payload))


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
        try:
            cmd_scope = command_scope(cmd)
        except UnknownStudioCommand:
            raise StudioCommandError(
                "unknown_command", f"Unsupported Studio command: {cmd}"
            ) from None
        if cmd_scope != scope:
            raise StudioCommandError(
                "wrong_scope", f"'{cmd}' is a {cmd_scope} command, not a {scope} command"
            )
        if scope == "device" and selected is None:
            raise StudioCommandError(
                "not_found", f"No Latter Device with subentry_id '{msg.get('subentry_id')}'"
            )
        extra = await _async_dispatch_scoped_command(
            hass, scope, selected if scope == "device" else None, cmd, body
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

    if selected is not None and extra.get("removed_subentry_id") == selected.subentry_id:
        selected = None
    elif selected is None and extra.get("adopted_subentry_id"):
        selected = resolve_target_coordinator(hass, str(extra["adopted_subentry_id"]))
    connection.send_result(
        msg["id"],
        {
            **build_studio_state_payload(
                hass,
                selected,
                include_catalog=False,
                include_logs=(cmd == "clear_internal_logs"),
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
    connection.send_result(
        msg["id"],
        build_studio_state_payload(
            hass,
            resolve_target_coordinator(hass, msg.get("subentry_id")),
            include_catalog=False,
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
    connection.send_result(
        msg["id"], build_studio_state_payload(hass, coord, include_catalog=False)
    )


@callback
def async_register_studio_ws_commands(hass: HomeAssistant) -> None:
    """Register all Latter Studio WebSocket API commands."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_studio_ws_registered") == INTEGRATION_VERSION:
        return
    domain_data["_studio_ws_registered"] = INTEGRATION_VERSION
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
