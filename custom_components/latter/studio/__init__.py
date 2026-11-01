"""Latter Studio custom panel and admin WebSocket API package."""

from __future__ import annotations

import logging
from pathlib import Path

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

STATIC_URL_PREFIX = "/latter_static"

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

    if not domain_data.get("_studio_static_registered"):
        domain_data["_studio_static_registered"] = True
        frontend_dir = Path(__file__).parent.parent / "frontend"
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL_PREFIX,
                    str(frontend_dir),
                    cache_headers=False,
                )
            ]
        )
        frontend.add_extra_js_url(hass, "/api/latter/brand/sidebar_icon.js")

    try:
        if "latter" in hass.data.get(frontend.DATA_PANELS, {}):
            frontend.async_remove_panel(hass, "latter")
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path="latter",
            webcomponent_name="latter-studio",
            module_url=f"{STATIC_URL_PREFIX}/latter-studio.js?v={INTEGRATION_VERSION}",
            sidebar_title="Latter",
            sidebar_icon="latter:logo",
            require_admin=True,
            embed_iframe=False,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Latter Studio panel_custom registration skipped: %s", err)


def async_unregister_studio_panel(hass: HomeAssistant) -> None:
    """Remove the Latter Studio custom panel when the integration unloads."""
    try:
        if "latter" in hass.data.get(frontend.DATA_PANELS, {}):
            frontend.async_remove_panel(hass, "latter")
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Latter Studio panel_custom removal skipped: %s", err)
