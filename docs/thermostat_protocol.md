# AVE Dominaplus Thermostat (Family 4) - Protocol & Implementation

## Device Info

- **Device family**: 4 (thermostat)
- **Entity class**: `AveThermostat(ClimateEntity)`

## WebSocket Protocol (port 14001)

**Framing**: `\x02` (STX) + command + params/records + `\x03` (ETX) + CRC (2 hex chars) + `\x04` (EOT)

- `\x1D` = parameter separator
- `\x1E` = record separator
- CRC = XOR all bytes from STX to ETX, then `0xFF - result`, as 2 uppercase hex digits

## Thermostat Commands

### STS (Set Temperature/Season)

```
\x02 STS \x1D {device_id} \x1E {season} \x1D {mode} \x1D {temperature_x10} \x03 {CRC} \x04
```

| Parameter | Description |
|-----------|-------------|
| `device_id` | Thermostat device ID |
| `season` | `0` = Cooling, `1` = Heating |
| `mode` | `0` = Schedule, `1` = Manual |
| `temperature_x10` | Target temperature in tenths (e.g., `210` = 21.0 C) |

### TOO (Thermostat On/Off)

```
\x02 TOO \x1D {device_id} \x1D {on_off} \x03 {CRC} \x04
```

| Parameter | Description |
|-----------|-------------|
| `device_id` | Thermostat device ID |
| `on_off` | `0` = OFF (set local_off=1), `1` = ON (clear local_off) |

## Bootstrap Flow

Thermostats are not fetched via GSF like switches. They use a multi-step initialization:

### Step 1: LM — Load Map (Areas)

```
LM
Response records: [[area_id, area_name, area_order], ...]
```

Loads thermostat areas into the map. Signals `_thermostat_lm_done` when complete.

### Step 2: LMC — Load Map Commands (per area)

```
LMC [area_id]
Response records: [[command_id, command_name, command_type, x, y,
                    icod, ico1-ico7, icoc, device_id, device_family], ...]
```

Loads commands for each area. When all areas have `commands_loaded=True`, signals `_thermostat_lmc_done`.

### Step 3: WTS — Whereis Thermostat Status

```
WTS [device_id]
Response parameters: [device_id]
Response records: [[response, fan_level, config, offset_x10, season,
                    temperature_x10, mode, setpoint_x10, forced_mode, local_off], ...]
```

Fetches the full state snapshot for each thermostat.

#### WTS Data Mapping

| Record Index | Property | Conversion |
|--------------|----------|------------|
| 0 | device_response | Raw value |
| 1 | fan_level | 0=OFF, 1=LOW, 2=MED, 3=HIGH |
| 2 | configuration | Raw string |
| 3 | offset | value / 10 |
| 4 | season | 0=Cool, 1=Heat |
| 5 | temperature | value / 10 |
| 6 | mode | "1"/"1F"/"M"=Manual, others=Schedule |
| 7 | set_point | value / 10 |
| 8 | forced_mode | Manual override flag |
| 9 | local_off | 1=Off, 0=On |

## Real-Time State Updates (UPD)

Thermostat state is updated via multiple UPD message subtypes:

### UPD TT — Current Temperature

```
upd params=['TT', '{command_id}', '{temperature_x10}']
```

Looks up device_id from command_id in LMC map. Updates `temperature = value / 10`.

### UPD TP — Set Point

```
upd params=['TP', '{device_id}', '{setpoint_x10}']
```

Updates `set_point = value / 10`.

### UPD TL — Fan Level

```
upd params=['TL', '{command_id}', '{fan_level}']
```

Fan levels: 0=OFF, 1=LOW, 2=MEDIUM, 3=HIGH.

### UPD TLO — Local Off (On/Off State)

```
upd params=['TLO', '{command_id}', '{tlo_flag}']
```

**Important: Logic is INVERTED:**
- `tlo_flag = 0` (thermostat is OFF) -> `local_off = 1`
- `tlo_flag = 1` (thermostat is ON) -> `local_off = 0`

### UPD TO — Temperature Offset

```
upd params=['TO', '{command_id}', '{offset_x10}']
```

Updates `offset = value / 10`.

### UPD TS — Season

```
upd params=['TS', '{command_id}', '{season}']
```

Season values: 0=COOL, 1=HEAT.

### UPD TM — Mode

```
upd params=['TM', '{device_id}', '{mode_string}']
```

Mode strings: "1", "1F", "M" = Manual; others = Schedule.

### UPD TW — Window State

```
upd params=['TW', '{device_id}', '{window_state}']
```

### UPD WT — Direct Property Update

```
upd params=['WT', '{subtype}', '{device_id}', '{value}']
```

| Subtype | Property | Conversion |
|---------|----------|------------|
| `O` | offset | value / 10 |
| `S` | season | as-is (0/1) |
| `T` | temperature | value / 10 |
| `L` | fan_level | as-is (0-3) |
| `Z` | local_off | as-is |

### UPD TR — Thermostat Record

```
upd params=['TR', '{command_id}', '{value}']
```

Looks up command in map using command_id + family=4.

## HVAC Mode Mapping

| HA HVAC Mode | AVE State |
|--------------|-----------|
| `HVACMode.HEAT` | season=1, local_off=0 |
| `HVACMode.COOL` | season=0, local_off=0 |
| `HVACMode.OFF` | local_off=1 |

## Preset Mode Mapping

| HA Preset | AVE Mode String |
|-----------|----------------|
| `PRESET_MANUAL` | "1", "1F", or "M" |
| `PRESET_SCHEDULE` | anything else |

## Fan Mode (Read-Only)

| HA Fan Mode | AVE fan_level |
|-------------|---------------|
| `FAN_OFF` | 0 |
| `FAN_LOW` | 1 |
| `FAN_MEDIUM` | 2 |
| `FAN_HIGH` | 3 |

Fan mode is displayed in HA but cannot be controlled — `async_set_fan_mode` is a no-op.

## Control Flow

### Set Temperature

```
User sets temperature in HA
    |
async_set_temperature(temperature)
    |
send_ws_command("STS", [device_id], [[season, mode, temp * 10]])
    |
Device confirms via UPD TP
```

### Set HVAC Mode

```
User selects HEAT/COOL/OFF
    |
async_set_hvac_mode(hvac_mode)
    |
OFF:  send_ws_command("TOO", [device_id, "0"])
HEAT: send_ws_command("TOO", [device_id, "1"])  (if currently off)
      send_ws_command("STS", [device_id], [[1, mode, temp*10]])
COOL: send_ws_command("TOO", [device_id, "1"])  (if currently off)
      send_ws_command("STS", [device_id], [[0, mode, temp*10]])
    |
Device confirms via UPD TLO/TS
```

### Turn On/Off

```
Turn on:
    1. TOO [device_id, 1]  (clear local_off)
    2. STS [device_id], [[season, mode, temp*10]]

Turn off:
    1. TOO [device_id, 0]  (set local_off)
```

**Note:** Optimistic state updates have been removed. The HA state only updates when the device confirms via WebSocket UPD messages.

## Key Issues Discovered

1. **TLO logic is inverted**: `tlo_flag=0` means the thermostat is OFF (`local_off=1`), not ON
2. **Temperature values are in tenths**: All temperatures in the protocol are multiplied by 10 (e.g., 210 = 21.0 C)
3. **Turning on requires TOO + STS**: First clear local_off with TOO, then send STS with season/mode/temperature
4. **No optimistic state updates**: State changes are only applied when confirmed by the device via UPD messages, preventing UI flickering and state mismatches

## Thermostat Properties (AveThermostatProperties)

| Property | Type | Description |
|----------|------|-------------|
| `device_id` | int | Thermostat device ID |
| `device_name` | str | Device name from WTS or map |
| `temperature` | float | Current temperature (C) |
| `set_point` | float | Target temperature (C) |
| `fan_level` | int | 0-3 (off/low/medium/high) |
| `season` | int | 0=Cooling, 1=Heating, -1=Unknown |
| `mode` | str | "1"/"1F"/"M"=Manual, others=Schedule |
| `offset` | float | Temperature offset (C) |
| `local_off` | int | 1=Off (disabled), 0=On (enabled) |
| `forced_mode` | int | Internal mode flag |
| `window_state` | int | Window open/closed flag |

## Implementation Files

- **`climate.py`** — `AveThermostat(ClimateEntity)` entity, HVAC modes, presets, fan display
- **`ave_thermostat.py`** — `AveThermostatProperties` data class
- **`web_server.py`** — `send_thermostat_sts()`, `thermostat_on_off()`, WTS/LM/LMC handlers, UPD handlers for all thermostat subtypes
- **`ave_map.py`** — Area/command mapping, `GetCommandByIdAndFamily()` lookup
- **`__init__.py`** — `Platform.CLIMATE` registered
