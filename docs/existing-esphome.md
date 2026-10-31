# Using Latter with ESPHome Devices You Already Have

You don't need Latter hardware to get value from Latter. There are three ways an ESPHome device can participate:

| | What it is | What you get |
| :--- | :--- | :--- |
| **Latter firmware** | One of the [supported displays](../README.md#get-started), or your own build on [Latter Core](https://github.com/slampton/esphome-latter-core) | Everything |
| **Mixin node** | Your existing YAML plus one or more [one-line packages](https://github.com/slampton/esphome-latter-core/blob/main/docs/mixins.md) | Automatic discovery, plus whatever the package adds: BLE beacon, proxy, WireGuard roaming, diagnostics |
| **Bridged device** | Any ESPHome device, with its YAML untouched | Grouping, live entity view and control in Studio, and settings backups |

---

## Bridging a device (no YAML changes)

1. Open **Studio → Devices → All Devices**. ESPHome devices that aren't in Latter yet are listed there.
2. Click **Add Device to Latter**, pick the device, and optionally set a default area.

The device is added as a headless node with BLE tracking off. What you get:
- **A live entity view.** Every entity on the device, controllable from Studio.
- **Groups and profiles.** Put it in a device group alongside your other devices.
- **Backups.** Device backups capture the device's live `select`, `switch`, and `number` values, and can restore them onto the same device or a replacement.

What you don't get: area tracking, the `latter.*` slot services, or anything that needs the device to call Home Assistant. Those require Latter firmware or mixins.

> [!WARNING]
> **Latter hides some entities on onboarded devices.** This applies to every onboarded ESPHome device, bridged ones included.
>
> **What gets hidden:** `light` and `switch` entities that look like internal hardware controls. A name matches if it contains a keyword such as `backlight`, `display`, `screen`, `status_led`, `restart`, `mmwave`, `ld2410`, `buzzer`, or `child_lock`, or if its friendly name starts with a prefix such as `System:` or `Display:`.
>
> **What Latter does to them:** sets the entity category to `config`, hides the entity, and un-exposes it from Assist, Alexa, and Google Assistant. This stops "turn off all the lights" from switching off a panel's backlight.
>
> **What this means for you:** a real load whose name contains one of these words, such as "Screen Porch Light", will be hidden too. To restore it, edit the entity in **Settings → Entities**: un-hide it, set its category back, and re-expose it under **Settings → Voice assistants**.
>
> On Latter firmware displays, *every* light and switch is treated this way, because none of them control loads in an area.

---

## Adding a mixin

Mixins are ESPHome packages you add to an existing config. Each one also registers a `latter_ping` action, which is how Latter discovers the device. For example, to make an existing node a BLE proxy for presence:

```yaml
packages:
  latter_proxy: github://slampton/esphome-latter-core/mixins/ble_proxy.yaml@main
```

After you flash it, the device shows up as **Discovered: Latter**.

The full list, with requirements and known conflicts, is in [mixins](https://github.com/slampton/esphome-latter-core/blob/main/docs/mixins.md).

> Mixins are designed for **your own** ESPHome configs. Don't add them to Latter firmware devices, which already include those features.

---

## Presence without flashing anything

If you already have ESPHome Bluetooth proxies assigned to Areas, you can track phones, watches, and iBeacons right now:

1. Set up Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration for each phone or watch.
2. Open **Studio → System → BLE & Area Presence → Discovered Nearby Bluetooth Devices** and click **Adopt**.

→ [Presence guide](presence.md)
