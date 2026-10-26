# Latter (`ha-latter`)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=slampton&repository=ha-latter&category=integration)
[![Version](https://img.shields.io/badge/Version-v2.1.0-03a9f4.svg)](https://github.com/slampton/ha-latter/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10.0%2B-41BDF5.svg)](https://www.home-assistant.io)
[![Quality Scale](https://img.shields.io/badge/Quality%20Scale-Platinum%20Target-brightgreen.svg)](custom_components/latter/quality_scale.yaml)

**Universal Home Assistant companion middleware, dynamic entity-mapping platform, and room/site fabric for ESPHome devices.**

Flagship reference hardware: **[Pocket Assistant (`v2.1.0+`)](https://github.com/slampton/esphome-pocket-assistant)** (Waveshare ESP32-S3-Touch-AMOLED-1.75C).

---

## Why Latter Exists

ESPHome devices—whether portable battery-powered smart displays, stationary wall panels, rotary knob controllers, or headless button/sensor nodes—should do as much as possible locally on the MCU. However, three limitations always hit sophisticated ESPHome projects:

1. **The YAML Recompile Trap**: Users shouldn't have to edit YAML `substitutions:` and recompile C++ firmware just to change a weather provider, swap a TV remote entity, map a macro button, or add an AV receiver volume override.
2. **MCU RAM & Flash Limits**: Running an on-device `web_server`, decoding progressive PNG/WebP album art, rendering OpenStreetMap tiles, or sorting 500 Music Assistant library items on an ESP32 wastes PSRAM, flash, and battery.
3. **Cross-Integration Context & Multi-Device Management**: A portable ESPHome device moving from room to room needs Home Assistant to track its BLE signal across room proxies, switch its active room controls, and update its Home Assistant Area assignment so saying *"Turn on the lights"* to Assist targets the room you are standing in—while multiple devices across your home need shared entity mappings, reusable profiles, and 1-click backup/restore.

**Latter** solves all three on the Home Assistant server while exposing a clean, hardware-agnostic **ESPHome Wire Specification (`v2.1+`)** over ESPHome's native Noise-encrypted API.

---

## Core Capabilities in v2.1.0

- **Native Home Assistant Sidebar Panel (`Latter Studio`)**: Registers a native `Latter` panel in the Home Assistant sidebar (inheriting your active HA dark/light/custom theme variables) with dual **System** and **Device** scopes—zero on-device `web_server` overhead.
- **System & Device Backup & Restore (`backup_engine.py`)**:
  - **Dual Scope**: Back up your entire **System** (`.storage/latter.household` shared entities, BLE room calibration offsets, 4-slot remotes, AVR volume routing, custom color palettes, macro bindings, device groups, reusable profiles, and all devices) or an individual **Device** (including a live snapshot of all configurable ESPHome `select`, `switch`, and `number` entities).
  - **Internal Snapshot Vault & Computer `.JSON` Export/Import**: Save up to 25 restore points in `.storage/latter.backups`, download `.json` backup bundles to your computer, upload `.json` files to restore, or clone a device snapshot onto a replacement ESPHome node.
- **Device Groups & Reusable Configuration Profiles**: Organize devices into logical groups (*Handheld Displays*, *Bedrooms*, *Common Areas*, *Wall Panels*, or custom groups), capture a device's complete settings + ESPHome preferences as a reusable **Profile** (or use built-in starter profiles), and apply profiles or live controls across a single device, a group, or all devices in 1 click.
- **Native ESPHome BLE Proxy Room Tracking & 1-Tap Calibration (`ble_engine.py`)**: Tracks your portable device's BLE iBeacon across fixed ESPHome `bluetooth_proxy` nodes (EMA RSSI smoothing, 5 dB hysteresis, log-distance estimation) with a live **Site Survey** UI and **1-Tap `Prioritize Here`** per-room dB offset calibration.
- **Live Two-Way Room & Whole-Home Control (`room_engine.py`)**: Automatically discovers scenes, lights (including RGB color & `2000K–6500K` Kelvin control), window coverings (blinds/curtains), fans, switches, room media, and whole-home entities (alarm, thermostat, garage/locks, robot vacuum), pushing debounced (`250ms`) slot updates and ambient `room_temp` / `room_humidity`.
- **Music Assistant 2.10.8+ Library, Queue, Lyrics & Bio Engine (`browse_engine.py`)**: Paginates speakers, favorites, playlists, artists, albums, tracks, active queues, podcast episodes, **time-synced/plain track lyrics**, and **artist/album biographies** (via Music Assistant + LRCLIB/Wikipedia fallback), plus single-call `music_assistant.transfer_queue` handoffs and post-reboot Sendspin queue recovery.
- **Baseline-JPEG Transcoders (`/api/latter/{artwork|wallpaper|camera|map}/<device_slug>`)**: Converts album art, custom/preset wallpapers, live `camera.*` snapshots, and **OpenStreetMap** event location tiles (with zoom `z=10..18` and `pan_x`/`pan_y` support) into non-progressive Baseline JPEGs sized and bezel-masked for your display.
- **4-Slot Hybrid TV / Media Remote & AVR Volume Router**: Automatically pairs sibling `remote.*` and `media_player.*` entities and translates navigation commands across Android TV (`DPAD_*`), Apple TV, Roku, Samsung TV, LG webOS (`webostv.button`), and Denon/Marantz AVRs (`denonavr.get_command`).
- **Roaming WireGuard VPN Provisioner (`vpn_engine.py`)**: Generates RFC 7748 Curve25519 WireGuard keypairs and copy-pasteable ESPHome + WireGuard server peer snippets so portable ESPHome devices stay connected over a phone hotspot away from home.

---

## Installation

1. Click the **Open HACS Repository** badge above, or add `https://github.com/slampton/ha-latter` as a Custom Repository (Category: **Integration**) in HACS.
2. Download **Latter** and restart Home Assistant.
3. Latter automatically discovers compatible ESPHome devices under **Settings -> Devices & Services** (or click **Add Integration -> Latter**).
4. Open **Latter** from the Home Assistant sidebar (or click **Visit** on the device page) to launch **Latter Studio**.

---

## Public ESPHome Developer Wire Specification (`v2.1+`)

Any ESPHome project (custom C++ display, LVGL panel, e-paper dashboard, or headless button/sensor node) can adopt Latter modularly.

### 1. Device-Scoped Sensors (`sensor.<device_slug>_*`)

| Entity ID | State | Key Attributes |
| :--- | :--- | :--- |
| `sensor.<slug>_active_media` | `playing` \| `paused` \| `idle` \| `buffering` \| `off` | `title`, `artist`, `album`, `duration`, `position` (2s idle-guarded + 4.5s transfer hold), `volume` (`0.0..1.0`), `media_type`, `supported_features`, `art_url`, `active_speaker`, `last_speaker`, `local_speaker`, `volume_entity` |
| `sensor.<slug>_room_context` | Active Room Name | `site_id`, `area_id`, `area_name`, `available_domains` (`scene,light,cover,fan,switch,media`), `room_temp`, `room_humidity`, `alarm_entity`, `alarm_state`, `ble_closest_proxy`, `ble_packets_seen`, `ble_rssi_by_room`, `ble_room_offsets`, `dock_apps`, `wallpaper_url`, `camera_snapshot_url`, `alert_*`, `custom_bindings_summary`, `theme_color_hex`, `custom_palettes`, `vpn_enabled`, `vpn_client_ip` |
| `sensor.<slug>_weather_forecast` | `MON:72:55:sunny;TUE:68:52:cloudy;...` (5 days) | `condition`, `temperature`, `humidity`, `wind_speed`, `wind_bearing`, `high`, `low`, `weather_entity` |
| `sensor.<slug>_remote_config` | Active Remote Name | `active_slot` (`1..4`), `configured_count`, `slot_1..4_name`, `slot_1..4_remote`, `slot_1..4_media_player`, `slot_1..4_state`, `slots_summary` |
| `sensor.<slug>_calendar_agenda` | `TODAY 14:30\|Dentist;TOM 09:00\|Standup;...` | `event_count`, `events`, `calendars` |

### 2. Baseline-JPEG HTTP Endpoints (For `online_image`)

- **Album / Podcast Artwork**: `/api/latter/artwork/<device_slug>?w=466&h=466&v=<hash>`
- **Photo & Preset Wallpapers**: `/api/latter/wallpaper/<device_slug>?w=466&h=466&shape=circle&v=<hash>`
- **Live Camera Snapshots**: `/api/latter/camera/<device_slug>?entity_id=camera.front_door&w=466&h=466&shape=circle&v=<ts>`
- **Interactive OpenStreetMap Snapshots**: `/api/latter/map/<device_slug>?w=466&h=466&shape=circle&q=<location>&z=15&pan_x=0&pan_y=0`

### 3. ESPHome Inbound API Actions (`api: actions:`)

Expose any of these actions under `api: actions:` in your ESPHome YAML (Latter auto-detects slot capacity `s1`..`s20`):

- **`set_browse_slots`**: 5-slot (up to 20-slot) paginated list callback for Music (`speakers`, `favorites`, `playlist`, `artist`, `album`, `podcast`, `radio`, `audiobook`, `active_queue`, `lyrics`, `bio`), Room Picker (`room_areas`), and Calendar (`calendar_agenda`).
- **`set_room_slots`**: Interactive room entity callback including `sX_level` (`0..100` for `light`, `cover`, `fan`; `-1` for toggle/scene domains).
- **`show_notification`**: Optional direct push toast & camera peephole alert callback (`title`, `message`, `priority`, `duration`, `chime`, `camera_url`).

### 4. Outbound Latter Services (`homeassistant.action` -> `latter.*`)

| Service | Purpose |
| :--- | :--- |
| `latter.music_browse` | Paginate Music Assistant (`speakers`, `favorites`, `playlist`, `artist`, `album`, `radio`, `podcast`, `audiobook`, `track`, `artist_albums`, `album_tracks`, `current_album_tracks`, `active_queue`, `podcast_episodes`, `lyrics`, `bio`). |
| `latter.set_active_speaker` | Switch `active_speaker` (`entity_id`) and optionally transfer the active Music Assistant queue (`transfer_queue`). |
| `latter.media_command` | Unified playback transport (`play`, `pause`, `toggle`, `next`, `previous`, `stop`, `seek`, `play_media`, `clear_queue`) with post-reboot Sendspin queue recovery. |
| `latter.media_volume` | Adjust speaker volume (`set`, `up`, `down`, `mute`), automatically routing to mapped AVR / `number.*` overrides. |
| `latter.room_browse` | Paginate rooms (`mode: "areas"`), room entities (`mode: "entities"`, `domain_filter: "scene"\|"light"\|"cover"\|"fan"\|"switch"\|"media"\|"all"`), or home-wide entities (`mode: "home"`). |
| `latter.room_action` | Execute room, light color/Kelvin (`set_color`, `set_kelvin`), or whole-home actions (`arm_home`, `arm_away`, `disarm`, `heat`, `cool`, `auto`, `off`, `lock`, `unlock`, `start`, `pause`, `dock`). |
| `latter.set_active_area` | Switch active room context (`area`), sync ESPHome Device Registry Area for Assist, and honor `handoff_media`. |
| `latter.remote_action` | Select a remote slot (`1..4`) or dispatch a protocol-translated remote command. |
| `latter.trigger_binding` | Execute user-mapped macro or hardware button bindings (`macro_1`..`macro_5`). |
| `latter.calendar_fetch` | Refresh upcoming family calendar events (`days`: `1..60`) and push paginated slots. |
| `latter.calendar_create_event` | Create a calendar event or relative quick reminder (`summary`, `in_minutes`, `duration_minutes` or `start_date_time`, `end_date_time`). |
| `latter.intercom_broadcast` | Broadcast a TTS `message` or `media_url` announcement across household speakers. |
| `latter.notify_device` | Push a toast alert, chime, and optional live `camera_entity` peephole snapshot to the ESPHome display. |
| `latter.save_custom_color` | Save a `#RRGGBB` hex color into the shared Household Color Library and apply it to the device. |

---

## Support the Project

Latter and Pocket Assistant are built and maintained by Sean Lampton (**Lampton Labs**). If this project is useful in your home and you'd like to support ongoing development:

* ☕ **[Buy Me a Coffee](https://www.buymeacoffee.com/slampton)**
* ❤️ **[Sponsor on GitHub](https://github.com/sponsors/slampton)**