# Latter (`ha-latter`)

**Universal Home Assistant companion middleware and dynamic entity-mapping layer for [Pocket Assistant](https://github.com/slampton/esphome-pocket-assistant) and ESPHome devices.**

Lightweight and battery-powered ESPHome devices shouldn't have to waste RAM, flash, and battery running an on-device `web_server`, nor should users have to edit YAML `substitutions:` and recompile firmware just to remap a weather provider, media player, room area, or data feed.

**Latter** provides a server-side companion tier inside Home Assistant that dynamically maps entities, normalizes complex backend APIs, and proxies heavy payloads into compact, MCU-friendly contracts over ESPHome's native Noise-encrypted API.

## Core Capabilities
- **Dynamic Entity Mapping (Zero Reflashing)**: Bind and remap `weather`, `media_player`, `calendar`, and room entities to your ESPHome device at runtime through Home Assistant's UI—no YAML `substitutions:` or firmware recompilation required.
- **Server-Side Device Companion**: Offloads configuration UI, state aggregation, and third-party service orchestration to Home Assistant so battery-powered and resource-constrained ESPHome nodes can remain ultra-lean.
- **Music Assistant Library, Queue & Podcast Engine**: Paginates speakers, favorites, playlists, artists, albums, live queues, and podcast episodes into compact 5-slot pages pushed directly to ESPHome device actions—eliminating external `mass_queue` dependencies.
- **Authenticated Image Proxy (`/api/latter/image_proxy/...`)**: Center-crops and downscales high-resolution artwork or wallpapers into lightweight baseline JPEGs (`~20 KB`) using Pillow and HMAC-SHA256 signed URLs, cutting MCU download and decode time by over 80%.
- **Idle-Guarded Media & Weather Serialization**: Interpolates active playback progress every 2 seconds *only* while playing/buffering (preventing Home Assistant Recorder bloat) and serializes multi-day `weather.get_forecasts` responses into compact strings for any display or headless ESPHome node.
- **100% Pocket Assistant v2.0 Backward Compatibility**: Drop-in replacement for `pocket_assistant_companion.yaml` (`sensor.pocket_assistant_active_media`, `sensor.pocket_assistant_weather_forecast`, `input_text.pocket_assistant_active_speaker`, and `script.pocket_assistant_music_browse`).

## Installation (Home Assistant Marketplace / HACS)
1. Open **Settings > Marketplace** (or **HACS > Integrations**) in Home Assistant.
2. Add `https://github.com/slampton/ha-latter` as a Custom Repository (Category: **Integration**).
3. Install **Latter** and restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration** and search for **Latter**.