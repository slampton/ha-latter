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
            "preset:ocean_swell",
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

    def test_builtin_presets_and_procedural_buffers(self) -> None:
        """The 5 built-in presets cover distinct themes and span the full canvas."""
        import ast

        tree = ast.parse((LATTER_DIR / "wallpaper_engine.py").read_text(encoding="utf-8"))
        ns: dict[str, object] = {"math": __import__("math")}
        for node in tree.body:
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "BUILTIN_WALLPAPER_PRESETS"
                and node.value is not None
            ):
                ns["BUILTIN_WALLPAPER_PRESETS"] = ast.literal_eval(node.value)
            elif isinstance(node, ast.FunctionDef) and node.name in {
                "_smoothstep",
                "_render_ocean_swell_buf",
                "_render_pine_ridges_buf",
                "_render_twilight_dunes_buf",
                "_render_aurora_veil_buf",
                "_render_topographic_waves_buf",
            }:
                mod = ast.Module(body=[node], type_ignores=[])
                exec(compile(mod, "wallpaper_engine.py", "exec"), ns)

        presets = ns["BUILTIN_WALLPAPER_PRESETS"]
        self.assertEqual(
            [p["id"] for p in presets],
            [
                "preset:ocean_swell",
                "preset:pine_ridges",
                "preset:twilight_dunes",
                "preset:aurora_veil",
                "preset:topographic_waves",
            ],
        )
        for p in presets:
            self.assertNotIn("AMOLED", p["name"])

        side = 64
        for fn_name in (
            "_render_ocean_swell_buf",
            "_render_pine_ridges_buf",
            "_render_twilight_dunes_buf",
            "_render_aurora_veil_buf",
            "_render_topographic_waves_buf",
        ):
            buf = ns[fn_name](side)
            self.assertEqual(len(buf), side * side * 3, fn_name)
            # Full-canvas check: both the upper half (y = 20%..45%) and lower half (y = 55%..85%) have active detail
            upper_sum = sum(
                buf[(y * side + x) * 3 + c]
                for y in range(int(side * 0.20), int(side * 0.45))
                for x in range(int(side * 0.20), int(side * 0.80))
                for c in range(3)
            )
            lower_sum = sum(
                buf[(y * side + x) * 3 + c]
                for y in range(int(side * 0.55), int(side * 0.85))
                for x in range(int(side * 0.20), int(side * 0.80))
                for c in range(3)
            )
            self.assertGreater(upper_sum, 0, fn_name)
            self.assertGreater(lower_sum, 0, fn_name)


if __name__ == "__main__":
    unittest.main()
