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
- **Conditional Alerts:** **Needs Attention** banner whenever Latter has open Home Assistant Repairs (with per-issue **Open Device** and **Open Repairs**) plus **Hardware Ready to Adopt** whenever unbound Latter ESPHome hardware is detected on the network (**Open Discovered**).
- **Column 1 — Status & Area Deployment:** **Status** renders a live System health chip (`All Online`, `<N> / <M> Online`, updates, or issues), `2×2` glanceable tiles for **Managed Devices**, **Area Presence**, **People & Roaming**, and **System Release**, plus **Open Repairs** and **Check Firmware Updates** footer links; underneath, **Area Deployment** maps active **Roaming Devices** and deployed **Areas** with live occupancy, stationed Devices, remotes, sensors, and BLE signature/proxy coverage.
- **Column 2 — System Capabilities:** visual readiness blocks linking directly to **Home Hub & Weather** (6 shared domain pills), **Cameras, Doorbells & Calendars**, **Media & Remotes**, **Device Groups**, **Colors & Wallpapers** (live color swatches + wallpaper counts), and **Perimeter Security** (**System PIN Set** / **No System PIN**).

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
- **Remote Control Groups:** named remote sets bound to Home Assistant Areas or assigned per device from **Overview → Assignments** or **Interface → App Dock → Remote → Configure**.
- **Speaker Volume Overrides:** routes volume changes for any speaker to an AV receiver `media_player` or amplifier `number` / `input_number` entity.

### Device Groups
- **Column 1 — Device Groups:** 4 built-in hardware presets (*Pocket Carry*, *Handhelds*, *Wearables*, *Wall & Desk Panels*) plus custom groups rendered in enclosed cards. By default each group manages **Operational** settings (power & wake timeouts, brightness schedule, wake-word mode & sensitivity, alert volume, BLE tracking, *Voice Follows Me*, media handoff, perimeter security policy) so personal wallpapers and shortcuts stay per-device, while any group can opt into **Include Display Settings** and/or **Include Interface & Shortcuts** to enforce visual styling, shortcuts, and categories too. Includes a top creation bar (with scope pills and optional **Copy from** Device seeding) and an inline **Baseline Settings** + **Copy From Device** drawer inside each group box.
- **Column 2 — Batch Controls:** applies a one-time live setting change across *All Latter Devices*, *Online Devices*, *Roaming Devices* (rolling up Pocket Carry, Handhelds, Wearables, and roaming custom devices), *Stationary Devices*, any configured Device Group (*Pocket Carry*, *Handhelds*, *Wearables*, *Wall & Desk Panels*, or custom groups), or *Custom* Devices across all 6 Device tab categories (*Display*, *Interface*—including *Home Hub Categories*, *Area Control Categories*, *Tools*, and *Games* pills—*Audio*, *Power*, *Presence*, *Security*) plus **Copy Multi-Item Lists** (*App Dock*, *Pinned Shortcuts*, *World Clocks*) without altering saved group baselines.

### BLE & Area Presence
- **Column 1 — Area Presence & Sensors:** unified enclosed Area cards showing live occupancy confidence, Floor, and BLE coverage chips (`Signature`, `BLE Proxy`, or `No BLE Proxy`), occupant and distance telemetry, an inline **Calibrate** shortcut that smoothly scrolls to **Walk-Around BLE Calibration** with a warning-highlighted target handoff (and **Clear Signature** when calibrated), **Presence Mode** (`weighted` / `any_or` / `ble_only` / `ble_and_sensor`), and an enclosed **Sensor & Threshold Settings** drawer (**Occupied At** `20–95%` threshold and **Sensors That Count** mmWave/PIR/door pills).
- **Column 2 — Walk-Around BLE Calibration:** guided live calibration with **Live Stream On / Stream Paused** (`ble_survey_delta` WebSocket stream with full snapshot freeze while paused), **Carried Device** (filtered strictly to actively BLE-tracked Devices and BLE Tags), a live signal / 12 s sleep-wake status banner, **Standing In Area** + **Calibrate Area** inside a warning-highlighted handoff box (capturing normalized multi-scanner Area signatures for boundary accuracy and proxy-less Areas), and Area-first **Nearby Bluetooth Proxies** signal bars with an inline collapsible **Antenna Trim** drawer inside each proxy row (`-1 dB` / `+1 dB` / **Reset** hardware gain trim within `±25 dB`). → [Presence guide](presence.md)
- **Column 2 — Advanced BLE Settings:** collapsed-by-default System-wide RF tuning card beneath **Walk-Around BLE Calibration** with **Away Timeout** (`30–900 s`, default `180 s`), **Maximum Area Radius** (`2–50 m`, default `12 m`), **Maximum Movement Speed** (`0.5–15 m/s`, default `3.5 m/s` velocity gate), and **Path-Loss Attenuation** (`1.5–4.5`, default `2.2`).

### Tools
| Card | What It Controls |
| :--- | :--- |
| **Notifications & Announcements** | Test **Screen Notification** (banner, chime, optional primary camera snapshot) or **Voice Broadcast** (TTS announcement) to a specific device, `occupied_areas`, or `all` via **Send Now**. |
| **Doorbell & Intercom Audio** | Pick a **Source Device**, enter **Test Door Speaker Reply**, and click **Play on Door Speaker** to verify TTS routing on the primary camera's speaker. |
| **Backup & Restore** | **Export** or **Restore** System or single-device `.json` bundles (`latter.backup.v3`: subentry configuration + all 49 typed device preferences, portable across hardware). Full storage is also included in native Home Assistant backups. |
| **Perimeter Security & Signing** | Set a fallback **System Security PIN** (used when a device requires a PIN and has no per-device PIN set) and **Rotate Signing Key** to invalidate previously issued HMAC media URLs immediately. |
| **System & Device Logs** | Filterable event and Home Assistant log viewer (Latter, ESPHome, Music Assistant) with **Refresh Logs**, **Copy Logs**, **Clear Studio Events**, and **Open Native HA Logs**. |

---

## Device Views

The **Devices** sidebar splits inventory lifecycle into two top-level views:
- **Managed** (`/latter/devices`, page title **Managed Devices**): sortable inventory table whose card header updates dynamically with the selected category filter (*All Devices* by default, *Online Devices*, *Roaming Devices*, *Stationary Devices*, plus populated *Group: \<Name\>*, *Group: Custom*, *BLE Tags*, *Assigned to a Person*, *Updates Available*, and System Overview deep links for *Latter Displays* and *BLE-Tracked Devices*; zero-member groups hide automatically). Capabilities come directly from each device's Hardware Manifest v2 (screenless nodes and BLE tags hide display-only tabs).
- **Discovered** (`/latter/devices/discovered`, page title **Discovered Devices**, showing a sidebar count badge whenever unbound Latter ESPHome hardware is waiting): two stacked onboarding cards—**Latter Devices** (one-click **Adopt** for unbound ESPHome devices running Latter firmware with auto-detected Device Group and optional Person assignment, plus **Open Integration**) and **Bluetooth Devices** (searchable, filterable, sortable by *Name (A–Z)* default / *Signal strength* / *Nearest Area*, and pausable via **Pause List** / **Resume List** so rows never jump during one-click **Adopt**, plus **Add BLE Tag**).

### Overview
- **Needs Attention** banner whenever the device has open Repairs.
- **Column 1 — Status & Quick Actions:** **Status** renders an online/offline/update state chip and compact responsive `2×2` glanceable tiles for **Area** (placement & closest BLE proxy), **Battery / Power** (*Plugged in* when docked), **Wi-Fi / BLE Signal**, and **Firmware**; directly underneath, **Quick Actions** surfaces Find My Device, Trigger Voice Assistant, Activate Screensaver, Hibernate Device, Restart Device, live **Speaker Volume**, and **Open in ESPHome** + **Download Backup** footer links.
- **Column 2 — Assignments & Timers & Alarms:**
  - **Assignments:** unified card at the top of the right column for **Device Group** (switches automatically to *Custom* whenever operational settings diverge from a group baseline, with **Save Custom Group** and **Manage Groups**), **Assigned Person**, and **Remote Control Group** (**Configure** opens the **Remote Control** modal directly on **Overview**).
  - **Timers & Alarms:** conditional ringing alert banner with one-tap **Dismiss**, live **Active Timer** countdown (`MM:SS` / `HH:MM:SS`) with **Cancel Timer**, live **Stopwatch** elapsed time with **Reset Stopwatch**, and the 3-slot recurring 1-minute **Alarms** editor synced two-way with on-device alarm edits.

### Display *(Visual Appearance)*
- **Column 1:** **Home Screen** (**Wake Greeting**, **Weather Background**, and **Sun & Moon** pills—when Weather Background is on, Home renders the live weather sky even if a wallpaper is active across other pages), **Screensavers** (docked switch, style, idle timeout, **Preview**), **Voice Assistant** (**Visual Profile**), **Brightness** (manual or Sun/schedule auto), and **Clock** (**Clock Face**: *Minimal Digital*, *Modern Analog*, *Hybrid Digital*; **Time Format**).
- **Column 2:** **Colors** (preset or **Custom Color** + **Add Color**), **Wallpapers** (upload photo, active selection, rotation schedule, favorite stars across 6 built-in presets + uploads), and **Media Player** (**Album Art Style** and **Overlay Style**).

### Interface *(Navigation & App Dock)*
- **Column 1 — Home Screen:** **Enable Home Screen** (turn off for Single-App Mode locked to **Start Screen**), **Start Screen** (*Home*, *Pinned*, *Time App*, *Calendar*, *Clock Face*, or any app, paired with an inline **Configure** button when Home Screen is off), **Home Time Tap** (*Time App* vs. *Clock Face*), **Home Date Tap** (*Day View* vs. *Overview*), **Return to Home Timeout** (exempting active media, timers, games, calls, composer drafts, and tools), and **Show the Activity Card** + **Activity Card Sources** pills.
- **Column 2 — App Dock** *(or **Single-App Mode Active** when Home Screen is disabled)*:
  - **Active on Dock:** Protected Native Apps (*Pinned*, *Music*, *Home Hub*, *Area Control*, *Remote*, *Sky & Weather*, *Time*, *Calendar*, *Clock Face*, *Tools*, *Games*) show live configuration summaries, `↑`/`↓` reorder buttons, a **Configure** button (opening that app's modal), and an On/Off switch (**Pinned** auto-hides on-device while empty; **Settings** is always locked last). Custom deep-subpage and Home Assistant entity shortcuts include **Edit** and **Remove**, above **Add Custom Shortcut** and **Reset Default Dock**.
  - **Hidden From Dock:** lists any disabled native apps (*Sky & Weather*, *Time*, *Calendar*, and *Clock Face* by default) with **Configure** still active and a switch to re-enable them on the Dock.
  - **App Configuration Modals (`Configure`):** **Pinned App** (6-slot swipable pages + **Add Pinned Item**), **Home Hub** (6 category pills + **Open Shared Entities**), **Area Control** (8 category pills), **Music** (library sort orders), **Remote Control** (**Remote Control Group** + **Manage Remote Groups**), **Time** (**Local Clock Label**, **Show UTC Clock**, and up to 4 custom-labeled `UTC-12:00..UTC+14:00` **World Clocks**), **Calendar** (**Overview Lookahead** *7/14/30/60 Days*, **Start Week On** *Sunday/Monday*, + **Open Shared Entities**), **Clock Face** (**Clock Face** & **Time Format**), **Tools** (capability-filtered *Analog Chronograph*, *Bubble Level*, *Flashlight*, *Calculator*, *Dice Roll*, *Coin Flip*), and **Games** (*Marbles*, *Archery*, *Bricks*, *Chomp*, *2048*, *Memory Match*).

### Audio
- **Voice Assistant & Wake Word:** **Wake Word Mode** (*Docked Only*, *Always On*, *Disabled*), Home Assistant Assist pipeline & wake-word selects, collapsible per-model **Wake Word Sensitivity**, **Wake Screen on Assist**, and roaming **Voice Follows Me** + dwell delay (3–60 s).
- **Sound & Playback:** **Default Speaker**, conditional **Music Assistant Player** override, **Media Follows This Device to Its New Area**, **Alert Volume**, **Volume Step Size**, and **Game Sound Effects**.

### Power
- **Sleep & Wake:** **Tap to Wake**, **Pickup to Wake**, **Battery Screen Timeout**, **Battery Hibernate Timeout**, and **Hold Crown to Power Off**, alongside live **Power & Battery** telemetry.

### Presence
- **Area Tracking:** **Track the Area with BLE Proxies**.
  - When **on**: **Auto-Switch Active Area**, **Fallback Area**, and battery **BLE Beacon Mode** (*Handheld Only*, *Handheld + Screen Off*, *Always*).
  - When **off**: **Assigned Area**, pinning the device to a static Area and syncing two-way with Home Assistant's Device Area across both the ESPHome and Latter device entries.
- **BLE Identity:** **BLE Target Address or Entity**, **iBeacon UUID**, and **Reference Power (1 Meter)** (optional `-90` to `-30 dBm` override; leave blank to use auto-detected advertised beacon power).

### Tools
- **Diagnostics:** firmware update controls, model/node/SDK/IP/MAC summary, **Download Diagnostics** (redacted JSON), **Open in ESPHome**, and a collapsed **Developer & Telemetry** drawer (Telemetry Profiler, Log Memory Report, Weather Simulation, parsed Link Report including **Session Uptime**, RAM/PSRAM watermarks, and Hardware Manifest traits).
- **Perimeter Security:** per-device **Perimeter Security Policy** (*Auto*, *Allow*, *Require PIN*, *Block*) and optional **Security PIN** (falling back to the System Security PIN when unset). Guards unlocking locks, opening garage/gate covers, and disarming code-less alarms; Home Assistant alarm panels with their own code validate directly against Home Assistant (`alarm_caps`).
- **Replace Hardware & Danger Zone:** download a portable device backup, **Reset to Defaults** (independently resetting NVS device settings and/or Studio options via [`latter.reset_device`](reference/services.md#latterreset_device) while preserving Wi-Fi, API pairing, and Music Assistant links), or **Remove Device**.
