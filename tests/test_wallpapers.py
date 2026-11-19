"""Tests for uploaded & built-in wallpapers: private storage, references, and signed serving."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from custom_components.latter import http as resource_signing, wallpapers as wallpaper_refs

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"


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
            "preset:forest_mountains",
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
            self.assertFalse(
                resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{other}|240|240|circle", sig, now)
            )
        self.assertFalse(resource_signing.verify(secret, "sub_office", f"wallpaper:{src}|240|240|circle", sig, now))
        self.assertFalse(
            resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|240|240|circle", sig, exp + 1)
        )

    def test_builtin_presets_and_bundled_jpegs(self) -> None:
        """The 6 built-in presets map to bundled 720x720 baseline JPEGs under custom_components/latter/wallpapers/."""
        presets = wallpaper_refs.BUILTIN_WALLPAPER_PRESETS
        self.assertEqual(
            [(p["id"], p["name"], p["file"]) for p in presets],
            [
                ("preset:forest_mountains", "Forest Mountains", "forest_mountains.jpg"),
                ("preset:wheat_field", "Wheat Field", "wheat_field.jpg"),
                ("preset:ocean_waves", "Ocean Waves", "ocean_waves.jpg"),
                ("preset:sahara_dunes", "Sahara Dunes", "sahara_dunes.jpg"),
                ("preset:andromeda_galaxy", "Andromeda Galaxy", "andromeda_galaxy.jpg"),
                ("preset:mars_crater", "Mars Crater", "mars_crater.jpg"),
            ],
        )

        wp_dir = LATTER_DIR / "wallpapers"
        for p in presets:
            jpg_path = wp_dir / p["file"]
            self.assertTrue(jpg_path.is_file(), f"Missing bundled wallpaper {jpg_path}")
            raw = jpg_path.read_bytes()
            self.assertTrue(raw.startswith(b"\xff\xd8\xff"), p["file"])
            self.assertTrue(raw.endswith(b"\xff\xd9"), p["file"])
            idx = 2
            sof_marker = None
            dims = None
            while idx < len(raw) - 1:
                if raw[idx] != 0xFF:
                    break
                marker = raw[idx + 1]
                idx += 2
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    continue
                if marker == 0xDA:
                    break
                seg_len = int.from_bytes(raw[idx : idx + 2], "big")
                if marker in (0xC0, 0xC2):
                    sof_marker = marker
                    height = int.from_bytes(raw[idx + 3 : idx + 5], "big")
                    width = int.from_bytes(raw[idx + 5 : idx + 7], "big")
                    dims = (width, height)
                idx += seg_len
            self.assertEqual(sof_marker, 0xC0, f"{p['file']} must be baseline SOF0 JPEG")
            self.assertEqual(dims, (720, 720), p["file"])

    def test_system_wide_snapshot_ids_and_delete_signature(self) -> None:
        """ordered_wallpaper_ids, known_wallpaper_ids, and delete_uploaded_wallpaper operate System-wide without device_slug."""
        import io
        from types import SimpleNamespace

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), (30, 80, 140)).save(buf, format="JPEG")
        raw_jpg = buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            fake_hass = SimpleNamespace(
                config=SimpleNamespace(config_dir=tmp),
                async_add_executor_job=lambda fn, *a: fn(*a),
            )
            wallpaper_refs._scan_all_wallpapers_sync(wallpaper_refs.get_wallpaper_root(fake_hass))
            preset_ids = [p["id"] for p in wallpaper_refs.BUILTIN_WALLPAPER_PRESETS]
            self.assertEqual(wallpaper_refs.ordered_wallpaper_ids(), preset_ids)
            self.assertEqual(wallpaper_refs.known_wallpaper_ids(), set(preset_ids))

            src_sys, _ = wallpaper_refs.save_uploaded_wallpaper_bytes(
                fake_hass, "system", "lobby.jpg", raw_jpg
            )
            src_dev, _ = wallpaper_refs.save_uploaded_wallpaper_bytes(
                fake_hass, "kitchen_panel", "patio.jpg", raw_jpg
            )
            ordered = wallpaper_refs.ordered_wallpaper_ids()
            self.assertEqual(ordered[: len(preset_ids)], preset_ids)
            self.assertIn(src_sys, ordered)
            self.assertIn(src_dev, ordered)
            self.assertLess(ordered.index(src_sys), ordered.index(src_dev))
            self.assertTrue({src_sys, src_dev}.issubset(wallpaper_refs.known_wallpaper_ids()))

            self.assertTrue(wallpaper_refs.delete_uploaded_wallpaper(fake_hass, src_dev))
            self.assertFalse(wallpaper_refs.delete_uploaded_wallpaper(fake_hass, src_dev))
            self.assertFalse(wallpaper_refs.delete_uploaded_wallpaper(fake_hass, "preset:ocean_waves"))
            self.assertNotIn(src_dev, wallpaper_refs.known_wallpaper_ids())
            self.assertIn(src_sys, wallpaper_refs.known_wallpaper_ids())
            self.assertTrue(wallpaper_refs.delete_uploaded_wallpaper(fake_hass, src_sys))


if __name__ == "__main__":
    unittest.main()
