# Document 02 — System Architecture

---

## 2.1 Architecture Overview

The system follows a **5-layer architecture** designed for local-only operation with zero cloud or internet dependencies. All communication occurs via USB serial between the Arduino hardware and the Python backend running on the laptop.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM ARCHITECTURE                            │
│                                                                        │
│  LAYER 1: HARDWARE (Arduino Uno)                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ IR Sensor │  │ IR Sensor │  │  Servo   │  │   LCD Display 16x2   │  │
│  │  (Entry)  │  │  (Exit)  │  │ (Barrier)│  │   I2C @ 0x27         │  │
│  │  Pin D2   │  │  Pin D3  │  │  Pin D9  │  │   SDA=A4, SCL=A5     │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────────┬───────────┘  │
│       │              │             │                    │               │
│       └──────────────┴─────────────┴────────────────────┘               │
│                            │                                            │
│                    Arduino Uno (ATmega328P)                             │
│                     Firmware: smart_parking.ino                         │
│                                                                        │
│ ═══════════════════════════════════════════════════════════════════════ │
│                                                                        │
│  LAYER 2: COMMUNICATION                                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              USB Serial Cable (Type-A to Type-B)               │   │
│  │              Protocol: 9600 baud, 8N1                          │   │
│  │              Format: JSON per line (newline-delimited)         │   │
│  │              Direction: Arduino → Laptop (one-way data)        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│ ═══════════════════════════════════════════════════════════════════════ │
│                                                                        │
│  LAYER 3: BACKEND (Python on Laptop)                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ Serial Bridge │  │  Flask API   │  │  ML Engine   │                 │
│  │ (pyserial)    │  │  (REST +     │  │ (scikit-     │                 │
│  │ Reads JSON    │→ │   WebSocket) │  │  learn)      │                 │
│  │ Parses events │  │  6 endpoints │  │ LinearReg    │                 │
│  │ Validates data│  │  + SocketIO  │  │ MovingAvg    │                 │
│  └───────┬──────┘  └──────┬───────┘  └──────┬───────┘                 │
│          │                │                  │                          │
│          └────────────────┼──────────────────┘                          │
│                           │                                             │
│  ┌────────────────────────▼────────────────────────────┐               │
│  │                    SQLite Database                    │               │
│  │    File: data/smart_parking.db                       │               │
│  │    Mode: WAL (Write-Ahead Logging)                   │               │
│  │    Tables: 5 (config, status, log, predictions,      │               │
│  │             daily_summary)                            │               │
│  └──────────────────────────────────────────────────────┘               │
│                                                                        │
│ ═══════════════════════════════════════════════════════════════════════ │
│                                                                        │
│  LAYER 4: REAL-TIME TRANSPORT                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              Flask-SocketIO (WebSocket)                          │  │
│  │              Event: 'parking_update'                            │  │
│  │              Direction: Server → All connected clients           │  │
│  │              Trigger: Every serial event processed               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│ ═══════════════════════════════════════════════════════════════════════ │
│                                                                        │
│  LAYER 5: FRONTEND (Browser)                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Web Dashboard                                │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │  │
│  │  │Occupancy │  │  Status  │  │   AI     │  7 Cards Total       │  │
│  │  │  Ring    │  │  Badge   │  │Prediction│                      │  │
│  │  └──────────┘  └──────────┘  └──────────┘                     │  │
│  │  ┌──────────┐  ┌──────────┐                                   │  │
│  │  │  Peak    │  │Utilization│                                   │  │
│  │  │  Hours   │  │  Gauge   │                                   │  │
│  │  └──────────┘  └──────────┘                                   │  │
│  │  ┌─────────────────────────┐  ┌──────────┐                   │  │
│  │  │   Timeline Chart        │  │  Daily   │                   │  │
│  │  │   (Chart.js Line)       │  │  Chart   │                   │  │
│  │  └─────────────────────────┘  └──────────┘                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2.2 Data Flow Diagram

```
Step 1: Vehicle approaches entry/exit
         │
Step 2: IR sensor beam is broken (LOW signal)
         │
Step 3: Arduino firmware detects + debounces (1000ms)
         │
Step 4: Firmware updates count (increment or decrement)
         │
Step 5: Firmware controls barrier (servo 90° → 3s → 0°)
         │
Step 6: Firmware updates LCD ("Slots: X/4 OK/FULL")
         │
Step 7: Firmware sends JSON via Serial.println()
         │  {"e":"ENTRY","c":2,"m":4,"t":12345}
         │
Step 8: Python serial_bridge.py reads the line
         │
Step 9: _parse_line() validates JSON structure
         │
Step 10: _process_event() executes:
         ├── update_status() → parking_status table
         ├── log_event() → occupancy_log table
         └── socketio.emit('parking_update', payload)
                  │
Step 11: WebSocket pushes to all connected browsers
                  │
Step 12: Frontend JS updates DOM:
         ├── Occupancy ring animation
         ├── Status badge (AVAILABLE/FULL)
         ├── Chart.js adds data point
         └── Last event + timestamp display
```

## 2.3 Component Interaction Matrix

| Component | Sends To | Receives From | Protocol |
|---|---|---|---|
| IR Sensor (Entry) | Arduino Pin D2 | Physical world | Digital signal |
| IR Sensor (Exit) | Arduino Pin D3 | Physical world | Digital signal |
| Arduino Firmware | USB Serial | IR Sensors, own state | JSON @ 9600 |
| Servo Motor | N/A | Arduino Pin D9 | PWM signal |
| LCD Display | N/A | Arduino I2C | I2C @ 0x27 |
| Serial Bridge | Database, WebSocket | Arduino serial | pyserial |
| Flask Server | HTTP responses, WebSocket | HTTP requests | REST + WS |
| ML Engine | Database (predictions) | Database (events) | Function calls |
| SQLite Database | Query results | SQL queries | sqlite3 driver |
| Dashboard (Browser) | HTTP requests, WS connect | HTTP responses, WS events | HTTP + WS |
| Chart.js | Canvas rendering | JS data arrays | JavaScript API |

## 2.4 Concurrency Model

```
┌──────────────────────────────────────────────────────────┐
│                  FLASK APPLICATION                        │
│                                                          │
│  Main Thread:           Flask HTTP request handling      │
│  Background Thread 1:   Serial Bridge (reading loop)    │
│  Background Thread 2:   WebSocket event emission        │
│                                                          │
│  Database Access:       WAL mode enables concurrent     │
│                         reads without blocking writes    │
└──────────────────────────────────────────────────────────┘
```

The serial bridge runs in a daemon thread, continuously reading from the serial port (or simulating events). When an event is processed, it writes to the database and emits a WebSocket event — both are thread-safe operations. Flask handles HTTP API requests on the main thread. WAL (Write-Ahead Logging) mode in SQLite ensures that API reads don't block serial event writes.

## 2.5 Failure Recovery

| Failure | System Behavior |
|---|---|
| Arduino disconnected mid-operation | Serial bridge catches exception, logs warning, retries every 5 seconds |
| Browser tab closed and reopened | WebSocket auto-reconnects, dashboard loads latest state from `/api/status` |
| Server restarted | Database persists on disk, all historical data preserved. Barrier defaults to closed (safe state). |
| Malformed serial data | `_parse_line()` returns None, event is silently dropped, no crash |
| Database file deleted | `init_db()` recreates all tables on next server start |

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
