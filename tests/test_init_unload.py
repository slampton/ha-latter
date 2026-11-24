"""Integration tests for setup, unload, device removal guards, platforms, repairs, and backup hooks."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import EntityCategory
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.latter import (
    async_remove_config_entry_device,
    async_setup,
)
from custom_components.latter.backup import async_post_backup, async_pre_backup
from custom_components.latter.cameras.stream_hub import _CameraIngest, get_camera_stream_hub
from custom_components.latter.const import (
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    DOMAIN,
    SUBENTRY_DEVICE,
)
from custom_components.latter.hub_registry import get_domain_data
from custom_components.latter.media.state_payload import build_active_media_payload
from custom_components.latter.repairs import (
    LinkMaPlayerRepairFlow,
    async_audit_coordinator_health,
    async_create_fix_flow,
)
from custom_components.latter.sensor import (
    LatterAreaOccupantsSensor,
    format_bounded_occupant_names,
)
from custom_components.latter.studio.payload import build_studio_state_payload
from tests.helpers.ha_setup import (
    add_mock_entry,
    ensure_area,
    ensure_floor,
    flush_debouncers,
    get_extra_js_urls,
    get_platform_entities,
    get_registered_panels,
    get_static_paths,
    make_subentry_dict,
    prepare_latter_dependencies,
    register_entity,
)


def _panel_attr(panel: Any, attr: str) -> Any:
    if isinstance(panel, dict):
        return panel.get(attr)
    return getattr(panel, attr, None)


async def test_setup_platforms_occupants_cap_and_clean_unload(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise full hub + device + ble_tag setup, dynamic Area entities, <255-char cap, and teardown."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    assert coord is not None
    assert "sub_tag" in sys_obj.coordinators
    assert get_domain_data(hass).registered_panel_url is not None
    panels = get_registered_panels(hass)
    assert "latter" in panels
    assert _panel_attr(panels["latter"], "config_panel_domain") == DOMAIN
    static_paths = get_static_paths(hass)
    assert static_paths
    assert all(sp.cache_headers is True for sp in static_paths)
    assert len(get_extra_js_urls(hass)) == 1

    # Verify all entity platforms populated states and enforce _attr_has_entity_name = True
    assert coord.get_device_info()["manufacturer"] == "Latter"
    for p_name in (
        "sensor",
        "binary_sensor",
        "device_tracker",
        "select",
        "number",
        "button",
        "switch",
        "light",
    ):
        entities = get_platform_entities(hass, p_name)
        assert entities, f"Expected entities for {p_name}"
        for ent in entities:
            assert ent.has_entity_name is True
            assert ent.translation_key
            _ = ent.device_info
            ent.async_write_ha_state()

    # BLE distance sensors are disabled by default & diagnostic; screen light and config controls use CONFIG
    ent_reg = er.async_get(hass)
    ble_dist_entry = ent_reg.async_get("sensor.pocket_assistant_ble_distance")
    assert ble_dist_entry is not None
    assert ble_dist_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert ble_dist_entry.entity_category == EntityCategory.DIAGNOSTIC
    for cfg_eid in (
        "light.pocket_assistant_screen",
        "switch.pocket_assistant_bedtime_mode",
        "switch.pocket_assistant_do_not_disturb",
        "switch.pocket_assistant_screensaver",
        "select.pocket_assistant_device_group",
        "select.pocket_assistant_glass_style",
        "select.pocket_assistant_wake_word_mode",
        "number.pocket_assistant_alert_volume",
        "button.pocket_assistant_find_my_device",
    ):
        cfg_ent = ent_reg.async_get(cfg_eid)
        assert cfg_ent is not None, f"Missing expected entity {cfg_eid}"
        assert cfg_ent.entity_category == EntityCategory.CONFIG, cfg_eid
    dismiss_ent = ent_reg.async_get("button.pocket_assistant_dismiss_alert")
    assert dismiss_ent is not None
    assert dismiss_ent.entity_category is None

    # Dynamic Area Registry create / update / remove syncs both sensor & binary_sensor
    area_reg = ar.async_get(hass)
    ensure_floor(hass, "Floor 1", floor_id="floor_1")
    ensure_area(hass, "Office", area_id="office", floor_id="floor_1")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.latter_system_office_occupants") is not None or any(
        e.entity_id == "sensor.latter_system_office_occupants"
        for e in get_platform_entities(hass, "sensor")
    )
    assert hass.states.get("binary_sensor.latter_system_office_occupancy") is not None or any(
        e.entity_id == "binary_sensor.latter_system_office_occupancy"
        for e in get_platform_entities(hass, "binary_sensor")
    )
    area_reg.async_update("office", name="Home Office")
    area_reg.async_delete("office")
    await hass.async_block_till_done()
    assert ent_reg.async_get("sensor.latter_system_office_occupants") is None
    assert ent_reg.async_get("binary_sensor.latter_system_office_occupancy") is None

    # Verify <255-char native_value cap on LatterAreaOccupantsSensor while full list stays in occupant_names
    long_names = [f"Occupant Person With Very Long Display Name {idx:02d}" for idx in range(30)]
    bounded = format_bounded_occupant_names(long_names)
    assert len(bounded) < 255
    assert "(+" in bounded
    single_huge = format_bounded_occupant_names(["X" * 400])
    assert len(single_huge) < 255

    occ_sensor = LatterAreaOccupantsSensor(hass, "living_room", "Living Room")
    occ_sensor._cached_occ = {
        "is_occupied": True,
        "occupant_names": long_names,
        "persons": ["person.alex"],
        "occupied_by": ["pocket_assistant"],
    }
    assert len(occ_sensor.native_value) < 255
    assert occ_sensor.extra_state_attributes["occupant_names"] == long_names
    assert occ_sensor.translation_key == "area_occupants"

    # Backup hooks flush cleanly
    await async_pre_backup(hass)
    await async_post_backup(hass)

    # Seed a live camera ingest background task and verify unload cancels it cleanly
    cam_hub = get_camera_stream_hub(hass)
    dummy_task = hass.async_create_task(asyncio.sleep(60), name="live_cam_dummy")
    cam_hub._ingests["camera.front_door"] = _CameraIngest(
        entity_id="camera.front_door", _task=dummy_task
    )

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    await hass.async_block_till_done()
    assert dummy_task.cancelled() or dummy_task.done()
    assert get_domain_data(hass).registered_panel_url is None
    assert "latter" not in get_registered_panels(hass)
    # Keep latter-icons.js registered across config-entry reloads; remove only when the entry is deleted.
    assert len(get_extra_js_urls(hass)) == 1

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(get_extra_js_urls(hass)) == 0


async def test_device_removal_guards_and_update_listener(
    hass: Any, setup_latter_hub: Any, monkeypatch: Any
) -> None:
    """Verify active subentries & System service device cannot be removed, while orphans can."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)

    reloaded_entries: list[str] = []
    orig_schedule_reload = hass.config_entries.async_schedule_reload

    def _spy_reload(entry_id: str) -> None:
        reloaded_entries.append(entry_id)
        orig_schedule_reload(entry_id)

    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", _spy_reload)

    sys_dev = next(
        (
            d
            for d in dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
            if (DOMAIN, "system") in d.identifiers
        ),
        None,
    )
    assert sys_dev is not None
    assert await async_remove_config_entry_device(hass, entry, sys_dev) is False

    active_latter_dev = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=coord.get_device_info()["identifiers"],
        name="Pocket Assistant",
    )
    assert await async_remove_config_entry_device(hass, entry, active_latter_dev) is False

    orphan_dev = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "ff:ff:ff:ff:ff:99")},
        name="Retired Display",
    )
    assert await async_remove_config_entry_device(hass, entry, orphan_dev) is True

    # In-place option update via _async_update_listener
    ensure_area(hass, "Kitchen", area_id="kitchen")
    sub = entry.subentries["sub_pocket"]
    new_data = dict(sub.data)
    new_data[CONF_DEFAULT_AREA] = "kitchen"
    hass.config_entries.async_update_subentry(entry, sub, data=new_data)
    hass.config_entries.async_update_entry(entry, options={"updated": True})
    await hass.async_block_till_done()
    assert coord.get_opt(CONF_DEFAULT_AREA) == "kitchen"

    # Structural change (slug change) schedules reload
    structural = dict(new_data)
    structural[CONF_DEVICE_SLUG] = "renamed_pocket"
    hass.config_entries.async_update_subentry(entry, entry.subentries["sub_pocket"], data=structural)
    await hass.async_block_till_done()
    assert entry.entry_id in reloaded_entries

    # Removing a subentry triggers reload and deletes its Repair issues
    reloaded_entries.clear()
    hass.config_entries.async_remove_subentry(entry, "sub_pocket")
    await hass.async_block_till_done()
    assert entry.entry_id in reloaded_entries
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_repairs_audit_and_fix_flow(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise health repair audits and LinkMaPlayerRepairFlow / ConfirmRepairFlow."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        extra_device_data={"default_speaker": "media_player.missing_ghost_speaker"},
    )
    warnings = async_audit_coordinator_health(hass, coord)
    assert any(w["code"] == "missing_entity" for w in warnings)

    # Register a Music Assistant player entity and run LinkMaPlayerRepairFlow
    ma_entry = add_mock_entry(
        hass, entry_id="ma_entry_1", domain="music_assistant", title="Music Assistant"
    )
    register_entity(
        hass,
        "media_player.ma_pocket",
        platform="music_assistant",
        config_entry=ma_entry,
        original_name="MA Pocket",
    )
    hass.states.async_set("media_player.ma_pocket", "idle", {"friendly_name": "MA Pocket"})

    flow = await async_create_fix_flow(hass, "link_ma_player_sub_pocket", None)
    assert isinstance(flow, LinkMaPlayerRepairFlow)
    flow.hass = hass
    form_res = await flow.async_step_init()
    assert form_res["type"] == "form"

    bad_res = await flow.async_step_pick({"ma_player_entity": "media_player.not_ma"})
    assert bad_res["errors"]["ma_player_entity"] == "invalid_ma_player"

    ok_res = await flow.async_step_pick({"ma_player_entity": "media_player.ma_pocket"})
    assert ok_res["type"] == "create_entry"

    # Generic confirm repair flow
    confirm = await async_create_fix_flow(hass, "ble_no_proxies", None)
    confirm.hass = hass
    confirm.handler = DOMAIN
    confirm.issue_id = "ble_no_proxies"
    assert (await confirm.async_step_init())["type"] == "form"
    assert (await confirm.async_step_confirm({}))["type"] == "create_entry"
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_discovery_scan_when_unconfigured(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify async_setup proposes discovery flow for unconfigured Latter ESPHome devices and aborts stale flows."""
    await prepare_latter_dependencies(hass)

    # Create a temporary ESPHome device to start a real discovery flow, then remove the device so it becomes stale
    stale_dev, _ = make_esphome_device(
        hass, slug="retired_panel", mac="ff:ff:ff:00:00:00", name="Retired Panel", stationary=1
    )
    stale_flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ESPHOME_DEVICE_ID: stale_dev.id},
    )
    stale_flow_id = stale_flow["flow_id"]
    dr.async_get(hass).async_remove_device(stale_dev.id)

    _dev, mac = make_esphome_device(
        hass, slug="desk_panel", mac="aa:bb:cc:11:22:33", name="Desk Panel", stationary=1
    )
    assert await async_setup(hass, {}) is True
    await hass.async_block_till_done()

    in_progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    active_ids = {f["flow_id"] for f in in_progress}
    assert stale_flow_id not in active_ids
    expected_uid = f"latter_{dr.format_mac(mac)}"
    assert any(f.get("context", {}).get("unique_id") == expected_uid for f in in_progress)


async def test_esphome_device_and_entity_rename_sync_and_heal(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Renaming a bound ESPHome device & its entities syncs title, subentry, child device, speaker & Studio payload."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord.device_title == "Pocket Assistant"
    assert coord.get_opt(CONF_DEFAULT_SPEAKER) == "media_player.pocket_assistant_music"

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    esp_dev_id = coord.esphome_device_id
    assert esp_dev_id is not None
    dev_info = coord.get_device_info()
    latter_dev_before = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=dev_info["identifiers"],
        name=dev_info["name"],
        via_device_id=esp_dev_id,
    )
    assert latter_dev_before.name == "Pocket Assistant"

    # 1. Rename the bound ESPHome device and its music / outbox entities live
    esp_ce = next(
        ce
        for ce in hass.config_entries.async_entries("esphome")
        if any(d.id == esp_dev_id for d in dr.async_entries_for_config_entry(dev_reg, ce.entry_id))
    )
    hass.config_entries.async_update_entry(
        esp_ce, data={**esp_ce.data, "device_name": "living-room-assistant"}
    )
    dev_reg.async_update_device(esp_dev_id, name="Living Room Assistant")

    hass.states.async_remove("media_player.pocket_assistant_music")
    ent_reg.async_update_entity(
        "media_player.pocket_assistant_music",
        new_entity_id="media_player.living_room_assistant_music",
    )
    ent_reg.async_update_entity(
        "sensor.pocket_assistant_system_rpc_outbox",
        new_entity_id="sensor.living_room_assistant_system_rpc_outbox",
    )
    hass.states.async_set(
        "media_player.living_room_assistant_music",
        "idle",
        {"friendly_name": "Living Room Assistant Music", "volume_level": 0.5},
    )
    await flush_debouncers(hass)

    # Subentry title, child Latter Device name, coordinator.device_title, Studio payload & Media speaker_name all match
    assert coord.device_title == "Living Room Assistant"
    assert entry.subentries[coord.subentry_id].title == "Living Room Assistant"
    latter_dev = coord._find_latter_device_entry()
    assert latter_dev is not None and latter_dev.name == "Living Room Assistant"

    payload = build_studio_state_payload(hass, coord)
    assert payload["title"] == "Living Room Assistant"
    assert payload["system_devices"][0]["title"] == "Living Room Assistant"
    assert payload["esphome"]["device"]["node_name"] == "living_room_assistant"

    # Default speaker, active_speaker, last_speaker & RPC outbox all migrated cleanly
    assert coord.get_opt(CONF_DEFAULT_SPEAKER) == "media_player.living_room_assistant_music"
    assert coord.active_speaker == "media_player.living_room_assistant_music"
    assert coord.rpc_receiver.tracked_entity_id == "sensor.living_room_assistant_system_rpc_outbox"
    _m_state, m_attrs = build_active_media_payload(coord)
    assert m_attrs["speaker_name"] == "Living Room Assistant"
    assert not any(
        w["code"] == "missing_entity" for w in async_audit_coordinator_health(hass, coord)
    )
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_startup_heals_preexisting_stale_renamed_local_speaker(
    hass: Any, make_esphome_device: Any
) -> None:
    """When a device was renamed before reload, startup heals stale built-in default/active/last speaker refs."""
    await prepare_latter_dependencies(hass)
    dev, mac = make_esphome_device(
        hass, slug="living_room_assistant", mac="aa:bb:cc:dd:ee:11", stationary=1
    )
    dev_reg = dr.async_get(hass)
    dev_reg.async_update_device(dev.id, name="Living Room Assistant")

    sub_dict = make_subentry_dict(
        {
            CONF_DEVICE_SLUG: "garage_assistant",
            CONF_ESPHOME_DEVICE_ID: dev.id,
            "mac": mac,
            CONF_DEFAULT_SPEAKER: "media_player.garage_assistant_music",
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Garage Assistant",
        unique_id=f"latter_{mac}",
        subentry_id="sub_renamed_lr",
    )
    entry = add_mock_entry(
        hass,
        entry_id="entry_renamed_lr",
        domain=DOMAIN,
        title="Latter",
        subentries_data=[sub_dict],
        unique_id=DOMAIN,
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    coord = entry.runtime_data.coordinators["sub_renamed_lr"]
    assert coord.device_title == "Living Room Assistant"
    assert entry.subentries["sub_renamed_lr"].title == "Living Room Assistant"
    assert coord.get_opt(CONF_DEFAULT_SPEAKER) == "media_player.living_room_assistant_music"
    assert coord.active_speaker == "media_player.living_room_assistant_music"
    assert coord.last_speaker == "media_player.living_room_assistant_music"
    assert not any(
        w["code"] == "missing_entity" for w in async_audit_coordinator_health(hass, coord)
    )
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_sidebar_icon_module_registered_early_and_persists_across_reload(
    hass: Any,
) -> None:
    """`latter-icons.js` registers at the start of `async_setup`, survives entry reload without churn, and unregisters on removal."""
    await prepare_latter_dependencies(hass)
    assert await async_setup_component(hass, DOMAIN, {}) is True
    extra_urls = get_extra_js_urls(hass)
    assert len(extra_urls) == 1
    icon_url = next(iter(extra_urls))
    assert "latter-icons.js?v=" in icon_url
    assert len(get_static_paths(hass)) == 1

    entry = add_mock_entry(
        hass, entry_id="entry_icon_reload", domain=DOMAIN, title="Latter", data={}, unique_id=DOMAIN
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()
    assert get_extra_js_urls(hass) == {icon_url}
    assert _panel_attr(get_registered_panels(hass)["latter"], "sidebar_icon") == "latter:logo"

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    await hass.async_block_till_done()
    assert "latter" not in get_registered_panels(hass)
    assert get_extra_js_urls(hass) == {icon_url}

    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()
    assert get_extra_js_urls(hass) == {icon_url}
    assert _panel_attr(get_registered_panels(hass)["latter"], "sidebar_icon") == "latter:logo"

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(get_extra_js_urls(hass)) == 0
