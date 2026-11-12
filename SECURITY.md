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

- **Scoped, Expiring HMAC Resource Signing**: Every `/api/latter/*` endpoint requires a constant-time verified HMAC-SHA256 signature (`http.py`) bound to the target Device subentry, server-chosen resource ID, render geometry, and expiry window. Client-supplied `entity_id` or arbitrary `src` paths are never trusted.
- **Admin-Gated Studio WebSocket**: Latter Studio is registered with `require_admin=True` and communicates exclusively over Home Assistant's authenticated `websocket_api` (`latter/system/*`, `latter/device/*`).
- **Bound Device Identity & 3-Tier Perimeter Policy**: Device RPCs authenticate by bound `esphome_device_id` (never caller-supplied names or slugs). Locks and alarm panels reject `toggle`, require explicit verbs, and enforce per-Device Studio policy (`allow`, `require_pin`, or `block`).
