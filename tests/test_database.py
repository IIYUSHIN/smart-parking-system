"""
Unit Tests — Database Layer
Tests all database.py functions using a temporary in-memory database.
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    init_db, get_connection, update_status, get_status,
    log_event, get_history, get_all_events,
    save_prediction, get_latest_prediction,
    aggregate_daily, get_daily_summaries, get_hourly_averages
)

PARKING_ID = "TEST_01"
MAX_CAP = 4


@pytest.fixture
def db_path(tmp_path):
    """Creates a fresh temp database for each test."""
    path = str(tmp_path / "test.db")
    init_db(path, PARKING_ID, "Test Parking", MAX_CAP)
    return path


# ── INIT ──

def test_init_creates_all_tables(db_path):
    conn = get_connection(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    table_names = sorted([t['name'] for t in tables])
    assert "daily_summary" in table_names
    assert "occupancy_log" in table_names
    assert "parking_config" in table_names
    assert "parking_status" in table_names
    assert "predictions" in table_names


def test_init_inserts_default_config(db_path):
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM parking_config WHERE parking_id = ?", (PARKING_ID,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row['max_capacity'] == MAX_CAP


# ── STATUS ──

def test_update_status_calculates_derived_fields(db_path):
    result = update_status(db_path, PARKING_ID, 3, MAX_CAP)
    assert result['current_count'] == 3
    assert result['available_slots'] == 1
    assert result['utilization_percent'] == 75.0
    assert result['is_full'] is False


def test_update_status_full(db_path):
    result = update_status(db_path, PARKING_ID, 4, MAX_CAP)
    assert result['is_full'] is True
    assert result['available_slots'] == 0
    assert result['utilization_percent'] == 100.0


def test_get_status_returns_data(db_path):
    update_status(db_path, PARKING_ID, 2, MAX_CAP)
    status = get_status(db_path, PARKING_ID)
    assert status is not None
    assert status['current_count'] == 2
    assert 'is_full' in status


def test_get_status_nonexistent(db_path):
    result = get_status(db_path, "NONEXISTENT")
    assert result is None


# ── EVENT LOGGING ──

def test_log_event_stores_correctly(db_path):
    eid = log_event(db_path, PARKING_ID, "ENTRY", 1)
    assert eid > 0
    events = get_all_events(db_path, PARKING_ID)
    assert len(events) == 1
    assert events[0]['event_type'] == "ENTRY"
    assert events[0]['occupancy_after'] == 1


def test_log_event_rejects_invalid_type(db_path):
    with pytest.raises(ValueError):
        log_event(db_path, PARKING_ID, "INVALID", 1)


def test_get_history_respects_hours(db_path):
    # Log an event now
    log_event(db_path, PARKING_ID, "ENTRY", 1)
    # Should appear in 1-hour window
    events = get_history(db_path, PARKING_ID, hours=1)
    assert len(events) >= 1


# ── PREDICTIONS ──

def test_save_and_get_prediction(db_path):
    pid = save_prediction(db_path, PARKING_ID, 3, "08:00", "10:00", 65.5)
    assert pid > 0
    pred = get_latest_prediction(db_path, PARKING_ID)
    assert pred is not None
    assert pred['predicted_count'] == 3
    assert pred['peak_hour_start'] == "08:00"


def test_get_prediction_empty(db_path):
    pred = get_latest_prediction(db_path, PARKING_ID)
    assert pred is None
