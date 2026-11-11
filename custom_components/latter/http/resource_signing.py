"""HMAC-SHA256 resource signatures for Latter's HTTP views.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.

Two expiry modes:

- Day-bucketed (`day_bucketed_expiry`): for URLs embedded in Protocol v3 payloads and Studio
  previews. Every signature minted during one UTC day is identical, so payload content hashes
  (and the device's image caches) stay stable. Lifetimes are whole days (48h default).
- Exact (`exact_expiry`): for URLs minted on demand and never embedded in a payload, such as the
  doorbell listen stream. Lifetimes are seconds (10 min default).
"""

from __future__ import annotations

import hashlib
import hmac

SIG_BUCKET_SECONDS: int = 86400
PAYLOAD_TTL_DAYS: int = 2
ON_DEMAND_TTL_SECONDS: int = 600
_MAC_HEX_CHARS: int = 32


def day_bucketed_expiry(now_s: int, ttl_days: int) -> int:
    """Return the first UTC midnight at least `ttl_days` days after `now_s` (valid for ttl_days to ttl_days + 1 days)."""
    if ttl_days < 1:
        raise ValueError("ttl_days must be >= 1")
    return (int(now_s) // SIG_BUCKET_SECONDS + ttl_days + 1) * SIG_BUCKET_SECONDS


def exact_expiry(now_s: int, ttl_s: int) -> int:
    """Return an expiry exactly `ttl_s` seconds after `now_s`."""
    if ttl_s < 1:
        raise ValueError("ttl_s must be >= 1")
    return int(now_s) + int(ttl_s)


def _mac(secret: bytes, scope: str, resource: str, exp: str) -> str:
    msg = f"{scope}|{resource}|{exp}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:_MAC_HEX_CHARS]


def sign(secret: bytes, scope: str, resource: str, exp: int) -> str:
    """Return the `<exp>.<mac>` signature binding `scope` (the Device's subentry ID or 'system'), `resource` and `exp`."""
    exp_s = str(int(exp))
    return f"{exp_s}.{_mac(secret, scope, resource, exp_s)}"


def verify(
    secret: bytes, scope: str, resource: str, sig: str | None, now_s: int
) -> bool:
    """Return True if `sig` is an unexpired signature for `scope` + `resource` (constant-time MAC compare)."""
    if not sig or "." not in sig:
        return False
    exp_s, mac = sig.split(".", 1)
    if not exp_s.isascii() or not exp_s.isdigit():
        return False
    if int(exp_s) < int(now_s):
        return False
    expected = _mac(secret, scope, resource, exp_s)
    return hmac.compare_digest(mac.encode("utf-8"), expected.encode("utf-8"))
