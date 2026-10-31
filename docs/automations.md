# Automation Recipes

Copy-and-paste starting points. Every field is documented in the [services reference](reference/services.md).

`target_device` accepts a device slug such as `pocket_assistant`, a Home Assistant device ID, or one of the [special targets](reference/services.md#special-target-values) like `all` and `follow_me`.

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

## Follow-me notification

Delivers only to devices in currently occupied areas. If no area is occupied, it goes to every device.

```yaml
alias: Laundry done
triggers:
  - trigger: state
    entity_id: sensor.washer_status
    to: complete
actions:
  - action: latter.notify
    data:
      target_device: follow_me
      title: Laundry
      message: The washer is done
      priority: normal
```

## Notify a person

Targets the devices assigned to that person, plus devices in that person's current area.

```yaml
actions:
  - action: latter.notify
    data:
      target_device: person.alex
      message: Your ride is outside
```

## Intercom announcement

Speaks a message on Music Assistant speakers using TTS. `follow_me` limits it to speakers in occupied areas. With no target, it plays on every online Music Assistant speaker.

```yaml
actions:
  - action: latter.intercom_broadcast
    data:
      message: Dinner is ready
      target_speakers: follow_me        # or a list of media_player entities
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

The `area_changed` event carries `device_slug`, `previous_area_id`, `area_id`, and `assigned_person`. Payloads for both event types are listed in the [entities reference](reference/entities.md#latter_event).

## Occupancy-driven automations

The per-area occupancy sensors are ordinary binary sensors:

```yaml
alias: Bedroom empty, lights off
triggers:
  - trigger: state
    entity_id: binary_sensor.bedroom_ble_occupancy
    to: "off"
    for: "00:05:00"
actions:
  - action: light.turn_off
    target:
      area_id: bedroom
```

## Move a device to an area from an automation

For example, from an NFC tag on a dock:

```yaml
actions:
  - action: latter.set_active_area
    data:
      target_device: pocket_assistant
      area: kitchen
      handoff_media: true    # move the active speaker to one in the new area
```
