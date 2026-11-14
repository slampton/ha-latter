"""In-memory Area, Device, Entity, and Issue Registry stubs for `homeassistant.helpers.*`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Any

from .optional_deps import ensure_module

EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"
CONNECTION_NETWORK_MAC = "mac"
EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"


def format_mac(mac: str) -> str:
    """Normalize a 12-hex-digit MAC address to lowercase colon-separated form."""
    hex_only = re.sub(r"[^0-9a-fA-F]", "", str(mac or ""))
    if len(hex_only) == 12:
        return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2)).lower()
    return str(mac or "").strip().lower()


def install_fake_ha_registries(slugify_fn: Callable[..., str], entity_category_cls: Any) -> dict[str, Any]:
    """Register `area_registry`, `device_registry`, `entity_registry`, and `issue_registry` stubs."""
    ar_mod = ensure_module("homeassistant.helpers.area_registry")
    dr_mod = ensure_module("homeassistant.helpers.device_registry")
    er_mod = ensure_module("homeassistant.helpers.entity_registry")
    ir_mod = ensure_module("homeassistant.helpers.issue_registry")

    @dataclass
    class AreaEntry:
        id: str
        name: str
        floor_id: str | None = None
        icon: str | None = None
        aliases: set[str] = field(default_factory=set)

    class AreaRegistry:
        def __init__(self, hass: Any) -> None:
            self._hass = hass
            self.areas: dict[str, AreaEntry] = {}

        def async_list_areas(self) -> list[AreaEntry]:
            return list(self.areas.values())

        def async_get_area(self, area_id: str) -> AreaEntry | None:
            return self.areas.get(area_id)

        def async_get_area_by_name(self, name: str) -> AreaEntry | None:
            low = name.strip().lower()
            for a in self.areas.values():
                if a.name.lower() == low:
                    return a
            return None

        def async_create(
            self,
            name: str,
            *,
            area_id: str | None = None,
            floor_id: str | None = None,
            icon: str | None = None,
        ) -> AreaEntry:
            aid = area_id or slugify_fn(name)
            entry = AreaEntry(id=aid, name=name, floor_id=floor_id, icon=icon)
            self.areas[aid] = entry
            self._hass.bus.async_fire(EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": aid})
            return entry

        def async_update(
            self,
            area_id: str,
            *,
            name: str | None = None,
            floor_id: str | None = None,
            icon: Any = ...,
        ) -> AreaEntry:
            entry = self.areas[area_id]
            if name is not None:
                entry.name = name
            if floor_id is not None:
                entry.floor_id = floor_id
            if icon is not ...:
                entry.icon = icon
            self._hass.bus.async_fire(EVENT_AREA_REGISTRY_UPDATED, {"action": "update", "area_id": area_id})
            return entry

        def async_delete(self, area_id: str) -> None:
            if area_id in self.areas:
                self.areas.pop(area_id)
                self._hass.bus.async_fire(EVENT_AREA_REGISTRY_UPDATED, {"action": "remove", "area_id": area_id})

    ar_mod.AreaEntry = AreaEntry  # type: ignore[attr-defined]
    ar_mod.AreaRegistry = AreaRegistry  # type: ignore[attr-defined]
    ar_mod.EVENT_AREA_REGISTRY_UPDATED = EVENT_AREA_REGISTRY_UPDATED  # type: ignore[attr-defined]
    ar_mod.async_get = lambda hass: hass._area_registry  # type: ignore[attr-defined]

    class DeviceEntryType(StrEnum):
        SERVICE = "service"

    class DeviceInfo(dict):  # type: ignore[type-arg]
        pass

    @dataclass
    class DeviceEntry:
        id: str
        identifiers: set[tuple[str, str]] = field(default_factory=set)
        connections: set[tuple[str, str]] = field(default_factory=set)
        config_entries: set[str] = field(default_factory=set)
        config_entries_subentries: dict[str, set[str | None]] = field(default_factory=dict)
        name: str | None = None
        name_by_user: str | None = None
        manufacturer: str | None = None
        model: str | None = None
        sw_version: str | None = None
        area_id: str | None = None
        via_device_id: str | None = None
        entry_type: DeviceEntryType | None = None
        configuration_url: str | None = None
        disabled_by: str | None = None

    class DeviceRegistry:
        def __init__(self, hass: Any) -> None:
            self._hass = hass
            self.devices: dict[str, DeviceEntry] = {}
            self._seq = 0

        def async_get(self, device_id: str) -> DeviceEntry | None:
            return self.devices.get(device_id)

        def async_get_device(
            self,
            identifiers: set[tuple[str, str]] | None = None,
            connections: set[tuple[str, str]] | None = None,
        ) -> DeviceEntry | None:
            norm_conns = (
                {(ct, format_mac(cv) if ct == CONNECTION_NETWORK_MAC else cv) for ct, cv in connections}
                if connections
                else set()
            )
            for dev in self.devices.values():
                if identifiers and (dev.identifiers & identifiers):
                    return dev
                if norm_conns and (dev.connections & norm_conns):
                    return dev
            return None

        def async_get_or_create(
            self,
            *,
            config_entry_id: str,
            config_subentry_id: str | None = None,
            identifiers: set[tuple[str, str]] | None = None,
            connections: set[tuple[str, str]] | None = None,
            name: str | None = None,
            manufacturer: str | None = None,
            model: str | None = None,
            sw_version: str | None = None,
            area_id: str | None = None,
            via_device: tuple[str, str] | None = None,
            via_device_id: str | None = None,
            entry_type: DeviceEntryType | None = None,
            configuration_url: str | None = None,
            device_id: str | None = None,
        ) -> DeviceEntry:
            _ = via_device
            idents = set(identifiers or set())
            conns = {
                (ct, format_mac(cv) if ct == CONNECTION_NETWORK_MAC else cv)
                for ct, cv in (connections or set())
            }
            existing = self.async_get_device(idents, conns)
            if existing is not None:
                existing.config_entries.add(config_entry_id)
                existing.config_entries_subentries.setdefault(config_entry_id, set()).add(config_subentry_id)
                existing.identifiers |= idents
                existing.connections |= conns
                if name is not None:
                    existing.name = name
                if via_device_id is not None:
                    existing.via_device_id = via_device_id
                if configuration_url is not None:
                    existing.configuration_url = configuration_url
                self._hass.bus.async_fire(
                    EVENT_DEVICE_REGISTRY_UPDATED, {"action": "update", "device_id": existing.id}
                )
                return existing
            self._seq += 1
            did = device_id or f"dev_{self._seq}"
            dev = DeviceEntry(
                id=did,
                identifiers=idents,
                connections=conns,
                config_entries={config_entry_id},
                config_entries_subentries={config_entry_id: {config_subentry_id}},
                name=name,
                manufacturer=manufacturer,
                model=model,
                sw_version=sw_version,
                area_id=area_id,
                via_device_id=via_device_id,
                entry_type=entry_type,
                configuration_url=configuration_url,
            )
            self.devices[did] = dev
            self._hass.bus.async_fire(EVENT_DEVICE_REGISTRY_UPDATED, {"action": "create", "device_id": did})
            return dev

        def async_update_device(self, device_id: str, **changes: Any) -> DeviceEntry | None:
            dev = self.devices.get(device_id)
            if dev is None:
                return None
            if "new_identifiers" in changes:
                dev.identifiers = set(changes.pop("new_identifiers"))
            for k, v in changes.items():
                setattr(dev, k, v)
            self._hass.bus.async_fire(EVENT_DEVICE_REGISTRY_UPDATED, {"action": "update", "device_id": device_id})
            return dev

        def async_remove_device(self, device_id: str) -> None:
            if self.devices.pop(device_id, None) is not None:
                self._hass.bus.async_fire(EVENT_DEVICE_REGISTRY_UPDATED, {"action": "remove", "device_id": device_id})

    dr_mod.CONNECTION_NETWORK_MAC = CONNECTION_NETWORK_MAC  # type: ignore[attr-defined]
    dr_mod.DeviceEntry = DeviceEntry  # type: ignore[attr-defined]
    dr_mod.DeviceEntryType = DeviceEntryType  # type: ignore[attr-defined]
    dr_mod.DeviceInfo = DeviceInfo  # type: ignore[attr-defined]
    dr_mod.DeviceRegistry = DeviceRegistry  # type: ignore[attr-defined]
    dr_mod.EVENT_DEVICE_REGISTRY_UPDATED = EVENT_DEVICE_REGISTRY_UPDATED  # type: ignore[attr-defined]
    dr_mod.format_mac = format_mac  # type: ignore[attr-defined]
    dr_mod.async_get = lambda hass: hass._device_registry  # type: ignore[attr-defined]
    dr_mod.async_entries_for_area = lambda reg, area_id: [
        d for d in reg.devices.values() if d.area_id == area_id
    ]  # type: ignore[attr-defined]
    dr_mod.async_entries_for_config_entry = lambda reg, entry_id: [
        d for d in reg.devices.values() if entry_id in d.config_entries
    ]  # type: ignore[attr-defined]

    @dataclass
    class RegistryEntry:
        entity_id: str
        platform: str = "esphome"
        unique_id: str = ""
        device_id: str | None = None
        area_id: str | None = None
        config_entry_id: str | None = None
        config_subentry_id: str | None = None
        name: str | None = None
        original_name: str | None = None
        disabled_by: str | None = None
        hidden_by: str | None = None
        entity_category: Any = None
        translation_key: str | None = None
        original_device_class: str | None = None
        device_class: str | None = None
        has_entity_name: bool = False
        options: dict[str, Any] = field(default_factory=dict)

        @property
        def domain(self) -> str:
            return self.entity_id.split(".", 1)[0]

        @property
        def disabled(self) -> bool:
            return self.disabled_by is not None

    _ = entity_category_cls

    class EntityRegistry:
        def __init__(self, hass: Any) -> None:
            self._hass = hass
            self.entities: dict[str, RegistryEntry] = {}

        def async_get(self, entity_id: str) -> RegistryEntry | None:
            return self.entities.get(entity_id)

        def async_register(self, entry: RegistryEntry) -> RegistryEntry:
            if not entry.unique_id:
                entry.unique_id = f"uid_{entry.entity_id}"
            self.entities[entry.entity_id] = entry
            self._hass.bus.async_fire(
                EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": entry.entity_id}
            )
            return entry

        def async_update_entity(self, entity_id: str, **changes: Any) -> RegistryEntry:
            ent = self.entities[entity_id]
            for k, v in changes.items():
                setattr(ent, k, v)
            self._hass.bus.async_fire(
                EVENT_ENTITY_REGISTRY_UPDATED, {"action": "update", "entity_id": entity_id, "changes": changes}
            )
            return ent

        def async_remove(self, entity_id: str) -> None:
            if self.entities.pop(entity_id, None) is not None:
                self._hass.bus.async_fire(
                    EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": entity_id}
                )

    er_mod.EVENT_ENTITY_REGISTRY_UPDATED = EVENT_ENTITY_REGISTRY_UPDATED  # type: ignore[attr-defined]
    er_mod.EntityRegistry = EntityRegistry  # type: ignore[attr-defined]
    er_mod.RegistryEntry = RegistryEntry  # type: ignore[attr-defined]
    er_mod.async_get = lambda hass: hass._entity_registry  # type: ignore[attr-defined]
    er_mod.async_entries_for_area = lambda reg, area_id: [
        e for e in reg.entities.values() if e.area_id == area_id
    ]  # type: ignore[attr-defined]
    er_mod.async_entries_for_device = lambda reg, device_id, include_disabled_entities=False: [
        e
        for e in reg.entities.values()
        if e.device_id == device_id and (include_disabled_entities or not e.disabled)
    ]  # type: ignore[attr-defined]
    er_mod.async_entries_for_config_entry = lambda reg, entry_id: [
        e for e in reg.entities.values() if e.config_entry_id == entry_id
    ]  # type: ignore[attr-defined]

    class IssueSeverity(StrEnum):
        CRITICAL = "critical"
        ERROR = "error"
        WARNING = "warning"

    @dataclass
    class IssueEntry:
        domain: str
        issue_id: str
        severity: IssueSeverity
        is_fixable: bool = False
        translation_key: str | None = None
        translation_placeholders: dict[str, str] = field(default_factory=dict)
        active: bool = True
        dismissed_version: str | None = None

    class IssueRegistry:
        def __init__(self, hass: Any) -> None:
            self._hass = hass
            self.issues: dict[tuple[str, str], IssueEntry] = {}

        def async_get_issue(self, domain: str, issue_id: str) -> IssueEntry | None:
            return self.issues.get((domain, issue_id))

    def _async_create_issue(
        hass: Any,
        domain: str,
        issue_id: str,
        *,
        is_fixable: bool = False,
        severity: IssueSeverity = IssueSeverity.WARNING,
        translation_key: str | None = None,
        translation_placeholders: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        _ = kwargs
        hass._issue_registry.issues[(domain, issue_id)] = IssueEntry(
            domain=domain,
            issue_id=issue_id,
            severity=severity,
            is_fixable=is_fixable,
            translation_key=translation_key,
            translation_placeholders=dict(translation_placeholders or {}),
        )

    def _async_delete_issue(hass: Any, domain: str, issue_id: str) -> None:
        hass._issue_registry.issues.pop((domain, issue_id), None)

    ir_mod.IssueSeverity = IssueSeverity  # type: ignore[attr-defined]
    ir_mod.async_get = lambda hass: hass._issue_registry  # type: ignore[attr-defined]
    ir_mod.async_create_issue = _async_create_issue  # type: ignore[attr-defined]
    ir_mod.async_delete_issue = _async_delete_issue  # type: ignore[attr-defined]

    return {
        "AreaRegistry": AreaRegistry,
        "DeviceRegistry": DeviceRegistry,
        "EntityRegistry": EntityRegistry,
        "IssueRegistry": IssueRegistry,
    }
