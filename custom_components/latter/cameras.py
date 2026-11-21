"""Shared 1-ingest-per-camera live MJPEG fan-out hub, 2x2 grid compositor, and camera capability resolver."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Collection, Mapping
import contextlib
from dataclasses import dataclass, field
from functools import partial
import io
import logging
import shutil
import time
from typing import Any

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .const import DOMAIN
from .doorbell import resolve_doorbell_targets
from .http import get_circular_mask_surfaces, validate_pil_image_dimensions
from .hub import get_area_state_index

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants, Guardrails & Capability Bits
# ---------------------------------------------------------------------------

DATA_CAMERA_HUB = "camera_stream_hub"

MAX_CONCURRENT_VIDEO_INGESTS: int = 6
VIDEO_INGEST_IDLE_SECONDS: float = 15.0
SNAPSHOT_PRIMER_TIMEOUT_SECONDS: float = 3.0
MIN_ALIGNED_DIM: int = 64
MAX_VIDEO_DIM: int = 1280
MIN_VIDEO_FPS: int = 1
MAX_VIDEO_FPS: int = 15

MJPEG_BOUNDARY: str = "latterframe"
MJPEG_CONTENT_TYPE: str = f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}"
MAX_SINGLE_FRAME_BYTES: int = 4 * 1024 * 1024
FFMPEG_READ_CHUNK_BYTES: int = 32768
FFMPEG_READ_TIMEOUT_SECONDS: float = 12.0
STREAM_WAIT_TIMEOUT_SECONDS: float = 10.0
SNAPSHOT_CACHE_MAX_AGE_SECONDS: float = 2.0
GRID_STALE_FRAME_SECONDS: float = 5.0
MAX_RTSP_EMPTY_RETRIES: int = 2
MJPEG_QUEUE_MAXSIZE: int = 32

GRID_GUTTER_PX: int = 2
GRID_BG_RGB: tuple[int, int, int] = (20, 24, 32)  # #141820
GRID_OFFLINE_TILE_RGB: tuple[int, int, int] = (28, 33, 44)
GRID_OFFLINE_BORDER_RGB: tuple[int, int, int] = (52, 60, 76)
GRID_OFFLINE_TEXT_RGB: tuple[int, int, int] = (180, 190, 206)

CAMERA_CAP_HAS_AUDIO: int = 1
CAMERA_CAP_HAS_TALKBACK: int = 2
CAMERA_CAP_IS_DOORBELL: int = 4
CAMERA_CAP_IN_CAROUSEL: int = 8
CAMERA_CAP_SHOW_REPLY: int = 16
CAMERA_CAP_SHOW_UNLOCK: int = 32

_CAMERA_FEATURE_STREAM: int = int(CameraEntityFeature.STREAM)
_FFMPEG_PROTOCOL_WHITELIST: str = "file,crypto,data,http,https,tcp,tls,rtp,rtsp,udp"
_ALLOWED_STREAM_SCHEMES: tuple[str, ...] = ("rtsp://", "rtsps://", "http://", "https://")


class CameraFetchError(Exception):
    """The camera entity did not return a frame or stream."""


class CameraTranscodeError(Exception):
    """Pillow could not decode or encode the camera frame."""


class CameraIngestLimitError(Exception):
    """Maximum concurrent live video ingests reached."""


# ---------------------------------------------------------------------------
# Pure Framing, 16px Alignment, JPEG Inspection & MJPEG Multipart Helpers
# ---------------------------------------------------------------------------


def align16(
    value: int,
    *,
    minimum: int = MIN_ALIGNED_DIM,
    maximum: int = MAX_VIDEO_DIM,
) -> int:
    """Clamp `value` into `[minimum, maximum]` and round down to a multiple of 16."""
    lo = max(16, (int(minimum) // 16) * 16)
    hi = max(lo, (int(maximum) // 16) * 16)
    clamped = max(lo, min(hi, int(value)))
    return max(lo, (clamped // 16) * 16)


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


def inspect_jpeg_header(raw: bytes) -> tuple[bool, int, int]:
    """Return `(is_baseline_420, width, height)` by scanning JPEG SOF markers without Pillow."""
    if len(raw) < 16 or not raw.startswith(b"\xff\xd8"):
        return False, 0, 0
    idx = 2
    n = len(raw)
    while idx + 4 < n:
        if raw[idx] != 0xFF:
            idx += 1
            continue
        while idx < n and raw[idx] == 0xFF:
            idx += 1
        if idx >= n:
            break
        marker = raw[idx]
        idx += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xDA:  # Start of Scan — no SOF follows
            break
        if idx + 2 > n:
            break
        seg_len = int.from_bytes(raw[idx : idx + 2], "big")
        if seg_len < 2 or idx + seg_len > n:
            break
        if marker in (0xC0, 0xC1, 0xC2) and seg_len >= 8:
            height = int.from_bytes(raw[idx + 3 : idx + 5], "big")
            width = int.from_bytes(raw[idx + 5 : idx + 7], "big")
            num_comp = raw[idx + 7]
            is_baseline_420 = False
            if marker == 0xC0 and num_comp == 3 and seg_len >= 17:
                # Component sampling factors: Y=0x22 (4:2:0), Cb=0x11, Cr=0x11
                y_samp = raw[idx + 9]
                cb_samp = raw[idx + 12]
                cr_samp = raw[idx + 15]
                is_baseline_420 = y_samp == 0x22 and cb_samp == 0x11 and cr_samp == 0x11
            return is_baseline_420, width, height
        idx += seg_len
    return False, 0, 0


def _apply_rotation(img: Image.Image, rot: int) -> Image.Image:
    """Apply clockwise rotation (`0 | 90 | 180 | 270`) to a PIL image."""
    if rot == 90:
        return img.transpose(Image.Transpose.ROTATE_270)
    if rot == 180:
        return img.transpose(Image.Transpose.ROTATE_180)
    if rot == 270:
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
            if img_rgb.width == out_w and img_rgb.height == out_h:
                framed = img_rgb
            else:
                framed = img_rgb.resize((out_w, out_h), resample=resample)

        out = io.BytesIO()
        if quality is None:
            pixels = framed.width * framed.height
            jpeg_q = (72 if pixels > 300000 else 80) if fast_live else 85
        else:
            jpeg_q = max(40, min(95, int(quality)))
        framed.save(
            out,
            format="JPEG",
            quality=jpeg_q,
            optimize=not fast_live,
            progressive=False,
            subsampling=2,
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
    except Exception:  # noqa: BLE001
        draw.text((max(0, cx - len(text) * 4), max(0, cy - 6)), text, fill=GRID_OFFLINE_TEXT_RGB)


def _draw_offline_tile(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    cell_w: int,
    cell_h: int,
    label: str,
) -> None:
    """Draw a readable centered placeholder tile for an offline or stalled camera quadrant."""
    x1 = x0 + cell_w - 1
    y1 = y0 + cell_h - 1
    draw.rectangle(
        (x0, y0, x1, y1),
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

    cell_w = max(16, (out_w - GRID_GUTTER_PX) // 2)
    cell_h = max(16, (out_h - GRID_GUTTER_PX) // 2)
    offsets = (
        (0, 0),
        (cell_w + GRID_GUTTER_PX, 0),
        (0, cell_h + GRID_GUTTER_PX),
        (cell_w + GRID_GUTTER_PX, cell_h + GRID_GUTTER_PX),
    )

    for idx in range(4):
        qx, qy = offsets[idx]
        raw = frames[idx] if idx < len(frames) else None
        label = labels[idx] if idx < len(labels) else ""
        if not raw:
            if idx < len(labels):
                _draw_offline_tile(draw, qx, qy, cell_w, cell_h, label)
            continue
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
                else:
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
                    px = qx + (cell_w - tw) // 2
                    py = qy + (cell_h - th) // 2
                    canvas.paste(tile, (px, py))
        except Exception:  # noqa: BLE001
            _draw_offline_tile(draw, qx, qy, cell_w, cell_h, label)

    out = io.BytesIO()
    canvas.save(
        out,
        format="JPEG",
        quality=max(40, min(95, int(quality))),
        optimize=False,
        progressive=False,
        subsampling=2,
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
    if rot_deg == 90:
        vf_parts.append("transpose=1")
    elif rot_deg == 180:
        vf_parts.append("hflip,vflip")
    elif rot_deg == 270:
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

    q_val = 6 if (target_w * target_h > 300000) else 5
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


class MjpegStreamParser:
    """Incremental parser extracting JPEG frames from multipart/x-mixed-replace or SOI/EOI streams."""

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
            # Fast path: multipart header with exact Content-Length
            header_end = self._buf.find(b"\r\n\r\n")
            soi = self._buf.find(b"\xff\xd8")

            if header_end != -1 and (soi == -1 or header_end < soi):
                header_bytes = bytes(self._buf[:header_end])
                content_len = _parse_content_length(header_bytes)
                body_start = header_end + 4
                if content_len is not None and 0 < content_len <= self._max_frame_bytes:
                    if len(self._buf) < body_start + content_len:
                        break
                    frame = bytes(self._buf[body_start : body_start + content_len])
                    del self._buf[: body_start + content_len]
                    if frame.startswith(b"\xff\xd8"):
                        frames.append(frame)
                    continue
                # Multipart header without usable Content-Length: drop header and scan SOI..EOI
                del self._buf[:body_start]
                continue

            if soi == -1:
                if len(self._buf) > 4096:
                    # Keep tail in case boundary/SOI spans chunk boundary
                    del self._buf[:-64]
                break

            if soi > 0:
                del self._buf[:soi]

            eoi = self._buf.find(b"\xff\xd9", 2)
            if eoi == -1:
                if len(self._buf) > self._max_frame_bytes:
                    self._buf.clear()
                break
            frame = bytes(self._buf[: eoi + 2])
            del self._buf[: eoi + 2]
            frames.append(frame)

        return frames


def _parse_content_length(header_bytes: bytes) -> int | None:
    """Extract integer `Content-Length` from a multipart part header block."""
    for raw_line in header_bytes.split(b"\r\n"):
        if b":" not in raw_line:
            continue
        key, val = raw_line.split(b":", 1)
        if key.strip().lower() == b"content-length":
            val_str = val.strip().decode("ascii", errors="ignore")
            if val_str.isdigit():
                return int(val_str)
    return None


class _LoopbackMjpegTransport:
    """Minimal transport capture shim for HA's `camera.async_get_mjpeg_stream` push model."""

    def __init__(self, queue: asyncio.Queue[bytes | None]) -> None:
        self._queue = queue
        self._closing = False

    def write(self, data: bytes) -> None:
        if not self._closing and data:
            payload = bytes(data)
            if self._queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(payload)

    def is_closing(self) -> bool:
        return self._closing

    def close(self) -> None:
        if not self._closing:
            self._closing = True
            if self._queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(None)


class _LoopbackMjpegRequest:
    """Minimal request stub accepted by Home Assistant camera MJPEG handlers."""

    def __init__(self, transport: _LoopbackMjpegTransport) -> None:
        self.transport = transport
        self.headers: dict[str, str] = {}
        self.query: dict[str, str] = {}
        self.method = "GET"
        self.version = (1, 1)


# ---------------------------------------------------------------------------
# Shared 1-Ingest-Per-Camera Fan-Out Pool
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class _CameraSubscriber:
    """One active video consumer attached to a shared `_CameraIngest`."""

    width: int
    height: int
    fps: int
    fit: str
    rot: int
    circular_mask: bool


@dataclass
class _CameraIngest:
    """Single upstream camera ingest (RTSP FFmpeg -> Native MJPEG -> Snapshot) fanning out to N subscribers."""

    entity_id: str
    subscribers: set[_CameraSubscriber] = field(default_factory=set)
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
    _next_frame_event: asyncio.Event = field(default_factory=asyncio.Event)
    _restart_event: asyncio.Event = field(default_factory=asyncio.Event)
    _task: asyncio.Task[None] | None = None
    _idle_task: asyncio.Task[None] | None = None
    _prime_task: asyncio.Task[None] | None = None
    _idle_since: float = 0.0
    _proc: asyncio.subprocess.Process | None = None
    _sem_acquired: bool = False
    _closed: bool = False

    def publish(
        self,
        frame: bytes,
        *,
        width: int,
        height: int,
        fit: str,
        rot: int,
        is_baseline_420: bool = True,
        is_primer: bool = False,
    ) -> None:
        """Store `frame` as the latest warm frame and wake every waiting subscriber."""
        self.latest_frame = frame
        self.latest_frame_ts = time.monotonic()
        self.latest_seq += 1
        if not is_primer:
            self.live_seq += 1
        self.latest_error = None
        self.stream_w = width
        self.stream_h = height
        self.stream_fit = fit
        self.stream_rot = rot
        self.stream_is_baseline_420 = is_baseline_420
        prev = self._next_frame_event
        self._next_frame_event = asyncio.Event()
        prev.set()

    def publish_error(self, err: Exception) -> None:
        """Record an ingest error and wake waiters so callers can react promptly."""
        self.latest_error = err
        prev = self._next_frame_event
        self._next_frame_event = asyncio.Event()
        prev.set()

    def desired_profile(self) -> tuple[int, int, int, str, int]:
        """Compute highest active subscriber `(w, h, fps, fit, rot)` for the shared ingest."""
        if not self.subscribers:
            return (
                self.stream_w,
                self.stream_h,
                self.stream_fps,
                self.stream_fit,
                self.stream_rot,
            )
        max_w = max(s.width for s in self.subscribers)
        max_h = max(s.height for s in self.subscribers)
        max_fps = max(s.fps for s in self.subscribers)
        fits = {s.fit for s in self.subscribers}
        rots = {s.rot for s in self.subscribers}
        target_fit = next(iter(fits)) if len(fits) == 1 else "contain"
        target_rot = next(iter(rots)) if len(rots) == 1 else 0
        return max_w, max_h, max_fps, target_fit, target_rot


class LatterCameraStreamHub:
    """Shared camera video hub owning 1-ingest-per-camera fan-out, 2x2 grid compositing, and warm snapshots."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        max_concurrent_ingests: int = MAX_CONCURRENT_VIDEO_INGESTS,
        idle_timeout_s: float = VIDEO_INGEST_IDLE_SECONDS,
    ) -> None:
        """Initialize the shared video hub with a dedicated video-only semaphore."""
        self.hass = hass
        self._max_concurrent_ingests = max(1, int(max_concurrent_ingests))
        self._idle_timeout_s = max(0.05, float(idle_timeout_s))
        self._video_semaphore = asyncio.Semaphore(self._max_concurrent_ingests)
        self._ingests: dict[str, _CameraIngest] = {}
        self._subscribe_locks: dict[str, asyncio.Lock] = {}
        self._stream_source_cache: dict[str, tuple[float, str | None]] = {}
        self._ffmpeg_bin_checked: bool = False
        self._cached_ffmpeg_bin: str | None = None

    @property
    def active_ingest_count(self) -> int:
        """Return the number of currently active `_CameraIngest` entries."""
        return len(self._ingests)

    def get_ingest(self, entity_id: str) -> _CameraIngest | None:
        """Return the active `_CameraIngest` for `entity_id`, if any."""
        return self._ingests.get(entity_id)

    async def _async_resolve_ffmpeg_binary(self) -> str | None:
        """Resolve the FFmpeg binary via HA's ffmpeg manager with executor-backed `PATH` fallback."""
        try:
            from homeassistant.components.ffmpeg import get_ffmpeg_manager

            binary = get_ffmpeg_manager(self.hass).binary
            if binary:
                return str(binary)
        except Exception:  # noqa: BLE001
            pass
        if not self._ffmpeg_bin_checked:
            self._cached_ffmpeg_bin = await self.hass.async_add_executor_job(
                shutil.which, "ffmpeg"
            )
            self._ffmpeg_bin_checked = True
        return self._cached_ffmpeg_bin

    async def _async_get_stream_source(self, entity_id: str) -> str | None:
        """Resolve upstream RTSP/stream URL from Home Assistant's camera component."""
        try:
            from homeassistant.components import camera as ha_camera

            url = await ha_camera.async_get_stream_source(self.hass, entity_id)
            result = str(url).strip() if url else None
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("camera.async_get_stream_source(%s) failed: %s", entity_id, err)
            result = None
        self._stream_source_cache[entity_id] = (time.monotonic(), result)
        return result

    async def async_get_cached_stream_source(
        self, entity_id: str, *, ttl_s: float = 60.0
    ) -> str | None:
        """Return a cached stream source URL if fresh, else probe `camera.async_get_stream_source`."""
        cached = self._stream_source_cache.get(entity_id)
        if cached is not None and (time.monotonic() - cached[0]) <= ttl_s:
            return cached[1]
        return await self._async_get_stream_source(entity_id)

    async def _async_terminate_proc(self, proc: asyncio.subprocess.Process | None) -> None:
        """Gracefully terminate an FFmpeg subprocess with kill fallback."""
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=1.5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(proc.wait(), timeout=1.0)
        except ProcessLookupError:
            pass

    async def _subscribe(
        self,
        entity_id: str,
        width: int,
        height: int,
        fps: int,
        *,
        fit: str = "contain",
        rot: int = 0,
        circular_mask: bool = False,
    ) -> tuple[_CameraIngest, _CameraSubscriber]:
        """Attach a subscriber to the shared `_CameraIngest` for `entity_id`, serialized per camera (`M-P1-30`)."""
        cam_lock = self._subscribe_locks.setdefault(entity_id, asyncio.Lock())
        async with cam_lock:
            sub = _CameraSubscriber(
                width=align16(width),
                height=align16(height),
                fps=normalize_fps(fps),
                fit=normalize_fit_mode(fit),
                rot=normalize_rotation(rot),
                circular_mask=bool(
                    circular_mask and normalize_fit_mode(fit) == "fill"
                ),
            )
            ingest = self._ingests.get(entity_id)
            if ingest is None or ingest._closed:
                if self._video_semaphore.locked():
                    idle_candidates = [
                        ing
                        for ing in self._ingests.values()
                        if not ing._closed and not ing.subscribers
                    ]
                    if idle_candidates:
                        victim = min(
                            idle_candidates, key=lambda ing: ing._idle_since
                        )
                        await self._async_stop_ingest(victim)
                try:
                    await asyncio.wait_for(
                        self._video_semaphore.acquire(), timeout=0.25
                    )
                except TimeoutError as err:
                    raise CameraIngestLimitError(
                        f"Maximum concurrent video ingests ({self._max_concurrent_ingests}) reached"
                    ) from err
                ingest = _CameraIngest(
                    entity_id=entity_id,
                    stream_w=sub.width,
                    stream_h=sub.height,
                    stream_fps=sub.fps,
                    stream_fit=sub.fit,
                    stream_rot=sub.rot,
                    _sem_acquired=True,
                )
                ingest.subscribers.add(sub)
                self._ingests[entity_id] = ingest
                ingest._task = self.hass.async_create_background_task(
                    self._async_run_ingest(ingest),
                    name=f"latter_camera_ingest_{entity_id}",
                )
                return ingest, sub

            if ingest._idle_task is not None and not ingest._idle_task.done():
                ingest._idle_task.cancel()
                ingest._idle_task = None
            ingest._idle_since = 0.0

            prev_w, prev_h, prev_fps, prev_fit, prev_rot = (
                ingest.desired_profile()
            )
            ingest.subscribers.add(sub)
            new_w, new_h, new_fps, new_fit, new_rot = ingest.desired_profile()
            if (
                new_w > prev_w
                or new_h > prev_h
                or new_fps > prev_fps
                or (new_fit == "contain" and prev_fit == "fill")
                or (new_rot != prev_rot and prev_rot != 0)
            ):
                ingest._restart_event.set()
            return ingest, sub

    def _unsubscribe(self, ingest: _CameraIngest, sub: _CameraSubscriber) -> None:
        """Detach `sub` and start the idle teardown timer if no subscribers remain."""
        ingest.subscribers.discard(sub)
        if (
            not ingest.subscribers
            and not ingest._closed
            and (ingest._idle_task is None or ingest._idle_task.done())
        ):
            ingest._idle_since = time.monotonic()
            ingest._idle_task = self.hass.async_create_background_task(
                self._async_idle_teardown(ingest),
                name=f"latter_camera_idle_{ingest.entity_id}",
            )

    async def _async_idle_teardown(self, ingest: _CameraIngest) -> None:
        """Stop `ingest` cleanly after `self._idle_timeout_s` with zero active subscribers."""
        try:
            await asyncio.sleep(self._idle_timeout_s)
        except asyncio.CancelledError:
            return
        if ingest.subscribers or ingest._closed:
            return
        await self._async_stop_ingest(ingest)

    async def _async_stop_ingest(self, ingest: _CameraIngest) -> None:
        """Cancel tasks, terminate FFmpeg, and release semaphore for one `_CameraIngest`."""
        ingest._closed = True
        if self._ingests.get(ingest.entity_id) is ingest:
            self._ingests.pop(ingest.entity_id, None)

        idle_task = ingest._idle_task
        ingest._idle_task = None
        if (
            idle_task is not None
            and not idle_task.done()
            and idle_task is not asyncio.current_task()
        ):
            idle_task.cancel()

        prime_task = ingest._prime_task
        ingest._prime_task = None
        if (
            prime_task is not None
            and not prime_task.done()
            and prime_task is not asyncio.current_task()
        ):
            prime_task.cancel()

        proc = ingest._proc
        ingest._proc = None
        await self._async_terminate_proc(proc)

        task = ingest._task
        ingest._task = None
        if (
            task is not None
            and not task.done()
            and task is not asyncio.current_task()
        ):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        if ingest._sem_acquired:
            ingest._sem_acquired = False
            self._video_semaphore.release()

        prev = ingest._next_frame_event
        ingest._next_frame_event = asyncio.Event()
        prev.set()

    async def async_shutdown(self) -> None:
        """Cancel and terminate all active camera ingests cleanly on integration unload."""
        ingests = list(self._ingests.values())
        self._ingests.clear()
        for ingest in ingests:
            await self._async_stop_ingest(ingest)
        self._stream_source_cache.clear()
        self._subscribe_locks.clear()

    async def _async_prime_snapshot(
        self,
        ingest: _CameraIngest,
        width: int,
        height: int,
        fit: str,
        rot: int,
    ) -> None:
        """Fetch one fast snapshot in parallel while cold RTSP/MJPEG connects to cut time-to-first-frame."""
        try:
            from homeassistant.components import camera as ha_camera

            get_img = getattr(ha_camera, "async_get_image", None)
            if not callable(get_img):
                return
            image_obj = await get_img(
                self.hass,
                ingest.entity_id,
                width=width,
                height=height,
                timeout=SNAPSHOT_PRIMER_TIMEOUT_SECONDS,
            )
            if ingest._closed or ingest.latest_seq > 0 or not getattr(image_obj, "content", None):
                return
            encoded = await self.hass.async_add_executor_job(
                partial(
                    transcode_camera_frame,
                    image_obj.content,
                    width,
                    height,
                    fit=fit,
                    rot=rot,
                    circular_mask=False,
                    fast_live=True,
                )
            )
            if not ingest._closed and ingest.latest_seq == 0:
                ingest.publish(
                    encoded,
                    width=width,
                    height=height,
                    fit=fit,
                    rot=rot,
                    is_baseline_420=True,
                    is_primer=True,
                )
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Snapshot primer skipped for %s: %s", ingest.entity_id, err)

    async def _async_run_ingest(self, ingest: _CameraIngest) -> None:
        """Run the 3-tier camera source cascade (RTSP FFmpeg -> Native MJPEG -> Snapshot)."""
        rtsp_empty_attempts = 0
        try:
            while not ingest._closed:
                ingest._restart_event.clear()
                target_w, target_h, target_fps, target_fit, target_rot = (
                    ingest.desired_profile()
                )
                ingest.stream_fps = target_fps

                # Tier 1: RTSP / Stream Source via FFmpeg
                stream_url = await self._async_get_stream_source(ingest.entity_id)
                ffmpeg_bin = (
                    await self._async_resolve_ffmpeg_binary() if stream_url else None
                )
                if stream_url and ffmpeg_bin:
                    # Fire a fast parallel snapshot primer while cold RTSP awaits its first IDR keyframe
                    if (
                        ingest.latest_frame is None
                        and (ingest._prime_task is None or ingest._prime_task.done())
                    ):
                        ingest._prime_task = self.hass.async_create_background_task(
                            self._async_prime_snapshot(
                                ingest, target_w, target_h, target_fit, target_rot
                            ),
                            name=f"latter_camera_prime_{ingest.entity_id}",
                        )
                    ingest.source_tier = "rtsp"
                    live_seq_before = ingest.live_seq
                    restarted = await self._async_run_rtsp_tier(
                        ingest,
                        ffmpeg_bin,
                        stream_url,
                        target_w,
                        target_h,
                        target_fps,
                        target_fit,
                        target_rot,
                    )
                    if ingest._closed:
                        return
                    if restarted:
                        rtsp_empty_attempts = 0
                        continue
                    if ingest.live_seq > live_seq_before:
                        rtsp_empty_attempts = 0
                        await asyncio.sleep(0.5)
                        continue
                    rtsp_empty_attempts += 1
                    if (
                        ingest.live_seq > 0
                        and rtsp_empty_attempts <= MAX_RTSP_EMPTY_RETRIES
                    ):
                        await asyncio.sleep(0.5)
                        continue

                # Tier 2: Native MJPEG stream via camera.async_get_mjpeg_stream
                mjpeg_ok = await self._async_run_mjpeg_tier(ingest)
                if ingest._closed:
                    return
                if mjpeg_ok:
                    if ingest._restart_event.is_set():
                        continue
                    await asyncio.sleep(0.5)
                    continue

                # Tier 3: Snapshot Fallback via camera.async_get_image
                ingest.source_tier = "snapshot"
                await self._async_run_snapshot_tier(ingest)
                if ingest._closed:
                    return
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Camera ingest loop ended for %s: %s", ingest.entity_id, err)
            ingest.publish_error(err)
        finally:
            proc = ingest._proc
            ingest._proc = None
            await self._async_terminate_proc(proc)
            if self._ingests.get(ingest.entity_id) is ingest:
                self._ingests.pop(ingest.entity_id, None)
            if ingest._sem_acquired:
                ingest._sem_acquired = False
                self._video_semaphore.release()

    async def _async_run_rtsp_tier(
        self,
        ingest: _CameraIngest,
        ffmpeg_bin: str,
        stream_url: str,
        width: int,
        height: int,
        fps: int,
        fit: str,
        rot: int,
    ) -> bool:
        """Spawn one low-latency FFmpeg RTSP->MJPEG process and publish frames. Returns True if restart requested."""
        cmd = build_ffmpeg_video_cmd(
            ffmpeg_bin,
            stream_url,
            width,
            height,
            fps,
            fit=fit,
            rot=rot,
        )
        proc: asyncio.subprocess.Process | None = None
        parser = MjpegStreamParser()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            ingest._proc = proc
            if proc.stdout is None:
                return False

            while not ingest._closed:
                if ingest._restart_event.is_set():
                    return True
                read_task = asyncio.create_task(proc.stdout.read(FFMPEG_READ_CHUNK_BYTES))
                restart_task = asyncio.create_task(ingest._restart_event.wait())
                done, pending = await asyncio.wait(
                    {read_task, restart_task},
                    timeout=FFMPEG_READ_TIMEOUT_SECONDS,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await p
                if not done:
                    _LOGGER.debug("RTSP FFmpeg read timeout for %s", ingest.entity_id)
                    return False
                if restart_task in done and ingest._restart_event.is_set():
                    return True
                chunk = read_task.result() if read_task in done else b""
                if not chunk:
                    return False
                for frame in parser.feed(chunk):
                    if ingest._prime_task is not None and not ingest._prime_task.done():
                        ingest._prime_task.cancel()
                        ingest._prime_task = None
                    ingest.publish(
                        frame,
                        width=width,
                        height=height,
                        fit=fit,
                        rot=rot,
                        is_baseline_420=True,
                    )
            return False
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("RTSP FFmpeg ingest failed for %s: %s", ingest.entity_id, err)
            return False
        finally:
            if ingest._proc is proc:
                ingest._proc = None
            await self._async_terminate_proc(proc)

    async def _async_publish_upstream_jpeg(
        self,
        ingest: _CameraIngest,
        raw_frame: bytes,
    ) -> None:
        """Publish an upstream MJPEG frame, transcoding only when required for 16px/Baseline/framing."""
        target_w, target_h, _fps, target_fit, target_rot = ingest.desired_profile()
        is_b420, fw, fh = inspect_jpeg_header(raw_frame)
        already_compatible = (
            is_b420
            and target_rot == 0
            and target_fit == "contain"
            and fw >= MIN_ALIGNED_DIM
            and fh >= MIN_ALIGNED_DIM
            and fw % 16 == 0
            and fh % 16 == 0
            and fw <= target_w
            and fh <= target_h
        )
        if already_compatible:
            ingest.publish(
                raw_frame,
                width=target_w,
                height=target_h,
                fit=target_fit,
                rot=target_rot,
                is_baseline_420=True,
            )
            return
        try:
            encoded = await self.hass.async_add_executor_job(
                lambda: transcode_camera_frame(
                    raw_frame,
                    target_w,
                    target_h,
                    fit=target_fit,
                    rot=target_rot,
                    circular_mask=False,
                    fast_live=True,
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("MJPEG transcode failed for %s: %s", ingest.entity_id, err)
            return
        ingest.publish(
            encoded,
            width=target_w,
            height=target_h,
            fit=target_fit,
            rot=target_rot,
            is_baseline_420=True,
        )

    async def _async_run_mjpeg_tier(self, ingest: _CameraIngest) -> bool:
        """Attempt Tier 2 native MJPEG ingest via `camera.async_get_mjpeg_stream`."""
        from homeassistant.components import camera as ha_camera

        mjpeg_fn = getattr(ha_camera, "async_get_mjpeg_stream", None)
        if not callable(mjpeg_fn):
            return False

        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=MJPEG_QUEUE_MAXSIZE)
        transport = _LoopbackMjpegTransport(queue)
        request = _LoopbackMjpegRequest(transport)
        parser = MjpegStreamParser()
        got_any_frame = False

        async def _invoke_mjpeg() -> Any:
            try:
                return await mjpeg_fn(self.hass, request, ingest.entity_id)
            finally:
                transport.close()

        producer = asyncio.create_task(_invoke_mjpeg())
        try:
            while not ingest._closed and not ingest._restart_event.is_set():
                get_task: asyncio.Task[bytes | None] = asyncio.create_task(
                    queue.get()
                )
                try:
                    done, _pending = await asyncio.wait(
                        {get_task, producer},
                        timeout=FFMPEG_READ_TIMEOUT_SECONDS,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        break

                    queue_eof = False
                    if get_task in done:
                        chunk = (
                            None
                            if get_task.cancelled() or get_task.exception() is not None
                            else get_task.result()
                        )
                        if chunk is None:
                            queue_eof = True
                        else:
                            for frame in parser.feed(chunk):
                                if not got_any_frame:
                                    ingest.source_tier = "mjpeg"
                                    got_any_frame = True
                                await self._async_publish_upstream_jpeg(ingest, frame)
                finally:
                    if not get_task.done():
                        get_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await get_task

                if producer in done or (queue_eof and producer.done()):
                    if producer.cancelled():
                        break
                    if (prod_exc := producer.exception()) is not None:
                        raise prod_exc
                    result = producer.result()
                    if result is None:
                        break
                    # Handle async-iterable or aiohttp-style response returns directly
                    if hasattr(result, "__aiter__"):
                        async for raw_chunk in result:
                            if ingest._closed or ingest._restart_event.is_set():
                                break
                            for frame in parser.feed(bytes(raw_chunk)):
                                if not got_any_frame:
                                    ingest.source_tier = "mjpeg"
                                    got_any_frame = True
                                await self._async_publish_upstream_jpeg(ingest, frame)
                    elif hasattr(result, "content") and hasattr(
                        result.content, "iter_chunked"
                    ):
                        async for raw_chunk in result.content.iter_chunked(
                            FFMPEG_READ_CHUNK_BYTES
                        ):
                            if ingest._closed or ingest._restart_event.is_set():
                                break
                            for frame in parser.feed(bytes(raw_chunk)):
                                if not got_any_frame:
                                    ingest.source_tier = "mjpeg"
                                    got_any_frame = True
                                await self._async_publish_upstream_jpeg(ingest, frame)
                    elif isinstance(getattr(result, "body", None), (bytes, bytearray)):
                        for frame in parser.feed(bytes(result.body)):
                            if not got_any_frame:
                                ingest.source_tier = "mjpeg"
                                got_any_frame = True
                            await self._async_publish_upstream_jpeg(ingest, frame)
                    break
                if queue_eof:
                    break
            return got_any_frame
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Native MJPEG ingest failed for %s: %s", ingest.entity_id, err)
            return got_any_frame
        finally:
            transport.close()
            if not producer.done():
                producer.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await producer

    async def _async_run_snapshot_tier(self, ingest: _CameraIngest) -> None:
        """Tier 3 paced snapshot fallback emitting Baseline 4:2:0 JPEG frames via `camera.async_get_image`."""
        from homeassistant.components import camera as ha_camera

        while not ingest._closed:
            t0 = time.monotonic()
            target_w, target_h, target_fps, target_fit, target_rot = (
                ingest.desired_profile()
            )
            try:
                image_obj = await ha_camera.async_get_image(
                    self.hass,
                    ingest.entity_id,
                    width=target_w,
                    height=target_h,
                    timeout=8,
                )
                encoded = await self.hass.async_add_executor_job(
                    partial(
                        transcode_camera_frame,
                        image_obj.content,
                        target_w,
                        target_h,
                        fit=target_fit,
                        rot=target_rot,
                        circular_mask=False,
                        fast_live=True,
                    )
                )
                ingest.publish(
                    encoded,
                    width=target_w,
                    height=target_h,
                    fit=target_fit,
                    rot=target_rot,
                    is_baseline_420=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "Snapshot ingest failed for %s: %s", ingest.entity_id, err
                )
                ingest.publish_error(CameraFetchError(str(err)))
                await asyncio.sleep(1.0)
                continue

            elapsed = time.monotonic() - t0
            interval = 1.0 / float(max(MIN_VIDEO_FPS, target_fps))
            sleep_for = interval - elapsed
            if sleep_for > 0.005:
                await asyncio.sleep(sleep_for)

    async def _async_format_for_subscriber(
        self,
        ingest: _CameraIngest,
        sub: _CameraSubscriber,
        frame: bytes,
    ) -> bytes:
        """Pass `frame` zero-copy when matching subscriber profile, else fast-downscale in executor."""
        if (
            ingest.stream_is_baseline_420
            and not sub.circular_mask
            and sub.width == ingest.stream_w
            and sub.height == ingest.stream_h
            and sub.fit == ingest.stream_fit
            and sub.rot == ingest.stream_rot
        ):
            return frame
        eff_rot = (sub.rot - ingest.stream_rot) % 360
        out: bytes = await self.hass.async_add_executor_job(
            lambda: transcode_camera_frame(
                frame,
                sub.width,
                sub.height,
                fit=sub.fit,
                rot=eff_rot,
                circular_mask=sub.circular_mask,
                fast_live=True,
            )
        )
        return out

    async def async_get_snapshot(
        self,
        entity_id: str,
        width: int,
        height: int,
        *,
        fit: str = "contain",
        rot: int = 0,
        circular_mask: bool = False,
        max_age_s: float = SNAPSHOT_CACHE_MAX_AGE_SECONDS,
    ) -> tuple[bytes, bool]:
        """Return `(jpeg_bytes, from_warm_ingest)` immediately if warm, else fetch & transcode."""
        target_w = align16(width)
        target_h = align16(height)
        fit_mode = normalize_fit_mode(fit)
        rot_deg = normalize_rotation(rot)
        use_mask = bool(circular_mask and fit_mode == "fill")

        ingest = self._ingests.get(entity_id)
        if (
            ingest is not None
            and ingest.latest_frame is not None
            and (time.monotonic() - ingest.latest_frame_ts) <= max_age_s
        ):
            sub = _CameraSubscriber(
                width=target_w,
                height=target_h,
                fps=1,
                fit=fit_mode,
                rot=rot_deg,
                circular_mask=use_mask,
            )
            try:
                jpeg = await self._async_format_for_subscriber(
                    ingest, sub, ingest.latest_frame
                )
            except Exception as err:
                raise CameraTranscodeError(str(err)) from err
            return jpeg, True

        from homeassistant.components import camera as ha_camera

        try:
            image_obj = await ha_camera.async_get_image(
                self.hass, entity_id, width=target_w, height=target_h, timeout=8
            )
        except Exception as err:
            raise CameraFetchError(str(err)) from err

        try:
            jpeg = await self.hass.async_add_executor_job(
                partial(
                    transcode_camera_frame,
                    image_obj.content,
                    target_w,
                    target_h,
                    fit=fit_mode,
                    rot=rot_deg,
                    circular_mask=use_mask,
                    fast_live=True,
                )
            )
        except Exception as err:
            raise CameraTranscodeError(str(err)) from err
        return jpeg, False

    async def async_iter_stream_frames(
        self,
        entity_id: str,
        width: int,
        height: int,
        *,
        fps: int = 10,
        fit: str = "contain",
        rot: int = 0,
        circular_mask: bool = False,
        wait_timeout_s: float = STREAM_WAIT_TIMEOUT_SECONDS,
    ) -> AsyncIterator[bytes]:
        """Yield Baseline 4:2:0 JPEG frames for one camera from the shared `_CameraIngest` pool."""
        ingest, sub = await self._subscribe(
            entity_id,
            width,
            height,
            fps,
            fit=fit,
            rot=rot,
            circular_mask=circular_mask,
        )
        min_interval = 1.0 / float(sub.fps)
        last_seq = 0
        last_emit = 0.0
        try:
            while not ingest._closed:
                if ingest.latest_seq > last_seq and ingest.latest_frame is not None:
                    now = time.monotonic()
                    if last_emit > 0.0 and (now - last_emit) < min_interval * 0.9:
                        await asyncio.sleep(min_interval - (now - last_emit))
                    frame = ingest.latest_frame
                    last_seq = ingest.latest_seq
                    if frame is None:
                        continue
                    out_bytes = await self._async_format_for_subscriber(ingest, sub, frame)
                    last_emit = time.monotonic()
                    yield out_bytes
                    continue

                if ingest.latest_frame is None and ingest.latest_error is not None:
                    raise CameraFetchError(str(ingest.latest_error)) from ingest.latest_error

                ev = ingest._next_frame_event
                try:
                    await asyncio.wait_for(ev.wait(), timeout=wait_timeout_s)
                except TimeoutError:
                    if ingest.latest_frame is not None:
                        out_bytes = await self._async_format_for_subscriber(
                            ingest, sub, ingest.latest_frame
                        )
                        last_emit = time.monotonic()
                        yield out_bytes
                    elif ingest.latest_error is not None:
                        raise CameraFetchError(str(ingest.latest_error)) from ingest.latest_error
                else:
                    if ingest.latest_frame is None and ingest.latest_error is not None:
                        raise CameraFetchError(str(ingest.latest_error)) from ingest.latest_error
        finally:
            self._unsubscribe(ingest, sub)

    async def async_iter_mjpeg_chunks(
        self,
        entity_id: str,
        width: int,
        height: int,
        *,
        fps: int = 10,
        fit: str = "contain",
        rot: int = 0,
        circular_mask: bool = False,
    ) -> AsyncGenerator[bytes, None]:
        """Yield multipart MJPEG chunks with exact `Content-Length` headers for HTTP streaming."""
        async for frame in self.async_iter_stream_frames(
            entity_id,
            width,
            height,
            fps=fps,
            fit=fit,
            rot=rot,
            circular_mask=circular_mask,
        ):
            yield format_mjpeg_chunk(frame)

    async def async_iter_grid_frames(
        self,
        entity_ids: list[str],
        width: int,
        height: int,
        *,
        fps: int = 5,
        fit: str = "contain",
        stale_after_s: float = GRID_STALE_FRAME_SECONDS,
        label_overrides: Mapping[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        """Subscribe to up to 4 shared camera ingests and yield composited 2x2 Baseline JPEG frames."""
        cams = [c.strip() for c in entity_ids if c and c.strip()][:4]
        out_w = align16(width)
        out_h = align16(height)
        target_fps = normalize_fps(fps, default=5)
        fit_mode = normalize_fit_mode(fit)
        quad_w = align16((out_w - GRID_GUTTER_PX) // 2)
        quad_h = align16((out_h - GRID_GUTTER_PX) // 2)

        overrides = label_overrides or {}
        labels: list[str] = []
        for cam in cams:
            custom_lbl = str(overrides.get(cam) or "").strip()
            if custom_lbl:
                labels.append(custom_lbl)
                continue
            st = self.hass.states.get(cam)
            friendly = (
                str(st.attributes.get("friendly_name") or "").strip()
                if st is not None
                else ""
            )
            labels.append(
                friendly or cam.split(".", 1)[-1].replace("_", " ").title()
            )

        attached: list[tuple[_CameraIngest, _CameraSubscriber] | None] = []
        limit_err: CameraIngestLimitError | None = None
        interval = 1.0 / float(target_fps)
        try:
            for cam in cams:
                try:
                    pair = await self._subscribe(
                        cam,
                        quad_w,
                        quad_h,
                        target_fps,
                        fit=fit_mode,
                        rot=0,
                        circular_mask=False,
                    )
                    attached.append(pair)
                except CameraIngestLimitError as err:
                    limit_err = err
                    _LOGGER.debug("Grid slot %s hit video ingest limit: %s", cam, err)
                    attached.append(None)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Grid slot %s unavailable: %s", cam, err)
                    attached.append(None)

            active_ingests = [pair[0] for pair in attached if pair is not None]
            if not active_ingests and limit_err is not None:
                raise limit_err

            # Wait briefly for at least one slot to publish its first frame
            if active_ingests and not any(ing.latest_frame is not None for ing in active_ingests):
                waiters = [
                    asyncio.create_task(ing._next_frame_event.wait())
                    for ing in active_ingests
                ]
                done, pending = await asyncio.wait(
                    waiters,
                    timeout=min(1.5, interval * 2.0),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                _ = done
                for p in pending:
                    p.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await p

            while True:
                t0 = time.monotonic()
                now = t0
                slot_frames: list[bytes | None] = []
                for attached_pair in attached:
                    if attached_pair is None:
                        slot_frames.append(None)
                        continue
                    ing = attached_pair[0]
                    if (
                        ing.latest_frame is not None
                        and (now - ing.latest_frame_ts) <= stale_after_s
                    ):
                        slot_frames.append(ing.latest_frame)
                    else:
                        slot_frames.append(None)

                grid_jpeg = await self.hass.async_add_executor_job(
                    lambda sf=slot_frames: compose_grid_frame(
                        sf,
                        labels,
                        out_w,
                        out_h,
                        fit=fit_mode,
                    )
                )
                yield grid_jpeg

                elapsed = time.monotonic() - t0
                sleep_for = interval - elapsed
                if sleep_for > 0.005:
                    await asyncio.sleep(sleep_for)
        finally:
            for attached_pair in attached:
                if attached_pair is not None:
                    self._unsubscribe(attached_pair[0], attached_pair[1])

    async def async_iter_grid_mjpeg_chunks(
        self,
        entity_ids: list[str],
        width: int,
        height: int,
        *,
        fps: int = 5,
        fit: str = "contain",
        label_overrides: Mapping[str, str] | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """Yield multipart MJPEG chunks for the server-side 2x2 camera grid."""
        async for frame in self.async_iter_grid_frames(
            entity_ids,
            width,
            height,
            fps=fps,
            fit=fit,
            label_overrides=label_overrides,
        ):
            yield format_mjpeg_chunk(frame)


# ---------------------------------------------------------------------------
# Camera Capabilities Helper (Protocol v3 `caps` Bitmask & Studio Metadata)
# ---------------------------------------------------------------------------


def resolve_camera_capabilities(
    hass: HomeAssistant,
    camera_entity_id: str,
    *,
    doorbell_ring_map: Mapping[str, str] | Collection[str] | None = None,
    carousel_entities: Collection[str] | None = None,
    volume_overrides: dict[str, str] | None = None,
    camera_config: Mapping[str, Any] | None = None,
    stream_source: str | None = None,
    has_mjpeg_stream: bool = False,
) -> dict[str, Any]:
    """Compute Protocol v3 camera `caps` bitmask and Studio capability metadata synchronously."""
    cam_ent = (camera_entity_id or "").strip()
    state = hass.states.get(cam_ent) if cam_ent else None
    attrs = state.attributes if state is not None else {}

    target_info = resolve_doorbell_targets(hass, cam_ent, volume_overrides)
    door_speaker = str(target_info.get("door_speaker") or "")
    area_id = str(
        target_info.get("area_id")
        or (get_area_state_index(hass).resolve_entity_area_id(cam_ent) if cam_ent else "")
        or ""
    )
    friendly_name = str(
        attrs.get("friendly_name")
        or target_info.get("friendly_name")
        or (cam_ent.split(".", 1)[-1].replace("_", " ").title() if cam_ent else "Camera")
    )

    try:
        supported_features = int(attrs.get("supported_features") or 0)
    except (TypeError, ValueError):
        supported_features = 0
    supports_stream = bool(supported_features & _CAMERA_FEATURE_STREAM)

    platform = str(target_info.get("platform") or "").lower()
    if not platform and cam_ent:
        ent_entry = er.async_get(hass).async_get(cam_ent)
        if ent_entry is not None:
            platform = str(ent_entry.platform or "").lower()

    has_stream = bool(stream_source) or supports_stream
    has_talkback = bool(door_speaker)

    if isinstance(doorbell_ring_map, Mapping):
        doorbell_cams = set(doorbell_ring_map.values())
    elif doorbell_ring_map is not None:
        doorbell_cams = set(doorbell_ring_map)
    else:
        doorbell_cams = set()
    is_doorbell = bool(cam_ent and cam_ent in doorbell_cams)

    carousel_set = {str(e).strip() for e in (carousel_entities or ()) if str(e).strip()}
    in_carousel = bool(cam_ent and cam_ent in carousel_set)

    if has_stream:
        stream_kind = "rtsp"
    elif has_mjpeg_stream or platform == "mjpeg" or bool(attrs.get("mjpeg_url")):
        stream_kind = "mjpeg"
    else:
        stream_kind = "snapshot"

    cfg = camera_config if isinstance(camera_config, Mapping) else {}
    custom_label = str(cfg.get("label") or "").strip()[:32]
    display_name = custom_label or friendly_name

    raw_listen = cfg.get("show_listen")
    raw_has_audio = attrs.get("has_audio")
    if raw_has_audio is None:
        raw_has_audio = attrs.get("audio")
    if isinstance(raw_has_audio, bool):
        has_audio = raw_has_audio
    elif raw_has_audio is not None:
        has_audio = str(raw_has_audio).strip().lower() in ("1", "true", "yes", "on")
    else:
        has_audio = bool(
            stream_kind == "rtsp"
            and (is_doorbell or has_talkback or raw_listen is True)
        )

    show_listen = (
        bool(raw_listen)
        if isinstance(raw_listen, bool)
        else bool(is_doorbell and has_audio)
    )
    raw_talk = cfg.get("show_talk")
    show_talk = bool(raw_talk) if isinstance(raw_talk, bool) else bool(is_doorbell and has_talkback)
    raw_reply = cfg.get("show_reply")
    show_reply = bool(raw_reply) if isinstance(raw_reply, bool) else bool(is_doorbell and has_talkback)
    raw_unlock = str(cfg.get("unlock_entity") or "").strip()
    unlock_entity = raw_unlock if raw_unlock.startswith(("lock.", "cover.")) else ""

    caps = 0
    if show_listen:
        caps |= CAMERA_CAP_HAS_AUDIO
    if show_talk:
        caps |= CAMERA_CAP_HAS_TALKBACK
    if is_doorbell:
        caps |= CAMERA_CAP_IS_DOORBELL
    if in_carousel:
        caps |= CAMERA_CAP_IN_CAROUSEL
    if show_reply:
        caps |= CAMERA_CAP_SHOW_REPLY
    if unlock_entity:
        caps |= CAMERA_CAP_SHOW_UNLOCK

    return {
        "entity_id": cam_ent,
        "name": display_name,
        "friendly_name": friendly_name,
        "label": custom_label,
        "area_id": area_id,
        "caps": caps,
        "has_audio": has_audio,
        "has_talkback": has_talkback,
        "show_listen": show_listen,
        "show_talk": show_talk,
        "show_reply": show_reply,
        "unlock_entity": unlock_entity,
        "is_doorbell": is_doorbell,
        "in_carousel": in_carousel,
        "stream_kind": stream_kind,
        "door_speaker": door_speaker,
    }


# ---------------------------------------------------------------------------
# Singleton Accessor & Shutdown
# ---------------------------------------------------------------------------


def get_camera_stream_hub(hass: HomeAssistant) -> LatterCameraStreamHub:
    """Return (or lazily create) the singleton `LatterCameraStreamHub` on `hass.data[DOMAIN]`."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    hub = domain_data.get(DATA_CAMERA_HUB)
    if not isinstance(hub, LatterCameraStreamHub):
        hub = LatterCameraStreamHub(hass)
        domain_data[DATA_CAMERA_HUB] = hub
    return hub


async def async_shutdown_camera_stream_hub(hass: HomeAssistant) -> None:
    """Shut down and remove the singleton `LatterCameraStreamHub` on integration unload."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return
    hub = domain_data.pop(DATA_CAMERA_HUB, None)
    if isinstance(hub, LatterCameraStreamHub):
        await hub.async_shutdown()
