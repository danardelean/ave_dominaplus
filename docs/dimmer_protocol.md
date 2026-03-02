# AVE Dominaplus Dimmer (Family 2) - Protocol & Implementation

## Device Info

- **Device family**: 2 (dimmer)
- **Example device**: "Aplique Soggiorno" — device_id=6, command_id=7

## WebSocket Protocol (port 14001)

**Framing**: `\x02` (STX) + command + params/records + `\x03` (ETX) + CRC (2 hex chars) + `\x04` (EOT)

- `\x1D` = parameter separator
- `\x1E` = record separator
- CRC = XOR all bytes from STX to ETX, then `0xFF - result`, as 2 uppercase hex digits

## Dimmer Commands

### SIL (Set Intensity Level) — turn on + set brightness

```
\x02 SIL \x1D {device_id} \x1E {brightness} \x03 {CRC} \x04
```

- Brightness is separated by `\x1E` (record separator), **NOT** `\x1D` (parameter separator). Using `\x1D` crashes the WebSocket connection.
- Brightness range: 0-31 (0 = off, 1 = 10%, 31 = 100%)
- SIL alone handles both turning on and setting brightness. Do **NOT** send EBI before SIL — it causes a race condition where EBI restores the stored brightness ~0.7s after SIL sets the target value.

### EBI (Execute Binary Input) — toggle off

```
\x02 EBI \x1D {device_id} \x1D 2 \x03 {CRC} \x04
```

- `EBI [device_id, 2]` = toggle (used for turning off)
- `EBI [device_id, 3]` = explicit turn on (not needed when using SIL)

## State Updates from Device

### UPD WS — real-time status

```
upd params=['WS', '2', '{device_id}', '{status}']
```

- device_type = 2 (dimmer)
- status: 0 = off, 1-31 = brightness level

### GSF "2" — initial state fetch

Sent on connect to retrieve the state of all dimmers.

### LDI — device list

Entries with device_type=2 are dimmers.

## Brightness Mapping

AVE uses 0-31, HA uses 0-255. The AVE app maps 10%-100% to AVE 1-31.

### Formulas

```
AVE -> HA percentage: pct = (ave_value - 1) * 90 / 30 + 10
HA percentage -> AVE: ave = round((pct - 10) * 30 / 90) + 1

AVE -> HA brightness (0-255): max(1, round(pct * 255 / 100))
HA brightness -> AVE (1-31): max(1, min(31, round((pct - 10) * 30 / 90) + 1))
```

### Reference Table

| AVE | App % | HA Brightness |
|-----|-------|---------------|
| 0   | off   | 0             |
| 1   | 10%   | 26            |
| 16  | 55%   | 140           |
| 31  | 100%  | 255           |

## CRC Verification Examples

| Command | Frame | CRC |
|---------|-------|-----|
| `SIL [6, 31]` | `\x02SIL\x1D6\x1E31\x03` | **9F** |
| `SIL [6, 1]`  | `\x02SIL\x1D6\x1E1\x03`  | **AC** |
| `EBI [6, 2]`  | `\x02EBI\x1D6\x1D2\x03`  | **B4** |
| `EBI [6, 3]`  | `\x02EBI\x1D6\x1D3\x03`  | **B5** |

## Key Issues Discovered

1. **SIL uses `\x1E` not `\x1D`** between device_id and brightness — wrong separator crashes the socket
2. **Do not combine EBI + SIL** for turn on — EBI restores the stored brightness and overwrites the SIL target after ~0.7s delay
3. **SIL alone is sufficient** to turn on and set brightness in a single command
4. **Turn off uses EBI [device_id, 2]** (toggle) since HA only calls turn_off when the device is known to be on
5. **Store last non-zero brightness** separately — when turning off, UPD WS reports status=0 which resets brightness; on turn on, restore the previously saved brightness instead of defaulting to 100%

## Implementation Files

- **`light.py`** — `AveDimmerLight(LightEntity)` with `ColorMode.BRIGHTNESS`
- **`web_server.py`** — `light_turn_on()` sends SIL via records, `light_turn_off()` sends EBI [id, 2], handlers for GSF/LDI/UPD family 2
- **`__init__.py`** — `Platform.LIGHT` registered
