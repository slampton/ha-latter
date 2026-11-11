"""3-tier Perimeter Security Policy and PBKDF2-HMAC-SHA256 PIN verification for Latter.

Standard library only (no Home Assistant imports), so standalone unit tests exercise this exact code.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

SECURITY_PIN_POLICIES: tuple[str, ...] = ("auto", "allow", "require_pin", "block")
PBKDF2_ITERATIONS: int = 200_000
_HASH_SCHEME: str = "pbkdf2_sha256"
_SALT_BYTES: int = 16

_GARAGE_COVER_CLASSES: frozenset[str] = frozenset({"garage", "gate", "door"})
_OPENING_COVER_ACTIONS: frozenset[str] = frozenset(
    {"turn_on", "open", "open_cover", "toggle", "set_level"}
)


def normalize_security_pin_policy(value: str | None) -> str:
    """Return a valid security PIN policy (`auto`, `allow`, `require_pin`, `block`), else `auto`."""
    cleaned = str(value or "").strip().lower()
    return cleaned if cleaned in SECURITY_PIN_POLICIES else "auto"


def effective_security_pin_policy(
    configured_policy: str | None,
    *,
    is_roaming: bool,
    alarm_has_code: bool,
) -> str:
    """Resolve `auto` to `require_pin` on stationary displays or when an alarm code is active."""
    norm = normalize_security_pin_policy(configured_policy)
    if norm in ("allow", "require_pin", "block"):
        return norm
    if (not is_roaming) or alarm_has_code:
        return "require_pin"
    return "allow"


def is_valid_pin_digits(pin: str | None) -> bool:
    """Return True if `pin` is 4 to 12 ASCII digits."""
    if not isinstance(pin, str):
        return False
    stripped = pin.strip()
    return 4 <= len(stripped) <= 12 and stripped.isascii() and stripped.isdigit()


def hash_security_pin(pin: str) -> str:
    """Hash a 4-12 digit PIN with PBKDF2-HMAC-SHA256 and a random 128-bit salt."""
    cleaned = str(pin or "").strip()
    if not is_valid_pin_digits(cleaned):
        raise ValueError("Security PIN must be 4 to 12 digits")
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        cleaned.encode("ascii"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{_HASH_SCHEME}${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_security_pin(pin: str | None, stored_hash: str | None) -> bool:
    """Verify `pin` against `stored_hash` in constant time."""
    if not is_valid_pin_digits(pin) or not stored_hash or not isinstance(stored_hash, str):
        return False
    parts = stored_hash.strip().split("$")
    if len(parts) != 4 or parts[0] != _HASH_SCHEME:
        return False
    try:
        iters = int(parts[1])
        if iters < 10_000 or iters > 1_000_000:
            return False
        salt = bytes.fromhex(parts[2])
        expected_dk = bytes.fromhex(parts[3])
    except ValueError:
        return False
    if len(salt) < 8 or len(expected_dk) != 32:
        return False
    candidate_dk = hashlib.pbkdf2_hmac(
        "sha256",
        str(pin).strip().encode("ascii"),
        salt,
        iters,
    )
    return hmac.compare_digest(candidate_dk, expected_dk)


def is_sensitive_perimeter_action(
    domain: str,
    action: str,
    *,
    device_class: str = "",
    entity_id: str = "",
    level: int | None = None,
) -> bool:
    """Return True only for perimeter-opening actions; closing/arming actions are always allowed."""
    dom = str(domain or "").strip().lower()
    act = str(action or "").strip().lower()
    if dom == "lock":
        return act in ("unlock", "open")
    if dom == "doorbell":
        return act == "unlock_door"
    if dom == "alarm_control_panel":
        return act == "disarm"
    if dom == "cover":
        dclass = str(device_class or "").strip().lower()
        ent_low = str(entity_id or "").strip().lower()
        is_perimeter_cover = dclass in _GARAGE_COVER_CLASSES or any(
            tok in ent_low for tok in ("garage", "gate")
        )
        if not is_perimeter_cover or act not in _OPENING_COVER_ACTIONS:
            return False
        return not (act == "set_level" and level is not None and int(level) <= 0)
    return False


def check_perimeter_action_allowed(
    policy: str,
    *,
    provided_code: str | None,
    stored_pin_hash: str | None,
    alarm_accepts_passthrough_code: bool = False,
) -> tuple[bool, str]:
    """Check whether a sensitive perimeter action is permitted under `policy`.

    Returns `(allowed, error_translation_key)`.
    """
    norm = policy if policy in ("allow", "require_pin", "block") else "require_pin"
    if norm == "allow":
        return True, ""
    if norm == "block":
        return False, "security_action_blocked"

    code = str(provided_code or "").strip()
    if not code:
        return False, "security_pin_required"
    if stored_pin_hash:
        if verify_security_pin(code, stored_pin_hash):
            return True, ""
        return False, "security_pin_invalid"
    if alarm_accepts_passthrough_code and is_valid_pin_digits(code):
        return True, ""
    return False, "security_pin_not_configured"
