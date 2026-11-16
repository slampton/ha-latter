# Latter Studio

Latter Studio is the **Latter** entry in the Home Assistant sidebar (visible to administrators only). Use it for everything that is configuration rather than automation—every change saves immediately to Home Assistant and pushes live to online devices without reflashing, and sleep-safe settings apply automatically the next time a sleeping battery device wakes.

Studio has two scopes in the top switcher:
- **Devices** *(default)*: per-device dashboards and settings across all onboarded displays, headless nodes, and BLE tags.
- **System**: shared Home Assistant entities, remotes, wallpapers, colors, Device Groups, BLE Area calibration, and system tools.

There is no Save button: controls apply immediately (text and number inputs commit on Enter or blur), URLs follow the active route (`/latter/devices/<id>/interface`, `/latter/system/presence`) for bookmarking and browser Back/Forward, and if Latter updates via HACS while Studio is open, a **Reload Page** banner appears automatically.

<!-- MEDIA: docs/media/studio-overview.png — Latter Studio, System → Overview. -->

---

## System Views

Shared entities, remotes, colors, and overrides live in the Latter hub entry's options; Device Groups, BLE calibration, Area fusion, signing/PIN secrets, and Studio logs live in `.storage/latter.site`; wallpapers live in `.storage/latter/wallpapers/`.

### Overview
- **Issues:** open Home Assistant Repairs for Latter (crashes, brownouts, firmware rollbacks, missing entities, BLE proxy coverage, unlinked Music Assistant players), with an **Open Repairs** shortcut.
- **System:** integration version, **Check Firmware Updates** across all devices, and clickable counts for **Devices Online**, **Latter Displays**, **BLE Tracked Devices**, **Assigned People**, and **Area BLE Proxies**.
- **Configured Items:** quick summary counts linking to configured remotes, volume overrides, cameras, calendars, custom colors, wallpapers, and Device Groups.

### Shared Entities
| Card | What It Controls |
| :--- | :--- |
| **Whole-Home Entities** | Weather provider, security alarm panel, primary thermostat, entry lock, garage door, and robot vacuum powering **Sky & Weather** and the **Home Hub**. |
| **Cameras & Doorbell Audio** | Up to 10 cameras (with live **Preview**) for the on-device camera view and doorbell popups, **Doorbell Audio Filter** (*Strong*, *Light*, *Off*), and read-only **Doorbells** status showing auto-detected ring entities and active listen/reply sessions. |
| **Calendars** | Home Assistant calendars merged and deduplicated into the on-device agenda (events with locations get signed OpenStreetMap pins). |
| **Custom Colors** | Up to 24 shared theme swatches available to any device whose **Color Profile** is **Custom**. |
| **Wallpapers** | **6 built-in `720p` presets** (*Forest Mountains*, *Wheat Field*, *Ocean Waves*, *Sahara Dunes*, *Andromeda Galaxy*, *Mars Crater*) plus shared photo uploads (up to 15 MB via admin Bearer-authenticated multipart upload, center-cropped to `960×960` and served at up to `720×720`). |

### Media & Remotes
- **Remote Controls:** up to 10 TVs, streaming boxes, and AV receivers (auto-pairing sibling `remote.*` and `media_player.*` entities, with native key maps for Android TV, Fire TV, Bravia, Apple TV, LG webOS, and Denon/Marantz).
- **Remote Control Groups:** named remote sets bound to Home Assistant Areas or assigned per device on each device's **Interface** page.
- **Speaker Volume Overrides:** routes volume changes for any speaker to an AV receiver `media_player` or amplifier `number` / `input_number` entity.

### Device Groups
- **Device Groups:** built-in groups (*Handhelds*, *Wearables*, *Bedrooms*, *Common Areas*, *Wall & Desk Panels*, *Unassigned*) plus custom groups storing an **operational baseline** (power profile, timeouts, brightness schedule, wake-word mode, alert volume, BLE tracking, *Voice Follows Me*, media handoff) without overwriting personal appearance settings. **Seed Baseline From Device** copies a configured device's operational baseline.
- **Group Controls & Baseline:** live-edit operational settings across a group (showing **Mixed** when members differ), plus a collapsible **Appearance & Personalization** bulk-override drawer.

### BLE & Area Presence
- **Live Area Presence & Sensor Fusion:** per-Area occupancy status, occupants, 6.0 dB cross-floor attenuation, and per-Area **Fusion Settings** (mode `weighted` / `any_or` / `ble_only` / `ble_and_sensor`, 20–95% threshold, and participating mmWave/PIR/door sensors).
- **Per-Area BLE Signal Calibration:** live raw and effective RSSI per Area with **Live Stream On / Stream Paused** (`ble_survey_delta` WebSocket stream), **Calibrate Current Area**, and ±1 dB fine-tuning. → [Presence guide](presence.md)

### Tools
| Card | What It Controls |
| :--- | :--- |
| **Notifications & Announcements** | Test **Screen Notification** (banner, chime, optional primary camera snapshot) or **Voice Broadcast** (TTS announcement) to a specific device, `occupied_areas`, or `all` via **Send Now**. |
| **Doorbell & Intercom Audio** | Pick a **Source Device**, enter **Test Door Speaker Reply**, and click **Play on Door Speaker** to verify TTS routing on the primary camera's speaker. |
| **Backup & Restore** | **Export** or **Restore** System or single-device `.json` bundles (`latter.backup.v3`: subentry configuration + all 50 typed device preferences, portable across hardware). Full storage is also included in native Home Assistant backups. |
| **Perimeter Security & Signing** | Set a fallback **System Security PIN** (used when a device requires a PIN and has no per-device PIN set) and **Rotate Signing Key** to invalidate previously issued HMAC media URLs immediately. |
| **System & Device Logs** | Filterable event and Home Assistant log viewer (Latter, ESPHome, Music Assistant) with **Refresh Logs**, **Copy Logs**, **Clear Studio Events**, and **Open Native HA Logs**. |

---

## Device Views

The **Devices** sidebar splits inventory lifecycle into two top-level views:
- **Managed** (`/latter/devices`, page title **Managed Devices**): sortable inventory table whose card header updates dynamically with the selected category filter (*All Devices* by default, *Online Devices*, *Latter Displays*, *Screenless Devices*, *Roaming Devices*, *Stationary Devices*, *BLE-Tracked Devices*, *BLE Tags*, *Assigned to a Person*, *Updates Available*, or *Group: \<Name\>*). Capabilities come directly from each device's Hardware Manifest v2 (screenless nodes and BLE tags hide display-only tabs).
- **Discovered** (`/latter/devices/discovered`, page title **Discovered Devices**, showing a sidebar count badge whenever unbound Latter ESPHome hardware is waiting): two stacked onboarding cards—**Latter Devices** (one-click **Adopt** for unbound ESPHome devices running Latter firmware with auto-detected Device Group and optional Person assignment, plus **Open Integration**) and **Bluetooth Devices** (searchable, filterable, sortable by *Name (A–Z)* default / *Signal strength* / *Nearest Area*, and pausable via **Pause List** / **Resume List** so rows never jump during one-click **Adopt**, plus **Add BLE Tag**).

### Overview
- **Needs Attention** banner whenever the device has open Repairs.
- **Status:** online/offline/update state chip, 2×2 glanceable tiles for **Area** (placement & closest BLE proxy), **Battery / Power** (*Plugged in* when docked), **Wi-Fi / BLE Signal**, and **Firmware**, clickable **Device Group** and **Remote Group** rows, plus **Open in ESPHome** and **Download Backup**.
- **Quick Actions:** Find My Device, Activate Screensaver, Restart, **Device Group** (*In Sync* / *Customized* badge + **Reset to Group**), and **Assigned Person**.

### Display *(Visual Appearance)*
- **Column 1:** **Home Screen** (**Wake Greeting**, **Weather Background**, and **Sun & Moon** pills—when Weather Background is on, Home renders the live weather sky even if a wallpaper is active across other pages), **Screensavers** (docked switch, style, idle timeout, **Preview**), **Voice Assistant** (**Visual Profile**), **Brightness** (manual or Sun/schedule auto), and **Clock** (**Clock Face**: *Minimal Digital*, *Modern Analog*, *Hybrid Digital*; **Time Format**).
- **Column 2:** **Colors** (preset or **Custom Color** + **Add Color**), **Wallpapers** (upload photo, active selection, rotation schedule, favorite stars across 6 built-in presets + uploads), and **Media Player** (**Album Art Style** and **Overlay Style**).

### Interface *(Navigation, Layout & Time)*
- **Column 1:**
  - **Home Screen:** **Enable Home Screen** (turn off for single-app kiosk mode locked to **Start Screen**), **Start Screen** (*Home*, *Time App*, *Clock Face*, or any Dock App), **Home Time Tap** (*Time App* vs. *Clock Face*), **Return to Home Timeout** (exempting active media, timers, games, calls, and tools), **Dock Apps** toggle/order pills (*Media*, *Home Hub*, *Area Controls*, *Remote*, *Weather*, *Time*, *Cameras*, *Games*, *Tools*), and **Show the Activity Card** + **Activity Card Sources** pills.
  - **Home Controls:** **Home Categories** toggle and order pills across all **6 Home Hub tabs**—*Security Alarm*, *Cameras*, *Intercom*, *Thermostat*, *Entry & Garage*, and *Robot Vacuum* (categories without configured entities hide automatically).
  - **Time:** optional **Local Clock Label** (up to 32 chars above local time), **Show UTC Clock**, **World Clocks** (up to 4 custom-labeled cities across `UTC-12:00..UTC+14:00` IANA zones with reorder/delete), and **Alarms** (3 recurring 1-minute slots synced two-way with on-device alarm edits).
- **Column 2:**
  - **Area Controls:** **Area Categories** toggle and order pills (*Scenes*, *Lights*, *Blinds & Curtains*, *Fans*, *Switches*, *Climate*, *Media*, and optional *All Devices*).
  - **Media Player:** **Shortcuts** pills (*Speaker*, *Library*) plus **Album**, **Artist Album**, and **Podcast** sort orders.
  - **Remote Controls:** **Remote Control Group** (*Area Auto*, specific group, or all System remotes) + **Manage Remote Groups**.

### Audio
- **Voice Assistant & Wake Word:** **Wake Word Mode** (*Docked Only*, *Always On*, *Disabled*), Home Assistant Assist pipeline & wake-word selects, collapsible per-model **Wake Word Sensitivity**, **Wake Screen on Assist**, and roaming **Voice Follows Me** + dwell delay (3–60 s).
- **Sound & Playback:** **Default Speaker**, conditional **Music Assistant Player** override, **Media Follows This Device to Its New Area**, **Alert Volume**, **Volume Step Size**, and **Game Sound Effects**.

### Power
- **Sleep & Wake:** **Power Profile** (*Portable Carry*, *Handheld Roaming*, *Wearable Watch*, *Tabletop Dock*, *Always-On Wall / Desk*, *Custom*), **Tap to Wake**, **Pickup to Wake**, **Battery Screen Timeout**, **Battery Hibernate Timeout**, and **Hold Crown to Power Off**, alongside live **Power & Battery** telemetry.

### Presence
- **Area Tracking:** **Track the Area with BLE Proxies**.
  - When **on**: **Auto-Switch Active Area**, **Fallback Area**, and battery **BLE Beacon Mode** (*Handheld Only*, *Handheld + Screen Off*, *Always*).
  - When **off**: **Assigned Area**, pinning the device to a static Area and syncing two-way with Home Assistant's Device Area across both the ESPHome and Latter device entries.
- **BLE Identity:** **BLE Target Address or Entity** and **iBeacon UUID**.

### Tools
- **Diagnostics:** firmware update controls, model/node/SDK/IP/MAC summary, **Download Diagnostics** (redacted JSON), **Open in ESPHome**, and a collapsed **Developer & Telemetry** drawer (Telemetry Profiler, Log Memory Report, Weather Simulation, parsed Link Report including **Session Uptime**, RAM/PSRAM watermarks, and Hardware Manifest traits).
- **Perimeter Security:** per-device **Perimeter Security Policy** (*Auto*, *Allow*, *Require PIN*, *Block*) and optional **Security PIN** (falling back to the System Security PIN when unset). Guards unlocking locks, opening garage/gate covers, and disarming code-less alarms; Home Assistant alarm panels with their own code validate directly against Home Assistant (`alarm_caps`).
- **Replace Hardware & Danger Zone:** download a portable device backup, **Reset to Defaults** (independently resetting NVS device settings and/or Studio options via [`latter.reset_device`](reference/services.md#latterreset_device) while preserving Wi-Fi, API pairing, and Music Assistant links), or **Remove Device**.
