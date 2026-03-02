# AVE Dominaplus Switch (Family 1) - Protocol & Implementation

## Device Info

- **Device family**: 1 (switch/light)
- **Entity class**: `LightSwitch(SwitchEntity)`

## WebSocket Protocol (port 14001)

**Framing**: `\x02` (STX) + command + params/records + `\x03` (ETX) + CRC (2 hex chars) + `\x04` (EOT)

- `\x1D` = parameter separator
- `\x1E` = record separator
- CRC = XOR all bytes from STX to ETX, then `0xFF - result`, as 2 uppercase hex digits

## Switch Commands

### EBI (Execute Binary Input)

```
\x02 EBI \x1D {device_id} \x1D {action_code} \x03 {CRC} \x04
```

All switch control uses the EBI command with standard `\x1D` parameter separators.

| Action Code | Description |
|-------------|-------------|
| `10`        | Toggle      |
| `11`        | Turn on     |
| `12`        | Turn off    |

### Examples

```
Turn on device 3:  EBI [3, 11]
Turn off device 3: EBI [3, 12]
Toggle device 3:   EBI [3, 10]
```

## State Updates from Device

### UPD WS — real-time status

```
upd params=['WS', '1', '{device_id}', '{status}']
```

- device_type = 1 (switch)
- status: 0 = off, 1 = on

### GSF "1" — initial state fetch

```
GSF [1]
Response records: [[device_id, device_status], ...]
```

Sent on connect to retrieve the state of all switches. Each record contains a device_id and its current status (0=off, 1=on).

### LDI — device list

```
LDI
Response records: [[device_id, device_name, device_type], ...]
```

Entries with device_type=1 are switches. Initial state is set to -1 (unknown) and will be updated by GSF or UPD messages.

## State Flow

```
User Action (HA UI)
    |
LightSwitch.async_turn_on() / async_turn_off() / async_toggle()
    |
webserver.switch_turn_on() / switch_turn_off() / switch_toggle()
    |
send_ws_command("EBI", [device_id, action_code])
    |
WebSocket: EBI message sent
    |
Device responds: UPD [WS, 1, device_id, status]
    |
manage_upd() -> update_switch()
    |
LightSwitch.update_state(device_status)
    |
async_write_ha_state()
```

## Entity Details

- **Unique ID format**: `ave_switch_{family}_{device_id}`
- **Device class**: `SwitchDeviceClass.SWITCH`
- **Extra attributes**: `AVE_family`, `AVE_device_id`, `AVE_name`
- **State**: `_attr_is_on` (bool) — set from `bool(device_status)` where 0=off, 1=on
- **Invalid states**: `device_status < 0` is ignored (used as placeholder during LDI discovery)

## Implementation Files

- **`switch.py`** — `LightSwitch(SwitchEntity)` entity, platform setup, state management
- **`web_server.py`** — `switch_turn_on()`, `switch_turn_off()`, `switch_toggle()` send EBI commands; GSF/LDI/UPD handlers for family 1
- **`__init__.py`** — `Platform.SWITCH` registered
