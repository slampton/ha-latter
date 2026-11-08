# Services Reference

Latter registers 14 user-facing services (plus the internal `latter.device_hello` handshake service) under the `latter` domain. Latter firmware calls most of them from the device. You can also call them from automations, scripts, or your own firmware.

- **Source:** [`services.py`](../../custom_components/latter/services.py), with UI schemas in [`services.yaml`](../../custom_components/latter/services.yaml).
- **Schema validation.** Every service rejects unknown keys. Most values (for example `priority`, `mode`, `action`, `command`) are free-form strings checked by the handler, which ignores or defaults values it doesn't recognize; `doorbell_intercom`'s `noise_reduction` is validated by the schema.

## Targeting

Services that target a device accept `target_device`:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `target_device` | string | A device slug (`pocket_assistant`), a subentry ID, a Home Assistant device ID, or a [special target](#special-target-values) |

If only a single Latter device is configured, `target_device` is optional. When multiple devices are configured, `target_device` is required.

### Special target values

| Value | `notify` | `intercom_broadcast` |
| :--- | :--- | :--- |
| `all` | Every display device | — |
| `follow_me`, `occupied`, `occupied_areas` | Devices whose current area is occupied | Music Assistant speakers in occupied areas, plus each matching device's active and local speaker |
| `person.<id>` | Devices assigned to that person, plus devices in that person's current area | — |
| No match | Nothing is delivered (`follow_me` / `person.*`) | No-op (returns a status response without broadcasting to unoccupied areas) |

An unknown device slug in `target_device` is an error (`ServiceValidationError`), not a fallback.

Headless and BLE-beacon-only devices never receive notifications.

---

## Notifications

### `latter.notify`
Shows a banner on the device, with an optional chime and an optional camera snapshot.

| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `message` | string | **required** | Truncated to 160 characters on the device |
| `title` | string | `Notification` | Truncated to 48 characters |
| `priority` | `normal` \| `warning` \| `critical` | `normal` | |
| `duration` | int (seconds) | `8` | Clamped to 2–60 |
| `chime` | bool | `true` | |
| `camera_entity` | `camera.*` | — | Adds a signed baseline-JPEG snapshot URL |
| `announce` | bool | `false` | Also speaks `message` with TTS on the device (through its Assist satellite, or its local speaker). The banner chime is skipped when this is on. |

Latter calls the bound ESPHome device's `esphome.<node>_show_notification` action with a monotonic `alert_id` and fires `latter_event` with `type: notification_dispatched`.

### `latter.intercom_broadcast`
Speaks a TTS message or plays an audio clip on speakers.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `message` | string | Spoken with `tts.speak` |
| `media_url` | string | Audio clip URL. Played through `music_assistant.play_announcement` on Music Assistant players, and through `media_player.play_media` with `announce: true` elsewhere. |
| `target_speakers` | entity list or special target | When empty, all online Music Assistant players |
| `tts_entity` | `tts.*` | When empty, the first TTS entity |

---

## Media

### `latter.set_active_speaker`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `entity_id` | `media_player.*` | **required** | |
| `transfer_queue` | bool | `true` | Moves the current queue to the new speaker (see below) |

How the queue moves:
- **Between two Music Assistant players:** Latter maps both ends to their Music Assistant counterparts and calls `music_assistant.transfer_queue`. A Latter device's own speaker maps to the Music Assistant player linked to that device (its **Music Assistant Player** setting); other speakers map by device or MAC address.
- **Otherwise:** Latter pauses the source and replays its `media_content_id` on the target.

### `latter.media_command`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `command` | string | `toggle` | `play`, `pause`, `toggle`, `next`, `previous`, `stop`, `seek`, `clear_queue`, `play_media` |
| `entity_id` | `media_player.*` | the device's active speaker | |
| `seek_position` | float (seconds) | — | For `seek` |
| `media_id`, `media_type`, `enqueue` | string | — | For `play_media`. If Music Assistant can't play an artist or album URI directly, Latter expands it to tracks (up to 25). |

### `latter.media_volume`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `action` | `set` \| `up` \| `down` \| `mute` | `set` | |
| `volume_level` | number | — | 0–1, or 0–100 (values above 1 are treated as a percentage) |
| `entity_id` | `media_player.*` | the active speaker | |

If the speaker has a **volume override** configured in Studio, the command goes to that entity instead. For `number` and `input_number` overrides, steps use the entity's own step size, or 5% of its range if it has none.

### `latter.music_browse`
Fetches one page of items and sends them to the device with `set_browse_slots`. All modes except `speakers` require Music Assistant.

| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `mode` | string | `speakers` | `speakers`, `favorites`, `playlist`, `artist`, `album`, `radio`, `podcast`, `audiobook`, `track`, `artist_albums`, `album_tracks`, `current_album_tracks`, `active_queue`, `podcast_episodes`, `lyrics`, `bio` |
| `page` | int | `1` | |
| `page_size` | int | `5` | Capped at the device's slot capacity |
| `search` | string | — | A drill-down ID. For `lyrics` and `bio`, pass `Title\|Artist\|Album`. |
| `speaker`, `last_speaker` | `media_player.*` | — | |
| `album_sort` | `name` \| `year` \| `year_desc` | `name` | |
| `artist_album_sort` | `year` \| `year_desc` \| `name` | `year` | |
| `podcast_sort` | `newest` \| `oldest` | `newest` | |

Where lyrics and bios come from, in order:
1. **Music Assistant metadata.**
2. **[LRCLIB](https://lrclib.net)** for lyrics. Plain lyrics are preferred; synced lyrics are passed through as text.
3. **Wikipedia's REST summary API** for bios.

Text is wrapped to 32 characters per line.

---

## Areas

### `latter.set_active_area`
| Field | Type | Notes |
| :--- | :--- | :--- |
| `area_id` | string | **Required.** An Area ID or Area name. |

Whether the device's speaker follows to the new Area is the device's own setting, **Media follows this Device to its new Area** in Studio (**Audio & Voice**). The same setting applies when Bluetooth moves the device.

On roaming devices (the hardware reports it isn't stationary) with **Voice Follows Me** on, this also moves the device's Home Assistant Area. Stationary devices are never moved.

### `latter.area_browse`
Sends a page of areas or entities to the device. `entities` and `home` pages use `set_area_slots`, which includes slider levels. `areas` uses `set_browse_slots`.

| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `mode` | `areas` \| `entities` \| `home` | `entities` | `home` covers entities across the whole home |
| `area_id` | area | the device's current area | |
| `domain_filter` | string | `all` | `scene`, `light`, `cover`, `fan`, `switch`, `media` / `media_player`, `climate`, or a comma-separated list |
| `page` | int | `1` | |
| `page_size` | int | `3` (`5` for `areas`) | |

### `latter.area_action`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `entity_id` | string | — | Any entity, or one of `whole_home.thermostat`, `whole_home.lock`, `whole_home.garage`, `whole_home.vacuum`, which resolve to the entities configured in Studio |
| `action` | string | — | `toggle`, `turn_on`, `turn_off`, `set_level`, `set_color`, `set_kelvin`, `step_up`, `step_down`, `arm_home`, `arm_away`, `arm_night`, `disarm`, `heat`, `cool`, `auto`, `off`, `lock`, `unlock`, `open`, `start`, `pause`, `dock` (`lock` and `alarm_control_panel` require an explicit verb; `toggle` is rejected) |
| `level` | number | — | 0–100 for brightness, position, and fan speed; Kelvin for `set_kelvin` |
| `code` | string | — | Alarm PIN, or `#RRGGBB` for `set_color` |
| `area_id` | area | — | |

Alarm actions with no `entity_id` use the alarm panel configured in Studio. `lock` (`lock`, `unlock`, `open`) and `alarm_control_panel` (`arm_home`, `arm_away`, `arm_night`, `disarm`) require an explicit action verb and never accept `toggle`.

---

## Remotes

### `latter.remote_action`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `slot` | int 1–10 | `1` | |
| `action` | string | `select_slot` | `select_slot`, `toggle`, `command`, `volume_up`, `volume_down`, `volume_mute`, `media_play_pause` |
| `command` | string | — | A key name such as `up`, `down`, `left`, `right`, `select`, `back`, `home` |

Key names are translated per platform:
- **Android TV, Fire TV, Bravia:** native key codes.
- **Denon AVR:** the integration's command URLs.
- **LG webOS:** `webostv.button`.
- **Apple TV:** `back` is sent as `menu`.
- **Anything else:** generic `remote.send_command`.

---

## Calendar

### `latter.calendar_fetch`
| Field | Type | Default |
| :--- | :--- | :--- |
| `days` | int 1–60 | `7` |
| `page`, `page_size` | int | `1`, `5` |

Returns at most 25 events, with duplicates (same summary and start) removed. Events with a location get a signed map URL.

### `latter.calendar_create_event`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `summary` | string | **required** | |
| `calendar_entity` | `calendar.*` | the first configured calendar | |
| `start_date_time`, `end_date_time` | ISO datetime | — | |
| `in_minutes`, `duration_minutes` | int | `15`, `30` | Used when no start time is given. The minimum duration is 5 minutes. |
| `description` | string | — | |

---

## Doorbell and appearance

### `latter.doorbell_intercom` *(experimental)*
Doorbell listen, push-to-talk reply, and unlock actions, plus `call_target`, which rings other displays with a notification. Can return a response.

- **Listen** (`listen_start` / `listen_stop` / `listen_toggle`): the camera's RTSP audio runs through an FFmpeg noise-reduction filter and plays on the device as FLAC.
- **Reply** (`talk_message` / `quick_reply`): Home Assistant speaks `message` with TTS on the camera's `media_player` (a sibling entity on the camera's device, or a Studio volume override). Latter firmware sends the text its push-to-talk speech recognition produced. Listening pauses during the reply and resumes after it, unless the call ended in the meantime. A new reply replaces a pending one, so listening resumes only after the last reply.
- **Unlock** (`unlock_door`): calls `lock.unlock` on the camera's lock, or the lock configured in Studio.
- **`call_target`**: sends a critical `latter.notify` ("Tap to answer") to the display named in `message`, or to every other display. No audio path is opened between displays, and it does not start listening on the calling device (the device sends its own listen_start).

There is no live audio from the device to the door and no echo cancellation.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `action` | string | `listen_start`, `listen_stop`, `listen_toggle` (the default), `talk_message`, `quick_reply`, `unlock_door`, `call_target`, `set_noise_reduction`, `select_camera` |
| `camera_entity` / `camera_index` | `camera.*` / int 0–9 | |
| `message` | string | Text to speak or target device slug (`all` or `<slug>`), depending on `action` |
| `noise_reduction` | `strong` \| `light` \| `off` | FFmpeg noise-reduction level for the listen stream. Applies to this device until the integration reloads or Studio settings are saved; the default comes from Studio (`strong`). `set_noise_reduction` applies it and restarts listening if active. |

### `latter.save_custom_color`
| Field | Type | Notes |
| :--- | :--- | :--- |
| `hex_color` | `#RRGGBB` | Added to the system color library (24 colors maximum) and applied to the device |
| `name` | string | |

### `latter.set_dock_apps`
Saves a device's Home dock: the apps shown, in order (Settings is always last). Latter firmware sends it when you show or hide an app in **Settings → Home** on the device; Studio's **Home dock apps** edits the same setting. Until a device has one, it shows the default dock (`music,alarm,area,remote,games,tools`).

| Field | Type | Notes |
| :--- | :--- | :--- |
| `dock_apps` | string | **Required.** Comma-separated, from `music`, `alarm`, `area`, `remote`, `camera`, `games`, `tools`; at least one |

## Maintenance

### `latter.reset_device`
Resets a Latter device to defaults. Choose what to reset with the two fields; at least one must be on.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `target_device` | device, **required** | The Latter device to reset. Unlike the other per-device services, it doesn't fall back to the only device when left out. |
| `device_settings` | boolean, default `true` | Calls the device's `latter_factory_reset` action. The device erases everything it has saved (all its settings, plus the Wi-Fi driver's cached network data and RF calibration) and restarts. Wi-Fi credentials and the API key are compiled into the firmware, so the device rejoins Home Assistant by itself. Needs Latter firmware SDK rev 2026110261 or later; older firmware returns an error asking you to update. Not available for BLE tags. |
| `latter_options` | boolean, default `true` | Puts this device's Latter options (everything set in Studio for it, such as group, dock apps, default speaker, default area, BLE tracking, wallpaper and color) back to the defaults it got when it was added. Kept: the bound ESPHome device and its MAC address, the device slug, and the Music Assistant player link. For a BLE tag, its name and tracked address are kept. System-wide settings aren't touched. |

The request is checked before anything changes. Latter options are reset first, then the device action is sent.
