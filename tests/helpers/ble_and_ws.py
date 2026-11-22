"""Real Home Assistant WebSocket (`ActiveConnection`), `habluetooth`, Camera, and HTTP helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import io
import json
import logging
import time
from types import SimpleNamespace
from typing import Any
import uuid

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from habluetooth import BaseHaRemoteScanner, get_manager, set_manager
from home_assistant_bluetooth import BluetoothServiceInfoBleak
from homeassistant.auth.models import User
from homeassistant.components import bluetooth, camera as ha_camera
from homeassistant.components.bluetooth.manager import HomeAssistantBluetoothManager
from homeassistant.components.bluetooth.storage import BluetoothStorage
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.http import WebSocketAdapter
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, device_registry as dr
from PIL import Image
import pytest

from custom_components.latter.presence.ble_registry import APPLE_COMPANY_ID, IBEACON_PREFIX
from tests.helpers.ha_setup import flush_debouncers, register_device

_BT_UNSUBS_KEY = "_latter_test_bt_unsubs"
_BT_SCANNERS_KEY = "_latter_test_bt_scanners"


class RealWsCapture:
    """Thin capture wrapper around a real Home Assistant `ActiveConnection`."""

    def __init__(self, hass: HomeAssistant, *, is_admin: bool = True) -> None:
        self.hass = hass
        self.sent: list[dict[str, Any]] = []
        self.results: list[tuple[int, Any]] = []
        self.errors: list[tuple[int, str, str]] = []
        self.messages: list[dict[str, Any]] = []
        self._pending_results: dict[int, asyncio.Event] = {}
        user = User(
            name="Admin" if is_admin else "Member",
            perm_lookup=None,  # type: ignore[arg-type]
            is_owner=is_admin,
            is_active=True,
        )
        logger = WebSocketAdapter(logging.getLogger(__name__), {"connid": id(self)})
        init_vars = ActiveConnection.__init__.__code__.co_varnames
        if "cancel_ws" in init_vars:
            self.conn = ActiveConnection(
                logger,
                hass,
                self._on_send_message,
                user,
                None,
                "127.0.0.1",
                lambda: None,
            )
        elif "remote" in init_vars:
            self.conn = ActiveConnection(
                logger,
                hass,
                self._on_send_message,
                user,
                None,
                "127.0.0.1",
            )
        else:
            self.conn = ActiveConnection(
                logger,
                hass,
                self._on_send_message,
                user,
                None,
            )

        def _cleanup_ws_subs(_event: Any) -> None:
            for unsub in list(self.conn.subscriptions.values()):
                unsub()
            self.conn.subscriptions.clear()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _cleanup_ws_subs)

    @property
    def subscriptions(self) -> dict[Any, Callable[[], Any]]:
        """Expose underlying `ActiveConnection.subscriptions`."""
        return self.conn.subscriptions

    def _on_send_message(self, raw: bytes | str | dict[str, Any]) -> None:
        if isinstance(raw, bytes):
            parsed = json.loads(raw.decode("utf-8"))
        elif isinstance(raw, str):
            parsed = json.loads(raw)
        else:
            parsed = dict(raw)

        self.sent.append(parsed)
        msg_type = parsed.get("type")
        if msg_type == "result":
            msg_id = int(parsed["id"])
            if parsed.get("success", False):
                self.results.append((msg_id, parsed.get("result")))
            else:
                err = parsed.get("error") or {}
                self.errors.append(
                    (
                        msg_id,
                        str(err.get("code") or "unknown_error"),
                        str(err.get("message") or ""),
                    )
                )
            done_ev = self._pending_results.get(msg_id)
            if done_ev is not None:
                done_ev.set()
        elif msg_type == "event":
            self.messages.append(parsed)

    async def call(self, msg_id: int, ws_type: str, **payload: Any) -> dict[str, Any] | None:
        """Dispatch a WebSocket command through real `ActiveConnection.async_handle`."""
        done_ev = self._pending_results.setdefault(msg_id, asyncio.Event())
        try:
            self.conn.async_handle({"id": msg_id, "type": ws_type, **payload})
            if not done_ev.is_set():
                await asyncio.wait_for(done_ev.wait(), timeout=5.0)
        finally:
            self._pending_results.pop(msg_id, None)
        await self.hass.async_block_till_done()
        await flush_debouncers(self.hass)
        return next(
            (
                m
                for m in reversed(self.sent)
                if m.get("type") == "result" and m.get("id") == msg_id
            ),
            None,
        )


def make_ws_connection(hass: HomeAssistant, *, is_admin: bool = True) -> RealWsCapture:
    """Create a `RealWsCapture` bound to `hass`'s registered WebSocket handlers."""
    return RealWsCapture(hass, is_admin=is_admin)


async def call_ws(
    hass: HomeAssistant,
    conn: RealWsCapture,
    msg_id: int,
    ws_type: str,
    **payload: Any,
) -> dict[str, Any] | None:
    """Send a WebSocket command through `RealWsCapture` and await background tasks."""
    _ = hass
    return await conn.call(msg_id, ws_type, **payload)


async def ensure_bluetooth_manager(hass: HomeAssistant) -> HomeAssistantBluetoothManager:
    """Ensure a real `HomeAssistantBluetoothManager` is initialized and bound to `hass`."""
    from bleak_retry_connector import BleakSlotManager
    from bluetooth_adapters import get_adapters
    from homeassistant.components.bluetooth import passive_update_processor
    from homeassistant.components.bluetooth.const import DATA_MANAGER
    from homeassistant.components.bluetooth.match import IntegrationMatcher

    existing = hass.data.get(DATA_MANAGER)
    if isinstance(existing, HomeAssistantBluetoothManager):
        set_manager(existing)
        return existing

    try:
        cur = get_manager()
        if isinstance(cur, HomeAssistantBluetoothManager) and cur.hass is hass:
            hass.data[DATA_MANAGER] = cur
            return cur
    except Exception as err:  # noqa: BLE001
        logging.getLogger(__name__).debug("Creating fresh Bluetooth manager: %s", err)

    bluetooth_adapters = get_adapters()
    bluetooth_storage = BluetoothStorage(hass)
    slot_manager = BleakSlotManager()
    integration_matcher = IntegrationMatcher([])
    integration_matcher.async_setup()
    await passive_update_processor.async_setup(hass)
    await bluetooth_storage.async_setup()
    manager = HomeAssistantBluetoothManager(
        hass, integration_matcher, bluetooth_adapters, bluetooth_storage, slot_manager
    )
    set_manager(manager)
    hass.data[DATA_MANAGER] = manager
    await manager.async_setup()
    hass.config.components.add("bluetooth")
    return manager


async def seed_ble_proxies(
    hass: HomeAssistant,
    proxies: list[tuple[str, str, str, str | None]] | None = None,
) -> dict[str, BaseHaRemoteScanner]:
    """Register real ESPHome BLE proxy devices and `BaseHaRemoteScanner` instances on `hass`."""
    await ensure_bluetooth_manager(hass)
    proxy_specs = (
        proxies
        if proxies is not None
        else [
            ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
            ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
            ("bed_proxy", "aa:bb:cc:00:00:33", "Bedroom Proxy", "bedroom"),
        ]
    )
    scanners_by_source: dict[str, BaseHaRemoteScanner] = hass.data.setdefault(
        _BT_SCANNERS_KEY, {}
    )
    if _BT_UNSUBS_KEY not in hass.data:
        unsubs: list[Callable[[], None]] = []
        hass.data[_BT_UNSUBS_KEY] = unsubs

        def _cleanup_bt_scanners(_event: Any) -> None:
            while unsubs:
                cb = unsubs.pop()
                cb()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _cleanup_bt_scanners)
    else:
        unsubs = hass.data[_BT_UNSUBS_KEY]

    for slug, mac, title, area_id in proxy_specs:
        src_upper = mac.upper()
        if src_upper in scanners_by_source:
            continue
        ce_id = f"esp_{slug}"
        dev = register_device(
            hass,
            config_entry_id=ce_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            identifiers={("esphome", mac)},
            name=title,
            manufacturer="Latter",
            model="esp32-ble-proxy",
            area_id=area_id,
        )
        scanner = BaseHaRemoteScanner(
            src_upper,
            title,
            connector=None,
            connectable=False,
        )
        unsub_setup = scanner.async_setup()
        unsub_reg = bluetooth.async_register_scanner(
            hass,
            scanner,
            source_domain="esphome",
            source_config_entry_id=ce_id,
            source_device_id=dev.id,
        )
        unsubs.extend([unsub_reg, unsub_setup])
        scanners_by_source[src_upper] = scanner

    return scanners_by_source


def make_ibeacon_service_info(
    beacon_uuid: str,
    *,
    rssi: int,
    source: str,
    obs_time: float | None = None,
    address: str = "AA:BB:CC:DD:EE:03",
    major: int = 1,
    minor: int = 1,
    tx_power_1m: int = -59,
    local_name: str = "",
    connectable: bool = False,
    service_data: dict[str, bytes] | None = None,
    service_uuids: list[str] | None = None,
    extra_mfg: dict[int, bytes] | None = None,
) -> BluetoothServiceInfoBleak:
    """Construct a real `BluetoothServiceInfoBleak` iBeacon advertisement packet."""
    mfg: dict[int, bytes] = {}
    if beacon_uuid:
        u_bytes = uuid.UUID(beacon_uuid).bytes
        payload = (
            IBEACON_PREFIX
            + u_bytes
            + major.to_bytes(2, "big")
            + minor.to_bytes(2, "big")
            + bytes([tx_power_1m & 0xFF])
        )
        mfg[APPLE_COMPANY_ID] = payload
    if extra_mfg:
        mfg.update(extra_mfg)

    src_upper = source.upper()
    addr_upper = address.upper()
    ts = time.monotonic() if obs_time is None else float(obs_time)
    svc_data = dict(service_data or {})
    svc_uuids = list(service_uuids or [])
    ble_dev = BLEDevice(addr_upper, local_name or addr_upper, {"source": src_upper})
    adv_data = AdvertisementData(
        local_name=local_name or None,
        manufacturer_data=mfg,
        service_data=svc_data,
        service_uuids=svc_uuids,
        tx_power=tx_power_1m,
        rssi=rssi,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=local_name or addr_upper,
        address=addr_upper,
        rssi=rssi,
        manufacturer_data=mfg,
        service_data=svc_data,
        service_uuids=svc_uuids,
        source=src_upper,
        device=ble_dev,
        advertisement=adv_data,
        connectable=connectable,
        time=ts,
        tx_power=tx_power_1m,
    )


def inject_ble_adv(hass: HomeAssistant, info: BluetoothServiceInfoBleak) -> None:
    """Deliver `info` through its registered `BaseHaRemoteScanner` (or directly into `HomeAssistantBluetoothManager`)."""
    scanners: dict[str, BaseHaRemoteScanner] = hass.data.get(_BT_SCANNERS_KEY, {})
    scanner = scanners.get(info.source.upper())
    if scanner is not None:
        scanner._async_on_advertisement(
            info.address,
            info.rssi,
            info.name if info.name != info.address else None,
            list(info.service_uuids),
            dict(info.service_data),
            dict(info.manufacturer_data),
            info.tx_power,
            {"source": scanner.source},
            info.time,
        )
        return
    bluetooth.async_get_advertisement_callback(hass)(info)


def make_jpeg_bytes(width: int = 320, height: int = 240, color: tuple[int, int, int] = (48, 96, 160)) -> bytes:
    """Encode a real non-progressive Baseline 4:2:0 JPEG via Pillow."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(
        buf, format="JPEG", progressive=False, subsampling=2
    )
    return buf.getvalue()


def install_camera_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    images: Mapping[str, bytes | Exception] | None = None,
    streams: Mapping[str, str | None] | None = None,
    mjpeg_fn: Callable[..., Any] | None = None,
) -> tuple[dict[str, bytes | Exception], dict[str, str | None]]:
    """Patch `homeassistant.components.camera` snapshot/stream helpers cleanly via `monkeypatch`."""
    img_map: dict[str, bytes | Exception] = dict(images or {})
    stream_map: dict[str, str | None] = dict(streams or {})

    async def _async_get_image(
        _hass: HomeAssistant,
        entity_id: str,
        *_args: Any,
        **_kwargs: Any,
    ) -> ha_camera.Image:
        if entity_id in img_map:
            val = img_map[entity_id]
            if isinstance(val, Exception):
                raise HomeAssistantError(str(val)) from val
            return ha_camera.Image("image/jpeg", val)
        return ha_camera.Image("image/jpeg", make_jpeg_bytes(320, 240))

    async def _async_get_stream_source(
        _hass: HomeAssistant, entity_id: str
    ) -> str | None:
        return stream_map.get(entity_id)

    monkeypatch.setattr(ha_camera, "async_get_image", _async_get_image)
    monkeypatch.setattr(ha_camera, "async_get_stream_source", _async_get_stream_source)
    if mjpeg_fn is not None:
        monkeypatch.setattr(ha_camera, "async_get_mjpeg_stream", mjpeg_fn)
    return img_map, stream_map


def mock_clientsession_get(
    monkeypatch: pytest.MonkeyPatch,
    get_handler: Callable[..., Any],
) -> None:
    """Patch `aiohttp_client.async_get_clientsession` with a local GET handler."""

    def _session_factory(_hass: HomeAssistant) -> Any:
        return SimpleNamespace(get=get_handler)

    monkeypatch.setattr(aiohttp_client, "async_get_clientsession", _session_factory)
