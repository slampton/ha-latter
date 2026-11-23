# `ha-latter` Agent & Contributor Guide (`v3.0.0`)

`ha-latter` (`Apache-2.0`, Home Assistant 2026.11+) is the local-push Home Assistant middleware and **Latter Studio** control plane for Latter ESPHome Devices and the Bluetooth Area presence fabric.

---

## 1. Zero-Cycle Functional Architecture (`custom_components/latter/`)

Do **not** create backward-compatibility shims, `try/except ImportError` wrappers, artificial line-count file splits, linear mixin inheritance chains, or upward/cyclic imports. Organize modules by **functional domain cohesion** with bounded McCabe complexity (`ruff` `C901 <= 18`), while `tools/verify_ha.py` enforces **Tarjan SCC zero cycles** (including implicit Python `pkg/__init__.py` imports) across 3 coarse architectural boundaries:

- **Pure Stdlib Leaves (Zero `homeassistant`/`voluptuous`/`aiohttp`/`PIL`)**:
  - `const.py` (domain constants, 6 `PUBLIC_SERVICES`, 20 `ALL_RPC_METHODS`, `INTEGRATION_VERSION = "3.0.0"`, `MIN_FIRMWARE_SDK_REV = 2026112201`), `config_defaults.py`, `repairs_keys.py`, `protocol_specs.py` (loads `protocol_v3.json` once), `protocol_codec.py` (`\x1f` Protocol v3 packers & UTF-8 truncation), `protocol_policy.py` (`v1:` HMAC-SHA256 PIN wrapping, `PinLockoutTracker`, PBKDF2), `presence/ble_math.py`, and `studio/settings_cleaners.py`.
- **Domain & Registry Tier (Never imports Coordinator, Services, HTTP views, Studio WS/panel, Repairs, or Diagnostics)**:
  - `media_cache.py`, `hub_registry.py` (`LatterSystemHub`, `LatterDomainData`, `DOMAIN_DATA_KEY: HassKey[LatterDomainData]`, `AreaStateIndex`, `get_system_config_lock`, `iter_coordinators`), `http/signing.py` (`UrlSigner`), `studio/state_gates.py`, `identity.py`, `feeds.py`, `remotes.py`, `doorbell.py`, `backup.py`.
  - Subpackages: `areas/{registry,sync,telemetry,curation,actions,catalogs}.py` (`sync.py:sync_esphome_device_area` is the sole device-area mutation boundary), `cameras/{capabilities,transcode,stream_hub}.py`, `groups/{esphome_inspector,device_groups}.py`, `media/{linking,lyrics,browse,tts_queue,playback,state_payload}.py`, `presence/{ble_registry,area_fusion,ble_discovery,ble_tracker,ble_fabric}.py`, `wallpapers/{models,store,media_import,pools}.py`.
- **Orchestration & Endpoint Tier**:
  - `coordinator/{__init__,runtime,area_follow,core}.py` (unified `LatterCoordinator`, `LatterDeviceRuntime`, `LatterAreaFollowController` — zero fake mixins, clean static re-exports, zero external `coord._*` accesses), `hub_sync.py`, `services/{rpc_slots,rpc_receiver,rpc_dispatcher,public_actions}.py` + `services.yaml` (6 public actions vs private 20-method `LatterRpcDispatcher`; `rpc_receiver.py` auto-hides `latter_rpc_outbox` via `RegistryEntryHider.INTEGRATION`), `http/{proxy_views,wallpaper_views,camera_views}.py`, `repairs.py`, `diagnostics.py`, `studio/{panel,payload,commands,system_commands,device_commands}.py`.
- **Integration Root & 8 Entity Platforms (Never imported by lower modules; platforms never import each other or `__init__`/`config_flow`)**:
  - `__init__.py` (`LatterConfigEntry = ConfigEntry[LatterRuntimeData]` on `entry.runtime_data`, registers HTTP views), `config_flow.py`, and `binary_sensor.py`, `button.py`, `device_tracker.py`, `light.py`, `number.py`, `select.py`, `sensor.py`, `switch.py`.

---

## 2. Non-Negotiable Engineering Invariants

1. **Strict Bound Identity**: Every Latter display subentry stores `esphome_device_id` and MAC, declaring `identifiers={(DOMAIN, format_mac(mac))}` and `via_device_id`. Resolve ESPHome entities, `esphome.<node>_*` services (`esphome_service()`), Music Assistant players, Areas, and camera sibling speakers strictly by exact ID/MAC—never by substring or first-device fallback. Never assign `self.device_entry` directly.
2. **Foreign Registry & Security Boundaries**: Never mutate devices or entities owned by other integrations. *Sole exceptions*: `services/rpc_receiver.py` auto-hiding the bound `latter_rpc_outbox` entity (`RegistryEntryHider.INTEGRATION`), and `areas/sync.py:sync_esphome_device_area` updating `area_id` on the Device's own bound `esphome_device_id` (and child `via_device` Latter Device) for roaming **Voice Follows Me** (`stationary == 0`) or administrator Static **Assigned Area** sync. Lock and alarm commands require explicit verbs (`lock`/`unlock`, `arm_*`/`disarm`—never `toggle`); `alarm_control_panel` codes pass straight through per `alarm_caps`, while opening locks, garage covers, and code-less alarms enforce `security_pin_policy` (`auto` / `allow` / `require_pin` / `block`).
3. **Signed Zero-WAN HTTP Views**: Every unauthenticated `/api/latter/*` view verifies a scoped HMAC `sig` binding all server-chosen parameters (`camera_audio:<entity_id>|<nr>|<fmt>`, `camera:<entity_id>|<w>|<h>|<shape>`, etc.) with zero cloud/WAN requests. `POST /api/latter/wallpaper/upload` requires an authenticated Home Assistant admin user. Resolve LAN IPv4 asynchronously without blocking sockets on the event loop.
4. **Latter Studio (`frontend_src/` -> `custom_components/latter/frontend/latter-studio.js`)**: Authored in strict TypeScript on stock `lit` and bundled via stock `esbuild` (`build.mjs`, `D-078`). Follow [`docs/studio-design.md`](docs/studio-design.md) and the zero-cycle Studio DAG (`build/guardrails.mjs`: Tarjan SCC over `esbuild` `metafile` + 4 coarse directory boundaries). Use HA CSS theme variables in `:host`, `websocket_api` (`hass.callWS`) for all state/commands (except the single Bearer-authenticated multipart XHR in `src/api/ws-client.ts` to `/api/latter/wallpaper/upload`), and never touch `localStorage.hassTokens`, `hass-subpage`, or shadow-root internals.
5. **Terminology & Translations**: Use Home Assistant terminology (`System`, `Sites`, `Areas`, `Devices`, `Roles`, `Policies`, `Bridges`—never `"household"`, `"fleet"`, or spatial `"room"`). Keep `strings.json` and `translations/en.json` byte-identical.

---

## 3. Branching & Local Verification

All changes land on `dev` (`validate.yml` fast-forwards `main` on green CI). Run from `ha-latter/`:

```bash
python tools/verify_ha.py
node --no-warnings frontend_src/build.mjs --check --typecheck
npm --prefix frontend_src test
ruff check custom_components/latter tests tools
mypy custom_components/latter
pytest tests --cov=custom_components.latter --cov-fail-under=95 -q
```
