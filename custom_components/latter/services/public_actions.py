"""Registration and flattened handlers for the 6 public Latter user actions."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import JsonObjectType
import probatio as vol

from ..const import (
    DOMAIN,
    PUBLIC_SERVICES,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_NAVIGATE,
    SERVICE_NOTIFY,
    SERVICE_RESET_DEVICE,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    TargetKind,
    target_kind,
)
from ..coordinator import LatterCoordinator
from ..groups.device_groups import async_reset_device
from ..hub_registry import iter_coordinators
from ..identity import esphome_service
from ..media.tts_queue import async_announce_on_targets, resolve_assist_satellite_entity
from ..protocol_codec import utf8_safe_truncate
from ..protocol_specs import normalize_navigate_route
from .rpc_slots import (
    BASE_TARGET_FIELDS,
    async_execute_intercom_broadcast,
    parse_bool,
    parse_int,
    require_admin_if_user_call,
    resolve_coordinator_from_call,
    resolve_occupied_area_ids,
)

_LOGGER = logging.getLogger(__name__)

_MIN_NOTIFY_DURATION_S = 2
_MAX_NOTIFY_DURATION_S = 60
_DEFAULT_NOTIFY_DURATION_S = 8
_MAX_TITLE_UTF8_BYTES = 48
_MAX_MESSAGE_UTF8_BYTES = 160


@dataclass(slots=True)
class _NotifyEnvelope:
    """Normalized notification fields shared across targeted display coordinators."""

    title: str
    message: str
    priority: str
    duration: int
    card_chime: bool
    is_announce: bool
    cam_ent: str | None


def _resolve_display_targets(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[list[LatterCoordinator], TargetKind]:
    """Resolve display `LatterCoordinator` targets and target kind for display actions."""
    raw_target = str(call.data.get("target_device") or "").strip()
    target_low = raw_target.lower()
    kind = target_kind(raw_target)

    all_coords = [
        c for c in iter_coordinators(hass) if not c.is_ble_tag and c.has_display
    ]
    if kind == "all":
        return list(all_coords), kind
    if kind in ("occupied_areas", "person"):
        occupied_areas = resolve_occupied_area_ids(hass, kind, target_low)
        return [
            c
            for c in all_coords
            if (
                kind == "person"
                and c.assigned_person.lower() == target_low
                and not c.is_device_away()
            )
            or (c.active_area_id and c.active_area_id in occupied_areas)
        ], kind
    return [resolve_coordinator_from_call(hass, call)], kind


async def _async_deliver_notify_to_coord(
    hass: HomeAssistant, coord: LatterCoordinator, env: _NotifyEnvelope
) -> None:
    """Deliver a single toast notification and optional TTS announcement to `coord`."""
    in_bedtime = bool(
        not coord.is_ble_tag
        and coord.has_display
        and coord.get_device_pref("bedtime_active")
    )
    in_dnd = bool(not coord.is_ble_tag and coord.has_display and coord.do_not_disturb)
    if in_dnd and env.priority in ("normal", "warning"):
        return

    suppress_quiet = (in_bedtime and env.priority != "critical") or (
        in_dnd and bool(env.cam_ent)
    )
    coord_chime = False if suppress_quiet else env.card_chime
    coord.async_dispatch_notification(
        title=env.title,
        message=env.message,
        priority=env.priority,
        duration=env.duration,
        chime=coord_chime,
        camera_entity=env.cam_ent,
    )

    esp_notify_svc = esphome_service(
        hass, coord.esphome_device_id, "latter_show_notification"
    )
    if esp_notify_svc:
        try:
            await hass.services.async_call(
                "esphome",
                esp_notify_svc,
                {
                    "title": utf8_safe_truncate(env.title, _MAX_TITLE_UTF8_BYTES),
                    "message": utf8_safe_truncate(env.message, _MAX_MESSAGE_UTF8_BYTES),
                    "priority": env.priority,
                    "duration": env.duration,
                    "chime": coord_chime,
                    "camera_url": coord.alert_camera_url,
                    "camera_entity": coord.alert_camera_entity,
                    "alert_id": coord.alert_id,
                },
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Direct esphome.%s call skipped: %s", esp_notify_svc, err)

    if env.is_announce and env.message and not suppress_quiet and not in_dnd:
        sat_ent = resolve_assist_satellite_entity(hass, coord.local_speaker, coord)
        target_list = (
            [sat_ent]
            if sat_ent
            else ([coord.local_speaker] if coord.local_speaker else [])
        )
        if target_list:
            await async_announce_on_targets(
                hass,
                speakers=target_list,
                message=env.message,
                blocking=False,
            )


async def _async_handle_notify(call: ServiceCall) -> None:
    """Dispatch a toast notification, chime, and optional camera snapshot to displays."""
    hass = call.hass
    target_coords, _kind = _resolve_display_targets(hass, call)
    if not target_coords:
        return

    data = call.data
    chime = parse_bool(data.get("chime"), default=True)
    is_announce = parse_bool(data.get("announce"), default=False)
    env = _NotifyEnvelope(
        title=str(data.get("title") or "Notification").strip() or "Notification",
        message=str(data.get("message") or "").strip(),
        priority=str(data.get("priority") or "normal").strip().lower(),
        duration=max(
            _MIN_NOTIFY_DURATION_S,
            min(
                _MAX_NOTIFY_DURATION_S,
                parse_int(data.get("duration"), _DEFAULT_NOTIFY_DURATION_S),
            ),
        ),
        card_chime=False if is_announce else chime,
        is_announce=is_announce,
        cam_ent=str(data.get("camera_entity") or "").strip() or None,
    )
    for coord in target_coords:
        await _async_deliver_notify_to_coord(hass, coord, env)


async def _async_handle_intercom_broadcast(call: ServiceCall) -> ServiceResponse:
    """Execute `latter.intercom_broadcast`."""
    res = await async_execute_intercom_broadcast(call.hass, call.data)
    out: JsonObjectType = {
        "delivered": res["delivered"],
        "targets": list(res["targets"]),
    }
    if isinstance(reason := res.get("reason"), str):
        out["reason"] = reason
    return out


async def _async_handle_set_active_area(call: ServiceCall) -> None:
    """Execute `latter.set_active_area`."""
    coord = resolve_coordinator_from_call(call.hass, call)
    area_val = str(call.data.get("area_id") or "").strip()
    if area_val:
        coord.async_set_active_area(area_val, sync_device_registry=True)


async def _async_handle_set_active_speaker(call: ServiceCall) -> None:
    """Execute `latter.set_active_speaker`."""
    speaker = str(call.data.get("entity_id") or "").strip()
    transfer_queue = parse_bool(call.data.get("transfer_queue"), default=True)
    coord = resolve_coordinator_from_call(call.hass, call)
    if speaker:
        coord.async_set_active_speaker(speaker, transfer_queue=transfer_queue)


async def _async_handle_reset_device(call: ServiceCall) -> None:
    """Reset a Latter Device: the settings saved on the device and/or its Latter options."""
    hass = call.hass
    await require_admin_if_user_call(hass, call)
    coord = resolve_coordinator_from_call(hass, call)
    await async_reset_device(
        hass,
        coord,
        device_settings=bool(call.data["device_settings"]),
        latter_options=bool(call.data["latter_options"]),
    )


async def _async_handle_navigate(call: ServiceCall) -> None:
    """Navigate one or more Latter displays to a canonical UI page or subpage."""
    raw_route = call.data.get("route")
    try:
        route = normalize_navigate_route(raw_route)
    except ValueError as err:
        bad_route = str(raw_route or "").strip() or "(empty)"
        raise ServiceValidationError(
            str(err),
            translation_domain=DOMAIN,
            translation_key="invalid_navigate_route",
            translation_placeholders={"route": bad_route},
        ) from err

    hass = call.hass
    target_coords, kind = _resolve_display_targets(hass, call)
    if not target_coords:
        return

    wake = parse_bool(call.data.get("wake"), default=True)
    is_multi_target = kind in ("all", "occupied_areas", "person")
    for coord in target_coords:
        if not is_multi_target and not coord.is_ble_tag and not coord.has_display:
            raise ServiceValidationError(
                f"Target Latter device {coord.device_slug} does not have a display.",
                translation_domain=DOMAIN,
                translation_key="not_supported",
            )
        in_bedtime = bool(
            not coord.is_ble_tag
            and coord.has_display
            and coord.get_device_pref("bedtime_active")
        )
        cmd = f"nav_silent:{route}" if (not wake or in_bedtime) else f"nav:{route}"
        await coord.async_send_device_command(cmd, raise_if_offline=not is_multi_target)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register ONLY the 6 public Latter user actions on `hass.services`."""
    if hass.services.has_service(DOMAIN, SERVICE_NOTIFY):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_NOTIFY,
        _async_handle_notify,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("title", default="Notification"): cv.string,
                vol.Required("message"): cv.string,
                vol.Optional("priority", default="normal"): cv.string,
                vol.Optional("duration", default=8): vol.Coerce(int),
                vol.Optional("chime", default=True): vol.Any(bool, cv.string),
                vol.Optional("announce", default=False): vol.Any(bool, cv.string),
                vol.Optional("camera_entity"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        _async_handle_intercom_broadcast,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("message"): cv.string,
                vol.Optional("media_url"): cv.string,
                vol.Optional("target_speakers"): vol.All(
                    cv.entity_ids, [cv.entity_domain("media_player")]
                ),
                vol.Optional("tts_entity"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_AREA,
        _async_handle_set_active_area,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("area_id"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_SPEAKER,
        _async_handle_set_active_speaker,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("entity_id"): cv.string,
                vol.Optional("transfer_queue", default=True): vol.Any(bool, cv.string),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_DEVICE,
        _async_handle_reset_device,
        schema=vol.Schema(
            {
                vol.Required("target_device"): vol.All(
                    cv.string, vol.Strip, vol.Length(min=1)
                ),
                vol.Optional("device_settings", default=True): cv.boolean,
                vol.Optional("latter_options", default=True): cv.boolean,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NAVIGATE,
        _async_handle_navigate,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("route"): cv.string,
                vol.Optional("wake", default=True): vol.Any(bool, cv.string),
            }
        ),
    )


@callback
def _remove_service_if_present(hass: HomeAssistant, service: str) -> None:
    """Remove a single public action from `hass.services` when registered."""
    if not hass.services.has_service(DOMAIN, service):
        return
    remove_fn = getattr(hass.services, "async_remove", None)
    if callable(remove_fn):
        remove_fn(DOMAIN, service)
        return
    raw_services = getattr(hass.services, "_services", None)
    if isinstance(raw_services, dict):
        dom_map = raw_services.get(DOMAIN)
        if isinstance(dom_map, dict):
            dom_map.pop(service, None)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister all 6 public Latter user actions from `hass.services`."""
    for svc in PUBLIC_SERVICES:
        _remove_service_if_present(hass, svc)
