"""Pure-Python Async SIP User Agent, RTP G.711 (PCMU/PCMA) Bridge & RFC 2833 DTMF Engine for Latter."""

from __future__ import annotations

from array import array
import asyncio
from collections import deque
import hashlib
import logging
import random
import re
import socket
import struct
from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_SIP_DTMF_CODE,
    CONF_SIP_ENABLED,
    CONF_SIP_EXTENSION,
    CONF_SIP_PASSWORD,
    CONF_SIP_PORT,
    CONF_SIP_SERVER,
    CONF_SIP_SPEED_DIALS,
    CONF_SIP_USERNAME,
    DATA_GLOBAL_CONFIG,
    DEFAULT_SIP_DTMF_CODE,
    DEFAULT_SIP_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _decode_ulaw_byte(u_val: int) -> int:
    """Decode a single 8-bit ITU-T G.711 mu-law byte to signed 16-bit linear PCM."""
    u = (~u_val) & 0xFF
    t = (((u & 0x0F) << 3) + 0x84) << ((u & 0x70) >> 4)
    val = (0x84 - t) if (u & 0x80) else (t - 0x84)
    return max(-32768, min(32767, val))


_ULAW_TO_PCM16: tuple[int, ...] = tuple(_decode_ulaw_byte(b) for b in range(256))


def _pcm16_to_ulaw_byte(sample: int) -> int:
    """Encode a single signed 16-bit PCM sample into an 8-bit ITU-T G.711 mu-law byte."""
    sign = 0x80 if sample < 0 else 0
    if sample < 0:
        sample = -sample
    if sample > 32635:
        sample = 32635
    sample += 0x84
    exponent = 7
    exp_mask = 0x4000
    while exponent > 0 and not (sample & exp_mask):
        exponent -= 1
        exp_mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def decode_ulaw_to_pcm16_16khz(ulaw_bytes: bytes) -> array[int]:
    """Decode 8kHz G.711 PCMU bytes and upsample 2x to 16kHz signed 16-bit PCM."""
    out = array("h", [0] * (len(ulaw_bytes) * 2))
    idx = 0
    prev = 0
    for b in ulaw_bytes:
        cur = _ULAW_TO_PCM16[b]
        out[idx] = int((prev + cur) >> 1)
        out[idx + 1] = cur
        prev = cur
        idx += 2
    return out


def encode_pcm16_16khz_to_ulaw(pcm_16k: array[int]) -> bytes:
    """Downsample 16kHz signed 16-bit PCM to 8kHz and encode as G.711 PCMU bytes."""
    n_out = len(pcm_16k) // 2
    buf = bytearray(n_out)
    for i in range(n_out):
        s = pcm_16k[i * 2]
        buf[i] = _pcm16_to_ulaw_byte(int(s))
    return bytes(buf)


RFC2833_EVENT_MAP: dict[str, int] = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "*": 10, "#": 11, "A": 12, "B": 13, "C": 14, "D": 15,
}


def _get_local_ip() -> str:
    """Resolve the Home Assistant host's primary LAN IPv4 address for SIP Contact & SDP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.254.254.254", 1))
            return str(s.getsockname()[0])
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


class _RtpSessionProtocol(asyncio.DatagramProtocol):
    """Handles bidirectional RTP audio (PCMU/8000) and RFC 2833 DTMF for an active SIP call."""

    def __init__(self, sip_engine: LatterSipEngine) -> None:
        self.sip_engine = sip_engine
        self.transport: asyncio.DatagramTransport | None = None
        self.seq: int = random.randint(100, 10000)
        self.timestamp: int = random.randint(1000, 100000)
        self.ssrc: int = random.randint(100000, 0x7FFFFFFF)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) <= 12 or self.sip_engine.call_state != "in_call":
            return
        remote_ip = self.sip_engine.remote_rtp_addr[0]
        if (
            remote_ip
            and addr[0] != remote_ip
            and addr[0] not in self.sip_engine._allowed_sip_hosts
        ):
            return
        pt = data[1] & 0x7F
        if pt == 0:  # PCMU (G.711 mu-law 8kHz)
            payload = data[12:]
            pcm_16k = decode_ulaw_to_pcm16_16khz(payload)
            self.sip_engine.ingest_inbound_rtp_pcm16(pcm_16k)

    def send_rtp_packet(
        self, payload: bytes, payload_type: int, marker: bool, remote_addr: tuple[str, int], ts_step: int = 160
    ) -> None:
        if self.transport is None or not remote_addr[0] or remote_addr[1] <= 0:
            return
        self.seq = (self.seq + 1) & 0xFFFF
        m_pt = (0x80 if marker else 0x00) | (payload_type & 0x7F)
        header = struct.pack("!BBHII", 0x80, m_pt, self.seq, self.timestamp & 0xFFFFFFFF, self.ssrc)
        self.timestamp = (self.timestamp + ts_step) & 0xFFFFFFFF
        try:
            self.transport.sendto(header + payload, remote_addr)
        except Exception:  # noqa: BLE001
            pass


class _SipUdpProtocol(asyncio.DatagramProtocol):
    """Async UDP protocol handler for SIP signaling (RFC 3261)."""

    def __init__(self, engine: LatterSipEngine) -> None:
        self.engine = engine

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.engine._sip_transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            text = data.decode("utf-8", errors="ignore")
            self.engine.on_sip_datagram(text, addr)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("SIP datagram parse error from %s: %s", addr, err)


class LatterSipEngine:
    """Domain-level SIP User Agent & RTP Audio/DTMF Bridge for Latter."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the SIP engine."""
        self.hass = hass
        self._sip_transport: asyncio.DatagramTransport | None = None
        self._rtp_protocol: _RtpSessionProtocol | None = None
        self._reg_task: asyncio.Task[None] | None = None
        self._local_ip: str = _get_local_ip()
        self._local_sip_port: int = 5062
        self._local_rtp_port: int = 16400

        self.registered: bool = False
        self.call_state: str = "idle"
        self.active_call_id: str = ""
        self.remote_caller: str = ""
        self.remote_sip_addr: tuple[str, int] = ("", 0)
        self.remote_rtp_addr: tuple[str, int] = ("", 0)
        self._allowed_sip_hosts: set[str] = set()
        self._last_invite_headers: dict[str, str] = {}
        self._inbound_pcm_ring: deque[int] = deque(maxlen=64000)

    def get_cfg(self) -> dict[str, Any]:
        """Return current SIP configuration from global store."""
        gcfg = self.hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
        return {
            "enabled": bool(gcfg.get(CONF_SIP_ENABLED, False)),
            "server": str(gcfg.get(CONF_SIP_SERVER) or "").strip(),
            "port": int(gcfg.get(CONF_SIP_PORT) or DEFAULT_SIP_PORT),
            "username": str(gcfg.get(CONF_SIP_USERNAME) or "latter").strip(),
            "password": str(gcfg.get(CONF_SIP_PASSWORD) or "").strip(),
            "extension": str(gcfg.get(CONF_SIP_EXTENSION) or gcfg.get(CONF_SIP_USERNAME) or "101").strip(),
            "dtmf_code": str(gcfg.get(CONF_SIP_DTMF_CODE) or DEFAULT_SIP_DTMF_CODE).strip(),
            "speed_dials": str(gcfg.get(CONF_SIP_SPEED_DIALS) or "").strip(),
        }

    async def async_start_or_reload(self) -> None:
        """Start or reload the SIP UDP listener and PBX registration loop."""
        cfg = self.get_cfg()
        if not cfg["enabled"]:
            self.async_stop()
            return

        self._local_ip = _get_local_ip()
        loop = asyncio.get_running_loop()

        allowed_hosts: set[str] = set()
        if cfg["server"]:
            allowed_hosts.add(cfg["server"])
            try:
                infos = await loop.getaddrinfo(
                    cfg["server"], None, family=socket.AF_INET
                )
                for info in infos:
                    if info[4] and info[4][0]:
                        allowed_hosts.add(str(info[4][0]))
            except Exception:  # noqa: BLE001
                pass
        self._allowed_sip_hosts = allowed_hosts

        if self._sip_transport is None:
            for candidate_port in (5060, 5062, 5064):
                try:
                    await loop.create_datagram_endpoint(
                        lambda: _SipUdpProtocol(self),
                        local_addr=("0.0.0.0", candidate_port),
                    )
                    self._local_sip_port = candidate_port
                    _LOGGER.info(
                        "Latter SIP Engine listening on UDP %s:%d",
                        self._local_ip,
                        self._local_sip_port,
                    )
                    break
                except OSError:
                    continue

        if self._rtp_protocol is None:
            for r_port in (16400, 16402, 16404):
                try:
                    _tr, proto = await loop.create_datagram_endpoint(
                        lambda: _RtpSessionProtocol(self),
                        local_addr=("0.0.0.0", r_port),
                    )
                    self._rtp_protocol = proto  # type: ignore[assignment]
                    self._local_rtp_port = r_port
                    break
                except OSError:
                    continue

        if self._reg_task is not None:
            self._reg_task.cancel()
            self._reg_task = None

        if cfg["server"]:
            self._reg_task = self.hass.async_create_background_task(
                self._async_registration_loop(), "latter_sip_register"
            )
        else:
            self.registered = True

    @callback
    def async_stop(self) -> None:
        """Close SIP and RTP UDP sockets and cancel background registration."""
        if self._reg_task is not None:
            self._reg_task.cancel()
            self._reg_task = None
        if self._sip_transport is not None:
            self._sip_transport.close()
            self._sip_transport = None
        if self._rtp_protocol is not None and self._rtp_protocol.transport is not None:
            self._rtp_protocol.transport.close()
            self._rtp_protocol = None
        self.registered = False
        self.call_state = "idle"

    async def _async_registration_loop(self) -> None:
        """Periodically send SIP REGISTER to the configured PBX."""
        while True:
            try:
                cfg = self.get_cfg()
                if cfg["enabled"] and cfg["server"]:
                    self._send_register(cfg)
            except asyncio.CancelledError:
                break
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("SIP REGISTER loop error: %s", err)
            await asyncio.sleep(110)

    def _send_raw_sip(self, msg: str, addr: tuple[str, int]) -> None:
        if self._sip_transport is not None and addr[0] and addr[1] > 0:
            try:
                self._sip_transport.sendto(msg.encode("utf-8"), addr)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("SIP sendto %s failed: %s", addr, err)

    def _send_register(self, cfg: dict[str, Any], auth_header: str = "") -> None:
        server = cfg["server"]
        port = cfg["port"]
        user = cfg["username"]
        call_id = f"reg-{hashlib.md5(self._local_ip.encode()).hexdigest()[:12]}@{self._local_ip}"
        branch = f"z9hG4bK-{random.randint(100000, 999999)}"
        lines = [
            f"REGISTER sip:{server}:{port} SIP/2.0",
            f"Via: SIP/2.0/UDP {self._local_ip}:{self._local_sip_port};rport;branch={branch}",
            "Max-Forwards: 70",
            f"From: <sip:{user}@{server}>;tag=latter01",
            f"To: <sip:{user}@{server}>",
            f"Call-ID: {call_id}",
            f"CSeq: {2 if auth_header else 1} REGISTER",
            f"Contact: <sip:{user}@{self._local_ip}:{self._local_sip_port}>",
            "Expires: 300",
            "User-Agent: Latter-SIP/2.2",
        ]
        if auth_header:
            lines.append(auth_header)
        lines.append("Content-Length: 0\r\n\r\n")
        self._send_raw_sip("\r\n".join(lines), (server, port))

    def _build_digest_auth(self, www_auth: str, method: str, uri: str, user: str, password: str) -> str:
        realm_m = re.search(r'realm="([^"]+)"', www_auth)
        nonce_m = re.search(r'nonce="([^"]+)"', www_auth)
        if not realm_m or not nonce_m:
            return ""
        realm = realm_m.group(1)
        nonce = nonce_m.group(1)
        ha1 = hashlib.md5(f"{user}:{realm}:{password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        resp = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        hdr_name = "Proxy-Authorization" if "Proxy" in www_auth else "Authorization"
        return (
            f'{hdr_name}: Digest username="{user}", realm="{realm}", '
            f'nonce="{nonce}", uri="{uri}", response="{resp}", algorithm=MD5'
        )

    @callback
    def on_sip_datagram(self, text: str, addr: tuple[str, int]) -> None:
        """Process an incoming SIP request or response."""
        lines = text.split("\r\n")
        if not lines:
            return
        first = lines[0].strip()
        headers: dict[str, str] = {}
        body_start = text.find("\r\n\r\n")
        body = text[body_start + 4 :] if body_start != -1 else ""
        for ln in lines[1:]:
            if not ln:
                break
            if ":" in ln:
                k, v = ln.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        cfg = self.get_cfg()
        if not cfg["enabled"]:
            return
        if self._allowed_sip_hosts and addr[0] not in self._allowed_sip_hosts:
            return

        if first.startswith("SIP/2.0 200"):
            cseq = headers.get("cseq", "")
            if "REGISTER" in cseq:
                self.registered = True
            elif "INVITE" in cseq:
                self.call_state = "in_call"
                self._parse_sdp_and_set_remote_rtp(body, addr[0])
            return

        if first.startswith("SIP/2.0 401") or first.startswith("SIP/2.0 407"):
            www = headers.get("www-authenticate") or headers.get("proxy-authenticate") or ""
            if www and cfg["password"]:
                uri = f"sip:{cfg['server']}:{cfg['port']}"
                auth_hdr = self._build_digest_auth(
                    www, "REGISTER", uri, cfg["username"], cfg["password"]
                )
                if auth_hdr:
                    self._send_register(cfg, auth_header=auth_hdr)
            return

        if first.startswith("OPTIONS "):
            resp = [
                "SIP/2.0 200 OK",
                f"Via: {headers.get('via', '')}",
                f"From: {headers.get('from', '')}",
                f"To: {headers.get('to', '')};tag=latter",
                f"Call-ID: {headers.get('call-id', '')}",
                f"CSeq: {headers.get('cseq', '1 OPTIONS')}",
                "Content-Length: 0\r\n\r\n",
            ]
            self._send_raw_sip("\r\n".join(resp), addr)
            return

        if first.startswith("INVITE "):
            self._last_invite_headers = headers
            self.active_call_id = headers.get("call-id", "")
            self.remote_sip_addr = addr
            from_hdr = headers.get("from", "SIP Intercom")
            m_caller = re.search(r'"([^"]+)"', from_hdr) or re.search(r"<sip:([^@>]+)", from_hdr)
            self.remote_caller = m_caller.group(1) if m_caller else "Doorbell / SIP"
            self._parse_sdp_and_set_remote_rtp(body, addr[0])
            self.call_state = "ringing"

            ring_resp = [
                "SIP/2.0 180 Ringing",
                f"Via: {headers.get('via', '')}",
                f"From: {headers.get('from', '')}",
                f"To: {headers.get('to', '')};tag=lattercall",
                f"Call-ID: {self.active_call_id}",
                f"CSeq: {headers.get('cseq', '1 INVITE')}",
                f"Contact: <sip:{cfg['username']}@{self._local_ip}:{self._local_sip_port}>",
                "Content-Length: 0\r\n\r\n",
            ]
            self._send_raw_sip("\r\n".join(ring_resp), addr)
            self.hass.async_create_task(self._async_notify_incoming_sip_call())
            return

        if first.startswith("BYE ") or first.startswith("CANCEL "):
            ok_resp = [
                "SIP/2.0 200 OK",
                f"Via: {headers.get('via', '')}",
                f"From: {headers.get('from', '')}",
                f"To: {headers.get('to', '')}",
                f"Call-ID: {headers.get('call-id', '')}",
                f"CSeq: {headers.get('cseq', '')}",
                "Content-Length: 0\r\n\r\n",
            ]
            self._send_raw_sip("\r\n".join(ok_resp), addr)
            self.call_state = "idle"
            self.active_call_id = ""
            return

    def _parse_sdp_and_set_remote_rtp(self, sdp: str, fallback_ip: str) -> None:
        rtp_ip = fallback_ip
        rtp_port = 0
        for ln in sdp.splitlines():
            ln = ln.strip()
            if ln.startswith("c=IN IP4 "):
                rtp_ip = ln.split("c=IN IP4 ", 1)[1].split("/", 1)[0].strip()
            elif ln.startswith("m=audio "):
                parts = ln.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    rtp_port = int(parts[1])
        if rtp_port > 0:
            self.remote_rtp_addr = (rtp_ip, rtp_port)

    async def _async_notify_incoming_sip_call(self) -> None:
        """Wake Latter displays with an Incoming SIP Call notification & Answer button."""
        domain_data = self.hass.data.get(DOMAIN, {})
        for val in domain_data.values():
            if hasattr(val, "device_slug") and hasattr(val, "camera_entity"):
                await self.hass.services.async_call(
                    DOMAIN,
                    "notify_device",
                    {
                        "device_slug": val.device_slug,
                        "title": f"SIP Call: {self.remote_caller}",
                        "message": "Tap Answer for 2-Way Audio",
                        "priority": "critical",
                        "duration": 25,
                        "chime": True,
                        **({"camera_entity": val.camera_entity} if val.camera_entity else {}),
                    },
                    blocking=False,
                )

    def answer_incoming_call(self) -> bool:
        """Send SIP 200 OK with SDP to answer a ringing SIP call."""
        if not self._last_invite_headers or not self.remote_sip_addr[0]:
            return False
        cfg = self.get_cfg()
        hdrs = self._last_invite_headers
        sdp_body = (
            "v=0\r\n"
            f"o=latter 1 1 IN IP4 {self._local_ip}\r\n"
            "s=Latter SIP Audio\r\n"
            f"c=IN IP4 {self._local_ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {self._local_rtp_port} RTP/AVP 0 101\r\n"
            "a=rtpmap:0 PCMU/8000\r\n"
            "a=rtpmap:101 telephone-event/8000\r\n"
            "a=fmtp:101 0-15\r\n"
            "a=sendrecv\r\n"
        )
        resp = [
            "SIP/2.0 200 OK",
            f"Via: {hdrs.get('via', '')}",
            f"From: {hdrs.get('from', '')}",
            f"To: {hdrs.get('to', '')};tag=lattercall",
            f"Call-ID: {hdrs.get('call-id', '')}",
            f"CSeq: {hdrs.get('cseq', '1 INVITE')}",
            f"Contact: <sip:{cfg['username']}@{self._local_ip}:{self._local_sip_port}>",
            "Content-Type: application/sdp",
            f"Content-Length: {len(sdp_body)}\r\n",
            sdp_body,
        ]
        self._send_raw_sip("\r\n".join(resp), self.remote_sip_addr)
        self.call_state = "in_call"
        return True

    def hangup_call(self) -> None:
        """Send SIP BYE to terminate an active call."""
        if self.active_call_id and self.remote_sip_addr[0]:
            cfg = self.get_cfg()
            hdrs = self._last_invite_headers
            branch = f"z9hG4bK-{random.randint(100000, 999999)}"
            default_from = f"<sip:{cfg['username']}@{self._local_ip}>"
            from_uri = hdrs.get("to", default_from)
            bye_msg = [
                f"BYE sip:{self.remote_sip_addr[0]}:{self.remote_sip_addr[1]} SIP/2.0",
                f"Via: SIP/2.0/UDP {self._local_ip}:{self._local_sip_port};rport;branch={branch}",
                "Max-Forwards: 70",
                f"From: {from_uri};tag=lattercall",
                f"To: {hdrs.get('from', '')}",
                f"Call-ID: {self.active_call_id}",
                "CSeq: 102 BYE",
                "Content-Length: 0\r\n\r\n",
            ]
            self._send_raw_sip("\r\n".join(bye_msg), self.remote_sip_addr)
        self.call_state = "idle"
        self.active_call_id = ""

    def dial_sip_uri(self, target_uri: str) -> bool:
        """Initiate an outbound SIP INVITE call to a SIP extension or URI."""
        cfg = self.get_cfg()
        clean = target_uri.strip()
        if clean.startswith("sip:"):
            clean = clean[4:]
        if "@" in clean:
            user_part, host_part = clean.split("@", 1)
        else:
            user_part = clean
            host_part = f"{cfg['server']}:{cfg['port']}" if cfg["server"] else ""
        if not host_part:
            return False
        if ":" in host_part:
            host, port_s = host_part.rsplit(":", 1)
            port = int(port_s) if port_s.isdigit() else 5060
        else:
            host, port = host_part, cfg["port"] or 5060

        self.remote_sip_addr = (host, port)
        self.active_call_id = f"call-{random.randint(100000, 999999)}@{self._local_ip}"
        branch = f"z9hG4bK-{random.randint(100000, 999999)}"
        sdp_body = (
            "v=0\r\n"
            f"o=latter 1 1 IN IP4 {self._local_ip}\r\n"
            "s=Latter SIP Audio\r\n"
            f"c=IN IP4 {self._local_ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {self._local_rtp_port} RTP/AVP 0 101\r\n"
            "a=rtpmap:0 PCMU/8000\r\n"
            "a=rtpmap:101 telephone-event/8000\r\n"
            "a=fmtp:101 0-15\r\n"
            "a=sendrecv\r\n"
        )
        inv = [
            f"INVITE sip:{user_part}@{host}:{port} SIP/2.0",
            f"Via: SIP/2.0/UDP {self._local_ip}:{self._local_sip_port};rport;branch={branch}",
            "Max-Forwards: 70",
            f'From: "Latter" <sip:{cfg["username"]}@{self._local_ip}>;tag=latterout',
            f"To: <sip:{user_part}@{host}>",
            f"Call-ID: {self.active_call_id}",
            "CSeq: 1 INVITE",
            f"Contact: <sip:{cfg['username']}@{self._local_ip}:{self._local_sip_port}>",
            "Content-Type: application/sdp",
            f"Content-Length: {len(sdp_body)}\r\n",
            sdp_body,
        ]
        self._send_raw_sip("\r\n".join(inv), (host, port))
        self.call_state = "in_call"
        return True

    async def async_send_dtmf(self, digits: str | None = None) -> None:
        """Send RFC 2833 RTP telephone-event & SIP INFO DTMF digits to unlock a gate/door strike."""
        cfg = self.get_cfg()
        code = (digits or cfg["dtmf_code"] or DEFAULT_SIP_DTMF_CODE).strip()
        for ch in code:
            ev = RFC2833_EVENT_MAP.get(ch.upper())
            if ev is None:
                continue
            if self._rtp_protocol is not None and self.remote_rtp_addr[0]:
                for seq_i, end_bit in ((1, 0), (2, 0), (3, 0x80)):
                    dur = seq_i * 160
                    payload = struct.pack("!BBH", ev, end_bit | 10, dur)
                    self._rtp_protocol.send_rtp_packet(
                        payload, 101, seq_i == 1, self.remote_rtp_addr, ts_step=0 if seq_i < 3 else 480
                    )
            if self.remote_sip_addr[0] and self.active_call_id:
                body = f"Signal={ch}\r\nDuration=160\r\n"
                branch = f"z9hG4bK-{random.randint(100000, 999999)}"
                info_msg = [
                    f"INFO sip:{self.remote_sip_addr[0]}:{self.remote_sip_addr[1]} SIP/2.0",
                    f"Via: SIP/2.0/UDP {self._local_ip}:{self._local_sip_port};rport;branch={branch}",
                    f"From: <sip:{cfg['username']}@{self._local_ip}>;tag=lattercall",
                    f"To: <sip:{self.remote_sip_addr[0]}>",
                    f"Call-ID: {self.active_call_id}",
                    f"CSeq: {random.randint(10, 999)} INFO",
                    "Content-Type: application/dtmf-relay",
                    f"Content-Length: {len(body)}\r\n",
                    body,
                ]
                self._send_raw_sip("\r\n".join(info_msg), self.remote_sip_addr)
            await asyncio.sleep(0.18)

    def ingest_inbound_rtp_pcm16(self, pcm_16k: array[int]) -> None:
        """Buffer incoming 16kHz PCM samples from the remote SIP peer."""
        self._inbound_pcm_ring.extend(pcm_16k)

    async def async_stream_pcm16_to_rtp(self, pcm_16k: array[int]) -> None:
        """Encode 16kHz PCM audio into 20ms G.711 PCMU RTP frames and transmit to remote SIP peer."""
        if self._rtp_protocol is None or not self.remote_rtp_addr[0]:
            return
        ulaw_all = encode_pcm16_16khz_to_ulaw(pcm_16k)
        for idx in range(0, len(ulaw_all), 160):
            chunk = ulaw_all[idx : idx + 160]
            if len(chunk) < 160:
                chunk = chunk + (b"\xFF" * (160 - len(chunk)))
            self._rtp_protocol.send_rtp_packet(
                chunk, 0, idx == 0, self.remote_rtp_addr, ts_step=160
            )
            await asyncio.sleep(0.018)


def get_sip_engine(hass: HomeAssistant) -> LatterSipEngine:
    """Return or initialize the singleton LatterSipEngine."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "sip_engine" not in domain_data:
        domain_data["sip_engine"] = LatterSipEngine(hass)
    return domain_data["sip_engine"]