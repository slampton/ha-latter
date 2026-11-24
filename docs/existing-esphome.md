# Using Latter with ESPHome Devices You Already Have

Latter manages Latter Devices: one of the [supported displays](../README.md#get-started-in-minutes), or your own build on [Latter Core](https://github.com/slampton/esphome-latter-core). Other ESPHome devices aren't added as Latter displays, but the Bluetooth data they already give Home Assistant powers Latter's Area presence and sensor-fusion engine—even with **zero Latter displays** configured.

> **Standalone 0-display setup:** Go to **Settings → Devices & Services → Add Integration → Latter** and leave **Initial ESPHome Device (optional)** blank, then click **Configure** (or **Latter** in the sidebar) to open Latter Studio. These are standard ESPHome components in your own configs—Latter reads what Home Assistant's Bluetooth integration already collects; it doesn't ship or support this YAML.

---

## Bluetooth proxies become Area scanners

Any ESPHome node running an active Bluetooth proxy, assigned to an Area in Home Assistant, is a presence scanner for that Area:

```yaml
esp32_ble_tracker:
  scan_parameters:
    active: true

bluetooth_proxy:
  active: true
```

## ESPHome beacons & standalone `latter_beacon`

Any node that advertises an iBeacon can be tracked as it moves between Areas. Give each node its own UUID using stock `esp32_ble_beacon`:

```yaml
esp32_ble_beacon:
  type: iBeacon
  uuid: "<a UUID unique to this node>"
```

If you want lightweight raw-HCI iBeacon advertising on ESP32-S3 or ESP32-P4 without pulling Bluedroid or NimBLE into RAM, you can also drop the standalone [`latter_beacon`](https://github.com/slampton/esphome-latter-core/tree/main/components/latter_beacon) external component directly into your own ESPHome YAML.

Then open **Studio → Devices → Discovered → Bluetooth devices** (**Phones & trackers** filter) and click **Adopt**, or add it by UUID with **Add BLE tag**.

## Phones and watches

1. On Android with the Home Assistant Companion App, enable the **BLE Transmitter** sensor (auto-discovered directly by phone name); on iOS, Apple Watch, or Android without the Companion App, set up Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration once.
2. Adopt it from **Bluetooth devices** under **Studio → Devices → Discovered** (Studio jumps straight to the new Device's **Overview** page so you can assign a Person).

→ [Presence guide](presence.md)

---

## Porting another display board to Latter Core

Want to run Latter OS on a different ESP32-S3 or ESP32-P4 display (including audio-less or rotary-knob displays)? Write a board HAL using the typed `latter_core:` schema and combine it with `modules/latter_display_firmware.yaml` (or `modules/latter_display_only_firmware.yaml`) in [Latter Core](https://github.com/slampton/esphome-latter-core) — see the **[Porting hardware guide](https://github.com/slampton/esphome-latter-core/blob/main/docs/porting-hardware.md)** and `tools/check_boards.py --external`. Home Assistant discovers the flashed board automatically as **Discovered: Latter**.
