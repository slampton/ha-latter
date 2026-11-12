"""Component stubs for `homeassistant.components.*` (entities, HTTP, Bluetooth, Repairs, WebSocket)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import SimpleNamespace
from typing import Any

import voluptuous as vol

from .optional_deps import build_minimal_baseline_jpeg, ensure_module


def install_fake_ha_components(callback_dec: Callable[..., Any]) -> None:
    """Register stubs for `homeassistant.components.*`."""
    ensure_module("homeassistant.components")
    bt_mod = ensure_module("homeassistant.components.bluetooth")
    cam_mod = ensure_module("homeassistant.components.camera")
    fe_mod = ensure_module("homeassistant.components.frontend")
    net_comp_mod = ensure_module("homeassistant.components.network")
    pc_mod = ensure_module("homeassistant.components.panel_custom")
    ws_mod = ensure_module("homeassistant.components.websocket_api")
    bs_mod = ensure_module("homeassistant.components.binary_sensor")
    dt_comp_mod = ensure_module("homeassistant.components.device_tracker")
    diag_comp_mod = ensure_module("homeassistant.components.diagnostics")
    ffmpeg_mod = ensure_module("homeassistant.components.ffmpeg")
    http_comp_mod = ensure_module("homeassistant.components.http")
    lock_mod = ensure_module("homeassistant.components.lock")
    repairs_comp_mod = ensure_module("homeassistant.components.repairs")
    sensor_comp_mod = ensure_module("homeassistant.components.sensor")

    class _BaseEntity:
        hass: Any = None
        entity_id: str | None = None
        _attr_has_entity_name: bool = False
        _attr_translation_key: str | None = None
        _attr_unique_id: str | None = None
        _attr_name: str | None = None
        _attr_icon: str | None = None
        _attr_device_info: Any = None
        _attr_entity_category: Any = None
        _attr_entity_registry_enabled_default: bool = True
        _attr_should_poll: bool = False

        def __init__(self) -> None:
            self._on_remove_cbs: list[Callable[[], None]] = []

        @property
        def unique_id(self) -> str | None:
            return self._attr_unique_id

        @property
        def translation_key(self) -> str | None:
            return self._attr_translation_key

        @property
        def has_entity_name(self) -> bool:
            return self._attr_has_entity_name

        @property
        def device_info(self) -> Any:
            return self._attr_device_info

        @property
        def extra_state_attributes(self) -> Mapping[str, Any] | None:
            return getattr(self, "_attr_extra_state_attributes", None)

        def async_on_remove(self, func: Callable[[], None]) -> None:
            cbs = getattr(self, "_on_remove_cbs", None)
            if cbs is None:
                cbs = []
                self._on_remove_cbs = cbs
            cbs.append(func)

        async def async_added_to_hass(self) -> None:
            return None

        async def async_will_remove_from_hass(self) -> None:
            cbs = getattr(self, "_on_remove_cbs", None)
            while cbs:
                cb = cbs.pop()
                cb()

        async def async_remove(self) -> None:
            await self.async_will_remove_from_hass()
            if self.hass is not None and self.entity_id:
                self.hass.states.async_remove(self.entity_id)

        @callback_dec
        def async_write_ha_state(self) -> None:
            if self.hass is None or not self.entity_id:
                return
            if hasattr(self, "is_on"):
                raw = "on" if self.is_on else ("off" if self.is_on is False else "unknown")
            elif hasattr(self, "in_zones"):
                zones = self.in_zones
                raw = "home" if zones else "not_home"
            else:
                val = getattr(self, "native_value", None)
                raw = "unknown" if val is None else str(val)
            self.hass.states.async_set(
                self.entity_id,
                raw,
                attributes=dict(self.extra_state_attributes or {}),
            )

    class SensorDeviceClass(StrEnum):
        DISTANCE = "distance"
        SIGNAL_STRENGTH = "signal_strength"

    class SensorStateClass(StrEnum):
        MEASUREMENT = "measurement"

    class SensorEntity(_BaseEntity):
        _attr_native_value: Any = None
        _attr_native_unit_of_measurement: str | None = None
        _attr_device_class: SensorDeviceClass | None = None
        _attr_state_class: SensorStateClass | None = None

        @property
        def native_value(self) -> Any:
            return self._attr_native_value

    sensor_comp_mod.SensorEntity = SensorEntity  # type: ignore[attr-defined]
    sensor_comp_mod.SensorDeviceClass = SensorDeviceClass  # type: ignore[attr-defined]
    sensor_comp_mod.SensorStateClass = SensorStateClass  # type: ignore[attr-defined]

    class BinarySensorDeviceClass(StrEnum):
        OCCUPANCY = "occupancy"
        MOTION = "motion"
        PRESENCE = "presence"

    class BinarySensorEntity(_BaseEntity):
        _attr_is_on: bool | None = None
        _attr_device_class: BinarySensorDeviceClass | None = None

        @property
        def is_on(self) -> bool | None:
            return self._attr_is_on

    bs_mod.BinarySensorEntity = BinarySensorEntity  # type: ignore[attr-defined]
    bs_mod.BinarySensorDeviceClass = BinarySensorDeviceClass  # type: ignore[attr-defined]

    class SourceType(StrEnum):
        BLUETOOTH_LE = "bluetooth_le"
        GPS = "gps"

    class TrackerEntity(_BaseEntity):
        @property
        def in_zones(self) -> list[str] | None:
            return None

    dt_comp_mod.SourceType = SourceType  # type: ignore[attr-defined]
    dt_comp_mod.TrackerEntity = TrackerEntity  # type: ignore[attr-defined]

    def _async_redact_data(data: Any, to_redact: Iterable[Any]) -> Any:
        redact_keys = set(to_redact)
        if isinstance(data, Mapping):
            return {
                k: ("**REDACTED**" if k in redact_keys else _async_redact_data(v, redact_keys))
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [_async_redact_data(item, redact_keys) for item in data]
        return data

    diag_comp_mod.async_redact_data = _async_redact_data  # type: ignore[attr-defined]
    ffmpeg_mod.get_ffmpeg_manager = lambda hass: SimpleNamespace(binary="ffmpeg")  # type: ignore[attr-defined]

    class HomeAssistantView:
        url: str = ""
        name: str = ""
        requires_auth: bool = True

    @dataclass
    class StaticPathConfig:
        url_path: str
        path: str
        cache_headers: bool = True

    http_comp_mod.HomeAssistantView = HomeAssistantView  # type: ignore[attr-defined]
    http_comp_mod.StaticPathConfig = StaticPathConfig  # type: ignore[attr-defined]

    class LockEntityFeature:
        OPEN = 1

    lock_mod.LockEntityFeature = LockEntityFeature  # type: ignore[attr-defined]

    class RepairsFlow:
        hass: Any

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any = None,
            errors: dict[str, str] | None = None,
            description_placeholders: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
                "description_placeholders": description_placeholders or {},
            }

        def async_create_entry(self, *, title: str = "", data: Mapping[str, Any] | None = None) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": dict(data or {})}

        def async_abort(self, *, reason: str) -> dict[str, Any]:
            return {"type": "abort", "reason": reason}

    class ConfirmRepairFlow(RepairsFlow):
        async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
            if user_input is not None:
                return {"type": "create_entry", "data": {}}
            return {"type": "form", "step_id": "confirm"}

    repairs_comp_mod.RepairsFlow = RepairsFlow  # type: ignore[attr-defined]
    repairs_comp_mod.ConfirmRepairFlow = ConfirmRepairFlow  # type: ignore[attr-defined]

    class BluetoothScanningMode(StrEnum):
        ACTIVE = "active"
        PASSIVE = "passive"

    class BluetoothCallbackMatcher(dict):  # type: ignore[type-arg]
        pass

    def _bt_register_callback(
        hass: Any,
        callback_fn: Callable[..., None],
        matcher: Mapping[str, Any] | None,
        mode: BluetoothScanningMode,
    ) -> Callable[[], None]:
        rec = (callback_fn, dict(matcher or {}), mode)
        bt_list = hass.data.setdefault("_bt_callbacks", [])
        bt_list.append(rec)

        def _unsub() -> None:
            if rec in bt_list:
                bt_list.remove(rec)

        return _unsub

    def _bt_register_advertisement_callback(
        hass: Any,
        callback_fn: Callable[..., None],
        address: str,
    ) -> Callable[[], None]:
        rec = (callback_fn, str(address or "").strip().upper())
        adv_list = hass.data.setdefault("_bt_adv_callbacks", [])
        adv_list.append(rec)

        def _unsub() -> None:
            if rec in adv_list:
                adv_list.remove(rec)

        return _unsub

    bt_mod.BluetoothCallbackMatcher = BluetoothCallbackMatcher  # type: ignore[attr-defined]
    bt_mod.BluetoothScanningMode = BluetoothScanningMode  # type: ignore[attr-defined]
    bt_mod.async_register_callback = _bt_register_callback  # type: ignore[attr-defined]
    bt_mod.async_register_advertisement_callback = _bt_register_advertisement_callback  # type: ignore[attr-defined]
    bt_mod.async_current_scanners = lambda hass: hass.data.get("_bt_scanners", [])  # type: ignore[attr-defined]
    bt_mod.async_scanner_by_source = lambda hass, source: next(  # type: ignore[attr-defined]
        (s for s in hass.data.get("_bt_scanners", []) if getattr(s, "source", None) == source),
        None,
    )

    @dataclass
    class _CameraImage:
        content: bytes
        content_type: str = "image/jpeg"

    async def _camera_get_image(hass: Any, entity_id: str, **kwargs: Any) -> _CameraImage:
        _ = kwargs
        images = hass.data.get("_camera_images", {})
        if entity_id in images:
            raw = images[entity_id]
            if isinstance(raw, Exception):
                raise raw
            return _CameraImage(content=raw)
        return _CameraImage(content=build_minimal_baseline_jpeg(320, 240))

    async def _camera_get_stream_source(hass: Any, entity_id: str) -> str | None:
        return hass.data.get("_camera_streams", {}).get(entity_id)

    cam_mod.async_get_image = _camera_get_image  # type: ignore[attr-defined]
    cam_mod.async_get_stream_source = _camera_get_stream_source  # type: ignore[attr-defined]

    fe_mod.add_extra_js_url = lambda hass, url: hass._extra_js_urls.add(url)  # type: ignore[attr-defined]
    fe_mod.remove_extra_js_url = lambda hass, url: hass._extra_js_urls.discard(url)  # type: ignore[attr-defined]
    fe_mod.async_remove_panel = lambda hass, path, **kw: hass._panels.pop(path, None)  # type: ignore[attr-defined]

    async def _async_get_source_ip(hass: Any, target_ip: Any = None) -> str:
        _ = target_ip
        return str(hass._source_ip)

    net_comp_mod.async_get_source_ip = _async_get_source_ip  # type: ignore[attr-defined]

    async def _register_panel(hass: Any, **kwargs: Any) -> None:
        path = str(kwargs.get("frontend_url_path") or "latter")
        hass._panels[path] = dict(kwargs)

    pc_mod.async_register_panel = _register_panel  # type: ignore[attr-defined]

    class ActiveConnection:
        def __init__(self, user: Any = None) -> None:
            self.user = user or SimpleNamespace(id="admin_user", is_admin=True)
            self.results: list[tuple[int, Any]] = []
            self.errors: list[tuple[int, str, str]] = []
            self.messages: list[dict[str, Any]] = []
            self.subscriptions: dict[int, Callable[[], None]] = {}

        @callback_dec
        def send_result(self, msg_id: int, result: Any = None) -> None:
            self.results.append((msg_id, result))

        @callback_dec
        def send_error(self, msg_id: int, code: str, message: str) -> None:
            self.errors.append((msg_id, code, message))

        @callback_dec
        def send_message(self, msg: dict[str, Any]) -> None:
            self.messages.append(msg)

    def _ws_command(schema_dict: Mapping[str, Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        compiled = vol.Schema({vol.Required("id"): int, **dict(schema_dict)}, extra=vol.PREVENT_EXTRA)

        def _dec(func: Callable[..., Any]) -> Callable[..., Any]:
            func._ws_type = schema_dict.get("type")  # type: ignore[attr-defined]
            func._ws_schema = compiled  # type: ignore[attr-defined]
            return func

        return _dec

    def _ws_require_admin(func: Callable[..., Any]) -> Callable[..., Any]:
        func._ws_require_admin = True  # type: ignore[attr-defined]
        return func

    def _ws_async_response(func: Callable[..., Any]) -> Callable[..., Any]:
        func._ws_async_response = True  # type: ignore[attr-defined]
        return func

    def _ws_register_command(hass: Any, handler: Callable[..., Any]) -> None:
        ws_type = getattr(handler, "_ws_type", handler.__name__)
        hass._ws_commands[str(ws_type)] = handler

    ws_mod.ActiveConnection = ActiveConnection  # type: ignore[attr-defined]
    ws_mod.websocket_command = _ws_command  # type: ignore[attr-defined]
    ws_mod.require_admin = _ws_require_admin  # type: ignore[attr-defined]
    ws_mod.async_response = _ws_async_response  # type: ignore[attr-defined]
    ws_mod.async_register_command = _ws_register_command  # type: ignore[attr-defined]
    ws_mod.event_message = lambda iden, event: {"id": iden, "type": "event", "event": event}  # type: ignore[attr-defined]
