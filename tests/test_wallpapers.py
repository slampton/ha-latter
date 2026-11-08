"""Standalone tests for uploaded wallpapers: private storage, references and signed serving.

They run without Home Assistant installed. The production modules under test (wallpaper_refs.py,
resource_signing.py) are standard-library only and loaded by file path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"latter_wallpaper_test_{name}", LATTER_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


wallpaper_refs = _load("wallpaper_refs")
resource_signing = _load("resource_signing")


class TestPrivateWallpapers(unittest.TestCase):
    """Uploads live in private storage and are referenced as upload:<slug>/<file> (D-005)."""

    def test_private_root(self) -> None:
        cfg = Path("/config")
        self.assertEqual(wallpaper_refs.private_root(cfg), cfg / ".storage" / "latter" / "wallpapers")
        self.assertNotIn("www", wallpaper_refs.private_root(cfg).parts)

    def test_references_round_trip_and_reject_traversal(self) -> None:
        src = wallpaper_refs.make_upload_source("kitchen", "beach_1a2b3c.jpg")
        self.assertEqual(src, "upload:kitchen/beach_1a2b3c.jpg")
        self.assertEqual(wallpaper_refs.parse_upload_source(src), ("kitchen", "beach_1a2b3c.jpg"))
        for bad in (
            "upload:../x.jpg",
            "upload:kitchen/../../secrets.jpg",
            "upload:kitchen/sub/x.jpg",
            "upload:Kitchen/x.jpg",
            "upload:kitchen/x.exe",
            "upload:kitchen/",
            "/local/latter_wallpapers/kitchen/x.jpg",
            "preset:amoled_rings",
            "",
        ):
            self.assertIsNone(wallpaper_refs.parse_upload_source(bad), bad)
        with self.assertRaises(ValueError):
            wallpaper_refs.make_upload_source("kitchen", "../x.jpg")

    def test_resolve_and_read_stay_inside_the_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "wallpapers"
            (root / "kitchen").mkdir(parents=True)
            (root / "kitchen" / "a.jpg").write_bytes(b"jpeg")
            self.assertEqual(wallpaper_refs.read_upload_bytes(root, "upload:kitchen/a.jpg"), b"jpeg")
            self.assertIsNone(wallpaper_refs.read_upload_bytes(root, "upload:kitchen/missing.jpg"))
            self.assertIsNone(wallpaper_refs.read_upload_bytes(root, "upload:kitchen/../../etc.jpg"))
            path = wallpaper_refs.resolve_upload_path(root, "upload:kitchen/a.jpg")
            self.assertIsNotNone(path)
            self.assertTrue(path.is_relative_to(root.resolve()))

    def test_signed_view_resource_binds_the_source(self) -> None:
        """The wallpaper view verifies wallpaper:<src>|w|h|shape; a signature never transfers to another source."""
        secret, now = b"k" * 32, 1_800_000_000
        exp = resource_signing.day_bucketed_expiry(now, resource_signing.PAYLOAD_TTL_DAYS)
        src = "upload:kitchen/beach_1a2b3c.jpg"
        sig = resource_signing.sign(secret, "sub_kitchen", f"wallpaper:{src}|240|240|circle", exp)
        self.assertTrue(resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|240|240|circle", sig, now))
        for other in ("upload:office/beach_1a2b3c.jpg", "upload:kitchen/other_1a2b3c.jpg"):
            self.assertFalse(resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{other}|240|240|circle", sig, now))
        self.assertFalse(resource_signing.verify(secret, "sub_office", f"wallpaper:{src}|240|240|circle", sig, now))
        self.assertFalse(resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|240|240|circle", sig, exp + 1))


if __name__ == "__main__":
    unittest.main()
