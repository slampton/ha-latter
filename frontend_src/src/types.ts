/**
 * TypeScript domain & Home Assistant panel types for Latter Studio (`STUDIO_REV = 38`).
 */

import type {
  CatalogItem,
  DevicePrefSpecItem,
  WorldClockZoneItem,
} from "./protocol-schema.js";

export type { CatalogItem, DevicePrefSpecItem, WorldClockZoneItem };

export type StudioScope = "device" | "system";

export type DeviceViewId =
  | "select_device_prompt"
  | "discovered_devices"
  | "dashboard"
  | "display"
  | "interface"
  | "audio_voice"
  | "power"
  | "presence"
  | "tools";

export type SystemViewId =
  | "system_overview"
  | "shared_entities"
  | "remotes"
  | "system_sync"
  | "area_tracking"
  | "system_tools";

export type StudioViewId = DeviceViewId | SystemViewId;

export type SecurityPinPolicy = "auto" | "allow" | "require_pin" | "block";

export type DeviceStatusCode = "online" | "offline" | "update" | "away" | "scanning";

export type ConfigurableAppId =
  | "pinned"
  | "music"
  | "home_hub"
  | "cameras"
  | "area"
  | "remote"
  | "time"
  | "calendar"
  | "tools"
  | "games"
  | "clock";

export interface HassEntityState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

export interface HassConnection {
  subscribeMessage<T = unknown>(
    callback: (event: T) => void,
    subscribeMessage: Record<string, unknown>,
  ): Promise<() => void>;
  addEventListener?: (eventType: string, callback: () => void) => void;
  removeEventListener?: (eventType: string, callback: () => void) => void;
}

interface HassAuth {
  data?: { access_token?: string };
  expired?: boolean;
  refreshAccessToken?: () => Promise<void>;
}

export interface HomeAssistant {
  auth?: HassAuth;
  language?: string;
  dockedSidebar?: "docked" | "auto" | "always_hidden";
  localize?: (key: string, ...args: unknown[]) => string;
  loadBackendTranslation?: (
    category: string,
    integration?: string | string[],
    configFlow?: boolean,
  ) => Promise<(key: string, ...args: unknown[]) => string>;
  formatEntityState?: (stateObj: HassEntityState, state?: string) => string;
  locale?: {
    language?: string;
    number_format?:
      | "language"
      | "system"
      | "comma_decimal"
      | "decimal_comma"
      | "space_comma"
      | "none"
      | string;
    time_format?: "language" | "system" | "am_pm" | "24" | string;
    date_format?: "language" | "system" | "DMY" | "MDY" | "YMD" | string;
    time_zone?: "local" | "server" | string;
    first_weekday?:
      | "language"
      | "monday"
      | "tuesday"
      | "wednesday"
      | "thursday"
      | "friday"
      | "saturday"
      | "sunday"
      | string;
  };
  config?: {
    unit_system?: { length?: string };
    time_zone?: string;
    version?: string;
  };
  themes?: { darkMode?: boolean };
  states?: Record<string, HassEntityState>;
  connection?: HassConnection;
  callWS<T = unknown>(msg: Record<string, unknown>): Promise<T>;
}

export interface HassRoute {
  prefix?: string;
  path?: string;
}

export interface CatalogChoice {
  id: string;
  name: string;
  area_name?: string;
  stream_kind?: "rtsp" | "mjpeg" | "snapshot" | string;
  has_audio?: boolean;
  has_talkback?: boolean;
  is_doorbell?: boolean;
}

interface AreaChoice {
  id: string;
  name: string;
}

export interface ShortcutItem {
  kind: "route" | "entity";
  target: string;
  action: string;
  label: string;
  icon: string;
  confirm: boolean;
}

interface ShortcutEntityOption {
  id: string;
  name: string;
  domain: string;
  device_class: string;
  icon: string;
  area_name: string;
}

interface EntityCatalog {
  areas?: AreaChoice[];
  ma_speakers?: CatalogChoice[];
  ma_players?: CatalogChoice[];
  volume_targets?: CatalogChoice[];
  remotes?: CatalogChoice[];
  alarms?: CatalogChoice[];
  cameras?: CatalogChoice[];
  climates?: CatalogChoice[];
  locks?: CatalogChoice[];
  garages?: CatalogChoice[];
  vacuums?: CatalogChoice[];
  weathers?: CatalogChoice[];
  calendars?: CatalogChoice[];
  persons?: CatalogChoice[];
  shortcut_entities?: ShortcutEntityOption[];
}

export interface BleSurveyRow {
  scanner_source?: string;
  scanner_name?: string;
  area_id: string;
  area_name: string;
  raw_rssi: number | null;
  filtered_rssi?: number | null;
  offset_db: number;
  effective_rssi: number | null;
  distance_m?: number | null;
  distance_ft?: number | null;
  age_seconds?: number | null;
  is_fresh?: boolean;
  is_winner: boolean;
}

export interface BleAreaSignatureSummary {
  area_id: string;
  area_name: string;
  floor_id?: string | null;
  has_ble_proxy: boolean;
  has_signature: boolean;
  scanner_count: number;
  sample_count: number;
  captured_at: string;
}

export interface SystemDeviceEntry {
  subentry_id: string;
  device_slug: string;
  title: string;
  model_label: string;
  area_id: string;
  has_assigned_area: boolean;
  area_label: string;
  status_code: DeviceStatusCode;
  status_label: string;
  is_online: boolean;
  kind: "device" | "ble_tag";
  ble_category?: "phone" | "ble_tag" | "" | string;
  has_display: boolean;
  has_battery: boolean;
  hw_jpeg?: boolean;
  is_roaming: boolean;
  device_group: string;
  device_remote_group: string;
  device_group_name: string;
  assigned_person: string;
  active_area_name: string;
  is_latter_native: boolean;
  battery_level: number | null;
  is_charging: boolean;
  is_usb_connected: boolean;
  wifi_rssi: number | null;
  ip_address: string;
  has_ble: boolean;
  ble_tracked: boolean;
  ble_survey_rows: BleSurveyRow[];
  ble_packets_seen: number;
  is_current: boolean;
}

export interface IssueItem {
  issue_id?: string;
  kind?: string;
  key?: string;
  severity?: "error" | "warning" | "critical" | "info" | string;
  subentry_id?: string;
  device_title?: string;
  detail?: string;
}

export interface DiscoveredLatterDevice {
  esphome_device_id: string;
  node_name: string;
  title: string;
  model_label: string;
  area_name: string;
  default_group: string;
}

export interface DiscoveredBleCandidate {
  target_address: string;
  title: string;
  label?: string;
  kind?: string;
  is_tracker: boolean;
  rssi: number | null;
  area_name?: string;
}

export interface VolumeOverride {
  speaker: string;
  target: string;
}

export interface RemoteGroup {
  id: string;
  name: string;
  area_id: string;
  remotes: string[];
}

export interface CustomPalette {
  name: string;
  hex: string;
}

export interface SystemConfig {
  weather_entity: string;
  alarm_entity: string;
  thermostat_entities: string[];
  lock_entities: string[];
  garage_entities: string[];
  vacuum_entities: string[];
  camera_entities: string[];
  remotes_list: string[];
  remote_groups: RemoteGroup[];
  volume_overrides: VolumeOverride[];
  calendar_entities: string[];
  custom_palettes: CustomPalette[];
  doorbell_noise_reduction: "strong" | "light" | "off" | string;
  ignored_discovered_devices?: string[];
  ble_attenuation?: number;
  ble_max_radius_m?: number;
  ble_max_velocity_mps?: number;
  ble_away_timeout_s?: number;
}

export interface DeviceConfig {
  device_slug?: string;
  kind?: "device" | "ble_tag";
  is_roaming?: boolean;
  display_shape?: "circle" | "square" | string;
  device_group?: string;
  device_remote_group?: string;
  default_speaker?: string;
  ma_player_entity?: string;
  default_area?: string;
  native_ble_tracking?: boolean;
  ble_beacon_uuid?: string;
  ble_target_address?: string;
  ble_category?: "auto" | "phone" | "ble_tag" | string;
  effective_ble_category?: "phone" | "ble_tag" | "" | string;
  ble_ref_power?: number | null;
  assigned_person?: string;
  ble_auto_switch?: boolean;
  sync_device_area?: boolean;
  area_follow_dwell_s?: number;
  area_handoff?: boolean;
  device_custom_color?: string;
  dock_items?: ShortcutItem[];
  pinned_items?: ShortcutItem[];
  area_categories?: string;
  home_categories?: string;
  tools_items?: string;
  games_items?: string;
  activity_card?: boolean;
  activity_sources?: string;
  camera_visible_entities?: string[];
  camera_carousel_entities?: string[];
  camera_default_view?: string;
  camera_carousel_interval?: string;
  camera_framing?: string;
  camera_stream_mode?: string;
  camera_doorbell_popup?: string;
  wallpaper_source?: string;
  wallpaper_cycle_minutes?: number;
  security_pin_policy?: SecurityPinPolicy | string;
  security_pin?: string;
  has_security_pin?: boolean;
  [key: string]: unknown;
}

export interface DeviceCapabilities {
  has_display?: boolean;
  has_imu?: boolean;
  is_round?: boolean;
  has_battery?: boolean;
  has_power?: boolean;
  has_voice?: boolean;
  has_audio?: boolean;
  has_ble_beacon?: boolean;
  is_roaming_device?: boolean;
  hw_jpeg?: boolean;
  video_max_fps?: number;
  video_grid_fps?: number;
}

export interface EspHomeEntityItem {
  entity_id: string;
  domain: string;
  name: string;
  state: string;
  key?: string;
  pref_key?: string;
  device_command?: string;
  unit?: string;
  device_class?: string;
  category?: string;
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  mode?: string;
}

interface EspHomeSection {
  id: string;
  title: string;
  items: EspHomeEntityItem[];
}

interface EspHomeInspector {
  device?: {
    id?: string;
    name?: string;
    model?: string;
    sw_version?: string;
    mac?: string;
  };
  sections?: EspHomeSection[];
}

export interface WallpaperItem {
  id: string;
  name: string;
  thumb_url?: string;
  preview_url?: string;
  active?: boolean;
  favorite?: boolean;
  deletable?: boolean;
  kind?: "preset" | "upload" | string;
  scope?: "device" | "system" | string;
}

interface DoorbellTalkEntry {
  device_title: string;
  state: string;
}

interface DoorbellStatusItem {
  camera_entity: string;
  camera_name?: string;
  ring_entity?: string;
  ring_name?: string;
  ring_state?: string;
  ring_at?: string;
  talk?: DoorbellTalkEntry[];
}

interface AreaFusionSensorChoice {
  entity_id: string;
  name: string;
  state?: string;
  device_class?: string;
}

export interface AreaPresenceRow {
  area_id: string;
  area_name: string;
  is_occupied?: boolean;
  confidence_pct?: number;
  occupant_names?: string[];
  winning_rssi?: number | null;
  closest_distance_m?: number | null;
  closest_distance_ft?: number | null;
  active_sensors?: string[];
  available_sensors?: string[];
  floor_id?: string | null;
  floor_name?: string | null;
  match_method?: string | null;
  fusion_mode?: string;
  fusion_threshold_pct?: number;
  fusion_sensors?: string[];
  fusion_sensor_choices?: AreaFusionSensorChoice[];
}

export interface SharedControlTarget {
  subentry_id?: string;
  device_slug?: string;
  device_group?: string;
  is_online?: boolean;
  is_roaming?: boolean;
  pref_key?: string;
  entity_id?: string;
  state: string;
}

export interface SharedControlItem {
  key?: string;
  canonical_key?: string;
  pref_key?: string;
  tier?: "behavior" | "display" | "interface" | string;
  section: string;
  section_title: string;
  name: string;
  domain: string;
  state?: string;
  options?: string[];
  option_labels?: Record<string, string>;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  unit?: string;
  targets: SharedControlTarget[];
}

export interface DevicePrefItem {
  key: string;
  label: string;
  section: string;
  group_tier?: string | null;
  domain: string;
  value: unknown;
  options?: string[];
  min?: number | null;
  max?: number | null;
  step?: number | null;
  unit?: string;
}

export interface DeviceGroup {
  id: string;
  name: string;
  description: string;
  builtin?: boolean;
  include_display?: boolean;
  include_interface?: boolean;
  device_config?: Record<string, unknown>;
}

interface LogEntry {
  ts?: number | string;
  timestamp?: string;
  level?: string;
  source?: string;
  message?: string;
}

interface BleTransmitterStatus {
  state: string;
  tx_power: string;
  advertise_mode: string;
}

export interface LiveDeviceTelemetry {
  active_area_name?: string;
  ma_link_matched?: boolean;
  ble_closest_proxy?: string;
  ble_detected_ref_power?: number | null;
  ble_transmitter_status?: BleTransmitterStatus | null;
  area_presence_grid?: AreaPresenceRow[];
  device_sw_version?: string;
  sdk_rev?: string;
  fw_update_entity?: string;
  fw_update_available?: boolean;
  effective_security_pin_policy?: string;
  has_security_pin?: boolean;
  is_ble_sleep_expected?: boolean;
  timer_running?: boolean;
  timer_paused?: boolean;
  timer_remaining_sec?: number;
  timer_ends_at?: string;
  stopwatch_running?: boolean;
  stopwatch_paused?: boolean;
  stopwatch_elapsed_sec?: number;
  stopwatch_started_at?: string;
  alarm_ringing?: boolean;
}

interface QuickActionPayloadItem {
  key: string;
  device_command: string;
  label: string;
  domain: string;
  state: string;
  device_class?: string;
}

interface DeviceLinks {
  entry_id?: string;
  esphome_device_id?: string;
  latter_device_id?: string;
}

export interface SystemInfo {
  ha_version: string;
  integration_version: string;
  min_firmware_sdk_rev: number;
  studio_rev: number;
}

export interface StudioStatePayload {
  type?: "state";
  subentry_id: string;
  title: string;
  version: string;
  studio_rev?: number;
  system_config_rev: number;
  device_config_rev: number;
  system_info?: SystemInfo;
  locale_strings?: Record<string, string>;
  internal_logs: LogEntry[];
  system_devices: SystemDeviceEntry[];
  issues: IssueItem[];
  ble_proxy_count: number;
  ble_area_signatures?: BleAreaSignatureSummary[];
  discovered_latter_devices?: DiscoveredLatterDevice[];
  ignored_latter_devices?: DiscoveredLatterDevice[];
  discovered_ble_devices: DiscoveredBleCandidate[];
  system_controls: SharedControlItem[];
  device_groups: DeviceGroup[];
  system_config: SystemConfig;
  has_security_pin?: boolean;
  system_wallpapers: WallpaperItem[];
  doorbells: DoorbellStatusItem[];
  catalog?: EntityCatalog;
  pref_specs?: DevicePrefSpecItem[];
  world_clock_zones?: WorldClockZoneItem[];
  capabilities: DeviceCapabilities;
  config: DeviceConfig;
  device_prefs: DevicePrefItem[];
  quick_actions?: QuickActionPayloadItem[];
  speaker_volume?: EspHomeEntityItem | null;
  esphome: EspHomeInspector;
  wallpapers: WallpaperItem[];
  links?: DeviceLinks;
  live: LiveDeviceTelemetry;
  update_check?: { checked: number; available: number };
  removed?: boolean;
  removed_subentry_id?: string;
  adopted_subentry_id?: string;
  adopted_esphome_device_id?: string;
}

export interface BleSurveyDeltaEvent {
  type: "ble_survey_delta";
  subentry_id?: string;
  ble_packets_seen?: number;
  ble_closest_proxy?: string;
  ble_survey_rows?: BleSurveyRow[];
  ble_area_signatures?: BleAreaSignatureSummary[];
  area_presence_grid?: AreaPresenceRow[];
}
