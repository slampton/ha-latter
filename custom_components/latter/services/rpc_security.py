"""PIN session-key unwrapping, exponential lockout, and unified Perimeter Security Policy (`M-P0-01`, `M-P2-24`)."""

from __future__ import annotations

from typing import NoReturn

from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError

from ..const import DOMAIN
from ..coordinator import LatterCoordinator
from ..hub_registry import get_latter_system
from ..protocol_policy import (
    PinLockoutTracker,
    PinWrapError,
    check_perimeter_action_allowed,
    is_sensitive_perimeter_action,
    is_valid_pin_digits,
    is_wrapped_pin_code,
    unwrap_pin_code,
)

_ALARM_ACTION_ALIASES: dict[str, str] = {
    "disarm": "disarm",
    "alarm_disarm": "disarm",
    "arm_home": "arm_home",
    "alarm_arm_home": "arm_home",
    "arm_away": "arm_away",
    "alarm_arm_away": "arm_away",
    "arm_night": "arm_night",
    "alarm_arm_night": "arm_night",
    "arm_vacation": "arm_vacation",
    "alarm_arm_vacation": "arm_vacation",
}

_ALARM_ARM_VERBS: frozenset[str] = frozenset(
    {"arm_home", "arm_away", "arm_night", "arm_vacation"}
)
_ALL_ALARM_VERBS: frozenset[str] = _ALARM_ARM_VERBS | {"disarm"}


def _get_system_pin_lockout(hass: HomeAssistant) -> PinLockoutTracker:
    """Return the System-wide `PinLockoutTracker` singleton."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        return sys_obj.pin_lockout
    domain_data = hass.data.setdefault(DOMAIN, {})
    tracker = domain_data.get("_pin_lockout")
    if not isinstance(tracker, PinLockoutTracker):
        tracker = PinLockoutTracker()
        domain_data["_pin_lockout"] = tracker
    return tracker


def _check_pin_not_locked_out(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    *,
    now_m: float | None = None,
) -> None:
    """Raise `security_pin_locked_out` when either the Device or System lockout cooldown is active."""
    sys_lockout = _get_system_pin_lockout(hass)
    if coord.pin_lockout.is_locked_out(
        coord.subentry_id, now=now_m
    ) or sys_lockout.is_locked_out("system", now=now_m):
        raise ServiceValidationError(
            "Too many failed security PIN attempts; temporarily locked out.",
            translation_domain=DOMAIN,
            translation_key="security_pin_locked_out",
        )


def _record_pin_failure_and_raise(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    err_key: str,
    detail: str,
    *,
    now_m: float | None = None,
) -> NoReturn:
    """Record a failed PIN attempt on Device + System trackers and raise the validation error."""
    dev_rem = coord.pin_lockout.record_failure(coord.subentry_id, now=now_m)
    sys_rem = _get_system_pin_lockout(hass).record_failure("system", now=now_m)
    final_key = (
        "security_pin_locked_out" if (dev_rem > 0.0 or sys_rem > 0.0) else err_key
    )
    raise ServiceValidationError(
        detail,
        translation_domain=DOMAIN,
        translation_key=final_key,
    )


def _record_pin_success(hass: HomeAssistant, coord: LatterCoordinator) -> None:
    """Clear failure streaks on the calling Device and System lockout trackers after valid PIN verification."""
    coord.pin_lockout.record_success(coord.subentry_id)
    _get_system_pin_lockout(hass).record_success("system")


def unwrap_rpc_pin_code(
    coord: LatterCoordinator,
    raw_entity_id: str,
    raw_action: str,
    raw_code: object,
    *,
    now_m: float | None = None,
) -> str | None:
    """Unwrap an authenticated `v1:...` RPC PIN envelope, rejecting plaintext or replayed PINs (`M-P0-01`)."""
    hass = coord.hass
    code_str = str(raw_code or "").strip()
    if not code_str:
        return None
    _check_pin_not_locked_out(hass, coord, now_m=now_m)
    key_id = coord.pin_session_key_id
    key_bytes = coord.pin_session_key_bytes
    if not is_wrapped_pin_code(code_str) or not key_id or not key_bytes:
        _record_pin_failure_and_raise(
            hass,
            coord,
            "security_pin_invalid",
            f"Rejected unwrapped or unprovisioned security PIN from '{coord.device_slug}'.",
            now_m=now_m,
        )
    try:
        pin_digits, nonce = unwrap_pin_code(
            key_id,
            key_bytes,
            coord.pin_last_nonce,
            raw_entity_id.strip(),
            raw_action.strip(),
            code_str,
        )
    except PinWrapError as err:
        _record_pin_failure_and_raise(
            hass,
            coord,
            "security_pin_invalid",
            f"Rejected wrapped security PIN from '{coord.device_slug}' ({err.reason}): {err}",
            now_m=now_m,
        )
    coord.record_pin_nonce(nonce)
    return pin_digits


def _validate_native_alarm_code_format(
    coord: LatterCoordinator,
    resolved_ent: str,
    act: str,
    code_fmt: str,
    clean_code: str,
) -> None:
    """Validate required native `alarm_control_panel` code format before HA passthrough."""
    hass = coord.hass
    _check_pin_not_locked_out(hass, coord)
    if not clean_code:
        raise ServiceValidationError(
            f"Alarm PIN required for '{act}' on '{resolved_ent}'.",
            translation_domain=DOMAIN,
            translation_key="security_pin_required",
        )
    if code_fmt == "number" and not is_valid_pin_digits(clean_code):
        _record_pin_failure_and_raise(
            hass,
            coord,
            "security_pin_invalid",
            f"Invalid alarm PIN format for '{act}' on '{resolved_ent}'.",
        )


async def _async_verify_stored_policy_pin(
    coord: LatterCoordinator,
    resolved_ent: str,
    act: str,
    eff_policy: str,
    provided_code: str | None,
) -> None:
    """Verify `provided_code` against `coord.security_pin_hash` under `eff_policy` in one shared helper."""
    hass = coord.hass
    if eff_policy != "block":
        _check_pin_not_locked_out(hass, coord)
    stored_hash = coord.security_pin_hash or None
    allowed, err_key = await hass.async_add_executor_job(
        lambda: check_perimeter_action_allowed(
            eff_policy,
            provided_code=provided_code,
            stored_pin_hash=stored_hash,
        )
    )
    if not allowed:
        if err_key == "security_pin_invalid":
            _record_pin_failure_and_raise(
                hass,
                coord,
                err_key,
                f"Perimeter action '{act}' on '{resolved_ent}' denied ({err_key}).",
            )
        raise ServiceValidationError(
            f"Perimeter action '{act}' on '{resolved_ent}' denied ({err_key}).",
            translation_domain=DOMAIN,
            translation_key=err_key,
        )
    if str(provided_code or "").strip() and stored_hash:
        _record_pin_success(hass, coord)


async def _async_enforce_alarm_panel_policy(
    coord: LatterCoordinator,
    resolved_ent: str,
    act: str,
    st: State | None,
    provided_code: str | None,
) -> None:
    """Enforce `alarm_control_panel` disarm/arm PIN rules and native `code_format` passthrough."""
    eff_policy = coord.security_pin_policy
    code_fmt = (
        str(st.attributes.get("code_format") or "").strip().lower()
        if st is not None
        else ""
    )
    code_arm_req = (
        bool(st.attributes.get("code_arm_required", False)) if st is not None else False
    )
    clean_code = str(provided_code or "").strip()

    if act == "disarm":
        if eff_policy == "block":
            raise ServiceValidationError(
                f"Perimeter action '{act}' on '{resolved_ent}' denied (security_action_blocked).",
                translation_domain=DOMAIN,
                translation_key="security_action_blocked",
            )
        if code_fmt:
            _validate_native_alarm_code_format(
                coord, resolved_ent, act, code_fmt, clean_code
            )
            return
        await _async_verify_stored_policy_pin(
            coord, resolved_ent, act, eff_policy, provided_code
        )
        return

    if act in _ALARM_ARM_VERBS and code_fmt and code_arm_req:
        _validate_native_alarm_code_format(
            coord, resolved_ent, act, code_fmt, clean_code
        )


async def async_enforce_perimeter_security_policy(
    coord: LatterCoordinator,
    entity_id: str,
    action: str,
    *,
    level: int | float | None = None,
    provided_code: str | None = None,
) -> None:
    """Enforce the Device's Perimeter Security Policy and PIN lockout on sensitive opening actions."""
    hass = coord.hass
    raw_act = action.strip().lower()
    act = _ALARM_ACTION_ALIASES.get(raw_act, raw_act)
    resolved_ent = entity_id.strip()
    if resolved_ent == "home_hub.alarm" or (
        not resolved_ent and act in _ALL_ALARM_VERBS
    ):
        resolved_ent = coord.alarm_entity or ""
    if not resolved_ent or "." not in resolved_ent:
        return

    dom = resolved_ent.split(".", 1)[0].lower()
    st = hass.states.get(resolved_ent)

    if dom == "alarm_control_panel":
        await _async_enforce_alarm_panel_policy(
            coord, resolved_ent, act, st, provided_code
        )
        return

    dclass = str(st.attributes.get("device_class") or "") if st is not None else ""
    if not is_sensitive_perimeter_action(
        dom,
        act,
        device_class=dclass,
        entity_id=resolved_ent,
        level=int(level) if level is not None else None,
    ):
        return

    await _async_verify_stored_policy_pin(
        coord, resolved_ent, act, coord.security_pin_policy, provided_code
    )


_unwrap_rpc_pin_code = unwrap_rpc_pin_code
_async_enforce_perimeter_security_policy = async_enforce_perimeter_security_policy
