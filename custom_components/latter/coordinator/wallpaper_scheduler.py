"""Wallpaper and Photo Frame Screensaver pool resolution and rotation timers (`L3`)."""

from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval

from ..const import (
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DAY_NIGHT_SKY_NATIVE_URL,
    DAY_NIGHT_SKY_PRESET_ID,
    DEFAULT_SCREENSAVER_CYCLE_MINUTES,
    DEFAULT_SCREENSAVER_PHOTO_COLLECTION,
    DEFAULT_SCREENSAVER_PHOTO_MODE,
    DEFAULT_SCREENSAVER_SHUFFLE,
    DEFAULT_WALLPAPER_COLLECTION,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DEFAULT_WALLPAPER_MODE,
)
from ..wallpapers.pools import resolve_photo_pool
from .device_traits import CoordinatorTraitsMixin

_MIN_ROTATION_POOL_LEN = 2


class CoordinatorWallpaperMixin(CoordinatorTraitsMixin):
    """Wallpaper & Photo Frame Screensaver options, URL builders, and cycle timers."""

    @property
    def wallpaper_mode(self) -> str:
        raw = str(self.get_opt(CONF_WALLPAPER_MODE, "") or "").strip().lower()
        if raw in ("off", "single", "collection", "custom"):
            return raw
        if str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip():
            return "single"
        return DEFAULT_WALLPAPER_MODE

    @property
    def wallpaper_collection(self) -> str:
        return str(
            self.get_opt(CONF_WALLPAPER_COLLECTION, DEFAULT_WALLPAPER_COLLECTION) or ""
        ).strip()

    @property
    def configured_wallpaper_source(self) -> str:
        return str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()

    @configured_wallpaper_source.setter
    def configured_wallpaper_source(self, value: str) -> None:
        self._configured_wallpaper_source = str(value or "").strip()

    @callback
    def set_configured_wallpaper_source(self, value: str) -> None:
        """Record the last applied configured wallpaper source ID."""
        self._configured_wallpaper_source = str(value or "").strip()

    @property
    def wallpaper_source(self) -> str:
        if self.wallpaper_mode == "off":
            return ""
        pool = self.resolve_wallpaper_rotation_pool()
        if not pool:
            return ""
        if self.current_wallpaper in pool:
            return self.current_wallpaper
        cfg_src = self.configured_wallpaper_source
        if cfg_src in pool:
            return cfg_src
        return pool[0]

    @property
    def wallpaper_favorites(self) -> list[str]:
        val = self.get_opt(CONF_WALLPAPER_FAVORITES, [])
        return [str(x) for x in val] if isinstance(val, (list, tuple)) else []

    @property
    def wallpaper_cycle_minutes(self) -> int:
        try:
            return max(
                0,
                int(
                    self.get_opt(
                        CONF_WALLPAPER_CYCLE_MINUTES, DEFAULT_WALLPAPER_CYCLE_MINUTES
                    )
                ),
            )
        except (ValueError, TypeError):
            return 0

    @property
    def screensaver_photo_mode(self) -> str:
        raw = str(self.get_opt(CONF_SCREENSAVER_PHOTO_MODE, "") or "").strip().lower()
        if raw in ("off", "single", "collection", "custom"):
            return raw
        return DEFAULT_SCREENSAVER_PHOTO_MODE

    @property
    def screensaver_photo_collection(self) -> str:
        return str(
            self.get_opt(
                CONF_SCREENSAVER_PHOTO_COLLECTION, DEFAULT_SCREENSAVER_PHOTO_COLLECTION
            )
            or DEFAULT_SCREENSAVER_PHOTO_COLLECTION
        ).strip()

    @property
    def configured_screensaver_photo_source(self) -> str:
        return str(self.get_opt(CONF_SCREENSAVER_PHOTO_SOURCE, "") or "").strip()

    @property
    def screensaver_photo_ids(self) -> list[str]:
        val = self.get_opt(CONF_SCREENSAVER_PHOTO_IDS, [])
        return [str(x) for x in val] if isinstance(val, (list, tuple)) else []

    @property
    def screensaver_cycle_minutes(self) -> int:
        try:
            return max(
                0,
                int(
                    self.get_opt(
                        CONF_SCREENSAVER_CYCLE_MINUTES,
                        DEFAULT_SCREENSAVER_CYCLE_MINUTES,
                    )
                ),
            )
        except (ValueError, TypeError):
            return DEFAULT_SCREENSAVER_CYCLE_MINUTES

    @property
    def screensaver_shuffle(self) -> bool:
        return bool(
            self.get_opt(CONF_SCREENSAVER_SHUFFLE, DEFAULT_SCREENSAVER_SHUFFLE)
        )

    @property
    def screensaver_photo_frame_active(self) -> bool:
        return bool(
            self.has_display
            and self.get_device_pref("screensaver_style") == "Photo Frame"
            and self.get_device_pref("screensaver_mode") != "Never"
        )

    @property
    def screensaver_photo_source(self) -> str:
        pool = self.resolve_screensaver_photo_pool()
        if not pool:
            return ""
        if self.current_screensaver_photo in pool:
            return self.current_screensaver_photo
        cfg_src = self.configured_screensaver_photo_source
        if cfg_src in pool:
            return cfg_src
        return pool[0]

    def build_wallpaper_url(self) -> str:
        src = self.wallpaper_source
        if not src:
            return ""
        if src == DAY_NIGHT_SKY_PRESET_ID:
            return DAY_NIGHT_SKY_NATIVE_URL
        width, height = self.wallpaper_dimensions
        return self._url_signer.build_wallpaper_url(
            self.device_slug, src, width, height, self.display_shape, mode="wallpaper"
        )

    def build_screensaver_photo_url(self) -> str:
        if not self.screensaver_photo_frame_active:
            return ""
        src = self.screensaver_photo_source
        if not src:
            return ""
        width, height = self.wallpaper_dimensions
        return self._url_signer.build_wallpaper_url(
            self.device_slug, src, width, height, self.display_shape, mode="screensaver"
        )

    def resolve_wallpaper_rotation_pool(self) -> list[str]:
        """Return valid photo IDs in the Device's active Wallpaper pool."""
        return resolve_photo_pool(
            self.wallpaper_mode,
            self.configured_wallpaper_source,
            self.wallpaper_collection,
            self.wallpaper_favorites,
            include_dynamic=True,
        )

    def resolve_screensaver_photo_pool(self) -> list[str]:
        """Return valid photo IDs in the Device's Photo Frame Screensaver pool (dynamic presets excluded)."""
        return resolve_photo_pool(
            self.screensaver_photo_mode,
            self.configured_screensaver_photo_source,
            self.screensaver_photo_collection,
            self.screensaver_photo_ids,
            include_dynamic=False,
        )

    @callback
    def ensure_active_wallpaper_for_rotation(self) -> bool:
        """Seed an active wallpaper from the configured wallpaper pool."""
        if self.is_ble_tag:
            return False
        pool = self.resolve_wallpaper_rotation_pool()
        if not pool:
            if self.current_wallpaper:
                self.current_wallpaper = ""
                self.schedule_persist_runtime_state()
            return False
        if self.current_wallpaper in pool:
            return False
        cfg_src = self.configured_wallpaper_source
        self.current_wallpaper = cfg_src if cfg_src in pool else pool[0]
        self.schedule_persist_runtime_state()
        return True

    @callback
    def ensure_active_screensaver_photo(self) -> bool:
        """Seed or prune the active Photo Frame screensaver photo from the configured pool."""
        if self.is_ble_tag:
            return False
        pool = self.resolve_screensaver_photo_pool()
        if not pool or not self.screensaver_photo_frame_active:
            if self.current_screensaver_photo and self.current_screensaver_photo not in pool:
                self.current_screensaver_photo = ""
                self.schedule_persist_runtime_state()
            return False
        if self.current_screensaver_photo in pool:
            return False
        cfg_src = self.configured_screensaver_photo_source
        if cfg_src in pool:
            picked = cfg_src
        elif self.screensaver_shuffle and len(pool) >= _MIN_ROTATION_POOL_LEN:
            picked = secrets.choice(pool)
        else:
            picked = pool[0]
        self.current_screensaver_photo = picked
        self.schedule_persist_runtime_state()
        return True

    @callback
    def bind_wallpaper_cycle_timer(self) -> None:
        """Bind or refresh the periodic Wallpaper rotation interval timer."""
        if self._unsub_wallpaper_timer is not None:
            self._unsub_wallpaper_timer()
            self._unsub_wallpaper_timer = None

        self.ensure_active_wallpaper_for_rotation()
        mins = self.wallpaper_cycle_minutes
        if mins <= 0:
            return

        pool = self.resolve_wallpaper_rotation_pool()
        if self.wallpaper_source and len(pool) >= _MIN_ROTATION_POOL_LEN:

            @callback
            def _on_wallpaper_tick(_now: datetime) -> None:
                tick_pool = self.resolve_wallpaper_rotation_pool()
                if len(tick_pool) < _MIN_ROTATION_POOL_LEN:
                    return
                cur = self.wallpaper_source
                try:
                    idx = (tick_pool.index(cur) + 1) % len(tick_pool)
                except ValueError:
                    idx = 0
                self.current_wallpaper = tick_pool[idx]
                self.schedule_persist_runtime_state()
                self.async_notify_listeners()

            self._unsub_wallpaper_timer = async_track_time_interval(
                self.hass, _on_wallpaper_tick, timedelta(minutes=mins)
            )

    @callback
    def _bind_wallpaper_cycle_timer(self) -> None:
        self.bind_wallpaper_cycle_timer()

    @callback
    def bind_screensaver_cycle_timer(self) -> None:
        """Bind or refresh the periodic Photo Frame Screensaver rotation interval timer."""
        if self._unsub_screensaver_timer is not None:
            self._unsub_screensaver_timer()
            self._unsub_screensaver_timer = None

        if not self.screensaver_photo_frame_active:
            if self.current_screensaver_photo and (
                self.current_screensaver_photo not in self.resolve_screensaver_photo_pool()
            ):
                self.current_screensaver_photo = ""
                self.schedule_persist_runtime_state()
            return

        self.ensure_active_screensaver_photo()
        mins = self.screensaver_cycle_minutes
        if mins <= 0:
            return

        pool = self.resolve_screensaver_photo_pool()
        if self.screensaver_photo_source and len(pool) >= _MIN_ROTATION_POOL_LEN:

            @callback
            def _on_screensaver_tick(_now: datetime) -> None:
                if not self.screensaver_photo_frame_active:
                    return
                tick_pool = self.resolve_screensaver_photo_pool()
                if len(tick_pool) < _MIN_ROTATION_POOL_LEN:
                    return
                cur = self.screensaver_photo_source
                if self.screensaver_shuffle:
                    candidates = [p for p in tick_pool if p != cur]
                    self.current_screensaver_photo = secrets.choice(
                        candidates or tick_pool
                    )
                else:
                    try:
                        idx = (tick_pool.index(cur) + 1) % len(tick_pool)
                    except ValueError:
                        idx = 0
                    self.current_screensaver_photo = tick_pool[idx]
                self.schedule_persist_runtime_state()
                self.async_notify_listeners()

            self._unsub_screensaver_timer = async_track_time_interval(
                self.hass, _on_screensaver_tick, timedelta(minutes=mins)
            )

    @callback
    def _bind_screensaver_cycle_timer(self) -> None:
        self.bind_screensaver_cycle_timer()
