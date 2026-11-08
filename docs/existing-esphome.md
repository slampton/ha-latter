# Using Latter with ESPHome Devices You Already Have

Latter manages Latter devices: one of the [supported displays](../README.md#get-started), or your own build on [Latter Core](https://github.com/slampton/esphome-latter-core). Other ESPHome devices aren't added to Latter, but the Bluetooth data they already give Home Assistant feeds Latter's presence engine.

> These are standard ESPHome components in your own configs. Latter reads what Home Assistant's Bluetooth integration already collects; it doesn't ship or support this YAML.

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

Then open **Studio → System → BLE & Area Presence → Discovered Nearby Bluetooth Devices** and click **Adopt**, or add it by UUID with **Add by address**.

## Phones and watches

1. Set up Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration for each phone or watch.
2. Adopt it from the same **Discovered Nearby Bluetooth Devices** list.

→ [Presence guide](presence.md)

---

## Building your own Latter device

To make an ESPHome device a full Latter device, build it on [Latter Core](https://github.com/slampton/esphome-latter-core) and implement the [device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md). Home Assistant then discovers it as **Discovered: Latter**.
