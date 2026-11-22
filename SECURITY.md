# Security Policy

## Supported Versions

Latter follows a lockstep release cadence across [`ha-latter`](https://github.com/slampton/ha-latter) and [`esphome-latter-core`](https://github.com/slampton/esphome-latter-core). Security fixes land on `dev`, promote automatically to `main` once CI passes, and ship in the latest tagged release.

| Version | Supported |
| :--- | :--- |
| `3.0.x` (latest release & `main`) | Yes |
| `< 3.0.0` | No |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report vulnerabilities privately through **[GitHub Security Advisories](https://github.com/slampton/ha-latter/security/advisories/new)**. Include:

1. Affected module (`http`, `studio`, `services`, `identity`, `presence`, etc.).
2. Reproduction steps or proof-of-concept request/payload.
3. Expected authorization or isolation boundary vs. observed behavior.

We acknowledge private vulnerability reports within 72 hours and coordinate fixes across both `ha-latter` and `esphome-latter-core` before disclosure.

## Integration Security Invariants

- **Scoped HMAC Resource Signing, Stream Capability Tokens & Private-LAN Enforcement**: Unauthenticated `/api/latter/*` media, camera, and audio `GET` views require a constant-time verified HMAC-SHA256 signature (`http/signing.py`) bound to the target Device subentry (or `system`), server-chosen resource ID, render geometry/filter parameters, and expiry window (`48 h` day-bucketed TTL for Protocol v3 resource URLs and `600 s` exact expiry for on-demand camera audio and Studio previews, with the cached numeric LAN base URL refreshed every `300 s` and invalidated on `EVENT_CORE_CONFIG_UPDATE`; `GET /api/latter/brand/icon.png` serves the static integration icon only). Live MJPEG camera streaming verifies dedicated `camera_stream:` and `camera_grid:` capability tokens against the Device's configured `visible_camera_entities` allowlist (`camera_audio:` enforces the same allowlist plus noise-reduction/format binding) and enforces private/LAN client IP ranges. `POST /api/latter/wallpaper/upload` enforces Home Assistant's bearer-authenticated session (`requires_auth = True` + `hass_user.is_admin`) with strict multipart size and Pillow `<= 8192 px` / `<= 25 MP` decompression-bomb guards. Client-supplied `entity_id` or arbitrary `src` paths are never trusted.
- **Admin-Gated Studio Control Plane & Private RPC Dispatcher**: Latter Studio is registered with `require_admin=True` and communicates over Home Assistant's authenticated `websocket_api` (`latter/system/*`, `latter/device/*`), plus Bearer-authenticated multipart `XMLHttpRequest` uploads to `POST /api/latter/wallpaper/upload`. Only the 5 public user actions (`notify`, `intercom_broadcast`, `set_active_area`, `set_active_speaker`, `reset_device`) are registered on `hass.services`; all 20 device-to-hub wire RPCs route exclusively through the private `LatterRpcDispatcher` bound to the originating `LatterCoordinator` (`LatterRpcReceiver.rebind()` seeds reconnect `(boot_id, seq)` silently to prevent reconnect replay, and `latter_rpc_outbox` is auto-hidden via `RegistryEntryHider.INTEGRATION` and excluded from recorder history).
- **`v1:` Session-Key PIN Wrapping, Brute-Force Lockout & Perimeter Policy**: Device RPCs authenticate strictly by bound `esphome_device_id` (never caller-supplied names or slugs). On connect/`device_hello`, `ha-latter` provisions an ephemeral 256-bit per-session key (`mint_pin_session_key` -> `set_pin_key:<key_id>:<hex_key>`, redacted from logs and diagnostics). All device-submitted PINs (`4..12` ASCII digits) must arrive wrapped as `v1:<key_id>:<nonce_hex8>:<ct_hex>:<mac_hex32>` (monotonic `nonce > last_nonce`, keystream XOR cipher, and truncated HMAC-SHA256 bound to `key_id`, `nonce`, `entity_id`, and `action`; plaintext PINs, replayed nonces, and mismatched targets raise `PinWrapError` and are rejected). Per-Device and System `PinLockoutTracker` instances enforce brute-force lockout after `5` failed attempts with `60 s` exponential backoff up to `900 s` (`security_pin_locked_out`). Locks and alarm panels reject `toggle` and require explicit verbs; opening locks, opening garage/gate covers, and disarming code-less alarms enforce per-Device Studio policy (`auto`, `allow`, `require_pin`, or `block`) verified in constant time against the PBKDF2-HMAC-SHA256 Device Security PIN (or System Security PIN fallback).
- **100% Zero-WAN Local Operation**: `ha-latter` performs zero outbound internet/cloud requests—lyrics, artist metadata, speaker artwork (`allow_redirects=False`), weather, and calendar feeds resolve strictly from local Home Assistant and Music Assistant state (external lyrics, encyclopedia, geocoding, and map-tile endpoints are banned and verified statically in CI).
