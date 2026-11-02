"""Universal Doorbell Two-Way Audio (go2rtc, ONVIF), 90° Landscape Proxy & FFmpeg ANC Filterchain Engine."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import io
import logging
import shutil
import time
from typing import Any
import wave

from aiohttp import ClientTimeout, web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .ble_engine import _iter_entities
from .const import (
    API_CAMERA_AUDIO_STREAM_PATH,
    API_DOORBELL_TALKBACK_PATH,
    DOMAIN,
    normalize_device_slug,
)
from .area_engine import resolve_entity_area_id
from .media_engine import async_announce_on_targets

_LOGGER = logging.getLogger(__name__)

UNIFI_PREROLL_MS: int = 250
TALKBACK_ECHO_GUARD_SECONDS: float = 0.75
_FFMPEG_STREAM_SEMAPHORE = asyncio.Semaphore(2)


def _build_silence_wav(duration_ms: int = UNIFI_PREROLL_MS, sample_rate: int = 16000) -> bytes:
    """Build a short PCM16 mono silent WAV buffer."""
    num_samples = max(160, int(sample_rate * (duration_ms / 1000.0)))
    out_io = io.BytesIO()
    with wave.open(out_io, "wb") as wf_out:
        wf_out.setnchannels(1)
        wf_out.setsampwidth(2)
        wf_out.setframerate(sample_rate)
        wf_out.writeframes(b"\x00\x00" * num_samples)
    return out_io.getvalue()


def resolve_doorbell_talkback_target(
    hass: HomeAssistant,
    camera_entity_id: str | None,
    volume_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Auto-discover the talkback media_player, ONVIF/go2rtc stream, and area lock for a camera."""
    info: dict[str, Any] = {
        "camera_entity": "",
        "friendly_name": "Camera",
        "talkback_media_player": "",
        "platform": "",
        "is_unifi": False,
        "area_id": "",
        "lock_entity": "",
    }
    if not camera_entity_id:
        return info

    cam_ent = camera_entity_id.strip()
    info["camera_entity"] = cam_ent
    cam_state = hass.states.get(cam_ent)
    if cam_state is not None:
        info["friendly_name"] = str(
            cam_state.attributes.get("friendly_name") or cam_ent
        )

    if volume_overrides and cam_ent in volume_overrides:
        mapped_spk = str(volume_overrides[cam_ent]).strip()
        if mapped_spk.startswith("media_player."):
            info["talkback_media_player"] = mapped_spk

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    cam_entry = ent_reg.async_get(cam_ent)

    if cam_entry is not None:
        info["platform"] = str(cam_entry.platform or "")
        if cam_entry.platform == "unifiprotect":
            info["is_unifi"] = True

        if cam_entry.device_id:
            dev = dev_reg.async_get(cam_entry.device_id)
            if dev is not None:
                mfg_model = f"{dev.manufacturer or ''} {dev.model or ''}".lower()
                if any(k in mfg_model for k in ("ubiquiti", "unifi", "g4", "g5", "g6")):
                    info["is_unifi"] = True

            for sib in er.async_entries_for_device(ent_reg, cam_entry.device_id):
                if sib.disabled_by:
                    continue
                if sib.domain == "media_player" and not info["talkback_media_player"]:
                    info["talkback_media_player"] = sib.entity_id
                    if sib.platform == "unifiprotect":
                        info["is_unifi"] = True
                elif sib.domain == "lock" and not info["lock_entity"]:
                    info["lock_entity"] = sib.entity_id

    if not info["talkback_media_player"]:
        base_slug = cam_ent.split(".", 1)[-1]
        for suffix in ("_high", "_medium", "_low", "_package", "_camera", "_rtsp", "_fluent", "_clear"):
            if base_slug.endswith(suffix):
                base_slug = base_slug[: -len(suffix)]
                break
        for cand_mp in (
            f"media_player.{base_slug}_speaker",
            f"media_player.{base_slug}",
        ):
            if hass.states.get(cand_mp) is not None:
                info["talkback_media_player"] = cand_mp
                mp_entry = ent_reg.async_get(cand_mp)
                if mp_entry and mp_entry.platform == "unifiprotect":
                    info["is_unifi"] = True
                break

        if not info["talkback_media_player"]:
            for entry in _iter_entities(ent_reg):
                if entry.domain == "media_player" and not entry.disabled_by:
                    if base_slug and base_slug in entry.entity_id and "speaker" in entry.entity_id:
                        info["talkback_media_player"] = entry.entity_id
                        if entry.platform == "unifiprotect":
                            info["is_unifi"] = True
                        break

    area_id = resolve_entity_area_id(hass, cam_ent) or ""
    info["area_id"] = area_id

    return info


class LatterAudioDspPipeline:
    """FFmpeg ANC Filtergraph Builder and Talkback Echo-Guard Timing Pipeline."""

    def __init__(self) -> None:
        """Initialize the talkback echo-guard state."""
        self._last_talkback_mono: float = 0.0

    def record_talkback_activity(self) -> None:
        """Record outbound talkback timestamp for the acoustic echo guard."""
        self._last_talkback_mono = time.monotonic()

    def is_in_echo_guard_window(self) -> bool:
        """Return True if outbound talkback is active or within the 750ms acoustic tail window."""
        return (time.monotonic() - self._last_talkback_mono) < TALKBACK_ECHO_GUARD_SECONDS

    @staticmethod
    def build_ffmpeg_anc_filtergraph(anc_mode: str = "ultra") -> str:
        """Build the broadcast-grade FFmpeg audio filterchain for live RTSP doorbell streams."""
        mode = (anc_mode or "ultra").strip().lower()
        if mode == "raw":
            return "highpass=f=60,alimiter=limit=0.95"
        if mode == "balanced":
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


def get_dsp_pipeline(hass: HomeAssistant) -> LatterAudioDspPipeline:
    """Return the singleton LatterAudioDspPipeline instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "audio_dsp" not in domain_data:
        domain_data["audio_dsp"] = LatterAudioDspPipeline()
    return domain_data["audio_dsp"]


def _resolve_coordinator_by_slug(hass: HomeAssistant, target_slug: str) -> Any | None:
    """Find a loaded LatterCoordinator by device slug or entry_id."""
    from .coordinator import resolve_coordinator

    return resolve_coordinator(hass, target_slug)


async def _async_push_go2rtc_or_onvif_backchannel(
    hass: HomeAssistant, camera_entity_id: str, wav_bytes: bytes
) -> bool:
    """Attempt to push talkback audio via local go2rtc (port 1984) or ONVIF RTSP backchannel."""
    slug = camera_entity_id.split(".", 1)[-1]
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            "http://127.0.0.1:1984/api/streams", timeout=ClientTimeout(total=1.5)
        ) as resp:
            if resp.status == 200:
                streams = await resp.json()
                matched_stream = None
                if isinstance(streams, dict):
                    if slug in streams:
                        matched_stream = slug
                    else:
                        for s_key in streams:
                            if slug in str(s_key).lower():
                                matched_stream = str(s_key)
                                break
                if matched_stream:
                    post_url = f"http://127.0.0.1:1984/api/streams?dst={matched_stream}"
                    async with session.post(
                        post_url, data=wav_bytes, timeout=ClientTimeout(total=8.0)
                    ) as p_resp:
                        if p_resp.status in (200, 201, 204):
                            return True
    except Exception:  # noqa: BLE001
        pass
    return False


class LatterCameraAudioStreamView(HomeAssistantView):
    """Streams live RTSP camera audio through Latter's 4-Stage ANC+AEC filterchain to ESPHome."""

    requires_auth = False
    url = API_CAMERA_AUDIO_STREAM_PATH
    name = "api:latter:camera_audio_stream"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the camera audio stream view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.StreamResponse:
        """Stream live de-noised FLAC/WAV audio from a camera's RTSP source."""
        coord = _resolve_coordinator_by_slug(self.hass, target_device)
        if coord is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        cam_ent = (
            request.query.get("entity_id")
            or coord.active_carousel_camera
            or coord.camera_entity
            or ""
        ).strip()
        if not cam_ent:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="No camera entity configured")

        if not coord.verify_resource(
            f"camera_audio:{cam_ent}",
            sig=request.query.get("sig"),
        ):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature")

        allowed_cams = set(coord.camera_entities)
        if coord.camera_entity:
            allowed_cams.add(coord.camera_entity)
        if coord.active_carousel_camera:
            allowed_cams.add(coord.active_carousel_camera)
        if cam_ent not in allowed_cams:
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Camera entity not authorized")

        anc_mode = (
            request.query.get("anc")
            or coord.doorbell_anc_mode
            or "ultra"
        ).strip().lower()
        fmt = (request.query.get("fmt") or "flac").strip().lower()

        stream_url: str | None = None
        try:
            from homeassistant.components import camera as ha_camera

            stream_url = await ha_camera.async_get_stream_source(self.hass, cam_ent)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("camera.async_get_stream_source(%s) failed: %s", cam_ent, err)

        dsp = get_dsp_pipeline(self.hass)

        ffmpeg_bin: str | None = None
        try:
            from homeassistant.components.ffmpeg import get_ffmpeg_manager

            ffmpeg_bin = get_ffmpeg_manager(self.hass).binary
        except Exception:  # noqa: BLE001
            ffmpeg_bin = shutil.which("ffmpeg")

        if not stream_url or not ffmpeg_bin:
            return web.Response(body=_build_silence_wav(), content_type="audio/wav")

        if _FFMPEG_STREAM_SEMAPHORE.locked():
            return web.Response(
                status=HTTPStatus.TOO_MANY_REQUESTS,
                text="Maximum concurrent camera audio streams reached",
            )

        input_args: list[str] = ["-rtsp_transport", "tcp"]
        filtergraph = LatterAudioDspPipeline.build_ffmpeg_anc_filtergraph(anc_mode)
        out_codec = "flac" if fmt == "flac" else "pcm_s16le"
        out_fmt = "flac" if fmt == "flac" else "wav"
        content_type = "audio/flac" if fmt == "flac" else "audio/wav"

        # Output format comes only from the device's declared audio traits (hardware manifest),
        # never from board-name matching.
        manifest = coord.hardware_manifest
        audio_info = manifest.get("audio")
        out_rate = (
            int(audio_info.get("out_rate") or 16000)
            if isinstance(audio_info, dict)
            else 16000
        )
        out_ch = (
            int(audio_info.get("out_ch") or 1)
            if isinstance(audio_info, dict)
            else 1
        )
        out_rate = out_rate if out_rate in (16000, 22050, 24000, 44100, 48000) else 16000
        out_ch = 2 if out_ch == 2 else 1

        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            *input_args,
            "-i",
            stream_url,
            "-vn",
            "-af",
            filtergraph,
            "-ar",
            str(out_rate),
            "-ac",
            str(out_ch),
            "-c:a",
            out_codec,
            "-f",
            out_fmt,
            "pipe:1",
        ]

        async with _FFMPEG_STREAM_SEMAPHORE:
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
                if proc.stdout is not None:
                    while True:
                        chunk = await proc.stdout.read(4096)
                        if not chunk:
                            break
                        if dsp.is_in_echo_guard_window() and out_fmt == "wav":
                            chunk = b"\x00" * len(chunk)
                        await resp.write(chunk)
            except (asyncio.CancelledError, ConnectionResetError):
                pass
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Camera audio stream ended for %s: %s", cam_ent, err)
            finally:
                if proc is not None and proc.returncode is None:
                    try:
                        proc.terminate()
                        await proc.wait()
                    except ProcessLookupError:
                        pass

            return resp


class LatterDoorbellTalkbackView(HomeAssistantView):
    """Serves and ingests talkback audio for camera speakers, go2rtc & ONVIF."""

    requires_auth = False
    url = API_DOORBELL_TALKBACK_PATH
    name = "api:latter:doorbell_talkback"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the doorbell talkback view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Serve the latest talkback WAV clip for media_player.<doorbell>_speaker."""
        norm = normalize_device_slug(target_device.removesuffix(".wav"))
        coord = _resolve_coordinator_by_slug(self.hass, norm)
        if coord is None or not coord.verify_resource(
            "talkback",
            sig=request.query.get("sig"),
        ):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature")

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        clips: dict[str, bytes] = domain_data.setdefault("talkback_clips", {})
        wav_bytes = clips.get(norm)
        if not wav_bytes:
            wav_bytes = _build_silence_wav()
        return web.Response(
            body=wav_bytes,
            content_type="audio/wav",
            headers={"Cache-Control": "no-store"},
        )

    async def post(self, request: web.Request, target_device: str) -> web.Response:
        """Ingest raw PCM16 or WAV talkback audio (requires admin HA user or valid talkback:<camera_entity> signature)."""
        coord = _resolve_coordinator_by_slug(self.hass, target_device)
        if coord is None:
            return web.json_response(
                {"error": "Unknown target device"}, status=HTTPStatus.NOT_FOUND
            )

        cam_ent = (
            request.query.get("camera_entity")
            or coord.active_carousel_camera
            or coord.camera_entity
            or ""
        ).strip()
        allowed_cams = set(coord.camera_entities)
        if coord.camera_entity:
            allowed_cams.add(coord.camera_entity)
        if coord.active_carousel_camera:
            allowed_cams.add(coord.active_carousel_camera)
        if not cam_ent or cam_ent not in allowed_cams:
            return web.json_response(
                {"error": "Camera entity not configured for this device"},
                status=HTTPStatus.FORBIDDEN,
            )

        user = request.get("hass_user")
        if user is None:
            auth_hdr = request.headers.get("Authorization", "")
            if auth_hdr.startswith("Bearer "):
                bearer = auth_hdr.removeprefix("Bearer ").strip()
                rt = await self.hass.auth.async_validate_access_token(bearer)
                if rt is not None:
                    user = rt.user

        is_admin_user = bool(user is not None and user.is_active and user.is_admin)
        sig = request.query.get("sig") or request.headers.get("X-Latter-Sig")
        has_valid_sig = coord.verify_resource(f"talkback:{cam_ent}", sig=sig)
        if not is_admin_user and not has_valid_sig:
            return web.json_response(
                {"error": "Forbidden"}, status=HTTPStatus.FORBIDDEN
            )

        raw_bytes = await request.read()
        if not raw_bytes:
            return web.json_response(
                {"error": "Empty audio payload"}, status=HTTPStatus.BAD_REQUEST
            )

        dsp = get_dsp_pipeline(self.hass)
        dsp.record_talkback_activity()

        norm = normalize_device_slug(target_device.removesuffix(".wav"))
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        clips: dict[str, bytes] = domain_data.setdefault("talkback_clips", {})
        clips[norm] = raw_bytes

        await async_play_talkback_clip_to_doorbell(self.hass, coord, cam_ent, raw_bytes)

        return web.json_response({"status": "ok", "bytes": len(raw_bytes)})


async def async_play_talkback_clip_to_doorbell(
    hass: HomeAssistant,
    coordinator: Any,
    camera_entity_id: str | None = None,
    wav_bytes: bytes | None = None,
) -> bool:
    """Stream the stored talkback WAV clip to camera speaker or go2rtc/ONVIF backchannel."""
    cam_ent = camera_entity_id or coordinator.active_carousel_camera or coordinator.camera_entity
    target_info = resolve_doorbell_talkback_target(
        hass, cam_ent, coordinator.volume_overrides
    )
    talkback_mp = target_info["talkback_media_player"]
    if talkback_mp:
        base_url = coordinator.get_lan_base_url()
        sig = coordinator.sign_resource("talkback", ttl_s=300)
        clip_url = (
            f"{base_url}/api/latter/doorbell_talkback/{coordinator.device_slug}.wav"
            f"?v={int(time.time() * 1000)}&sig={sig}"
        )
        try:
            await async_announce_on_targets(
                hass,
                speakers=[talkback_mp],
                media_url=clip_url,
                blocking=False,
            )
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Doorbell talkback announce failed on %s: %s", talkback_mp, err)

    if cam_ent and wav_bytes:
        if await _async_push_go2rtc_or_onvif_backchannel(hass, cam_ent, wav_bytes):
            return True

    return False


async def async_execute_doorbell_intercom(
    hass: HomeAssistant,
    coordinator: Any,
    action: str,
    camera_entity: str | None = None,
    message: str = "",
    anc_mode: str | None = None,
    camera_index: int | None = None,
) -> dict[str, Any]:
    """Execute a unified two-way doorbell or area-to-area intercom command."""
    act = (action or "listen_toggle").strip().lower()
    dsp = get_dsp_pipeline(hass)

    if anc_mode and anc_mode.strip().lower() in ("ultra", "balanced", "raw"):
        coordinator.doorbell_anc_mode = anc_mode.strip().lower()

    cams = coordinator.camera_entities
    if camera_index is not None and cams:
        idx = max(0, min(len(cams) - 1, int(camera_index)))
        coordinator.active_camera_index = idx
        coordinator.active_carousel_camera = cams[idx]

    cam_ent = (
        (camera_entity or "").strip()
        or coordinator.active_carousel_camera
        or coordinator.camera_entity
        or (cams[0] if cams else "")
    )
    if cam_ent:
        coordinator.active_carousel_camera = cam_ent

    target_info = resolve_doorbell_talkback_target(
        hass, cam_ent, coordinator.volume_overrides
    )
    local_spk = coordinator.local_speaker

    # 1. Door / Gate Unlock (Acts ONLY on an explicitly configured lock entity)
    if act == "unlock_door":
        lock_ent = target_info.get("lock_entity") or coordinator.lock_entity
        if lock_ent and hass.states.get(lock_ent) is not None:
            await hass.services.async_call(
                "lock", "unlock", {ATTR_ENTITY_ID: lock_ent}, blocking=True
            )
        return target_info

    # 2. Area-to-Area Device Call
    if act == "call_target":
        target_str = (message or "").strip()
        # Area-to-Area Call to another Latter display (or 'all' displays)
        domain_data = hass.data.get(DOMAIN, {})
        all_coords = [v for v in domain_data.values() if hasattr(v, "device_slug")]
        caller_title = coordinator.device_slug.replace("_", " ").title()
        # Check if calling device has an onboard P4 camera entity to include in the video call popup!
        caller_cam = (
            f"camera.{coordinator.device_slug}"
            if hass.states.get(f"camera.{coordinator.device_slug}") is not None
            else (coordinator.camera_entity or "")
        )
        for c in all_coords:
            if c.device_slug == coordinator.device_slug:
                continue
            if target_str in ("all", "", c.device_slug):
                await hass.services.async_call(
                    DOMAIN,
                    "notify",
                    {
                        "target_device": c.device_slug,
                        "title": f"Intercom: {caller_title}",
                        "message": "Tap Answer for 2-Way Call",
                        "priority": "critical",
                        "duration": 20,
                        "chime": True,
                        **({"camera_entity": caller_cam} if caller_cam else {}),
                    },
                    blocking=False,
                )
        coordinator.doorbell_talk_state = "listening"
        coordinator.async_notify_listeners()
        return target_info

    if act == "select_camera":
        coordinator.async_notify_listeners()
        return target_info

    if act == "set_anc_mode":
        if coordinator.doorbell_talk_state == "listening" and local_spk and cam_ent:
            act = "listen_start"
        else:
            coordinator.async_notify_listeners()
            return target_info

    if act == "listen_toggle":
        act = (
            "listen_stop"
            if coordinator.doorbell_talk_state == "listening"
            else "listen_start"
        )

    if act == "listen_stop":
        coordinator.doorbell_talk_state = "idle"
        coordinator.async_notify_listeners()
        if local_spk:
            try:
                await hass.services.async_call(
                    "media_player",
                    "media_stop",
                    {ATTR_ENTITY_ID: local_spk},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                pass
        return target_info

    if act == "listen_start":
        if not local_spk or not cam_ent:
            return target_info
        coordinator.doorbell_talk_state = "listening"
        coordinator.async_notify_listeners()
        base_url = coordinator.get_lan_base_url()
        sig = coordinator.sign_resource(f"camera_audio:{cam_ent}", ttl_s=3600)
        stream_url = (
            f"{base_url}/api/latter/camera_audio/{coordinator.device_slug}"
            f"?entity_id={cam_ent}&anc={coordinator.doorbell_anc_mode}&fmt=flac"
            f"&v={int(time.time())}&sig={sig}"
        )
        try:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: local_spk,
                    "media_content_id": stream_url,
                    "media_content_type": "music",
                    "announce": True,
                },
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed starting camera audio listen on %s: %s", local_spk, err)
        return target_info

    if act in ("talk_message", "quick_reply", "talk"):
        spoken_text = (message or "").strip()
        if not spoken_text:
            spoken_text = "Please leave the package at the door, thank you."

        was_listening = coordinator.doorbell_talk_state == "listening"
        coordinator.doorbell_talk_state = "talking"
        dsp.record_talkback_activity()
        coordinator.async_notify_listeners()

        if local_spk and was_listening:
            try:
                await hass.services.async_call(
                    "media_player",
                    "media_stop",
                    {ATTR_ENTITY_ID: local_spk},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                pass

        talkback_mp = target_info["talkback_media_player"]
        if talkback_mp:
            mp_st = hass.states.get(talkback_mp)
            if mp_st is not None:
                cur_vol = mp_st.attributes.get("volume_level")
                if cur_vol is not None and float(cur_vol) < 0.25:
                    try:
                        await hass.services.async_call(
                            "media_player",
                            "volume_set",
                            {ATTR_ENTITY_ID: talkback_mp, "volume_level": 0.80},
                            blocking=True,
                        )
                    except Exception:  # noqa: BLE001
                        pass

            stabilized_msg = (
                f"... {spoken_text}" if target_info["is_unifi"] else spoken_text
            )
            tts_states = hass.states.async_all("tts")
            tts_ent = tts_states[0].entity_id if tts_states else ""

            try:
                await async_announce_on_targets(
                    hass,
                    speakers=[talkback_mp],
                    message=stabilized_msg,
                    tts_entity=tts_ent,
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Doorbell TTS announce to %s failed: %s", talkback_mp, err)

        est_duration = max(2.2, min(8.0, len(spoken_text) * 0.085 + 1.2))
        dsp.record_talkback_activity()

        async def _post_talkback_restore() -> None:
            await asyncio.sleep(est_duration)
            dsp.record_talkback_activity()
            if was_listening:
                await async_execute_doorbell_intercom(
                    hass, coordinator, action="listen_start", camera_entity=cam_ent
                )
            else:
                coordinator.doorbell_talk_state = "idle"
                coordinator.async_notify_listeners()

        coordinator.entry.async_create_background_task(
            hass,
            _post_talkback_restore(),
            f"latter_doorbell_talkback_{coordinator.device_slug}",
        )
        return target_info

    return target_info


def resolve_doorbell_ring_entities(
    hass: HomeAssistant, camera_entities: list[str]
) -> dict[str, str]:
    """Discover sibling doorbell ring / visitor binary_sensor or event entities for configured cameras.

    Returns a mapping of `ring_entity_id -> camera_entity_id`.
    """
    if not camera_entities:
        return {}

    ent_reg = er.async_get(hass)
    ring_to_cam: dict[str, str] = {}

    ring_keywords = (
        "doorbell",
        "visitor",
        "ring",
        "ding",
        "chime_button",
        "button_press",
    )
    exclude_keywords = (
        "motion",
        "person",
        "package",
        "vehicle",
        "animal",
        "pet",
        "light",
        "dark",
        "battery",
        "tamper",
        "wifi",
        "signal",
        "volume",
        "status",
        "chime_duration",
        "chime_type",
    )

    for cam_ent in camera_entities:
        if not cam_ent or not cam_ent.startswith("camera."):
            continue
        cam_entry = ent_reg.async_get(cam_ent)
        cam_dev_id = cam_entry.device_id if cam_entry else None
        cam_slug = cam_ent.split(".", 1)[-1].lower()
        for suffix in (
            "_high_resolution_channel",
            "_medium_resolution_channel",
            "_low_resolution_channel",
            "_package_camera",
            "_camera",
            "_live",
        ):
            if cam_slug.endswith(suffix):
                cam_slug = cam_slug[: -len(suffix)]
                break

        event_matches: list[str] = []
        binary_matches: list[str] = []

        from .ble_engine import _iter_entities

        for reg_ent in _iter_entities(ent_reg):
            if reg_ent.disabled_by is not None:
                continue
            domain = reg_ent.domain
            if domain not in ("binary_sensor", "event"):
                continue

            same_device = bool(cam_dev_id and reg_ent.device_id == cam_dev_id)
            eid_low = reg_ent.entity_id.lower()
            slug_match = bool(cam_slug and len(cam_slug) >= 4 and cam_slug in eid_low)
            if not same_device and not slug_match:
                continue

            meta_low = " ".join(
                filter(
                    None,
                    [
                        eid_low,
                        str(reg_ent.translation_key or "").lower(),
                        str(reg_ent.original_device_class or "").lower(),
                        str(reg_ent.device_class or "").lower(),
                        str(reg_ent.original_name or "").lower(),
                    ],
                )
            )
            if any(k in meta_low for k in ring_keywords) and not any(
                ex in eid_low for ex in exclude_keywords
            ):
                if domain == "event":
                    event_matches.append(reg_ent.entity_id)
                else:
                    binary_matches.append(reg_ent.entity_id)

        # Prefer HA 2026.11+ event.* doorbell entities over deprecated binary_sensor.* doorbell entities
        chosen_entities = event_matches if event_matches else binary_matches
        for ent_id in chosen_entities:
            ring_to_cam[ent_id] = cam_ent

    return ring_to_cam
