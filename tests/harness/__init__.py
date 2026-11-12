"""Bootstrap lightweight in-memory Home Assistant test harness when running offline."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from .deterministic_loop import DeterministicEventLoop
from .fake_ha_core import install_fake_ha_core
from .optional_deps import build_minimal_baseline_jpeg, ensure_module, install_optional_dep_stubs

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

install_optional_dep_stubs()

USING_HA_STUBS: bool = importlib.util.find_spec("homeassistant") is None
if USING_HA_STUBS:
    install_fake_ha_core()

__all__ = [
    "REPO_ROOT",
    "USING_HA_STUBS",
    "DeterministicEventLoop",
    "build_minimal_baseline_jpeg",
    "ensure_module",
]
