"""System-level singleton (`LatterSystemHub`), coordinator registry, and reactive O(1) Area state index."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
import secrets
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

from .const import (
    CALENDAR_REFRESH_INTERVAL_MINUTES,
    CONF_CALENDAR_ENTITIES,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DATA_HMAC_SECRET,
    DOMAIN,
    FORECAST_REFRESH_INTERVAL_MINUTES,
    INTEGRATION_VERSION,
)
from .feeds import (
    async_fetch_raw_calendar_events,
    async_fetch_weather_snapshot,
    read_sun_and_moon_fields,
)
from .http import UrlSigner
from .protocol import V3Records

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

DATA_SYSTEM = "system"
_SKY_TRACKED_ENTITIES: tuple[str, ...] = ("sun.sun", "sensor.moon_phase", "sensor.moon")

# ---------------------------------------------------------------------------
# Reactive O(1) Per-Area & Per-Domain Entity State Index
# ---------------------------------------------------------------------------

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
        affected_areas = (
            prev_areas
            | set(self._area_entities.keys())
            | set(self._area_listeners.keys())
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


# ---------------------------------------------------------------------------
# System Hub (`LatterSystemHub`) & Global Config Helpers
# ---------------------------------------------------------------------------


class LatterSystemHub:
    """Represents the shared Latter System state across all configured devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[dict[str, Any]],
        config: dict[str, Any],
        hmac_secret: bytes,
    ) -> None:
        """Initialize the shared LatterSystemHub instance."""
        self.hass = hass
        self.store = store
        self.config = config
        self.hmac_secret = hmac_secret
        self.url_signer = UrlSigner(hass, "system", hmac_secret)
        self.coordinators: dict[str, LatterCoordinator] = {}

        self._unsub_weather_state: Callable[[], None] | None = None
        self._unsub_sky_state: Callable[[], None] | None = None
        self._unsub_forecast_timer: Callable[[], None] | None = None
        self._unsub_calendar_timer: Callable[[], None] | None = None
        self._tracked_weather_entity: str | None = None

        self.weather_snapshot: tuple[V3Records, dict[str, Any]] | None = None
        self.weather_loaded: bool = False
        self._weather_last_fetch_mono: float = 0.0

        self.calendar_records: V3Records = V3Records()
        self.calendar_raw_rows: list[dict[str, Any]] = []
        self.calendar_loaded: bool = False
        self._calendar_last_fetch_mono: float = 0.0

    def _live_global_config(self) -> dict[str, Any]:
        """Return the live System-Wide configuration dict."""
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
        if isinstance(global_cfg, dict):
            self.config = global_cfg
        return self.config

    @property
    def weather_entity(self) -> str | None:
        """Return the configured System-Wide weather entity_id."""
        val = self._live_global_config().get(CONF_WEATHER_ENTITY)
        return str(val).strip() if val and str(val).strip() else None

    @property
    def calendar_entities(self) -> list[str]:
        """Return the configured System-Wide calendar entity_ids."""
        val = self._live_global_config().get(CONF_CALENDAR_ENTITIES, [])
        return (
            [str(x).strip() for x in val if str(x or "").strip()]
            if isinstance(val, (list, tuple))
            else []
        )

    async def async_rotate_hmac_secret(self) -> None:
        """Mint a fresh 256-bit HMAC signing secret, persist it, and republish all signed URLs."""
        new_hex = secrets.token_hex(32)
        new_secret = bytes.fromhex(new_hex)
        self.hmac_secret = new_secret
        self.url_signer = UrlSigner(self.hass, "system", new_secret)
        await self.url_signer.async_prime_lan_base_url()
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        domain_data[DATA_HMAC_SECRET] = new_secret
        global_cfg = self._live_global_config()
        global_cfg["hmac_secret_hex"] = new_hex
        await self.store.async_save(global_cfg)
        for coord in list(self.coordinators.values()):
            coord.update_hmac_secret(new_secret)
            coord.force_republish_all_domains()

    @callback
    def bind_feed_listeners(self) -> None:
        """Bind or rebind the single System-level weather, sun/moon, and periodic feed listeners."""
        weather_ent = self.weather_entity
        if weather_ent != self._tracked_weather_entity or (
            weather_ent and self._unsub_weather_state is None
        ):
            if self._unsub_weather_state is not None:
                self._unsub_weather_state()
                self._unsub_weather_state = None
            self._tracked_weather_entity = weather_ent
            if weather_ent:
                self._unsub_weather_state = async_track_state_change_event(
                    self.hass,
                    [weather_ent],
                    self._async_on_weather_state_change,
                )

        if self._unsub_sky_state is None:
            self._unsub_sky_state = async_track_state_change_event(
                self.hass,
                list(_SKY_TRACKED_ENTITIES),
                self._async_on_sky_state_change,
            )

        if self._unsub_forecast_timer is None:
            self._unsub_forecast_timer = async_track_time_interval(
                self.hass,
                self._async_periodic_weather_refresh,
                timedelta(minutes=FORECAST_REFRESH_INTERVAL_MINUTES),
            )
        if self._unsub_calendar_timer is None:
            self._unsub_calendar_timer = async_track_time_interval(
                self.hass,
                self._async_periodic_calendar_refresh,
                timedelta(minutes=CALENDAR_REFRESH_INTERVAL_MINUTES),
            )

    @callback
    def async_cleanup_feeds(self) -> None:
        """Unsubscribe System-level weather and calendar listeners/timers on unload."""
        for unsub in (
            self._unsub_weather_state,
            self._unsub_sky_state,
            self._unsub_forecast_timer,
            self._unsub_calendar_timer,
        ):
            if unsub is not None:
                unsub()
        self._unsub_weather_state = None
        self._unsub_sky_state = None
        self._unsub_forecast_timer = None
        self._unsub_calendar_timer = None
        self._tracked_weather_entity = None
        self.weather_loaded = False
        self.calendar_loaded = False

    @callback
    def _async_on_weather_state_change(
        self, _event: Event[EventStateChangedData]
    ) -> None:
        """Refresh the Site weather snapshot once when the configured weather entity updates."""
        self.hass.async_create_task(
            self.async_refresh_weather_forecast(),
            "latter_system_weather_refresh",
        )

    @callback
    def _async_on_sky_state_change(
        self, _event: Event[EventStateChangedData]
    ) -> None:
        """Update sun/moon fields on cached weather snapshot (or refresh if not yet loaded)."""
        if self.weather_snapshot is not None:
            recs, fields = self.weather_snapshot
            merged = {**fields, **read_sun_and_moon_fields(self.hass)}
            if merged == fields:
                return
            self.weather_snapshot = (recs, merged)
            weather_ent = self.weather_entity
            for coord in list(self.coordinators.values()):
                if not coord.is_ble_tag:
                    coord.apply_weather_snapshot(weather_ent, self.weather_snapshot)
            return
        self.hass.async_create_task(
            self.async_refresh_weather_forecast(coalesce=True),
            "latter_system_sky_refresh",
        )

    async def _async_periodic_weather_refresh(self, _now: datetime) -> None:
        """Refresh the 5-day Site weather forecast every 30 minutes."""
        await self.async_refresh_weather_forecast()

    async def _async_periodic_calendar_refresh(self, _now: datetime) -> None:
        """Refresh the Site calendar agenda every 15 minutes."""
        await self.async_refresh_calendar_agenda()

    async def async_refresh_weather_forecast(self, *, coalesce: bool = False) -> None:
        """Fetch the daily forecast once for the Site and fan out to all display coordinators."""
        self.bind_feed_listeners()
        now_m = time.monotonic()
        weather_ent = self.weather_entity
        if (
            coalesce
            and self.weather_loaded
            and (now_m - self._weather_last_fetch_mono) < 0.5
        ):
            return
        self._weather_last_fetch_mono = now_m
        snap = await async_fetch_weather_snapshot(self.hass, weather_ent)
        if snap is None:
            sky_only = (
                V3Records(),
                {
                    "condition": "",
                    "temperature": None,
                    "humidity": None,
                    "wind_speed": None,
                    "wind_bearing": None,
                    "high": None,
                    "low": None,
                    **read_sun_and_moon_fields(self.hass),
                },
            )
            self.weather_snapshot = sky_only
            self.weather_loaded = True
            for coord in list(self.coordinators.values()):
                if not coord.is_ble_tag:
                    coord.apply_weather_snapshot(None, sky_only)
            return

        self.weather_snapshot = snap
        self.weather_loaded = True
        for coord in list(self.coordinators.values()):
            if not coord.is_ble_tag:
                coord.apply_weather_snapshot(weather_ent, snap)

    async def async_refresh_calendar_agenda(
        self, days: int = 30, *, coalesce: bool = False
    ) -> tuple[V3Records, list[dict[str, Any]]]:
        """Fetch and deduplicate upcoming calendar events once for the Site and fan out to all display coordinators."""
        self.bind_feed_listeners()
        now_m = time.monotonic()
        if (
            coalesce
            and days == 30
            and self.calendar_loaded
            and (now_m - self._calendar_last_fetch_mono) < 0.5
        ):
            return self.calendar_records, self.calendar_raw_rows
        records, raw_rows = await async_fetch_raw_calendar_events(
            self.hass,
            self.calendar_entities,
            days=days,
        )
        if days == 30:
            self.calendar_records = records
            self.calendar_raw_rows = raw_rows
            self.calendar_loaded = True
            self._calendar_last_fetch_mono = now_m
            for coord in list(self.coordinators.values()):
                if not coord.is_ble_tag:
                    coord.apply_calendar_snapshot(records, raw_rows)
        return records, raw_rows


def get_latter_system(hass: HomeAssistant) -> LatterSystemHub | None:
    """Return the initialized LatterSystemHub instance if present."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return None
    sys_obj = domain_data.get(DATA_SYSTEM)
    if isinstance(sys_obj, LatterSystemHub):
        return sys_obj
    store = domain_data.get(DATA_GLOBAL_STORE)
    cfg = domain_data.get(DATA_GLOBAL_CONFIG)
    secret = domain_data.get(DATA_HMAC_SECRET)
    if isinstance(store, Store) and isinstance(cfg, dict) and isinstance(secret, bytes):
        sys_obj = LatterSystemHub(hass, store, cfg, secret)
        domain_data[DATA_SYSTEM] = sys_obj
        return sys_obj
    return None


def iter_coordinators(hass: HomeAssistant) -> list[LatterCoordinator]:
    """Return all active LatterCoordinator instances sorted deterministically by `device_slug`."""
    from .coordinator import LatterCoordinator

    seen_ids: set[int] = set()
    coords: list[LatterCoordinator] = []

    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        for coord in sys_obj.coordinators.values():
            if isinstance(coord, LatterCoordinator) and id(coord) not in seen_ids:
                seen_ids.add(id(coord))
                coords.append(coord)

    domain_data = hass.data.get(DOMAIN)
    if isinstance(domain_data, dict):
        for val in domain_data.values():
            if isinstance(val, LatterCoordinator) and id(val) not in seen_ids:
                seen_ids.add(id(val))
                coords.append(val)

    return sorted(coords, key=lambda c: c.device_slug)


async def async_save_and_broadcast_global_config(
    hass: HomeAssistant, updates: dict[str, Any]
) -> dict[str, Any]:
    """Persist updates to `.storage/latter.site` and broadcast to all loaded device coordinators."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
    if not updates:
        return global_cfg
    changed_keys = {k for k, v in updates.items() if global_cfg.get(k) != v}
    global_cfg.update(updates)
    store = domain_data.get(DATA_GLOBAL_STORE)
    if store is not None:
        await store.async_save(global_cfg)
    for coord in iter_coordinators(hass):
        await coord.async_on_global_config_updated(changed_keys or set(updates.keys()))
    return global_cfg


def get_system_device_info() -> DeviceInfo:
    """Return canonical DeviceInfo for the System-level Latter service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, "system")},
        entry_type=dr.DeviceEntryType.SERVICE,
        name="Latter System",
        manufacturer="Lampton Labs",
        model="Latter Site & BLE Fabric Engine",
        sw_version=INTEGRATION_VERSION,
        configuration_url="homeassistant://latter",
    )
