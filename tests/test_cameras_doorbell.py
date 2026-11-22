"""Tests for camera capability bitmasks, singleton lifecycle, Studio video caps, and HTTP streaming."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from homeassistant.components import camera as ha_camera
import pytest

from custom_components.latter.cameras.capabilities import (
    CAMERA_CAP_HAS_AUDIO,
    CAMERA_CAP_HAS_TALKBACK,
    CAMERA_CAP_IN_CAROUSEL,
    CAMERA_CAP_IS_DOORBELL,
    CAMERA_CAP_SHOW_REPLY,
    CAMERA_CAP_SHOW_UNLOCK,
    resolve_camera_capabilities,
)
from custom_components.latter.cameras.stream_hub import (
    async_shutdown_camera_stream_hub,
    get_camera_stream_hub,
)
from custom_components.latter.cameras.transcode import (
    format_mjpeg_chunk,
    inspect_jpeg_header,
)
from custom_components.latter.const import (
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    STUDIO_REV,
)
from custom_components.latter.http import camera_views as http_mod
from custom_components.latter.http.camera_views import (
    LatterCameraGridView,
    LatterCameraSnapshotView,
    LatterCameraStreamView,
)
from custom_components.latter.studio.device_commands import _cmd_save_device_config
from custom_components.latter.studio.payload import (
    StudioCommandError,
    build_studio_state_payload,
)
from custom_components.latter.studio.settings_cleaners import SettingsScopeError
from custom_components.latter.studio.system_commands import _cmd_save_system_config
from tests.helpers import (
    install_camera_mocks,
    make_jpeg_bytes,
    register_device,
    register_entity,
)


def _make_baseline_420_jpeg(width: int, height: int) -> bytes:
    """Build a valid Baseline 4:2:0 JPEG via Pillow with SOF0 stub fallback."""
    real_raw = make_jpeg_bytes(width, height, (36, 92, 148))
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


async def test_resolve_camera_capabilities_and_singleton_lifecycle(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`resolve_camera_capabilities` computes accurate bitmask + Studio metadata, and singleton shuts down cleanly."""
    doorbell_dev = register_device(
        hass,
        config_entry_id="unifi_entry",
        entry_domain="unifiprotect",
        identifiers={("unifiprotect", "doorbell_1")},
        name="Front Doorbell",
        manufacturer="Latter",
        area_id="entryway",
    )
    register_entity(
        hass,
        "camera.front_door",
        platform="unifiprotect",
        device_id=doorbell_dev.id,
        config_entry_id="unifi_entry",
    )
    register_entity(
        hass,
        "media_player.front_door_speaker",
        platform="unifiprotect",
        device_id=doorbell_dev.id,
        config_entry_id="unifi_entry",
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
    install_camera_mocks(
        monkeypatch, streams={"camera.front_door": "rtsp://10.0.0.5/door"}
    )

    caps_doorbell = resolve_camera_capabilities(
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
        | CAMERA_CAP_SHOW_REPLY
    )
    assert caps_doorbell["stream_kind"] == "rtsp"
    assert caps_doorbell["has_audio"] is True
    assert caps_doorbell["has_talkback"] is True
    assert caps_doorbell["show_listen"] is True
    assert caps_doorbell["show_talk"] is True
    assert caps_doorbell["show_reply"] is True
    assert caps_doorbell["unlock_entity"] == ""
    assert caps_doorbell["is_doorbell"] is True
    assert caps_doorbell["in_carousel"] is True
    assert caps_doorbell["door_speaker"] == "media_player.front_door_speaker"
    assert caps_doorbell["area_id"] == "entryway"

    # Non-doorbell RTSP camera defaults Listen/Talk/Reply/Unlock OFF even when hardware has audio/speaker
    caps_regular = resolve_camera_capabilities(hass, "camera.front_door")
    assert caps_regular["has_audio"] is True
    assert caps_regular["has_talkback"] is True
    assert caps_regular["show_listen"] is False
    assert caps_regular["show_talk"] is False
    assert caps_regular["show_reply"] is False
    assert caps_regular["unlock_entity"] == ""
    assert caps_regular["caps"] == 0

    # Explicit per-camera config overrides label, toggles, and explicit unlock_entity
    caps_custom = resolve_camera_capabilities(
        hass,
        "camera.front_door",
        camera_config={
            "label": "Driveway",
            "show_listen": True,
            "show_talk": False,
            "show_reply": True,
            "unlock_entity": "lock.front_door",
        },
    )
    assert caps_custom["name"] == "Driveway"
    assert caps_custom["label"] == "Driveway"
    assert caps_custom["unlock_entity"] == "lock.front_door"
    assert caps_custom["caps"] == (
        CAMERA_CAP_HAS_AUDIO | CAMERA_CAP_SHOW_REPLY | CAMERA_CAP_SHOW_UNLOCK
    )

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
        install_camera_mocks(
            monkeypatch,
            images={
                "camera.front_door": make_jpeg_bytes(640, 360),
                "camera.backyard": make_jpeg_bytes(640, 480),
            },
        )
        monkeypatch.setattr(ha_camera, "async_get_mjpeg_stream", None, raising=False)

        # Save valid per-Device camera_visible_entities & camera_carousel_entities via Studio command
        await _cmd_save_device_config(
            hass,
            coord,
            {
                "config": {
                    CONF_CAMERA_VISIBLE_ENTITIES: [
                        "camera.front_door",
                        "camera.backyard",
                    ],
                    CONF_CAMERA_CAROUSEL_ENTITIES: ["camera.front_door"],
                    "camera_default_view": "Single",
                    "camera_doorbell_popup": "Live Video",
                },
                "studio_rev": STUDIO_REV,
            },
            global_cfg,
            {},
        )
        assert coord.visible_camera_entities == [
            "camera.front_door",
            "camera.backyard",
        ]
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
        assert cat_cams["camera.front_door"]["has_audio"] is False
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
        assert len(wire) == 43
        # Non-doorbell cameras default Listen/Talk/Reply/Unlock OFF -> front_door has only in_carousel (8)
        assert "camera.front_door|Front Door||8|" in wire[21]
        assert "camera.backyard|Backyard||0|" in wire[21]
        assert "/api/latter/camera_stream/" in wire[39]
        assert wire[40] == "camera.front_door"

        # Save per-camera label, action toggles, and explicit unlock_entity via System settings
        await _cmd_save_system_config(
            hass,
            None,
            {
                "config": {
                    "camera_configs": {
                        "camera.front_door": {
                            "label": "Porch",
                            "show_listen": True,
                            "show_talk": False,
                            "show_reply": True,
                            "unlock_entity": "lock.front_door",
                        }
                    }
                }
            },
            global_cfg,
            {},
        )
        coord._cached_area_payload = None
        _st2, area_attrs2 = coord.get_area_context_payload()
        wire2 = area_attrs2["payload"].split("\x1f")
        # 1 (listen) | 8 (in_carousel) | 16 (reply) | 32 (unlock) = 57
        assert "camera.front_door|Porch||57|lock.front_door" in wire2[21]

        # Stream 1 chunk from LatterCameraStreamView & LatterCameraGridView
        stream_sig = parse_qs(urlsplit(wire[39]).query)["sig"][0]

        async def _one_chunk_single(*_a: Any, **_kw: Any) -> Any:
            yield format_mjpeg_chunk(_make_baseline_420_jpeg(464, 256))

        async def _one_chunk_grid(*_a: Any, **_kw: Any) -> Any:
            yield format_mjpeg_chunk(_make_baseline_420_jpeg(800, 480))

        hub = get_camera_stream_hub(hass)
        monkeypatch.setattr(hub, "async_iter_mjpeg_chunks", _one_chunk_single)
        monkeypatch.setattr(hub, "async_iter_grid_mjpeg_chunks", _one_chunk_grid)

        class _CapturingStreamResponse:
            def __init__(
                self, *, status: int = 200, headers: dict[str, str] | None = None
            ) -> None:
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
            SimpleNamespace(
                query={**snap_qs, "entity_id": "camera.backyard"}, headers={}
            ),
            coord.device_slug,
        )
        assert r_cam2.status == 200
        assert r_cam2.body.startswith(b"\xff\xd8")

        # Hide camera.backyard from device's visible_camera_entities -> allowlist sig rejects camera.backyard with 403
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
                urlsplit(
                    coord.get_area_context_payload()[1]["camera_snapshot_url"]
                ).query
            ).items()
        }
        r_hidden = await snap_view.get(
            SimpleNamespace(
                query={**new_snap_qs, "entity_id": "camera.backyard"}, headers={}
            ),
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
            k: v[0] for k, v in parse_qs(urlsplit(coord.alert_camera_url).query).items()
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
            "video": {
                "hw_jpeg": 0,
                "max_w": 464,
                "max_h": 464,
                "max_fps": 5,
                "grid_fps": 2,
            },
        }
        s3_payload = build_studio_state_payload(hass, coord, include_catalog=False)
        assert s3_payload["config"]["camera_doorbell_popup"] == "Snapshot"
        assert {d["subentry_id"]: d for d in s3_payload["system_devices"]}[
            coord.subentry_id
        ]["hw_jpeg"] is False
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
        assert await hass.config_entries.async_unload(entry.entry_id) is True
