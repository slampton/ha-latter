# Latter — Universal ESPHome Companion & Room Fabric for Home Assistant

[![Release](https://img.shields.io/badge/version-2.2.2-blue.svg)](https://github.com/slampton/ha-latter/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Quality Scale](https://img.shields.io/badge/Quality%20Scale-Platinum-E5E4E2.svg)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
[![HACS](https://img.shields.io/badge/HACS-Custom%20%2F%20Default-orange.svg)](https://hacs.xyz/)

**Latter** (`custom_components/latter`) is an asynchronous, zero-dependency Home Assistant middleware integration and web studio that turns **any ESPHome device**—from flagship AMOLED handhelds and smartwatches to 1-line mixin nodes and existing off-the-shelf presence sensors—into a room-aware, dynamically mapped smart home companion.

Instead of hardcoding entity IDs in ESPHome YAML and recompiling firmware every time you add a light, speaker, or TV, Latter provides a dynamic entity-mapping contract, a native Bluetooth room-presence calibration radar, an on-demand Baseline-JPEG artwork/camera/map transcoder, and a built-in **Latter Studio** sidebar panel.

---

## Key Features & Supported Functions

1. **3-Tier Universal ESPHome Device Model**:
   - **Tier 1 (Flagship Native Displays)**: Zero-YAML auto-discovered smart displays such as **[Pocket Assistant](https://github.com/slampton/esphome-pocket-assistant)** (`466x466` round AMOLED) and **[Wrist Assist](https://github.com/slampton/esphome-wrist-assist)** (`410x502` rectangular watch) powered by **[esphome-latter-core](https://github.com/slampton/esphome-latter-core)**.
   - **Tier 2 (1-Line Drop-In Mixin Nodes)**: Upgrade any existing ESPHome YAML with a single line from `esphome-latter-core/mixins/*.yaml` to add BLE room beaconing (`ble_beacon.yaml`), stationary BLE proxy scanning (`ble_proxy.yaml`), WireGuard roaming VPN (`roaming_vpn.yaml`), or Studio diagnostics (`diagnostics.yaml`).
   - **Tier 3 (Zero-YAML Bridged Devices)**: Bridge any existing ESPHome device (e.g., Everything Presence One, Bed Presence, Home Assistant Voice PE) in 1 click from **Latter Studio &rarr; System &rarr; Overview &amp; Devices** to organize groups, inspect live entities, and back up device preferences.
2. **Native BLE Proxy Room Presence & Site Survey Radar**:
   - Tracks roaming ESPHome BLE iBeacons across your home's ESPHome Bluetooth Proxies, bypassing static-beacon deduplication via 2-second per-scanner advertisement table polling, Exponential Moving Average (EMA) smoothing, per-room dB calibration offsets, and 1-click **"Prioritize Here"** calibration.
   - Automatically syncs the active room to the ESPHome device's Home Assistant Area assignment so room-aware **Assist** voice commands (*"turn on the lights"*) target the room you are standing in.
3. **Music Assistant 2.10+ Browse, Queue Transfer & Lyrics/Bio Engine**:
   - Paginates Music Assistant libraries (Favorites, Playlists, Artists, Albums, Tracks, Podcasts, Radio, Audiobooks, Active Queue), fetches synced track lyrics and artist/album biographies (via Music Assistant metadata, LRCLIB, and Wikipedia fallbacks), and performs seamless speaker-to-speaker queue transfers.
4. **Area-Aware Room Control & Whole-Home Hub**:
   - Curates room entities by domain (`scene`, `light`, `cover`, `fan`, `switch`, `media_player`, `climate`) and pushes 3-card or 5-slot pages with live brightness/cover/fan levels (`0..100%`), RGB color wheel & Kelvin temperature control, and shared Whole-Home Hub state (Security Alarm, Primary Thermostat, Entry Lock, Garage Door, Robot Vacuum, and Doorbell Camera).
5. **Local LAN Baseline-JPEG Transcoder (Artwork, Wallpapers, Camera Peephole & OpenStreetMap)**:
   - Transcodes progressive PNG/WebP/JPEG album art, custom wallpapers, live `camera.*` snapshots, and multi-tile OpenStreetMap event location maps into memory-safe **Baseline RGB565 JPEG** sized to each device's exact display geometry (`466x466` circle or `410x502` rectangle).
6. **System & Device Backup Vault, Reusable Profiles & Roaming WireGuard Provisioning**:
   - Create full System or per-device snapshots (including live ESPHome `select`, `switch`, and `number` preferences) in `.storage/latter.backups` or download/restore portable `.JSON` bundles.
   - Generate RFC 7748 Curve25519 WireGuard keypairs and copy-pasteable ESPHome roaming VPN configurations in 1 click.

---

## Supported Devices

- **Flagship Companion Displays**:
  - **Pocket Assistant**: Waveshare ESP32-S3-Touch-AMOLED-1.75C (`466x466` Round QSPI AMOLED, ES8311 DAC, ES7210 dual-mic array, AXP2101 PMU, QMI8658 IMU).
  - **Wrist Assist**: Waveshare ESP32-S3-Touch-AMOLED-2.06 (`410x502` Rectangular Watch QSPI AMOLED, FT3168 touch, ES8311 DAC, ES7210 mic ADC, AXP2101 PMU, QMI8658 IMU).
- **Any ESP32 / ESP32-S3 / ESP32-C3 / ESP32-C6 / ESP32-P4 ESPHome Node**:
  - Works with any ESPHome device via 1-line mixins (`esphome-latter-core/mixins/*.yaml`) or 1-click Zero-YAML bridging in Latter Studio.

---

## Installation Instructions

### Option 1: HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the three dots in the top-right corner and select **Custom repositories** (or search for **Latter** directly once listed in the default catalog).
3. Add `https://github.com/slampton/ha-latter` with category **Integration**.
4. Click **Download**, then restart Home Assistant.

### Option 2: Manual Installation
1. Copy the `custom_components/latter` folder from this repository into your Home Assistant `/config/custom_components/latter` directory.
2. Restart Home Assistant.

---

## Configuration & Onboarding Parameters

Latter automatically discovers compatible ESPHome devices on your network. You can also add a device manually via **Settings &rarr; Devices &amp; Services &rarr; Add Integration &rarr; Latter**:

| Parameter | Description |
| :--- | :--- |
| **ESPHome Device Name / Slug** (`device_slug`) | The normalized name of your ESPHome node (e.g., `pocket_assistant` or `wrist_assist`). |
| **Configuration Profile** (`apply_profile`) | Defaults to **Auto-Detect from Device Hardware** (automatically configures `466x466` round for Pocket Assistant, `410x502` square/rect for Wrist Assist, or headless sensor defaults), or applies any saved reusable profile. |
| **This device roams** (`native_ble_tracking`) | Enable for portable/wearable devices that move between rooms. Uncheck for stationary devices fixed to a single Area. |

Once added, open **Latter** from the Home Assistant sidebar (or click **Visit** on the ESPHome device page) to configure shared household entities (Security Alarm, Primary Camera, Weather Provider, Primary Thermostat, Entry Lock, Garage Door, Robot Vacuum, Calendars, 4-Slot TV Remotes, and Volume Routing).

---

## Exposed Entities & Data Update Model

Latter uses a **local push (`local_push`)** coordinator model with an idle-guarded timer:
- Each onboarded device exposes 5 device-scoped sensors linked directly to the ESPHome device entry:
  1. `sensor.<device_slug>_active_media`: Active speaker playback state and track attributes. Uses an **idle-guarded 2-second position timer** that runs *only* while media is actively playing, plus `_unrecorded_attributes` to prevent SQLite database bloat.
  2. `sensor.<device_slug>_room_context`: Active room name, room temperature/humidity, curated entity counts, and live Whole-Home Hub states (Alarm, Thermostat, Lock, Garage, Vacuum, Alert/Notification state).
  3. `sensor.<device_slug>_weather_forecast`: Semicolon-delimited 5-day forecast string (`DAY:HIGH:LOW:COND;...`) refreshed every 30 minutes and on weather state changes.
  4. `sensor.<device_slug>_calendar_agenda`: Upcoming family calendar events refreshed every 15 minutes, with automatic geocoded OpenStreetMap snapshot URLs for events with locations.
  5. `sensor.<device_slug>_remote_config`: Active TV/AVR remote slot and 4-slot entity pairings.

---

## Actions (Services) & Examples

### 1. Send a Doorbell / Camera Peephole Alert (`latter.notify_device`)
```yaml
action: latter.notify_device
data:
  target_device: "pocket_assistant"
  title: "Front Door"
  message: "Person detected at the front porch"
  priority: "critical"
  duration: 12
  chime: true
  camera_entity: "camera.front_door_bell"
```

### 2. Broadcast a Household Intercom Announcement (`latter.intercom_broadcast`)
```yaml
action: latter.intercom_broadcast
data:
  message: "Dinner is ready in the kitchen!"
```

### 3. Trigger a Custom Hardware Macro Slot (`latter.trigger_binding`)
```yaml
action: latter.trigger_binding
data:
  target_device: "wrist_assist"
  slot: "macro_1"
```

---

## Troubleshooting & Known Limitations

- **ESP32 Artwork / Camera Snapshots Not Loading**:
  - ESP-IDF's `http_request` client on ESP32 cannot resolve `.local` mDNS hostnames without a local DNS proxy and requires **Baseline JPEG** (non-progressive). Latter automatically resolves Home Assistant's numeric LAN IPv4 address and transcodes all images to Baseline JPEG via `/api/latter/{artwork,wallpaper,camera,map}/<device_slug>`.
- **BLE Room Presence Not Switching Rooms**:
  - Ensure your stationary ESPHome nodes have `bluetooth_proxy: active: true` (or include `github://slampton/esphome-latter-core/mixins/ble_proxy.yaml@main`) and are assigned to a Home Assistant **Area**. Open **Latter Studio &rarr; System &rarr; Room Calibration** to inspect live Raw dBm vs. Effective dBm per room and click **Prioritize Here**.
- **Known Limitations**:
  - Music library browsing (`favorites`, `playlist`, `artist`, `album`, `podcast`, `audiobook`, `active_queue`) requires the **Music Assistant** integration to be loaded in Home Assistant. Basic transport controls (`play`, `pause`, `next`, `previous`, `volume`) work with any Home Assistant `media_player.*` entity.

---

## Removal Instructions

1. In Home Assistant, navigate to **Settings &rarr; Devices &amp; Services &rarr; Latter**.
2. Click the three dots next to each configured device entry and select **Delete**.
3. If installed via HACS, open **HACS &rarr; Integrations &rarr; Latter**, click the three dots, and select **Remove**, then restart Home Assistant.
