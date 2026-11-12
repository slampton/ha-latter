"""Optional offline stubs for Pillow (`PIL`) and `aiohttp` when running in isolated environments."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


def ensure_module(name: str) -> ModuleType:
    """Return or create an in-memory `sys.modules` entry and bind it to its parent package."""
    mod = sys.modules.get(name)
    if mod is None:
        mod = ModuleType(name)
        mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = mod
        if "." in name:
            parent_name, child = name.rsplit(".", 1)
            parent = ensure_module(parent_name)
            setattr(parent, child, mod)
    return mod


HAS_REAL_PIL = importlib.util.find_spec("PIL") is not None


def build_minimal_baseline_jpeg(width: int, height: int) -> bytes:
    """Encode a real non-progressive Baseline JPEG via Pillow (with SOF0 stub fallback when PIL is absent)."""
    w = max(1, min(65535, int(width)))
    h = max(1, min(65535, int(height)))
    if HAS_REAL_PIL:
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


def install_optional_dep_stubs() -> None:
    """Install minimal `PIL` and `aiohttp` stubs only when absent from the active Python environment."""
    if not HAS_REAL_PIL:
        pil_mod = ensure_module("PIL")
        image_mod = ensure_module("PIL.Image")
        draw_mod = ensure_module("PIL.ImageDraw")
        ops_mod = ensure_module("PIL.ImageOps")
        enhance_mod = ensure_module("PIL.ImageEnhance")

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
                    else build_minimal_baseline_jpeg(self.width, self.height)
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

    if importlib.util.find_spec("aiohttp") is None:
        aiohttp_mod = ensure_module("aiohttp")
        web_mod = ensure_module("aiohttp.web")

        class ClientError(Exception):
            """Base aiohttp client error."""

        class ClientTimeout:
            def __init__(
                self,
                total: float | None = None,
                connect: float | None = None,
                sock_read: float | None = None,
            ) -> None:
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
