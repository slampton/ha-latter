"""Latter Studio custom panel and admin WebSocket API package."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import DOMAIN, INTEGRATION_VERSION
from .assets import content_digest
from .commands import async_register_studio_ws_commands
from .payload import (
    LatterBrandIconView,
    build_studio_state_payload,
    log_studio_event,
)

_LOGGER = logging.getLogger(__name__)

STATIC_URL_PREFIX = "/latter_ui"
ICONS_MODULE = "latter-icons.js"
SIDEBAR_ICON = "latter:logo"
SIDEBAR_ICON_FALLBACK = "mdi:ladder"

__all__ = [
    "LatterBrandIconView",
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
    cache_tag = INTEGRATION_VERSION.replace(".", "_")
    versioned_prefix = f"{STATIC_URL_PREFIX}_{cache_tag}"

    static_configs: list[StaticPathConfig] = []
    registered_prefixes: set[str] = domain_data.setdefault(
        "_studio_static_prefixes", set()
    )
    for prefix in (versioned_prefix, STATIC_URL_PREFIX, "/latter_static"):
        if prefix not in registered_prefixes:
            registered_prefixes.add(prefix)
            static_configs.append(
                StaticPathConfig(
                    prefix,
                    str(frontend_dir),
                    cache_headers=False,
                )
            )
    if static_configs:
        await hass.http.async_register_static_paths(static_configs)

    # The sidebar icon: a tiny frontend module registers "latter:logo" (window.customIcons, D-017). It's
    # loaded on every Home Assistant page, cache-busted by its content like the panel JS, and removed with
    # the panel. If it can't be registered, the panel falls back to an MDI icon.
    sidebar_icon = SIDEBAR_ICON_FALLBACK
    icon_url = domain_data.get("_studio_icon_js_url")
    if not icon_url:
        try:
            icon_digest = await hass.async_add_executor_job(
                content_digest, frontend_dir / ICONS_MODULE
            )
            icon_url = f"{versioned_prefix}/{ICONS_MODULE}?v={icon_digest}"
            frontend.add_extra_js_url(hass, icon_url)
            domain_data["_studio_icon_js_url"] = icon_url
        except OSError as err:
            icon_url = None
            _LOGGER.warning("Latter sidebar icon unavailable, using %s: %s", SIDEBAR_ICON_FALLBACK, err)
    if icon_url:
        sidebar_icon = SIDEBAR_ICON

    # The cache-buster follows the JS content, so every change to latter-studio.js reaches the
    # browser without a hard refresh (a cached old panel would be ignored as a stale client).
    js_digest = domain_data.get("_studio_js_digest")
    if not js_digest:
        js_digest = await hass.async_add_executor_job(
            content_digest, frontend_dir / "latter-studio.js"
        )
        domain_data["_studio_js_digest"] = js_digest
    module_url = f"{versioned_prefix}/latter-studio.js?v={js_digest}"
    panels = hass.data.get("frontend_panels", {})
    if (
        domain_data.get("_registered_panel_url") == module_url
        and "latter" in panels
    ):
        return
    try:
        if "latter" in panels:
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
        )
        domain_data["_registered_panel_url"] = module_url
        log_studio_event(
            hass,
            "INFO",
            "studio",
            f"Registered Latter Studio v{INTEGRATION_VERSION} panel_custom ({module_url})",
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Latter Studio panel_custom registration failed: %s", err)


def async_unregister_studio_panel(hass: HomeAssistant) -> None:
    """Remove the Latter Studio custom panel, and its sidebar icon module, when the integration is removed."""
    domain_data = hass.data.get(DOMAIN, {})
    icon_url = None
    if isinstance(domain_data, dict):
        domain_data.pop("_registered_panel_url", None)
        icon_url = domain_data.pop("_studio_icon_js_url", None)
    try:
        frontend.async_remove_panel(hass, "latter", warn_if_unknown=False)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Latter Studio panel_custom removal skipped: %s", err)
    if icon_url:
        frontend.remove_extra_js_url(hass, icon_url)
