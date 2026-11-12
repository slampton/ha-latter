"""Core `homeassistant.*` runtime, StateMachine, EventBus, ServiceRegistry, ConfigEntry, and helper stubs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
import importlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

import voluptuous as vol

from .fake_ha_components import install_fake_ha_components
from .fake_ha_registries import install_fake_ha_registries
from .optional_deps import ensure_module


def install_fake_ha_core() -> None:
    """Install lightweight in-memory Home Assistant runtime stubs into `sys.modules`."""
    ensure_module("homeassistant")
    const_mod = ensure_module("homeassistant.const")
    core_mod = ensure_module("homeassistant.core")
    exc_mod = ensure_module("homeassistant.exceptions")
    ce_mod = ensure_module("homeassistant.config_entries")
    def_mod = ensure_module("homeassistant.data_entry_flow")
    util_mod = ensure_module("homeassistant.util")
    dt_mod = ensure_module("homeassistant.util.dt")
    ensure_module("homeassistant.helpers")
    cv_mod = ensure_module("homeassistant.helpers.config_validation")
    sel_mod = ensure_module("homeassistant.helpers.selector")
    disc_mod = ensure_module("homeassistant.helpers.discovery_flow")
    aio_client_mod = ensure_module("homeassistant.helpers.aiohttp_client")
    deb_mod = ensure_module("homeassistant.helpers.debounce")
    ep_mod = ensure_module("homeassistant.helpers.entity_platform")
    ev_mod = ensure_module("homeassistant.helpers.event")
    net_helper_mod = ensure_module("homeassistant.helpers.network")
    store_mod = ensure_module("homeassistant.helpers.storage")
    typing_mod = ensure_module("homeassistant.helpers.typing")

    class Platform(StrEnum):
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        DEVICE_TRACKER = "device_tracker"

    class EntityCategory(StrEnum):
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

    const_mod.Platform = Platform  # type: ignore[attr-defined]
    const_mod.EntityCategory = EntityCategory  # type: ignore[attr-defined]
    const_mod.ATTR_ENTITY_ID = "entity_id"  # type: ignore[attr-defined]
    const_mod.EVENT_CORE_CONFIG_UPDATE = "core_config_updated"  # type: ignore[attr-defined]
    const_mod.EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"  # type: ignore[attr-defined]
    const_mod.EVENT_SERVICE_REGISTERED = "service_registered"  # type: ignore[attr-defined]
    const_mod.EVENT_STATE_CHANGED = "state_changed"  # type: ignore[attr-defined]
    const_mod.STATE_ON = "on"  # type: ignore[attr-defined]
    const_mod.STATE_OFF = "off"  # type: ignore[attr-defined]
    const_mod.STATE_OPEN = "open"  # type: ignore[attr-defined]
    const_mod.STATE_CLOSED = "closed"  # type: ignore[attr-defined]
    const_mod.STATE_PLAYING = "playing"  # type: ignore[attr-defined]
    const_mod.STATE_PAUSED = "paused"  # type: ignore[attr-defined]
    const_mod.STATE_IDLE = "idle"  # type: ignore[attr-defined]
    const_mod.STATE_BUFFERING = "buffering"  # type: ignore[attr-defined]
    const_mod.STATE_UNAVAILABLE = "unavailable"  # type: ignore[attr-defined]
    const_mod.STATE_UNKNOWN = "unknown"  # type: ignore[attr-defined]

    class HomeAssistantError(Exception):
        def __init__(
            self,
            *args: Any,
            translation_domain: str | None = None,
            translation_key: str | None = None,
            translation_placeholders: dict[str, str] | None = None,
        ) -> None:
            super().__init__(*args)
            self.translation_domain = translation_domain
            self.translation_key = translation_key
            self.translation_placeholders = translation_placeholders or {}

    class ServiceValidationError(HomeAssistantError):
        pass

    class Unauthorized(HomeAssistantError):
        def __init__(
            self,
            context: Any = None,
            user_id: str | None = None,
            entity_id: str | None = None,
            config_entry_id: str | None = None,
            perm_category: str | None = None,
            permission: str | None = None,
        ) -> None:
            super().__init__("Unauthorized")
            self.context = context
            self.user_id = user_id
            self.entity_id = entity_id
            self.config_entry_id = config_entry_id
            self.perm_category = perm_category
            self.permission = permission

    exc_mod.HomeAssistantError = HomeAssistantError  # type: ignore[attr-defined]
    exc_mod.ServiceValidationError = ServiceValidationError  # type: ignore[attr-defined]
    exc_mod.Unauthorized = Unauthorized  # type: ignore[attr-defined]

    def _slugify(text: str | None, *, separator: str = "_") -> str:
        s = re.sub(r"[^a-z0-9]+", separator, str(text or "").strip().lower())
        return s.strip(separator)

    def _utcnow() -> datetime:
        return datetime.now(UTC)

    def _now(time_zone: Any = None) -> datetime:
        return datetime.now(time_zone or UTC)

    def _as_local(dattim: datetime) -> datetime:
        if dattim.tzinfo is None:
            return dattim.replace(tzinfo=UTC)
        return dattim.astimezone(UTC)

    def _parse_datetime(dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        try:
            cleaned = str(dt_str).strip()
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            parsed = datetime.fromisoformat(cleaned)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    def _parse_date(d_str: str | None) -> date | None:
        if not d_str:
            return None
        try:
            return date.fromisoformat(str(d_str).strip()[:10])
        except ValueError:
            return None

    dt_mod.UTC = UTC  # type: ignore[attr-defined]
    dt_mod.utcnow = _utcnow  # type: ignore[attr-defined]
    dt_mod.now = _now  # type: ignore[attr-defined]
    dt_mod.as_local = _as_local  # type: ignore[attr-defined]
    dt_mod.parse_datetime = _parse_datetime  # type: ignore[attr-defined]
    dt_mod.parse_date = _parse_date  # type: ignore[attr-defined]
    util_mod.dt = dt_mod  # type: ignore[attr-defined]
    util_mod.slugify = _slugify  # type: ignore[attr-defined]

    def callback(func: Callable[..., Any]) -> Callable[..., Any]:
        func._hass_callback = True  # type: ignore[attr-defined]
        return func

    reg_classes = install_fake_ha_registries(_slugify, EntityCategory)
    AreaRegistry = reg_classes["AreaRegistry"]
    DeviceRegistry = reg_classes["DeviceRegistry"]
    EntityRegistry = reg_classes["EntityRegistry"]
    IssueRegistry = reg_classes["IssueRegistry"]

    class SupportsResponse(StrEnum):
        NONE = "none"
        OPTIONAL = "optional"
        ONLY = "only"

    @dataclass
    class Context:
        user_id: str | None = None
        parent_id: str | None = None
        id: str = "ctx_test"

    @dataclass
    class Event:
        event_type: str
        data: dict[str, Any] = field(default_factory=dict)
        context: Context = field(default_factory=Context)
        time_fired: datetime = field(default_factory=_utcnow)

    class State:
        def __init__(
            self,
            entity_id: str,
            state: str,
            attributes: Mapping[str, Any] | None = None,
            last_changed: datetime | None = None,
            last_updated: datetime | None = None,
        ) -> None:
            self.entity_id = entity_id
            self.domain = entity_id.split(".", 1)[0]
            self.object_id = entity_id.split(".", 1)[1] if "." in entity_id else entity_id
            self.state = str(state)
            self.attributes = dict(attributes or {})
            now = _utcnow()
            self.last_changed = last_changed or now
            self.last_updated = last_updated or now

        @property
        def name(self) -> str:
            return str(self.attributes.get("friendly_name") or self.object_id.replace("_", " ").title())

    @dataclass
    class ServiceCall:
        hass: Any
        domain: str
        service: str
        data: dict[str, Any] = field(default_factory=dict)
        context: Context = field(default_factory=Context)
        return_response: bool = False

    class EventBus:
        def __init__(self, hass: HomeAssistant) -> None:
            self._hass = hass
            self._listeners: dict[str, list[Callable[[Event], Any]]] = {}

        @callback
        def async_listen(self, event_type: str, listener: Callable[[Event], Any]) -> Callable[[], None]:
            bucket = self._listeners.setdefault(event_type, [])
            bucket.append(listener)

            def _unsub() -> None:
                if listener in bucket:
                    bucket.remove(listener)

            return _unsub

        @callback
        def async_listen_once(self, event_type: str, listener: Callable[[Event], Any]) -> Callable[[], None]:
            unsub_holder: list[Callable[[], None]] = []

            def _once(event: Event) -> Any:
                if unsub_holder:
                    unsub_holder[0]()
                return listener(event)

            unsub = self.async_listen(event_type, _once)
            unsub_holder.append(unsub)
            return unsub

        @callback
        def async_fire(
            self,
            event_type: str,
            event_data: Mapping[str, Any] | None = None,
            context: Context | None = None,
        ) -> None:
            ev = Event(event_type=event_type, data=dict(event_data or {}), context=context or Context())
            self._hass._fired_events.append(ev)
            for listener in list(self._listeners.get(event_type, [])) + list(self._listeners.get("*", [])):
                res = listener(ev)
                if asyncio.iscoroutine(res):
                    self._hass.async_create_task(res)

    class StateMachine:
        def __init__(self, hass: HomeAssistant) -> None:
            self._hass = hass
            self._states: dict[str, State] = {}

        def get(self, entity_id: str) -> State | None:
            return self._states.get(entity_id)

        def async_entity_ids(self, domain_filter: str | Iterable[str] | None = None) -> list[str]:
            if domain_filter is None:
                return list(self._states.keys())
            domains = {domain_filter} if isinstance(domain_filter, str) else set(domain_filter)
            return [eid for eid, st in self._states.items() if st.domain in domains]

        def async_all(self, domain_filter: str | Iterable[str] | None = None) -> list[State]:
            return [self._states[eid] for eid in self.async_entity_ids(domain_filter)]

        @callback
        def async_set(
            self,
            entity_id: str,
            new_state: str,
            attributes: Mapping[str, Any] | None = None,
            force_update: bool = False,
            context: Context | None = None,
        ) -> None:
            old = self._states.get(entity_id)
            new_attrs = dict(attributes or {})
            if (
                not force_update
                and old is not None
                and old.state == str(new_state)
                and old.attributes == new_attrs
            ):
                return
            now = _utcnow()
            last_changed = (
                old.last_changed
                if (old is not None and old.state == str(new_state))
                else now
            )
            cur = State(
                entity_id,
                str(new_state),
                attributes=new_attrs,
                last_changed=last_changed,
                last_updated=now,
            )
            self._states[entity_id] = cur
            self._hass.bus.async_fire(
                const_mod.EVENT_STATE_CHANGED,
                {"entity_id": entity_id, "old_state": old, "new_state": cur},
                context=context,
            )

        @callback
        def async_remove(self, entity_id: str, context: Context | None = None) -> bool:
            old = self._states.pop(entity_id, None)
            if old is None:
                return False
            self._hass.bus.async_fire(
                const_mod.EVENT_STATE_CHANGED,
                {"entity_id": entity_id, "old_state": old, "new_state": None},
                context=context,
            )
            return True

    class ServiceRegistry:
        def __init__(self, hass: HomeAssistant) -> None:
            self._hass = hass
            self._services: dict[str, dict[str, tuple[Callable[[ServiceCall], Any], Any, SupportsResponse]]] = {}
            self.calls: list[ServiceCall] = []

        def has_service(self, domain: str, service: str) -> bool:
            return service in self._services.get(domain, {})

        def async_services(self) -> dict[str, dict[str, Any]]:
            return {dom: dict(svcs) for dom, svcs in self._services.items()}

        def async_services_for_domain(self, domain: str) -> dict[str, Any]:
            return dict(self._services.get(domain, {}))

        @callback
        def async_register(
            self,
            domain: str,
            service: str,
            service_func: Callable[[ServiceCall], Any],
            schema: Any = None,
            supports_response: SupportsResponse = SupportsResponse.NONE,
        ) -> None:
            self._services.setdefault(domain, {})[service] = (service_func, schema, supports_response)
            self._hass.bus.async_fire(
                const_mod.EVENT_SERVICE_REGISTERED, {"domain": domain, "service": service}
            )

        async def async_call(
            self,
            domain: str,
            service: str,
            service_data: Mapping[str, Any] | None = None,
            blocking: bool = False,
            context: Context | None = None,
            target: Mapping[str, Any] | None = None,
            return_response: bool = False,
        ) -> Any:
            _ = blocking
            merged = dict(service_data or {})
            if target:
                for k, v in target.items():
                    merged.setdefault(k, v)
            reg = self._services.get(domain, {}).get(service)
            if reg is not None:
                func, schema, _sup = reg
                validated = schema(merged) if callable(schema) else merged
                call = ServiceCall(
                    hass=self._hass,
                    domain=domain,
                    service=service,
                    data=dict(validated),
                    context=context or Context(),
                    return_response=return_response,
                )
                self.calls.append(call)
                res = func(call)
                if asyncio.iscoroutine(res):
                    res = await res
                return res if return_response else None
            call = ServiceCall(
                hass=self._hass,
                domain=domain,
                service=service,
                data=merged,
                context=context or Context(),
                return_response=return_response,
            )
            self.calls.append(call)
            return {} if return_response else None

    FlowResult = dict[str, Any]
    def_mod.FlowResult = FlowResult  # type: ignore[attr-defined]

    class ConfigEntryState(StrEnum):
        LOADED = "loaded"
        SETUP_IN_PROGRESS = "setup_in_progress"
        NOT_LOADED = "not_loaded"
        SETUP_ERROR = "setup_error"

    @dataclass
    class ConfigSubentry:
        data: Mapping[str, Any]
        subentry_type: str
        title: str
        unique_id: str | None = None
        subentry_id: str = "sub_default"

    class ConfigSubentryData(dict):  # type: ignore[type-arg]
        pass

    class ConfigEntry:
        def __init__(
            self,
            *,
            entry_id: str = "entry_latter_hub",
            domain: str = "latter",
            title: str = "Latter",
            data: Mapping[str, Any] | None = None,
            options: Mapping[str, Any] | None = None,
            subentries_data: Iterable[ConfigSubentry] | None = None,
            state: ConfigEntryState = ConfigEntryState.LOADED,
            unique_id: str | None = None,
        ) -> None:
            self.entry_id = entry_id
            self.domain = domain
            self.title = title
            self.data = dict(data or {})
            self.options = dict(options or {})
            self.subentries: dict[str, ConfigSubentry] = {
                s.subentry_id: s for s in (subentries_data or [])
            }
            self.state = state
            self.unique_id = unique_id
            self.version: int = 2
            self._unload_callbacks: list[Callable[[], None]] = []
            self._update_listeners: list[Callable[[HomeAssistant, ConfigEntry], Any]] = []
            self.runtime_data: Any = None

        def async_on_unload(self, func: Callable[[], Any]) -> None:
            self._unload_callbacks.append(func)

        def add_update_listener(self, listener: Callable[[HomeAssistant, ConfigEntry], Any]) -> Callable[[], None]:
            self._update_listeners.append(listener)

            def _remove() -> None:
                if listener in self._update_listeners:
                    self._update_listeners.remove(listener)

            return _remove

        def async_create_background_task(
            self, hass: HomeAssistant, target: Any, name: str, eager_start: bool = True
        ) -> asyncio.Task[Any]:
            return hass.async_create_task(target, name=name, eager_start=eager_start)

    class ConfigEntriesManager:
        def __init__(self, hass: HomeAssistant) -> None:
            self._hass = hass
            self._entries: dict[str, ConfigEntry] = {}
            self.forwarded_platforms: list[tuple[str, tuple[str, ...]]] = []
            self.unloaded_platforms: list[tuple[str, tuple[str, ...]]] = []
            self.reloaded_entries: list[str] = []
            self._in_progress_flows: list[dict[str, Any]] = []
            self.aborted_flow_ids: list[str] = []

            def _abort_flow(flow_id: str) -> None:
                self.aborted_flow_ids.append(flow_id)
                self._in_progress_flows[:] = [
                    f for f in self._in_progress_flows if f.get("flow_id") != flow_id
                ]

            self.flow = SimpleNamespace(
                async_progress_by_handler=lambda domain: [
                    f for f in self._in_progress_flows if f.get("handler") == domain
                ],
                async_abort=_abort_flow,
            )

        def add_entry(self, entry: ConfigEntry) -> ConfigEntry:
            self._entries[entry.entry_id] = entry
            return entry

        def async_entries(self, domain: str | None = None) -> list[ConfigEntry]:
            if domain is None:
                return list(self._entries.values())
            return [e for e in self._entries.values() if e.domain == domain]

        def async_get_entry(self, entry_id: str) -> ConfigEntry | None:
            return self._entries.get(entry_id)

        @callback
        def async_update_entry(
            self,
            entry: ConfigEntry,
            *,
            data: Mapping[str, Any] | None = None,
            options: Mapping[str, Any] | None = None,
            title: str | None = None,
            unique_id: str | None = None,
        ) -> bool:
            if data is not None:
                entry.data = dict(data)
            if options is not None:
                entry.options = dict(options)
            if title is not None:
                entry.title = title
            if unique_id is not None:
                entry.unique_id = unique_id
            for listener in list(entry._update_listeners):
                res = listener(self._hass, entry)
                if asyncio.iscoroutine(res):
                    self._hass.async_create_task(res)
            return True

        @callback
        def async_add_subentry(self, entry: ConfigEntry, subentry: ConfigSubentry) -> bool:
            entry.subentries[subentry.subentry_id] = subentry
            return True

        @callback
        def async_update_subentry(
            self,
            entry: ConfigEntry,
            subentry: ConfigSubentry,
            *,
            data: Mapping[str, Any] | None = None,
            title: str | None = None,
            unique_id: str | None = None,
        ) -> bool:
            new_sub = ConfigSubentry(
                data=dict(data) if data is not None else dict(subentry.data),
                subentry_type=subentry.subentry_type,
                title=title if title is not None else subentry.title,
                unique_id=unique_id if unique_id is not None else subentry.unique_id,
                subentry_id=subentry.subentry_id,
            )
            entry.subentries[subentry.subentry_id] = new_sub
            return True

        async def async_remove_subentry(self, entry_id: str, subentry_id: str) -> bool:
            entry = self._entries.get(entry_id)
            if entry is None or subentry_id not in entry.subentries:
                return False
            entry.subentries.pop(subentry_id, None)
            return True

        @callback
        def async_schedule_reload(self, entry_id: str) -> None:
            self.reloaded_entries.append(entry_id)

        async def async_forward_entry_setups(self, entry: ConfigEntry, platforms: Iterable[Any]) -> None:
            names = tuple(str(p) for p in platforms)
            self.forwarded_platforms.append((entry.entry_id, names))
            for p_name in names:
                mod = importlib.import_module(f"custom_components.{entry.domain}.{p_name}")
                setup_fn = getattr(mod, "async_setup_entry", None)
                if callable(setup_fn):
                    added: list[tuple[list[Any], str | None]] = []

                    def _add_entities(
                        entities: Iterable[Any],
                        update_before_add: bool = False,
                        *,
                        config_subentry_id: str | None = None,
                        _added: list[tuple[list[Any], str | None]] = added,
                        _platform_name: str = p_name,
                    ) -> None:
                        _ = update_before_add
                        ent_list = list(entities)
                        _added.append((ent_list, config_subentry_id))
                        for ent in ent_list:
                            ent.hass = self._hass
                            if not getattr(ent, "entity_id", None):
                                key = getattr(ent, "translation_key", None) or getattr(ent, "unique_id", "entity")
                                ent.entity_id = f"{_platform_name}.{_slugify(str(key))}"
                            add_hook = getattr(ent, "async_added_to_hass", None)
                            if callable(add_hook):
                                res = add_hook()
                                if asyncio.iscoroutine(res):
                                    self._hass.async_create_task(res)
                            ent.async_write_ha_state()
                        self._hass.data.setdefault("_test_entities", {}).setdefault(_platform_name, []).extend(ent_list)

                    await setup_fn(self._hass, entry, _add_entities)

        async def async_unload_platforms(self, entry: ConfigEntry, platforms: Iterable[Any]) -> bool:
            names = tuple(str(p) for p in platforms)
            self.unloaded_platforms.append((entry.entry_id, names))
            for p_name in names:
                for ent in list(self._hass.data.get("_test_entities", {}).get(p_name, [])):
                    rem_hook = getattr(ent, "async_will_remove_from_hass", None)
                    if callable(rem_hook):
                        res = rem_hook()
                        if asyncio.iscoroutine(res):
                            await res
            while entry._unload_callbacks:
                cb = entry._unload_callbacks.pop()
                res = cb()
                if asyncio.iscoroutine(res):
                    await res
            return True

    class HomeAssistant:
        def __init__(self, config_dir: Path | str | None = None) -> None:
            root = Path(config_dir or Path.cwd())
            self.data: dict[str, Any] = {}
            self.is_running: bool = True
            self._fired_events: list[Event] = []
            self._background_tasks: list[asyncio.Task[Any]] = []
            self._timers: list[tuple[Any, Callable[..., Any]]] = []
            self._users: dict[str, Any] = {
                "admin_user": SimpleNamespace(id="admin_user", is_admin=True, is_active=True, name="Admin"),
                "regular_user": SimpleNamespace(id="regular_user", is_admin=False, is_active=True, name="Guest"),
            }
            self.config = SimpleNamespace(
                config_dir=str(root),
                latitude=37.8044,
                longitude=-122.2712,
                location_name="Oakland Site",
                units=SimpleNamespace(temperature_unit="°F"),
                path=lambda *parts: str(root.joinpath(*parts)),
                components={"esphome", "bluetooth", "http", "frontend", "panel_custom"},
            )
            self.bus = EventBus(self)
            self.states = StateMachine(self)
            self.services = ServiceRegistry(self)
            self.config_entries = ConfigEntriesManager(self)
            self.auth = SimpleNamespace(async_get_user=self._async_get_user)
            self.http = SimpleNamespace(
                server_port=8123,
                views=[],
                static_paths=[],
                register_view=lambda v: self.http.views.append(v),
                async_register_static_paths=self._async_register_static_paths,
            )
            self._area_registry = AreaRegistry(self)
            self._device_registry = DeviceRegistry(self)
            self._entity_registry = EntityRegistry(self)
            self._issue_registry = IssueRegistry(self)
            self._ws_commands: dict[str, Callable[..., Any]] = {}
            self._panels: dict[str, dict[str, Any]] = {}
            self._extra_js_urls: set[str] = set()
            self._storage_mem: dict[str, Any] = {}
            self._source_ip: str = "192.168.1.50"

        async def _async_get_user(self, user_id: str) -> Any:
            return self._users.get(user_id)

        async def _async_register_static_paths(self, configs: list[Any]) -> None:
            self.http.static_paths.extend(configs)

        def async_create_task(self, target: Any, name: str | None = None, eager_start: bool = False) -> asyncio.Task[Any]:
            _ = eager_start
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(target, name=name)
                self._background_tasks.append(task)
                return task
            except RuntimeError:
                if asyncio.iscoroutine(target):
                    target.close()
                raise

        def async_create_background_task(
            self, target: Any, name: str | None = None, eager_start: bool = True
        ) -> asyncio.Task[Any]:
            return self.async_create_task(target, name=name, eager_start=eager_start)

        async def async_add_executor_job(self, target: Callable[..., Any], *args: Any) -> Any:
            return target(*args)

        async def async_block_till_done(self) -> None:
            pending = [t for t in self._background_tasks if not t.done()]
            while pending:
                await asyncio.gather(*pending, return_exceptions=True)
                pending = [t for t in self._background_tasks if not t.done()]

    core_mod.HomeAssistant = HomeAssistant  # type: ignore[attr-defined]
    core_mod.State = State  # type: ignore[attr-defined]
    core_mod.Event = Event  # type: ignore[attr-defined]
    core_mod.Context = Context  # type: ignore[attr-defined]
    core_mod.ServiceCall = ServiceCall  # type: ignore[attr-defined]
    core_mod.SupportsResponse = SupportsResponse  # type: ignore[attr-defined]
    core_mod.ServiceResponse = dict[str, Any] | None  # type: ignore[attr-defined]
    core_mod.EventStateChangedData = dict[str, Any]  # type: ignore[attr-defined]
    core_mod.callback = callback  # type: ignore[attr-defined]

    class AbortFlow(Exception):
        def __init__(self, reason: str) -> None:
            super().__init__(reason)
            self.reason = reason

    class ConfigFlow:
        def __init_subclass__(cls, *, domain: str | None = None, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            if domain:
                cls._domain = domain

        def __init__(self) -> None:
            self.hass: HomeAssistant = None  # type: ignore[assignment]
            self.context: dict[str, Any] = {}
            self.flow_id: str = "flow_user_1"
            self._unique_id: str | None = None

        async def async_set_unique_id(self, unique_id: str, *, raise_on_progress: bool = True) -> None:
            _ = raise_on_progress
            self._unique_id = unique_id

        def _abort_if_unique_id_configured(self, updates: Mapping[str, Any] | None = None) -> None:
            _ = updates
            for entry in self.hass.config_entries.async_entries(getattr(self, "_domain", "latter")):
                if entry.unique_id == self._unique_id:
                    raise AbortFlow("already_configured")

        def _async_current_entries(self) -> list[ConfigEntry]:
            return self.hass.config_entries.async_entries(getattr(self, "_domain", "latter"))

        def _get_reconfigure_entry(self) -> ConfigEntry:
            eid = self.context.get("entry_id")
            if eid and (e := self.hass.config_entries.async_get_entry(eid)):
                return e
            return self._async_current_entries()[0]

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

        def async_create_entry(
            self,
            *,
            title: str,
            data: Mapping[str, Any],
            options: Mapping[str, Any] | None = None,
            subentries: Iterable[Mapping[str, Any]] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "create_entry",
                "title": title,
                "data": dict(data),
                "options": dict(options or {}),
                "subentries": list(subentries or []),
            }

        def async_abort(self, *, reason: str) -> dict[str, Any]:
            return {"type": "abort", "reason": reason}

        def async_update_reload_and_abort(
            self,
            entry: ConfigEntry,
            *,
            data_updates: Mapping[str, Any] | None = None,
            reason: str = "reconfigure_successful",
        ) -> dict[str, Any]:
            if data_updates:
                merged = dict(entry.data)
                merged.update(data_updates)
                self.hass.config_entries.async_update_entry(entry, data=merged)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return {"type": "abort", "reason": reason}

        def async_update_and_abort(
            self,
            entry: ConfigEntry,
            *,
            data_updates: Mapping[str, Any] | None = None,
            reason: str = "reconfigure_successful",
        ) -> dict[str, Any]:
            return self.async_update_reload_and_abort(entry, data_updates=data_updates, reason=reason)

    class ConfigSubentryFlow:
        def __init__(self) -> None:
            self.hass: HomeAssistant = None  # type: ignore[assignment]
            self.context: dict[str, Any] = {}
            self._entry: ConfigEntry | None = None
            self._subentry: ConfigSubentry | None = None

        def _get_entry(self) -> ConfigEntry:
            if self._entry is not None:
                return self._entry
            return self.hass.config_entries.async_entries("latter")[0]

        def _get_reconfigure_subentry(self) -> ConfigSubentry:
            if self._subentry is not None:
                return self._subentry
            return next(iter(self._get_entry().subentries.values()))

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

        def async_create_entry(
            self, *, title: str, data: Mapping[str, Any], unique_id: str | None = None
        ) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": dict(data), "unique_id": unique_id}

        def async_abort(self, *, reason: str) -> dict[str, Any]:
            return {"type": "abort", "reason": reason}

        def async_update_and_abort(
            self,
            entry: ConfigEntry,
            subentry: ConfigSubentry,
            *,
            data: Mapping[str, Any] | None = None,
            title: str | None = None,
            unique_id: str | None = None,
        ) -> dict[str, Any]:
            self.hass.config_entries.async_update_subentry(
                entry, subentry, data=data, title=title, unique_id=unique_id
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return {"type": "abort", "reason": "reconfigure_successful"}

    class OptionsFlow:
        def __init__(self) -> None:
            self.hass: HomeAssistant = None  # type: ignore[assignment]
            self.config_entry: ConfigEntry = None  # type: ignore[assignment]

        def async_show_form(self, *, step_id: str, data_schema: Any = None, errors: dict[str, str] | None = None) -> dict[str, Any]:
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors or {}}

        def async_create_entry(self, *, title: str = "", data: Mapping[str, Any] | None = None) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": dict(data or {})}

    ce_mod.ConfigEntry = ConfigEntry  # type: ignore[attr-defined]
    ce_mod.ConfigEntryState = ConfigEntryState  # type: ignore[attr-defined]
    ce_mod.ConfigFlow = ConfigFlow  # type: ignore[attr-defined]
    ce_mod.ConfigFlowResult = FlowResult  # type: ignore[attr-defined]
    ce_mod.ConfigSubentry = ConfigSubentry  # type: ignore[attr-defined]
    ce_mod.ConfigSubentryData = ConfigSubentryData  # type: ignore[attr-defined]
    ce_mod.ConfigSubentryFlow = ConfigSubentryFlow  # type: ignore[attr-defined]
    ce_mod.OptionsFlow = OptionsFlow  # type: ignore[attr-defined]
    ce_mod.SOURCE_INTEGRATION_DISCOVERY = "integration_discovery"  # type: ignore[attr-defined]
    ce_mod.SubentryFlowResult = FlowResult  # type: ignore[attr-defined]

    def _cv_boolean(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        s = str(val).strip().lower()
        if s in ("true", "1", "yes", "on", "enable"):
            return True
        if s in ("false", "0", "no", "off", "disable"):
            return False
        raise vol.Invalid(f"Invalid boolean {val!r}")

    def _cv_entity_ids(val: Any) -> list[str]:
        items = (
            [s.strip() for s in val.split(",") if s.strip()]
            if isinstance(val, str)
            else [str(x).strip() for x in val]
        )
        for eid in items:
            if "." not in eid:
                raise vol.Invalid(f"Invalid entity_id {eid!r}")
        return items

    def _cv_entity_domain(domain: str) -> Callable[[Any], str]:
        def _validate(val: Any) -> str:
            s = str(val).strip()
            if not s.startswith(f"{domain}."):
                raise vol.Invalid(f"Entity {s!r} does not belong to domain {domain!r}")
            return s

        return _validate

    cv_mod.string = lambda v: str(v) if v is not None else (_ for _ in ()).throw(vol.Invalid("None is not string"))  # type: ignore[attr-defined]
    cv_mod.boolean = _cv_boolean  # type: ignore[attr-defined]
    cv_mod.entity_ids = _cv_entity_ids  # type: ignore[attr-defined]
    cv_mod.entity_domain = _cv_entity_domain  # type: ignore[attr-defined]
    cv_mod.config_entry_only_config_schema = lambda _domain: lambda cfg: cfg  # type: ignore[attr-defined]

    class _SelectorPassthrough:
        def __init__(self, config: Any = None) -> None:
            self.config = config

        def __call__(self, val: Any) -> Any:
            return val

    class SelectSelectorMode(StrEnum):
        DROPDOWN = "dropdown"
        LIST = "list"

    sel_mod.BooleanSelector = _SelectorPassthrough  # type: ignore[attr-defined]
    sel_mod.DeviceSelector = _SelectorPassthrough  # type: ignore[attr-defined]
    sel_mod.DeviceSelectorConfig = lambda **kw: kw  # type: ignore[attr-defined]
    sel_mod.EntitySelector = _SelectorPassthrough  # type: ignore[attr-defined]
    sel_mod.EntitySelectorConfig = lambda **kw: kw  # type: ignore[attr-defined]
    sel_mod.SelectOptionDict = dict  # type: ignore[attr-defined]
    sel_mod.SelectSelector = _SelectorPassthrough  # type: ignore[attr-defined]
    sel_mod.SelectSelectorConfig = lambda **kw: kw  # type: ignore[attr-defined]
    sel_mod.SelectSelectorMode = SelectSelectorMode  # type: ignore[attr-defined]
    sel_mod.TextSelector = _SelectorPassthrough  # type: ignore[attr-defined]

    disc_mod.async_create_flow = lambda hass, domain, context, data: hass.config_entries._in_progress_flows.append(  # type: ignore[attr-defined]
        {"handler": domain, "context": context, "data": data}
    )

    class _StubClientSession:
        def __init__(self, hass: HomeAssistant) -> None:
            self._hass = hass

        def get(self, url: str, timeout: Any = None, headers: Any = None, **kwargs: Any) -> Any:
            _ = (timeout, headers)
            handler = self._hass.data.get("_mock_http_get")
            if callable(handler):
                try:
                    return handler(url, **kwargs)
                except TypeError:
                    return handler(url)
            raise RuntimeError(f"Unmocked HTTP GET {url}")

    aio_client_mod.async_get_clientsession = lambda hass: _StubClientSession(hass)  # type: ignore[attr-defined]

    class Debouncer:
        def __init__(
            self,
            hass: HomeAssistant,
            logger: Any,
            *,
            cooldown: float,
            immediate: bool,
            function: Callable[[], Any],
        ) -> None:
            self.hass = hass
            self.logger = logger
            self.cooldown = cooldown
            self.immediate = immediate
            self.function = function
            self._cancelled = False
            self._in_flight = False
            self.scheduled_count = 0

        @callback
        def async_schedule_call(self) -> None:
            self._cancelled = False
            self.scheduled_count += 1
            if self._in_flight:
                return
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return

            async def _runner() -> None:
                try:
                    if not self._cancelled:
                        res = self.function()
                        if asyncio.iscoroutine(res):
                            await res
                finally:
                    self._in_flight = False

            self._in_flight = True
            self.hass.async_create_task(_runner(), name="debouncer_call")

        async def async_call(self) -> None:
            if self._cancelled:
                return
            res = self.function()
            if asyncio.iscoroutine(res):
                await res

        @callback
        def async_cancel(self) -> None:
            self._cancelled = True

        def __class_getitem__(cls, _item: Any) -> type[Debouncer]:
            return cls

    deb_mod.Debouncer = Debouncer  # type: ignore[attr-defined]
    ep_mod.AddConfigEntryEntitiesCallback = Callable[..., None]  # type: ignore[attr-defined]
    typing_mod.ConfigType = dict[str, Any]  # type: ignore[attr-defined]

    def _track_state_change_event(
        hass: HomeAssistant, entity_ids: Iterable[str] | str, action: Callable[[Event], Any]
    ) -> Callable[[], None]:
        tracked = {entity_ids} if isinstance(entity_ids, str) else set(entity_ids)

        @callback
        def _listener(event: Event) -> None:
            if event.data.get("entity_id") in tracked:
                res = action(event)
                if asyncio.iscoroutine(res):
                    hass.async_create_task(res)

        return hass.bus.async_listen(const_mod.EVENT_STATE_CHANGED, _listener)

    def _track_time_interval(
        hass: HomeAssistant, action: Callable[[datetime], Any], interval: timedelta
    ) -> Callable[[], None]:
        rec = (interval, action)
        hass._timers.append(rec)

        def _unsub() -> None:
            if rec in hass._timers:
                hass._timers.remove(rec)

        return _unsub

    def _call_later(hass: HomeAssistant, delay: float, action: Callable[[datetime], Any]) -> Callable[[], None]:
        rec = (delay, action)
        hass._timers.append(rec)

        def _unsub() -> None:
            if rec in hass._timers:
                hass._timers.remove(rec)

        return _unsub

    ev_mod.async_track_state_change_event = _track_state_change_event  # type: ignore[attr-defined]
    ev_mod.async_track_time_interval = _track_time_interval  # type: ignore[attr-defined]
    ev_mod.async_call_later = _call_later  # type: ignore[attr-defined]

    net_helper_mod.get_url = lambda hass, **kw: hass.data.get(  # type: ignore[attr-defined]
        "_internal_url", "http://homeassistant.local:8123"
    )

    class Store:
        def __init__(self, hass: HomeAssistant, version: int, key: str) -> None:
            self.hass = hass
            self.version = version
            self.key = key
            self._delayed_producer: Callable[[], Any] | None = None

        async def async_load(self) -> Any:
            if self.key in self.hass._storage_mem:
                return json.loads(json.dumps(self.hass._storage_mem[self.key]))
            return None

        async def async_save(self, data: Any) -> None:
            self.hass._storage_mem[self.key] = json.loads(json.dumps(data))
            self._delayed_producer = None

        @callback
        def async_delay_save(self, data_func: Callable[[], Any], delay: float = 0.0) -> None:
            _ = delay
            self._delayed_producer = data_func
            self.hass._storage_mem[self.key] = json.loads(json.dumps(data_func()))

        async def async_remove(self) -> None:
            self.hass._storage_mem.pop(self.key, None)
            self._delayed_producer = None

        def __class_getitem__(cls, _item: Any) -> type[Store]:
            return cls

    store_mod.Store = Store  # type: ignore[attr-defined]

    install_fake_ha_components(callback)
