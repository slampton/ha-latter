"""Repair issue IDs raised per Latter Device.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
Every per-Device issue ID is built here, so removing a Device can delete all of them.
"""

from __future__ import annotations


def link_ma_player_issue_id(subentry_id: str) -> str:
    """Issue: the Device's speaker has no Music Assistant counterpart."""
    return f"link_ma_player_{subentry_id}"


def missing_mapped_entity_issue_id(subentry_id: str) -> str:
    """Issue: an entity mapped for the Device no longer exists."""
    return f"missing_mapped_entity_{subentry_id}"


def ble_no_proxies_issue_id(subentry_id: str) -> str:
    """Issue: BLE Area tracking is on but no Area-assigned Bluetooth proxy exists."""
    return f"ble_no_proxies_{subentry_id}"


def slot_push_failing_issue_id(subentry_id: str) -> str:
    """Issue: pushing browse/Area slots to the Device keeps failing."""
    return f"slot_push_failing_{subentry_id}"


def device_health_issue_id(kind: str, subentry_id: str) -> str:
    """Issue: a device health problem (device_crashed, device_brownout, firmware_rolled_back)."""
    return f"{kind}_{subentry_id}"


DEVICE_HEALTH_ISSUE_KINDS: tuple[str, ...] = (
    "device_crashed",
    "device_brownout",
    "firmware_rolled_back",
)


def device_issue_ids(subentry_id: str) -> list[str]:
    """Return every repair issue ID that can exist for one Device."""
    return [
        link_ma_player_issue_id(subentry_id),
        missing_mapped_entity_issue_id(subentry_id),
        ble_no_proxies_issue_id(subentry_id),
        slot_push_failing_issue_id(subentry_id),
        *(device_health_issue_id(kind, subentry_id) for kind in DEVICE_HEALTH_ISSUE_KINDS),
    ]


# Every per-Device issue kind; the issue ID is f"{kind}_{subentry_id}" for each of them.
DEVICE_ISSUE_KINDS: tuple[str, ...] = (
    "link_ma_player",
    "missing_mapped_entity",
    "ble_no_proxies",
    "slot_push_failing",
    *DEVICE_HEALTH_ISSUE_KINDS,
)


def parse_device_issue_id(issue_id: str, subentry_ids: set[str]) -> tuple[str, str] | None:
    """Return (kind, subentry_id) for a per-Device issue of a known Device, else None."""
    for kind in DEVICE_ISSUE_KINDS:
        prefix = f"{kind}_"
        if issue_id.startswith(prefix) and issue_id[len(prefix):] in subentry_ids:
            return kind, issue_id[len(prefix):]
    return None
