# Latter — Universal ESPHome Companion & Room Fabric for Home Assistant

[![Validate](https://github.com/slampton/ha-latter/actions/workflows/validate.yml/badge.svg)](https://github.com/slampton/ha-latter/actions)
[![Version](https://img.shields.io/badge/Version-v2.2.0-blue)](https://github.com/slampton/ha-latter/releases)
[![Quality Scale](https://img.shields.io/badge/Quality%20Scale-Platinum-E5E4E2)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
[![ESPHome](https://img.shields.io/badge/ESPHome-2026.10.0%2B-blue?logo=esphome&logoColor=white)](https://esphome.io)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io)
[![Music Assistant](https://img.shields.io/badge/Music%20Assistant-2.10.8%2B-purple)](https://music-assistant.io)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/slampton)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-%E2%9D%A4-ea4aaa?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/slampton)

**Latter** (`custom_components/latter`) is an asynchronous, zero-dependency Home Assistant middleware integration and web studio that turns **any ESPHome device**—from flagship AMOLED handhelds and smartwatches to 1-line mixin nodes and existing off-the-shelf presence sensors—into a room-aware, dynamically mapped smart home companion.

Instead of hardcoding entity IDs in ESPHome YAML and recompiling firmware every time you buy a smart light, speaker, or TV, Latter provides a dynamic entity-mapping contract, a native Bluetooth room-presence calibration radar, an on-demand Baseline-JPEG artwork/camera/map transcoder, and a built-in **Latter Studio** sidebar panel.

---

## Part of the Latter Ecosystem

| Repository | Role in the Ecosystem |
| :--- | :--- |
| 👉 **[Latter (`ha-latter`)](https://github.com/slampton/ha-latter)** | **Home Assistant Middleware & Web Studio (You Are Here)** — Zero-YAML entity mapping, BLE room presence radar, Music Assistant browser, Baseline-JPEG transcoder, and backup vault. |
| **[Latter Core (`esphome-latter-core`)](https://github.com/slampton/esphome-latter-core)** | **Shared ESPHome OS, Device Catalog & 1-Line Mixin SDK** — Modular C++20 UI engine, board HALs (`boards/`), turnkey device configs (`devices/` for **Pocket Assistant**, **Mobile Assistant**, **Wrist Assist**, **Remote Assistant**, and **Desk Assistant**), and 1-line drop-in mixins. |

---

## Documentation & Deep-Dive Guides

- 📖 **[Everyday User & Studio Guide (`docs/USER_GUIDE.md`)](docs/USER_GUIDE.md)** — Navigating Latter Studio, mapping Shared Household Entities (Alarm, Camera, Weather, Thermostat, Lock, Garage, Vacuum, Calendars), setting up 4-Slot TV Remotes & AVR Volume Routing, uploading Wallpapers, and using Device Groups, Profiles & Backups.
- 📡 **[BLE Room Calibration & Roaming VPN Guide (`docs/BLE_AND_VPN_GUIDE.md`)](docs/BLE_AND_VPN_GUIDE.md)** — Placing ESPHome BLE proxies, using the live Site Survey radar & *"Prioritize Here"* calibration, syncing room context with Assist, and provisioning 1-click WireGuard roaming over phone hotspots.
- ⚡ **[Services & Automations Cookbook (`docs/SERVICES_AND_AUTOMATIONS.md`)](docs/SERVICES_AND_AUTOMATIONS.md)** — Copy-pasteable Home Assistant automation recipes for Doorbell Camera Peephole Alerts (`latter.notify_device`), Family Intercom (`latter.intercom_broadcast`), and Custom Macro Buttons (`latter.trigger_binding`).
- 🛠️ **[Developer API Contract & Hardware Porting (`esphome-latter-core/docs/`)](https://github.com/slampton/esphome-latter-core/tree/main/docs)** — How to build your own custom ESPHome display or sensor node for Latter.

---

## Key Features & Supported Functions

1. **3-Tier Universal ESPHome Device Model**:
   - **Tier 1 (Flagship Native Displays)**: Zero-YAML auto-discovered smart displays including **[Pocket Assistant](https://github.com/slampton/esphome-latter-core/blob/main/devices/pocket-assistant.yaml)** (`466×466` round AMOLED), **[Mobile Assistant](https://github.com/slampton/esphome-latter-core/blob/main/devices/mobile-assistant.yaml)** (`480×480` square AMOLED), **[Wrist Assist](https://github.com/slampton/esphome-latter-core/blob/main/devices/wrist-assist.yaml)** (`410×502` watch), **[Remote Assistant](https://github.com/slampton/esphome-latter-core/blob/main/devices/remote-assistant.yaml)** (`320×480` P4 handheld), and **[Desk Assistant](https://github.com/slampton/esphome-latter-core/blob/main/devices/desk-assistant.yaml)** (`720×720` P4 panel).
   - **Tier 2 (1-Line Drop-In Mixin Nodes)**: Upgrade any existing ESPHome YAML with a single line from `esphome-latter-core/mixins/*.yaml` to add BLE room beaconing (`ble_beacon.yaml`), stationary BLE proxy scanning (`ble_proxy.yaml`), WireGuard roaming VPN (`roaming_vpn.yaml`), or Studio diagnostics (`diagnostics.yaml`).
   - **Tier 3 (Zero-YAML Bridged Devices)**: Bridge any existing ESPHome device (e.g., Everything Presence One, Bed Presence, Home Assistant Voice PE) in 1 click from **Latter Studio &rarr; System &rarr; Overview &amp; Devices** to organize groups, inspect live entities, and back up device preferences.
2. **Native BLE Proxy Room Presence & Site Survey Radar**:
   - Tracks roaming ESPHome BLE iBeacons across your home's ESPHome Bluetooth Proxies, bypassing static-beacon deduplication via 2-second per-scanner advertisement table polling, Exponential Moving Average (EMA) smoothing, per-room dB calibration offsets, and 1-click **"Prioritize Here"** calibration.
   - Automatically syncs the active room to the ESPHome device's Home Assistant Area assignment so room-aware **Assist** voice commands (*"turn on the lights"*) target the room you are standing in.
3. **Music Assistant 2.10.8+ Browse, Queue Transfer & Lyrics/Bio Engine**:
   - Paginates Music Assistant libraries (Favorites, Playlists, Artists, Albums, Tracks, Podcasts, Radio, Audiobooks, Active Queue), fetches synced track lyrics and artist/album biographies (via Music Assistant metadata, LRCLIB, and Wikipedia fallbacks), and performs seamless speaker-to-speaker queue transfers.
4. **Area-Aware Room Control & Whole-Home Hub**:
   - Curates room entities by domain (`scene`, `light`, `cover`, `fan`, `switch`, `media_player`, `climate`) and pushes 3-card or 5-slot pages with live brightness/cover/fan levels (`0..100%`), RGB color wheel & Kelvin temperature control, and shared Whole-Home Hub state (Security Alarm, Primary Thermostat, Entry Lock, Garage Door, Robot Vacuum, and Doorbell Camera).
5. **Local LAN Baseline-JPEG Transcoder (Artwork, Wallpapers, Camera Peephole & OpenStreetMap)**:
   - Transcodes progressive PNG/WebP/JPEG album art, custom wallpapers, live `camera.*` snapshots, and multi-tile OpenStreetMap event location maps into memory-safe **Baseline RGB565 JPEG** sized to each device's exact display geometry (`466×466` circle or `410×502` rectangle).
6. **System & Device Backup Vault, Reusable Profiles & Roaming WireGuard Provisioning**:
   - Create full System or per-device snapshots (including live ESPHome `select`, `switch`, and `number` preferences) in `.storage/latter.backups` or download/restore portable `.JSON` bundles.
   - Generate RFC 7748 Curve25519 WireGuard keypairs and copy-pasteable ESPHome roaming VPN configurations in 1 click.

---

## Repository Architecture (`v2.2+`)

```text
ha-latter/
├── custom_components/
│   └── latter/
│       ├── __init__.py          # Domain setup, auto-discovery & signed sidebar panel registration
│       ├── manifest.json        # Integration metadata (local_push, device, zero PyPI requirements)
│       ├── const.py             # Configuration keys, service names & entity ID builders
│       ├── config_flow.py       # Streamlined 3-field onboarding & hardware auto-detection
│       ├── coordinator.py       # Push state coordinator, queue recovery & LAN URL builders
│       ├── sensor.py            # 5 device-scoped sensors with _unrecorded_attributes DB guard
│       ├── services.py          # 14 native latter.* service handlers & slot pagination engine
│       ├── services.yaml        # Home Assistant Developer Tools service schemas
│       ├── ble_engine.py        # 2s per-scanner BLE proxy room tracker & dB offset calibrator
│       ├── browse_engine.py     # Music Assistant 2.10.8+ library browser & Lyrics/Bio engine
│       ├── calendar_engine.py   # Multi-calendar agenda serializer & event creator
│       ├── room_engine.py       # Curated room entity filter, Whole-Home Hub & ESPHome inspector
│       ├── vpn_engine.py        # Curve25519 WireGuard key generator & YAML snippet builder
│       ├── backup_engine.py     # System & Device snapshot vault (.storage/latter.backups) & profiles
│       ├── wallpaper_engine.py  # Built-in AMOLED presets & custom photo wallpaper manager
│       ├── http.py              # Baseline-JPEG transcoders (artwork, wallpaper, camera, OSM map)
│       ├── dashboard.py         # REST API & studio view handlers
│       ├── frontend/
│       │   └── studio.html      # Extracted single-page Latter Web Companion Studio UI
│       ├── brand/
│       │   └── icon.png         # Local integration brand icon
│       ├── strings.json         # Config flow, entity & repairs strings
│       ├── icons.json           # Entity & service icon translations
│       ├── quality_scale.yaml   # Home Assistant Platinum Quality Scale manifest
│       └── py.typed             # PEP 561 strict typing marker
├── docs/
│   ├── USER_GUIDE.md            # Everyday user & Latter Studio administration guide
│   ├── BLE_AND_VPN_GUIDE.md     # BLE room calibration radar & WireGuard roaming guide
│   └── SERVICES_AND_AUTOMATIONS.md # Automation recipes for doorbell alerts, intercom & macros
└── hacs.json                    # HACS repository manifest
```

---

## Supported Devices & Requirements

- **Home Assistant**: `2026.10.0` or newer.
- **Music Assistant** *(Optional, recommended for media browsing & Sendspin streaming)*: `2.10.8` or newer.
- **Supported Hardware**:
  - **Pocket Assistant**: Waveshare ESP32-S3-Touch-AMOLED-1.75C (`466×466` Round QSPI AMOLED).
  - **Mobile Assistant**: Waveshare ESP32-S3-Touch-AMOLED-2.16 (`480×480` Square QSPI AMOLED).
  - **Wrist Assist**: Waveshare ESP32-S3-Touch-AMOLED-2.06 (`410×502` Rectangular Watch QSPI AMOLED).
  - **Remote Assistant**: Waveshare ESP32-P4-WIFI6-Touch-LCD-3.5 (`320×480` Widescreen IPS LCD + 5MP Camera).
  - **Desk Assistant**: Waveshare ESP32-P4-WIFI6-Touch-LCD-4B (`720×720` High-DPI Stationary MIPI-DSI Panel).
  - **Any ESP32 / ESP32-S3 / ESP32-C3 / ESP32-C6 / ESP32-P4 ESPHome Node**: Via 1-line mixins (`esphome-latter-core/mixins/*.yaml`) or 1-click Zero-YAML bridging in Latter Studio.

---

## Installation Instructions

### Option 1: HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the three dots in the top-right corner and select **Custom repositories** (or search for **Latter** directly).
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
| **Configuration Profile** (`apply_profile`) | Defaults to **Auto-Detect from Device Hardware** (automatically configures `466×466` round for Pocket Assistant, `410×502` square/rect for Wrist Assist, or headless sensor defaults), or applies any saved reusable profile. |
| **This device roams** (`native_ble_tracking`) | Enable for portable/wearable devices that move between rooms. Uncheck for stationary devices fixed to a single Area. |

Once added, open **Latter** from the Home Assistant sidebar (or click **Visit** on the ESPHome device page) to configure shared household entities.

---

## Exposed Entities & Data Update Model

Latter uses a **local push (`local_push`)** coordinator model with an idle-guarded timer:
- Each onboarded device exposes 5 device-scoped sensors linked directly to the ESPHome device entry:
  1. `sensor.<device_slug>_active_media`: Active speaker playback state and track attributes. Uses an **idle-guarded 2-second position timer** that runs *only* while media is actively playing, plus `_unrecorded_attributes` to prevent SQLite database bloat.
  2. `sensor.<device_slug>_area_context`: Active room name, room temperature/humidity, curated entity counts, and live Whole-Home Hub states (Alarm, Thermostat, Lock, Garage, Vacuum, Alert/Notification state).
  3. `sensor.<device_slug>_weather_forecast`: Semicolon-delimited 5-day forecast string (`DAY:HIGH:LOW:COND;...`) refreshed every 30 minutes and on weather state changes.
  4. `sensor.<device_slug>_calendar_agenda`: Upcoming family calendar events refreshed every 15 minutes, with automatic geocoded OpenStreetMap snapshot URLs for events with locations.
  5. `sensor.<device_slug>_remote_config`: Active TV/AVR remote slot and 4-slot entity pairings.

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

---

## Support the Project

If you enjoy using **Latter**, **Pocket Assistant**, or **Wrist Assist**, consider supporting ongoing hardware bring-up and open-source development:

- ☕ **[Buy Me a Coffee](https://www.buymeacoffee.com/slampton)**
- ❤️ **[Sponsor on GitHub](https://github.com/sponsors/slampton)**

---

## Development & AI Disclosure

This project is architected, hardware-validated, and maintained by **Sean Lampton** ([Lampton Labs](https://github.com/slampton)), a Senior Systems Engineer. AI coding assistants are used as a pair-programming accelerator for C++20 shader math, Python boilerplate, and documentation—while all system architecture, ESP32-S3 hardware/PMIC/I2S bus engineering, power-state validation, and real-world Home Assistant testing are human-directed and verified on physical hardware.

---

## License

Licensed under the **[Apache License 2.0](LICENSE)**.
