"""Shared 1-ingest-per-camera live MJPEG fan-out hub, 2x2 grid stream, and warm snapshots (`L2a`)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
import contextlib
from functools import partial
import logging
import shutil
import time
from typing import Any, Final

from homeassistant.components import camera as ha_camera
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from .transcode import (
    DATA_CAMERA_HUB,
    FFMPEG_READ_CHUNK_BYTES,
    FFMPEG_READ_TIMEOUT_SECONDS,
    GRID_GUTTER_PX,
    GRID_STALE_FRAME_SECONDS,
    MAX_CONCURRENT_VIDEO_INGESTS,
    MAX_RTSP_EMPTY_RETRIES,
    MIN_ALIGNED_DIM,
    MIN_VIDEO_FPS,
    MJPEG_QUEUE_MAXSIZE,
    SNAPSHOT_CACHE_MAX_AGE_SECONDS,
    SNAPSHOT_PRIMER_TIMEOUT_SECONDS,
    STREAM_WAIT_TIMEOUT_SECONDS,
    VIDEO_INGEST_IDLE_SECONDS,
    CameraFetchError,
    CameraIngest as _CameraIngest,
    CameraIngestLimitError,
    CameraSubscriber as _CameraSubscriber,
    CameraTranscodeError,
    LoopbackMjpegRequest,
    LoopbackMjpegTransport,
    MjpegStreamParser,
    align16,
    build_ffmpeg_video_cmd,
    compose_grid_frame,
    format_mjpeg_chunk,
    inspect_jpeg_header,
    normalize_fit_mode,
    normalize_fps,
    normalize_rotation,
    transcode_camera_frame,
)

_LOGGER = logging.getLogger(__name__)
_MACROBLOCK_ALIGN: Final[int] = 16
_FULL_CIRCLE_DEG: Final[int] = 360
_MAX_GRID_SLOTS: Final[int] = 4
_SEMAPHORE_ACQUIRE_TIMEOUT_S: Final[float] = 0.25
_PROC_TERM_TIMEOUT_S: Final[float] = 1.5
_PROC_KILL_WAIT_S: Final[float] = 1.0
_SNAPSHOT_TIMEOUT_S: Final[int] = 8
_MIN_SLEEP_THRESHOLD_S: Final[float] = 0.005
_TIER_RETRY_BACKOFF_S: Final[float] = 0.5
_GRID_FIRST_FRAME_CAP_S: Final[float] = 1.5


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
        try:
            from homeassistant.components.ffmpeg import get_ffmpeg_manager

            if binary := get_ffmpeg_manager(self.hass).binary:
                return str(binary)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("FFmpeg manager lookup fell back to PATH: %s", err)
        if not self._ffmpeg_bin_checked:
            self._cached_ffmpeg_bin = await self.hass.async_add_executor_job(shutil.which, "ffmpeg")
            self._ffmpeg_bin_checked = True
        return self._cached_ffmpeg_bin

    async def _async_get_stream_source(self, entity_id: str) -> str | None:
        try:
            url = await ha_camera.async_get_stream_source(self.hass, entity_id)
            result = str(url).strip() if url else None
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("camera.async_get_stream_source(%s) failed: %s", entity_id, err)
            result = None
        self._stream_source_cache[entity_id] = (time.monotonic(), result)
        return result

    async def async_get_cached_stream_source(self, entity_id: str, *, ttl_s: float = 60.0) -> str | None:
        """Return a cached stream source URL if fresh, else probe `camera.async_get_stream_source`."""
        cached = self._stream_source_cache.get(entity_id)
        if cached is not None and (time.monotonic() - cached[0]) <= ttl_s:
            return cached[1]
        return await self._async_get_stream_source(entity_id)

    async def _async_terminate_proc(self, proc: asyncio.subprocess.Process | None) -> None:
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=_PROC_TERM_TIMEOUT_S)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(TimeoutError, ProcessLookupError, OSError):
                await asyncio.wait_for(proc.wait(), timeout=_PROC_KILL_WAIT_S)
        except ProcessLookupError:
            return

    async def _async_evict_oldest_idle_ingest_if_locked(self) -> None:
        if not self._video_semaphore.locked():
            return
        idle_candidates = [
            ing for ing in self._ingests.values() if not ing.closed and not ing.subscribers
        ]
        if idle_candidates:
            await self._async_stop_ingest(min(idle_candidates, key=lambda ing: ing.idle_since))

    async def _subscribe(  # noqa: PLR0913
        self, entity_id: str, width: int, height: int, fps: int,
        *, fit: str = "contain", rot: int = 0, circular_mask: bool = False,
    ) -> tuple[_CameraIngest, _CameraSubscriber]:
        """Attach a subscriber to the shared `_CameraIngest` for `entity_id`, serialized per camera (`M-P1-30`)."""
        cam_lock = self._subscribe_locks.setdefault(entity_id, asyncio.Lock())
        async with cam_lock:
            norm_fit = normalize_fit_mode(fit)
            sub = _CameraSubscriber(
                align16(width), align16(height), normalize_fps(fps),
                norm_fit, normalize_rotation(rot), bool(circular_mask and norm_fit == "fill"),
            )
            ingest = self._ingests.get(entity_id)
            if ingest is None or ingest.closed:
                await self._async_evict_oldest_idle_ingest_if_locked()
                try:
                    await asyncio.wait_for(self._video_semaphore.acquire(), timeout=_SEMAPHORE_ACQUIRE_TIMEOUT_S)
                except TimeoutError as err:
                    raise CameraIngestLimitError(
                        f"Maximum concurrent video ingests ({self._max_concurrent_ingests}) reached"
                    ) from err
                ingest = _CameraIngest(
                    entity_id=entity_id, stream_w=sub.width, stream_h=sub.height,
                    stream_fps=sub.fps, stream_fit=sub.fit, stream_rot=sub.rot, sem_acquired=True,
                )
                ingest.subscribers.add(sub)
                self._ingests[entity_id] = ingest
                ingest._task = self.hass.async_create_background_task(
                    self._async_run_ingest(ingest), name=f"latter_camera_ingest_{entity_id}"
                )
                return ingest, sub

            if ingest.idle_task is not None and not ingest.idle_task.done():
                ingest.idle_task.cancel()
                ingest.idle_task = None
            ingest.idle_since = 0.0
            prev_w, prev_h, prev_fps, prev_fit, prev_rot = ingest.desired_profile()
            ingest.subscribers.add(sub)
            new_w, new_h, new_fps, new_fit, new_rot = ingest.desired_profile()
            if (
                new_w > prev_w or new_h > prev_h or new_fps > prev_fps
                or (new_fit == "contain" and prev_fit == "fill") or prev_rot not in (new_rot, 0)
            ):
                ingest.restart_event.set()
            return ingest, sub

    def _unsubscribe(self, ingest: _CameraIngest, sub: _CameraSubscriber) -> None:
        ingest.subscribers.discard(sub)
        if (
            not ingest.subscribers
            and not ingest.closed
            and (ingest.idle_task is None or ingest.idle_task.done())
        ):
            ingest.idle_since = time.monotonic()
            ingest.idle_task = self.hass.async_create_background_task(
                self._async_idle_teardown(ingest), name=f"latter_camera_idle_{ingest.entity_id}"
            )

    async def _async_idle_teardown(self, ingest: _CameraIngest) -> None:
        try:
            await asyncio.sleep(self._idle_timeout_s)
        except asyncio.CancelledError:
            return
        if not ingest.subscribers and not ingest.closed:
            await self._async_stop_ingest(ingest)

    async def _async_stop_ingest(self, ingest: _CameraIngest) -> None:
        ingest.closed = True
        if self._ingests.get(ingest.entity_id) is ingest:
            self._ingests.pop(ingest.entity_id, None)

        for aux_task in (ingest.idle_task, ingest.prime_task):
            if aux_task is not None and not aux_task.done() and aux_task is not asyncio.current_task():
                aux_task.cancel()
        ingest.idle_task = None
        ingest.prime_task = None

        proc, ingest.proc = ingest.proc, None
        await self._async_terminate_proc(proc)

        task, ingest._task = ingest._task, None
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        if ingest.sem_acquired:
            ingest.sem_acquired = False
            self._video_semaphore.release()

        prev = ingest.next_frame_event
        ingest.next_frame_event = asyncio.Event()
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
        self, ingest: _CameraIngest, profile: tuple[int, int, str, int]
    ) -> None:
        width, height, fit, rot = profile
        try:
            get_img = getattr(ha_camera, "async_get_image", None)
            if not callable(get_img):
                return
            image_obj = await get_img(
                self.hass, ingest.entity_id, width=width, height=height, timeout=SNAPSHOT_PRIMER_TIMEOUT_SECONDS
            )
            if ingest.closed or ingest.latest_seq > 0 or not getattr(image_obj, "content", None):
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
            if not ingest.closed and ingest.latest_seq == 0:
                ingest.publish(encoded, profile, is_baseline_420=True, is_primer=True)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Snapshot primer skipped for %s: %s", ingest.entity_id, err)

    async def _async_try_rtsp_ingest_step(
        self, ingest: _CameraIngest, rtsp_empty_attempts: int
    ) -> tuple[bool, int]:
        """Attempt Tier 1 RTSP ingest; return `(continue_loop, updated_empty_attempts)`."""
        target_w, target_h, target_fps, target_fit, target_rot = ingest.desired_profile()
        ingest.stream_fps = target_fps
        stream_url = await self._async_get_stream_source(ingest.entity_id)
        ffmpeg_bin = await self._async_resolve_ffmpeg_binary() if stream_url else None
        if not stream_url or not ffmpeg_bin:
            return False, rtsp_empty_attempts

        frame_profile = (target_w, target_h, target_fit, target_rot)
        if ingest.latest_frame is None and (ingest.prime_task is None or ingest.prime_task.done()):
            ingest.prime_task = self.hass.async_create_background_task(
                self._async_prime_snapshot(ingest, frame_profile),
                name=f"latter_camera_prime_{ingest.entity_id}",
            )
        ingest.source_tier = "rtsp"
        live_seq_before = ingest.live_seq
        restarted = await self._async_run_rtsp_tier(
            ingest, ffmpeg_bin, stream_url, (target_w, target_h, target_fps, target_fit, target_rot)
        )
        if ingest.closed:
            return True, rtsp_empty_attempts
        if restarted:
            return True, 0
        if ingest.live_seq > live_seq_before:
            await asyncio.sleep(_TIER_RETRY_BACKOFF_S)
            return True, 0
        rtsp_empty_attempts += 1
        if ingest.live_seq > 0 and rtsp_empty_attempts <= MAX_RTSP_EMPTY_RETRIES:
            await asyncio.sleep(_TIER_RETRY_BACKOFF_S)
            return True, rtsp_empty_attempts
        return False, rtsp_empty_attempts

    async def _async_run_ingest(self, ingest: _CameraIngest) -> None:
        rtsp_empty_attempts = 0
        try:
            while not ingest.closed:
                ingest.restart_event.clear()
                keep_rtsp, rtsp_empty_attempts = await self._async_try_rtsp_ingest_step(
                    ingest, rtsp_empty_attempts
                )
                if ingest.closed:
                    return
                if keep_rtsp:
                    continue

                mjpeg_ok = await self._async_run_mjpeg_tier(ingest)
                if ingest.closed:
                    return
                if mjpeg_ok:
                    if not ingest.restart_event.is_set():
                        await asyncio.sleep(_TIER_RETRY_BACKOFF_S)
                    continue

                ingest.source_tier = "snapshot"
                await self._async_run_snapshot_tier(ingest)
                if ingest.closed:
                    return
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Camera ingest loop ended for %s: %s", ingest.entity_id, err)
            ingest.publish_error(err)
        finally:
            proc, ingest.proc = ingest.proc, None
            await self._async_terminate_proc(proc)
            if self._ingests.get(ingest.entity_id) is ingest:
                self._ingests.pop(ingest.entity_id, None)
            if ingest.sem_acquired:
                ingest.sem_acquired = False
                self._video_semaphore.release()

    async def _async_read_rtsp_stdout_loop(
        self,
        ingest: _CameraIngest,
        stdout: asyncio.StreamReader,
        parser: MjpegStreamParser,
        frame_profile: tuple[int, int, str, int],
    ) -> bool:
        while not ingest.closed:
            if ingest.restart_event.is_set():
                return True
            read_task = asyncio.create_task(stdout.read(FFMPEG_READ_CHUNK_BYTES))
            restart_task = asyncio.create_task(ingest.restart_event.wait())
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
            if restart_task in done and ingest.restart_event.is_set():
                return True
            chunk = read_task.result() if read_task in done else b""
            if not chunk:
                return False
            for frame in parser.feed(chunk):
                if ingest.prime_task is not None and not ingest.prime_task.done():
                    ingest.prime_task.cancel()
                    ingest.prime_task = None
                ingest.publish(frame, frame_profile, is_baseline_420=True)
        return False

    async def _async_run_rtsp_tier(
        self,
        ingest: _CameraIngest,
        ffmpeg_bin: str,
        stream_url: str,
        full_profile: tuple[int, int, int, str, int],
    ) -> bool:
        width, height, fps, fit, rot = full_profile
        cmd = build_ffmpeg_video_cmd(ffmpeg_bin, stream_url, width, height, fps, fit=fit, rot=rot)
        proc: asyncio.subprocess.Process | None = None
        parser = MjpegStreamParser()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            ingest.proc = proc
            if proc.stdout is None:
                return False
            return await self._async_read_rtsp_stdout_loop(
                ingest, proc.stdout, parser, (width, height, fit, rot)
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("RTSP FFmpeg ingest failed for %s: %s", ingest.entity_id, err)
            return False
        finally:
            if ingest.proc is proc:
                ingest.proc = None
            await self._async_terminate_proc(proc)

    async def _async_publish_upstream_jpeg(self, ingest: _CameraIngest, raw_frame: bytes) -> None:
        target_w, target_h, _fps, target_fit, target_rot = ingest.desired_profile()
        frame_profile = (target_w, target_h, target_fit, target_rot)
        is_b420, fw, fh = inspect_jpeg_header(raw_frame)
        if (
            is_b420
            and target_rot == 0
            and target_fit == "contain"
            and fw >= MIN_ALIGNED_DIM
            and fh >= MIN_ALIGNED_DIM
            and fw % _MACROBLOCK_ALIGN == 0
            and fh % _MACROBLOCK_ALIGN == 0
            and fw <= target_w
            and fh <= target_h
        ):
            ingest.publish(raw_frame, frame_profile, is_baseline_420=True)
            return
        try:
            encoded = await self.hass.async_add_executor_job(
                partial(
                    transcode_camera_frame,
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
        ingest.publish(encoded, frame_profile, is_baseline_420=True)

    async def _async_feed_mjpeg_chunk(
        self, ingest: _CameraIngest, parser: MjpegStreamParser, raw_chunk: bytes
    ) -> bool:
        got_frame = False
        for frame in parser.feed(raw_chunk):
            ingest.source_tier = "mjpeg"
            got_frame = True
            await self._async_publish_upstream_jpeg(ingest, frame)
        return got_frame

    async def _async_consume_mjpeg_return_value(
        self, ingest: _CameraIngest, parser: MjpegStreamParser, result: Any
    ) -> bool:
        if result is None:
            return False
        got_frame = False
        if hasattr(result, "__aiter__"):
            async for raw_chunk in result:
                if ingest.closed or ingest.restart_event.is_set():
                    break
                got_frame = await self._async_feed_mjpeg_chunk(ingest, parser, bytes(raw_chunk)) or got_frame
            return got_frame
        if hasattr(result, "content") and hasattr(result.content, "iter_chunked"):
            async for raw_chunk in result.content.iter_chunked(FFMPEG_READ_CHUNK_BYTES):
                if ingest.closed or ingest.restart_event.is_set():
                    break
                got_frame = await self._async_feed_mjpeg_chunk(ingest, parser, bytes(raw_chunk)) or got_frame
            return got_frame
        if isinstance(getattr(result, "body", None), (bytes, bytearray)):
            return await self._async_feed_mjpeg_chunk(ingest, parser, bytes(result.body))
        return False

    async def _async_step_mjpeg_queue(
        self,
        ingest: _CameraIngest,
        queue: asyncio.Queue[bytes | None],
        producer: asyncio.Task[Any],
        parser: MjpegStreamParser,
    ) -> tuple[bool, bool]:
        """Execute one `FIRST_COMPLETED` queue/producer step; return `(keep_looping, got_frame)`."""
        get_task: asyncio.Task[bytes | None] = asyncio.create_task(queue.get())
        got_frame = False
        queue_eof = False
        try:
            done, _pending = await asyncio.wait(
                {get_task, producer},
                timeout=FFMPEG_READ_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                return False, False
            if get_task in done:
                chunk = (
                    None
                    if get_task.cancelled() or get_task.exception() is not None
                    else get_task.result()
                )
                if chunk is None:
                    queue_eof = True
                else:
                    got_frame = await self._async_feed_mjpeg_chunk(ingest, parser, chunk)
        finally:
            if not get_task.done():
                get_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await get_task

        if producer in done or (queue_eof and producer.done()):
            if producer.cancelled():
                return False, got_frame
            if (prod_exc := producer.exception()) is not None:
                raise prod_exc
            extra = await self._async_consume_mjpeg_return_value(ingest, parser, producer.result())
            return False, (got_frame or extra)
        return (not queue_eof), got_frame

    async def _async_run_mjpeg_tier(self, ingest: _CameraIngest) -> bool:
        """Attempt Tier 2 native MJPEG ingest with clean `FIRST_COMPLETED` pending cleanup (`M-P2-23`)."""
        mjpeg_fn = getattr(ha_camera, "async_get_mjpeg_stream", None)
        if not callable(mjpeg_fn):
            return False

        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=MJPEG_QUEUE_MAXSIZE)
        transport = LoopbackMjpegTransport(queue)
        request = LoopbackMjpegRequest(transport)
        parser = MjpegStreamParser()
        got_any_frame = False

        async def _invoke_mjpeg() -> Any:
            try:
                return await mjpeg_fn(self.hass, request, ingest.entity_id)
            finally:
                transport.close()

        producer = asyncio.create_task(_invoke_mjpeg())
        try:
            while not ingest.closed and not ingest.restart_event.is_set():
                keep_going, step_got = await self._async_step_mjpeg_queue(
                    ingest, queue, producer, parser
                )
                got_any_frame = got_any_frame or step_got
                if not keep_going:
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

    async def _async_poll_single_snapshot(
        self, ingest: _CameraIngest, profile: tuple[int, int, str, int]
    ) -> bool:
        target_w, target_h, target_fit, target_rot = profile
        try:
            image_obj = await ha_camera.async_get_image(
                self.hass, ingest.entity_id, width=target_w, height=target_h, timeout=_SNAPSHOT_TIMEOUT_S
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
            ingest.publish(encoded, profile, is_baseline_420=True)
            return True
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Snapshot ingest failed for %s: %s", ingest.entity_id, err)
            ingest.publish_error(CameraFetchError(str(err)))
            return False

    async def _async_run_snapshot_tier(self, ingest: _CameraIngest) -> None:
        while not ingest.closed:
            t0 = time.monotonic()
            target_w, target_h, target_fps, target_fit, target_rot = ingest.desired_profile()
            if not await self._async_poll_single_snapshot(
                ingest, (target_w, target_h, target_fit, target_rot)
            ):
                await asyncio.sleep(1.0)
                continue
            sleep_for = (1.0 / float(max(MIN_VIDEO_FPS, target_fps))) - (time.monotonic() - t0)
            if sleep_for > _MIN_SLEEP_THRESHOLD_S:
                await asyncio.sleep(sleep_for)

    async def _async_format_for_subscriber(
        self, ingest: _CameraIngest, sub: _CameraSubscriber, frame: bytes
    ) -> bytes:
        if (
            ingest.stream_is_baseline_420
            and not sub.circular_mask
            and (sub.width, sub.height, sub.fit, sub.rot)
            == (ingest.stream_w, ingest.stream_h, ingest.stream_fit, ingest.stream_rot)
        ):
            return frame
        eff_rot = (sub.rot - ingest.stream_rot) % _FULL_CIRCLE_DEG
        out: bytes = await self.hass.async_add_executor_job(
            partial(
                transcode_camera_frame,
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

    async def async_get_snapshot(  # noqa: PLR0913
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
        target_w, target_h = align16(width), align16(height)
        fit_mode = normalize_fit_mode(fit)
        rot_deg = normalize_rotation(rot)
        use_mask = bool(circular_mask and fit_mode == "fill")

        ingest = self._ingests.get(entity_id)
        if (
            ingest is not None
            and ingest.latest_frame is not None
            and (time.monotonic() - ingest.latest_frame_ts) <= max_age_s
        ):
            sub = _CameraSubscriber(target_w, target_h, 1, fit_mode, rot_deg, use_mask)
            try:
                return await self._async_format_for_subscriber(ingest, sub, ingest.latest_frame), True
            except Exception as err:
                raise CameraTranscodeError(str(err)) from err

        try:
            image_obj = await ha_camera.async_get_image(
                self.hass, entity_id, width=target_w, height=target_h, timeout=_SNAPSHOT_TIMEOUT_S
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

    async def _async_wait_next_ingest_frame(
        self, ingest: _CameraIngest, sub: _CameraSubscriber, wait_timeout_s: float
    ) -> bytes | None:
        ev = ingest.next_frame_event
        try:
            await asyncio.wait_for(ev.wait(), timeout=wait_timeout_s)
        except TimeoutError as err:
            if ingest.latest_frame is not None:
                return await self._async_format_for_subscriber(ingest, sub, ingest.latest_frame)
            if ingest.latest_error is not None:
                raise CameraFetchError(str(ingest.latest_error)) from err
            return None
        if ingest.latest_frame is None and ingest.latest_error is not None:
            raise CameraFetchError(str(ingest.latest_error)) from ingest.latest_error
        return None

    async def async_iter_stream_frames(  # noqa: PLR0913
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
            entity_id, width, height, fps, fit=fit, rot=rot, circular_mask=circular_mask
        )
        min_interval = 1.0 / float(sub.fps)
        last_seq = 0
        last_emit = 0.0
        try:
            while not ingest.closed:
                if ingest.latest_seq > last_seq and ingest.latest_frame is not None:
                    now = time.monotonic()
                    if last_emit > 0.0 and (now - last_emit) < min_interval * 0.9:
                        await asyncio.sleep(min_interval - (now - last_emit))
                    frame, last_seq = ingest.latest_frame, ingest.latest_seq
                    if frame is None:
                        continue
                    out_bytes = await self._async_format_for_subscriber(ingest, sub, frame)
                    last_emit = time.monotonic()
                    yield out_bytes
                    continue

                if ingest.latest_frame is None and ingest.latest_error is not None:
                    raise CameraFetchError(str(ingest.latest_error)) from ingest.latest_error

                keepalive = await self._async_wait_next_ingest_frame(ingest, sub, wait_timeout_s)
                if keepalive is not None:
                    last_emit = time.monotonic()
                    yield keepalive
        finally:
            self._unsubscribe(ingest, sub)

    async def async_iter_mjpeg_chunks(  # noqa: PLR0913
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
            entity_id, width, height, fps=fps, fit=fit, rot=rot, circular_mask=circular_mask
        ):
            yield format_mjpeg_chunk(frame)

    def _resolve_grid_labels(self, cams: list[str], overrides: Mapping[str, str]) -> list[str]:
        labels: list[str] = []
        for cam in cams:
            if custom_lbl := str(overrides.get(cam) or "").strip():
                labels.append(custom_lbl)
                continue
            st = self.hass.states.get(cam)
            friendly = str(st.attributes.get("friendly_name") or "").strip() if st else ""
            labels.append(friendly or cam.split(".", 1)[-1].replace("_", " ").title())
        return labels

    async def _async_try_subscribe_grid_slot(
        self, cam: str, quad_dims: tuple[int, int, int], fit_mode: str
    ) -> tuple[tuple[_CameraIngest, _CameraSubscriber] | None, CameraIngestLimitError | None]:
        quad_w, quad_h, target_fps = quad_dims
        try:
            pair = await self._subscribe(
                cam, quad_w, quad_h, target_fps, fit=fit_mode, rot=0, circular_mask=False
            )
            return pair, None
        except CameraIngestLimitError as err:
            _LOGGER.debug("Grid slot %s hit video ingest limit: %s", cam, err)
            return None, err
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Grid slot %s unavailable: %s", cam, err)
            return None, None

    async def _async_subscribe_grid_slots(
        self, cams: list[str], quad_dims: tuple[int, int, int], fit_mode: str
    ) -> tuple[list[tuple[_CameraIngest, _CameraSubscriber] | None], CameraIngestLimitError | None]:
        attached: list[tuple[_CameraIngest, _CameraSubscriber] | None] = []
        limit_err: CameraIngestLimitError | None = None
        for cam in cams:
            pair, slot_limit_err = await self._async_try_subscribe_grid_slot(cam, quad_dims, fit_mode)
            if slot_limit_err is not None:
                limit_err = slot_limit_err
            attached.append(pair)
        return attached, limit_err

    async def async_iter_grid_frames(  # noqa: PLR0913
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
        cams = [c.strip() for c in entity_ids if c and c.strip()][:_MAX_GRID_SLOTS]
        out_w, out_h = align16(width), align16(height)
        target_fps = normalize_fps(fps, default=5)
        fit_mode = normalize_fit_mode(fit)
        quad_w, quad_h = align16((out_w - GRID_GUTTER_PX) // 2), align16((out_h - GRID_GUTTER_PX) // 2)
        labels = self._resolve_grid_labels(cams, label_overrides or {})
        interval = 1.0 / float(target_fps)

        attached: list[tuple[_CameraIngest, _CameraSubscriber] | None] = []
        try:
            attached, limit_err = await self._async_subscribe_grid_slots(
                cams, (quad_w, quad_h, target_fps), fit_mode
            )
            active_ingests = [pair[0] for pair in attached if pair is not None]
            if not active_ingests and limit_err is not None:
                raise limit_err

            if active_ingests and not any(ing.latest_frame is not None for ing in active_ingests):
                waiters = [asyncio.create_task(ing.next_frame_event.wait()) for ing in active_ingests]
                _done, pending = await asyncio.wait(
                    waiters,
                    timeout=min(_GRID_FIRST_FRAME_CAP_S, interval * 2.0),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await p

            while True:
                t0 = time.monotonic()
                slot_frames = [
                    pair[0].latest_frame
                    if (
                        pair is not None
                        and pair[0].latest_frame is not None
                        and (t0 - pair[0].latest_frame_ts) <= stale_after_s
                    )
                    else None
                    for pair in attached
                ]
                yield await self.hass.async_add_executor_job(
                    partial(compose_grid_frame, slot_frames, labels, out_w, out_h, fit=fit_mode)
                )
                sleep_for = interval - (time.monotonic() - t0)
                if sleep_for > _MIN_SLEEP_THRESHOLD_S:
                    await asyncio.sleep(sleep_for)
        finally:
            for pair in attached:
                if pair is not None:
                    self._unsubscribe(pair[0], pair[1])

    async def async_iter_grid_mjpeg_chunks(  # noqa: PLR0913
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
            entity_ids, width, height, fps=fps, fit=fit, label_overrides=label_overrides
        ):
            yield format_mjpeg_chunk(frame)


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
