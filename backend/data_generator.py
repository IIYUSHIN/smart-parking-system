"""
Smart Parking System — Synthetic Data Generator
Generates 14 days of realistic parking events for ML training.
Patterns: weekday commuter peaks (8-10 AM, 5-7 PM),
          weekend leisure peaks (11 AM - 3 PM).
"""

import random
import math
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, log_event, update_status, aggregate_daily
from backend.config import DB_PATH, PARKING_ID, PARKING_NAME, MAX_CAPACITY


# ═══════════════════════════════════════════════════════════
# ARRIVAL RATE MODEL
# ═══════════════════════════════════════════════════════════

def hourly_arrival_rate(hour: int, is_weekend: bool) -> float:
    """Returns expected events per hour (Poisson lambda).

    Weekday: commuter pattern (peaks 8-10, 17-19)
    Weekend: leisure pattern (peak 11-15)
    """
    if is_weekend:
        rates = {
            (0, 6): 0.3,    # late night / early morning
            (6, 9): 0.8,    # slow morning
            (9, 11): 1.5,   # buildup
            (11, 15): 3.5,  # midday peak
            (15, 18): 2.0,  # afternoon
            (18, 21): 1.0,  # evening
            (21, 24): 0.3,  # night
        }
    else:
        rates = {
            (0, 6): 0.5,    # very low
            (6, 8): 2.0,    # morning buildup
            (8, 10): 4.0,   # MORNING PEAK
            (10, 12): 2.0,  # midday settle
            (12, 14): 2.5,  # lunch activity
            (14, 17): 2.5,  # afternoon
            (17, 19): 4.0,  # EVENING PEAK
            (19, 21): 2.0,  # evening wind-down
            (21, 24): 0.5,  # night
        }

    for (start, end), rate in rates.items():
        if start <= hour < end:
            return rate
    return 0.5  # fallback


def _poisson_sample(lam: float) -> int:
    """Simple Poisson random sample using inverse transform."""
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p < L:
            return k - 1


# ═══════════════════════════════════════════════════════════
# DAY GENERATION
# ═══════════════════════════════════════════════════════════

def generate_day(date: datetime, parking_id: str,
                 db_path: str, max_capacity: int = MAX_CAPACITY) -> int:
    """Generates one full day of entry/exit events.

    Algorithm:
    1. Start with current_count = 0
    2. For each hour (0-23):
       - Sample events from Poisson distribution
       - Decide ENTRY/EXIT based on count state
       - Log each event with proper timestamp
    3. Return total events generated.
    """
    is_weekend = date.weekday() >= 5  # Sat=5, Sun=6
    current_count = 0
    total_events = 0

    for hour in range(24):
        lam = hourly_arrival_rate(hour, is_weekend)
        num_events = _poisson_sample(lam)

        # Generate events distributed within the hour
        minutes = sorted(random.sample(range(60), min(num_events, 60)))
        if len(minutes) < num_events:
            minutes = sorted([random.randint(0, 59) for _ in range(num_events)])

        for minute in minutes:
            # Decide event type based on current state
            if current_count >= max_capacity:
                event_type = "EXIT"
            elif current_count == 0:
                event_type = "ENTRY"
            else:
                # Bias: during peaks, more entries; otherwise more balanced
                entry_prob = 0.55 if lam >= 3.0 else 0.50
                event_type = "ENTRY" if random.random() < entry_prob else "EXIT"

            # Apply event
            if event_type == "ENTRY" and current_count < max_capacity:
                current_count += 1
            elif event_type == "EXIT" and current_count > 0:
                current_count -= 1
            else:
                continue  # skip invalid events

            # Create timestamp
            second = random.randint(0, 59)
            event_time = date.replace(
                hour=hour, minute=minute, second=second
            ).isoformat(timespec='seconds')

            # Log to database
            log_event(db_path, parking_id, event_type,
                      current_count, event_time=event_time)
            total_events += 1

    return total_events


# ═══════════════════════════════════════════════════════════
# DATASET GENERATION
# ═══════════════════════════════════════════════════════════

def generate_dataset(start_date: str, num_days: int = 14,
                     parking_id: str = PARKING_ID,
                     db_path: str = DB_PATH) -> dict:
    """Generates full dataset across multiple days.

    Args:
        start_date: "YYYY-MM-DD" format
        num_days: number of days to generate (default 14)
        parking_id: parking zone identifier
        db_path: SQLite database path

    Returns:
        {'days': num_days, 'total_events': int}
    """
    # Ensure DB and config exist
    init_db(db_path, parking_id, PARKING_NAME, MAX_CAPACITY)

    base_date = datetime.strptime(start_date, "%Y-%m-%d").replace(
        tzinfo=timezone.utc)
    total_events = 0

    print(f"Generating {num_days} days of synthetic data...")
    print(f"  Start date: {start_date}")
    print(f"  Parking ID: {parking_id}")
    print(f"  Max capacity: {MAX_CAPACITY}")
    print()

    for day_offset in range(num_days):
        current_date = base_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%A")
        is_wknd = "Weekend" if current_date.weekday() >= 5 else "Weekday"

        events = generate_day(current_date, parking_id, db_path)
        total_events += events

        # Aggregate daily summary
        aggregate_daily(db_path, parking_id, date_str, MAX_CAPACITY)

        print(f"  Day {day_offset + 1:2d} | {date_str} ({day_name:9s}) "
              f"| {is_wknd:7s} | {events:3d} events")

    print(f"\n  Total: {total_events} events across {num_days} days")
    print(f"  [OK] Synthetic data generation complete")

    return {"days": num_days, "total_events": total_events}


# ═══════════════════════════════════════════════════════════
# STANDALONE EXECUTION
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Clear existing data for clean generation
    import sqlite3
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM occupancy_log")
        conn.execute("DELETE FROM daily_summary")
        conn.commit()
        conn.close()
        print("Cleared existing data.\n")

    result = generate_dataset("2026-03-10", num_days=14)
    print(f"\nResult: {result}")
