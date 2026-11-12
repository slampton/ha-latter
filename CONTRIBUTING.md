# Contributing to Latter (`ha-latter`)

Thank you for contributing to `ha-latter`, the Home Assistant integration and Latter Studio control plane for Latter Devices and Bluetooth Area presence!

## License & Developer Certificate of Origin (DCO)

All contributions are licensed under the **[Apache License, Version 2.0](LICENSE)** (inbound = outbound; no separate CLA required).

Every commit must include a `Signed-off-by` trailer certifying the [Developer Certificate of Origin v1.1](https://developercertificate.org/):

```bash
git commit -s -m "Short summary of your change"
```

## Branching & CI Gate (`dev` -> `main`)

- Target all pull requests against the **`dev`** branch (never directly against `main`).
- `main` is the branch HACS installs from, and moves **only** by automated fast-forward after HACS validation, Home Assistant `hassfest`, static guardrails, `ruff`, and the automated test suite pass on `dev`.

## Architectural Ground Rules

1. **28-Module Canonical Topology**: `custom_components/latter/` contains 24 flat root `.py` modules plus 4 `studio/` `.py` modules (`28` total), and `tests/harness/` holds the deterministic Home Assistant test doubles. Do not add backward-compatibility shims or `try/except ImportError` wrappers.
2. **Bound Identity Only**: Devices bind by `esphome_device_id` and MAC address (`{(DOMAIN, format_mac(mac))}` with `via_device_id` in `identity.py`). Never match ESPHome entities, Areas, or camera sibling speakers by substring or first-device fallback, and never mutate entities or devices owned by other integrations (outside the documented roaming *Voice Follows Me* `area_id` update on the bound ESPHome device in `areas.py`).
3. **Signed HTTP Views**: Every unauthenticated `/api/latter/*` endpoint verifies a scoped, expiring HMAC signature (`http.py`) binding target parameters (`camera_audio:<entity_id>|<nr>|<fmt>`, `camera:<entity_id>|<w>|<h>|<shape>`, etc.); `POST /api/latter/wallpaper/upload` requires an authenticated Home Assistant administrator session. Never trust client-supplied `entity_id` or file paths.
4. **Latter Studio Standards**: Read [`docs/studio-design.md`](docs/studio-design.md) before changing Latter Studio (`frontend_src/` or `studio/`). Studio mounts its versioned static bundle at `/latter_ui_<version>`, uses HA theme CSS tokens in `:host`, Title Case labels (`D-013`), immediate debounced saves (`D-010`), and talks over `websocket_api` (`hass.callWS`).
5. **Standard Terminology**: Use Home Assistant terminology (`System`, `Sites`, `Areas`, `Devices`, `Roles`, `Policies`, `Bridges`).
6. **Translation Parity**: Keep `custom_components/latter/strings.json` and `custom_components/latter/translations/en.json` byte-identical.

## Local Pre-Flight Checks

Before opening a pull request, run the verification suite from the root of `ha-latter`:

```bash
python tools/verify_ha.py
npm --prefix frontend_src run check
ruff check custom_components/latter tests
pytest tests --cov=custom_components.latter --cov-fail-under=75 -q
```
