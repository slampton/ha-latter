"""Tests for LatterCameraStreamHub RTSP/MJPEG/snapshot tiers, grid compositor, primer, and semaphore."""

from __future__ import annotations

import asyncio
import io
import sys
from types import SimpleNamespace
from typing import Any

from PIL import Image
import pytest

from custom_components.latter.cameras import stream_hub as cameras_mod
from custom_components.latter.cameras.stream_hub import LatterCameraStreamHub
from custom_components.latter.cameras.transcode import (
    MAX_CONCURRENT_VIDEO_INGESTS,
    CameraFetchError,
    CameraIngestLimitError,
    compose_grid_frame,
    format_mjpeg_chunk,
    inspect_jpeg_header,
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
    # Disable parallel snapshot primer on this test so frame #1 strictly exercises zero-copy RTSP pass-through
    cam_mod = sys.modules["homeassistant.components.camera"]
    monkeypatch.setattr(cam_mod, "async_get_image", None, raising=False)

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


async def test_cold_rtsp_snapshot_primer_and_lru_idle_eviction(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cold RTSP emits an instant parallel snapshot primer, and idle warm ingests evict LRU when full."""
    hass.data.setdefault("_camera_streams", {})["camera.slow_rtsp"] = "rtsp://10.0.0.99/slow"
    hass.data["_camera_streams"]["camera.cam_two"] = "rtsp://10.0.0.99/two"
    live_jpeg = _make_baseline_420_jpeg(464, 256)
    snap_jpeg = _make_baseline_420_jpeg(464, 256)

    release_rtsp = asyncio.Event()

    class _DelayedStdout:
        def __init__(self) -> None:
            self._sent = False

        async def read(self, _n: int = 32768) -> bytes:
            if not self._sent:
                await release_rtsp.wait()
                self._sent = True
                return format_mjpeg_chunk(live_jpeg)
            await asyncio.sleep(3600)
            return b""

        def close(self) -> None:
            pass

    class _DelayedProc:
        def __init__(self) -> None:
            self.stdout = _DelayedStdout()
            self.returncode: int | None = None

        def terminate(self) -> None:
            self.returncode = 0

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            return 0

    async def _fake_exec(*_cmd: str, **_kwargs: Any) -> _DelayedProc:
        return _DelayedProc()

    cam_mod = sys.modules["homeassistant.components.camera"]

    async def _fast_snap(*_a: Any, **_kw: Any) -> Any:
        return SimpleNamespace(content=snap_jpeg)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    monkeypatch.setattr(cam_mod, "async_get_image", _fast_snap, raising=False)

    # Cap at 1 ingest with a long 10s idle timer to test LRU idle eviction
    hub = LatterCameraStreamHub(hass, max_concurrent_ingests=1, idle_timeout_s=10.0)
    try:
        gen1 = hub.async_iter_stream_frames("camera.slow_rtsp", 464, 256, fps=10, fit="contain")
        # Primer delivers frame #0 immediately even while RTSP is still blocked waiting for IDR keyframe!
        primer_frame = await asyncio.wait_for(anext(gen1), timeout=1.0)
        assert primer_frame.startswith(b"\xff\xd8")
        # Now release RTSP live frame and confirm seamless live handover
        release_rtsp.set()
        live_frame = await asyncio.wait_for(anext(gen1), timeout=1.0)
        assert live_frame == live_jpeg
        await gen1.aclose()
        await asyncio.sleep(0.02)
        # Ingest #1 is warm and idle in its 10s window
        assert hub.active_ingest_count == 1

        # Subscribing to camera #2 immediately evicts idle camera #1 instead of raising CameraIngestLimitError
        gen2 = hub.async_iter_stream_frames("camera.cam_two", 464, 256, fps=10, fit="contain")
        frame2 = await asyncio.wait_for(anext(gen2), timeout=1.0)
        assert frame2.startswith(b"\xff\xd8")
        assert hub.get_ingest("camera.slow_rtsp") is None
        assert hub.get_ingest("camera.cam_two") is not None
        await gen2.aclose()
    finally:
        await hub.async_shutdown()


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
