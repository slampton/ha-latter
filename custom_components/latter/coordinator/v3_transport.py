"""Protocol v3 domain payload builders and dirty-domain push transport (`L3`)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import callback

from ..areas.telemetry import build_area_context_payload
from ..const import CONF_DEFAULT_AREA
from ..feeds import (
    apply_coordinator_calendar_snapshot,
    apply_coordinator_weather_snapshot,
    async_refresh_coordinator_calendar,
    async_refresh_coordinator_weather,
    build_calendar_agenda_payload,
)
from ..identity import esphome_service
from ..media.state_payload import build_active_media_payload
from ..protocol_codec import (
    V3Records,
    pack_device_prefs_fields,
    pack_weather_forecast_fields,
)
from ..protocol_policy import (
    resolve_shortcut_entity_icon,
    resolve_shortcut_live_state,
    shortcut_records,
)
from ..protocol_specs import (
    MAX_DOCK_ITEMS,
    MAX_PINNED_ITEMS,
    sanitize_shortcut_label,
)
from ..remotes import (
    build_remote_config_payload,
    resolve_effective_remote_entities,
    resolve_remote_slot_pair,
)
from .device_lifecycle import CoordinatorLifecycleMixin

_LOGGER = logging.getLogger(__name__)


class CoordinatorV3TransportMixin(CoordinatorLifecycleMixin):
    """Protocol v3 domain packing, dirty-frame push loop, and listener debounce."""

    @property
    def epoch(self) -> int:
        return self._packer.epoch

    def pack_domain_payload(self, domain: str, *fields: Any) -> tuple[int, str]:
        """Pack a Protocol v3 domain payload and advance coordinator `rev`."""
        cur_rev, packed = self._packer.pack(domain, *fields)
        self.rev = max(self.rev, self._packer.rev)
        return cur_rev, packed

    def _pack_domain_payload(self, domain: str, *fields: Any) -> tuple[int, str]:
        return self.pack_domain_payload(domain, *fields)

    @callback
    def clear_last_pushed_v3(self) -> None:
        """Clear last-pushed Protocol v3 domain digest cache."""
        self._last_pushed_v3.clear()

    async def async_push_beacon_uuid(self) -> None:
        """Push the configured System/Device BLE Beacon UUID to ESPHome."""
        if (
            self.is_ble_tag
            or self.is_rpc_outbox_unavailable()
            or not (
                svc := esphome_service(
                    self.hass, self.esphome_device_id, "latter_set_beacon_uuid"
                )
            )
        ):
            return
        try:
            await self.hass.services.async_call(
                "esphome", svc, {"uuid": self.ble_beacon_uuid}, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("esphome.%s failed: %s", svc, err)

    def _collect_domain_payload_pairs(self) -> tuple[tuple[str, str], ...]:
        return (
            ("active_media", str(self.get_active_media_payload()[1].get("payload") or "")),
            ("weather_forecast", str(self.weather_attributes.get("payload") or "")),
            ("area_context", str(self.get_area_context_payload()[1].get("payload") or "")),
            ("calendar_agenda", str(self.get_calendar_agenda_payload()[1].get("payload") or "")),
            ("remote_config", str(self.get_remote_config_payload()[1].get("payload") or "")),
            ("device_prefs", str(self.get_device_prefs_payload()[1].get("payload") or "")),
        )

    async def _async_push_shortcuts_frames(
        self, svc: str, shortcuts_frames: tuple[str, ...]
    ) -> None:
        shortcuts_sig = "\n".join(shortcuts_frames)
        if not shortcuts_frames or self._last_pushed_v3.get("shortcuts") == shortcuts_sig:
            return
        try:
            for frame in shortcuts_frames:
                if self.is_rpc_outbox_unavailable():
                    self._last_pushed_v3.clear()
                    return
                await self.hass.services.async_call(
                    "esphome",
                    svc,
                    {"domain": "shortcuts", "payload": frame},
                    blocking=True,
                )
            self._last_pushed_v3["shortcuts"] = shortcuts_sig
        except Exception as err:  # noqa: BLE001
            self._last_pushed_v3.pop("shortcuts", None)
            _LOGGER.debug("esphome.%s (shortcuts) failed: %s", svc, err)

    async def async_push_dirty_v3_domains(self) -> None:
        """Push dirty Protocol v3 domain frames, aborting immediately on disconnect (`M-P2-18`)."""
        if self.is_ble_tag or not (
            svc := esphome_service(
                self.hass, self.esphome_device_id, "latter_push_v3"
            )
        ):
            return
        if self.is_rpc_outbox_unavailable():
            self._last_pushed_v3.clear()
            return

        for dom, payload in self._collect_domain_payload_pairs():
            if self.is_rpc_outbox_unavailable():
                self._last_pushed_v3.clear()
                return
            if not payload or self._last_pushed_v3.get(dom) == payload:
                continue
            try:
                await self.hass.services.async_call(
                    "esphome", svc, {"domain": dom, "payload": payload}, blocking=True
                )
                self._last_pushed_v3[dom] = payload
            except Exception as err:  # noqa: BLE001
                self._last_pushed_v3.pop(dom, None)
                _LOGGER.debug("esphome.%s (%s) failed: %s", svc, dom, err)
                if self.is_rpc_outbox_unavailable():
                    self._last_pushed_v3.clear()
                    return

        _, shortcuts_frames = self.get_shortcuts_payload()
        await self._async_push_shortcuts_frames(svc, shortcuts_frames)

    @callback
    def force_republish_all_domains(self) -> None:
        """Bump packer epoch, invalidate cached frames, and schedule a full Protocol v3 republish."""
        self._packer.force_republish_all_domains()
        self.rev = max(self.rev, self._packer.rev)
        self._last_pushed_v3.clear()
        self._cached_media_payload = None
        self._cached_media_anchor = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._cached_prefs_payload = None
        self._cached_shortcuts_payload = None
        if self.weather_attributes and "condition" in self.weather_attributes:
            wa = self.weather_attributes
            wa["rev"], wa["payload"] = self.pack_domain_payload(
                "weather_forecast",
                *pack_weather_forecast_fields(
                    wa.get("condition"),
                    wa.get("temperature"),
                    wa.get("humidity"),
                    wa.get("wind_speed"),
                    wa.get("wind_bearing"),
                    wa.get("high"),
                    wa.get("low"),
                    self.forecast_records,
                    wa.get("sun_state"),
                    wa.get("sun_elevation"),
                    wa.get("sun_azimuth"),
                    wa.get("sun_next_rising"),
                    wa.get("sun_next_setting"),
                    wa.get("moon_phase"),
                    wa.get("temp_unit", ""),
                ),
            )
        self.async_update_listeners()
        if not self.is_ble_tag:
            self.create_background_task(
                self.async_push_dirty_v3_domains(),
                f"latter_push_v3_republish_{self.device_slug}",
            )

    async def _async_debounced_notify(self) -> None:
        self.async_update_listeners()
        await self.async_push_dirty_v3_domains()

    @callback
    def schedule_debounced_notify(self) -> None:
        """Schedule a debounced entity/Studio listener update and dirty-domain push."""
        self._notify_debouncer.async_schedule_call()

    @callback
    def async_notify_listeners(self) -> None:
        """Invalidate domain payload caches, persist runtime state, and schedule debounced push."""
        self._cached_media_payload = None
        self._cached_area_payload = None
        self._cached_remote_payload = None
        self._cached_prefs_payload = None
        self._cached_shortcuts_payload = None
        self.schedule_persist_runtime_state()
        self.schedule_debounced_notify()

    def _resolve_shortcut_wire_items(
        self, items: list[dict[str, Any]], *, max_len: int
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for item in items[:max_len]:
            if item.get("kind") == "route":
                resolved.append(
                    {
                        "kind": "route",
                        "target": item["target"],
                        "action": "",
                        "label": item.get("label") or "",
                        "icon": item.get("icon") or "",
                        "confirm": False,
                        "state": -1,
                    }
                )
                continue
            target = str(item.get("target") or "").strip().lower()
            domain = target.split(".", 1)[0] if "." in target else ""
            st = self.hass.states.get(target)
            raw_state = st.state if st is not None else None
            live_state = resolve_shortcut_live_state(domain, raw_state)
            eff_label = str(item.get("label") or "") or sanitize_shortcut_label(
                (st.attributes.get("friendly_name") if st is not None else None)
                or target
            )
            eff_icon = str(item.get("icon") or "") or resolve_shortcut_entity_icon(
                domain,
                device_class=(
                    str(st.attributes.get("device_class") or "")
                    if st is not None
                    else ""
                ),
                entity_icon=(
                    str(st.attributes.get("icon") or "") if st is not None else ""
                ),
                state=str(raw_state or ""),
            )
            resolved.append(
                {
                    "kind": "entity",
                    "target": target,
                    "action": item.get("action") or "",
                    "label": eff_label,
                    "icon": eff_icon,
                    "confirm": bool(item.get("confirm", False)),
                    "state": live_state,
                }
            )
        return resolved

    def get_shortcuts_payload(self) -> tuple[int, tuple[str, ...]]:
        if self._cached_shortcuts_payload is not None:
            return self._cached_shortcuts_payload
        dock_wire = self._resolve_shortcut_wire_items(
            self.dock_items, max_len=MAX_DOCK_ITEMS
        )
        pinned_wire = self._resolve_shortcut_wire_items(
            self.pinned_items, max_len=MAX_PINNED_ITEMS
        )
        dock_recs = shortcut_records(dock_wire, max_records=MAX_DOCK_ITEMS)
        pinned_recs = shortcut_records(pinned_wire, max_records=MAX_PINNED_ITEMS)
        cur_rev, frames = self._packer.pack_shortcuts(dock_recs, pinned_recs)
        self.rev = max(self.rev, self._packer.rev)
        res = (cur_rev, frames)
        self._cached_shortcuts_payload = res
        return res

    def get_device_prefs_payload(self) -> tuple[int, dict[str, Any]]:
        if self._cached_prefs_payload is not None:
            return self._cached_prefs_payload
        sub_data = self._live_subentry().data
        eff_seq = max(1, self.prefs_seq)
        fields = pack_device_prefs_fields(
            eff_seq,
            sub_data,
            native_ble_tracking=self.native_ble_tracking_enabled,
            custom_color_hex=self.device_custom_color,
            is_round_display=self.is_round_display,
            supports_hw_jpeg=self.supports_hw_jpeg,
            do_not_disturb=self.do_not_disturb,
        )
        cur_rev, packed = self.pack_domain_payload("device_prefs", *fields)
        res = (
            eff_seq,
            {
                "prefs_seq": eff_seq,
                "device_group": self.device_group,
                "wake_word_mode": self.get_device_pref("wake_word_mode"),
                "alert_volume": self.get_device_pref("alert_volume"),
                "ble_beacon_enabled": self.native_ble_tracking_enabled,
                "rev": cur_rev,
                "payload": packed,
            },
        )
        self._cached_prefs_payload = res
        return res

    def get_effective_remote_entities_for_device(self) -> list[str]:
        return resolve_effective_remote_entities(
            self.hass,
            all_inventory=self.get_remote_entities_list(),
            groups=self.remote_groups,
            mode=self.device_remote_group,
            cur_area=(
                self.active_area_id or str(self.get_opt(CONF_DEFAULT_AREA) or "")
            ).strip(),
        )

    def get_remote_slots(self) -> list[dict[str, str]]:
        return [
            resolve_remote_slot_pair(self.hass, eid)
            for eid in self.get_effective_remote_entities_for_device()[:10]
        ]

    def get_remote_config_payload(self) -> tuple[str | None, dict[str, Any]]:
        return build_remote_config_payload(self)

    def get_area_context_payload(self) -> tuple[str, dict[str, Any]]:
        return build_area_context_payload(self)

    def get_active_media_payload(self) -> tuple[str | None, dict[str, Any]]:
        return build_active_media_payload(self)

    @callback
    def apply_calendar_snapshot(
        self, records: V3Records, raw_rows: list[dict[str, Any]]
    ) -> None:
        apply_coordinator_calendar_snapshot(self, records, raw_rows)

    async def async_refresh_calendar_agenda(self, days: int = 30) -> None:
        await async_refresh_coordinator_calendar(self, days=days)

    def get_calendar_agenda_payload(self) -> tuple[int, dict[str, Any]]:
        return build_calendar_agenda_payload(self)

    @callback
    def apply_weather_snapshot(
        self, weather_ent: str | None, snap: tuple[V3Records, dict[str, Any]] | None
    ) -> None:
        apply_coordinator_weather_snapshot(self, weather_ent, snap)

    async def async_refresh_weather_forecast(self) -> None:
        await async_refresh_coordinator_weather(self)
