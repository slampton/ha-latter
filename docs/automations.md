# Automation Recipes

Copy-and-paste starting points. Every field is documented in the [services reference](reference/services.md).

`target_device` accepts a device slug such as `pocket_assistant`, a Home Assistant device ID, or one of the [special targets](reference/services.md#special-target-values) like `all` and `occupied_areas`.

---

## Doorbell: camera popup on every display

Latter already does this automatically: if a camera is configured in **Studio → Shared Entities → Cameras**, Latter finds the doorbell's ring entity on its own. Use this recipe only when your trigger isn't a ring entity Latter can detect, such as a gate sensor or a button in another integration.

```yaml
alias: Gate opened, show camera
triggers:
  - trigger: state
    entity_id: binary_sensor.side_gate
    to: "on"
actions:
  - action: latter.notify
    data:
      target_device: all
      title: Side Gate
      message: Gate opened
      priority: critical      # normal | warning | critical
      duration: 20            # seconds, 2–60
      chime: true
      camera_entity: camera.side_yard
```

## Notify the occupied Areas

Delivers only to devices in currently occupied areas. If no area is occupied, nothing is delivered.

```yaml
alias: Laundry done
triggers:
  - trigger: state
    entity_id: sensor.washer_status
    to: complete
actions:
  - action: latter.notify
    data:
      target_device: occupied_areas
      title: Laundry
      message: The washer is done
      priority: normal
```

## Notify a person

Targets the devices assigned to that person, plus devices in that person's current area. If none match, nothing is delivered.

```yaml
actions:
  - action: latter.notify
    data:
      target_device: person.alex
      message: Your ride is outside
```

## Intercom announcement

Speaks a message on Music Assistant speakers using TTS. `target_device: occupied_areas` limits it to speakers in occupied areas, and `target_speakers` picks speakers by entity. With neither, it plays on every online Music Assistant speaker.

```yaml
actions:
  - action: latter.intercom_broadcast
    data:
      message: Dinner is ready
      target_device: occupied_areas     # or target_speakers: [media_player.kitchen, ...]
      # tts_entity: tts.piper           # optional; defaults to the first tts.* entity
```

## React when a device or person changes areas

Latter fires `latter_event` on the event bus:

```yaml
alias: Office lights follow Alex
triggers:
  - trigger: event
    event_type: latter_event
    event_data:
      type: area_changed
      assigned_person: person.alex
      area_id: office
actions:
  - action: light.turn_on
    target:
      area_id: office
```

The `area_changed` event carries `device_slug`, `previous_area_id`, `area_id`, and `assigned_person`. Payloads for all three event types are listed in the [entities reference](reference/entities.md#latter_event).

## Occupancy-driven automations

The per-area occupancy sensors are ordinary binary sensors (`binary_sensor.latter_system_<area>_occupancy`):

```yaml
alias: Bedroom empty, lights off
triggers:
  - trigger: state
    entity_id: binary_sensor.latter_system_bedroom_occupancy
    to: "off"
    for: "00:05:00"
actions:
  - action: light.turn_off
    target:
      area_id: bedroom
```

## Move a device to an area from an automation

For example, from an NFC tag on a dock. On a roaming device with **Voice Follows Me** on, this also moves the device's Home Assistant Area.

```yaml
actions:
  - action: latter.set_active_area
    data:
      target_device: pocket_assistant
      area_id: kitchen       # the speaker follows if the device's "Media Follows This Device" setting is on
```

## Wake bedroom lights when an on-device alarm rings

Every display exposes sleep-safe **Alarm Ringing**, **Timer Active**, and **Timer Remaining** entities on its Latter device:

```yaml
alias: Sunrise lamp on Wrist Assist alarm
triggers:
  - trigger: state
    entity_id: binary_sensor.wrist_assist_alarm_ringing
    to: "on"
actions:
  - action: light.turn_on
    target:
      area_id: bedroom
    data:
      brightness_pct: 40
      transition: 30
```

## Switch Do Not Disturb, Bedtime Mode, or wake-word mode on a schedule (even while sleeping)

Because `switch.<slug>_do_not_disturb`, `switch.<slug>_bedtime_mode`, `select.<slug>_device_group`, `select.<slug>_wake_word_mode`, and `number.<slug>_alert_volume` write to the Device's sleep-safe subentry (`device_prefs`), automations succeed even if a battery handheld is currently hibernating (while live `light.<slug>_screen`, `switch.<slug>_screensaver`, and `button.<slug>_dismiss_alert` control awake displays directly):

```yaml
alias: Quiet bedside alert volume at night
triggers:
  - trigger: time
    at: "22:30:00"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.pocket_assistant_do_not_disturb
  - action: number.set_value
    target:
      entity_id: number.pocket_assistant_alert_volume
    data:
      value: 35
```
