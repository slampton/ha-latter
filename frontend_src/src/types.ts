/**
 * TypeScript domain & Home Assistant panel types for Latter Studio.
 */

export type StudioScope = "device" | "system";

export type DeviceViewId =
  | "select_device_prompt"
  | "dashboard"
  | "home_display"
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
}

export interface HassAuth {
  data?: { access_token?: string };
  expired?: boolean;
  refreshAccessToken?: () => Promise<void>;
}

export interface HomeAssistant {
  auth?: HassAuth;
  language?: string;
  locale?: { language?: string; time_zone?: string };
  config?: {
    unit_system?: { length?: string };
    time_zone?: string;
  };
  themes?: { darkMode?: boolean };
  selectedTheme?: { dark?: boolean };
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
  preview_url?: string;
}

export interface AreaChoice {
  id: string;
  name: string;
}

export interface EntityCatalog {
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
}

export interface BleSurveyRow {
  area_id: string;
  area_name: string;
  raw_rssi: number | null;
  offset_db: number;
  effective_rssi: number | null;
  is_winner: boolean;
  scanner?: string;
  age_seconds?: number | null;
  distance_m?: number | null;
  distance_ft?: number | null;
}

export type GroupSyncStatus =
  | "in_sync"
  | "customized"
  | string
  | {
      in_sync?: boolean;
      status?: string;
    };

export interface SystemDeviceEntry {
  subentry_id: string;
  device_slug: string;
  title: string;
  model_label: string;
  has_assigned_area: boolean;
  area_label: string;
  status_label: string;
  is_online: boolean;
  kind: "device" | "ble_tag";
  has_display: boolean;
  is_roaming: boolean;
  device_group: string;
  device_remote_group: string;
  device_group_name: string;
  group_sync_status?: GroupSyncStatus | null;
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

export interface DiscoveredBleCandidate {
  target_address: string;
  title: string;
  label?: string;
  kind?: string;
  rssi: number | null;
  area_name?: string;
  address?: string;
  name?: string;
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
  thermostat_entity: string;
  lock_entity: string;
  garage_entity: string;
  vacuum_entity: string;
  camera_entities: string[];
  remotes_list: string[];
  remote_groups: RemoteGroup[];
  volume_overrides: VolumeOverride[];
  calendar_entities: string[];
  custom_palettes: CustomPalette[];
  doorbell_noise_reduction: "strong" | "light" | "off" | string;
}

export interface DeviceConfig {
  device_slug?: string;
  kind?: "device" | "ble_tag";
  is_roaming?: boolean;
  display_shape?: "circle" | "square" | string;
  device_group?: string;
  default_page_size?: number;
  default_speaker?: string;
  ma_player_entity?: string;
  default_area?: string;
  native_ble_tracking?: boolean;
  ble_beacon_uuid?: string;
  ble_target_address?: string;
  assigned_person?: string;
  ble_auto_switch?: boolean;
  sync_device_area?: boolean;
  area_follow_dwell_s?: number;
  area_handoff?: boolean;
  device_custom_color?: string;
  dock_apps?: string;
  activity_card?: boolean;
  activity_sources?: string;
  wallpaper_cycle_minutes?: number;
  security_pin_policy?: SecurityPinPolicy | string;
  security_pin?: string;
  has_security_pin?: boolean;
}

export interface DeviceCapabilities {
  has_display?: boolean;
  has_power?: boolean;
  has_voice?: boolean;
  has_audio?: boolean;
  has_ble_beacon?: boolean;
  is_roaming_device?: boolean;
}

export interface EspHomeEntityItem {
  entity_id: string;
  domain: string;
  name: string;
  state: string;
  key?: string;
  unit?: string;
  device_class?: string;
  category?: string;
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  mode?: string;
}

export interface EspHomeSection {
  id: string;
  title: string;
  items: EspHomeEntityItem[];
}

export interface EspHomeInspector {
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

export interface DoorbellTalkEntry {
  device_title: string;
  state: string;
}

export interface DoorbellStatusItem {
  camera_entity: string;
  camera_name?: string;
  preview_url?: string;
  ring_entity?: string;
  ring_name?: string;
  ring_state?: string;
  ring_at?: string;
  talk?: DoorbellTalkEntry[];
}

export interface AreaFusionSensorChoice {
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
  fusion_mode?: string;
  fusion_threshold_pct?: number;
  fusion_sensors?: string[];
  fusion_sensor_choices?: AreaFusionSensorChoice[];
}

export interface SharedControlTarget {
  subentry_id?: string;
  device_slug?: string;
  device_group?: string;
  is_roaming?: boolean;
  entity_id: string;
  state: string;
}

export interface SharedControlItem {
  key?: string;
  canonical_key: string;
  tier?: "behavior" | "appearance" | string;
  section: string;
  section_title: string;
  name: string;
  domain: string;
  state?: string;
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  targets: SharedControlTarget[];
}

export interface DeviceGroup {
  id: string;
  name: string;
  description: string;
  builtin?: boolean;
  device_config?: Record<string, unknown>;
  esphome_controls?: Record<string, unknown>;
}

export interface LogEntry {
  ts?: number | string;
  timestamp?: string;
  level?: string;
  source?: string;
  message?: string;
}

export interface NowPlayingInfo {
  speaker_name: string;
  media_state: string;
  media_title: string;
  media_artist: string;
}

export interface LiveDeviceSection {
  active_area_name?: string;
  ma_link_matched?: boolean;
  group_sync_status?: GroupSyncStatus | null;
  ble_closest_proxy?: string;
  area_presence_grid?: AreaPresenceRow[];
  now?: NowPlayingInfo;
  device_sw_version?: string;
  sdk_rev?: string;
  fw_update_entity?: string;
  fw_update_available?: boolean;
  effective_security_pin_policy?: string;
  has_security_pin?: boolean;
}

export interface DeviceLinks {
  entry_id?: string;
  esphome_device_id?: string;
  latter_device_id?: string;
}

export interface StudioStatePayload {
  subentry_id: string;
  title: string;
  version: string;
  internal_logs: LogEntry[];
  system_devices: SystemDeviceEntry[];
  issues: IssueItem[];
  ble_proxy_count: number;
  discovered_ble_devices: DiscoveredBleCandidate[];
  system_controls: SharedControlItem[];
  device_groups: DeviceGroup[];
  system_config: SystemConfig;
  has_security_pin?: boolean;
  system_wallpapers: WallpaperItem[];
  doorbells: DoorbellStatusItem[];
  catalog?: EntityCatalog;
  capabilities: DeviceCapabilities;
  config: DeviceConfig;
  esphome: EspHomeInspector;
  wallpapers: WallpaperItem[];
  links?: DeviceLinks;
  live: LiveDeviceSection;
  update_check?: { checked: number; available: number };
  removed?: boolean;
  removed_subentry_id?: string;
}

export interface BleSurveyDeltaEvent {
  type?: string;
  event?: string;
  subentry_id?: string;
  ble_packets_seen?: number;
  ble_closest_proxy?: string;
  ble_survey_rows?: BleSurveyRow[];
  area_presence_grid?: AreaPresenceRow[];
}
