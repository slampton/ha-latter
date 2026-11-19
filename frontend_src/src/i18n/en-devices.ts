/**
 * Device-scope, Managed inventory, Wallpaper gallery, & Discovered onboarding UI strings
 * (`D-061` — Home Assistant Sentence case).
 */

export const EN_DEVICES_STRINGS = {
  // Offline / sleeping & BLE transmitter banners (D-066)
  "offline.device_banner_title": "Device is offline or hibernating",
  "offline.device_sleeping_title": "Device is sleeping",
  "offline.device_banner_body":
    "Settings saved here are queued in Home Assistant and sync automatically when this Device wakes or reconnects. Live quick actions are unavailable while offline.",
  "offline.ble_tx_off_title": "BLE transmitter not active ({state})",
  "offline.ble_tx_off_body":
    "Enable the BLE Transmitter sensor in the Home Assistant Companion App on this phone so Bluetooth proxies can detect its Area.",

  // Device card titles & disambiguated display sections (D-066 / Q7 / Q8)
  "card.status": "Status",
  "card.quick_actions": "Quick actions",
  "card.assignments": "Assignments",
  "card.timers_alarms": "Timers & alarms",
  "card.sensors_controls": "Sensors & controls",
  "card.wallpapers": "Wallpapers",
  "card.brightness": "Brightness",
  "card.clock": "Clock",
  "card.colors": "Colors",
  "card.screensaver": "Screensaver",
  "card.home_screen_appearance": "Home screen appearance",
  "card.music_appearance": "Music appearance",
  "card.home_screen": "Home screen",
  "card.app_dock": "App Dock",
  "card.diagnostics": "Diagnostics",
  "card.developer_telemetry": "Developer & telemetry",
  "card.replace_hardware": "Replace hardware",
  "card.replace_hardware_body":
    "Replaced a physical board or reflashed under a new ESPHome node? Use Reconfigure on this Device entry in Home Assistant Integrations to rebind its hardware identity while keeping all shortcuts, Area rules, and settings.",
  "card.danger_zone": "Danger zone",

  // Device list & discovered devices (D-041 / D-066 / Q12)
  "devices.inventory_heading": "Inventory",
  "devices.col_device": "Device",
  "devices.col_model": "Model",
  "devices.col_area": "Area",
  "devices.col_group": "Group",
  "devices.col_status": "Status",
  "devices.filter_aria": "Filter managed Devices by category",
  "devices.open_row_aria": "Open {title}",
  "devices.all": "All Devices",
  "devices.online": "Online Devices",
  "devices.roaming": "Roaming Devices",
  "devices.stationary": "Stationary Devices",
  "devices.latter_displays": "Latter displays",
  "devices.ble_tracked": "BLE-tracked Devices",
  "devices.phones": "Phones",
  "devices.ble_tags": "BLE tags",
  "devices.assigned_person": "Assigned to a person",
  "devices.updates_available": "Updates available",
  "devices.group_prefix": "Group: {name}",
  "devices.empty_filtered": "No Devices match this category.",
  "devices.empty_zero_title": "No managed Devices yet",
  "devices.empty_zero_body":
    "Adopt discovered Latter displays, add Bluetooth tags for Area presence, or configure System Area sensor fusion.",
  "devices.open_discovered": "Open Discovered",
  "devices.open_area_presence": "Configure Area presence",

  "discovered.latter_devices": "Latter Devices",
  "discovered.bluetooth_devices": "Bluetooth devices",
  "discovered.empty_latter":
    "No unconfigured Latter Devices found in Home Assistant. Newly added ESPHome Devices running Latter firmware appear here automatically.",
  "discovered.web_installer": "Open Web Installer",
  "discovered.getting_started": "Getting started guide",
  "discovered.ignored_count": "Ignored ({count})",
  "discovered.default_latter_title": "Latter Device",
  "discovered.default_latter_model": "Latter ESPHome Device",
  "discovered.default_ble_kind": "BLE device",
  "discovered.meta_node": "Node: {node}",
  "discovered.meta_area": "Area: {area}",
  "discovered.meta_nearest_area": "Nearest Area: {area}",
  "discovered.group_select_aria": "Device group for {title}",
  "discovered.auto_group_option": "Auto ({group})",
  "discovered.person_select_aria": "Assigned person for {title}",
  "discovered.ignore_aria": "Ignore {title}",
  "discovered.restore_aria": "Restore {title}",
  "discovered.search_ble_aria": "Search discovered Bluetooth devices",
  "discovered.search_ble_placeholder": "Search name, address, or Area…",
  "discovered.filter_ble_aria": "Filter discovered Bluetooth devices",
  "discovered.all_ble": "All Bluetooth devices",
  "discovered.phones_trackers": "Phones & trackers",
  "discovered.named_ble": "Named BLE advertisements",
  "discovered.sort_ble_aria": "Sort discovered Bluetooth devices",
  "discovered.sort_name": "Sort: Name (A–Z)",
  "discovered.sort_rssi": "Sort: Signal strength",
  "discovered.sort_area": "Sort: Nearest Area",
  "discovered.pause_list": "Pause list",
  "discovered.resume_list": "Resume list",
  "discovered.paused_hint":
    "List updates paused ({count} shown). Select Resume list to refresh.",
  "discovered.empty_ble_filtered": "No Bluetooth devices match this filter.",
  "discovered.empty_ble_none": "No unadopted Bluetooth devices nearby.",
  "discovered.adopted_toast": "Adopted \"{title}\"",
  "discovered.ignored_toast": "Ignored \"{title}\"",
  "discovered.restored_toast": "Restored \"{title}\" to discovered list",

  // Wallpaper gallery & multipart upload (D-25 / Q5)
  "wp_gallery.empty": "No wallpapers available yet.",
  "wp_gallery.use_aria": "Use wallpaper {name}",
  "wp_gallery.star_add_aria": "Star {name} for rotation",
  "wp_gallery.star_remove_aria": "Remove {name} from favorites",
  "wp_gallery.star_active_title": "Starred for rotation",
  "wp_gallery.star_inactive_title": "Star for rotation",
  "wp_gallery.delete_aria": "Delete wallpaper {name}",
  "wp_gallery.uploaded": "Uploaded",
  "wp_gallery.builtin": "Built-in",
  "wp_gallery.file_aria": "Wallpaper image (up to 15 MB)",
  "wp_gallery.upload_photo": "Upload photo",
  "wp_gallery.uploading": "Uploading…",
  "wp_gallery.uploading_photo": "Uploading photo…",
  "wp_gallery.upload_progress_aria": "Wallpaper upload progress",

  // Device -> Overview (D-003 / D-066 / F-01)
  "dev_overview.waiting_for_reading": "Waiting for reading",
  "dev_overview.tile_area": "Area",
  "dev_overview.tile_current_area": "Current Area",
  "dev_overview.tile_closest_proxy": "Closest proxy",
  "dev_overview.ble_presence_meta": "BLE presence",
  "dev_overview.tile_battery": "Battery",
  "dev_overview.tile_power": "Power",
  "dev_overview.tile_ble_signal": "BLE signal",
  "dev_overview.tile_wifi_signal": "Wi-Fi signal",
  "dev_overview.tile_ble_target": "BLE target",
  "dev_overview.ble_address_meta": "Bluetooth address",
  "dev_overview.tile_firmware": "Firmware",
  "dev_overview.qa_find_my": "Find my Device",
  "dev_overview.qa_trigger_va": "Trigger voice assistant",
  "dev_overview.qa_activate_screensaver": "Activate screensaver",
  "dev_overview.qa_restart": "Restart Device",
  "dev_overview.restart_device": "Restart Device",
  "dev_overview.restart_device_desc":
    "Reboots this Device; Wi-Fi and active sessions reconnect automatically.",
  "dev_overview.restart_btn": "Restart",
  "dev_overview.empty_quick_actions": "No live actions reported by this Device.",
  "dev_overview.device_group_label": "Device group",
  "dev_overview.device_group_custom_desc":
    "Uses individual operational settings; save as a reusable group or pick an existing preset.",
  "dev_overview.device_group_preset_desc":
    "Applies shared operational settings (power, wake word, brightness, BLE).",
  "dev_overview.device_category_label": "Device category",
  "dev_overview.device_category_desc":
    "Classifies this Bluetooth Device under Phones or BLE tags across Managed devices.",
  "dev_overview.auto_category_option": "Auto ({category})",
  "dev_overview.assigned_person_label": "Assigned person",
  "dev_overview.assigned_person_desc":
    "Links this Device's Area presence to a Home Assistant person entity.",
  "dev_overview.unassigned_option": "— Unassigned —",
  "dev_overview.remote_group_label": "Remote control scope",
  "dev_overview.remote_group_desc":
    "Controls which TV and AV remotes appear in the Remote app.",
  "dev_overview.remote_follow_area": "Follow Area",
  "dev_overview.remote_all_system": "All System remotes",
  "dev_overview.ringing_alert_text": "An alarm or timer is ringing on this Device.",
  "dev_overview.dismissed_ringing_toast": "Dismissed ringing alert",
  "dev_overview.active_timer_label": "Active timer",
  "dev_overview.no_active_timer": "No active timer",
  "dev_overview.running": "Running",
  "dev_overview.paused": "Paused",
  "dev_overview.cancel_timer": "Cancel timer",
  "dev_overview.cancelled_timer_toast": "Cancelled timer",
  "dev_overview.stopwatch_label": "Stopwatch",
  "dev_overview.not_running": "Not running",
  "dev_overview.reset_stopwatch": "Reset stopwatch",
  "dev_overview.reset_stopwatch_toast": "Reset stopwatch",
  "dev_overview.alarms_label": "Alarms",
  "dev_overview.alarms_enabled_summary": "{count} enabled • {nextTime}",
  "dev_overview.alarms_desc":
    "Syncs 2-way with on-device alarm edits (1-minute precision).",
  "dev_overview.alarms_group_aria": "Device alarms",
  "dev_overview.alarm_time_label": "Alarm {index} time",
  "dev_overview.alarm_schedule_label": "Alarm {index} schedule",
  "dev_overview.alarm_rec_daily": "Daily",
  "dev_overview.alarm_rec_weekdays": "Weekdays",
  "dev_overview.alarm_rec_weekends": "Weekends",
  "dev_overview.alarm_rec_once": "Once",

  // Device -> Display (D-034 / D-066 / Q7)
  "dev_display.card_voice_assistant": "Voice assistant",
  "dev_display.sun_moon_label": "Sun & Moon",
  "dev_display.sun_moon_desc":
    "Choose which sky bodies appear on the live weather background.",
  "dev_display.screensaver_preview_desc":
    "Starts the screensaver on this Device immediately.",
  "dev_display.preview_btn": "Preview",
  "dev_display.custom_color_label": "Custom color",
  "dev_display.custom_color_desc": "Used when Color profile is set to Custom.",
  "dev_display.current_color_option": "Current ({hex})",
  "dev_display.add_color_btn": "Add color",
  "dev_display.wallpapers_subtitle":
    "Shared presets and uploaded photos cropped for this display.",
  "dev_display.active_wallpaper_label": "Active wallpaper",
  "dev_display.wp_rotating_named_starred_one":
    "{name} • rotating 1 starred wallpaper.",
  "dev_display.wp_rotating_named_starred_many":
    "{name} • rotating {count} starred wallpapers.",
  "dev_display.wp_rotating_named_all": "{name} • rotating all {count} wallpapers.",
  "dev_display.wp_rotating_starred_one": "Rotating 1 starred wallpaper.",
  "dev_display.wp_rotating_starred_many": "Rotating {count} starred wallpapers.",
  "dev_display.wp_rotating_all": "Rotating all {count} wallpapers.",
  "dev_display.wp_static_named": "{name} (static — not rotating).",
  "dev_display.wp_off": "Off — select Use on a wallpaper below or enable rotation.",
  "dev_display.wp_hint_none":
    "No wallpapers starred — rotation cycles through all wallpapers.",
  "dev_display.wp_hint_one":
    "1 wallpaper starred — star at least 2 to cycle between favorites.",
  "dev_display.wp_hint_many":
    "{starred} of {total} wallpapers starred for rotation.",
  "dev_display.stop_rotation": "Stop rotation",
  "dev_display.enable_rotation": "Enable rotation",
  "dev_display.turn_off_wallpaper": "Turn off wallpaper",
  "dev_display.rotation_interval_label": "Rotation interval",
  "dev_display.rotation_interval_aria": "Wallpaper rotation interval",
  "dev_display.rot_0": "Do not rotate",
  "dev_display.rot_5": "Every 5 minutes",
  "dev_display.rot_15": "Every 15 minutes",
  "dev_display.rot_30": "Every 30 minutes",
  "dev_display.rot_60": "Every hour",
  "dev_display.rot_360": "Every 6 hours",
  "dev_display.rot_1440": "Once a day",
  "dev_display.star_all": "Star all",
  "dev_display.clear_stars": "Clear stars",

  // Device -> Interface (D-053 / D-064 / U4)
  "dev_interface.enable_home_desc":
    "Provides the Home screen and App Dock. Turn off to lock this Device to a single start screen app.",
  "dev_interface.start_screen_multi_desc":
    "Choose the screen shown on startup. Swipe up from the bottom to return to Home.",
  "dev_interface.start_screen_single_desc":
    "Single-app screen shown at all times while the Home screen is disabled.",
  "dev_interface.home_clock_tap_desc":
    "Choose whether tapping the clock readout on Home opens the Time app or the standalone clock face.",
  "dev_interface.home_date_tap_desc":
    "Choose whether tapping the date readout on Home opens Day view or Overview in the Calendar app.",
  "dev_interface.return_timeout_desc":
    "Resets idle screens back to Home unless media is playing or a live activity is active.",
  "dev_interface.activity_card_desc":
    "Shows live timers, alarms, media queue, stopwatch, and next calendar event on Home.",
  "dev_interface.activity_sources_desc":
    "Choose and reorder which live items appear in the Activity card.",
  "dev_interface.activity_src_calendar": "Calendar",
  "dev_interface.activity_src_music_queue": "Music queue",
  "dev_interface.activity_src_stopwatch": "Stopwatch",
  "dev_interface.activity_src_alarms": "Alarms",
  "dev_interface.activity_src_timers": "Timers",
  "dev_interface.app_dock_desc":
    "Toggle, drag to reorder, and configure apps on the App Dock, or add custom subpage and Home Assistant entity shortcuts. Pinned hides automatically when empty.",
  "dev_interface.active_dock_aria": "Active on App Dock",
  "dev_interface.show_on_dock_aria": "Show {title} on App Dock",
  "dev_interface.settings_title": "Settings",
  "dev_interface.settings_locked_meta": "Always shown last on the App Dock",
  "dev_interface.hidden_from_dock": "Hidden from dock",
  "dev_interface.single_app_title": "Single-app mode active",
  "dev_interface.single_app_desc":
    "The Home screen and App Dock are disabled while this Device is locked to {app}. Turn on Enable Home screen to restore multi-app navigation and the App Dock.",
  "dev_interface.pinned_empty_meta": "Empty — auto-hidden on dock",
  "dev_interface.pinned_count_meta": "{count} {shortcutWord} • {pages} {pageWord}",
  "dev_interface.word_shortcut_one": "shortcut",
  "dev_interface.word_shortcut_many": "shortcuts",
  "dev_interface.word_page_one": "page",
  "dev_interface.word_page_many": "pages",
  "dev_interface.music_meta": "Albums: {albums} • Artists: {artists}",
  "dev_interface.categories_enabled_one": "1 category enabled",
  "dev_interface.categories_enabled_many": "{count} categories enabled",
  "dev_interface.remote_follow_area": "Follow the active Area",
  "dev_interface.remote_all": "All System remotes",
  "dev_interface.weather_meta": "Current, forecast, Sun & Moon",
  "dev_interface.time_utc_world_one": "UTC + 1 world clock",
  "dev_interface.time_utc_world_many": "UTC + {count} world clocks",
  "dev_interface.time_world_one": "1 world clock",
  "dev_interface.time_world_many": "{count} world clocks",
  "dev_interface.time_local_utc": "Local time + UTC",
  "dev_interface.time_local": "Local time",
  "dev_interface.clock_24h": "24-hour",
  "dev_interface.clock_12h": "12-hour",
  "dev_interface.calendar_meta": "{days}-day lookahead • Starts {weekday}",
  "dev_interface.tools_enabled_one": "1 tool enabled",
  "dev_interface.tools_enabled_many": "{count} tools enabled",
  "dev_interface.games_enabled_one": "1 game enabled",
  "dev_interface.games_enabled_many": "{count} games enabled",
  "dev_interface.custom_route_meta": "Custom • {target}",
  "dev_interface.custom_entity_confirm_meta":
    "Custom • {action} • Confirm • {target}",
  "dev_interface.custom_entity_tap_meta": "Custom • {action} • 1-tap • {target}",

  // Device -> Audio (D-008 / D-031 / D-066 / Q8)
  "dev_audio.card_voice_wake": "Voice assistant & wake word",
  "dev_audio.card_sound_playback": "Sound & playback",
  "dev_audio.vfm_desc":
    "Updates this roaming Device's Home Assistant Area when BLE presence settles in a new Area, so Area-less voice commands target where you are.",
  "dev_audio.vfm_delay_label": "Voice Follows Me delay",
  "dev_audio.vfm_delay_desc":
    "How long a BLE-detected Area stays stable before moving the Device (3 to 60 seconds).",
  "dev_audio.ww_sensitivity_summary": "Wake word sensitivity (per model)",
  "dev_audio.default_speaker_label": "Default speaker",
  "dev_audio.default_speaker_desc":
    "Primary speaker controlled from Music and Home when this Device starts up.",
  "dev_audio.default_speaker_auto": "— Automatic (built-in or Area) —",
  "dev_audio.ma_player_label": "Music Assistant player",
  "dev_audio.ma_player_unmatched_desc":
    "Automatic match did not find {entity} in Music Assistant. Choose this Device's player for library playback, queues, and lyrics.",
  "dev_audio.ma_player_manual_desc":
    "Linked manually ({entity} was not used). Clear to return to automatic matching.",
  "dev_audio.ma_player_fallback_target": "this Device's player",
  "dev_audio.ma_player_auto": "— Automatic match —",
  "dev_audio.area_handoff_desc":
    "Transfers active Music Assistant playback when this Device moves to or selects another Area.",

  // Device -> Power (D-027)
  "dev_power.card_sleep_wake": "Sleep & wake",
  "dev_power.card_power_battery": "Power & battery",
  "dev_power.empty": "No sleep or battery entities reported by this Device.",

  // Device -> Presence (D-032 / D-066 / Q8)
  "dev_presence.card_area_tracking": "Area tracking",
  "dev_presence.card_ble_identity": "BLE identity",
  "dev_presence.track_ble_label": "Track Area with BLE proxies",
  "dev_presence.track_ble_desc":
    "Uses Home Assistant Area-assigned Bluetooth proxies to locate this Device automatically. Turn off to pin it to one assigned Area.",
  "dev_presence.auto_switch_desc":
    "Switches the Device's active Area controls automatically when BLE detects a move.",
  "dev_presence.fallback_area_label": "Fallback Area",
  "dev_presence.fallback_area_desc":
    "Default Home Assistant Area when no Bluetooth proxy is in range.",
  "dev_presence.fallback_area_auto": "— Automatic (ESPHome Area) —",
  "dev_presence.assigned_area_label": "Assigned Area",
  "dev_presence.assigned_area_desc":
    "Pins this Device's Area controls and Home Assistant Device Area to one location.",
  "dev_presence.target_addr_label": "BLE target address or entity",
  "dev_presence.target_addr_placeholder":
    "AA:BB:CC:DD:EE:FF or device_tracker.phone_ble",
  "dev_presence.target_addr_help":
    "Leave blank on Latter displays to track their built-in BLE beacon MAC automatically.",
  "dev_presence.ref_power_label": "Reference power (1 meter)",
  "dev_presence.ref_power_placeholder_detected": "Auto ({dbm} dBm)",
  "dev_presence.ref_power_help":
    "Leave blank to use auto-detected beacon power in dBm, or enter -90 to -30 dBm to calibrate this Device.",
  "dev_presence.companion_low_title": "Companion App low-power beacon detected",
  "dev_presence.companion_low_body":
    "This phone is advertising at {txPower} power{modeSuffix}.{refSuffix} Setting Transmit Power to Medium or High and Advertise Mode to Balanced in the Home Assistant Companion App improves multi-Area accuracy through walls.",
  "dev_presence.companion_mode_suffix": " ({mode} mode)",
  "dev_presence.companion_ref_suffix":
    " Latter automatically compensates its 1 m reference power ({dbm} dBm).",
  "dev_presence.companion_default_power": "default",
  "dev_presence.ibeacon_uuid_label": "iBeacon UUID",
  "dev_presence.ibeacon_uuid_placeholder": "Generated automatically per System",

  // Device -> Tools (D-027 / D-064 / D-066 / Q8 / Q12)
  "dev_tools.ble_signal": "BLE signal",
  "dev_tools.ble_target": "BLE target",
  "dev_tools.model": "Model",
  "dev_tools.esphome_node": "ESPHome node",
  "dev_tools.firmware_version": "Firmware version",
  "dev_tools.latter_sdk": "Latter SDK",
  "dev_tools.wifi_signal": "Wi-Fi signal",
  "dev_tools.ip_address": "IP address",
  "dev_tools.mac_address": "MAC address",
  "dev_tools.diagnostics_file_label": "Diagnostics file",
  "dev_tools.diagnostics_file_desc":
    "Downloads redacted Home Assistant diagnostics for troubleshooting.",
  "dev_tools.backup_row_label": "Device backup",
  "dev_tools.backup_row_desc":
    "Downloads this Device's Latter configuration and settings as JSON.",
  "dev_tools.perimeter_subtitle":
    "Governs unlocking doors, disarming alarms, and opening garage or gate covers from this Device.",
  "dev_tools.pin_policy_desc_prefix":
    "Auto requires a PIN on stationary wall panels when configured and allows roaming personal Devices. Effective policy:",
  "dev_tools.security_pin_label": "Security PIN",
  "dev_tools.security_pin_desc":
    "Write-only 4 to 12 digit numeric PIN verified by Home Assistant when the on-device keypad prompts. Never shown again after saving.",
  "dev_tools.pin_input_aria": "New security PIN (4 to 12 digits)",
  "dev_tools.pin_placeholder_replace": "Enter new PIN to replace…",
  "dev_tools.pin_placeholder_new": "4 to 12 digits",
  "dev_tools.save_pin": "Save PIN",
  "dev_tools.clear_pin": "Clear PIN",
  "dev_tools.reconfigure_in_ha": "Reconfigure in Home Assistant",
  "dev_tools.reset_defaults_label": "Reset to defaults",
  "dev_tools.reset_defaults_desc":
    "Resets on-device preferences and/or Latter settings while keeping Wi-Fi and Home Assistant pairing.",
  "dev_tools.remove_device_label": "Remove Device",
  "dev_tools.remove_device_desc":
    "Removes this Device from Latter. Your ESPHome device stays in Home Assistant.",
  "dev_tools.telem_uptime": "Session uptime",
  "dev_tools.telem_last_reset": "Last reset",
  "dev_tools.telem_wifi_disc": "Wi-Fi disconnects",
  "dev_tools.telem_beacon_timeouts": " ({count} beacon timeouts)",
  "dev_tools.telem_wifi_avg_min": "Wi-Fi avg / min",
  "dev_tools.telem_ha_sessions": "Home Assistant sessions",
  "dev_tools.telem_max_gap": " (max gap {duration})",
  "dev_tools.telem_light_sleep": "Light sleep duty",
  "dev_tools.telem_cycles": " ({count} cycles)",
  "dev_tools.telem_nvs_writes": "NVS flash writes",
  "dev_tools.telem_nvs_value":
    "{writes} writes ({erases} erases, {maxMs} ms max)",
  "dev_tools.telem_board": "Hardware board",
  "dev_tools.telem_processor": "Processor & PSRAM",
  "dev_tools.telem_psram_suffix": " • {mb} MB PSRAM",
  "dev_tools.telem_display_panel": "Display panel",
  "dev_tools.telem_headless": "Headless",
  "dev_tools.telem_traits": "Hardware traits",
  "dev_tools.trait_touch": "Touch",
  "dev_tools.trait_mic": "Mic",
  "dev_tools.trait_speaker": "Speaker",
  "dev_tools.trait_audio": "Audio",
  "dev_tools.trait_imu": "IMU",
  "dev_tools.trait_battery": "Battery",
  "dev_tools.trait_wearable": "Wearable",
  "dev_tools.trait_stationary": "Stationary",
} as const;
