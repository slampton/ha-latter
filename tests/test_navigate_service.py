"""Unit and integration tests for the `latter.navigate` public Home Assistant action."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
import yaml

from custom_components.latter.const import (
    CONF_ASSIGNED_PERSON,
    CONF_BEDTIME_ACTIVE,
    CONF_DEFAULT_AREA,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    DOMAIN,
    PUBLIC_SERVICES,
    SERVICE_NAVIGATE,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.protocol_specs import (
    NAVIGATE_EXTRA_ROUTES,
    NAVIGATE_ROUTES,
    SHORTCUT_ROUTE_TOKENS,
    normalize_navigate_route,
)
from tests.conftest import LATTER_DIR
from tests.helpers import (
    add_mock_entry,
    ensure_area,
    get_test_manifest,
    make_subentry_dict,
    mock_service,
    prepare_latter_dependencies,
    seed_device_hello_manifest,
    seed_esphome_device,
)


def test_navigate_route_catalog_and_normalizer() -> None:
    """Verify `NAVIGATE_ROUTES` derives from `protocol_v3.json` and rejects private/unknown routes."""
    expected_extra = frozenset({"home", "app:home", "app:settings", "quick_actions"})
    expected_all = frozenset(SHORTCUT_ROUTE_TOKENS) | expected_extra
    assert set(SHORTCUT_ROUTE_TOKENS).issubset(NAVIGATE_ROUTES)
    assert expected_extra == NAVIGATE_EXTRA_ROUTES
    assert expected_all == NAVIGATE_ROUTES

    # Every shortcut route in protocol_v3.json plus extra canonical routes normalize cleanly
    for route in (*SHORTCUT_ROUTE_TOKENS, "home", "app:home", "app:settings", "quick_actions"):
        assert normalize_navigate_route(route) == route
        assert normalize_navigate_route(f"  {route.upper()}  ") == route

    # Every curated option documented in services.yaml must be a canonical NAVIGATE_ROUTES member
    services_yaml = yaml.safe_load(
        (LATTER_DIR / "services.yaml").read_text(encoding="utf-8")
    )
    route_selector = services_yaml["navigate"]["fields"]["route"]["selector"]["select"]
    assert route_selector["custom_value"] is True
    curated_options = route_selector["options"]
    assert len(curated_options) >= 30
    for opt in curated_options:
        assert normalize_navigate_route(opt) == opt

    # Private showcase/dock/music_hud commands and invalid tokens must be rejected
    for bad in (
        "",
        "   ",
        None,
        "showcase:on",
        "showcase:off",
        "showcase:va:listening",
        "dock:1",
        "music_hud:on",
        "unknown:page",
        "settings:nonexistent",
    ):
        with pytest.raises(ValueError):
            normalize_navigate_route(bad)


@pytest.mark.asyncio
async def test_navigate_single_device_wake_bedtime_and_validation(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise single-target `latter.navigate` with wake, silent, Bedtime Mode, validation, and offline errors."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_ble_tag=True)
    assert SERVICE_NAVIGATE in PUBLIC_SERVICES
    assert hass.services.has_service(DOMAIN, SERVICE_NAVIGATE)

    sent_cmds: list[str] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_device_command",
        lambda call: sent_cmds.append(str(call.data["command"])),
    )

    # 1. Default wake=True -> nav:<route> (including deep Protocol v3 subpages & case/whitespace trimming)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": coord.device_slug, "route": "  WEATHER:MOON  "},
        blocking=True,
    )
    assert sent_cmds[-1] == "nav:weather:moon"

    # 2. Explicit wake=False (bool and YAML string) -> nav_silent:<route>
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": coord.device_slug, "route": "music:lyrics", "wake": False},
        blocking=True,
    )
    assert sent_cmds[-1] == "nav_silent:music:lyrics"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": coord.device_slug, "route": "quick_actions", "wake": "false"},
        blocking=True,
    )
    assert sent_cmds[-1] == "nav_silent:quick_actions"

    # 3. Bedtime Mode forces nav_silent:<route> even when wake=True
    coord.update_device_config({**coord.device_data, CONF_BEDTIME_ACTIVE: True})
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": coord.device_slug, "route": "cameras:grid", "wake": True},
        blocking=True,
    )
    assert sent_cmds[-1] == "nav_silent:cameras:grid"

    # Clearing Bedtime Mode restores wake=True -> nav:<route>
    coord.update_device_config({**coord.device_data, CONF_BEDTIME_ACTIVE: False})
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": coord.device_slug, "route": "home", "wake": True},
        blocking=True,
    )
    assert sent_cmds[-1] == "nav:home"

    # 4. Invalid route raises translated ServiceValidationError before touching ESPHome
    count_before = len(sent_cmds)
    with pytest.raises(ServiceValidationError) as exc_route:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE,
            {"target_device": coord.device_slug, "route": "showcase:on"},
            blocking=True,
        )
    assert exc_route.value.translation_domain == DOMAIN
    assert exc_route.value.translation_key == "invalid_navigate_route"
    assert len(sent_cmds) == count_before

    # 5. Unknown device raises unknown_target
    with pytest.raises(ServiceValidationError) as exc_target:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE,
            {"target_device": "nonexistent_panel", "route": "home"},
            blocking=True,
        )
    assert exc_target.value.translation_key == "unknown_target"

    # 6. Explicit BLE tag target raises ble_tag_no_commands
    with pytest.raises(HomeAssistantError) as exc_tag:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE,
            {"target_device": "sub_tag", "route": "home"},
            blocking=True,
        )
    assert exc_tag.value.translation_key == "ble_tag_no_commands"

    # 7. Explicit single target while offline/sleeping raises device_offline_or_sleeping
    hass.states.async_set(
        "sensor.pocket_assistant_system_rpc_outbox", STATE_UNAVAILABLE
    )
    with pytest.raises(HomeAssistantError) as exc_off:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE,
            {"target_device": coord.device_slug, "route": "app:clock"},
            blocking=True,
        )
    assert exc_off.value.translation_key == "device_offline_or_sleeping"

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    assert not hass.services.has_service(DOMAIN, SERVICE_NAVIGATE)


@pytest.mark.asyncio
async def test_navigate_single_device_fallback_and_headless_rejection(
    hass: Any,
) -> None:
    """Verify omitted `target_device` single-device fallback and explicit headless target rejection."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Office", area_id="office")

    desk_dev, desk_mac = seed_esphome_device(
        hass,
        slug="desk_panel",
        mac="aa:bb:cc:dd:ee:10",
        name="Desk Panel",
        area_id="office",
        stationary=1,
        display=1,
    )
    sub_desk = make_subentry_dict(
        {
            CONF_DEVICE_SLUG: "desk_panel",
            CONF_ESPHOME_DEVICE_ID: desk_dev.id,
            "mac": desk_mac,
            CONF_DEFAULT_AREA: "office",
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Desk Panel",
        unique_id=f"latter_{desk_mac}",
        subentry_id="sub_desk",
    )
    entry = add_mock_entry(
        hass,
        entry_id="entry_single_nav",
        domain=DOMAIN,
        title="Latter",
        subentries_data=[sub_desk],
        unique_id=DOMAIN,
    )
    await seed_device_hello_manifest(hass, "sub_desk", get_test_manifest(hass, desk_dev.id))
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    desk_cmds: list[str] = []
    mock_service(
        hass,
        "esphome",
        "desk_panel_latter_device_command",
        lambda call: desk_cmds.append(str(call.data["command"])),
    )

    # Omitted target_device resolves the sole display cleanly
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"route": "app:home"},
        blocking=True,
    )
    assert desk_cmds == ["nav:app:home"]
    assert await hass.config_entries.async_unload(entry.entry_id) is True

    # Headless (display=0) explicit target is rejected with not_supported
    headless_dev, headless_mac = seed_esphome_device(
        hass,
        slug="voice_puck",
        mac="aa:bb:cc:dd:ee:11",
        name="Voice Puck",
        area_id="office",
        stationary=1,
        display=0,
    )
    sub_headless = make_subentry_dict(
        {
            CONF_DEVICE_SLUG: "voice_puck",
            CONF_ESPHOME_DEVICE_ID: headless_dev.id,
            "mac": headless_mac,
            CONF_DEFAULT_AREA: "office",
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Voice Puck",
        unique_id=f"latter_{headless_mac}",
        subentry_id="sub_headless",
    )
    entry2 = add_mock_entry(
        hass,
        entry_id="entry_headless_nav",
        domain=DOMAIN,
        title="Latter",
        subentries_data=[sub_headless],
        unique_id=f"{DOMAIN}_2",
    )
    await seed_device_hello_manifest(hass, "sub_headless", get_test_manifest(hass, headless_dev.id))
    assert await hass.config_entries.async_setup(entry2.entry_id) is True
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_headless:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE,
            {"target_device": "voice_puck", "route": "home"},
            blocking=True,
        )
    assert exc_headless.value.translation_key == "not_supported"
    assert await hass.config_entries.async_unload(entry2.entry_id) is True


@pytest.mark.asyncio
async def test_navigate_multi_target_all_occupied_person_and_offline_skip(
    hass: Any,
) -> None:
    """Verify `all`, `occupied_areas`, and `person.*` skip offline displays and honor per-device Bedtime."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Office", area_id="office")
    ensure_area(hass, "Bedroom", area_id="bedroom")
    ensure_area(hass, "Living Room", area_id="living_room")

    desk_dev, desk_mac = seed_esphome_device(
        hass,
        slug="desk_panel",
        mac="aa:bb:cc:dd:ee:21",
        name="Desk Panel",
        area_id="office",
        stationary=1,
        display=1,
    )
    bed_dev, bed_mac = seed_esphome_device(
        hass,
        slug="bedroom_panel",
        mac="aa:bb:cc:dd:ee:22",
        name="Bedroom Panel",
        area_id="bedroom",
        stationary=1,
        display=1,
    )
    pocket_dev, pocket_mac = seed_esphome_device(
        hass,
        slug="pocket_handheld",
        mac="aa:bb:cc:dd:ee:23",
        name="Pocket Handheld",
        area_id="living_room",
        stationary=0,
        display=1,
    )
    headless_dev, headless_mac = seed_esphome_device(
        hass,
        slug="voice_puck",
        mac="aa:bb:cc:dd:ee:24",
        name="Voice Puck",
        area_id="office",
        stationary=1,
        display=0,
    )

    subentries = [
        make_subentry_dict(
            {
                CONF_DEVICE_SLUG: "desk_panel",
                CONF_ESPHOME_DEVICE_ID: desk_dev.id,
                "mac": desk_mac,
                CONF_DEFAULT_AREA: "office",
                CONF_ASSIGNED_PERSON: "person.alex",
            },
            subentry_type=SUBENTRY_DEVICE,
            title="Desk Panel",
            unique_id=f"latter_{desk_mac}",
            subentry_id="sub_desk",
        ),
        make_subentry_dict(
            {
                CONF_DEVICE_SLUG: "bedroom_panel",
                CONF_ESPHOME_DEVICE_ID: bed_dev.id,
                "mac": bed_mac,
                CONF_DEFAULT_AREA: "bedroom",
                CONF_BEDTIME_ACTIVE: True,
            },
            subentry_type=SUBENTRY_DEVICE,
            title="Bedroom Panel",
            unique_id=f"latter_{bed_mac}",
            subentry_id="sub_bedroom",
        ),
        make_subentry_dict(
            {
                CONF_DEVICE_SLUG: "pocket_handheld",
                CONF_ESPHOME_DEVICE_ID: pocket_dev.id,
                "mac": pocket_mac,
                CONF_DEFAULT_AREA: "living_room",
                CONF_ASSIGNED_PERSON: "person.alex",
            },
            subentry_type=SUBENTRY_DEVICE,
            title="Pocket Handheld",
            unique_id=f"latter_{pocket_mac}",
            subentry_id="sub_pocket",
        ),
        make_subentry_dict(
            {
                CONF_DEVICE_SLUG: "voice_puck",
                CONF_ESPHOME_DEVICE_ID: headless_dev.id,
                "mac": headless_mac,
                CONF_DEFAULT_AREA: "office",
            },
            subentry_type=SUBENTRY_DEVICE,
            title="Voice Puck",
            unique_id=f"latter_{headless_mac}",
            subentry_id="sub_headless",
        ),
        make_subentry_dict(
            {
                CONF_DEVICE_SLUG: "alex_phone",
                "ble_target_address": "11:22:33:44:55:66",
                CONF_ASSIGNED_PERSON: "person.alex",
            },
            subentry_type=SUBENTRY_BLE_TAG,
            title="Alex Phone",
            unique_id="latter_ble_112233445566",
            subentry_id="sub_tag",
        ),
    ]
    entry = add_mock_entry(
        hass,
        entry_id="entry_multi_nav",
        domain=DOMAIN,
        title="Latter",
        subentries_data=subentries,
        unique_id=DOMAIN,
    )
    await seed_device_hello_manifest(hass, "sub_desk", get_test_manifest(hass, desk_dev.id))
    await seed_device_hello_manifest(hass, "sub_bedroom", get_test_manifest(hass, bed_dev.id))
    await seed_device_hello_manifest(hass, "sub_pocket", get_test_manifest(hass, pocket_dev.id))
    await seed_device_hello_manifest(hass, "sub_headless", get_test_manifest(hass, headless_dev.id))
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    recorded: dict[str, list[str]] = {
        "desk_panel": [],
        "bedroom_panel": [],
        "pocket_handheld": [],
        "voice_puck": [],
    }
    for slug in recorded:
        mock_service(
            hass,
            "esphome",
            f"{slug}_latter_device_command",
            lambda call, s=slug: recorded[s].append(str(call.data["command"])),
        )

    # Mark pocket_handheld hibernating/offline
    hass.states.async_set(
        "sensor.pocket_handheld_system_rpc_outbox", STATE_UNAVAILABLE
    )

    # 1. target_device="all": awake gets nav:, bedtime gets nav_silent:, offline & headless skipped cleanly
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": "all", "route": "cameras:grid", "wake": True},
        blocking=True,
    )
    assert recorded["desk_panel"] == ["nav:cameras:grid"]
    assert recorded["bedroom_panel"] == ["nav_silent:cameras:grid"]
    assert recorded["pocket_handheld"] == []
    assert recorded["voice_puck"] == []

    for cmds in recorded.values():
        cmds.clear()

    # 2. target_device="occupied_areas": empty when no Area occupied
    fabric = get_ble_fabric(hass)
    desk_coord = entry.runtime_data.coordinators["sub_desk"]
    pocket_coord = entry.runtime_data.coordinators["sub_pocket"]
    tag_coord = entry.runtime_data.coordinators["sub_tag"]
    if pocket_coord._ble_tracker is not None:
        pocket_coord._ble_tracker.current_area_id = None
        pocket_coord._ble_tracker.is_away = True
    if tag_coord._ble_tracker is not None:
        tag_coord._ble_tracker.current_area_id = None
        tag_coord._ble_tracker.is_away = True
    fabric.notify_occupancy_listeners()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": "occupied_areas", "route": "weather:forecast"},
        blocking=True,
    )
    assert recorded["desk_panel"] == []
    assert recorded["bedroom_panel"] == []

    # Mark office occupied via tag_coord; only desk_panel (in office) receives command
    assert tag_coord._ble_tracker is not None
    tag_coord._ble_tracker.current_area_id = "office"
    tag_coord._ble_tracker.is_away = False
    desk_coord.active_area_id = "office"
    fabric.notify_occupancy_listeners()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": "occupied_areas", "route": "weather:forecast"},
        blocking=True,
    )
    assert recorded["desk_panel"] == ["nav:weather:forecast"]
    assert recorded["bedroom_panel"] == []
    assert recorded["pocket_handheld"] == []

    for cmds in recorded.values():
        cmds.clear()

    # 3. target_device="person.alex": hits online assigned desk_panel and skips offline pocket_handheld
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAVIGATE,
        {"target_device": "person.alex", "route": "home_hub:thermostat", "wake": False},
        blocking=True,
    )
    assert recorded["desk_panel"] == ["nav_silent:home_hub:thermostat"]
    assert recorded["bedroom_panel"] == []
    assert recorded["pocket_handheld"] == []

    assert await hass.config_entries.async_unload(entry.entry_id) is True
