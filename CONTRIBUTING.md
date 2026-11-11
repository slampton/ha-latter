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

1. **Bound Identity Only**: Devices bind by `esphome_device_id` and MAC address (`{(DOMAIN, format_mac(mac))}` with `via_device_id`). Never match ESPHome entities or services by substring or first-device fallback, and never mutate entities or devices owned by other integrations (outside the documented roaming *Voice Follows Me* `area_id` update on the bound ESPHome device).
2. **Signed HTTP Views**: Every `/api/latter/*` endpoint verifies a scoped, expiring HMAC signature (`resource_signing.py`). Never trust client-supplied `entity_id` or file paths.
3. **Latter Studio Standards**: Read [`docs/studio-design.md`](docs/studio-design.md) before changing Latter Studio (`frontend_src/` or `studio/`). Studio uses HA theme CSS tokens in `:host`, Title Case labels (`D-013`), immediate debounced saves (`D-010`), and talks exclusively over `websocket_api` (`hass.callWS`).
4. **Standard Terminology**: Use Home Assistant terminology (`System`, `Sites`, `Areas`, `Devices`, `Roles`, `Policies`, `Bridges`).
5. **Translation Parity**: Keep `custom_components/latter/strings.json` and `custom_components/latter/translations/en.json` byte-identical.

## Local Pre-Flight Checks

Before opening a pull request, run the verification suite from the root of `ha-latter`:

```bash
python tools/verify_ha.py
ruff check custom_components/latter tests
python -m unittest discover -s tests -v
```
