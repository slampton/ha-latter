"""When a Studio push carries the entity catalog.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
The catalog (every entity Studio offers in its pickers) is the largest part of the Studio payload and
changes only when the entity, device or Area registry changes. So `get_state` and the first subscription
answer always carry it, live pushes carry it only after a registry change, and command answers never do
(Studio keeps the last catalog it received).
"""

from __future__ import annotations


class CatalogGate:
    """Per-subscription flag: does the next live push need the catalog?"""

    def __init__(self) -> None:
        """Start clean: the subscription's first answer already carried the catalog."""
        self._dirty = False

    def mark_dirty(self) -> None:
        """A registry changed; the next push carries the catalog."""
        self._dirty = True

    def take(self) -> bool:
        """Return True once after a registry change, then False until the next one."""
        dirty, self._dirty = self._dirty, False
        return dirty
