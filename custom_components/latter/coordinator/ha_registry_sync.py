"""Home Assistant Device Registry, Entity Registry, and target resolution sync (`L3`)."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..areas.sync import sync_esphome_device_area
from ..const import (
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_MA_PLAYER_ENTITY,
    DOMAIN,
    normalize_device_slug,
)
from ..hub_registry import iter_coordinators
from ..identity import get_bound_esphome_device
from ..media.playback import bind_coordinator_speaker_listener
from ..repairs import async_audit_coordinator_health
from .area_follow_controller import CoordinatorAreaFollowMixin

_LOGGER = logging.getLogger(__name__)


def match_coordinator_target_generic[CoordT: CoordinatorAreaFollowMixin](
    hass: HomeAssistant, coords: Sequence[CoordT], target: str | None
) -> CoordT | None:
    """Match a loaded coordinator by `subentry_id`, Latter or ESPHome `device_id`, or exact slug."""
    if not coords:
        return None
    if not target or not str(target).strip():
        return coords[0] if len(coords) == 1 else None
    raw = str(target).strip()
    norm = normalize_device_slug(raw)
    target_dev = dr.async_get(hass).async_get(raw)
    for coord in coords:
        if (
            coord.subentry_id == raw
            or coord.device_slug == norm
            or (coord.esphome_device_id and coord.esphome_device_id == raw)
        ):
            return coord
        if isinstance(target_dev, dr.DeviceEntry):
            mac = coord.device_mac
            if (DOMAIN, coord.subentry_id) in target_dev.identifiers or (
                mac and (DOMAIN, dr.format_mac(mac)) in target_dev.identifiers
            ):
                return coord
            if (
                target_dev.via_device_id
                and coord.esphome_device_id
                and target_dev.via_device_id == coord.esphome_device_id
            ):
                return coord
    return None


class CoordinatorRegistrySyncMixin(CoordinatorAreaFollowMixin):
    """Device Registry name/Area mirroring and Entity Registry rename healing."""

    def _find_latter_device_entry(self) -> dr.DeviceEntry | None:
        dev_reg = dr.async_get(self.hass)
        idents = self.get_device_info()["identifiers"]
        esp_id = self.esphome_device_id
        for dev in dr.async_entries_for_config_entry(dev_reg, self.entry.entry_id):
            if (DOMAIN, "system") in dev.identifiers:
                continue
            if (dev.identifiers & idents) or (esp_id and dev.via_device_id == esp_id):
                return dev
        return None

    @callback
    def async_record_own_area_write(self, device_id: str, area_id: str) -> None:
        """Record an internal Device Registry Area write so external change tracking stays aligned."""
        if device_id == self.esphome_device_id:
            self._last_esp_area = area_id
        else:
            latter_dev = self._find_latter_device_entry()
            if latter_dev is not None and latter_dev.id == device_id:
                self._last_latter_area = area_id

    @callback
    def async_sync_ha_device_name(self) -> bool:
        """Mirror the bound ESPHome Device's live name onto the Latter subentry and child Latter Device."""
        if self.is_ble_tag or not self.esphome_device_id:
            return False
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        if esp_dev is None:
            return False
        live_name = str(esp_dev.name_by_user or esp_dev.name or "").strip()
        if not live_name:
            return False
        self.async_heal_renamed_local_speaker()
        changed = False
        live_sub = self._live_subentry()
        if live_sub.title != live_name:
            self.hass.config_entries.async_update_subentry(
                self.entry, live_sub, title=live_name
            )
            self._live_subentry()
            changed = True
        latter_dev = self._find_latter_device_entry()
        if latter_dev is not None and latter_dev.name != live_name:
            dr.async_get(self.hass).async_update_device(latter_dev.id, name=live_name)
            changed = True
        if changed:
            self._cached_media_payload = None
            for coord in iter_coordinators(self.hass):
                coord.cached_area_payload = None
                coord.async_notify_listeners()
        return changed

    @callback
    def async_heal_renamed_local_speaker(self) -> bool:
        """Heal stale built-in speaker refs when the bound ESPHome node was renamed before/offline."""
        if self.is_ble_tag:
            return False
        local_spk = self.local_speaker
        if not local_spk:
            return False
        prior_slugs = {
            slug
            for slug in (
                self.device_slug,
                normalize_device_slug(str(self._live_subentry().title or "")),
            )
            if slug
        }
        old_local_candidates = {
            f"media_player.{slug}{sfx}"
            for slug in prior_slugs
            for sfx in ("", "_music", "_media_player")
        }
        old_local_candidates.discard(local_spk)
        if not old_local_candidates:
            return False

        ent_reg = er.async_get(self.hass)

        def _is_stale_local(entity_id: str) -> bool:
            return (
                bool(entity_id)
                and entity_id in old_local_candidates
                and self.hass.states.get(entity_id) is None
                and ent_reg.async_get(entity_id) is None
            )

        healed = False
        raw_def_spk = str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip()
        if _is_stale_local(raw_def_spk):
            _LOGGER.info(
                "Healed renamed built-in default_speaker for '%s': %s -> %s",
                self.device_slug,
                raw_def_spk,
                local_spk,
            )
            self.update_device_config(
                {**self.device_data, CONF_DEFAULT_SPEAKER: local_spk},
                bump_prefs_seq=False,
            )
            healed = True

        runtime_changed = False
        if _is_stale_local(self.active_speaker):
            self.active_speaker = local_spk
            runtime_changed = True
        if _is_stale_local(self.last_speaker):
            self.last_speaker = local_spk
            runtime_changed = True
        if runtime_changed:
            self._cached_media_payload = None
            self.schedule_persist_runtime_state()
            healed = True
        return healed

    @callback
    def async_on_ha_entity_renamed(
        self,
        old_entity_id: str,
        new_entity_id: str,
        entity_device_id: str | None = None,
    ) -> bool:
        """Migrate Device speaker/MA references and rebind listeners when an HA entity is renamed."""
        if (
            self.is_ble_tag
            or not old_entity_id
            or not new_entity_id
            or old_entity_id == new_entity_id
        ):
            return False
        changed = self._migrate_renamed_speaker_refs(old_entity_id, new_entity_id)
        is_own_device = bool(
            entity_device_id
            and self.esphome_device_id
            and entity_device_id == self.esphome_device_id
        )
        if changed or is_own_device:
            self._cached_media_payload = None
            bind_coordinator_speaker_listener(self)
            if is_own_device:
                self._bind_link_report_listener()
                self._bind_ble_radio_listener()
            try:
                async_audit_coordinator_health(self.hass, self)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Repairs audit after rename skipped: %s", err)
            self.async_notify_listeners()
        return changed or is_own_device

    def _migrate_renamed_speaker_refs(
        self, old_entity_id: str, new_entity_id: str
    ) -> bool:
        changed = False
        cfg_updates: dict[str, Any] = {}
        if str(self.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() == old_entity_id:
            cfg_updates[CONF_DEFAULT_SPEAKER] = new_entity_id
        if str(self.get_opt(CONF_MA_PLAYER_ENTITY) or "").strip() == old_entity_id:
            cfg_updates[CONF_MA_PLAYER_ENTITY] = new_entity_id
        if cfg_updates:
            self.update_device_config(
                {**self.device_data, **cfg_updates},
                bump_prefs_seq=False,
            )
            changed = True

        runtime_changed = False
        if self.active_speaker == old_entity_id:
            self.active_speaker = new_entity_id
            runtime_changed = True
        if self.last_speaker == old_entity_id:
            self.last_speaker = new_entity_id
            runtime_changed = True
        if runtime_changed:
            self.schedule_persist_runtime_state()
            changed = True
        return changed

    @callback
    def async_sync_ha_device_areas(self) -> None:
        """Mirror the authoritative Area across the bound ESPHome Device and child Latter Device."""
        if self.is_ble_tag:
            return
        esp_id = self.esphome_device_id
        esp_dev = get_bound_esphome_device(self.hass, esp_id)
        esp_area = str(esp_dev.area_id or "").strip() if esp_dev else ""
        latter_dev = self._find_latter_device_entry()
        latter_area = str(latter_dev.area_id or "").strip() if latter_dev else ""
        if esp_id:
            if not self.native_ble_tracking_enabled:
                target = (
                    str(self.get_opt(CONF_DEFAULT_AREA) or "").strip() or esp_area
                )
                if target:
                    sync_esphome_device_area(
                        self.hass, esp_id, target, require_ble_proxy_area=False
                    )
                    esp_area = latter_area = target
            elif esp_area and latter_dev is not None and latter_area != esp_area:
                sync_esphome_device_area(
                    self.hass, esp_id, esp_area, require_ble_proxy_area=False
                )
                latter_area = esp_area
        self._last_esp_area = esp_area
        self._last_latter_area = latter_area

    @callback
    def async_on_ha_device_area_updated(
        self, updated_device_id: str, new_area_id: str
    ) -> None:
        """React live when an administrator reassigns the ESPHome or Latter Device Area in Home Assistant."""
        if self.is_ble_tag:
            return
        clean_area = str(new_area_id or "").strip()
        expected_prev = (
            self._last_esp_area
            if updated_device_id == self.esphome_device_id
            else self._last_latter_area
        )
        if clean_area == expected_prev:
            return
        self._last_esp_area = clean_area
        self._last_latter_area = clean_area
        if self.esphome_device_id:
            sync_esphome_device_area(
                self.hass,
                self.esphome_device_id,
                clean_area,
                require_ble_proxy_area=False,
                allow_clear=True,
            )
        if not self.native_ble_tracking_enabled:
            cur_conf = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
            if clean_area != cur_conf:
                self.update_device_config(
                    {**self.device_data, CONF_DEFAULT_AREA: clean_area},
                    bump_prefs_seq=False,
                )
            self._configured_default_area = clean_area
            if clean_area:
                self.async_set_active_area(clean_area, sync_device_registry=False)
            else:
                self._clear_active_area()
            return
        has_ble_lock = bool(
            self._ble_tracker and self._ble_tracker.current_area_id
        )
        explicit_default = str(self.get_opt(CONF_DEFAULT_AREA) or "").strip()
        if not has_ble_lock and not explicit_default:
            if clean_area:
                self.async_set_active_area(clean_area, sync_device_registry=False)
            else:
                self._clear_active_area()
        else:
            self.async_notify_listeners()
