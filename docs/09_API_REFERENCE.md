# Document 09 — API Reference

---

## 9.1 API Overview

The Smart Parking System exposes a RESTful HTTP API through Flask running on port 5000. All endpoints return JSON responses. The API serves two purposes:

1. **Frontend data source** — The dashboard calls these endpoints on initial load
2. **External integration** — Any HTTP client can query the parking status

**Base URL:** `http://localhost:5000`
**Content-Type:** `application/json` (all responses)
**Authentication:** None (prototype-level)

## 9.2 Response Format

All API responses follow a consistent envelope:

```json
{
    "status": "ok",        // "ok" or "error"
    "data": { ... },       // Response payload (object or array)
    "error": "..."         // Present only on error
}
```

## 9.3 Endpoint Reference

---

### GET `/api/status`

**Purpose:** Returns the current live parking status — the most frequently called endpoint.

**Parameters:** None

**Response:**
```json
{
    "status": "ok",
    "data": {
        "parking_id": "MODEL_01",
        "name": "Smart Parking Prototype",
        "current_count": 2,
        "max_capacity": 4,
        "available_slots": 2,
        "utilization_percent": 50.0,
        "is_full": false,
        "last_event": "EXIT",
        "last_updated": "2026-03-25T18:20:57+00:00"
    }
}
```

**Response Fields:**

| Field | Type | Description |
|---|---|---|
| `parking_id` | string | Zone identifier |
| `name` | string | Human-readable zone name |
| `current_count` | integer | Vehicles currently inside (0 to max_capacity) |
| `max_capacity` | integer | Maximum parking slots (4) |
| `available_slots` | integer | Remaining free slots (max_capacity - current_count) |
| `utilization_percent` | float | (current_count / max_capacity) × 100 |
| `is_full` | boolean | `true` when current_count >= max_capacity |
| `last_event` | string | Most recent event: "ENTRY" or "EXIT" |
| `last_updated` | string | ISO 8601 timestamp of last status change |

---

### GET `/api/history`

**Purpose:** Returns recent occupancy events for the timeline chart.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `hours` | integer | 24 | How many hours of history to return |

**Example:** `GET /api/history?hours=12`

**Response:**
```json
{
    "status": "ok",
    "data": [
        {
            "event_id": 582,
            "parking_id": "MODEL_01",
            "event_type": "ENTRY",
            "occupancy_after": 2,
            "event_time": "2026-03-25T18:20:57+00:00"
        },
        {
            "event_id": 581,
            "parking_id": "MODEL_01",
            "event_type": "EXIT",
            "occupancy_after": 1,
            "event_time": "2026-03-25T18:18:30+00:00"
        }
    ]
}
```

**Notes:** Events are returned in reverse chronological order (newest first). The frontend reverses them for the chart.

---

### GET `/api/predictions`

**Purpose:** Returns the latest AI prediction and analytics.

**Parameters:** None

**Response:**
```json
{
    "status": "ok",
    "data": {
        "prediction_id": 1,
        "parking_id": "MODEL_01",
        "predicted_count": 2,
        "peak_hour_start": "06:00",
        "peak_hour_end": "24:00",
        "utilization_avg": 51.3,
        "created_at": "2026-03-25T18:16:00+00:00"
    }
}
```

**Response Fields:**

| Field | Type | Description |
|---|---|---|
| `predicted_count` | integer | ML-predicted occupancy for the next hour (0-4) |
| `peak_hour_start` | string | Start of highest-traffic hour window |
| `peak_hour_end` | string | End of highest-traffic hour window |
| `utilization_avg` | float | Overall average utilization % across all data |
| `created_at` | string | When this prediction was generated |

---

### GET `/api/analytics/daily`

**Purpose:** Returns daily utilization summaries for the bar chart.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | integer | 7 | Number of days of summaries to return |

**Example:** `GET /api/analytics/daily?days=14`

**Response:**
```json
{
    "status": "ok",
    "data": [
        {
            "date": "2026-03-23",
            "total_entries": 25,
            "total_exits": 24,
            "peak_occupancy": 4,
            "avg_utilization": 52.3
        },
        {
            "date": "2026-03-22",
            "total_entries": 18,
            "total_exits": 18,
            "peak_occupancy": 3,
            "avg_utilization": 38.7
        }
    ]
}
```

---

### GET `/api/analytics/hourly`

**Purpose:** Returns average occupancy per hour of day (0-23).

**Parameters:** None

**Response:**
```json
{
    "status": "ok",
    "data": [
        { "hour": 0, "avg_occupancy": 0.8 },
        { "hour": 1, "avg_occupancy": 0.5 },
        { "hour": 8, "avg_occupancy": 3.2 },
        { "hour": 12, "avg_occupancy": 3.8 },
        { "hour": 23, "avg_occupancy": 1.1 }
    ]
}
```

---

### POST `/api/ml/run`

**Purpose:** Manually trigger a full ML prediction pipeline run.

**Body:** None required

**Response:**
```json
{
    "status": "ok",
    "data": {
        "predicted_count": 2,
        "peak_hour_start": "06:00",
        "peak_hour_end": "24:00",
        "utilization_avg": 51.3,
        "mae": 0.918
    }
}
```

## 9.4 Static File Serving

Flask automatically serves frontend files from the `frontend/` directory:

| URL Pattern | Served From | Example |
|---|---|---|
| `/` | `frontend/index.html` | Dashboard page |
| `/css/styles.css` | `frontend/css/styles.css` | Design system |
| `/js/app.js` | `frontend/js/app.js` | Dashboard logic |
| `/js/websocket.js` | `frontend/js/websocket.js` | WebSocket client |
| `/js/charts.js` | `frontend/js/charts.js` | Chart.js charts |
| `/manifest.json` | `frontend/manifest.json` | PWA config |

## 9.5 WebSocket API

### Connection
- **URL:** Same as HTTP origin (e.g., `http://localhost:5000`)
- **Library:** Socket.IO 4.x (both server and client)
- **Transport:** WebSocket with polling fallback

### Server Events (Server → Client)

| Event Name | Payload | When Emitted |
|---|---|---|
| `parking_update` | `{ parking_id, current_count, max_capacity, available_slots, utilization_percent, is_full, last_event, last_updated }` | Every time an entry/exit event is processed by the serial bridge |

### Client Events (Client → Server)

| Event Name | Payload | Purpose |
|---|---|---|
| `connect` | N/A (automatic) | Client connected — logged by server |
| `disconnect` | N/A (automatic) | Client disconnected — logged by server |

### WebSocket Payload Example

```json
{
    "parking_id": "MODEL_01",
    "current_count": 3,
    "max_capacity": 4,
    "available_slots": 1,
    "utilization_percent": 75.0,
    "is_full": false,
    "last_event": "ENTRY",
    "last_updated": "2026-03-25T23:50:37+00:00"
}
```

## 9.6 CLI Interface

The server supports command-line arguments for different run modes:

| Argument | Type | Default | Purpose |
|---|---|---|---|
| `--simulate` | flag | off | Run with simulated events (no Arduino needed) |
| `--serial PORT` | string | COM3 | Serial port for real Arduino |
| `--port N` | integer | 5000 | HTTP server port |
| `--generate-data` | flag | off | Generate 14-day synthetic dataset, then exit |
| `--run-ml` | flag | off | Run ML prediction pipeline, then exit |

### Usage Examples

```powershell
# Simulation mode
python -m backend.app --simulate

# Real Arduino on COM3
python -m backend.app --serial COM3

# Custom port
python -m backend.app --simulate --port 8080

# Generate training data only
python -m backend.app --generate-data

# Run ML prediction only
python -m backend.app --run-ml
```

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
