# Entities Reference

All Latter entities are pure local-push—none of them poll. Per-device entities sit on a **Latter** device card (`_attr_has_entity_name = True`) linked to the bound ESPHome device through `via_device`.

## 3-Tier Entity Architecture

Latter spans **6 Home Assistant platforms** ([`sensor.py`](../../custom_components/latter/sensor.py), [`binary_sensor.py`](../../custom_components/latter/binary_sensor.py), [`device_tracker.py`](../../custom_components/latter/device_tracker.py), [`select.py`](../../custom_components/latter/select.py), [`number.py`](../../custom_components/latter/number.py), [`button.py`](../../custom_components/latter/button.py)) organized into three clean tiers:

1. **Tier 1 — Hardware & OS Entities on the Bound `ESPHome` Device:** `Music` (Sendspin `media_player`), Assist satellite + `Wake word` / `Wake word 2` selects, `Display: Screen Backlight`, `Project Firmware`, battery/USB telemetry, `System: RPC Outbox`, `System: Hardware Manifest`, `System: Link Report`, and hardware diagnostics. → [Using your device](https://github.com/slampton/esphome-latter-core/blob/main/docs/using-your-device.md)
2. **Tier 2 — Sleep-Safe Automation Surface on the `Latter` Device:** curated presence, timer/alarm, config, and quick-action entities backed by the Device's subentry—staying available for automations even while a battery device is asleep or hibernating.
3. **Tier 3 — Studio Preferences (`device_prefs` Protocol v3 Domain):** all **50 typed device preferences** (`studio/settings.py`) push directly over `esphome.<node>_latter_push_v3` across **6 Protocol v3 domains**, keeping `~8 KB` of signed URLs and preference blobs off Home Assistant's `state_changed` bus and SQLite recorder.

---

## Per-Device Entities (`Latter` Device)

`<slug>` is the normalized device slug (for example `pocket_assistant`). **BLE Tag** entries (phones, watches, and beacons) create only the presence entities marked ★; hardware traits in the device's manifest (`display`, `mic`, `spk`, `beacon`) gate the others.

### Visible Automation & Control Entities

| Entity | Platform / Category | State / Range | Key Attributes & Update Trigger |
| :--- | :--- | :--- | :--- |
| ★ `device_tracker.<slug>_ble_tracker` *(or `device_tracker.<slug>`)* | `device_tracker` | `home`, `not_home`, `unknown` | `area_id`, `area_name`, `floor_id`, `floor_name`, `closest_proxy`, `distance_ft`, `distance_m`, `rssi`, `match_method`, `assigned_person` — updates on BLE readings and away timeout |
| ★ `sensor.<slug>_current_area` | `sensor` | Area name, `Away`, `Unassigned` | `area_id`, `floor_id`, `floor_name`, `is_home`, `closest_proxy`, `distance_ft`, `distance_m`, `rssi`, `raw_rssi`, `ref_power_dbm`, `match_method`, `assigned_person` — updates on Area change or away |
| ★ `sensor.<slug>_current_floor` | `sensor` | Floor name, `Away`, `Unassigned` *(auto-created when Home Assistant Floors exist)* | `floor_id`, `area_id`, `area_name`, `is_home`, `assigned_person` — updates on Floor/Area change or away; omitted when zero Floors exist |
| ★ `sensor.<slug>_ble_distance` | `sensor` (`distance`) | Feet / meters | Same attributes as `current_area` — updates on BLE readings |
| `binary_sensor.<slug>_timer_active` | `binary_sensor` (`running`) | `on` / `off` *(display devices)* | `paused`, `remaining_seconds` — event-driven via `latter.timer_alarm_state` |
| `sensor.<slug>_timer_remaining` | `sensor` (`duration`, `s`) | Remaining seconds *(display devices)* | `running`, `paused` — ticked locally at 1 Hz in Home Assistant while running (zero Wi-Fi polling) |
| `binary_sensor.<slug>_alarm_ringing` | `binary_sensor` (`sound`) | `on` / `off` *(display devices)* | Asserts while an on-device alarm or timer chime is ringing (`latter.timer_alarm_state`) |
| `select.<slug>_power_profile` | `select` (`config`) | *Portable Carry* · *Handheld Roaming* · *Wearable Watch* · *Tabletop Dock* · *Always-On Wall / Desk* · *Custom* | Sleep-safe subentry control *(display devices)*; syncs via `device_prefs` |
| `select.<slug>_wake_word_mode` | `select` (`config`) | *Docked Only* · *Always On* · *Disabled* | Sleep-safe subentry control *(mic-equipped devices)*; syncs via `device_prefs` |
| `number.<slug>_alert_volume` | `number` (`config`) | `20–100%` (step `5%`) | Sleep-safe chime/alarm volume *(speaker-equipped devices)*; syncs via `device_prefs` |
| `button.<slug>_find_my_device` | `button` (`identify`) | Press | Dispatches `latter_device_command(command="find_my")` *(speaker-equipped devices)* |
| `button.<slug>_activate_screensaver` | `button` | Press | Dispatches `latter_device_command(command="activate_screensaver")` *(display devices)* |

### Hidden-by-Default Diagnostic Protocol v3 Sensors

Enabled by default (`entity_registry_visible_default = False`, `EntityCategory.DIAGNOSTIC`, `_unrecorded_attributes`) on display devices so human-readable summaries remain inspectable without recording wire payloads in SQLite. Full wire schemas live in [`DEVICE_CONTRACT.md`](https://github.com/slampton/esphome-latter-core/blob/main/DEVICE_CONTRACT.md).

| Entity | State (`< 255` chars) | Attributes | Pushed Domain (`latter_push_v3`) |
| :--- | :--- | :--- | :--- |
| `sensor.<slug>_area_context` | Active Area name | `rev` | **`area_context`:** `area_id`, `area_name`, `site_id`, `ble_closest_proxy`, `dock_apps`, `wallpaper_url`, `available_domains`, `area_temp`, `area_humidity`, `lights_on`, `covers_open`, whole-home states & capability bitmasks (`alarm_*` + `alarm_caps`, `thermostat_*` + `climate_caps`, `lock_*`, `garage_*`, `vacuum_*` + `vacuum_caps`), `alert_*`, `camera_snapshot_url`, `cameras_summary`, `doorbell_talk_state`, `intercom_targets_summary`, `activity_card`, `activity_sources`, `security_pin_policy`, `home_categories`, `area_icon`, `local_tz_info`, `world_clocks_summary` |
| `sensor.<slug>_active_media` | `off`, `idle`, `playing`, `paused`, `buffering` | `rev` | **`active_media`:** active/local/last speaker, volume target, playback state, title, artist, album, duration, position, volume, media type, signed `art_url` |
| `sensor.<slug>_weather_forecast` | Current weather condition | `rev` | **`weather_forecast`:** temperature, condition, high/low, humidity, wind, 5-day `forecast_5d` records, solar arc (`sun_*`), `moon_phase` |
| `sensor.<slug>_calendar_agenda` | Upcoming event count (up to 25) | `rev` | **`calendar_agenda`:** `summary` (up to 5 `time\|title\|location\|all_day` records) and `count` |
| `sensor.<slug>_remote_config` | Active remote slot label | `rev` | **`remote_config`:** active slot, configured count, and up to 10 `slots_summary` records |
| `sensor.<slug>_device_prefs` | Current `prefs_seq` | `rev`, `prefs_seq` | **`device_prefs`:** `prefs_seq` plus all 50 typed device preferences (`power_profile` through `local_clock_label`, including `theme_color_hex`, `world_clocks`, and `alarms_summary`) |

---

## Per-Person & Per-Area Entities

| Scope | Entity | State | Key Attributes |
| :--- | :--- | :--- | :--- |
| **Per Person** *(when a device has `Assigned Person`)* | `sensor.<person>_current_area` | Area of that person's most recently heard device | `area_id`, `floor_id`, `floor_name`, `device_slug`, `distance_ft`, `distance_m`, `match_method` |
| **Per Person** *(when Home Assistant Floors exist)* | `sensor.<person>_current_floor` | Floor of that person's most recently heard device, `Away`, or `Unassigned` | `floor_id`, `floor_name`, `area_id`, `device_slug`, `distance_ft`, `distance_m`, `match_method` |
| **Per Person** | `sensor.<person>_ble_distance` | Distance (`ft` / `m`) | Same as `sensor.<person>_current_area` *(avoid giving a device the exact same slug as a `person` ID)* |
| **Per Area** *(mapped BLE Areas)* | `binary_sensor.<area>_ble_occupancy` | `on` / `off` (`occupancy`) | `area_id`, `area_name`, `floor_id`, `fusion_mode`, `confidence_pct`, `ble_occupied`, `sensor_occupied`, `active_sensors`, `occupant_names`, `occupied_by`, `persons`, `closest_device`, `winning_rssi`, `closest_distance_m`, `closest_distance_ft`, `tracker_count` |
| **Per Area** | `sensor.<area>_occupants` | Occupant summary, `Occupied (Sensor)`, or `Empty` | `area_id`, `area_name`, `is_occupied`, `occupant_count`, `occupant_names`, `occupied_by`, `persons` |

→ [How sensor fusion works](../presence.md#area-occupancy-and-sensor-fusion)

---

## `latter_event` Bus Events & Area Registry Sync

Latter fires **`latter_event`** on the Home Assistant event bus:

| `type` | Event Data Fields |
| :--- | :--- |
| `area_changed` | `device_slug`, `previous_area_id`, `area_id`, `assigned_person` |
| `notification_dispatched` | `device_slug`, `title`, `message`, `priority`, `camera_url` |
| `doorbell_ring` | `camera_entity`, `ring_entity` |

**Device Registry Area Boundary (`areas.py:sync_esphome_device_area`):** Latter never mutates entities or devices owned by other integrations, with one documented exception—updating `area_id` on the Device's own bound ESPHome device (and mirroring it onto the child `via_device` Latter device):
1. **BLE Roaming (`Track the Area with BLE Proxies` on):** on roaming hardware (`stationary == 0`) with **Voice Follows Me** enabled, after the device remains in the new Area for its dwell delay (3–60 s, default 10 s), so area-less Assist commands target where you stand.
2. **Static Placement (`Track the Area with BLE Proxies` off):** synced two-way between Studio's **Assigned Area** and Home Assistant's Device Area.
