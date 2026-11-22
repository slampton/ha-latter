"""Studio WebSocket command handlers for Photo Library, media import, announcements, and camera previews (`L3`)."""

from __future__ import annotations

from typing import Any, Final
from urllib.parse import quote

from homeassistant.core import HomeAssistant
import voluptuous as vol

from ..const import (
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DOMAIN,
)
from ..coordinator import LatterCoordinator
from ..doorbell import async_execute_doorbell_intercom
from ..hub_registry import get_latter_system, iter_coordinators
from ..presence.ble_fabric import get_ble_fabric
from ..wallpapers.media_import import (
    import_media_photos_sync,
    list_media_folder_sync,
)
from ..wallpapers.models import VIRTUAL_COLLECTION_IDS
from ..wallpapers.pools import known_collection_ids, known_wallpaper_ids
from ..wallpapers.store import (
    bulk_update_photos,
    create_collection,
    delete_collection,
    delete_photo,
    rename_collection,
    update_photo_metadata,
)
from .payload_shared import StudioCommandError
from .settings_cleaners import clean_announcement, system_settings_view
from .state_gates import find_by_subentry_id

MAX_CUSTOM_PHOTO_POOL: Final = 200
_MEDIA_THUMB_DIM: Final = 160
_CAMERA_PREVIEW_TTL_S: Final = 600


def _payload_device(
    hass: HomeAssistant, body: dict[str, Any], purpose: str
) -> LatterCoordinator:
    """Return the Device a System command names in its payload (`subentry_id`), else fail."""
    coords: list[LatterCoordinator] = list(iter_coordinators(hass))
    coord = find_by_subentry_id(coords, str(body.get("subentry_id") or ""))
    if coord is None:
        raise StudioCommandError("not_found", f"Choose {purpose}")
    return coord


async def _cmd_test_doorbell_speaker(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    speaker_coord = _payload_device(hass, body, "the Device to test from")
    cameras = system_settings_view(global_cfg)["camera_entities"]
    cam_ent = str(body.get("camera_entity") or "").strip()
    if not cameras:
        raise StudioCommandError(
            "invalid_format", "Add a camera in Shared Entities first"
        )
    if cam_ent not in cameras:
        raise StudioCommandError(
            "not_allowed", f"'{cam_ent}' isn't one of the System cameras"
        )
    msg = str(body.get("message") or "").strip()
    if not msg:
        raise StudioCommandError("invalid_format", "message is required")
    await async_execute_doorbell_intercom(
        hass,
        speaker_coord,
        action="talk_message",
        camera_entity=cam_ent,
        message=msg,
    )


async def _cmd_send_announcement(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    announcement = clean_announcement(
        body, {c.device_slug for c in iter_coordinators(hass) if not c.is_ble_tag}
    )
    data = dict(announcement["data"])
    if announcement["include_camera"]:
        cameras = system_settings_view(global_cfg)["camera_entities"]
        if not cameras:
            raise StudioCommandError(
                "invalid_format",
                "Add a camera in Shared Entities first, or turn off the camera snapshot",
            )
        data["camera_entity"] = cameras[0]
    await hass.services.async_call(
        DOMAIN, announcement["service"], data, blocking=True
    )


def _prune_coordinator_deleted_photos(
    coord: LatterCoordinator, deleted_ids: set[str]
) -> None:
    """Prune `deleted_ids` from a single coordinator's wallpaper and screensaver pools."""
    merged = dict(coord.device_data)
    changed = False

    wp_favs = [f for f in coord.wallpaper_favorites if f not in deleted_ids]
    if wp_favs != coord.wallpaper_favorites:
        merged[CONF_WALLPAPER_FAVORITES] = wp_favs
        changed = True
    if coord.wallpaper_mode == "single" and coord.configured_wallpaper_source in deleted_ids:
        merged[CONF_WALLPAPER_MODE] = "off"
        merged[CONF_WALLPAPER_SOURCE] = ""
        coord.current_wallpaper = ""
        coord.set_configured_wallpaper_source("")
        changed = True
    elif coord.wallpaper_mode == "custom" and not wp_favs:
        merged[CONF_WALLPAPER_MODE] = "off"
        merged[CONF_WALLPAPER_SOURCE] = ""
        merged[CONF_WALLPAPER_CYCLE_MINUTES] = 0
        coord.current_wallpaper = ""
        changed = True
    elif coord.current_wallpaper in deleted_ids or coord.wallpaper_source in deleted_ids:
        coord.current_wallpaper = ""
        changed = True

    ss_ids = [f for f in coord.screensaver_photo_ids if f not in deleted_ids]
    if ss_ids != coord.screensaver_photo_ids:
        merged[CONF_SCREENSAVER_PHOTO_IDS] = ss_ids
        changed = True
    if (
        coord.screensaver_photo_mode == "single"
        and coord.configured_screensaver_photo_source in deleted_ids
    ) or (coord.screensaver_photo_mode == "custom" and not ss_ids):
        merged[CONF_SCREENSAVER_PHOTO_MODE] = "off"
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        coord.current_screensaver_photo = ""
        changed = True
    elif (
        coord.current_screensaver_photo in deleted_ids
        or coord.screensaver_photo_source in deleted_ids
    ):
        coord.current_screensaver_photo = ""
        changed = True

    if changed:
        if merged != coord.device_data:
            coord.update_device_config(merged)
        coord.bind_wallpaper_cycle_timer()
        coord.bind_screensaver_cycle_timer()
        coord.async_notify_listeners()


def _prune_deleted_photos_from_coordinators(
    hass: HomeAssistant, deleted_ids: set[str]
) -> None:
    """Remove deleted photo IDs from all Devices' wallpaper & screensaver pools and re-seed active photos."""
    if not deleted_ids:
        return
    for coord in iter_coordinators(hass):
        if not coord.is_ble_tag:
            _prune_coordinator_deleted_photos(coord, deleted_ids)


def _prune_deleted_collection_from_coordinators(
    hass: HomeAssistant, collection_id: str
) -> None:
    """Clear references to a deleted collection from all Devices' wallpaper & screensaver pools."""
    for c in iter_coordinators(hass):
        if c.is_ble_tag:
            continue
        merged = dict(c.device_data)
        changed = False
        if (
            c.wallpaper_mode == "collection"
            and c.wallpaper_collection == collection_id
        ):
            merged[CONF_WALLPAPER_MODE] = "off"
            merged[CONF_WALLPAPER_COLLECTION] = ""
            merged[CONF_WALLPAPER_SOURCE] = ""
            c.current_wallpaper = ""
            c.set_configured_wallpaper_source("")
            changed = True
        if (
            c.screensaver_photo_mode == "collection"
            and c.screensaver_photo_collection == collection_id
        ):
            merged[CONF_SCREENSAVER_PHOTO_MODE] = "off"
            merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
            c.current_screensaver_photo = ""
            changed = True
        if changed:
            c.update_device_config(merged)
            c.bind_wallpaper_cycle_timer()
            c.bind_screensaver_cycle_timer()
            c.async_notify_listeners()


def _rebind_collection_pool_coordinators(hass: HomeAssistant) -> None:
    """Refresh cycle timers on coordinators currently using a collection pool."""
    for c in iter_coordinators(hass):
        if not c.is_ble_tag and (
            c.wallpaper_mode == "collection"
            or c.screensaver_photo_mode == "collection"
        ):
            c.bind_wallpaper_cycle_timer()
            c.bind_screensaver_cycle_timer()
            c.async_notify_listeners()


async def _cmd_create_photo_collection(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    raw_name = str(body.get("name") or "").strip()
    if not raw_name:
        raise StudioCommandError("invalid_format", "Collection name is required")
    try:
        col = await hass.async_add_executor_job(create_collection, hass, raw_name)
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    extra["collection"] = col
    get_ble_fabric(hass).notify_occupancy_listeners()


async def _cmd_rename_photo_collection(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    col_id = str(body.get("collection_id") or "").strip()
    raw_name = str(body.get("name") or "").strip()
    if not col_id or not raw_name:
        raise StudioCommandError(
            "invalid_format", "collection_id and name are required"
        )
    try:
        col = await hass.async_add_executor_job(
            rename_collection, hass, col_id, raw_name
        )
    except ValueError as err:
        code = "not_found" if "Unknown collection" in str(err) else "invalid_format"
        raise StudioCommandError(code, str(err)) from err
    extra["collection"] = col
    get_ble_fabric(hass).notify_occupancy_listeners()


async def _cmd_delete_photo_collection(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    col_id = str(body.get("collection_id") or "").strip()
    if not col_id:
        raise StudioCommandError("invalid_format", "collection_id is required")
    deleted = await hass.async_add_executor_job(delete_collection, hass, col_id)
    if not deleted:
        raise StudioCommandError("not_found", f"Unknown collection '{col_id}'")
    _prune_deleted_collection_from_coordinators(hass, col_id)
    extra["deleted_collection_id"] = col_id
    get_ble_fabric(hass).notify_occupancy_listeners()


async def _cmd_update_photo_metadata(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    photo_id = str(body.get("photo_id") or "").strip()
    if not photo_id:
        raise StudioCommandError("invalid_format", "photo_id is required")
    name = body.get("name") if "name" in body else None
    crop = body.get("crop") if "crop" in body else None
    collections = body.get("collections") if "collections" in body else None
    if name is None and crop is None and collections is None:
        raise StudioCommandError(
            "invalid_format", "Provide name, crop, or collections to update"
        )
    try:
        res = await hass.async_add_executor_job(
            lambda: update_photo_metadata(
                hass,
                photo_id,
                name=name,
                crop=crop,
                collections=collections,
            )
        )
    except ValueError as err:
        code = "not_found" if "Unknown photo" in str(err) else "invalid_format"
        raise StudioCommandError(code, str(err)) from err
    crop_changed = bool(res.pop("crop_changed", False))
    extra["photo"] = res
    if crop_changed or collections is not None:
        for c in iter_coordinators(hass):
            if c.is_ble_tag:
                continue
            if photo_id in {
                c.wallpaper_source,
                c.screensaver_photo_source,
            } or (
                collections is not None
                and "collection" in {c.wallpaper_mode, c.screensaver_photo_mode}
            ):
                c.bind_wallpaper_cycle_timer()
                c.bind_screensaver_cycle_timer()
                c.async_notify_listeners()
    get_ble_fabric(hass).notify_occupancy_listeners()


async def _cmd_bulk_update_photos(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    photo_ids = body.get("photo_ids")
    if not isinstance(photo_ids, list) or not photo_ids:
        raise StudioCommandError("invalid_format", "photo_ids must be a non-empty list")
    add_col = body.get("add_collection")
    rem_col = body.get("remove_collection")
    do_delete = bool(body.get("delete", False))
    if not do_delete and not add_col and not rem_col:
        raise StudioCommandError(
            "invalid_format",
            "Specify add_collection, remove_collection, or delete",
        )
    try:
        res = await hass.async_add_executor_job(
            lambda: bulk_update_photos(
                hass,
                photo_ids,
                add_collection=add_col,
                remove_collection=rem_col,
                delete=do_delete,
            )
        )
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    if res["deleted_ids"]:
        _prune_deleted_photos_from_coordinators(hass, set(res["deleted_ids"]))
    elif res["updated"] > 0:
        _rebind_collection_pool_coordinators(hass)
    extra["bulk_result"] = res
    get_ble_fabric(hass).notify_occupancy_listeners()


async def _cmd_delete_photo(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    photo_id = str(body.get("photo_id") or "").strip()
    if not photo_id:
        raise StudioCommandError("invalid_format", "photo_id is required")
    deleted = await hass.async_add_executor_job(delete_photo, hass, photo_id)
    if not deleted:
        raise StudioCommandError(
            "not_found", "That photo isn't a deletable custom photo"
        )
    _prune_deleted_photos_from_coordinators(hass, {photo_id})
    extra["deleted_photo_id"] = photo_id
    get_ble_fabric(hass).notify_occupancy_listeners()


async def _cmd_browse_media_folder(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    root = str(body.get("root") or "").strip()
    subpath = str(body.get("subpath") or "").strip()
    media_dirs = getattr(hass.config, "media_dirs", None)
    try:
        listing = await hass.async_add_executor_job(
            list_media_folder_sync, media_dirs, root, subpath
        )
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    sys_obj = get_latter_system(hass)
    used_root = str(listing.get("root") or "")
    for img in listing.get("images") or []:
        rel = str(img.get("relpath") or "")
        img["thumb_url"] = (
            sys_obj.url_signer.build_media_preview_url(
                used_root, rel, _MEDIA_THUMB_DIM, _MEDIA_THUMB_DIM
            )
            if (sys_obj is not None and used_root and rel and not img.get("too_large"))
            else ""
        )
    extra.update(listing)


async def _cmd_import_media_photos(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    root = str(body.get("root") or "").strip()
    paths = body.get("paths")
    if not root:
        raise StudioCommandError("invalid_format", "root is required")
    if not isinstance(paths, list) or not paths:
        raise StudioCommandError(
            "invalid_format", "Select at least one photo to import"
        )
    collection_id = str(body.get("collection_id") or "").strip()
    new_col_name = str(body.get("new_collection_name") or "").strip()
    deduplicate = bool(body.get("deduplicate", True))
    if not collection_id and new_col_name:
        try:
            created = await hass.async_add_executor_job(
                create_collection, hass, new_col_name
            )
            collection_id = str(created["id"])
        except ValueError as err:
            raise StudioCommandError("invalid_format", str(err)) from err

    media_dirs = getattr(hass.config, "media_dirs", None)
    try:
        result = await hass.async_add_executor_job(
            lambda: import_media_photos_sync(
                hass,
                media_dirs,
                root,
                paths,
                collection_id=collection_id or None,
                deduplicate=deduplicate,
            )
        )
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    extra["import_result"] = {
        "imported": result["imported"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "collection_id": collection_id,
    }
    if result["imported"] > 0:
        _rebind_collection_pool_coordinators(hass)
    get_ble_fabric(hass).notify_occupancy_listeners()


def _validate_photo_pool_selection(
    body: dict[str, Any], *, target: str, mode: str
) -> tuple[str, str, list[str]]:
    """Validate `source_id`, `collection_id`, or `photo_ids` for `set_device_photo_pool`."""
    known_ids = known_wallpaper_ids(include_dynamic=(target == "wallpaper"))
    valid_collections = VIRTUAL_COLLECTION_IDS | known_collection_ids()
    source_id = str(body.get("source_id") or "").strip()
    collection_id = str(body.get("collection_id") or "").strip()
    raw_photo_ids = body.get("photo_ids")
    cleaned_ids: list[str] = []

    if mode == "single":
        if not source_id or source_id not in known_ids:
            raise StudioCommandError(
                "not_allowed", "Choose a valid photo from the Photo Library"
            )
    elif mode == "collection":
        if not collection_id or collection_id not in valid_collections:
            raise StudioCommandError(
                "not_found",
                f"Unknown photo collection '{collection_id or '(empty)'}'",
            )
    elif mode == "custom":
        if not isinstance(raw_photo_ids, list):
            raise StudioCommandError("invalid_format", "photo_ids must be a list")
        for item in raw_photo_ids:
            pid = str(item or "").strip()
            if pid and pid not in cleaned_ids:
                if pid not in known_ids:
                    raise StudioCommandError("not_allowed", f"Unknown photo '{pid}'")
                cleaned_ids.append(pid)
        if not cleaned_ids:
            raise StudioCommandError(
                "invalid_format", "Select at least one photo for custom mode"
            )
        if len(cleaned_ids) > MAX_CUSTOM_PHOTO_POOL:
            raise StudioCommandError(
                "invalid_format",
                f"Custom photo pool cannot exceed {MAX_CUSTOM_PHOTO_POOL} photos",
            )
    return source_id, collection_id, cleaned_ids


def _apply_wallpaper_pool_locked(
    coordinator: LatterCoordinator,
    merged: dict[str, Any],
    mode: str,
    selection: tuple[str, str, list[str]],
    cycle_minutes: Any,
) -> None:
    """Mutate `merged` and coordinator runtime state for `target == 'wallpaper'`."""
    source_id, collection_id, cleaned_ids = selection
    merged[CONF_WALLPAPER_MODE] = mode
    if mode == "off":
        merged[CONF_WALLPAPER_SOURCE] = ""
        merged[CONF_WALLPAPER_COLLECTION] = ""
        merged[CONF_WALLPAPER_CYCLE_MINUTES] = 0
        coordinator.current_wallpaper = ""
        coordinator.set_configured_wallpaper_source("")
    elif mode == "single":
        merged[CONF_WALLPAPER_SOURCE] = source_id
        merged[CONF_WALLPAPER_COLLECTION] = ""
        coordinator.current_wallpaper = source_id
        coordinator.set_configured_wallpaper_source(source_id)
        if cycle_minutes is None:
            merged[CONF_WALLPAPER_CYCLE_MINUTES] = 0
    elif mode == "collection":
        merged[CONF_WALLPAPER_COLLECTION] = collection_id
        merged[CONF_WALLPAPER_SOURCE] = ""
        coordinator.current_wallpaper = ""
        coordinator.set_configured_wallpaper_source("")
    elif mode == "custom":
        merged[CONF_WALLPAPER_FAVORITES] = list(cleaned_ids)
        merged[CONF_WALLPAPER_COLLECTION] = ""
        merged[CONF_WALLPAPER_SOURCE] = ""
        coordinator.current_wallpaper = ""
        coordinator.set_configured_wallpaper_source("")
    if cycle_minutes is not None:
        merged[CONF_WALLPAPER_CYCLE_MINUTES] = max(0, int(cycle_minutes))
    coordinator.update_device_config(merged)
    coordinator.bind_wallpaper_cycle_timer()


def _apply_screensaver_pool_locked(
    coordinator: LatterCoordinator,
    merged: dict[str, Any],
    mode: str,
    selection: tuple[str, str, list[str]],
    timing: tuple[Any, Any],
) -> None:
    """Mutate `merged` and coordinator runtime state for `target == 'screensaver'`."""
    source_id, collection_id, cleaned_ids = selection
    cycle_minutes, shuffle = timing
    merged[CONF_SCREENSAVER_PHOTO_MODE] = mode
    if mode == "off":
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
        coordinator.current_screensaver_photo = ""
    elif mode == "single":
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = source_id
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
        coordinator.current_screensaver_photo = source_id
    elif mode == "collection":
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = collection_id
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        coordinator.current_screensaver_photo = ""
    elif mode == "custom":
        merged[CONF_SCREENSAVER_PHOTO_IDS] = list(cleaned_ids)
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        coordinator.current_screensaver_photo = ""
    if cycle_minutes is not None:
        merged[CONF_SCREENSAVER_CYCLE_MINUTES] = max(0, int(cycle_minutes))
    if shuffle is not None:
        merged[CONF_SCREENSAVER_SHUFFLE] = bool(shuffle)
    coordinator.update_device_config(merged)
    coordinator.bind_screensaver_cycle_timer()


async def _cmd_set_device_photo_pool(
    _hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    if coordinator is None:
        raise StudioCommandError("not_found", "Device required")
    if coordinator.is_ble_tag or not coordinator.has_display:
        raise StudioCommandError(
            "not_supported",
            f"{coordinator.device_title} has no display for photo pools",
        )
    target = str(body.get("target") or "").strip().lower()
    if target not in ("wallpaper", "screensaver"):
        raise StudioCommandError(
            "invalid_format", "target must be 'wallpaper' or 'screensaver'"
        )
    mode = str(body.get("mode") or "").strip().lower()
    if mode not in ("off", "single", "collection", "custom"):
        raise StudioCommandError(
            "invalid_format", "mode must be one of off, single, collection, custom"
        )
    selection = _validate_photo_pool_selection(body, target=target, mode=mode)
    cycle_minutes = body.get("cycle_minutes")
    shuffle = body.get("shuffle")

    async with coordinator.config_lock:
        merged = dict(coordinator.device_data)
        if target == "wallpaper":
            _apply_wallpaper_pool_locked(
                coordinator, merged, mode, selection, cycle_minutes
            )
        else:
            _apply_screensaver_pool_locked(
                coordinator, merged, mode, selection, (cycle_minutes, shuffle)
            )
        coordinator.schedule_persist_runtime_state()
        coordinator.async_notify_listeners()


async def _cmd_mint_camera_preview_url(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    cam_ent = str(body.get("camera_entity") or "").strip()
    if not cam_ent or not cam_ent.startswith("camera."):
        raise StudioCommandError(
            "invalid_format", "camera_entity must be a valid camera.* entity ID"
        )
    if hass.states.get(cam_ent) is None:
        raise StudioCommandError("not_found", f"Camera '{cam_ent}' was not found")
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        raise StudioCommandError("not_ready", "Latter System is not initialized")
    sig = sys_obj.url_signer.sign_on_demand_resource(
        f"camera:{cam_ent}|320|180|square",
        ttl_s=_CAMERA_PREVIEW_TTL_S,
    )
    extra["camera_entity"] = cam_ent
    extra["preview_url"] = (
        f"/api/latter/camera/system"
        f"?entity_id={quote(cam_ent, safe='')}&w=320&h=180&shape=square&sig={sig}"
    )
    extra["expires_in"] = _CAMERA_PREVIEW_TTL_S


def _str_cap(max_len: int) -> Any:
    return vol.All(str, vol.Length(max=max_len))


def _non_bool_int(val: Any) -> int:
    if isinstance(val, bool) or not isinstance(val, int):
        raise vol.Invalid("Expected an integer")
    return val


def _schema(fields: dict[Any, Any]) -> vol.Schema:
    return vol.Schema(fields, extra=vol.PREVENT_EXTRA)


PHOTOS_MEDIA_SCHEMAS: dict[str, vol.Schema] = {
    "test_doorbell_speaker": _schema({
        vol.Optional("subentry_id"): _str_cap(128),
        vol.Optional("camera_entity"): _str_cap(128),
        vol.Optional("message"): _str_cap(250),
    }),
    "send_announcement": _schema({
        vol.Optional("mode"): _str_cap(32),
        vol.Optional("target_device"): _str_cap(128),
        vol.Optional("title"): _str_cap(64),
        vol.Optional("message"): _str_cap(500),
        vol.Optional("priority"): _str_cap(32),
        vol.Optional("include_camera"): bool,
    }),
    "create_photo_collection": _schema({vol.Optional("name"): _str_cap(64)}),
    "rename_photo_collection": _schema({
        vol.Optional("collection_id"): _str_cap(64),
        vol.Optional("name"): _str_cap(64),
    }),
    "delete_photo_collection": _schema({vol.Optional("collection_id"): _str_cap(64)}),
    "update_photo_metadata": _schema({
        vol.Optional("photo_id"): _str_cap(128),
        vol.Optional("name"): _str_cap(96),
        vol.Optional("crop"): dict,
        vol.Optional("collections"): [_str_cap(64)],
    }),
    "bulk_update_photos": _schema({
        vol.Optional("photo_ids"): [_str_cap(128)],
        vol.Optional("add_collection"): vol.Any(_str_cap(64), None),
        vol.Optional("remove_collection"): vol.Any(_str_cap(64), None),
        vol.Optional("delete"): bool,
    }),
    "delete_photo": _schema({vol.Optional("photo_id"): _str_cap(128)}),
    "browse_media_folder": _schema({
        vol.Optional("root"): _str_cap(64),
        vol.Optional("subpath"): _str_cap(512),
    }),
    "import_media_photos": _schema({
        vol.Optional("root"): _str_cap(64),
        vol.Optional("paths"): [_str_cap(512)],
        vol.Optional("collection_id"): vol.Any(_str_cap(64), None),
        vol.Optional("new_collection_name"): vol.Any(_str_cap(64), None),
        vol.Optional("deduplicate"): bool,
    }),
    "set_device_photo_pool": _schema({
        vol.Optional("target"): _str_cap(32),
        vol.Optional("mode"): _str_cap(32),
        vol.Optional("source_id"): vol.Any(_str_cap(128), None),
        vol.Optional("collection_id"): vol.Any(_str_cap(64), None),
        vol.Optional("photo_ids"): [_str_cap(128)],
        vol.Optional("cycle_minutes"): vol.Any(_non_bool_int, None),
        vol.Optional("shuffle"): vol.Any(bool, None),
    }),
    "mint_camera_preview_url": _schema({vol.Optional("camera_entity"): _str_cap(128)}),
}

__all__ = [
    "MAX_CUSTOM_PHOTO_POOL",
    "PHOTOS_MEDIA_SCHEMAS",
    "_cmd_browse_media_folder",
    "_cmd_bulk_update_photos",
    "_cmd_create_photo_collection",
    "_cmd_delete_photo",
    "_cmd_delete_photo_collection",
    "_cmd_import_media_photos",
    "_cmd_mint_camera_preview_url",
    "_cmd_rename_photo_collection",
    "_cmd_send_announcement",
    "_cmd_set_device_photo_pool",
    "_cmd_test_doorbell_speaker",
    "_cmd_update_photo_metadata",
]
