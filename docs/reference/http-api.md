# HTTP API Reference

Latter registers **8 `HomeAssistantView` endpoints** under `/api/latter/` ([`http/`](../../custom_components/latter/http/), [`doorbell.py`](../../custom_components/latter/doorbell.py), [`wallpapers/`](../../custom_components/latter/wallpapers/)).

Device media/audio endpoints exist so an ESP32 can fetch baseline JPEGs and FLAC streams over LAN HTTP without carrying a Home Assistant bearer token; Studio multipart wallpaper uploads use Home Assistant's authenticated administrator session.

---

## URL Signing & LAN Resolution

Latter stores a 256-bit HMAC secret in `.storage/latter.site` (rotatable anytime via **Rotate Signing Key** in Studio). Unauthenticated resource URLs carry `sig=<expiry>.<128-bit HMAC-SHA256>`, binding the target scope (`<subentry_id>` or `system`), resource type, server-chosen dimensions/filters, and expiry timestamp, verified in constant time:

| Endpoint / Resource | Auth / Expiry Mode | Lifetime | Signed Canonical Resource / Check |
| :--- | :--- | :--- | :--- |
| **Artwork** | Day-bucketed HMAC | 48 h (2–3 days to UTC midnight) | `artwork\|<w>\|<h>\|<shape>` |
| **Wallpaper** (device & Studio preview) | Day-bucketed HMAC | 48 h (2–3 days to UTC midnight) | `wallpaper:<src>\|<w>\|<h>\|<shape>` |
| **Camera snapshot** (device & Studio preview) | Day-bucketed HMAC | 48 h (2–3 days to UTC midnight) | `camera:<entity_id>\|<w>\|<h>\|<shape>` |
| **Calendar event map** | Day-bucketed HMAC | 48 h (2–3 days to UTC midnight) | `map:<q>\|<w>\|<h>\|<shape>` |
| **Doorbell camera audio** | Exact-expiry HMAC | 10 minutes | `camera_audio:<entity_id>\|<nr>\|<fmt>` |
| **Studio wallpaper upload** | HA Admin `Bearer` | Current admin session | `requires_auth = True` + `hass_user.is_admin` |
| **Brand icon** | Static public asset | — | Integration icon PNG (`GET /api/latter/brand/icon.png`) |

Day-bucketed signatures stay identical throughout a UTC day so Protocol v3 content hashes remain stable and devices avoid redundant image downloads. LAN IPv4 addresses are resolved asynchronously via `homeassistant.components.network.async_get_source_ip` (zero blocking sockets on the event loop) so ESP32 clients never hit `.local` mDNS names.

---

## Baseline JPEG Transcoding

Every image endpoint decodes and re-encodes on an executor thread as a **baseline (non-progressive) 4:2:0 JPEG** cropped to the panel's dimensions (`<= 480×480` for artwork, `<= 720×720` via `WALLPAPER_MAX_DIM` for wallpapers), applying a circular mask over black when `shape=circle`:

| Source | Resampling | JPEG Quality | Notes |
| :--- | :--- | :--- | :--- |
| **Artwork & Wallpapers** | Lanczos | `85`, optimized | External art fetches cap at 8 MB and reject private/loopback/link-local IPs; wallpapers dim to 78% brightness for text contrast |
| **Live Camera** | Bilinear | `72` (`> 300k` px) / `80` | Backed by `_LiveCameraFeeds` predictive prefetcher (`0.2 s` min gap, `2.0 s` max age, up to 8 active feeds, `Cache-Control: private, no-store`) |
| **Calendar Map** | Direct tile stitch | `86` | 3×3 OpenStreetMap tile grid + Nominatim geocoding pin (home coordinates are never plotted) |

---

## Endpoints

### 1. `GET /api/latter/artwork/{target_device}`
Serves active speaker album art (`entity_picture_local` → `entity_picture` → `media_image_url`, retaining the last valid frame across transient gaps).
- **Query params:** `sig` (**required**), optional `m` / `v` cache buster, `w`, `h`, `shape`.

### 2. `GET /api/latter/wallpaper/{target_device}`
Serves a wallpaper for a Device subentry or `"system"` preview.
- **Query params:** `sig` (**required**), `src` (`preset:<name>` across the **6 bundled photographic presets**—`forest_mountains`, `wheat_field`, `ocean_waves`, `sahara_dunes`, `andromeda_galaxy`, `mars_crater`—or `upload:<file>` from `.storage/latter/wallpapers/`), optional `w`, `h`, `shape`.

### 3. `POST /api/latter/wallpaper/upload`
Accepts a `multipart/form-data` photo upload up to **15 MB** from Latter Studio (`XMLHttpRequest` with `Authorization: Bearer <token>`), center-crops and stores a `960×960` master JPEG in `.storage/latter/wallpapers/` without hitting Home Assistant's 4 MB WebSocket frame limit, and returns the updated wallpaper catalog.

### 4. `GET /api/latter/camera/{target_device}`
Serves a baseline-JPEG snapshot from a configured camera.
- **Query params:** `sig` (**required**, binding `entity_id`, `w`, `h`, `shape`), `entity_id`, `w`, `h`, `shape`, optional `rot` (`0` \| `90` \| `180` \| `270`).

### 5. `GET /api/latter/camera_audio/{target_device}` *(experimental)*
Streams a camera's RTSP audio through `ffmpeg` (`-t 120`, `-rw_timeout 5000000`) at the device manifest's sample rate and channel count (48 kHz mono FLAC on current boards), minted on demand by `doorbell.py` and dispatched to `media_player.play_media` (at most 2 concurrent streams system-wide; `429` when full).
- **Query params:** `sig` (**required**, binding `entity_id`, `nr`, `fmt`), `entity_id`, `nr` (`strong` \| `light` \| `off`), `fmt` (`flac` \| `wav`).

### 6. `GET /api/latter/map/{target_device}`
Renders a 3×3 OpenStreetMap event map (`sig` **required**, `q` address/`lat,lon`/zone, `z` `10–18` default `15`, `pan_x` & `pan_y` clamped to `±4` tiles).

### 7. `GET /api/latter/brand/icon.png` & Studio Static Mount
Serves the integration brand icon, alongside the content-hashed admin `panel_custom` bundle mounted at `/latter_ui_<version>` (`latter-studio.js` and `latter-icons.js`). Aside from `POST /api/latter/wallpaper/upload`, Studio communicates exclusively over admin-gated WebSocket commands (`latter/system/*` and `latter/device/*`, version-locked via `STUDIO_REV`).
