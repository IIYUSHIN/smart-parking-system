# Document 05 — Database Design

---

## 5.1 Database Engine

| Property | Value |
|---|---|
| **Engine** | SQLite 3 |
| **Driver** | Python sqlite3 (standard library) |
| **File Location** | `data/smart_parking.db` |
| **Journal Mode** | WAL (Write-Ahead Logging) |
| **Row Factory** | `sqlite3.Row` (dict-like access) |
| **Concurrency** | WAL enables concurrent reads while writing |

## 5.2 Why SQLite?

1. **Zero setup** — No server process, no installation, no credentials
2. **File-based** — Single `.db` file, easy to backup/restore
3. **Built into Python** — Part of the standard library, no pip install
4. **WAL mode** — Concurrent reads don't block writes (critical for serial bridge + API)
5. **ACID compliant** — Full transaction support, crash recovery
6. **Single server** — Perfect for a system that runs entirely on one laptop

## 5.3 Schema Design

### Table 1: `parking_config`

**Purpose:** Stores the parking zone configuration. One row per zone. Currently 1 zone.

```sql
CREATE TABLE IF NOT EXISTS parking_config (
    parking_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    max_capacity INTEGER NOT NULL,
    created_at   TEXT DEFAULT (datetime('now'))
)
```

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `parking_id` | TEXT | PRIMARY KEY | Unique zone identifier (e.g., "MODEL_01") |
| `name` | TEXT | NOT NULL | Human-readable name (e.g., "Smart Parking Prototype") |
| `max_capacity` | INTEGER | NOT NULL | Maximum vehicle slots (4 for our model) |
| `created_at` | TEXT | DEFAULT now | Zone creation timestamp |

**Default Row:** `("MODEL_01", "Smart Parking Prototype", 4, <auto>)`

---

### Table 2: `parking_status`

**Purpose:** Live status — the current state of the parking zone. Updated on every entry/exit event.

```sql
CREATE TABLE IF NOT EXISTS parking_status (
    parking_id         TEXT PRIMARY KEY,
    current_count      INTEGER NOT NULL DEFAULT 0,
    max_capacity       INTEGER NOT NULL DEFAULT 4,
    available_slots    INTEGER NOT NULL DEFAULT 4,
    utilization_percent REAL NOT NULL DEFAULT 0.0,
    is_full            INTEGER NOT NULL DEFAULT 0,
    last_event         TEXT,
    last_updated       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
)
```

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `parking_id` | TEXT | PRIMARY KEY, FK | Links to parking_config |
| `current_count` | INTEGER | NOT NULL, DEFAULT 0 | Vehicles currently inside |
| `max_capacity` | INTEGER | NOT NULL, DEFAULT 4 | Max slots (denormalized for fast access) |
| `available_slots` | INTEGER | NOT NULL, DEFAULT 4 | `max_capacity - current_count` (computed on write) |
| `utilization_percent` | REAL | NOT NULL, DEFAULT 0.0 | `(current_count / max_capacity) * 100` (computed) |
| `is_full` | INTEGER | NOT NULL, DEFAULT 0 | `1` if count >= capacity, `0` otherwise (computed) |
| `last_event` | TEXT | NULLABLE | Most recent event: "ENTRY" or "EXIT" |
| `last_updated` | TEXT | DEFAULT now | Timestamp of last status update |

**Derived Fields:** `available_slots`, `utilization_percent`, and `is_full` are computed by `update_status()` on every write to eliminate repeated calculations in the API layer.

---

### Table 3: `occupancy_log`

**Purpose:** Immutable event log — one row per entry or exit. This is the core data used for ML training.

```sql
CREATE TABLE IF NOT EXISTS occupancy_log (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL CHECK(event_type IN ('ENTRY', 'EXIT')),
    occupancy_after INTEGER NOT NULL,
    event_time      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
)
```

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `event_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique sequential event ID |
| `parking_id` | TEXT | NOT NULL, FK | Links to parking zone |
| `event_type` | TEXT | NOT NULL, CHECK constraint | Either "ENTRY" or "EXIT" — no other values accepted |
| `occupancy_after` | INTEGER | NOT NULL | Vehicle count AFTER this event (0 to max_capacity) |
| `event_time` | TEXT | NOT NULL, DEFAULT now | ISO 8601 timestamp of event occurrence |

**CHECK constraint** on `event_type` ensures data integrity — the database itself rejects invalid event types.

**Index recommendation:** `CREATE INDEX idx_log_time ON occupancy_log(parking_id, event_time DESC)` — for time-range queries. Currently queries use sequential scan which is adequate for prototype scale.

---

### Table 4: `predictions`

**Purpose:** Stores ML-generated predictions. One row per prediction run.

```sql
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id      TEXT NOT NULL,
    predicted_count INTEGER NOT NULL,
    peak_hour_start TEXT,
    peak_hour_end   TEXT,
    utilization_avg REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
)
```

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `prediction_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique prediction ID |
| `parking_id` | TEXT | NOT NULL, FK | Links to parking zone |
| `predicted_count` | INTEGER | NOT NULL | ML-predicted occupancy for next hour |
| `peak_hour_start` | TEXT | NULLABLE | Start of highest-traffic window (e.g., "08:00") |
| `peak_hour_end` | TEXT | NULLABLE | End of highest-traffic window (e.g., "10:00") |
| `utilization_avg` | REAL | NULLABLE | Overall average utilization percentage |
| `created_at` | TEXT | DEFAULT now | When this prediction was generated |

---

### Table 5: `daily_summary`

**Purpose:** Aggregated daily statistics for trend analysis.

```sql
CREATE TABLE IF NOT EXISTS daily_summary (
    summary_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id     TEXT NOT NULL,
    date           TEXT NOT NULL,
    total_entries  INTEGER NOT NULL DEFAULT 0,
    total_exits    INTEGER NOT NULL DEFAULT 0,
    peak_occupancy INTEGER NOT NULL DEFAULT 0,
    avg_utilization REAL NOT NULL DEFAULT 0.0,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
)
```

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `summary_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique summary ID |
| `parking_id` | TEXT | NOT NULL, FK | Links to parking zone |
| `date` | TEXT | NOT NULL | Date in YYYY-MM-DD format |
| `total_entries` | INTEGER | NOT NULL, DEFAULT 0 | Count of ENTRY events on this date |
| `total_exits` | INTEGER | NOT NULL, DEFAULT 0 | Count of EXIT events on this date |
| `peak_occupancy` | INTEGER | NOT NULL, DEFAULT 0 | Highest occupancy reached during the day |
| `avg_utilization` | REAL | NOT NULL, DEFAULT 0.0 | Average utilization % across the day |
| `created_at` | TEXT | DEFAULT now | When this summary was generated |

## 5.4 Entity Relationship Diagram

```
                    ┌─────────────────────┐
                    │   parking_config    │
                    │─────────────────────│
                    │ parking_id  (PK)    │
                    │ name                │
                    │ max_capacity        │
                    │ created_at          │
                    └─────────┬───────────┘
                              │
                    ┌─────────┤ 1:1
                    │         │
          ┌─────────▼─────┐   │   ┌─────────────────────┐
          │ parking_status │   │   │    occupancy_log     │
          │───────────────│   │   │─────────────────────│
          │ parking_id(PK)│   ├──►│ event_id (PK)       │
          │ current_count │   │   │ parking_id (FK)     │ 1:N
          │ max_capacity  │   │   │ event_type          │
          │ available_slots│  │   │ occupancy_after     │
          │ utilization_% │   │   │ event_time          │
          │ is_full       │   │   └─────────────────────┘
          │ last_event    │   │
          │ last_updated  │   │   ┌─────────────────────┐
          └───────────────┘   │   │     predictions      │
                              │   │─────────────────────│
                              ├──►│ prediction_id (PK)  │
                              │   │ parking_id (FK)     │ 1:N
                              │   │ predicted_count     │
                              │   │ peak_hour_start     │
                              │   │ peak_hour_end       │
                              │   │ utilization_avg     │
                              │   │ created_at          │
                              │   └─────────────────────┘
                              │
                              │   ┌─────────────────────┐
                              │   │   daily_summary      │
                              └──►│─────────────────────│
                                  │ summary_id (PK)     │
                                  │ parking_id (FK)     │ 1:N
                                  │ date                │
                                  │ total_entries       │
                                  │ total_exits         │
                                  │ peak_occupancy      │
                                  │ avg_utilization     │
                                  │ created_at          │
                                  └─────────────────────┘
```

**Relationships:**
- `parking_config` → `parking_status`: 1:1 (one status per zone)
- `parking_config` → `occupancy_log`: 1:N (many events per zone)
- `parking_config` → `predictions`: 1:N (many prediction runs per zone)
- `parking_config` → `daily_summary`: 1:N (one summary per day per zone)

## 5.5 Query Patterns

| Operation | SQL Pattern | Frequency |
|---|---|---|
| Update status | `INSERT OR REPLACE INTO parking_status ...` | Every event (~5-15s in simulation) |
| Log event | `INSERT INTO occupancy_log ...` | Every event |
| Get status | `SELECT * FROM parking_status WHERE parking_id = ?` | Every API request to /api/status |
| Get history | `SELECT * FROM occupancy_log WHERE event_time >= ? ORDER BY event_time DESC` | Dashboard load |
| Get prediction | `SELECT * FROM predictions ORDER BY created_at DESC LIMIT 1` | Dashboard load + every 5 min |
| Daily summary | `SELECT date, COUNT(*) ... GROUP BY date` | /api/analytics/daily |
| Hourly average | `SELECT strftime('%H', event_time) as hour, AVG(occupancy_after) ... GROUP BY hour` | /api/analytics/hourly |

## 5.6 Data Volume Estimates

| Scenario | Events/Day | Events/Month | DB Size |
|---|---|---|---|
| Simulation mode | ~3,000+ | ~90,000 | ~10 MB |
| Real Arduino (4-slot model) | 20-50 | 600-1,500 | < 1 MB |
| Synthetic training data | 41/day avg | 581 (14 days) | < 1 MB |

SQLite can comfortably handle millions of rows. Data volume is never a concern for this system.

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
