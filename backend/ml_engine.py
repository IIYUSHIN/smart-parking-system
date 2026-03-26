"""
Smart Parking System v2.0 — AI/ML Engine

Features:
  1. Per-location ML models (Linear Regression + Random Forest)
  2. Smart Recommendation Engine (6 utilization tiers)
  3. Anomaly Detection (Z-score based)
  4. Best Time Finder (per location)
  5. Peak Hour Detection (per zone)
  6. Overall pipeline for all locations
"""

import os
import sys
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    get_connection, get_hourly_averages, get_all_events,
    save_prediction, save_recommendation,
    get_all_locations, get_zones_for_location,
    get_status, get_all_statuses
)
from backend.config import DB_PATH, LOCATIONS, MODELS_DIR, MOVING_AVG_WINDOW


# ═══════════════════════════════════════════════════════════
# DATA LOADING + FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════

def load_training_data(zone_id: str, db_path: str = DB_PATH) -> pd.DataFrame:
    """Loads occupancy_log for a zone into DataFrame with features."""
    events = get_all_events(db_path, zone_id)
    if not events:
        return pd.DataFrame()

    df = pd.DataFrame(events)
    df['event_time'] = pd.to_datetime(df['event_time'])
    df['hour'] = df['event_time'].dt.hour
    df['day_of_week'] = df['event_time'].dt.dayofweek
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['minute_of_day'] = df['event_time'].dt.hour * 60 + df['event_time'].dt.minute
    df['date'] = df['event_time'].dt.strftime('%Y-%m-%d')

    return df


def compute_hourly_occupancy(df: pd.DataFrame) -> pd.DataFrame:
    """Groups by date + hour, computes avg occupancy per hour."""
    if df.empty:
        return pd.DataFrame()

    hourly = df.groupby(['date', 'hour']).agg(
        avg_occupancy=('occupancy_after', 'mean'),
        max_occupancy=('occupancy_after', 'max'),
        entry_count=('event_type', lambda x: (x == 'ENTRY').sum()),
        exit_count=('event_type', lambda x: (x == 'EXIT').sum()),
        event_count=('event_id', 'count')
    ).reset_index()

    hourly['net_flow'] = hourly['entry_count'] - hourly['exit_count']

    # Add day of week
    hourly['day_of_week'] = pd.to_datetime(hourly['date']).dt.dayofweek
    hourly['is_weekend'] = (hourly['day_of_week'] >= 5).astype(int)

    return hourly


# ═══════════════════════════════════════════════════════════
# MOVING AVERAGE PREDICTOR
# ═══════════════════════════════════════════════════════════

class MovingAveragePredictor:
    """Simple N-point moving average model."""

    def __init__(self, window: int = MOVING_AVG_WINDOW):
        self.window = window

    def predict(self, recent_values: list) -> float:
        if not recent_values:
            return 0.0
        if len(recent_values) < self.window:
            return sum(recent_values) / len(recent_values)
        return sum(recent_values[-self.window:]) / self.window


# ═══════════════════════════════════════════════════════════
# LINEAR REGRESSION MODEL (Per Zone)
# ═══════════════════════════════════════════════════════════

class ZoneLinearModel:
    """Predicts occupancy from hour-of-day for a specific zone."""

    def __init__(self, zone_id: str, max_capacity: int):
        self.zone_id = zone_id
        self.max_capacity = max_capacity
        self.model = LinearRegression()
        self.is_trained = False
        self.mae = None

    def train(self, hourly_df: pd.DataFrame) -> float:
        if hourly_df.empty or len(hourly_df) < 5:
            raise ValueError(f"Need >= 5 data points for {self.zone_id}")  

        X = hourly_df[['hour']].values
        y = hourly_df['avg_occupancy'].values.astype(float)
        self.model.fit(X, y)

        predictions = self.model.predict(X)
        self.mae = float(mean_absolute_error(y, predictions))
        self.is_trained = True
        return self.mae

    def predict(self, hour: int) -> float:
        if not self.is_trained:
            raise RuntimeError(f"Model for {self.zone_id} not trained")
        raw = self.model.predict([[hour]])[0]
        return max(0.0, min(float(self.max_capacity), round(float(raw), 1)))

    def predict_all_hours(self) -> list[dict]:
        """Returns predictions for all 24 hours."""
        if not self.is_trained:
            return []
        return [
            {"hour": h, "predicted": self.predict(h),
             "utilization": round(self.predict(h) / self.max_capacity * 100, 1)}
            for h in range(24)
        ]


# ═══════════════════════════════════════════════════════════
# RANDOM FOREST MODEL (Per Zone — handles non-linear patterns)
# ═══════════════════════════════════════════════════════════

class ZoneRandomForest:
    """Non-linear predictor using hour + day_of_week + is_weekend."""

    def __init__(self, zone_id: str, max_capacity: int):
        self.zone_id = zone_id
        self.max_capacity = max_capacity
        self.model = RandomForestRegressor(
            n_estimators=50, max_depth=8, random_state=42
        )
        self.is_trained = False
        self.mae = None

    def train(self, hourly_df: pd.DataFrame) -> float:
        if hourly_df.empty or len(hourly_df) < 10:
            raise ValueError(f"Need >= 10 data points for RF {self.zone_id}")

        X = hourly_df[['hour', 'day_of_week', 'is_weekend']].values
        y = hourly_df['avg_occupancy'].values.astype(float)
        self.model.fit(X, y)

        predictions = self.model.predict(X)
        self.mae = float(mean_absolute_error(y, predictions))
        self.is_trained = True
        return self.mae

    def predict(self, hour: int, day_of_week: int = None,
                is_weekend: bool = None) -> float:
        if not self.is_trained:
            raise RuntimeError(f"RF for {self.zone_id} not trained")
        if day_of_week is None:
            day_of_week = datetime.now().weekday()
        if is_weekend is None:
            is_weekend = day_of_week >= 5
        raw = self.model.predict([[hour, day_of_week, int(is_weekend)]])[0]
        return max(0.0, min(float(self.max_capacity), round(float(raw), 1)))

    def predict_all_hours(self, day_of_week: int = None) -> list[dict]:
        if not self.is_trained:
            return []
        if day_of_week is None:
            day_of_week = datetime.now().weekday()
        is_wknd = int(day_of_week >= 5)
        return [
            {"hour": h, "predicted": self.predict(h, day_of_week, bool(is_wknd)),
             "utilization": round(
                 self.predict(h, day_of_week, bool(is_wknd)) / self.max_capacity * 100, 1
             )}
            for h in range(24)
        ]


# ═══════════════════════════════════════════════════════════
# SMART RECOMMENDATION ENGINE
# ═══════════════════════════════════════════════════════════

def generate_recommendation(zone_id: str, zone_name: str,
                            utilization_pct: float,
                            available_slots: int,
                            max_capacity: int,
                            alternative: dict = None) -> dict:
    """Generates smart recommendation based on current utilization.

    6 tiers:
    - 0-30%:   CALM
    - 31-60%:  INFORMATIONAL
    - 61-80%:  ALERT
    - 81-90%:  URGENT
    - 91-99%:  CRITICAL
    - 100%:    FULL_REDIRECT
    """
    if utilization_pct <= 30:
        category = "CALM"
        message = (f"Great time to park! Plenty of space at {zone_name}. "
                   f"{available_slots} of {max_capacity} spots available.")
    elif utilization_pct <= 60:
        category = "INFORMATIONAL"
        message = (f"Moderate traffic at {zone_name}. "
                   f"{available_slots} spots available. No rush.")
    elif utilization_pct <= 80:
        category = "ALERT"
        message = (f"Getting busy at {zone_name}! "
                   f"Only {available_slots} spots left. "
                   f"Consider arriving in the next 30 minutes.")
    elif utilization_pct <= 90:
        category = "URGENT"
        message = (f"{zone_name} is almost full -- "
                   f"only {available_slots} spots remaining!")
    elif utilization_pct < 100:
        category = "CRITICAL"
        if alternative:
            message = (f"Hurry! {zone_name} has just {available_slots} spots! "
                       f"Alternative: {alternative['name']} has "
                       f"{alternative['available']} spots free.")
        else:
            message = (f"Hurry! {zone_name} has just {available_slots} spots! "
                       f"Getting critical fast.")
    else:
        category = "FULL_REDIRECT"
        if alternative:
            message = (f"{zone_name} is FULL. "
                       f"Nearest alternative: {alternative['name']} "
                       f"({alternative['available']} spots free).")
        else:
            message = (f"{zone_name} is completely FULL. "
                       f"No spots available. Please check other locations.")

    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "message": message,
        "category": category,
        "utilization_pct": utilization_pct,
        "available_slots": available_slots
    }


def find_alternative_zone(db_path: str, exclude_zone: str) -> dict | None:
    """Finds the nearest zone with most availability, excluding the given zone."""
    all_statuses = get_all_statuses(db_path)
    best = None
    best_avail = -1

    for s in all_statuses:
        if s["zone_id"] == exclude_zone:
            continue
        avail = s.get("available_slots", 0) or 0
        if avail > best_avail:
            best_avail = avail
            best = {
                "zone_id": s["zone_id"],
                "name": f"{s.get('location_name', '')} - {s.get('zone_name', '')}",
                "available": avail
            }

    return best if best and best_avail > 0 else None


# ═══════════════════════════════════════════════════════════
# ANOMALY DETECTION (Z-Score)
# ═══════════════════════════════════════════════════════════

def detect_anomalies(zone_id: str, db_path: str = DB_PATH,
                     threshold: float = 2.0) -> list[dict]:
    """Detects anomalous occupancy readings using Z-score.

    For each hour, compute mean and std of historical occupancy.
    Current reading > mean + threshold * std = anomaly.
    """
    hourly_avgs = get_hourly_averages(db_path, zone_id)
    if not hourly_avgs or len(hourly_avgs) < 12:
        return []

    # Build lookup: mean and std per hour
    events = get_all_events(db_path, zone_id)
    if not events:
        return []

    df = pd.DataFrame(events)
    df['event_time'] = pd.to_datetime(df['event_time'])
    df['hour'] = df['event_time'].dt.hour

    hourly_stats = df.groupby('hour')['occupancy_after'].agg(
        ['mean', 'std', 'max']
    ).reset_index()
    hourly_stats['std'] = hourly_stats['std'].fillna(0)

    anomalies = []
    for _, row in hourly_stats.iterrows():
        hour = int(row['hour'])
        mean_val = row['mean']
        std_val = row['std']
        max_val = row['max']

        if std_val > 0:
            z_score = (max_val - mean_val) / std_val
            if z_score > threshold:
                anomalies.append({
                    "hour": hour,
                    "mean_occupancy": round(mean_val, 1),
                    "max_occupancy": int(max_val),
                    "std_dev": round(std_val, 2),
                    "z_score": round(z_score, 2),
                    "severity": "HIGH" if z_score > 3.0 else "MEDIUM"
                })

    return sorted(anomalies, key=lambda x: x['z_score'], reverse=True)


# ═══════════════════════════════════════════════════════════
# PEAK DETECTION + BEST TIME FINDER (Per Zone)
# ═══════════════════════════════════════════════════════════

def detect_peak_hours(zone_id: str, db_path: str = DB_PATH) -> dict:
    """Finds busiest and quietest hours from historical data."""
    hourly_avgs = get_hourly_averages(db_path, zone_id)
    if not hourly_avgs:
        return {
            "peak_start": "N/A", "peak_end": "N/A",
            "peak_avg_occupancy": 0,
            "low_start": "N/A", "low_end": "N/A"
        }

    sorted_by_occ = sorted(hourly_avgs, key=lambda x: x['avg_occupancy'],
                           reverse=True)
    peak_hour = sorted_by_occ[0]['hour']
    peak_avg = round(sorted_by_occ[0]['avg_occupancy'], 1)

    threshold = peak_avg * 0.7
    peak_hours = sorted([h['hour'] for h in hourly_avgs
                         if h['avg_occupancy'] >= threshold])
    peak_start = peak_hours[0] if peak_hours else peak_hour
    peak_end = peak_hours[-1] + 1 if peak_hours else peak_hour + 1

    sorted_asc = sorted(hourly_avgs, key=lambda x: x['avg_occupancy'])
    low_hours = sorted([h['hour'] for h in sorted_asc[:4]])
    low_start = low_hours[0] if low_hours else 0
    low_end = low_hours[-1] + 1 if low_hours else 6

    return {
        "peak_start": f"{peak_start:02d}:00",
        "peak_end": f"{peak_end:02d}:00",
        "peak_avg_occupancy": peak_avg,
        "low_start": f"{low_start:02d}:00",
        "low_end": f"{low_end:02d}:00"
    }


def find_best_time(zone_id: str, db_path: str = DB_PATH) -> dict:
    """Returns the hour with lowest predicted occupancy for a zone."""
    hourly_avgs = get_hourly_averages(db_path, zone_id)
    if not hourly_avgs:
        return {"best_hour": "N/A", "expected_occupancy": 0}

    # Filter to reasonable hours (6 AM - 11 PM)
    reasonable = [h for h in hourly_avgs if 6 <= h['hour'] <= 22]
    if not reasonable:
        reasonable = hourly_avgs

    best = min(reasonable, key=lambda x: x['avg_occupancy'])
    return {
        "best_hour": f"{best['hour']:02d}:00",
        "expected_occupancy": round(best['avg_occupancy'], 1),
        "expected_events": best.get('event_count', 0)
    }


def compute_overall_utilization(zone_id: str, max_capacity: int,
                                db_path: str = DB_PATH) -> float:
    """Returns average utilization % across all data for a zone."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT AVG(occupancy_after) as avg_occ FROM occupancy_log "
            "WHERE zone_id = ?", (zone_id,)
        ).fetchone()
        avg = row['avg_occ'] if row and row['avg_occ'] is not None else 0
        return round((avg / max_capacity) * 100, 1) if max_capacity > 0 else 0.0
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# FULL PREDICTION PIPELINE (Per Zone)
# ═══════════════════════════════════════════════════════════

def run_zone_prediction(zone_id: str, max_capacity: int,
                        db_path: str = DB_PATH) -> dict:
    """Runs complete ML pipeline for a single zone.

    Steps:
    1. Load training data
    2. Compute hourly occupancy
    3. Train Linear Regression model
    4. Train Random Forest model
    5. Predict next hour (both models)
    6. Run Moving Average
    7. Detect peaks + best time
    8. Run anomaly detection
    9. Save prediction to DB + model to disk
    """
    # Step 1-2
    df = load_training_data(zone_id, db_path)
    if df.empty:
        return {"zone_id": zone_id, "error": "No training data"}

    hourly = compute_hourly_occupancy(df)
    if hourly.empty or len(hourly) < 10:
        return {"zone_id": zone_id, "error": "Insufficient data"}

    # Step 3: Linear Regression
    lr_model = ZoneLinearModel(zone_id, max_capacity)
    lr_mae = lr_model.train(hourly)

    # Step 4: Random Forest
    rf_model = ZoneRandomForest(zone_id, max_capacity)
    rf_mae = rf_model.train(hourly)

    # Step 5: Predict next hour
    current_hour = datetime.now().hour
    next_hour = (current_hour + 1) % 24
    pred_lr = lr_model.predict(next_hour)
    pred_rf = rf_model.predict(next_hour)

    # Step 6: Moving Average
    ma = MovingAveragePredictor()
    recent = hourly['avg_occupancy'].tail(MOVING_AVG_WINDOW).tolist()
    pred_ma = round(ma.predict(recent), 1)

    # Step 7: Peaks + best time
    peaks = detect_peak_hours(zone_id, db_path)
    best_time = find_best_time(zone_id, db_path)
    utilization = compute_overall_utilization(zone_id, max_capacity, db_path)

    # Step 8: Anomalies
    anomalies = detect_anomalies(zone_id, db_path)

    # Step 9: Final prediction (ensemble: weighted average)
    # RF gets higher weight because it handles non-linear patterns better
    final_pred = round(0.5 * pred_rf + 0.3 * pred_lr + 0.2 * pred_ma)
    final_pred = max(0, min(max_capacity, final_pred))

    # Determine best model
    best_model = "random_forest" if rf_mae < lr_mae else "linear_regression"

    # Save to database
    save_prediction(
        db_path, zone_id,
        predicted_count=final_pred,
        peak_hour_start=peaks["peak_start"],
        peak_hour_end=peaks["peak_end"],
        utilization_avg=utilization,
        model_type=best_model,
        mae=min(lr_mae, rf_mae)
    )

    # Save models to disk
    model_dir = os.path.join(MODELS_DIR, zone_id)
    os.makedirs(model_dir, exist_ok=True)
    try:
        joblib.dump(lr_model.model, os.path.join(model_dir, "linear.pkl"))
        joblib.dump(rf_model.model, os.path.join(model_dir, "random_forest.pkl"))
        models_saved = True
    except Exception:
        models_saved = False

    # Get 24-hour predictions
    hourly_predictions = rf_model.predict_all_hours()

    return {
        "zone_id": zone_id,
        "max_capacity": max_capacity,
        "total_events": len(df),
        "training_samples": len(hourly),
        "models": {
            "linear_regression": {"mae": round(lr_mae, 3), "prediction": pred_lr},
            "random_forest": {"mae": round(rf_mae, 3), "prediction": pred_rf},
            "moving_average": {"prediction": pred_ma},
        },
        "best_model": best_model,
        "predicted_count_final": final_pred,
        "peak_hours": peaks,
        "best_time": best_time,
        "utilization_avg": utilization,
        "anomalies": anomalies,
        "hourly_predictions": hourly_predictions,
        "models_saved": models_saved
    }


# ═══════════════════════════════════════════════════════════
# FULL SYSTEM PREDICTION (All Locations)
# ═══════════════════════════════════════════════════════════

def run_all_predictions(db_path: str = DB_PATH) -> dict:
    """Runs ML pipeline for every zone across all locations."""
    results = {}

    for loc in LOCATIONS:
        loc_id = loc["location_id"]
        loc_results = {}

        for zone in loc["zones"]:
            zone_id = zone["zone_id"]
            max_cap = zone["max_capacity"]

            result = run_zone_prediction(zone_id, max_cap, db_path)
            loc_results[zone_id] = result

        results[loc_id] = {
            "location_name": loc["name"],
            "location_type": loc["location_type"],
            "zones": loc_results
        }

    return results


# ═══════════════════════════════════════════════════════════
# RECOMMENDATIONS FOR ALL ZONES
# ═══════════════════════════════════════════════════════════

def generate_all_recommendations(db_path: str = DB_PATH) -> list[dict]:
    """Generates smart recommendations for all zones based on current status."""
    all_statuses = get_all_statuses(db_path)
    recommendations = []

    for status in all_statuses:
        zone_id = status["zone_id"]
        zone_name = f"{status.get('location_name', '')} - {status.get('zone_name', '')}"
        utilization = status.get("utilization_percent", 0) or 0
        available = status.get("available_slots", 0) or 0
        max_cap = status.get("max_capacity", 1) or 1

        # Find alternative if utilization > 80%
        alt = None
        if utilization > 80:
            alt = find_alternative_zone(db_path, zone_id)

        rec = generate_recommendation(
            zone_id, zone_name, utilization, available, max_cap, alt
        )
        recommendations.append(rec)

        # Save to database
        save_recommendation(
            db_path, zone_id, rec["message"], rec["category"],
            utilization, alt["zone_id"] if alt else None
        )

    return recommendations


# ═══════════════════════════════════════════════════════════
# STANDALONE VERIFICATION
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  SMART PARKING v2.0 -- ML Engine Verification")
    print("=" * 70)

    results = run_all_predictions()

    for loc_id, loc_data in results.items():
        print(f"\n  [{loc_data['location_type']}] {loc_data['location_name']}")
        for zone_id, zone_result in loc_data["zones"].items():
            if "error" in zone_result:
                print(f"    {zone_id}: ERROR - {zone_result['error']}")
                continue

            print(f"    {zone_id}:")
            print(f"      Events:      {zone_result['total_events']:,}")
            print(f"      LR MAE:      {zone_result['models']['linear_regression']['mae']}")
            print(f"      RF MAE:      {zone_result['models']['random_forest']['mae']}")
            print(f"      Best Model:  {zone_result['best_model']}")
            print(f"      Prediction:  {zone_result['predicted_count_final']}"
                  f"/{zone_result['max_capacity']}")
            print(f"      Peak Hours:  {zone_result['peak_hours']['peak_start']} - "
                  f"{zone_result['peak_hours']['peak_end']}")
            print(f"      Best Time:   {zone_result['best_time']['best_hour']}")
            print(f"      Utilization: {zone_result['utilization_avg']}%")
            if zone_result['anomalies']:
                print(f"      Anomalies:   {len(zone_result['anomalies'])} detected")
            print(f"      Models Saved:{zone_result['models_saved']}")

    # Generate recommendations
    print("\n" + "-" * 70)
    print("  Generating Smart Recommendations...")
    recs = generate_all_recommendations()
    for rec in recs:
        print(f"    [{rec['category']:15s}] {rec['message'][:80]}")

    print("\n" + "=" * 70)
    print("  [OK] ML Engine verification complete")
    print("=" * 70)
