# Latter Studio — Everyday User & Administration Guide

When you install **Latter**, a new **Latter** panel is registered in your Home Assistant sidebar (and linked to the **Visit** button on each onboarded ESPHome device page).

Latter Studio is organized into two scopes using the top-left switcher:
1. **System Scope**: Shared household entities, BLE room calibration radar, device groups & reusable profiles, system/device backups, 4-slot TV remotes, and AVR volume routing.
2. **Device Scope**: Per-device live telemetry, capability-aware settings (Home & Display, Power, Voice Assistant, Audio & Media), BLE & WireGuard add-ons, and diagnostics.

---

## 1. System Scope: Shared Household Configuration

Settings configured under **System** are stored in `.storage/latter.household` and automatically shared across all companion devices in your home:

- **Overview & Devices**:
  - View all onboarded ESPHome devices, their current room, active speaker, and assigned Device Group.
  - Use **+ Bridge Existing Device** to onboard any existing 3rd-party ESPHome sensor (e.g., Everything Presence One, Bed Presence) in 1 click without editing YAML.
- **Shared Entities**:
  - **Security Alarm** (`alarm_control_panel.*`): Used by the on-device Whole-Home Hub (Disarm, Arm Home, Arm Away).
  - **Primary Camera** (`camera.*`): Used by the on-device Camera tool and Doorbell Peephole notification popups.
  - **Weather Forecast Provider** (`weather.*`): Drives the 20 FPS animated weather sky, 5-day forecast, and wake greetings.
  - **Primary Thermostat (`climate.*`), Entry Lock (`lock.*`), Garage Door (`cover.*`), Robot Vacuum (`vacuum.*`)**: Live entities controlled by the Whole-Home Hub (Page 9) on Pocket Assistant and Wrist Assist.
  - **Shared Calendars (`calendar.*`)**: Aggregated and deduplicated into upcoming agenda slots with automatic geocoded OpenStreetMap location views.
  - **Pinned Entities**: Entities pinned here appear at the top of Room Control across all rooms.
- **Remote Controls (4 Slots)**:
  - Assign up to 4 TVs, streaming boxes (Apple TV, Android TV / Shield / Fire TV / Bravia, Roku, Samsung, LG webOS), or AV Receivers (Denon / Marantz). Latter automatically pairs sibling `remote.*` and `media_player.*` entities on the same device.
- **Volume Routing**:
  - Map up to 2 external AV Receivers or `number.*` amplifiers so that when any companion device streams to a mapped Music Assistant speaker, volume up/down/set commands automatically route to your AVR.
- **Groups & Profiles**:
  - Assign devices to logical groups (*Handheld Displays*, *Bedrooms*, *Common Areas*, *Wall Panels*, *Presence Sensors*).
  - Click **Capture Profile** to snapshot a device's display, dock, wake word, sensitivity, and timeout settings into a reusable template that can be applied to any device or group in 1 click.
- **Backup & Restore**:
  - Save full **System** or single **Device** snapshots to the internal vault (`.storage/latter.backups`) or download a `.JSON` file to your computer. Device backups can also be restored onto a *different* device to clone its setup.

---

## 2. Device Scope: Per-Device Customization

Select any device in the sidebar dropdown to configure settings specific to that hardware:

- **Home & Display**:
  - Customize the Home Dock app order (`music,alarm,room,remote,games,tools`), choose a custom HSV Color Profile from the household color wheel, and upload or favorite photo wallpapers.
- **Power**:
  - Adjust battery screen timeout, docked idle timeout, hibernate schedule, pickup-to-wake, tap-to-wake, and screensaver style (*Aurora Borealis*, *Starfield*, *Matrix Rain*, *Fireworks*, *Ambient Clock*).
- **Voice Assistant**:
  - Switch on-device wake words (*Okay Nabu*, *Hey Luna*, *Hey Jarvis*, *Hey Mycroft*, *Alexa*), tune per-model detection sensitivity, and toggle automatic Home Assistant Area synchronization.
- **Audio & Media**:
  - Set onboard alert volume, volume step size, default speaker, and Music Assistant library sorting preferences.
