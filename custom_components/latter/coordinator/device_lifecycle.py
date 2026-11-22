"""Device connection predicates, `device_hello` handshake, prefs convergence, and commands (`L3`)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import json
import time
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_GAMES_ITEMS,
    CONF_NATIVE_BLE_TRACKING,
    CONF_TOOLS_ITEMS,
    DOMAIN,
    EVENT_LATTER,
)
from ..identity import esphome_service, find_device_entity_by_suffix
from ..media.playback import (
    enforce_local_speaker_if_remote_idle,
    execute_coordinator_media_command,
    set_coordinator_active_speaker,
)
from ..presence.ble_fabric import get_ble_fabric
from ..protocol_codec import parse_dirty_prefs_records
from ..protocol_policy import mint_pin_session_key
from ..protocol_specs import DEVICE_PREF_KEYS
from ..repairs_keys import (
    ISSUE_ROLLED_BACK,
    device_health_issue_id,
    evaluate_device_health,
    parse_device_health,
)
from ..studio.settings_cleaners import clean_device_settings
from .ha_registry_sync import CoordinatorRegistrySyncMixin

_RPC_OUTBOX_SUFFIXES: tuple[str, ...] = ("_system_rpc_outbox", "_rpc_outbox")
_RPC_OUTBOX_NAMES: tuple[str, ...] = ("System: RPC Outbox", "RPC Outbox")
_RPC_OUTBOX_UID_SUFFIXES: tuple[str, ...] = ("/text_sensor/System: RPC Outbox",)
_MIN_ALERT_DURATION_S = 2
_MAX_ALERT_DURATION_S = 60


def _parse_bool_flag(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _parse_opt_bool(val: Any) -> bool | None:
    if val is None or str(val).strip() == "":
        return None
    return _parse_bool_flag(val)


def _parse_kb(val: Any) -> int | None:
    if val is None or isinstance(val, bool) or str(val).strip() == "":
        return None
    try:
        iv = round(float(val))
        return iv if iv >= 0 else None
    except (TypeError, ValueError):
        return None


class CoordinatorLifecycleMixin(CoordinatorRegistrySyncMixin):
    """Unified online/sleep predicates, `device_hello`, timer/alarm ticks, and device actions."""

    def _resolve_rpc_outbox_entity_id(self) -> str | None:
        if self._rpc_receiver is not None:
            tracked = getattr(
                self._rpc_receiver,
                "tracked_entity_id",
                getattr(self._rpc_receiver, "_tracked_entity_id", None),
            )
            if tracked:
                return str(tracked)
        if not self.esphome_device_id:
            return None
        return find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "sensor",
            _RPC_OUTBOX_SUFFIXES,
            original_names=_RPC_OUTBOX_NAMES,
            unique_id_suffixes=_RPC_OUTBOX_UID_SUFFIXES,
        )

    def is_rpc_outbox_unavailable(self) -> bool:
        """Return True when the bound RPC outbox entity exists in HA and reports `unavailable`."""
        if self._rpc_receiver is not None and hasattr(
            self._rpc_receiver, "is_device_unavailable"
        ):
            return bool(self._rpc_receiver.is_device_unavailable())
        ent_id = self._resolve_rpc_outbox_entity_id()
        if not ent_id:
            return False
        st = self.hass.states.get(ent_id)
        return st is not None and st.state == STATE_UNAVAILABLE

    @property
    def is_online(self) -> bool:
        """Single canonical online predicate across ESPHome Devices and BLE Tags (`M-P2-18`)."""
        if self.is_ble_tag:
            return not self.is_device_away()
        return self.is_device_online()

    @property
    def radio_connected(self) -> bool:
        """Return True when the bound ESPHome Device has an active online API connection and is not hibernating."""
        return (
            not self.is_ble_tag
            and not self._entered_hibernate
            and self.is_device_online()
        )

    def is_device_online(self) -> bool:
        """Return True when the bound ESPHome Device has an active connection in Home Assistant."""
        if self.is_ble_tag or self.is_rpc_outbox_unavailable():
            return False
        saw_conn_sensor = False
        for sfx in ("_system_wi_fi_signal", "_wi_fi_signal", "_ip_address"):
            ent_id = find_device_entity_by_suffix(
                self.hass,
                self.esphome_device_id,
                "sensor",
                (sfx,),
            )
            if not ent_id:
                continue
            saw_conn_sensor = True
            st = self.hass.states.get(ent_id)
            if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
                return True
        if saw_conn_sensor or self._entered_hibernate:
            return False
        if (
            self.device_telemetry.get("updated_at") is not None
            or bool(self._runtime.last_boot_id)
        ):
            outbox_id = self._resolve_rpc_outbox_entity_id()
            if outbox_id:
                st = self.hass.states.get(outbox_id)
                return st is not None and st.state != STATE_UNAVAILABLE
        return False

    def is_ble_sleep_expected(self) -> bool:
        """Pure query: return True when BLE silence is intentional (light sleep/docked pause or hibernate)."""
        if self.is_ble_tag:
            return False
        if self.is_device_online():
            telem_ble = self.device_telemetry.get("ble_active")
            if isinstance(telem_ble, bool):
                return not telem_ble
            ble_ent_id = find_device_entity_by_suffix(
                self.hass,
                self.esphome_device_id,
                "binary_sensor",
                ("_ble_radio_active",),
            )
            ble_st = self.hass.states.get(ble_ent_id) if ble_ent_id else None
            return bool(ble_st is not None and ble_st.state == "off")
        return bool(
            self._entered_hibernate
            and int(self.hardware_manifest.get("battery", 0) or 0) == 1
        )

    def is_device_away(self) -> bool:
        """Return True when native BLE tracking confirms the Device or BLE Tag is away."""
        if not self.native_ble_tracking_enabled or self._ble_tracker is None:
            return False
        if not self._ble_tracker.is_away:
            return False
        if self.is_ble_tag:
            return True
        if not self.is_device_online():
            return not self.is_ble_sleep_expected()
        telem_ble = self.device_telemetry.get("ble_active")
        if isinstance(telem_ble, bool):
            return telem_ble
        ble_ent_id = find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "binary_sensor",
            ("_ble_radio_active",),
        )
        ble_st = self.hass.states.get(ble_ent_id) if ble_ent_id else None
        return bool(ble_st is not None and ble_st.state == "on")

    async def async_sync_presence_beacon(self, trigger: str = "options") -> None:
        _ = trigger
        if self.is_ble_tag:
            return
        self._cached_prefs_payload = None

    @callback
    def _apply_device_health(
        self, manifest: dict[str, Any], boot_id: str
    ) -> None:
        if (
            boot_id
            and self.last_device_health is not None
            and self.last_device_health.get("boot_id") == boot_id
        ):
            return
        health = parse_device_health(manifest)
        reported_at = dt_util.now().isoformat(timespec="seconds")
        self.last_device_health = {
            "boot_id": boot_id,
            "sdk": health.sdk,
            "reset": health.reset,
            "crash": health.crash,
            "rollback": health.rollback,
            "reported_at": reported_at,
        }
        self.schedule_persist_runtime_state()
        actions = evaluate_device_health(health)
        for kind in actions.delete_issues:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                device_health_issue_id(kind, self.subentry_id),
            )
        for kind, extra in actions.raise_issues.items():
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                device_health_issue_id(kind, self.subentry_id),
                is_fixable=True,
                severity=(
                    ir.IssueSeverity.ERROR
                    if kind == ISSUE_ROLLED_BACK
                    else ir.IssueSeverity.WARNING
                ),
                translation_key=kind,
                translation_placeholders={
                    "device": self.device_title,
                    "time": reported_at,
                    **extra,
                },
                config_entry_id=self.entry.entry_id,
            )

    async def _async_finish_reconnect_post_delay(self) -> None:
        enforce_local_speaker_if_remote_idle(self, "device_reconnect_post_delay")
        if (
            self._ble_tracker is not None
            and self._ble_tracker.current_area_id
            and self._ble_tracker.current_area_id != self.active_area_id
        ):
            self.async_set_active_area(
                self._ble_tracker.current_area_id,
                handoff_media=False,
                sync_device_registry=True,
                ble_driven=True,
            )
        self.async_notify_listeners()
        if self.on_area_changed_push_slots is not None:
            await self.on_area_changed_push_slots(self)

    async def _async_handle_reconnect(self) -> None:
        if self._unsub_reconnect_post_delay is not None:
            self._unsub_reconnect_post_delay()
            self._unsub_reconnect_post_delay = None
        enforce_local_speaker_if_remote_idle(self, "device_reconnect")
        if self._ble_tracker is not None:
            self._ble_tracker.reset_for_device_wake()
            if (
                self._ble_tracker.current_area_id
                and self._ble_tracker.current_area_id != self.active_area_id
            ):
                self.async_set_active_area(
                    self._ble_tracker.current_area_id,
                    handoff_media=False,
                    sync_device_registry=True,
                    ble_driven=True,
                )
        self.async_notify_listeners()

        @callback
        def _on_post_delay(_now: datetime) -> None:
            self._unsub_reconnect_post_delay = None
            self.create_background_task(
                self._async_finish_reconnect_post_delay(),
                f"latter_reconnect_post_delay_{self.device_slug}",
            )

        self._unsub_reconnect_post_delay = async_call_later(
            self.hass, 1.5, _on_post_delay
        )

    async def async_provision_pin_session_key(self) -> bool:
        """Mint a fresh per-boot/reconnect HMAC PIN session key in RAM and push to firmware (`M-P0-01`)."""
        if self.is_ble_tag:
            return False
        key_id, key_bytes = mint_pin_session_key()
        self._pin_key_id = key_id
        self._pin_key_bytes = key_bytes
        self._pin_last_nonce = 0
        return await self.async_send_device_command(
            f"set_pin_key:{key_id}:{key_bytes.hex()}"
        )

    def _resolve_next_display_power(
        self, power_state: Any, screensaver_active: Any
    ) -> int:
        next_power = self.display_power_state
        if power_state is not None and not isinstance(power_state, bool):
            try:
                parsed_p = int(float(power_state))
                if parsed_p in (0, 1, 2):
                    next_power = parsed_p
            except (TypeError, ValueError):
                pass
        elif screensaver_active is not None:
            next_power = 1 if _parse_bool_flag(screensaver_active) else 0
        if (
            screensaver_active is not None
            and next_power == 0
            and _parse_bool_flag(screensaver_active)
        ):
            next_power = 1
        return next_power

    @callback
    def apply_display_state(
        self,
        power_state: Any,
        brightness_pct: Any,
        screensaver_active: Any = None,
    ) -> None:
        """Apply live `display_state` RPC telemetry (`0`=awake, `1`=screensaver, `2`=off)."""
        next_power = self._resolve_next_display_power(power_state, screensaver_active)
        next_bri = self.display_brightness_pct
        if brightness_pct is not None and not isinstance(brightness_pct, bool):
            try:
                parsed_b = round(float(brightness_pct))
                if parsed_b > 0:
                    next_bri = max(1, min(100, parsed_b))
            except (TypeError, ValueError):
                pass

        self.display_power_state = next_power
        self.display_brightness_pct = next_bri
        self.async_update_listeners()

    @callback
    def apply_device_telemetry(self, payload: Mapping[str, Any]) -> None:
        """Apply live `device_telemetry` RPC diagnostics and update hibernate/BLE state (`M-P1-20`)."""
        raw_link = payload.get("link_json", payload.get("link"))
        link_dict: dict[str, Any] = {}
        if isinstance(raw_link, Mapping):
            link_dict = dict(raw_link)
        elif isinstance(raw_link, str) and raw_link.strip().startswith("{"):
            try:
                parsed_link = json.loads(raw_link)
                if isinstance(parsed_link, dict):
                    link_dict = parsed_link
            except (TypeError, ValueError):
                link_dict = {}

        link_state = str(
            link_dict.get("state")
            or link_dict.get("status")
            or payload.get("link_state")
            or ""
        ).strip().lower()
        if link_state == "hibernating":
            if not self._entered_hibernate:
                self._entered_hibernate = True
                self.schedule_persist_runtime_state()
        elif link_dict and self._entered_hibernate:
            self._entered_hibernate = False
            self.schedule_persist_runtime_state()

        ble_active = _parse_opt_bool(payload.get("ble_active"))
        if ble_active is True and self._ble_tracker is not None:
            self._ble_tracker.note_ble_radio_active(time.monotonic())

        self.device_telemetry = {
            "link": link_dict,
            "int_ram_free_kb": _parse_kb(payload.get("int_ram_free_kb")),
            "int_ram_min_kb": _parse_kb(payload.get("int_ram_min_kb")),
            "int_ram_largest_kb": _parse_kb(payload.get("int_ram_largest_kb")),
            "psram_min_kb": _parse_kb(payload.get("psram_min_kb")),
            "ble_active": ble_active,
            "profiler_on": bool(_parse_opt_bool(payload.get("profiler_on"))),
            "updated_at": dt_util.now().isoformat(timespec="seconds"),
        }
        self.async_update_listeners()

    def _merge_hello_device_prefs(
        self, dev_seq: int, incoming_prefs: dict[str, Any]
    ) -> bool:
        ble_tracking_changed = False
        if self.prefs_seq == 0:
            raw_sub = self._live_subentry().data
            seeded = {k: v for k, v in incoming_prefs.items() if k not in raw_sub}
            if seeded:
                cleaned = clean_device_settings(
                    seeded,
                    current=self.device_data,
                    is_round_display=self.is_round_display,
                    supports_hw_jpeg=self.supports_hw_jpeg,
                )
                if cleaned:
                    self.update_device_config(
                        {**self.device_data, **cleaned}, bump_prefs_seq=False
                    )
                    ble_tracking_changed = CONF_NATIVE_BLE_TRACKING in cleaned
                    if not ble_tracking_changed:
                        self._applied_options_snapshot = self._capture_options_snapshot()
            self.prefs_seq = max(
                1, dev_seq + (1 if incoming_prefs and dev_seq > 0 else 0)
            )
            cur_sub = self._live_subentry().data
            for key in (
                *DEVICE_PREF_KEYS,
                CONF_NATIVE_BLE_TRACKING,
                CONF_DEVICE_CUSTOM_COLOR,
                CONF_TOOLS_ITEMS,
                CONF_GAMES_ITEMS,
            ):
                if key in cur_sub:
                    self.prefs_key_seq.setdefault(key, self.prefs_seq)
            return ble_tracking_changed

        if dev_seq <= 0:
            return False
        if not incoming_prefs:
            self.prefs_seq = max(self.prefs_seq, dev_seq)
            return False

        accepted = {
            k: v
            for k, v in incoming_prefs.items()
            if self.prefs_key_seq.get(k, 0) <= dev_seq
        }
        new_seq = max(self.prefs_seq, dev_seq) + 1
        if accepted:
            cleaned = clean_device_settings(
                accepted,
                current=self.device_data,
                is_round_display=self.is_round_display,
                supports_hw_jpeg=self.supports_hw_jpeg,
            )
            if cleaned:
                self.update_device_config(
                    {**self.device_data, **cleaned}, bump_prefs_seq=False
                )
                for key in cleaned:
                    self.prefs_key_seq[key] = new_seq
                ble_tracking_changed = CONF_NATIVE_BLE_TRACKING in cleaned
                if not ble_tracking_changed:
                    self._applied_options_snapshot = self._capture_options_snapshot()
        self.prefs_seq = new_seq
        return ble_tracking_changed

    async def async_handle_device_hello(
        self,
        boot_id: str,
        manifest_raw: str,
        prefs_seq: int = 0,
        dirty_prefs: str = "",
    ) -> None:
        """Process firmware `device_hello`, reset boot-scoped timers on reboot, and converge prefs."""
        self._entered_hibernate = False
        is_new_boot, parsed = self._runtime.apply_device_hello(boot_id, manifest_raw)
        if parsed is not None:
            if self._ble_tracker is not None:
                self._ble_tracker.update_manifest_beacon(parsed.get("beacon"))
            self._apply_device_health(parsed, str(boot_id or "").strip())
        if is_new_boot:
            self._local_needs_cold_resume = True
            self.handle_timer_alarm_state(False, False, 0, False)

        dev_seq = max(0, int(prefs_seq or 0))
        incoming_prefs = parse_dirty_prefs_records(dirty_prefs)
        if self._merge_hello_device_prefs(dev_seq, incoming_prefs):
            self.sync_ble_tracker()
            self._applied_options_snapshot = self._capture_options_snapshot()
            get_ble_fabric(self.hass).notify_occupancy_listeners()

        self._cached_prefs_payload = None
        self.schedule_persist_runtime_state()
        self._last_pushed_v3.clear()
        await self.async_provision_pin_session_key()
        self.force_republish_all_domains()
        await self.async_push_beacon_uuid()
        await self._async_handle_reconnect()
        await self.async_sync_presence_beacon("hello")

    async def async_update_device_prefs(
        self,
        updates: Mapping[str, Any],
        *,
        min_next_seq: int | None = None,
        force_bump: bool = False,
    ) -> dict[str, Any]:
        """Validate, persist, and push subentry device preferences (sleep-safe when offline)."""
        cleaned = clean_device_settings(
            dict(updates),
            current=self.device_data,
            is_round_display=self.is_round_display,
            supports_hw_jpeg=self.supports_hw_jpeg,
        )
        if not cleaned and not force_bump:
            return {}
        prev_seq = self.prefs_seq
        if cleaned:
            self.update_device_config(
                {**self.device_data, **cleaned}, bump_prefs_seq=True
            )
        if (force_bump and self.prefs_seq == prev_seq) or (
            min_next_seq is not None and self.prefs_seq < min_next_seq
        ):
            target_seq = max(
                self.prefs_seq + (1 if self.prefs_seq == prev_seq else 0),
                min_next_seq or 1,
            )
            self.prefs_seq = max(1, target_seq)
            for key in cleaned:
                self.prefs_key_seq[key] = self.prefs_seq
            self._cached_prefs_payload = None
            self.schedule_persist_runtime_state()
        self._cached_prefs_payload = None
        if "screensaver_mode" in cleaned or "screensaver_style" in cleaned:
            self.bind_screensaver_cycle_timer()
        if CONF_NATIVE_BLE_TRACKING in cleaned:
            await self.async_apply_options()
            self.async_update_listeners()
        else:
            self.async_update_listeners()
            self.async_notify_listeners()
        return cleaned

    async def async_handle_set_device_prefs(
        self, base_seq: int, changes_raw: str
    ) -> None:
        """Apply live touchscreen preference edits and echo canonical `device_prefs` back to clear `dirty_mask`."""
        incoming = parse_dirty_prefs_records(changes_raw)
        if not incoming:
            return
        await self.async_update_device_prefs(
            incoming,
            min_next_seq=max(self.prefs_seq, max(0, int(base_seq or 0))) + 1,
            force_bump=True,
        )

    @callback
    def _stop_timer_tick(self) -> None:
        if self._unsub_timer_tick is not None:
            self._unsub_timer_tick()
            self._unsub_timer_tick = None

    @callback
    def _sync_timer_tick(self) -> None:
        need_tick = self.timer_running and self.current_timer_remaining_sec > 0
        if need_tick:
            if self._unsub_timer_tick is None:

                @callback
                def _on_timer_tick(_now: datetime) -> None:
                    if not (
                        self.timer_running and self.current_timer_remaining_sec > 0
                    ):
                        self._stop_timer_tick()
                    self._notify_timer_tick_listeners()

                self._unsub_timer_tick = async_track_time_interval(
                    self.hass, _on_timer_tick, timedelta(seconds=1)
                )
        else:
            self._stop_timer_tick()

    @callback
    def handle_timer_alarm_state(  # noqa: PLR0913, PLR0917
        self,
        timer_running: bool,
        timer_paused: bool,
        remaining_sec: int,
        ringing: bool,
        stopwatch_running: bool = False,
        stopwatch_paused: bool = False,
        stopwatch_elapsed_sec: int = 0,
    ) -> None:
        """Update event-driven timer, stopwatch, and alarm state and manage the isolated 1 Hz tick."""
        now_mono = time.monotonic()
        now_utc = dt_util.utcnow()
        self.timer_running = bool(timer_running)
        self.timer_paused = bool(timer_paused) and not self.timer_running
        self.timer_remaining_sec = max(0, int(remaining_sec or 0))
        self._timer_anchor_mono = now_mono
        self.timer_ends_at_utc = (
            (now_utc + timedelta(seconds=self.timer_remaining_sec)).isoformat(
                timespec="seconds"
            )
            if self.timer_running and self.timer_remaining_sec > 0
            else ""
        )
        self.alarm_ringing = bool(ringing)
        self.stopwatch_running = bool(stopwatch_running)
        self.stopwatch_paused = bool(stopwatch_paused) and not self.stopwatch_running
        self.stopwatch_elapsed_sec = max(0, int(stopwatch_elapsed_sec or 0))
        self._stopwatch_anchor_mono = now_mono
        self.stopwatch_started_at_utc = (
            (now_utc - timedelta(seconds=self.stopwatch_elapsed_sec)).isoformat(
                timespec="seconds"
            )
            if self.stopwatch_running
            else ""
        )

        self._sync_timer_tick()
        self._notify_timer_tick_listeners()
        self.async_update_listeners()

    async def async_set_screen_light(
        self, *, turn_on: bool, brightness_pct: int | None = None
    ) -> None:
        """Control the Device's display power & brightness via `latter_device_command` (`M-P1-21`)."""
        if turn_on:
            if brightness_pct is not None and not isinstance(brightness_pct, bool):
                pct = max(1, min(100, round(float(brightness_pct))))
                await self.async_send_device_command(f"set_screen_bri:{pct}")
                self.display_brightness_pct = pct
            else:
                await self.async_send_device_command("wake_screen")
            self.display_power_state = 0
        else:
            await self.async_send_device_command("screen_off")
            self.display_power_state = 2
        self.async_update_listeners()

    async def async_set_screensaver(self, active: bool) -> None:
        """Activate or deactivate the Device screensaver via `latter_device_command` (`M-P1-21`)."""
        await self.async_send_device_command(
            "activate_screensaver" if active else "deactivate_screensaver"
        )
        self.display_power_state = 1 if active else 0
        self.async_update_listeners()

    async def async_dismiss_alert(self) -> None:
        """Dismiss any active ringing alarm/timer/alert on the Device."""
        await self.async_send_device_command("dismiss_ringing")

    @callback
    def _apply_device_command_side_effects(self, cmd: str) -> None:
        if cmd == "dismiss_ringing":
            self.alarm_ringing = False
            self.async_update_listeners()
        elif cmd == "cancel_timer":
            self.timer_running = False
            self.timer_paused = False
            self.timer_remaining_sec = 0
            self.timer_ends_at_utc = ""
            self._sync_timer_tick()
            self._notify_timer_tick_listeners()
            self.async_update_listeners()
        elif cmd == "reset_stopwatch":
            self.stopwatch_running = False
            self.stopwatch_paused = False
            self.stopwatch_elapsed_sec = 0
            self.stopwatch_started_at_utc = ""
            self._sync_timer_tick()
            self.async_update_listeners()

    async def async_send_device_command(
        self, command: str, *, raise_if_offline: bool = False
    ) -> bool:
        """Send an immediate action (`restart`, `find_my`, `activate_screensaver`, `trigger_va`, etc.) to the Device."""
        cmd = str(command or "").strip().lower()
        safe_cmd_label = "set_pin_key" if cmd.startswith("set_pin_key:") else cmd
        if self.is_ble_tag:
            if raise_if_offline:
                raise HomeAssistantError("BLE tags do not accept device commands")
            return False

        wifi_ent_id = find_device_entity_by_suffix(
            self.hass,
            self.esphome_device_id,
            "sensor",
            ("_system_wi_fi_signal", "_wi_fi_signal", "_ip_address"),
        )
        wifi_st = self.hass.states.get(wifi_ent_id) if wifi_ent_id else None
        wifi_offline = wifi_st is not None and wifi_st.state == STATE_UNAVAILABLE
        svc = esphome_service(
            self.hass, self.esphome_device_id, "latter_device_command"
        )

        if not wifi_offline and not self.is_rpc_outbox_unavailable():
            if svc:
                try:
                    await self.hass.services.async_call(
                        "esphome", svc, {"command": cmd}, blocking=True
                    )
                    self._apply_device_command_side_effects(cmd)
                    return True
                except Exception as err:
                    if raise_if_offline:
                        raise HomeAssistantError(
                            f"Failed to send '{safe_cmd_label}' to {self.device_title}: {err}"
                        ) from err
                    return False
            if cmd == "restart" and (
                restart_ent := self.device_entity(
                    "button", "_actions_restart_device", "_restart_device"
                )
            ):
                rst_st = self.hass.states.get(restart_ent)
                if rst_st is None or rst_st.state != STATE_UNAVAILABLE:
                    await self.hass.services.async_call(
                        "button",
                        "press",
                        {ATTR_ENTITY_ID: restart_ent},
                        blocking=True,
                    )
                    return True

        if raise_if_offline:
            raise HomeAssistantError(
                f"{self.device_title} is currently offline or sleeping"
            )
        return False

    async def async_execute_media_command(  # noqa: PLR0913, PLR0917
        self,
        command: str,
        speaker: str | None = None,
        seek_position: float | None = None,
        media_id: str | None = None,
        media_type: str | None = None,
        enqueue: str | None = None,
        group_members: list[str] | str | None = None,
        *,
        radio_mode: bool = False,
        queue_item_id: str | None = None,
        pos_shift: int | str | None = None,
    ) -> None:
        await execute_coordinator_media_command(
            self,
            command,
            speaker,
            seek_position,
            media_id,
            media_type,
            enqueue,
            group_members,
            radio_mode=radio_mode,
            queue_item_id=queue_item_id,
            pos_shift=pos_shift,
        )

    @callback
    def async_set_active_speaker(
        self, speaker_entity_id: str, transfer_queue: bool = True
    ) -> None:
        set_coordinator_active_speaker(
            self, speaker_entity_id, transfer_queue=transfer_queue
        )

    @callback
    def async_dispatch_notification(  # noqa: PLR0913, PLR0917
        self,
        title: str,
        message: str,
        priority: str = "normal",
        duration: int = 8,
        chime: bool = True,
        camera_entity: str | None = None,
    ) -> None:
        self.alert_id += 1
        self.alert_title = title.strip() or "Notification"
        self.alert_message = message.strip()
        self.alert_priority = priority.strip().lower() or "normal"
        self.alert_duration = max(
            _MIN_ALERT_DURATION_S, min(_MAX_ALERT_DURATION_S, int(duration))
        )
        self.alert_chime = bool(chime)
        clean_cam = str(camera_entity or "").strip()
        self.alert_camera_entity = clean_cam
        self.alert_camera_url = (
            self.build_camera_snapshot_url(
                clean_cam, cache_bust=f"{self.alert_id}_{int(time.time())}"
            )
            if clean_cam
            else ""
        )
        self.hass.bus.async_fire(
            EVENT_LATTER,
            {
                "type": "notification_dispatched",
                "device_slug": self.device_slug,
                "title": self.alert_title,
                "message": self.alert_message,
                "priority": self.alert_priority,
                "camera_url": self.alert_camera_url,
                "camera_entity": self.alert_camera_entity,
            },
        )
        self.schedule_persist_runtime_state()
        self.async_notify_listeners()
