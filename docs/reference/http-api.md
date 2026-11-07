# HTTP API Reference

Latter registers its HTTP endpoints under `/api/latter/`. Source: [`http.py`](../../custom_components/latter/http.py), [`doorbell_engine.py`](../../custom_components/latter/doorbell_engine.py) (camera audio), [`url_signer.py`](../../custom_components/latter/url_signer.py) and [`resource_signing.py`](../../custom_components/latter/resource_signing.py) (signatures).

These endpoints exist so an ESP32 can fetch images without Home Assistant's bearer token. Each request is authorized by a signature in the URL instead.

## URL signing

Latter keeps a 256-bit secret in `.storage/latter.site`. URLs carry a `sig` parameter of the form `<expiry>.<HMAC-SHA256, truncated to 128 bits>`. The signature covers the Device (its config subentry), the resource including the server-chosen render parameters (for example `camera:camera.front_door|480|480|circle`), and the expiry time. Signatures are compared in constant time.

There are two expiry modes:

- **Day-bucketed**, for URLs embedded in Protocol v3 payloads and Studio previews. The expiry is the first UTC midnight after the lifetime has passed, so every URL signed during one UTC day is identical. Payload content hashes stay stable and devices (and the Studio page) can cache images. Lifetimes are whole days.
- **Exact**, for URLs minted on demand and never embedded in a payload. The URL expires exactly when its lifetime ends.

| Resource | Mode | Lifetime | Actually valid for |
| :--- | :--- | :--- | :--- |
| Artwork, wallpaper, camera snapshot, map | Day-bucketed | 7 days | 7 to 8 days |
| Studio camera preview, wallpaper thumbnail | Day-bucketed | 7 days | 7 to 8 days |
| Camera audio (doorbell listen stream) | Exact | 10 minutes | 10 minutes (a new URL is signed each time listening starts; the signature is checked when the stream opens) |

You shouldn't build these URLs yourself. Latter publishes the image URLs, already signed, in sensor attributes (`art_url`, `wallpaper_url`, `camera_snapshot_url`, `alert_camera_url`, and the calendar `map_url`).

URLs use Home Assistant's numeric LAN IPv4 address, not a `.local` name. Latter finds the address by opening a UDP socket and caches it until Home Assistant's core config changes.

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
| `src` | `preset:<name>` for one of the 5 generated presets, or `upload:<slug>/<file>` for an uploaded photo in Latter's private storage (`.storage/latter/wallpapers/`). Anything else is rejected. Without `src`, the device's current wallpaper is served. |
| `w`, `h`, `shape` | |

Photos are darkened to 78% brightness so text stays readable on top of them.

### `GET /api/latter/camera/{slug}`
A snapshot from a camera configured for this device. Cameras that aren't configured return `404`; a missing or invalid signature returns `403`.

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
Streams a camera's RTSP audio through `ffmpeg` with a noise-reduction filter chain. The sample rate and channel count come from the device's hardware manifest (`audio.out_rate`, `audio.out_ch`), so current Latter boards get 48 kHz mono. Latter firmware requests FLAC. If the camera has no stream source or `ffmpeg` isn't available, a short silent WAV is returned.

| Param | Notes |
| :--- | :--- |
| `entity_id` | A camera configured for this device. Others return `403`. |
| `nr` | Noise reduction: `strong` (speech band-limit, spectral denoise, presence EQ, compressor, limiter), `light` (wider band, milder denoise, compressor, limiter), or `off` (rumble high-pass and limiter only). Defaults to the Studio setting. |
| `fmt` | `flac` (default) or `wav` |

At most 2 streams can run at once. Further requests get `429`.

### Studio
Studio has no HTTP API of its own. It's a `panel_custom` web component at `/latter` (admin only), loaded from the static path `/latter_ui`. It talks to Home Assistant only through admin-gated WebSocket commands: `latter/system/*` (`get_state`, `subscribe`, `command`, `export`, `import`) and `latter/device/*` (`command`, `export`, `import`). These are internal, not a stable API.

Two unauthenticated branding assets are also served: `GET /api/latter/brand/icon.png` and `/api/latter/brand/sidebar_icon.js`.
