# Latter (`ha-latter`)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=slampton&repository=ha-latter&category=integration)

**Universal Home Assistant companion middleware and dynamic entity-mapping layer for [Pocket Assistant](https://github.com/slampton/esphome-pocket-assistant) (`v2.1.0+`) and ESPHome devices.**

Lightweight and battery-powered ESPHome devices shouldn't have to waste RAM, flash, and battery running an on-device `web_server`, nor should users have to edit YAML `substitutions:` and recompile firmware just to remap a weather provider, media player, TV remote, alarm panel, or room area.

**Latter** provides a server-side companion tier inside Home Assistant that dynamically maps entities, normalizes complex backend APIs, tracks room presence over BLE, and proxies heavy payloads into compact, MCU-friendly contracts over ESPHome's native Noise-encrypted API.

---

## Key Capabilities

1. **Zero-YAML Dynamic Entity Mapping (`ConfigFlow` + `OptionsFlow`)**
   - Map and remap your **Weather Provider**, **Home Security Alarm (`alarm_control_panel`)**, **4 TV/Media Remote Slots**, **Music Assistant Speakers**, **Speaker Volume Overrides**, and **Family Calendars** directly in **Settings > Devices & Services > Latter > Configure**—never recompile ESPHome YAML again.
2. **BLE Room Presence & Room-Aware Voice Assistant**
   - Automatically detects which room your portable ESPHome device is in and switches your on-device Room Controls, active room speaker/remote, **and** your ESPHome device's Home Assistant Area assignment—so saying *"Turn on the lights"* or *"Close the blinds"* to the Voice Assistant automatically controls the room you are standing in!
3. **Curated Room Control & Environmental Telemetry**
   - Automatically discovers lights, scenes, window coverings (blinds/curtains/shades), fans, climate, smart outlets, and the room's Music Assistant speaker—filtering out diagnostic/config switch clutter—while exposing live room temperature and humidity (`room_temp`, `room_humidity`).
4. **Native Music Assistant Library, Queue & Podcast Engine**
   - Filters speaker selection strictly to Music Assistant players and paginates favorites, playlists, artists, albums, tracks, live queues, and podcast episodes into 5-slot pages with zero `mass_queue` dependency.
5. **Authenticated 466×466 JPEG Artwork Proxy (`/api/latter/image_proxy/...`)**
   - Center-crops and downscales high-resolution album artwork into lightweight baseline JPEGs (`~20 KB`) using Pillow and HMAC-SHA256 signed URLs, with a sticky pause/transfer cache so artwork never disappears when paused.

---

## Installation

1. Click the **Open HACS Repository** badge above, or open **Settings > Marketplace** (or **HACS > Integrations**) in Home Assistant and add `https://github.com/slampton/ha-latter` as a Custom Repository (Category: **Integration**).
2. Download **Latter** and restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and search for **Latter**.

---

## Configuration & Feature Guides

You can adjust any setting at any time under **Settings > Devices & Services > Latter > Configure**.

### 1. Automatic BLE Room Presence (Two Easy Ways)

To track a portable battery-powered ESPHome device (like Pocket Assistant) across rooms without draining its battery, the device broadcasts a lightweight **BLE iBeacon** (`UUID: 504F434B-4554-4153-5354-000000000210`) when its **BLE Room Beacon** switch is turned ON, while fixed ESPHome `bluetooth_proxy` nodes in your rooms listen for it.

 Make sure each of your room ESPHome BLE proxy devices is assigned to its proper **Area (Room)** in Home Assistant!

#### Option A: Built-In Native BLE Proxy Tracking (Recommended — Zero Extra Integrations!)
Latter includes a built-in Bluetooth advertisement engine (`ble_engine.py`) that listens directly to Home Assistant's internal Bluetooth manager:
1. Turn ON the **BLE Room Beacon** toggle on your Pocket Assistant device.
2. In **Latter > Configure**, keep **Enable Built-In ESPHome BLE Proxy Room Tracking** checked (`ON`).
3. Leave **External BLE Room Sensor Override** blank.
4. As you walk from room to room, Latter measures the smoothed signal strength (EMA RSSI with 6 dB hysteresis and an 8-second hold guard) reported by each room's ESPHome BLE Proxy and automatically switches your active room!

#### Option B: Using Bermuda BLE Trilateration (Optional)
If you already run the **Bermuda BLE Trilateration** integration and prefer to use Bermuda's distance solver:
1. Turn ON the **BLE Room Beacon** toggle on your Pocket Assistant device.
2. Open **Settings > Devices & Services > Bermuda BLE Trilateration > Configure > Select Devices** and check the iBeacon **`504f434b-4554-4153-5354-000000000210`** (Major `1`, Minor `1`).
3. Bermuda will create an Area sensor for the device (e.g., `sensor.pocket_assistant_area`).
4. Open **Settings > Devices & Services > Latter > Configure** and select that `sensor.*_area` entity under **External BLE Room Sensor Override**.

#### How Room-Aware Voice Assistant Works
When **Sync Active Room to ESPHome Device Area** is enabled in Latter, every time your active room changes, Latter updates the Pocket Assistant device's `area_id` in Home Assistant's Device Registry. When you trigger the Voice Assistant and say *"Turn on the lights"*, Home Assistant's Assist pipeline automatically targets the lights in your current room!

---

### 2. Speaker Volume Overrides (Music Streamer + AV Receiver)

Many setups stream music to a Music Assistant player (e.g., a WiiM, Chromecast, or network streamer) whose output is plugged into a separate Home Theater AV Receiver (`media_player.*`) or amplifier (`number.*` / `input_number.*`) that actually controls the room's volume.

In **Latter > Configure**:
1. Under **Volume Override 1: When Streaming to Speaker...**, select your Music Assistant streamer from the dropdown (e.g., `media_player.living_room_streamer`).
2. Under **Volume Override 1: Control Volume on Entity...**, select the AV Receiver or volume entity that controls the physical volume (e.g., `media_player.denon_avr` or `number.amp_volume`).
3. *(Optional)* Use **Volume Override 2** for a second room, or add more pairs in **Additional Volume Overrides** using `media_player.streamer=media_player.receiver` format.

Whenever that Music Assistant speaker is selected on Pocket Assistant:
- The volume bar on Pocket Assistant automatically displays the AV Receiver's current volume.
- Volume Up, Volume Down, Mute, and slider adjustments (`latter.media_volume`) automatically route to the AV Receiver!

---

### 3. 4-Slot TV / Media Remotes (Zero YAML Substitutions)

In **Latter > Configure**, select up to 4 TVs, Apple TVs, Rokus, Android TVs, or Media Players under **TV / Media Remote Slot 1–4**:
- You can pick either the `remote.*` entity or the `media_player.*` entity—Latter automatically looks up the device in Home Assistant's Device Registry and binds both its `remote.*` and `media_player.*` sibling entities!
- When you walk into a room that matches one of your 4 remote slots, Latter automatically highlights that room's remote slot.

---

### 4. Home Security Alarm (`alarm_control_panel`)

In **Latter > Configure**, select your home's primary `alarm_control_panel.*` entity under **Home Security Alarm Entity** (Latter also auto-selects your first alarm panel by default).
- Exposes real-time `alarm_state` (`disarmed`, `armed_home`, `armed_away`, `armed_night`, `triggered`), `alarm_name`, and `alarm_code_required` on `sensor.pocket_assistant_room_context`.
- Supports arming and disarming directly via `latter.room_action` (`action: "arm_home" | "arm_away" | "arm_night" | "disarm"`).
---

---

## Support the Project

Pocket Assistant and Latter for Home Assistant are built and maintained by Sean Lampton (**Lampton Labs**). If this project is useful in your home and you'd like to support ongoing development and test hardware:

* ☕ **[Buy Me a Coffee](https://www.buymeacoffee.com/slampton)**
* ❤️ **[Sponsor on GitHub](https://github.com/sponsors/slampton)**
  
---
