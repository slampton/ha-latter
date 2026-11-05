# Latter Studio

Latter Studio is the **Latter** entry in the Home Assistant sidebar. Only admin users can see it. Use it for anything that's configuration rather than automation. Changes are pushed to devices immediately, so nothing needs to be reflashed.

Studio has two scopes, selected with the switcher at the top: **System** for settings shared by every device, and **Devices** for one device at a time.

<!-- MEDIA: docs/media/studio-overview.png — System → Overview. -->

---

## System

Settings here live in `.storage/latter.site` and apply to every device.

### Overview
- **System summary:** every onboarded device, with its current area, active speaker, and group.
- **Configured Integrations:** the Home Assistant integrations Latter detected and uses, such as Music Assistant and Bluetooth.

### Shared Entities
| Card | What it does |
| :--- | :--- |
| **Whole-Home Entities** | Weather provider, alarm panel, primary thermostat, entry lock, garage door, and robot vacuum. These drive the on-device weather page and Whole-Home Hub. |
| **Cameras & Doorbell Audio** | Up to 10 cameras for the on-device camera carousel and doorbell popups, plus the **Doorbell audio noise reduction** level (Strong, Light, Off) for listening to a doorbell, and a **Test door speaker** button that speaks a test sentence on the camera's speaker with TTS. Listen and push-to-talk replies are experimental. |
| **Calendars** | Calendars merged into the on-device agenda. Duplicate events across calendars are removed, and events with a location get a map. |

### Media & Remotes
| Card | What it does |
| :--- | :--- |
| **System Remote Inventory** | TVs, streaming boxes, and AV receivers available as remote slots, up to 10. Latter pairs each `remote.*` with the `media_player.*` on the same device. It has key mappings for Android TV, Fire TV, Bravia, Apple TV, LG webOS, and Denon/Marantz, and falls back to `remote.send_command` for everything else. |
| **Remote Control Groups** | Which remotes appear on which devices, or in which areas. |
| **Speaker Volume Overrides** | Sends volume changes for a speaker to a different entity, such as an AV receiver `media_player` or an amplifier's `number` entity. |

### Groups & Profiles
- **Configuration Profiles:** capture one device's display, dock, wake word, and timeout settings, then apply them to another device or to a whole group.
- **Device Groups:** logical groupings such as handhelds, bedrooms, or wall panels, used for organization and when applying profiles.

### BLE & Area Presence
- **Live Area Presence & Sensor Fusion:** per-area occupancy, the devices and people in each area, and the fusion mode used for each area.
- **Per-Area BLE Signal Calibration:** live raw and effective RSSI per area for a selected device. Includes **Calibrate Current Area**, ±1 dB adjustment, and a **Fast Refresh (1.5s)** toggle.
- **Discovered Nearby Bluetooth Devices (1-Click Adopt):** named BLE devices, `private_ble_device` entities, and iBeacons your scanners can hear. Adopt one to track it as its own Latter device.

→ [Presence guide](presence.md)

### System Administration
| Card | What it does |
| :--- | :--- |
| **Export Settings (.JSON)** | Download the whole System's settings, or one device's, as a `.json` file. Device exports include the device's live ESPHome select, switch, and number values. Full backups are Home Assistant's own: Latter's storage is included in every Home Assistant backup. |
| **Restore from File (.JSON)** | Upload an exported `.json` file to restore it. A device export can be restored onto a different device to clone its setup. |
| **Reverse Proxy & External Access** | An external base URL for the device **Visit** links, for setups behind a reverse proxy. |
| **Notification Tester** | Send a test notification to any device. |
| **System Custom Color Library** | Up to 24 saved theme colors. |

---

## Devices

The **All Devices** page lists onboarded devices. **+ Add Device** adopts a BLE phone, watch, or tag; Latter devices are added through Home Assistant's ESPHome discovery. → [Existing ESPHome devices](existing-esphome.md)

Each device has five pages. The options on each page depend on what the device's hardware reports. A headless sensor won't show display settings.

| Page | Contents |
| :--- | :--- |
| **Overview** | Quick actions, power profile, apply a profile, assigned person, device status, and a live view of every entity on the device |
| **Display & Home** | Color profile, display geometry, home dock apps and their order, area cards per page, and wallpapers (5 built-in presets, plus uploads that can rotate on a schedule) |
| **Audio & Voice** | Wake word and sensitivity, default speaker, alert volume, and music sorting |
| **Power & Battery** | Sleep and wake timeouts, plus battery and power readings |
| **Administration** | Device slug (read-only: the ESPHome node name), type, and group; BLE tracking settings; and **Remove Device** |

> Most settings apply live: Studio saves them and pushes the change to the device without a reload. Adding or removing a device, or changing a device's bound ESPHome device, reloads the Latter integration; devices reconnect within a few seconds.
