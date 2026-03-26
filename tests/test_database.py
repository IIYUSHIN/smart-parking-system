"""
Unit Tests — Database Layer v2.0
Tests 14-table schema, location/zone seeding, status, events,
user auth, sessions, bookings, payments, predictions, analytics.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    init_db, get_connection, update_status, get_status, get_all_statuses,
    log_event, batch_log_events, get_history, get_all_events,
    save_prediction, get_latest_prediction,
    aggregate_daily, get_daily_summaries, get_hourly_averages,
    get_all_locations, get_location, get_zones_for_location,
    create_user, authenticate_user, get_user_by_id,
    create_session, validate_session, invalidate_session,
    create_booking, get_user_bookings, cancel_booking, complete_booking,
    create_payment, process_payment, get_user_payments,
    calculate_parking_fee, save_recommendation, get_latest_recommendation,
    save_chat_message
)

# ── MINIMAL LOCATION CONFIG FOR TESTS ──
TEST_LOCATIONS = [
    {
        "location_id": "LOC_TEST",
        "name": "Test Mall",
        "address": "123 Test St",
        "city": "Test City",
        "latitude": 30.0,
        "longitude": 76.0,
        "location_type": "MALL",
        "operating_hours": "00:00-23:59",
        "pricing": {"rate_per_hour": 50, "rate_per_day": 300, "currency": "INR"},
        "zones": [
            {"zone_id": "Z_TEST_A", "zone_name": "Ground Floor", "max_capacity": 100},
            {"zone_id": "Z_TEST_B", "zone_name": "Basement P1", "max_capacity": 50},
        ]
    }
]


@pytest.fixture
def db_path(tmp_path):
    """Creates a fresh database with test locations seeded."""
    path = str(tmp_path / "test_v2.db")
    init_db(path, TEST_LOCATIONS)
    return path


# ═══════════════════════════════════════════════
# SCHEMA TESTS
# ═══════════════════════════════════════════════

def test_init_creates_14_tables(db_path):
    conn = get_connection(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    names = sorted([t['name'] for t in tables])
    expected = [
        'ai_recommendations', 'bookings', 'chatbot_history', 'daily_summary',
        'occupancy_log', 'parking_config', 'parking_locations', 'parking_status',
        'parking_zones', 'payments', 'predictions', 'pricing_rules',
        'sessions', 'users'
    ]
    for table in expected:
        assert table in names, f"Missing table: {table}"


def test_init_seeds_location(db_path):
    locations = get_all_locations(db_path)
    assert len(locations) == 1
    assert locations[0]['name'] == "Test Mall"
    assert locations[0]['location_type'] == "MALL"


def test_init_seeds_zones(db_path):
    zones = get_zones_for_location(db_path, "LOC_TEST")
    assert len(zones) == 2
    zone_ids = {z['zone_id'] for z in zones}
    assert zone_ids == {"Z_TEST_A", "Z_TEST_B"}


def test_init_seeds_pricing(db_path):
    loc = get_location(db_path, "LOC_TEST")
    assert loc['rate_per_hour'] == 50
    assert loc['rate_per_day'] == 300


def test_init_idempotent(db_path):
    """Calling init_db twice should not duplicate data."""
    init_db(db_path, TEST_LOCATIONS)
    locations = get_all_locations(db_path)
    assert len(locations) == 1


# ═══════════════════════════════════════════════
# STATUS TESTS
# ═══════════════════════════════════════════════

def test_update_status_derived_fields(db_path):
    result = update_status(db_path, "Z_TEST_A", 75, 100)
    assert result['current_count'] == 75
    assert result['available_slots'] == 25
    assert result['utilization_percent'] == 75.0
    assert result['is_full'] is False


def test_update_status_full(db_path):
    result = update_status(db_path, "Z_TEST_A", 100, 100)
    assert result['is_full'] is True
    assert result['available_slots'] == 0
    assert result['utilization_percent'] == 100.0


def test_get_status_returns_data(db_path):
    update_status(db_path, "Z_TEST_A", 30, 100)
    status = get_status(db_path, "Z_TEST_A")
    assert status is not None
    assert status['current_count'] == 30
    assert status['zone_name'] == "Ground Floor"


def test_get_status_nonexistent(db_path):
    result = get_status(db_path, "NONEXISTENT")
    assert result is None


def test_get_all_statuses(db_path):
    statuses = get_all_statuses(db_path)
    assert len(statuses) == 2
    assert all('zone_name' in s for s in statuses)


# ═══════════════════════════════════════════════
# LOCATION QUERIES
# ═══════════════════════════════════════════════

def test_get_location_with_zones(db_path):
    loc = get_location(db_path, "LOC_TEST")
    assert loc is not None
    assert loc['name'] == "Test Mall"
    assert loc['total_capacity'] == 150  # 100 + 50
    assert len(loc['zones']) == 2


def test_get_location_aggregates_occupancy(db_path):
    update_status(db_path, "Z_TEST_A", 60, 100)
    update_status(db_path, "Z_TEST_B", 20, 50)
    loc = get_location(db_path, "LOC_TEST")
    assert loc['total_occupied'] == 80
    assert loc['total_available'] == 70


def test_get_location_nonexistent(db_path):
    loc = get_location(db_path, "FAKE_LOC")
    assert loc is None


# ═══════════════════════════════════════════════
# EVENT LOGGING
# ═══════════════════════════════════════════════

def test_log_event_stores_correctly(db_path):
    eid = log_event(db_path, "Z_TEST_A", "ENTRY", 1)
    assert eid > 0
    events = get_all_events(db_path, "Z_TEST_A")
    assert len(events) == 1
    assert events[0]['event_type'] == "ENTRY"
    assert events[0]['occupancy_after'] == 1


def test_log_event_rejects_invalid_type(db_path):
    with pytest.raises(ValueError):
        log_event(db_path, "Z_TEST_A", "INVALID", 1)


def test_batch_log_events(db_path):
    events = [
        ("Z_TEST_A", "ENTRY", "2026-03-20T10:00:00+00:00", 1),
        ("Z_TEST_A", "ENTRY", "2026-03-20T10:05:00+00:00", 2),
        ("Z_TEST_A", "EXIT", "2026-03-20T10:10:00+00:00", 1),
    ]
    inserted = batch_log_events(db_path, events)
    assert inserted == 3
    all_events = get_all_events(db_path, "Z_TEST_A")
    assert len(all_events) == 3


def test_get_history_respects_hours(db_path):
    log_event(db_path, "Z_TEST_A", "ENTRY", 1)
    events = get_history(db_path, "Z_TEST_A", hours=1)
    assert len(events) >= 1


# ═══════════════════════════════════════════════
# PREDICTIONS
# ═══════════════════════════════════════════════

def test_save_and_get_prediction(db_path):
    pid = save_prediction(db_path, "Z_TEST_A", 60, "08:00", "10:00", 65.5,
                          model_type="random_forest", mae=2.1)
    assert pid > 0
    pred = get_latest_prediction(db_path, "Z_TEST_A")
    assert pred is not None
    assert pred['predicted_count'] == 60
    assert pred['model_type'] == "random_forest"


def test_get_prediction_empty(db_path):
    pred = get_latest_prediction(db_path, "Z_TEST_A")
    assert pred is None


# ═══════════════════════════════════════════════
# DAILY SUMMARY
# ═══════════════════════════════════════════════

def test_aggregate_daily(db_path):
    events = [
        ("Z_TEST_A", "ENTRY", "2026-03-20T09:00:00+00:00", 1),
        ("Z_TEST_A", "ENTRY", "2026-03-20T09:30:00+00:00", 2),
        ("Z_TEST_A", "EXIT", "2026-03-20T17:00:00+00:00", 1),
    ]
    batch_log_events(db_path, events)
    summary = aggregate_daily(db_path, "Z_TEST_A", "2026-03-20", 100)
    assert summary['total_entries'] == 2
    assert summary['total_exits'] == 1
    assert summary['peak_count'] == 2


# ═══════════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════════

def test_create_user(db_path):
    user = create_user(db_path, "Test User", "test@example.com", "password123")
    assert user['user_id'] > 0
    assert user['name'] == "Test User"
    assert user['email'] == "test@example.com"


def test_create_user_duplicate_email(db_path):
    create_user(db_path, "User 1", "same@example.com", "pass1")
    with pytest.raises(ValueError, match="already registered"):
        create_user(db_path, "User 2", "same@example.com", "pass2")


def test_authenticate_user_valid(db_path):
    create_user(db_path, "Auth Test", "auth@test.com", "secret")
    user = authenticate_user(db_path, "auth@test.com", "secret")
    assert user is not None
    assert user['name'] == "Auth Test"


def test_authenticate_user_wrong_password(db_path):
    create_user(db_path, "Auth Test", "auth2@test.com", "correct")
    user = authenticate_user(db_path, "auth2@test.com", "wrong")
    assert user is None


def test_get_user_by_id(db_path):
    created = create_user(db_path, "ID Test", "id@test.com", "pass")
    user = get_user_by_id(db_path, created['user_id'])
    assert user is not None
    assert user['name'] == "ID Test"


# ═══════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════

def test_create_and_validate_session(db_path):
    user = create_user(db_path, "Session Test", "session@test.com", "pass")
    token = create_session(db_path, user['user_id'])
    assert len(token) == 64  # hex(32) = 64 chars

    validated = validate_session(db_path, token)
    assert validated is not None
    assert validated['name'] == "Session Test"


def test_invalidate_session(db_path):
    user = create_user(db_path, "Logout", "logout@test.com", "pass")
    token = create_session(db_path, user['user_id'])
    assert invalidate_session(db_path, token) is True
    assert validate_session(db_path, token) is None


def test_invalid_token_returns_none(db_path):
    result = validate_session(db_path, "fake_token_123")
    assert result is None


# ═══════════════════════════════════════════════
# BOOKINGS
# ═══════════════════════════════════════════════

def test_create_booking(db_path):
    user = create_user(db_path, "Booker", "book@test.com", "pass")
    booking = create_booking(db_path, user['user_id'], "Z_TEST_A",
                             "2026-03-25T10:00:00+00:00", "CH01AB1234")
    assert booking['booking_id'] > 0
    assert booking['status'] == "CONFIRMED"
    assert booking['vehicle_plate'] == "CH01AB1234"


def test_get_user_bookings(db_path):
    user = create_user(db_path, "Booker", "book2@test.com", "pass")
    create_booking(db_path, user['user_id'], "Z_TEST_A",
                   "2026-03-25T10:00:00+00:00")
    create_booking(db_path, user['user_id'], "Z_TEST_B",
                   "2026-03-25T14:00:00+00:00")
    bookings = get_user_bookings(db_path, user['user_id'])
    assert len(bookings) == 2
    assert all('zone_name' in b for b in bookings)
    assert all('location_name' in b for b in bookings)


def test_cancel_booking(db_path):
    user = create_user(db_path, "Cancel", "cancel@test.com", "pass")
    booking = create_booking(db_path, user['user_id'], "Z_TEST_A",
                             "2026-03-25T10:00:00+00:00")
    success = cancel_booking(db_path, booking['booking_id'], user['user_id'])
    assert success is True

    bookings = get_user_bookings(db_path, user['user_id'])
    assert bookings[0]['status'] == "CANCELLED"


def test_complete_booking(db_path):
    user = create_user(db_path, "Complete", "complete@test.com", "pass")
    booking = create_booking(db_path, user['user_id'], "Z_TEST_A",
                             "2026-03-25T10:00:00+00:00")
    success = complete_booking(db_path, booking['booking_id'])
    assert success is True


# ═══════════════════════════════════════════════
# PAYMENTS
# ═══════════════════════════════════════════════

def test_create_payment(db_path):
    user = create_user(db_path, "Payer", "pay@test.com", "pass")
    booking = create_booking(db_path, user['user_id'], "Z_TEST_A",
                             "2026-03-25T10:00:00+00:00")
    payment = create_payment(db_path, booking['booking_id'],
                             user['user_id'], 150.0, "SIMULATED")
    assert payment['payment_id'] > 0
    assert payment['status'] == "PENDING"
    assert payment['amount'] == 150.0
    assert payment['transaction_id'].startswith("TXN_")


def test_process_payment(db_path):
    user = create_user(db_path, "Processor", "proc@test.com", "pass")
    booking = create_booking(db_path, user['user_id'], "Z_TEST_A",
                             "2026-03-25T10:00:00+00:00")
    payment = create_payment(db_path, booking['booking_id'],
                             user['user_id'], 200.0)
    success = process_payment(db_path, payment['payment_id'])
    assert success is True

    # Can't process again
    assert process_payment(db_path, payment['payment_id']) is False


def test_get_user_payments(db_path):
    user = create_user(db_path, "PayHist", "payhist@test.com", "pass")
    booking = create_booking(db_path, user['user_id'], "Z_TEST_A",
                             "2026-03-25T10:00:00+00:00")
    create_payment(db_path, booking['booking_id'], user['user_id'], 100.0)
    payments = get_user_payments(db_path, user['user_id'])
    assert len(payments) == 1
    assert 'zone_name' in payments[0]


# ═══════════════════════════════════════════════
# PRICING
# ═══════════════════════════════════════════════

def test_calculate_parking_fee(db_path):
    fee = calculate_parking_fee(db_path, "LOC_TEST", 3)
    assert fee['amount'] == 150  # 3 * 50
    assert fee['currency'] == "INR"


def test_calculate_parking_fee_daily_cap(db_path):
    fee = calculate_parking_fee(db_path, "LOC_TEST", 8)
    # 8 hours * 50 = 400, but daily rate is 300, so should cap at 300
    assert fee['amount'] == 300


# ═══════════════════════════════════════════════
# AI RECOMMENDATIONS + CHATBOT HISTORY
# ═══════════════════════════════════════════════

def test_save_and_get_recommendation(db_path):
    save_recommendation(db_path, "Z_TEST_A", "Great time to park!",
                        "CALM", 25.0, None)
    rec = get_latest_recommendation(db_path, "Z_TEST_A")
    assert rec is not None
    assert rec['category'] == "CALM"
    assert "Great time" in rec['message']


def test_save_chat_message(db_path):
    save_chat_message(db_path, "Is the mall full?",
                      "No, plenty of space!", "CHECK_AVAILABILITY", None)
    # Just verify no exception — chat history is write-only in this layer


# ═══════════════════════════════════════════════
# FK ENFORCEMENT + WAL MODE
# ═══════════════════════════════════════════════

def test_wal_mode_enabled(db_path):
    """Database operates in WAL mode."""
    conn = get_connection(db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal", f"Expected WAL, got {mode}"


def test_fk_enforcement_invalid_zone_booking(db_path):
    """Inserting a booking with nonexistent zone_id fails."""
    user = create_user(db_path, "FK Test", "fk@test.com", "pass")
    conn = get_connection(db_path)
    try:
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO bookings "
                "(user_id, zone_id, booking_time, start_time, status) "
                "VALUES (?, 'NONEXISTENT_ZONE', '2026-01-01', '2026-01-01', 'CONFIRMED')",
                (user['user_id'],)
            )
            conn.commit()
    finally:
        conn.close()


def test_booking_rejected_when_zone_full(db_path):
    """Creating a booking on a full zone raises ValueError."""
    # Fill Z_TEST_B to capacity (50)
    update_status(db_path, "Z_TEST_B", 50, 50)
    user = create_user(db_path, "Full Test", "full@test.com", "pass")
    with pytest.raises(ValueError, match="full"):
        create_booking(db_path, user['user_id'], "Z_TEST_B",
                       "2026-03-25T10:00:00+00:00")


def test_all_locations_with_config(db_path):
    """5 locations with correct data using the full LOCATIONS config."""
    from backend.config import LOCATIONS
    full_path = str(db_path).replace("test_v2.db", "test_full.db")
    init_db(full_path, LOCATIONS)
    locations = get_all_locations(full_path)
    assert len(locations) == 5
    names = {l['name'] for l in locations}
    assert 'Elante Mall Parking' in names
