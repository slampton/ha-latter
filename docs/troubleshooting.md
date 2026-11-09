# Troubleshooting

## Setup

**"Discovered: Latter" never appears**

Latter discovers devices from Home Assistant's device and service registries, not from the network. Check these in order:
1. **The device is in the ESPHome integration and online.** Latter needs the ESPHome device first.
2. **The device registers at least one Latter action.** Look in **Developer Tools → Actions** for `esphome.<name>_latter_ping` or `esphome.<name>_set_browse_slots`. If neither is there, the device isn't running Latter firmware.
3. **A rescan has run.** Latter rescans 5 seconds after any device-registry change, and when ESPHome registers a new action. Reloading the ESPHome integration triggers a rescan.

You can also add the device by hand: **Settings → Devices & Services → Add Integration → Latter**.

**The device shows up, but Music, Area, and Remote screens stay empty or taps do nothing**

The device can't call Home Assistant services. Go to **Settings → Devices & Services → ESPHome → (device) → Configure** and enable **Allow the device to perform Home Assistant actions**.

**I renamed the device and now nothing updates**

Latter finds the ESPHome device by its device ID (or by its MAC address if the ESPHome device was re-created), so renaming the device in Home Assistant changes nothing. The Device's slug is the ESPHome node name, which Latter firmware also uses (the `device_slug` substitution). If you rename the ESPHome node, set `device_slug` in its YAML to match, lowercase with underscores (for example, `Kitchen Pocket` becomes `kitchen_pocket`). Then open **Settings → Devices & Services → Latter**, choose the Device, and run **Reconfigure or Replace Hardware** with the same ESPHome device selected. Latter picks up the new node name and reloads.

---

## Images

**Album art, wallpapers, or camera snapshots don't load**

Latter serves images from Home Assistant's numeric LAN IP, because ESP32 firmware can't resolve `.local` names. Check:
- **The device can reach Home Assistant's IP** on Home Assistant's HTTP port. Watch out for VLANs and firewalls between them.
- **Image URLs use the LAN IP.** Image URLs always use Home Assistant's LAN IP, never an external or reverse-proxy URL, so the device must be able to reach it directly.

---

## Presence

**A roaming device never changes areas**
- **Proxies lack an Area.** Every Bluetooth proxy must be assigned to an Area in Home Assistant. Home Assistant raises a repair issue, **"No Area-assigned Bluetooth proxies found"**, when Latter can't map any scanner to an area.
- **Bluetooth area tracking is off.** Check that **Track the Area with BLE Proxies** was enabled when the device was added. To change it, use **Studio → Devices → your device → BLE & Area Presence → Track the Area with BLE Proxies**, or the device's **Reconfigure or Replace Hardware** entry under **Settings → Devices & Services → Latter**.
- **The device's beacon is off.** Latter firmware ships with **Area: BLE Presence Beacon** off and Latter turns it on when the device connects with tracking enabled. If you turned the switch off by hand, reconnecting the device (or saving its options) turns it back on.
- **Look at the live readings.** Open **Studio → BLE & Area Presence**. If an area never shows a reading, its proxy isn't hearing the device.

**The device keeps choosing the neighboring area**

Calibrate it. Stand in the area that should win and click **Calibrate Current Area**. → [Calibrating](presence.md#calibrating)

**A phone isn't tracked**

The phone has to be set up in Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration first. Latter doesn't resolve IRKs itself. Then adopt the `private_ble_device` entity in Studio.

---

## Music

**Library browsing is empty**

Library browsing, queue transfer, and the default intercom speaker list need the Music Assistant integration loaded in Home Assistant. Without it, only transport controls and volume work.

**A repair asks you to pick the Music Assistant player for a device**

Music Assistant identifies a Latter device's Sendspin player by a key hash, not by its MAC address, and doesn't link it to the ESPHome device. So Latter can't find the device's own Music Assistant player by itself, and library playback, queues and lyrics on that device fail until it's linked. Open the repair (**Settings → Repairs**), pick the device's player (it's pre-selected when exactly one Music Assistant player has the same manufacturer and model as the ESPHome device), and submit. You can change the link later in **Studio → (device) → Audio & Voice → Music Assistant Player**.

**Volume buttons do nothing**

If the speaker's real volume control is an AV receiver, map the speaker in **Studio → Media & Remotes → Speaker Volume Overrides**.

---

## Device health

**A repair says the device restarted after a crash**

The device reported a panic or watchdog reset when it booted. Open its logs in ESPHome Device Builder before it restarts again: ESPHome prints the decoded backtrace to every log client until the next restart, and decoding needs the build the device is running. The repair shows the Latter SDK rev and the boot time, and clears when a later boot is clean (power-on, external, software, deep sleep, USB reset).

**A repair says the device restarted after a brownout**

The supply voltage sagged below the safe level. Try another power supply or USB cable, or charge the battery.

**A repair says a firmware update failed**

The update didn't boot, so the device went back to the previous firmware. Check the build logs and install the update again; the repair clears after a successful update.

The last reported reset reason, crash flag, rollback flag and SDK rev for each Device are in Latter's diagnostics download.

**Firmware updates are very slow or stall at 0%, or the device drops off Wi-Fi**

Check the device's **Wi-Fi Signal** sensor. Below about -70 dBm, updates slow down sharply: ESPHome may judge the link lossy and switch the upload to UDP, which is much slower. Two common causes:

- **Devices docked next to each other.** Latter devices (and other 2.4 GHz gear) a few centimeters apart detune each other's antennas. Keep docked devices at least 30 cm apart; moving one device clear of the others can improve the signal of both by 15-20 dB.
- **Distance or walls to the access point.** Move the device closer for the update, or check that it joined the nearest access point.

Start one update at a time: ESPHome Device Builder runs simultaneous uploads in parallel, and they slow each other down.

---

## Getting help

When you [open an issue](https://github.com/slampton/ha-latter/issues), attach the integration's diagnostics: **Settings → Devices & Services → Latter → ⋮ → Download diagnostics**. Read the file before posting it. It can contain your LAN IP address and signed image URLs.
