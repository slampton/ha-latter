"""Targeted real-HA 2026.11 coverage tests for Latter Studio system, device, WS, panel, and state-gate modules."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from homeassistant.components import frontend, panel_custom
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.util import dt as dt_util
import probatio as vol
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.latter.const import (
    CONF_AREA_ILLUMINANCE_CONFIG,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_IGNORED_DISCOVERED_DEVICES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    DOMAIN,
    STUDIO_REV,
    SUBENTRY_BLE_TAG,
)
from custom_components.latter.hub_registry import (
    get_domain_data,
    get_global_config,
    iter_coordinators,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.studio import (
    commands as studio_commands,
    device_commands,
    panel as studio_panel,
    system_commands,
)
from custom_components.latter.studio.commands import (
    _async_dispatch_scoped_command,
    _bind_subscription_cleanup,
)
from custom_components.latter.studio.device_commands import (
    DEVICE_COMMAND_SCHEMAS,
    MAX_CUSTOM_PHOTO_POOL,
    _cmd_device_action,
    _cmd_esphome_entity_action,
    _cmd_save_device_config,
    _cmd_set_device_photo_pool,
    _optional_level,
    _validate_photo_pool_selection,
    evaluate_bedtime_if_ready,
)
from custom_components.latter.studio.panel import (
    async_register_studio_icon_module,
    async_register_studio_panel,
    async_unregister_studio_panel,
)
from custom_components.latter.studio.payload import StudioCommandError
from custom_components.latter.studio.state_gates import SectionHashGate
from custom_components.latter.studio.system_commands import (
    SYSTEM_COMMAND_SCHEMAS,
    _apply_group_config_updates,
    _apply_group_scope_and_seed,
    _cmd_add_ble_device,
    _cmd_add_latter_device,
    _cmd_mint_camera_preview_url,
    _cmd_rotate_signing_key,
    _cmd_set_ble_scanner_offset,
    _ensure_ble_target_unique,
    _normalize_ble_target_key,
    _prune_deleted_photos_from_coordinators,
    compute_illuminance_calibration_from_stats,
)
from custom_components.latter.wallpapers.models import VIRTUAL_COLLECTION_ALL
from custom_components.latter.wallpapers.store import save_uploaded_photo_bytes
from tests.helpers import (
    add_mock_entry,
    call_ws,
    ensure_area,
    get_extra_js_urls,
    get_service_calls,
    make_jpeg_bytes,
    make_subentry_dict,
    make_ws_connection,
    mock_service,
    prepare_latter_dependencies,
    register_entity,
)


async def test_state_gates_panel_and_pure_studio_helpers(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise SectionHashGate, Studio panel lifecycle error paths, stop cleanup, and pure validators."""
    # 1) SectionHashGate.mark_dirty selective & full invalidation (state_gates.py: 51-55)
    gate = SectionHashGate()
    gate.record_initial(
        {
            "discovered_ble_devices": [{"id": "d1"}],
            "system_wallpapers": [{"id": "preset:ocean_waves"}],
            "photo_collections": [{"id": "col_1"}],
            "ble_area_signatures": [{"area_id": "living_room"}],
        }
    )
    assert gate.has_sent("discovered_ble_devices") is True
    assert gate.has_sent("system_wallpapers") is True

    gate.mark_dirty("discovered_ble_devices")
    assert gate.has_sent("discovered_ble_devices") is False
    assert gate.has_sent("system_wallpapers") is True
    filtered = gate.filter_sections(
        {
            "discovered_ble_devices": [{"id": "d1"}],
            "system_wallpapers": [{"id": "preset:ocean_waves"}],
        }
    )
    assert "discovered_ble_devices" in filtered
    assert "system_wallpapers" not in filtered

    gate.mark_dirty()
    assert gate.has_sent("discovered_ble_devices") is False
    assert gate.has_sent("system_wallpapers") is False
    assert gate.has_sent("photo_collections") is False

    # 2) Studio panel lifecycle error & idempotency branches (panel.py: 62-66, 73-76, 98, 119-120, 136-137, 141-142)
    await prepare_latter_dependencies(hass)
    domain_data = get_domain_data(hass)

    def _raise_os_err(_path: Path) -> str:
        raise OSError("missing icon bundle")

    with monkeypatch.context() as mp:
        mp.setattr(studio_panel, "content_digest", _raise_os_err)
        assert await async_register_studio_icon_module(hass) is None

    # Failed static path registration must NOT poison `studio_static_prefixes`
    domain_data.studio_static_prefixes.clear()

    async def _fail_static_paths(_configs: list[Any]) -> None:
        raise RuntimeError("http busy")

    with monkeypatch.context() as mp:
        mp.setattr(hass.http, "async_register_static_paths", _fail_static_paths)
        with pytest.raises(RuntimeError, match="http busy"):
            await studio_panel._async_ensure_static_dir(hass)
    assert not domain_data.studio_static_prefixes

    # Stale prev_icon_url removal succeeds, then fails cleanly
    stale_url_1 = "/latter_ui_old/latter-icons.js?v=old1"
    frontend.add_extra_js_url(hass, stale_url_1)
    domain_data.studio_icon_js_url = stale_url_1
    first_icon_url = await async_register_studio_icon_module(hass)
    assert first_icon_url is not None
    assert stale_url_1 not in get_extra_js_urls(hass)
    assert first_icon_url in get_extra_js_urls(hass)

    # Repeat call when `studio_icon_js_url` already matches current prefix returns early without re-hashing
    with monkeypatch.context() as mp:
        mp.setattr(studio_panel, "content_digest", _raise_os_err)
        assert await async_register_studio_icon_module(hass) == first_icon_url

    stale_url_2 = "/latter_ui_old/latter-icons.js?v=old2"
    domain_data.studio_icon_js_url = stale_url_2

    def _raise_remove_err(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("frontend busy")

    with monkeypatch.context() as mp:
        mp.setattr(frontend, "remove_extra_js_url", _raise_remove_err)
        second_icon_url = await async_register_studio_icon_module(hass)
    assert second_icon_url == first_icon_url

    # Panel registration succeeds, second call hits idempotent early return (line 98)
    panel_calls: list[dict[str, Any]] = []
    orig_reg_panel = panel_custom.async_register_panel

    async def _spy_reg_panel(*args: Any, **kwargs: Any) -> Any:
        panel_calls.append(dict(kwargs))
        return await orig_reg_panel(*args, **kwargs)

    with monkeypatch.context() as mp:
        mp.setattr(panel_custom, "async_register_panel", _spy_reg_panel)
        await async_register_studio_panel(hass)
        assert len(panel_calls) == 1
        assert domain_data.registered_panel_url is not None
        await async_register_studio_panel(hass)
        assert len(panel_calls) == 1

    # Panel registration exception is caught cleanly (lines 119-120)
    domain_data.registered_panel_url = None

    async def _fail_reg_panel(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("panel_custom failure")

    with monkeypatch.context() as mp:
        mp.setattr(panel_custom, "async_register_panel", _fail_reg_panel)
        await async_register_studio_panel(hass)
    assert domain_data.registered_panel_url is None

    # Panel & icon unregistration exception paths (lines 136-137, 141-142)
    domain_data.studio_icon_js_url = first_icon_url
    with monkeypatch.context() as mp:
        mp.setattr(frontend, "async_remove_panel", _raise_remove_err)
        mp.setattr(frontend, "remove_extra_js_url", _raise_remove_err)
        async_unregister_studio_panel(hass, remove_icon_module=True)
    assert domain_data.registered_panel_url is None
    assert domain_data.studio_icon_js_url is None

    # 3) commands.py direct dispatch unknown command (126) & HA-stop cleanup callback (376-377)
    with pytest.raises(StudioCommandError) as exc_cmd:
        await _async_dispatch_scoped_command(hass, "system", None, "no_such_cmd", {})
    assert exc_cmd.value.code == "unknown_command"

    cleaned: list[str] = []
    debounce_slot: list[Any] = [lambda: cleaned.append("debounce")]
    state_slot: list[Any] = [lambda: cleaned.append("state")]
    coord_slots: dict[int, Any] = {1: lambda: cleaned.append("coord")}
    extra_slots: list[Any] = [lambda: cleaned.append("extra")]

    # Fire real EVENT_HOMEASSISTANT_STOP so _bind_subscription_cleanup executes all cleanup callbacks
    _bind_subscription_cleanup(hass, debounce_slot, state_slot, coord_slots, extra_slots)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert set(cleaned) == {"debounce", "state", "coord", "extra"}
    assert debounce_slot[0] is None
    assert state_slot[0] is None
    assert coord_slots == {}
    assert extra_slots == []

    # 4) device_commands.py pure & fallback paths (80, 169, 254-262, 278, 308, 351, 363, 454, 494, 499-503)
    sentinel_sys = object()
    bedtime_mock = AsyncMock()
    with monkeypatch.context() as mp:
        mp.setattr(device_commands, "get_latter_system", lambda _h: sentinel_sys)
        mp.setattr(device_commands, "async_evaluate_hub_bedtime_schedules", bedtime_mock)
        await evaluate_bedtime_if_ready(hass)
    bedtime_mock.assert_awaited_once_with(sentinel_sys)

    for fn in (
        _cmd_save_device_config,
        _cmd_esphome_entity_action,
        _cmd_device_action,
        _cmd_set_device_photo_pool,
    ):
        with pytest.raises(StudioCommandError) as exc_none:
            await fn(hass, None, {}, {}, {})
        assert exc_none.value.code == "not_found"

    assert _optional_level({"level": None}) is None
    assert _optional_level({"level": "42.6"}) == 43
    for bad_lvl in (True, "bad", float("nan"), float("inf")):
        with pytest.raises(StudioCommandError) as exc_lvl:
            _optional_level({"level": bad_lvl})
        assert exc_lvl.value.code == "invalid_format"

    with pytest.raises(StudioCommandError) as exc_pool_type:
        _validate_photo_pool_selection(
            {"photo_ids": "not_a_list"}, target="wallpaper", mode="custom"
        )
    assert exc_pool_type.value.code == "invalid_format"

    fake_ids = [f"photo:item_{i:03d}" for i in range(MAX_CUSTOM_PHOTO_POOL + 1)]
    with monkeypatch.context() as mp:
        mp.setattr(
            device_commands,
            "known_wallpaper_ids",
            lambda include_dynamic=True: set(fake_ids),
        )
        with pytest.raises(StudioCommandError) as exc_pool_max:
            _validate_photo_pool_selection(
                {"photo_ids": fake_ids}, target="wallpaper", mode="custom"
            )
    assert exc_pool_max.value.code == "invalid_format"

    assert DEVICE_COMMAND_SCHEMAS["esphome_entity_action"]({"level": 50})["level"] == 50
    for bad_num in (True, float("nan"), float("inf")):
        with pytest.raises(vol.Invalid):
            DEVICE_COMMAND_SCHEMAS["esphome_entity_action"]({"level": bad_num})
    with pytest.raises(vol.Invalid):
        DEVICE_COMMAND_SCHEMAS["save_device_config"]({"expected_config_rev": True})

    # 5) system_commands.py pure / uninitialized-hub paths (565, 569, 1074, 1164, 1173, 1176-1177, 1201-1204, 1600, 1648-1654, 1672-1677, 1687-1689, 1735, 1741, 1743)
    with pytest.raises(StudioCommandError) as exc_rot_none:
        await _cmd_rotate_signing_key(hass, None, {}, {}, {})
    assert exc_rot_none.value.code == "not_ready"

    rotate_mock = AsyncMock()
    with monkeypatch.context() as mp:
        mp.setattr(system_commands, "get_latter_system", lambda _h: sentinel_sys)
        mp.setattr(system_commands, "async_rotate_hub_hmac_secret", rotate_mock)
        await _cmd_rotate_signing_key(hass, None, {}, {}, {})
    rotate_mock.assert_awaited_once_with(sentinel_sys)

    hass.states.async_set("camera.driveway", "idle")
    with pytest.raises(StudioCommandError) as exc_cam_not_ready:
        await _cmd_mint_camera_preview_url(
            hass, None, {"camera_entity": "camera.driveway"}, {}, {}
        )
    assert exc_cam_not_ready.value.code == "not_ready"

    with pytest.raises(StudioCommandError) as exc_no_entry_dev:
        await _cmd_add_latter_device(hass, None, {}, {}, {})
    assert exc_no_entry_dev.value.code == "not_found"

    with pytest.raises(StudioCommandError) as exc_no_entry_ble:
        await _cmd_add_ble_device(hass, None, {}, {}, {})
    assert exc_no_entry_ble.value.code == "not_found"

    assert _normalize_ble_target_key("") == ""
    assert _normalize_ble_target_key("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"
    assert (
        _normalize_ble_target_key("ibeacon:E2C56DB5-DFFB-48D2-B060-D0F5A71096E1")
        == "e2c56db5-dffb-48d2-b060-d0f5a71096e1"
    )
    assert _normalize_ble_target_key("CustomBeacon") == "custombeacon"

    sub_only_entry = add_mock_entry(
        hass,
        domain=DOMAIN,
        entry_id="entry_sub_only_ble",
        subentries_data=[
            make_subentry_dict(
                {CONF_BLE_TARGET_ADDRESS: "99:88:77:66:55:44"},
                subentry_type=SUBENTRY_BLE_TAG,
                title="Orphan Tag",
                subentry_id="sub_orphan_tag",
            )
        ],
    )
    with pytest.raises(StudioCommandError) as exc_sub_dup:
        _ensure_ble_target_unique(hass, sub_only_entry, "new_tag", "99-88-77-66-55-44")
    assert exc_sub_dup.value.code == "already_configured"

    # Illuminance stats edge cases: single sample, None/bool/bad strings, <4 positive means, all-zero means
    cal_single = compute_illuminance_calibration_from_stats(
        [
            {"min": None, "mean": True},
            {"min": "bad", "mean": "also_bad"},
            {"min": 1.5, "mean": 25.0},
        ]
    )
    assert cal_single == (1.5, 25.0)
    cal_small_pos = compute_illuminance_calibration_from_stats(
        [{"min": 1.0, "mean": 1.0}, {"min": 1.0, "mean": 42.0}]
    )
    assert cal_small_pos == (1.0, 42.0)
    cal_all_zero = compute_illuminance_calibration_from_stats(
        [{"min": 0.0, "mean": 0.0}, {"min": 0.0, "mean": 0.0}]
    )
    assert cal_all_zero == (0.0, 5.0)

    with pytest.raises(vol.Invalid):
        SYSTEM_COMMAND_SCHEMAS["save_system_config"]({"expected_config_rev": True})
    for bad_off in (True, float("nan"), float("inf")):
        with pytest.raises(vol.Invalid):
            SYSTEM_COMMAND_SCHEMAS["set_ble_scanner_offset"](
                {"scanner_source": "AA:BB", "offset_db": bad_off}
            )


async def test_device_commands_and_ws_endpoint_errors(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise device_commands branches and WS export/import/reset/command error paths."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    conn = make_ws_connection(hass)
    msg_id = 0

    async def _ws(ws_type: str, **payload: Any) -> dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        res_msg = await call_ws(
            hass, conn, msg_id, ws_type, studio_rev=STUDIO_REV, **payload
        )
        assert res_msg is not None
        return res_msg

    # 1) save_device_config: group transitions, unknown group, activity_sources, wallpaper lock, explicit updates, MA refresh
    res = await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"device_group": "handhelds"}},
    )
    assert res and res["success"] is True
    assert coord.device_group == "handhelds"

    # Switch back to custom ("") -> lines 148-149
    res = await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"device_group": ""}},
    )
    assert res and res["success"] is True
    assert coord.device_group == "custom"

    # Unknown device group -> line 154
    await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"device_group": "no_such_group"}},
    )
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    # Switch from custom to handhelds WITH explicit_other_updates -> lines 224-227
    res = await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"device_group": "handhelds", "alert_volume": 77}},
    )
    assert res and res["success"] is True
    assert coord.get_device_pref("alert_volume") == 77

    # activity_sources valid (194-196) and ValueError -> SettingsScopeError (197-198)
    res = await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"activity_sources": "timers,alarms"}},
    )
    assert res and res["success"] is True
    assert coord.device_data["activity_sources"] == "alarms,timers"

    def _raise_val_err(_raw: Any) -> str:
        raise ValueError("rejected activity source")

    with monkeypatch.context() as mp:
        mp.setattr(device_commands, "normalize_activity_sources", _raise_val_err)
        await _ws(
            "latter/device/command",
            command="save_device_config",
            subentry_id=coord.subentry_id,
            payload={"config": {"activity_sources": "timers"}},
        )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    # wallpaper_cycle_minutes=0 locks current_wallpaper when wallpaper_source omitted (line 206)
    res = await _ws(
        "latter/device/command",
        command="set_device_photo_pool",
        subentry_id=coord.subentry_id,
        payload={
            "target": "wallpaper",
            "mode": "single",
            "source_id": "preset:ocean_waves",
            "cycle_minutes": 5,
        },
    )
    assert res and res["success"] is True
    assert coord.current_wallpaper == "preset:ocean_waves"
    res = await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"wallpaper_cycle_minutes": 0}},
    )
    assert res and res["success"] is True
    assert coord.configured_wallpaper_source == "preset:ocean_waves"
    assert coord.wallpaper_cycle_minutes == 0

    # ma_player_entity change triggers async_refresh_ma_link (line 237)
    ma_refreshes: list[str] = []
    orig_ma_refresh = device_commands.async_refresh_ma_link

    def _spy_ma_refresh(h: Any, c: Any) -> Any:
        ma_refreshes.append(c.subentry_id)
        return orig_ma_refresh(h, c)

    with monkeypatch.context() as mp:
        mp.setattr(device_commands, "async_refresh_ma_link", _spy_ma_refresh)
        res = await _ws(
            "latter/device/command",
            command="save_device_config",
            subentry_id=coord.subentry_id,
            payload={"config": {"ma_player_entity": "media_player.ma_main"}},
        )
    assert res and res["success"] is True
    assert ma_refreshes == [coord.subentry_id]

    # Schema validation failure -> commands.py 131-132 + device_commands.py 494
    await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"expected_config_rev": True},
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    # 2) esphome_entity_action: TargetNotAllowed (commands.py 530-531), level parsing (254-262), ServiceValidationError/HomeAssistantError (294-297)
    await _ws(
        "latter/device/command",
        command="esphome_entity_action",
        subentry_id=coord.subentry_id,
        payload={"entity_id": "light.not_bound_here", "action": "toggle"},
    )
    assert conn.errors[-1][1] == "not_allowed"
    conn.errors.clear()

    spk_eid = f"media_player.{coord.device_slug}_music"
    res = await _ws(
        "latter/device/command",
        command="esphome_entity_action",
        subentry_id=coord.subentry_id,
        payload={"entity_id": spk_eid, "action": "set_level", "level": "55"},
    )
    assert res and res["success"] is True

    for bad_level in ("not_a_num", "inf", True):
        await _ws(
            "latter/device/command",
            command="esphome_entity_action",
            subentry_id=coord.subentry_id,
            payload={"entity_id": spk_eid, "action": "set_level", "level": bad_level},
        )
        assert conn.errors[-1][1] == "invalid_format"
        conn.errors.clear()

    with monkeypatch.context() as mp:
        mp.setattr(
            device_commands,
            "async_execute_area_action",
            AsyncMock(side_effect=ServiceValidationError("bad option")),
        )
        await _ws(
            "latter/device/command",
            command="esphome_entity_action",
            subentry_id=coord.subentry_id,
            payload={"entity_id": spk_eid, "action": "toggle"},
        )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    with monkeypatch.context() as mp:
        mp.setattr(
            device_commands,
            "async_execute_area_action",
            AsyncMock(side_effect=HomeAssistantError("service failed")),
        )
        await _ws(
            "latter/device/command",
            command="esphome_entity_action",
            subentry_id=coord.subentry_id,
            payload={"entity_id": spk_eid, "action": "toggle"},
        )
    assert conn.errors[-1][1] == "command_failed"
    conn.errors.clear()

    # 3) device_action HomeAssistantError -> command_failed (317-318)
    with monkeypatch.context() as mp:
        mp.setattr(
            coord,
            "async_send_device_command",
            AsyncMock(side_effect=HomeAssistantError("Device offline")),
        )
        await _ws(
            "latter/device/command",
            command="device_action",
            subentry_id=coord.subentry_id,
            payload={"action": "wake_screen"},
        )
    assert conn.errors[-1][1] == "command_failed"
    conn.errors.clear()

    # 4) set_device_photo_pool guards (345, 356, 359, 456, 462, 467) & screensaver single/collection/off (422-432)
    await _ws(
        "latter/device/command",
        command="set_device_photo_pool",
        subentry_id="sub_tag",
        payload={"target": "wallpaper", "mode": "off"},
    )
    assert conn.errors[-1][1] == "not_supported"
    conn.errors.clear()

    for bad_payload, expected_code in (
        ({"target": "invalid", "mode": "off"}, "invalid_format"),
        ({"target": "wallpaper", "mode": "invalid"}, "invalid_format"),
        ({"target": "wallpaper", "mode": "collection", "collection_id": "col_none"}, "not_found"),
        ({"target": "wallpaper", "mode": "custom", "photo_ids": ["photo:missing"]}, "not_allowed"),
        ({"target": "wallpaper", "mode": "custom", "photo_ids": []}, "invalid_format"),
    ):
        await _ws(
            "latter/device/command",
            command="set_device_photo_pool",
            subentry_id=coord.subentry_id,
            payload=bad_payload,
        )
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    for mode_payload, expected_mode, expected_src, expected_col in (
        (
            {"target": "screensaver", "mode": "single", "source_id": "preset:ocean_waves"},
            "single",
            "preset:ocean_waves",
            "",
        ),
        (
            {
                "target": "screensaver",
                "mode": "collection",
                "collection_id": VIRTUAL_COLLECTION_ALL,
            },
            "collection",
            "",
            VIRTUAL_COLLECTION_ALL,
        ),
        ({"target": "screensaver", "mode": "off"}, "off", "", ""),
    ):
        res = await _ws(
            "latter/device/command",
            command="set_device_photo_pool",
            subentry_id=coord.subentry_id,
            payload=mode_payload,
        )
        assert res and res["success"] is True
        assert coord.screensaver_photo_mode == expected_mode
        assert coord.current_screensaver_photo == expected_src
        if expected_col:
            assert coord.screensaver_photo_collection == expected_col

    # 5) commands.py WS endpoint error paths (520, 535-538, 635-640, 664-666, 692-697, 716-721, 724-729, 750-755, 763-768)
    await _ws(
        "latter/device/command",
        command="save_device_config",
        subentry_id="missing_sub",
        payload={},
    )
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    with monkeypatch.context() as mp:
        mp.setitem(
            system_commands.SYSTEM_COMMAND_HANDLERS,
            "clear_internal_logs",
            AsyncMock(side_effect=RuntimeError("unexpected boom")),
        )
        await _ws(
            "latter/system/command",
            command="clear_internal_logs",
            payload={},
        )
    assert conn.errors[-1][1] == "command_failed"
    conn.errors.clear()

    await _ws("latter/device/export", subentry_id="missing_sub")
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await _ws("latter/system/import", bundle={"scope": "device"})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    await _ws("latter/system/import", bundle={"scope": "system", "version": 999})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    await _ws(
        "latter/device/import",
        subentry_id=coord.subentry_id,
        bundle={"scope": "system"},
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    await _ws(
        "latter/device/import",
        subentry_id="missing_sub",
        bundle={"scope": "device"},
    )
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await _ws("latter/device/reset", subentry_id="missing_sub")
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await _ws(
        "latter/device/reset",
        subentry_id=coord.subentry_id,
        device_settings=False,
        latter_options=False,
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    with monkeypatch.context() as mp:
        mp.setattr(
            studio_commands,
            "async_reset_device",
            AsyncMock(side_effect=HomeAssistantError("reset backend error")),
        )
        await _ws(
            "latter/device/reset",
            subentry_id=coord.subentry_id,
            device_settings=True,
            latter_options=True,
        )
    assert conn.errors[-1][1] == "command_failed"
    conn.errors.clear()

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_commands_subscribe_survey_flush_stopping_and_remove_device(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise survey timer flush, CoreState.stopping guards, entity-change push, token invalidation, and remove_device."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    fabric = get_ble_fabric(hass)
    conn = make_ws_connection(hass)
    conn_missing = make_ws_connection(hass)

    await call_ws(
        hass,
        conn,
        10,
        "latter/system/subscribe",
        subentry_id=coord.subentry_id,
        survey_subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    await call_ws(
        hass,
        conn_missing,
        11,
        "latter/system/subscribe",
        survey_subentry_id="nonexistent_sub",
        studio_rev=STUDIO_REV,
    )
    conn.messages.clear()
    conn_missing.messages.clear()

    # Rapid survey burst: zero pre-coalesce work, time advance flushes single compact delta
    # conn_missing ignores delta cleanly
    assert coord._ble_tracker is not None
    fabric.emit_survey_delta(coord._ble_tracker)
    fabric.emit_survey_delta(coord._ble_tracker)
    assert conn_missing.messages == []
    assert conn.messages == []

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert [
        m for m in conn_missing.messages if m["event"].get("type") == "ble_survey_delta"
    ] == []
    survey_evts = [
        m["event"] for m in conn.messages if m["event"].get("type") == "ble_survey_delta"
    ]
    assert len(survey_evts) == 1
    assert "ble_area_signatures" not in survey_evts[0]
    assert "area_presence_grid" not in survey_evts[0]

    # CoreState.stopping suppresses survey deltas and scheduled state pushes
    conn.messages.clear()
    orig_state = hass.state
    hass.state = CoreState.stopping
    try:
        fabric.emit_survey_delta(coord._ble_tracker)
        coord.async_notify_listeners()
    finally:
        hass.state = orig_state
    assert conn.messages == []

    # Rotate signing key so HMAC token changes -> SectionTokenGate refreshes signed wallpaper sections
    # `_system_rpc_outbox` is NO LONGER watched (avoids RPC frame push spam); watched entity mutation triggers push
    await call_ws(
        hass,
        conn,
        20,
        "latter/system/command",
        command="rotate_signing_key",
        payload={},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    rotated_events = [m["event"] for m in conn.messages if m["event"].get("type") == "state"]
    assert rotated_events
    assert "system_wallpapers" in rotated_events[-1]
    assert "wallpapers" in rotated_events[-1]

    conn.messages.clear()
    hass.states.async_set(f"sensor.{coord.device_slug}_system_rpc_outbox", "frame_1")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert [m for m in conn.messages if m["event"].get("type") == "state"] == []

    hass.states.async_set(f"media_player.{coord.device_slug}_music", "playing")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    state_events = [m["event"] for m in conn.messages if m["event"].get("type") == "state"]
    assert state_events
    assert "system_wallpapers" not in state_events[-1]
    assert "wallpapers" not in state_events[-1]

    # remove_device: missing subentry -> not_found (system_commands 1538-1544)
    await call_ws(
        hass,
        conn,
        21,
        "latter/system/command",
        command="remove_device",
        payload={"subentry_id": "missing_sub"},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    # remove_device matching WS selected subentry_id -> system_commands 1545-1549 + commands.py 545
    res_rm = await call_ws(
        hass,
        conn,
        22,
        "latter/system/command",
        command="remove_device",
        subentry_id="sub_tag",
        payload={"subentry_id": "sub_tag"},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert res_rm and res_rm["result"]["removed"] is True
    assert res_rm["result"]["removed_subentry_id"] == "sub_tag"

    # Trigger Area registry mutation after reload so _sync_subscribed_coordinators prunes old coordinator handles (290-293)
    tmp_area = ensure_area(hass, "Temp Zone", area_id="temp_zone")
    ar.async_get(hass).async_delete(tmp_area.id)
    await hass.async_block_till_done()

    conn.subscriptions.pop(10)()
    conn_missing.subscriptions.pop(11)()
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_system_commands_groups_batch_pin_doorbell_and_announcements(
    hass: Any,
    setup_latter_hub: Any,
    make_esphome_device: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise Device Group errors, batch setting copy/targets/modes, PIN errors, doorbell test, and announcements."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    # Adopt a stationary Wall Panel so we have both roaming and stationary Devices
    wall_dev, _wall_mac = make_esphome_device(
        hass,
        slug="wall_panel",
        mac="aa:bb:cc:dd:ee:08",
        name="Wall Panel",
        area_id="kitchen",
        stationary=1,
        w=480,
        h=480,
        shape="square",
    )
    conn = make_ws_connection(hass)
    msg_id = 0

    async def _sys(command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        res_msg = await call_ws(
            hass,
            conn,
            msg_id,
            "latter/system/command",
            command=command,
            payload=payload or {},
            studio_rev=STUDIO_REV,
        )
        assert res_msg is not None
        return res_msg

    res_adopt = await _sys(
        "add_latter_device",
        {"esphome_device_id": wall_dev.id, "device_group": "auto"},
    )
    assert res_adopt and res_adopt["success"] is True
    coord = entry.runtime_data.coordinators["sub_pocket"]
    wall_coord = next(
        c for c in iter_coordinators(hass) if c.device_slug == "wall_panel"
    )
    assert coord.is_roaming_device is True
    assert wall_coord.is_roaming_device is False

    # 1) create_device_group error paths (184, 197, 208, 215)
    for bad_grp, expected_code in (
        ({"name": ""}, "invalid_format"),
        ({"name": "Online"}, "invalid_format"),
        ({"name": "Alpha", "source_subentry_id": "missing_sub"}, "not_found"),
        ({"name": "Alpha", "source_subentry_id": "sub_tag"}, "not_found"),
    ):
        await _sys("create_device_group", bad_grp)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    res_g = await _sys("create_device_group", {"name": "Studio Group"})
    assert res_g and res_g["success"] is True
    await _sys("create_device_group", {"name": "Studio Group"})
    assert conn.errors[-1][1] == "already_configured"
    conn.errors.clear()

    # 2) update_group_baseline error & helper paths (304, 310, 317, 335, 344, 369, 408)
    for bad_upd, expected_code in (
        ({"group_id": "missing_group", "config": {"alert_volume": 50}}, "not_found"),
        ({"group_id": "handhelds", "source_subentry_id": "sub_tag"}, "not_found"),
        (
            {
                "group_id": "handhelds",
                "source_subentry_id": coord.subentry_id,
                "copy_keys": ["not_a_real_key"],
            },
            "invalid_format",
        ),
        ({"group_id": "handhelds", "config": {"unsupported_key": 1}}, "invalid_format"),
        ({"group_id": "handhelds"}, "invalid_format"),
    ):
        await _sys("update_group_baseline", bad_upd)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    with pytest.raises(StudioCommandError) as exc_ck_type:
        _apply_group_scope_and_seed(
            hass,
            {"id": "studio_group", "device_config": {}},
            {"source_subentry_id": coord.subentry_id, "copy_keys": "not_a_list"},
            [coord],
        )
    assert exc_ck_type.value.code == "invalid_format"

    with monkeypatch.context() as mp:
        mp.setattr(system_commands, "clean_device_settings", lambda *_a, **_kw: {})
        assert (
            _apply_group_config_updates(
                {"id": "studio_group", "device_config": {}},
                {"alert_volume": 60},
                {},
            )
            is False
        )

    # Valid copy_keys subset
    res_copy = await _sys(
        "update_group_baseline",
        {
            "group_id": "studio_group",
            "source_subentry_id": coord.subentry_id,
            "copy_keys": ["alert_volume"],
        },
    )
    assert res_copy and res_copy["success"] is True

    # 3) apply_batch_device_setting: source_subentry_id copy, target filters, unsupported key skip, wallpaper/screensaver mode inference (439-455, 463, 481, 485, 502, 513-514, 519-520, 525-526, 529-531)
    for bad_batch, expected_code in (
        ({"source_subentry_id": "sub_tag", "copy_keys": ["alert_volume"]}, "not_found"),
        ({"source_subentry_id": coord.subentry_id, "copy_keys": []}, "invalid_format"),
        ({"target": "all", "config": {"bogus_setting": 1}}, "invalid_format"),
    ):
        await _sys("apply_batch_device_setting", bad_batch)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    # Seed wallpaper + alert_volume on coord, then copy via source_subentry_id to stationary wall_coord
    msg_id += 1
    await call_ws(
        hass,
        conn,
        msg_id,
        "latter/device/command",
        command="set_device_photo_pool",
        subentry_id=coord.subentry_id,
        payload={
            "target": "wallpaper",
            "mode": "single",
            "source_id": "preset:ocean_waves",
        },
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    msg_id += 1
    await call_ws(
        hass,
        conn,
        msg_id,
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"alert_volume": 66}},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors

    res_src_batch = await _sys(
        "apply_batch_device_setting",
        {
            "target": "stationary",
            "source_subentry_id": coord.subentry_id,
            "copy_keys": ["alert_volume", "wallpaper_source"],
        },
    )
    assert res_src_batch and res_src_batch["success"] is True
    assert wall_coord.get_device_pref("alert_volume") == 66
    assert wall_coord.wallpaper_mode == "single"
    assert wall_coord.current_wallpaper == "preset:ocean_waves"

    # target="online" (481) and target="stationary" with roaming-only key sync_device_area hitting line 502
    res_online = await _sys(
        "apply_batch_device_setting",
        {"target": "online", "config": {"alert_volume": 55}},
    )
    assert res_online and res_online["success"] is True
    res_skip = await _sys(
        "apply_batch_device_setting",
        {"target": "stationary", "config": {"sync_device_area": True}},
    )
    assert res_skip and res_skip["success"] is True

    # Batch wallpaper_source="" -> off (513-514, 529-531), wallpaper_collection -> collection (519-520), screensaver_photo_collection -> collection (525-526)
    res_wp_off = await _sys(
        "apply_batch_device_setting",
        {"target": "all", "config": {"wallpaper_source": ""}},
    )
    assert res_wp_off and res_wp_off["success"] is True
    assert coord.wallpaper_mode == "off"

    res_wp_col = await _sys(
        "apply_batch_device_setting",
        {
            "target": "all",
            "config": {
                "wallpaper_collection": VIRTUAL_COLLECTION_ALL,
                "screensaver_photo_collection": VIRTUAL_COLLECTION_ALL,
            },
        },
    )
    assert res_wp_col and res_wp_col["success"] is True
    assert coord.wallpaper_mode == "collection"
    assert coord.screensaver_photo_mode == "collection"

    # 4) set_security_pin errors (584, 596-597, 619-620)
    for bad_pin, expected_code in (
        ({"subentry_id": "missing_sub", "pin": "1234"}, "not_found"),
        ({"subentry_id": coord.subentry_id, "pin": "12"}, "invalid_format"),
        ({"pin": "abcd"}, "invalid_format"),
    ):
        await _sys("set_security_pin", bad_pin)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    # 5) test_doorbell_speaker (637-641, 651-671) & send_announcement (681-695)
    await _sys(
        "test_doorbell_speaker",
        {"subentry_id": "missing_sub", "camera_entity": "camera.front", "message": "Hi"},
    )
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await _sys(
        "test_doorbell_speaker",
        {"subentry_id": coord.subentry_id, "camera_entity": "camera.front", "message": "Hi"},
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    await _sys(
        "send_announcement",
        {
            "mode": "notify",
            "target_device": "all",
            "title": "Door",
            "message": "Visitor",
            "include_camera": True,
        },
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    hass.states.async_set("camera.front_door", "idle", {"friendly_name": "Front Door"})
    res_cams = await _sys(
        "save_system_config",
        {
            "config": {
                "camera_entities": ["camera.front_door"],
                "broadcast_speakers": [f"media_player.{coord.device_slug}_music"],
            }
        },
    )
    assert res_cams["success"] is True

    await _sys(
        "test_doorbell_speaker",
        {
            "subentry_id": coord.subentry_id,
            "camera_entity": "camera.not_configured",
            "message": "Hi",
        },
    )
    assert conn.errors[-1][1] == "not_allowed"
    conn.errors.clear()

    await _sys(
        "test_doorbell_speaker",
        {
            "subentry_id": coord.subentry_id,
            "camera_entity": "camera.front_door",
            "message": "",
        },
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    intercom_mock = AsyncMock()
    with monkeypatch.context() as mp:
        mp.setattr(system_commands, "async_execute_doorbell_intercom", intercom_mock)
        res_db = await _sys(
            "test_doorbell_speaker",
            {
                "subentry_id": coord.subentry_id,
                "camera_entity": "camera.front_door",
                "message": "Please leave it by the gate",
            },
        )
    assert res_db and res_db["success"] is True
    intercom_mock.assert_awaited_once_with(
        hass,
        coord,
        action="talk_message",
        camera_entity="camera.front_door",
        message="Please leave it by the gate",
    )

    calls = get_service_calls(hass)
    calls.clear()
    res_ann = await _sys(
        "send_announcement",
        {
            "mode": "notify",
            "target_device": "all",
            "title": "Front Entry",
            "message": "Package arrived",
            "priority": "warning",
            "include_camera": True,
        },
    )
    assert res_ann and res_ann["success"] is True
    notify_calls = [c for c in calls if c.domain == DOMAIN and c.service == "notify"]
    assert len(notify_calls) == 1
    assert notify_calls[0].data["camera_entity"] == "camera.front_door"

    res_bc = await _sys(
        "send_announcement",
        {
            "mode": "broadcast",
            "target_device": "all",
            "message": "Dinner is served",
        },
    )
    assert res_bc and res_bc["success"] is True
    assert any(
        c.domain == DOMAIN and c.service == "intercom_broadcast" for c in calls
    )

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_system_commands_photos_collections_pruning_and_media_errors(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise Photo Library CRUD errors, coordinator pool pruning branches, media errors, and camera preview guards."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    conn = make_ws_connection(hass)
    msg_id = 0

    async def _sys(command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        res_msg = await call_ws(
            hass,
            conn,
            msg_id,
            "latter/system/command",
            command=command,
            subentry_id=coord.subentry_id,
            payload=payload or {},
            studio_rev=STUDIO_REV,
        )
        assert res_msg is not None
        return res_msg

    async def _dev(command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        res_msg = await call_ws(
            hass,
            conn,
            msg_id,
            "latter/device/command",
            command=command,
            subentry_id=coord.subentry_id,
            payload=payload or {},
            studio_rev=STUDIO_REV,
        )
        assert res_msg is not None
        return res_msg

    # Empty deleted_ids early return
    await _prune_deleted_photos_from_coordinators(hass, set())

    # Collection CRUD validation & error branches (818, 821-822, 837, 844-846, 860, 863)
    await _sys("create_photo_collection", {"name": ""})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    res_a = await _sys("create_photo_collection", {"name": "Album A"})
    assert res_a and res_a["success"] is True
    col_a = res_a["result"]["collection"]["id"]

    res_b = await _sys("create_photo_collection", {"name": "Album B"})
    assert res_b and res_b["success"] is True
    col_b = res_b["result"]["collection"]["id"]

    await _sys("create_photo_collection", {"name": "Album A"})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    for bad_ren, expected_code in (
        ({"collection_id": "", "name": "New"}, "invalid_format"),
        ({"collection_id": col_a, "name": ""}, "invalid_format"),
        ({"collection_id": "col_unknown", "name": "New"}, "not_found"),
        ({"collection_id": col_a, "name": "Album B"}, "invalid_format"),
    ):
        await _sys("rename_photo_collection", bad_ren)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    for bad_del_col, expected_code in (
        ({"collection_id": ""}, "invalid_format"),
        ({"collection_id": "col_unknown"}, "not_found"),
    ):
        await _sys("delete_photo_collection", bad_del_col)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    # Upload 4 distinct photos into Album A
    uploaded_ids: list[str] = []
    for idx, rgb in enumerate(
        ((20, 40, 80), (40, 90, 120), (80, 130, 60), (140, 70, 50)), start=1
    ):
        jpg = make_jpeg_bytes(64, 64, rgb)
        rec = await hass.async_add_executor_job(
            lambda j=jpg, i=idx: save_uploaded_photo_bytes(
                hass, f"cov_photo_{i}.jpg", j, collection_id=col_a
            )
        )
        uploaded_ids.append(rec["id"])
    p1, p2, p3, p4 = uploaded_ids

    # Photo metadata, bulk, and delete validation errors (878, 883, 896-898, 904, 927, 932, 946-947, 965, 968)
    for bad_meta, expected_code in (
        ({"photo_id": ""}, "invalid_format"),
        ({"photo_id": p1}, "invalid_format"),
        ({"photo_id": "photo:unknown", "name": "Nope"}, "not_found"),
        ({"photo_id": "preset:ocean_waves", "name": "Nope"}, "invalid_format"),
    ):
        await _sys("update_photo_metadata", bad_meta)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    # Crop update triggers coordinator scan skipping BLE tag (line 904)
    res_crop = await _sys(
        "update_photo_metadata",
        {"photo_id": p1, "crop": {"x": 0.3, "y": 0.7, "zoom": 1.3}},
    )
    assert res_crop and res_crop["success"] is True

    for bad_bulk, expected_code in (
        ({"photo_ids": [], "delete": True}, "invalid_format"),
        ({"photo_ids": [p1]}, "invalid_format"),
        ({"photo_ids": [p1], "add_collection": "col_missing"}, "invalid_format"),
    ):
        await _sys("bulk_update_photos", bad_bulk)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    for bad_del_photo, expected_code in (
        ({"photo_id": ""}, "invalid_format"),
        ({"photo_id": "preset:ocean_waves"}, "not_found"),
    ):
        await _sys("delete_photo", bad_del_photo)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    # Pruning Scenario A: wallpaper mode=single -> delete_photo resets to off (710-714)
    assert (
        await _dev(
            "set_device_photo_pool",
            {"target": "wallpaper", "mode": "single", "source_id": p1},
        )
    )["success"] is True
    assert (await _sys("delete_photo", {"photo_id": p1}))["success"] is True
    assert coord.wallpaper_mode == "off"
    assert coord.configured_wallpaper_source == ""

    # Pruning Scenario B: wallpaper mode=custom [p2] -> bulk delete prunes favorites & resets to off (707-708, 716-720, 949)
    assert (
        await _dev(
            "set_device_photo_pool",
            {
                "target": "wallpaper",
                "mode": "custom",
                "photo_ids": [p2],
                "cycle_minutes": 5,
            },
        )
    )["success"] is True
    assert (
        await _sys("bulk_update_photos", {"photo_ids": [p2], "delete": True})
    )["success"] is True
    assert coord.wallpaper_mode == "off"
    assert coord.wallpaper_favorites == []
    assert coord.wallpaper_cycle_minutes == 0

    # Pruning Scenario C: wallpaper mode=collection -> bulk add rebinds collection coordinators (804-806), delete active current_wallpaper clears it (722-723)
    assert (
        await _dev(
            "set_device_photo_pool",
            {"target": "wallpaper", "mode": "collection", "collection_id": col_a},
        )
    )["success"] is True
    assert (
        await _sys(
            "bulk_update_photos",
            {"photo_ids": ["preset:ocean_waves"], "add_collection": col_a},
        )
    )["success"] is True
    coord.current_wallpaper = p3
    assert (await _sys("delete_photo", {"photo_id": p3}))["success"] is True
    assert coord.current_wallpaper != p3

    # Pruning Scenario D: screensaver mode=single [p4] -> delete resets screensaver to off (733-736)
    assert (
        await _dev(
            "set_device_photo_pool",
            {"target": "screensaver", "mode": "single", "source_id": p4},
        )
    )["success"] is True
    assert (await _sys("delete_photo", {"photo_id": p4}))["success"] is True
    assert coord.screensaver_photo_mode == "off"
    assert coord.current_screensaver_photo == ""

    # Pruning Scenario E: screensaver mode=collection [col_a] -> delete collection skips BLE tag (769) & resets screensaver (786-789)
    assert (
        await _dev(
            "set_device_photo_pool",
            {"target": "screensaver", "mode": "collection", "collection_id": col_a},
        )
    )["success"] is True
    assert (await _sys("delete_photo_collection", {"collection_id": col_a}))["success"] is True
    assert coord.screensaver_photo_mode == "off"
    assert coord.device_data[CONF_SCREENSAVER_PHOTO_COLLECTION] == ""

    # Media browse/import & camera preview error paths (990-991, 1016, 1018, 1030-1031, 1045-1046, 1067, 1071)
    def _seed_media() -> Path:
        m_dir = Path(hass.config.config_dir) / "ws_media_cov"
        m_dir.mkdir(parents=True, exist_ok=True)
        (m_dir / "sample.jpg").write_bytes(make_jpeg_bytes(48, 48, (99, 88, 77)))
        return m_dir

    media_dir = await hass.async_add_executor_job(_seed_media)
    hass.config.media_dirs = {"local": str(media_dir)}

    await _sys("browse_media_folder", {"root": "no_such_root", "subpath": ""})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    for bad_import in (
        {"root": "", "paths": ["sample.jpg"]},
        {"root": "local", "paths": []},
        {"root": "local", "paths": ["sample.jpg"], "new_collection_name": "Album B"},
        {"root": "local", "paths": ["sample.jpg"], "collection_id": "col_missing"},
    ):
        await _sys("import_media_photos", bad_import)
        assert conn.errors[-1][1] == "invalid_format"
        conn.errors.clear()

    await _sys("mint_camera_preview_url", {"camera_entity": "light.not_a_camera"})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    await _sys("mint_camera_preview_url", {"camera_entity": "camera.not_registered"})
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    assert (await _sys("delete_photo_collection", {"collection_id": col_b}))["success"] is True
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_system_commands_presence_illuminance_updates_and_onboarding(
    hass: Any,
    setup_latter_hub: Any,
    make_esphome_device: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise scanner offsets, fusion/illuminance calibration, BLE signatures, firmware checks, and device/BLE onboarding."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    conn = make_ws_connection(hass)
    msg_id = 0

    async def _sys(
        command: str,
        payload: dict[str, Any] | None = None,
        *,
        subentry_id: str | None = None,
    ) -> dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        extra_kw: dict[str, Any] = {}
        if subentry_id is not None:
            extra_kw["subentry_id"] = subentry_id
        res_msg = await call_ws(
            hass,
            conn,
            msg_id,
            "latter/system/command",
            command=command,
            payload=payload or {},
            studio_rev=STUDIO_REV,
            **extra_kw,
        )
        assert res_msg is not None
        return res_msg

    # 1) set_ble_scanner_offset validation & malformed existing dict cleanup (1101, 1104, 1107-1108, 1110, 1120, 1124-1125)
    await _sys("set_ble_scanner_offset", {"scanner_source": "", "offset_db": 1.0})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    await _sys("set_ble_scanner_offset", {"scanner_source": "AA:BB", "offset_db": True})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    for bad_off in (True, "not_num", float("inf")):
        with pytest.raises(StudioCommandError) as exc_off:
            await _cmd_set_ble_scanner_offset(
                hass, None, {"scanner_source": "AA:BB", "offset_db": bad_off}, {}, {}
            )
        assert exc_off.value.code == "invalid_format"

    get_global_config(hass)[CONF_BLE_SCANNER_OFFSETS] = {
        "": 2.0,
        "AA:BB:CC:00:00:99": "bad_float",
        "AA:BB:CC:00:00:11": 3.0,
    }
    res_off = await _sys(
        "set_ble_scanner_offset",
        {"scanner_source": "AA:BB:CC:00:00:22", "offset_db": -2.5},
    )
    assert res_off and res_off["success"] is True
    saved_offsets = get_global_config(hass)[CONF_BLE_SCANNER_OFFSETS]
    assert saved_offsets == {"AA:BB:CC:00:00:11": 3.0, "AA:BB:CC:00:00:22": -2.5}

    # 2) set_area_fusion & set_area_illuminance unknown Area (1143, 1229)
    await _sys("set_area_fusion", {"area_id": "no_such_area", "mode": "weighted"})
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await _sys("set_area_illuminance", {"area_id": "no_such_area", "entity_id": "auto"})
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    # 3) calibrate_area_illuminance error & multi-Area calibration branches (1252, 1255, 1262-1263, 1266-1270, 1274, 1298-1300, 1314, 1333-1334, 1351)
    assert "recorder" not in hass.config.components
    await _sys("calibrate_area_illuminance", {"area_id": "living_room"})
    assert conn.errors[-1][1] == "not_supported"
    conn.errors.clear()

    hass.config.components.add("recorder")
    try:
        await _sys("calibrate_area_illuminance", {"area_id": "no_such_area"})
        assert conn.errors[-1][1] == "not_found"
        conn.errors.clear()

        await _sys("calibrate_area_illuminance", {"area_id": "bedroom"})
        assert conn.errors[-1][1] == "invalid_format"
        conn.errors.clear()

        await _sys("calibrate_area_illuminance", {})
        assert conn.errors[-1][1] == "invalid_format"
        conn.errors.clear()

        lr_lux = "sensor.living_area_lux"
        kit_lux = "sensor.kitchen_area_lux"
        register_entity(hass, lr_lux, platform="esphome", area_id="living_room")
        register_entity(hass, kit_lux, platform="esphome", area_id="kitchen")
        hass.states.async_set(
            lr_lux,
            "12.0",
            {"device_class": "illuminance", "unit_of_measurement": "lx"},
        )
        hass.states.async_set(
            kit_lux,
            "25.0",
            {"device_class": "illuminance", "unit_of_measurement": "lx"},
        )
        await hass.async_block_till_done()

        # Disable living_room sensor -> skipped on all-Area scan (1262-1263); recorder unavailable -> failed (1298-1303)
        res_dis = await _sys(
            "set_area_illuminance",
            {"area_id": "living_room", "entity_id": "disabled"},
        )
        assert res_dis and res_dis["success"] is True

        await _sys("calibrate_area_illuminance", {})
        assert conn.errors[-1][1] == "failed"
        conn.errors.clear()

        # Empty stats -> skipped (1333-1334) and not calibrated (1351)
        with monkeypatch.context() as mp:
            mp.setattr(
                system_commands,
                "_async_fetch_illuminance_stats",
                AsyncMock(return_value={kit_lux: []}),
            )
            await _sys("calibrate_area_illuminance", {})
        assert conn.errors[-1][1] == "invalid_format"
        conn.errors.clear()

        # Mixed: kitchen calibrates while living_room (re-enabled) has empty stats -> both calibrated and skipped populated
        res_en = await _sys(
            "set_area_illuminance",
            {"area_id": "living_room", "entity_id": "auto"},
        )
        assert res_en and res_en["success"] is True
        kit_stats = [
            {"min": 1.0, "mean": 2.0},
            {"min": 1.0, "mean": 15.0},
            {"min": 2.0, "mean": 30.0},
            {"min": 5.0, "mean": 60.0},
            {"min": 10.0, "mean": 90.0},
        ]
        with monkeypatch.context() as mp:
            mp.setattr(
                system_commands,
                "_async_fetch_illuminance_stats",
                AsyncMock(return_value={kit_lux: kit_stats, lr_lux: []}),
            )
            res_cal = await _sys("calibrate_area_illuminance", {})
        assert res_cal and res_cal["success"] is True
        assert len(res_cal["result"]["calibrated"]) == 1
        assert res_cal["result"]["calibrated"][0]["area_id"] == "kitchen"
        assert "Living Room" in res_cal["result"]["skipped"]
        assert "kitchen" in get_global_config(hass)[CONF_AREA_ILLUMINANCE_CONFIG]
    finally:
        if "recorder" in hass.config.components:
            hass.config.components.remove("recorder")

    # 4) capture_ble_area_signature & clear_ble_area_signature guards (1375, 1377, 1379, 1384, 1387, 1394, 1423)
    for bad_sig, expected_code in (
        ({"area_id": "", "survey_subentry_id": coord.subentry_id}, "invalid_format"),
        ({"area_id": "no_area", "survey_subentry_id": coord.subentry_id}, "not_found"),
        ({"area_id": "living_room", "survey_subentry_id": ""}, "invalid_format"),
        ({"area_id": "living_room", "survey_subentry_id": "missing_sub"}, "not_found"),
        ({"area_id": "living_room", "survey_subentry_id": "sub_tag"}, "not_ready"),
    ):
        await _sys("capture_ble_area_signature", bad_sig)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    # Disable BLE tracking on coord so coord.ble_tracker is None -> not_supported (1387)
    msg_id += 1
    await call_ws(
        hass,
        conn,
        msg_id,
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"native_ble_tracking": False}},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert coord.ble_tracker is None
    await _sys(
        "capture_ble_area_signature",
        {"area_id": "living_room", "survey_subentry_id": coord.subentry_id},
    )
    assert conn.errors[-1][1] == "not_supported"
    conn.errors.clear()

    await _sys("clear_ble_area_signature", {"area_id": ""})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    # 5) check_system_updates with update entities + TimeoutError (1448-1456)
    upd_eid = f"update.{coord.device_slug}_project_firmware"
    register_entity(
        hass,
        upd_eid,
        platform="esphome",
        config_entry_id=f"esp_entry_{coord.device_slug}",
        device_id=coord.esphome_device_id,
        original_name="Project Firmware",
    )
    hass.states.async_set(upd_eid, "on")
    upd_calls = mock_service(hass, "homeassistant", "update_entity")

    res_upd = await _sys("check_system_updates", {})
    assert res_upd and res_upd["success"] is True
    assert res_upd["result"]["update_check"] == {"checked": 1, "available": 1}
    assert len(upd_calls) == 1

    def _raise_timeout(_call: Any) -> None:
        raise TimeoutError

    mock_service(hass, "homeassistant", "update_entity", handler=_raise_timeout)
    await _sys("check_system_updates", {})
    assert conn.errors[-1][1] == "timeout"
    conn.errors.clear()

    # 6) ignore/unignore_discovered_device validation (1487, 1490, 1516) & add_latter_device (1608-1613, 1618-1625)
    await _sys("ignore_discovered_device", {"esphome_device_id": ""})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    await _sys("ignore_discovered_device", {"esphome_device_id": "unknown_dev"})
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await _sys("unignore_discovered_device", {"esphome_device_id": ""})
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    new_dev, _new_mac = make_esphome_device(
        hass,
        slug="hall_panel",
        mac="aa:bb:cc:dd:ee:07",
        name="Hall Panel",
        area_id="kitchen",
        stationary=1,
        w=480,
        h=480,
        shape="square",
    )
    assert (
        await _sys("ignore_discovered_device", {"esphome_device_id": new_dev.id})
    )["success"] is True
    assert new_dev.id in get_global_config(hass)[CONF_IGNORED_DISCOVERED_DEVICES]

    with monkeypatch.context() as mp:
        mp.setattr(
            hass.config_entries.subentries,
            "async_init",
            AsyncMock(return_value={"type": "abort", "reason": "already_configured"}),
        )
        await _sys("add_latter_device", {"esphome_device_id": new_dev.id})
    assert conn.errors[-1][1] == "already_configured"
    conn.errors.clear()

    res_adopt = await _sys("add_latter_device", {"esphome_device_id": new_dev.id})
    assert res_adopt and res_adopt["success"] is True
    assert new_dev.id not in get_global_config(hass)[CONF_IGNORED_DISCOVERED_DEVICES]
    assert res_adopt["result"]["adopted_esphome_device_id"] == new_dev.id

    # 7) add_ble_device validation, duplicate checks, non-create_entry abort, and happy path (1660-1671, 1690-1721)
    for bad_ble, expected_code in (
        (
            {"name": "Tag", "target_address": "22:33:44:55:66:77", "ble_category": "bogus"},
            "invalid_format",
        ),
        ({"name": "", "target_address": "22:33:44:55:66:77"}, "invalid_format"),
        ({"name": "Tag", "target_address": ""}, "invalid_format"),
        ({"name": "Keys Tag", "target_address": "22:33:44:55:66:77"}, "already_configured"),
        ({"name": "Dup Mac", "target_address": "11-22-33-44-55-66"}, "already_configured"),
    ):
        await _sys("add_ble_device", bad_ble)
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    with monkeypatch.context() as mp:
        mp.setattr(
            hass.config_entries.subentries,
            "async_init",
            AsyncMock(
                return_value={"type": "form", "errors": {"base": "ble_tag_incomplete"}}
            ),
        )
        await _sys(
            "add_ble_device",
            {"name": "Backpack Tag", "target_address": "22:33:44:55:66:77"},
        )
    assert conn.errors[-1][1] == "ble_tag_incomplete"
    conn.errors.clear()

    # Happy path: ensure subentry reload completes so adopted_ble coordinator is found (lines 1717-1721 + commands.py 546-547)
    orig_sub_init = hass.config_entries.subentries.async_init

    async def _sync_sub_init(*args: Any, **kwargs: Any) -> Any:
        flow_out = await orig_sub_init(*args, **kwargs)
        await hass.async_block_till_done()
        return flow_out

    with monkeypatch.context() as mp:
        mp.setattr(hass.config_entries.subentries, "async_init", _sync_sub_init)
        res_ble = await _sys(
            "add_ble_device",
            {
                "name": "Backpack Tag",
                "target_address": "22:33:44:55:66:77",
                "ble_category": "ble_tag",
                "assigned_person": "person.alex",
            },
        )
    assert res_ble and res_ble["success"] is True
    assert res_ble["result"]["adopted_subentry_id"]
    assert any(c.device_slug == "backpack_tag" for c in iter_coordinators(hass))

    assert await hass.config_entries.async_unload(entry.entry_id) is True
