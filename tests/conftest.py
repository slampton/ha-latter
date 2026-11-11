"""Shared pytest fixtures and lightweight async Home Assistant test harness for ha-latter.

Installs realistic in-memory stubs for `homeassistant.*` (and `aiohttp` / `PIL` when absent in
offline environments) so the full 6-package integration suite runs identically in <3s locally and in CI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import voluptuous as vol

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _ensure_module(name: str) -> ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = ModuleType(name)
        mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = mod
        if "." in name:
            parent_name, child = name.rsplit(".", 1)
            parent = _ensure_module(parent_name)
            setattr(parent, child, mod)
    return mod


# ---------------------------------------------------------------------------
# Minimal PIL stub (used ONLY when Pillow is not installed in local sandbox)
# ---------------------------------------------------------------------------
_HAS_REAL_PIL = importlib.util.find_spec("PIL") is not None


def _build_minimal_baseline_jpeg(width: int, height: int) -> bytes:
    """Encode a real non-progressive Baseline JPEG via Pillow (with SOF0 stub fallback when PIL is absent)."""
    w = max(1, min(65535, int(width)))
    h = max(1, min(65535, int(height)))
    if _HAS_REAL_PIL:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (w, h), (48, 96, 160)).save(buf, format="JPEG", progressive=False)
        return buf.getvalue()
    sof0 = (
        b"\xff\xc0"
        + (11).to_bytes(2, "big")
        + b"\x08"
        + h.to_bytes(2, "big")
        + w.to_bytes(2, "big")
        + b"\x01\x01\x11\x00"
    )
    sos = b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x00"
    return b"\xff\xd8" + sof0 + sos + b"\xff\xd9"


if not _HAS_REAL_PIL:
    pil_mod = _ensure_module("PIL")
    image_mod = _ensure_module("PIL.Image")
    draw_mod = _ensure_module("PIL.ImageDraw")
    ops_mod = _ensure_module("PIL.ImageOps")
    enhance_mod = _ensure_module("PIL.ImageEnhance")

    class _StubImage:
        def __init__(self, mode: str = "RGB", size: tuple[int, int] = (240, 240)) -> None:
            self.mode = mode
            self.size = (int(size[0]), int(size[1]))

        @property
        def width(self) -> int:
            return self.size[0]

        @property
        def height(self) -> int:
            return self.size[1]

        def copy(self) -> _StubImage:
            return _StubImage(self.mode, self.size)

        def convert(self, mode: str) -> _StubImage:
            return _StubImage(mode, self.size)

        def resize(self, size: tuple[int, int], resample: Any = None) -> _StubImage:
            _ = resample
            return _StubImage(self.mode, (int(size[0]), int(size[1])))

        def transpose(self, method: Any) -> _StubImage:
            if method in (2, 4):
                return _StubImage(self.mode, (self.size[1], self.size[0]))
            return _StubImage(self.mode, self.size)

        def crop(self, box: tuple[int, int, int, int]) -> _StubImage:
            w = max(1, int(box[2] - box[0]))
            h = max(1, int(box[3] - box[1]))
            return _StubImage(self.mode, (w, h))

        def paste(self, im: Any, box: Any = None, mask: Any = None) -> None:
            _ = (im, box, mask)

        def putalpha(self, alpha: Any) -> None:
            _ = alpha
            self.mode = "RGBA"

        def split(self) -> tuple[_StubImage, ...]:
            return tuple(_StubImage("L", self.size) for _ in range(len(self.mode)))

        def save(self, fp: Any, format: str = "JPEG", **kwargs: Any) -> None:
            _ = kwargs
            fmt = (format or "JPEG").upper()
            payload = (
                b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
                if fmt == "PNG"
                else _build_minimal_baseline_jpeg(self.width, self.height)
            )
            if hasattr(fp, "write"):
                fp.write(payload)
            else:
                Path(fp).write_bytes(payload)

        def verify(self) -> None:
            return None

        def __enter__(self) -> _StubImage:
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

    class _Resampling:
        LANCZOS = 1
        BILINEAR = 2
        BICUBIC = 3
        NEAREST = 0

    def _pil_new(mode: str, size: tuple[int, int], color: Any = 0) -> _StubImage:
        _ = color
        return _StubImage(mode, size)

    def _pil_open(fp: Any) -> _StubImage:
        if isinstance(fp, (str, Path)):
            raw = Path(fp).read_bytes()
        elif hasattr(fp, "read"):
            pos = fp.tell() if hasattr(fp, "tell") else 0
            raw = fp.read()
            if hasattr(fp, "seek"):
                fp.seek(pos)
        else:
            raw = bytes(fp)
        if not raw or raw.startswith(b"NOT_AN_IMAGE"):
            raise OSError("Unidentified or corrupt image bytes")
        return _StubImage("RGB", (480, 480))

    def _pil_alpha_composite(im1: _StubImage, im2: _StubImage) -> _StubImage:
        _ = im2
        return _StubImage("RGBA", im1.size)

    class _Transpose:
        ROTATE_90 = 2
        ROTATE_180 = 3
        ROTATE_270 = 4

    def _pil_composite(im1: _StubImage, im2: _StubImage, mask: Any) -> _StubImage:
        _ = (im2, mask)
        return _StubImage("RGB", im1.size)

    image_mod.Image = _StubImage  # type: ignore[attr-defined]
    image_mod.Resampling = _Resampling  # type: ignore[attr-defined]
    image_mod.Transpose = _Transpose  # type: ignore[attr-defined]
    image_mod.LANCZOS = 1  # type: ignore[attr-defined]
    image_mod.BICUBIC = 3  # type: ignore[attr-defined]
    image_mod.BILINEAR = 2  # type: ignore[attr-defined]
    image_mod.new = _pil_new  # type: ignore[attr-defined]
    image_mod.open = _pil_open  # type: ignore[attr-defined]
    image_mod.alpha_composite = _pil_alpha_composite  # type: ignore[attr-defined]
    image_mod.composite = _pil_composite  # type: ignore[attr-defined]

    class _StubDraw:
        def __init__(self, im: _StubImage, mode: str | None = None) -> None:
            self.im = im
            self.mode = mode

        def __getattr__(self, _name: str) -> Callable[..., None]:
            def _noop(*_args: Any, **_kwargs: Any) -> None:
                return None

            return _noop

    draw_mod.Draw = _StubDraw  # type: ignore[attr-defined]
    ops_mod.exif_transpose = lambda im: im  # type: ignore[attr-defined]
    ops_mod.fit = lambda im, size, method=None, bleed=0.0, centering=(0.5, 0.5): _StubImage(im.mode, size)  # type: ignore[attr-defined]

    class _StubEnhancer:
        def __init__(self, im: _StubImage) -> None:
            self._im = im

        def enhance(self, _factor: float) -> _StubImage:
            return self._im.copy()

    enhance_mod.Brightness = _StubEnhancer  # type: ignore[attr-defined]
    enhance_mod.Contrast = _StubEnhancer  # type: ignore[attr-defined]
    pil_mod.Image = image_mod  # type: ignore[attr-defined]
    pil_mod.ImageDraw = draw_mod  # type: ignore[attr-defined]
    pil_mod.ImageOps = ops_mod  # type: ignore[attr-defined]
    pil_mod.ImageEnhance = enhance_mod  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Minimal aiohttp stub (used ONLY when aiohttp is not installed locally)
# ---------------------------------------------------------------------------
if importlib.util.find_spec("aiohttp") is None:
    aiohttp_mod = _ensure_module("aiohttp")
    web_mod = _ensure_module("aiohttp.web")

    class ClientError(Exception):
        """Base aiohttp client error."""

    class ClientTimeout:
        def __init__(self, total: float | None = None, connect: float | None = None, sock_read: float | None = None) -> None:
            self.total = total
            self.connect = connect
            self.sock_read = sock_read

    class Response:
        def __init__(
            self,
            *,
            body: bytes | str | None = None,
            text: str | None = None,
            status: int = 200,
            content_type: str = "text/plain",
            headers: Mapping[str, str] | None = None,
        ) -> None:
            self.status = int(status)
            self.content_type = content_type
            self.headers = dict(headers or {})
            if text is not None:
                self.text = text
                self.body = text.encode("utf-8")
            elif isinstance(body, str):
                self.text = body
                self.body = body.encode("utf-8")
            else:
                self.body = bytes(body or b"")
                self.text = self.body.decode("utf-8", errors="replace")

    class StreamResponse(Response):
        def __init__(self, *, status: int = 200, headers: Mapping[str, str] | None = None) -> None:
            super().__init__(status=status, headers=headers)
            self._chunks: list[bytes] = []

        async def prepare(self, _request: Any) -> StreamResponse:
            return self

        async def write(self, data: bytes) -> None:
            self._chunks.append(bytes(data))
            self.body = b"".join(self._chunks)

        async def write_eof(self) -> None:
            return None

    def json_response(data: Any, *, status: int = 200, headers: Mapping[str, str] | None = None) -> Response:
        return Response(
            text=json.dumps(data),
            status=status,
            content_type="application/json",
            headers=headers,
        )

    class Request(dict):  # type: ignore[type-arg]
        def __init__(
            self,
            *,
            app: Mapping[str, Any] | None = None,
            query: Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None,
            match_info: Mapping[str, str] | None = None,
            multipart_parts: list[Any] | None = None,
            user: Any = None,
        ) -> None:
            super().__init__()
            self.app = dict(app or {})
            self.query = dict(query or {})
            self.headers = dict(headers or {})
            self.match_info = dict(match_info or {})
            self._multipart_parts = list(multipart_parts or [])
            if user is not None:
                self["hass_user"] = user

        async def multipart(self) -> Any:
            parts = list(self._multipart_parts)

            class _Reader:
                def __init__(self) -> None:
                    self._idx = 0

                async def next(self) -> Any:
                    if self._idx >= len(parts):
                        return None
                    item = parts[self._idx]
                    self._idx += 1
                    return item

            return _Reader()

    web_mod.Response = Response  # type: ignore[attr-defined]
    web_mod.StreamResponse = StreamResponse  # type: ignore[attr-defined]
    web_mod.json_response = json_response  # type: ignore[attr-defined]
    web_mod.Request = Request  # type: ignore[attr-defined]
    aiohttp_mod.ClientError = ClientError  # type: ignore[attr-defined]
    aiohttp_mod.ClientTimeout = ClientTimeout  # type: ignore[attr-defined]
    aiohttp_mod.web = web_mod  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Lightweight async Home Assistant stubs (when homeassistant is not installed)
# ---------------------------------------------------------------------------
_USING_HA_STUBS: bool = importlib.util.find_spec("homeassistant") is None
if _USING_HA_STUBS:
    ha_mod = _ensure_module("homeassistant")
    const_mod = _ensure_module("homeassistant.const")
    core_mod = _ensure_module("homeassistant.core")
    exc_mod = _ensure_module("homeassistant.exceptions")
    ce_mod = _ensure_module("homeassistant.config_entries")
    def_mod = _ensure_module("homeassistant.data_entry_flow")
    util_mod = _ensure_module("homeassistant.util")
    dt_mod = _ensure_module("homeassistant.util.dt")
    helpers_mod = _ensure_module("homeassistant.helpers")
    ar_mod = _ensure_module("homeassistant.helpers.area_registry")
    dr_mod = _ensure_module("homeassistant.helpers.device_registry")
    er_mod = _ensure_module("homeassistant.helpers.entity_registry")
    ir_mod = _ensure_module("homeassistant.helpers.issue_registry")
    cv_mod = _ensure_module("homeassistant.helpers.config_validation")
    sel_mod = _ensure_module("homeassistant.helpers.selector")
    disc_mod = _ensure_module("homeassistant.helpers.discovery_flow")
    aio_client_mod = _ensure_module("homeassistant.helpers.aiohttp_client")
    deb_mod = _ensure_module("homeassistant.helpers.debounce")
    ep_mod = _ensure_module("homeassistant.helpers.entity_platform")
    ev_mod = _ensure_module("homeassistant.helpers.event")
    net_helper_mod = _ensure_module("homeassistant.helpers.network")
    store_mod = _ensure_module("homeassistant.helpers.storage")
    typing_mod = _ensure_module("homeassistant.helpers.typing")
    comp_mod = _ensure_module("homeassistant.components")
    bt_mod = _ensure_module("homeassistant.components.bluetooth")
    cam_mod = _ensure_module("homeassistant.components.camera")
    fe_mod = _ensure_module("homeassistant.components.frontend")
    net_comp_mod = _ensure_module("homeassistant.components.network")
    pc_mod = _ensure_module("homeassistant.components.panel_custom")
    ws_mod = _ensure_module("homeassistant.components.websocket_api")
    bs_mod = _ensure_module("homeassistant.components.binary_sensor")
    dt_comp_mod = _ensure_module("homeassistant.components.device_tracker")
    diag_comp_mod = _ensure_module("homeassistant.components.diagnostics")
    ffmpeg_mod = _ensure_module("homeassistant.components.ffmpeg")
    http_comp_mod = _ensure_module("homeassistant.components.http")
    lock_mod = _ensure_module("homeassistant.components.lock")
    repairs_comp_mod = _ensure_module("homeassistant.components.repairs")
    sensor_comp_mod = _ensure_module("homeassistant.components.sensor")

    # --- homeassistant.const ---
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

    # --- homeassistant.exceptions ---
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

    # --- homeassistant.util & dt ---
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

    # --- homeassistant.core ---
    def callback(func: Callable[..., Any]) -> Callable[..., Any]:
        func._hass_callback = True  # type: ignore[attr-defined]
        return func

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
            self.auth = SimpleNamespace(
                async_get_user=self._async_get_user,
            )
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

    # --- homeassistant.config_entries & data_entry_flow ---
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
            self, entry: ConfigEntry, *, data_updates: Mapping[str, Any] | None = None, reason: str = "reconfigure_successful"
        ) -> dict[str, Any]:
            if data_updates:
                merged = dict(entry.data)
                merged.update(data_updates)
                self.hass.config_entries.async_update_entry(entry, data=merged)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return {"type": "abort", "reason": reason}

        def async_update_and_abort(
            self, entry: ConfigEntry, *, data_updates: Mapping[str, Any] | None = None, reason: str = "reconfigure_successful"
        ) -> dict[str, Any]:
            return self.async_update_reload_and_abort(entry, data_updates=data_updates, reason=reason)

    class AbortFlow(Exception):
        def __init__(self, reason: str) -> None:
            super().__init__(reason)
            self.reason = reason

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

    # --- Registries: area_registry, device_registry, entity_registry, issue_registry ---
    EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"

    @dataclass
    class AreaEntry:
        id: str
        name: str
        floor_id: str | None = None
        icon: str | None = None
        aliases: set[str] = field(default_factory=set)

    class AreaRegistry:
        def __init__(self, hass: HomeAssistant) -> None:
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

        def async_create(self, name: str, *, area_id: str | None = None, floor_id: str | None = None) -> AreaEntry:
            aid = area_id or _slugify(name)
            entry = AreaEntry(id=aid, name=name, floor_id=floor_id)
            self.areas[aid] = entry
            self._hass.bus.async_fire(EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": aid})
            return entry

        def async_update(self, area_id: str, *, name: str | None = None, floor_id: str | None = None) -> AreaEntry:
            entry = self.areas[area_id]
            if name is not None:
                entry.name = name
            if floor_id is not None:
                entry.floor_id = floor_id
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

    CONNECTION_NETWORK_MAC = "mac"
    EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"

    class DeviceEntryType(StrEnum):
        SERVICE = "service"

    class DeviceInfo(dict):  # type: ignore[type-arg]
        pass

    def _format_mac(mac: str) -> str:
        hex_only = re.sub(r"[^0-9a-fA-F]", "", str(mac or ""))
        if len(hex_only) == 12:
            return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2)).lower()
        return str(mac or "").strip().lower()

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
        def __init__(self, hass: HomeAssistant) -> None:
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
                {(ct, _format_mac(cv) if ct == CONNECTION_NETWORK_MAC else cv) for ct, cv in connections}
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
                (ct, _format_mac(cv) if ct == CONNECTION_NETWORK_MAC else cv)
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
    dr_mod.format_mac = _format_mac  # type: ignore[attr-defined]
    dr_mod.async_get = lambda hass: hass._device_registry  # type: ignore[attr-defined]
    dr_mod.async_entries_for_area = lambda reg, area_id: [d for d in reg.devices.values() if d.area_id == area_id]  # type: ignore[attr-defined]
    dr_mod.async_entries_for_config_entry = lambda reg, entry_id: [
        d for d in reg.devices.values() if entry_id in d.config_entries
    ]  # type: ignore[attr-defined]

    EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"

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
        entity_category: EntityCategory | None = None
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

    class EntityRegistry:
        def __init__(self, hass: HomeAssistant) -> None:
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
        def __init__(self, hass: HomeAssistant) -> None:
            self._hass = hass
            self.issues: dict[tuple[str, str], IssueEntry] = {}

        def async_get_issue(self, domain: str, issue_id: str) -> IssueEntry | None:
            return self.issues.get((domain, issue_id))

    def _async_create_issue(
        hass: HomeAssistant,
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

    def _async_delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
        hass._issue_registry.issues.pop((domain, issue_id), None)

    ir_mod.IssueSeverity = IssueSeverity  # type: ignore[attr-defined]
    ir_mod.async_get = lambda hass: hass._issue_registry  # type: ignore[attr-defined]
    ir_mod.async_create_issue = _async_create_issue  # type: ignore[attr-defined]
    ir_mod.async_delete_issue = _async_delete_issue  # type: ignore[attr-defined]

    # --- config_validation, selector, discovery_flow, debounce, event, storage, network ---
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
        items = [s.strip() for s in val.split(",") if s.strip()] if isinstance(val, str) else [str(x).strip() for x in val]
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

        def get(
            self, url: str, timeout: Any = None, headers: Any = None, **kwargs: Any
        ) -> Any:
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

    net_helper_mod.get_url = lambda hass, **kw: hass.data.get("_internal_url", "http://homeassistant.local:8123")  # type: ignore[attr-defined]

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

    # --- Entity base classes & component stubs ---
    class _BaseEntity:
        hass: HomeAssistant | None = None
        entity_id: str | None = None
        _attr_has_entity_name: bool = False
        _attr_translation_key: str | None = None
        _attr_unique_id: str | None = None
        _attr_name: str | None = None
        _attr_icon: str | None = None
        _attr_device_info: Any = None
        _attr_entity_category: EntityCategory | None = None
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

        @callback
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
        hass: HomeAssistant

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

    # --- bluetooth, camera, frontend, network, panel_custom, websocket_api ---
    class BluetoothScanningMode(StrEnum):
        ACTIVE = "active"
        PASSIVE = "passive"

    class BluetoothCallbackMatcher(dict):  # type: ignore[type-arg]
        pass

    def _bt_register_callback(
        hass: HomeAssistant,
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

    bt_mod.BluetoothCallbackMatcher = BluetoothCallbackMatcher  # type: ignore[attr-defined]
    bt_mod.BluetoothScanningMode = BluetoothScanningMode  # type: ignore[attr-defined]
    bt_mod.async_register_callback = _bt_register_callback  # type: ignore[attr-defined]
    bt_mod.async_current_scanners = lambda hass: hass.data.get("_bt_scanners", [])  # type: ignore[attr-defined]
    bt_mod.async_scanner_by_source = lambda hass, source: next(  # type: ignore[attr-defined]
        (s for s in hass.data.get("_bt_scanners", []) if getattr(s, "source", None) == source),
        None,
    )

    @dataclass
    class _CameraImage:
        content: bytes
        content_type: str = "image/jpeg"

    async def _camera_get_image(hass: HomeAssistant, entity_id: str, **kwargs: Any) -> _CameraImage:
        _ = kwargs
        images = hass.data.get("_camera_images", {})
        if entity_id in images:
            raw = images[entity_id]
            if isinstance(raw, Exception):
                raise raw
            return _CameraImage(content=raw)
        return _CameraImage(content=_build_minimal_baseline_jpeg(320, 240))

    async def _camera_get_stream_source(hass: HomeAssistant, entity_id: str) -> str | None:
        return hass.data.get("_camera_streams", {}).get(entity_id)

    cam_mod.async_get_image = _camera_get_image  # type: ignore[attr-defined]
    cam_mod.async_get_stream_source = _camera_get_stream_source  # type: ignore[attr-defined]

    fe_mod.add_extra_js_url = lambda hass, url: hass._extra_js_urls.add(url)  # type: ignore[attr-defined]
    fe_mod.remove_extra_js_url = lambda hass, url: hass._extra_js_urls.discard(url)  # type: ignore[attr-defined]
    fe_mod.async_remove_panel = lambda hass, path, **kw: hass._panels.pop(path, None)  # type: ignore[attr-defined]

    async def _async_get_source_ip(hass: HomeAssistant, target_ip: Any = None) -> str:
        _ = target_ip
        return hass._source_ip

    net_comp_mod.async_get_source_ip = _async_get_source_ip  # type: ignore[attr-defined]

    async def _register_panel(hass: HomeAssistant, **kwargs: Any) -> None:
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

        @callback
        def send_result(self, msg_id: int, result: Any = None) -> None:
            self.results.append((msg_id, result))

        @callback
        def send_error(self, msg_id: int, code: str, message: str) -> None:
            self.errors.append((msg_id, code, message))

        @callback
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

    def _ws_register_command(hass: HomeAssistant, handler: Callable[..., Any]) -> None:
        ws_type = getattr(handler, "_ws_type", handler.__name__)
        hass._ws_commands[str(ws_type)] = handler

    ws_mod.ActiveConnection = ActiveConnection  # type: ignore[attr-defined]
    ws_mod.websocket_command = _ws_command  # type: ignore[attr-defined]
    ws_mod.require_admin = _ws_require_admin  # type: ignore[attr-defined]
    ws_mod.async_response = _ws_async_response  # type: ignore[attr-defined]
    ws_mod.async_register_command = _ws_register_command  # type: ignore[attr-defined]
    ws_mod.event_message = lambda iden, event: {"id": iden, "type": "event", "event": event}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Shared Pytest Fixtures
# ---------------------------------------------------------------------------
if _USING_HA_STUBS and sys.platform == "win32":
    from collections import deque
    import heapq

    class _DeterministicEventLoop(asyncio.AbstractEventLoop):
        """Pure-Python virtual-clock event loop for offline unit tests (zero TCP loopback sockets)."""

        def __init__(self) -> None:
            self._ready: deque[asyncio.Handle] = deque()
            self._scheduled: list[asyncio.TimerHandle] = []
            self._clock: float = 0.0
            self._closed: bool = False
            self._running: bool = False
            self._task_factory: Any = None
            self._exception_handler: Any = None

        def get_debug(self) -> bool:
            return False

        def set_debug(self, enabled: bool) -> None:
            _ = enabled

        def time(self) -> float:
            return self._clock

        def is_running(self) -> bool:
            return self._running

        def is_closed(self) -> bool:
            return self._closed

        def close(self) -> None:
            self._ready.clear()
            self._scheduled.clear()
            self._closed = True

        def _timer_handle_cancelled(self, handle: asyncio.TimerHandle) -> None:
            _ = handle

        def create_future(self) -> asyncio.Future[Any]:
            return asyncio.Future(loop=self)

        def create_task(self, coro: Any, *, name: str | None = None, context: Any = None) -> asyncio.Task[Any]:
            if self._task_factory is not None:
                return self._task_factory(self, coro, name=name, context=context)
            return asyncio.Task(coro, loop=self, name=name, context=context)

        def set_task_factory(self, factory: Any) -> None:
            self._task_factory = factory

        def get_task_factory(self) -> Any:
            return self._task_factory

        def set_exception_handler(self, handler: Any) -> None:
            self._exception_handler = handler

        def get_exception_handler(self) -> Any:
            return self._exception_handler

        def default_exception_handler(self, context: dict[str, Any]) -> None:
            _ = context

        def call_exception_handler(self, context: dict[str, Any]) -> None:
            if self._exception_handler is not None:
                self._exception_handler(self, context)

        def call_soon(self, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.Handle:
            h = asyncio.Handle(callback_fn, args, self, context)
            self._ready.append(h)
            return h

        def call_soon_threadsafe(self, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.Handle:
            return self.call_soon(callback_fn, *args, context=context)

        def call_at(self, when: float, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.TimerHandle:
            h = asyncio.TimerHandle(float(when), callback_fn, args, self, context)
            heapq.heappush(self._scheduled, h)
            return h

        def call_later(self, delay: float, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.TimerHandle:
            return self.call_at(self._clock + max(0.0, float(delay)), callback_fn, *args, context=context)

        async def shutdown_asyncgens(self) -> None:
            return None

        async def shutdown_default_executor(self, *args: Any, **kwargs: Any) -> None:
            _ = (args, kwargs)

        def run_until_complete(self, future: Any) -> Any:
            fut = asyncio.ensure_future(future, loop=self)
            self._running = True
            asyncio.events._set_running_loop(self)
            try:
                steps = 0
                while not fut.done():
                    steps += 1
                    if steps > 100000:
                        raise RuntimeError("Deterministic event loop exceeded step budget")
                    while self._scheduled and self._scheduled[0]._when <= self._clock:
                        th = heapq.heappop(self._scheduled)
                        if not th._cancelled:
                            self._ready.append(th)
                    if not self._ready and self._scheduled:
                        while self._scheduled and self._scheduled[0]._cancelled:
                            heapq.heappop(self._scheduled)
                        if self._scheduled:
                            self._clock = self._scheduled[0]._when
                            continue
                    if not self._ready:
                        break
                    batch = len(self._ready)
                    for _ in range(batch):
                        h = self._ready.popleft()
                        if not h._cancelled:
                            h._run()
                return fut.result()
            finally:
                self._running = False
                asyncio.events._set_running_loop(None)

    def pytest_asyncio_loop_factories(config: Any, item: Any) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
        """Provide socket-free deterministic event loop factory on Windows offline test runs."""
        _ = (config, item)
        return {"deterministic": _DeterministicEventLoop}


@pytest.fixture
def hass(tmp_path: Path) -> Any:
    """Provide a fresh, isolated HomeAssistant instance backed by tmp_path."""
    from homeassistant.core import HomeAssistant

    return HomeAssistant(config_dir=tmp_path)


@pytest.fixture
def make_esphome_device() -> Callable[..., tuple[Any, str]]:
    """Helper fixture to seed a realistic ESPHome device + entities in Device/Entity/State registries."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er

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
        sdk: int = 41,
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

        beacon_eid = f"switch.{slug}_ble_presence_beacon"
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=beacon_eid,
                platform="esphome",
                device_id=dev.id,
                config_entry_id=esp_entry.entry_id,
                original_name="BLE Presence Beacon",
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
