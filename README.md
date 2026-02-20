# 🌟 AVE Dominaplus Integration for Home Assistant

Control your AVE Dominaplus home automation system directly from Home Assistant! This integration uses WebSocket communication with the AVE webserver for a **completely asynchronous** and **100% local** setup.

---

## 📋 Requirements

- An **AVE webserver device** installed and accessible from your Home Assistant instance.
- **Alarm units** connected to the webserver (required for motion sensors and alarm zones).
- Only tested with the **"autologin" setting** enabled in the webserver.
- **AVE Cloud configuration is NOT required**.

---

## 🚀 Installation

1. Install the integration via HACS (recommended) or manually copy the files to your `custom_components` directory.
2. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
3. Search for **"AVE Dominaplus"** and select it.
4. Provide the webserver IP address and configure additional settings as needed.

---

## 🛠️ Supported Devices

### ✅ Switches
- **Fully supported**: Discovered at startup, with names.
- Synced with the **"Get lights"** flag.
- Supports turning on, off, and toggling.

### ✅ Alarm Areas
- **Supported**: Discovered at startup, with names.
- Synced with the **"Get antitheft sensor areas"** flag.
- Provides motion sensor functionality.
- Includes **"Last cleared"** and **"Last revealed"** timestamps as attributes.
- *Note: "Armed" and "Triggered" states are not yet exposed as entities.*

### ✅ Individual Alarm Sensors
- **Supported**: Discovered when the first event is triggered.
- Synced with the **"Get individual antitheft sensors"** flag.
- The system does not provide names, so sensors are auto-named. It is recommended to set custom
   names after discovery.
- These sensors are sensitive and may trigger quickly; configure accordingly.

### ✅ Thermostats
- **Supported** when **"Get thermostats"** is enabled in the config flow.
- For each thermostat the integration creates two entities:
  * a **climate** entity (`AveThermostat`) representing the controller
  * a **number** entity showing the current temperature offset of the device (–5 °C..+5 °C)

#### Climate entity behaviour
- `Mode` controls the combination of season and on/off state:
  * `Cool` for summer mode
  * `Heat` for winter mode
  * `Off` if the thermostat is powered off (support depends on the device)
- `Preset` is either `Schedule` (follow the schedule on the webserver)
  or `Manual` (immediate changes from Home Assistant). Changing the
  target temperature from HA will automatically switch the preset to
  `Manual`, mimicking the vendor app behaviour.
- `Fan mode` reflects the fancoil speed reported by the zone; it is **read‑only**.

#### Offset sensor
- A read‑only number sensor is created for each thermostat exposing the
  device’s current offset.
- The offset **cannot be modified from Home Assistant**; it must be set on the
  physical thermostat itself.  The sensor simply mirrors the value reported
  by the device.

#### Naming
Entity names are obtained from the webserver when the
"Get entities names from webserver" option is enabled.  Otherwise
generated names based on family and device ID are used.
---

## 🔜 Not yet supported (contributors welcome!)

Other devices are not yet supported either for lack of time or lack of devices at hand

- **Dimmers**: Work in progress
- **Scenarios**: Backend discovery is ready; no entity is exposed
- **Areas**: Feel free to come with a plan to add AVE areas and device area assignments without clashing with the HA areas
- **Economizers**: Not yet supported
- **Shutters**: Not yet supported

---

## 🏷️ About Device Names

The integration supports two naming strategies:

1. **Names from Webserver** (Recommended):
   - Entity IDs like: `switch.normalized_ave_name`.
   - Names are fetched from the Dominaplus configuration.
   - Changes are fetched at every restart.

2. **Generated Names**:
   - Entity IDs like: `switch.<ave_family_id>_<ave_device_id>`.
   - Names are automatically generated.

**Tip**: If you plan to customize entity names:
The integration tries its best to not override your custom names. But for better measure:
- First, enable **"Get entities names from webserver"** to discover all entities.
- Then, disable this option before setting custom names to prevent overwriting.

---

## ⚠️ Known Issues

### Multiple Webservers for Different Plants
- Currently, multiple webservers for different plants are **not supported**. Multiple controllers for the
   same plant are supported, but separate plant setups may cause device ID clashes. Support for
   multi-plant setups is being explored.

### Individual sensor alarm states after power outage
- After a webserver or alarm unit reboot, a brief arm/disarm cycle may be needed for sensors to
   start reporting state updates. This behavior is due to the alarm system firmware, not the
   integration.

---

## 🤝 Contributing

Contributions are welcome! If you encounter issues or have feature requests, feel free to open an issue or submit a pull request on GitHub.
You can join our [discord server](https://discord.gg/PQ52jwV6BX)
---

## 📜 License

This project is licensed under the **MIT License**. See the `LICENSE` file for more details.

