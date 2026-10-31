# Troubleshooting

## Setup

**"Discovered: Latter" never appears**

Latter discovers devices from Home Assistant's device and service registries, not from the network. Check these in order:
1. **The device is in the ESPHome integration and online.** Latter needs the ESPHome device first.
2. **The device registers at least one Latter action.** Look in **Developer Tools → Actions** for `esphome.<name>_latter_ping` or `esphome.<name>_set_browse_slots`. If neither is there, the firmware or mixin isn't included.
3. **A rescan has run.** Latter rescans 5 seconds after any device-registry change, and when ESPHome registers a new action. Reloading the ESPHome integration triggers a rescan.

You can also add the device by hand: **Settings → Devices & Services → Add Integration → Latter**.

**The device shows up, but Music, Area, and Remote screens stay empty or taps do nothing**

The device can't call Home Assistant services. Go to **Settings → Devices & Services → ESPHome → (device) → Configure** and enable **Allow the device to perform Home Assistant actions**.

**I renamed the device and now nothing updates**

Latter derives the slug from the device's name in Home Assistant. Latter firmware derives its sensor names from the `device_slug` substitution. If you rename a device, set `device_slug` in its YAML to match the new name, lowercase with underscores. For example, `Kitchen Pocket` becomes `kitchen_pocket`. Then update the slug in **Studio → Devices → Administration**.

---

## Images

**Album art, wallpapers, or camera snapshots don't load**

Latter serves images from Home Assistant's numeric LAN IP, because ESP32 firmware can't resolve `.local` names. Check:
- **The device can reach Home Assistant's IP** on Home Assistant's HTTP port. Watch out for VLANs and firewalls between them.
- **Your external URL setup, if you use a reverse proxy.** Set **Studio → System Administration → Reverse Proxy & External Access** only if the device has to go through the proxy. Most setups should leave it empty.

---

## Presence

**A roaming device never changes areas**
- **Proxies lack an Area.** Every Bluetooth proxy must be assigned to an Area in Home Assistant. Home Assistant raises a repair issue, **"No Area-assigned Bluetooth proxies found"**, when Latter can't map any scanner to an area.
- **Roaming is off.** Check that **This device roams** was enabled when the device was added. You can change it in the integration's options.
- **Look at the live readings.** Open **Studio → BLE & Area Presence**. If an area never shows a reading, its proxy isn't hearing the device.

**The device keeps choosing the neighboring area**

Calibrate it. Stand in the area that should win and click **Calibrate Current Area**. → [Calibrating](presence.md#calibrating)

**A phone isn't tracked**

The phone has to be set up in Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration first. Latter doesn't resolve IRKs itself. Then adopt the `private_ble_device` entity in Studio.

---

## Music

**Library browsing is empty**

Library browsing, queue transfer, and the default intercom speaker list need the Music Assistant integration loaded in Home Assistant. Without it, only transport controls and volume work.

**Volume buttons do nothing**

If the speaker's real volume control is an AV receiver, map the speaker in **Studio → Media & Remotes → Speaker Volume Overrides**.

---

## Getting help

When you [open an issue](https://github.com/slampton/ha-latter/issues), attach the integration's diagnostics: **Settings → Devices & Services → Latter → ⋮ → Download diagnostics**. Read the file before posting it. It can contain your LAN IP address and signed image URLs.
