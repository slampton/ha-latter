"""Tests for Home Hub Broadcast speakers, phrases, caller exclusion, and Bedtime Mode quietness (D-074)."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.latter.const import (
    CONF_BEDTIME_ACTIVE,
    CONF_BROADCAST_PHRASES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_BROADCAST_SPEAKERS,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    DATA_GLOBAL_CONFIG,
    DEFAULT_BROADCAST_PHRASES,
    DOMAIN,
    SERVICE_INTERCOM_BROADCAST,
    SUBENTRY_DEVICE,
)
from custom_components.latter.studio.commands import STUDIO_REV
from custom_components.latter.studio.settings import (
    SettingsScopeError,
    clean_device_settings,
    clean_system_settings,
    system_settings_view,
)


async def _call_ws(
    hass: Any,
    conn: websocket_api.ActiveConnection,
    msg_id: int,
    msg_type: str,
    **kwargs: Any,
) -> None:
    handler = hass._ws_commands[msg_type]
    schema = getattr(handler, "_ws_schema", None)
    raw_msg = {"id": msg_id, "type": msg_type, **kwargs}
    validated = schema(raw_msg) if schema is not None else raw_msg
    await handler(hass, conn, validated)


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
    entry, sys_obj, caller = await setup_latter_hub(hass)

    # Add a 2nd Latter display in the Bedroom that is currently in Bedtime Mode
    esp_dev_2, mac_2 = make_esphome_device(
        hass,
        slug="bedroom_panel",
        mac="aa:bb:cc:dd:ee:44",
        name="Bedroom Panel",
        area_id="bedroom",
        stationary=1,
    )
    entry.subentries["sub_bedroom"] = ConfigSubentry(
        data={
            CONF_ESPHOME_DEVICE_ID: esp_dev_2.id,
            "mac": mac_2,
            CONF_DEVICE_SLUG: "bedroom_panel",
            CONF_BEDTIME_ACTIVE: True,
        },
        subentry_type=SUBENTRY_DEVICE,
        title="Bedroom Panel",
        unique_id=mac_2,
        subentry_id="sub_bedroom",
    )
    from custom_components.latter.coordinator import LatterCoordinator

    bed_coord = LatterCoordinator(
        hass, entry, sys_obj.hmac_secret, entry.subentries["sub_bedroom"]
    )
    sys_obj.coordinators["sub_bedroom"] = bed_coord

    # Register speakers: caller's local speaker, bedroom display's local speaker, kitchen MA speaker, unconfigured TV
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    ma_dev = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("music_assistant", "kitchen_sonos")},
        name="Kitchen Sonos",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.kitchen_sonos",
            platform="music_assistant",
            device_id=ma_dev.id,
            config_entry_id=entry.entry_id,
            original_name="Kitchen Sonos",
            unique_id="kitchen_sonos_uid",
        )
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.bedroom_panel_media_player",
            platform="esphome",
            device_id=esp_dev_2.id,
            config_entry_id=entry.entry_id,
            original_name="Bedroom Speaker",
            unique_id="bedroom_panel_spk_uid",
        )
    )
    hass.states.async_set(caller.local_speaker, "idle", {"friendly_name": "Desk Speaker"})
    hass.states.async_set(
        "media_player.bedroom_panel_media_player", "idle", {"friendly_name": "Bedroom Speaker"}
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
    hass.services.async_register(
        "tts",
        "speak",
        lambda call: tts_calls.append(dict(call.data)),
    )

    global_cfg = hass.data[DOMAIN][DATA_GLOBAL_CONFIG]
    global_cfg[CONF_BROADCAST_SPEAKERS] = [
        caller.local_speaker,
        "media_player.bedroom_panel_media_player",
        "media_player.kitchen_sonos",
    ]
    global_cfg[CONF_BROADCAST_PHRASES] = ["Dinner is ready", "Time to leave"]

    # Area context packs custom broadcast phrases at field index 23 and enables 'intercom'
    caller._cached_area_payload = None
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
    bed_coord.update_device_config({**bed_coord.device_data, CONF_BEDTIME_ACTIVE: False})
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
    conn = websocket_api.ActiveConnection()
    await _call_ws(
        hass,
        conn,
        1,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=caller.subentry_id,
        command="save_device_config",
        payload={"config": {CONF_BROADCAST_SPEAKER_ENTITIES: ["media_player.unconfigured_avr"]}},
    )
    assert conn.errors and conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    await _call_ws(
        hass,
        conn,
        2,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=caller.subentry_id,
        command="save_device_config",
        payload={"config": {CONF_BROADCAST_SPEAKER_ENTITIES: ["media_player.kitchen_sonos"]}},
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
    bed_coord.update_device_config({**bed_coord.device_data, CONF_BEDTIME_ACTIVE: True})
    res_all = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": "all", "message": "Whole-home notice"},
        blocking=True,
        return_response=True,
    )
    assert res_all["delivered"] is True
    assert res_all["targets"] == [caller.local_speaker, "media_player.kitchen_sonos"]
    assert "media_player.bedroom_panel_media_player" not in res_all["targets"]
    assert "media_player.unconfigured_avr" not in res_all["targets"]

    # 5. target_device="occupied_areas" intersects System broadcast_speakers with occupied areas
    from homeassistant.helpers import area_registry as ar

    from custom_components.latter.presence import get_ble_fabric

    area_reg = ar.async_get(hass)
    area_reg.areas["kitchen"] = ar.AreaEntry("kitchen", "Kitchen")
    ent_reg.entities["media_player.kitchen_sonos"].area_id = "kitchen"
    fabric = get_ble_fabric(hass)
    orig_occ = fabric.get_area_occupancy
    fabric.get_area_occupancy = lambda area_id: {"is_occupied": area_id == "kitchen", "persons": []}
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
