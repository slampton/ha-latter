"""Pure-stdlib shortcut icon/state policies and PBKDF2 / PIN session-key security (`L0b`)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import hashlib
import hmac
import math
import re
import secrets
import time
from typing import Any, Final

from .protocol_codec import V3Records, build_v3_records
from .protocol_specs import (
    MAX_PINNED_ITEMS,
    SHORTCUT_LABEL_MAX,
    normalize_activity_sources,
    normalize_mdi_icon,
)

# ---------------------------------------------------------------------------
# Universal Shortcut Engine, Home Dock & Activity Card Policies
# ---------------------------------------------------------------------------

_STATIC_DOMAIN_ICONS: Final[dict[str, str]] = {
    "light": "mdi:lightbulb",
    "fan": "mdi:fan",
    "valve": "mdi:pipe-valve",
    "scene": "mdi:palette",
    "script": "mdi:script-text-play",
    "automation": "mdi:robot",
    "button": "mdi:gesture-tap-button",
    "input_button": "mdi:gesture-tap-button",
    "alarm_control_panel": "mdi:shield-home",
    "vacuum": "mdi:robot-vacuum",
    "lawn_mower": "mdi:robot-mower",
    "climate": "mdi:thermostat",
    "humidifier": "mdi:air-humidifier",
    "siren": "mdi:bullhorn",
    "water_heater": "mdi:water-boiler",
    "select": "mdi:form-select",
    "input_select": "mdi:form-select",
}

_STATIC_COVER_CLASS_ICONS: Final[dict[str, str]] = {
    "gate": "mdi:gate",
    "curtain": "mdi:curtains",
    "blind": "mdi:blinds-horizontal",
    "shade": "mdi:blinds-horizontal",
    "shutter": "mdi:blinds-horizontal",
}

_STATELESS_SHORTCUT_DOMAINS: Final[frozenset[str]] = frozenset(
    {"scene", "button", "input_button", "select", "input_select"}
)

_ACTIVE_DOMAIN_STATES: Final[dict[str, frozenset[str]]] = {
    "cover": frozenset({"open", "opening"}),
    "valve": frozenset({"open", "opening"}),
    "lock": frozenset({"unlocked", "unlocking", "open", "opening"}),
    "vacuum": frozenset({"cleaning", "mowing", "returning"}),
    "lawn_mower": frozenset({"cleaning", "mowing", "returning"}),
    "media_player": frozenset({"playing", "buffering"}),
}


def _resolve_cover_shortcut_icon(dclass: str, st: str) -> str:
    if dclass == "garage":
        return "mdi:garage-open" if st in ("open", "opening") else "mdi:garage"
    if dclass == "door":
        return "mdi:door-open" if st in ("open", "opening") else "mdi:door-closed"
    return _STATIC_COVER_CLASS_ICONS.get(dclass, "mdi:window-shutter")


def resolve_shortcut_entity_icon(
    domain: str,
    *,
    device_class: str = "",
    entity_icon: str = "",
    state: str = "",
) -> str:
    """Return the canonical `mdi:<slug>` icon for an entity shortcut when no custom override is set."""
    explicit = normalize_mdi_icon(entity_icon, strict=False)
    if explicit:
        return explicit
    dom = str(domain or "").strip().lower()
    dclass = str(device_class or "").strip().lower()
    st = str(state or "").strip().lower()
    if dom in ("switch", "input_boolean"):
        return "mdi:power-plug" if dclass == "outlet" else "mdi:toggle-switch"
    if dom == "cover":
        return _resolve_cover_shortcut_icon(dclass, st)
    if dom == "lock":
        return (
            "mdi:lock-open"
            if st in ("unlocked", "unlocking", "open", "opening")
            else "mdi:lock"
        )
    if dom == "media_player":
        return "mdi:television" if dclass in ("tv", "receiver") else "mdi:speaker"
    return _STATIC_DOMAIN_ICONS.get(dom, "mdi:flash")


def _resolve_known_domain_live_state(dom: str, st: str) -> int:
    if dom in ("alarm_control_panel",):
        return 0 if st == "disarmed" else 1
    if dom in ("climate", "water_heater"):
        return 0 if st == "off" else 1
    active_set = _ACTIVE_DOMAIN_STATES.get(dom)
    if active_set is not None:
        return 1 if st in active_set else 0
    return 1 if st == "on" else 0


def resolve_shortcut_live_state(domain: str, raw_state: str | None) -> int:
    """Map an HA entity state to compact shortcut wire state (`-1` stateless, `0` off, `1` on, `2` unavailable)."""
    if raw_state is None:
        return 2
    st = str(raw_state).strip().lower()
    if st == "unavailable":
        return 2
    dom = str(domain or "").strip().lower()
    if dom in _STATELESS_SHORTCUT_DOMAINS:
        return -1
    if st in ("", "unknown"):
        return 0 if dom in ("script", "automation") else -1
    return _resolve_known_domain_live_state(dom, st)


def _coerce_shortcut_state(kind: str, raw_state: object) -> int:
    if (
        kind != "entity"
        or raw_state is None
        or isinstance(raw_state, bool)
        or not isinstance(raw_state, (int, float, str))
    ):
        return -1
    try:
        f_state = float(raw_state)
        state_val = int(f_state) if math.isfinite(f_state) else -1
    except (TypeError, ValueError, OverflowError):
        return -1
    return state_val if state_val in (-1, 0, 1, 2) else -1


def shortcut_records(
    items: Iterable[Mapping[str, Any]], *, max_records: int = MAX_PINNED_ITEMS
) -> V3Records:
    """Encode resolved shortcut items (`kind|target|action|label|icon|confirm|state`) into `V3Records`."""
    rows: list[tuple[object, ...]] = []
    for it in items:
        kind = str(it.get("kind") or "")
        target = str(it.get("target") or "")
        action = str(it.get("action") or "") if kind == "entity" else ""
        label = str(it.get("label") or "")
        icon = str(it.get("icon") or "")
        confirm = "1" if (kind == "entity" and bool(it.get("confirm"))) else "0"
        state_val = _coerce_shortcut_state(kind, it.get("state"))
        rows.append((kind, target, action, label, icon, confirm, str(state_val)))
    return build_v3_records(
        rows,
        (None, None, None, SHORTCUT_LABEL_MAX, None, 1, 2),
        max_records,
    )


def activity_payload(card_on: bool, sources: str) -> tuple[int, str]:
    """Return `(activity_card, activity_sources)` for Protocol v3."""
    clean = normalize_activity_sources(sources)
    return (1 if card_on and clean else 0), clean


# ---------------------------------------------------------------------------
# 3-Tier Perimeter Security Policy, PIN Session-Key Wrap & Brute-Force Lockout
# ---------------------------------------------------------------------------

SECURITY_PIN_POLICIES: Final[tuple[str, ...]] = (
    "auto",
    "allow",
    "require_pin",
    "block",
)
MIN_PIN_LEN: Final[int] = 4
MAX_PIN_LEN: Final[int] = 12
PIN_SESSION_KEY_BYTES: Final[int] = 32
PIN_WRAP_PREFIX: Final[str] = "v1:"
PBKDF2_ITERATIONS: Final[int] = 200_000
_HASH_SCHEME: Final[str] = "pbkdf2_sha256"
_SALT_BYTES: Final[int] = 16
_KEY_ID_HEX_LEN: Final[int] = 8
_NONCE_HEX_LEN: Final[int] = 8
_WIRE_MAC_HEX_LEN: Final[int] = 32
_ENVELOPE_PARTS: Final[int] = 5
_MAX_U32_NONCE: Final[int] = 0xFFFFFFFF
_HASH_PARTS_COUNT: Final[int] = 4
_MIN_PBKDF2_ITERS: Final[int] = 10_000
_MAX_PBKDF2_ITERS: Final[int] = 1_000_000
_MIN_SALT_BYTES: Final[int] = 8
_DK_BYTES: Final[int] = 32
_MAX_BACKOFF_EXP: Final[int] = 20

_LOWER_HEX_RE: Final = re.compile(r"^[0-9a-f]+$")
_GARAGE_COVER_CLASSES: Final[frozenset[str]] = frozenset({"garage", "gate", "door"})
_OPENING_COVER_ACTIONS: Final[frozenset[str]] = frozenset(
    {"turn_on", "open", "open_cover", "toggle", "set_level"}
)


class PinWrapError(ValueError):
    """Raised when a `v1:` session-key wrapped PIN fails format, key, replay, MAC, or digit validation."""

    def __init__(self, reason: str, message: str = "") -> None:
        """Initialize with machine-readable `reason` and human-readable `message`."""
        super().__init__(message or reason)
        self.reason = reason


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
    """Return True if `pin` is `MIN_PIN_LEN..MAX_PIN_LEN` (`4..12`) ASCII digits."""
    if not isinstance(pin, str):
        return False
    stripped = pin.strip()
    return (
        MIN_PIN_LEN <= len(stripped) <= MAX_PIN_LEN
        and stripped.isascii()
        and stripped.isdigit()
    )


def is_wrapped_pin_code(code: str | None) -> bool:
    """Return True if `code` carries the `v1:` PIN session-key envelope prefix."""
    return isinstance(code, str) and code.strip().startswith(PIN_WRAP_PREFIX)


def mint_pin_session_key() -> tuple[str, bytes]:
    """Mint a random 8-hex `key_id` and 32-byte HMAC-SHA256 session key for bound PIN transport."""
    return secrets.token_hex(4), secrets.token_bytes(PIN_SESSION_KEY_BYTES)


def _validate_pin_key_material(key_id: str, key_bytes: bytes) -> tuple[str, bytes]:
    kid = str(key_id or "").strip().lower()
    if len(kid) != _KEY_ID_HEX_LEN or not _LOWER_HEX_RE.fullmatch(kid):
        raise ValueError("PIN session key_id must be 8 lowercase hex characters")
    raw_key = bytes(key_bytes)
    if len(raw_key) != PIN_SESSION_KEY_BYTES:
        raise ValueError(
            f"PIN session key_bytes must be {PIN_SESSION_KEY_BYTES} bytes"
        )
    return kid, raw_key


def wrap_pin_code(
    key_id: str,
    key_bytes: bytes,
    nonce: int,
    entity_id: str,
    action: str,
    code: str,
) -> str:
    """Encrypt-then-MAC wrap a `4..12` digit PIN as `v1:<key_id>:<nonce_hex8>:<ct_hex>:<mac_hex32>`."""
    kid, raw_key = _validate_pin_key_material(key_id, key_bytes)
    nonce_int = int(nonce)
    if nonce_int < 1 or nonce_int > _MAX_U32_NONCE:
        raise ValueError("PIN session nonce must be in 1..0xFFFFFFFF")
    clean_code = str(code or "").strip()
    if not is_valid_pin_digits(clean_code):
        raise ValueError(
            f"PIN code must be {MIN_PIN_LEN} to {MAX_PIN_LEN} ASCII digits"
        )

    nonce_hex8 = f"{nonce_int:08x}"
    ent = str(entity_id or "").strip()
    act = str(action or "").strip()
    pt_bytes = clean_code.encode("ascii")
    keystream = hmac.new(
        raw_key,
        f"stream|{kid}|{nonce_hex8}".encode(),
        hashlib.sha256,
    ).digest()[: len(pt_bytes)]
    ct_hex = bytes(b ^ k for b, k in zip(pt_bytes, keystream, strict=True)).hex()
    mac_hex32 = hmac.new(
        raw_key,
        f"latter-pin-v1|{kid}|{nonce_hex8}|{ent}|{act}|{ct_hex}".encode(),
        hashlib.sha256,
    ).hexdigest()[:_WIRE_MAC_HEX_LEN]
    return f"v1:{kid}:{nonce_hex8}:{ct_hex}:{mac_hex32}"


def _parse_wrapped_pin_envelope(wrapped: str) -> tuple[str, str, str, str]:
    parts = str(wrapped or "").strip().split(":")
    if len(parts) != _ENVELOPE_PARTS or parts[0] != "v1":
        raise PinWrapError("malformed", "Invalid v1 PIN envelope format")
    wire_kid, nonce_hex8, ct_hex, wire_mac = parts[1], parts[2], parts[3], parts[4]
    valid_hex = (
        len(wire_kid) == _KEY_ID_HEX_LEN
        and len(nonce_hex8) == _NONCE_HEX_LEN
        and len(wire_mac) == _WIRE_MAC_HEX_LEN
        and len(ct_hex) % 2 == 0
        and (2 * MIN_PIN_LEN <= len(ct_hex) <= 2 * MAX_PIN_LEN)
        and bool(_LOWER_HEX_RE.fullmatch(wire_kid))
        and bool(_LOWER_HEX_RE.fullmatch(nonce_hex8))
        and bool(_LOWER_HEX_RE.fullmatch(ct_hex))
        and bool(_LOWER_HEX_RE.fullmatch(wire_mac))
    )
    if not valid_hex:
        raise PinWrapError("malformed", "Invalid hex field in v1 PIN envelope")
    return wire_kid, nonce_hex8, ct_hex, wire_mac


def unwrap_pin_code(
    key_id: str,
    key_bytes: bytes,
    last_nonce: int,
    entity_id: str,
    action: str,
    wrapped: str,
) -> tuple[str, int]:
    """Verify and decrypt a `v1:` wrapped PIN, returning `(plaintext_pin, nonce)`."""
    expected_kid, raw_key = _validate_pin_key_material(key_id, key_bytes)
    if int(last_nonce) < 0:
        raise ValueError("last_nonce must be >= 0")

    wire_kid, nonce_hex8, ct_hex, wire_mac = _parse_wrapped_pin_envelope(wrapped)
    if not hmac.compare_digest(wire_kid, expected_kid):
        raise PinWrapError("key_mismatch", "PIN session key_id mismatch")

    nonce_int = int(nonce_hex8, 16)
    if nonce_int < 1 or nonce_int <= int(last_nonce):
        raise PinWrapError("replay", "PIN session nonce replay or out-of-order")

    ent = str(entity_id or "").strip()
    act = str(action or "").strip()
    expected_mac = hmac.new(
        raw_key,
        f"latter-pin-v1|{expected_kid}|{nonce_hex8}|{ent}|{act}|{ct_hex}".encode(),
        hashlib.sha256,
    ).hexdigest()[:_WIRE_MAC_HEX_LEN]
    if not hmac.compare_digest(wire_mac, expected_mac):
        raise PinWrapError("bad_mac", "PIN session MAC verification failed")

    ct_bytes = bytes.fromhex(ct_hex)
    keystream = hmac.new(
        raw_key,
        f"stream|{expected_kid}|{nonce_hex8}".encode(),
        hashlib.sha256,
    ).digest()[: len(ct_bytes)]
    pt_bytes = bytes(c ^ k for c, k in zip(ct_bytes, keystream, strict=True))
    try:
        pin = pt_bytes.decode("ascii")
    except UnicodeDecodeError as err:
        raise PinWrapError("invalid_digits", "Decrypted PIN is non-ASCII") from err
    if not is_valid_pin_digits(pin):
        raise PinWrapError(
            "invalid_digits", "Decrypted PIN is not 4 to 12 ASCII digits"
        )
    return pin, nonce_int


class PinLockoutTracker:
    """Pure-stdlib exponential-backoff brute-force lockout tracker for PIN verification."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        base_cooldown_s: float = 60.0,
        max_cooldown_s: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize lockout thresholds and monotonic clock source."""
        self.max_failures: int = max(1, int(max_failures))
        self.base_cooldown_s: float = max(1.0, float(base_cooldown_s))
        self.max_cooldown_s: float = max(self.base_cooldown_s, float(max_cooldown_s))
        self._clock: Callable[[], float] = clock
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}

    def _now(self, now: float | None) -> float:
        return float(now) if now is not None else float(self._clock())

    def remaining_cooldown(
        self, scope: str = "global", *, now: float | None = None
    ) -> float:
        """Return seconds remaining in active lockout for `scope`, or `0.0` when unlocked."""
        key = str(scope or "global")
        until = self._locked_until.get(key, 0.0)
        if until <= 0.0:
            return 0.0
        rem = until - self._now(now)
        if rem <= 0.0:
            self._locked_until.pop(key, None)
            return 0.0
        return rem

    def is_locked_out(
        self, scope: str = "global", *, now: float | None = None
    ) -> bool:
        """Return True if `scope` is currently under an active brute-force cooldown."""
        return self.remaining_cooldown(scope, now=now) > 0.0

    def failure_count(self, scope: str = "global") -> int:
        """Return the consecutive failure count recorded for `scope`."""
        return self._failures.get(str(scope or "global"), 0)

    def record_failure(
        self, scope: str = "global", *, now: float | None = None
    ) -> float:
        """Record a failed PIN attempt for `scope` and return any newly applied cooldown in seconds."""
        key = str(scope or "global")
        t = self._now(now)
        count = self._failures.get(key, 0) + 1
        self._failures[key] = count
        if count < self.max_failures:
            return 0.0
        exponent = min(count - self.max_failures, _MAX_BACKOFF_EXP)
        cooldown = min(self.max_cooldown_s, self.base_cooldown_s * (2**exponent))
        self._locked_until[key] = max(self._locked_until.get(key, 0.0), t + cooldown)
        return self._locked_until[key] - t

    def record_success(self, scope: str = "global") -> None:
        """Clear consecutive failures and cooldown for `scope` after a valid PIN."""
        key = str(scope or "global")
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)

    def reset(self, scope: str | None = None) -> None:
        """Clear lockout state for `scope`, or all scopes when `scope` is None."""
        if scope is None:
            self._failures.clear()
            self._locked_until.clear()
            return
        self.record_success(scope)


def hash_security_pin(pin: str) -> str:
    """Hash a 4-12 digit PIN with PBKDF2-HMAC-SHA256 and a random 128-bit salt."""
    cleaned = str(pin or "").strip()
    if not is_valid_pin_digits(cleaned):
        raise ValueError(
            f"Security PIN must be {MIN_PIN_LEN} to {MAX_PIN_LEN} digits"
        )
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
    if (
        not is_valid_pin_digits(pin)
        or not stored_hash
        or not isinstance(stored_hash, str)
    ):
        return False
    parts = stored_hash.strip().split("$")
    if len(parts) != _HASH_PARTS_COUNT or parts[0] != _HASH_SCHEME:
        return False
    try:
        iters = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_dk = bytes.fromhex(parts[3])
    except ValueError:
        return False
    if (
        not (_MIN_PBKDF2_ITERS <= iters <= _MAX_PBKDF2_ITERS)
        or len(salt) < _MIN_SALT_BYTES
        or len(expected_dk) != _DK_BYTES
    ):
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
    """Check whether a sensitive perimeter action is permitted under `policy`."""
    norm = policy if policy in ("allow", "require_pin", "block") else "require_pin"
    if norm == "allow":
        return True, ""
    if norm == "block":
        return False, "security_action_blocked"

    code = str(provided_code or "").strip()
    if not code:
        return False, "security_pin_required"
    if stored_pin_hash:
        return (True, "") if verify_security_pin(code, stored_pin_hash) else (False, "security_pin_invalid")
    if alarm_accepts_passthrough_code and is_valid_pin_digits(code):
        return True, ""
    return False, "security_pin_not_configured"
