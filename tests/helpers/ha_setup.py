"""Real Home Assistant 2026.11+ registry, config-entry, entity, and service test helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
import json
from types import MappingProxyType, SimpleNamespace
from typing import Any

from homeassistant.components import frontend, network as ha_network
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_platform,
    entity_registry as er,
    floor_registry as fr,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from custom_components.latter.const import (
    DOMAIN,
    MIN_FIRMWARE_SDK_REV,
    SUBENTRY_DEVICE,
)
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
from tests.helpers.service_mocks import (
    RecordedServiceCall,
    get_service_calls,
    install_service_call_recorder,
    mock_service,
    register_common_target_services,
)

_STATIC_PATHS_KEY = "_latter_test_static_paths"


def __getattr_unused__() -> tuple[Any, ...]:
    return (
        FRONTEND_DIR,
        FRONTEND_SRC,
        LATTER_DIR,
        NODE_BIN,
        REPO_ROOT,
        RecordedServiceCall,
        get_service_calls,
        read_py_tree,
        read_ts_tree,
        run_studio_node_esm,
    )


def make_subentry_dict(
    data: Mapping[str, Any],
    *,
    subentry_type: str = SUBENTRY_DEVICE,
    title: str = "Pocket Assistant",
    unique_id: str | None = None,
    subentry_id: str | None = None,
) -> dict[str, Any]:
    """Build a `ConfigSubentryDataWithId` dictionary suitable for `MockConfigEntry(subentries_data=[...])`."""
    item: dict[str, Any] = {
        "data": dict(data),
        "subentry_type": subentry_type,
        "title": title,
        "unique_id": unique_id,
    }
    if subentry_id:
        item["subentry_id"] = subentry_id
    return item


def make_subentry(
    data: Mapping[str, Any],
    *,
    subentry_type: str = SUBENTRY_DEVICE,
    title: str = "Pocket Assistant",
    unique_id: str | None = None,
    subentry_id: str | None = None,
) -> ConfigSubentry:
    """Build a real `ConfigSubentry` suitable for `hass.config_entries.async_add_subentry(entry, sub)`."""
    kwargs: dict[str, Any] = {}
    if subentry_id:
        kwargs["subentry_id"] = subentry_id
    return ConfigSubentry(
        data=MappingProxyType(dict(data)),
        subentry_type=subentry_type,
        title=title,
        unique_id=unique_id,
        **kwargs,
    )


def add_mock_entry(
    hass: HomeAssistant,
    *,
    domain: str = DOMAIN,
    title: str = "Latter",
    data: Mapping[str, Any] | None = None,
    options: Mapping[str, Any] | None = None,
    entry_id: str | None = None,
    unique_id: str | None = None,
    subentries_data: Iterable[Mapping[str, Any] | ConfigSubentry] | None = None,
    version: int = 2,
    source: str = "user",
) -> Any:
    """Create a `MockConfigEntry`, normalize `subentries_data`, add it to `hass`, and return it."""
    from unittest.mock import AsyncMock

    from pytest_homeassistant.common import (
        MockConfigEntry,
        MockModule,
        mock_integration,
    )

    mocked_domains: set[str] = hass.data.setdefault("_latter_test_mocked_domains", set())
    if domain != DOMAIN and domain not in mocked_domains and domain not in hass.config.components:
        mock_integration(
            hass,
            MockModule(
                domain,
                async_setup_entry=AsyncMock(return_value=True),
                async_unload_entry=AsyncMock(return_value=True),
            ),
        )
        mocked_domains.add(domain)

    normalized_subs: list[dict[str, Any]] = []
    for raw_sub in subentries_data or ():
        if isinstance(raw_sub, ConfigSubentry):
            normalized_subs.append(
                make_subentry_dict(
                    raw_sub.data,
                    subentry_type=raw_sub.subentry_type,
                    title=raw_sub.title,
                    unique_id=raw_sub.unique_id,
                    subentry_id=raw_sub.subentry_id,
                )
            )
        else:
            normalized_subs.append(dict(raw_sub))

    kwargs: dict[str, Any] = {
        "domain": domain,
        "title": title,
        "data": dict(data or {}),
        "options": dict(options or {}),
        "unique_id": unique_id,
        "version": version,
        "source": source,
        "subentries_data": normalized_subs,
    }
    if entry_id is not None:
        kwargs["entry_id"] = entry_id
    entry = MockConfigEntry(**kwargs)
    entry.add_to_hass(hass)
    return entry


def ensure_floor(
    hass: HomeAssistant,
    name: str,
    *,
    floor_id: str | None = None,
    level: int | None = None,
    icon: str | None = None,
) -> fr.FloorEntry:
    """Ensure a Floor exists in real `FloorRegistry` with exact `(floor_id, name)`."""
    floor_reg = fr.async_get(hass)
    target_id = floor_id or slugify(name)
    existing = floor_reg.async_get_floor(target_id)
    if existing is None:
        existing = floor_reg.async_get_floor_by_name(name)
    if existing is not None:
        updates: dict[str, Any] = {}
        if existing.name != name:
            updates["name"] = name
        if level is not None and existing.level != level:
            updates["level"] = level
        if icon is not None and existing.icon != icon:
            updates["icon"] = icon
        if updates:
            existing = floor_reg.async_update(existing.floor_id, **updates)
        return existing

    seed_name = target_id if (floor_id and slugify(name) != floor_id) else name
    created = floor_reg.async_create(seed_name, level=level, icon=icon)
    if created.name != name:
        created = floor_reg.async_update(created.floor_id, name=name)
    return created


def ensure_area(
    hass: HomeAssistant,
    name: str,
    *,
    area_id: str | None = None,
    floor_id: str | None = None,
    icon: str | None = None,
    aliases: set[str] | None = None,
) -> ar.AreaEntry:
    """Ensure an Area exists in real `AreaRegistry` with exact `(id, name)`."""
    area_reg = ar.async_get(hass)
    target_id = area_id or slugify(name)
    existing = area_reg.async_get_area(target_id)
    if existing is None and area_id is None:
        existing = area_reg.async_get_area_by_name(name)
    if existing is not None:
        updates: dict[str, Any] = {}
        if existing.name != name:
            updates["name"] = name
        if floor_id is not None and existing.floor_id != floor_id:
            updates["floor_id"] = floor_id
        if icon is not None and existing.icon != icon:
            updates["icon"] = icon
        if aliases is not None:
            updates["aliases"] = aliases
        if updates:
            existing = area_reg.async_update(existing.id, **updates)
        return existing

    seed_name = target_id if (area_id and slugify(name) != area_id) else name
    created = area_reg.async_create(
        seed_name, floor_id=floor_id, icon=icon, aliases=aliases
    )
    if created.name != name:
        created = area_reg.async_update(created.id, name=name)
    return created


def _ensure_entry_for_id(hass: HomeAssistant, config_entry_id: str, domain: str) -> ConfigEntry:
    existing = hass.config_entries.async_get_entry(config_entry_id)
    if existing is not None:
        return existing
    return add_mock_entry(
        hass,
        domain=domain,
        title=config_entry_id,
        entry_id=config_entry_id,
        data={"device_name": config_entry_id.removeprefix("esp_entry_").removeprefix("esp_")},
        version=1,
    )


def register_device(
    hass: HomeAssistant,
    *,
    config_entry_id: str,
    identifiers: set[tuple[str, str]] | None = None,
    connections: set[tuple[str, str]] | None = None,
    name: str | None = None,
    manufacturer: str | None = "Latter",
    model: str | None = None,
    sw_version: str | None = None,
    area_id: str | None = None,
    via_device: tuple[str, str] | None = None,
    via_device_id: str | None = None,
    entry_type: dr.DeviceEntryType | None = None,
    configuration_url: str | None = None,
    config_subentry_id: str | None = None,
    entry_domain: str = "esphome",
) -> dr.DeviceEntry:
    """Create or update a real `DeviceEntry` and optionally assign `area_id`."""
    _ensure_entry_for_id(hass, config_entry_id, entry_domain)
    dev_reg = dr.async_get(hass)
    resolved_via_id = via_device_id
    if resolved_via_id is None and via_device is not None:
        matched_parent = next(
            (d for d in dev_reg.devices.values() if via_device in d.identifiers),
            None,
        )
        if matched_parent is not None:
            resolved_via_id = matched_parent.id
    kwargs: dict[str, Any] = {"config_entry_id": config_entry_id}
    if identifiers is not None:
        kwargs["identifiers"] = identifiers
    if connections is not None:
        kwargs["connections"] = connections
    if name is not None:
        kwargs["name"] = name
    if manufacturer is not None:
        kwargs["manufacturer"] = manufacturer
    if model is not None:
        kwargs["model"] = model
    if sw_version is not None:
        kwargs["sw_version"] = sw_version
    if resolved_via_id is not None:
        kwargs["via_device_id"] = resolved_via_id
    if entry_type is not None:
        kwargs["entry_type"] = entry_type
    if configuration_url is not None:
        kwargs["configuration_url"] = configuration_url
    if config_subentry_id is not None:
        kwargs["config_subentry_id"] = config_subentry_id

    dev = dev_reg.async_get_or_create(**kwargs)
    if area_id is not None:
        if area_id and ar.async_get(hass).async_get_area(area_id) is None:
            ensure_area(hass, area_id.replace("_", " ").title(), area_id=area_id)
        updated = dev_reg.async_update_device(dev.id, area_id=area_id or None)
        if updated is not None:
            dev = updated
    return dev


def register_entity(
    hass: HomeAssistant,
    entity_id: str,
    *,
    platform: str = "esphome",
    unique_id: str | None = None,
    config_entry_id: str | None = None,
    config_entry: ConfigEntry | None = None,
    config_subentry_id: str | None = None,
    device_id: str | None = None,
    area_id: str | None = None,
    original_name: str | None = None,
    original_device_class: str | None = None,
    device_class: str | None = None,
    entity_category: EntityCategory | None = None,
    has_entity_name: bool = False,
    hidden_by: er.RegistryEntryHider | None = None,
    disabled_by: er.RegistryEntryDisabler | None = None,
    translation_key: str | None = None,
    unit_of_measurement: str | None = None,
    supported_features: int = 0,
    capabilities: Mapping[str, Any] | None = None,
) -> er.RegistryEntry:
    """Register an entity in real `EntityRegistry` with exact `entity_id` and optional `area_id`."""
    domain, suggested_object_id = entity_id.split(".", 1)
    resolved_ce = config_entry
    if resolved_ce is None and config_entry_id is not None:
        resolved_ce = _ensure_entry_for_id(hass, config_entry_id, platform)

    ent_reg = er.async_get(hass)
    kwargs: dict[str, Any] = {
        "suggested_object_id": suggested_object_id,
        "has_entity_name": has_entity_name,
        "supported_features": supported_features,
    }
    if resolved_ce is not None:
        kwargs["config_entry"] = resolved_ce
    if config_subentry_id is not None:
        kwargs["config_subentry_id"] = config_subentry_id
    if device_id is not None:
        kwargs["device_id"] = device_id
    if original_name is not None:
        kwargs["original_name"] = original_name
    elif area_id:
        kwargs["original_name"] = suggested_object_id.replace("_", " ").title()
    if original_device_class is not None:
        kwargs["original_device_class"] = original_device_class
    if entity_category is not None:
        kwargs["entity_category"] = entity_category
    if hidden_by is not None:
        kwargs["hidden_by"] = hidden_by
    if disabled_by is not None:
        kwargs["disabled_by"] = disabled_by
    if translation_key is not None:
        kwargs["translation_key"] = translation_key
    if unit_of_measurement is not None:
        kwargs["unit_of_measurement"] = unit_of_measurement
    if capabilities is not None:
        kwargs["capabilities"] = capabilities

    entry = ent_reg.async_get_or_create(
        domain,
        platform,
        unique_id or f"uid_{entity_id}",
        **kwargs,
    )
    updates: dict[str, Any] = {}
    if entry.entity_id != entity_id:
        updates["new_entity_id"] = entity_id
    if area_id is not None:
        if area_id and ar.async_get(hass).async_get_area(area_id) is None:
            ensure_area(hass, area_id.replace("_", " ").title(), area_id=area_id)
        updates["area_id"] = area_id or None
        if area_id and entry.device_id and not entry.name:
            updates["name"] = (
                original_name
                or entry.original_name
                or suggested_object_id.replace("_", " ").title()
            )
    if device_class is not None:
        updates["device_class"] = device_class
    if updates:
        entry = ent_reg.async_update_entity(entry.entity_id, **updates)
    return entry


def get_platform_entities(
    hass: HomeAssistant, platform_name: str, integration_domain: str = DOMAIN
) -> list[Any]:
    """Return live `Entity` instances added by `integration_domain` on `platform_name`."""
    out: list[Any] = []
    for plat in entity_platform.async_get_platforms(hass, integration_domain):
        if plat.domain == platform_name:
            out.extend(plat.entities.values())
    return out


def find_entity_instance(
    hass: HomeAssistant, platform_name: str, entity_id: str, integration_domain: str = DOMAIN
) -> Any:
    """Find a live `Entity` instance by `entity_id` on `platform_name`."""
    for ent in get_platform_entities(hass, platform_name, integration_domain):
        if ent.entity_id == entity_id:
            return ent
    raise AssertionError(f"Entity {entity_id} not found on platform {platform_name}")


def get_registered_panels(hass: HomeAssistant) -> dict[str, Any]:
    """Return registered frontend panels dict (`hass.data[frontend.DATA_PANELS]`)."""
    panels: dict[str, Any] = hass.data.get(frontend.DATA_PANELS, {})
    return panels


def get_extra_js_urls(hass: HomeAssistant) -> set[str]:
    """Return registered frontend extra module URLs (`frontend.DATA_EXTRA_MODULE_URL`)."""
    mgr = hass.data.get(frontend.DATA_EXTRA_MODULE_URL)
    if mgr is None:
        return set()
    urls = getattr(mgr, "urls", None)
    return set(urls) if urls is not None else set()


def get_static_paths(hass: HomeAssistant) -> list[Any]:
    """Return `StaticPathConfig` entries registered via `hass.http.async_register_static_paths`."""
    paths: list[Any] = hass.data.setdefault(_STATIC_PATHS_KEY, [])
    return paths


async def flush_debouncers(hass: HomeAssistant) -> None:
    """Flush pending 200ms `LatterCoordinator` notify debouncers deterministically without sleep."""
    from custom_components.latter.hub_registry import iter_coordinators

    await hass.async_block_till_done()
    fired = False
    for coord in list(iter_coordinators(hass)):
        debouncer = getattr(coord, "_notify_debouncer", None)
        if debouncer is not None and getattr(debouncer, "_execute_at_end_of_timer", False):
            timer = getattr(debouncer, "_timer_task", None)
            if timer is not None:
                timer.cancel()
            debouncer._on_debounce()
            fired = True
    if fired:
        await hass.async_block_till_done()
        for coord in list(iter_coordinators(hass)):
            debouncer = getattr(coord, "_notify_debouncer", None)
            if debouncer is not None and not getattr(debouncer, "_execute_at_end_of_timer", False):
                debouncer.async_cancel()


async def prepare_latter_dependencies(hass: HomeAssistant) -> None:
    """Ensure `http`, `frontend`, `panel_custom`, `network`, and `websocket_api` are ready on `hass`."""
    install_service_call_recorder(hass)
    register_common_target_services(hass)

    static_log = get_static_paths(hass)
    if getattr(hass, "http", None) is None:

        async def _reg_static(configs: list[Any]) -> None:
            static_log.extend(configs)

        hass.http = SimpleNamespace(  # type: ignore[assignment]
            server_port=8123,
            views=[],
            register_view=lambda v: hass.http.views.append(v),  # type: ignore[attr-defined]
            async_register_static_paths=_reg_static,
            register_redirect=lambda *_a, **_kw: None,
        )
    elif not getattr(hass.http, "_latter_static_wrapped", False):
        orig_reg_static = hass.http.async_register_static_paths

        async def _wrapped_reg_static(configs: list[Any]) -> None:
            static_log.extend(configs)
            res = orig_reg_static(configs)
            if asyncio.iscoroutine(res):
                await res

        hass.http.async_register_static_paths = _wrapped_reg_static  # type: ignore[method-assign]
        hass.http._latter_static_wrapped = True  # type: ignore[attr-defined]

    hass.config.components.add("http")

    if "frontend" not in hass.config.components:
        hass.data.setdefault(
            frontend.DATA_EXTRA_MODULE_URL,
            frontend.UrlManager(lambda *_args: None, []),
        )
        hass.data.setdefault(
            frontend.DATA_EXTRA_JS_URL_ES5,
            frontend.UrlManager(lambda *_args: None, []),
        )
        hass.data.setdefault(frontend.DATA_PANELS, {})
        hass.config.components.add("frontend")

    hass.config.components.add("panel_custom")

    if "network" not in hass.config.components:
        hass.config.components.add("network")

        async def _local_source_ip(
            _hass: HomeAssistant, target_ip: Any = None
        ) -> str:
            _ = target_ip
            return str(hass.data.get("_latter_test_source_ip", "192.168.1.50"))

        ha_network.async_get_source_ip = _local_source_ip  # type: ignore[assignment]

    if "websocket_api" not in hass.config.components:
        await async_setup_component(hass, "websocket_api", {})


def seed_esphome_device(
    hass: HomeAssistant,
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
) -> tuple[dr.DeviceEntry, str]:
    """Create a realistic ESPHome config entry, device, entities, and Latter contract actions."""
    install_service_call_recorder(hass)
    esp_entry = add_mock_entry(
        hass,
        domain="esphome",
        title=name,
        data={"device_name": slug},
        entry_id=f"esp_entry_{slug}",
        version=1,
    )
    dev = register_device(
        hass,
        config_entry_id=esp_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        identifiers={("esphome", mac)},
        name=name,
        manufacturer="Latter",
        model=f"{slug}-board",
        sw_version="3.0.0",
        area_id=area_id,
    )
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
    register_entity(
        hass,
        hw_eid,
        platform="esphome",
        config_entry=esp_entry,
        device_id=dev.id,
        original_name="System: Hardware Manifest",
        unique_id=f"{mac.upper()}/0/text_sensor/System: Hardware Manifest",
    )
    hass.states.async_set(hw_eid, manifest_json)

    rpc_eid = f"sensor.{slug}_system_rpc_outbox"
    register_entity(
        hass,
        rpc_eid,
        platform="esphome",
        config_entry=esp_entry,
        device_id=dev.id,
        original_name="System: RPC Outbox",
        unique_id=f"{mac.upper()}/0/text_sensor/System: RPC Outbox",
    )
    hass.states.async_set(rpc_eid, "")

    beacon_eid = f"binary_sensor.{slug}_ble_radio_active"
    register_entity(
        hass,
        beacon_eid,
        platform="esphome",
        config_entry=esp_entry,
        device_id=dev.id,
        original_name="BLE Radio Active",
    )
    hass.states.async_set(beacon_eid, "off")

    if with_speaker:
        spk_eid = f"media_player.{slug}_music"
        register_entity(
            hass,
            spk_eid,
            platform="esphome",
            config_entry=esp_entry,
            device_id=dev.id,
            original_name="Music",
        )
        hass.states.async_set(
            spk_eid,
            "idle",
            {"volume_level": 0.5, "friendly_name": f"{name} Speaker"},
        )

    for svc_suffix in (
        "latter_ping",
        "latter_push_v3",
        "latter_set_beacon_uuid",
        "latter_device_command",
        "latter_set_slots",
        "latter_set_music_lyrics",
        "latter_set_calendar_view",
        "latter_show_notification",
        "latter_factory_reset",
    ):
        mock_service(hass, "esphome", f"{slug}_{svc_suffix}")

    return dev, mac
