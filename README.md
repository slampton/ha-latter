<div align="center">

# Latter for Home Assistant (`ha-latter`)

**Universal ESPHome Companion Middleware, BLE Room Presence Fabric & Web Studio for Home Assistant**

[![Release](https://img.shields.io/badge/release-v2.2.0-03a9f4?style=for-the-badge&logo=github)](https://github.com/slampton/ha-latter/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5?style=for-the-badge&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Custom%20Repository-41BDF5?style=for-the-badge&logo=home-assistant-community-store&logoColor=white)](https://github.com/slampton/ha-latter)
[![Quality Scale](https://img.shields.io/badge/Quality%20Scale-Platinum-E5E4E2?style=for-the-badge&logo=home-assistant&logoColor=black)](custom_components/latter/quality_scale.yaml)
[![Python](https://img.shields.io/badge/Python-3.13%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/slampton/ha-latter)
[![ESPHome Core](https://img.shields.io/badge/ESPHome%20SDK-esphome--latter--core-000000?style=for-the-badge&logo=esphome&logoColor=white)](https://github.com/slampton/esphome-latter-core)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-brightgreen.svg?style=for-the-badge)](https://github.com/slampton/ha-latter/graphs/commit-activity)
[![Sponsor](https://img.shields.io/badge/Sponsor-Lampton%20Labs-ea4aaa?style=for-the-badge&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/slampton)

</div>

---

## Overview

**Latter (`ha-latter`)** is an async Home Assistant integration and sidebar **Web Studio** that turns ESPHome displays, handhelds, smartwatches, wall panels, and sensor nodes into a unified, room-aware smart home fabric—with **zero YAML entity hardcoding**.

### The Latter Ecosystem
1. **`slampton/ha-latter` (This Repo)** — Home Assistant middleware integration, BLE room calibration engine, baseline-JPEG artwork/wallpaper/camera/map transcoder, and sidebar Web Studio (`custom_components/latter/`).
2. **[`slampton/esphome-latter-core`](https://github.com/slampton/esphome-latter-core)** — Universal ESPHome C++20 UI SDK, 1-line drop-in mixins (`mixins/*.yaml`), board HALs (`boards/*.yaml`), and turnkey configurations (`devices/*.yaml`) for all five flagship devices:
   - **Pocket Assistant** (*1.75" `466×466` Round AMOLED Handheld* — also at [`slampton/esphome-pocket-assistant`](https://github.com/slampton/esphome-pocket-assistant))
   - **Mobile Assistant** (*2.16" `480×480` Square AMOLED Handheld*)
   - **Wrist Assist** (*2.06" `410×502` Rectangular AMOLED Smartwatch*)
   - **Remote Assistant** (*3.5" `320×480` Widescreen ESP32-P4 Handheld + Camera*)
   - **Desk Assistant** (*4.0" `720×720` High-DPI ESP32-P4 Stationary Display*)

---

## Key Capabilities

- **Streamlined Web Studio (Sidebar Panel)**:
  - **System Scope (6 Tabs)**:
    1. **Devices**: 5-column sortable Home Assistant data table (*Device*, *Model*, *Area* / *Roaming*, *Group*, *Status*) with real-time search filtering and 1-click onboarding of existing ESPHome devices.
    2. **Shared Entities**: Map household Weather, Security Alarm, Thermostat, Entry Lock, Garage Door, Robot Vacuum, up to **10 Cameras** (with rectangular 16:9 snapshot previews), **Calendars**, and **Pinned Room Entities** (which also populate the on-device scrollable *Macros* tool).
    3. **Media & Remotes**: Dynamic **Remote Controls** list (`+ Add Remote Control`, up to **10 scrollable slots** with automatic sibling entity pairing and protocol detection) and dynamic **Speaker Volume Overrides** (up to 10 speaker-to-AVR/number volume mappings).
    4. **Groups & Profiles**: Capture live device configurations into reusable profiles, organize devices into groups, and dispatch bulk controls by category.
    5. **BLE Calibration**: Select any BLE-enabled device (persisted in browser storage), view live per-room Raw/Effective dBm and estimated distance, and calibrate room offsets in 1 click.
    6. **Administration**: Local backup snapshots & JSON file export/import, Reverse Proxy base URL override, Notification Tester, System Custom Color Library (HSV Color Wheel), Developer YAML tools, and live System/Studio logs.
  - **Device Scope (5 Tabs)**:
    1. **Overview**: 3 live telemetry cards (*Current Room*, *Battery / Power*, *Wi-Fi Signal*), highlighted blue **Quick Actions** (*Find My Device*, *Hibernate Now*, *Screensaver Now*, *Trigger Voice Assistant*, *Restart Device*), 1-click Profile deployment, and Device Status.
    2. **Display & Home**: Logically ordered display settings with conditional brightness visibility, interactive **Home Dock App** toggle/reorder pills, and a unified **Wallpapers** card.
    3. **Audio & Voice**: Wake word mode, active model, visual profile, room-context sync, collapsible per-model sensitivity controls, and collapsible library sorting preferences.
    4. **Power & Battery**: Logically ordered sleep/wake timeouts, wake gestures, and live battery telemetry.
    5. **Administration**: Separate **Device Identity** and **BLE Room Tracking** cards, collapsible **Roaming WireGuard VPN** provisioning, BLE mixin snippets, raw entity inspector, and a dedicated **Remove Device** section.

---

## Repository Structure

```text
ha-latter/
├── custom_components/
│   └── latter/
│       ├── brand/
│       │   └── icon.png                 # Local integration & sidebar brand icon
│       ├── frontend/
│       │   └── studio.html              # Single-page Latter Web Studio (System & Device scopes)
│       ├── translations/
│       │   └── en.json                  # English UI & Repairs translations
│       ├── __init__.py                  # Domain setup, auto-discovery & panel registration
│       ├── backup_engine.py             # Local backups, JSON export/import & device profiles
│       ├── ble_engine.py                # Native ESPHome BLE Proxy room presence engine
│       ├── browse_engine.py             # Music Assistant library, queue, lyrics & bio browser
│       ├── calendar_engine.py           # Multi-calendar agenda & quick-event engine
│       ├── config_flow.py               # Hardware-auto-detecting 3-field onboarding & options flow
│       ├── const.py                     # Constants, service names & storage keys
│       ├── coordinator.py               # Per-device state coordinator & household store sync
│       ├── dashboard.py                 # Web Studio REST API & authenticated panel views
│       ├── diagnostics.py               # Redacted config entry diagnostics
│       ├── http.py                      # Baseline-JPEG artwork, wallpaper, camera & map proxy views
│       ├── icons.json                   # Entity & service icon mappings
│       ├── manifest.json                # Integration manifest (v2.2.0)
│       ├── py.typed                     # PEP 561 strict typing marker
│       ├── quality_scale.yaml           # HA Platinum Quality Scale declaration
│       ├── repairs.py                   # Automated configuration health & Repairs monitor
│       ├── room_engine.py               # Area discovery, entity curation & ESPHome inspector
│       ├── sensor.py                    # 5 device-scoped push sensors (sensor.<slug>_*)
│       ├── services.py                  # 14 domain services (music, room, remote, calendar, notify)
│       ├── services.yaml                # Service schemas & selectors
│       ├── strings.json                 # Config flow & Repairs strings
│       ├── vpn_engine.py                # Curve25519 WireGuard keygen & YAML snippet builder
│       └── wallpaper_engine.py          # AMOLED preset renderer & custom wallpaper manager
└── docs/
    ├── USER_GUIDE.md                    # Complete setup & Web Studio guide
    ├── BLE_AND_VPN_GUIDE.md             # BLE room calibration & WireGuard roaming guide
    └── SERVICES_AND_AUTOMATIONS.md      # Service reference & automation examples
```

---

## License

Licensed under the [Apache License 2.0](LICENSE). Copyright © Lampton Labs.