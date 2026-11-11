# Entities Reference

All Latter entities are push-updated: none of them poll. Per-device entities sit on a **Latter** device card (`_attr_has_entity_name = True`) that is linked to the ESPHome device through `via_device`.

Protocol v3 domain payloads (`active_media`, `area_context`, `weather_forecast`, `calendar_agenda`, `remote_config`) push directly to the bound ESPHome device over the Native API via `esphome.<node>_latter_push_v3` (`domain`, `payload`)—keeping `~8 KB` of signed URLs off Home Assistant's `state_changed` bus and SQLite recorder. The corresponding diagnostic sensors in Home Assistant expose `<255`-character human-readable states and only `rev` (`_unrecorded_attributes = {"rev"}`). Source: [`sensor.py`](../../custom_components/latter/sensor.py), [`binary_sensor.py`](../../custom_components/latter/binary_sensor.py), [`device_tracker.py`](../../custom_components/latter/device_tracker.py).

Latter creates **sensor**, **binary_sensor**, and **device_tracker** entities only. There are no `switch` or `select` platforms. A device's own settings (such as wake word or clock face) and its outbound Zero-Privilege RPC channel (**System: RPC Outbox**, `sensor.<node>_system_rpc_outbox`) are ESPHome entities on the bound ESPHome device. They are listed in [esphome-latter-core: Using your device](https://github.com/slampton/esphome-latter-core/blob/main/docs/using-your-device.md).

---

## Per device

`<slug>` is the device slug, for example `pocket_assistant`. BLE tags (phones, watches and tags added as **BLE Tag** entries) get only the three entities marked ★.

| Entity | State | Key attributes | Updates when |
| :--- | :--- | :--- | :--- |
| ★ `device_tracker.<slug>` | `home`, `not_home`, or `unknown` | `area_id`, `area_name`, `closest_proxy`, `distance_ft`, `distance_m`, `rssi`, `assigned_person` | A BLE reading arrives, or the device goes away |
| ★ `sensor.<slug>_current_area` | Area name, `Away`, or `Unassigned` | `area_id`, `is_home`, `closest_proxy`, `distance_ft`, `distance_m`, `rssi`, `assigned_person` | The area changes, or the device goes away |
| ★ `sensor.<slug>_ble_distance` | Feet (device class `distance`) | `area_id`, `is_home`, `closest_proxy`, `distance_ft`, `distance_m`, `rssi`, `assigned_person` | A BLE reading arrives |
| `sensor.<slug>_active_media` | `off`, `idle`, `playing`, `paused`, `buffering` | `rev` (Protocol v3 `active_media` pushes directly via `latter_push_v3`: active/local speaker, volume entity, playback state, title, artist, album, duration, position, volume, media type, and signed `art_url`) | The speaker's state changes. While playing, there is also a position update every 15 s; the device interpolates between updates. |
| `sensor.<slug>_area_context` | Current area name | `rev` (Protocol v3 `area_context` pushes directly via `latter_push_v3`; see [below](#protocol-v3-domain-payloads-latter_push_v3)) | Any mapped entity changes (indexed in `O(1)` by `AreaStateIndex`, debounced to 250 ms) |
| `sensor.<slug>_weather_forecast` | The weather entity's current condition | `rev` (Protocol v3 `weather_forecast` pushes directly via `latter_push_v3`: current weather, up to 5 `day\|cond\|high\|low` daily records, `sun_state`, `sun_elevation`, `sun_azimuth`, `sun_next_rising`, `sun_next_setting`, and `moon_phase`) | The weather or sun state changes, and every 30 min |
| `sensor.<slug>_calendar_agenda` | Number of upcoming events (up to 25) | `rev` (Protocol v3 `calendar_agenda` pushes directly via `latter_push_v3`: up to 5 `time\|title\|location\|all_day` records, event count, and next event) | Every 15 min |
| `sensor.<slug>_remote_config` | Active remote slot name | `rev` (Protocol v3 `remote_config` pushes directly via `latter_push_v3`: active slot, configured count, and up to 10 `index\|label\|entity_id\|kind\|area_id\|state` slot records) | Remote entities change |

### Protocol v3 domain payloads (`latter_push_v3`)

Latter pushes all five Protocol v3 domains directly to the bound ESPHome device through `esphome.<node>_latter_push_v3` (`domain`, `payload`). The largest domain, `area_context`, packs 41 positional Protocol v3 fields (`v3\x1f<epoch>\x1f<rev>\x1f...`), grouped like this:

| Group | Fields in `area_context` |
| :--- | :--- |
| Area | `area_id`, `area_name`, `area_temp`, `area_humidity`, `available_domains` |
| Whole-home | `alarm_entity`, `alarm_state`, `thermostat_entity`, `thermostat_state`, `thermostat_temp`, `lock_entity`, `lock_state`, `garage_entity`, `garage_state`, `vacuum_entity`, `vacuum_state` |
| Notification | `alert_id` (increments with each notification), `alert_title`, `alert_message`, `alert_priority`, `alert_duration`, `alert_chime`, `alert_camera_url` |
| Appearance & Home | `wallpaper_url`, `theme_color_hex`, `dock_apps`, `activity_card`, `activity_sources` |
| Cameras and doorbell | `camera_entity`, `camera_name`, `camera_snapshot_url`, `cameras_count`, `cameras_summary`, `doorbell_ring_state`, `doorbell_audio_url`, `doorbell_talk_state`, `doorbell_noise_reduction`, `intercom_targets_summary` |
| Presence | `ble_closest_proxy`, `ble_rssi_by_area` |
| Security | `security_pin_policy` (`allow` \| `require_pin` \| `block`, resolved from the Device's Studio Perimeter Security Policy) |

The exact field indices and record formats (`cameras_summary`, `intercom_targets_summary`, `slots_summary`, `forecast_5d`, `summary`) are defined in [`protocol_v3.json`](../../custom_components/latter/protocol_v3.json) and specified in the [device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md).

---

## Per person

These are created when a device has an **Assigned person**.

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
| `sensor.<area>_occupants` | `<255`-char occupant summary, `Occupied (Sensor)`, or `Empty` | Same as above (`occupant_count` and full `occupant_names` list) |

These update on area transitions, on away events, when Area registry entries are created, renamed or removed, and when any tracked occupancy, presence, motion, door, or opening sensor changes. They don't update on sub-deadband RSSI changes alone. → [How fusion works](../presence.md#area-occupancy-and-sensor-fusion)

---

## `latter_event`

Latter fires this on the Home Assistant event bus.

| `type` | Fields |
| :--- | :--- |
| `area_changed` | `device_slug`, `previous_area_id`, `area_id`, `assigned_person` |
| `notification_dispatched` | `device_slug`, `title`, `message`, `priority`, `camera_url` |

---

## Voice Follows Me (Device Area Sync)

Latter never modifies entities owned by other integrations. On roaming displays (`stationary == 0` in the hardware manifest) with **Voice Follows Me** enabled, Latter updates only the bound ESPHome device's Home Assistant Area after the device has remained in the new Area for the Device's dwell period (`area_follow_dwell_s` in the Device's subentry, 3 to 60 s, default 10 s; Studio's **Voice Follows Me Delay**), so area-less Assist voice commands target the Area you're in.
