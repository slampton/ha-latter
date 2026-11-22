"""Shared controls and entity catalog builders for Latter Studio (`L3`)."""

from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any, Final, TypedDict, Unpack

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar

from ..cameras.capabilities import resolve_camera_capabilities
from ..const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_BLE_AUTO_SWITCH,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN_POLICY,
    CONF_SYNC_DEVICE_AREA,
    CONF_TOOLS_ITEMS,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
)
from ..coordinator import LatterCoordinator
from ..doorbell_targets import resolve_doorbell_ring_entities
from ..groups.device_groups import (
    coordinator_supports_pref,
    resolve_behavior_key_value,
)
from ..hub_registry import get_area_state_index, iter_coordinators
from ..media.linking import is_music_assistant_player, ma_player_entities
from ..protocol_policy import resolve_shortcut_entity_icon
from ..protocol_specs import (
    ACTIVITY_SOURCES_CATALOG,
    AREA_CATEGORIES_CATALOG,
    DEVICE_PREF_SPECS,
    GAMES_ITEMS_CATALOG,
    HOME_CATEGORIES_CATALOG,
    SHORTCUT_SUPPORTED_DOMAINS,
    TOOLS_ITEMS_CATALOG,
    resolve_device_pref_value,
)
from ..wallpapers.models import (
    VIRTUAL_COLLECTION_ALL,
    VIRTUAL_COLLECTION_DEFAULTS,
    VIRTUAL_COLLECTION_UNCATEGORIZED,
    VIRTUAL_COLLECTION_UPLOADS,
)
from ..wallpapers.pools import list_photo_collections, list_wallpaper_catalog
from .payload_shared import (
    STUDIO_BULK_CONTROL_DOMAINS,
    build_device_prefs_payload,
    build_pref_specs_catalog,
    build_quick_actions_payload,
    build_speaker_volume_payload,
    is_coordinator_online_for_studio,
)
from .settings_cleaners import system_settings_view

_MUSIC_SUFFIX_LEN: Final = 6
_SHARED_SECTION_FALLBACK_ORDER: Final = 99

_CATALOG_DOMAINS: Final[tuple[str, ...]] = (
    "media_player", "remote", "number", "input_number", "alarm_control_panel",
    "camera", "climate", "lock", "cover", "vacuum", "weather", "calendar", "person",
)
_SHARED_SECTION_TITLES: Final[dict[str, str]] = {
    "display": "Display", "interface": "Interface", "audio": "Audio",
    "power": "Power", "presence": "Presence", "security": "Security",
}
_SHARED_SECTION_ORDER: Final[dict[str, int]] = {
    "display": 0, "interface": 1, "audio": 2,
    "power": 3, "presence": 4, "security": 5,
}

_CoordMeta = list[tuple[LatterCoordinator, bool, bool]]


class _ControlExtraOpts(TypedDict, total=False):
    state: str
    options: list[str]
    option_labels: dict[str, str]
    min_val: int | float | None
    max_val: int | float | None
    step: int | float | None
    unit: str


def _make_shared_control(
    ident: tuple[str, str | None, str, str],
    name: str,
    targets: list[dict[str, Any]],
    **opts: Unpack[_ControlExtraOpts],
) -> dict[str, Any]:
    """Construct a canonical `StudioSharedControlItem` entry."""
    pref_key, tier, section, domain = ident
    entry: dict[str, Any] = {
        "key": f"{section}:{domain}:{name.lower()}",
        "pref_key": pref_key,
        "tier": tier,
        "section": section,
        "section_title": _SHARED_SECTION_TITLES.get(section, section.title()),
        "name": name,
        "domain": domain,
        "state": opts.get("state", ""),
        "options": opts.get("options", []),
        "min": opts.get("min_val"),
        "max": opts.get("max_val"),
        "step": opts.get("step"),
        "unit": opts.get("unit", ""),
        "targets": targets,
    }
    if "option_labels" in opts:
        entry["option_labels"] = opts["option_labels"]
    return entry


def _targets_for_shared_control(
    coord_meta: _CoordMeta,
    conf_key: str,
    state_fn: Callable[[LatterCoordinator], str],
    *,
    roaming_only: bool = False,
    display_only: bool = False,
) -> list[dict[str, Any]]:
    """Collect per-Device state targets for a shared System control."""
    return [
        {
            "device_slug": coord.device_slug,
            "device_group": coord.device_group,
            "is_online": is_online,
            "is_roaming": is_roaming,
            "pref_key": conf_key,
            "state": str(state_fn(coord)),
        }
        for coord, is_online, is_roaming in coord_meta
        if (not roaming_only or is_roaming)
        and (not display_only or coord.has_display)
    ]


def _append_pref_spec_shared_controls(
    controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append native `DEVICE_PREF_SPECS` entries into `controls`."""
    for spec in DEVICE_PREF_SPECS:
        if (
            spec.group_tier is None
            and spec.key not in ("bedtime_active", "do_not_disturb")
        ) or spec.domain not in STUDIO_BULK_CONTROL_DOMAINS:
            continue
        targets: list[dict[str, Any]] = []
        for coord, is_online, is_roaming in coord_meta:
            if not coordinator_supports_pref(coord, spec):
                continue
            cur_val = resolve_device_pref_value(coord.device_data, spec.key)
            if (
                spec.key == "clock_face"
                and not coord.is_round_display
                and cur_val == "Modern Analog"
            ):
                cur_val = "Minimal Digital"
            state_val = (
                ("on" if cur_val else "off")
                if spec.domain == "switch"
                else str(cur_val)
            )
            targets.append(
                {
                    "device_slug": coord.device_slug,
                    "device_group": coord.device_group,
                    "is_online": is_online,
                    "is_roaming": is_roaming,
                    "pref_key": spec.key,
                    "state": state_val,
                }
            )
        if targets:
            def_state = (
                ("on" if spec.default else "off")
                if spec.domain == "switch"
                else str(spec.default)
            )
            controls.append(
                _make_shared_control(
                    (spec.key, spec.group_tier, spec.section, spec.domain),
                    spec.label,
                    targets,
                    state=def_state,
                    options=list(spec.options),
                    min_val=spec.min_val,
                    max_val=spec.max_val,
                    step=spec.step,
                    unit=spec.unit,
                )
            )


def _append_behavior_shared_controls(
    controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append presence, audio handoff, dwell, and perimeter security controls."""
    for conf_key, label, sec_id, roaming_only in (
        (CONF_NATIVE_BLE_TRACKING, "Track the Area with BLE Proxies", "presence", False),
        (CONF_BLE_AUTO_SWITCH, "Auto-Switch Active Area", "presence", False),
        (CONF_SYNC_DEVICE_AREA, "Voice Follows Me", "audio", True),
        (CONF_AREA_HANDOFF, "Media Follows Device to New Area", "audio", False),
    ):
        def _switch_val(
            coord: LatterCoordinator, ck: str = conf_key
        ) -> str:
            return (
                "on"
                if bool(resolve_behavior_key_value(coord.device_data, ck))
                else "off"
            )

        targets = _targets_for_shared_control(
            coord_meta,
            conf_key,
            _switch_val,
            roaming_only=roaming_only,
        )
        if targets:
            controls.append(
                _make_shared_control(
                    (conf_key, "behavior", sec_id, "switch"),
                    label,
                    targets,
                    state="off",
                )
            )

    dwell_targets = _targets_for_shared_control(
        coord_meta,
        CONF_AREA_FOLLOW_DWELL_S,
        lambda c: str(resolve_behavior_key_value(c.device_data, CONF_AREA_FOLLOW_DWELL_S)),
        roaming_only=True,
    )
    if dwell_targets:
        controls.append(
            _make_shared_control(
                (CONF_AREA_FOLLOW_DWELL_S, "behavior", "audio", "number"),
                "Area Follow Dwell",
                dwell_targets,
                state="10",
                min_val=3,
                max_val=60,
                step=1,
                unit="s",
            )
        )

    pin_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SECURITY_PIN_POLICY,
        lambda c: str(resolve_behavior_key_value(c.device_data, CONF_SECURITY_PIN_POLICY)),
    )
    if pin_targets:
        controls.append(
            _make_shared_control(
                (CONF_SECURITY_PIN_POLICY, "behavior", "security", "select"),
                "Perimeter Security Policy",
                pin_targets,
                state="auto",
                options=["auto", "allow", "require_pin", "block"],
                option_labels={
                    "auto": "Auto (Roaming Requires PIN)",
                    "allow": "Allow Without PIN",
                    "require_pin": "Always Require PIN",
                    "block": "Block Sensitive Actions",
                },
            )
        )


def _append_display_shared_controls(
    hass: HomeAssistant, controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append custom color, wallpaper, and Photo Frame screensaver controls."""
    color_targets = _targets_for_shared_control(
        coord_meta, CONF_DEVICE_CUSTOM_COLOR, lambda c: c.device_custom_color, display_only=True
    )
    if color_targets:
        controls.append(
            _make_shared_control(
                (CONF_DEVICE_CUSTOM_COLOR, "display", "display", "color"),
                "Custom Accent Color",
                color_targets,
                state="#3898FF",
            )
        )

    wp_targets = _targets_for_shared_control(
        coord_meta, CONF_WALLPAPER_SOURCE, lambda c: c.wallpaper_source, display_only=True
    )
    if wp_targets:
        sys_wps = list_wallpaper_catalog(
            hass, "system", "", [], sign_resource=None, display_shape="square"
        )
        wp_opts: list[str] = [""]
        wp_labels: dict[str, str] = {"": "None (Weather / Solid)"}
        for wp in sys_wps:
            sid = str(wp.get("id") or "").strip()
            if sid and sid not in wp_labels:
                wp_opts.append(sid)
                wp_labels[sid] = str(wp.get("name") or wp.get("label") or sid)
        controls.append(
            _make_shared_control(
                (CONF_WALLPAPER_SOURCE, "display", "display", "select"),
                "Wallpaper",
                wp_targets,
                options=wp_opts,
                option_labels=wp_labels,
            )
        )

    wp_rot_targets = _targets_for_shared_control(
        coord_meta,
        CONF_WALLPAPER_CYCLE_MINUTES,
        lambda c: str(c.wallpaper_cycle_minutes),
        display_only=True,
    )
    if wp_rot_targets:
        controls.append(
            _make_shared_control(
                (CONF_WALLPAPER_CYCLE_MINUTES, "display", "display", "select"),
                "Wallpaper Rotation",
                wp_rot_targets,
                state="0",
                options=["0", "5", "15", "30", "60", "360", "1440"],
                option_labels={
                    "0": "Off (Static)",
                    "5": "Every 5 min",
                    "15": "Every 15 min",
                    "30": "Every 30 min",
                    "60": "Every 1 hr",
                    "360": "Every 6 hr",
                    "1440": "Every 24 hr",
                },
            )
        )

    col_opts = [
        VIRTUAL_COLLECTION_ALL,
        VIRTUAL_COLLECTION_DEFAULTS,
        VIRTUAL_COLLECTION_UPLOADS,
        VIRTUAL_COLLECTION_UNCATEGORIZED,
    ]
    col_labels: dict[str, str] = {
        VIRTUAL_COLLECTION_ALL: "All photos",
        VIRTUAL_COLLECTION_DEFAULTS: "Defaults",
        VIRTUAL_COLLECTION_UPLOADS: "My photos",
        VIRTUAL_COLLECTION_UNCATEGORIZED: "Uncategorized",
    }
    for col in list_photo_collections():
        cid = str(col.get("id") or "").strip()
        if cid and cid not in col_labels:
            col_opts.append(cid)
            col_labels[cid] = str(col.get("name") or cid)

    wp_col_targets = _targets_for_shared_control(
        coord_meta, CONF_WALLPAPER_COLLECTION, lambda c: c.wallpaper_collection, display_only=True
    )
    if wp_col_targets:
        controls.append(
            _make_shared_control(
                (CONF_WALLPAPER_COLLECTION, "display", "display", "select"),
                "Wallpaper collection",
                wp_col_targets,
                options=["", *col_opts],
                option_labels={"": "Not using a collection", **col_labels},
            )
        )

    ss_col_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SCREENSAVER_PHOTO_COLLECTION,
        lambda c: c.screensaver_photo_collection,
        display_only=True,
    )
    if ss_col_targets:
        controls.append(
            _make_shared_control(
                (CONF_SCREENSAVER_PHOTO_COLLECTION, "display", "display", "select"),
                "Photo Frame collection",
                ss_col_targets,
                state=VIRTUAL_COLLECTION_ALL,
                options=col_opts,
                option_labels=col_labels,
            )
        )

    ss_rot_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SCREENSAVER_CYCLE_MINUTES,
        lambda c: str(c.screensaver_cycle_minutes),
        display_only=True,
    )
    if ss_rot_targets:
        controls.append(
            _make_shared_control(
                (CONF_SCREENSAVER_CYCLE_MINUTES, "display", "display", "select"),
                "Photo Frame rotation",
                ss_rot_targets,
                state="5",
                options=["0", "1", "5", "15", "30", "60"],
                option_labels={
                    "0": "Off (Static)",
                    "1": "Every 1 min",
                    "5": "Every 5 min",
                    "15": "Every 15 min",
                    "30": "Every 30 min",
                    "60": "Every 1 hr",
                },
            )
        )

    ss_shuf_targets = _targets_for_shared_control(
        coord_meta,
        CONF_SCREENSAVER_SHUFFLE,
        lambda c: "on" if c.screensaver_shuffle else "off",
        display_only=True,
    )
    if ss_shuf_targets:
        controls.append(
            _make_shared_control(
                (CONF_SCREENSAVER_SHUFFLE, "display", "display", "switch"),
                "Shuffle Photo Frame photos",
                ss_shuf_targets,
                state="off",
            )
        )


def _append_interface_shared_controls(
    hass: HomeAssistant, controls: list[dict[str, Any]], coord_meta: _CoordMeta
) -> None:
    """Append interface pill catalogs and remote control scope controls."""
    act_card_targets = _targets_for_shared_control(
        coord_meta,
        CONF_ACTIVITY_CARD,
        lambda c: "on" if c.activity_card_enabled else "off",
        display_only=True,
    )
    if act_card_targets:
        controls.append(
            _make_shared_control(
                (CONF_ACTIVITY_CARD, "interface", "interface", "switch"),
                "Home Activity Card",
                act_card_targets,
                state="on",
            )
        )

    for conf_key, label, min_count, catalog, getter in (
        (
            CONF_ACTIVITY_SOURCES,
            "Activity Card Sources",
            0,
            ACTIVITY_SOURCES_CATALOG,
            lambda c: c.activity_sources_csv,
        ),
        (
            CONF_HOME_CATEGORIES,
            "Home Hub Categories",
            1,
            HOME_CATEGORIES_CATALOG,
            lambda c: c.home_categories_csv,
        ),
        (
            CONF_AREA_CATEGORIES,
            "Area Control Categories",
            1,
            AREA_CATEGORIES_CATALOG,
            lambda c: c.area_categories_csv,
        ),
        (CONF_TOOLS_ITEMS, "Tools", 1, TOOLS_ITEMS_CATALOG, lambda c: c.tools_items_csv),
        (CONF_GAMES_ITEMS, "Games", 1, GAMES_ITEMS_CATALOG, lambda c: c.games_items_csv),
    ):
        targets = _targets_for_shared_control(coord_meta, conf_key, getter, display_only=True)
        if targets:
            controls.append(
                _make_shared_control(
                    (conf_key, "interface", "interface", "pills"),
                    label,
                    targets,
                    options=[str(c["token"]) for c in catalog],
                    option_labels={str(c["token"]): str(c["label"]) for c in catalog},
                    min_val=min_count,
                )
            )

    rem_targets = _targets_for_shared_control(
        coord_meta, CONF_DEVICE_REMOTE_GROUP, lambda c: c.device_remote_group, display_only=True
    )
    if rem_targets:
        raw_global_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
        rem_groups = system_settings_view(raw_global_cfg).get("remote_groups") or []
        rem_opts: list[str] = ["area_auto"]
        rem_labels: dict[str, str] = {"area_auto": "Match Active Area"}
        for rg in rem_groups:
            rg_id = f"group:{rg['id']}"
            rem_opts.append(rg_id)
            rem_labels[rg_id] = f"Group: {rg['name']}"
        rem_opts.append("all")
        rem_labels["all"] = "All System Remotes"
        controls.append(
            _make_shared_control(
                (CONF_DEVICE_REMOTE_GROUP, "interface", "interface", "select"),
                "Remote Control Scope",
                rem_targets,
                state="area_auto",
                options=rem_opts,
                option_labels=rem_labels,
            )
        )


def build_system_shared_controls(
    hass: HomeAssistant,
    coords: list[LatterCoordinator] | None = None,
) -> list[dict[str, Any]]:
    """Build tab-aligned shared controls across all onboarded Latter Devices."""
    all_coords = [
        c
        for c in (coords if coords is not None else iter_coordinators(hass))
        if not c.is_ble_tag
    ]
    coord_meta: _CoordMeta = [
        (c, is_coordinator_online_for_studio(hass, c), c.is_roaming_device)
        for c in all_coords
    ]
    controls: list[dict[str, Any]] = []
    _append_pref_spec_shared_controls(controls, coord_meta)
    _append_behavior_shared_controls(controls, coord_meta)
    _append_display_shared_controls(hass, controls, coord_meta)
    _append_interface_shared_controls(hass, controls, coord_meta)

    return sorted(
        controls,
        key=lambda x: (
            _SHARED_SECTION_ORDER.get(x["section"], _SHARED_SECTION_FALLBACK_ORDER),
            x["name"].lower(),
        ),
    )


_build_system_shared_controls = build_system_shared_controls


def _is_garage_cover_state(state_obj: Any) -> bool:
    """Return True strictly for garage door `cover.*` entities."""
    dev_class = str(state_obj.attributes.get("device_class") or "").strip().lower()
    if dev_class == "garage":
        return True
    if dev_class != "":
        return False
    friendly = str(state_obj.attributes.get("friendly_name") or "")
    return "garage" in f"{state_obj.entity_id} {friendly}".lower()


def _enrich_hub_catalog_item(
    base_item: dict[str, str], state_obj: Any, idx: Any, area_reg: ar.AreaRegistry
) -> dict[str, Any]:
    """Attach `area_name` for Studio Home Hub & Camera catalog entries."""
    enriched: dict[str, Any] = dict(base_item)
    area_id = idx.resolve_entity_area_id(state_obj.entity_id) or ""
    area_entry = area_reg.async_get_area(area_id) if area_id else None
    if area_entry is not None:
        enriched["area_name"] = area_entry.name
    return enriched


def _extract_volume_overrides_map(hass: HomeAssistant) -> dict[str, str]:
    """Read System `volume_overrides` into a `{speaker_entity: target_entity}` map."""
    global_cfg = (hass.data.get(DOMAIN, {}) or {}).get(DATA_GLOBAL_CONFIG) or {}
    raw_vol_ov = global_cfg.get("volume_overrides")
    vol_overrides_map: dict[str, str] = {}
    if isinstance(raw_vol_ov, list):
        for ov in raw_vol_ov:
            if isinstance(ov, dict):
                spk = str(ov.get("speaker") or "").strip()
                tgt = str(ov.get("target") or "").strip()
                if spk and tgt:
                    vol_overrides_map[spk] = tgt
    elif isinstance(raw_vol_ov, dict):
        for k, v in raw_vol_ov.items():
            if k and v:
                vol_overrides_map[str(k).strip()] = str(v).strip()
    return vol_overrides_map


def _build_ma_players_catalog(hass: HomeAssistant) -> list[dict[str, str]]:
    """Build sorted Music Assistant player entity options."""
    ma_players: list[dict[str, str]] = []
    for ma_entry in ma_player_entities(hass):
        ma_st = hass.states.get(ma_entry.entity_id)
        ma_name = str(
            (ma_st.attributes.get("friendly_name") if ma_st else None)
            or ma_entry.name
            or ma_entry.original_name
            or ma_entry.entity_id
        )
        ma_suffix = (
            " (unavailable)"
            if ma_st is not None and ma_st.state == STATE_UNAVAILABLE
            else ""
        )
        ma_players.append(
            {
                "id": ma_entry.entity_id,
                "name": f"{ma_name} ({ma_entry.entity_id}){ma_suffix}",
            }
        )
    ma_players.sort(key=lambda item: item["name"].lower())
    return ma_players


def _build_shortcut_entities_catalog(
    idx: Any, area_name_by_id: dict[str, str]
) -> list[dict[str, str]]:
    """Build sorted shortcut entity picker entries from `AreaStateIndex`."""
    shortcut_entities: list[dict[str, str]] = []
    seen_sc_ids: set[str] = set()
    for sc_dom in sorted(SHORTCUT_SUPPORTED_DOMAINS):
        for st_obj in idx.states_for_domain(sc_dom):
            eid = st_obj.entity_id
            if eid in seen_sc_ids:
                continue
            seen_sc_ids.add(eid)
            friendly_lbl = str(st_obj.attributes.get("friendly_name") or eid)
            dclass = str(st_obj.attributes.get("device_class") or "")
            ent_icon = resolve_shortcut_entity_icon(
                sc_dom,
                device_class=dclass,
                entity_icon=str(st_obj.attributes.get("icon") or ""),
                state=str(st_obj.state or ""),
            )
            aid = idx.resolve_entity_area_id(eid) or ""
            shortcut_entities.append(
                {
                    "id": eid,
                    "name": friendly_lbl,
                    "domain": sc_dom,
                    "device_class": dclass,
                    "icon": ent_icon,
                    "area_name": area_name_by_id.get(aid, ""),
                }
            )
    shortcut_entities.sort(
        key=lambda item: (
            item["area_name"] == "",
            item["area_name"].lower(),
            item["name"].lower(),
            item["id"],
        )
    )
    return shortcut_entities


def _append_media_player_catalog_entry(
    hass: HomeAssistant,
    state_obj: Any,
    item: dict[str, str],
    ctx: tuple[str, str, Any, ar.AreaRegistry, list[dict[str, Any]]],
) -> None:
    """Append MA or local built-in speaker options for a `media_player` state."""
    local_spk_id, local_ma_id, idx, area_reg, ma_speakers = ctx
    ent_id = state_obj.entity_id
    if (
        local_spk_id
        and local_ma_id
        and ent_id == local_ma_id
        and local_ma_id != local_spk_id
    ):
        return
    if ent_id == local_spk_id:
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        suffix_state = " (unavailable)" if state_obj.state == STATE_UNAVAILABLE else ""
        clean_lbl = (
            friendly[:-_MUSIC_SUFFIX_LEN].strip()
            if friendly.lower().endswith(" music") and len(friendly) > _MUSIC_SUFFIX_LEN
            else friendly
        )
        ma_speakers.append(
            _enrich_hub_catalog_item(
                {
                    "id": ent_id,
                    "name": f"{clean_lbl} — built-in speaker ({ent_id}){suffix_state}",
                },
                state_obj,
                idx,
                area_reg,
            )
        )
    elif is_music_assistant_player(hass, state_obj):
        ma_speakers.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))


def build_entity_catalog(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    all_coords: list[LatterCoordinator] | None = None,
) -> dict[str, Any]:
    """Build the entity pickers for Studio using `AreaStateIndex` (zero full-state scans)."""
    _ = all_coords
    area_reg = ar.async_get(hass)
    areas_list = [
        {"id": a.id, "name": a.name}
        for a in sorted(area_reg.async_list_areas(), key=lambda x: x.name.lower())
    ]

    buckets: dict[str, list[Any]] = {
        "ma_speakers": [],
        "remotes": [],
        "volume_targets": [],
        "alarms": [],
        "cameras": [],
        "climates": [],
        "locks": [],
        "garages": [],
        "vacuums": [],
        "weathers": [],
        "calendars": [],
        "persons": [],
    }
    enriched_domain_map: dict[str, str] = {
        "alarm_control_panel": "alarms",
        "climate": "climates",
        "lock": "locks",
        "vacuum": "vacuums",
        "weather": "weathers",
    }

    local_spk_id = coordinator.local_speaker if coordinator is not None else ""
    local_ma_id = coordinator.local_ma_speaker if coordinator is not None else ""
    idx = get_area_state_index(hass)
    catalog_states = [
        st_obj for dom in _CATALOG_DOMAINS for st_obj in idx.states_for_domain(dom)
    ]
    all_cam_ids = [s.entity_id for s in catalog_states if s.domain == "camera"]
    doorbell_ring_map = (
        resolve_doorbell_ring_entities(hass, all_cam_ids) if all_cam_ids else {}
    )
    vol_overrides_map = _extract_volume_overrides_map(hass)
    mp_ctx = (local_spk_id, local_ma_id, idx, area_reg, buckets["ma_speakers"])

    for state_obj in sorted(catalog_states, key=lambda s: s.entity_id):
        ent_id = state_obj.entity_id
        domain = state_obj.domain
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        suffix_state = " (unavailable)" if state_obj.state == STATE_UNAVAILABLE else ""
        item = {"id": ent_id, "name": f"{friendly} ({ent_id}){suffix_state}"}

        if domain == "media_player":
            buckets["remotes"].append(item)
            buckets["volume_targets"].append(item)
            _append_media_player_catalog_entry(hass, state_obj, item, mp_ctx)
        elif domain == "remote":
            buckets["remotes"].append(item)
        elif domain in ("number", "input_number"):
            buckets["volume_targets"].append(item)
        elif domain in enriched_domain_map:
            buckets[enriched_domain_map[domain]].append(
                _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
            )
        elif domain == "camera":
            enriched_cam = _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
            cam_caps = resolve_camera_capabilities(
                hass,
                ent_id,
                doorbell_ring_map=doorbell_ring_map,
                volume_overrides=vol_overrides_map,
            )
            enriched_cam["stream_kind"] = cam_caps["stream_kind"]
            enriched_cam["has_audio"] = cam_caps["has_audio"]
            enriched_cam["has_talkback"] = cam_caps["has_talkback"]
            enriched_cam["is_doorbell"] = cam_caps["is_doorbell"]
            buckets["cameras"].append(enriched_cam)
        elif domain == "cover" and _is_garage_cover_state(state_obj):
            buckets["garages"].append(
                _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
            )
        elif domain == "calendar":
            buckets["calendars"].append(item)
        elif domain == "person":
            p_slug = re.sub(
                r"[^a-z0-9]+", "_", ent_id.split(".", 1)[-1].lower()
            ).strip("_")
            buckets["persons"].append(
                {"id": ent_id, "name": f"{friendly} (sensor.{p_slug}_current_area)"}
            )

    area_name_by_id = {a["id"]: a["name"] for a in areas_list}
    return {
        "areas": areas_list,
        "ma_speakers": buckets["ma_speakers"],
        "ma_players": _build_ma_players_catalog(hass),
        "volume_targets": buckets["volume_targets"],
        "remotes": buckets["remotes"],
        "alarms": buckets["alarms"],
        "cameras": buckets["cameras"],
        "climates": buckets["climates"],
        "locks": buckets["locks"],
        "garages": buckets["garages"],
        "vacuums": buckets["vacuums"],
        "weathers": buckets["weathers"],
        "calendars": buckets["calendars"],
        "persons": buckets["persons"],
        "shortcut_entities": _build_shortcut_entities_catalog(idx, area_name_by_id),
    }


_build_entity_catalog = build_entity_catalog
_build_pref_specs_catalog = build_pref_specs_catalog

__all__ = [
    "_build_entity_catalog",
    "_build_pref_specs_catalog",
    "_build_system_shared_controls",
    "build_device_prefs_payload",
    "build_entity_catalog",
    "build_pref_specs_catalog",
    "build_quick_actions_payload",
    "build_speaker_volume_payload",
    "build_system_shared_controls",
]
