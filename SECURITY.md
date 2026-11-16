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

- **Scoped HMAC Resource Signing & Admin Upload Auth**: Unauthenticated `/api/latter/*` media/audio `GET` views require a constant-time verified HMAC-SHA256 signature (`http.py`) bound to the target Device subentry (or `system`), server-chosen resource ID, render geometry/filter parameters, and expiry window (`GET /api/latter/brand/icon.png` serves the static integration icon only). `POST /api/latter/wallpaper/upload` enforces Home Assistant's bearer-authenticated session (`requires_auth = True` + `hass_user.is_admin`). Client-supplied `entity_id` or arbitrary `src` paths are never trusted.
- **Admin-Gated Studio Control Plane**: Latter Studio is registered with `require_admin=True` and communicates over Home Assistant's authenticated `websocket_api` (`latter/system/*`, `latter/device/*`), plus Bearer-authenticated multipart `XMLHttpRequest` uploads to `POST /api/latter/wallpaper/upload`.
- **Bound Device Identity, Alarm Capabilities & Perimeter Policy**: Device RPCs authenticate strictly by bound `esphome_device_id` (never caller-supplied names or slugs). Locks and alarm panels reject `toggle` and require explicit verbs. Home Assistant `alarm_control_panel` entities with `code_format` (`alarm_caps`) validate and forward the alarm code directly to Home Assistant for arming/disarming as required by the panel, while opening locks, opening garage/gate covers, and disarming code-less alarms enforce per-Device Studio policy (`auto`, `allow`, `require_pin`, or `block`) verified in constant time against the PBKDF2-HMAC-SHA256 Device Security PIN (or System Security PIN fallback).
