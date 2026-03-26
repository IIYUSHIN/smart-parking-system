"""
Smart Parking System v2.0 — Realistic Synthetic Data Generator

Generates 30 days of parking events for 5 locations (9 zones) with:
- Location-specific hourly occupancy curves (researched real-world patterns)
- Weekday vs weekend differentiation
- Event-driven surges (movie releases, festivals, exams, emergencies)
- Day-of-week multipliers per location type
- Batch insertion for performance (~45K events in <30 seconds)

Target: ~45,000 total events across all locations.
"""

import random
import math
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    init_db, batch_log_events, aggregate_daily, get_connection
)
from backend.config import DB_PATH, LOCATIONS


# ═══════════════════════════════════════════════════════════
# POISSON SAMPLING
# ═══════════════════════════════════════════════════════════

def _poisson_sample(lam: float) -> int:
    """Poisson random sample using Knuth's algorithm."""
    if lam <= 0:
        return 0
    L = math.exp(-min(lam, 700))
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p < L:
            return k - 1


# ═══════════════════════════════════════════════════════════
# LOCATION-SPECIFIC OCCUPANCY PROFILES
# Each returns target occupancy % (0-100) for a given hour.
# ═══════════════════════════════════════════════════════════

def _corporate_profile(hour: int, is_weekend: bool) -> float:
    if is_weekend:
        return 3.0
    profiles = {
        0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 3,
        6: 8, 7: 35, 8: 75, 9: 92, 10: 95, 11: 93,
        12: 88, 13: 92, 14: 95, 15: 94, 16: 90, 17: 70,
        18: 30, 19: 10, 20: 5, 21: 3, 22: 2, 23: 2
    }
    return profiles.get(hour, 2)


def _mall_profile(hour: int, is_weekend: bool) -> float:
    base = {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
        6: 0, 7: 2, 8: 10, 9: 25, 10: 45, 11: 65,
        12: 80, 13: 75, 14: 70, 15: 65, 16: 60, 17: 70,
        18: 85, 19: 90, 20: 75, 21: 45, 22: 15, 23: 2
    }
    multiplier = 1.25 if is_weekend else 1.0
    return min(100, base.get(hour, 0) * multiplier)


def _airport_profile(hour: int, is_weekend: bool) -> float:
    base = {
        0: 45, 1: 40, 2: 38, 3: 35, 4: 38, 5: 50,
        6: 65, 7: 75, 8: 80, 9: 82, 10: 78, 11: 75,
        12: 72, 13: 70, 14: 72, 15: 75, 16: 78, 17: 80,
        18: 82, 19: 80, 20: 75, 21: 65, 22: 55, 23: 48
    }
    multiplier = 1.08 if is_weekend else 1.0
    return min(100, base.get(hour, 50) * multiplier)


def _university_profile(hour: int, is_weekend: bool) -> float:
    if is_weekend:
        return 5.0
    profiles = {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
        6: 5, 7: 30, 8: 70, 9: 85, 10: 90, 11: 88,
        12: 75, 13: 80, 14: 85, 15: 75, 16: 50, 17: 25,
        18: 10, 19: 5, 20: 0, 21: 0, 22: 0, 23: 0
    }
    return profiles.get(hour, 0)


def _hospital_profile(hour: int, is_weekend: bool) -> float:
    base = {
        0: 20, 1: 15, 2: 12, 3: 10, 4: 12, 5: 18,
        6: 30, 7: 55, 8: 75, 9: 85, 10: 90, 11: 88,
        12: 82, 13: 80, 14: 78, 15: 72, 16: 65, 17: 55,
        18: 40, 19: 30, 20: 25, 21: 22, 22: 20, 23: 20
    }
    multiplier = 0.85 if is_weekend else 1.0
    return max(10, base.get(hour, 20) * multiplier)


_PROFILES = {
    "MALL": _mall_profile,
    "AIRPORT": _airport_profile,
    "CORPORATE": _corporate_profile,
    "UNIVERSITY": _university_profile,
    "HOSPITAL": _hospital_profile,
}


# ═══════════════════════════════════════════════════════════
# EVENT-DRIVEN SURGES
# ═══════════════════════════════════════════════════════════

def _generate_special_events(location_type: str, num_days: int) -> dict:
    """Returns {day_offset: (surge_multiplier, description, affected_hours)}."""
    events = {}
    if location_type == "MALL":
        events[5] = (1.40, "Blockbuster Movie Release", range(17, 23))
        events[6] = (1.35, "Movie Release Day 2", range(14, 23))
        events[15] = (1.60, "Diwali Festival", range(10, 23))
        events[16] = (1.50, "Diwali Day 2", range(10, 23))
        events[22] = (1.35, "End of Season Sale", range(11, 21))
    elif location_type == "AIRPORT":
        events[8] = (1.30, "Holiday Season Start", range(0, 24))
        events[9] = (1.35, "Peak Holiday Travel", range(0, 24))
        events[10] = (1.25, "Holiday Season End", range(0, 24))
        events[20] = (1.25, "Long Weekend Travel", range(4, 20))
    elif location_type == "CORPORATE":
        events[12] = (1.15, "Quarter-End All-Hands", range(8, 18))
        events[13] = (1.20, "Client Visit Day", range(7, 19))
        events[25] = (1.25, "Annual Company Day", range(8, 22))
    elif location_type == "UNIVERSITY":
        for d in range(18, 23):
            events[d] = (1.50, "Mid-Semester Exams", range(6, 20))
        events[10] = (1.30, "Cultural Festival", range(8, 22))
        events[11] = (1.35, "Cultural Festival Day 2", range(8, 22))
    elif location_type == "HOSPITAL":
        events[7] = (1.30, "Emergency Surge", range(0, 24))
        events[14] = (1.25, "Flu Season Peak", range(8, 18))
        events[23] = (1.20, "Health Camp", range(7, 16))

    return {k: v for k, v in events.items() if k < num_days}


# ═══════════════════════════════════════════════════════════
# DAY-OF-WEEK MULTIPLIERS
# ═══════════════════════════════════════════════════════════

_DOW_MULTIPLIERS = {
    "CORPORATE": {0: 1.10, 1: 1.05, 2: 1.00, 3: 1.00, 4: 0.90, 5: 0.05, 6: 0.05},
    "MALL":      {0: 0.85, 1: 0.80, 2: 0.80, 3: 0.85, 4: 0.95, 5: 1.20, 6: 1.25},
    "AIRPORT":   {0: 1.00, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.10, 5: 1.08, 6: 1.05},
    "UNIVERSITY":{0: 1.05, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.90, 5: 0.05, 6: 0.05},
    "HOSPITAL":  {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.95, 5: 0.85, 6: 0.85},
}


# ═══════════════════════════════════════════════════════════
# CORE GENERATION ENGINE (BATCH-OPTIMIZED)
# ═══════════════════════════════════════════════════════════

def generate_zone_day(date: datetime, zone_id: str,
                      max_capacity: int, location_type: str,
                      special_event: tuple = None,
                      day_of_week_multiplier: float = 1.0) -> list[tuple]:
    """Generates one full day of events for a single zone.
    Returns list of tuples: (zone_id, event_type, event_time, occupancy_after).
    Does NOT insert into database — caller handles batching."""
    is_weekend = date.weekday() >= 5
    profile_fn = _PROFILES[location_type]
    current_count = 0
    events = []

    surge_multiplier = 1.0
    surge_hours = range(0)
    if special_event:
        surge_multiplier, _, surge_hours = special_event

    for hour in range(24):
        # Calculate target occupancy
        target_pct = profile_fn(hour, is_weekend)
        target_pct *= day_of_week_multiplier
        if hour in surge_hours:
            target_pct *= surge_multiplier

        target_count = int(round(target_pct / 100.0 * max_capacity))
        target_count = max(0, min(max_capacity, target_count))

        # Add noise
        noise_range = max(1, max_capacity // 20)
        noise = random.randint(-noise_range, noise_range)
        target_count = max(0, min(max_capacity, target_count + noise))

        # Generate events to move toward target
        delta = target_count - current_count
        if delta == 0:
            # Generate 0-2 balanced event pairs for activity
            num_pairs = random.randint(0, 2)
            for _ in range(num_pairs):
                minute = random.randint(0, 58)
                second = random.randint(0, 59)
                et1 = date.replace(hour=hour, minute=minute, second=second
                                   ).isoformat(timespec='seconds')
                et2 = date.replace(hour=hour, minute=minute + 1, second=second
                                   ).isoformat(timespec='seconds')
                if current_count < max_capacity:
                    current_count += 1
                    events.append((zone_id, "ENTRY", et1, current_count))
                if current_count > 0:
                    current_count -= 1
                    events.append((zone_id, "EXIT", et2, current_count))
        else:
            num_main = abs(delta)
            churn = random.randint(0, max(1, num_main // 4))
            all_seconds = sorted(random.sample(
                range(3600), min(num_main + churn * 2, 3600)
            ))

            churn_done = 0
            remaining = delta

            for ts in all_seconds:
                m = ts // 60
                s = ts % 60
                et = date.replace(hour=hour, minute=m, second=s
                                  ).isoformat(timespec='seconds')

                if churn_done < churn and current_count < max_capacity:
                    current_count += 1
                    events.append((zone_id, "ENTRY", et, current_count))
                    churn_done += 1
                elif churn_done < churn * 2 and churn_done >= churn and current_count > 0:
                    current_count -= 1
                    events.append((zone_id, "EXIT", et, current_count))
                    churn_done += 1
                elif remaining > 0 and current_count < max_capacity:
                    current_count += 1
                    events.append((zone_id, "ENTRY", et, current_count))
                    remaining -= 1
                elif remaining < 0 and current_count > 0:
                    current_count -= 1
                    events.append((zone_id, "EXIT", et, current_count))
                    remaining += 1

    return events


def generate_all_data(start_date: str = "2026-02-24",
                      num_days: int = 30,
                      db_path: str = DB_PATH) -> dict:
    """Generates synthetic data for ALL 5 locations across all zones.
    Uses batch insertion for performance."""
    init_db(db_path, LOCATIONS)

    base_date = datetime.strptime(start_date, "%Y-%m-%d").replace(
        tzinfo=timezone.utc)

    print("=" * 70)
    print("  SMART PARKING SYSTEM v2.0 -- Synthetic Data Generator")
    print("=" * 70)
    print(f"  Start date:  {start_date}")
    print(f"  Duration:    {num_days} days")
    print(f"  Locations:   {len(LOCATIONS)}")
    total_zones = sum(len(l['zones']) for l in LOCATIONS)
    total_cap = sum(z['max_capacity'] for l in LOCATIONS for z in l['zones'])
    print(f"  Total zones: {total_zones}")
    print(f"  Total capacity: {total_cap} slots")
    print()

    results = {}
    grand_total = 0

    for loc in LOCATIONS:
        loc_id = loc["location_id"]
        loc_name = loc["name"]
        loc_type = loc["location_type"]
        total_loc_cap = sum(z["max_capacity"] for z in loc["zones"])
        dow_mults = _DOW_MULTIPLIERS.get(loc_type, {i: 1.0 for i in range(7)})
        special_events = _generate_special_events(loc_type, num_days)

        print(f"  [{loc_type:10s}] {loc_name} ({total_loc_cap} slots)")

        zone_stats = {}

        for zone in loc["zones"]:
            zone_id = zone["zone_id"]
            max_cap = zone["max_capacity"]
            all_zone_events = []

            for day_offset in range(num_days):
                current_date = base_date + timedelta(days=day_offset)
                dow = current_date.weekday()
                dow_mult = dow_mults.get(dow, 1.0)
                special = special_events.get(day_offset)

                day_events = generate_zone_day(
                    current_date, zone_id, max_cap, loc_type,
                    special_event=special,
                    day_of_week_multiplier=dow_mult
                )
                all_zone_events.extend(day_events)

            # Batch insert all events for this zone at once
            batch_log_events(db_path, all_zone_events)

            # Aggregate daily summaries
            for day_offset in range(num_days):
                current_date = base_date + timedelta(days=day_offset)
                date_str = current_date.strftime("%Y-%m-%d")
                aggregate_daily(db_path, zone_id, date_str, max_cap)

            zone_stats[zone_id] = len(all_zone_events)
            grand_total += len(all_zone_events)
            print(f"    Zone {zone_id}: {len(all_zone_events):,} events")

        results[loc_id] = {
            "location_type": loc_type,
            "zones": zone_stats,
            "total_events": sum(zone_stats.values())
        }
        print(f"    Total: {results[loc_id]['total_events']:,} events")
        print()

    print("-" * 70)
    print(f"  GRAND TOTAL: {grand_total:,} events across "
          f"{len(LOCATIONS)} locations, {num_days} days")
    print("=" * 70)

    return {"locations": results, "grand_total": grand_total}


# ═══════════════════════════════════════════════════════════
# STANDALONE EXECUTION
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        conn = get_connection(DB_PATH)
        try:
            conn.execute("DELETE FROM occupancy_log")
            conn.execute("DELETE FROM daily_summary")
            conn.commit()
            print("[CLEAN] Cleared existing event data.\n")
        finally:
            conn.close()

    result = generate_all_data("2026-02-24", num_days=30)
    print(f"\nResult: {result['grand_total']:,} total events generated")
