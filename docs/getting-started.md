# Getting Started

This guide takes one device from the box to fully working. It should take about 20 minutes.

## What you need

- **A supported device.** See the [device table](../README.md#get-started).
- **Home Assistant 2026.10 or newer** with [HACS](https://hacs.xyz) installed.
- **A desktop computer running Chrome or Edge**, plus a **USB-C data cable**. Some cables carry power only.
- **2.4 GHz Wi-Fi.** None of the supported chips can join a 5 GHz network.
- **Optional:** [Music Assistant](https://music-assistant.io) for music browsing, and one ESPHome Bluetooth proxy per area if you want area presence.

<!-- MEDIA: docs/media/getting-started-video — link to an unboxing → working video (YouTube), not embedded. -->

---

## 1. Flash the firmware

Open the [web installer](https://slampton.github.io/esphome-latter-core/), pick your device, click **Connect & Install**, and choose the USB serial port.

The firmware repository's [flashing guide](https://github.com/slampton/esphome-latter-core/blob/main/docs/flashing.md) covers:
- Setting up Wi-Fi right in the browser over USB (Improv Serial on all five devices).
- Building the firmware yourself in ESPHome Device Builder instead (`api: encryption:` and `ota: password:`).

## 2. Add it to Home Assistant through ESPHome

Once the device is on Wi-Fi, Home Assistant shows **Discovered: ESPHome**. Click **Add**, and assign the device to the Area where it usually lives.

> **No extra ESPHome permissions needed:** Latter communicates with your device over a bound Zero-Privilege RPC channel (**System: RPC Outbox** + `esphome.<node>_latter_push_v3` authenticated by `esphome_device_id`). Leave **Allow the device to perform Home Assistant actions** turned **off**.

## 3. Install Latter

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/slampton/ha-latter` with category **Integration**.
3. Search for **Latter**, download it, and restart Home Assistant.

## 4. Accept the discovered device

Latter watches Home Assistant's device registry for ESPHome devices that implement its protocol. When it finds yours, you'll see **Discovered: Latter** under **Settings → Devices & Services**. Click **Add**. The form has three fields:

| Field | What to enter |
| :--- | :--- |
| **ESPHome Device** | Pre-selected. Latter binds to this ESPHome device ID and its MAC address. |
| **Device Group** | Pick an initial operational group (**Handhelds**, **Wearables**, **Bedrooms**, **Common Areas**, **Wall & Desk Panels**, or **Unassigned**). Latter reads screen size and hardware capabilities automatically from the device's manifest. |
| **Track the Area with BLE Proxies** | Leave it checked for handhelds and the watch. Uncheck it for something fixed in one Area, like the Desk Assistant. |

The device's entities now appear under a **Latter** device card linked to the ESPHome device.

## 5. Open Latter Studio

Click **Latter** in the Home Assistant sidebar. It's visible to admin users only. Set up these items first:

1. **System → Shared Entities**: choose your weather entity, then any alarm panel, thermostat, lock, garage door, vacuum, cameras, and calendars you want on the device.
2. **System → Media & Remotes**: add TVs or streaming boxes as remote slots. If your speakers' volume is controlled by an AV receiver, map them under **Speaker Volume Overrides**.
3. **Devices → your device → Audio**: pick the device's default speaker and wake word.
4. **Devices → your device → Tools → Perimeter Security Policy** *(optional)*: choose how opening actions (unlocking doors, disarming alarms, opening garage/gate covers) are guarded (`Auto`, `Allow`, `Require PIN`, or `Block`) and set a Device Security PIN if desired. `Auto` requires a PIN on stationary panels or when your Home Assistant alarm panel uses a code.

Changes reach the device within a second or two. There is nothing to reflash.

<!-- MEDIA: docs/media/studio-shared-entities.png -->

## 6. Try it

On the device:
- **Swipe up** from the bottom edge, or **tap the pill** at the bottom, to go home.
- Open **Music**, pick a speaker, and browse your library.
- Open **Area**. You'll see controls for the Area the device is assigned to.
- Say **"Okay Nabu"**. The wake word works while the device is docked, by default. You can change this in Studio under **Audio**, or with the device's **Voice: Wake Word Mode** entity.

## 7. Optional: area presence for handhelds

If you checked **Track the Area with BLE Proxies**, Latter follows the device from area to area using your Bluetooth proxies. You need at least one ESPHome Bluetooth proxy in each area, and each proxy must be assigned to its Area in Home Assistant. The device's BLE presence beacon is off out of the box; Latter turns it on for you when tracking is on.

After that, open **System → BLE & Area Presence** in Studio, walk the device around, and use **Calibrate Current Area** wherever it picks the wrong area.

→ [Presence guide](presence.md)

---

## If something doesn't work

- **"Discovered: Latter" never appears.** Check that the device shows up in the ESPHome integration and is online. Latter rescans 5 seconds after any device-registry change. Reloading the ESPHome integration also triggers a rescan.
- **Screens are empty or taps do nothing.** Verify the ESPHome device is online, its **System: RPC Outbox** entity is enabled in Home Assistant, and both `esphome-latter-core` and `ha-latter` are on `v3.0.0` or newer (`esphome.<node>_latter_push_v3` appears under **Developer Tools → Actions**).

→ [Troubleshooting](troubleshooting.md)
