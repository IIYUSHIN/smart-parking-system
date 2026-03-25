# AI-Enabled Smart Parking Management System

> An AI-powered parking occupancy monitoring and prediction system using Arduino Uno, Python Flask, SQLite, and a real-time web dashboard.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                        │
│                                                               │
│  ┌─────────────┐    USB Serial     ┌─────────────────────┐  │
│  │  ARDUINO UNO │ ──────────────►  │   PYTHON BACKEND    │  │
│  │  - 2x IR     │   JSON @ 9600    │   - Serial Bridge   │  │
│  │  - Servo     │                  │   - Flask Server     │  │
│  │  - LCD 16x2  │                  │   - SQLite DB        │  │
│  └─────────────┘                   │   - ML Engine        │  │
│                                    └─────────┬────────────┘  │
│                                              │ WebSocket      │
│                                    ┌─────────▼────────────┐  │
│                                    │   WEB DASHBOARD       │  │
│                                    │   - Live Occupancy    │  │
│                                    │   - AI Predictions    │  │
│                                    │   - Chart.js Charts   │  │
│                                    │   - PWA Support       │  │
│                                    └──────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Hardware | Arduino Uno, 2x IR Sensors, Servo Motor, 16x2 I2C LCD |
| Communication | USB Serial (9600 baud, JSON) |
| Backend | Python 3.11+, Flask, Flask-SocketIO |
| Database | SQLite 3 (WAL mode) |
| AI/ML | scikit-learn (LinearRegression), Moving Average |
| Frontend | HTML5, CSS3, JavaScript (vanilla) |
| Charts | Chart.js 4.x |
| Mobile | PWA (Progressive Web App) |

## Quick Start

### 1. Install Dependencies
```powershell
cd smart_parking
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate Training Data
```powershell
python -m backend.app --generate-data
```

### 3. Run ML Predictions
```powershell
python -m backend.app --run-ml
```

### 4. Start Server (Simulation Mode — No Arduino)
```powershell
python -m backend.app --simulate
```
Open browser: **http://localhost:5000**

### 5. Start Server (Live Arduino Mode)
```powershell
python -m backend.app --serial COM3
```

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/status` | Current parking status (count, availability, utilization) |
| GET | `/api/history?hours=24` | Recent occupancy events |
| GET | `/api/predictions` | Latest AI prediction |
| GET | `/api/analytics/daily?days=7` | Daily utilization summaries |
| GET | `/api/analytics/hourly` | Hourly average occupancy |
| POST | `/api/ml/run` | Trigger ML prediction manually |

### WebSocket Event
- **Event name:** `parking_update`
- **Data:** `{ parking_id, current_count, available_slots, utilization_percent, is_full, last_event, last_updated }`

## ML Models

### 1. Moving Average Predictor
- **Formula:** (O(t) + O(t-1) + O(t-2)) / 3
- **Window:** 3 data points
- **Purpose:** Short-term smoothing

### 2. Linear Regression (Time → Occupancy)
- **Input:** Hour of day (0-23)
- **Output:** Predicted average occupancy
- **Training data:** Hourly averages from 14-day synthetic dataset
- **MAE:** 0.918 (on training data)

### 3. Peak Detection
- Identifies highest-occupancy hour windows
- Reports busiest and quietest periods

## Project Structure

```
smart_parking/
├── arduino/smart_parking/
│   └── smart_parking.ino          # Arduino firmware
├── backend/
│   ├── __init__.py
│   ├── app.py                     # Flask + WebSocket server
│   ├── config.py                  # Global configuration
│   ├── database.py                # SQLite (5 tables)
│   ├── data_generator.py          # Synthetic data (14 days)
│   ├── ml_engine.py               # ML prediction pipeline
│   └── serial_bridge.py           # USB serial + simulation
├── frontend/
│   ├── index.html                 # Dashboard (7 cards)
│   ├── manifest.json              # PWA config
│   ├── css/styles.css             # Dark theme design system
│   └── js/
│       ├── app.js                 # Dashboard logic
│       ├── charts.js              # Chart.js (timeline + daily)
│       └── websocket.js           # Real-time client
├── tests/
│   ├── test_api.py                # 6 API tests
│   ├── test_database.py           # 11 database tests
│   ├── test_ml_engine.py          # 8 ML tests
│   └── test_serial_parser.py      # 8 parse tests
├── data/                          # SQLite database
├── models/                        # Saved ML models
├── requirements.txt
└── README.md
```

## Testing

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

**33 tests | 33 passed | 0 failed**

| Suite | Tests | Status |
|---|---|---|
| API Endpoints | 6 | All passed |
| Database Layer | 11 | All passed |
| ML Engine | 8 | All passed |
| Serial Parser | 8 | All passed |

## Arduino Wiring

| Component | Pin | Notes |
|---|---|---|
| Entry IR Sensor | Digital 2 | LOW = beam broken |
| Exit IR Sensor | Digital 3 | LOW = beam broken |
| Servo Motor | PWM 9 | 0° = closed, 90° = open |
| LCD (SDA) | A4 | I2C address 0x27 |
| LCD (SCL) | A5 | I2C |

## Serial Protocol

Each event is one JSON line at 9600 baud:
```json
{"e":"ENTRY","c":2,"m":4,"t":12345}
```

| Field | Type | Meaning |
|---|---|---|
| `e` | string | Event: ENTRY, EXIT, BOOT |
| `c` | int | Current count after event |
| `m` | int | Max capacity |
| `t` | ulong | Arduino millis() timestamp |

## Design Decisions

- **No cloud/WiFi** — All processing is local via USB serial
- **AI is advisory only** — ML predicts; it never controls the barrier
- **Barrier is rule-based** — Arduino firmware controls servo deterministically
- **Simulation mode** — Full system testing without physical hardware

---

**Author:** Piyush Kumar
**Version:** 1.0 Prototype
**Academic Project:** AI-Enabled Smart Parking Management System
