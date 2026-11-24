# Entities Reference

All Latter entities are pure local-push—none of them poll. Per-device entities sit on a **Latter** device card (`_attr_has_entity_name = True`) linked to the bound ESPHome device through `via_device`.

## 3-Tier Entity Architecture

Latter spans **8 Home Assistant platforms** ([`sensor.py`](../../custom_components/latter/sensor.py), [`binary_sensor.py`](../../custom_components/latter/binary_sensor.py), [`device_tracker.py`](../../custom_components/latter/device_tracker.py), [`light.py`](../../custom_components/latter/light.py), [`select.py`](../../custom_components/latter/select.py), [`number.py`](../../custom_components/latter/number.py), [`button.py`](../../custom_components/latter/button.py), [`switch.py`](../../custom_components/latter/switch.py)) organized into three clean tiers:

1. **Tier 1 — Stock-Clean Hardware & OS Entities on the Bound `ESPHome` Device:** `Music` (Sendspin `media_player`), Assist satellite + `Wake word` / `Wake word 2` selects, `Project Firmware`, battery/USB telemetry, and auto-hidden `System: RPC Outbox` (`RegistryEntryHider.INTEGRATION`). → [Using your device](https://github.com/slampton/esphome-latter-core/blob/main/docs/using-your-device.md)
2. **Tier 2 — Automation & Control Surface on the `Latter` Device:** curated presence, screen light, screensaver, Do Not Disturb, Bedtime Mode, timer/alarm, config, and quick-action entities backed by the Device's subentry—with sleep-safe preference entities staying available even while a battery device is asleep or hibernating.
3. **Tier 3 — Studio Preferences & Developer Telemetry (`device_prefs` & `device_telemetry`):** all **65 typed device preferences** (`protocol_specs.py`, merged from `protocol_v3.json` + `studio_contract.json`) push directly over `esphome.<node>_latter_push_v3` across **7 Protocol v3 domains**, while on-demand heap/PSRAM/BLE/link diagnostics stream over `device_telemetry` straight into Latter Studio's **Developer & telemetry** drawer—keeping signed URLs, preference blobs, and diagnostic churn off Home Assistant's `state_changed` bus and SQLite recorder. When a Device's hardware capabilities change across firmware updates, `reconcile_capability_entities()` automatically prunes stale display/mic/speaker/DND entities on `device_hello`. Full wire schemas live in [`DEVICE_CONTRACT.md`](https://github.com/slampton/esphome-latter-core/blob/main/DEVICE_CONTRACT.md).

---

## Per-Device Entities (`Latter` Device)

`<slug>` is the normalized device slug (for example `pocket_assistant`); on Home Assistant `2026.11+`, newly created entities on a Device that already belongs to an Area may include the Area slug prefix per Home Assistant's default entity naming rules. **BLE Tag** entries (phones, watches, and beacons) create only the presence entities marked ★; hardware traits in the device's manifest (`display`, `mic`, `spk`) gate the others.

| Entity | Platform / Category | Availability | State / Range | Key Attributes & Update Trigger |
| :--- | :--- | :--- | :--- | :--- |
| ★ `device_tracker.<slug>` *(or `device_tracker.<slug>_ble_tracker`)* | `device_tracker` | Sleep-safe | `home`, `not_home`, `unknown` | `area_id`, `area_name`, `floor_id`, `floor_name`, `closest_proxy`, `distance_m`, `rssi`, `match_method`, `assigned_person` — updates on BLE readings and away timeout |
| ★ `sensor.<slug>_current_area` | `sensor` | Sleep-safe | Area name, `Away`, `Unassigned` | `area_id`, `floor_id`, `floor_name`, `is_home`, `closest_proxy`, `distance_m`, `rssi`, `raw_rssi`, `ref_power_dbm`, `match_method`, `assigned_person` — updates on Area change or away |
| ★ `sensor.<slug>_current_floor` | `sensor` | Sleep-safe | Floor name, `Away`, `Unassigned` *(auto-created when Home Assistant Floors exist)* | `floor_id`, `area_id`, `area_name`, `is_home`, `assigned_person` — updates on Floor/Area change or away; omitted when zero Floors exist |
| ★ `sensor.<slug>_ble_distance` | `sensor` (`distance`, `m`, `diagnostic`; *disabled by default*) | Sleep-safe | Meters (`UnitOfLength.METERS`) | Same attributes as `current_area` — enable per device in Home Assistant's entity settings if you want continuous RSSI-derived distance history; Home Assistant converts automatically to `ft` or `m` per user unit preferences |
| `light.<slug>_screen` | `light` (`brightness`, `config`) | Live (`radio_connected`) | `on` / `off`, `1–100%` *(display devices)* | Event-driven via `display_state` RPC; `light.turn_on` / `light.turn_off` wakes the screen, adjusts backlight brightness, or turns the panel off (`EntityCategory.CONFIG` keeps it out of Area/Lights dashboards, Assist, and Area `light.turn_off`) |
| `switch.<slug>_screensaver` | `switch` (`config`) | Live (`radio_connected`) | `on` / `off` *(display devices)* | Reflects active ambient screensaver (`display_state` RPC); toggles `activate_screensaver` / `deactivate_screensaver` (`EntityCategory.CONFIG` keeps it out of Area `switch.turn_off`) |
| `switch.<slug>_do_not_disturb` | `switch` (`config`) | Sleep-safe | `on` / `off` *(display or speaker devices)* | Silences non-critical notification chimes, banners, and voice announcements across sleep/wake (`do_not_disturb` in `device_prefs`; `EntityCategory.CONFIG`) |
| `switch.<slug>_bedtime_mode` | `switch` (`config`) | Sleep-safe | `on` / `off` *(display devices)* | Overnight Bedtime Mode toggle (`Screen Off` or `Ambient Clock` idle display, `18%` night-wake brightness, silenced non-critical alerts, without detaching from the Device Group); syncs via `device_prefs` (`EntityCategory.CONFIG`) |
| `button.<slug>_dismiss_alert` | `button` | Live (`radio_connected`) | Press *(display devices)* | Dismisses any active notification takeover or ringing timer/alarm alert (`dismiss_ringing` / `cancel_timer`) |
| `button.<slug>_find_my_device` | `button` (`identify`, `config`) | Live (`radio_connected`) | Press *(speaker devices)* | Plays the Find My Device locator chime via `latter_device_command(command="find_my")` |
| `binary_sensor.<slug>_timer_active` | `binary_sensor` (`running`) | Sleep-safe | `on` / `off` *(display devices)* | `paused`, `remaining_seconds` — event-driven via `timer_alarm_state` RPC |
| `sensor.<slug>_timer_remaining` | `sensor` (`duration`, `s`) | Sleep-safe | Remaining seconds *(display devices)* | `running`, `paused` — ticked locally at 1 Hz in Home Assistant only while running (zero Wi-Fi polling) |
| `binary_sensor.<slug>_alarm_ringing` | `binary_sensor` (`sound`) | Sleep-safe | `on` / `off` *(display devices)* | Asserts while an on-device alarm or timer chime is ringing (`timer_alarm_state` RPC) |
| `select.<slug>_device_group` | `select` (`config`) | Sleep-safe | *Pocket Carry* · *Handhelds* · *Wearables* · *Wall & Desk Panels* · custom groups · *Custom* | Subentry Device Group preset selector; syncs active group baseline via `device_prefs` |
| `select.<slug>_wake_word_mode` | `select` (`config`) | Sleep-safe | *Docked Only* · *Always On* · *Disabled* | Subentry wake-word policy *(mic-equipped devices)*; syncs via `device_prefs` |
| `number.<slug>_alert_volume` | `number` (`config`) | Sleep-safe | `20–100%` (step `5%`) | Chime and alarm volume *(speaker-equipped devices)*; syncs via `device_prefs` |

---

## Per-Person & Per-Area Entities (`Latter System` Service Device)

| Scope | Entity | State | Key Attributes |
| :--- | :--- | :--- | :--- |
| **Per Person** *(when a device has `Assigned Person`)* | `sensor.latter_system_<person>_current_area` | Area of that person's most recently heard device | `area_id`, `floor_id`, `floor_name`, `device_slug`, `distance_m`, `match_method` |
| **Per Person** *(when Home Assistant Floors exist)* | `sensor.latter_system_<person>_current_floor` | Floor of that person's most recently heard device, `Away`, or `Unassigned` | `floor_id`, `floor_name`, `area_id`, `device_slug`, `distance_m`, `match_method` |
| **Per Person** *(`diagnostic`, disabled by default)* | `sensor.latter_system_<person>_ble_distance` | Meters (`UnitOfLength.METERS`) | Same as `sensor.latter_system_<person>_current_area` |
| **Per Area** *(mapped BLE Areas)* | `binary_sensor.latter_system_<area>_occupancy` | `on` / `off` (`occupancy`) | `area_id`, `area_name`, `floor_id`, `fusion_mode`, `confidence_pct`, `ble_occupied`, `sensor_occupied`, `active_sensors`, `occupant_names`, `occupied_by`, `persons`, `closest_device`, `winning_rssi`, `closest_distance_m`, `tracker_count` |
| **Per Area** | `sensor.latter_system_<area>_occupants` | Occupant summary, `Occupied (Sensor)`, or `Empty` | `area_id`, `area_name`, `is_occupied`, `occupant_count`, `occupant_names`, `occupied_by`, `persons` |

→ [How sensor fusion works](../presence.md#area-occupancy-and-sensor-fusion)

---

## `latter_event`

Latter fires **`latter_event`** on the Home Assistant event bus:

| `type` | Event Data Fields |
| :--- | :--- |
| `area_changed` | `device_slug`, `previous_area_id`, `area_id`, `assigned_person` |
| `notification_dispatched` | `device_slug`, `title`, `message`, `priority`, `camera_url` |
| `doorbell_ring` | `camera_entity`, `ring_entity` |

**Device Registry Area Boundary (`areas/sync.py:sync_esphome_device_area`):** Latter never mutates entities or devices owned by other integrations, with one documented exception—updating `area_id` on the Device's own bound ESPHome device (and mirroring it onto the child `via_device` Latter device):
1. **BLE Roaming (`Track the Area with BLE Proxies` on):** on roaming hardware (`stationary == 0`) with **Voice Follows Me** enabled, after the device remains in the new Area for its dwell delay (3–60 s, default 10 s), so area-less Assist commands target where you stand.
2. **Static Placement (`Track the Area with BLE Proxies` off):** synced two-way between Studio's **Assigned Area** and Home Assistant's Device Area.
