# Services Reference

Latter registers 16 services under the `latter` domain. Latter firmware calls most of them from the device. You can also call them from automations, scripts, or your own firmware.

- **Source:** [`services.py`](../../custom_components/latter/services.py), with UI schemas in [`services.yaml`](../../custom_components/latter/services.yaml).
- **Unknown fields are accepted and ignored.** Every schema allows extra keys, so a misspelled field name won't raise an error. Check your spelling.

## Targeting

Most services take one of these fields to choose a device:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `target_device` | string | A device slug (`pocket_assistant`), a config entry ID, or a [special target](#special-target-values) |
| `device_slug` | string | Same as a slug passed in `target_device` |
| `device_id` | string or list | A Home Assistant device ID |

Latter resolves them in this order:
1. A slug or entry ID.
2. A Home Assistant device ID, matched through the device's identifiers and then its name.
3. **Otherwise, the first loaded Latter device.** If you have more than one device, always set a target.

### Special target values

| Value | `notify` / `notify_device` | `intercom_broadcast` |
| :--- | :--- | :--- |
| `all` | Every display device | — |
| `follow_me`, `occupied`, `occupied_areas` | Devices whose current area is occupied | Music Assistant speakers in occupied areas, plus each matching device's active and local speaker |
| `person.<id>` | Devices assigned to that person, plus devices in that person's current area | — |
| No match | Falls back to every display device | Falls back to every online Music Assistant speaker |

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

Latter updates the device's `alert_*` attributes on `sensor.<slug>_area_context` **and** calls `esphome.<slug>_show_notification` directly. It also fires `latter_event` with `type: notification_dispatched`.

### `latter.notify_device`
Identical to `latter.notify`. Both names are registered.

### `latter.intercom_broadcast`
Speaks a TTS message or plays an audio clip on speakers.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `message` | string | Spoken with `tts.speak`, falling back to `tts.cloud_say` |
| `media_url` | string | Audio clip URL. Played through `music_assistant.play_announcement` on Music Assistant players, and through `media_player.play_media` with `announce: true` elsewhere. |
| `target_speakers` | entity list or special target | When empty, all online Music Assistant players |
| `tts_entity` | `tts.*` | When empty, the first TTS entity |

---

## Media

### `latter.set_active_speaker`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `entity_id` (alias `speaker`) | `media_player.*` | **required** | |
| `transfer_queue` | bool | `true` | Moves the current queue to the new speaker (see below) |

How the queue moves:
- **Between two Music Assistant players:** Latter calls `music_assistant.transfer_queue`.
- **Otherwise:** Latter pauses the source and replays its `media_content_id` on the target. If playback was more than 5 s in and the target ends up more than 4 s away from that position, Latter seeks back to it. This takes about 4.5 s.

### `latter.media_command`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `command` (alias `action`) | string | `toggle` | `play`, `pause`, `toggle`, `next`, `previous`, `stop`, `seek`, `clear_queue`, `play_media` |
| `entity_id` / `speaker` | `media_player.*` | the device's active speaker | |
| `seek_position` | float (seconds) | — | For `seek` |
| `media_id`, `media_type`, `enqueue` | string | — | For `play_media`. If Music Assistant can't play an artist or album URI directly, Latter expands it to tracks (up to 25). |

### `latter.media_volume`
| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `action` | `set` \| `up` \| `down` \| `mute` | `set` | |
| `volume_level` | number | — | 0–1, or 0–100 (values above 1 are treated as a percentage) |
| `entity_id` / `speaker` | `media_player.*` | the active speaker | |

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
| `area` (alias `area_id`) | string | **Required.** An Area ID or Area name. |
| `handoff_media` | bool | Moves playback to a Music Assistant speaker in the new area |

This also moves the ESPHome device's Home Assistant Area, unless area sync is off for the device.

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
| `action` | string | `toggle` | `toggle`, `turn_on`, `turn_off`, `set_level`, `set_color`, `set_kelvin`, `step_up`, `step_down`, `arm_home`, `arm_away`, `arm_night`, `arm_vacation`, `disarm`, `heat`, `cool`, `auto`, `off`, `lock`, `unlock`, `start`, `pause`, `dock` |
| `level` | number | — | 0–100 for brightness, position, and fan speed; Kelvin for `set_kelvin` |
| `code` | string | — | Alarm PIN, or `#RRGGBB` for `set_color` |
| `area_id` | area | — | |

Alarm actions with no `entity_id` use the alarm panel configured in Studio.

### `latter.trigger_binding`
| Field | Type | Notes |
| :--- | :--- | :--- |
| `slot` | string | **Required.** An entity ID, a binding name from Studio, or `macro_N`. |
| `action` | `toggle` \| `turn_on` \| `turn_off` \| `step_up` \| `step_down` \| `set_level` | |
| `level` | 0–100 | |

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
| `days` | int 1–60 | `7` when called without the field, `30` in the UI form |
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
Two-way doorbell and SIP actions. Can return a response.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `action` | string | `listen_start`, `listen_stop`, `listen_toggle` (the default), `talk_message`, `quick_reply`, `unlock_door`, `call_target`, `set_anc_mode`, `select_camera` |
| `camera_entity` / `camera_index` | `camera.*` / int 0–9 | |
| `message` | string | Text to speak, a SIP URI, or DTMF digits, depending on `action` |
| `anc_mode` | `ultra` \| `balanced` \| `raw` | Noise-reduction preset for doorbell audio |

### `latter.save_custom_color`
| Field | Type | Notes |
| :--- | :--- | :--- |
| `hex_color` | `#RRGGBB` | Added to the system color library (24 colors maximum) and applied to the device |
| `name` | string | |
