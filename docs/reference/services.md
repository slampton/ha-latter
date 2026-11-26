# Services Reference

Latter separates its service surface cleanly into two layers ([`services/`](../../custom_components/latter/services/), [`services.yaml`](../../custom_components/latter/services.yaml)):

1. **6 Public Home Assistant Actions (`hass.services` under `latter.*`):** `latter.notify`, `latter.intercom_broadcast`, `latter.set_active_area`, `latter.set_active_speaker`, `latter.reset_device`, and `latter.navigate`—registered for Home Assistant automations, scripts, and Developer Tools.
2. **20 Private Bound-Device Wire RPCs (`LatterRpcDispatcher`):** invoked strictly by bound ESPHome displays over their Zero-Privilege **System: RPC Outbox** (`LatterRpcReceiver` in `services/rpc_receiver.py` -> private `LatterRpcDispatcher` in `services/rpc_dispatcher.py`, authenticated by bound `esphome_device_id` so `allow_service_calls` is never required and internal wire RPCs never pollute `hass.services`).

---

## Public Home Assistant Actions (`latter.*`)

### Special Target Values

Actions that target a device accept `target_device` (a device slug such as `pocket_assistant`, a subentry ID, a Home Assistant device ID, or a special target below). When only one Latter device is configured, `target_device` is optional (except on `latter.reset_device`, which always requires an explicit target).

| Special Target | `latter.notify` & `latter.navigate` | `latter.intercom_broadcast` |
| :--- | :--- | :--- |
| `all` | Every display device | Configured System broadcast speakers *(same as omitting target)* |
| `occupied_areas` | Display devices whose current Area is occupied | Configured broadcast speakers in occupied Areas |
| `person.<id>` | Display devices assigned to that person or in their current Area | Configured broadcast speakers in that person's current Area |
| *(No match)* | Delivers nothing | No-op (never broadcasts to unoccupied Areas) |

### `latter.notify`
Wakes target displays via `esphome.<node>_latter_show_notification` (respecting sleep-safe `switch.<slug>_do_not_disturb` on non-critical alerts), shows an alert banner, optionally plays an embedded chime or speaks TTS, optionally attaches a signed camera snapshot, and fires `latter_event` (`type: notification_dispatched`).

| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `message` | string | **required** | Truncated to 160 characters on the device |
| `title` | string | `Notification` | Truncated to 48 characters |
| `priority` | `normal` \| `warning` \| `critical` | `normal` | `critical` bypasses Do Not Disturb |
| `duration` | int (seconds) | `8` | Clamped to 2–60 |
| `chime` | bool | `true` | Skipped when `announce: true` |
| `camera_entity` | `camera.*` | — | Mints a signed baseline-JPEG snapshot URL |
| `announce` | bool | `false` | Speaks `message` via TTS on the device's Assist satellite or local speaker |
| `target_device` | string | — | Device slug, device ID, `all`, `occupied_areas`, or `person.<id>` |

### `latter.intercom_broadcast`
Broadcasts a TTS announcement (`message`) or local/`media-source://` clip (`media_url`) across `target_speakers` (or `target_device` special targets) using `tts_entity` (defaults to the first `tts.*` entity). Uses `music_assistant.play_announcement` on Music Assistant players and `media_player.play_media` (`announce: true`) elsewhere.

### `latter.set_active_area`
Switches the device's active Area (`area_id`, ID or name). Moves media along when **Media Area handoff** is on, and updates the Home Assistant Device Area on roaming hardware (`stationary == 0`) when **Voice Follows Me** is enabled.

### `latter.set_active_speaker`
Selects `entity_id` (`media_player.*`, required) as the device's active speaker. With `transfer_queue: true` (default), transfers Music Assistant queues via `music_assistant.transfer_queue` (holding Now Playing metadata and album art steady across spin-up) or pauses and replays `media_content_id` on standard players.

### `latter.reset_device`
Admin-only action that resets `target_device` (**required**; never falls back to a default device):
- `device_settings` (`true` default): calls `esphome.<node>_latter_factory_reset` (erases saved on-device NVS preferences and restarts while keeping compiled Wi-Fi and API pairing; requires firmware core rev `2026112402+`).
- `latter_options` (`true` default): resets Studio per-device settings back to onboarding defaults while preserving the bound ESPHome device, MAC, slug, and Music Assistant player link.

### `latter.navigate`
Switches one or more Latter displays to any canonical Protocol v3 page or subpage route (`home`, `app:home`, `app:settings`, `quick_actions`, or any route token from `catalogs.shortcut_routes` such as `cameras:grid`, `weather:forecast`, `music:lyrics`, `home_hub:thermostat`, `area:light`, or `time:timers`; requires firmware core rev `2026112201+`).

| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `route` | string | **required** | Canonical Latter route token (validated against `protocol_v3.json`; unknown routes raise `ServiceValidationError`) |
| `wake` | bool | `true` | Sends `nav:<route>` when `true` or `nav_silent:<route>` when `false`; **Bedtime Mode** (`bedtime_active`) always forces `nav_silent:<route>` so bedroom displays stay dark |
| `target_device` | string | — | Device slug, device ID, `all`, `occupied_areas`, or `person.<id>`. Multi-target calls skip sleeping/offline displays without aborting; explicit single-device calls raise an error if offline |

---

## Private Bound-Device Wire RPCs (`LatterRpcDispatcher`)

Bound ESPHome displays emit compact chunked frames on `sensor.<node>_system_rpc_outbox` (`ALL_RPC_METHODS` in [`const.py`](../../custom_components/latter/const.py), dispatched in [`services/rpc_dispatcher.py`](../../custom_components/latter/services/rpc_dispatcher.py) strictly against the calling `LatterCoordinator`):

| Category | Wire RPC Method | Summary |
| :--- | :--- | :--- |
| **Lifecycle & Telemetry** | `device_hello` | Registers `contract=3`, `boot_id`, Hardware Manifest v2, `prefs_seq`, and `dirty_prefs`, mints a per-boot HMAC PIN session key, and pushes fresh Protocol v3 domains. |
| | `device_telemetry` | Streams on-demand internal SRAM, PSRAM low-water, BLE radio state, profiler state, and `[PROF:LINK]` metrics into Studio's `live.telemetry`. |
| | `display_state` | Reports live `power_state`, `brightness_pct`, and `screensaver_active` for `light.<slug>_screen` and `switch.<slug>_screensaver`. |
| | `timer_alarm_state` | Reports `timer_running`, `timer_paused`, `remaining_sec`, `ringing`, and stopwatch state for Tier 2 timer/alarm entities and Studio Overview. |
| **Preferences & Appearance** | `set_device_prefs` | Reconciles on-device typed preference edits (`base_seq`, `changes`), detaching `device_group` to `custom` if an enforced baseline diverges. |
| | `save_custom_color` | Saves `#RRGGBB` into the 24-swatch System color library and switches the calling Device's `color_profile` to `Custom`. |
| **Media & Remotes** | `music_browse` | Paginates local Music Assistant library categories, speakers, active queues, track info, and local Music Assistant lyrics (`lyrics` / `lyrics_fetch` -> `latter_set_music_lyrics`, 100% Zero-WAN). |
| | `media_command` | Executes `play`, `pause`, `toggle`, `next`, `previous`, `stop`, `seek`, `clear_queue`, `play_media`, `join`, `unjoin`, and queue reordering (auto-healing cold Sendspin queues). |
| | `media_volume` | Adjusts `set` \| `up` \| `down` \| `mute` volume, routing through any configured Studio **Speaker volume override**. |
| | `set_active_speaker` | Bound-device counterpart of `latter.set_active_speaker`. |
| | `remote_action` | Dispatches TV/AV slot selection, power toggle, transport, volume, and D-pad commands (including press-and-hold `hold_secs`). |
| **Areas, Home Hub & Shortcuts** | `area_browse` | Pushes paginated Area lists (`mode: areas`) or controllable Area/Home entities (`mode: entities` \| `home`) via `latter_set_slots`. |
| | `area_action` | Executes Area or Home Hub (`home_hub.alarm`, `home_hub.thermostat`, `home_hub.lock`, `home_hub.garage`, `home_hub.vacuum`) control actions. |
| | `set_active_area` | Bound-device counterpart of `latter.set_active_area`. |
| | `shortcut_action` | Executes an `(entity_id, action)` pair strictly allowlisted on the calling Device's `dock_items` or `pinned_items`. |
| **Calendar & Intercom** | `calendar_fetch` | Fetches and deduplicates up to 64 structured events across configured Site calendars (`[start_date .. end_date]`, up to 60 days) and pushes chunks via `latter_set_calendar_view`. |
| | `calendar_create_event` | Creates a timed, all-day, or RFC 5545 recurring (`rrule`) event on a writable configured Site calendar. |
| | `calendar_delete_event` | Deletes an event (or recurring instance) on a writable configured Site calendar. |
| | `intercom_broadcast` | Bound-device counterpart of `latter.intercom_broadcast` from the Home Hub **Broadcast** tab. |
| | `doorbell_intercom` | Controls live camera audio (`listen_start` \| `listen_stop` \| `listen_toggle`), TTS `talk_message` / `quick_reply`, `set_noise_reduction`, and `select_camera`. |

### Session-Key PIN Unwrapping & Perimeter Security (`services/rpc_dispatcher.py` & `protocol_policy.py`)

- **Authenticated `v1:` PIN Envelopes & Lockout:** PINs entered on the touch keypad (`4–12` digits) are wrapped with the Device's per-boot session key (`v1:<key_id>:<nonce_hex8>:<ct_hex>:<mac_hex32>`) before crossing `System: RPC Outbox`, unwrapped in constant time by `unwrap_rpc_pin_code`, and guarded by `PinLockoutTracker` (`5` consecutive failures trigger `60 s` exponential backoff).
- **Home Assistant Alarm Panels with a Code (`alarm_caps`):** when the target `alarm_control_panel` defines `code_format`, `disarm` (and `arm_*` when `code_arm_required` is true) validates `code` and passes it straight through to Home Assistant's alarm service. Arming is never blocked by `security_pin_policy: block`.
- **Locks, Garage/Gate Covers & Code-Less Alarms:** opening actions (`unlock`/`open`, opening garage/gate/door covers, and `disarm` on code-less alarms) enforce the calling Device's Studio **Perimeter security policy** (`allow`, `require_pin`, or `block`; `auto` resolves to `require_pin` on stationary panels or when an HA alarm code exists), verifying `code` in constant time against the PBKDF2-HMAC-SHA256 Device security PIN (falling back to the System security PIN).
