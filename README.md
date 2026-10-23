# Latter (`ha-latter`)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=slampton&repository=ha-latter&category=integration)

**Universal Home Assistant companion middleware and dynamic entity-mapping layer for [Pocket Assistant](https://github.com/slampton/esphome-pocket-assistant) (v2.1.0+) and ESPHome devices.**

Lightweight and battery-powered ESPHome devices shouldn't have to waste RAM, flash, and battery running an on-device `web_server`, nor should users have to edit YAML `substitutions:` and recompile firmware just to remap a weather provider, media player, room area, or data feed.

**Latter** provides a server-side companion tier inside Home Assistant that dynamically maps entities, normalizes complex backend APIs, and proxies heavy payloads into compact, MCU-friendly contracts over ESPHome's native Noise-encrypted API.

## Core Capabilities
- **Dynamic Entity Mapping (Zero Reflashing)**: Bind and remap `weather`, `media_player`, `calendar`, and room entities to your ESPHome device at runtime through Home Assistant's UI—no YAML `substitutions:` or firmware recompilation required.
- **Server-Side Device Companion**: Offloads configuration UI, state aggregation, and third-party service orchestration to Home Assistant so battery-powered and resource-constrained ESPHome nodes can remain ultra-lean.
- **Area-Aware Room Control & Unified Context Handoff**: Automatically discovers Home Assistant areas and controllable entities (`light`, `cover`, `climate`, `fan`, `switch`, `scene`), normalizes 0–100 slider levels, and optionally hands off active speaker/remote context when switching rooms.
- **Music Assistant Library, Queue & Podcast Engine**: Paginates speakers, favorites, playlists, artists, albums, live queues, and podcast episodes into compact 5-slot pages pushed directly to ESPHome device actions—eliminating external `mass_queue` dependencies.
- **Family Calendar Agenda & Household Intercom**: Aggregates and deduplicates upcoming events across `calendar.*` entities into compact strings and relays TTS/audio announcements across household speakers.
- **Authenticated Image Proxy (`/api/latter/image_proxy/...`)**: Center-crops and downscales high-resolution artwork or wallpapers into lightweight baseline JPEGs (`~20 KB`) using Pillow and HMAC-SHA256 signed URLs, cutting MCU download and decode time by over 80%.
- **Idle-Guarded Media & Weather Serialization**: Interpolates active playback progress every 2 seconds *only* while playing/buffering (preventing Home Assistant Recorder bloat) and serializes multi-day `weather.get_forecasts` responses into compact strings for any display or headless ESPHome node.

## Installation (Home Assistant Marketplace / HACS)
1. Click the **Open HACS Repository** badge above, or open **Settings > Marketplace** (or **HACS > Integrations**) in Home Assistant and add `https://github.com/slampton/ha-latter` as a Custom Repository (Category: **Integration**).
2. Install **Latter** and restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and search for **Latter**.