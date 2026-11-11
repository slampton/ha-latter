"""Per-device persisted runtime store, hardware manifest tracker, and configuration mixin for Latter."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store

from ..const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_ALARM_ENTITY,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_OFFSETS,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_CALENDAR_ENTITIES,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_ENTITY,
    CONF_CUSTOM_PALETTES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_APPS,
    CONF_DOORBELL_NOISE_REDUCTION,
    CONF_ESPHOME_DEVICE_ID,
    CONF_GARAGE_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_SYSTEM_BLE_UUID,
    CONF_THERMOSTAT_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DEFAULT_ACTIVITY_CARD,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_AREA_FOLLOW_DWELL_S,
    DEFAULT_AREA_HANDOFF,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_AUTO_SWITCH,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_DOCK_APPS,
    DEFAULT_DOORBELL_NOISE_REDUCTION,
    DEFAULT_NATIVE_BLE_TRACKING,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SECURITY_PIN_POLICY,
    DEFAULT_SITE_ID,
    DEFAULT_SYNC_DEVICE_AREA,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DOMAIN,
    EVENT_LATTER,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    SUBENTRY_BLE_TAG,
    normalize_device_slug,
    normalize_noise_reduction,
)
from ..http.url_signer import UrlSigner
from .activity_policy import normalize_activity_sources
from .identity import (
    find_device_entity_by_suffix,
    get_bound_esphome_device,
    read_device_hardware_manifest,
    resolve_bound_esphome_device_id,
)
from .security_policy import effective_security_pin_policy, normalize_security_pin_policy
from .traits import manifest_has_display, manifest_is_roaming, manifest_is_wearable

_LOGGER = logging.getLogger(__name__)


class LatterDeviceRuntime:
    """Manages change-gated .storage/latter.runtime.<entry_id> persistence and device_hello state."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the per-device runtime store."""
        self.hass = hass
        self.entry_id = entry_id
        self.store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}"
        )
        self._last_persisted_snapshot: dict[str, Any] | None = None
        self.hello_manifest: dict[str, Any] = {}
        self.last_boot_id: str = ""

    async def async_load(self) -> dict[str, Any]:
        """Load persisted runtime state from disk."""
        try:
            stored = await self.store.async_load()
            if isinstance(stored, dict):
                return stored
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed loading Latter runtime store: %s", err)
        return {}

    @callback
    def schedule_save(self, snapshot_builder: Callable[[], dict[str, Any]]) -> None:
        """Persist runtime state to HA Store only when semantic values change."""
        snap = snapshot_builder()
        if snap == self._last_persisted_snapshot:
            return
        self._last_persisted_snapshot = dict(snap)
        self.store.async_delay_save(snapshot_builder, delay=1.5)

    def seed_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Record the baseline snapshot after initial load."""
        self._last_persisted_snapshot = dict(snapshot)

    def apply_device_hello(
        self, boot_id: str, manifest_raw: str
    ) -> tuple[bool, dict[str, Any] | None]:
        """Parse device_hello handshake and return (is_new_boot, parsed_manifest_or_none)."""
        parsed_manifest: dict[str, Any] | None = None
        if manifest_raw and manifest_raw.strip().startswith("{"):
            try:
                parsed = json.loads(manifest_raw)
                if isinstance(parsed, dict) and "w" in parsed and "h" in parsed:
                    self.hello_manifest = parsed
                    parsed_manifest = parsed
            except (ValueError, TypeError):
                pass

        clean_boot_id = str(boot_id or "").strip()
        is_new_boot = bool(clean_boot_id and clean_boot_id != self.last_boot_id)
        if clean_boot_id:
            self.last_boot_id = clean_boot_id
        return is_new_boot, parsed_manifest


def build_coordinator_persisted_snapshot(coordinator: Any) -> dict[str, Any]:
    """Build the semantic runtime dictionary for change-gated Store persistence."""
    return {
        "rev": coordinator.rev,
        "alert_id": coordinator.alert_id,
        "active_speaker": coordinator.active_speaker,
        "last_speaker": coordinator.last_speaker,
        "active_area_id": coordinator.active_area_id or "",
        "active_remote_slot": coordinator.active_remote_slot,
        "current_wallpaper": coordinator.current_wallpaper,
        "last_media_uri": coordinator.last_media_uri,
        "last_media_type": coordinator.last_media_type,
        "last_media_title": coordinator.last_media_title,
        "last_media_artist": coordinator.last_media_artist,
        "last_media_album": coordinator.last_media_album,
        "last_media_duration": round(coordinator.last_media_duration, 1),
        "last_media_position": round(coordinator.last_media_position, 1),
        "last_device_health": coordinator.last_device_health,
    }


def apply_stored_runtime_to_coordinator(
    coordinator: Any, stored: dict[str, Any]
) -> None:
    """Restore persisted runtime fields onto `coordinator`."""
    if not stored:
        return
    coordinator.rev = max(1, int(stored.get("rev") or 1))
    coordinator.alert_id = max(0, int(stored.get("alert_id") or 0))
    saved_spk = str(stored.get("active_speaker") or "").strip()
    if saved_spk:
        coordinator.active_speaker = saved_spk
    saved_last = str(stored.get("last_speaker") or "").strip()
    if saved_last:
        coordinator.last_speaker = saved_last
    saved_area = str(stored.get("active_area_id") or "").strip()
    if saved_area and not coordinator.active_area_id:
        coordinator.active_area_id = saved_area
    saved_slot = stored.get("active_remote_slot")
    if isinstance(saved_slot, int) and 1 <= saved_slot <= 10:
        coordinator.active_remote_slot = saved_slot
    saved_wp = str(stored.get("current_wallpaper") or "").strip()
    if saved_wp:
        coordinator.current_wallpaper = saved_wp
    coordinator.last_media_uri = str(stored.get("last_media_uri") or "")
    coordinator.last_media_type = str(stored.get("last_media_type") or "music")
    coordinator.last_media_title = str(stored.get("last_media_title") or "")
    coordinator.last_media_artist = str(stored.get("last_media_artist") or "")
    coordinator.last_media_album = str(stored.get("last_media_album") or "")
    coordinator.last_media_duration = float(stored.get("last_media_duration") or 0.0)
    coordinator.last_media_position = float(stored.get("last_media_position") or 0.0)
    saved_health = stored.get("last_device_health")
    coordinator.last_device_health = (
        saved_health if isinstance(saved_health, dict) else None
    )


class LatterCoordinatorConfigMixin:
    """Configuration, hardware-manifest trait, identity, and URL-signing accessors for `LatterCoordinator`."""

    hass: HomeAssistant
    entry: ConfigEntry
    subentry: ConfigSubentry
    subentry_id: str
    _runtime: LatterDeviceRuntime
    _url_signer: UrlSigner
    _hmac_secret: bytes
    _last_art_proxy_url: str
    _cached_esphome_device_id: str | None
    _structural_snapshot: dict[str, Any]
    current_wallpaper: str
    active_speaker: str
    active_area_id: str | None

    def _capture_structural_snapshot(self) -> dict[str, Any]:
        return {
            CONF_DEVICE_SLUG: self.device_slug,
            CONF_ESPHOME_DEVICE_ID: str(
                self.get_opt(CONF_ESPHOME_DEVICE_ID, "") or ""
            ).strip(),
        }

    def has_structural_changes(self) -> bool:
        return self._capture_structural_snapshot() != self._structural_snapshot

    def _live_subentry(self) -> ConfigSubentry:
        live_sub = self.entry.subentries.get(self.subentry_id)
        if live_sub is not None:
            self.subentry = live_sub
        return self.subentry

    @property
    def device_data(self) -> dict[str, Any]:
        return dict(self._live_subentry().data)

    def update_device_config(self, merged_data: dict[str, Any]) -> None:
        self.hass.config_entries.async_update_subentry(
            self.entry, self._live_subentry(), data=merged_data
        )
        self._live_subentry()

    def get_opt(self, key: str, default: Any = None) -> Any:
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
        if isinstance(global_cfg, dict) and key in global_cfg:
            return global_cfg[key]
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
            return dr.format_mac(stored_mac)
        esp_dev = get_bound_esphome_device(self.hass, self.esphome_device_id)
        if esp_dev is not None:
            for ctype, cval in esp_dev.connections:
                if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                    return dr.format_mac(str(cval))
        ble_addr = str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()
        return (
            dr.format_mac(ble_addr)
            if len(ble_addr) == 17 and ble_addr.count(":") == 5
            else None
        )

    @property
    def device_title(self) -> str:
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

    def get_device_info(self) -> DeviceInfo:
        esp_dev_id = self.esphome_device_id
        mac = self.device_mac
        ident_key = dr.format_mac(mac) if mac else self.subentry_id
        return DeviceInfo(
            identifiers={(DOMAIN, ident_key)},
            name=self.device_title,
            manufacturer="Lampton Labs",
            model="Latter ESPHome Companion Middleware",
            sw_version=INTEGRATION_VERSION,
            configuration_url=f"homeassistant://latter/devices/{self.subentry_id}",
            **({"via_device_id": esp_dev_id} if esp_dev_id else {}),
        )

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
        return self.subentry.subentry_type == SUBENTRY_BLE_TAG

    @property
    def has_display(self) -> bool:
        return not self.is_ble_tag and manifest_has_display(self.hardware_manifest)

    @property
    def is_wearable(self) -> bool:
        return manifest_is_wearable(self.hardware_manifest)

    @property
    def is_roaming_device(self) -> bool:
        return manifest_is_roaming(self.hardware_manifest)

    @property
    def device_group(self) -> str:
        raw = str(
            self.get_opt(CONF_DEVICE_GROUP, DEFAULT_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP
        ).strip()
        return DEFAULT_DEVICE_GROUP if raw == "handhelds" and not self.has_display else raw

    @property
    def display_shape(self) -> str:
        hw_shape = str(self.hardware_manifest.get("shape") or "").strip().lower()
        return hw_shape if hw_shape in ("circle", "square") else DEFAULT_DISPLAY_SHAPE

    @property
    def default_page_size(self) -> int:
        return max(
            1, min(20, int(self.get_opt(CONF_DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE)))
        )

    @property
    def dock_apps_csv(self) -> str:
        return str(self.get_opt(CONF_DOCK_APPS, DEFAULT_DOCK_APPS)).strip()

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
    def wallpaper_source(self) -> str:
        return (
            self.current_wallpaper
            or str(self.get_opt(CONF_WALLPAPER_SOURCE, "") or "").strip()
        )

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
        if raw.startswith("#") and len(raw) == 7:
            return raw
        return self.custom_palettes[0]["hex"] if self.custom_palettes else "#3898FF"

    @property
    def weather_entity(self) -> str | None:
        val = self.get_opt(CONF_WEATHER_ENTITY)
        return str(val) if val else None

    @property
    def alarm_entity(self) -> str | None:
        val = self.get_opt(CONF_ALARM_ENTITY)
        if val:
            return str(val)
        from ..areas.context_builder import get_home_alarm_summary

        return get_home_alarm_summary(self.hass)["entity_id"] or None

    @property
    def camera_entities(self) -> list[str]:
        raw_list = self.get_opt(CONF_CAMERA_ENTITIES)
        cleaned = (
            [str(x).strip() for x in raw_list[:10] if str(x or "").strip()]
            if isinstance(raw_list, list)
            else []
        )
        if not cleaned and (single := str(self.get_opt(CONF_CAMERA_ENTITY) or "").strip()):
            cleaned = [single]
        return cleaned[:10]

    @property
    def camera_entity(self) -> str | None:
        cams = self.camera_entities
        return (
            cams[0]
            if cams
            else (str(self.get_opt(CONF_CAMERA_ENTITY) or "").strip() or None)
        )

    @property
    def thermostat_entity(self) -> str | None:
        return str(self.get_opt(CONF_THERMOSTAT_ENTITY) or "").strip() or None

    @property
    def lock_entity(self) -> str | None:
        return str(self.get_opt(CONF_LOCK_ENTITY) or "").strip() or None

    @property
    def garage_entity(self) -> str | None:
        return str(self.get_opt(CONF_GARAGE_ENTITY) or "").strip() or None

    @property
    def vacuum_entity(self) -> str | None:
        return str(self.get_opt(CONF_VACUUM_ENTITY) or "").strip() or None

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
    def ble_target_address(self) -> str:
        return str(self.get_opt(CONF_BLE_TARGET_ADDRESS, "") or "").strip()

    @property
    def ble_area_offsets(self) -> dict[str, float]:
        raw = self.get_opt(CONF_BLE_AREA_OFFSETS, {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            try:
                if (val := round(max(-25.0, min(25.0, float(v))), 1)) != 0.0:
                    out[str(k)] = val
            except (ValueError, TypeError):
                pass
        return out

    @property
    def assigned_person(self) -> str:
        return str(self.get_opt(CONF_ASSIGNED_PERSON, "") or "").strip()

    @property
    def ble_auto_switch_enabled(self) -> bool:
        return bool(self.get_opt(CONF_BLE_AUTO_SWITCH, DEFAULT_BLE_AUTO_SWITCH))

    @property
    def sync_device_area_enabled(self) -> bool:
        return self.is_roaming_device and bool(
            self.get_opt(CONF_SYNC_DEVICE_AREA, DEFAULT_SYNC_DEVICE_AREA)
        )

    @property
    def area_follow_dwell_s(self) -> int:
        try:
            return max(
                3,
                min(
                    60,
                    int(
                        self.get_opt(
                            CONF_AREA_FOLLOW_DWELL_S, DEFAULT_AREA_FOLLOW_DWELL_S
                        )
                    ),
                ),
            )
        except (ValueError, TypeError):
            return DEFAULT_AREA_FOLLOW_DWELL_S

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

    @property
    def area_handoff_enabled(self) -> bool:
        return bool(self.get_opt(CONF_AREA_HANDOFF, DEFAULT_AREA_HANDOFF))

    @property
    def art_dimensions(self) -> tuple[int, int]:
        hw = self.hardware_manifest
        try:
            w, h = int(hw.get("w") or 0), int(hw.get("h") or 0)
        except (ValueError, TypeError):
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        if w < 64 or h < 64:
            return DEFAULT_ART_SIZE, DEFAULT_ART_SIZE
        w, h = max(64, min(1920, w)), max(64, min(1920, h))
        peak = max(w, h)
        return (
            (w, h)
            if peak <= 502
            else (max(64, round(w * 480.0 / peak)), max(64, round(h * 480.0 / peak)))
        )

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
        w, h = self.art_dimensions
        return self._url_signer.build_camera_snapshot_url(
            self.device_slug,
            (camera_entity_id or self.camera_entity or "").strip(),
            w,
            h,
            self.display_shape,
            cache_bust=cache_bust,
        )

    def build_map_snapshot_url(self, location: str) -> str:
        w, h = self.art_dimensions
        return self._url_signer.build_map_snapshot_url(
            self.device_slug, location, w, h, self.display_shape
        )

    def build_wallpaper_url(self) -> str:
        w, h = self.art_dimensions
        return self._url_signer.build_wallpaper_url(
            self.device_slug, self.wallpaper_source, w, h, self.display_shape
        )

    def build_proxy_art_url(self, cache_bust: str) -> str:
        w, h = self.art_dimensions
        return self._url_signer.build_proxy_art_url(
            self.device_slug, w, h, self.display_shape, cache_bust
        )

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


def init_coordinator_runtime_fields(coord: Any) -> None:
    """Initialize transient media, weather, calendar, alert, and listener slots on a LatterCoordinator."""
    from ..areas.calendar import init_weather_attributes
    from .payloads import V3Records

    coord._cached_media_payload = None
    coord._cached_media_anchor = None
    coord._cached_area_payload = None
    coord._cached_remote_payload = None
    for unsub_attr in (
        "_unsub_core_config",
        "_unsub_speaker_state",
        "_unsub_alarm_state",
        "_unsub_remotes_state",
        "_unsub_area_entities_state",
        "_unsub_area_debounce",
        "_unsub_wallpaper_timer",
        "_unsub_doorbell_ring_state",
    ):
        setattr(coord, unsub_attr, None)
    coord._doorbell_ring_map = {}
    coord._doorbell_ring_cooldown_until = {}
    coord._ble_tracker = None
    coord._last_pushed_v3 = {}
    coord.active_speaker = (
        str(coord.get_opt(CONF_DEFAULT_SPEAKER) or "").strip() or coord.local_speaker
    )
    coord.last_speaker = coord.active_speaker
    coord.active_area_id = coord.get_opt(CONF_DEFAULT_AREA)
    coord.active_remote = ""
    coord.active_remote_slot = 1
    coord.last_area_filter = "scene"
    coord.last_area_page = 1
    coord.on_area_changed_push_slots = None
    coord.last_media_uri = ""
    coord.last_media_type = "music"
    coord.last_media_title = ""
    coord.last_media_artist = ""
    coord.last_media_album = ""
    coord.last_media_duration = 0.0
    coord.last_media_position = 0.0
    coord._resuming_guard_until = 0.0
    coord._local_needs_cold_resume = True
    coord.last_valid_raw_pic = ""
    coord._last_art_track_key = ""
    coord._last_art_proxy_url = ""
    coord._transfer_hold_until = 0.0
    coord._transfer_hold_position = 0.0
    coord._transfer_hold_title = ""
    coord._transfer_hold_artist = ""
    coord._transfer_hold_album = ""
    coord._transfer_hold_duration = 0.0
    coord.forecast_records = V3Records()
    coord.weather_attributes = init_weather_attributes(coord._pack_domain_payload)
    coord.calendar_records = V3Records()
    coord.calendar_events = []
    coord.alert_id = 0
    coord.alert_title = ""
    coord.alert_message = ""
    coord.alert_priority = "normal"
    coord.alert_duration = 8
    coord.alert_chime = True
    coord.alert_camera_url = ""
    coord.active_carousel_camera = ""
    coord.doorbell_talk_state = "idle"
    coord.last_device_health = None
    coord._doorbell_reply_task = None
    coord._doorbell_reply_resume_listen = False
    coord.doorbell_noise_reduction = normalize_noise_reduction(
        coord.get_opt(CONF_DOORBELL_NOISE_REDUCTION, DEFAULT_DOORBELL_NOISE_REDUCTION)
    )
    coord._configured_wallpaper_source = str(
        coord.get_opt(CONF_WALLPAPER_SOURCE, "") or ""
    ).strip()
    coord.current_wallpaper = ""
    coord._structural_snapshot = coord._capture_structural_snapshot()


def dispatch_coordinator_notification(
    coord: Any,
    title: str,
    message: str,
    priority: str = "normal",
    duration: int = 8,
    chime: bool = True,
    camera_entity: str | None = None,
) -> None:
    """Populate alert fields, fire EVENT_LATTER, and notify push listeners."""
    import time

    coord.alert_id += 1
    coord.alert_title = title.strip() or "Notification"
    coord.alert_message = message.strip()
    coord.alert_priority = priority.strip().lower() or "normal"
    coord.alert_duration = max(2, min(60, int(duration)))
    coord.alert_chime = bool(chime)
    coord.alert_camera_url = (
        coord.build_camera_snapshot_url(
            camera_entity, cache_bust=f"{coord.alert_id}_{int(time.time())}"
        )
        if camera_entity
        else ""
    )
    coord.hass.bus.async_fire(
        EVENT_LATTER,
        {
            "type": "notification_dispatched",
            "device_slug": coord.device_slug,
            "title": coord.alert_title,
            "message": coord.alert_message,
            "priority": coord.alert_priority,
            "camera_url": coord.alert_camera_url,
        },
    )
    coord._schedule_persist_runtime_state()
    coord.async_notify_listeners()


def match_coordinator_target(
    hass: HomeAssistant, coords: list[Any], target: str | None
) -> Any | None:
    """Match a loaded coordinator by subentry_id, Latter or ESPHome device_id, or exact slug."""
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
        if target_dev is not None:
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


async def async_push_coordinator_v3_domains(coord: Any) -> None:
    """Push any changed Protocol v3 domain payloads directly via esphome.<dev>_latter_push_v3."""
    from .identity import esphome_service

    if coord.is_ble_tag or not (
        svc := esphome_service(coord.hass, coord.esphome_device_id, "latter_push_v3")
    ):
        return
    rpc_rx = getattr(coord, "_rpc_receiver", None)
    if rpc_rx is not None and rpc_rx.is_device_unavailable():
        coord._last_pushed_v3.clear()
        return
    for dom, payload in (
        ("active_media", str(coord.get_active_media_payload()[1].get("payload") or "")),
        ("weather_forecast", str(coord.weather_attributes.get("payload") or "")),
        ("area_context", str(coord.get_area_context_payload()[1].get("payload") or "")),
        (
            "calendar_agenda",
            str(coord.get_calendar_agenda_payload()[1].get("payload") or ""),
        ),
        (
            "remote_config",
            str(coord.get_remote_config_payload()[1].get("payload") or ""),
        ),
    ):
        if not payload or coord._last_pushed_v3.get(dom) == payload:
            continue
        try:
            await coord.hass.services.async_call(
                "esphome", svc, {"domain": dom, "payload": payload}, blocking=True
            )
            coord._last_pushed_v3[dom] = payload
        except Exception as err:  # noqa: BLE001
            coord._last_pushed_v3.pop(dom, None)
            _LOGGER.debug("esphome.%s (%s) failed: %s", svc, dom, err)


def force_republish_coordinator_domains(coord: Any) -> None:
    """Force every Protocol v3 domain to bump its rev and re-push to the device."""
    coord._packer.force_republish_all_domains()
    coord.rev = max(coord.rev, coord._packer.rev)
    coord._last_pushed_v3.clear()
    coord._cached_media_payload = None
    coord._cached_media_anchor = None
    coord._cached_area_payload = None
    coord._cached_remote_payload = None
    if coord.weather_attributes and "condition" in coord.weather_attributes:
        wa = coord.weather_attributes
        wa["rev"], wa["payload"] = coord._pack_domain_payload(
            "weather_forecast",
            wa.get("condition"),
            wa.get("temperature"),
            wa.get("humidity"),
            wa.get("wind_speed"),
            wa.get("wind_bearing"),
            wa.get("high"),
            wa.get("low"),
            coord.forecast_records,
            wa.get("sun_state"),
            wa.get("sun_elevation"),
            wa.get("sun_azimuth"),
            wa.get("sun_next_rising"),
            wa.get("sun_next_setting"),
            wa.get("moon_phase"),
        )
    coord.async_update_listeners()
    if not coord.is_ble_tag:
        coord.entry.async_create_background_task(
            coord.hass,
            coord.async_push_dirty_v3_domains(),
            f"latter_push_v3_republish_{coord.device_slug}",
        )
