# Document 04 — Project Structure & File Reference

---

## 4.1 Complete Directory Tree

```
smart_parking/                          # PROJECT ROOT
│
├── arduino/                            # HARDWARE FIRMWARE
│   └── smart_parking/
│       └── smart_parking.ino           # Arduino firmware source (195 lines)
│
├── backend/                            # PYTHON BACKEND PACKAGE
│   ├── __init__.py                     # Package initializer
│   ├── config.py                       # Global configuration constants
│   ├── database.py                     # SQLite database layer (5 tables)
│   ├── data_generator.py              # Synthetic data generation (14 days)
│   ├── ml_engine.py                    # AI/ML prediction pipeline
│   ├── serial_bridge.py               # USB serial reader + simulator
│   └── app.py                          # Flask server + API + WebSocket
│
├── frontend/                           # WEB DASHBOARD
│   ├── index.html                      # Main dashboard page (7 cards)
│   ├── manifest.json                   # PWA configuration
│   ├── css/
│   │   └── styles.css                  # Design system (dark theme)
│   ├── js/
│   │   ├── app.js                      # Dashboard logic + DOM updates
│   │   ├── websocket.js               # Real-time WebSocket client
│   │   └── charts.js                   # Chart.js initialization + updates
│   └── assets/
│       └── icons/                      # PWA icon directory (placeholder)
│
├── tests/                              # AUTOMATED TEST SUITE
│   ├── __init__.py                     # Test package initializer
│   ├── test_database.py               # Database layer tests (11 tests)
│   ├── test_ml_engine.py              # ML engine tests (8 tests)
│   ├── test_serial_parser.py          # Serial parser tests (8 tests)
│   └── test_api.py                     # REST API tests (6 tests)
│
├── data/                               # DATABASE STORAGE
│   └── smart_parking.db               # SQLite database file (auto-created)
│
├── models/                             # ML MODEL STORAGE
│   └── occupancy_model.pkl            # Trained LinearRegression model (auto-created)
│
├── docs/                               # PROJECT DOCUMENTATION
│   ├── 01_PROJECT_OVERVIEW.md
│   ├── 02_SYSTEM_ARCHITECTURE.md
│   ├── 03_TECHNOLOGY_STACK.md
│   ├── 04_PROJECT_STRUCTURE.md         # (this file)
│   ├── 05_DATABASE_DESIGN.md
│   ├── 06_ML_ENGINE_DOCUMENTATION.md
│   ├── 07_FRONTEND_DASHBOARD.md
│   ├── 08_ARDUINO_FIRMWARE.md
│   ├── 09_API_REFERENCE.md
│   ├── 10_TESTING_REPORT.md
│   ├── 11_CURRENT_STATUS.md
│   ├── dashboard_overview.png          # Screenshot: initial dashboard
│   ├── dashboard_live_events.png       # Screenshot: live events flowing
│   └── dashboard_final_state.png       # Screenshot: after 40+ events
│
├── venv/                               # Python virtual environment
├── requirements.txt                    # Python dependencies
└── README.md                           # Quick-start documentation
```

## 4.2 File-by-File Detailed Reference

---

### 4.2.1 `backend/config.py` — Global Configuration

**Lines:** ~30 | **Purpose:** Single source of truth for all configurable values

| Constant | Value | Purpose |
|---|---|---|
| `SERIAL_PORT` | `"COM3"` | Arduino serial port (user-adjustable) |
| `BAUD_RATE` | `9600` | Serial communication speed |
| `SERIAL_TIMEOUT` | `1` second | Read timeout for serial |
| `DB_PATH` | `data/smart_parking.db` | SQLite database file location |
| `PARKING_ID` | `"MODEL_01"` | Parking zone identifier |
| `PARKING_NAME` | `"Smart Parking Prototype"` | Human-readable zone name |
| `MAX_CAPACITY` | `4` | Physical model slot count |
| `FLASK_PORT` | `5000` | Web server port |
| `MODEL_PATH` | `models/occupancy_model.pkl` | ML model save location |
| `MOVING_AVG_WINDOW` | `3` | Moving average window size |
| `SIMULATE_INTERVAL_MIN` | `5` seconds | Min time between simulated events |
| `SIMULATE_INTERVAL_MAX` | `15` seconds | Max time between simulated events |

---

### 4.2.2 `backend/database.py` — Database Layer

**Lines:** ~315 | **Purpose:** All database operations, schema management, analytics

**Functions Exposed:**

| Function | Parameters | Returns | Purpose |
|---|---|---|---|
| `get_connection()` | db_path | Connection | Opens SQLite with WAL mode |
| `init_db()` | db_path, parking_id, name, capacity | None | Creates all 5 tables + default config |
| `update_status()` | db_path, parking_id, count, max_cap | dict | Upserts parking_status with derived fields |
| `get_status()` | db_path, parking_id | dict or None | Returns current status |
| `log_event()` | db_path, parking_id, event_type, occupancy, time | int (event_id) | Inserts occupancy event |
| `get_history()` | db_path, parking_id, hours | list[dict] | Events from last N hours |
| `get_all_events()` | db_path, parking_id | list[dict] | All events ever recorded |
| `save_prediction()` | db_path, parking_id, count, start, end, util | int (pred_id) | Saves ML prediction |
| `get_latest_prediction()` | db_path, parking_id | dict or None | Most recent prediction |
| `aggregate_daily()` | db_path, parking_id, date, max_cap | dict | Computes daily summary |
| `get_daily_summaries()` | db_path, parking_id, days | list[dict] | Last N daily summaries |
| `get_hourly_averages()` | db_path, parking_id | list[dict] | Avg occupancy per hour (0-23) |

---

### 4.2.3 `backend/data_generator.py` — Synthetic Data

**Lines:** ~160 | **Purpose:** Generate 14 days of realistic parking events for ML training

**Key Functions:**
- `hourly_arrival_rate(hour, is_weekend)` — Returns Poisson lambda for event generation
- `generate_day(date, parking_id, db_path)` — One full day of events
- `generate_dataset(start_date, num_days)` — Complete multi-day generation

**Output:** 581 events across 14 days with weekday/weekend patterns

---

### 4.2.4 `backend/ml_engine.py` — ML Prediction Pipeline

**Lines:** ~280 | **Purpose:** Training, prediction, and analytics using ML models

**Classes:**
- `MovingAveragePredictor` — 3-point moving average
- `TimeRegressionModel` — sklearn LinearRegression wraper

**Pipeline Function:** `run_full_prediction()` — 10-step end-to-end pipeline

---

### 4.2.5 `backend/serial_bridge.py` — Serial Communication

**Lines:** ~170 | **Purpose:** Read Arduino serial, parse JSON, update DB, emit WebSocket

**Class:** `SerialBridge`
- Real mode: reads from pyserial
- Simulation mode: generates fake events
- Common: `_parse_line()` validates, `_process_event()` persists and broadcasts

---

### 4.2.6 `backend/app.py` — Flask Server

**Lines:** ~175 | **Purpose:** HTTP server, REST API, WebSocket, CLI entry point

**Routes:** 6 REST endpoints + 1 WebSocket event handler + frontend serving
**CLI:** `--simulate`, `--port`, `--serial`, `--generate-data`, `--run-ml`

---

### 4.2.7 `frontend/index.html` — Dashboard Page

**Lines:** ~110 | **Purpose:** 7-card dashboard with semantic HTML5

**Cards:** Occupancy Ring, Status Badge, AI Prediction, Peak Hours, Utilization Gauge, Timeline Chart, Daily Chart

---

### 4.2.8 `frontend/css/styles.css` — Design System

**Lines:** ~350+ | **Purpose:** Complete dark theme with glassmorphism

**Key Design Tokens:** `--bg-primary: #0a0f1c`, `--accent-cyan: #00e5ff`, `--font: Inter`

---

### 4.2.9 `frontend/js/app.js` — Dashboard Logic

**Lines:** ~130 | **Purpose:** DOM updates, initial data loading, occupancy ring animation

---

### 4.2.10 `frontend/js/websocket.js` — WebSocket Client

**Lines:** ~45 | **Purpose:** Connect to Flask-SocketIO, handle parking_update events

---

### 4.2.11 `frontend/js/charts.js` — Chart.js Charts

**Lines:** ~130 | **Purpose:** Timeline line chart + daily bar chart + live data injection

---

### 4.2.12 `arduino/smart_parking/smart_parking.ino` — Firmware

**Lines:** ~195 | **Purpose:** Complete IoT firmware for Arduino Uno

**Modules:** sensor detection (M1/M2), barrier control (M4), LCD display, serial JSON output (M5)

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
