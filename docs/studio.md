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
| **Cameras & Doorbell Two-Way Audio** | Up to 10 cameras for the on-device camera carousel and doorbell popups. Talkback and SIP settings are here too; both are experimental. |
| **Calendars** | Calendars merged into the on-device agenda. Duplicate events across calendars are removed, and events with a location get a map. |
| **Pinned Area Entities** | Entities shown at the top of Area Control in every area. |

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
| **Create or Export Backup** | Back up the whole system or a single device. Device backups include the device's live ESPHome select, switch, and number values. You can save to the internal vault or download a `.json` file. |
| **Restore from File** / **Saved Local Backups** | Restore a backup. A device backup can be restored onto a different device to clone its setup. The vault keeps 25 backups. |
| **Reverse Proxy & External Access** | An external base URL for the device **Visit** links, for setups behind a reverse proxy. |
| **Notification Tester** | Send a test notification to any device. |
| **System Custom Color Library** | Up to 24 saved theme colors. |
| **1-Line Drop-In ESPHome Mixin Packages** | Ready-to-copy package lines for [mixins](https://github.com/slampton/esphome-latter-core/blob/main/docs/mixins.md). |

---

## Devices

The **All Devices** page lists onboarded devices, plus ESPHome devices not yet in Latter. **Add Device to Latter** bridges an existing ESPHome device or adopts a BLE device. → [Existing ESPHome devices](existing-esphome.md)

Each device has five pages. The options on each page depend on what the device's hardware reports. A headless sensor won't show display settings.

| Page | Contents |
| :--- | :--- |
| **Overview** | Quick actions, power profile, apply a profile, assigned person, device status, and a live view of every entity on the device |
| **Display & Home** | Color profile, display geometry, home dock apps and their order, area cards per page, and wallpapers (5 built-in presets, plus uploads that can rotate on a schedule) |
| **Audio & Voice** | Wake word and sensitivity, default speaker, alert volume, and music sorting |
| **Power & Battery** | Sleep and wake timeouts, plus battery and power readings |
| **Administration** | Device slug, type, and group; BLE tracking settings; WireGuard roaming; and **Remove Device** |

### WireGuard roaming

This feature keeps a portable device connected to Home Assistant over a phone hotspot or other remote Wi-Fi. Latter **generates keys and config text only**. It does not set up the WireGuard server for you.

1. Under **System WireGuard Server Endpoint**, enter your server's public `host:port`, its public key, and the tunnel subnet. The default subnet is `10.10.10.0/24`.
2. Under **Device Roaming Identity**, generate keys. Latter creates an X25519 keypair and a preshared key, and assigns the next free tunnel IP.
3. Copy the generated ESPHome snippet into the device's config, or use the [`roaming_vpn` mixin](https://github.com/slampton/esphome-latter-core/blob/main/docs/mixins.md#roaming_vpn) with your `secrets.yaml`.
4. Copy the generated peer block into your WireGuard server: a router, or the Home Assistant WireGuard add-on.

> Key generation and every config save reload the Latter config entry for that device. The device reconnects within a few seconds.
