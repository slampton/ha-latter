"""Latter Studio custom panel registration, asset digest helper, and lifecycle management."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import DOMAIN, INTEGRATION_VERSION
from ..hub_registry import get_domain_data, peek_domain_data
from .commands import async_register_studio_ws_commands
from .payload import load_studio_locales_sync, log_studio_event

_LOGGER = logging.getLogger(__name__)

STATIC_URL_PREFIX = "/latter_ui"
ICONS_MODULE = "latter-icons.js"
SIDEBAR_ICON = "latter:logo"
SIDEBAR_ICON_FALLBACK = "mdi:ladder"


def content_digest(path: Path) -> str:
    """Return a short SHA-256 digest of a file, used as the panel module's cache-buster (executor)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


async def _async_ensure_static_dir(hass: HomeAssistant) -> tuple[Path, str]:
    """Mount the versioned Studio frontend directory once and return `(frontend_dir, prefix)`."""
    domain_data = get_domain_data(hass)
    frontend_dir = Path(__file__).parent.parent / "frontend"
    cache_tag = INTEGRATION_VERSION.replace(".", "_")
    versioned_prefix = f"{STATIC_URL_PREFIX}_{cache_tag}"

    registered_prefixes = domain_data.studio_static_prefixes
    if versioned_prefix not in registered_prefixes:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    versioned_prefix,
                    str(frontend_dir),
                    cache_headers=True,
                )
            ]
        )
        registered_prefixes.add(versioned_prefix)
    return frontend_dir, versioned_prefix


async def async_register_studio_icon_module(hass: HomeAssistant) -> str | None:
    """Register `latter-icons.js` as a frontend extra module as early as possible (idempotent)."""
    domain_data = get_domain_data(hass)
    frontend_dir, versioned_prefix = await _async_ensure_static_dir(hass)
    prev_icon_url = domain_data.studio_icon_js_url
    if prev_icon_url and prev_icon_url.startswith(
        f"{versioned_prefix}/{ICONS_MODULE}?v="
    ):
        return prev_icon_url

    try:
        icon_digest = await hass.async_add_executor_job(
            content_digest, frontend_dir / ICONS_MODULE
        )
    except OSError as err:
        _LOGGER.warning(
            "Latter sidebar icon unavailable, using %s: %s", SIDEBAR_ICON_FALLBACK, err
        )
        return None

    icon_url = f"{versioned_prefix}/{ICONS_MODULE}?v={icon_digest}"
    if prev_icon_url:
        try:
            frontend.remove_extra_js_url(hass, prev_icon_url)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Previous Studio icon extra_js removal skipped: %s", err)

    frontend.add_extra_js_url(hass, icon_url)
    domain_data.studio_icon_js_url = icon_url
    return icon_url


async def async_register_studio_panel(hass: HomeAssistant) -> None:
    """Register Latter Studio static assets, admin WebSocket commands, and `panel_custom` sidebar panel."""
    domain_data = get_domain_data(hass)
    icon_url = await async_register_studio_icon_module(hass)
    await hass.async_add_executor_job(load_studio_locales_sync)
    async_register_studio_ws_commands(hass)

    frontend_dir, versioned_prefix = await _async_ensure_static_dir(hass)
    sidebar_icon = SIDEBAR_ICON if icon_url else SIDEBAR_ICON_FALLBACK

    js_digest = await hass.async_add_executor_job(
        content_digest, frontend_dir / "latter-studio.js"
    )
    module_url = f"{versioned_prefix}/latter-studio.js?v={js_digest}"
    if domain_data.registered_panel_url == module_url:
        return
    try:
        frontend.async_remove_panel(hass, "latter", warn_if_unknown=False)
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path="latter",
            webcomponent_name="latter-studio",
            module_url=module_url,
            sidebar_title="Latter",
            sidebar_icon=sidebar_icon,
            require_admin=True,
            embed_iframe=False,
            config_panel_domain=DOMAIN,
        )
        domain_data.registered_panel_url = module_url
        log_studio_event(
            hass,
            "INFO",
            "studio",
            f"Registered Latter Studio v{INTEGRATION_VERSION} panel_custom ({module_url})",
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Latter Studio panel_custom registration failed: %s", err)


def async_unregister_studio_panel(
    hass: HomeAssistant, *, remove_icon_module: bool = False
) -> None:
    """Remove the Latter Studio custom panel; keep `latter-icons.js` across reloads unless removing the entry."""
    domain_data = peek_domain_data(hass)
    icon_url = None
    if domain_data is not None:
        domain_data.registered_panel_url = None
        if remove_icon_module:
            icon_url = domain_data.studio_icon_js_url
            domain_data.studio_icon_js_url = None
    try:
        frontend.async_remove_panel(hass, "latter", warn_if_unknown=False)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Latter Studio panel_custom removal skipped: %s", err)
    if icon_url:
        try:
            frontend.remove_extra_js_url(hass, icon_url)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Latter Studio icon extra_js removal skipped: %s", err)


__all__ = [
    "ICONS_MODULE",
    "SIDEBAR_ICON",
    "SIDEBAR_ICON_FALLBACK",
    "STATIC_URL_PREFIX",
    "async_register_studio_icon_module",
    "async_register_studio_panel",
    "async_unregister_studio_panel",
    "content_digest",
]
