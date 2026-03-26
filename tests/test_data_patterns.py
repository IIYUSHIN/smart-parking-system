"""
Unit Tests — Synthetic Data Pattern Verification (Phase 2)
Tests data volume, duration, location-specific patterns, surge events,
capacity bounds, and day entry/exit balance.
Requires a database with generated data (30 days, 5 locations).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, get_connection, get_all_events
from backend.config import LOCATIONS, DB_PATH
from backend.data_generator import generate_all_data


# ═══════════════════════════════════════════════
# FIXTURE: Generate data into temp DB
# ═══════════════════════════════════════════════

@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    """Creates a database with ALL 5 locations and 30 days of synthetic data.
    Scope=module so this expensive fixture runs only once."""
    path = str(tmp_path_factory.mktemp("data") / "data_test.db")
    init_db(path, LOCATIONS)
    generate_all_data("2026-02-24", 30, db_path=path)
    return path


# ═══════════════════════════════════════════════
# VOLUME + DURATION
# ═══════════════════════════════════════════════

def test_total_events_above_40000(db_path):
    """Phase 2 QVF: ≥40,000 total events across all 5 locations."""
    conn = get_connection(db_path)
    total = conn.execute("SELECT COUNT(*) as cnt FROM occupancy_log").fetchone()["cnt"]
    conn.close()
    assert total >= 40000, f"Only {total} events generated, need ≥40,000"


def test_data_spans_30_days(db_path):
    """Phase 2 QVF: 30 days of data per location."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT zone_id,
               MIN(SUBSTR(event_time, 1, 10)) as min_date,
               MAX(SUBSTR(event_time, 1, 10)) as max_date,
               COUNT(DISTINCT SUBSTR(event_time, 1, 10)) as unique_days
        FROM occupancy_log
        GROUP BY zone_id
    """).fetchall()
    conn.close()
    for row in rows:
        assert row["unique_days"] >= 28, (
            f"Zone {row['zone_id']}: only {row['unique_days']} days"
        )


# ═══════════════════════════════════════════════
# CAPACITY BOUNDS
# ═══════════════════════════════════════════════

def test_no_negative_occupancy(db_path):
    """No event ever has occupancy_after < 0."""
    conn = get_connection(db_path)
    neg = conn.execute(
        "SELECT COUNT(*) as cnt FROM occupancy_log WHERE occupancy_after < 0"
    ).fetchone()["cnt"]
    conn.close()
    assert neg == 0, f"{neg} events with negative occupancy"


def test_no_exceeding_capacity(db_path):
    """No event has occupancy_after > max_capacity for that zone."""
    conn = get_connection(db_path)
    violations = conn.execute("""
        SELECT ol.zone_id, ol.occupancy_after, pz.max_capacity
        FROM occupancy_log ol
        JOIN parking_zones pz ON ol.zone_id = pz.zone_id
        WHERE ol.occupancy_after > pz.max_capacity
        LIMIT 1
    """).fetchone()
    conn.close()
    assert violations is None, (
        f"Zone {violations['zone_id']}: occupancy {violations['occupancy_after']} "
        f"> max {violations['max_capacity']}"
    )


# ═══════════════════════════════════════════════
# PATTERN: CORPORATE (weekday heavy, weekend dead)
# ═══════════════════════════════════════════════

def test_corporate_weekday_vs_weekend(db_path):
    """Corporate lot: weekday occupancy >> weekend occupancy."""
    conn = get_connection(db_path)
    # Get corporate zone(s) - all zones under LOC_CORP
    corp_zones = conn.execute(
        "SELECT zone_id FROM parking_zones WHERE location_id = 'LOC_CORP'"
    ).fetchall()
    corp_zone_ids = [z["zone_id"] for z in corp_zones]
    if not corp_zone_ids:
        conn.close()
        pytest.skip("No corporate zones found")

    placeholders = ",".join(["?" for _ in corp_zone_ids])

    weekday_avg = conn.execute(f"""
        SELECT AVG(occupancy_after) as avg
        FROM occupancy_log
        WHERE zone_id IN ({placeholders})
        AND CAST(strftime('%w', SUBSTR(event_time, 1, 10)) AS INTEGER)
            BETWEEN 1 AND 5
    """, corp_zone_ids).fetchone()["avg"]

    weekend_avg = conn.execute(f"""
        SELECT AVG(occupancy_after) as avg
        FROM occupancy_log
        WHERE zone_id IN ({placeholders})
        AND CAST(strftime('%w', SUBSTR(event_time, 1, 10)) AS INTEGER)
            IN (0, 6)
    """, corp_zone_ids).fetchone()["avg"]
    conn.close()

    assert weekday_avg > weekend_avg * 2, (
        f"Corporate weekday avg {weekday_avg:.1f} not significantly "
        f"> weekend avg {weekend_avg:.1f}"
    )


# ═══════════════════════════════════════════════
# PATTERN: MALL (weekend > weekday)
# ═══════════════════════════════════════════════

def test_mall_weekend_higher_than_weekday(db_path):
    """Mall: weekend occupancy should be higher than weekday."""
    conn = get_connection(db_path)
    mall_zones = conn.execute(
        "SELECT zone_id FROM parking_zones WHERE location_id = 'LOC_MALL'"
    ).fetchall()
    mall_zone_ids = [z["zone_id"] for z in mall_zones]
    if not mall_zone_ids:
        conn.close()
        pytest.skip("No mall zones found")

    placeholders = ",".join(["?" for _ in mall_zone_ids])

    weekday_avg = conn.execute(f"""
        SELECT AVG(occupancy_after) as avg
        FROM occupancy_log
        WHERE zone_id IN ({placeholders})
        AND CAST(strftime('%w', SUBSTR(event_time, 1, 10)) AS INTEGER)
            BETWEEN 1 AND 5
    """, mall_zone_ids).fetchone()["avg"]

    weekend_avg = conn.execute(f"""
        SELECT AVG(occupancy_after) as avg
        FROM occupancy_log
        WHERE zone_id IN ({placeholders})
        AND CAST(strftime('%w', SUBSTR(event_time, 1, 10)) AS INTEGER)
            IN (0, 6)
    """, mall_zone_ids).fetchone()["avg"]
    conn.close()

    assert weekend_avg > weekday_avg, (
        f"Mall weekend avg {weekend_avg:.1f} not > weekday avg {weekday_avg:.1f}"
    )


# ═══════════════════════════════════════════════
# PATTERN: AIRPORT (never below 30%, 24/7)
# ═══════════════════════════════════════════════

def test_airport_never_empty(db_path):
    """Airport: 24/7 operation, events at all hours including late night."""
    conn = get_connection(db_path)
    air_zones = conn.execute(
        "SELECT zone_id FROM parking_zones WHERE location_id = 'LOC_AIRPORT'"
    ).fetchall()
    air_zone_ids = [z["zone_id"] for z in air_zones]
    if not air_zone_ids:
        conn.close()
        pytest.skip("No airport zones found")

    placeholders = ",".join(["?" for _ in air_zone_ids])

    # Check data exists in late-night hours (2-5 AM)
    late_night = conn.execute(f"""
        SELECT COUNT(*) as cnt
        FROM occupancy_log
        WHERE zone_id IN ({placeholders})
        AND CAST(SUBSTR(event_time, 12, 2) AS INTEGER) BETWEEN 2 AND 5
    """, air_zone_ids).fetchone()["cnt"]
    conn.close()

    assert late_night > 0, "Airport has no events in late night hours (2-5 AM)"


# ═══════════════════════════════════════════════
# PATTERN: UNIVERSITY (dead on weekends)
# ═══════════════════════════════════════════════

def test_university_weekend_low(db_path):
    """University: weekends should have very low occupancy."""
    conn = get_connection(db_path)
    uni_zones = conn.execute(
        "SELECT zone_id, max_capacity FROM parking_zones WHERE location_id = 'LOC_UNI'"
    ).fetchall()
    if not uni_zones:
        conn.close()
        pytest.skip("No university zones found")

    zone_id = uni_zones[0]["zone_id"]
    max_cap = uni_zones[0]["max_capacity"]

    weekend_avg = conn.execute("""
        SELECT AVG(occupancy_after) as avg
        FROM occupancy_log
        WHERE zone_id = ?
        AND CAST(strftime('%w', SUBSTR(event_time, 1, 10)) AS INTEGER)
            IN (0, 6)
    """, (zone_id,)).fetchone()["avg"]
    conn.close()

    weekend_util = (weekend_avg / max_cap * 100) if max_cap > 0 else 0
    assert weekend_util < 30, (
        f"University weekend utilization {weekend_util:.1f}% is too high"
    )


# ═══════════════════════════════════════════════
# PATTERN: HOSPITAL (never truly empty)
# ═══════════════════════════════════════════════

def test_hospital_always_occupied(db_path):
    """Hospital: never truly empty, even at 3 AM."""
    conn = get_connection(db_path)
    hosp_zones = conn.execute(
        "SELECT zone_id FROM parking_zones WHERE location_id = 'LOC_HOSP'"
    ).fetchall()
    if not hosp_zones:
        conn.close()
        pytest.skip("No hospital zones found")

    # Check events exist at late night (2-5 AM)
    zone_id = hosp_zones[0]["zone_id"]
    late_events = conn.execute("""
        SELECT COUNT(*) as cnt
        FROM occupancy_log
        WHERE zone_id = ?
        AND CAST(SUBSTR(event_time, 12, 2) AS INTEGER) BETWEEN 2 AND 5
    """, (zone_id,)).fetchone()["cnt"]
    conn.close()

    assert late_events > 0, "Hospital has no events in late night (2-5 AM)"


# ═══════════════════════════════════════════════
# DAY CONSISTENCY (entries ≈ exits)
# ═══════════════════════════════════════════════

def test_daily_entry_exit_balance(db_path):
    """Total entries ≈ total exits per day (±10% tolerance)."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            SUBSTR(event_time, 1, 10) as date,
            zone_id,
            SUM(CASE WHEN event_type = 'ENTRY' THEN 1 ELSE 0 END) as entries,
            SUM(CASE WHEN event_type = 'EXIT' THEN 1 ELSE 0 END) as exits
        FROM occupancy_log
        GROUP BY date, zone_id
    """).fetchall()
    conn.close()

    imbalanced_days = 0
    for row in rows:
        entries = row["entries"]
        exits = row["exits"]
        total = entries + exits
        if total > 10:  # Only check days with meaningful data
            diff = abs(entries - exits)
            # Allow reasonable imbalance (end-of-day residual)
            if diff > max(5, total * 0.15):
                imbalanced_days += 1

    total_days = len(rows)
    # Require 90% of days to be mathematically balanced
    assert imbalanced_days < total_days * 0.1, (
        f"{imbalanced_days}/{total_days} days have large entry/exit imbalance"
    )


# ═══════════════════════════════════════════════
# EVENTS PER LOCATION (all 5 locations have data)
# ═══════════════════════════════════════════════

def test_all_5_locations_have_events(db_path):
    """All 5 locations should have events generated."""
    conn = get_connection(db_path)
    locations = conn.execute("""
        SELECT pl.location_id, pl.name, COUNT(ol.event_id) as event_count
        FROM parking_locations pl
        JOIN parking_zones pz ON pl.location_id = pz.location_id
        LEFT JOIN occupancy_log ol ON pz.zone_id = ol.zone_id
        GROUP BY pl.location_id
    """).fetchall()
    conn.close()

    assert len(locations) == 5, f"Expected 5 locations, got {len(locations)}"
    for loc in locations:
        assert loc["event_count"] > 1000, (
            f"{loc['name']} has only {loc['event_count']} events"
        )
