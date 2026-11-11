"""Home dock: validation of a Device's `dock_apps` setting (the one source for its Home dock).

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
"""

from __future__ import annotations

DOCK_APP_TOKENS: tuple[str, ...] = (
    "music",
    "alarm",
    "area",
    "remote",
    "camera",
    "games",
    "tools",
)


def parse_dock_apps(csv: str | None) -> list[str]:
    """Return the known dock apps named in `csv`, in order, without duplicates."""
    out: list[str] = []
    for raw in str(csv or "").split(","):
        tok = raw.strip().lower()
        if tok in DOCK_APP_TOKENS and tok not in out:
            out.append(tok)
    return out


def normalize_dock_apps(csv: str | None) -> str:
    """Return `csv` as canonical comma-separated dock apps; raise ValueError if it names none or an unknown app."""
    names = [t.strip().lower() for t in str(csv or "").split(",") if t.strip()]
    unknown = sorted({t for t in names if t not in DOCK_APP_TOKENS})
    if unknown:
        raise ValueError(f"Unknown dock app: {', '.join(unknown)}")
    apps = parse_dock_apps(csv)
    if not apps:
        raise ValueError("The Home dock needs at least one app")
    return ",".join(apps)
