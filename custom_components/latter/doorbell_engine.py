"""Universal Doorbell Two-Way Audio (UniFi, go2rtc, ONVIF, SIP), 90° Landscape Proxy & 4-Stage ANC+AEC DSP Engine."""

from __future__ import annotations

from array import array
import asyncio
from collections import deque
from http import HTTPStatus
import io
import logging
import math
import shutil
import time
from typing import Any
import wave

from aiohttp import ClientTimeout, web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .ble_engine import _iter_entities
from .const import (
    API_CAMERA_AUDIO_STREAM_PATH,
    API_CAMERA_PROXY_PATH,
    API_DOORBELL_TALKBACK_PATH,
    DOMAIN,
    normalize_device_slug,
)
from .http import LatterCameraSnapshotView
from .area_engine import resolve_entity_area_id
from .sip_engine import get_sip_engine

_LOGGER = logging.getLogger(__name__)

UNIFI_PREROLL_MS: int = 250
TALKBACK_ECHO_GUARD_SECONDS: float = 0.75
_FFMPEG_STREAM_SEMAPHORE = asyncio.Semaphore(2)


def resolve_doorbell_talkback_target(
    hass: HomeAssistant,
    camera_entity_id: str | None,
    volume_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Auto-discover the talkback media_player (UniFi Protect), ONVIF/go2rtc stream, and area lock for a camera."""
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
    if area_id and not info["lock_entity"]:
        for lock_st in hass.states.async_all("lock"):
            if lock_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                if resolve_entity_area_id(hass, lock_st.entity_id) == area_id:
                    info["lock_entity"] = lock_st.entity_id
                    break

    return info


class LatterRotatableCameraSnapshotView(LatterCameraSnapshotView):
    """Extends LatterCameraSnapshotView with server-side 90° Landscape Widescreen rotation (&rot=90)."""

    url = API_CAMERA_PROXY_PATH
    name = "api:latter:camera_snapshot"

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Serve camera snapshot, delegating to LatterCameraSnapshotView (which supports &rot=90/180/270)."""
        return await super().get(request, target_device)


class LatterAudioDspPipeline:
    """4-Stage Leading-Class Audio DSP Pipeline (Biquad Wind Filter + Wiener ANC + NLMS AEC + Soft-Knee AGC)."""

    def __init__(self) -> None:
        """Initialize the adaptive NLMS echo reference ring buffer and DSP state."""
        self._ref_ring: deque[int] = deque(maxlen=16000)
        self._last_talkback_mono: float = 0.0

    def record_talkback_activity(self, pcm_samples: array[int] | None = None) -> None:
        """Record outbound talkback samples and timestamp for the NLMS echo canceller & guard."""
        self._last_talkback_mono = time.monotonic()
        if pcm_samples:
            self._ref_ring.extend(pcm_samples[-8000:])

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

    @staticmethod
    def biquad_highpass_120hz(samples: array[int], sample_rate: int = 16000) -> array[int]:
        """Stage 1: 2nd-order Butterworth High-Pass Filter (fc=120Hz, Q=0.7071) removing wind & street rumble."""
        if not samples:
            return samples
        fc = 120.0
        w0 = 2.0 * math.pi * fc / max(8000.0, float(sample_rate))
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * 0.70710678)

        b0 = (1.0 + cos_w0) * 0.5
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) * 0.5
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

        b0 /= a0
        b1 /= a0
        b2 /= a0
        a1 /= a0
        a2 /= a0

        out = array("h", [0] * len(samples))
        z1 = 0.0
        z2 = 0.0
        for i, x_int in enumerate(samples):
            x = float(x_int)
            y = b0 * x + z1
            z1 = b1 * x - a1 * y + z2
            z2 = b2 * x - a2 * y
            if y > 32767.0:
                y = 32767.0
            elif y < -32768.0:
                y = -32768.0
            out[i] = int(y)
        return out

    @staticmethod
    def wiener_spectral_denoise(
        samples: array[int], sample_rate: int = 16000, anc_mode: str = "ultra"
    ) -> array[int]:
        """Stage 2: Minimum-Statistics Envelope Wiener Noise Gate + Speech Formant Pre-Emphasis."""
        if not samples or anc_mode == "raw":
            return samples

        frame_len = max(64, int(sample_rate * 0.020))
        atten_floor = 0.14 if anc_mode == "ultra" else 0.28
        out = array("h", [0] * len(samples))

        min_rms = 99999.0
        n_total = len(samples)
        for start in range(0, n_total, frame_len):
            end = min(n_total, start + frame_len)
            if end - start < 16:
                break
            acc = 0.0
            for k in range(start, end):
                v = float(samples[k])
                acc += v * v
            rms = math.sqrt(acc / float(end - start))
            if rms > 8.0 and rms < min_rms:
                min_rms = rms
        noise_est = min(650.0, max(35.0, min_rms * 1.35)) if min_rms < 99999.0 else 140.0

        smooth_gain = 1.0
        prev_sample = 0.0
        for start in range(0, n_total, frame_len):
            end = min(n_total, start + frame_len)
            acc = 0.0
            for k in range(start, end):
                v = float(samples[k])
                acc += v * v
            frame_rms = math.sqrt(acc / float(max(1, end - start)))

            if frame_rms < noise_est:
                noise_est = 0.85 * noise_est + 0.15 * frame_rms
            else:
                noise_est = 0.995 * noise_est + 0.005 * frame_rms

            snr_prio = max(0.0, (frame_rms * frame_rms) - (noise_est * noise_est)) / (
                (noise_est * noise_est) + 1.0
            )
            target_gain = max(atten_floor, min(1.0, snr_prio / (1.0 + snr_prio)))

            for k in range(start, end):
                smooth_gain = 0.92 * smooth_gain + 0.08 * target_gain
                raw_x = float(samples[k])
                emph = raw_x - 0.18 * prev_sample
                prev_sample = raw_x
                val = emph * smooth_gain
                if val > 32767.0:
                    val = 32767.0
                elif val < -32768.0:
                    val = -32768.0
                out[k] = int(val)
        return out

    def nlms_echo_cancel(self, mic_samples: array[int]) -> array[int]:
        """Stage 3: Normalized Least Mean Squares (NLMS) Acoustic Echo Canceller."""
        if not mic_samples or not self._ref_ring:
            return mic_samples

        in_guard = self.is_in_echo_guard_window()
        ref_list = list(self._ref_ring)
        ref_len = len(ref_list)
        if ref_len < 32:
            return mic_samples

        taps = 32
        w = [0.0] * taps
        mu = 0.18
        eps = 1000.0
        duck_factor = 0.12 if in_guard else 0.85
        out = array("h", [0] * len(mic_samples))

        for i, d_int in enumerate(mic_samples):
            d = float(d_int)
            r_idx = i % (ref_len - taps)
            y_est = 0.0
            norm_x = eps
            for k in range(taps):
                rk = float(ref_list[r_idx + k])
                y_est += w[k] * rk
                norm_x += rk * rk
            err = (d - y_est) * duck_factor
            step = (mu * err) / norm_x
            for k in range(taps):
                w[k] += step * float(ref_list[r_idx + k])
            if err > 32767.0:
                err = 32767.0
            elif err < -32768.0:
                err = -32768.0
            out[i] = int(err)
        return out

    @staticmethod
    def soft_knee_agc_limiter(
        samples: array[int], target_rms: float = 7200.0, max_peak: float = 29500.0
    ) -> array[int]:
        """Stage 4: Lookahead Soft-Knee Dynamic Range Compressor & Brickwall Limiter."""
        if not samples:
            return samples
        acc = 0.0
        active_cnt = 0
        for s in samples:
            if abs(s) > 180:
                acc += float(s) * float(s)
                active_cnt += 1
        cur_rms = math.sqrt(acc / float(max(1, active_cnt))) if active_cnt > 32 else 1000.0
        makeup_gain = max(0.75, min(3.8, target_rms / max(250.0, cur_rms)))

        out = array("h", [0] * len(samples))
        env_gain = makeup_gain
        for i, s in enumerate(samples):
            val = float(s) * env_gain
            abs_v = abs(val)
            if abs_v > max_peak:
                desired = makeup_gain * (max_peak / abs_v)
                env_gain = 0.70 * env_gain + 0.30 * desired
                val = float(s) * env_gain
            else:
                env_gain = 0.995 * env_gain + 0.005 * makeup_gain

            if val > 28000.0:
                val = 28000.0 + 4700.0 * math.tanh((val - 28000.0) / 4700.0)
            elif val < -28000.0:
                val = -28000.0 - 4700.0 * math.tanh((-val - 28000.0) / 4700.0)
            out[i] = int(max(-32768.0, min(32767.0, val)))
        return out

    def process_pcm16_frames(
        self,
        pcm_samples: array[int],
        sample_rate: int = 16000,
        anc_mode: str = "ultra",
        prepend_unifi_preroll: bool = True,
        apply_aec: bool = False,
    ) -> array[int]:
        """Run the full 4-stage DSP pipeline and optionally prepend the 250ms UniFi talkback stabilizer."""
        stage1 = self.biquad_highpass_120hz(pcm_samples, sample_rate)
        stage2 = self.nlms_echo_cancel(stage1) if apply_aec else stage1
        stage3 = self.wiener_spectral_denoise(stage2, sample_rate, anc_mode)
        stage4 = self.soft_knee_agc_limiter(stage3)

        if prepend_unifi_preroll:
            preroll_samples = int(sample_rate * (UNIFI_PREROLL_MS / 1000.0))
            preroll = array("h", [0] * preroll_samples)
            return preroll + stage4
        return stage4

    def process_wav_bytes(
        self,
        raw_bytes: bytes,
        anc_mode: str = "ultra",
        prepend_unifi_preroll: bool = True,
    ) -> bytes:
        """Process a WAV or raw PCM16 buffer through the 4-stage DSP pipeline and return valid WAV bytes."""
        sample_rate = 16000
        pcm_samples = array("h")
        try:
            with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
                sample_rate = wf.getframerate() or 16000
                n_ch = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())
                if sampwidth == 2:
                    raw_arr = array("h")
                    raw_arr.frombytes(frames[: len(frames) - (len(frames) % 2)])
                    if n_ch == 2:
                        pcm_samples = array(
                            "h",
                            [
                                int((raw_arr[i] + raw_arr[i + 1]) // 2)
                                for i in range(0, len(raw_arr) - 1, 2)
                            ],
                        )
                    else:
                        pcm_samples = raw_arr
        except Exception:  # noqa: BLE001
            trimmed = raw_bytes[: len(raw_bytes) - (len(raw_bytes) % 2)]
            if trimmed:
                pcm_samples.frombytes(trimmed)

        if not pcm_samples:
            pcm_samples = array("h", [0] * 3200)

        processed = self.process_pcm16_frames(
            pcm_samples,
            sample_rate=sample_rate,
            anc_mode=anc_mode,
            prepend_unifi_preroll=prepend_unifi_preroll,
            apply_aec=False,
        )
        self.record_talkback_activity(processed)

        out_io = io.BytesIO()
        with wave.open(out_io, "wb") as wf_out:
            wf_out.setnchannels(1)
            wf_out.setsampwidth(2)
            wf_out.setframerate(sample_rate)
            wf_out.writeframes(processed.tobytes())
        return out_io.getvalue()


def get_dsp_pipeline(hass: HomeAssistant) -> LatterAudioDspPipeline:
    """Return the singleton LatterAudioDspPipeline instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "audio_dsp" not in domain_data:
        domain_data["audio_dsp"] = LatterAudioDspPipeline()
    return domain_data["audio_dsp"]


def _resolve_coordinator_by_slug(hass: HomeAssistant, target_slug: str) -> Any | None:
    """Find a loaded LatterCoordinator by device slug or entry_id."""
    domain_data = hass.data.get(DOMAIN, {})
    norm = normalize_device_slug(target_slug)
    for k, val in domain_data.items():
        if hasattr(val, "device_slug"):
            if k == target_slug or val.device_slug == norm:
                return val
    for val in domain_data.values():
        if hasattr(val, "device_slug"):
            return val
    return None


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
            token=request.query.get("token"),
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

        sip = get_sip_engine(self.hass)
        dsp = get_dsp_pipeline(self.hass)

        # If an active SIP call is in progress with RTP audio arriving and no RTSP camera stream is used,
        # drain and DSP-process the live SIP RTP ring buffer into a WAV stream for the ESPHome speaker!
        if sip.call_state == "in_call" and sip._inbound_pcm_ring and not stream_url:
            raw_pcm = array("h", list(sip._inbound_pcm_ring))
            sip._inbound_pcm_ring.clear()
            clean_pcm = await self.hass.async_add_executor_job(
                dsp.process_pcm16_frames, raw_pcm, 16000, anc_mode, False, True
            )
            out_io = io.BytesIO()
            with wave.open(out_io, "wb") as wf_out:
                wf_out.setnchannels(1)
                wf_out.setsampwidth(2)
                wf_out.setframerate(16000)
                wf_out.writeframes(clean_pcm.tobytes())
            return web.Response(body=out_io.getvalue(), content_type="audio/wav")

        ffmpeg_bin = shutil.which("ffmpeg")
        if not stream_url or not ffmpeg_bin:
            wav_bytes = dsp.process_wav_bytes(b"", anc_mode=anc_mode, prepend_unifi_preroll=True)
            return web.Response(body=wav_bytes, content_type="audio/wav")

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
            "16000",
            "-ac",
            "1",
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
                    except ProcessLookupError:
                        pass

            return resp


class LatterDoorbellTalkbackView(HomeAssistantView):
    """Serves and ingests DSP-processed, pre-roll-stabilized talkback audio for UniFi, go2rtc, ONVIF & SIP."""

    requires_auth = False
    url = API_DOORBELL_TALKBACK_PATH
    name = "api:latter:doorbell_talkback"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the doorbell talkback view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Serve the latest DSP-stabilized talkback WAV clip for media_player.<doorbell>_speaker."""
        norm = normalize_device_slug(target_device.removesuffix(".wav"))
        coord = _resolve_coordinator_by_slug(self.hass, norm)
        if coord is None or not coord.verify_resource(
            "talkback",
            sig=request.query.get("sig"),
            token=request.query.get("token"),
        ):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature")

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        clips: dict[str, bytes] = domain_data.setdefault("talkback_clips", {})
        wav_bytes = clips.get(norm)
        if not wav_bytes:
            dsp = get_dsp_pipeline(self.hass)
            wav_bytes = dsp.process_wav_bytes(b"", anc_mode="ultra", prepend_unifi_preroll=True)
        return web.Response(
            body=wav_bytes,
            content_type="audio/wav",
            headers={"Cache-Control": "no-store"},
        )

    async def post(self, request: web.Request, target_device: str) -> web.Response:
        """Ingest raw PCM16 or WAV talkback audio (requires valid Latter token or HA Bearer token)."""
        from .dashboard import verify_studio_panel_token

        token = request.query.get("token") or request.headers.get("X-Latter-Token")
        authed = verify_studio_panel_token(self.hass, token)
        if not authed:
            auth_hdr = request.headers.get("Authorization", "")
            if auth_hdr.startswith("Bearer "):
                bearer = auth_hdr.removeprefix("Bearer ").strip()
                rt = await self.hass.auth.async_validate_access_token(bearer)
                authed = rt is not None
        if not authed:
            return web.json_response(
                {"error": "Unauthorized"}, status=HTTPStatus.FORBIDDEN
            )

        coord = _resolve_coordinator_by_slug(self.hass, target_device)
        raw_bytes = await request.read()
        if not raw_bytes:
            return web.json_response(
                {"error": "Empty audio payload"}, status=HTTPStatus.BAD_REQUEST
            )

        anc_mode = (
            request.query.get("anc")
            or (coord.doorbell_anc_mode if coord else "ultra")
            or "ultra"
        )
        cam_ent = (
            request.query.get("camera_entity")
            or (coord.active_carousel_camera if coord else "")
            or (coord.camera_entity if coord else "")
        )

        dsp = get_dsp_pipeline(self.hass)
        wav_bytes = await self.hass.async_add_executor_job(
            dsp.process_wav_bytes, raw_bytes, anc_mode, True
        )

        norm = normalize_device_slug(target_device.removesuffix(".wav"))
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        clips: dict[str, bytes] = domain_data.setdefault("talkback_clips", {})
        clips[norm] = wav_bytes

        if coord is not None:
            await async_play_talkback_clip_to_doorbell(self.hass, coord, cam_ent, wav_bytes)

        return web.json_response({"status": "ok", "bytes": len(wav_bytes)})


async def async_play_talkback_clip_to_doorbell(
    hass: HomeAssistant,
    coordinator: Any,
    camera_entity_id: str | None = None,
    wav_bytes: bytes | None = None,
) -> bool:
    """Stream the stored DSP-stabilized talkback WAV clip to UniFi speaker, go2rtc, or SIP."""
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
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: talkback_mp,
                    "media_content_id": clip_url,
                    "media_content_type": "music",
                    "announce": True,
                },
                blocking=False,
            )
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Doorbell talkback play_media failed on %s: %s", talkback_mp, err)

    if cam_ent and wav_bytes:
        if await _async_push_go2rtc_or_onvif_backchannel(hass, cam_ent, wav_bytes):
            return True

    sip = get_sip_engine(hass)
    if sip.call_state == "in_call" and wav_bytes:
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                pcm_arr = array("h")
                pcm_arr.frombytes(frames[: len(frames) - (len(frames) % 2)])
                await sip.async_stream_pcm16_to_rtp(pcm_arr)
                return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("SIP RTP talkback stream error: %s", err)

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
    """Execute a unified two-way doorbell, SIP, or area-to-area intercom command."""
    act = (action or "listen_toggle").strip().lower()
    dsp = get_dsp_pipeline(hass)
    sip = get_sip_engine(hass)

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

    # 1. Door / Gate Unlock (Triggers paired HA lock.* entity AND sends SIP RFC 2833 DTMF tones!)
    if act in ("unlock_door", "dtmf_unlock", "send_dtmf"):
        lock_ent = target_info.get("lock_entity") or coordinator.lock_entity
        if lock_ent and hass.states.get(lock_ent) is not None:
            try:
                await hass.services.async_call(
                    "lock", "unlock", {ATTR_ENTITY_ID: lock_ent}, blocking=False
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Lock unlock failed on %s: %s", lock_ent, err)
        await sip.async_send_dtmf(message if message else None)
        return target_info

    # 2. Area-to-Area Device Call or Outbound SIP Speed-Dial Call
    if act == "call_target":
        target_str = (message or "").strip()
        if target_str.startswith("sip:") or "@" in target_str:
            sip.dial_sip_uri(target_str)
            coordinator.doorbell_talk_state = "listening"
            coordinator._notify_listeners()
            return target_info

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
                    "notify_device",
                    {
                        "device_slug": c.device_slug,
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
        coordinator._notify_listeners()
        return target_info

    if act == "select_camera":
        coordinator._notify_listeners()
        return target_info

    if act == "set_anc_mode":
        if coordinator.doorbell_talk_state == "listening" and local_spk and cam_ent:
            act = "listen_start"
        else:
            coordinator._notify_listeners()
            return target_info

    if act == "listen_toggle":
        act = (
            "listen_stop"
            if coordinator.doorbell_talk_state == "listening"
            else "listen_start"
        )

    if act == "listen_stop":
        if sip.call_state != "idle":
            sip.hangup_call()
        coordinator.doorbell_talk_state = "idle"
        coordinator._notify_listeners()
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
        if sip.call_state == "ringing":
            sip.answer_incoming_call()
        if not local_spk or not cam_ent:
            return target_info
        coordinator.doorbell_talk_state = "listening"
        coordinator._notify_listeners()
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
        coordinator._notify_listeners()

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

            if tts_ent and hass.services.has_service("tts", "speak"):
                try:
                    await hass.services.async_call(
                        "tts",
                        "speak",
                        {
                            ATTR_ENTITY_ID: tts_ent,
                            "media_player_entity_id": [talkback_mp],
                            "message": stabilized_msg,
                            "cache": False,
                        },
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("tts.speak to doorbell %s failed: %s", talkback_mp, err)
            elif hass.services.has_service("tts", "cloud_say"):
                try:
                    await hass.services.async_call(
                        "tts",
                        "cloud_say",
                        {
                            ATTR_ENTITY_ID: talkback_mp,
                            "message": stabilized_msg,
                        },
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("tts.cloud_say to doorbell %s failed: %s", talkback_mp, err)

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
                coordinator._notify_listeners()

        hass.async_create_task(_post_talkback_restore())
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

        for reg_ent in ent_reg.entities.values():
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
                ring_to_cam[reg_ent.entity_id] = cam_ent

    return ring_to_cam
