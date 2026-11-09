# Latter Studio

Latter Studio is the **Latter** entry in the Home Assistant sidebar, with the Latter mark as its icon. Only admin users can see it. Use it for anything that's configuration rather than automation. Changes are pushed to devices immediately, so nothing needs to be reflashed.

Studio has two scopes, selected with the switcher at the top: **Devices** (where Studio opens) for one device at a time, and **System** for settings shared by every device. System pages work whether or not a device is selected; a System action that affects one device asks you which device.

There's no Save button: a setting applies as soon as you change it, like Home Assistant's own controls. Text and number fields apply when you press Enter or leave the field. If a change fails, Studio shows the reason in a red message at the bottom of the page and puts the setting back.

The address bar follows the page you're on (for example `/latter/devices/<id>/display` or `/latter/system/presence`), so reloading or pressing Back keeps your place, and you can bookmark a page. The **Visit** link on a Latter device's page in Home Assistant opens that device in Studio.

<!-- MEDIA: docs/media/studio-overview.png — System → Overview. -->

---

## System

Settings here live in `.storage/latter.site` and apply to every device.

### Overview
- **Issues:** every Latter repair that's open in Home Assistant (crashes, brownouts, firmware rollbacks, missing entities, BLE proxies, Music Assistant links), with the device it belongs to. **Open Repairs** opens Home Assistant's Repairs page, where you fix them.
- **System:** the Latter version (Latter itself updates through HACS), **Check Firmware Updates**, which asks every device for a firmware update and says how many have one, and counts of online devices, Latter devices, BLE-tracked devices, devices with an assigned person, and BLE area proxies. Each count opens the matching device list or page.
- **Configured Items:** how many remotes, volume overrides, cameras, calendars, groups, and saved profiles are set up.

### Shared Entities
| Card | What it does |
| :--- | :--- |
| **Whole-Home Entities** | Weather provider, alarm panel, primary thermostat, entry lock, garage door, and robot vacuum. These drive the on-device weather page and Whole-Home Hub. |
| **Cameras & Doorbell Audio** | Up to 10 cameras for the on-device camera carousel and doorbell popups, plus the **Doorbell Audio Noise Reduction** level (Strong, Light, Off) for listening to a doorbell, and **Test the Door Speaker**, which speaks a test sentence on the primary camera's speaker with TTS, from the device you choose. Under **Doorbells**, each camera shows, read-only, the doorbell ring entity Latter found for it (and when it last rang or changed) and which devices are listening or replying right now. Listen and push-to-talk replies are experimental. |
| **Calendars** | Calendars merged into the on-device agenda. Duplicate events across calendars are removed, and events with a location get a map. |

### Media & Remotes
| Card | What it does |
| :--- | :--- |
| **Remote Controls** | TVs, streaming boxes, and AV receivers available as remote slots, up to 10. Latter pairs each `remote.*` with the `media_player.*` on the same device. It has key mappings for Android TV, Fire TV, Bravia, Apple TV, LG webOS, and Denon/Marantz, and falls back to `remote.send_command` for everything else. |
| **Remote Control Groups** | Which remote controls appear on which devices, or in which areas (**Device Assignments**). |
| **Speaker Volume Overrides** | Sends volume changes for a speaker to a different entity, such as an AV receiver `media_player` or an amplifier's `number` entity. |

### Groups & Profiles
- **Configuration Profiles:** choose a device and capture its display, dock, wake word, and timeout settings, then apply them to one device, a group, or all devices.
- **Device Groups:** logical groupings such as handhelds, bedrooms, or wall panels, used for organization and when applying profiles.
- **Custom Color Library:** up to 24 saved theme colors shared by every device; **Add Color** opens a color picker. Apply one to a device from that device's **Display & Home** page.
- **Bulk Device Controls:** change a display, sleep, voice, sound, music, or Area setting on every device in a group (or all roaming or stationary devices) at once. When the devices disagree, the control shows **Mixed**.

### BLE & Area Presence
- **Live Area Presence & Sensor Fusion:** per-area occupancy, the devices and people in each area, and each area's fusion mode. **Fusion Settings** under each area set the occupancy threshold (weighted mode, 20 to 95%) and which of the area's sensors count (none picked means all of them). Changes apply at once.
- **Per-Area BLE Signal Calibration:** live raw and effective RSSI per area for a selected device. Includes **Calibrate Current Area**, ±1 dB adjustment, and a **Fast Refresh** switch (updates every 1.5 s while the page is open; off, the page updates when something changes).
- **Discovered Bluetooth Devices:** named BLE devices, `private_ble_device` entities, and iBeacons your scanners can hear. **Adopt** one to track it as a BLE tag, or use **Add BLE Tag** to enter an address.

→ [Presence guide](presence.md)

### Tools
| Card | What it does |
| :--- | :--- |
| **Notifications & Announcements** | Choose **Notification** (an on-screen alert with a chime on one device, every device, or the devices in occupied Areas, optionally with a snapshot from the primary camera) or **Announcement** (the message spoken with text-to-speech on every speaker, or on the speakers in occupied Areas), then **Send**. Use it to test how alerts look and sound. |
| **Backup & Restore** | **Export**: download the whole System's settings, or one device's, as a `.json` file (device exports include the device's live ESPHome select, switch, and number values). **Restore**: upload an exported file; for a device export, choose the device to restore it onto (it can be a different device, to clone a setup). Full backups are Home Assistant's own: Latter's storage is included in every Home Assistant backup. |
| **System & Device Logs** | Latter's own events plus the Latter, ESPHome and Music Assistant entries from the Home Assistant log. Show all entries, Latter only, warnings and errors, or one device's; **Open in Home Assistant** opens Home Assistant's log page filtered the same way. **Copy** and **Clear** act on Latter's list. |

---

## Devices

The **All Devices** page lists onboarded devices. **Add Device** opens Latter in Home Assistant, where **Add Device** adds a Latter Device, with or without a screen (Home Assistant's ESPHome discovery offers new Devices too). **Add BLE Tag** adds a phone, watch, or Bluetooth tag as a **BLE Tag** entry (you can also add one from **Settings → Devices & Services → Latter → Add BLE Tag**). What a device can do comes from its hardware manifest (display, roaming, wearable), not from a type setting. → [Existing ESPHome devices](existing-esphome.md)

Each device has up to six pages. The options on each page depend on what the device's hardware reports. A headless sensor won't show display settings.

| Page | Contents |
| :--- | :--- |
| **Overview** | A **Needs Attention** banner when the device has open repairs; **Status** (online or offline, firmware, SDK revision, Area, battery, Wi-Fi signal, IP address, active speaker and what's playing, location mode, nearest BLE proxy, hardware model and ESPHome node name), with **Tools**, **Open in Home Assistant** (the ESPHome device page) and **Download Backup**; **Quick Actions**: the device's quick actions, power profile, **Device Group**, apply a profile, and assigned person. A value the device hasn't reported shows as —. |
| **Display & Home** | Color profile, Area cards per page, home dock apps and their order (the device shows exactly these apps, plus Settings, and **Settings → Home** on the device edits the same list), the **Activity Card** (shown on the Home screen while an enabled source has something to show; one switch for the card and one per source: **Calendar**, **Music Queue**, **Stopwatch**, **Alarms**, **Timers**, all on by default; the sources hide while the card is off), and wallpapers (5 built-in presets, plus uploads that can rotate on a schedule). Screen shape and resolution come from the device's hardware manifest. |
| **Audio & Voice** | **Voice Assistant & Wake Word**: Wake Word Mode; the wake words (Home Assistant's Wake Word and Wake Word 2, the one wake-word control) and per-model sensitivity, which hide while Wake Word Mode is Disabled; Home Assistant's Assistant and Finished Speaking Detection; Visual Profile and Wake Screen on Assist, which stay because the action button and Home Assistant can still start the assistant; **Voice Follows Me** and its delay (roaming devices: how long Bluetooth must place the device in a new Area before its Home Assistant Area follows, 3 to 60 s), **Media Follows This Device to Its New Area** (one setting for Bluetooth moves and Area picks on the device), and **Sound & Media Player**, grouped as **Sound** (alert volume), **Music Screen** (album art, overlay, shortcuts), **Speaker** (default speaker, the device's **Music Assistant Player**, needed for library playback) and **Library Sorting** |
| **Power & Battery** | **Sleep & Wake** timeouts, plus **Power & Battery** readings |
| **BLE & Area Presence** | **Area Tracking**: track the Area with BLE proxies, switch the active Area on movement (the BLE presence beacon follows **Track the Area with BLE Proxies** and is shown read-only), fallback Area and external Area sensor. **BLE Identity**: BLE target and iBeacon UUID. |
| **Tools** | **Diagnostics**: **Download Diagnostics** (a redacted JSON file), network and status entities, a **Developer** group (profiler, memory, weather simulation) and **All Entities**. **Replace Hardware**: opens Latter in Home Assistant to reconfigure or replace the hardware. **Danger Zone**: **Reset…** and **Remove…** |

**Reset…** opens a confirmation with two options, both on by default: **Settings Saved on the Device** (erases everything saved on the device; it restarts) and **Latter Settings for This Device**. Wi-Fi and pairing are kept, as are the device's ESPHome binding and Music Assistant player link. It does the same as the [`latter.reset_device`](reference/services.md#latterreset_device) service; BLE tags only offer the Latter settings.

> Most settings apply live: Studio saves them and pushes the change to the device without a reload. Adding or removing a device, or changing a device's bound ESPHome device, reloads the Latter integration; devices reconnect within a few seconds.

Uploaded wallpapers are stored in Latter's private storage (`.storage/latter/wallpapers/`), not in `/config/www`, so Home Assistant never serves them publicly. Devices and Studio load them through signed links that expire.
