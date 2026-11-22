# `ha-latter` Agent & Contributor Guide (`v3.0.0`)

`ha-latter` (`Apache-2.0`, Home Assistant 2026.10+) is the local-push Home Assistant middleware and **Latter Studio** control plane for Latter ESPHome Devices and the Bluetooth Area presence fabric.

---

## 1. Acyclic `L0a`–`L4` DAG Architecture (`custom_components/latter/`)

Do **not** create backward-compatibility shims, `try/except ImportError` wrappers, artificial line-count file splits, or upward/cyclic imports. Organize modules by **functional domain cohesion** with bounded per-function complexity (`ruff` `PLR`), while `tools/verify_ha.py` enforces zero Tarjan SCC cycles across 8 strict downward layers (`L0a < L0b < L1a < L1b < L2a < L2b < L3 < L4`). Multi-layer subpackage `__init__.py` files (`areas`, `cameras`, `groups`, `http`, `media`, `presence`, `services`, `studio`, `wallpapers`) MUST remain 1-line docstrings with zero imports:

- **`L0a` (Pure Stdlib Leaves — Zero `homeassistant`/`voluptuous`/`aiohttp`/`PIL`)**:
  - `const.py` (domain constants, 5 `PUBLIC_SERVICES`, 20 `ALL_RPC_METHODS`, `INTEGRATION_VERSION = "3.0.0"`, `MIN_FIRMWARE_SDK_REV = 2026112007`), `config_defaults.py`, `repairs_keys.py`, `protocol_specs.py` (loads `protocol_v3.json` once), plus 9 docstring-only subpackage `__init__.py` markers.
- **`L0b` (Pure Stdlib Codecs, Math & Cleaners -> `L0a` Only)**:
  - `protocol_codec.py` (`\x1f` Protocol v3 domain packers & UTF-8 truncation), `protocol_policy.py` (`v1:` HMAC-SHA256 PIN session-key wrapping, `PinLockoutTracker`, PBKDF2 hashing), `presence/ble_math.py` (RSSI path-loss, Kalman & multi-floor math), `studio/settings_cleaners.py` (typed Studio setting validators).
- **`L1a` (Foundational Caches, Hub Registry, Signing & Gates)**:
  - `media_cache.py` (`threading.Lock`-guarded LRU artwork/thumbnail/mask caches), `hub_registry.py` (`LatterSystemHub`, `AreaStateIndex`, `get_system_config_lock`, `iter_coordinators`), `http/signing.py` (`UrlSigner`), `studio/state_gates.py` (`CatalogGate`, `SectionHashGate`, command scope checks).
- **`L1b` (Bound Identity, Feeds, Remotes, Area/BLE Registries, Linking & Wallpapers)**:
  - `identity.py` (bound `esphome_device_id`/MAC/`via_device_id` & manifest traits), `feeds.py` (weather, sun/moon, calendar builders), `remotes.py`, `doorbell_targets.py`, `areas/{registry,state_index}.py`, `presence/{ble_registry,area_fusion,ble_discovery}.py`, `media/{linking,lyrics}.py`, `wallpapers/{models,store,media_import,pools}.py`.
- **`L2a` (Doorbell, Camera Stream Hub, Device Groups, Media Playback & BLE Trackers)**:
  - `doorbell.py`, `cameras/{transcode,stream_hub,capabilities}.py`, `groups/{esphome_inspector,device_groups,device_reset}.py`, `media/{browse,volume,announce,tts_queue,playback,state_payload}.py`, `presence/{ble_tracker_matcher,ble_tracker_calibration}.py`.
- **`L2b` (Area Curation/Actions/Sync, BLE Spatial Fabric & Backup)**:
  - `areas/{sync,telemetry,curation,actions,catalogs}.py` (`sync_esphome_device_area`), `presence/ble_fabric.py` (`LatterBleFabric`), `backup.py` (`async_pre_backup`/`async_post_backup` & JSON bundles). Zero cross-domain `areas <-> presence` imports at `L2b`.
- **`L3` (Coordinator, Hub Sync, Services/RPC, HTTP Views, Repairs, Diagnostics & Studio WS)**:
  - `coordinator/{runtime_store,device_traits,wallpaper_scheduler,area_follow_controller,ha_registry_sync,device_lifecycle,v3_transport,core,__init__}.py` (typed public runtime API — zero external `coord._*` accesses), `hub_sync.py`, `services/{rpc_security,rpc_slots,rpc_receiver,rpc_dispatcher,public_actions}.py` + `services.yaml` (5 public actions vs private 20-method `LatterRpcDispatcher`; `rpc_receiver.py` auto-hides `latter_rpc_outbox` via `RegistryEntryHider.INTEGRATION`), `http/{proxy_views,wallpaper_views,camera_views,views_register}.py`, `repairs.py`, `diagnostics.py`, `studio/{panel,payload,commands,system_commands,device_commands}.py`.
- **`L4` (Integration Entry, Config Flows & 8 Entity Platforms)**:
  - `__init__.py` (typed `LatterConfigEntry = ConfigEntry[LatterRuntimeData]` on `entry.runtime_data`), `config_flow.py`, and entity platforms `binary_sensor.py`, `button.py`, `device_tracker.py`, `light.py`, `number.py`, `select.py`, `sensor.py`, `switch.py` (each platform imports strictly `< L4`).

---

## 2. Non-Negotiable Engineering Invariants

1. **Strict Bound Identity**: Every Latter display subentry stores `esphome_device_id` and MAC, declaring `identifiers={(DOMAIN, format_mac(mac))}` and `via_device_id`. Resolve ESPHome entities, `esphome.<node>_*` services (`esphome_service()`), Music Assistant players, Areas, and camera sibling speakers strictly by exact ID/MAC—never by substring or first-device fallback. Never assign `self.device_entry` directly.
2. **Foreign Registry & Security Boundaries**: Never mutate devices or entities owned by other integrations. *Sole exceptions*: `services/rpc_receiver.py` auto-hiding the bound `latter_rpc_outbox` entity (`RegistryEntryHider.INTEGRATION`), and `areas/sync.py:sync_esphome_device_area` updating `area_id` on the Device's own bound `esphome_device_id` (and child `via_device` Latter Device) for roaming **Voice Follows Me** (`stationary == 0`) or administrator Static **Assigned Area** sync. Lock and alarm commands require explicit verbs (`lock`/`unlock`, `arm_*`/`disarm`—never `toggle`); `alarm_control_panel` codes pass straight through per `alarm_caps`, while opening locks, garage covers, and code-less alarms enforce `security_pin_policy` (`auto` / `allow` / `require_pin` / `block`).
3. **Signed Zero-WAN HTTP Views**: Every unauthenticated `/api/latter/*` view verifies a scoped HMAC `sig` binding all server-chosen parameters (`camera_audio:<entity_id>|<nr>|<fmt>`, `camera:<entity_id>|<w>|<h>|<shape>`, etc.) with zero cloud/WAN requests. `POST /api/latter/wallpaper/upload` requires an authenticated Home Assistant admin user. Resolve LAN IPv4 asynchronously without blocking sockets on the event loop.
4. **Latter Studio (`frontend_src/` -> `custom_components/latter/frontend/latter-studio.js`)**: Follow [`docs/studio-design.md`](docs/studio-design.md) and the cohesive `L0`–`L4` Tarjan zero-cycle TypeScript DAG (`build/guardrails.mjs`: `src/styles/{tokens,layout,cards,controls,data,dialogs}.ts`, `src/i18n/en.ts`, `src/state/*`, `src/components/*`, and `src/views/**` including `src/views/groups/group-baseline-drawer.ts`). Use HA CSS theme variables in `:host`, `websocket_api` (`hass.callWS`) for all state/commands (except the single Bearer-authenticated multipart XHR in `src/api/ws-client.ts` to `/api/latter/wallpaper/upload`), and never touch `localStorage.hassTokens`, `hass-subpage`, or shadow-root internals.
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
pytest tests --cov=custom_components.latter --cov-fail-under=75 -q
```
