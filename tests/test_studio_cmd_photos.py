"""Tests for Studio Photo Library collections, metadata, pools, Day & Night Sky, and HA /media import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from custom_components.latter.const import (
    DAY_NIGHT_SKY_NATIVE_URL,
    DAY_NIGHT_SKY_PRESET_ID,
    STUDIO_REV,
)
from custom_components.latter.wallpapers.store import save_uploaded_photo_bytes
from tests.helpers import call_ws, ensure_area, make_jpeg_bytes, make_ws_connection


async def test_studio_commands_photo_library_pools_and_media_import(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise Studio Photo Library collections, wallpaper/screensaver pools, and /media import."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    conn = make_ws_connection(hass)
    msg_seq = 100

    async def _sys_cmd(
        command: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal msg_seq
        msg_seq += 1
        await call_ws(
            hass,
            conn,
            msg_seq,
            "latter/system/command",
            command=command,
            subentry_id=coord.subentry_id,
            payload=payload or {},
            studio_rev=STUDIO_REV,
        )
        assert not conn.errors, f"{command} failed: {conn.errors}"
        return conn.results[-1][1]

    async def _dev_cmd(
        command: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal msg_seq
        msg_seq += 1
        await call_ws(
            hass,
            conn,
            msg_seq,
            "latter/device/command",
            command=command,
            subentry_id=coord.subentry_id,
            payload=payload or {},
            studio_rev=STUDIO_REV,
        )
        assert not conn.errors, f"{command} failed: {conn.errors}"
        return conn.results[-1][1]

    # Retired wallpaper WS commands must be rejected as unknown_command
    for retired_scope, retired_cmd in (
        ("device", "upload_wallpaper"),
        ("device", "select_wallpaper"),
        ("device", "toggle_wallpaper_favorite"),
        ("system", "delete_wallpaper"),
    ):
        msg_seq += 1
        await call_ws(
            hass,
            conn,
            msg_seq,
            f"latter/{retired_scope}/command",
            command=retired_cmd,
            **({"subentry_id": coord.subentry_id} if retired_scope == "device" else {}),
            payload={},
            studio_rev=STUDIO_REV,
        )
        assert conn.errors[-1][1] == "unknown_command"
        conn.errors.clear()

    # Photo Library Collections + Metadata + Bulk + Device Photo Pool (`STUDIO_REV = 44`)
    col_created = await _sys_cmd("create_photo_collection", {"name": "Family"})
    col_id = col_created["collection"]["id"]
    assert any(
        c["id"] == col_id and c["name"] == "Family"
        for c in col_created["photo_collections"]
    )
    col_renamed = await _sys_cmd(
        "rename_photo_collection", {"collection_id": col_id, "name": "Favorites"}
    )
    assert col_renamed["collection"]["name"] == "Favorites"

    sample_jpg = make_jpeg_bytes(64, 64, (80, 120, 200))
    dev_photo_rec = await hass.async_add_executor_job(
        lambda: save_uploaded_photo_bytes(
            hass, "dev_bg.jpg", sample_jpg, collection_id=col_id
        )
    )
    dev_wp_id = dev_photo_rec["id"]
    assert dev_wp_id.startswith("photo:")

    upd_meta = await _sys_cmd(
        "update_photo_metadata",
        {
            "photo_id": dev_wp_id,
            "name": "Living Wall",
            "crop": {"x": 0.4, "y": 0.6, "zoom": 1.4},
            "collections": [col_id],
        },
    )
    assert upd_meta["photo"]["name"] == "Living Wall"
    assert upd_meta["photo"]["crop"] == {"x": 0.4, "y": 0.6, "zoom": 1.4}

    # Select single uploaded photo on Device wallpaper pool
    await _dev_cmd(
        "set_device_photo_pool",
        {"target": "wallpaper", "mode": "single", "source_id": dev_wp_id},
    )
    assert coord.wallpaper_mode == "single"
    assert coord.wallpaper_source == dev_wp_id
    assert "mode=wallpaper" in coord.build_wallpaper_url()

    # Select Day & Night Sky -> native sentinel `latter://day_night_sky` pushed in `area_context`
    await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "wallpaper",
            "mode": "single",
            "source_id": DAY_NIGHT_SKY_PRESET_ID,
        },
    )
    assert coord.build_wallpaper_url() == DAY_NIGHT_SKY_NATIVE_URL
    _, area_attrs = coord.get_area_context_payload()
    assert area_attrs["wallpaper_url"] == DAY_NIGHT_SKY_NATIVE_URL
    assert area_attrs["screensaver_photo_url"] == ""

    # Screensaver Photo Frame pool + area_context field 41 (`screensaver_photo_url`)
    await _dev_cmd(
        "save_device_config",
        {
            "config": {
                "screensaver_mode": "Always",
                "screensaver_style": "Photo Frame",
                "screensaver_photo_clock": True,
                "weather_app_background": False,
            }
        },
    )
    ss_pool_state = await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "screensaver",
            "mode": "custom",
            "photo_ids": ["preset:ocean_waves", dev_wp_id],
            "cycle_minutes": 5,
            "shuffle": True,
        },
    )
    assert coord.screensaver_photo_mode == "custom"
    assert coord.screensaver_shuffle is True
    assert coord.screensaver_cycle_minutes == 5
    assert coord._unsub_screensaver_timer is not None
    assert ss_pool_state["live"]["screensaver_pool_count"] == 2
    _, area_attrs_ss = coord.get_area_context_payload()
    assert "mode=screensaver" in area_attrs_ss["screensaver_photo_url"]
    assert (
        area_attrs_ss["payload"].split("\x1f")[41]
        == area_attrs_ss["screensaver_photo_url"]
    )

    # Dynamic preset rejected on screensaver pool
    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/command",
        command="set_device_photo_pool",
        subentry_id=coord.subentry_id,
        payload={
            "target": "screensaver",
            "mode": "single",
            "source_id": DAY_NIGHT_SKY_PRESET_ID,
        },
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "not_allowed"
    conn.errors.clear()

    # `delete_photo` is canonical on System scope; calling it on Device scope fails with `wrong_scope`
    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/command",
        command="delete_photo",
        subentry_id=coord.subentry_id,
        payload={"photo_id": dev_wp_id},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "wrong_scope"
    conn.errors.clear()

    # Deleting `dev_wp_id` prunes it cleanly from the Device's screensaver custom pool
    await _sys_cmd("delete_photo", {"photo_id": dev_wp_id})
    assert dev_wp_id not in coord.screensaver_photo_ids
    assert coord.screensaver_photo_ids == ["preset:ocean_waves"]

    # Wallpaper pool rotation state machine: custom -> collection -> delete collection prunes -> off
    rot_state = await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "wallpaper",
            "mode": "custom",
            "photo_ids": ["preset:ocean_waves", "preset:mars_crater"],
            "cycle_minutes": 5,
        },
    )
    assert coord.wallpaper_cycle_minutes == 5
    assert coord.wallpaper_source == "preset:ocean_waves"
    assert coord._unsub_wallpaper_timer is not None
    assert rot_state["live"]["wallpaper_pool_count"] == 2

    await _sys_cmd(
        "bulk_update_photos",
        {
            "photo_ids": ["preset:forest_mountains", "preset:wheat_field"],
            "add_collection": col_id,
        },
    )
    await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "wallpaper",
            "mode": "collection",
            "collection_id": col_id,
            "cycle_minutes": 15,
        },
    )
    assert coord.wallpaper_mode == "collection"
    assert coord.wallpaper_collection == col_id
    assert coord.wallpaper_source == "preset:forest_mountains"

    # Deleting the active collection cleanly resets wallpaper pool to off
    await _sys_cmd("delete_photo_collection", {"collection_id": col_id})
    assert coord.wallpaper_mode == "off"
    assert coord.wallpaper_collection == ""
    assert coord.wallpaper_source == ""

    # HA `/media` browse & import WS commands
    def _seed_media_file() -> Path:
        m_dir = Path(hass.config.config_dir) / "ws_media"
        (m_dir / "trip").mkdir(parents=True, exist_ok=True)
        (m_dir / "trip" / "a.jpg").write_bytes(sample_jpg)
        return m_dir

    media_dir = await hass.async_add_executor_job(_seed_media_file)
    hass.config.media_dirs = {"local": str(media_dir)}

    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/system/command",
        command="browse_media_folder",
        payload={"root": "local", "subpath": "trip"},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    browse_res = conn.results[-1][1]
    assert browse_res["root"] == "local"
    assert len(browse_res["images"]) == 1
    assert browse_res["images"][0]["thumb_url"].startswith(
        "/api/latter/wallpaper/system?"
    )

    import_res = await _sys_cmd(
        "import_media_photos",
        {
            "root": "local",
            "paths": ["trip/a.jpg"],
            "new_collection_name": "Trip Import",
            "deduplicate": True,
        },
    )
    assert import_res["import_result"]["imported"] == 1
    assert import_res["import_result"]["collection_id"].startswith("col_")

    # Reset screensaver style back to default for downstream group tests
    await _dev_cmd(
        "save_device_config",
        {
            "config": {
                "screensaver_mode": "Docked Only",
                "screensaver_style": "Ambient Clock",
            }
        },
    )

    # Turn Off Wallpaper resets active source & rotation timer
    final_off = await _dev_cmd(
        "set_device_photo_pool", {"target": "wallpaper", "mode": "off"}
    )
    assert coord.wallpaper_source == ""
    assert coord.wallpaper_cycle_minutes == 0
    assert coord._unsub_wallpaper_timer is None
    assert final_off["config"]["wallpaper_cycle_minutes"] == 0

    assert await hass.config_entries.async_unload(entry.entry_id) is True
