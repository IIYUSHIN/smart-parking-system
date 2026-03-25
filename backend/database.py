"""
Smart Parking System — Database Layer
SQLite database with 5 tables: parking_config, parking_status,
occupancy_log, predictions, daily_summary.
"""

import sqlite3
import os
from datetime import datetime, timezone, timedelta


# ═══════════════════════════════════════════════════════════
# CONNECTION
# ═══════════════════════════════════════════════════════════

def get_connection(db_path: str) -> sqlite3.Connection:
    """Returns a connection with WAL mode and row_factory set."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    """Returns current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


# ═══════════════════════════════════════════════════════════
# SCHEMA INITIALIZATION
# ═══════════════════════════════════════════════════════════

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS parking_config (
    parking_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    max_capacity INTEGER NOT NULL CHECK(max_capacity > 0)
);

CREATE TABLE IF NOT EXISTS parking_status (
    parking_id          TEXT PRIMARY KEY,
    current_count       INTEGER NOT NULL DEFAULT 0,
    available_slots     INTEGER NOT NULL,
    utilization_percent REAL NOT NULL DEFAULT 0.0,
    last_updated        TEXT NOT NULL,
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
);

CREATE TABLE IF NOT EXISTS occupancy_log (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL CHECK(event_type IN ('ENTRY', 'EXIT')),
    event_time      TEXT NOT NULL,
    occupancy_after INTEGER NOT NULL CHECK(occupancy_after >= 0),
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id      TEXT NOT NULL,
    predicted_at    TEXT NOT NULL,
    predicted_count INTEGER NOT NULL,
    peak_hour_start TEXT,
    peak_hour_end   TEXT,
    utilization_avg REAL,
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
);

CREATE TABLE IF NOT EXISTS daily_summary (
    date            TEXT NOT NULL,
    parking_id      TEXT NOT NULL,
    total_entries   INTEGER NOT NULL DEFAULT 0,
    total_exits     INTEGER NOT NULL DEFAULT 0,
    peak_count      INTEGER NOT NULL DEFAULT 0,
    avg_utilization REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (date, parking_id),
    FOREIGN KEY (parking_id) REFERENCES parking_config(parking_id)
);
"""


def init_db(db_path: str, parking_id: str = "MODEL_01",
            parking_name: str = "Smart Parking Prototype",
            max_capacity: int = 4) -> None:
    """Creates all 5 tables and inserts default config if not present."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)

        # Insert default parking config if not exists
        existing = conn.execute(
            "SELECT 1 FROM parking_config WHERE parking_id = ?",
            (parking_id,)
        ).fetchone()

        if not existing:
            conn.execute(
                "INSERT INTO parking_config (parking_id, name, max_capacity) "
                "VALUES (?, ?, ?)",
                (parking_id, parking_name, max_capacity)
            )
            # Initialize status row
            conn.execute(
                "INSERT INTO parking_status "
                "(parking_id, current_count, available_slots, "
                "utilization_percent, last_updated) "
                "VALUES (?, 0, ?, 0.0, ?)",
                (parking_id, max_capacity, _now_iso())
            )
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# PARKING STATUS
# ═══════════════════════════════════════════════════════════

def update_status(db_path: str, parking_id: str,
                  current_count: int, max_capacity: int) -> dict:
    """Upserts parking_status row with derived fields.
    Returns the status dict."""
    available = max_capacity - current_count
    utilization = (current_count / max_capacity) * 100 if max_capacity > 0 else 0.0
    now = _now_iso()

    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO parking_status "
            "(parking_id, current_count, available_slots, "
            "utilization_percent, last_updated) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(parking_id) DO UPDATE SET "
            "current_count = excluded.current_count, "
            "available_slots = excluded.available_slots, "
            "utilization_percent = excluded.utilization_percent, "
            "last_updated = excluded.last_updated",
            (parking_id, current_count, available, utilization, now)
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "parking_id": parking_id,
        "current_count": current_count,
        "available_slots": available,
        "utilization_percent": round(utilization, 1),
        "last_updated": now,
        "max_capacity": max_capacity,
        "is_full": current_count >= max_capacity
    }


def get_status(db_path: str, parking_id: str) -> dict | None:
    """Returns current parking_status row as dict."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT ps.*, pc.max_capacity, pc.name "
            "FROM parking_status ps "
            "JOIN parking_config pc ON ps.parking_id = pc.parking_id "
            "WHERE ps.parking_id = ?",
            (parking_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["is_full"] = d["current_count"] >= d["max_capacity"]
        return d
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# EVENT LOGGING
# ═══════════════════════════════════════════════════════════

def log_event(db_path: str, parking_id: str,
              event_type: str, occupancy_after: int,
              event_time: str | None = None) -> int:
    """Inserts into occupancy_log. Returns event_id."""
    if event_type not in ("ENTRY", "EXIT"):
        raise ValueError(f"Invalid event_type: {event_type}")
    if event_time is None:
        event_time = _now_iso()

    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO occupancy_log "
            "(parking_id, event_type, event_time, occupancy_after) "
            "VALUES (?, ?, ?, ?)",
            (parking_id, event_type, event_time, occupancy_after)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_history(db_path: str, parking_id: str,
                hours: int = 24) -> list[dict]:
    """Returns occupancy_log events from last N hours, ordered newest first."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(
        timespec='seconds')

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT event_id, event_type, event_time, occupancy_after "
            "FROM occupancy_log "
            "WHERE parking_id = ? AND event_time >= ? "
            "ORDER BY event_time DESC",
            (parking_id, cutoff)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_events(db_path: str, parking_id: str) -> list[dict]:
    """Returns ALL occupancy_log events for a parking_id, ordered by time."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT event_id, event_type, event_time, occupancy_after "
            "FROM occupancy_log "
            "WHERE parking_id = ? "
            "ORDER BY event_time ASC",
            (parking_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# PREDICTIONS
# ═══════════════════════════════════════════════════════════

def save_prediction(db_path: str, parking_id: str,
                    predicted_count: int, peak_hour_start: str,
                    peak_hour_end: str, utilization_avg: float) -> int:
    """Inserts into predictions table. Returns prediction_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO predictions "
            "(parking_id, predicted_at, predicted_count, "
            "peak_hour_start, peak_hour_end, utilization_avg) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (parking_id, _now_iso(), predicted_count,
             peak_hour_start, peak_hour_end, round(utilization_avg, 1))
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_latest_prediction(db_path: str, parking_id: str) -> dict | None:
    """Returns most recent prediction row."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM predictions "
            "WHERE parking_id = ? "
            "ORDER BY predicted_at DESC LIMIT 1",
            (parking_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════

def aggregate_daily(db_path: str, parking_id: str, date: str,
                    max_capacity: int = 4) -> dict:
    """Computes and stores daily_summary for given date (YYYY-MM-DD).
    Returns the summary dict."""
    conn = get_connection(db_path)
    try:
        # Count entries and exits for the date
        entries = conn.execute(
            "SELECT COUNT(*) as cnt FROM occupancy_log "
            "WHERE parking_id = ? AND event_type = 'ENTRY' "
            "AND event_time LIKE ?",
            (parking_id, f"{date}%")
        ).fetchone()["cnt"]

        exits = conn.execute(
            "SELECT COUNT(*) as cnt FROM occupancy_log "
            "WHERE parking_id = ? AND event_type = 'EXIT' "
            "AND event_time LIKE ?",
            (parking_id, f"{date}%")
        ).fetchone()["cnt"]

        # Peak count for the day
        peak_row = conn.execute(
            "SELECT MAX(occupancy_after) as peak FROM occupancy_log "
            "WHERE parking_id = ? AND event_time LIKE ?",
            (parking_id, f"{date}%")
        ).fetchone()
        peak_count = peak_row["peak"] if peak_row["peak"] is not None else 0

        # Average utilization
        avg_row = conn.execute(
            "SELECT AVG(occupancy_after) as avg_occ FROM occupancy_log "
            "WHERE parking_id = ? AND event_time LIKE ?",
            (parking_id, f"{date}%")
        ).fetchone()
        avg_occ = avg_row["avg_occ"] if avg_row["avg_occ"] is not None else 0
        avg_util = (avg_occ / max_capacity) * 100

        # Upsert
        conn.execute(
            "INSERT INTO daily_summary "
            "(date, parking_id, total_entries, total_exits, "
            "peak_count, avg_utilization) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date, parking_id) DO UPDATE SET "
            "total_entries = excluded.total_entries, "
            "total_exits = excluded.total_exits, "
            "peak_count = excluded.peak_count, "
            "avg_utilization = excluded.avg_utilization",
            (date, parking_id, entries, exits, peak_count,
             round(avg_util, 1))
        )
        conn.commit()

        summary = {
            "date": date,
            "parking_id": parking_id,
            "total_entries": entries,
            "total_exits": exits,
            "peak_count": peak_count,
            "avg_utilization": round(avg_util, 1)
        }
        return summary
    finally:
        conn.close()


def get_daily_summaries(db_path: str, parking_id: str,
                        days: int = 7) -> list[dict]:
    """Returns daily_summary rows for last N days, ordered by date DESC."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM daily_summary "
            "WHERE parking_id = ? "
            "ORDER BY date DESC LIMIT ?",
            (parking_id, days)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_hourly_averages(db_path: str, parking_id: str) -> list[dict]:
    """Returns average occupancy per hour (0-23) across all data.
    Used by ML for peak detection."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT CAST(SUBSTR(event_time, 12, 2) AS INTEGER) as hour, "
            "AVG(occupancy_after) as avg_occupancy, "
            "COUNT(*) as event_count "
            "FROM occupancy_log "
            "WHERE parking_id = ? "
            "GROUP BY hour "
            "ORDER BY hour",
            (parking_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from backend.config import DB_PATH, PARKING_ID, PARKING_NAME, MAX_CAPACITY

    print("Initializing database...")
    init_db(DB_PATH, PARKING_ID, PARKING_NAME, MAX_CAPACITY)

    print("Testing status...")
    s = update_status(DB_PATH, PARKING_ID, 2, MAX_CAPACITY)
    print(f"  Status: {s}")

    print("Testing log_event...")
    eid = log_event(DB_PATH, PARKING_ID, "ENTRY", 3)
    print(f"  Event ID: {eid}")

    print("Testing get_status...")
    gs = get_status(DB_PATH, PARKING_ID)
    print(f"  Current: {gs}")

    print("Testing get_history...")
    h = get_history(DB_PATH, PARKING_ID, hours=1)
    print(f"  Events: {len(h)}")

    print("\n[OK] Database layer verified successfully")
