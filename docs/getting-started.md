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
- Getting the device onto Wi-Fi. This step differs by device.
- Building the firmware yourself in ESPHome Device Builder instead.

## 2. Add it to Home Assistant through ESPHome

Once the device is on Wi-Fi, Home Assistant shows **Discovered: ESPHome**. Click **Add**, and assign the device to the Area where it usually lives.

Then turn on the setting that lets the device call Home Assistant services. **Without it, music browsing, area control, and remotes won't respond:**

1. Go to **Settings → Devices & Services → ESPHome**.
2. Find your device, click **Configure**, and enable **Allow the device to perform Home Assistant actions**.

<!-- MEDIA: docs/media/esphome-allow-actions.png — the ESPHome options dialog with the actions checkbox enabled. -->

## 3. Install Latter

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/slampton/ha-latter` with category **Integration**.
3. Search for **Latter**, download it, and restart Home Assistant.

## 4. Accept the discovered device

Latter watches Home Assistant's device registry for ESPHome devices that implement its protocol. When it finds yours, you'll see **Discovered: Latter** under **Settings → Devices & Services**. Click **Add**. The form has three fields:

| Field | What to enter |
| :--- | :--- |
| **ESPHome Device Name / Slug** | Pre-filled. Leave it unless you renamed the device. |
| **Configuration Profile** | Leave **Auto-detect**. Latter reads the screen size and shape from the device. |
| **This device roams** | Check it for handhelds and the watch. Uncheck it for something fixed in one Area, like the Desk Assistant. |

The device's entities now appear under a **Latter** device card linked to the ESPHome device.

## 5. Open Latter Studio

Click **Latter** in the Home Assistant sidebar. It's visible to admin users only. Set up these items first:

1. **System → Shared Entities**: choose your weather entity, then any alarm panel, thermostat, lock, garage door, vacuum, cameras, and calendars you want on the device.
2. **System → Media & Remotes**: add TVs or streaming boxes as remote slots. If your speakers' volume is controlled by an AV receiver, map them under **Speaker Volume Overrides**.
3. **Devices → your device → Audio & Voice**: pick the device's default speaker and wake word.

Changes reach the device within a second or two. There is nothing to reflash.

<!-- MEDIA: docs/media/studio-shared-entities.png -->

## 6. Try it

On the device:
- **Swipe up** from the bottom edge, or **tap the pill** at the bottom, to go home.
- Open **Music**, pick a speaker, and browse your library.
- Open **Area**. You'll see controls for the Area the device is assigned to.
- Say **"Okay Nabu"**. The wake word works while the device is docked, by default. You can change this in Studio under **Audio & Voice**, or with the device's **Voice: Wake Word Mode** entity.

## 7. Optional: area presence for handhelds

If you checked **This device roams**, Latter follows the device from area to area using your Bluetooth proxies. You need at least one ESPHome Bluetooth proxy in each area, and each proxy must be assigned to its Area in Home Assistant.

After that, open **System → BLE & Area Presence** in Studio, walk the device around, and use **Calibrate Current Area** wherever it picks the wrong area.

→ [Presence guide](presence.md)

---

## If something doesn't work

- **"Discovered: Latter" never appears.** Check that the device shows up in the ESPHome integration and is online. Latter rescans 5 seconds after any device-registry change. Reloading the ESPHome integration also triggers a rescan.
- **Screens are empty or taps do nothing.** The "Allow the device to perform Home Assistant actions" setting is almost certainly off. See [step 2](#2-add-it-to-home-assistant-through-esphome).

→ [Troubleshooting](troubleshooting.md)
