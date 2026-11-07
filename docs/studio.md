# Latter Studio

Latter Studio is the **Latter** entry in the Home Assistant sidebar. Only admin users can see it. Use it for anything that's configuration rather than automation. Changes are pushed to devices immediately, so nothing needs to be reflashed.

Studio has two scopes, selected with the switcher at the top: **Devices** (where Studio opens) for one device at a time, and **System** for settings shared by every device. System pages work whether or not a device is selected; a System action that affects one device asks you which device.

The **Save** button saves System settings and the open device's settings separately, so saving one never changes the other. If a save fails, Studio shows the reason in a red message at the bottom of the page.

<!-- MEDIA: docs/media/studio-overview.png — System → System overview. -->

---

## System

Settings here live in `.storage/latter.site` and apply to every device.

### System overview
- **System:** the Latter version, a **Check for Updates** button for device firmware, and counts of online devices, Latter devices, BLE-tracked devices, devices with an assigned person, and BLE area proxies. Each count opens the matching device list or page.
- **Configured Integrations:** how many remotes, volume overrides, cameras, calendars, groups, and saved profiles are set up.

### Shared Entities
| Card | What it does |
| :--- | :--- |
| **Whole-Home Entities** | Weather provider, alarm panel, primary thermostat, entry lock, garage door, and robot vacuum. These drive the on-device weather page and Whole-Home Hub. |
| **Cameras & Doorbell Audio** | Up to 10 cameras for the on-device camera carousel and doorbell popups, plus the **Doorbell audio noise reduction** level (Strong, Light, Off) for listening to a doorbell, and a **Test door speaker** button that speaks a test sentence on the primary camera's speaker with TTS, from the device you choose. Listen and push-to-talk replies are experimental. |
| **Calendars** | Calendars merged into the on-device agenda. Duplicate events across calendars are removed, and events with a location get a map. |

### Media & Remotes
| Card | What it does |
| :--- | :--- |
| **System Remote Inventory** | TVs, streaming boxes, and AV receivers available as remote slots, up to 10. Latter pairs each `remote.*` with the `media_player.*` on the same device. It has key mappings for Android TV, Fire TV, Bravia, Apple TV, LG webOS, and Denon/Marantz, and falls back to `remote.send_command` for everything else. |
| **Remote Control Groups** | Which remotes appear on which devices, or in which areas. |
| **Speaker Volume Overrides** | Sends volume changes for a speaker to a different entity, such as an AV receiver `media_player` or an amplifier's `number` entity. |

### Groups & Profiles
- **Configuration Profiles:** choose a device and capture its display, dock, wake word, and timeout settings, then apply them to one device, a group, or all devices.
- **Device Groups:** logical groupings such as handhelds, bedrooms, or wall panels, used for organization and when applying profiles.

### BLE & Area Presence
- **Live Area Presence & Sensor Fusion:** per-area occupancy, the devices and people in each area, and the fusion mode used for each area.
- **Per-Area BLE Signal Calibration:** live raw and effective RSSI per area for a selected device. Includes **Calibrate Current Area**, ±1 dB adjustment, and a **Fast Refresh (1.5s)** toggle.
- **Discovered Nearby Bluetooth Devices (1-Click Adopt):** named BLE devices, `private_ble_device` entities, and iBeacons your scanners can hear. Adopt one to track it as its own Latter device.

→ [Presence guide](presence.md)

### System settings
| Card | What it does |
| :--- | :--- |
| **Export Settings (.JSON)** | Download the whole System's settings, or one device's, as a `.json` file. Device exports include the device's live ESPHome select, switch, and number values. Full backups are Home Assistant's own: Latter's storage is included in every Home Assistant backup. |
| **Restore from File (.JSON)** | Upload an exported `.json` file to restore it. For a device export, choose the device to restore it onto; it can be a different device, to clone a setup. |
| **Notification Tester** | Send a test notification to any device, optionally with a snapshot from the primary camera. |
| **System Custom Color Library** | Up to 24 saved theme colors. Apply one to a device from that device's **Display & Home** page. |

---

## Devices

The **All Devices** page lists onboarded devices. **+ Add Device** adds a BLE phone, watch, or tag as a **BLE tag** entry (you can also add one from **Settings → Devices & Services → Latter → Add BLE tag**). Latter devices are added through Home Assistant's ESPHome discovery. What a device can do comes from its hardware manifest (display, roaming, wearable), not from a type setting. → [Existing ESPHome devices](existing-esphome.md)

Each device has five pages. The options on each page depend on what the device's hardware reports. A headless sensor won't show display settings.

| Page | Contents |
| :--- | :--- |
| **Overview** | Quick actions, power profile, apply a profile, assigned person, and device status. A value the device hasn't reported shows as —. |
| **Display & Home** | Color profile, home dock apps and their order, and wallpapers (5 built-in presets, plus uploads that can rotate on a schedule). Screen shape and resolution come from the device's hardware manifest. |
| **Audio & Voice** | Wake word and sensitivity, default speaker, the device's **Music Assistant Player** (its link to Music Assistant, needed for library playback), alert volume, and music sorting |
| **Power & Battery** | Sleep and wake timeouts, plus battery and power readings |
| **Device settings** | Device slug (read-only: the ESPHome node name), group, and area cards per page; BLE tracking settings (the BLE presence beacon follows **Enable BLE Proxy Area Tracking** and is shown read-only); diagnostics and the raw entity inspector; **Reset to defaults…**; and **Remove Device** |

**Reset to defaults…** opens a confirmation with two options, both on by default: **Device settings** (erases everything saved on the device; it restarts) and **Latter options for this device**. Wi-Fi and pairing are kept, as are the device's ESPHome binding and Music Assistant player link. It does the same as the [`latter.reset_device`](reference/services.md#latterreset_device) service; BLE tags only offer the Latter options.

> Most settings apply live: Studio saves them and pushes the change to the device without a reload. Adding or removing a device, or changing a device's bound ESPHome device, reloads the Latter integration; devices reconnect within a few seconds.

Uploaded wallpapers are stored in Latter's private storage (`.storage/latter/wallpapers/`), not in `/config/www`, so Home Assistant never serves them publicly. Devices and Studio load them through signed links that expire. Uploads from earlier versions are moved there automatically when Latter starts.
