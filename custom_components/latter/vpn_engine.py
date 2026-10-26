"""WireGuard Curve25519 Keypair Generator & Roaming ESPHome Provisioning Engine for Latter."""

from __future__ import annotations

import base64
import ipaddress
import secrets
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519


def generate_wireguard_keypair() -> dict[str, str]:
    """Generate a standard RFC 7748 Curve25519 WireGuard private/public keypair and preshared key (base64)."""
    priv = x25519.X25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    psk_bytes = secrets.token_bytes(32)
    return {
        "private_key": base64.b64encode(priv_bytes).decode("ascii"),
        "public_key": base64.b64encode(pub_bytes).decode("ascii"),
        "preshared_key": base64.b64encode(psk_bytes).decode("ascii"),
    }


def allocate_next_tunnel_ip(
    subnet_cidr: str, used_ips: list[str]
) -> tuple[str, str]:
    """Return (server_tunnel_ip, next_available_client_ip) from a subnet like '10.10.10.0/24'."""
    try:
        net = ipaddress.ip_network(subnet_cidr or "10.10.10.0/24", strict=False)
    except ValueError:
        net = ipaddress.ip_network("10.10.10.0/24", strict=False)

    hosts = list(net.hosts())
    if len(hosts) < 3:
        return "10.10.10.1", "10.10.10.2"

    server_ip = str(hosts[0])
    used_set = {ip.split("/", 1)[0].strip() for ip in used_ips if ip}
    used_set.add(server_ip)

    for candidate in hosts[1:]:
        cand_str = str(candidate)
        if cand_str not in used_set:
            return server_ip, cand_str

    return server_ip, str(hosts[-1])


def build_wireguard_provisioning_snippets(
    device_slug: str,
    device_vpn: dict[str, Any],
    global_vpn: dict[str, Any],
) -> dict[str, str]:
    """Build copy-pasteable ESPHome YAML and WireGuard Server Peer snippets for a roaming device."""
    endpoint_raw = str(global_vpn.get("vpn_endpoint") or "vpn.example.com:51820").strip()
    if ":" in endpoint_raw:
        host, port_str = endpoint_raw.rsplit(":", 1)
        port = int(port_str) if port_str.isdigit() else 51820
    else:
        host, port = endpoint_raw, 51820

    server_pub = str(global_vpn.get("vpn_server_public_key") or "<YOUR_WG_SERVER_PUBLIC_KEY>").strip()
    subnet_raw = str(global_vpn.get("vpn_subnet") or "10.10.10.0/24").strip()
    try:
        net = ipaddress.ip_network(subnet_raw, strict=False)
        netmask_str = str(net.netmask)
    except ValueError:
        netmask_str = "255.255.255.0"

    client_ip = str(device_vpn.get("vpn_client_ip") or "10.10.10.2").strip()
    client_priv = str(device_vpn.get("vpn_private_key") or "<CLICK_GENERATE_KEYS>").strip()
    client_pub = str(device_vpn.get("vpn_public_key") or "<CLICK_GENERATE_KEYS>").strip()
    psk = str(device_vpn.get("vpn_preshared_key") or "").strip()
    hotspot_ssid = str(device_vpn.get("vpn_hotspot_ssid") or "!secret hotspot_ssid").strip()
    hotspot_psk = str(device_vpn.get("vpn_hotspot_password") or "!secret hotspot_password").strip()

    esphome_lines = [
        f"# === OPTION A: 1-Line Drop-In Mixin Package for '{device_slug}' (Recommended) ===",
        "# 1. Add this single line under packages: in your device's ESPHome YAML:",
        "packages:",
        "  latter.vpn: github://slampton/esphome-latter-core/mixins/roaming_vpn.yaml@main",
        "",
        "# 2. Paste these 4 lines into your ESPHome secrets.yaml:",
        f"# latter_vpn_private_key: \"{client_priv}\"",
        f"# latter_vpn_endpoint: \"{host}\"",
        f"# latter_vpn_server_public_key: \"{server_pub}\"",
        f"# latter_vpn_preshared_key: \"{psk}\"",
        "",
        f"# === OPTION B: Full Inline WireGuard & Multi-Wi-Fi YAML for '{device_slug}' ===",
        "wifi:",
        "  networks:",
        "    - ssid: !secret wifi_ssid",
        "      password: !secret wifi_password",
        "      priority: 10",
        f"    - ssid: \"{hotspot_ssid}\"",
        f"      password: \"{hotspot_psk}\"",
        "      priority: 5",
        "",
        "# 2. Native ESP32-S3 WireGuard Tunnel (LwIP esp_wireguard + api: outgoing_connection:)",
        "wireguard:",
        "  id: wg_roaming",
        f"  address: {client_ip}",
        f"  netmask: {netmask_str}",
        f"  private_key: \"{client_priv}\"",
        f"  peer_endpoint: \"{host}\"",
        f"  peer_port: {port}",
        f"  peer_public_key: \"{server_pub}\"",
    ]
    if psk:
        esphome_lines.append(f"  peer_preshared_key: \"{psk}\"")
    esphome_lines.extend(
        [
            "  peer_persistent_keepalive: 25s",
            "  allowed_ips:",
            f"    - {subnet_raw}",
        ]
    )

    server_peer_lines = [
        f"# WireGuard Server / HA WireGuard Add-on Peer Entry for '{device_slug}'",
        "[Peer]",
        f"# Friendly Name: {device_slug}",
        f"PublicKey = {client_pub}",
    ]
    if psk:
        server_peer_lines.append(f"PresharedKey = {psk}")
    server_peer_lines.append(f"AllowedIPs = {client_ip}/32")

    addon_yaml_lines = [
        f"# Home Assistant Official WireGuard Add-on peers: YAML snippet for '{device_slug}'",
        f"- name: {device_slug}",
        "  addresses:",
        f"    - {client_ip}",
        "  allowed_ips: []",
        "  client_allowed_ips:",
        f"    - {subnet_raw}",
    ]

    return {
        "esphome_yaml": "\n".join(esphome_lines),
        "server_peer_conf": "\n".join(server_peer_lines),
        "ha_addon_yaml": "\n".join(addon_yaml_lines),
    }