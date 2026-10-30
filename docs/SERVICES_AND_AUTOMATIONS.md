# Latter Services & Automations Cookbook

Latter registers 14 native services under the `latter.*` domain for automations, scripts, and custom ESPHome hardware triggers.

---

## 1. Doorbell & Security Camera Peephole Alert (`latter.notify_device`)

Wake up your Pocket Assistant or Wrist Assist, play an alert chime, display a priority banner, and render a live Baseline-JPEG snapshot from any `camera.*` entity:

```yaml
alias: "Doorbell Ring -> Show Camera Peephole on Pocket Assistant & Wrist Assist"
triggers:
  - trigger: state
    entity_id: binary_sensor.front_doorbell_button
    to: "on"
actions:
  - action: latter.notify_device
    data:
      target_device: "pocket_assistant"
      title: "Front Doorbell"
      message: "Someone is at the Front Door"
      priority: "critical"
      duration: 15
      chime: true
      camera_entity: "camera.front_door"
  - action: latter.notify_device
    data:
      target_device: "wrist_assist"
      title: "Front Doorbell"
      message: "Someone is at the Front Door"
      priority: "critical"
      duration: 15
      chime: true
      camera_entity: "camera.front_door"
```

---

## 2. Household Intercom Broadcast (`latter.intercom_broadcast`)

Broadcast a TTS announcement or audio URL across all active Music Assistant speakers in your home:

```yaml
action: latter.intercom_broadcast
data:
  message: "Dinner is on the table!"
```

---

## 3. Custom Macro Slot Trigger (`latter.trigger_binding`)

Trigger any of the 5 user-configured macro slots (`macro_1` .. `macro_5`) mapped in **Latter Studio &rarr; System &rarr; Macros &amp; YAML**:

```yaml
action: latter.trigger_binding
data:
  target_device: "pocket_assistant"
  slot: "macro_1"
```

---

## 4. Area & Media Handoff Actions

- **`latter.set_active_area`**: Programmatically switch a device's active area context (`area: "living_room"`, `handoff_media: true`).
- **`latter.set_active_speaker`**: Switch the target media player (`entity_id: "media_player.kitchen_speaker"`, `transfer_queue: true`).
- **`latter.media_command`**: Execute debounced playback commands (`command: "toggle" | "play" | "pause" | "next" | "previous" | "seek" | "clear_queue"`).
- **`latter.media_volume`**: Step or set volume (`action: "up" | "down" | "mute" | "set"`), automatically respecting external AVR volume overrides.
