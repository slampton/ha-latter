"""16px-aligned Baseline 4:2:0 JPEG transcoder, 2x2 grid compositor, FFmpeg builder, and MJPEG parser."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import io
import time
from typing import Any, Final

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..media_cache import get_circular_mask_surfaces, validate_pil_image_dimensions

MAX_CONCURRENT_VIDEO_INGESTS: Final[int] = 6
VIDEO_INGEST_IDLE_SECONDS: Final[float] = 15.0
SNAPSHOT_PRIMER_TIMEOUT_SECONDS: Final[float] = 3.0
MIN_ALIGNED_DIM: Final[int] = 64
MAX_VIDEO_DIM: Final[int] = 1280
MIN_VIDEO_FPS: Final[int] = 1
MAX_VIDEO_FPS: Final[int] = 15

MJPEG_BOUNDARY: Final[str] = "latterframe"
MJPEG_CONTENT_TYPE: Final[str] = f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}"
MAX_SINGLE_FRAME_BYTES: Final[int] = 4 * 1024 * 1024
FFMPEG_READ_CHUNK_BYTES: Final[int] = 32768
FFMPEG_READ_TIMEOUT_SECONDS: Final[float] = 12.0
STREAM_WAIT_TIMEOUT_SECONDS: Final[float] = 10.0
SNAPSHOT_CACHE_MAX_AGE_SECONDS: Final[float] = 2.0
GRID_STALE_FRAME_SECONDS: Final[float] = 5.0
MAX_RTSP_EMPTY_RETRIES: Final[int] = 2
MJPEG_QUEUE_MAXSIZE: Final[int] = 32

GRID_GUTTER_PX: Final[int] = 2
GRID_BG_RGB: Final[tuple[int, int, int]] = (20, 24, 32)
GRID_OFFLINE_TILE_RGB: Final[tuple[int, int, int]] = (28, 33, 44)
GRID_OFFLINE_BORDER_RGB: Final[tuple[int, int, int]] = (52, 60, 76)
GRID_OFFLINE_TEXT_RGB: Final[tuple[int, int, int]] = (180, 190, 206)

CAMERA_CAP_HAS_AUDIO: Final[int] = 1
CAMERA_CAP_HAS_TALKBACK: Final[int] = 2
CAMERA_CAP_IS_DOORBELL: Final[int] = 4
CAMERA_CAP_IN_CAROUSEL: Final[int] = 8
CAMERA_CAP_SHOW_REPLY: Final[int] = 16
CAMERA_CAP_SHOW_UNLOCK: Final[int] = 32

_FFMPEG_PROTOCOL_WHITELIST: Final[str] = (
    "file,crypto,data,http,https,tcp,tls,rtp,rtsp,udp"
)
_ALLOWED_STREAM_SCHEMES: Final[tuple[str, ...]] = (
    "rtsp://",
    "rtsps://",
    "http://",
    "https://",
)

_MACROBLOCK_ALIGN: Final[int] = 16
_ROT_90: Final[int] = 90
_ROT_180: Final[int] = 180
_ROT_270: Final[int] = 270
_MIN_JPEG_HEADER_LEN: Final[int] = 16
_JPEG_MARKER_PREFIX: Final[int] = 0xFF
_JPEG_SOI: Final[int] = 0xD8
_JPEG_EOI: Final[int] = 0xD9
_JPEG_RST0: Final[int] = 0xD0
_JPEG_RST7: Final[int] = 0xD7
_JPEG_SOS: Final[int] = 0xDA
_JPEG_SOF0: Final[int] = 0xC0
_JPEG_SOF_MARKERS: Final[tuple[int, ...]] = (0xC0, 0xC1, 0xC2)
_MIN_SOF_SEG_LEN: Final[int] = 8
_YUV420_SOF_SEG_LEN: Final[int] = 17
_YCBCR_COMPONENTS: Final[int] = 3
_SAMP_420_LUMA: Final[int] = 0x22
_SAMP_420_CHROMA: Final[int] = 0x11
_LARGE_FRAME_PIXELS: Final[int] = 300_000
_MIN_JPEG_QUALITY: Final[int] = 40
_MAX_JPEG_QUALITY: Final[int] = 95
_SUBSAMPLING_420: Final[int] = 2
_GRID_QUADRANTS: Final[int] = 4
_MAX_IDLE_BUFFER_BYTES: Final[int] = 4096
_TAIL_KEEP_BYTES: Final[int] = 64
_HEADER_DELIM_LEN: Final[int] = 4
_EOI_MARKER_LEN: Final[int] = 2
_MIN_SEG_LEN: Final[int] = 2
_MIN_SCAN_TAIL: Final[int] = 4


class CameraFetchError(Exception):
    """The camera entity did not return a frame or stream."""


class CameraTranscodeError(Exception):
    """Pillow could not decode or encode the camera frame."""


class CameraIngestLimitError(Exception):
    """Maximum concurrent live video ingests reached."""


def align16(
    value: int,
    *,
    minimum: int = MIN_ALIGNED_DIM,
    maximum: int = MAX_VIDEO_DIM,
) -> int:
    """Clamp `value` into `[minimum, maximum]` and round down to a multiple of 16."""
    lo = max(_MACROBLOCK_ALIGN, (int(minimum) // _MACROBLOCK_ALIGN) * _MACROBLOCK_ALIGN)
    hi = max(lo, (int(maximum) // _MACROBLOCK_ALIGN) * _MACROBLOCK_ALIGN)
    clamped = max(lo, min(hi, int(value)))
    return max(lo, (clamped // _MACROBLOCK_ALIGN) * _MACROBLOCK_ALIGN)


def normalize_fit_mode(fit: str | None) -> str:
    """Normalize framing mode to canonical `'contain'` (default, uncropped) or `'fill'`."""
    return "fill" if str(fit or "").strip().lower() == "fill" else "contain"


def normalize_rotation(rot: int | str | None) -> int:
    """Normalize clockwise rotation angle to `0`, `90`, `180`, or `270`."""
    raw = str(rot if rot is not None else "0").strip()
    if raw not in ("0", "90", "180", "270"):
        raise ValueError(f"Invalid rotation angle: {rot!r}")
    return int(raw)


def normalize_fps(fps: int | float | str | None, *, default: int = 10) -> int:
    """Clamp target FPS into `[MIN_VIDEO_FPS, MAX_VIDEO_FPS]`."""
    try:
        val = round(float(fps)) if fps is not None else int(default)
    except (TypeError, ValueError):
        val = int(default)
    return max(MIN_VIDEO_FPS, min(MAX_VIDEO_FPS, val))


def compute_contain_size(
    src_w: int,
    src_h: int,
    max_w: int,
    max_h: int,
) -> tuple[int, int]:
    """Compute 16px-aligned output dimensions preserving native aspect ratio inside `(max_w, max_h)`."""
    bound_w = align16(max_w)
    bound_h = align16(max_h)
    if src_w <= 0 or src_h <= 0:
        return bound_w, bound_h
    scale = min(bound_w / float(src_w), bound_h / float(src_h))
    scaled_w = max(MIN_ALIGNED_DIM, int(src_w * scale))
    scaled_h = max(MIN_ALIGNED_DIM, int(src_h * scale))
    out_w = align16(scaled_w, minimum=MIN_ALIGNED_DIM, maximum=bound_w)
    out_h = align16(scaled_h, minimum=MIN_ALIGNED_DIM, maximum=bound_h)
    return out_w, out_h


def format_mjpeg_chunk(
    jpeg_bytes: bytes,
    boundary: str = MJPEG_BOUNDARY,
) -> bytes:
    """Wrap one JPEG frame in a multipart MJPEG chunk with an exact `Content-Length` header."""
    header = (
        f"--{boundary}\r\n"
        f"Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg_bytes)}\r\n\r\n"
    ).encode("ascii")
    return header + jpeg_bytes + b"\r\n"


def _parse_sof_segment(raw: bytes, idx: int, marker: int, seg_len: int) -> tuple[bool, int, int]:
    height = int.from_bytes(raw[idx + 3 : idx + 5], "big")
    width = int.from_bytes(raw[idx + 5 : idx + 7], "big")
    num_comp = raw[idx + 7]
    is_baseline_420 = False
    if (
        marker == _JPEG_SOF0
        and num_comp == _YCBCR_COMPONENTS
        and seg_len >= _YUV420_SOF_SEG_LEN
    ):
        y_samp = raw[idx + 9]
        cb_samp = raw[idx + 12]
        cr_samp = raw[idx + 15]
        is_baseline_420 = (
            y_samp == _SAMP_420_LUMA
            and cb_samp == _SAMP_420_CHROMA
            and cr_samp == _SAMP_420_CHROMA
        )
    return is_baseline_420, width, height


def inspect_jpeg_header(raw: bytes) -> tuple[bool, int, int]:
    """Return `(is_baseline_420, width, height)` by scanning JPEG SOF markers without Pillow."""
    if len(raw) < _MIN_JPEG_HEADER_LEN or not raw.startswith(b"\xff\xd8"):
        return False, 0, 0
    idx = 2
    n = len(raw)
    while idx + _MIN_SCAN_TAIL < n:
        if raw[idx] != _JPEG_MARKER_PREFIX:
            idx += 1
            continue
        while idx < n and raw[idx] == _JPEG_MARKER_PREFIX:
            idx += 1
        if idx >= n:
            break
        marker = raw[idx]
        idx += 1
        if marker in (_JPEG_SOI, _JPEG_EOI) or _JPEG_RST0 <= marker <= _JPEG_RST7:
            continue
        if marker == _JPEG_SOS or idx + _MIN_SEG_LEN > n:
            break
        seg_len = int.from_bytes(raw[idx : idx + 2], "big")
        if seg_len < _MIN_SEG_LEN or idx + seg_len > n:
            break
        if marker in _JPEG_SOF_MARKERS and seg_len >= _MIN_SOF_SEG_LEN:
            return _parse_sof_segment(raw, idx, marker, seg_len)
        idx += seg_len
    return False, 0, 0


def _apply_rotation(img: Image.Image, rot: int) -> Image.Image:
    if rot == _ROT_90:
        return img.transpose(Image.Transpose.ROTATE_270)
    if rot == _ROT_180:
        return img.transpose(Image.Transpose.ROTATE_180)
    if rot == _ROT_270:
        return img.transpose(Image.Transpose.ROTATE_90)
    return img


def transcode_camera_frame(
    raw_bytes: bytes,
    max_w: int,
    max_h: int,
    *,
    fit: str = "contain",
    rot: int = 0,
    circular_mask: bool = False,
    fast_live: bool = True,
    quality: int | None = None,
) -> bytes:
    """Decode `raw_bytes`, frame to 16px-aligned dimensions, and encode Baseline 4:2:0 JPEG."""
    target_w = align16(max_w)
    target_h = align16(max_h)
    fit_mode = normalize_fit_mode(fit)
    rot_deg = normalize_rotation(rot)

    with Image.open(io.BytesIO(raw_bytes)) as img:
        validate_pil_image_dimensions(img)
        draft_fn = getattr(img, "draft", None)
        if callable(draft_fn):
            draft_fn("RGB", (target_w, target_h))
        img_rgb = img.convert("RGB")
        if rot_deg:
            img_rgb = _apply_rotation(img_rgb, rot_deg)

        resample = (
            Image.Resampling.BILINEAR if fast_live else Image.Resampling.LANCZOS
        )
        if fit_mode == "fill":
            framed = ImageOps.fit(
                img_rgb,
                (target_w, target_h),
                method=resample,
                centering=(0.5, 0.5),
            )
            if circular_mask:
                mask, black_bg = get_circular_mask_surfaces(target_w, target_h)
                framed = Image.composite(framed, black_bg, mask)
        else:
            out_w, out_h = compute_contain_size(
                img_rgb.width, img_rgb.height, target_w, target_h
            )
            framed = (
                img_rgb
                if (img_rgb.width == out_w and img_rgb.height == out_h)
                else img_rgb.resize((out_w, out_h), resample=resample)
            )

        out = io.BytesIO()
        if quality is None:
            pixels = framed.width * framed.height
            jpeg_q = (72 if pixels > _LARGE_FRAME_PIXELS else 80) if fast_live else 85
        else:
            jpeg_q = max(_MIN_JPEG_QUALITY, min(_MAX_JPEG_QUALITY, int(quality)))
        framed.save(
            out,
            format="JPEG",
            quality=jpeg_q,
            optimize=not fast_live,
            progressive=False,
            subsampling=_SUBSAMPLING_420,
        )
        return out.getvalue()


def _load_tile_font(size_px: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        return ImageFont.load_default()


def _draw_centered_line(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
) -> None:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = max(1, int(bbox[2] - bbox[0]))
        th = max(1, int(bbox[3] - bbox[1]))
        draw.text(
            (cx - tw // 2 - int(bbox[0]), cy - th // 2 - int(bbox[1])),
            text,
            fill=GRID_OFFLINE_TEXT_RGB,
            font=font,
        )
    except (AttributeError, OSError, TypeError, ValueError):
        draw.text(
            (max(0, cx - len(text) * 4), max(0, cy - 6)),
            text,
            fill=GRID_OFFLINE_TEXT_RGB,
        )


def _draw_offline_tile(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    label: str,
) -> None:
    """Draw a readable centered placeholder tile (`>= 13 px` scaled font) for an offline quadrant."""
    x0, y0, cell_w, cell_h = rect
    draw.rectangle(
        (x0, y0, x0 + cell_w - 1, y0 + cell_h - 1),
        fill=GRID_OFFLINE_TILE_RGB,
        outline=GRID_OFFLINE_BORDER_RGB,
        width=1,
    )
    cx = x0 + cell_w // 2
    cy = y0 + cell_h // 2
    title_size = max(13, min(20, cell_h // 9))
    sub_size = max(12, title_size - 2)
    title_font = _load_tile_font(title_size)
    sub_font = _load_tile_font(sub_size)
    clean_label = (label or "").strip()[:22]
    gap = max(8, title_size // 2 + 4)
    if clean_label:
        _draw_centered_line(draw, cx, cy - gap, clean_label, title_font)
        _draw_centered_line(draw, cx, cy + gap, "Offline", sub_font)
    else:
        _draw_centered_line(draw, cx, cy, "Offline", title_font)


def _paste_grid_quadrant(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    slot: tuple[bytes | None, str, bool],
    rect: tuple[int, int, int, int],
    fit_mode: str,
) -> None:
    raw, label, has_label_slot = slot
    qx, qy, cell_w, cell_h = rect
    if not raw:
        if has_label_slot:
            _draw_offline_tile(draw, rect, label)
        return
    try:
        with Image.open(io.BytesIO(raw)) as img:
            validate_pil_image_dimensions(img)
            draft_fn = getattr(img, "draft", None)
            if callable(draft_fn):
                draft_fn("RGB", (cell_w, cell_h))
            img_rgb = img.convert("RGB")
            if fit_mode == "fill":
                tile = ImageOps.fit(
                    img_rgb,
                    (cell_w, cell_h),
                    method=Image.Resampling.BILINEAR,
                    centering=(0.5, 0.5),
                )
                canvas.paste(tile, (qx, qy))
                return
            src_w = max(1, img_rgb.width)
            src_h = max(1, img_rgb.height)
            scale = min(cell_w / float(src_w), cell_h / float(src_h))
            tw = max(1, min(cell_w, round(src_w * scale)))
            th = max(1, min(cell_h, round(src_h * scale)))
            tile = (
                img_rgb
                if (img_rgb.width == tw and img_rgb.height == th)
                else img_rgb.resize((tw, th), resample=Image.Resampling.BILINEAR)
            )
            canvas.paste(tile, (qx + (cell_w - tw) // 2, qy + (cell_h - th) // 2))
    except Exception:  # noqa: BLE001
        _draw_offline_tile(draw, rect, label)


def compose_grid_frame(
    frames: list[bytes | None],
    labels: list[str],
    width: int,
    height: int,
    *,
    fit: str = "contain",
    quality: int = 72,
) -> bytes:
    """Composite up to 4 camera frames into one 16px-aligned 2x2 Baseline 4:2:0 JPEG."""
    out_w = align16(width)
    out_h = align16(height)
    fit_mode = normalize_fit_mode(fit)

    canvas = Image.new("RGB", (out_w, out_h), GRID_BG_RGB)
    draw = ImageDraw.Draw(canvas)

    cell_w = max(_MACROBLOCK_ALIGN, (out_w - GRID_GUTTER_PX) // 2)
    cell_h = max(_MACROBLOCK_ALIGN, (out_h - GRID_GUTTER_PX) // 2)
    offsets = (
        (0, 0),
        (cell_w + GRID_GUTTER_PX, 0),
        (0, cell_h + GRID_GUTTER_PX),
        (cell_w + GRID_GUTTER_PX, cell_h + GRID_GUTTER_PX),
    )

    for idx in range(_GRID_QUADRANTS):
        qx, qy = offsets[idx]
        raw = frames[idx] if idx < len(frames) else None
        has_label_slot = idx < len(labels)
        label = labels[idx] if has_label_slot else ""
        _paste_grid_quadrant(
            canvas,
            draw,
            (raw, label, has_label_slot),
            (qx, qy, cell_w, cell_h),
            fit_mode,
        )

    out = io.BytesIO()
    canvas.save(
        out,
        format="JPEG",
        quality=max(_MIN_JPEG_QUALITY, min(_MAX_JPEG_QUALITY, int(quality))),
        optimize=False,
        progressive=False,
        subsampling=_SUBSAMPLING_420,
    )
    return out.getvalue()


def build_ffmpeg_video_cmd(
    ffmpeg_bin: str,
    stream_url: str,
    width: int,
    height: int,
    fps: int,
    *,
    fit: str = "contain",
    rot: int = 0,
) -> list[str]:
    """Build low-latency FFmpeg command producing 16px-aligned Baseline 4:2:0 MJPEG on stdout."""
    target_w = align16(width)
    target_h = align16(height)
    target_fps = normalize_fps(fps)
    fit_mode = normalize_fit_mode(fit)
    rot_deg = normalize_rotation(rot)

    vf_parts: list[str] = []
    if rot_deg == _ROT_90:
        vf_parts.append("transpose=1")
    elif rot_deg == _ROT_180:
        vf_parts.append("hflip,vflip")
    elif rot_deg == _ROT_270:
        vf_parts.append("transpose=2")
    if fit_mode == "fill":
        vf_parts.append(
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h}"
        )
    else:
        vf_parts.append(
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:"
            "force_divisible_by=16"
        )

    clean_url = (stream_url or "").strip()
    if (
        not clean_url
        or clean_url.startswith("-")
        or not clean_url.lower().startswith(_ALLOWED_STREAM_SCHEMES)
    ):
        raise ValueError(f"Unsupported camera stream URL scheme: {clean_url[:16]!r}")

    q_val = 6 if (target_w * target_h > _LARGE_FRAME_PIXELS) else 5
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-protocol_whitelist",
        _FFMPEG_PROTOCOL_WHITELIST,
    ]
    if clean_url.lower().startswith(("rtsp://", "rtsps://")):
        cmd.extend(["-rtsp_transport", "tcp"])
    cmd.extend(
        [
            "-rw_timeout",
            "5000000",
            "-fflags",
            "+nobuffer+discardcorrupt",
            "-flags",
            "low_delay",
            "-flags2",
            "+fast",
            "-analyzeduration",
            "250000",
            "-probesize",
            "200000",
            "-i",
            clean_url,
            "-an",
            "-sn",
            "-dn",
            "-r",
            str(target_fps),
            "-vf",
            ",".join(vf_parts),
            "-pix_fmt",
            "yuvj420p",
            "-c:v",
            "mjpeg",
            "-q:v",
            str(q_val),
            "-flush_packets",
            "1",
            "-f",
            "mpjpeg",
            "pipe:1",
        ]
    )
    return cmd


def _parse_content_length(header_bytes: bytes) -> int | None:
    for raw_line in header_bytes.split(b"\r\n"):
        if b":" not in raw_line:
            continue
        key, val = raw_line.split(b":", 1)
        if key.strip().lower() == b"content-length":
            val_str = val.strip().decode("ascii", errors="ignore")
            if val_str.isdigit():
                return int(val_str)
    return None


class MjpegStreamParser:
    """Incremental parser extracting JPEG frames from `multipart/x-mixed-replace` or SOI/EOI streams."""

    def __init__(self, max_frame_bytes: int = MAX_SINGLE_FRAME_BYTES) -> None:
        """Initialize an empty MJPEG parser buffer."""
        self._buf = bytearray()
        self._max_frame_bytes = max_frame_bytes

    def feed(self, chunk: bytes) -> list[bytes]:
        """Consume `chunk` and return all complete JPEG frames extracted so far."""
        if not chunk:
            return []
        self._buf.extend(chunk)
        frames: list[bytes] = []

        while True:
            header_end = self._buf.find(b"\r\n\r\n")
            soi = self._buf.find(b"\xff\xd8")

            if header_end != -1 and (soi == -1 or header_end < soi):
                header_bytes = bytes(self._buf[:header_end])
                content_len = _parse_content_length(header_bytes)
                body_start = header_end + _HEADER_DELIM_LEN
                if content_len is not None and 0 < content_len <= self._max_frame_bytes:
                    if len(self._buf) < body_start + content_len:
                        break
                    frame = bytes(self._buf[body_start : body_start + content_len])
                    del self._buf[: body_start + content_len]
                    if frame.startswith(b"\xff\xd8"):
                        frames.append(frame)
                    continue
                del self._buf[:body_start]
                continue

            if soi == -1:
                if len(self._buf) > _MAX_IDLE_BUFFER_BYTES:
                    del self._buf[:-_TAIL_KEEP_BYTES]
                break

            if soi > 0:
                del self._buf[:soi]

            eoi = self._buf.find(b"\xff\xd9", _EOI_MARKER_LEN)
            if eoi == -1:
                if len(self._buf) > self._max_frame_bytes:
                    self._buf.clear()
                break
            frame = bytes(self._buf[: eoi + _EOI_MARKER_LEN])
            del self._buf[: eoi + _EOI_MARKER_LEN]
            frames.append(frame)

        return frames


class LoopbackMjpegTransport:
    """Minimal transport capture adapter for HA's `camera.async_get_mjpeg_stream` push model."""

    def __init__(self, queue: asyncio.Queue[bytes | None]) -> None:
        """Initialize loopback queue writer."""
        self._queue = queue
        self._closing = False

    def write(self, data: bytes) -> None:
        """Push non-empty MJPEG bytes into the bounded queue, dropping oldest on overflow."""
        if not self._closing and data:
            payload = bytes(data)
            if self._queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(payload)

    def is_closing(self) -> bool:
        """Return True once the loopback stream has closed."""
        return self._closing

    def close(self) -> None:
        """Mark transport closed and enqueue EOF sentinel."""
        if not self._closing:
            self._closing = True
            if self._queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(None)


class LoopbackMjpegRequest:
    """Minimal request stub accepted by Home Assistant camera MJPEG handlers."""

    def __init__(self, transport: LoopbackMjpegTransport) -> None:
        """Bind loopback transport to HTTP GET request fields."""
        self.transport = transport
        self.headers: dict[str, str] = {}
        self.query: dict[str, str] = {}
        self.method = "GET"
        self.version = (1, 1)


@dataclass(eq=False)
class CameraSubscriber:
    """One active video consumer attached to a shared `CameraIngest`."""

    width: int
    height: int
    fps: int
    fit: str
    rot: int
    circular_mask: bool


@dataclass
class CameraIngest:
    """Single upstream camera ingest (RTSP FFmpeg -> Native MJPEG -> Snapshot) fanning out to N subscribers."""

    entity_id: str
    subscribers: set[CameraSubscriber] = field(default_factory=set)
    stream_w: int = 480
    stream_h: int = 320
    stream_fps: int = 10
    stream_fit: str = "contain"
    stream_rot: int = 0
    stream_is_baseline_420: bool = True
    source_tier: str = ""
    latest_frame: bytes | None = None
    latest_frame_ts: float = 0.0
    latest_seq: int = 0
    live_seq: int = 0
    latest_error: Exception | None = None
    next_frame_event: asyncio.Event = field(default_factory=asyncio.Event)
    restart_event: asyncio.Event = field(default_factory=asyncio.Event)
    _task: asyncio.Task[Any] | None = None
    idle_task: asyncio.Task[None] | None = None
    prime_task: asyncio.Task[None] | None = None
    idle_since: float = 0.0
    proc: asyncio.subprocess.Process | None = None
    sem_acquired: bool = False
    closed: bool = False

    def publish(
        self,
        frame: bytes,
        profile: tuple[int, int, str, int],
        *,
        is_baseline_420: bool = True,
        is_primer: bool = False,
    ) -> None:
        """Store `frame` as the latest warm frame and wake every waiting subscriber."""
        width, height, fit, rot = profile
        self.latest_frame = frame
        self.latest_frame_ts = time.monotonic()
        self.latest_seq += 1
        if not is_primer:
            self.live_seq += 1
        self.latest_error = None
        self.stream_w, self.stream_h, self.stream_fit, self.stream_rot = width, height, fit, rot
        self.stream_is_baseline_420 = is_baseline_420
        prev = self.next_frame_event
        self.next_frame_event = asyncio.Event()
        prev.set()

    def publish_error(self, err: Exception) -> None:
        """Record an ingest error and wake waiters so callers can react promptly."""
        self.latest_error = err
        prev = self.next_frame_event
        self.next_frame_event = asyncio.Event()
        prev.set()

    def desired_profile(self) -> tuple[int, int, int, str, int]:
        """Compute highest active subscriber `(w, h, fps, fit, rot)` for the shared ingest."""
        if not self.subscribers:
            return self.stream_w, self.stream_h, self.stream_fps, self.stream_fit, self.stream_rot
        max_w = max(s.width for s in self.subscribers)
        max_h = max(s.height for s in self.subscribers)
        max_fps = max(s.fps for s in self.subscribers)
        fits = {s.fit for s in self.subscribers}
        rots = {s.rot for s in self.subscribers}
        return (
            max_w,
            max_h,
            max_fps,
            next(iter(fits)) if len(fits) == 1 else "contain",
            next(iter(rots)) if len(rots) == 1 else 0,
        )
