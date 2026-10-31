"""AMOLED-Optimized Procedural Wallpaper Generator & Gallery File Manager for Latter."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import math
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from homeassistant.core import HomeAssistant

from .const import normalize_device_slug

_LOGGER = logging.getLogger(__name__)

BUILTIN_WALLPAPER_PRESETS: tuple[dict[str, str], ...] = (
    {
        "id": "preset:amoled_rings",
        "name": "AMOLED Concentric Rings (Ultra-Low Power)",
        "kind": "preset",
    },
    {
        "id": "preset:amoled_grid",
        "name": "AMOLED Precision Telemetry Grid",
        "kind": "preset",
    },
    {
        "id": "preset:amoled_horizon",
        "name": "AMOLED Deep Steel Horizon",
        "kind": "preset",
    },
    {
        "id": "preset:amoled_nebula",
        "name": "AMOLED Midnight Indigo Glow",
        "kind": "preset",
    },
    {
        "id": "preset:amoled_ember",
        "name": "AMOLED Warm Amber Eclipse",
        "kind": "preset",
    },
)


def get_device_wallpaper_dir(hass: HomeAssistant, device_slug: str) -> Path:
    """Return the persistent directory `/config/www/latter_wallpapers/<device_slug>`."""
    slug = normalize_device_slug(device_slug)
    return Path(hass.config.path("www")) / "latter_wallpapers" / slug


def render_builtin_preset_bytes(
    preset_id: str, width: int = 466, height: int = 466
) -> bytes:
    """Generate a crisp, low-power (>80% pure black) AMOLED procedural wallpaper as raw PNG bytes."""
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = width // 2, height // 2
    max_r = min(cx, cy)

    if preset_id == "preset:amoled_grid":
        step = max(24, width // 12)
        for x in range(step // 2, width, step):
            dist = abs(x - cx) / max(1, cx)
            val = max(6, int(26 * (1.0 - dist * 0.55)))
            draw.line([(x, 0), (x, height)], fill=(val // 2, val, int(val * 1.4)), width=1)
        for y in range(step // 2, height, step):
            dist = abs(y - cy) / max(1, cy)
            val = max(6, int(26 * (1.0 - dist * 0.55)))
            draw.line([(0, y), (width, y)], fill=(val // 2, val, int(val * 1.4)), width=1)
        for r_frac, col in ((0.96, (14, 52, 84)), (0.72, (10, 32, 52)), (0.42, (8, 22, 36))):
            r = int(max_r * r_frac)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=1)

    elif preset_id == "preset:amoled_horizon":
        horizon_y = int(height * 0.62)
        for y in range(horizon_y - 60, height):
            if y < horizon_y:
                t = (y - (horizon_y - 60)) / 60.0
                r_c = int(10 * (t**2))
                g_c = int(42 * (t**2))
                b_c = int(78 * (t**2))
            else:
                t = 1.0 - min(1.0, (y - horizon_y) / max(1, height - horizon_y))
                r_c = int(8 * (t**1.8))
                g_c = int(28 * (t**1.8))
                b_c = int(52 * (t**1.8))
            draw.line([(0, y), (width, y)], fill=(r_c, g_c, b_c))
        draw.line([(0, horizon_y), (width, horizon_y)], fill=(28, 96, 156), width=2)
        for deg in range(-75, 80, 15):
            rad = math.radians(deg)
            x_end = cx + int(math.sin(rad) * width * 0.9)
            draw.line([(cx, horizon_y), (x_end, height)], fill=(12, 38, 64), width=1)

    elif preset_id == "preset:amoled_nebula":
        for r in range(max_r, 4, -3):
            t = 1.0 - (r / max_r)
            glow = math.exp(-((r / (max_r * 0.52)) ** 2))
            r_c = int(24 * glow)
            g_c = int(18 * (t**1.5))
            b_c = int(68 * glow + 16 * t)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(r_c, g_c, b_c))
        inner = int(max_r * 0.58)
        draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=(0, 0, 0))
        draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), outline=(28, 42, 88), width=2)

    elif preset_id == "preset:amoled_ember":
        for r in range(int(max_r * 0.98), int(max_r * 0.78), -2):
            t = (r - max_r * 0.78) / (max_r * 0.20)
            intensity = math.sin(t * math.pi)
            draw.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                outline=(int(92 * intensity), int(38 * intensity), int(6 * intensity)),
                width=2,
            )

    else:  # Default: preset:amoled_rings
        for idx, frac in enumerate((0.97, 0.88, 0.76, 0.62, 0.46, 0.28)):
            r = int(max_r * frac)
            shade = max(12, 46 - idx * 6)
            col = (shade // 3, int(shade * 0.85), int(shade * 1.35))
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=2 if idx == 0 else 1)
        for deg in range(0, 360, 30):
            rad = math.radians(deg)
            r1 = int(max_r * 0.90)
            r2 = int(max_r * 0.96)
            x1, y1 = cx + int(r1 * math.cos(rad)), cy + int(r1 * math.sin(rad))
            x2, y2 = cx + int(r2 * math.cos(rad)), cy + int(r2 * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=(20, 68, 108), width=2 if deg % 90 == 0 else 1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_WALLPAPER_FILES_CACHE: dict[str, list[tuple[str, str]]] = {}


def _scan_wallpaper_dir_sync(wp_dir: Path, slug: str) -> list[tuple[str, str]]:
    """Scan uploaded wallpaper files in a worker thread and update the in-memory cache."""
    entries: list[tuple[str, str]] = []
    if wp_dir.is_dir():
        for file_path in sorted(wp_dir.glob("*"), key=lambda p: p.name.lower()):
            if file_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            source_id = f"/local/latter_wallpapers/{slug}/{file_path.name}"
            entries.append((source_id, file_path.name))
    _WALLPAPER_FILES_CACHE[slug] = entries
    return entries


async def async_refresh_wallpaper_cache(
    hass: HomeAssistant, device_slug: str
) -> None:
    """Populate the uploaded wallpaper file cache in the executor without blocking the event loop."""
    slug = normalize_device_slug(device_slug)
    wp_dir = get_device_wallpaper_dir(hass, slug)
    await hass.async_add_executor_job(_scan_wallpaper_dir_sync, wp_dir, slug)


def list_wallpaper_catalog(
    hass: HomeAssistant,
    device_slug: str,
    active_source: str,
    favorites: list[str],
) -> list[dict[str, Any]]:
    """Return built-in AMOLED presets + cached uploaded wallpapers in `/config/www/latter_wallpapers/<slug>`."""
    fav_set = set(favorites or [])
    items: list[dict[str, Any]] = []

    for preset in BUILTIN_WALLPAPER_PRESETS:
        pid = preset["id"]
        items.append(
            {
                "id": pid,
                "name": preset["name"],
                "kind": "preset",
                "active": pid == active_source,
                "favorite": pid in fav_set,
                "deletable": False,
            }
        )

    slug = normalize_device_slug(device_slug)
    cached_files = _WALLPAPER_FILES_CACHE.get(slug)
    if cached_files is None:
        wp_dir = get_device_wallpaper_dir(hass, slug)
        hass.async_add_executor_job(_scan_wallpaper_dir_sync, wp_dir, slug)
        cached_files = []

    for source_id, fname in cached_files:
        stem = Path(fname).stem
        items.append(
            {
                "id": source_id,
                "name": stem.replace("_", " ").title(),
                "filename": fname,
                "kind": "uploaded",
                "active": source_id == active_source,
                "favorite": source_id in fav_set,
                "deletable": True,
            }
        )

    return items


def save_uploaded_wallpaper(
    hass: HomeAssistant,
    device_slug: str,
    filename: str,
    base64_data: str,
) -> str:
    """Decode a base64 image upload, convert to high-quality RGB JPEG, save in www/latter_wallpapers/<slug>, and return `/local/...` ID."""
    if "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]
    raw_bytes = base64.b64decode(base64_data)

    wp_dir = get_device_wallpaper_dir(hass, device_slug)
    wp_dir.mkdir(parents=True, exist_ok=True)

    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(filename or "wallpaper").stem).strip("_")
    if not stem:
        stem = "wallpaper"
    short_hash = hashlib.md5(raw_bytes).hexdigest()[:6]
    out_name = f"{stem[:28]}_{short_hash}.jpg"
    out_path = wp_dir / out_name

    with Image.open(io.BytesIO(raw_bytes)) as img:
        rgb = img.convert("RGB")
        fitted = ImageOps.fit(
            rgb, (960, 960), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
        fitted.save(out_path, format="JPEG", quality=92, optimize=True, progressive=False)

    slug = normalize_device_slug(device_slug)
    _scan_wallpaper_dir_sync(wp_dir, slug)
    return f"/local/latter_wallpapers/{slug}/{out_name}"


def delete_uploaded_wallpaper(
    hass: HomeAssistant,
    device_slug: str,
    source_id: str,
) -> bool:
    """Delete an uploaded wallpaper file from `/config/www/latter_wallpapers/<slug>`."""
    slug = normalize_device_slug(device_slug)
    prefix = f"/local/latter_wallpapers/{slug}/"
    if not source_id.startswith(prefix):
        return False
    fname = Path(source_id[len(prefix) :]).name
    wp_dir = get_device_wallpaper_dir(hass, device_slug)
    target = wp_dir / fname
    if target.is_file():
        target.unlink()
        _scan_wallpaper_dir_sync(wp_dir, slug)
        return True
    return False