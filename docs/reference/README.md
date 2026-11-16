# Reference

Technical reference for people building on Latter.

| Document | Contents |
| :--- | :--- |
| [Services](services.md) | All 19 `latter.*` services (17 user/automation services + `device_hello` & `timer_alarm_state`), parameters, and security PIN rules |
| [Entities](entities.md) | The 3-tier entity architecture across all 6 Home Assistant platforms, attributes, and `latter_event` |
| [HTTP API](http-api.md) | All 7 `/api/latter/*` views, HMAC URL signing, Bearer wallpaper upload, and JPEG/FLAC transcoding |

For the device side of the protocol (what firmware must implement to be discovered and to receive slot data), see [esphome-latter-core: Device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md).
