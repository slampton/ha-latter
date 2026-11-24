"""Tests for Site Broadcast speakers, phrases, caller exclusion, and Bedtime Mode quietness (D-074)."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.latter.const import (
    CONF_BROADCAST_PHRASES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_BROADCAST_SPEAKERS,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    DEFAULT_BROADCAST_PHRASES,
    DOMAIN,
    SERVICE_INTERCOM_BROADCAST,
    STUDIO_REV,
    SUBENTRY_DEVICE,
)
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.studio.settings_cleaners import (
    SettingsScopeError,
    clean_device_settings,
    clean_system_settings,
    system_settings_view,
)
from tests.helpers import (
    call_ws,
    ensure_area,
    make_subentry,
    make_ws_connection,
    mock_service,
    register_device,
    register_entity,
)


def test_broadcast_settings_validation_and_defaults() -> None:
    """Validate System broadcast_speakers/broadcast_phrases and per-Device broadcast_speaker_entities."""
    view_default = system_settings_view({})
    assert view_default["broadcast_speakers"] == []
    assert view_default["broadcast_phrases"] == list(DEFAULT_BROADCAST_PHRASES)

    cleaned_sys = clean_system_settings(
        {
            "broadcast_speakers": [
                "media_player.kitchen",
                "media_player.kitchen",
                "media_player.living_room",
            ],
            "broadcast_phrases": ["  Dinner time  ", "Dinner time", "", "A" * 80],
        }
    )
    assert cleaned_sys["broadcast_speakers"] == [
        "media_player.kitchen",
        "media_player.living_room",
    ]
    assert cleaned_sys["broadcast_phrases"] == ["Dinner time", "A" * 64]

    view_empty_phrases = system_settings_view({"broadcast_phrases": []})
    assert view_empty_phrases["broadcast_phrases"] == []

    with pytest.raises(SettingsScopeError):
        clean_system_settings({"broadcast_speakers": ["light.kitchen"]})

    cleaned_dev = clean_device_settings(
        {"broadcast_speaker_entities": ["media_player.kitchen"]}
    )
    assert cleaned_dev["broadcast_speaker_entities"] == ["media_player.kitchen"]

    with pytest.raises(SettingsScopeError):
        clean_device_settings({"broadcast_speaker_entities": ["switch.lamp"]})


@pytest.mark.asyncio
async def test_broadcast_delivery_excludes_caller_and_bedtime_displays(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify configured speaker routing, per-Device override, caller exclusion, and Bedtime Mode skip."""
    entry, _sys_obj_init, _caller_init = await setup_latter_hub(hass)

    # Add a 2nd Latter display in the Bedroom that is currently in Bedtime Mode
    esp_dev_2, mac_2 = make_esphome_device(
        hass,
        slug="bedroom_panel",
        mac="aa:bb:cc:dd:ee:44",
        name="Bedroom Panel",
        area_id="bedroom",
        stationary=1,
    )
    sub_bedroom = make_subentry(
        {
            CONF_ESPHOME_DEVICE_ID: esp_dev_2.id,
            "mac": mac_2,
            CONF_DEVICE_SLUG: "bedroom_panel",
            "bedtime_active": True,
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Bedroom Panel",
        unique_id=mac_2,
        subentry_id="sub_bedroom",
    )
    hass.config_entries.async_add_subentry(entry, sub_bedroom)
    await hass.async_block_till_done()

    sys_obj = entry.runtime_data
    caller = sys_obj.coordinators["sub_pocket"]
    bed_coord = sys_obj.coordinators["sub_bedroom"]

    # Register speakers: caller's local speaker, bedroom display's local speaker, kitchen MA speaker, unconfigured TV
    ma_dev = register_device(
        hass,
        config_entry_id="ma_entry_sonos",
        entry_domain="music_assistant",
        identifiers={("music_assistant", "kitchen_sonos")},
        name="Kitchen Sonos",
        manufacturer="Latter",
    )
    register_entity(
        hass,
        "media_player.kitchen_sonos",
        platform="music_assistant",
        device_id=ma_dev.id,
        config_entry_id="ma_entry_sonos",
        original_name="Kitchen Sonos",
        unique_id="kitchen_sonos_uid",
    )
    register_entity(
        hass,
        "media_player.bedroom_panel_media_player",
        platform="esphome",
        device_id=esp_dev_2.id,
        config_entry_id="esp_entry_bedroom_panel",
        original_name="Bedroom Speaker",
        unique_id="bedroom_panel_spk_uid",
    )
    hass.states.async_set(
        caller.local_speaker, "idle", {"friendly_name": "Desk Speaker"}
    )
    hass.states.async_set(
        "media_player.bedroom_panel_media_player",
        "idle",
        {"friendly_name": "Bedroom Speaker"},
    )
    hass.states.async_set(
        "media_player.kitchen_sonos",
        "idle",
        {"friendly_name": "Kitchen Sonos", "mass_player_type": "player"},
    )
    hass.states.async_set(
        "media_player.unconfigured_avr",
        "idle",
        {"friendly_name": "Living Room AVR", "mass_player_type": "player"},
    )
    hass.states.async_set("tts.piper", "unknown", {})

    tts_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "tts",
        "speak",
        lambda call: tts_calls.append(dict(call.data)),
    )

    global_cfg = get_global_config(hass)
    global_cfg[CONF_BROADCAST_SPEAKERS] = [
        caller.local_speaker,
        "media_player.bedroom_panel_media_player",
        "media_player.kitchen_sonos",
    ]
    global_cfg[CONF_BROADCAST_PHRASES] = ["Dinner is ready", "Time to leave"]

    # Area context packs custom broadcast phrases at field index 23 and enables 'intercom'
    caller.cached_area_payload = None
    _st, attrs = caller.get_area_context_payload()
    assert "intercom" in attrs["home_categories"].split(",")
    assert attrs["payload"].split("\x1f")[23] == "Dinner is ready\x1eTime to leave"

    # 1. Device-originated broadcast excludes caller's own speaker + Bedtime Mode display + unconfigured AVR
    res = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": caller.device_slug, "message": "Dinner is ready"},
        blocking=True,
        return_response=True,
    )
    assert res["delivered"] is True
    assert res["targets"] == ["media_player.kitchen_sonos"]

    # 2. Turning off Bedtime Mode on Bedroom Panel includes it while still excluding caller
    bed_coord.update_device_config(
        {**bed_coord.device_data, "bedtime_active": False}
    )
    res_awake = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": caller.device_slug, "message": "Time to leave"},
        blocking=True,
        return_response=True,
    )
    assert res_awake["delivered"] is True
    assert res_awake["targets"] == [
        "media_player.bedroom_panel_media_player",
        "media_player.kitchen_sonos",
    ]

    # 3. Studio WS save_device_config enforces System membership for broadcast_speaker_entities
    conn = make_ws_connection(hass)
    await call_ws(
        hass,
        conn,
        1,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=caller.subentry_id,
        command="save_device_config",
        payload={
            "config": {
                CONF_BROADCAST_SPEAKER_ENTITIES: ["media_player.unconfigured_avr"]
            }
        },
    )
    assert conn.errors and conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await call_ws(
        hass,
        conn,
        2,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=caller.subentry_id,
        command="save_device_config",
        payload={
            "config": {CONF_BROADCAST_SPEAKER_ENTITIES: ["media_player.kitchen_sonos"]}
        },
    )
    assert conn.errors == []
    assert caller.effective_broadcast_speakers == ["media_player.kitchen_sonos"]

    res_subset = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": caller.device_slug, "message": "Subset test"},
        blocking=True,
        return_response=True,
    )
    assert res_subset["targets"] == ["media_player.kitchen_sonos"]

    # 4. System-wide target_device="all" uses System broadcast_speakers and skips unconfigured AVR + Bedtime displays
    bed_coord.update_device_config(
        {**bed_coord.device_data, "bedtime_active": True}
    )
    res_all = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": "all", "message": "Site-wide notice"},
        blocking=True,
        return_response=True,
    )
    assert res_all["delivered"] is True
    assert res_all["targets"] == [caller.local_speaker, "media_player.kitchen_sonos"]
    assert "media_player.bedroom_panel_media_player" not in res_all["targets"]
    assert "media_player.unconfigured_avr" not in res_all["targets"]

    # 5. target_device="occupied_areas" intersects System broadcast_speakers with occupied areas
    ensure_area(hass, "Kitchen", area_id="kitchen")
    er.async_get(hass).async_update_entity(
        "media_player.kitchen_sonos", area_id="kitchen", name="Kitchen Sonos"
    )
    await hass.async_block_till_done()

    fabric = get_ble_fabric(hass)
    orig_occ = fabric.get_area_occupancy
    fabric.get_area_occupancy = lambda area_id: {
        "is_occupied": area_id == "kitchen",
        "persons": [],
    }
    try:
        res_occ = await hass.services.async_call(
            DOMAIN,
            SERVICE_INTERCOM_BROADCAST,
            {"target_device": "occupied_areas", "message": "Occupied only"},
            blocking=True,
            return_response=True,
        )
    finally:
        fabric.get_area_occupancy = orig_occ
    assert res_occ["delivered"] is True
    assert res_occ["targets"] == ["media_player.kitchen_sonos"]

    assert await hass.config_entries.async_unload(entry.entry_id) is True
