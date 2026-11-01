"""Latter Studio custom panel and admin WebSocket API package."""

from __future__ import annotations

import logging
from pathlib import Path
import time

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import DOMAIN, INTEGRATION_VERSION
from .commands import async_register_studio_ws_commands
from .payload import (
    LatterBrandIconView,
    LatterSidebarIconJsView,
    build_studio_state_payload,
    log_studio_event,
)

_LOGGER = logging.getLogger(__name__)

STATIC_URL_PREFIX = "/latter_ui"

__all__ = [
    "LatterBrandIconView",
    "LatterSidebarIconJsView",
    "async_register_studio_panel",
    "async_register_studio_ws_commands",
    "async_unregister_studio_panel",
    "build_studio_state_payload",
    "log_studio_event",
]


async def async_register_studio_panel(hass: HomeAssistant) -> None:
    """Register Latter Studio static assets, admin WebSocket commands, and `panel_custom` sidebar panel."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    async_register_studio_ws_commands(hass)

    frontend_dir = Path(__file__).parent.parent / "frontend"
    cache_tag = f"{INTEGRATION_VERSION.replace('.', '_')}_{int(time.time())}"
    versioned_prefix = f"{STATIC_URL_PREFIX}_{cache_tag}"

    static_configs = [
        StaticPathConfig(
            versioned_prefix,
            str(frontend_dir),
            cache_headers=False,
        )
    ]
    if not domain_data.get("_studio_static_registered"):
        domain_data["_studio_static_registered"] = True
        static_configs.extend(
            [
                StaticPathConfig(
                    STATIC_URL_PREFIX,
                    str(frontend_dir),
                    cache_headers=False,
                ),
                StaticPathConfig(
                    "/latter_static",
                    str(frontend_dir),
                    cache_headers=False,
                ),
            ]
        )
        frontend.add_extra_js_url(hass, "/api/latter/brand/sidebar_icon.js")

    await hass.http.async_register_static_paths(static_configs)

    module_url = f"{versioned_prefix}/latter-studio.js?v={cache_tag}"
    try:
        frontend.async_remove_panel(hass, "latter", warn_if_unknown=False)
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path="latter",
            webcomponent_name="latter-studio",
            module_url=module_url,
            sidebar_title="Latter",
            sidebar_icon="latter:logo",
            require_admin=True,
            embed_iframe=False,
        )
        log_studio_event(
            hass,
            "INFO",
            "studio",
            f"Registered Latter Studio v{INTEGRATION_VERSION} panel_custom ({module_url})",
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Latter Studio panel_custom registration failed: %s", err)


def async_unregister_studio_panel(hass: HomeAssistant) -> None:
    """Remove the Latter Studio custom panel when the integration unloads."""
    try:
        frontend.async_remove_panel(hass, "latter", warn_if_unknown=False)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Latter Studio panel_custom removal skipped: %s", err)
