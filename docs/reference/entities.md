# Entities Reference

All Latter entities are push-updated: none of them poll. Per-device entities sit on a **Latter** device card that is linked to the ESPHome device through `via_device`.

Large attributes are excluded from the recorder through `_unrecorded_attributes`, so they don't bloat your database. Source: [`sensor.py`](../../custom_components/latter/sensor.py), [`binary_sensor.py`](../../custom_components/latter/binary_sensor.py).

Latter creates **sensor** and **binary_sensor** entities only. There are no `device_tracker`, `switch`, or `select` platforms. A device's own settings, such as wake word or clock face, are ESPHome entities on the ESPHome device. They are listed in [esphome-latter-core: Using your device](https://github.com/slampton/esphome-latter-core/blob/main/docs/using-your-device.md).

---

## Per device

`<slug>` is the device slug, for example `pocket_assistant`. Devices adopted as BLE beacons get only the three sensors marked ★.

| Entity | State | Key attributes | Updates when |
| :--- | :--- | :--- | :--- |
| ★ `sensor.<slug>_current_area` | Area name, `Away`, or `Unassigned` | `area_id`, `is_home`, `closest_proxy`, `distance_ft`, `distance_m`, `rssi`, `assigned_person` | The area changes, or the device goes away |
| ★ `sensor.<slug>_ble_distance` | Feet (device class `distance`) | — | A BLE reading arrives |
| `sensor.<slug>_active_media` | `off`, `idle`, `playing`, `paused`, `buffering` | `title`, `artist`, `album`, `duration`, `position`, `volume`, `media_type`, `art_url`, `active_speaker`, `local_speaker`, `volume_entity` | The speaker's state changes. While playing, there is also a position update every 15 s; the device interpolates between updates. |
| ★ `sensor.<slug>_area_context` | Current area name | See [below](#area_context-attributes) | Any mapped entity changes. Area entity changes are debounced to 250 ms. |
| `sensor.<slug>_weather_forecast` | `DAY:HIGH:LOW:COND;…` for 5 days | `condition`, `temperature`, `humidity`, `wind_speed`, `wind_bearing`, `high`, `low` | The weather entity changes, and every 30 min |
| `sensor.<slug>_calendar_agenda` | Up to 5 entries, `LABEL\|summary;…` | `event_count`, `events` (up to 25, with `map_url`), `calendars` | Every 15 min |
| `sensor.<slug>_remote_config` | Active remote slot name | `active_slot`, `slot_N_name` / `_remote` / `_media_player` / `_area_id` / `_state` for N = 1–10, and `slots_summary` | Remote entities change |

### `area_context` attributes

This sensor is the main channel from Home Assistant to the device. It has about 70 attributes, grouped like this:

| Group | Attributes |
| :--- | :--- |
| Area | `area_id`, `area_temp`, `area_humidity`, `available_domains`, `entities_summary` |
| Whole-home | `alarm_entity`, `alarm_state`, `thermostat_state`, `thermostat_temp`, `lock_state`, `garage_state`, `vacuum_state` |
| Notification | `alert_id` (increments with each notification), `alert_title`, `alert_message`, `alert_priority`, `alert_duration`, `alert_chime`, `alert_camera_url` |
| Appearance | `wallpaper_url`, `theme_color_hex`, `dock_apps` |
| Cameras and doorbell | `camera_snapshot_url`, `cameras_summary`, `doorbell_talk_state`, `intercom_targets_summary` |
| Bindings | `custom_bindings_summary` |
| Presence | `ble_closest_proxy`, `ble_rssi_by_area`, `ble_scanners_map` |
| VPN | `vpn_enabled`, `vpn_client_ip` |
| Hardware | `hardware_manifest` (parsed from the device; see [device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md#2-hardware-manifest)) |

The field formats the firmware parses, such as `slots_summary` and `cameras_summary`, are specified in the [device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md).

---

## Per person

These are created when a device has an **Assigned Person**.

| Entity | State |
| :--- | :--- |
| `sensor.<person>_current_area` | The area of whichever of that person's devices was heard most recently |
| `sensor.<person>_ble_distance` | That device's distance, in feet |

> Don't give a device the same slug as a person's ID. The two `current_area` entity IDs would collide.

---

## Per area

Latter creates one of each for every area that has a Bluetooth scanner Latter can map. If none can be mapped, it creates them for every area.

| Entity | State | Attributes |
| :--- | :--- | :--- |
| `binary_sensor.<area>_ble_occupancy` | `on` / `off` (device class `occupancy`) | `floor_id`, `fusion_mode`, `confidence_pct`, `ble_occupied`, `sensor_occupied`, `active_sensors`, `occupant_names`, `persons`, `closest_device`, `winning_rssi`, `closest_distance_m`, `closest_distance_ft`, `tracker_count` |
| `sensor.<area>_occupants` | Occupant names, `Occupied (Sensor)`, or `Empty` | Same as above |

These update on area transitions, on away events, and when any occupancy, presence, motion, door, or opening sensor changes. They don't update on RSSI changes alone. → [How fusion works](../presence.md#area-occupancy-and-sensor-fusion)

---

## `latter_event`

Latter fires this on the Home Assistant event bus.

| `type` | Fields |
| :--- | :--- |
| `area_changed` | `device_slug`, `previous_area_id`, `area_id`, `assigned_person` |
| `notification_dispatched` | `device_slug`, `title`, `message`, `priority`, `camera_url` |

---

## Changes Latter makes to other entities

On onboarded ESPHome devices, Latter changes some entities it doesn't own:
- **Internal-looking controls:** `light` and `switch` entities that look like internal hardware controls are hidden, set to category `config`, and un-exposed from voice assistants. → [Details and how to undo it](../existing-esphome.md#bridging-a-device-no-yaml-changes)
- **Sensors on roaming displays:** temperature and humidity sensors are set to `diagnostic`, so they don't appear as area climate readings.
- **The device's Area:** roaming devices have their Home Assistant Area updated as they move.
