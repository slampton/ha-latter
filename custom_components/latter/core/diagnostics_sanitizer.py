"""Pure standard-library diagnostics redaction and PII sanitizer for Latter."""

from __future__ import annotations

import hashlib
import re
from typing import Any

REDACTED = "**REDACTED**"

REDACTED_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "alert_camera_url",
        "art_url",
        "ble_beacon_uuid",
        "ble_target_address",
        "hmac_secret_hex",
        "mac",
        "payload",
        "security_pin",
        "security_pin_hash",
        "system_ble_uuid",
        "wallpaper_url",
    }
)

_MAC_KEY_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_SIG_QUERY_RE = re.compile(r"([?&])sig=[^&#\s\"']+")


def _redact_string(val: str) -> str:
    """Strip resource HMAC signatures from URL strings while keeping path/shape structure."""
    if "sig=" in val:
        return _SIG_QUERY_RE.sub(rf"\1sig={REDACTED}", val)
    return val


def _redact_mac_dict_key(key: str) -> str:
    """Replace raw MAC address dictionary keys with a deterministic non-reversible short digest."""
    if _MAC_KEY_RE.match(key):
        norm = key.replace("-", ":").upper()
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]
        return f"mac_{digest}"
    return key


def sanitize_diagnostics_payload(obj: Any, *, parent_key: str = "") -> Any:
    """Recursively strip HMAC signatures, v3 payloads, MAC keys, PINs, and calendar PII from diagnostics."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for raw_k, raw_v in obj.items():
            k_str = str(raw_k)
            if k_str in REDACTED_FIELD_KEYS:
                out[k_str] = REDACTED
                continue
            safe_k = _redact_mac_dict_key(k_str)
            if parent_key == "calendar_agenda" and k_str == "records" and isinstance(raw_v, list):
                sanitized_records: list[Any] = []
                for rec in raw_v:
                    if isinstance(rec, (list, tuple)) and len(rec) >= 4:
                        sanitized_records.append([str(rec[0]), REDACTED, REDACTED, str(rec[3])])
                    else:
                        sanitized_records.append(REDACTED)
                out[safe_k] = sanitized_records
                continue
            out[safe_k] = sanitize_diagnostics_payload(raw_v, parent_key=k_str)
        return out
    if isinstance(obj, (list, tuple)):
        return [sanitize_diagnostics_payload(item, parent_key=parent_key) for item in obj]
    if isinstance(obj, str):
        return _redact_string(obj)
    return obj
