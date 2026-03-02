# AVE Dominaplus Dimmer (Famiglia 2) - Protocollo & Implementazione

## Info Dispositivo

- **Famiglia dispositivo**: 2 (dimmer)
- **Esempio**: "Aplique Soggiorno" — device_id=6, command_id=7

## Protocollo WebSocket (porta 14001)

**Framing**: `\x02` (STX) + comando + parametri/record + `\x03` (ETX) + CRC (2 caratteri hex) + `\x04` (EOT)

- `\x1D` = separatore parametri
- `\x1E` = separatore record
- CRC = XOR di tutti i byte da STX a ETX, poi `0xFF - risultato`, come 2 cifre hex maiuscole

## Comandi Dimmer

### SIL (Set Intensity Level) — accensione + impostazione luminosità

```
\x02 SIL \x1D {device_id} \x1E {luminosità} \x03 {CRC} \x04
```

- La luminosità è separata da `\x1E` (separatore record), **NON** `\x1D` (separatore parametri). Usare `\x1D` causa il crash della connessione WebSocket.
- Range luminosità: 0-31 (0 = spento, 1 = 10%, 31 = 100%)
- SIL da solo gestisce sia l'accensione che l'impostazione della luminosità. **NON** inviare EBI prima di SIL — causa una race condition dove EBI ripristina la luminosità memorizzata ~0.7s dopo che SIL ha impostato il valore target.

### EBI (Execute Binary Input) — toggle spegnimento

```
\x02 EBI \x1D {device_id} \x1D 2 \x03 {CRC} \x04
```

- `EBI [device_id, 2]` = toggle (usato per spegnere)
- `EBI [device_id, 3]` = accensione esplicita (non necessario se si usa SIL)

## Aggiornamenti di Stato dal Dispositivo

### UPD WS — stato in tempo reale

```
upd params=['WS', '2', '{device_id}', '{stato}']
```

- device_type = 2 (dimmer)
- stato: 0 = spento, 1-31 = livello luminosità

### GSF "2" — recupero stato iniziale

Inviato alla connessione per ottenere lo stato di tutti i dimmer.

### LDI — lista dispositivi

Le voci con device_type=2 sono dimmer.

## Mappatura Luminosità

AVE usa 0-31, HA usa 0-255. L'app AVE mappa 10%-100% su AVE 1-31.

### Formule

```
AVE → percentuale HA: pct = (valore_ave - 1) * 90 / 30 + 10
Percentuale HA → AVE: ave = round((pct - 10) * 30 / 90) + 1

AVE → luminosità HA (0-255): max(1, round(pct * 255 / 100))
Luminosità HA → AVE (1-31): max(1, min(31, round((pct - 10) * 30 / 90) + 1))
```

### Tabella di riferimento

| AVE | App % | Luminosità HA |
|-----|-------|---------------|
| 0   | spento| 0             |
| 1   | 10%   | 26            |
| 16  | 55%   | 140           |
| 31  | 100%  | 255           |

## Esempi Verifica CRC

| Comando | Frame | CRC |
|---------|-------|-----|
| `SIL [6, 31]` | `\x02SIL\x1D6\x1E31\x03` | **9F** |
| `SIL [6, 1]`  | `\x02SIL\x1D6\x1E1\x03`  | **AC** |
| `EBI [6, 2]`  | `\x02EBI\x1D6\x1D2\x03`  | **B4** |
| `EBI [6, 3]`  | `\x02EBI\x1D6\x1D3\x03`  | **B5** |

## Problemi Chiave Riscontrati

1. **SIL usa `\x1E` non `\x1D`** tra device_id e luminosità — il separatore sbagliato causa il crash del socket
2. **Non combinare EBI + SIL** per l'accensione — EBI ripristina la luminosità memorizzata e sovrascrive il target di SIL dopo ~0.7s di ritardo
3. **SIL da solo è sufficiente** per accendere e impostare la luminosità in un unico comando
4. **Lo spegnimento usa EBI [device_id, 2]** (toggle) dato che HA chiama turn_off solo quando il dispositivo è noto essere acceso

## File Implementazione

- **`light.py`** — `AveDimmerLight(LightEntity)` con `ColorMode.BRIGHTNESS`
- **`web_server.py`** — `light_turn_on()` invia SIL tramite records, `light_turn_off()` invia EBI [id, 2], handler per GSF/LDI/UPD famiglia 2
- **`__init__.py`** — `Platform.LIGHT` registrata
