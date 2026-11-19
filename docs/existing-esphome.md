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

## ESPHome beacons are tracked like any iBeacon

A node that advertises an iBeacon can be tracked as it moves between Areas. Give each node its own UUID:

```yaml
esp32_ble_beacon:
  type: iBeacon
  uuid: "<a UUID unique to this node>"
```

Then open **Studio → Devices → Discovered → Bluetooth devices** (**Phones & trackers** filter) and click **Adopt**, or add it by UUID with **Add BLE tag**.

## Phones and watches

1. On Android with the Home Assistant Companion App, enable the **BLE Transmitter** sensor (auto-discovered directly by phone name); on iOS, Apple Watch, or Android without the Companion App, set up Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration once.
2. Adopt it from **Bluetooth devices** under **Studio → Devices → Discovered** (Studio jumps straight to the new Device's **Overview** page so you can assign a Person).

→ [Presence guide](presence.md)

---

## Building your own Latter device

To make an ESPHome device a full Latter device, build it on [Latter Core](https://github.com/slampton/esphome-latter-core) and implement the [Device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md) (`latter_ping`, `latter_push_v3`, `latter_device_command`, `System: Hardware Manifest`, and `System: RPC Outbox`, plus `latter_set_slots` and `latter_show_notification` on displays). Home Assistant then discovers it automatically as **Discovered: Latter**.
