"""Reactive O(1) per-Area and per-domain entity state index for Latter.

Eliminates full `StateMachine` scans by indexing Entity/Device/Area registries once and
maintaining live domain sets + media-position-filtered Area change notifications.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ..const import DOMAIN

INDEXED_DOMAINS: frozenset[str] = frozenset(
    {
        "alarm_control_panel",
        "binary_sensor",
        "button",
        "calendar",
        "camera",
        "climate",
        "cover",
        "device_tracker",
        "event",
        "fan",
        "input_boolean",
        "input_number",
        "input_select",
        "light",
        "lock",
        "media_player",
        "number",
        "person",
        "remote",
        "scene",
        "script",
        "select",
        "sensor",
        "sun",
        "switch",
        "tts",
        "update",
        "vacuum",
        "weather",
        "zone",
    }
)

_IGNORED_MEDIA_TICK_ATTRS: frozenset[str] = frozenset(
    {"media_position", "media_position_updated_at"}
)


def _iter_registry_entities(ent_reg: er.EntityRegistry) -> Iterable[er.RegistryEntry]:
    """Iterate EntityRegistry entries across Home Assistant versions and test doubles."""
    entities = getattr(ent_reg, "entities", None)
    if entities is None:
        return ()
    if hasattr(entities, "values"):
        return entities.values()
    return entities


def _strip_media_tick_attrs(attrs: dict[str, Any] | Any) -> dict[str, Any]:
    """Return attributes without high-frequency playback position tick fields."""
    if not isinstance(attrs, dict):
        attrs = dict(attrs or {})
    return {k: v for k, v in attrs.items() if k not in _IGNORED_MEDIA_TICK_ATTRS}


def is_media_position_only_tick(
    old_state: State | None, new_state: State | None
) -> bool:
    """Return True when a media_player update only advances media_position / timestamp."""
    if old_state is None or new_state is None:
        return False
    if old_state.domain != "media_player" or new_state.domain != "media_player":
        return False
    if old_state.state != new_state.state:
        return False
    return _strip_media_tick_attrs(old_state.attributes) == _strip_media_tick_attrs(
        new_state.attributes
    )


class AreaStateIndex:
    """Maintains O(1) per-Area and per-domain entity sets without full StateMachine scans."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the reactive Area state index."""
        self.hass = hass
        self._started = False
        self._dirty_registry = True
        self._entity_area: dict[str, str] = {}
        self._area_entities: dict[str, set[str]] = {}
        self._area_domain_entities: dict[tuple[str, str], set[str]] = {}
        self._domain_entities: dict[str, set[str]] = {}
        self._area_listeners: dict[str, list[Callable[[str], None]]] = {}
        self._unsubs: list[Callable[[], None]] = []

    @property
    def started(self) -> bool:
        """Return True when bus listeners are active."""
        return self._started

    @callback
    def start(self) -> None:
        """Subscribe once to registry and state_changed events and build initial index."""
        if self._started:
            if self._dirty_registry:
                self.rebuild()
            return
        self._started = True
        self.rebuild()
        self._unsubs = [
            self.hass.bus.async_listen(
                ar.EVENT_AREA_REGISTRY_UPDATED, self._on_registry_updated
            ),
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, self._on_registry_updated
            ),
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry_updated
            ),
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._on_state_changed),
        ]

    async def async_start(self) -> None:
        """Async wrapper around `start()` for setup entrypoints."""
        self.start()

    @callback
    def stop(self) -> None:
        """Unsubscribe all bus listeners and clear dynamic listeners."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._area_listeners.clear()
        self._started = False
        self._dirty_registry = True

    @callback
    def rebuild(self) -> None:
        """Rebuild Area <-> Entity and Domain -> Entity maps from registries + state IDs."""
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)

        entity_area: dict[str, str] = {}
        area_entities: dict[str, set[str]] = {}
        area_domain_entities: dict[tuple[str, str], set[str]] = {}
        domain_entities: dict[str, set[str]] = {}

        for entry in _iter_registry_entities(ent_reg):
            eid = entry.entity_id
            domain = entry.domain or eid.split(".", 1)[0]
            if domain in INDEXED_DOMAINS:
                domain_entities.setdefault(domain, set()).add(eid)
            if entry.disabled_by:
                continue
            area_id = entry.area_id or ""
            if not area_id and entry.device_id:
                dev = dev_reg.async_get(entry.device_id)
                if dev and dev.area_id:
                    area_id = dev.area_id
            if area_id:
                entity_area[eid] = area_id
                area_entities.setdefault(area_id, set()).add(eid)
                area_domain_entities.setdefault((area_id, domain), set()).add(eid)

        async_entity_ids = getattr(self.hass.states, "async_entity_ids", None)
        if callable(async_entity_ids):
            for eid in async_entity_ids():
                domain = eid.split(".", 1)[0]
                if domain in INDEXED_DOMAINS:
                    domain_entities.setdefault(domain, set()).add(eid)

        self._entity_area = entity_area
        self._area_entities = area_entities
        self._area_domain_entities = area_domain_entities
        self._domain_entities = domain_entities
        self._dirty_registry = False

    def _ensure_ready(self) -> None:
        """Ensure index maps are populated even when called before hub setup in unit tests."""
        if self._dirty_registry:
            self.rebuild()

    @callback
    def _on_registry_updated(self, _event: Event[Any] | Any = None) -> None:
        """Rebuild registry maps and notify subscribed Areas whose membership may have changed."""
        prev_areas = set(self._area_entities.keys())
        self.rebuild()
        affected_areas = prev_areas | set(self._area_entities.keys()) | set(
            self._area_listeners.keys()
        )
        for area_id in affected_areas:
            for cb in list(self._area_listeners.get(area_id, ())):
                cb("")

    @callback
    def _on_state_changed(self, event: Event[Any] | Any) -> None:
        """Update domain entity sets and notify Area listeners (ignoring media_position ticks)."""
        data = getattr(event, "data", None) or {}
        entity_id = str(data.get("entity_id") or "")
        if not entity_id or "." not in entity_id:
            return
        domain = entity_id.split(".", 1)[0]
        if domain not in INDEXED_DOMAINS:
            return

        old_state: State | None = data.get("old_state")
        new_state: State | None = data.get("new_state")

        if new_state is not None:
            self._domain_entities.setdefault(domain, set()).add(entity_id)
        elif entity_id not in self._entity_area:
            ent_reg = er.async_get(self.hass)
            if ent_reg.async_get(entity_id) is None:
                dom_set = self._domain_entities.get(domain)
                if dom_set is not None:
                    dom_set.discard(entity_id)

        area_id = self._entity_area.get(entity_id)
        if not area_id:
            return
        listeners = self._area_listeners.get(area_id)
        if not listeners:
            return
        if is_media_position_only_tick(old_state, new_state):
            return
        for cb in list(listeners):
            cb(entity_id)

    @callback
    def register_area_listener(
        self, area_id: str, listener: Callable[[str], None]
    ) -> Callable[[], None]:
        """Subscribe to state/registry changes affecting a single Home Assistant Area."""
        self._ensure_ready()
        bucket = self._area_listeners.setdefault(area_id, [])
        if listener not in bucket:
            bucket.append(listener)

        @callback
        def _unsub() -> None:
            cur = self._area_listeners.get(area_id)
            if cur and listener in cur:
                cur.remove(listener)
                if not cur:
                    self._area_listeners.pop(area_id, None)

        return _unsub

    def resolve_entity_area_id(self, entity_id: str) -> str | None:
        """Return the indexed Area ID for `entity_id` (falling back to registry lookup if unindexed)."""
        self._ensure_ready()
        cached = self._entity_area.get(entity_id)
        if cached:
            return cached
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(entity_id)
        if entry is None:
            return None
        if entry.area_id:
            return entry.area_id
        if entry.device_id:
            dev = dr.async_get(self.hass).async_get(entry.device_id)
            if dev and dev.area_id:
                return dev.area_id
        return None

    def entity_ids_in_area(
        self, area_id: str, domain: str | None = None
    ) -> set[str]:
        """Return O(1) copy of entity_ids assigned to `area_id` (optionally filtered by `domain`)."""
        if not area_id:
            return set()
        self._ensure_ready()
        if domain is not None:
            return set(self._area_domain_entities.get((area_id, domain), ()))
        return set(self._area_entities.get(area_id, ()))

    def entities_in_area(
        self, area_id: str, domains: Iterable[str] | None = None
    ) -> list[State]:
        """Return live `State` objects for entities in `area_id` without scanning other Areas."""
        if not area_id:
            return []
        self._ensure_ready()
        if domains is None:
            eids: Iterable[str] = self._area_entities.get(area_id, ())
        else:
            combined: list[str] = []
            for dom in domains:
                combined.extend(self._area_domain_entities.get((area_id, dom), ()))
            eids = combined
        out: list[State] = []
        for eid in eids:
            st = self.hass.states.get(eid)
            if st is not None:
                out.append(st)
        return out

    def entity_ids_for_domain(self, domain: str) -> set[str]:
        """Return tracked entity_ids for a single Home Assistant domain."""
        self._ensure_ready()
        known = set(self._domain_entities.get(domain, ()))
        if not self._started:
            async_entity_ids = getattr(self.hass.states, "async_entity_ids", None)
            if callable(async_entity_ids):
                known.update(async_entity_ids(domain))
        return known

    def states_for_domain(self, domain: str) -> list[State]:
        """Return live `State` objects for `domain` via indexed entity_ids (never `async_all`)."""
        out: list[State] = []
        for eid in sorted(self.entity_ids_for_domain(domain)):
            st = self.hass.states.get(eid)
            if st is not None:
                out.append(st)
        return out

    def all_indexed_area_ids(self) -> set[str]:
        """Return the set of area_ids that contain at least one indexed entity."""
        self._ensure_ready()
        return set(self._area_entities.keys())


def get_area_state_index(hass: HomeAssistant) -> AreaStateIndex:
    """Return or create the domain-level `AreaStateIndex` singleton."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    idx = domain_data.get("area_state_index")
    if not isinstance(idx, AreaStateIndex):
        idx = AreaStateIndex(hass)
        domain_data["area_state_index"] = idx
    return idx


@callback
def async_stop_area_state_index(hass: HomeAssistant) -> None:
    """Stop and remove the domain-level `AreaStateIndex` singleton on unload."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return
    idx = domain_data.pop("area_state_index", None)
    if isinstance(idx, AreaStateIndex):
        idx.stop()
