"""Unit tests for `LatterCameraStreamHub`, 3-tier cascade, 1-ingest fan-out, 2x2 grid, and camera caps."""

from __future__ import annotations

import asyncio
import io
import sys
from types import SimpleNamespace
from typing import Any

from PIL import Image
import pytest

from custom_components.latter import cameras as cameras_mod
from custom_components.latter.cameras import (
    CAMERA_CAP_HAS_AUDIO,
    CAMERA_CAP_HAS_TALKBACK,
    CAMERA_CAP_IN_CAROUSEL,
    CAMERA_CAP_IS_DOORBELL,
    MAX_CONCURRENT_VIDEO_INGESTS,
    CameraFetchError,
    CameraIngestLimitError,
    LatterCameraStreamHub,
    MjpegStreamParser,
    align16,
    async_resolve_camera_capabilities,
    async_shutdown_camera_stream_hub,
    build_ffmpeg_video_cmd,
    compose_grid_frame,
    compute_contain_size,
    format_mjpeg_chunk,
    get_camera_stream_hub,
    inspect_jpeg_header,
    normalize_fit_mode,
    normalize_fps,
    normalize_rotation,
    resolve_camera_capabilities,
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


def _make_real_or_stub_jpeg(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (36, 92, 148)).save(
        buf, format="JPEG", progressive=False, subsampling=2
    )
    return buf.getvalue()


def _jpeg_size(raw: bytes) -> tuple[int, int]:
    _is_b420, w, h = inspect_jpeg_header(raw)
    if w > 0 and h > 0:
        return w, h
    with Image.open(io.BytesIO(raw)) as im:
        return im.size


class _FakeStdout:
    """Async byte stream feeding chunks on demand like an FFmpeg stdout pipe."""

    def __init__(self, chunks: list[bytes], *, stall_after: bool = False) -> None:
        self._chunks = list(chunks)
        self._stall_after = stall_after
        self._closed = False
        self._gate = asyncio.Event()

    def close(self) -> None:
        self._closed = True
        self._gate.set()

    async def read(self, _n: int = 32768) -> bytes:
        if self._chunks:
            await asyncio.sleep(0.001)
            return self._chunks.pop(0)
        if self._stall_after and not self._closed:
            await self._gate.wait()
        return b""


class _FakeSubprocess:
    """Minimal asyncio.subprocess.Process double recording terminate/kill calls."""

    def __init__(self, chunks: list[bytes], *, stall_after: bool = True) -> None:
        self.stdout = _FakeStdout(chunks, stall_after=stall_after)
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0
        self.stdout.close()

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9
        self.stdout.close()

    async def wait(self) -> int:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


# ---------------------------------------------------------------------------
# Pure Math, Framing, Alignment & Parser Unit Tests
# ---------------------------------------------------------------------------


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
    orig_mask = cameras_mod._get_circular_mask_surfaces

    def _spy_mask(w: int, h: int) -> Any:
        mask_calls.append((w, h))
        return orig_mask(w, h)

    monkeypatch.setattr(cameras_mod, "_get_circular_mask_surfaces", _spy_mask)

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
    assert "-fflags" in cmd and "nobuffer" in cmd
    assert "-flags" in cmd and "low_delay" in cmd
    assert "-analyzeduration" in cmd and "500000" in cmd
    assert "-probesize" in cmd and "500000" in cmd
    assert "-an" in cmd
    assert "-pix_fmt" in cmd and cmd[cmd.index("-pix_fmt") + 1] == "yuvj420p"
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "mjpeg"
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "mpjpeg"
    assert cmd[-1] == "pipe:1"
    vf = cmd[cmd.index("-vf") + 1]
    assert "transpose=1" in vf
    assert "fps=15" in vf
    assert "scale=464:464:force_original_aspect_ratio=decrease:force_divisible_by=16" in vf

    cmd_fill = build_ffmpeg_video_cmd("ffmpeg", "http://cam/live", 480, 320, 8, fit="fill")
    assert "-rtsp_transport" not in cmd_fill
    assert "crop=480:320" in cmd_fill[cmd_fill.index("-vf") + 1]


# ---------------------------------------------------------------------------
# 3-Tier Cascade & Shared 1-Ingest-Per-Camera Fan-Out Tests
# ---------------------------------------------------------------------------


async def test_rtsp_tier_1_ingest_fanout_and_zero_copy(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two subscribers on one RTSP camera share 1 FFmpeg ingest; exact match is zero-copy, smaller downscales."""
    hass.data.setdefault("_camera_streams", {})["camera.front_door"] = (
        "rtsp://10.0.0.10/front"
    )
    frame_a = _make_baseline_420_jpeg(464, 256)
    frame_b = _make_baseline_420_jpeg(464, 256)
    spawned: list[_FakeSubprocess] = []

    async def _fake_exec(*cmd: str, **_kwargs: Any) -> _FakeSubprocess:
        _ = cmd
        proc = _FakeSubprocess(
            [format_mjpeg_chunk(frame_a), format_mjpeg_chunk(frame_b)],
            stall_after=True,
        )
        spawned.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

    transcode_calls: list[tuple[int, int]] = []
    orig_transcode = cameras_mod.transcode_camera_frame

    def _spy_transcode(raw: bytes, max_w: int, max_h: int, **kwargs: Any) -> bytes:
        transcode_calls.append((max_w, max_h))
        return orig_transcode(raw, max_w, max_h, **kwargs)

    monkeypatch.setattr(cameras_mod, "transcode_camera_frame", _spy_transcode)

    hub = LatterCameraStreamHub(hass, idle_timeout_s=0.1)
    try:
        gen_primary = hub.async_iter_stream_frames(
            "camera.front_door", 466, 466, fps=10, fit="contain"
        )
        gen_secondary = hub.async_iter_stream_frames(
            "camera.front_door", 240, 240, fps=5, fit="contain"
        )

        # Primary exact match gets zero-copy JPEG bytes (exact identity `is` or equal without Pillow)
        p_frame = await anext(gen_primary)
        assert p_frame == frame_a
        assert len(spawned) == 1
        assert transcode_calls == []
        assert hub.get_ingest("camera.front_door").source_tier == "rtsp"

        # Secondary smaller subscriber reuses the SAME single FFmpeg ingest and downscales via Pillow
        s_frame = await anext(gen_secondary)
        assert len(spawned) == 1
        assert transcode_calls == [(240, 240)]
        sw, sh = _jpeg_size(s_frame)
        assert sw <= 240 and sh <= 240 and sw % 16 == 0 and sh % 16 == 0

        await gen_primary.aclose()
        await gen_secondary.aclose()
        # Idle teardown stops FFmpeg cleanly after idle_timeout_s
        await asyncio.sleep(0.18)
        assert hub.active_ingest_count == 0
        assert spawned[0].terminated is True
    finally:
        await hub.async_shutdown()


async def test_mjpeg_tier2_fallback_when_no_rtsp(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When `async_get_stream_source` returns None, hub cascades to Tier 2 `camera.async_get_mjpeg_stream`."""
    cam_mod = sys.modules["homeassistant.components.camera"]
    raw_frame = _make_baseline_420_jpeg(320, 192)
    mjpeg_payload = format_mjpeg_chunk(raw_frame)

    async def _fake_mjpeg_stream(_hass: Any, _request: Any, entity_id: str) -> Any:
        assert entity_id == "camera.garage"
        return SimpleNamespace(body=mjpeg_payload)

    monkeypatch.setattr(cam_mod, "async_get_mjpeg_stream", _fake_mjpeg_stream, raising=False)

    hub = LatterCameraStreamHub(hass, idle_timeout_s=0.1)
    try:
        chunks_gen = hub.async_iter_mjpeg_chunks("camera.garage", 320, 240, fps=5)
        chunk = await anext(chunks_gen)
        assert chunk.startswith(b"--latterframe\r\n")
        assert f"Content-Length: {len(raw_frame)}\r\n\r\n".encode("ascii") in chunk
        assert hub.get_ingest("camera.garage").source_tier == "mjpeg"
        await chunks_gen.aclose()
    finally:
        await hub.async_shutdown()


async def test_snapshot_tier3_fallback_when_no_rtsp_or_mjpeg(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When RTSP and MJPEG are unavailable, hub falls back to Tier 3 paced `camera.async_get_image`."""
    cam_mod = sys.modules["homeassistant.components.camera"]
    monkeypatch.setattr(cam_mod, "async_get_mjpeg_stream", None, raising=False)
    hass.data.setdefault("_camera_images", {})["camera.cloud_cam"] = _make_real_or_stub_jpeg(
        640, 360
    )

    hub = LatterCameraStreamHub(hass, idle_timeout_s=0.1)
    try:
        gen = hub.async_iter_stream_frames("camera.cloud_cam", 320, 240, fps=10, fit="contain")
        frame = await anext(gen)
        assert frame.startswith(b"\xff\xd8")
        w, h = _jpeg_size(frame)
        assert w % 16 == 0 and h % 16 == 0 and w <= 320 and h <= 240
        assert hub.get_ingest("camera.cloud_cam").source_tier == "snapshot"
        await gen.aclose()
    finally:
        await hub.async_shutdown()


# ---------------------------------------------------------------------------
# 2x2 Grid Compositor, Warm Snapshot, Guardrails & Capabilities Tests
# ---------------------------------------------------------------------------


async def test_grid_compositor_with_one_offline_camera(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2x2 Grid composites 3 live cameras + 1 offline camera into one 16px-aligned Baseline JPEG."""
    cam_mod = sys.modules["homeassistant.components.camera"]
    monkeypatch.setattr(cam_mod, "async_get_mjpeg_stream", None, raising=False)

    images = hass.data.setdefault("_camera_images", {})
    images["camera.front"] = _make_real_or_stub_jpeg(640, 360)
    images["camera.back"] = _make_real_or_stub_jpeg(640, 480)
    images["camera.driveway"] = _make_real_or_stub_jpeg(360, 640)
    images["camera.broken"] = RuntimeError("Camera offline")

    hass.states.async_set("camera.front", "idle", {"friendly_name": "Front Door"})
    hass.states.async_set("camera.back", "idle", {"friendly_name": "Backyard"})
    hass.states.async_set("camera.driveway", "idle", {"friendly_name": "Driveway"})
    hass.states.async_set("camera.broken", "unavailable", {"friendly_name": "Side Gate"})

    hub = LatterCameraStreamHub(hass, idle_timeout_s=0.1)
    try:
        grid_gen = hub.async_iter_grid_mjpeg_chunks(
            ["camera.front", "camera.back", "camera.driveway", "camera.broken"],
            width=800,
            height=480,
            fps=5,
            fit="contain",
        )
        chunk = await anext(grid_gen)
        assert chunk.startswith(b"--latterframe\r\n")
        assert b"Content-Length: " in chunk
        jpeg_bytes = chunk.split(b"\r\n\r\n", 1)[1][:-2]
        assert _jpeg_size(jpeg_bytes) == (800, 480)
        await grid_gen.aclose()
    finally:
        await hub.async_shutdown()

    # Pure compose_grid_frame check with corrupt frame bytes falls back to clean offline tile
    direct = compose_grid_frame(
        [images["camera.front"], b"NOT_AN_IMAGE", None, images["camera.back"]],
        ["Front", "Corrupt", "Offline", "Back"],
        466,
        466,
        fit="contain",
    )
    assert _jpeg_size(direct) == (464, 464)


async def test_instant_snapshot_warm_hit_and_cold_miss(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`async_get_snapshot` returns warm ingest frame immediately without fetching; cold miss fetches & transcodes."""
    cam_mod = sys.modules["homeassistant.components.camera"]
    monkeypatch.setattr(cam_mod, "async_get_mjpeg_stream", None, raising=False)
    fetch_count = 0
    orig_get_image = cam_mod.async_get_image

    async def _counting_get_image(h: Any, eid: str, **kw: Any) -> Any:
        nonlocal fetch_count
        fetch_count += 1
        return await orig_get_image(h, eid, **kw)

    monkeypatch.setattr(cam_mod, "async_get_image", _counting_get_image)
    hass.data.setdefault("_camera_images", {})["camera.patio"] = _make_real_or_stub_jpeg(
        640, 360
    )

    hub = LatterCameraStreamHub(hass, idle_timeout_s=0.2)
    try:
        # Cold miss fetches via camera.async_get_image with uncropped contain default
        cold_bytes, was_warm = await hub.async_get_snapshot("camera.patio", 466, 466)
        assert was_warm is False
        assert fetch_count == 1
        assert _jpeg_size(cold_bytes) == (464, 256)

        # Start a stream so the ingest is warm
        gen = hub.async_iter_stream_frames("camera.patio", 466, 466, fps=10)
        stream_frame = await anext(gen)
        count_after_start = fetch_count

        # Warm hit serves directly from memory without an extra camera.async_get_image call
        warm_bytes, was_warm2 = await hub.async_get_snapshot("camera.patio", 466, 466)
        assert was_warm2 is True
        assert warm_bytes == stream_frame
        assert fetch_count == count_after_start

        await gen.aclose()
    finally:
        await hub.async_shutdown()

    # Cold fetch error raises CameraFetchError
    hass.data["_camera_images"]["camera.err"] = RuntimeError("timeout")
    with pytest.raises(CameraFetchError):
        await hub.async_get_snapshot("camera.err", 320, 240)


async def test_video_semaphore_cap_and_shutdown_cleanup(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dedicated video semaphore enforces max concurrent distinct ingests and releases cleanly on shutdown."""
    assert MAX_CONCURRENT_VIDEO_INGESTS == 6
    cam_mod = sys.modules["homeassistant.components.camera"]
    monkeypatch.setattr(cam_mod, "async_get_mjpeg_stream", None, raising=False)

    hub = LatterCameraStreamHub(hass, max_concurrent_ingests=2, idle_timeout_s=0.1)
    gens: list[Any] = []
    try:
        for cid in ("camera.c1", "camera.c2"):
            hass.data.setdefault("_camera_images", {})[cid] = _make_real_or_stub_jpeg(320, 240)
            g = hub.async_iter_stream_frames(cid, 320, 240, fps=5)
            await anext(g)
            gens.append(g)

        assert hub.active_ingest_count == 2

        # A second subscriber on an existing camera succeeds without consuming another slot
        g_shared = hub.async_iter_stream_frames("camera.c1", 160, 128, fps=5)
        await anext(g_shared)
        gens.append(g_shared)
        assert hub.active_ingest_count == 2

        # A 3rd distinct camera exceeds max_concurrent_ingests=2
        hass.data["_camera_images"]["camera.c3"] = _make_real_or_stub_jpeg(320, 240)
        g_over = hub.async_iter_stream_frames("camera.c3", 320, 240, fps=5)
        with pytest.raises(CameraIngestLimitError):
            await anext(g_over)

        # Shutdown tears down all ingests and releases semaphore slots
        await hub.async_shutdown()
        assert hub.active_ingest_count == 0
        for g in gens:
            await g.aclose()

        # Semaphore is free again after shutdown
        g_after = hub.async_iter_stream_frames("camera.c3", 320, 240, fps=5)
        assert (await anext(g_after)).startswith(b"\xff\xd8")
        await g_after.aclose()
    finally:
        await hub.async_shutdown()


async def test_resolve_camera_capabilities_and_singleton_lifecycle(hass: Any) -> None:
    """`resolve_camera_capabilities` computes accurate bitmask + Studio metadata, and singleton shuts down cleanly."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    doorbell_dev = dev_reg.async_get_or_create(
        config_entry_id="unifi_entry",
        identifiers={("unifiprotect", "doorbell_1")},
        name="Front Doorbell",
        area_id="entryway",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="camera.front_door",
            platform="unifiprotect",
            device_id=doorbell_dev.id,
            config_entry_id="unifi_entry",
        )
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.front_door_speaker",
            platform="unifiprotect",
            device_id=doorbell_dev.id,
            config_entry_id="unifi_entry",
        )
    )
    hass.states.async_set(
        "camera.front_door",
        "streaming",
        {"friendly_name": "Front Door", "supported_features": 2},
    )
    hass.states.async_set(
        "camera.mjpeg_cam",
        "idle",
        {"friendly_name": "Garage MJPEG", "mjpeg_url": "http://10.0.0.2/mjpeg"},
    )
    hass.states.async_set(
        "camera.snap_cam",
        "idle",
        {"friendly_name": "Cloud Snap", "supported_features": 0},
    )
    hass.data.setdefault("_camera_streams", {})["camera.front_door"] = "rtsp://10.0.0.5/door"

    caps_doorbell = await async_resolve_camera_capabilities(
        hass,
        "camera.front_door",
        doorbell_ring_map={"binary_sensor.front_door_ring": "camera.front_door"},
        carousel_entities=["camera.front_door"],
    )
    assert caps_doorbell["caps"] == (
        CAMERA_CAP_HAS_AUDIO
        | CAMERA_CAP_HAS_TALKBACK
        | CAMERA_CAP_IS_DOORBELL
        | CAMERA_CAP_IN_CAROUSEL
    )
    assert caps_doorbell["stream_kind"] == "rtsp"
    assert caps_doorbell["has_audio"] is True
    assert caps_doorbell["has_talkback"] is True
    assert caps_doorbell["is_doorbell"] is True
    assert caps_doorbell["in_carousel"] is True
    assert caps_doorbell["door_speaker"] == "media_player.front_door_speaker"
    assert caps_doorbell["area_id"] == "entryway"

    caps_mjpeg = resolve_camera_capabilities(hass, "camera.mjpeg_cam")
    assert caps_mjpeg["stream_kind"] == "mjpeg"
    assert caps_mjpeg["caps"] == 0

    caps_snap = resolve_camera_capabilities(hass, "camera.snap_cam")
    assert caps_snap["stream_kind"] == "snapshot"
    assert caps_snap["caps"] == 0

    hub = get_camera_stream_hub(hass)
    assert hub is get_camera_stream_hub(hass)
    await async_shutdown_camera_stream_hub(hass)
    assert get_camera_stream_hub(hass) is not hub
    await async_shutdown_camera_stream_hub(hass)


async def test_stage2_manifest_video_caps_studio_and_http_streaming(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end Stage 2 test: P4 video manifest, Studio payload/commands, area_context v3, and HTTP stream/grid."""
    from urllib.parse import parse_qs, urlsplit

    from custom_components.latter import async_unload_entry
    from custom_components.latter.const import (
        CONF_CAMERA_CAROUSEL_ENTITIES,
        CONF_CAMERA_ENTITIES,
        CONF_CAMERA_VISIBLE_ENTITIES,
        DATA_GLOBAL_CONFIG,
        DOMAIN,
        STUDIO_REV,
    )
    from custom_components.latter.http import (
        LatterCameraGridView,
        LatterCameraSnapshotView,
        LatterCameraStreamView,
    )
    from custom_components.latter.studio.commands import (
        StudioCommandError,
        _cmd_save_device_config,
    )
    from custom_components.latter.studio.payload import build_studio_state_payload

    entry, _sys_obj, coord = await setup_latter_hub(hass)
    try:
        # S3 default manifest has hw_jpeg=False, 5/2 fps
        assert coord.supports_hw_jpeg is False
        assert coord.video_max_fps == 5
        assert coord.video_grid_fps == 2

        # P4 AC manifest unlocks hw_jpeg=True, 800x480, 15/8 fps
        coord._runtime.hello_manifest = {
            "v": 2,
            "contract": 3,
            "w": 800,
            "h": 480,
            "shape": "square",
            "display": 1,
            "battery": 0,
            "stationary": 1,
            "video": {
                "hw_jpeg": 1,
                "max_w": 800,
                "max_h": 480,
                "max_fps": 15,
                "grid_fps": 8,
            },
        }
        assert coord.supports_hw_jpeg is True
        assert coord.video_max_dims == (800, 480)
        assert coord.video_max_fps == 15
        assert coord.video_grid_fps == 8

        # Configure two System cameras
        global_cfg = hass.data[DOMAIN][DATA_GLOBAL_CONFIG]
        global_cfg[CONF_CAMERA_ENTITIES] = ["camera.front_door", "camera.backyard"]
        hass.states.async_set(
            "camera.front_door",
            "streaming",
            {"friendly_name": "Front Door", "supported_features": 2},
        )
        hass.states.async_set(
            "camera.backyard",
            "idle",
            {"friendly_name": "Backyard", "supported_features": 0},
        )
        hass.data.setdefault("_camera_images", {})["camera.front_door"] = _make_real_or_stub_jpeg(
            640, 360
        )
        hass.data["_camera_images"]["camera.backyard"] = _make_real_or_stub_jpeg(640, 480)

        # Save valid per-Device camera_visible_entities & camera_carousel_entities via Studio command
        await _cmd_save_device_config(
            hass,
            coord,
            {
                "config": {
                    CONF_CAMERA_VISIBLE_ENTITIES: ["camera.front_door", "camera.backyard"],
                    CONF_CAMERA_CAROUSEL_ENTITIES: ["camera.front_door"],
                    "camera_default_view": "Single",
                    "camera_doorbell_popup": "Live Video",
                },
                "studio_rev": STUDIO_REV,
            },
            global_cfg,
            {},
        )
        assert coord.visible_camera_entities == ["camera.front_door", "camera.backyard"]
        assert coord.carousel_camera_entities == ["camera.front_door"]

        # Reject camera not in System shared entities
        with pytest.raises(StudioCommandError):
            await _cmd_save_device_config(
                hass,
                coord,
                {
                    "config": {CONF_CAMERA_VISIBLE_ENTITIES: ["camera.unknown_cam"]},
                    "studio_rev": STUDIO_REV,
                },
                global_cfg,
                {},
            )

        # Verify Studio payload capabilities, config, and enriched catalog.cameras
        payload = build_studio_state_payload(hass, coord, include_catalog=True)
        assert payload["capabilities"]["hw_jpeg"] is True
        assert payload["capabilities"]["video_max_fps"] == 15
        assert payload["capabilities"]["video_grid_fps"] == 8
        assert payload["config"][CONF_CAMERA_VISIBLE_ENTITIES] == [
            "camera.front_door",
            "camera.backyard",
        ]
        assert payload["config"][CONF_CAMERA_CAROUSEL_ENTITIES] == ["camera.front_door"]
        cat_cams = {c["id"]: c for c in payload["catalog"]["cameras"]}
        assert cat_cams["camera.front_door"]["stream_kind"] == "rtsp"
        assert cat_cams["camera.front_door"]["has_audio"] is True
        assert cat_cams["camera.backyard"]["stream_kind"] == "snapshot"

        # Dispatch doorbell alert and verify area_context wire indices 21, 39, 40
        coord.async_dispatch_notification(
            title="Doorbell Ringing",
            message="Visitor at Front Door",
            priority="critical",
            duration=20,
            chime=True,
            camera_entity="camera.front_door",
        )
        coord._cached_area_payload = None
        _st, area_attrs = coord.get_area_context_payload()
        wire = area_attrs["payload"].split("\x1f")
        assert len(wire) == 41
        assert "camera.front_door|Front Door||9" in wire[21]  # 1 (audio) | 8 (in_carousel)
        assert "camera.backyard|Backyard||0" in wire[21]
        assert "/api/latter/camera_stream/" in wire[39]
        assert wire[40] == "camera.front_door"

        # Stream 1 chunk from LatterCameraStreamView & LatterCameraGridView
        stream_sig = parse_qs(urlsplit(wire[39]).query)["sig"][0]
        cam_mod = sys.modules["homeassistant.components.camera"]
        monkeypatch.setattr(cam_mod, "async_get_mjpeg_stream", None, raising=False)

        async def _one_chunk_single(*_a: Any, **_kw: Any) -> Any:
            yield format_mjpeg_chunk(_make_baseline_420_jpeg(464, 256))

        async def _one_chunk_grid(*_a: Any, **_kw: Any) -> Any:
            yield format_mjpeg_chunk(_make_baseline_420_jpeg(800, 480))

        hub = get_camera_stream_hub(hass)
        monkeypatch.setattr(hub, "async_iter_mjpeg_chunks", _one_chunk_single)
        monkeypatch.setattr(hub, "async_iter_grid_mjpeg_chunks", _one_chunk_grid)

        from custom_components.latter import http as http_mod

        class _CapturingStreamResponse:
            def __init__(self, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
                self.status = status
                self.headers = dict(headers or {})
                self._chunks: list[bytes] = []

            @property
            def body(self) -> bytes:
                return b"".join(self._chunks)

            async def prepare(self, _request: Any) -> _CapturingStreamResponse:
                return self

            async def write(self, data: bytes) -> None:
                self._chunks.append(bytes(data))

            async def write_eof(self) -> None:
                return None

        monkeypatch.setattr(http_mod.web, "StreamResponse", _CapturingStreamResponse)

        s_view = LatterCameraStreamView(hass)
        s_resp = await s_view.get(
            SimpleNamespace(
                query={
                    "entity_id": "camera.front_door",
                    "w": "800",
                    "h": "480",
                    "fps": "15",
                    "fit": "contain",
                    "sig": stream_sig,
                },
                headers={},
            ),
            coord.device_slug,
        )
        assert s_resp.status == 200
        assert b"--latterframe\r\n" in s_resp.body
        assert b"Content-Length: " in s_resp.body

        g_view = LatterCameraGridView(hass)
        g_resp = await g_view.get(
            SimpleNamespace(
                query={
                    "cameras": "camera.front_door,camera.backyard",
                    "w": "800",
                    "h": "480",
                    "fps": "8",
                    "sig": stream_sig,
                },
                headers={},
            ),
            coord.device_slug,
        )
        assert g_resp.status == 200
        assert b"--latterframe\r\n" in g_resp.body
        assert b"Content-Length: " in g_resp.body

        # Allowlist-signed camera_snapshot_url works for camera #2, blocks hidden camera (403), and single-entity alert snapshot still works
        snap_view = LatterCameraSnapshotView(hass)
        snap_base = area_attrs["camera_snapshot_url"]
        snap_qs = {k: v[0] for k, v in parse_qs(urlsplit(snap_base).query).items()}
        r_cam2 = await snap_view.get(
            SimpleNamespace(query={**snap_qs, "entity_id": "camera.backyard"}, headers={}),
            coord.device_slug,
        )
        assert r_cam2.status == 200
        assert r_cam2.body.startswith(b"\xff\xd8")

        # Hide camera.backyard from device's visible_camera_entities -> old or new allowlist sig rejects camera.backyard with 403
        await _cmd_save_device_config(
            hass,
            coord,
            {
                "config": {CONF_CAMERA_VISIBLE_ENTITIES: ["camera.front_door"]},
                "studio_rev": STUDIO_REV,
            },
            global_cfg,
            {},
        )
        coord._cached_area_payload = None
        new_snap_qs = {
            k: v[0]
            for k, v in parse_qs(
                urlsplit(coord.get_area_context_payload()[1]["camera_snapshot_url"]).query
            ).items()
        }
        r_hidden = await snap_view.get(
            SimpleNamespace(query={**new_snap_qs, "entity_id": "camera.backyard"}, headers={}),
            coord.device_slug,
        )
        assert r_hidden.status == 403

        # Single-entity alert_camera_url for a System camera hidden from visible list still succeeds while active alert
        coord.async_dispatch_notification(
            title="Doorbell Ringing",
            message="Visitor at Backyard",
            priority="critical",
            duration=20,
            chime=True,
            camera_entity="camera.backyard",
        )
        alert_qs = {
            k: v[0]
            for k, v in parse_qs(urlsplit(coord.alert_camera_url).query).items()
        }
        r_alert = await snap_view.get(
            SimpleNamespace(query=alert_qs, headers={}),
            coord.device_slug,
        )
        assert r_alert.status == 200
        assert r_alert.body.startswith(b"\xff\xd8")

        # Verify system_devices includes hw_jpeg and S3 rejects Live Video doorbell popup
        sys_devs = {d["subentry_id"]: d for d in payload["system_devices"]}
        assert sys_devs[coord.subentry_id]["hw_jpeg"] is True

        coord._runtime.hello_manifest = {
            "v": 2,
            "contract": 3,
            "w": 466,
            "h": 466,
            "shape": "circle",
            "display": 1,
            "battery": 1,
            "stationary": 0,
            "video": {"hw_jpeg": 0, "max_w": 464, "max_h": 464, "max_fps": 5, "grid_fps": 2},
        }
        s3_payload = build_studio_state_payload(hass, coord, include_catalog=False)
        assert s3_payload["config"]["camera_doorbell_popup"] == "Snapshot"
        assert {d["subentry_id"]: d for d in s3_payload["system_devices"]}[coord.subentry_id][
            "hw_jpeg"
        ] is False
        from custom_components.latter.studio.settings import SettingsScopeError

        with pytest.raises(SettingsScopeError):
            await _cmd_save_device_config(
                hass,
                coord,
                {
                    "config": {"camera_doorbell_popup": "Live Video"},
                    "studio_rev": STUDIO_REV,
                },
                global_cfg,
                {},
            )
    finally:
        await async_unload_entry(hass, entry)


async def test_offline_stream_fast_fail_grid_429_and_rtsp_fallback(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Offline camera fails fast with CameraFetchError, saturated grid raises CameraIngestLimitError, and dead RTSP falls back."""
    cam_mod = sys.modules["homeassistant.components.camera"]
    monkeypatch.setattr(cam_mod, "async_get_mjpeg_stream", None, raising=False)
    hass.data.setdefault("_camera_images", {})["camera.dead"] = RuntimeError("camera down")

    hub = LatterCameraStreamHub(hass, max_concurrent_ingests=1, idle_timeout_s=0.1)
    try:
        # 1) Offline camera raises CameraFetchError promptly (does not hang until timeout)
        gen_dead = hub.async_iter_stream_frames("camera.dead", 320, 240, fps=5, wait_timeout_s=5.0)
        with pytest.raises(CameraFetchError):
            await asyncio.wait_for(anext(gen_dead), timeout=1.0)
        await gen_dead.aclose()
        await hub.async_shutdown()

        # 2) Saturated video semaphore raises CameraIngestLimitError when 0 grid slots can attach
        hass.data["_camera_images"]["camera.live1"] = _make_real_or_stub_jpeg(320, 240)
        hass.data["_camera_images"]["camera.live2"] = _make_real_or_stub_jpeg(320, 240)
        g_hold = hub.async_iter_stream_frames("camera.live1", 320, 240, fps=5)
        await anext(g_hold)
        g_grid = hub.async_iter_grid_frames(["camera.live2"], 320, 240, fps=5)
        with pytest.raises(CameraIngestLimitError):
            await anext(g_grid)
        await g_grid.aclose()
        await g_hold.aclose()
        await hub.async_shutdown()

        # 3) RTSP camera that stops producing frames falls back to Tier 3 Snapshot after retries
        hass.data.setdefault("_camera_streams", {})["camera.flaky"] = "rtsp://10.0.0.99/flaky"
        hass.data["_camera_images"]["camera.flaky"] = _make_real_or_stub_jpeg(320, 240)
        rtsp_calls = 0

        async def _flaky_exec(*_cmd: str, **_kw: Any) -> _FakeSubprocess:
            nonlocal rtsp_calls
            rtsp_calls += 1
            if rtsp_calls == 1:
                return _FakeSubprocess(
                    [format_mjpeg_chunk(_make_baseline_420_jpeg(320, 240))],
                    stall_after=False,
                )
            return _FakeSubprocess([], stall_after=False)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", _flaky_exec)
        orig_sleep = asyncio.sleep

        async def _fast_sleep(delay: float) -> None:
            await orig_sleep(min(delay, 0.005))

        monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

        g_flaky = hub.async_iter_stream_frames("camera.flaky", 320, 240, fps=10)
        await anext(g_flaky)
        # Wait briefly for dead RTSP retries to exhaust and fall back to Tier 3 snapshot
        for _ in range(20):
            ing = hub.get_ingest("camera.flaky")
            if ing is not None and ing.source_tier == "snapshot":
                break
            await orig_sleep(0.01)
        assert hub.get_ingest("camera.flaky").source_tier == "snapshot"
        await g_flaky.aclose()
    finally:
        await hub.async_shutdown()
