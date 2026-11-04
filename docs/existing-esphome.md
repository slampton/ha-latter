# Using Latter with ESPHome Devices You Already Have

You don't need Latter hardware to get value from Latter. There are two ways an ESPHome device can participate:

| | What it is | What you get |
| :--- | :--- | :--- |
| **Latter firmware** | One of the [supported displays](../README.md#get-started), or your own build on [Latter Core](https://github.com/slampton/esphome-latter-core) | Everything |
| **Bridged device** | Any ESPHome device, with its YAML untouched | Grouping, live entity view and control in Studio, and settings backups |

---

## Bridging a device (no YAML changes)

1. Open **Studio → Devices → All Devices**. ESPHome devices that aren't in Latter yet are listed there.
2. Click **Add Device to Latter**, pick the device, and optionally set a default area.

The device is added as a headless node with BLE tracking off. What you get:
- **A live entity view.** Every entity on the device, controllable from Studio.
- **Groups and profiles.** Put it in a device group alongside your other devices.
- **Backups.** Device backups capture the device's live `select`, `switch`, and `number` values, and can restore them onto the same device or a replacement.

What you don't get: area tracking, the `latter.*` slot services, or anything that needs the device to call Home Assistant. Those require Latter firmware.

---

## Presence without flashing anything

If you already have ESPHome Bluetooth proxies assigned to Areas, you can track phones, watches, and iBeacons right now:

1. Set up Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration for each phone or watch.
2. Open **Studio → System → BLE & Area Presence → Discovered Nearby Bluetooth Devices** and click **Adopt**.

→ [Presence guide](presence.md)
