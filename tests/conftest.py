"""Shared pytest fixtures for `ha-latter` backed by `tests.harness`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import json
from pathlib import Path
import sys
from typing import Any

import pytest

from tests.harness import REPO_ROOT, USING_HA_STUBS, DeterministicEventLoop

_ = REPO_ROOT

if USING_HA_STUBS and sys.platform == "win32":

    def pytest_asyncio_loop_factories(config: Any, item: Any) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
        """Provide socket-free deterministic event loop factory on Windows offline test runs."""
        _ = (config, item)
        return {"deterministic": DeterministicEventLoop}


@pytest.fixture
def hass(tmp_path: Path) -> Any:
    """Provide a fresh, isolated HomeAssistant instance backed by `tmp_path`."""
    from homeassistant.core import HomeAssistant

    return HomeAssistant(config_dir=tmp_path)


@pytest.fixture
def make_esphome_device() -> Callable[..., tuple[Any, str]]:
    """Seed a realistic ESPHome device and entities in Device/Entity/State registries."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    from custom_components.latter.const import MIN_FIRMWARE_SDK_REV

    def _factory(
        hass: Any,
        *,
        slug: str = "pocket_assistant",
        mac: str = "aa:bb:cc:dd:ee:01",
        name: str = "Pocket Assistant",
        area_id: str | None = "living_room",
        stationary: int = 0,
        wearable: int = 0,
        display: int = 1,
        w: int = 466,
        h: int = 466,
        shape: str = "circle",
        sdk: int = MIN_FIRMWARE_SDK_REV,
        with_speaker: bool = True,
    ) -> tuple[Any, str]:
        esp_entry = hass.config_entries.add_entry(
            sys.modules["homeassistant.config_entries"].ConfigEntry(
                entry_id=f"esp_entry_{slug}",
                domain="esphome",
                title=name,
                data={"device_name": slug},
            )
        )
        dev_reg = dr.async_get(hass)
        dev = dev_reg.async_get_or_create(
            config_entry_id=esp_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            identifiers={("esphome", mac)},
            name=name,
            manufacturer="slampton",
            model=f"{slug}-board",
            area_id=area_id,
        )
        ent_reg = er.async_get(hass)
        manifest_json = json.dumps(
            {
                "v": 2,
                "contract": 3,
                "board": f"{slug}_board",
                "w": w,
                "h": h,
                "shape": shape,
                "display": display,
                "touch": 1,
                "audio": 1,
                "mic": 1,
                "spk": 1,
                "imu": 1,
                "battery": 1 - stationary,
                "stationary": stationary,
                "wearable": wearable,
                "ips": 1,
                "minor": 1,
                "sdk": sdk,
            },
            separators=(",", ":"),
        )
        hw_eid = f"sensor.{slug}_system_hardware_manifest"
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=hw_eid,
                platform="esphome",
                device_id=dev.id,
                config_entry_id=esp_entry.entry_id,
                original_name="System: Hardware Manifest",
                unique_id=f"{mac.upper()}/0/text_sensor/System: Hardware Manifest",
            )
        )
        hass.states.async_set(hw_eid, manifest_json)

        rpc_eid = f"sensor.{slug}_system_rpc_outbox"
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=rpc_eid,
                platform="esphome",
                device_id=dev.id,
                config_entry_id=esp_entry.entry_id,
                original_name="System: RPC Outbox",
                unique_id=f"{mac.upper()}/0/text_sensor/System: RPC Outbox",
            )
        )
        hass.states.async_set(rpc_eid, "")

        beacon_eid = f"binary_sensor.{slug}_ble_radio_active"
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=beacon_eid,
                platform="esphome",
                device_id=dev.id,
                config_entry_id=esp_entry.entry_id,
                original_name="BLE Radio Active",
            )
        )
        hass.states.async_set(beacon_eid, "off")

        if with_speaker:
            spk_eid = f"media_player.{slug}_music"
            ent_reg.async_register(
                er.RegistryEntry(
                    entity_id=spk_eid,
                    platform="esphome",
                    device_id=dev.id,
                    config_entry_id=esp_entry.entry_id,
                    original_name="Music",
                )
            )
            hass.states.async_set(spk_eid, "idle", {"volume_level": 0.5, "friendly_name": f"{name} Speaker"})

        for svc_suffix in (
            "latter_ping",
            "latter_push_v3",
            "latter_set_beacon_uuid",
            "latter_device_command",
            "set_browse_slots",
            "show_notification",
            "wake_display_page",
            "latter_factory_reset",
        ):
            hass.services.async_register("esphome", f"{slug}_{svc_suffix}", lambda _call: None)

        return dev, mac

    return _factory


@pytest.fixture
def setup_latter_hub(make_esphome_device: Callable[..., tuple[Any, str]]) -> Callable[..., Any]:
    """Set up a complete Latter System hub entry with Areas, Person, Display Device, and optional BLE Tag."""
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.helpers import area_registry as ar

    from custom_components.latter import async_setup, async_setup_entry
    from custom_components.latter.const import (
        CONF_ASSIGNED_PERSON,
        CONF_BLE_AUTO_SWITCH,
        CONF_BLE_BEACON_UUID,
        CONF_BLE_TARGET_ADDRESS,
        CONF_DEFAULT_AREA,
        CONF_DEFAULT_SPEAKER,
        CONF_DEVICE_SLUG,
        CONF_ESPHOME_DEVICE_ID,
        CONF_NATIVE_BLE_TRACKING,
        CONF_SYNC_DEVICE_AREA,
        DOMAIN,
        SUBENTRY_BLE_TAG,
        SUBENTRY_DEVICE,
    )

    async def _setup(
        hass: Any,
        *,
        with_device: bool = True,
        with_ble_tag: bool = False,
        stationary: int = 0,
        sync_device_area: bool = True,
        extra_device_data: Mapping[str, Any] | None = None,
    ) -> tuple[Any, Any, Any]:
        area_reg = ar.async_get(hass)
        if not area_reg.async_get_area("living_room"):
            area_reg.async_create("Living Room", area_id="living_room", floor_id="floor_1")
        if not area_reg.async_get_area("kitchen"):
            area_reg.async_create("Kitchen", area_id="kitchen", floor_id="floor_1")
        if not area_reg.async_get_area("bedroom"):
            area_reg.async_create("Bedroom", area_id="bedroom", floor_id="floor_2")

        hass.states.async_set(
            "person.sean",
            "home",
            {"friendly_name": "Sean", "latitude": 37.8045, "longitude": -122.2715},
        )
        hass.states.async_set(
            "weather.home",
            "sunny",
            {"temperature": 72, "humidity": 48, "wind_speed": 8, "friendly_name": "Home Weather"},
        )
        hass.states.async_set("sun.sun", "above_horizon", {"next_setting": "2026-11-11T01:00:00Z"})

        subentries: list[ConfigSubentry] = []
        esp_dev = None
        if with_device:
            esp_dev, mac = make_esphome_device(
                hass,
                slug="pocket_assistant",
                mac="aa:bb:cc:dd:ee:01",
                name="Pocket Assistant",
                area_id="living_room",
                stationary=stationary,
            )
            dev_data: dict[str, Any] = {
                CONF_ESPHOME_DEVICE_ID: esp_dev.id,
                "mac": mac,
                CONF_DEVICE_SLUG: "pocket_assistant",
                CONF_DEFAULT_AREA: "living_room",
                CONF_DEFAULT_SPEAKER: "media_player.pocket_assistant_music",
                CONF_ASSIGNED_PERSON: "person.sean",
                CONF_NATIVE_BLE_TRACKING: True,
                CONF_BLE_AUTO_SWITCH: True,
                CONF_SYNC_DEVICE_AREA: sync_device_area,
            }
            if extra_device_data:
                dev_data.update(extra_device_data)
            subentries.append(
                ConfigSubentry(
                    data=dev_data,
                    subentry_type=SUBENTRY_DEVICE,
                    title="Pocket Assistant",
                    unique_id=mac,
                    subentry_id="sub_pocket",
                )
            )

        if with_ble_tag:
            subentries.append(
                ConfigSubentry(
                    data={
                        CONF_DEVICE_SLUG: "keys_tag",
                        CONF_BLE_TARGET_ADDRESS: "11:22:33:44:55:66",
                        CONF_BLE_BEACON_UUID: "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1",
                        CONF_ASSIGNED_PERSON: "person.sean",
                        CONF_NATIVE_BLE_TRACKING: True,
                    },
                    subentry_type=SUBENTRY_BLE_TAG,
                    title="Keys Tag",
                    unique_id="tag_11:22:33:44:55:66",
                    subentry_id="sub_tag",
                )
            )

        await async_setup(hass, {})
        entry = hass.config_entries.add_entry(
            ConfigEntry(
                entry_id="entry_latter_hub",
                domain=DOMAIN,
                title="Latter",
                data={},
                subentries_data=subentries,
                unique_id=DOMAIN,
            )
        )
        assert await async_setup_entry(hass, entry) is True
        await hass.async_block_till_done()
        sys_obj = entry.runtime_data
        coord = sys_obj.coordinators.get("sub_pocket")
        return entry, sys_obj, coord

    return _setup
