# Presence

Latter tracks which area each device is in using the Bluetooth proxies you already have. It then uses that area: it moves the device's Home Assistant Area so Assist targets the right area, scopes Area Control, and routes "follow me" notifications.

<!-- MEDIA: docs/media/presence-survey.png — Studio → BLE & Area Presence with the live survey and per-area calibration. -->

---

## What you need

- **At least one Bluetooth scanner in each area** you want to detect, assigned to that Area in Home Assistant. ESPHome proxies are tested. Any scanner Home Assistant's Bluetooth integration can use (a USB adapter, Shelly, and others) should work too, but is not verified yet.
  - To make an ESPHome node a proxy, add [`ble_proxy`](https://github.com/slampton/esphome-latter-core/blob/main/docs/mixins.md#ble_proxy) or set `bluetooth_proxy: active: true`.
- **Optional:** Home Assistant **Floors** assigned to your Areas. This turns on the cross-floor penalty described below.

## What can be tracked

| Target | How it's identified | How to add it |
| :--- | :--- | :--- |
| Latter firmware devices | The device's MAC address from Home Assistant's device registry (±2, to cover the ESP32 BLE MAC offset). The Latter iBeacon UUID and minor are also accepted, which covers ESP32-P4 boards where BLE runs on a separate C6 chip with its own MAC. | Check **This device roams** when adding the device |
| ESPHome nodes running the [`ble_beacon`](https://github.com/slampton/esphome-latter-core/blob/main/docs/mixins.md#ble_beacon) mixin | MAC address from the device registry | Same as above |
| Phones and watches | Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration resolves the rotating address from the device's IRK. Latter re-reads the current address every 2 seconds. | Set up Private BLE Device, then **Studio → BLE & Area Presence → Discovered Nearby Bluetooth Devices → Adopt** |
| iBeacons | UUID, or an `ibeacon` device tracker entity | Adopt from the same list, or enter the UUID |
| Other BLE devices with a static address | MAC address | Adopt from the same list, or enter the MAC |

Latter parses Apple-format iBeacons only. Eddystone and AltBeacon frames are not supported.

To link a tracked device to a person, set **Assigned Person** on the device's Overview page. You'll get `sensor.<person>_current_area`, which follows whichever of that person's devices was heard most recently.

---

## How it decides

All of these values are constants in [`ble_engine.py`](../custom_components/latter/ble_engine.py), so you can check them.

1. **Collect.** Latter gets advertisements in two ways:
   - It registers for Home Assistant Bluetooth callbacks.
   - Every **2 s** it reads each scanner's advertisement table directly, because Home Assistant's Bluetooth stack suppresses repeated identical advertisements from static beacons.

   Readings at or below −100 dBm are dropped.
2. **Smooth.** Each area keeps an exponential moving average of RSSI with α = 0.5. If an area hasn't heard the device for **25 s**, its average resets.
3. **Adjust.** The per-area calibration offset is added. Offsets are limited to ±25 dB. If the device's current area has a floor and a candidate area is on a different floor, the candidate gets **−6 dB**.
4. **Decide.**
   - A challenger area takes over immediately if it leads by **8 dB** or more.
   - Otherwise it needs a lead of at least **5 dB**, and at least **4 s** must have passed since the last switch.
5. **Away.**
   - With no matched packets for **180 s**, the device is marked `Away`.
   - Display devices with a live Wi-Fi connection are never marked away; they just keep their last area.
   - A gap of 8 s or more clears the area history, so a device waking from sleep starts fresh.

**Distance** uses a log-distance model: d = 10<sup>(−59 − RSSI) / 22</sup> meters, clamped to 0.2–50 m. It's computed after calibration offsets are applied, so treat it as a rough indicator, not a measurement.

## Calibrating

Walls, furniture, and antenna orientation mean the nearest proxy isn't always the loudest one.

1. Open **Studio → System → BLE & Area Presence** and select a device in **Per-Area BLE Signal Calibration**.
2. Turn on **Fast Refresh (1.5s)**.
3. Carry the device into an area and watch the effective RSSI for each area.
4. If the wrong area wins, click **Calibrate Current Area**. Latter sets this area's offset so it beats the strongest competitor by 6 dB. Use ±1 dB to fine-tune.

Offsets are **per area and shared by every tracked device**. This is the main simplification compared with per-scanner calibration. See [known limitations](#known-limitations).

---

## Area occupancy and sensor fusion

Latter creates one occupancy binary sensor and one occupants sensor per area. These are `binary_sensor.<area>_ble_occupancy` and `sensor.<area>_occupants`. Each area can combine BLE with the other sensors already assigned to it:

| Input | Effect on the area's confidence score |
| :--- | :--- |
| A tracked device present | +0.85 at −68 dBm or stronger, +0.70 at −80 dBm or stronger, otherwise +0.54 |
| Occupancy or presence sensor on (for example mmWave) | Raises the score to at least 0.78, plus a bonus if BLE agrees |
| Motion sensor on | Raises the score to at least 0.68, plus a bonus if BLE agrees |
| Door or opening closed | +0.08 |
| Occupancy sensor explicitly off, no motion, weak BLE | −0.18 |

Fusion modes, set per area in Studio:

| Mode | Behavior |
| :--- | :--- |
| `auto_bayes` (default) | Occupied when the score passes the area's threshold (default 50%, adjustable from 20% to 95%) |
| `any_or` | Occupied if BLE **or** any sensor says so |
| `ble_only` | BLE only |
| `ble_and_sensor` | BLE **and** a sensor, where the area has one |

> Despite the mode name, `auto_bayes` is a hand-tuned weighted score, not a formal Bayesian update. It's simple and predictable, and the weights above are the whole model.

Sensors are discovered automatically by device class (occupancy, presence, motion, moving, door, opening), from both entity areas and device areas. You can also list them explicitly per area.

## What Latter does with the area

- **Moves the device's Home Assistant Area.** When a roaming device changes areas, Latter updates the device's Area in the registry, so Assist's area-aware commands target where you are. If you have proxies, the device only moves into areas that contain one. You can turn this off per device.
- **Scopes Area Control** on the device to the current area.
- **Routes notifications and intercom.** `target_device: follow_me` delivers to devices in occupied areas. See [services](reference/services.md#special-target-values).
- **Fires `latter_event`** with `type: area_changed` for your own automations.

---

## Coming from Bermuda

[Bermuda](https://github.com/agittins/bermuda) is a mature, widely used BLE trilateration integration, and it does several things Latter doesn't. Here is the honest comparison:

| | Bermuda | Latter |
| :--- | :--- | :--- |
| Area sensor per tracked device | ✓ | ✓ (`sensor.<slug>_current_area`) |
| Area sensor per person | Through `person` | ✓ (`sensor.<person>_current_area`) |
| Phones and watches via Private BLE Device | ✓ | ✓ |
| iBeacons and static MACs | ✓ | ✓ (Apple iBeacon only) |
| `device_tracker` entities for `person` home/away | ✓ | **Not yet** |
| Distance sensor per scanner | ✓ | **No.** One closest-distance sensor per device. |
| Calibration | Per scanner, plus global reference power and attenuation | **Per area only**, with fixed path-loss constants |
| Same entity IDs, so automations carry over | — | **No.** You'll need to update automations. |

**Things Latter adds on top of area detection:** the cross-floor penalty, per-area occupancy fused with your existing sensors, automatic Home Assistant Area moves for Assist, follow-me routing, and a walk-around calibration view.

### Using both

You don't have to choose. On a device's **Administration** page, set **External Area Sensor Override** to a Bermuda area sensor. When its state matches an Area name or ID, Latter switches the device to that area. It also moves the device's Home Assistant Area and rescopes Area Control, just as it would with its own engine.

Per-area occupancy sensors and `follow_me` routing are different: they come only from Latter's own engine and ignore the override.

### Switching over

1. Make sure each proxy is assigned to its Area. Bermuda needs this too, so it's probably done already.
2. Adopt your phones and watches in **Studio → BLE & Area Presence**, and set **Assigned Person** on each.
3. Walk the house and calibrate the areas that pick wrong.
4. Point your automations at `sensor.<person>_current_area` or `binary_sensor.<area>_ble_occupancy`.
5. If you use Bermuda's `device_tracker` for `person` home/away, keep Bermuda for that until Latter supports it.

---

## Known limitations

- **No `device_tracker` entities.**
- **Calibration is per area, not per scanner.** Offsets are shared by all tracked devices, and the path-loss constants (−59 dBm at 1 m, exponent 2.2) can't be configured.
- **Areas share an average.** If two scanners are in the same area, the most recent reading wins.
- **The 2-second table poll sets the smoothing rate.** The moving average updates at the poll rate, not the advertisement rate.
- **Occupancy sensors don't update on RSSI changes alone.** They refresh on area transitions, away events, and changes to any occupancy, motion, or door sensor.
- **Timing constants are fixed.** These are the 4 s hold, 5 and 8 dB thresholds, and 180 s away timeout.
