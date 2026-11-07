# Latter Studio

Latter Studio is the **Latter** entry in the Home Assistant sidebar. Only admin users can see it. Use it for anything that's configuration rather than automation. Changes are pushed to devices immediately, so nothing needs to be reflashed.

Studio has two scopes, selected with the switcher at the top: **Devices** (where Studio opens) for one device at a time, and **System** for settings shared by every device. System pages work whether or not a device is selected; a System action that affects one device asks you which device.

The **Save** button saves System settings and the open device's settings separately, so saving one never changes the other. If a save fails, Studio shows the reason in a red message at the bottom of the page.

The address bar follows the page you're on (for example `/latter/devices/<id>/display` or `/latter/system/presence`), so reloading or pressing Back keeps your place, and you can bookmark a page. The **Visit** link on a Latter device's page in Home Assistant opens that device in Studio.

<!-- MEDIA: docs/media/studio-overview.png — System → System overview. -->

---

## System

Settings here live in `.storage/latter.site` and apply to every device.

### System overview
- **Issues:** every Latter repair that's open in Home Assistant (crashes, brownouts, firmware rollbacks, missing entities, BLE proxies, Music Assistant links), with the device it belongs to. **Open Repairs** opens Home Assistant's Repairs page, where you fix them.
- **System:** the Latter version (Latter itself updates through HACS), **Check firmware updates**, which asks every device for a firmware update and says how many have one, and counts of online devices, Latter devices, BLE-tracked devices, devices with an assigned person, and BLE area proxies. Each count opens the matching device list or page.
- **Configured integrations:** how many remotes, volume overrides, cameras, calendars, groups, and saved profiles are set up.

### Shared entities
| Card | What it does |
| :--- | :--- |
| **Whole-home entities** | Weather provider, alarm panel, primary thermostat, entry lock, garage door, and robot vacuum. These drive the on-device weather page and Whole-Home Hub. |
| **Cameras & doorbell audio** | Up to 10 cameras for the on-device camera carousel and doorbell popups, plus the **Doorbell audio noise reduction** level (Strong, Light, Off) for listening to a doorbell, and **Test the door speaker**, which speaks a test sentence on the primary camera's speaker with TTS, from the device you choose. Listen and push-to-talk replies are experimental. |
| **Calendars** | Calendars merged into the on-device agenda. Duplicate events across calendars are removed, and events with a location get a map. |

### Media & remotes
| Card | What it does |
| :--- | :--- |
| **Remote inventory** | TVs, streaming boxes, and AV receivers available as remote slots, up to 10. Latter pairs each `remote.*` with the `media_player.*` on the same device. It has key mappings for Android TV, Fire TV, Bravia, Apple TV, LG webOS, and Denon/Marantz, and falls back to `remote.send_command` for everything else. |
| **Remote control groups** | Which remotes appear on which devices, or in which areas. |
| **Speaker volume overrides** | Sends volume changes for a speaker to a different entity, such as an AV receiver `media_player` or an amplifier's `number` entity. |

### Groups & profiles
- **Configuration profiles:** choose a device and capture its display, dock, wake word, and timeout settings, then apply them to one device, a group, or all devices.
- **Device groups:** logical groupings such as handhelds, bedrooms, or wall panels, used for organization and when applying profiles.
- **Bulk Device controls:** change a display, sleep, voice, sound, music, or Area setting on every device in a group (or all roaming or stationary devices) at once. When the devices disagree, the control shows **Mixed**.

### BLE & Area presence
- **Live Area presence & sensor fusion:** per-area occupancy, the devices and people in each area, and each area's fusion mode. **Fusion settings** under each area set the occupancy threshold (weighted mode, 20 to 95%) and which of the area's sensors count (none picked means all of them). Changes apply at once.
- **Per-Area BLE signal calibration:** live raw and effective RSSI per area for a selected device. Includes **Calibrate current Area**, ±1 dB adjustment, and a **Fast refresh** switch (updates every 1.5 s while the page is open; off, the page updates when something changes).
- **Discovered nearby Bluetooth devices:** named BLE devices, `private_ble_device` entities, and iBeacons your scanners can hear. **Adopt** one to track it as its own Latter device.

→ [Presence guide](presence.md)

### System settings
| Card | What it does |
| :--- | :--- |
| **Export settings** | Download the whole System's settings, or one device's, as a `.json` file. Device exports include the device's live ESPHome select, switch, and number values. Full backups are Home Assistant's own: Latter's storage is included in every Home Assistant backup. |
| **Restore from file** | Upload an exported `.json` file to restore it. For a device export, choose the device to restore it onto; it can be a different device, to clone a setup. |
| **Notification tester** | Send a test notification to any device, optionally with a snapshot from the primary camera. |
| **Custom color library** | Up to 24 saved theme colors; **Add color** opens a color picker. Apply one to a device from that device's **Display & home** page. |

---

## Devices

The **All Devices** page lists onboarded devices. **Add BLE Device** adds a BLE phone, watch, or tag as a **BLE tag** entry (you can also add one from **Settings → Devices & Services → Latter → Add BLE tag**). **Add display** opens Latter in Home Assistant, where **Add Device** adds a Latter display (Home Assistant's ESPHome discovery offers new displays too). What a device can do comes from its hardware manifest (display, roaming, wearable), not from a type setting. → [Existing ESPHome devices](existing-esphome.md)

Each device has five pages. The options on each page depend on what the device's hardware reports. A headless sensor won't show display settings.

| Page | Contents |
| :--- | :--- |
| **Overview** | A **Needs attention** banner when the device has open repairs; battery, Wi-Fi and firmware; **Now** (the device's Area, its active speaker and what's playing); device status; quick actions, power profile, apply a profile, and assigned person. A value the device hasn't reported shows as —. |
| **Display & home** | Color profile, home dock apps and their order (applied when you save; the device shows exactly these apps, plus Settings, and **Settings → Home** on the device edits the same list), and wallpapers (5 built-in presets, plus uploads that can rotate on a schedule). Screen shape and resolution come from the device's hardware manifest. |
| **Audio & voice** | Wake word and sensitivity, **Voice Follows Me** and its delay (roaming devices: how long Bluetooth must place the device in a new Area before its Home Assistant Area follows, 3 to 60 s), **Media follows this Device to its new Area** (one setting for Bluetooth moves and Area picks on the device), default speaker, the device's **Music Assistant player** (its link to Music Assistant, needed for library playback), alert volume, and music sorting |
| **Power & battery** | Sleep and wake timeouts, plus battery and power readings |
| **Device settings** | Device slug (read-only: the ESPHome node name), group, and area cards per page; BLE tracking settings (the BLE presence beacon follows **Track the Area with BLE proxies** and is shown read-only); diagnostics and the raw entity inspector; **In Home Assistant** (**Open in Home Assistant** for the ESPHome device page, **Download diagnostics**, and **Replace hardware**, which opens Latter in Home Assistant to reconfigure or replace the device's hardware); **Reset to defaults** (**Reset…**); and **Remove Device** (**Remove…**) |

**Reset…** opens a confirmation with two options, both on by default: **Device settings** (erases everything saved on the device; it restarts) and **Latter options for this Device**. Wi-Fi and pairing are kept, as are the device's ESPHome binding and Music Assistant player link. It does the same as the [`latter.reset_device`](reference/services.md#latterreset_device) service; BLE tags only offer the Latter options.

> Most settings apply live: Studio saves them and pushes the change to the device without a reload. Adding or removing a device, or changing a device's bound ESPHome device, reloads the Latter integration; devices reconnect within a few seconds.

Uploaded wallpapers are stored in Latter's private storage (`.storage/latter/wallpapers/`), not in `/config/www`, so Home Assistant never serves them publicly. Devices and Studio load them through signed links that expire. Uploads from earlier versions are moved there automatically when Latter starts.
