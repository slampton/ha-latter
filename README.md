# Latter

A Home Assistant integration for ESPHome touch displays, wearables, and sensors. Each device knows which area it is in. Latter maps your Home Assistant entities to it at runtime, so you don't hardcode entity IDs into firmware.

[![Validate](https://github.com/slampton/ha-latter/actions/workflows/validate.yml/badge.svg)](https://github.com/slampton/ha-latter/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/slampton/ha-latter)](https://github.com/slampton/ha-latter/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5)](https://hacs.xyz)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

<!-- MEDIA: docs/media/hero.jpg — all five devices on a desk, each showing a different app. -->

Latter is split across two repositories:

| Repository | Runs on | Responsibility |
| :--- | :--- | :--- |
| **ha-latter** (this repo) | Home Assistant | The integration and the **Latter Studio** panel. Maps entities to devices, tracks which area each device is in, re-encodes images so an ESP32 can decode them, and provides services for automations. |
| **[esphome-latter-core](https://github.com/slampton/esphome-latter-core)** | The ESP32 | Firmware for five Waveshare displays, one-line packages for ESPHome devices you already own, and the SDK for building your own device. |

You need both for the finished devices. If you only want BLE presence or Studio for ESPHome devices you already run, this repo alone is enough.

---

## Why this exists

Most ESPHome display projects bake entity IDs into the YAML. A new speaker, a renamed light, or a display moved to another area all mean editing YAML and reflashing. Latter keeps that mapping in Home Assistant instead. The firmware asks what's in its area and what's playing, and Latter answers based on where the device is right now.

## What it does

### Devices know which area they're in
Latter reads RSSI from the Bluetooth proxies you already have and gives every Latter device a **Current Area** sensor. Phones and watches get one too, through Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration.

When a handheld changes areas, Latter also updates its Home Assistant Area. "Turn off the lights" to Assist then targets the area you're standing in.

Per-area occupancy sensors combine BLE with any mmWave, PIR, or door sensors already in that area. Areas on different floors get a 6 dB penalty, so a device upstairs doesn't flap into the area below it.

<!-- MEDIA: docs/media/presence-walk.gif — walking between areas with Wrist Assist while the Studio presence card switches areas. -->

→ [How presence works, and how it compares to Bermuda](docs/presence.md)

### Music Assistant on a small screen
- **Browsing:** favorites, playlists, artists, albums, podcasts, radio, and audiobooks, in pages sized to the device.
- **Speaker moves:** move the queue from one speaker to another and it picks up within a few seconds of where it left off.
- **Lyrics and bios:** lyrics come from Music Assistant or [LRCLIB](https://lrclib.net); artist and album bios come from Wikipedia.
- **Any media player:** transport and volume work with any `media_player`, and volume can be routed to an AV receiver.

### Area control that follows the device
The device's current area drives its controls:
- Scenes and switches.
- Lights: brightness, color, and color temperature.
- Covers, fans, climate, and media.

Whole-home tiles cover the alarm panel, thermostat, lock, garage door, and robot vacuum.

### Doorbell popups
Latter finds your doorbell's ring entity on its own. A press wakes the displays and shows a camera snapshot for 20 seconds. Two-way talk exists, but is [experimental](#project-status).

<!-- MEDIA: docs/media/doorbell.gif — doorbell press, camera popup on the device. -->

### Images an ESP32 can decode
The ESP32 has two problems with Home Assistant's images: ESP-IDF's JPEG decoder rejects progressive JPEGs, and the HTTP client can't resolve `.local` hostnames.

Latter re-encodes album art, wallpapers, camera snapshots, and calendar-event maps as baseline JPEG at the panel's exact resolution, with a circular mask on round screens. It serves them from Home Assistant's numeric LAN address using signed, expiring URLs.

### Latter Studio
Latter Studio is an admin-only sidebar panel for everything that isn't an automation:
- Shared entities.
- TV remotes and AV receiver volume routing.
- BLE calibration.
- Device groups and reusable profiles.
- Wallpapers and backups.
- WireGuard key generation.

<!-- MEDIA: docs/media/studio-overview.png — Studio, System → Overview. -->

→ [Studio guide](docs/studio.md)

---

## Get started

**1. Get a device.** Each of these runs the full Latter firmware without modification:

| Device | Hardware | Screen |
| :--- | :--- | :--- |
| Pocket Assistant | [Waveshare ESP32-S3-Touch-AMOLED-1.75C][ws-175c] | 1.75" round AMOLED, 466×466 |
| Mobile Assistant | [Waveshare ESP32-S3-Touch-AMOLED-2.16][ws-216] | 2.16" square AMOLED, 480×480 |
| Wrist Assist | [Waveshare ESP32-S3-Touch-AMOLED-2.06][ws-206] | 2.06" watch AMOLED, 410×502 |
| Remote Assistant | [Waveshare ESP32-P4-WIFI6-Touch-LCD-3.5][ws-p4-35] | 3.5" IPS, 320×480 |
| Desk Assistant | [Waveshare ESP32-P4-WIFI6-Touch-LCD-4B][ws-p4-4b] | 4" IPS, 720×720 |

<sub>Some hardware links are affiliate links. Buying through them supports the project at no extra cost to you.</sub>

**2. Flash it** from Chrome or Edge with a USB-C cable using the [web installer](https://slampton.github.io/esphome-latter-core/). → [Flashing guide](https://github.com/slampton/esphome-latter-core/blob/main/docs/flashing.md)

**3. Install Latter** with HACS:
1. Open **HACS → ⋮ → Custom repositories**, add `https://github.com/slampton/ha-latter`, and pick category **Integration**.
2. Download **Latter**, then restart Home Assistant.

**4. Add the device.** Once the device is on your network and adopted by the ESPHome integration, Home Assistant shows **Discovered: Latter**. Accept it, then open **Latter** in the sidebar.

→ [Full walkthrough with screenshots](docs/getting-started.md)

---

## Already running ESPHome?

You don't need Latter hardware to use most of this.
- **Bridge any ESPHome device into Studio** without editing its YAML. You get grouping, live entity inspection, and backups of its settings. → [Existing ESPHome devices](docs/existing-esphome.md)
- **Area presence from the proxies you already have.** Phones, watches, and iBeacons can be tracked without flashing anything new. → [Presence](docs/presence.md)
- **One-line packages** add a BLE beacon, BLE proxy, WireGuard roaming, or diagnostics to an existing config. → [Mixins](https://github.com/slampton/esphome-latter-core/blob/main/docs/mixins.md)
- **Coming from Bermuda?** Read [what's different, and what isn't there yet](docs/presence.md#coming-from-bermuda).

## Building your own?

Everything the finished devices use is documented and open to you:

| Reference | Covers |
| :--- | :--- |
| [Services](docs/reference/services.md) | All 16 `latter.*` services, their fields, and special targets such as `follow_me` |
| [Entities](docs/reference/entities.md) | Every entity Latter creates, its attributes, update cadence, and the `latter_event` bus event |
| [HTTP API](docs/reference/http-api.md) | Image endpoints, the signed-URL model, and the transcoder output spec |
| [Device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md) | What a device must implement to be discovered and receive data |
| [Building a GUI](https://github.com/slampton/esphome-latter-core/blob/main/docs/building-a-gui.md) | Writing your own UI on top of Latter Core |

---

## Requirements

| | Version | Notes |
| :--- | :--- | :--- |
| Home Assistant | 2026.10 or newer | |
| ESPHome | 2026.10 or newer | Only needed if you build Latter firmware yourself |
| Music Assistant | 2.10.8 or newer, optional | Required for library browsing, queue transfer, and the default intercom speaker set. Basic transport and volume work without it. |
| Bluetooth proxies | At least one per area you want to detect | ESPHome proxies are tested. Other HA Bluetooth scanners should work but are unverified. |
| `ffmpeg` | Optional | Used for doorbell audio. Bundled with Home Assistant OS. |

**Network access.** Everything runs locally except four lookups. Calendar-event maps use OpenStreetMap tiles and Nominatim geocoding. Lyrics come from LRCLIB and bios from Wikipedia, and both are used only when Music Assistant doesn't already have the text.

---

## Project status

This is version **2.2.0**, built and maintained by one person and tested on the five devices listed above.

| Area | Status |
| :--- | :--- |
| Device discovery, Studio, area control, media, notifications, backups | Stable |
| BLE area presence and area occupancy | Stable. See the [known gaps](docs/presence.md#known-limitations). |
| Doorbell ring detection and camera popup | Stable |
| Doorbell two-way talk, SIP client | **Experimental.** The SIP client supports only G.711 μ-law, has no NAT traversal, and has not been tested against a range of PBXs. |

What's not here yet:
- No `device_tracker` entities. The presence engine creates area and distance sensors, but nothing a `person` entity can use.
- BLE calibration is a single offset per area. There is no per-scanner calibration.
- CI runs `hassfest` and HACS validation. There is no unit test suite yet.

Bugs and feature requests: [issues](https://github.com/slampton/ha-latter/issues).

---

## Documentation

| Guide | For |
| :--- | :--- |
| [Getting started](docs/getting-started.md) | Your first device, from box to working |
| [Latter Studio](docs/studio.md) | Every Studio page and what it controls |
| [Presence](docs/presence.md) | BLE area tracking, calibration, occupancy, and migrating from Bermuda |
| [Existing ESPHome devices](docs/existing-esphome.md) | Bridging devices you already have |
| [Automations](docs/automations.md) | Ready-to-use automation recipes |
| [Troubleshooting](docs/troubleshooting.md) | Common problems and their fixes |
| [Reference](docs/reference/) | Services, entities, and the HTTP API |

## Removal

1. Go to **Settings → Devices & Services → Latter** and delete each entry.
2. Remove Latter in HACS, then restart Home Assistant.

Leftover data:
- Studio settings and backups stay in `.storage/latter.site`, `.storage/latter.backups`, and `.storage/latter.runtime.*`.
- Uploaded wallpapers stay in `/config/www/latter_wallpapers/`.

Delete these by hand if you want a clean slate.

## Support

Latter is free and open source. Hardware bring-up costs real money, so if the project is useful to you:
- [GitHub Sponsors](https://github.com/sponsors/slampton)
- [Buy Me a Coffee](https://www.buymeacoffee.com/slampton)

## How this was built

Latter is designed, tested on hardware, and maintained by Sean Lampton, a systems engineer. AI coding assistants are used for drafting code and documentation. Architecture decisions, hardware bring-up, and testing on physical devices are done by hand. If something here is wrong, please [open an issue](https://github.com/slampton/ha-latter/issues).

## License

[Apache License 2.0](LICENSE)

[ws-175c]: https://www.waveshare.com/esp32-s3-touch-amoled-1.75c.htm
[ws-216]: https://www.waveshare.com/esp32-s3-touch-amoled-2.16.htm
[ws-206]: https://www.waveshare.com/esp32-s3-touch-amoled-2.06.htm
[ws-p4-35]: https://www.waveshare.com/esp32-p4-wifi6-touch-lcd-3.5.htm
[ws-p4-4b]: https://www.waveshare.com/esp32-p4-wifi6-touch-lcd-4b.htm
