# Contributing to Latter (`ha-latter`)

Thank you for contributing to `ha-latter`, the local-push Home Assistant integration and **Latter Studio** control plane for Latter Devices and the Bluetooth Area presence fabric!

## License & Developer Certificate of Origin (DCO)

All contributions are licensed under the **[Apache License, Version 2.0](LICENSE)** (inbound = outbound; no separate CLA required). Third-party attributions live in **[NOTICE](NOTICE)**.

Every commit must include a `Signed-off-by` trailer certifying the [Developer Certificate of Origin v1.1](https://developercertificate.org/):

```bash
git commit -s -m "Short summary of your change"
```

## Branching & CI Gate (`dev` -> `main`)

- Target all pull requests against the **`dev`** branch (never directly against `main`).
- `main` is the branch Home Assistant Marketplace installs from, and moves **only** by automated fast-forward after Marketplace validation, Home Assistant `hassfest`, static DAG/security guardrails, `ruff`, `mypy --strict` against Home Assistant 2026.11, Playwright Chromium + `@axe-core/playwright` E2E, and the official `pytest-homeassistant` suite pass on `dev`.

## Architectural Ground Rules

1. **Functional Domain Cohesion & Zero-Cycle Architecture**: Organize modules by cohesive functional responsibility rather than arbitrary per-file line-count splits, keeping McCabe complexity bounded with HA-Core `ruff` rules (`C901 <= 18`). Both the Python integration (`custom_components/latter/`, verified by `tools/verify_ha.py`) and the stock `esbuild` + `lit` Studio frontend (`frontend_src/src/`, verified by `frontend_src/build/guardrails.mjs`) enforce **zero-cycle Tarjan SCC** import graphs across coarse architectural boundaries (see [`AGENTS.md`](AGENTS.md)). Never add backward-compatibility shims, `try/except ImportError` wrappers, or custom Home Assistant / DOM mock harnesses.
2. **Bound Identity & Foreign Registry Boundary**: Devices bind strictly by `esphome_device_id` and MAC address (`{(DOMAIN, format_mac(mac))}` with `via_device_id` in `identity.py`). Never match ESPHome entities, Areas, or camera sibling speakers by substring or first-device fallback, and never mutate entities or devices owned by other integrations (outside `services/rpc_receiver.py` auto-hiding the bound `latter_rpc_outbox` transport entity via `RegistryEntryHider.INTEGRATION`, and `areas/sync.py:sync_esphome_device_area` updating `area_id` on the bound ESPHome device and child Latter device for roaming *Voice Follows Me* moves or static *Assigned Area* sync).
3. **5 Public Actions vs. Private `LatterRpcDispatcher`**: Expose only the 5 user automation actions (`latter.notify`, `latter.intercom_broadcast`, `latter.set_active_area`, `latter.set_active_speaker`, `latter.reset_device`) on `hass.services` / `services.yaml`. All 20 `Device -> HA` wire RPC methods dispatch privately through `LatterRpcDispatcher` (`services/rpc_dispatcher.py`).
4. **Signed 100% Zero-WAN HTTP Views**: `ha-latter` makes zero outbound cloud or WAN requests. Unauthenticated `/api/latter/*` media/stream `GET` endpoints verify a scoped, expiring HMAC `sig` (`http/signing.py`) binding server-chosen parameters (`camera_audio:<entity_id>|<nr>|<fmt>`, `camera:<entity_id>|<w>|<h>|<shape>`, etc.); `POST /api/latter/wallpaper/upload` requires an authenticated Home Assistant administrator session.
5. **Latter Studio & Protocol v3 Lockstep**: Read [`docs/studio-design.md`](docs/studio-design.md) before changing Latter Studio (`frontend_src/` or `studio/`). Keep `custom_components/latter/protocol_v3.json` and `frontend_src/src/protocol-schema.ts` generated from `esphome-latter-core/protocol/latter_v3.json` (`tools/gen_protocol.py`), and rebuild `custom_components/latter/frontend/latter-studio.js` via `npm --prefix frontend_src run build`.
6. **Standard Terminology & Translations**: Use Home Assistant terminology (`System`, `Sites`, `Areas`, `Devices`, `Roles`, `Policies`, `Bridges`). Keep `custom_components/latter/strings.json` and `custom_components/latter/translations/en.json` byte-identical.

## Local Pre-Flight Checks

Before opening a pull request, install test dependencies (`pip install --group test` on Python 3.14+ and `npm --prefix frontend_src ci && npx --prefix frontend_src playwright install chromium` on Node 24+) and run from `ha-latter/`:

```bash
python tools/verify_ha.py
npm --prefix frontend_src run check
npm --prefix frontend_src test
ruff check custom_components/latter tests tools
mypy custom_components/latter
pytest tests --cov=custom_components.latter --cov-fail-under=75 -q
```

When working in a dual-repo checkout alongside `esphome-latter-core`, run `python .agents/scripts/verify_workspace.py` (or `--linux-parity` on Windows to execute real Home Assistant `pytest` via WSL2 / Docker) from the workspace root.
