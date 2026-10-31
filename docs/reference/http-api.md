# HTTP API Reference

Latter registers its HTTP endpoints under `/api/latter/`. Source: [`http.py`](../../custom_components/latter/http.py), [`dashboard.py`](../../custom_components/latter/dashboard.py).

These endpoints exist so an ESP32 can fetch images without Home Assistant's bearer token. Each request is authorized by a signature in the URL instead.

## URL signing

Latter keeps a 256-bit secret in `.storage/latter.site`. Image URLs carry a `sig` parameter of the form `<expiry>.<HMAC-SHA256>`. The signature covers the config entry, the resource (for example `camera:camera.front_door`), and the expiry time. Signatures are compared in constant time.

| Resource | Lifetime |
| :--- | :--- |
| Artwork, wallpaper, camera snapshot, map | 7 days |
| Camera audio | 1 hour |
| Doorbell talkback | 5 minutes |

You shouldn't build these URLs yourself. Latter publishes them, already signed, in sensor attributes (`art_url`, `wallpaper_url`, `camera_snapshot_url`, `alert_camera_url`, and the calendar `map_url`).

URLs use Home Assistant's numeric LAN IPv4 address, not a `.local` name. Latter finds the address by opening a UDP socket and caches it until Home Assistant's core config changes. If you set an external base URL in Studio, it's used instead.

## Image output

Every image endpoint returns a **baseline (non-progressive) JPEG with 4:2:0 chroma subsampling**, center-cropped to the requested size. When `shape=circle` is set, a circular mask is applied over black. Decoding and encoding run in an executor thread, so they never block Home Assistant's event loop.

| Source | Resampling | JPEG quality |
| :--- | :--- | :--- |
| Artwork, wallpaper | Lanczos | 85, optimized |
| Live camera | Bilinear | 72 above 300k pixels, otherwise 80 |
| Map | — | 86 |

The device converts the JPEG to RGB565 itself, using ESPHome's `online_image`.

---

## Endpoints

### `GET /api/latter/artwork/{slug}`
Album art for the device's active speaker. Latter tries `entity_picture_local`, then `entity_picture`, then `media_image_url`, and keeps the last good image when none of them work.

| Param | Notes |
| :--- | :--- |
| `w`, `h` | 32–1200 |
| `shape` or `mask` | `circle` for round displays |
| `v` | Cache buster |

### `GET /api/latter/wallpaper/{slug}`

| Param | Notes |
| :--- | :--- |
| `src` | `preset:<name>` for one of the 5 generated presets, or a path under `/local/` or `/config/www/`. Paths that escape those directories are rejected. |
| `w`, `h`, `shape` | |

Photos are darkened to 78% brightness so text stays readable on top of them.

### `GET /api/latter/camera/{slug}`
A snapshot from a camera configured for this device. Cameras that aren't configured return `403`.

| Param | Notes |
| :--- | :--- |
| `entity_id` | `camera.*` |
| `w`, `h`, `shape` | |
| `rot` | `90`, `180`, or `270` |

Responses are cached for 200 ms and sent with `Cache-Control: no-store`.

### `GET /api/latter/map/{slug}`
A map of a calendar event's location, stitched from a 3×3 grid of OpenStreetMap tiles, with pins for the event and for home.

| Param | Notes |
| :--- | :--- |
| `q` | An address, `lat,lon`, or a zone name. Addresses are geocoded with Nominatim. |
| `z` | Zoom level, 10–18. Default 15. |
| `pan_x`, `pan_y` | ±30 steps |
| `w`, `h` | 128–768 |
| `shape` | |

### `GET /api/latter/camera_audio/{slug}` *(experimental)*
Streams camera audio through `ffmpeg` with a noise-reduction filter chain, as 16 kHz mono.

| Param | Notes |
| :--- | :--- |
| `entity_id` | |
| `anc` | Noise-reduction preset |
| `fmt` | `flac` (default) or `wav` |

At most 2 streams can run at once. Further requests get `429`.

### `GET` / `POST /api/latter/doorbell_talkback/{slug}` *(experimental)*
- `POST` accepts PCM16 or WAV, processes it, and plays it on the doorbell's speaker.
- `GET` returns the last processed clip.

### Studio endpoints
These serve the Studio panel. They're documented here for completeness, not as a stable API.

| Route | Purpose |
| :--- | :--- |
| `GET /api/latter/studio` | Entry point for the sidebar panel |
| `GET /api/latter/companion/{entry_id}` | Studio page |
| `GET` / `POST /api/latter/companion/{entry_id}/api` | Studio state and commands |
| `GET /api/latter/brand/icon.png`, `/api/latter/brand/sidebar_icon.js` | Branding assets |
