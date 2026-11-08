"""Ask each bound Device to resend `latter.device_hello` once Latter's services exist.

After a Home Assistant restart a Device can reconnect and send `latter.device_hello` before Latter has
registered its services. That hello is lost, and Latter would wait for the next reconnect to learn the
Device's boot, manifest and health. Latter registers its services in `async_setup`; once the System
entry has created its Device coordinators, it calls each bound Device's `latter_ping` action, and the
firmware answers with a fresh `latter.device_hello`.

Standard library only, so it is unit-tested without Home Assistant (tests/test_device_ping.py).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

PING_ACTION = "latter_ping"


async def async_ping_bound_devices(
    esphome_device_ids: Iterable[str | None],
    resolve_service: Callable[[str, str], str | None],
    call_service: Callable[[str], Awaitable[None]],
    on_error: Callable[[str, Exception], None] | None = None,
) -> list[str]:
    """Call `latter_ping` on every bound Device whose ESPHome action is registered.

    `resolve_service(device_id, action)` returns the `esphome.<node>_<action>` service name, or None
    when the Device is offline (its own hello on reconnect then reaches the registered service).
    Returns the services that were called successfully. One failing Device never stops the others.
    """
    pinged: list[str] = []
    seen: set[str] = set()
    for dev_id in esphome_device_ids:
        if not dev_id or dev_id in seen:
            continue
        seen.add(dev_id)
        service = resolve_service(dev_id, PING_ACTION)
        if not service:
            continue
        try:
            await call_service(service)
        except Exception as err:  # noqa: BLE001 - a Device that drops mid-call must not stop the rest
            if on_error is not None:
                on_error(service, err)
            continue
        pinged.append(service)
    return pinged
