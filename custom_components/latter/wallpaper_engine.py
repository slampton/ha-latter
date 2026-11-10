"""Procedural Wallpaper Generator & Gallery File Manager for Latter."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import math
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageOps

from homeassistant.core import HomeAssistant

from .const import normalize_device_slug
from .wallpaper_refs import (
    IMAGE_SUFFIXES,
    make_upload_source,
    parse_upload_source,
    private_root,
    resolve_upload_path,
)

_LOGGER = logging.getLogger(__name__)

BUILTIN_WALLPAPER_PRESETS: tuple[dict[str, str], ...] = (
    {
        "id": "preset:steel_horizon",
        "name": "Deep Steel Horizon",
        "kind": "preset",
    },
    {
        "id": "preset:pine_ridges",
        "name": "Cascade Pine Ridges",
        "kind": "preset",
    },
    {
        "id": "preset:twilight_dunes",
        "name": "Sahara Twilight Dunes",
        "kind": "preset",
    },
    {
        "id": "preset:aurora_veil",
        "name": "Northern Aurora Veil",
        "kind": "preset",
    },
    {
        "id": "preset:topographic_waves",
        "name": "Obsidian Topographic Waves",
        "kind": "preset",
    },
)


def get_wallpaper_root(hass: HomeAssistant) -> Path:
    """Return Latter's private wallpaper root (`<config>/.storage/latter/wallpapers`, never served by HA)."""
    return private_root(hass.config.config_dir)


def get_device_wallpaper_dir(hass: HomeAssistant, device_slug: str) -> Path:
    """Return the private upload directory of one Device (`<wallpaper root>/<device_slug>`)."""
    return get_wallpaper_root(hass) / normalize_device_slug(device_slug)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Hermite smoothstep interpolation in [0.0, 1.0]."""
    t = max(0.0, min(1.0, (x - edge0) / max(1e-6, edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _render_pine_ridges_buf(side: int) -> bytearray:
    """Render Cascade Pine Ridges onto a (side x side) RGB bytearray."""
    buf = bytearray(side * side * 3)
    ridges = (
        (0.51, 0.055, 0.45, (28, 66, 72), (16, 40, 46), 0.59, (54, 118, 118), 0.055),
        (0.62, 0.048, 2.05, (20, 50, 56), (11, 28, 34), 0.70, (42, 96, 98), 0.050),
        (0.73, 0.040, 3.65, (13, 34, 40), (7, 18, 23), 0.81, (30, 72, 76), 0.045),
        (0.84, 0.030, 5.20, (7, 18, 22), (3, 8, 11), 1.00, (0, 0, 0), 0.0),
    )
    ridge_y: list[list[float]] = []
    mist_line_y: list[list[float]] = []
    for idx, (base_y, amp, ph, _ct, _cb, mist_y, _cm, _ms) in enumerate(ridges):
        prof: list[float] = []
        mprof: list[float] = []
        for x in range(side):
            xf = x / max(1, side - 1)
            h = (
                0.52 * math.sin(xf * math.tau * 0.95 + ph)
                + 0.27 * math.cos(xf * math.tau * 1.90 - ph * 0.65)
                + 0.13 * math.sin(xf * math.tau * 3.40 + ph * 1.25)
                + 0.08 * math.cos(xf * math.tau * 5.80 - ph * 1.80)
            )
            prof.append(base_y + amp * h)
            mprof.append(mist_y + 0.008 * math.sin(xf * math.tau * 0.70 + idx * 1.4))
        ridge_y.append(prof)
        mist_line_y.append(mprof)

    aa = 1.6 / side
    for y in range(side):
        yf = y / max(1, side - 1)
        sky_t = min(1.0, yf / 0.54)
        glow_h = math.exp(-(((yf - 0.49) / 0.14) ** 2))
        sr = 3.0 + 11.0 * (sky_t**1.8) + 20.0 * glow_h
        sg = 7.0 + 28.0 * (sky_t**1.6) + 50.0 * glow_h
        sb = 11.0 + 34.0 * (sky_t**1.5) + 56.0 * glow_h

        row_off = y * side * 3
        for x in range(side):
            r, g, b = sr, sg, sb
            for r_idx, (_base_y, _amp, _ph, c_top, c_bot, _mist_y, c_mist, mist_span) in enumerate(ridges):
                ry = ridge_y[r_idx][x]
                if yf >= ry - aa:
                    cov = _smoothstep(ry - aa, ry + aa, yf)
                    depth_t = min(1.0, max(0.0, (yf - ry) / 0.16))
                    rr = c_top[0] + (c_bot[0] - c_top[0]) * depth_t
                    rg = c_top[1] + (c_bot[1] - c_top[1]) * depth_t
                    rb = c_top[2] + (c_bot[2] - c_top[2]) * depth_t
                    if mist_span > 0.0:
                        my = mist_line_y[r_idx][x]
                        dy_mist = (yf - my) / mist_span
                        mist_w = math.exp(-(dy_mist * dy_mist)) * 0.58
                        crest_clear = min(1.0, max(0.0, (yf - ry) / 0.025))
                        mist_w *= crest_clear
                        rr = rr * (1.0 - mist_w) + c_mist[0] * mist_w
                        rg = rg * (1.0 - mist_w) + c_mist[1] * mist_w
                        rb = rb * (1.0 - mist_w) + c_mist[2] * mist_w
                    r = r * (1.0 - cov) + rr * cov
                    g = g * (1.0 - cov) + rg * cov
                    b = b * (1.0 - cov) + rb * cov

            idx = row_off + x * 3
            buf[idx] = int(min(255.0, max(0.0, r)))
            buf[idx + 1] = int(min(255.0, max(0.0, g)))
            buf[idx + 2] = int(min(255.0, max(0.0, b)))
    return buf


def _render_twilight_dunes_buf(side: int) -> bytearray:
    """Render Sahara Twilight Dunes onto a (side x side) RGB bytearray."""
    buf = bytearray(side * side * 3)
    dunes = (
        (0.52, -0.055, 0.044, 0.35, (118, 56, 25), (42, 18, 9), (168, 92, 42)),
        (0.65, 0.075, 0.050, 2.25, (48, 21, 11), (16, 7, 5), (136, 68, 30)),
        (0.79, -0.065, 0.045, 4.05, (96, 44, 20), (18, 8, 5), (152, 80, 35)),
    )
    dune_y: list[list[float]] = []
    for base_y, slope, amp, ph, *_rest in dunes:
        prof: list[float] = []
        for x in range(side):
            xf = x / max(1, side - 1)
            curve = (
                slope * (xf - 0.5)
                + amp * math.sin(xf * math.tau * 0.85 + ph)
                + (amp * 0.34) * math.cos(xf * math.tau * 1.70 - ph * 0.6)
            )
            prof.append(base_y + curve)
        dune_y.append(prof)

    aa = 1.5 / side
    rim_w = 2.8 / side
    for y in range(side):
        yf = y / max(1, side - 1)
        sky_t = min(1.0, yf / 0.52)
        glow = math.exp(-(((yf - 0.48) / 0.13) ** 2))
        sr = 6.0 + 26.0 * (sky_t**2.0) + 54.0 * glow
        sg = 4.0 + 11.0 * (sky_t**2.0) + 23.0 * glow
        sb = 5.0 + 8.0 * (sky_t**1.8) + 11.0 * glow

        row_off = y * side * 3
        for x in range(side):
            xf = x / max(1, side - 1)
            sun_x = math.exp(-(((xf - 0.35) / 0.45) ** 2))
            r = sr + 16.0 * glow * sun_x
            g = sg + 7.0 * glow * sun_x
            b = sb + 2.0 * glow * sun_x

            for d_idx, (_base_y, _slope, _amp, _ph, c_top, c_bot, c_rim) in enumerate(dunes):
                dy = dune_y[d_idx][x]
                if yf >= dy - aa:
                    cov = _smoothstep(dy - aa, dy + aa, yf)
                    depth_t = min(1.0, max(0.0, (yf - dy) / 0.22))
                    sun_slope = 0.82 + 0.18 * math.cos(xf * math.tau * 0.85 + d_idx * 1.7)
                    dr = (c_top[0] + (c_bot[0] - c_top[0]) * depth_t) * sun_slope
                    dg = (c_top[1] + (c_bot[1] - c_top[1]) * depth_t) * sun_slope
                    db = (c_top[2] + (c_bot[2] - c_top[2]) * depth_t) * sun_slope
                    crest_dist = yf - dy
                    if 0.0 <= crest_dist <= rim_w:
                        rim_k = ((1.0 - crest_dist / rim_w) ** 2) * 0.75
                        dr = dr * (1.0 - rim_k) + c_rim[0] * rim_k
                        dg = dg * (1.0 - rim_k) + c_rim[1] * rim_k
                        db = db * (1.0 - rim_k) + c_rim[2] * rim_k
                    r = r * (1.0 - cov) + dr * cov
                    g = g * (1.0 - cov) + dg * cov
                    b = b * (1.0 - cov) + db * cov

            idx = row_off + x * 3
            buf[idx] = int(min(255.0, max(0.0, r)))
            buf[idx + 1] = int(min(255.0, max(0.0, g)))
            buf[idx + 2] = int(min(255.0, max(0.0, b)))
    return buf


def _render_aurora_veil_buf(side: int) -> bytearray:
    """Render Northern Aurora Veil onto a (side x side) RGB bytearray."""
    buf = bytearray(side * side * 3)
    for y in range(side):
        yf = y / max(1, side - 1)
        clock_band = _smoothstep(0.26, 0.52, yf)
        row_off = y * side * 3
        for x in range(side):
            xf = x / max(1, side - 1)
            r = 3.0 + 5.0 * (yf**1.5)
            g = 4.0 + 9.0 * (yf**1.5)
            b = 10.0 + 20.0 * (yf**1.2)

            c1_y = (
                0.67
                - 0.09 * math.sin(xf * math.tau * 0.70 + 0.35)
                + 0.035 * math.cos(xf * math.tau * 1.45 - 0.7)
            )
            dy1 = yf - c1_y
            env1 = math.exp(-((dy1 / (0.18 if dy1 < 0.0 else 0.032)) ** 2))
            ray_u = xf + dy1 * 0.18
            rays1 = (
                0.70
                + 0.15 * math.sin(ray_u * math.tau * 3.5 + 0.5)
                + 0.09 * math.cos(ray_u * math.tau * 9.0 - 1.1)
                + 0.06 * math.sin(ray_u * math.tau * 17.0 + 2.4)
            )
            w1 = env1 * rays1 * (0.25 + 0.75 * clock_band)
            alt1 = max(0.0, min(1.0, -dy1 / 0.21))
            ar1 = 16.0 * (1.0 - alt1) + 74.0 * alt1
            ag1 = 132.0 * (1.0 - alt1) + 32.0 * alt1
            ab1 = 106.0 * (1.0 - alt1) + 128.0 * alt1

            c2_y = (
                0.56
                + 0.08 * math.cos(xf * math.tau * 0.65 - 0.4)
                + 0.025 * math.sin(xf * math.tau * 1.3 + 1.1)
            )
            dy2 = yf - c2_y
            env2 = math.exp(-((dy2 / (0.15 if dy2 < 0.0 else 0.045)) ** 2))
            ray_u2 = xf - dy2 * 0.14
            rays2 = (
                0.74
                + 0.16 * math.sin(ray_u2 * math.tau * 4.5 + 1.9)
                + 0.10 * math.cos(ray_u2 * math.tau * 11.0 - 0.6)
            )
            w2 = env2 * rays2 * (0.20 + 0.80 * clock_band) * 0.78
            alt2 = max(0.0, min(1.0, -dy2 / 0.18))
            ar2 = 44.0 * (1.0 - alt2) + 86.0 * alt2
            ag2 = 58.0 * (1.0 - alt2) + 28.0 * alt2
            ab2 = 122.0 * (1.0 - alt2) + 136.0 * alt2

            r = min(255.0, r + ar1 * w1 + ar2 * w2)
            g = min(255.0, g + ag1 * w1 + ag2 * w2)
            b = min(255.0, b + ab1 * w1 + ab2 * w2)

            hor_y = 0.89 + 0.022 * math.sin(xf * math.tau * 1.1 + 0.8)
            if yf > hor_y:
                fade = max(0.0, 1.0 - (yf - hor_y) / 0.022)
                r = r * fade + 3.0 * (1.0 - fade)
                g = g * fade + 6.0 * (1.0 - fade)
                b = b * fade + 10.0 * (1.0 - fade)

            idx = row_off + x * 3
            buf[idx] = int(r)
            buf[idx + 1] = int(g)
            buf[idx + 2] = int(b)
    return buf


def _render_topographic_waves_buf(side: int) -> bytearray:
    """Render Obsidian Topographic Waves onto a (side x side) RGB bytearray."""
    buf = bytearray(side * side * 3)
    num_levels = 10.0
    for y in range(side):
        yf = y / max(1, side - 1)
        vert_vis = 0.16 + 0.84 * _smoothstep(0.22, 0.56, yf)
        dy_clock = (yf - 0.26) / 0.20
        row_off = y * side * 3
        for x in range(side):
            xf = x / max(1, side - 1)
            dx_clock = (xf - 0.50) / 0.36
            clock_pocket = min(
                1.0, max(0.25, (dx_clock * dx_clock + dy_clock * dy_clock) * 0.75)
            )
            vis = vert_vis * clock_pocket

            h = (
                yf * 0.85
                + 0.24 * math.sin(xf * 4.4 + yf * 2.2 + 0.4)
                + 0.18 * math.cos(xf * 2.8 - yf * 3.6 + 1.2)
                + 0.11 * math.sin(xf * 6.2 + yf * 4.0 - 0.7)
            )
            dh_dx = (
                0.24 * 4.4 * math.cos(xf * 4.4 + yf * 2.2 + 0.4)
                - 0.18 * 2.8 * math.sin(xf * 2.8 - yf * 3.6 + 1.2)
                + 0.11 * 6.2 * math.cos(xf * 6.2 + yf * 4.0 - 0.7)
            )
            dh_dy = (
                0.85
                + 0.24 * 2.2 * math.cos(xf * 4.4 + yf * 2.2 + 0.4)
                + 0.18 * 3.6 * math.sin(xf * 2.8 - yf * 3.6 + 1.2)
                + 0.11 * 4.0 * math.cos(xf * 6.2 + yf * 4.0 - 0.7)
            )
            grad_mag = max(0.008, math.hypot(dh_dx, dh_dy) * num_levels / side)

            scaled = h * num_levels
            level_idx = int(math.floor(scaled + 0.5))
            dist_px = abs(scaled - level_idx) / grad_mag

            is_major = (level_idx % 3) == 0
            line_half_w = 1.05 if is_major else 0.72
            line_alpha = (
                max(0.0, min(1.0, (line_half_w + 0.65 - dist_px) / 1.15)) * vis
            )

            shade = max(0.0, min(1.0, 0.50 + 0.10 * dh_dx - 0.12 * dh_dy))
            elev_norm = max(0.0, min(1.0, (h + 0.2) / 1.4)) * vis
            base_r = 5.0 + 22.0 * elev_norm * shade
            base_g = 6.0 + 23.0 * elev_norm * shade
            base_b = 8.0 + 27.0 * elev_norm * shade

            if is_major:
                cr, cg, cb = 128.0, 118.0, 102.0
            else:
                cr, cg, cb = 64.0, 68.0, 76.0

            r = base_r * (1.0 - line_alpha) + cr * line_alpha
            g = base_g * (1.0 - line_alpha) + cg * line_alpha
            b = base_b * (1.0 - line_alpha) + cb * line_alpha

            idx = row_off + x * 3
            buf[idx] = int(min(255.0, r))
            buf[idx + 1] = int(min(255.0, g))
            buf[idx + 2] = int(min(255.0, b))
    return buf


def render_builtin_preset_image(
    preset_id: str, width: int = 466, height: int = 466
) -> Image.Image:
    """Generate a square-master procedural wallpaper and center-crop to (width, height)."""
    width = max(64, min(1920, int(width)))
    height = max(64, min(1920, int(height)))
    side = max(width, height)

    if preset_id == "preset:pine_ridges":
        grid = min(side, 280)
        buf = _render_pine_ridges_buf(grid)
        master = Image.frombytes("RGB", (grid, grid), bytes(buf))
        if grid != side:
            master = master.resize((side, side), resample=Image.Resampling.BICUBIC)
    elif preset_id == "preset:twilight_dunes":
        grid = min(side, 280)
        buf = _render_twilight_dunes_buf(grid)
        master = Image.frombytes("RGB", (grid, grid), bytes(buf))
        if grid != side:
            master = master.resize((side, side), resample=Image.Resampling.BICUBIC)
    elif preset_id == "preset:aurora_veil":
        grid = min(side, 260)
        buf = _render_aurora_veil_buf(grid)
        master = Image.frombytes("RGB", (grid, grid), bytes(buf))
        if grid != side:
            master = master.resize((side, side), resample=Image.Resampling.BICUBIC)
    elif preset_id == "preset:topographic_waves":
        grid = min(side, 320)
        buf = _render_topographic_waves_buf(grid)
        master = Image.frombytes("RGB", (grid, grid), bytes(buf))
        if grid != side:
            master = master.resize((side, side), resample=Image.Resampling.BICUBIC)
    else:  # Default: preset:steel_horizon (Deep Steel Horizon)
        master = Image.new("RGB", (side, side), (0, 0, 0))
        draw = ImageDraw.Draw(master)
        cx = side // 2
        horizon_y = int(side * 0.62)
        band_h = max(1, int(side * 0.13))
        for y in range(max(0, horizon_y - band_h), side):
            if y < horizon_y:
                t = (y - (horizon_y - band_h)) / float(band_h)
                r_c = int(10 * (t**2))
                g_c = int(42 * (t**2))
                b_c = int(78 * (t**2))
            else:
                t = 1.0 - min(1.0, (y - horizon_y) / max(1, side - horizon_y))
                r_c = int(8 * (t**1.8))
                g_c = int(28 * (t**1.8))
                b_c = int(52 * (t**1.8))
            draw.line([(0, y), (side, y)], fill=(r_c, g_c, b_c))
        draw.line([(0, horizon_y), (side, horizon_y)], fill=(28, 96, 156), width=2)
        for deg in range(-75, 80, 15):
            rad = math.radians(deg)
            x_end = cx + int(math.sin(rad) * side * 0.9)
            draw.line([(cx, horizon_y), (x_end, side)], fill=(12, 38, 64), width=1)

    if width != side or height != side:
        left = (side - width) // 2
        top = (side - height) // 2
        return master.crop((left, top, left + width, top + height))
    return master


def render_builtin_preset_bytes(
    preset_id: str, width: int = 466, height: int = 466
) -> bytes:
    """Generate a crisp, low-power (>80% pure black) AMOLED procedural wallpaper as raw PNG bytes."""
    img = render_builtin_preset_image(preset_id, width, height)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_WALLPAPER_FILES_CACHE: dict[str, list[tuple[str, str]]] = {}


def _scan_wallpaper_dir_sync(wp_dir: Path, slug: str) -> list[tuple[str, str]]:
    """Scan uploaded wallpaper files in a worker thread and update the in-memory cache."""
    entries: list[tuple[str, str]] = []
    if wp_dir.is_dir():
        for file_path in sorted(wp_dir.glob("*"), key=lambda p: p.name.lower()):
            if file_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                source_id = make_upload_source(slug, file_path.name)
            except ValueError:
                continue
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


def known_wallpaper_ids(device_slug: str) -> set[str]:
    """Return the wallpaper IDs a Device may select: the built-in presets and its own cached uploads."""
    slug = normalize_device_slug(device_slug)
    return {p["id"] for p in BUILTIN_WALLPAPER_PRESETS} | {
        source_id for source_id, _ in _WALLPAPER_FILES_CACHE.get(slug, [])
    }


def list_wallpaper_catalog(
    hass: HomeAssistant,
    device_slug: str,
    active_source: str,
    favorites: list[str],
    *,
    sign_resource: Callable[[str], str] | None = None,
    display_shape: str = "circle",
) -> list[dict[str, Any]]:
    """Return built-in AMOLED presets + the Device's cached uploads, each with a signed Studio thumbnail URL."""
    fav_set = set(favorites or [])
    items: list[dict[str, Any]] = []
    slug = normalize_device_slug(device_slug)
    wp_shape = "square" if display_shape == "square" else "circle"

    def _build_thumb_url(src_id: str) -> str:
        if sign_resource is None:
            return ""
        sig = sign_resource(f"wallpaper:{src_id}|240|240|{wp_shape}")
        return (
            f"/api/latter/wallpaper/{slug}"
            f"?w=240&h=240&shape={wp_shape}&src={quote(src_id, safe='')}&sig={sig}"
        )

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
                "thumb_url": _build_thumb_url(pid),
            }
        )

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
                "thumb_url": _build_thumb_url(source_id),
            }
        )

    return items


def save_uploaded_wallpaper(
    hass: HomeAssistant,
    device_slug: str,
    filename: str,
    base64_data: str,
) -> str:
    """Decode a base64 image upload, save it as an RGB JPEG in the Device's private directory, and return its `upload:` ID."""
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
    source_id = make_upload_source(slug, out_name)
    from .http import evict_wallpaper_lru_cache

    evict_wallpaper_lru_cache(source_id)
    return source_id


def delete_uploaded_wallpaper(
    hass: HomeAssistant,
    device_slug: str,
    source_id: str,
) -> bool:
    """Delete one of this Device's uploads (an `upload:<slug>/<file>` ID with the Device's own slug)."""
    slug = normalize_device_slug(device_slug)
    parsed = parse_upload_source(source_id)
    if parsed is None or parsed[0] != slug:
        return False
    wp_dir = get_device_wallpaper_dir(hass, device_slug)
    target = resolve_upload_path(get_wallpaper_root(hass), source_id)
    if target is not None and target.is_file():
        target.unlink()
        _scan_wallpaper_dir_sync(wp_dir, slug)
        from .http import evict_wallpaper_lru_cache

        evict_wallpaper_lru_cache(source_id)
        return True
    return False