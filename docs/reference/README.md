# Reference

Technical reference for people building on Latter.

| Document | Contents |
| :--- | :--- |
| [Services](services.md) | All 6 public `latter.*` actions and 20 private bound-device wire RPCs (`LatterRpcDispatcher`), parameters, and security PIN rules |
| [Entities](entities.md) | The 3-tier entity architecture across all 8 Home Assistant platforms, attributes, and `latter_event` |
| [HTTP API](http-api.md) | All 7 `/api/latter/*` views, HMAC URL signing, Bearer wallpaper upload, and JPEG/MJPEG/FLAC transcoding |

For the device side of the protocol (what firmware must implement to be discovered and to receive slot data), see [esphome-latter-core: Device protocol](https://github.com/slampton/esphome-latter-core/blob/main/docs/device-protocol.md).
