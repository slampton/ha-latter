"""Standalone tests for uploaded wallpapers: private storage, references, migration and signed serving.

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
    """Uploads live in private storage, are referenced as upload:<slug>/<file>, and are migrated (D-005)."""

    def test_roots(self) -> None:
        cfg = Path("/config")
        self.assertEqual(wallpaper_refs.private_root(cfg), cfg / ".storage" / "latter" / "wallpapers")
        self.assertEqual(wallpaper_refs.public_root(cfg), cfg / "www" / "latter_wallpapers")
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

    def test_reference_migration(self) -> None:
        old = "/local/latter_wallpapers/kitchen/beach_1a2b3c.jpg"
        self.assertEqual(wallpaper_refs.migrate_public_source(old), "upload:kitchen/beach_1a2b3c.jpg")
        for keep in ("preset:amoled_grid", "upload:kitchen/a.jpg", "", "/local/other/x.jpg", "/local/latter_wallpapers/../x.jpg"):
            self.assertEqual(wallpaper_refs.migrate_public_source(keep), keep)
        data = {"device_slug": "kitchen", "wallpaper_source": old, "wallpaper_favorites": [old, "preset:amoled_rings"]}
        migrated = wallpaper_refs.migrate_wallpaper_settings(data)
        self.assertEqual(migrated["wallpaper_source"], "upload:kitchen/beach_1a2b3c.jpg")
        self.assertEqual(migrated["wallpaper_favorites"], ["upload:kitchen/beach_1a2b3c.jpg", "preset:amoled_rings"])
        self.assertEqual(migrated["device_slug"], "kitchen")
        self.assertIsNone(wallpaper_refs.migrate_wallpaper_settings(migrated))
        profiles = [{"id": "p1", "device_config": {"wallpaper_source": old}}, {"id": "p2", "device_config": {}}]
        new_profiles = wallpaper_refs.migrate_profiles(profiles)
        self.assertEqual(new_profiles[0]["device_config"]["wallpaper_source"], "upload:kitchen/beach_1a2b3c.jpg")
        self.assertEqual(new_profiles[1], profiles[1])
        self.assertIsNone(wallpaper_refs.migrate_profiles(new_profiles))

    def test_move_public_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            pub = wallpaper_refs.public_root(cfg)
            priv = wallpaper_refs.private_root(cfg)
            (pub / "kitchen").mkdir(parents=True)
            (pub / "kitchen" / "beach_1a2b3c.jpg").write_bytes(b"one")
            (pub / "kitchen" / "dup.png").write_bytes(b"public copy")
            (pub / "office").mkdir()
            (pub / "office" / "notes.txt").write_text("not a wallpaper")
            (priv / "kitchen").mkdir(parents=True)
            (priv / "kitchen" / "dup.png").write_bytes(b"private copy")
            self.assertEqual(wallpaper_refs.move_public_uploads(cfg), 1)
            self.assertEqual((priv / "kitchen" / "beach_1a2b3c.jpg").read_bytes(), b"one")
            self.assertEqual((priv / "kitchen" / "dup.png").read_bytes(), b"private copy")
            self.assertFalse((pub / "kitchen").exists())
            # Files that aren't wallpapers are left where they are.
            self.assertTrue((pub / "office" / "notes.txt").exists())
            (pub / "office" / "notes.txt").unlink()
            self.assertEqual(wallpaper_refs.move_public_uploads(cfg), 0)
            self.assertFalse(pub.exists())
            self.assertEqual(wallpaper_refs.move_public_uploads(cfg), 0)

    def test_signed_view_resource_binds_the_source(self) -> None:
        """The wallpaper view verifies wallpaper:<src>|w|h|shape; a signature never transfers to another source."""
        secret, now = b"k" * 32, 1_800_000_000
        exp = resource_signing.day_bucketed_expiry(now, resource_signing.PAYLOAD_TTL_DAYS)
        src = "upload:kitchen/beach_1a2b3c.jpg"
        sig = resource_signing.sign(secret, "sub_kitchen", f"wallpaper:{src}|240|240|circle", exp)
        self.assertTrue(resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|240|240|circle", sig, now))
        for other in ("upload:office/beach_1a2b3c.jpg", "/local/latter_wallpapers/kitchen/beach_1a2b3c.jpg"):
            self.assertFalse(resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{other}|240|240|circle", sig, now))
        self.assertFalse(resource_signing.verify(secret, "sub_office", f"wallpaper:{src}|240|240|circle", sig, now))
        self.assertFalse(resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|240|240|circle", sig, exp + 1))


if __name__ == "__main__":
    unittest.main()
