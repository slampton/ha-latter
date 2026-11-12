# HTTP API Reference

Latter registers its HTTP endpoints under `/api/latter/`. Source: [`http.py`](../../custom_components/latter/http.py) (URL signing + all 7 `HomeAssistantView` classes), [`doorbell.py`](../../custom_components/latter/doorbell.py) (doorbell audio URL minting), and [`wallpapers.py`](../../custom_components/latter/wallpapers.py) (preset & uploaded wallpaper storage).

These endpoints exist so an ESP32 can fetch images and audio streams without Home Assistant's bearer token, and so Studio can stream multipart wallpaper uploads. Device media/image/audio requests are authorized by a scoped, expiring HMAC signature; Studio multipart uploads require an authenticated Home Assistant administrator session.

## URL signing

Latter keeps a 256-bit secret in `.storage/latter.site` (rotatable at any time via **Rotate Signing Key** in Studio). URLs carry a `sig` parameter of the form `<expiry>.<HMAC-SHA256, truncated to 128 bits>`. The signature covers the Device (its config subentry, or `system` for Studio system previews), the resource including the server-chosen render/filter parameters (for example `camera:camera.front_door|480|480|circle` or `camera_audio:camera.front_door|strong|flac`), and the expiry time. Signatures are compared in constant time (`http.py`).

There are two expiry modes:

- **Day-bucketed**, for URLs embedded in Protocol v3 payloads and Studio previews. The expiry is the first UTC midnight after the lifetime has passed, so every URL signed during one UTC day is identical. Payload content hashes stay stable and devices (and the Studio page) can cache images. Lifetimes are whole days.
- **Exact**, for URLs minted on demand and never embedded in a payload. The URL expires exactly when its lifetime ends.

| Resource | Mode | Lifetime | Actually valid for |
| :--- | :--- | :--- | :--- |
| Artwork, wallpaper, camera snapshot, map | Day-bucketed | 48 hours (2 days) | 2 to 3 days |
| Studio camera preview, wallpaper thumbnail | Day-bucketed | 48 hours (2 days) | 2 to 3 days |
| Camera audio (doorbell listen stream) | Exact | 10 minutes | 10 minutes (a new URL is signed each time listening starts; the signature is checked when the stream opens) |
| Studio multipart wallpaper upload | HA Admin Auth | Current session | Verified via Home Assistant `requires_auth = True` + `hass_user.is_admin` when `POST /api/latter/wallpaper/upload` receives the upload |

You shouldn't build these URLs yourself. Latter publishes the image URLs, already signed, in its Protocol v3 payloads (`art_url` in `active_media`; `wallpaper_url`, `camera_snapshot_url`, `cameras_summary`, `alert_camera_url`, and `doorbell_audio_url` in `area_context`) and in the `latter.calendar_fetch` response (`map_url`).

URLs use Home Assistant's numeric LAN IPv4 address, not a `.local` name. Latter resolves the LAN IPv4 address asynchronously on an executor thread (zero event-loop socket calls) and caches it until Home Assistant's core config changes.

## Image output

Every image endpoint returns a **baseline (non-progressive) JPEG with 4:2:0 chroma subsampling**, center-cropped to the device's panel resolution (from its hardware manifest). On round displays (`shape=circle` in the signed resource), a circular mask is applied over black. Decoding and encoding run in an executor thread, so they never block Home Assistant's event loop.

| Source | Resampling | JPEG quality |
| :--- | :--- | :--- |
| Artwork, wallpaper | Lanczos | 85, optimized |
| Live camera | Bilinear | 72 above 300k pixels, otherwise 80 |
| Map | — | 86 |

The device converts the JPEG to RGB565 itself, using ESPHome's `online_image`.

---

## Endpoints

### `GET /api/latter/artwork/{slug}`
Album art for the device's active speaker. Latter tries `entity_picture_local`, then `entity_picture`, then `media_image_url`, and keeps the last good image when none of them work. External upstream fetches stream-cap downloads at **8 MB** and reject URLs resolving to private, loopback, or link-local IP addresses.

| Param | Notes |
| :--- | :--- |
| `sig` | **Required.** Signed resource `artwork:<media_key>\|<w>\|<h>\|<shape>` |
| `v` | Optional cache buster |

### `GET /api/latter/wallpaper/{slug}`

| Param | Notes |
| :--- | :--- |
| `sig` | **Required.** Signed resource `wallpaper:<src>\|<w>\|<h>\|<shape>` |
| `src` | `preset:<name>` for one of the 5 generated presets, or `upload:<slug>/<file>` for an uploaded photo in Latter's private storage (`.storage/latter/wallpapers/`). Anything else is rejected. Without `src`, the device's current wallpaper is served. |

Photos are darkened to 78% brightness so text stays readable on top of them.

### `GET /api/latter/camera/{slug}`
A snapshot from a camera configured for this device. The camera `entity_id` and target dimensions are bound inside the signed resource (`camera:<entity_id>|<w>|<h>|<shape>`); a missing or invalid signature returns `403`, and an unconfigured camera returns `404`.

| Param | Notes |
| :--- | :--- |
| `sig` | **Required.** Signed resource `camera:<entity_id>\|<w>\|<h>\|<shape>` |

Responses are cached for 200 ms and sent with `Cache-Control: no-store`.

### `GET /api/latter/map/{slug}`
A map of a calendar event's location, stitched from a 3×3 grid of OpenStreetMap tiles, with a pin for the event location (Home Assistant's home coordinates are never plotted).

| Param | Notes |
| :--- | :--- |
| `sig` | **Required.** Signed resource `map:<q>\|<w>\|<h>\|<shape>` |
| `q` | An address, `lat,lon`, or a zone name. Addresses are geocoded with Nominatim. |
| `z` | Zoom level, 10–18. Default 15. |
| `pan_x`, `pan_y` | Clamped to `±4` tiles |

### `GET /api/latter/camera_audio/{slug}` *(experimental)*
Streams a camera's RTSP audio through `ffmpeg` with a noise-reduction filter chain (`-t 120` 120-second maximum stream duration and `-rw_timeout 5000000` 5-second RTSP I/O timeout). The sample rate and channel count come from the device's hardware manifest (`audio.out_rate`, `audio.out_ch`), so current Latter boards get 48 kHz mono. Latter firmware requests FLAC. If the camera has no stream source or `ffmpeg` isn't available, a short silent WAV is returned.

| Param | Notes |
| :--- | :--- |
| `sig` | **Required.** Short-lived (10 min) signed resource `camera_audio:<entity_id>\|<nr>\|<fmt>` |
| `nr` | `strong` (default), `light`, or `off` (bound into `sig`; tampering returns `403`) |
| `fmt` | `flac` (default) or `wav` (bound into `sig`; tampering returns `403`) |

The noise-reduction filter level (`strong`, `light`, or `off`) and output format (`flac` or `wav`) are both bound inside the signed resource minted by `doorbell.py` (`coordinator.build_camera_audio_url(cam_ent, nr_norm, "flac")`). Opening a new stream on a Device terminates any prior stream on that same Device; at most 2 streams can run concurrently across the System (`429` when full).

### `POST /api/latter/wallpaper/upload`
Accepts a `multipart/form-data` photo upload (up to **15 MB**) from Latter Studio (`XMLHttpRequest`), authorized by Home Assistant's bearer-token session (`requires_auth = True` + `hass_user.is_admin`), validates and stores the image under `.storage/latter/wallpapers/`, and returns the refreshed wallpaper catalogs without touching Home Assistant's 4 MB WebSocket frame limit.

### Studio
Studio is a `panel_custom` web component at `/latter` (admin only), loaded from the single versioned static path `/latter_ui_<version>` (for example `/latter_ui_3_0_0`). Aside from `POST /api/latter/wallpaper/upload`, it talks to Home Assistant exclusively through admin-gated WebSocket commands: `latter/system/*` (`get_state`, `subscribe`, `command`, `export`, `import`) and `latter/device/*` (`command`, `export`, `import`, `reset`). These are internal, not a stable API.

One unauthenticated branding asset is also served: `GET /api/latter/brand/icon.png`. Studio's sidebar icon is a static frontend module (`/latter_ui_<version>/latter-icons.js?v=<content hash>`), served like the panel JavaScript and loaded by Home Assistant on every page; it only defines the `latter:logo` icon.
