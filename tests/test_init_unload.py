"""Integration tests for setup, unload, device removal guards, platforms, repairs, and backup hooks."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from custom_components.latter import (
    async_remove_config_entry_device,
    async_remove_entry,
    async_setup,
    async_unload_entry,
)
from custom_components.latter.backup import async_post_backup, async_pre_backup
from custom_components.latter.const import CONF_DEFAULT_AREA, CONF_DEVICE_SLUG, DOMAIN
from custom_components.latter.http import _LiveCameraFeed, _LiveCameraFeeds
from custom_components.latter.repairs import (
    LinkMaPlayerRepairFlow,
    async_audit_coordinator_health,
    async_create_fix_flow,
)
from custom_components.latter.sensor import (
    LatterAreaOccupantsSensor,
    format_bounded_occupant_names,
)


async def test_setup_platforms_occupants_cap_and_clean_unload(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise full hub + device + ble_tag setup, dynamic Area entities, <255-char cap, and teardown."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    assert coord is not None
    assert "sub_tag" in sys_obj.coordinators
    assert "_studio_js_digest" in hass.data[DOMAIN]
    assert "latter" in hass._panels
    assert len(hass._extra_js_urls) == 1

    # Verify all entity platforms populated states and enforce _attr_has_entity_name = True
    for p_name in ("sensor", "binary_sensor", "device_tracker"):
        entities = hass.data["_test_entities"][p_name]
        assert entities, f"Expected entities for {p_name}"
        for ent in entities:
            assert ent.has_entity_name is True
            assert ent.translation_key
            _ = ent.device_info
            ent.async_write_ha_state()

    # Dynamic Area Registry create / update / remove syncs both sensor & binary_sensor
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    area_reg.async_create("Office", area_id="office", floor_id="floor_1")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.office_occupants") is not None or any(
        e.entity_id == "sensor.office_occupants" for e in hass.data["_test_entities"]["sensor"]
    )
    # Register in entity registry so remove exercises ent_reg.async_remove too
    ent_reg.async_register(
        er.RegistryEntry(entity_id="sensor.office_occupants", platform=DOMAIN)
    )
    ent_reg.async_register(
        er.RegistryEntry(entity_id="binary_sensor.office_ble_occupancy", platform=DOMAIN)
    )
    area_reg.async_update("office", name="Home Office")
    area_reg.async_delete("office")
    await hass.async_block_till_done()
    assert ent_reg.async_get("sensor.office_occupants") is None
    assert ent_reg.async_get("binary_sensor.office_ble_occupancy") is None

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
        "persons": ["person.sean"],
        "occupied_by": ["pocket_assistant"],
    }
    assert len(occ_sensor.native_value) < 255
    assert occ_sensor.extra_state_attributes["occupant_names"] == long_names
    assert occ_sensor.icon == "mdi:account-group"

    # Backup hooks flush cleanly
    await async_pre_backup(hass)
    await async_post_backup(hass)

    # Seed a live camera feed background task and verify unload cancels it cleanly
    live_feeds = _LiveCameraFeeds(hass)
    dummy_task = hass.async_create_task(asyncio.sleep(60), name="live_cam_dummy")
    live_feeds._feeds[("camera.front_door", 240, 240, False, 0)] = _LiveCameraFeed(task=dummy_task)

    assert await async_unload_entry(hass, entry) is True
    await hass.async_block_till_done()
    assert dummy_task.cancelled() or dummy_task.done()
    assert "_studio_js_digest" not in hass.data.get(DOMAIN, {})
    assert "latter" not in hass._panels
    assert len(hass._extra_js_urls) == 0

    await async_remove_entry(hass, entry)


async def test_device_removal_guards_and_update_listener(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify active subentries & System service device cannot be removed, while orphans can."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)

    sys_dev = dev_reg.async_get_device({(DOMAIN, "system")})
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
    hass.config_entries.async_update_entry(entry, options={"structural": True})
    await hass.async_block_till_done()
    assert entry.entry_id in hass.config_entries.reloaded_entries

    # Removing a subentry triggers reload and deletes its Repair issues
    hass.config_entries.reloaded_entries.clear()
    await hass.config_entries.async_remove_subentry(entry.entry_id, "sub_pocket")
    hass.config_entries.async_update_entry(entry, options={"removed": True})
    await hass.async_block_till_done()
    assert entry.entry_id in hass.config_entries.reloaded_entries


async def test_repairs_audit_and_fix_flow(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise health repair audits and LinkMaPlayerRepairFlow / ConfirmRepairFlow."""
    _entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        extra_device_data={"default_speaker": "media_player.missing_ghost_speaker"},
    )
    warnings = async_audit_coordinator_health(hass, coord)
    assert any(w["code"] == "missing_entity" for w in warnings)

    # Register a Music Assistant player entity and run LinkMaPlayerRepairFlow
    from homeassistant.config_entries import ConfigEntry

    ma_entry = hass.config_entries.add_entry(
        ConfigEntry(entry_id="ma_entry_1", domain="music_assistant", title="Music Assistant")
    )
    ent_reg = er.async_get(hass)
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.ma_pocket",
            platform="music_assistant",
            config_entry_id=ma_entry.entry_id,
            original_name="MA Pocket",
        )
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
    assert (await confirm.async_step_init())["type"] == "form"
    assert (await confirm.async_step_init({}))["type"] == "create_entry"


async def test_discovery_scan_when_unconfigured(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify async_setup proposes discovery flow for unconfigured Latter ESPHome devices and aborts stale flows."""
    dev, _mac = make_esphome_device(hass, slug="desk_panel", mac="aa:bb:cc:11:22:33", stationary=1)
    hass.config_entries._in_progress_flows.append(
        {"flow_id": "crashed_1", "handler": DOMAIN, "step_id": None, "context": {}}
    )
    hass.config_entries._in_progress_flows.append(
        {
            "flow_id": "stale_disc_1",
            "handler": DOMAIN,
            "step_id": "user",
            "context": {"source": "integration_discovery", "unique_id": "latter_ff:ff:ff:00:00:00"},
        }
    )
    assert await async_setup(hass, {}) is True
    assert "crashed_1" in hass.config_entries.aborted_flow_ids
    assert "stale_disc_1" in hass.config_entries.aborted_flow_ids
    assert any(
        f.get("data", {}).get("esphome_device_id") == dev.id
        for f in hass.config_entries._in_progress_flows
    )
