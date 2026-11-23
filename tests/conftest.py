"""Shared pytest fixtures for `ha-latter` backed by official `pytest-homeassistant`."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Mapping
from typing import Any

import pytest

from tests.helpers.paths import (
    FRONTEND_DIR,
    FRONTEND_SRC,
    LATTER_DIR,
    NODE_BIN,
    REPO_ROOT,
    read_py_tree,
    read_ts_tree,
    run_studio_node_esm,
)


@pytest.fixture
async def hass(hass: Any) -> AsyncGenerator[Any]:
    """Clean up test BLE scanners registered on real `hass` before stop."""
    yield hass
    unsubs = hass.data.pop("_latter_test_bt_unsubs", None)
    if unsubs:
        while unsubs:
            cb = unsubs.pop()
            cb()


@pytest.fixture
def make_esphome_device() -> Callable[..., tuple[Any, str]]:
    """Seed a realistic ESPHome device and entities in real Device/Entity/State registries."""
    from custom_components.latter.const import MIN_FIRMWARE_SDK_REV
    from tests.helpers.ha_setup import seed_esphome_device

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
        return seed_esphome_device(
            hass,
            slug=slug,
            mac=mac,
            name=name,
            area_id=area_id,
            stationary=stationary,
            wearable=wearable,
            display=display,
            w=w,
            h=h,
            shape=shape,
            sdk=sdk,
            with_speaker=with_speaker,
        )

    return _factory


@pytest.fixture
def setup_latter_hub(
    make_esphome_device: Callable[..., tuple[Any, str]],
) -> Callable[..., Any]:
    """Set up a complete Latter System hub entry on real Home Assistant Core."""
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
    from tests.helpers.ble_and_ws import ensure_bluetooth_manager
    from tests.helpers.ha_setup import (
        add_mock_entry,
        ensure_area,
        ensure_floor,
        flush_debouncers,
        make_subentry_dict,
        prepare_latter_dependencies,
    )

    async def _setup(
        hass: Any,
        *,
        with_device: bool = True,
        with_ble_tag: bool = False,
        with_floors: bool = True,
        stationary: int = 0,
        sync_device_area: bool = True,
        extra_device_data: Mapping[str, Any] | None = None,
    ) -> tuple[Any, Any, Any]:
        await prepare_latter_dependencies(hass)
        await ensure_bluetooth_manager(hass)

        f1_id: str | None = None
        f2_id: str | None = None
        if with_floors:
            f1 = ensure_floor(hass, "Ground Level", floor_id="floor_1", level=1)
            f2 = ensure_floor(hass, "Upper Level", floor_id="floor_2", level=2)
            f1_id = f1.floor_id
            f2_id = f2.floor_id

        ensure_area(hass, "Living Room", area_id="living_room", floor_id=f1_id)
        ensure_area(hass, "Kitchen", area_id="kitchen", floor_id=f1_id)
        ensure_area(hass, "Bedroom", area_id="bedroom", floor_id=f2_id)

        hass.states.async_set(
            "person.alex",
            "home",
            {"friendly_name": "Alex", "latitude": 45.5152, "longitude": -122.6784},
        )
        hass.states.async_set(
            "weather.home",
            "sunny",
            {
                "temperature": 72,
                "humidity": 48,
                "wind_speed": 8,
                "friendly_name": "Home Weather",
            },
        )
        hass.states.async_set(
            "sun.sun",
            "above_horizon",
            {"next_setting": "2026-11-11T01:00:00Z"},
        )

        subentries_data: list[dict[str, Any]] = []
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
                CONF_ASSIGNED_PERSON: "person.alex",
                CONF_NATIVE_BLE_TRACKING: True,
                CONF_BLE_AUTO_SWITCH: True,
                CONF_SYNC_DEVICE_AREA: sync_device_area,
            }
            if extra_device_data:
                dev_data.update(extra_device_data)
            subentries_data.append(
                make_subentry_dict(
                    dev_data,
                    subentry_type=SUBENTRY_DEVICE,
                    title="Pocket Assistant",
                    unique_id=mac,
                    subentry_id="sub_pocket",
                )
            )

        if with_ble_tag:
            subentries_data.append(
                make_subentry_dict(
                    {
                        CONF_DEVICE_SLUG: "keys_tag",
                        CONF_BLE_TARGET_ADDRESS: "11:22:33:44:55:66",
                        CONF_BLE_BEACON_UUID: "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1",
                        CONF_ASSIGNED_PERSON: "person.alex",
                        CONF_NATIVE_BLE_TRACKING: True,
                    },
                    subentry_type=SUBENTRY_BLE_TAG,
                    title="Keys Tag",
                    unique_id="tag_11:22:33:44:55:66",
                    subentry_id="sub_tag",
                )
            )

        entry = add_mock_entry(
            hass,
            entry_id="entry_latter_hub",
            domain=DOMAIN,
            title="Latter",
            data={},
            subentries_data=subentries_data,
            unique_id=DOMAIN,
        )
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()
        await flush_debouncers(hass)
        sys_obj = entry.runtime_data
        coord = sys_obj.coordinators.get("sub_pocket")
        return entry, sys_obj, coord

    return _setup


__all__ = [
    "FRONTEND_DIR",
    "FRONTEND_SRC",
    "LATTER_DIR",
    "NODE_BIN",
    "REPO_ROOT",
    "hass",
    "make_esphome_device",
    "read_py_tree",
    "read_ts_tree",
    "run_studio_node_esm",
    "setup_latter_hub",
]
