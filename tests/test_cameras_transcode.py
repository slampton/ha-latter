"""Tests for camera JPEG geometry alignment, circular masking, MJPEG parsing, and FFmpeg flags."""

from __future__ import annotations

import io
from typing import Any

from PIL import Image
import pytest

from custom_components.latter.cameras import transcode as cameras_mod
from custom_components.latter.cameras.transcode import (
    MjpegStreamParser,
    align16,
    build_ffmpeg_video_cmd,
    compute_contain_size,
    format_mjpeg_chunk,
    inspect_jpeg_header,
    normalize_fit_mode,
    normalize_fps,
    normalize_rotation,
    transcode_camera_frame,
)


def _make_baseline_420_jpeg(width: int, height: int) -> bytes:
    """Build a valid Baseline 4:2:0 JPEG (real via Pillow when installed, SOF0 stub fallback)."""
    real_raw = _make_real_or_stub_jpeg(width, height)
    is_b420, rw, rh = inspect_jpeg_header(real_raw)
    if is_b420 and rw == width and rh == height:
        return real_raw
    sof0 = (
        b"\xff\xc0"
        + (17).to_bytes(2, "big")
        + b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03"
        + b"\x01\x22\x00"
        + b"\x02\x11\x01"
        + b"\x03\x11\x01"
    )
    sos = b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x00"
    return b"\xff\xd8" + sof0 + sos + b"\xff\xd9"

def _make_real_or_stub_jpeg(width: int = 320, height: int = 240) -> bytes:
    """Create a valid RGB JPEG for transcode tests."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (40, 120, 200)).save(
        buf, format="JPEG", quality=85, subsampling=2
    )
    return buf.getvalue()


def _jpeg_size(raw: bytes) -> tuple[int, int]:
    _is_b420, w, h = inspect_jpeg_header(raw)
    if w > 0 and h > 0:
        return w, h
    with Image.open(io.BytesIO(raw)) as im:
        return im.size


def test_align16_and_contain_aspect_preservation() -> None:
    """Output dimensions are always multiples of 16 (>= 64) and preserve native aspect ratios."""
    assert align16(466) == 464
    assert align16(270) == 256
    assert align16(12) == 64
    assert align16(2000) == 1280

    # 16:9 landscape into 466x466 round screen -> uncropped 464x256
    w16, h16 = compute_contain_size(1920, 1080, 466, 466)
    assert (w16, h16) == (464, 256)
    assert w16 % 16 == 0 and h16 % 16 == 0

    # 9:16 vertical doorbell into 800x480 panel -> uncropped 256x480
    wv, hv = compute_contain_size(1080, 1920, 800, 480)
    assert (wv, hv) == (256, 480)
    assert wv % 16 == 0 and hv % 16 == 0

    # 4:3 camera into 800x480 -> uncropped 640x480
    w43, h43 = compute_contain_size(640, 480, 800, 480)
    assert (w43, h43) == (640, 480)

    assert normalize_fit_mode(None) == "contain"
    assert normalize_fit_mode("contain") == "contain"
    assert normalize_fit_mode("FILL") == "fill"
    assert normalize_fps(99) == 15
    assert normalize_fps(0) == 1
    assert normalize_fps("bad", default=7) == 7
    assert normalize_rotation("90") == 90
    with pytest.raises(ValueError):
        normalize_rotation("45")


def test_transcode_contain_vs_fill_and_circular_mask(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default `fit='contain'` preserves aspect ratio with zero crop; `fit='fill'` fills target & supports circular mask."""
    raw_16x9 = _make_real_or_stub_jpeg(640, 360)

    out_contain = transcode_camera_frame(raw_16x9, 466, 466, fit="contain", circular_mask=True)
    cw, ch = _jpeg_size(out_contain)
    assert (cw, ch) == (464, 256)

    # Confirm circular_mask is ONLY invoked for fit="fill", never for fit="contain"
    mask_calls: list[tuple[int, int]] = []
    orig_mask = cameras_mod.get_circular_mask_surfaces

    def _spy_mask(w: int, h: int) -> Any:
        mask_calls.append((w, h))
        return orig_mask(w, h)

    monkeypatch.setattr(cameras_mod, "get_circular_mask_surfaces", _spy_mask)

    transcode_camera_frame(raw_16x9, 466, 466, fit="contain", circular_mask=True)
    assert mask_calls == []

    out_fill = transcode_camera_frame(raw_16x9, 466, 466, fit="fill", circular_mask=True)
    assert _jpeg_size(out_fill) == (464, 464)
    assert mask_calls == [(464, 464)]

    # Rotation 90 swaps 640x360 -> 360x640 before fitting into 464x464 -> 256x464
    out_rot = transcode_camera_frame(raw_16x9, 466, 466, fit="contain", rot=90)
    assert _jpeg_size(out_rot) == (256, 464)


def test_mjpeg_parser_and_chunk_content_length() -> None:
    """Multipart MJPEG chunks include exact Content-Length and parse cleanly across arbitrary splits."""
    f1 = _make_baseline_420_jpeg(320, 192)
    f2 = _make_baseline_420_jpeg(480, 272)

    chunk1 = format_mjpeg_chunk(f1)
    assert b"--latterframe\r\n" in chunk1
    assert f"Content-Length: {len(f1)}\r\n\r\n".encode("ascii") in chunk1

    combined = chunk1 + format_mjpeg_chunk(f2)
    parser = MjpegStreamParser()
    extracted: list[bytes] = []
    for i in range(0, len(combined), 17):
        extracted.extend(parser.feed(combined[i : i + 17]))
    assert extracted == [f1, f2]

    # Boundary-only stream without Content-Length (SOI..EOI fallback)
    no_cl = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + f1 + b"\r\n--frame\r\n"
    assert MjpegStreamParser().feed(no_cl) == [f1]

    # Header inspection distinguishes Baseline 4:2:0 SOF0 from progressive SOF2
    is_b420, w, h = inspect_jpeg_header(f1)
    assert (is_b420, w, h) == (True, 320, 192)
    progressive = f1.replace(b"\xff\xc0", b"\xff\xc2", 1)
    is_prog_b420, pw, ph = inspect_jpeg_header(progressive)
    assert (is_prog_b420, pw, ph) == (False, 320, 192)


def test_build_ffmpeg_video_cmd_flags() -> None:
    """FFmpeg video command enforces low-latency RTSP TCP flags and 16px-aligned Baseline 4:2:0 MJPEG."""
    cmd = build_ffmpeg_video_cmd(
        "ffmpeg",
        "rtsp://192.168.1.50/stream1",
        466,
        466,
        15,
        fit="contain",
        rot=90,
    )
    assert "-rtsp_transport" in cmd and cmd[cmd.index("-rtsp_transport") + 1] == "tcp"
    assert "-fflags" in cmd and "+nobuffer+discardcorrupt" in cmd
    assert "-flags" in cmd and "low_delay" in cmd
    assert "-flags2" in cmd and "+fast" in cmd
    assert "-analyzeduration" in cmd and "250000" in cmd
    assert "-probesize" in cmd and "200000" in cmd
    assert "-an" in cmd
    assert "-r" in cmd and cmd[cmd.index("-r") + 1] == "15"
    assert "-pix_fmt" in cmd and cmd[cmd.index("-pix_fmt") + 1] == "yuvj420p"
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "mjpeg"
    assert "-flush_packets" in cmd and cmd[cmd.index("-flush_packets") + 1] == "1"
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "mpjpeg"
    assert cmd[-1] == "pipe:1"
    vf = cmd[cmd.index("-vf") + 1]
    assert "transpose=1" in vf
    assert "scale=464:464:force_original_aspect_ratio=decrease:force_divisible_by=16" in vf

    cmd_fill = build_ffmpeg_video_cmd("ffmpeg", "http://cam/live", 480, 320, 8, fit="fill")
    assert "-rtsp_transport" not in cmd_fill
    assert "crop=480:320" in cmd_fill[cmd_fill.index("-vf") + 1]
