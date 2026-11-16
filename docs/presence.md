# Presence

Latter tracks which Area each Device is in using the Bluetooth proxies across your System. It then puts that Area to work: moving a roaming Device's Home Assistant Area so Assist targets where you stand, scoping Area Controls, handing off active media, and routing occupied-Area notifications and intercom broadcasts.

<!-- MEDIA: docs/media/presence-survey.png — Studio → BLE & Area Presence with live per-scanner calibration and multi-scanner Area signatures. -->

---

## What you need

- **Bluetooth scanners assigned to your Areas** in Home Assistant. ESPHome Bluetooth proxies (`bluetooth_proxy: active: true`) are tested; local USB adapters, Shelly proxies, and other scanners exposed by Home Assistant's `bluetooth` integration work through the same passive callback pipeline.
  - **Proxy-less Areas work too:** interior Areas without their own proxy (for example a guest bath, hallway, or pantry surrounded by 2–3 proxies in neighboring Areas) can be resolved by capturing a **Multi-Scanner Area Signature** in Studio.
- **Optional:** Home Assistant **Floors** assigned to your Areas. Configuring Floors enables the `6.0 dB` cross-floor vertical attenuation penalty and automatically creates `sensor.<slug>_current_floor` and `sensor.<person>_current_floor` entities.

## What can be tracked

| Target | How it's identified | How to add it |
| :--- | :--- | :--- |
| Latter firmware Devices | Bound Device MAC (`±2` for ESP32 BLE offset) + unique 128-bit CSPRNG System BLE UUID (`latter_set_beacon_uuid`, saved in NVS) + verified `major` / `minor` identity (including ESP32-P4 Devices whose BLE radio runs on a companion C6 chip, while rejecting spoofed UUIDs) | Adopt from **Studio → Devices → Discovered → Latter Devices** (or enable **Track the Area with BLE Proxies** on the Device's **Presence** page) |
| Phones and watches | Home Assistant's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration resolves rotating IRK addresses; Latter listens to `state_changed` events on `current_address` for **0 ms RPA rotation** and immediately evicts stale addresses | Set up Private BLE Device, then **Studio → Devices → Discovered → Bluetooth Devices → Adopt** |
| Beacons and BLE sensors | **Apple iBeacon**, **Eddystone-UID** (`0xFEAA`), **BTHome v2** (`0xFCD2`), or an `ibeacon` tracker entity (both connectable and non-connectable advertisements) | Adopt from **Discovered → Bluetooth Devices**, or click **Add BLE Tag** |
| Static-MAC BLE Devices | Static Bluetooth MAC address (connectable or non-connectable) | Adopt from **Discovered → Bluetooth Devices**, or click **Add BLE Tag** |

Latter firmware ships with its BLE presence beacon inactive out of the box so a new or reset Device does not advertise until presence is configured. When **Track the Area with BLE Proxies** is enabled, Latter provisions the System's random 128-bit BLE UUID (`latter_set_beacon_uuid`) and enables advertising via Protocol v3 (`device_prefs.ble_beacon_enabled`), with battery duty tuned in **Studio → Devices → Presence → BLE Beacon Mode** (*Handheld Only*, *Handheld + Screen Off*, or *Always*). Roaming Latter Devices also pause `latter_beacon` automatically whenever Wi-Fi is disconnected (`!wifi_connected`), preventing off-site public BLE tracking and saving battery.

To link a tracked Device to a person, set **Assigned Person** on the Device's **Overview** page. Latter creates `sensor.<person>_current_area`, `sensor.<person>_ble_distance`, and (whenever Floors exist in Home Assistant) `sensor.<person>_current_floor`, following whichever of that person's Devices was heard most recently, alongside `device_tracker.<slug>` (`home` / `not_home`) for Home Assistant `person` zone tracking (**Settings → People**).

---

## How the spatial engine decides

All filtering, trilateration, hysteresis, and sensor-fusion parameters live in [`presence.py`](../custom_components/latter/presence.py), with environmental constants tunable live in **Studio → System → BLE & Area Presence → Spatial Engine Settings**.

1. **Collect.** Latter registers passive Home Assistant Bluetooth callbacks (`BluetoothCallbackMatcher()` in `PASSIVE` mode, accepting both `connectable=True` and `connectable=False` frames) plus per-address advertisement listeners for static-payload beacons and instant `state_changed` RPA handoff for `private_ble_device` trackers. Readings at or below `−100 dBm` are dropped, and a **3.0 dBm RSSI hysteresis deadband** suppresses minor fluctuations while the winning Area is unchanged.
2. **Filter per scanner (never blended).** Every scanner (`source` MAC) maintains its own `ScannerObservationState`—two proxies in the same Area never contaminate each other's filter:
   - **3-sample rolling median** strips single-channel BLE 37/38/39 Rayleigh multipath spikes and deep fades before smoothing.
   - **Adaptive 1D Kalman filter + velocity gate** (`Maximum Movement Speed`, default `3.5 m/s`, `0.5–15.0 m/s`) damps sudden human-body shadowing drops that imply receding faster than `max_velocity_mps × Δt`, while genuine approaches toward a scanner converge immediately.
   - After **2 s** without a packet, a scanner's score decays by **1.5 dB/s**; after **12 s**, it ages out of Area competition.
3. **Normalize & score Areas.**
   - **Reference Power Normalization:** Latter auto-detects advertised 1 m reference power from Apple iBeacon byte 22, Eddystone-UID 0 m TX power (`− 41 dB`), or `tx_power` metadata (falling back to `−59 dBm`), or uses the per-Device **Reference Power (1 Meter)** override (`−90` to `−30 dBm` on **Devices → Presence → BLE Identity**). Each scanner's filtered RSSI is shifted by its **per-scanner offset** (`±25 dB`) and normalized to a `−59 dBm @ 1 m` equivalent (`norm_dbm`).
   - **Path-loss distance & radius gate:** Distance is estimated via `d = 10^((−59 − norm_dbm) / (10 × attenuation))` meters (**Path-Loss Attenuation**, default `2.2`, `1.5–4.5`). Scanners beyond **Maximum Area Radius** (default `12.0 m`, `2.0–50.0 m`) are disqualified from claiming an Area via path-loss so outdoor leakage cannot pull a Device out of an indoor Area.
   - **Same-Area multi-scanner aggregation:** An Area with multiple scanners takes the **maximum** decayed score among its fresh scanners—never averaging a nearby scanner down with a far corner scanner—plus a **`+1.5 dB` corroboration bonus** when a second fresh scanner in that Area is also at `−82 dBm` or stronger.
   - **Multi-Scanner Area Signatures (`match_method: signature`):** Any Area with a saved vector signature—including **proxy-less Areas**—is scored by joint multi-scanner Gaussian + pairwise-differential matching across visible scanners (penalizing missing strong signature scanners) on the same dBm-equivalent scale.
   - **Cross-floor vertical attenuation:** When Floors are configured and a candidate Area sits on a different Floor from the current Area, the candidate receives **`−6.0 dB`**.
4. **Decide & prevent Area-jumping.**
   - **Wake multi-proxy coalescing (`~0.35 s`):** When a sleeping Device wakes while holding a sticky Area that has a registered scanner, an early Packet #1 arriving over TCP from a distant Area waits `0.35 s` (or for Packet #2) before switching—eliminating 20–150 ms Wi-Fi/TCP proxy race jumps while still committing genuine moves cleanly.
   - **Fast override (`≥ 8.0 dB` lead with `≥ 2` challenger packets):** Bypasses the **4.0 s** hold only once the challenger Area has delivered at least two packets, blocking single-packet multipath spikes.
   - **Standard switch (`≥ 5.0 dB` lead after `4.0 s` hold):** Switches once a challenger leads by at least `5.0 dB` and `4.0 s` have elapsed since the last Area switch.
   - No Area wins while its effective score is below **`−88 dBm`**.
5. **Away.**
   - With no matched packets for **Away Timeout** (default **180 s**, configurable `30–900 s`), BLE tags and offline Devices are marked `Away` (and `current_floor` transitions to `Away`).
   - Display Devices with a live Wi-Fi connection, intentional screen-off BLE sleep (`ble_radio_active == off`), or latched battery hibernation retain their last Area instead of flipping `Away`.

## Calibrating & capturing signatures

Walls, foil-backed insulation, and receiver antenna designs mean raw RSSI varies across proxy hardware and tricky boundaries.

1. **Per-Scanner BLE Calibration (`Studio → System → BLE & Area Presence`):**
   - Select a tracked Device and click **Live Stream On** to stream real-time per-scanner raw, Kalman-filtered, offset, and effective RSSI plus distance over WebSocket.
   - Use **`-1 dB`**, **`+1 dB`**, or **`Reset`** (`±25 dB`) on individual scanners to normalize hot or recessed proxy hardware across all tracked Devices.
2. **Multi-Scanner Area Signatures (`Studio → System → BLE & Area Presence`):**
   - Stand in an Area—such as a boundary zone or a **proxy-less Area** surrounded by neighboring scanners—for 5–10 seconds with **Live Stream On**.
   - Click **Capture Signature** on that Area's row. Latter records the normalized multi-scanner fingerprint (`mean`, `std`, and sample count in 1 m-equivalent `norm_dbm` space), so signatures captured with one handheld or phone generalize automatically to other Devices with different TX powers.
   - Click **Clear** at any time to return that Area to standard path-loss scoring.
3. **Per-Device Reference Power (`Studio → Devices → <Device> → Presence → BLE Identity`):**
   - Leave **Reference Power (1 Meter)** blank to use the auto-detected advertised 1 m power shown in the placeholder, or enter a calibrated value (`−90` to `−30 dBm`) for cases, pockets, or custom tags.

---

## Area occupancy and sensor fusion

Latter creates one occupancy binary sensor and one occupants sensor per mapped Area: `binary_sensor.<area>_ble_occupancy` and `sensor.<area>_occupants`. Each Area can fuse BLE presence with existing sensors assigned to that Area:

| Input | Effect on the Area's confidence score |
| :--- | :--- |
| A tracked Device present | `+0.85` at `−68 dBm` or stronger, `+0.70` at `−80 dBm` or stronger, otherwise `+0.54` |
| Occupancy or presence sensor on (for example mmWave) | Raises the score to at least `0.78`, plus a bonus if BLE agrees |
| Motion sensor on | Raises the score to at least `0.68`, plus a bonus if BLE agrees |
| Door or opening closed | `+0.08` |
| Occupancy sensor explicitly off, no motion, weak BLE | `−0.18` |

Fusion modes, set per Area in Studio (**System → BLE & Area Presence**, with threshold and participating sensors under **Fusion Settings**):

| Mode | Behavior |
| :--- | :--- |
| `weighted` (default) | Occupied when the weighted confidence score passes the Area's threshold (default `50%`, adjustable `20–95%`) |
| `any_or` | Occupied if BLE **or** any selected sensor is active |
| `ble_only` | BLE presence only |
| `ble_and_sensor` | Requires BLE **and** an active sensor (where the Area has sensors) |

> The weighted score is a transparent additive rule—not an opaque Bayesian network—so every transition can be inspected directly from entity attributes.

Sensors are discovered automatically by device class (`occupancy`, `presence`, `motion`, `moving`, `door`, `opening`) across both entity Areas and device Areas.

## What Latter does with the Area

- **Moves roaming Devices' Home Assistant Area (and syncs static Assigned Areas).** When a roaming Device (`stationary == 0`) with **Voice Follows Me** enabled settles into a new Area for its **Voice Follows Me Delay** (`10 s` default, `3–60 s` in **Studio → Audio**), Latter updates `area_id` on both the bound ESPHome Device and child Latter Device so area-less Assist commands target where you stand. When **Track the Area with BLE Proxies** is off, Studio's **Assigned Area** syncs two-way with Home Assistant's Device Area instead.
- **Scopes Area Controls** on the Device to its active Area.
- **Moves media with the Device**, when **Media Follows This Device to Its New Area** is on (**Studio → Audio**): switching speaker targets and transferring active playback cleanly.
- **Routes notifications and intercom.** `target_device: occupied_areas` delivers strictly to Devices in occupied Areas; if no Area is occupied, nothing plays into empty spaces. See [services](reference/services.md#special-target-values).
- **Fires `latter_event`** with `type: area_changed` for custom automations.

---

## Coming from Bermuda

[Bermuda](https://github.com/agittins/bermuda) is a mature, widely used Home Assistant BLE trilateration integration. Here is the direct technical comparison:

| Capability | Bermuda | Latter |
| :--- | :--- | :--- |
| Area sensor per tracked Device | ✓ | ✓ (`sensor.<slug>_current_area`) |
| Floor sensor per tracked Device | ✓ | ✓ (`sensor.<slug>_current_floor`, auto-created when Floors exist) |
| Area & Floor sensors per Person | Through `person` | ✓ (`sensor.<person>_current_area`, `sensor.<person>_current_floor`) |
| Phones & watches via Private BLE Device | ✓ | ✓ (**0 ms** event-driven IRK RPA rotation) |
| Beacons, BTHome & connectable BLE | ✓ (iBeacon, Eddystone, BTHome, MACs) | ✓ (Apple iBeacon, Eddystone-UID `0xFEAA`, BTHome v2 `0xFCD2`, connectable & non-connectable MACs) |
| `device_tracker` for `person` Home/Away | ✓ | ✓ (`device_tracker.<slug>`) |
| Filtering & anti-jump protection | Kalman / adaptive smoothing + velocity spike rejection | **3-sample median** (channel-hop null rejection) + **velocity-gated 1D Kalman** + **0.35 s wake multi-proxy coalescing** + **2-packet fast-override gate** |
| Calibration & RF physics tuning | Per-scanner offsets, per-device ref power, global attenuation, max radius, max velocity | ✓ Per-scanner offsets (`±25 dB`), auto/manual per-Device 1 m reference power, configurable attenuation, max radius, max velocity, and away timeout |
| Proxy-less Areas & boundary zones | Requires local scanner or manual radius tricks | ✓ **Multi-Scanner Area Signatures** resolve proxy-less Areas via multi-scanner vector matching |
| Per-scanner distance entities (`N × M`) | ✓ (`sensor.<dev>_distance_to_<scanner>`) | **No.** Exposes one closest-distance sensor per Device/Person (`ble_distance`) and streams per-scanner distances live in Studio to keep the state machine lean |
| Same entity IDs for drop-in automations | — | **No.** Automations should point to Latter's `current_area`, `current_floor`, or `ble_occupancy` entities |

**What Latter adds natively on top of BLE positioning:** `6.0 dB` cross-floor vertical attenuation, per-Area occupancy fused with mmWave/PIR/door sensors, automatic Home Assistant Device Area sync for Assist (*Voice Follows Me*), media handoff, occupied-Area notification/intercom routing, and zero-reflash sleep-safe Studio calibration.

### Switching over

1. Ensure each Bluetooth proxy is assigned to its Home Assistant Area (and assign Floors to your Areas if your Site has multiple levels).
2. Open **Studio → Devices → Discovered**, adopt your Latter Devices, phones (`Private BLE Device`), watches, and BLE tags, and set **Assigned Person** on personal Devices.
3. Attach `device_tracker.<slug>` to each person in **Settings → People** if you want BLE Home/Away zone tracking.
4. Walk your Site with **Studio → System → BLE & Area Presence → Live Stream On**: trim any hot/quiet proxy hardware in **Per-Scanner BLE Calibration**, and click **Capture Signature** in any proxy-less Area or tight doorway boundary.
5. Point your automations at `sensor.<person>_current_area`, `sensor.<person>_current_floor`, or `binary_sensor.<area>_ble_occupancy`.

---

## Known trade-offs

- **Discrete Areas and Floors, not `(x, y, z)` coordinates.** Latter determines which Home Assistant Area and Floor a Device occupies (including proxy-less Areas via captured signatures), rather than estimating meter coordinates on a floorplan.
- **No `devices × scanners` entity explosion.** Per-scanner raw/filtered RSSI and distance stream live over WebSocket when calibrating in Studio instead of registering dozens of high-churn recorder entities per Device.
- **Captured signatures depend on proxy placement.** If you physically move or replace a Bluetooth proxy, recapture **Multi-Scanner Area Signatures** for nearby Areas that depend on that scanner.
