"""Local-only signed camera snapshot, MJPEG single/grid stream, and RTSP audio stream HTTP views (`L3`, 4 of 8 HTTP views, `M-P3-03`)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from http import HTTPStatus
import io
import logging
import shutil
import wave

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from ..cameras.stream_hub import (
    async_shutdown_camera_stream_hub,
    get_camera_stream_hub,
)
from ..cameras.transcode import (
    MJPEG_CONTENT_TYPE,
    CameraFetchError,
    CameraIngestLimitError,
    CameraTranscodeError,
    align16,
    normalize_fit_mode,
    normalize_fps,
)
from ..const import (
    API_CAMERA_AUDIO_STREAM_PATH,
    API_CAMERA_GRID_PATH,
    API_CAMERA_PROXY_PATH,
    API_CAMERA_STREAM_PATH,
    normalize_device_slug,
    normalize_noise_reduction,
)
from ..coordinator import LatterCoordinator, resolve_coordinator
from ..hub_registry import get_latter_system
from ..media_cache import clear_http_caches
from .proxy_views import (
    _is_private_or_loopback_client,
    _parse_dimensions_and_shape,
    _parse_render_params,
)
from .signing import camera_allowlist_hash

_LOGGER = logging.getLogger(__name__)

SILENCE_FALLBACK_MS: int = 250
_FFMPEG_STREAM_SEMAPHORE = asyncio.Semaphore(2)
_ACTIVE_DEVICE_STREAMS: dict[str, asyncio.subprocess.Process] = {}
_FFMPEG_PROTOCOL_WHITELIST = "file,crypto,data,http,https,tcp,tls,rtp,rtsp,udp"
_ALLOWED_STREAM_SCHEMES: tuple[str, ...] = ("rtsp://", "rtsps://", "http://", "https://")
_VALID_ROTATIONS: frozenset[str] = frozenset({"0", "90", "180", "270"})
_VALID_SAMPLE_RATES: frozenset[int] = frozenset({16000, 22050, 24000, 44100, 48000})
_DEFAULT_SAMPLE_RATE = 48000
_STEREO_CHANNELS = 2
_MAX_GRID_CAMERAS = 4
_AUDIO_READ_CHUNK = 4096
_SYSTEM_PREVIEW_W = 320
_SYSTEM_PREVIEW_H = 180


@dataclass(slots=True)
class _SnapshotTarget:
    """Validated target parameters for `LatterCameraSnapshotView`."""

    cam_entity: str
    width: int
    height: int
    is_circle: bool


@dataclass(slots=True)
class _AudioStreamConfig:
    """Validated audio stream target and codec parameters for `LatterCameraAudioStreamView`."""

    coord: LatterCoordinator
    cam_ent: str
    nr_level: str
    fmt: str
    out_rate: int
    out_ch: int


def _is_allowed_stream_url(stream_url: str | None) -> bool:
    """Return True only when `stream_url` uses an explicit `rtsp(s)://` or `http(s)://` scheme (`M-P1-30`)."""
    if not stream_url:
        return False
    clean = stream_url.strip()
    if not clean or clean.startswith("-"):
        return False
    return clean.lower().startswith(_ALLOWED_STREAM_SCHEMES)


async def async_shutdown_camera_feeds(hass: HomeAssistant | None = None) -> None:
    """Shut down shared camera video ingests and clear HTTP caches on integration unload."""
    if hass is not None:
        await async_shutdown_camera_stream_hub(hass)
    clear_http_caches()


async def _terminate_ffmpeg_process(
    proc: asyncio.subprocess.Process, timeout_s: float
) -> None:
    """Gracefully terminate an FFmpeg subprocess, escalating to `kill()` on timeout."""
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
    except ProcessLookupError:
        pass


async def async_shutdown_doorbell_streams(hass: HomeAssistant | None = None) -> None:
    """Terminate all active FFmpeg camera audio subprocesses on integration unload."""
    _ = hass
    active = list(_ACTIVE_DEVICE_STREAMS.items())
    _ACTIVE_DEVICE_STREAMS.clear()
    for _sub_id, proc in active:
        await _terminate_ffmpeg_process(proc, 1.5)


def _build_silence_wav(
    duration_ms: int = SILENCE_FALLBACK_MS, sample_rate: int = _DEFAULT_SAMPLE_RATE
) -> bytes:
    """Build a short PCM16 mono silent WAV buffer at the device's I2S bus sample rate."""
    num_samples = max(160, int(sample_rate * (duration_ms / 1000.0)))
    out_io = io.BytesIO()
    with wave.open(out_io, "wb") as wf_out:
        wf_out.setnchannels(1)
        wf_out.setsampwidth(2)
        wf_out.setframerate(sample_rate)
        wf_out.writeframes(b"\x00\x00" * num_samples)
    return out_io.getvalue()


def build_noise_reduction_filter(level: str) -> str:
    """Build the FFmpeg audio filter chain for a doorbell listen stream."""
    if level == "off":
        return "highpass=f=60,alimiter=limit=0.95"
    if level == "light":
        return (
            "highpass=f=100,lowpass=f=4000,"
            "afftdn=nf=-20,"
            "acompressor=threshold=-18dB:ratio=2.5:attack=5:release=90,"
            "alimiter=limit=0.91"
        )
    return (
        "highpass=f=120,lowpass=f=3600,"
        "afftdn=nf=-26,"
        "equalizer=f=1800:t=q:w=1.2:g=3,"
        "acompressor=threshold=-20dB:ratio=3.2:attack=4:release=75:makeup=2,"
        "alimiter=limit=0.89"
    )


def _resolve_device_snapshot_target(
    coordinator: LatterCoordinator, request: web.Request
) -> tuple[_SnapshotTarget | None, web.Response | None]:
    """Validate signature and camera allow-list for a Device snapshot request."""
    cam_entity = str(
        request.query.get("entity_id") or coordinator.camera_entity or ""
    ).strip()
    if not cam_entity or not cam_entity.startswith("camera."):
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="No camera entity specified"
        )
    width, height, is_circle, shape_str = _parse_render_params(
        request,
        coordinator,
        default_circle=(coordinator.display_shape == "circle"),
    )
    visible_cams = coordinator.visible_camera_entities
    visible_set = set(visible_cams)
    allow_hash = camera_allowlist_hash(visible_cams)
    sig = request.query.get("sig")
    allow_sig_ok = bool(visible_cams) and coordinator.verify_resource(
        f"camera_allow:{allow_hash}|{width}|{height}|{shape_str}", sig=sig
    )
    single_sig_ok = coordinator.verify_resource(
        f"camera:{cam_entity}|{width}|{height}|{shape_str}", sig=sig
    )
    if not (allow_sig_ok or single_sig_ok):
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN, text="Invalid signature"
        )
    if allow_sig_ok and cam_entity not in visible_set:
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN, text="Camera entity not in allow-list"
        )
    allowed_single = visible_set | (
        {coordinator.alert_camera_entity}
        if coordinator.alert_camera_entity
        else set()
    )
    if not allow_sig_ok and cam_entity not in allowed_single:
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="Camera entity not in allow-list"
        )
    return _SnapshotTarget(cam_entity, width, height, is_circle), None


def _resolve_system_snapshot_target(
    hass: HomeAssistant, request: web.Request, target_device: str
) -> tuple[_SnapshotTarget | None, web.Response | None]:
    """Validate signature and dimensions for a System-scoped snapshot preview."""
    if normalize_device_slug(target_device) != "system":
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="Unknown target device"
        )
    sys_obj = get_latter_system(hass)
    if sys_obj is None or sys_obj.url_signer is None:
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="Latter System not initialized"
        )
    cam_entity = str(request.query.get("entity_id") or "").strip()
    if not cam_entity or not cam_entity.startswith("camera."):
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="No camera entity specified"
        )
    width, height, is_circle, shape_str = _parse_dimensions_and_shape(
        request, _SYSTEM_PREVIEW_W, _SYSTEM_PREVIEW_H, default_circle=False
    )
    if not sys_obj.url_signer.verify_resource(
        f"camera:{cam_entity}|{width}|{height}|{shape_str}",
        sig=request.query.get("sig"),
    ):
        return None, web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")
    if hass.states.get(cam_entity) is None:
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="Camera entity not found"
        )
    return _SnapshotTarget(cam_entity, width, height, is_circle), None


def _resolve_snapshot_target(
    hass: HomeAssistant, request: web.Request, target_device: str
) -> tuple[_SnapshotTarget | None, web.Response | None]:
    """Validate signature and camera allow-list for `LatterCameraSnapshotView`."""
    coordinator = resolve_coordinator(hass, target_device)
    if coordinator is not None:
        return _resolve_device_snapshot_target(coordinator, request)
    return _resolve_system_snapshot_target(hass, request, target_device)


class LatterCameraSnapshotView(HomeAssistantView):
    """Fetches a live frame from an allow-listed `camera.*` entity and transcodes to Baseline JPEG."""

    requires_auth = False
    url = API_CAMERA_PROXY_PATH
    name = "api:latter:camera_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the camera snapshot transcoder view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/camera/{target_device}?entity_id=camera.front_door&w=466&h=466&shape=circle&fit=contain"""
        target, err_resp = _resolve_snapshot_target(self.hass, request, target_device)
        if err_resp is not None or target is None:
            return err_resp or web.Response(status=HTTPStatus.NOT_FOUND)

        rot_str = (request.query.get("rot") or "0").strip()
        if rot_str not in _VALID_ROTATIONS:
            return web.Response(
                status=HTTPStatus.BAD_REQUEST, text="Invalid rotation angle"
            )
        rotate_deg = int(rot_str)
        raw_fit = request.query.get("fit")
        fit_mode = normalize_fit_mode(raw_fit) if raw_fit is not None else "contain"

        try:
            jpeg_bytes, from_memory = await get_camera_stream_hub(
                self.hass
            ).async_get_snapshot(
                target.cam_entity,
                target.width,
                target.height,
                fit=fit_mode,
                rot=rotate_deg,
                circular_mask=(target.is_circle and fit_mode == "fill"),
            )
        except CameraFetchError as err:
            _LOGGER.debug(
                "Camera snapshot fetch failed for %s: %s", target.cam_entity, err
            )
            return web.Response(
                status=HTTPStatus.BAD_GATEWAY, text="Camera snapshot unavailable"
            )
        except CameraTranscodeError as err:
            _LOGGER.debug("Camera snapshot Pillow transcode failed: %s", err)
            return web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
                text="Camera image processing error",
            )

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={
                "Cache-Control": "private, no-store, max-age=0",
                "X-Latter-Cam-Cache": "HIT" if from_memory else "MISS",
            },
        )


def _clamp_video_query_dim(raw: str | None, max_dim: int) -> int:
    """Parse an integer query dimension, clamp to `[64, max_dim]`, and align down to 16px."""
    try:
        parsed = int(raw) if raw is not None and str(raw).strip() else max_dim
    except (TypeError, ValueError):
        parsed = max_dim
    return align16(min(max_dim, parsed), maximum=max_dim)


def _validate_video_stream_coord(
    hass: HomeAssistant, request: web.Request, target_device: str
) -> tuple[LatterCoordinator | None, web.Response | None]:
    """Validate LAN client, coordinator, HMAC `camera_stream:` signature, and video capability."""
    if not _is_private_or_loopback_client(request):
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN,
            text="Camera streams require local LAN client",
        )
    coord = resolve_coordinator(hass, target_device)
    if coord is None:
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="Unknown target device"
        )
    allowed = coord.visible_camera_entities
    max_w, max_h = coord.video_max_dims
    max_fps = coord.video_max_fps
    allow_hash = camera_allowlist_hash(allowed)
    if not coord.verify_resource(
        f"camera_stream:{allow_hash}|{max_w}|{max_h}|{max_fps}",
        sig=request.query.get("sig"),
    ):
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature"
        )
    if max_w <= 0 or max_h <= 0:
        return None, web.Response(
            status=HTTPStatus.BAD_REQUEST, text="Device does not support video"
        )
    return coord, None


async def _async_stream_mjpeg_iterator(
    request: web.Request,
    stream_iter: AsyncIterator[bytes],
    unavail_text: str,
    label: str,
) -> web.StreamResponse:
    """Pull the first MJPEG chunk before committing HTTP 200 headers, then stream until closed."""
    try:
        try:
            first_chunk = await anext(stream_iter)
        except StopAsyncIteration:
            return web.Response(status=HTTPStatus.BAD_GATEWAY, text=unavail_text)
        except CameraIngestLimitError:
            return web.Response(
                status=HTTPStatus.TOO_MANY_REQUESTS,
                text="Maximum concurrent camera streams reached",
            )
        except CameraFetchError as err:
            _LOGGER.debug("Camera stream start failed (%s): %s", label, err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY, text=unavail_text)

        resp = web.StreamResponse(
            status=HTTPStatus.OK,
            headers={
                "Content-Type": MJPEG_CONTENT_TYPE,
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "X-Accel-Buffering": "no",
            },
        )
        await resp.prepare(request)
        try:
            await resp.write(first_chunk)
            async for chunk in stream_iter:
                await resp.write(chunk)
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Camera stream closed (%s): %s", label, err)
        return resp
    finally:
        aclose = getattr(stream_iter, "aclose", None)
        if callable(aclose):
            await aclose()


class LatterCameraStreamView(HomeAssistantView):
    """Streams live 16px-aligned Baseline 4:2:0 MJPEG video for a single allow-listed camera."""

    requires_auth = False
    url = API_CAMERA_STREAM_PATH
    name = "api:latter:camera_stream"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the single-camera MJPEG stream view."""
        self.hass = hass

    async def get(
        self, request: web.Request, target_device: str
    ) -> web.StreamResponse:
        """Handle GET /api/latter/camera_stream/{target_device}?entity_id=...&w=...&h=...&fps=...&fit=contain&rot=0&sig=..."""
        coord, err_resp = _validate_video_stream_coord(self.hass, request, target_device)
        if err_resp is not None or coord is None:
            return err_resp or web.Response(status=HTTPStatus.NOT_FOUND)

        allowed = coord.visible_camera_entities
        cam_entity = (
            request.query.get("entity_id")
            or coord.active_carousel_camera
            or (allowed[0] if allowed else "")
        ).strip()
        if not cam_entity or not cam_entity.startswith("camera."):
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="No camera entity configured"
            )
        if cam_entity not in set(allowed):
            return web.Response(
                status=HTTPStatus.FORBIDDEN, text="Camera entity not in allow-list"
            )

        rot_str = (request.query.get("rot") or "0").strip()
        if rot_str not in _VALID_ROTATIONS:
            return web.Response(
                status=HTTPStatus.BAD_REQUEST, text="Invalid rotation angle"
            )

        max_w, max_h = coord.video_max_dims
        max_fps = coord.video_max_fps
        req_w = _clamp_video_query_dim(request.query.get("w"), max_w)
        req_h = _clamp_video_query_dim(request.query.get("h"), max_h)
        req_fps = min(
            max_fps, normalize_fps(request.query.get("fps"), default=max_fps)
        )
        fit_mode = normalize_fit_mode(request.query.get("fit"))
        is_circle = (request.query.get("shape") or "").strip().lower() == "circle"

        stream_iter = get_camera_stream_hub(self.hass).async_iter_mjpeg_chunks(
            cam_entity,
            req_w,
            req_h,
            fps=req_fps,
            fit=fit_mode,
            rot=int(rot_str),
            circular_mask=(is_circle and fit_mode == "fill"),
        )
        return await _async_stream_mjpeg_iterator(
            request, stream_iter, "Camera stream unavailable", cam_entity
        )


def _parse_grid_requested_cameras(
    raw_csv: str, allowed: list[str]
) -> list[str]:
    """Parse up to 4 unique requested grid camera IDs (defaulting to first 4 visible cameras)."""
    if not raw_csv:
        return list(allowed[:_MAX_GRID_CAMERAS])
    requested: list[str] = []
    for tok in raw_csv.split(","):
        cid = tok.strip()
        if cid and cid not in requested:
            requested.append(cid)
    return requested[:_MAX_GRID_CAMERAS]


class LatterCameraGridView(HomeAssistantView):
    """Streams a server-side 2x2 composited Baseline 4:2:0 MJPEG grid for up to 4 allow-listed cameras."""

    requires_auth = False
    url = API_CAMERA_GRID_PATH
    name = "api:latter:camera_grid"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the 2x2 camera grid MJPEG stream view."""
        self.hass = hass

    async def get(
        self, request: web.Request, target_device: str
    ) -> web.StreamResponse:
        """Handle GET /api/latter/camera_grid/{target_device}?cameras=cam1,cam2,...&w=...&h=...&fps=...&fit=contain&sig=..."""
        coord, err_resp = _validate_video_stream_coord(self.hass, request, target_device)
        if err_resp is not None or coord is None:
            return err_resp or web.Response(status=HTTPStatus.NOT_FOUND)

        allowed = coord.visible_camera_entities
        allowed_set = set(allowed)
        requested = _parse_grid_requested_cameras(
            str(request.query.get("cameras") or "").strip(), allowed
        )
        if not requested:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="No cameras configured for grid"
            )
        if any(
            not cid.startswith("camera.") or cid not in allowed_set
            for cid in requested
        ):
            return web.Response(
                status=HTTPStatus.FORBIDDEN,
                text="One or more camera entities not in allow-list",
            )

        max_w, max_h = coord.video_max_dims
        grid_fps = min(coord.video_max_fps, coord.video_grid_fps)
        req_w = _clamp_video_query_dim(request.query.get("w"), max_w)
        req_h = _clamp_video_query_dim(request.query.get("h"), max_h)
        req_fps = min(
            grid_fps, normalize_fps(request.query.get("fps"), default=grid_fps)
        )
        fit_mode = normalize_fit_mode(request.query.get("fit"))

        cam_configs = coord.camera_configs
        label_overrides = {
            cid: str(cfg.get("label") or "").strip()
            for cid, cfg in cam_configs.items()
            if isinstance(cfg, dict) and str(cfg.get("label") or "").strip()
        }
        stream_iter = get_camera_stream_hub(self.hass).async_iter_grid_mjpeg_chunks(
            requested,
            req_w,
            req_h,
            fps=req_fps,
            fit=fit_mode,
            label_overrides=label_overrides or None,
        )
        return await _async_stream_mjpeg_iterator(
            request, stream_iter, "Camera grid stream unavailable", "grid"
        )


def _validate_camera_audio_request(
    hass: HomeAssistant, request: web.Request, target_device: str
) -> tuple[_AudioStreamConfig | None, web.Response | None]:
    """Validate LAN client, signature (`camera_audio:...`), allow-list, and device audio traits."""
    if not _is_private_or_loopback_client(request):
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN,
            text="Camera audio streams require local LAN client",
        )
    coord = resolve_coordinator(hass, target_device)
    if coord is None:
        return None, web.Response(status=HTTPStatus.NOT_FOUND)

    cam_ent = (
        request.query.get("entity_id")
        or coord.active_carousel_camera
        or coord.camera_entity
        or ""
    ).strip()
    if not cam_ent:
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="No camera entity configured"
        )

    raw_nr = (
        (request.query.get("nr") or coord.doorbell_noise_reduction).strip().lower()
    )
    raw_fmt = (request.query.get("fmt") or "flac").strip().lower()
    if not coord.verify_resource(
        f"camera_audio:{cam_ent}|{raw_nr}|{raw_fmt}",
        sig=request.query.get("sig"),
    ):
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature"
        )

    if cam_ent not in set(coord.visible_camera_entities):
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN, text="Camera entity not authorized"
        )

    audio_info = coord.hardware_manifest.get("audio")
    raw_rate = (
        int(audio_info.get("out_rate") or _DEFAULT_SAMPLE_RATE)
        if isinstance(audio_info, dict)
        else _DEFAULT_SAMPLE_RATE
    )
    raw_ch = (
        int(audio_info.get("out_ch") or 1) if isinstance(audio_info, dict) else 1
    )
    out_rate = raw_rate if raw_rate in _VALID_SAMPLE_RATES else _DEFAULT_SAMPLE_RATE
    out_ch = _STEREO_CHANNELS if raw_ch == _STEREO_CHANNELS else 1
    return (
        _AudioStreamConfig(
            coord=coord,
            cam_ent=cam_ent,
            nr_level=normalize_noise_reduction(raw_nr),
            fmt="wav" if raw_fmt == "wav" else "flac",
            out_rate=out_rate,
            out_ch=out_ch,
        ),
        None,
    )


async def _async_resolve_stream_and_ffmpeg(
    hass: HomeAssistant, cam_ent: str
) -> tuple[str | None, str | None]:
    """Resolve the upstream camera RTSP/HTTP stream URL and local FFmpeg binary path."""
    stream_url: str | None = None
    try:
        from homeassistant.components import camera as ha_camera

        stream_url = await ha_camera.async_get_stream_source(hass, cam_ent)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("camera.async_get_stream_source(%s) failed: %s", cam_ent, err)

    try:
        from homeassistant.components.ffmpeg import get_ffmpeg_manager

        ffmpeg_bin: str | None = get_ffmpeg_manager(hass).binary
    except Exception:  # noqa: BLE001
        ffmpeg_bin = shutil.which("ffmpeg")
    return stream_url, ffmpeg_bin


def _build_camera_audio_ffmpeg_cmd(
    ffmpeg_bin: str, clean_stream_url: str, cfg: _AudioStreamConfig
) -> list[str]:
    """Build hardened FFmpeg CLI arguments for live camera audio transcoding (`M-P1-30`)."""
    filtergraph = build_noise_reduction_filter(cfg.nr_level)
    out_codec = "flac" if cfg.fmt == "flac" else "pcm_s16le"
    out_fmt = "flac" if cfg.fmt == "flac" else "wav"
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-protocol_whitelist",
        _FFMPEG_PROTOCOL_WHITELIST,
    ]
    if clean_stream_url.lower().startswith(("rtsp://", "rtsps://")):
        cmd.extend(["-rtsp_transport", "tcp"])
    cmd.extend(
        [
            "-rw_timeout",
            "5000000",
            "-i",
            clean_stream_url,
            "-t",
            "120",
            "-vn",
            "-sn",
            "-dn",
            "-af",
            filtergraph,
            "-ar",
            str(cfg.out_rate),
            "-ac",
            str(cfg.out_ch),
            "-c:a",
            out_codec,
            "-f",
            out_fmt,
            "pipe:1",
        ]
    )
    return cmd


async def _async_pipe_ffmpeg_audio(
    request: web.Request, cfg: _AudioStreamConfig, cmd: list[str]
) -> web.StreamResponse:
    """Run FFmpeg audio transcode under `_FFMPEG_STREAM_SEMAPHORE` and pipe stdout to `request`."""
    prev_proc = _ACTIVE_DEVICE_STREAMS.pop(cfg.coord.subentry_id, None)
    if prev_proc is not None:
        await _terminate_ffmpeg_process(prev_proc, 1.5)

    content_type = "audio/flac" if cfg.fmt == "flac" else "audio/wav"
    resp = web.StreamResponse(
        status=HTTPStatus.OK,
        headers={
            "Content-Type": content_type,
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )
    await resp.prepare(request)

    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _ACTIVE_DEVICE_STREAMS[cfg.coord.subentry_id] = proc
        if proc.stdout is not None:
            while True:
                chunk = await proc.stdout.read(_AUDIO_READ_CHUNK)
                if not chunk:
                    break
                await resp.write(chunk)
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Camera audio stream ended for %s: %s", cfg.cam_ent, err)
    finally:
        if _ACTIVE_DEVICE_STREAMS.get(cfg.coord.subentry_id) is proc:
            _ACTIVE_DEVICE_STREAMS.pop(cfg.coord.subentry_id, None)
        if proc is not None:
            await _terminate_ffmpeg_process(proc, 3.0)
    return resp


class LatterCameraAudioStreamView(HomeAssistantView):
    """Streams live RTSP camera audio through an FFmpeg noise-reduction filter to a Latter device."""

    requires_auth = False
    url = API_CAMERA_AUDIO_STREAM_PATH
    name = "api:latter:camera_audio_stream"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the camera audio stream view."""
        self.hass = hass

    async def get(
        self, request: web.Request, target_device: str
    ) -> web.StreamResponse:
        """Stream live de-noised FLAC/WAV audio from a camera's RTSP source."""
        cfg, err_resp = _validate_camera_audio_request(
            self.hass, request, target_device
        )
        if err_resp is not None or cfg is None:
            return err_resp or web.Response(status=HTTPStatus.NOT_FOUND)

        stream_url, ffmpeg_bin = await _async_resolve_stream_and_ffmpeg(
            self.hass, cfg.cam_ent
        )
        if not stream_url or not _is_allowed_stream_url(stream_url) or not ffmpeg_bin:
            return web.Response(
                body=_build_silence_wav(sample_rate=cfg.out_rate),
                content_type="audio/wav",
            )

        try:
            await asyncio.wait_for(_FFMPEG_STREAM_SEMAPHORE.acquire(), timeout=0.25)
        except TimeoutError:
            return web.Response(
                status=HTTPStatus.TOO_MANY_REQUESTS,
                text="Maximum concurrent camera audio streams reached",
            )

        try:
            cmd = _build_camera_audio_ffmpeg_cmd(ffmpeg_bin, stream_url.strip(), cfg)
            return await _async_pipe_ffmpeg_audio(request, cfg, cmd)
        finally:
            _FFMPEG_STREAM_SEMAPHORE.release()
