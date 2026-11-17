# Services Reference

Latter registers **19 services** under the `latter` domain ([`services.py`](../../custom_components/latter/services.py), [`services.yaml`](../../custom_components/latter/services.yaml)): **17 user/automation-callable services** plus **2 device-reported state/handshake services** (`latter.device_hello` and `latter.timer_alarm_state`).

Bound ESPHome displays invoke the 15 device-permitted operations over their Zero-Privilege **System: RPC Outbox** (`LatterRpcReceiver` in `identity.py`, authenticated by `esphome_device_id` so `allow_service_calls` is never required), while Home Assistant automations and scripts call `latter.*` directly. Administrative mutations (`reset_device`, `save_custom_color`, `set_dock_apps`, `set_device_prefs`) require an admin user context when invoked from Home Assistant.

---

## Targeting (`target_device`)

Services that act on a device accept `target_device` (a device slug such as `pocket_assistant`, a subentry ID, a Home Assistant device ID, or a special target below). When only one Latter device is configured, `target_device` is optional (except on `latter.reset_device`, which always requires an explicit target).

| Special Target | `latter.notify` | `latter.intercom_broadcast` |
| :--- | :--- | :--- |
| `all` | Every display device | Every online Music Assistant speaker *(same as omitting target)* |
| `occupied_areas` | Display devices whose current Area is occupied | Music Assistant speakers in occupied Areas, plus matching devices' active/local speakers |
| `person.<id>` | Display devices assigned to that person or in their current Area | Music Assistant speakers in that person's current Area, plus matching devices' active/local speakers |
| *(No match)* | Delivers nothing | No-op (never broadcasts to unoccupied Areas) |

---

## Notifications & Intercom

### `latter.notify`
Wakes target displays via `esphome.<node>_latter_show_notification`, shows an alert banner, optionally plays an embedded chime or speaks TTS, optionally attaches a signed camera snapshot, and fires `latter_event` (`type: notification_dispatched`).

| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `message` | string | **required** | Truncated to 160 characters on the device |
| `title` | string | `Notification` | Truncated to 48 characters |
| `priority` | `normal` \| `warning` \| `critical` | `normal` | |
| `duration` | int (seconds) | `8` | Clamped to 2–60 |
| `chime` | bool | `true` | Skipped when `announce: true` |
| `camera_entity` | `camera.*` | — | Mints a signed baseline-JPEG snapshot URL |
| `announce` | bool | `false` | Speaks `message` via TTS on the device's Assist satellite or local speaker |

### `latter.intercom_broadcast`
Broadcasts a TTS announcement (`message`) or local/media-source clip (`media_url`) across `target_speakers` (or `target_device` special targets) using `tts_entity` (defaults to the first `tts.*` entity). Uses `music_assistant.play_announcement` on Music Assistant players and `media_player.play_media` (`announce: true`) elsewhere.

---

## Media & Remotes

### `latter.set_active_speaker`
Selects `entity_id` (`media_player.*`, required) as the device's active speaker. With `transfer_queue: true` (default), transfers Music Assistant queues via `music_assistant.transfer_queue` (holding Now Playing metadata/art steady across spin-up) or pauses and replays `media_content_id` on standard players.

### `latter.media_command`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `command` | string | `toggle` | `play`, `pause`, `toggle`, `next`, `previous`, `stop`, `seek`, `clear_queue`, `play_media`, `join`, `unjoin` |
| `entity_id` | `media_player.*` | active speaker | If idle/cold with an empty Sendspin buffer, `play` automatically heals and re-streams the Music Assistant queue |
| `seek_position` | float (seconds) | — | For `seek` |
| `media_id`, `media_type`, `enqueue` | string | — | For `play_media` (expands unplayable artist/album URIs up to 25 tracks) |
| `group_members` | `media_player.*` list/CSV | — | Target speaker entities for `join` / `unjoin` speaker grouping |

### `latter.media_volume`
Adjusts volume (`action`: `set` \| `up` \| `down` \| `mute`, `volume_level`: `0–1` or `0–100`, optional `entity_id`), automatically routing through any Studio **Speaker Volume Override** (`media_player`, `number`, or `input_number`).

### `latter.music_browse`
Fetches a page of library items, speakers, queues, lyrics (Music Assistant → [LRCLIB](https://lrclib.net)), or bios (Music Assistant → Wikipedia) and pushes it to the device via `esphome.<node>_latter_set_slots` (`is_area_slots: false`), echoing `req_id` to discard stale rapid-tap responses.
- **Fields:** `mode` (`speakers`, `favorites`, `playlist`, `artist`, `album`, `radio`, `podcast`, `audiobook`, `track`, `artist_albums`, `album_tracks`, `current_album_tracks`, `active_queue`, `podcast_episodes`, `lyrics`, `bio`), `page` (`1`), `page_size` (`5`, capped to manifest `slot_count`), `search` (`Title|Artist|Album` for lyrics/bio), `speaker`, `last_speaker`, `album_sort` (`name` \| `year` \| `year_desc`), `artist_album_sort` (`year` \| `year_desc` \| `name`), `podcast_sort` (`newest` \| `oldest`), `req_id` (`0`).

### `latter.remote_action`
Sends a TV/AV remote action (`slot`: `1–10`, `action`: `select_slot` \| `toggle` \| `command` \| `volume_up` \| `volume_down` \| `volume_mute` \| `media_play_pause`, `command`: `up`, `down`, `left`, `right`, `select`, `back`, `home`, etc.), translating key codes automatically for Android TV, Fire TV, Bravia, Denon AVR, LG webOS, Apple TV, or generic `remote.send_command`.

---

## Areas & Home Hub

### `latter.set_active_area`
Switches the device's active Area (`area_id`, ID or name). Moves media along when **Media Follows This Device to Its New Area** is on, and updates the Home Assistant Device Area on roaming hardware (`stationary == 0`) when **Voice Follows Me** is enabled.

### `latter.area_browse`
Pushes paginated Areas (`mode: areas`) or controllable entities (`mode: entities` \| `home`) via `esphome.<node>_latter_set_slots` (`is_area_slots: true` for entity/home slider cards; `false` for Area lists).
- **Fields:** `mode` (`entities`), `area_id`, `domain_filter` (`all`, `scene`, `light`, `cover`, `fan`, `switch`, `climate`, `media`, or CSV), `page` (`1`), `page_size` (`3`–`6` cards or `5`–`7` list rows per manifest), `req_id` (`0`).

### `latter.area_action`
Executes an explicit Area or Home Hub control action.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `entity_id` | string | Any entity ID, or a Home Hub virtual target: **`home_hub.alarm`**, **`home_hub.thermostat`** *(or `home_hub.climate`)*, **`home_hub.lock`**, **`home_hub.garage`**, **`home_hub.vacuum`** |
| `action` | string | `toggle`, `turn_on`, `turn_off`, `set_level`, `set_color`, `set_kelvin`, `set_temperature`, `step_up`, `step_down`, `arm_home` / `alarm_arm_home`, `arm_away` / `alarm_arm_away`, `arm_night` / `alarm_arm_night`, `disarm` / `alarm_disarm`, `heat`, `cool`, `auto`, `off`, `lock`, `unlock`, `open`, `open_cover`, `close_cover`, `stop_cover`, `start`, `pause`, `dock` / `return_to_base` *(`lock` and `alarm_control_panel` reject `toggle`)* |
| `level` | number | `0–100` (brightness/position/fan speed), Kelvin (`set_kelvin`), or target temperature (`set_temperature`) |
| `code` | string | `#RRGGBB` (`set_color`), Home Assistant Alarm PIN, or Latter Security PIN |
| `area_id` | area | Optional Area scope |

**Separate Alarm PINs vs. Perimeter Security (`protocol.py`, `services.py`):**
- **Home Assistant Alarm Panels with a Code (`alarm_caps`):** when the target `alarm_control_panel` defines `code_format`, `disarm` (and `arm_*` when `code_arm_required` is true) validates `code` and passes it straight through to Home Assistant's alarm service. Arming is never blocked by `security_pin_policy: block`.
- **Locks, Garage/Gate Covers & Code-Less Alarms:** opening actions (`unlock`/`open`, opening garage/gate/door covers, and `disarm` on code-less alarms) enforce the calling Device's Studio **Perimeter Security Policy** (`allow`, `require_pin`, or `block`; `auto` resolves to `require_pin` on stationary panels or when an HA alarm code exists), verifying `code` in constant time against the PBKDF2-HMAC-SHA256 Device Security PIN (falling back to the System Security PIN).

---

## Calendar & Doorbell

- **`latter.calendar_fetch`** (`days: 1–60` default `30`, `page: 1`, `page_size: 5`, `req_id: 0`): deduplicates up to 25 upcoming events across configured calendars, signs OpenStreetMap `map_url`s for events with locations, and pushes slots via `latter_set_slots`.
- **`latter.calendar_create_event`** (`summary` required, optional `calendar_entity`, `start_date_time`, `end_date_time`, `in_minutes: 15`, `duration_minutes: 30`, `description`): creates an event and refreshes `calendar_agenda`.
- **`latter.doorbell_intercom`** *(experimental)* (`action`: `listen_start` \| `listen_stop` \| `listen_toggle` \| `talk_message` \| `quick_reply` \| `unlock_door` \| `call_target` \| `set_noise_reduction` \| `select_camera`, plus `camera_entity` / `camera_index`, `message`, `noise_reduction`: `strong` \| `light` \| `off`, `code`): streams noise-reduced camera audio as FLAC, speaks push-to-talk/quick replies via TTS on the camera's speaker, unlocks the door (`code` verified under `require_pin`), or rings other displays (`call_target`).

---

## Preferences, Appearance & Device Lifecycle

### `latter.save_custom_color` *(admin)*
Saves `hex_color` (`#RRGGBB`, optional `name`) into the 24-swatch System color library and applies it to the target device.

### `latter.shortcut_action` *(bound-device RPC / user)*
Executes a Home Assistant entity shortcut (`entity_id`, `action`, optional `code`) configured on the target device's **App Dock** (`dock_items`) or **Pinned App** (`pinned_items`), strictly enforcing the device's configured `(entity_id, action)` allowlist and `security_pin_policy` (`auto` / `allow` / `require_pin` / `block`) on perimeter locks, garage/gate/door covers, and security alarms.

### `latter.set_device_prefs` *(admin / bound-device RPC)*
Applies typed preference updates (`changes` dict, optional `base_seq`) to the Device's sleep-safe subentry (`studio/settings.py`), switching `device_group` to `custom` when an enforced baseline setting diverges, incrementing `prefs_seq`, and pushing the updated `device_prefs` Protocol v3 frame.

### `latter.reset_device` *(admin)*
Resets `target_device` (**required**; never falls back to a default device):
- `device_settings` (`true` default): calls `esphome.<node>_latter_factory_reset` (wipes NVS settings and restarts while keeping Wi-Fi and API pairing).
- `latter_options` (`true` default): resets Studio per-device settings back to onboarding defaults while preserving the bound ESPHome device, MAC, slug, and Music Assistant player link.

### `latter.device_hello` & `latter.timer_alarm_state` *(device-reported RPCs)*
- **`latter.device_hello`** (`contract`, `boot_id`, `manifest`, `prefs_seq`, `dirty_prefs`): handshake emitted by firmware on API connect and `latter_ping` to register Hardware Manifest v2, check boot health, reconcile offline NVS preference edits, and push fresh Protocol v3 domains.
- **`latter.timer_alarm_state`** (`timer_running`, `timer_paused`, `remaining_sec`, `ringing`): event-driven update emitted by firmware on timer/alarm transitions to drive `timer_active`, `timer_remaining` (1 Hz local tick), and `alarm_ringing` without background polling.
