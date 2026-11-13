# `ha-latter` Agent & Contributor Guide (`v3.0.0`)

`ha-latter` (`Apache-2.0`, Home Assistant 2026.11+) is the local-push Home Assistant middleware and **Latter Studio** control plane for Latter ESPHome Devices and the Bluetooth Area presence fabric.

---

## 1. Exact 31-Module Architecture (`custom_components/latter/`)

Do **not** create backward-compatibility shims, `try/except ImportError` wrappers, or splinter subpackages. Every subsystem has one canonical owner across **27 flat root modules** + **4 `studio/` modules**:

### Root Integration Modules (27)
- `__init__.py` — Integration lifecycle (`LatterConfigEntry = ConfigEntry[LatterSystemHub]`), HTTP view & Studio registration, and `latter_ping` handshake (`async_ping_bound_devices`).
- `areas.py` — Area curation, exact normalized Area matching (`match_area_by_name_or_id`), roaming *Voice Follows Me* `area_id` sync (`sync_esphome_device_area`), Person Area distance, and `area_context` v3 payloads.
- `backup.py` — Home Assistant `backup` hooks (`async_pre_backup` / `async_post_backup`) and System/Device JSON bundle export/restore.
- `binary_sensor.py` — Per-Area `binary_sensor.<area>_ble_occupancy` driven by `LatterBleFabric` plus display-gated per-Device `timer_active` and `alarm_ringing` binary sensors.
- `button.py` — Curated Tier 2 action buttons (`find_my_device`, `activate_screensaver`) forwarding via `latter_device_command`.
- `config_flow.py` — Single-instance hub `ConfigFlow`, options flow, and Device / BLE Tag `ConfigSubentryFlow`s.
- `const.py` — Domain constants, config keys, service target helpers, `INTEGRATION_VERSION = "3.0.0"`, and `MIN_FIRMWARE_SDK_REV`.
- `coordinator.py` — Pure local-push `LatterCoordinator` (per-Device runtime, sleep-safe `device_prefs` two-way sync, local 1 Hz timer tick, state listeners, Protocol v3 push dispatch, and target resolution).
- `device_tracker.py` — BLE Tag and roaming Device Area `ScannerEntity` trackers.
- `diagnostics.py` — Redacted System and Device diagnostics snapshots.
- `doorbell.py` — Auto-detected doorbell ring reflexes, exact `device_id` sibling speaker resolution, noise-reduced RTSP audio URL minting, and PTT TTS replies.
- `feeds.py` — Weather forecast, sun/sky elevation, moon phase, and calendar agenda v3 builders.
- `groups.py` — Sleep-safe subentry-backed Device Groups, Power Profile baselines, Studio entity section classifier, and Device factory/option reset (`async_reset_device`).
- `http.py` — Constant-time HMAC `UrlSigner` (`sign_payload_resource`, `sign_on_demand_resource`, `verify_resource`) and all 7 `HomeAssistantView` endpoints (`/api/latter/*`).
- `hub.py` — `LatterSystemHub`, `iter_coordinators`, `AreaStateIndex` (incremental O(1) Area state index; never call `hass.states.async_all()`), and global config persistence.
- `identity.py` — Bound ESPHome device/entity resolution (`esphome_device_id` + MAC + `via_device_id`), hardware capability manifest parser, and chunked `latter_rpc_outbox` receiver.
- `media.py` — Active media player controller, volume routing, and exact `device_id`/MAC Music Assistant linking (`resolve_ma_counterpart_entity`) with container track expansion.
- `media_browse.py` — Paginated Music Assistant and Home Assistant media browser slot builders.
- `number.py` — Curated Tier 2 sleep-safe `alert_volume` slider entity backed by the Device subentry.
- `presence.py` — `LatterBleFabric`, RSSI path-loss math, `6.0 dB` cross-floor vertical attenuation, weighted Area sensor fusion, and dwell-gated Area follow.
- `protocol.py` — Pure-stdlib Protocol v3 `\x1f` frame packer (`v3␟<epoch>␟<rev>` across 6 domains including `device_prefs`), content-hash `rev` tracker, dock/activity normalizers, and PBKDF2 security PIN hashing.
- `remotes.py` — TV/AV remote slot discovery, canonical navigation command maps, `remote_config` v3 builder, and `async_execute_remote_action`.
- `repairs.py` — Home Assistant Repairs issue helpers and System health checks.
- `select.py` — Curated Tier 2 sleep-safe `power_profile` and `wake_word_mode` select entities backed by the Device subentry.
- `sensor.py` — System diagnostic, BLE presence, Person Area, and display-gated `timer_remaining` sensors.
- `services.py` — All 19 `latter.*` Home Assistant service schemas and handlers (`target_device="occupied_areas"` supported on `notify` and `intercom_broadcast`).
- `wallpapers.py` — Built-in preset catalog and private `.storage/latter/wallpapers/` asset management.

### Latter Studio Package (`studio/`, 4)
- `studio/__init__.py` — Admin-only `panel_custom` registration and content-hashed versioned static mount (`/latter_ui_<version>`).
- `studio/settings.py` — Pure-stdlib setting descriptors, scope classification (`SYSTEM_COMMANDS` vs `DEVICE_COMMANDS`), and `CatalogGate`.
- `studio/payload.py` — Studio state snapshot and live delta builders.
- `studio/commands.py` — Admin-gated `websocket_api` handlers (`latter/system/*`, `latter/device/*`).

---

## 2. Non-Negotiable Engineering Invariants

1. **Strict Bound Identity**: Every Latter display subentry stores `esphome_device_id` and MAC, declaring `identifiers={(DOMAIN, format_mac(mac))}` and `via_device_id`. Resolve ESPHome entities, `esphome.<node>_*` services, Music Assistant players, Areas, and camera sibling speakers strictly by exact ID/MAC—never by substring or first-device fallback. Never assign `self.device_entry` directly.
2. **Foreign Registry & Security Boundaries**: Never mutate devices or entities owned by other integrations. *Sole exception*: `areas.py:sync_esphome_device_area` updates `area_id` on the Device's own bound `esphome_device_id` (and child `via_device` Latter Device) either for roaming Devices (`stationary == 0`) with **Voice Follows Me** enabled or when an administrator explicitly sets a Static **Assigned Area** in Studio (`not native_ble_tracking`). Lock and alarm commands require explicit verbs (`lock`/`unlock`, `arm_*`/`disarm`—never `toggle`).
3. **Signed HTTP Views**: Every unauthenticated `/api/latter/*` view verifies a scoped HMAC `sig` binding all server-chosen parameters (`camera_audio:<entity_id>|<nr>|<fmt>`, `camera:<entity_id>|<w>|<h>|<shape>`, etc.). `POST /api/latter/wallpaper/upload` requires an authenticated Home Assistant admin user. Resolve LAN IPv4 asynchronously without blocking sockets on the event loop.
4. **Latter Studio (`frontend_src/` -> `custom_components/latter/frontend/latter-studio.js`)**: Follow [`docs/studio-design.md`](docs/studio-design.md). Use HA CSS theme variables in `:host`, `websocket_api` (`hass.callWS`) for all state/commands (except multipart XHR to `/api/latter/wallpaper/upload`), and never touch `localStorage.hassTokens`, `hass-subpage`, or shadow-root internals.
5. **Terminology & Translations**: Use Home Assistant terminology (`System`, `Sites`, `Areas`, `Devices`, `Roles`, `Policies`, `Bridges`). Keep `strings.json` and `translations/en.json` byte-identical.

---

## 3. Branching & Local Verification

All changes land on `dev` (`validate.yml` fast-forwards `main` on green CI). Run from `ha-latter/`:

```bash
python tools/verify_ha.py
npm --prefix frontend_src run check
ruff check custom_components/latter tests
pytest tests --cov=custom_components.latter --cov-fail-under=75 -q
```
