# HTTP API Reference

Latter registers **7 local-only `HomeAssistantView` endpoints** under `/api/latter/` ([`http/`](../../custom_components/latter/http/), [`cameras/`](../../custom_components/latter/cameras/), [`wallpapers/`](../../custom_components/latter/wallpapers/)).

Device media, MJPEG stream, and audio endpoints allow an ESP32 on the local LAN to fetch baseline JPEGs, live MJPEG frames, and camera audio streams without carrying a long-lived Home Assistant bearer token; Studio multipart photo uploads use Home Assistant's authenticated administrator session. Every endpoint operates **100% locally on your LAN (Zero-WAN)** with private/loopback/link-local client IP enforcement.

---

## URL Signing & LAN Resolution

Latter stores a 256-bit HMAC secret in `.storage/latter.site` (rotatable anytime via **Rotate signing key** in Studio). Unauthenticated `GET` resource URLs carry `sig=<expiry>.<128-bit HMAC-SHA256>`, binding the target scope (`<subentry_id>` or `system`), resource type, server-chosen dimensions/crop/allowlist hash, and expiry timestamp, verified in constant time:

| Endpoint / Resource | Auth / Expiry Mode | Lifetime | Signed Canonical Resource / Check |
| :--- | :--- | :--- | :--- |
| **Artwork** | Day-bucketed HMAC | 48 h (2–3 days to UTC midnight) | `artwork\|<w>\|<h>\|<shape>` |
| **Wallpaper / Photo frame** (device & Studio preview) | Day-bucketed HMAC | 48 h (2–3 days to UTC midnight) | `wallpaper:<src>\|<w>\|<h>\|<shape>\|<crop_hash>` |
| **Camera snapshot** (device & Studio preview) | Day-bucketed / `600 s` Studio HMAC | 48 h device / 10 min Studio | `camera:<entity_id>\|<w>\|<h>\|<shape>` |
| **Camera live MJPEG stream** (single) | Day-bucketed HMAC | 48 h | `camera_stream:<entity_id>\|<w>\|<h>\|<fit>` |
| **Camera live MJPEG grid** (2×2) | Day-bucketed HMAC | 48 h | `camera_grid:<allowlist_hash>\|<w>\|<h>` |
| **Doorbell camera audio** | Exact-expiry HMAC | 10 minutes | `camera_audio:<entity_id>\|<nr>\|<fmt>` |
| **Studio photo upload** | HA Admin `Bearer` | Current admin session | `requires_auth = True` + `hass_user.is_admin` |

Day-bucketed signatures stay identical throughout a UTC day so Protocol v3 content hashes remain stable and devices avoid redundant image downloads. LAN IPv4 addresses are resolved asynchronously via `homeassistant.components.network.async_get_source_ip` (zero blocking sockets on the event loop) so ESP32 clients never hit `.local` mDNS names.

---

## Local Baseline JPEG & MJPEG Transcoding

Every image endpoint decodes and re-encodes on an executor thread (or shared `CameraStreamHub`) as a **baseline (non-progressive) 4:2:0 JPEG** sized to the panel's dimensions (`<= 480×480` for artwork, `<= 720×720` for wallpapers/cameras, `16 px`-aligned on ESP32-P4 hardware JPEG decode), applying a circular mask over black when `shape=circle`:

| Source | Resampling | JPEG Quality | Notes |
| :--- | :--- | :--- | :--- |
| **Artwork & Wallpapers** | Lanczos | `85`, optimized | Artwork fetches strictly through Home Assistant's native `media_player.async_get_media_image` / local `entity_picture` (`<= 8 MB`, zero outbound WAN redirects); wallpapers dim to 78% brightness for text contrast |
| **Camera Snapshot & Live MJPEG** | Bilinear / `ffmpeg` | `72` (`> 300k` px) / `80` | Backed by `CameraStreamHub` shared single-ingest fan-out (`multipart/x-mixed-replace` MJPEG with `Content-Length` framing and `Cache-Control: private, no-store`) |

---

## Endpoints

### 1. `GET /api/latter/artwork/{target_device}`
Serves active speaker album art locally via Home Assistant's `media_player` image interface (retaining the last valid frame across transient track-change gaps).
- **Query params:** `sig` (**required**), optional `m` / `v` cache buster, `w`, `h`, `shape`.

### 2. `GET /api/latter/wallpaper/{target_device}`
Serves a wallpaper or *Photo frame* screensaver image for a Device subentry or `"system"` preview.
- **Query params:** `sig` (**required**), `src` (`preset:<name>` across the **6 bundled `720p` presets**—`forest_mountains`, `wheat_field`, `ocean_waves`, `sahara_dunes`, `andromeda_galaxy`, `mars_crater`—or `upload:<file>` from `.storage/latter/wallpapers/`), optional `w`, `h`, `shape`, `mode` (`wallpaper` \| `screensaver` \| `preview`).

### 3. `POST /api/latter/wallpaper/upload`
Accepts a `multipart/form-data` photo upload up to **15 MB** from Latter Studio (`XMLHttpRequest` with `Authorization: Bearer <token>`), validates image dimensions, stores the master photo + normalized `(crop_x, crop_y, crop_zoom)` metadata and collection membership in `.storage/latter/wallpapers/` without hitting Home Assistant's 4 MB WebSocket frame limit, and returns the updated photo catalog.

### 4. `GET /api/latter/camera/{target_device}`
Serves a baseline-JPEG snapshot from a configured camera (or a `600 s` signed Studio preview on `target_device="system"`).
- **Query params:** `sig` (**required**, binding `entity_id`, `w`, `h`, `shape`), `entity_id`, `w`, `h`, `shape`, optional `rot` (`0` \| `90` \| `180` \| `270`).

### 5. `GET /api/latter/camera_stream/{target_device}`
Streams live baseline-JPEG frames (`multipart/x-mixed-replace`) for a single configured camera via `CameraStreamHub`.
- **Query params:** `sig` (**required**), `entity_id`, `w`, `h`, `fit` (`contain` \| `cover`), `fps`, optional `rot`.

### 6. `GET /api/latter/camera_grid/{target_device}`
Streams a server-composited `2×2` baseline-JPEG quad view (`multipart/x-mixed-replace`) across up to 4 configured cameras for the on-device **Cameras → Grid** tab.
- **Query params:** `sig` (**required**, binding the Device's camera allowlist hash, `w`, and `h`), `cams` (comma-separated `camera.*` entities, validated against the allowlist), `w`, `h`, `fps`.

### 7. `GET /api/latter/camera_audio/{target_device}` *(experimental)*
Streams a camera's RTSP/HTTP audio through `ffmpeg` (`-protocol_whitelist`, `-t 120`, `-rw_timeout 5000000`) at the device manifest's sample rate (`48 kHz` mono FLAC/WAV on current boards), minted on demand by `doorbell.py` and dispatched to `media_player.play_media` (at most 2 concurrent streams system-wide; `429` when full).
- **Query params:** `sig` (**required**, binding `entity_id`, `nr`, `fmt`), `entity_id`, `nr` (`strong` \| `light` \| `off`), `fmt` (`flac` \| `wav`).

### Studio Static Mount
Latter Studio serves its content-hashed admin `panel_custom` bundle (`latter-studio.js` + lazy `latter-studio-mdi.js` + precompressed `.gz` siblings) from a versioned static mount (`/latter_ui_<ver>`). Aside from `POST /api/latter/wallpaper/upload`, Studio communicates exclusively over admin-gated WebSocket commands (`latter/system/*` and `latter/device/*`, version-locked via `STUDIO_REV = 48`). Integration brand icons live in `custom_components/latter/brand/` and are served natively by Home Assistant.
