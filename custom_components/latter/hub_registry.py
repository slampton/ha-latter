"""Reactive O(1) `AreaStateIndex`, `LatterSystemHub` core state, and coordinator/config locks."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
import secrets
from typing import Any, Final

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_CALENDAR_ENTITIES,
    CONF_SYSTEM_CONFIG_REV,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    INTEGRATION_VERSION,
)
from .protocol_codec import V3Records
from .protocol_policy import PinLockoutTracker

_HOURS_PER_DAY: Final = 24

# ---------------------------------------------------------------------------
# Reactive O(1) Per-Area & Per-Domain Entity State Index
# ---------------------------------------------------------------------------

INDEXED_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "alarm_control_panel",
        "automation",
        "binary_sensor",
        "button",
        "calendar",
        "camera",
        "climate",
        "cover",
        "device_tracker",
        "event",
        "fan",
        "humidifier",
        "input_boolean",
        "input_button",
        "input_number",
        "input_select",
        "lawn_mower",
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
        "siren",
        "sun",
        "switch",
        "tts",
        "update",
        "vacuum",
        "valve",
        "water_heater",
        "weather",
        "zone",
    }
)

_IGNORED_MEDIA_TICK_ATTRS: Final[frozenset[str]] = frozenset(
    {"media_position", "media_position_updated_at"}
)


def _iter_registry_entities(ent_reg: er.EntityRegistry) -> Iterable[er.RegistryEntry]:
    """Iterate `EntityRegistry` entries across Home Assistant versions and test doubles."""
    entities = getattr(ent_reg, "entities", None)
    if entities is None:
        return ()
    if hasattr(entities, "values"):
        vals: Iterable[er.RegistryEntry] = entities.values()
        return vals
    items: Iterable[er.RegistryEntry] = entities
    return items


def _strip_media_tick_attrs(attrs: Mapping[str, Any] | object) -> dict[str, Any]:
    """Return attributes without high-frequency playback position tick fields."""
    raw = attrs if isinstance(attrs, Mapping) else {}
    return {k: v for k, v in raw.items() if k not in _IGNORED_MEDIA_TICK_ATTRS}


def is_media_position_only_tick(
    old_state: State | None, new_state: State | None
) -> bool:
    """Return True when a `media_player` update only advances `media_position` / timestamp."""
    if old_state is None or new_state is None:
        return False
    if old_state.domain != "media_player" or new_state.domain != "media_player":
        return False
    if old_state.state != new_state.state:
        return False
    return _strip_media_tick_attrs(old_state.attributes) == _strip_media_tick_attrs(
        new_state.attributes
    )


def _is_irrelevant_registry_update(event_type: str, data: object) -> bool:
    if not isinstance(data, Mapping) or data.get("action") != "update":
        return False
    changes = data.get("changes")
    if not isinstance(changes, Mapping):
        return False
    keys = set(changes.keys())
    if event_type == er.EVENT_ENTITY_REGISTRY_UPDATED:
        return not bool(keys & {"area_id", "device_id", "disabled_by", "entity_id"})
    if event_type == dr.EVENT_DEVICE_REGISTRY_UPDATED:
        return not bool(keys & {"area_id", "disabled_by"})
    return False


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
        """Subscribe once to registry and `state_changed` events and build initial index."""
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

    def _resolve_entry_area(
        self, entry: er.RegistryEntry, dev_reg: dr.DeviceRegistry
    ) -> str:
        if entry.area_id:
            return str(entry.area_id)
        if entry.device_id:
            dev = dev_reg.async_get(entry.device_id)
            if dev and dev.area_id:
                return str(dev.area_id)
        return ""

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
            area_id = self._resolve_entry_area(entry, dev_reg)
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
        if self._dirty_registry:
            self.rebuild()

    def _affected_areas_for_event(
        self,
        event_type: str,
        data: object,
        prev_area_entities: dict[str, set[str]],
    ) -> set[str]:
        if event_type == ar.EVENT_AREA_REGISTRY_UPDATED:
            changed_area = (
                str(data.get("area_id") or "")
                if isinstance(data, Mapping)
                else ""
            )
            if changed_area:
                return {changed_area}
            return (
                set(prev_area_entities.keys())
                | set(self._area_entities.keys())
                | set(self._area_listeners.keys())
            )
        all_areas = set(prev_area_entities.keys()) | set(self._area_entities.keys())
        return {
            aid
            for aid in all_areas
            if prev_area_entities.get(aid) != self._area_entities.get(aid)
        }

    @callback
    def _on_registry_updated(self, event: Event[Any] | Any = None) -> None:
        """Rebuild registry maps and notify subscribed Areas whose membership changed."""
        data = getattr(event, "data", None)
        event_type = str(getattr(event, "event_type", "") or "")
        if _is_irrelevant_registry_update(event_type, data):
            return
        prev_area_entities = {k: set(v) for k, v in self._area_entities.items()}
        self.rebuild()
        for area_id in self._affected_areas_for_event(
            event_type, data, prev_area_entities
        ):
            for cb in list(self._area_listeners.get(area_id, ())):
                cb("")

    @callback
    def _on_state_changed(self, event: Event[Any] | Any) -> None:
        """Update domain entity sets and notify Area listeners (ignoring `media_position` ticks)."""
        data = getattr(event, "data", None)
        if not isinstance(data, Mapping):
            return
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
        if not listeners or is_media_position_only_tick(old_state, new_state):
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

        unsub: Callable[[], None] = _unsub
        return unsub

    def resolve_entity_area_id(self, entity_id: str) -> str | None:
        """Return the indexed Area ID for `entity_id` (falling back to registry lookup if unindexed)."""
        self._ensure_ready()
        cached = self._entity_area.get(entity_id)
        if cached:
            return cached
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None:
            return None
        resolved = self._resolve_entry_area(entry, dr.async_get(self.hass))
        return resolved or None

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
        return [
            st
            for eid in eids
            if (st := self.hass.states.get(eid)) is not None
        ]

    def entity_ids_for_domain(self, domain: str) -> set[str]:
        """Return tracked `entity_ids` for a single Home Assistant domain."""
        self._ensure_ready()
        known = set(self._domain_entities.get(domain, ()))
        if not self._started:
            async_entity_ids = getattr(self.hass.states, "async_entity_ids", None)
            if callable(async_entity_ids):
                known.update(async_entity_ids(domain))
        return known

    def states_for_domain(self, domain: str) -> list[State]:
        """Return live `State` objects for `domain` via indexed `entity_ids` (never `async_all`)."""
        return [
            st
            for eid in sorted(self.entity_ids_for_domain(domain))
            if (st := self.hass.states.get(eid)) is not None
        ]


def get_area_state_index(hass: HomeAssistant) -> AreaStateIndex:
    """Return or create the domain-level `AreaStateIndex` singleton."""
    domain_data = get_domain_data(hass)
    if domain_data.area_state_index is None:
        domain_data.area_state_index = AreaStateIndex(hass)
    return domain_data.area_state_index


@callback
def async_stop_area_state_index(hass: HomeAssistant) -> None:
    """Stop and remove the domain-level `AreaStateIndex` singleton on unload."""
    domain_data = peek_domain_data(hass)
    if domain_data is None:
        return
    idx = domain_data.area_state_index
    domain_data.area_state_index = None
    if idx is not None:
        idx.stop()


# ---------------------------------------------------------------------------
# System Hub (`LatterSystemHub`) & Global Config Locks
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class HubRuntimeHooks:
    """Orchestration-tier (`hub_sync`) factories and feed/schedule callbacks wired at setup."""

    url_signer_factory: Callable[[HomeAssistant, str, bytes], Any] | None = None
    rpc_dispatcher_factory: Callable[[HomeAssistant], Any] | None = None
    bind_feeds: Callable[[LatterSystemHub], None] | None = None
    cleanup_feeds: Callable[[LatterSystemHub], None] | None = None
    evaluate_bedtime: Callable[[LatterSystemHub, datetime | None], Awaitable[None]] | None = None
    refresh_weather: Callable[[LatterSystemHub, bool], Awaitable[None]] | None = None
    refresh_calendar: (
        Callable[[LatterSystemHub, int, bool], Awaitable[tuple[V3Records, list[dict[str, Any]]]]]
        | None
    ) = None


_HUB_HOOKS = HubRuntimeHooks()


def register_hub_hooks(
    *,
    url_signer_factory: Callable[[HomeAssistant, str, bytes], Any] | None = None,
    rpc_dispatcher_factory: Callable[[HomeAssistant], Any] | None = None,
    bind_feeds: Callable[[LatterSystemHub], None] | None = None,
    cleanup_feeds: Callable[[LatterSystemHub], None] | None = None,
    evaluate_bedtime: Callable[[LatterSystemHub, datetime | None], Awaitable[None]] | None = None,
    refresh_weather: Callable[[LatterSystemHub, bool], Awaitable[None]] | None = None,
    refresh_calendar: (
        Callable[[LatterSystemHub, int, bool], Awaitable[tuple[V3Records, list[dict[str, Any]]]]]
        | None
    ) = None,
) -> None:
    """Register orchestration-tier factories and feed-sync callbacks without creating an import cycle."""
    if url_signer_factory is not None:
        _HUB_HOOKS.url_signer_factory = url_signer_factory
    if rpc_dispatcher_factory is not None:
        _HUB_HOOKS.rpc_dispatcher_factory = rpc_dispatcher_factory
    if bind_feeds is not None:
        _HUB_HOOKS.bind_feeds = bind_feeds
    if cleanup_feeds is not None:
        _HUB_HOOKS.cleanup_feeds = cleanup_feeds
    if evaluate_bedtime is not None:
        _HUB_HOOKS.evaluate_bedtime = evaluate_bedtime
    if refresh_weather is not None:
        _HUB_HOOKS.refresh_weather = refresh_weather
    if refresh_calendar is not None:
        _HUB_HOOKS.refresh_calendar = refresh_calendar


def safe_hour(val: object, default: int) -> int:
    """Coerce a schedule hour preference into `0..23` without raising on corrupted input."""
    if isinstance(val, bool) or val is None or not isinstance(val, (int, float, str)):
        return default
    try:
        return int(val) % _HOURS_PER_DAY
    except (TypeError, ValueError):
        return default


class LatterSystemHub:
    """Represents the shared Latter System state across all configured devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[dict[str, Any]],
        config: dict[str, Any],
        hmac_secret: bytes,
    ) -> None:
        """Initialize the shared `LatterSystemHub` instance."""
        self.hass = hass
        self.store = store
        self.config = config
        self.hmac_secret = hmac_secret
        self._url_signer: Any = (
            _HUB_HOOKS.url_signer_factory(hass, "system", hmac_secret)
            if _HUB_HOOKS.url_signer_factory is not None
            else None
        )
        self.pin_lockout = PinLockoutTracker()
        self._rpc_dispatcher: Any = (
            _HUB_HOOKS.rpc_dispatcher_factory(hass)
            if _HUB_HOOKS.rpc_dispatcher_factory is not None
            else None
        )
        self.coordinators: dict[str, Any] = {}

        self._unsub_weather_state: Callable[[], None] | None = None
        self._unsub_sky_state: Callable[[], None] | None = None
        self._unsub_forecast_timer: Callable[[], None] | None = None
        self._unsub_calendar_timer: Callable[[], None] | None = None
        self._unsub_bedtime_timer: Callable[[], None] | None = None
        self._unsub_core_config: Callable[[], None] | None = None
        self._bedtime_sched_trackers: dict[str, tuple[bool, int, int, bool]] = {}
        self._tracked_weather_entity: str | None = None

        self.weather_snapshot: tuple[V3Records, dict[str, Any]] | None = None
        self.weather_loaded: bool = False
        self._weather_last_fetch_mono: float = 0.0

        self.calendar_records: V3Records = V3Records()
        self.calendar_raw_rows: list[dict[str, Any]] = []
        self.calendar_loaded: bool = False
        self._calendar_last_fetch_mono: float = 0.0

    @property
    def url_signer(self) -> Any:
        """Return the system-scoped `UrlSigner` instance (lazily constructed if factory registered later)."""
        if self._url_signer is None and _HUB_HOOKS.url_signer_factory is not None:
            self._url_signer = _HUB_HOOKS.url_signer_factory(
                self.hass, "system", self.hmac_secret
            )
        return self._url_signer

    @url_signer.setter
    def url_signer(self, value: Any) -> None:
        self._url_signer = value

    @property
    def rpc_dispatcher(self) -> Any:
        """Return the singleton `LatterRpcDispatcher` instance (lazily constructed if factory registered later)."""
        if (
            self._rpc_dispatcher is None
            and _HUB_HOOKS.rpc_dispatcher_factory is not None
        ):
            self._rpc_dispatcher = _HUB_HOOKS.rpc_dispatcher_factory(self.hass)
        return self._rpc_dispatcher

    @rpc_dispatcher.setter
    def rpc_dispatcher(self, value: Any) -> None:
        self._rpc_dispatcher = value

    def live_global_config(self) -> dict[str, Any]:
        """Return the live System-Wide configuration dict."""
        domain_data = peek_domain_data(self.hass)
        if domain_data is not None:
            self.config = domain_data.global_config
        return self.config

    @property
    def weather_entity(self) -> str | None:
        """Return the configured System-Wide weather `entity_id`."""
        val = self.live_global_config().get(CONF_WEATHER_ENTITY)
        return str(val).strip() if val and str(val).strip() else None

    @property
    def calendar_entities(self) -> list[str]:
        """Return the configured System-Wide calendar `entity_ids`."""
        val = self.live_global_config().get(CONF_CALENDAR_ENTITIES, [])
        return (
            [str(x).strip() for x in val if str(x or "").strip()]
            if isinstance(val, (list, tuple))
            else []
        )

    async def async_rotate_hmac_secret(self) -> None:
        """Mint a fresh 256-bit HMAC signing secret, persist it, and republish all signed URLs."""
        new_hex = secrets.token_hex(32)
        new_secret = bytes.fromhex(new_hex)
        async with get_system_config_lock(self.hass):
            self.hmac_secret = new_secret
            if _HUB_HOOKS.url_signer_factory is not None:
                self._url_signer = _HUB_HOOKS.url_signer_factory(
                    self.hass, "system", new_secret
                )
            if self._url_signer is not None:
                await self._url_signer.async_prime_lan_base_url()
            get_domain_data(self.hass).hmac_secret = new_secret
            global_cfg = self.live_global_config()
            global_cfg["hmac_secret_hex"] = new_hex
            await self.store.async_save(global_cfg)
        for coord in list(self.coordinators.values()):
            coord.update_hmac_secret(new_secret)
            coord.force_republish_all_domains()

    @callback
    def bind_feed_listeners(self) -> None:
        """Bind or rebind System-level weather, sun/moon, and periodic feed listeners via `hub_sync`."""
        if _HUB_HOOKS.bind_feeds is not None:
            _HUB_HOOKS.bind_feeds(self)

    @callback
    def async_cleanup_feeds(self) -> None:
        """Unsubscribe System-level weather and calendar listeners/timers on unload."""
        if _HUB_HOOKS.cleanup_feeds is not None:
            _HUB_HOOKS.cleanup_feeds(self)
            return
        for unsub in (
            self._unsub_weather_state,
            self._unsub_sky_state,
            self._unsub_forecast_timer,
            self._unsub_calendar_timer,
            self._unsub_bedtime_timer,
            self._unsub_core_config,
        ):
            if unsub is not None:
                unsub()
        self._unsub_weather_state = None
        self._unsub_sky_state = None
        self._unsub_forecast_timer = None
        self._unsub_calendar_timer = None
        self._unsub_bedtime_timer = None
        self._unsub_core_config = None
        self._bedtime_sched_trackers.clear()
        self._tracked_weather_entity = None
        self.weather_loaded = False
        self.calendar_loaded = False

    async def async_evaluate_bedtime_schedules(
        self, *, now: datetime | None = None
    ) -> None:
        """Apply Bedtime Mode schedule boundary transitions via `hub_sync`."""
        if _HUB_HOOKS.evaluate_bedtime is not None:
            await _HUB_HOOKS.evaluate_bedtime(self, now)

    async def async_refresh_weather_forecast(self, *, coalesce: bool = False) -> None:
        """Fetch the daily forecast once for the Site and fan out to all display coordinators."""
        if _HUB_HOOKS.refresh_weather is not None:
            await _HUB_HOOKS.refresh_weather(self, coalesce)

    async def async_refresh_calendar_agenda(
        self, days: int = 30, *, coalesce: bool = False
    ) -> tuple[V3Records, list[dict[str, Any]]]:
        """Fetch and deduplicate upcoming calendar events once for the Site and fan out."""
        if _HUB_HOOKS.refresh_calendar is not None:
            return await _HUB_HOOKS.refresh_calendar(self, days, coalesce)
        return self.calendar_records, self.calendar_raw_rows


@dataclass(slots=True)
class LatterDomainData:
    """Strongly typed domain-level state stored on `hass.data[DOMAIN_DATA_KEY]`."""

    global_store: Store[dict[str, Any]] | None = None
    global_config: dict[str, Any] = field(default_factory=dict)
    hmac_secret: bytes = b""
    system_config_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    system_hub: LatterSystemHub | None = None

    views_registered: bool = False
    discovery_unsubs: tuple[Callable[[], None], ...] | None = None
    unsub_delayed_scan: Callable[[], None] | None = None
    unsub_stop_cleanup: Callable[[], None] | None = None
    unsub_started_scan: Callable[[], None] | None = None
    own_area_writes: dict[str, tuple[str, float]] = field(default_factory=dict)

    area_state_index: AreaStateIndex | None = None
    camera_hub: Any = None
    ble_fabric: Any = None
    pin_lockout: PinLockoutTracker | None = None
    rpc_dispatcher: Any = None
    probed_lan_ip: str = ""

    studio_ws_registered_version: str = ""
    studio_static_prefixes: set[str] = field(default_factory=set)
    studio_icon_js_url: str | None = None
    registered_panel_url: str | None = None
    internal_logs: list[dict[str, str]] = field(default_factory=list)

    created_area_occupancy_ids: set[str] = field(default_factory=set)
    created_area_occupants_ids: set[str] = field(default_factory=set)
    registered_person_sensors: set[str] = field(default_factory=set)
    registered_subentry_floors: set[str] = field(default_factory=set)
    registered_person_floors: set[str] = field(default_factory=set)

    ma_queue_counts: dict[str, int] = field(default_factory=dict)
    ma_known_macs: dict[str, set[str]] = field(default_factory=dict)
    ma_known_protocols: dict[str, set[str]] = field(default_factory=dict)
    ma_reconnect_until: dict[str, float] = field(default_factory=dict)
    ma_reconnect_timer: Callable[[], None] | None = None
    ma_cache_unsubs: tuple[Callable[[], None], ...] | None = None
    ma_counterpart_cache: dict[str, tuple[str | None, bool, float]] = field(
        default_factory=dict
    )
    healing_ma_links: bool = False

    fusion_index: dict[str, list[str]] = field(default_factory=dict)
    ble_scanner_cache_active: bool = False
    ble_scanner_cache: dict[str, str] = field(default_factory=dict)

    slot_push_failures: dict[str, int] = field(default_factory=dict)
    slot_push_last_warn: dict[str, float] = field(default_factory=dict)


DOMAIN_DATA_KEY: Final[HassKey[LatterDomainData]] = HassKey(DOMAIN)


def get_domain_data(hass: HomeAssistant) -> LatterDomainData:
    """Return (or lazily create) the strongly typed `LatterDomainData` for `DOMAIN`."""
    existing = hass.data.get(DOMAIN_DATA_KEY)
    if existing is None:
        existing = LatterDomainData()
        hass.data[DOMAIN_DATA_KEY] = existing
    return existing


def peek_domain_data(hass: HomeAssistant) -> LatterDomainData | None:
    """Return `LatterDomainData` if initialized for `DOMAIN`, else `None`."""
    return hass.data.get(DOMAIN_DATA_KEY)


def get_global_config(hass: HomeAssistant) -> dict[str, Any]:
    """Return the live mutable System-Wide configuration dict."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        return sys_obj.config
    return get_domain_data(hass).global_config


def peek_global_config(hass: HomeAssistant) -> dict[str, Any]:
    """Return the live System-Wide configuration dict, or `{}` if not initialized."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        return sys_obj.config
    domain_data = peek_domain_data(hass)
    return domain_data.global_config if domain_data is not None else {}


def get_latter_system(hass: HomeAssistant) -> LatterSystemHub | None:
    """Return the initialized `LatterSystemHub` from `entry.runtime_data` or `DOMAIN_DATA_KEY`."""
    entries_fn = getattr(getattr(hass, "config_entries", None), "async_entries", None)
    if callable(entries_fn):
        for entry in entries_fn(DOMAIN):
            runtime = getattr(entry, "runtime_data", None)
            if isinstance(runtime, LatterSystemHub):
                return runtime

    domain_data = peek_domain_data(hass)
    if domain_data is None:
        return None
    if domain_data.system_hub is not None:
        return domain_data.system_hub
    if domain_data.global_store is not None and domain_data.hmac_secret:
        sys_obj = LatterSystemHub(
            hass,
            domain_data.global_store,
            domain_data.global_config,
            domain_data.hmac_secret,
        )
        domain_data.system_hub = sys_obj
        return sys_obj
    return None


def _is_coordinator_instance(val: object) -> bool:
    return bool(
        getattr(val, "_is_latter_coordinator", False)
        or (
            hasattr(val, "device_slug")
            and hasattr(val, "subentry_id")
            and callable(getattr(val, "get_opt", None))
        )
    )


def iter_coordinators(hass: HomeAssistant) -> list[Any]:
    """Return all active `LatterCoordinator` instances sorted deterministically by `device_slug`."""
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        return []
    coords = [
        coord
        for coord in sys_obj.coordinators.values()
        if _is_coordinator_instance(coord)
    ]
    return sorted(coords, key=lambda c: str(c.device_slug))


def get_system_config_lock(hass: HomeAssistant) -> asyncio.Lock:
    """Return the domain-level `asyncio.Lock` guarding System config read-modify-write."""
    return get_domain_data(hass).system_config_lock


def get_system_config_rev(hass: HomeAssistant) -> int:
    """Return the monotonic System config revision (`>= 1`)."""
    raw_rev = peek_global_config(hass).get(CONF_SYSTEM_CONFIG_REV)
    if isinstance(raw_rev, bool) or not isinstance(raw_rev, (int, float, str)):
        return 1
    try:
        return max(1, int(raw_rev) or 1)
    except (TypeError, ValueError):
        return 1


def get_system_device_info() -> DeviceInfo:
    """Return canonical `DeviceInfo` for the System-level Latter service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, "system")},
        entry_type=dr.DeviceEntryType.SERVICE,
        name="Latter System",
        manufacturer="Latter",
        model="Latter Site & BLE Fabric Engine",
        sw_version=INTEGRATION_VERSION,
        configuration_url="homeassistant://latter",
    )
