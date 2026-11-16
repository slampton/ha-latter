# Getting Started

This guide takes one device from the box to fully working in about 20 minutes.

## What You Need

- **A supported device.** See the [device table](../README.md#get-started-in-minutes).
- **Home Assistant `2026.10` or newer** with [HACS](https://hacs.xyz) installed.
- **A desktop computer running Chrome or Edge**, plus a **USB-C data cable** (power-only cables won't expose a serial port).
- **2.4 GHz Wi-Fi.** Neither the ESP32-S3 nor the ESP32-C6 co-processor on the P4 boards joins 5 GHz networks.
- **Optional:** [Music Assistant](https://music-assistant.io) for library browsing and queue transfer, and one ESPHome Bluetooth proxy per Area for roaming presence.

<!-- MEDIA: docs/media/getting-started-video — link to an unboxing → working walkthrough video (YouTube), not embedded. -->

---

## 1. Flash the Firmware

Open the **[Latter Web Installer](https://slampton.github.io/esphome-latter-core/)**, pick your device, click **Connect & Install**, and select the USB serial port. Right after flashing, enter your Wi-Fi credentials in the browser dialog (Improv Serial over USB).

Prefer compiling locally? See the [Flashing guide](https://github.com/slampton/esphome-latter-core/blob/main/docs/flashing.md) for the turnkey ESPHome Device Builder YAML (`api: encryption:` + Noise-encrypted `ota:`).

## 2. Add It to Home Assistant Through ESPHome

Once on Wi-Fi, Home Assistant shows **Discovered: ESPHome**. Click **Add**, and assign the device to the Area where it lives (or usually docks).

> **Leave extra permissions off:** Latter communicates over a bound Zero-Privilege RPC channel (**System: RPC Outbox** + `esphome.<node>_latter_push_v3`). Leave *"Allow the device to perform Home Assistant actions"* **unchecked**.

## 3. Install Latter via HACS

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/slampton/ha-latter` with category **Integration**.
3. Download **Latter**, then restart Home Assistant.

## 4. Accept Discovered: Latter

Under **Settings → Devices & Services**, click **Add** on **Discovered: Latter**:

| Field | What to Choose |
| :--- | :--- |
| **ESPHome Device** | Pre-selected—Latter binds to this `esphome_device_id` and hardware MAC. |
| **Device Group** | Defaults to **Auto-Detect from Device Hardware** (maps handhelds, wearables, or desk/wall panels automatically), or pick a specific operational group. |
| **Track the Area with BLE Proxies** | Pre-checked for handhelds and wearables; automatically unchecked for stationary panels already assigned to an Area in Step 2. |

## 5. Configure in Latter Studio

Click **Latter** in the Home Assistant sidebar (admin users only):

1. **System → Shared Entities:** select your weather entity, plus any alarm panel, thermostat, lock, garage door, vacuum, cameras, calendars, and wallpapers.
2. **System → Media & Remotes:** add TVs, streaming boxes, or AV receivers as remote slots, and map any AV-receiver speaker volumes under **Speaker Volume Overrides**.
3. **Devices → your device → Display & Interface:** choose your theme/wallpaper, customize **Dock Apps** and **Area / Home Categories**, and add any **World Clocks** or recurring **Alarms** under **Time**.
4. **Devices → your device → Audio:** pick the device's default speaker and Assist wake word.
5. **Devices → your device → Tools → Perimeter Security** *(optional)*: set the policy (`Auto`, `Allow`, `Require PIN`, or `Block`) and PIN for locks, garage covers, and code-less alarms (Home Assistant alarm panels with their own code prompt automatically).

Every change reaches online devices within a second or two—nothing needs to be reflashed.

<!-- MEDIA: docs/media/studio-shared-entities.png -->

## 6. Try It Out

- **Swipe up** from the bottom edge to return Home from any app.
- Tap the **clock** on Home to open the 4-tab **Time** app, or tap **Area** to control lights, climate, and shades in the device's current Area.
- Open **Music** to pick a speaker and browse your Music Assistant library.
- Say **"Okay Nabu"** while USB-docked (default on battery boards; change anytime in **Studio → Devices → Audio** or via `select.<slug>_wake_word_mode`).

## 7. Optional: Calibrate BLE Area Presence

With **Track the Area with BLE Proxies** enabled and one Area-assigned ESPHome Bluetooth proxy per Area, Latter provisions your System's private 128-bit BLE UUID and enables the device's beacon automatically (`device_prefs.ble_beacon_enabled`). Open **System → BLE & Area Presence** in Studio, click **Live Stream On**, walk between Areas, and use **Calibrate Current Area** anywhere a neighboring proxy wins. → [Presence guide](presence.md)

---

## Quick Checks If Needed

- **"Discovered: Latter" never appears:** confirm the device is online in the ESPHome integration (Latter rescans 5 seconds after device-registry updates, or reload ESPHome to trigger a scan).
- **Screens stay empty or taps do nothing:** confirm the bound ESPHome device is online, its **System: RPC Outbox** sensor is enabled, and both `esphome-latter-core` and `ha-latter` are on `v3.0.0+` (`esphome.<node>_latter_push_v3` and `esphome.<node>_latter_set_slots` appear in **Developer Tools → Actions**). → [Troubleshooting](troubleshooting.md)
