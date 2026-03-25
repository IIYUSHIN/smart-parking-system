# Document 08 — Arduino Firmware Documentation

---

## 8.1 Firmware Overview

The Arduino firmware is the IoT layer of the smart parking system. It runs on an Arduino Uno (ATmega328P) and handles all physical hardware interactions: sensor reading, barrier control, LCD display updates, and serial data transmission.

**File:** `arduino/smart_parking/smart_parking.ino`
**Language:** C/C++ (Arduino framework)
**Lines:** 195

## 8.2 Hardware Wiring Diagram

```
                    ARDUINO UNO
              ┌─────────────────────┐
              │                     │
    IR Entry ─┤ D2           D9    ├─ Servo Motor (Signal)
              │                     │
    IR Exit  ─┤ D3           5V    ├─ Servo VCC + LCD VCC + IR VCC
              │                     │
              │              GND   ├─ Servo GND + LCD GND + IR GND
              │                     │
    LCD SDA  ─┤ A4                  │
              │                     │
    LCD SCL  ─┤ A5                  │
              │                     │
    USB      ─┤ Type-B   →  Laptop │
              │                     │
              └─────────────────────┘
```

### Pin Assignment Table

| Pin | Function | Component | Signal Type | Direction |
|---|---|---|---|---|
| **D2** | Digital Input | Entry IR Sensor | HIGH (idle) / LOW (triggered) | Input |
| **D3** | Digital Input | Exit IR Sensor | HIGH (idle) / LOW (triggered) | Input |
| **D9** | PWM Output | Servo Motor (SG90) | 0° (closed) to 90° (open) | Output |
| **A4** | I2C SDA | LCD Display | I2C data | Bidirectional |
| **A5** | I2C SCL | LCD Display | I2C clock | Output |
| **USB** | Serial TX/RX | Laptop (Python) | JSON @ 9600 baud | Output (data) |
| **5V** | Power | All components | 5V DC | Output |
| **GND** | Ground | All components | Ground reference | Output |

## 8.3 IR Sensor Behavior

The infrared proximity sensors output a **digital signal**:

| Beam Status | Pin Reading | Meaning |
|---|---|---|
| Beam intact (no object) | `HIGH` | No vehicle detected |
| Beam broken (object present) | `LOW` | Vehicle detected |

**Debouncing:** Each sensor has a 1000ms debounce window to prevent multiple triggers from a single vehicle:
```cpp
const unsigned long DEBOUNCE_MS = 1000;

if (sensorState == LOW && !entryBlocked
    && (now - lastEntryTrigger > DEBOUNCE_MS)) {
    // Process event...
}
```

**State tracking:** Boolean flags (`entryBlocked`, `exitBlocked`) ensure each beam-break triggers exactly one event, even if the beam stays broken for multiple loop iterations:
```
Vehicle approaches → beam breaks → event fires → flag set
Vehicle passes     → beam restores → flag cleared → ready for next
```

## 8.4 Firmware Logic Modules

### Module M1: Entry Detection (`checkEntry()`)

```
┌──────────────────────────────┐
│ Read ENTRY_IR_PIN (Digital)  │
│            │                 │
│   ┌────────▼────────┐       │
│   │ sensorState LOW? │       │
│   │ (beam broken)    │       │
│   └──┬─────────┬────┘       │
│      │ YES     │ NO         │
│      │         │            │
│   ┌──▼──────┐  └──► Reset   │
│   │Debounce │      flag     │
│   │passed?  │               │
│   └──┬──────┘               │
│      │ YES                  │
│      │                      │
│   ┌──▼──────────┐           │
│   │count < MAX? │           │
│   └──┬─────┬────┘           │
│      │YES  │NO              │
│      │     │                │
│   ┌──▼──┐  └──► Do nothing  │
│   │count++│     (barrier     │
│   │openBarrier()│  stays     │
│   │updateLCD() │  closed)   │
│   │sendSerialJSON()│        │
│   └─────┘                   │
└──────────────────────────────┘
```

### Module M2: Exit Detection (`checkExit()`)

Identical logic to M1, but decrements count when `count > 0`.

### Module M4: Barrier Control (`openBarrier()`)

```cpp
void openBarrier() {
    barrierServo.write(90);   // Open position
    delay(3000);              // Hold 3 seconds for vehicle passage
    barrierServo.write(0);    // Close position
}
```

| State | Servo Angle | Duration | Purpose |
|---|---|---|---|
| **Closed** (default) | 0° | Permanent until triggered | Blocks entry/exit |
| **Open** | 90° | 3 seconds | Allows vehicle passage |
| **Return to closed** | 0° | Immediate | Safety: barrier always returns to closed |

**Safety: The barrier defaults to closed.** On power loss, reset, or any error, the servo returns to 0° (closed position).

### Module M5: Serial JSON Output (`sendSerialJSON()`)

**Format:** Single JSON object per line (newline-terminated)

```json
{"e":"ENTRY","c":2,"m":4,"t":12345}
```

**Field specification:**

| Field | Key | Type | Valid Values | Description |
|---|---|---|---|---|
| Event Type | `e` | String | `"ENTRY"`, `"EXIT"`, `"BOOT"` | What happened |
| Count | `c` | Integer | 0 to 4 | Vehicle count AFTER event |
| Max | `m` | Integer | Always 4 | Physical capacity |
| Time | `t` | Unsigned Long | 0 to 2³² | Arduino millis() timestamp |

**Why JSON?** Machine-parseable, self-describing, human-readable, trivial to parse in Python via `json.loads()`.

### LCD Display Update (`updateLCD()`)

```
┌────────────────┐
│ Smart Parking   │  ← Line 0 (static, set in setup())
│ Slots: 2/4  OK │  ← Line 1 (updated on every event)
└────────────────┘
```

| Count | Line 1 Display | Status |
|---|---|---|
| 0 | `Slots: 0/4  OK  ` | Available |
| 1 | `Slots: 1/4  OK  ` | Available |
| 2 | `Slots: 2/4  OK  ` | Available |
| 3 | `Slots: 3/4  OK  ` | Available |
| 4 | `Slots: 4/4  FULL` | Full |

## 8.5 Main Loop

```cpp
void loop() {
    checkEntry();     // Read entry sensor, process, debounce
    checkExit();      // Read exit sensor, process, debounce
    delay(50);        // 50ms cycle time
}
```

**Loop frequency:** 20 Hz (50ms delay)
**Why 50ms?** Balances responsiveness (fast enough to catch vehicles) with stability (prevents sensor noise). A vehicle at 5 km/h takes ~1 second to pass the sensor beam — 50ms is 20× faster than needed.

## 8.6 Boot Sequence

```
Power on → setup()
    │
    ├── Serial.begin(9600)        ← Open USB serial
    ├── pinMode(D2, INPUT)        ← Entry IR sensor
    ├── pinMode(D3, INPUT)        ← Exit IR sensor
    ├── barrierServo.attach(D9)   ← Servo on PWM pin
    ├── barrierServo.write(0)     ← Barrier defaults to CLOSED
    ├── lcd.init()                ← Initialize I2C LCD
    ├── lcd.backlight()           ← Turn on LCD backlight
    ├── lcd.print("Smart Parking")← Show title
    ├── lcd.print("Slots: 0/4 OK")← Show initial state
    ├── sendSerialJSON("BOOT")    ← Notify Python: {"e":"BOOT","c":0,"m":4,"t":0}
    └── delay(1000)               ← 1 second stabilization
```

## 8.7 Libraries Required

| Library | Version | Purpose | Install |
|---|---|---|---|
| `Servo.h` | Built-in | Servo motor control | Pre-installed |
| `Wire.h` | Built-in | I2C communication for LCD | Pre-installed |
| `LiquidCrystal_I2C.h` | 1.1.2+ | Simplified LCD control over I2C | Arduino Library Manager → search "LiquidCrystal I2C" |

## 8.8 Upload Instructions

1. Open `arduino/smart_parking/smart_parking.ino` in Arduino IDE
2. Select Board: **Arduino Uno**
3. Select Port: **COM3** (or whichever port Arduino is on)
4. Install library: `LiquidCrystal_I2C` via Library Manager
5. Click **Upload** (Ctrl+U)
6. Open Serial Monitor (Ctrl+Shift+M) at 9600 baud to see JSON output
7. Wave hand over IR sensors to see events

## 8.9 Edge Cases Handled

| Edge Case | Firmware Behavior |
|---|---|
| Entry when parking is FULL (count = 4) | No count increment, no barrier open, no serial output |
| Exit when parking is EMPTY (count = 0) | No count decrement, no barrier open, no serial output |
| Both sensors triggered simultaneously | Loop processes entry first, exit second (sequential in 50ms cycle) |
| Sensor held down (object blocking beam) | Single event per beam-break due to state tracking flags |
| Power loss / reset | Count resets to 0, barrier closes, BOOT event sent |
| Rapid successive triggers (< 1s) | Debounce filter ignores triggers within 1000ms window |

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
