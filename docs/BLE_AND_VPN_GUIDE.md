# BLE Room Calibration & Roaming WireGuard VPN Guide

## Part 1: Native BLE Room Presence & Calibration Radar

Latter includes a zero-config Bluetooth room presence engine (`ble_engine.py`) that tracks portable ESPHome devices across your home's ESPHome Bluetooth Proxies.

### 1. Setting Up Room Bluetooth Proxies
For Latter to know which room a proxy represents:
1. Ensure you have at least one stationary ESPHome node with `bluetooth_proxy: active: true` (or include the 1-line mixin `github://slampton/esphome-latter-core/mixins/ble_proxy.yaml@main`) in each room you want to track.
2. In Home Assistant, assign each ESPHome proxy device to its corresponding **Area** (*Living Room*, *Kitchen*, *Primary Bedroom*, *Office*, etc.).

### 2. Calibrating Room Boundaries ("Prioritize Here")
Because walls, furniture, and antenna placement affect 2.4 GHz signal strength, a proxy in an adjacent hallway may occasionally report a stronger raw RSSI than the proxy in the room you are standing in.

1. Open **Latter Studio &rarr; System &rarr; Room Calibration**.
2. Enable **Fast Refresh (1.5s)** in the top-right corner of the Site Survey card.
3. Walk into a room holding your **Pocket Assistant** or wearing your **Wrist Assist**.
4. Observe the live **Raw dBm**, **Offset dB**, **Effective dBm**, and **Estimated Distance** bars for each room.
5. If an adjacent room is winning over the room you are physically standing in, click **Prioritize Here** next to your current room (or use the `-1 dB` / `+1 dB` buttons). Latter automatically calculates and saves the global dB offset so that room wins reliably.

---

## Part 2: Roaming WireGuard VPN Provisioning

Want to carry your Pocket Assistant or Wrist Assist away from home (in the car, at work, or traveling) over a phone hotspot while keeping full Home Assistant, Assist, and Music control?

1. Open **Latter Studio &rarr; Device &rarr; Roaming &amp; VPN**.
2. Under **System WireGuard Endpoint**, enter your home WireGuard server's public hostname/IP:port (e.g., `vpn.example.com:51820`), Server Public Key, and tunnel subnet (`10.10.10.0/24`).
3. Under **Device Roaming Identity**, click **Generate WireGuard Keys**. Latter generates a fresh RFC 7748 Curve25519 keypair, preshared key, and unique client tunnel IP (`10.10.10.x`).
4. Copy **Box 1 (ESPHome WireGuard & Hotspot YAML)** into your device's ESPHome configuration (or use the 1-line `github://slampton/esphome-latter-core/mixins/roaming_vpn.yaml@main` mixin with your `secrets.yaml`).
5. Copy **Box 2 (WireGuard Server / HA Add-on Peer Config)** into your router (UniFi, OPNsense, pfSense) or the official Home Assistant WireGuard Add-on.
