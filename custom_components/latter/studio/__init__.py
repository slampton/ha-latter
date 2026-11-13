"""Latter Studio custom panel registration, asset digest helper, and lifecycle management."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

STATIC_URL_PREFIX = "/latter_ui"
ICONS_MODULE = "latter-icons.js"
SIDEBAR_ICON = "latter:logo"
SIDEBAR_ICON_FALLBACK = "mdi:ladder"


def content_digest(path: Path) -> str:
    """Return a short SHA-256 digest of a file, used as the panel module's cache-buster (executor)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


async def async_register_studio_panel(hass: HomeAssistant) -> None:
    """Register Latter Studio static assets, admin WebSocket commands, and `panel_custom` sidebar panel."""
    from .commands import async_register_studio_ws_commands
    from .payload import log_studio_event

    domain_data = hass.data.setdefault(DOMAIN, {})
    # Always recompute asset digests on setup/reload so HACS upgrades never serve stale cached JS.
    domain_data.pop("_studio_js_digest", None)
    prev_icon_url = domain_data.pop("_studio_icon_js_url", None)
    if prev_icon_url:
        try:
            frontend.remove_extra_js_url(hass, prev_icon_url)
        except Exception:  # noqa: BLE001
            pass

    async_register_studio_ws_commands(hass)

    frontend_dir = Path(__file__).parent.parent / "frontend"
    cache_tag = INTEGRATION_VERSION.replace(".", "_")
    versioned_prefix = f"{STATIC_URL_PREFIX}_{cache_tag}"

    registered_prefixes: set[str] = domain_data.setdefault(
        "_studio_static_prefixes", set()
    )
    if versioned_prefix not in registered_prefixes:
        registered_prefixes.add(versioned_prefix)
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    versioned_prefix,
                    str(frontend_dir),
                    cache_headers=False,
                )
            ]
        )

    sidebar_icon = SIDEBAR_ICON_FALLBACK
    icon_url: str | None = None
    try:
        icon_digest = await hass.async_add_executor_job(
            content_digest, frontend_dir / ICONS_MODULE
        )
        icon_url = f"{versioned_prefix}/{ICONS_MODULE}?v={icon_digest}"
        frontend.add_extra_js_url(hass, icon_url)
        domain_data["_studio_icon_js_url"] = icon_url
    except OSError as err:
        icon_url = None
        _LOGGER.warning(
            "Latter sidebar icon unavailable, using %s: %s", SIDEBAR_ICON_FALLBACK, err
        )
    if icon_url:
        sidebar_icon = SIDEBAR_ICON

    js_digest = await hass.async_add_executor_job(
        content_digest, frontend_dir / "latter-studio.js"
    )
    domain_data["_studio_js_digest"] = js_digest
    module_url = f"{versioned_prefix}/latter-studio.js?v={js_digest}"
    panels = hass.data.get("frontend_panels", {})
    if domain_data.get("_registered_panel_url") == module_url and "latter" in panels:
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
    """Remove the Latter Studio custom panel and clear cached digests/resources on unload."""
    domain_data = hass.data.get(DOMAIN, {})
    icon_url = None
    if isinstance(domain_data, dict):
        domain_data.pop("_registered_panel_url", None)
        domain_data.pop("_studio_js_digest", None)
        icon_url = domain_data.pop("_studio_icon_js_url", None)
    try:
        frontend.async_remove_panel(hass, "latter", warn_if_unknown=False)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Latter Studio panel_custom removal skipped: %s", err)
    if icon_url:
        try:
            frontend.remove_extra_js_url(hass, icon_url)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Latter Studio icon extra_js removal skipped: %s", err)
