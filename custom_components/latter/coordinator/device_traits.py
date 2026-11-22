"""Device identity, hardware manifest traits, option getters, and signed URL builders (`L3`)."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.core import State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_ALARM_ENTITY,
    CONF_AREA_CATEGORIES,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BROADCAST_PHRASES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_BROADCAST_SPEAKERS,
    CONF_CALENDAR_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_CONFIGS,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_CUSTOM_PALETTES,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DO_NOT_DISTURB,
    CONF_DOCK_ITEMS,
    CONF_ESPHOME_DEVICE_ID,
    CONF_GAMES_ITEMS,
    CONF_GARAGE_ENTITIES,
    CONF_HOME_CATEGORIES,
    CONF_LOCK_ENTITIES,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SITE_ID,
    CONF_SYSTEM_BLE_UUID,
    CONF_THERMOSTAT_ENTITIES,
    CONF_TOOLS_ITEMS,
    CONF_VACUUM_ENTITIES,
    CONF_VOLUME_OVERRIDES,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DEFAULT_ACTIVITY_CARD,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_BROADCAST_PHRASES,
    DEFAULT_CARD_SLOT_COUNT,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES,
    DEFAULT_LIST_SLOT_COUNT,
    DEFAULT_NATIVE_BLE_TRACKING,
    DEFAULT_SECURITY_PIN_POLICY,
    DEFAULT_SITE_ID,
    DEFAULT_TOOLS_ITEMS,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    SUBENTRY_BLE_TAG,
    WALLPAPER_MAX_DIM,
    normalize_device_slug,
)
from ..groups.device_groups import resolve_effective_device_group
from ..http.signing import UrlSigner
from ..identity import (
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    manifest_has_audio,
    manifest_has_battery,
    manifest_has_display,
    manifest_has_imu,
    manifest_has_mic,
    manifest_has_speaker,
    manifest_is_roaming,
    manifest_is_round,
    manifest_is_wearable,
    manifest_supports_hw_jpeg,
    manifest_video_caps,
    read_device_hardware_manifest,
    resolve_bound_esphome_device_id,
)
from ..media.linking import resolve_esphome_local_speaker, resolve_ma_counterpart_entity
from ..protocol_policy import effective_security_pin_policy, normalize_security_pin_policy
from ..protocol_specs import (
    DEVICE_PREF_KEYS,
    normalize_activity_sources,
    normalize_area_categories,
    normalize_dock_items,
    normalize_games_items,
    normalize_home_categories,
    normalize_pinned_items,
    normalize_tools_items,
    resolve_device_pref_value,
)
from .runtime_store import CoordinatorStateBase

_MAC_COLON_LEN = 17
_MAC_COLON_COUNT = 5
_HEX_COLOR_LEN = 7
_MIN_MEDIA_DIM = 64
_MAX_MEDIA_DIM = 1920
_MAX_SLOT_CAPACITY = 20


class CoordinatorTraitsMixin(CoordinatorStateBase):
    """Hardware manifest traits, device option accessors, and signed resource URL builders."""

    @property
    def device_data(self) -> dict[str, Any]:
        """Return a shallow copy of the live subentry option dictionary."""
        return dict(self._live_subentry().data)

    def update_device_config(
        self,
        merged_data: dict[str, Any],
        *,
        bump_prefs_seq: bool = True,
        preserve_group: bool = False,
    ) -> None:
        """Persist updated subentry data and advance `prefs_seq` / `device_config_rev`."""
        prev = self._live_subentry().data
        if not self.is_ble_tag and not preserve_group:
            eff_grp = resolve_effective_device_group(
                self.hass, self, candidate_data=merged_data
            )
            if merged_data.get(CONF_DEVICE_GROUP) != eff_grp:
                merged_data = {**merged_data, CONF_DEVICE_GROUP: eff_grp}
        changed_pref_keys: list[str] = []
        if bump_prefs_seq:
            changed_pref_keys = self._compute_changed_pref_keys(prev, merged_data)
            if changed_pref_keys:
                self.prefs_seq = max(1, self.prefs_seq + 1)
                for key in changed_pref_keys:
                    self.prefs_key_seq[key] = self.prefs_seq
                self._cached_prefs_payload = None
                if "world_clocks" in changed_pref_keys:
                    self._cached_area_payload = None
        self.hass.config_entries.async_update_subentry(
            self.entry, self._live_subentry(), data=merged_data
        )
        self._live_subentry()
        self.device_config_rev = max(1, self.device_config_rev + 1)
        self.schedule_persist_runtime_state()

    @staticmethod
    def _compute_changed_pref_keys(
        prev: Any, merged_data: dict[str, Any]
    ) -> list[str]:
        changed: list[str] = [
            key
            for key in DEVICE_PREF_KEYS
            if resolve_device_pref_value(merged_data, key)
            != resolve_device_pref_value(prev, key)
        ]
        if bool(
            merged_data.get(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)
        ) != bool(prev.get(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING)):
            changed.append(CONF_NATIVE_BLE_TRACKING)
        if (
            str(merged_data.get(CONF_DEVICE_CUSTOM_COLOR) or "").strip().upper()
            != str(prev.get(CONF_DEVICE_CUSTOM_COLOR) or "").strip().upper()
        ):
            changed.append(CONF_DEVICE_CUSTOM_COLOR)
        for csv_key, csv_default, csv_norm in (
            (CONF_TOOLS_ITEMS, DEFAULT_TOOLS_ITEMS, normalize_tools_items),
            (CONF_GAMES_ITEMS, DEFAULT_GAMES_ITEMS, normalize_games_items),
        ):
            try:
                new_csv = csv_norm(merged_data.get(csv_key, csv_default))
            except ValueError:
                new_csv = csv_default
            try:
                old_csv = csv_norm(prev.get(csv_key, csv_default))
            except ValueError:
                old_csv = csv_default
            if new_csv != old_csv:
                changed.append(csv_key)
        return changed

    def get_opt(self, key: str, default: Any = None) -> Any:
        """Read a System-scoped (`GLOBAL_CONFIG_KEYS`) or Device-scoped option value."""
        domain_data = self.hass.data.get(DOMAIN, {})
        global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
        if key in GLOBAL_CONFIG_KEYS:
            if (
                isinstance(global_cfg, dict)
                and key in global_cfg
                and global_cfg[key] is not None
            ):
                return global_cfg[key]
            return default
        sub_data = self._live_subentry().data
        if key in sub_data:
            return sub_data[key]
        return default

    @property
    def device_slug(self) -> str:
        return normalize_device_slug(
            str(self._live_subentry().data.get(CONF_DEVICE_SLUG) or "")
        )

    @property
    def device_mac(self) -> str | None:
        stored_mac = str(self.get_opt("mac", "") or "").strip()
        if stored_mac:
            return str(dr.format_mac(stored_mac))
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        if esp_dev is not None:
            for ctype, cval in esp_dev.connections:
                if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                    return str(dr.format_mac(str(cval)))
        ble_addr = str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()
        return (
            str(dr.format_mac(ble_addr))
            if len(ble_addr) == _MAC_COLON_LEN and ble_addr.count(":") == _MAC_COLON_COUNT
            else None
        )

    @property
    def device_title(self) -> str:
        if not self.is_ble_tag and self.esphome_device_id:
            esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
            if esp_dev is not None:
                live_name = str(esp_dev.name_by_user or esp_dev.name or "").strip()
                if live_name:
                    return live_name
        return (
            self.subentry.title
            if self._live_subentry().title
            else self.device_slug.replace("_", " ").title()
        )

    @property
    def esphome_device_id(self) -> str | None:
        dev_reg = dr.async_get(self.hass)
        if (
            self._cached_esphome_device_id
            and dev_reg.async_get(self._cached_esphome_device_id) is not None
        ):
            return self._cached_esphome_device_id
        stored = str(self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or "").strip() or None
        stored_mac = str(self.get_opt("mac", "") or "").strip() or None
        self._cached_esphome_device_id = resolve_bound_esphome_device_id(
            self.hass, stored, stored_mac
        )
        return self._cached_esphome_device_id

    def device_entity(self, domain: str, *suffixes: str) -> str | None:
        return find_device_entity_by_suffix(
            self.hass, self.esphome_device_id, domain, suffixes
        )

    def device_state(self, domain: str, *suffixes: str) -> State | None:
        ent_id = self.device_entity(domain, *suffixes)
        return self.hass.states.get(ent_id) if ent_id else None

    @property
    def url_signer(self) -> UrlSigner:
        return self._url_signer

    def get_device_info(self) -> DeviceInfo:
        esp_dev_id = self.esphome_device_id
        mac = self.device_mac
        ident_key = dr.format_mac(mac) if mac else self.subentry_id
        return DeviceInfo(
            identifiers={(DOMAIN, ident_key)},
            name=self.device_title,
            manufacturer="Latter",
            model="Latter ESPHome Companion Middleware",
            sw_version=INTEGRATION_VERSION,
            configuration_url=f"homeassistant://latter/devices/{self.subentry_id}",
            **({"via_device_id": esp_dev_id} if esp_dev_id else {}),
        )

    @property
    def local_speaker(self) -> str:
        return resolve_esphome_local_speaker(self.hass, self.esphome_device_id)

    @property
    def local_ma_speaker(self) -> str:
        return resolve_ma_counterpart_entity(self.hass, self.local_speaker) or ""

    def is_local_speaker_entity(self, speaker_entity_id: str | None) -> bool:
        spk = str(speaker_entity_id or "").strip()
        return bool(spk and spk in (self.local_speaker, self.local_ma_speaker))

    @property
    def site_id(self) -> str:
        return str(self.get_opt(CONF_SITE_ID, DEFAULT_SITE_ID) or DEFAULT_SITE_ID).strip()

    @property
    def hardware_manifest(self) -> dict[str, Any]:
        return read_device_hardware_manifest(
            self.hass,
            self.esphome_device_id,
            cached_manifest=self._runtime.hello_manifest,
        )

    @property
    def is_ble_tag(self) -> bool:
        return bool(self.subentry.subentry_type == SUBENTRY_BLE_TAG)

    @property
    def has_display(self) -> bool:
        return not self.is_ble_tag and manifest_has_display(self.hardware_manifest)

    @property
    def has_mic(self) -> bool:
        return not self.is_ble_tag and manifest_has_mic(self.hardware_manifest)

    @property
    def has_speaker(self) -> bool:
        return not self.is_ble_tag and manifest_has_speaker(self.hardware_manifest)

    @property
    def has_audio(self) -> bool:
        return not self.is_ble_tag and manifest_has_audio(self.hardware_manifest)

    @property
    def has_imu(self) -> bool:
        return not self.is_ble_tag and manifest_has_imu(self.hardware_manifest)

    @property
    def has_battery(self) -> bool:
        return not self.is_ble_tag and manifest_has_battery(self.hardware_manifest)

    @property
    def has_ble_beacon(self) -> bool:
        if self.is_ble_tag:
            return False
        hw = self.hardware_manifest
        if not hw:
            return True
        return (
            isinstance(hw.get("beacon"), dict)
            or hw.get("minor") is not None
            or self.device_telemetry.get("ble_active") is not None
            or bool(self.device_entity("binary_sensor", "_ble_radio_active"))
        )

    @property
    def screensaver_active(self) -> bool:
        """Return True when the Device display is currently in screensaver power state (`1`)."""
        return self.display_power_state == 1

    @property
    def do_not_disturb(self) -> bool:
        """Return True when Do Not Disturb is active on this Device."""
        return bool(self.get_device_pref(CONF_DO_NOT_DISTURB))

    @property
    def is_round_display(self) -> bool:
        return self.has_display and manifest_is_round(self.hardware_manifest)

    @property
    def supports_hw_jpeg(self) -> bool:
        return not self.is_ble_tag and manifest_supports_hw_jpeg(self.hardware_manifest)

    @property
    def video_max_dims(self) -> tuple[int, int]:
        if self.is_ble_tag or not self.has_display:
            return (0, 0)
        caps = manifest_video_caps(self.hardware_manifest)
        return (int(caps["max_w"]), int(caps["max_h"]))

    @property
    def video_max_fps(self) -> int:
        if self.is_ble_tag or not self.has_display:
            return 0
        return int(manifest_video_caps(self.hardware_manifest)["max_fps"])

    @property
    def video_grid_fps(self) -> int:
        if self.is_ble_tag or not self.has_display:
            return 0
        return int(manifest_video_caps(self.hardware_manifest)["grid_fps"])

    def get_device_pref(self, key: str) -> Any:
        return resolve_device_pref_value(self._live_subentry().data, key)

    @property
    def current_timer_remaining_sec(self) -> int:
        if not self.timer_running and not self.timer_paused:
            return 0
        if self.timer_paused or not self.timer_running:
            return max(0, int(self.timer_remaining_sec))
        elapsed = max(0.0, time.monotonic() - self._timer_anchor_mono)
        return max(0, round(self.timer_remaining_sec - elapsed))

    @property
    def current_stopwatch_elapsed_sec(self) -> int:
        if not self.stopwatch_running and not self.stopwatch_paused:
            return 0
        base = max(0, int(self.stopwatch_elapsed_sec))
        if not self.stopwatch_running:
            return base
        elapsed = max(0, int(time.monotonic() - self._stopwatch_anchor_mono))
        return base + elapsed

    @property
    def is_wearable(self) -> bool:
        return manifest_is_wearable(self.hardware_manifest)

    @property
    def is_roaming_device(self) -> bool:
        return manifest_is_roaming(self.hardware_manifest)

    @property
    def device_group(self) -> str:
        return resolve_effective_device_group(self.hass, self)

    @property
    def display_shape(self) -> str:
        hw_shape = str(self.hardware_manifest.get("shape") or "").strip().lower()
        return hw_shape if hw_shape in ("circle", "square") else DEFAULT_DISPLAY_SHAPE

    @property
    def list_slot_capacity(self) -> int:
        try:
            raw = self.hardware_manifest.get("slot_count")
            val = int(raw) if raw is not None else DEFAULT_LIST_SLOT_COUNT
        except (TypeError, ValueError):
            val = DEFAULT_LIST_SLOT_COUNT
        return max(1, min(_MAX_SLOT_CAPACITY, val))

    @property
    def card_slot_capacity(self) -> int:
        try:
            raw = self.hardware_manifest.get("card_slot_count")
            val = int(raw) if raw is not None else DEFAULT_CARD_SLOT_COUNT
        except (TypeError, ValueError):
            val = DEFAULT_CARD_SLOT_COUNT
        return max(1, min(_MAX_SLOT_CAPACITY, val))

    @property
    def dock_items(self) -> list[Any]:
        return list(
            normalize_dock_items(
                self._live_subentry().data.get(CONF_DOCK_ITEMS), strict=False
            )
        )

    @property
    def pinned_items(self) -> list[Any]:
        return list(
            normalize_pinned_items(
                self._live_subentry().data.get(CONF_PINNED_ITEMS), strict=False
            )
        )

    @property
    def area_categories_csv(self) -> str:
        try:
            return normalize_area_categories(
                self.get_opt(CONF_AREA_CATEGORIES, DEFAULT_AREA_CATEGORIES)
            )
        except ValueError:
            return DEFAULT_AREA_CATEGORIES

    @property
    def home_categories_csv(self) -> str:
        try:
            return normalize_home_categories(
                self.get_opt(CONF_HOME_CATEGORIES, DEFAULT_HOME_CATEGORIES)
            )
        except ValueError:
            return DEFAULT_HOME_CATEGORIES

    @property
    def tools_items_csv(self) -> str:
        try:
            return normalize_tools_items(
                self.get_opt(CONF_TOOLS_ITEMS, DEFAULT_TOOLS_ITEMS)
            )
        except ValueError:
            return DEFAULT_TOOLS_ITEMS

    @property
    def games_items_csv(self) -> str:
        try:
            return normalize_games_items(
                self.get_opt(CONF_GAMES_ITEMS, DEFAULT_GAMES_ITEMS)
            )
        except ValueError:
            return DEFAULT_GAMES_ITEMS

    @property
    def activity_card_enabled(self) -> bool:
        return bool(self.get_opt(CONF_ACTIVITY_CARD, DEFAULT_ACTIVITY_CARD))

    @property
    def activity_sources_csv(self) -> str:
        try:
            return normalize_activity_sources(
                self.get_opt(CONF_ACTIVITY_SOURCES, DEFAULT_ACTIVITY_SOURCES)
            )
        except ValueError:
            return DEFAULT_ACTIVITY_SOURCES

    @property
    def custom_palettes(self) -> list[dict[str, str]]:
        val = self.get_opt(CONF_CUSTOM_PALETTES, [])
        if not isinstance(val, list):
            return []
        return [
            {
                "name": str(it.get("name") or it["hex"]).strip(),
                "hex": str(it["hex"]).strip().upper(),
            }
            for it in val
            if isinstance(it, dict) and it.get("hex")
        ]

    @property
    def device_custom_color(self) -> str:
        raw = str(self.get_opt(CONF_DEVICE_CUSTOM_COLOR, "") or "").strip().upper()
        if raw.startswith("#") and len(raw) == _HEX_COLOR_LEN:
            return raw
        return self.custom_palettes[0]["hex"] if self.custom_palettes else "#3898FF"

    @property
    def weather_entity(self) -> str | None:
        val = self.get_opt(CONF_WEATHER_ENTITY)
        return str(val) if val else None

    @property
    def alarm_entity(self) -> str | None:
        return str(self.get_opt(CONF_ALARM_ENTITY) or "").strip() or None

    @property
    def camera_entities(self) -> list[str]:
        raw_list = self.get_opt(CONF_CAMERA_ENTITIES)
        return (
            [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
            if isinstance(raw_list, list)
            else []
        )

    @property
    def camera_configs(self) -> dict[str, dict[str, Any]]:
        """Return sanitized per-camera configuration map (`label`, action toggles, `unlock_entity`)."""
        raw = self.get_opt(CONF_CAMERA_CONFIGS)
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for cam_id, entry in raw.items():
            cid = str(cam_id or "").strip()
            if cid.startswith("camera.") and isinstance(entry, dict):
                out[cid] = dict(entry)
        return out

    @staticmethod
    def _dedup_scoped_ids(
        raw: Any, allowed: set[str], limit: int
    ) -> list[str]:
        if not isinstance(raw, (list, tuple)):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in raw:
            cid = str(item or "").strip()
            if cid and cid in allowed and cid not in seen:
                seen.add(cid)
                out.append(cid)
        return out[:limit]

    @property
    def configured_camera_visible_entities(self) -> list[str]:
        return self._dedup_scoped_ids(
            self._live_subentry().data.get(CONF_CAMERA_VISIBLE_ENTITIES),
            set(self.camera_entities),
            10,
        )

    @property
    def visible_camera_entities(self) -> list[str]:
        configured = self.configured_camera_visible_entities
        return configured if configured else self.camera_entities

    @property
    def configured_camera_carousel_entities(self) -> list[str]:
        return self._dedup_scoped_ids(
            self._live_subentry().data.get(CONF_CAMERA_CAROUSEL_ENTITIES),
            set(self.visible_camera_entities),
            10,
        )

    @property
    def carousel_camera_entities(self) -> list[str]:
        configured = self.configured_camera_carousel_entities
        return configured if configured else self.visible_camera_entities

    @property
    def system_broadcast_speakers(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_BROADCAST_SPEAKERS, "media_player.", 32)

    @property
    def configured_broadcast_speaker_entities(self) -> list[str]:
        return self._dedup_scoped_ids(
            self._live_subentry().data.get(CONF_BROADCAST_SPEAKER_ENTITIES),
            set(self.system_broadcast_speakers),
            32,
        )

    @property
    def effective_broadcast_speakers(self) -> list[str]:
        configured = self.configured_broadcast_speaker_entities
        return configured if configured else self.system_broadcast_speakers

    @property
    def broadcast_phrases(self) -> list[str]:
        domain_data = self.hass.data.get(DOMAIN) if self.hass is not None else None
        global_cfg = (
            domain_data.get(DATA_GLOBAL_CONFIG)
            if isinstance(domain_data, dict)
            else None
        )
        if not isinstance(global_cfg, dict) or CONF_BROADCAST_PHRASES not in global_cfg:
            return list(DEFAULT_BROADCAST_PHRASES)
        raw = global_cfg.get(CONF_BROADCAST_PHRASES)
        if not isinstance(raw, (list, tuple)):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in raw:
            clean = str(item or "").strip()[:64]
            if clean and clean not in seen:
                seen.add(clean)
                out.append(clean)
        return out[:12]

    @property
    def camera_entity(self) -> str | None:
        cams = self.visible_camera_entities
        return cams[0] if cams else None

    def _clean_entity_list_opt(self, key: str, prefix: str, limit: int) -> list[str]:
        raw_list = self.get_opt(key)
        if not isinstance(raw_list, (list, tuple)):
            return []
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in raw_list:
            s = str(item or "").strip()
            if s.startswith(prefix) and s not in seen:
                seen.add(s)
                cleaned.append(s)
        return cleaned[:limit]

    @property
    def thermostat_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_THERMOSTAT_ENTITIES, "climate.", 8)

    @property
    def lock_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_LOCK_ENTITIES, "lock.", 8)

    @property
    def garage_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_GARAGE_ENTITIES, "cover.", 6)

    @property
    def vacuum_entities(self) -> list[str]:
        return self._clean_entity_list_opt(CONF_VACUUM_ENTITIES, "vacuum.", 6)

    @property
    def native_ble_tracking_enabled(self) -> bool:
        return bool(self.get_opt(CONF_NATIVE_BLE_TRACKING, DEFAULT_NATIVE_BLE_TRACKING))

    @property
    def ble_beacon_uuid(self) -> str:
        sub_raw = str(self._live_subentry().data.get(CONF_BLE_BEACON_UUID) or "").strip()
        if sub_raw and sub_raw.upper() != DEFAULT_BLE_BEACON_UUID:
            return sub_raw.upper()
        sys_raw = str(self.get_opt(CONF_SYSTEM_BLE_UUID) or "").strip()
        return (sys_raw or sub_raw or DEFAULT_BLE_BEACON_UUID).upper()

    @property
    def configured_security_pin_policy(self) -> str:
        return normalize_security_pin_policy(
            self.get_opt(CONF_SECURITY_PIN_POLICY, DEFAULT_SECURITY_PIN_POLICY)
        )

    @property
    def security_pin_policy(self) -> str:
        alarm_st = self.hass.states.get(self.alarm_entity) if self.alarm_entity else None
        return effective_security_pin_policy(
            self.configured_security_pin_policy,
            is_roaming=self.is_roaming_device,
            alarm_has_code=bool(
                alarm_st is not None and alarm_st.attributes.get("code_format")
            ),
        )

    @property
    def device_security_pin_hash(self) -> str | None:
        return (
            str(self._live_subentry().data.get(CONF_SECURITY_PIN_HASH) or "").strip()
            or None
        )

    @property
    def security_pin_hash(self) -> str | None:
        if self.device_security_pin_hash:
            return self.device_security_pin_hash
        global_cfg = self.hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG)
        if isinstance(global_cfg, dict):
            return str(global_cfg.get(CONF_SECURITY_PIN_HASH) or "").strip() or None
        return None

    @property
    def has_security_pin(self) -> bool:
        return bool(self.security_pin_hash)

    @callback
    def update_hmac_secret(self, new_secret: bytes) -> None:
        self._hmac_secret = new_secret
        self._url_signer = UrlSigner(self.hass, self.subentry_id, new_secret)
        self._last_art_proxy_url = ""

    @property
    def volume_overrides(self) -> dict[str, str]:
        raw_list = self.get_opt(CONF_VOLUME_OVERRIDES)
        if not isinstance(raw_list, list):
            return {}
        return {
            str(it["speaker"]).strip(): str(it["target"]).strip()
            for it in raw_list[:10]
            if isinstance(it, dict)
            and str(it.get("speaker") or "").strip()
            and str(it.get("target") or "").strip()
        }

    def get_volume_target_entity(self, speaker_entity_id: str | None = None) -> str:
        spk = speaker_entity_id or self.active_speaker
        return self.volume_overrides.get(spk, spk)

    @property
    def calendar_entities(self) -> list[str]:
        val = self.get_opt(CONF_CALENDAR_ENTITIES, [])
        return list(val) if isinstance(val, (list, tuple)) else []

    def _scaled_media_dimensions(self) -> tuple[int, int]:
        """Compute bounded panel artwork/wallpaper dimensions (`M-P2-18` single helper)."""
        hw = self.hardware_manifest
        try:
            width, height = int(hw.get("w") or 0), int(hw.get("h") or 0)
        except (ValueError, TypeError):
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        if width < _MIN_MEDIA_DIM or height < _MIN_MEDIA_DIM:
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        width = max(_MIN_MEDIA_DIM, min(_MAX_MEDIA_DIM, width))
        height = max(_MIN_MEDIA_DIM, min(_MAX_MEDIA_DIM, height))
        peak = max(width, height)
        if peak <= WALLPAPER_MAX_DIM:
            return width, height
        return (
            max(_MIN_MEDIA_DIM, round(width * float(WALLPAPER_MAX_DIM) / peak)),
            max(_MIN_MEDIA_DIM, round(height * float(WALLPAPER_MAX_DIM) / peak)),
        )

    @property
    def art_dimensions(self) -> tuple[int, int]:
        return self._scaled_media_dimensions()

    @property
    def wallpaper_dimensions(self) -> tuple[int, int]:
        return self._scaled_media_dimensions()

    @property
    def remote_groups(self) -> list[dict[str, Any]]:
        raw = self.get_opt(CONF_REMOTE_GROUPS, [])
        if not isinstance(raw, list):
            return []
        return [
            {
                "id": str(it["id"]).strip(),
                "name": str(it["name"]).strip(),
                "area_id": str(it.get("area_id") or "").strip(),
                "remotes": [
                    str(r).strip()
                    for r in (it.get("remotes") or [])[:10]
                    if str(r or "").strip()
                ],
            }
            for it in raw[:20]
            if isinstance(it, dict) and it.get("id") and it.get("name")
        ]

    @property
    def device_remote_group(self) -> str:
        return (
            str(
                self.get_opt(CONF_DEVICE_REMOTE_GROUP, DEFAULT_DEVICE_REMOTE_GROUP)
                or DEFAULT_DEVICE_REMOTE_GROUP
            ).strip()
            or DEFAULT_DEVICE_REMOTE_GROUP
        )

    def get_remote_entities_list(self) -> list[str]:
        raw_list = self.get_opt(CONF_REMOTES_LIST)
        return (
            [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
            if isinstance(raw_list, list)
            else []
        )

    # -----------------------------------------------------------------------
    # Scoped HMAC Resource Signing & URL Builders
    # -----------------------------------------------------------------------

    def sign_payload_resource(self, resource: str) -> str:
        return self._url_signer.sign_payload_resource(resource)

    def sign_on_demand_resource(self, resource: str) -> str:
        return self._url_signer.sign_on_demand_resource(resource)

    def verify_resource(self, resource: str, sig: str | None = None) -> bool:
        return self._url_signer.verify_resource(resource, sig)

    def get_lan_base_url(self) -> str:
        return self._url_signer.get_lan_base_url()

    def build_camera_snapshot_url(
        self, camera_entity_id: str | None = None, cache_bust: str = ""
    ) -> str:
        width, height = self.art_dimensions
        return self._url_signer.build_camera_snapshot_url(
            self.device_slug,
            (camera_entity_id or self.camera_entity or "").strip(),
            width,
            height,
            self.display_shape,
            cache_bust=cache_bust,
        )

    def build_camera_allowlist_snapshot_url(
        self, camera_entity_id: str | None = None, cache_bust: str = ""
    ) -> str:
        width, height = self.art_dimensions
        return self._url_signer.build_camera_allowlist_snapshot_url(
            self.device_slug,
            self.visible_camera_entities,
            (camera_entity_id or self.camera_entity or "").strip(),
            width,
            height,
            self.display_shape,
            cache_bust=cache_bust,
        )

    def build_camera_stream_url(self) -> str:
        max_w, max_h = self.video_max_dims
        return self._url_signer.build_camera_stream_url(
            self.device_slug,
            self.visible_camera_entities,
            max_w,
            max_h,
            self.video_max_fps,
        )

    def build_camera_audio_url(
        self,
        camera_entity_id: str | None = None,
        nr_level: str | None = None,
        fmt: str = "flac",
    ) -> str:
        return self._url_signer.build_camera_audio_url(
            self.device_slug,
            (camera_entity_id or self.camera_entity or "").strip(),
            nr_level or self.doorbell_noise_reduction,
            fmt,
        )

    def build_proxy_art_url(self, cache_bust: str) -> str:
        width, height = self.art_dimensions
        return self._url_signer.build_proxy_art_url(
            self.device_slug, width, height, self.display_shape, cache_bust
        )
