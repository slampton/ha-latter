# Troubleshooting

## Setup

**"Discovered: Latter" never appears**

Latter discovers devices from Home Assistant's device and service registries, not from the network. Check these in order:
1. **The device is in the ESPHome integration and online.** Latter needs the ESPHome device first.
2. **The device registers at least one Latter action.** Look in **Developer Tools → Actions** for `esphome.<name>_latter_ping`, `esphome.<name>_latter_push_v3`, or `esphome.<name>_latter_set_slots`. If none of them are there, the device isn't running Latter firmware.
3. **A rescan has run.** Latter rescans 5 seconds after any device-registry change, and when ESPHome registers a new action. Reloading the ESPHome integration triggers a rescan.

You can also create the Latter System hub by hand (**Settings → Devices & Services → Add Integration → Latter**, leaving **Initial ESPHome Device (optional)** blank if you want standalone BLE presence). Once the Latter hub is installed, click **Configure** on the Latter integration card (or **Latter** in the sidebar) and adopt additional displays or Bluetooth trackers under **Devices → Discovered**—and expand **Ignored (`<N>`)** on **Discovered devices** if a previously ignored ESPHome node isn't listed.

**The device shows up, but Music, Area, and Remote screens stay empty or taps do nothing**

Latter communicates over Zero-Privilege RPC—you do **not** need *"Allow the device to perform Home Assistant actions"*. Instead, check:
1. **The bound ESPHome device is online** in **Settings → Devices & Services → ESPHome**.
2. **The `System: RPC Outbox` entity is enabled** on the ESPHome device (`sensor.<node>_system_rpc_outbox`, enabled by default and auto-hidden from dashboards). Latter listens to that entity for every tap and browse request from the device.
3. **Both `ha-latter` and `esphome-latter-core` are on `v3.0.0` or newer**, so `esphome.<node>_latter_push_v3` is registered under **Developer Tools → Actions**.

**Studio shows "Device is offline or hibernating" and Quick actions are disabled**

Battery handhelds and wearables enter deep-sleep hibernation after their **Battery hibernate timeout** to conserve power. While offline or hibernating, Studio disables live **Quick actions** (such as Find My Device or Restart Device), **but every setting you edit in Studio saves immediately in Home Assistant and pushes automatically the moment the Device wakes or reconnects**. To inspect the underlying Home Assistant device entry or raw ESPHome entities, click **Open in Home Assistant** in the **Overview → Quick actions** or **Tools → Diagnostics** footer.

**I renamed the device or replaced physical hardware**

Renaming a device in Home Assistant works immediately—nothing breaks and there is **no `device_slug` YAML substitution** to keep in sync. Latter resolves both inbound `latter_push_v3` actions and outbound `System: RPC Outbox` frames directly from the bound `esphome_device_id` (falling back to MAC address if the ESPHome entry was re-created). If you flashed replacement hardware and Home Assistant created a brand-new ESPHome device entry, open **Settings → Devices & Services → Latter**, click **⋮ → Reconfigure** (**Reconfigure or Replace Hardware**) on that Device subentry, and select the new ESPHome device to rebind it in place while keeping all Studio shortcuts, settings, and Area assignments.

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
- **Bluetooth area tracking is off.** Check that **Track the Area with BLE Proxies** is enabled in **Studio → Devices → your device → Presence → Track the Area with BLE Proxies** (or via **Reconfigure or Replace Hardware** under **Settings → Devices & Services → Latter**).
- **The device's beacon is paused on battery.** On battery boards, check **BLE Beacon Mode** under **Studio → Devices → your device → Presence** (*Handheld Only* pauses advertising when the screen turns off on battery; choose *Handheld + Screen Off* or *Always* to advertise while the screen is off, and check **BLE radio** inside **Studio → Devices → your device → Tools → Developer & telemetry**).
- **Look at the live readings.** Open **Studio → System → BLE & Area Presence** and click **Live Stream On**. If an Area never shows a reading, its proxy isn't hearing the device.

**The device keeps choosing the neighboring area**

Calibrate it. Stand in the Area that should win, open **Studio → System → BLE & Area presence → Walk-around BLE calibration**, and click **Calibrate Area**. → [Calibrating & capturing signatures](presence.md#calibrating--capturing-signatures)

**A phone isn't tracked**

The phone has to be set up in Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration first. Latter doesn't resolve IRKs itself. Then adopt the `private_ble_device` entity in Studio.

---

## Music

**Library browsing is empty**

Library browsing, queue transfer, and the default intercom speaker list need the Music Assistant integration loaded in Home Assistant. Without it, only transport controls and volume work.

**A repair asks you to pick the Music Assistant player for a device**

Music Assistant identifies a Latter device's Sendspin player by a key hash, not by its MAC address, and doesn't link it to the ESPHome device. So Latter can't find the device's own Music Assistant player by itself, and library playback, queues and lyrics on that device fail until it's linked. Open the repair (**Settings → Repairs**), pick the device's player (it's pre-selected when exactly one Music Assistant player has the same manufacturer and model as the ESPHome device), and submit. You can change the link later in **Studio → (device) → Audio → Music Assistant Player**.

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

When you [open an issue](https://github.com/slampton/ha-latter/issues), open **Studio → System → Tools → Support & diagnostics** and click **Download System diagnostics** (or **Device → Tools → Diagnostics → Download diagnostics** for a single Device; also available via **Settings → Devices & Services → Latter → ⋮ → Download diagnostics**) and **Copy version summary** to paste your exact Home Assistant, Latter integration, minimum firmware SDK, and Studio contract versions. Latter automatically redacts URL `sig=` signatures, Protocol v3 `payload` blobs, security PINs/hashes, BLE UUIDs/addresses, calendar titles and locations, and MAC dictionary keys, though you should still review the file (for example, LAN IP addresses) before posting it publicly.
