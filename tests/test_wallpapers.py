"""Tests for Shared Photo Library, Collections, Non-Destructive Crop, HA /media Import, & Pool Resolver."""

from __future__ import annotations

import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from PIL import Image

from custom_components.latter.http import signing as resource_signing
from custom_components.latter.wallpapers import (
    media_import as _wp_import,
    models as _wp_models,
    pools as _wp_pools,
    store as _wp_store,
)

wp = SimpleNamespace(
    **(
        vars(_wp_models)
        | vars(_wp_store)
        | vars(_wp_import)
        | vars(_wp_pools)
        | {
            "_load_photo_library_sync": vars(_wp_store).get(
                "_load_photo_library_sync"
            )
            or vars(_wp_store).get("load_photo_library_sync")
        }
    )
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"


def _make_jpeg(w: int = 120, h: int = 80, color: tuple[int, int, int] = (220, 140, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG", quality=92, progressive=False)
    return buf.getvalue()


def _make_storage_ctx(config_dir: str) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(config_dir=config_dir),
        async_add_executor_job=lambda fn, *a: fn(*a),
    )


class TestPhotoLibraryAndCrop(unittest.TestCase):
    """Photo Library storage, references, non-destructive crop math, collections, pools, and /media import."""

    def test_private_root(self) -> None:
        cfg = Path("/config")
        self.assertEqual(wp.private_root(cfg), cfg / ".storage" / "latter" / "wallpapers")
        self.assertNotIn("www", wp.private_root(cfg).parts)

    def test_photo_references_round_trip_and_reject_traversal(self) -> None:
        src = wp.make_photo_source("sunset_1a2b3c")
        self.assertEqual(src, "photo:sunset_1a2b3c")
        self.assertEqual(wp.parse_photo_source(src), "sunset_1a2b3c")
        for bad in (
            "photo:../x",
            "photo:a/b",
            "photo:Sunset_1234",
            "photo:ab",
            "upload:kitchen/a.jpg",
            "preset:forest_mountains",
            "",
        ):
            self.assertIsNone(wp.parse_photo_source(bad), bad)
        with self.assertRaises(ValueError):
            wp.make_photo_source("../escape")

    def test_resolve_and_read_stay_inside_originals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "wallpapers"
            (root / "originals").mkdir(parents=True)
            (root / "originals" / "beach_1a2b.jpg").write_bytes(b"jpeg")
            self.assertEqual(wp.read_photo_bytes(root, "photo:beach_1a2b"), b"jpeg")
            self.assertIsNone(wp.read_photo_bytes(root, "photo:missing_1234"))
            self.assertIsNone(wp.read_photo_bytes(root, "photo:../../etc"))
            path = wp.resolve_photo_path(root, "photo:beach_1a2b")
            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.is_relative_to((root / "originals").resolve()))

    def test_signed_view_resource_binds_source_and_mode(self) -> None:
        """The wallpaper view verifies wallpaper:<src>|w|h|shape|mode; signatures never transfer across modes or sources."""
        secret, now = b"k" * 32, 1_800_000_000
        exp = resource_signing.day_bucketed_expiry(now, resource_signing.PAYLOAD_TTL_DAYS)
        src = "photo:beach_1a2b3c"
        sig = resource_signing.sign(secret, "sub_kitchen", f"wallpaper:{src}|466|466|circle|wallpaper", exp)
        self.assertTrue(
            resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|466|466|circle|wallpaper", sig, now)
        )
        self.assertFalse(
            resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|466|466|circle|screensaver", sig, now)
        )
        self.assertFalse(
            resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|466|466|circle|original", sig, now)
        )
        self.assertFalse(
            resource_signing.verify(secret, "sub_office", f"wallpaper:{src}|466|466|circle|wallpaper", sig, now)
        )
        self.assertFalse(
            resource_signing.verify(secret, "sub_kitchen", f"wallpaper:{src}|466|466|circle|wallpaper", sig, exp + 1)
        )

    def test_builtin_presets_include_day_night_sky_and_6_jpegs(self) -> None:
        """7 built-in defaults: Day & Night Sky (dynamic_preset) + 6 bundled 720x720 baseline JPEGs."""
        presets = wp.BUILTIN_WALLPAPER_PRESETS
        self.assertEqual(len(presets), 7)
        self.assertEqual(presets[0]["id"], wp.DAY_NIGHT_SKY_PRESET_ID)
        self.assertEqual(presets[0]["name"], "Day & Night Sky")
        self.assertEqual(presets[0]["kind"], "dynamic_preset")
        self.assertTrue(wp.is_dynamic_preset(wp.DAY_NIGHT_SKY_PRESET_ID))
        self.assertFalse(wp.is_dynamic_preset("preset:forest_mountains"))

        wp_dir = LATTER_DIR / "wallpapers"
        photo_presets = [p for p in presets if p["kind"] == "preset"]
        self.assertEqual(len(photo_presets), 6)
        for p in photo_presets:
            jpg_path = wp_dir / p["file"]
            self.assertTrue(jpg_path.is_file(), f"Missing bundled wallpaper {jpg_path}")
            raw = jpg_path.read_bytes()
            self.assertTrue(raw.startswith(b"\xff\xd8\xff"), p["file"])
            self.assertTrue(raw.endswith(b"\xff\xd9"), p["file"])
            with Image.open(io.BytesIO(raw)) as img:
                self.assertEqual(img.size, (720, 720), p["file"])

        # Day & Night Sky preview generator produces distinct day/night/split images
        split_img = wp.render_day_night_sky_preview_image(240, 240, mode="split")
        day_img = wp.render_day_night_sky_preview_image(240, 240, mode="live", is_night=False)
        night_img = wp.render_day_night_sky_preview_image(240, 240, mode="live", is_night=True)
        self.assertEqual(split_img.size, (240, 240))
        self.assertGreater(day_img.getpixel((120, 120))[2], night_img.getpixel((120, 120))[2])

    def test_crop_and_fit_image_zero_black_bars_all_orientations(self) -> None:
        """Non-destructive focal crop guarantees zero black bars across round, square, portrait, and widescreen panels."""
        sources = (
            Image.new("RGB", (1600, 900), (230, 180, 120)),   # 16:9 landscape
            Image.new("RGB", (900, 1600), (120, 210, 180)),   # 9:16 portrait
            Image.new("RGB", (1000, 1000), (200, 140, 220)),  # 1:1 square
        )
        targets = (
            (466, 466),   # Round / square
            (720, 720),   # High-res square
            (360, 640),   # Portrait
            (800, 480),   # Widescreen
        )
        crops = (
            (0.5, 0.5, 1.0),
            (0.0, 0.0, 1.0),
            (1.0, 1.0, 1.0),
            (0.15, 0.85, 2.2),
            (0.95, 0.05, 3.0),
        )
        for src in sources:
            for dw, dh in targets:
                for cx, cy, cz in crops:
                    left, top, right, bottom = wp.compute_crop_box(
                        src.width, src.height, dw, dh, cx, cy, cz
                    )
                    self.assertGreaterEqual(left, 0.0)
                    self.assertGreaterEqual(top, 0.0)
                    self.assertLessEqual(right, float(src.width) + 1e-6)
                    self.assertLessEqual(bottom, float(src.height) + 1e-6)
                    self.assertAlmostEqual(
                        (right - left) / (bottom - top),
                        float(dw) / float(dh),
                        places=3,
                    )
                    out = wp.crop_and_fit_image(src, dw, dh, cx, cy, cz)
                    self.assertEqual(out.size, (dw, dh))
                    # Corners and center must never be black (zero letterboxing/bars)
                    for px, py in ((0, 0), (dw - 1, 0), (0, dh - 1), (dw - 1, dh - 1), (dw // 2, dh // 2)):
                        r, g, b = out.getpixel((px, py))
                        self.assertGreater(r + g + b, 300)

        # Focal point shifts visible quadrant cleanly
        quad = Image.new("RGB", (400, 400), (0, 0, 0))
        quad.paste(Image.new("RGB", (200, 200), (255, 0, 0)), (0, 0))
        quad.paste(Image.new("RGB", (200, 200), (0, 255, 0)), (200, 200))
        top_left = wp.crop_and_fit_image(quad, 100, 100, 0.1, 0.1, 2.5)
        bot_right = wp.crop_and_fit_image(quad, 100, 100, 0.9, 0.9, 2.5)
        self.assertGreater(top_left.getpixel((50, 50))[0], 200)
        self.assertGreater(bot_right.getpixel((50, 50))[1], 200)

    def test_upload_downscales_exif_collections_crud_pools_and_backup_roundtrip(self) -> None:
        """Full Photo Library lifecycle: upload <=1600px, collections CRUD, metadata edit, bulk ops, pools, backup."""
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _make_storage_ctx(tmp)
            wp._load_photo_library_sync(wp.get_wallpaper_root(ctx))

            # 1) Collection CRUD
            col_family = wp.create_collection(ctx, "Family")
            col_travel = wp.create_collection(ctx, "Travel")
            with self.assertRaises(ValueError):
                wp.create_collection(ctx, "family")
            renamed = wp.rename_collection(ctx, col_travel["id"], "Trips")
            self.assertEqual(renamed["name"], "Trips")

            # 2) Upload oversized 2400x1200 image -> downscaled to 1600x800 preserving aspect ratio
            big_raw = _make_jpeg(2400, 1200, (190, 120, 80))
            rec1 = wp.save_uploaded_photo_bytes(
                ctx,
                "beach_panorama.jpg",
                big_raw,
                crop_x=0.25,
                crop_y=0.75,
                crop_zoom=1.5,
                name="Beach Panorama",
                collection_id=col_family["id"],
            )
            self.assertTrue(rec1["id"].startswith("photo:"))
            self.assertEqual((rec1["width"], rec1["height"]), (1600, 800))
            self.assertEqual(rec1["crop"], {"x": 0.25, "y": 0.75, "zoom": 1.5})
            self.assertEqual(rec1["collections"], [col_family["id"]])

            rec2 = wp.save_uploaded_photo_bytes(
                ctx, "mountain.jpg", _make_jpeg(400, 300, (80, 160, 210))
            )

            # 3) Update metadata & preset collection tagging
            upd = wp.update_photo_metadata(
                ctx,
                rec1["id"],
                name="Sunset Coast",
                crop={"x": 0.6, "y": 0.4, "zoom": 2.0},
                collections=[col_family["id"], col_travel["id"]],
            )
            self.assertEqual(upd["name"], "Sunset Coast")
            self.assertEqual(upd["crop"], {"x": 0.6, "y": 0.4, "zoom": 2.0})
            self.assertTrue(upd["crop_changed"])

            wp.update_photo_metadata(
                ctx,
                "preset:forest_mountains",
                collections=[col_travel["id"]],
            )
            with self.assertRaises(ValueError):
                wp.update_photo_metadata(ctx, "preset:forest_mountains", name="Renamed")

            # 4) Pure pool resolver (include_dynamic=True vs False)
            self.assertEqual(
                wp.resolve_photo_pool("off", rec1["id"], "", [], include_dynamic=True), []
            )
            self.assertEqual(
                wp.resolve_photo_pool("single", wp.DAY_NIGHT_SKY_PRESET_ID, "", [], include_dynamic=True),
                [wp.DAY_NIGHT_SKY_PRESET_ID],
            )
            self.assertEqual(
                wp.resolve_photo_pool("single", wp.DAY_NIGHT_SKY_PRESET_ID, "", [], include_dynamic=False),
                [],
            )
            all_wp = wp.resolve_photo_pool("collection", "", wp.VIRTUAL_COLLECTION_ALL, [], include_dynamic=True)
            all_ss = wp.resolve_photo_pool("collection", "", wp.VIRTUAL_COLLECTION_ALL, [], include_dynamic=False)
            self.assertIn(wp.DAY_NIGHT_SKY_PRESET_ID, all_wp)
            self.assertNotIn(wp.DAY_NIGHT_SKY_PRESET_ID, all_ss)
            self.assertIn(rec1["id"], all_ss)
            self.assertEqual(
                wp.resolve_photo_pool("collection", "", wp.VIRTUAL_COLLECTION_UNCATEGORIZED, [], include_dynamic=True),
                [rec2["id"]],
            )
            self.assertEqual(
                wp.resolve_photo_pool("collection", "", col_travel["id"], [], include_dynamic=True),
                ["preset:forest_mountains", rec1["id"]],
            )
            self.assertEqual(
                wp.resolve_photo_pool(
                    "custom",
                    "",
                    "",
                    [wp.DAY_NIGHT_SKY_PRESET_ID, rec2["id"], "photo:missing_0000"],
                    include_dynamic=False,
                ),
                [rec2["id"]],
            )

            # 5) Backup metadata export + restore round-trip
            exported = wp.export_photo_library_metadata()
            self.assertEqual(len(exported["photo_collections"]), 2)
            self.assertEqual(exported["photo_metadata"][rec1["id"]]["name"], "Sunset Coast")
            self.assertEqual(exported["preset_collections"]["preset:forest_mountains"], [col_travel["id"]])

            # Mutate then restore
            wp.update_photo_metadata(ctx, rec1["id"], name="Temp Name")
            wp.restore_photo_library_metadata(
                ctx,
                exported["photo_collections"],
                exported["photo_metadata"],
                exported["preset_collections"],
            )
            self.assertEqual(wp.get_photo_library_snapshot().photos[rec1["id"]].name, "Sunset Coast")

            # 6) Bulk update & delete collection / photos
            bulk_add = wp.bulk_update_photos(
                ctx, [rec2["id"]], add_collection=col_family["id"]
            )
            self.assertEqual(bulk_add["updated"], 1)
            self.assertTrue(wp.delete_collection(ctx, col_family["id"]))
            self.assertNotIn(
                col_family["id"], wp.get_photo_library_snapshot().photos[rec2["id"]].collections
            )
            bulk_del = wp.bulk_update_photos(
                ctx, [rec1["id"], rec2["id"], "preset:ocean_waves"], delete=True
            )
            self.assertEqual(set(bulk_del["deleted_ids"]), {rec1["id"], rec2["id"]})
            self.assertFalse(wp.delete_photo(ctx, "preset:ocean_waves"))

            # Reload from disk confirms clean empty custom library
            reloaded = wp._load_photo_library_sync(wp.get_wallpaper_root(ctx))
            self.assertEqual(len(reloaded.photos), 0)

    def test_media_folder_browse_import_dedup_and_confinement(self) -> None:
        """HA /media browser and batch importer enforce strict path/symlink confinement, 15 MB cap, and SHA-256 dedup."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg_dir = base / "config"
            media_root = base / "media_local"
            outside_dir = base / "outside_secret"
            (media_root / "vacation").mkdir(parents=True)
            outside_dir.mkdir(parents=True)
            (outside_dir / "secret.jpg").write_bytes(_make_jpeg(64, 64, (255, 0, 0)))

            img_a = _make_jpeg(200, 150, (10, 120, 230))
            img_b = _make_jpeg(180, 180, (230, 80, 40))
            (media_root / "vacation" / "beach.jpg").write_bytes(img_a)
            (media_root / "vacation" / "beach_dup.jpg").write_bytes(img_a)  # identical bytes
            (media_root / "vacation" / "sunset.png").write_bytes(img_b)
            (media_root / "vacation" / "notes.txt").write_text("ignore me", encoding="utf-8")
            (media_root / ".hidden.jpg").write_bytes(img_a)

            # Optional symlink escape test (skipped silently only if OS denies unprivileged symlink creation)
            symlink_created = False
            try:
                os.symlink(outside_dir / "secret.jpg", media_root / "vacation" / "escape_link.jpg")
                symlink_created = True
            except OSError:
                pass

            media_dirs = {"local": str(media_root)}
            ctx = _make_storage_ctx(str(cfg_dir))
            wp._load_photo_library_sync(wp.get_wallpaper_root(ctx))

            # Root listing shows subfolder, skips dotfiles
            top = wp.list_media_folder_sync(media_dirs, "local", "")
            self.assertEqual(top["root"], "local")
            self.assertEqual([f["name"] for f in top["folders"]], ["vacation"])
            self.assertEqual(top["images"], [])

            # Subfolder listing shows valid images only (never notes.txt, never symlink escape)
            sub = wp.list_media_folder_sync(media_dirs, "local", "vacation")
            self.assertEqual(sub["parent_subpath"], "")
            listed_names = [im["name"] for im in sub["images"]]
            self.assertEqual(listed_names, ["beach.jpg", "beach_dup.jpg", "sunset.png"])
            self.assertNotIn("escape_link.jpg", listed_names)

            # Traversal rejected
            with self.assertRaises(ValueError):
                wp.list_media_folder_sync(media_dirs, "local", "../outside_secret")
            self.assertIsNone(wp.resolve_media_path(media_dirs, "local", "../outside_secret/secret.jpg"))
            if symlink_created:
                self.assertIsNone(wp.resolve_media_path(media_dirs, "local", "vacation/escape_link.jpg"))

            # Batch import with SHA-256 deduplication and collection tagging
            col = wp.create_collection(ctx, "Vacation")
            res = wp.import_media_photos_sync(
                ctx,
                media_dirs,
                "local",
                [
                    "vacation/beach.jpg",
                    "vacation/beach_dup.jpg",
                    "vacation/sunset.png",
                    "../outside_secret/secret.jpg",
                    "vacation/notes.txt",
                ],
                collection_id=col["id"],
                deduplicate=True,
            )
            self.assertEqual(res["imported"], 2)
            self.assertEqual(res["skipped"], 1)
            self.assertEqual(len(res["failed"]), 2)
            self.assertEqual(len(res["photos"]), 2)
            self.assertTrue(all(p["source_kind"] == "media_import" for p in res["photos"]))

            # Batch > 100 rejected
            with self.assertRaises(ValueError):
                wp.import_media_photos_sync(
                    ctx, media_dirs, "local", [f"vacation/p{i}.jpg" for i in range(101)]
                )


if __name__ == "__main__":
    unittest.main()
