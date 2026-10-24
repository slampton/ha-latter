# Latter (`ha-latter`)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=slampton&repository=ha-latter&category=integration)

**Universal Home Assistant companion middleware and dynamic entity-mapping platform for ESPHome devices.**

Flagship reference hardware: **[Pocket Assistant](https://github.com/slampton/esphome-pocket-assistant)** (Waveshare ESP32-S3-Touch-AMOLED-1.75C).

---

## Why Latter Exists

ESPHome devices—whether portable battery-powered smart displays, stationary wall panels, rotary knob controllers, or headless button/sensor nodes—should do as much as possible locally on the MCU. However, three limitations always hit complex ESPHome projects:

1. **The YAML Recompile Trap**: Users shouldn't have to edit YAML `substitutions:` and recompile C++ firmware for 10 minutes just to change a weather provider, swap a TV remote entity, map a hardware button, or add a speaker volume override.
2. **MCU RAM & Flash Limits**: Running an on-device `web_server`, decoding 2000×2000 progressive PNG/WebP album art, or sorting 500 Music Assistant library items on an ESP32 wastes precious PSRAM, flash, and battery.
3. **Cross-Integration Context**: A portable ESPHome device moving from room to room needs Home Assistant to track its BLE signal across room proxies, switch its active room controls, and update its Home Assistant Area assignment so saying *"Turn on the lights"* to the Voice Assistant controls the room you are standing in.

**Latter** solves all three on the Home Assistant server while exposing a clean, hardware-agnostic **ESPHome Wire Specification** over ESPHome's native Noise-encrypted API.

---

## Core Capabilities

- **Server-Side Web Companion Studio (`/api/latter/companion/<entry_id>`)**: Click **Visit** on your ESPHome device in Home Assistant to open a full Device Manager, Live BLE Signal Radar, 4-Slot Remote Mapper, AVR Volume Override Mapper, and Universal Hardware Trigger Mapper—zero on-device `web_server` overhead.
- **Native ESPHome BLE Proxy Room Tracking (`ble_engine.py`)**: Tracks your portable device's BLE iBeacon across fixed ESPHome `bluetooth_proxy` nodes (EMA RSSI smoothing, 5 dB hysteresis, instant wake lock after standby) with optional Bermuda BLE Trilateration override.
- **Live Two-Way Room Control & Environmental Telemetry (`room_engine.py`)**: Automatically discovers lights, window coverings, fans, climate, scenes, and smart outlets per room, subscribes to live state changes (`250ms` debounced push), and exposes ambient `room_temp` and `room_humidity`.
- **Music Assistant 2.10+ Library, Queue & Handoff Engine (`browse_engine.py`)**: Paginates speakers, favorites, playlists, artists, albums, tracks, active queues, and podcast episodes, and performs single-call `music_assistant.transfer_queue` handoffs with position verification.
- **Universal Baseline-JPEG Transcoder (`/api/latter/artwork/<device_slug>`)**: Converts any upstream image format (PNG, WebP, Progressive JPEG, GIF) into non-progressive Baseline JPEG sized to your screen (`?w=466&h=466&shape=circle`), backed by a 16-entry RAM LRU cache.
- **4-Slot Hybrid TV / Media Remote Adapter**: Automatically pairs sibling `remote.*` and `media_player.*` entities on the same device and translates navigation intents across Android TV (`DPAD_*`), Apple TV, Roku, LG webOS (`webostv.button`), and Denon/Marantz AVRs (`denonavr.get_command`).

---

## Installation

1. Click the **Open HACS Repository** badge above, or add `https://github.com/slampton/ha-latter` as a Custom Repository (Category: **Integration**) in HACS / Home Assistant Marketplace.
2. Download **Latter** and restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and search for **Latter** (or accept the automatic discovery card when your ESPHome device connects).
4. Click **Visit** on the Latter or ESPHome device page to open the **Latter Companion Studio**, or use **Configure** in Home Assistant.

---

## Public ESPHome Developer Wire Specification (`v1.4+`)

Any ESPHome project (custom C++ display, LVGL touchscreen, e-paper dashboard, or headless button/sensor node) can adopt Latter modularly. You only subscribe to the sensors or services your hardware needs.

### 1. Device-Scoped Sensors (`sensor.<device_slug>_*`)

When you configure Latter for an ESPHome device named `kitchen-panel` (slug `kitchen_panel`) or `pocket-assistant` (slug `pocket_assistant`), Latter creates 5 push-updated sensors:

| Entity ID | State | Key Attributes |
| :--- | :--- | :--- |
| `sensor.<slug>_active_media` | `playing` \| `paused` \| `idle` \| `buffering` \| `off` | `title`, `artist`, `album`, `duration`, `position` (2s idle-guarded only while playing), `volume` (`0.0..1.0`), `media_type`, `supported_features`, `art_url`, `active_speaker`, `last_speaker`, `local_speaker`, `volume_entity` |
| `sensor.<slug>_room_context` | Active Room Name (e.g. `Living Room`) | `area_id`, `area_name`, `room_temp`, `room_humidity`, `lights_on`, `covers_open`, `entity_count`, `area_speaker`, `area_remote`, `alarm_entity`, `alarm_state`, `alarm_code_required`, `dock_apps`, `wallpaper_url`, `companion_url`, `entities_summary` |
| `sensor.<slug>_weather_forecast` | `MON:72:55:sunny;TUE:68:52:cloudy;...` (5 days) | `condition`, `temperature`, `humidity`, `wind_speed`, `wind_bearing`, `high`, `low`, `weather_entity` |
| `sensor.<slug>_remote_config` | Active Remote Name | `active_slot` (`1..4`), `configured_count`, `slot_1..4_name`, `slot_1..4_remote`, `slot_1..4_media_player`, `slot_1..4_state`, `slots_summary` |
| `sensor.<slug>_calendar_agenda` | `TODAY 14:30\|Dentist;TOM 09:00\|Standup;...` | `event_count`, `events`, `calendars` |

### 2. Baseline-JPEG HTTP Endpoints (For `online_image`)

ESPHome's `online_image` JPEG decoder requires non-progressive Baseline JPEGs. Latter provides two fast LAN endpoints (cached in RAM):

- **Album / Podcast Artwork**:
  `http://<ha_ip>:8123/api/latter/artwork/<device_slug>?w=466&h=466&shape=circle&v=<hash>`
  *(Automatically published in the `art_url` attribute of `sensor.<slug>_active_media`)*
- **Pre-Masked Photo Wallpaper**:
  `http://<ha_ip>:8123/api/latter/wallpaper/<device_slug>?w=466&h=466&shape=circle&v=<hash>`
  *(Automatically published in the `wallpaper_url` attribute of `sensor.<slug>_room_context`)*

### 3. ESPHome Inbound Pagination Callbacks (`api.services`)

To display paginated lists or room controls without storing large arrays in MCU RAM, expose one or both of these services in your ESPHome YAML under `api: services:`. Latter automatically inspects your service schema to detect how many slots (`s1` .. `sN`, from `1` to `20`) your GUI supports!

#### A. `set_browse_slots` (5-Slot Compact List Callback — Music, Room Picker `room_areas`, Calendar)
```yaml
api:
  services:
    - service: set_browse_slots
      variables:
        mode: string
        page: int
        total_pages: int
        has_prev: bool
        has_next: bool
        s1_name: string
        s1_id: string
        s1_type: string
        s1_active: bool
        # Repeat s2_* through s5_* (or up to s20_* for large wall panels)
```

#### B. `set_room_slots` (3-Slot Interactive Control Card Callback — Room Entities & Home Alarm)
Includes `sX_level` (`0..100` for slider-capable domains `light`, `cover`, `fan`; `-1` for toggle/button domains `scene`, `switch`, `climate`, `media_player`, `alarm_control_panel`):
```yaml
api:
  services:
    - service: set_room_slots
      variables:
        mode: string
        page: int
        total_pages: int
        has_prev: bool
        has_next: bool
        s1_name: string
        s1_id: string
        s1_type: string
        s1_active: bool
        s1_level: int
        # Repeat s2_* through s3_* (or up to s20_*; falls back to set_browse_slots if omitted)
```

### 4. Outbound Actions (`homeassistant.action` -> `latter.*`)

Call any of Latter's 12 services from ESPHome using `homeassistant.action:`:

| Service | Purpose & Parameters |
| :--- | :--- |
| `latter.room_browse` | Browse rooms or room entities. `mode`: `"areas"` (pushes 5-row page to `set_browse_slots`), `"entities"` (pushes 3-card page with `level` to `set_room_slots`), or `"home"` (alarm + pinned entities). `domain_filter`: `"all"`, `"light"`, `"cover,fan"`, `"scene"`, `"climate"`. `page`: `1..N`. |
| `latter.room_action` | Control any room entity or home alarm. `entity_id`, `action`: `"toggle"`, `"turn_on"`, `"turn_off"`, `"set_level"`, `"step_up"`, `"step_down"`, `"arm_home"`, `"arm_away"`, `"arm_night"`, `"disarm"`. Optional `level` (`0..100`), `code`. |
| `latter.set_active_area` | Switch the device's active room by `area_id` or room name (`area`) and sync the ESPHome device's Home Assistant Area for room-aware Voice Assistant. |
| `latter.music_browse` | Browse Music Assistant (`mode`: `"speakers"`, `"favorites"`, `"playlist"`, `"artist"`, `"album"`, `"radio"`, `"podcast"`, `"audiobook"`, `"track"`, `"artist_albums"`, `"album_tracks"`, `"current_album_tracks"`, `"active_queue"`, `"podcast_episodes"`). Pushes 5-row page to `set_browse_slots`. |
| `latter.set_active_speaker` | Switch `active_speaker` (`entity_id`) and automatically transfer the active Music Assistant queue (`transfer_queue: true`). |
| `latter.media_command` | Transport control (`command`: `"play"`, `"pause"`, `"toggle"`, `"next"`, `"previous"`, `"stop"`, `"seek"`, `"play_media"`, `"clear_queue"`). Includes post-reboot local Sendspin queue resumption. |
| `latter.media_volume` | Adjust volume (`action`: `"set"`, `"up"`, `"down"`, `"mute"`, `volume_level`: `0..100`), routing automatically to mapped AVR / `number.*` volume overrides. |
| `latter.remote_action` | Control 4-slot TV/Media remotes (`slot`: `1..4`, `action`: `"select_slot"`, `"toggle"`, `"volume_up"`, `"volume_down"`, `"volume_mute"`, `"command"`, `command`: `"up"`, `"down"`, `"left"`, `"right"`, `"select"`, `"back"`, `"home"`, `"menu"`). |
| `latter.trigger_binding` | For headless buttons, rotary encoders, or custom touch macros: send `slot: "button_1_single"` and Latter executes whatever entity + action the user mapped in the Web Companion Studio. |
| `latter.calendar_fetch` | Refresh upcoming calendar events (`days`: `7`, `page`: `1`) and push a 5-row page to `set_browse_slots`. |
| `latter.calendar_create_event` | Create a new event (`summary`, `start_date_time`, `end_date_time`) on the primary family calendar. |
| `latter.intercom_broadcast` | Broadcast a TTS `message` or `media_url` announcement across household speakers. |

---

## Convention-Over-Configuration for ESPHome Device Controls

When you open the **ESPHome Device Manager** tab in the Latter Web Companion Studio, Latter automatically organizes all entities exposed by your ESPHome firmware:
- Prefix any ESPHome entity name with `"Category: Name"` (e.g., `"Display: Brightness"`, `"Sleep & Wake: Timeout"`, `"Voice: Wake Word"`, or your own custom `"Hydroponics: Pump Mode"`) and Latter dynamically creates a dedicated navigation category for it!
- Entities without a prefix are semantically grouped by domain/device_class, with a `"General & Custom Entities"` spillover bucket so custom project entities are always accessible.

---

## Support the Project

Latter and Pocket Assistant are built and maintained by Sean Lampton (**Lampton Labs**). If this project is useful in your home and you'd like to support ongoing development:

* ☕ **[Buy Me a Coffee](https://www.buymeacoffee.com/slampton)**
* ❤️ **[Sponsor on GitHub](https://github.com/sponsors/slampton)**