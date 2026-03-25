"""
Smart Parking System — AI/ML Engine
Models: MovingAveragePredictor + TimeRegressionModel
Pipeline: load data -> engineer features -> train -> predict -> detect peaks
"""

import os
import sys
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    get_connection, get_hourly_averages, get_all_events,
    save_prediction, get_connection
)
from backend.config import (
    DB_PATH, PARKING_ID, MAX_CAPACITY,
    MODEL_PATH, MOVING_AVG_WINDOW
)


# ═══════════════════════════════════════════════════════════
# UNIT 07 — DATA LOADER + FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════

def load_training_data(parking_id: str = PARKING_ID,
                       db_path: str = DB_PATH) -> pd.DataFrame:
    """Loads occupancy_log into DataFrame with engineered features.

    Columns: event_id, event_type, event_time, occupancy_after,
             hour, day_of_week, is_weekend, minute_of_day
    """
    events = get_all_events(db_path, parking_id)
    if not events:
        return pd.DataFrame()

    df = pd.DataFrame(events)
    df['event_time'] = pd.to_datetime(df['event_time'])
    df['hour'] = df['event_time'].dt.hour
    df['day_of_week'] = df['event_time'].dt.dayofweek  # 0=Mon, 6=Sun
    df['is_weekend'] = df['day_of_week'] >= 5
    df['minute_of_day'] = df['event_time'].dt.hour * 60 + df['event_time'].dt.minute
    df['date'] = df['event_time'].dt.strftime('%Y-%m-%d')

    return df


def compute_hourly_occupancy(df: pd.DataFrame) -> pd.DataFrame:
    """Groups by date + hour, computes average occupancy per hour.

    Returns: date, hour, avg_occupancy, entry_count, exit_count, net_flow
    """
    if df.empty:
        return pd.DataFrame()

    hourly = df.groupby(['date', 'hour']).agg(
        avg_occupancy=('occupancy_after', 'mean'),
        entry_count=('event_type', lambda x: (x == 'ENTRY').sum()),
        exit_count=('event_type', lambda x: (x == 'EXIT').sum()),
        event_count=('event_id', 'count')
    ).reset_index()

    hourly['net_flow'] = hourly['entry_count'] - hourly['exit_count']
    return hourly


def compute_features_for_prediction(hourly_df: pd.DataFrame) -> pd.DataFrame:
    """Adds ML features: rolling average, lag features, utilization."""
    if hourly_df.empty:
        return hourly_df

    df = hourly_df.copy()
    df['rolling_avg_3'] = df['avg_occupancy'].rolling(
        window=MOVING_AVG_WINDOW, min_periods=1).mean()
    df['prev_hour_occ'] = df['avg_occupancy'].shift(1).fillna(0)
    df['prev_2_hour_occ'] = df['avg_occupancy'].shift(2).fillna(0)
    df['utilization_pct'] = (df['avg_occupancy'] / MAX_CAPACITY) * 100

    return df


# ═══════════════════════════════════════════════════════════
# UNIT 08 — MOVING AVERAGE PREDICTOR
# ═══════════════════════════════════════════════════════════

class MovingAveragePredictor:
    """Simple 3-point moving average model.
    Formula: (O(t) + O(t-1) + O(t-2)) / 3
    """

    def __init__(self, window: int = MOVING_AVG_WINDOW):
        self.window = window

    def predict(self, recent_values: list) -> float:
        """Takes last `window` occupancy values, returns average.

        Args:
            recent_values: list of floats, most recent last
        Returns:
            Predicted occupancy for next period (float)
        """
        if len(recent_values) < self.window:
            # Use whatever we have
            return sum(recent_values) / len(recent_values) if recent_values else 0.0
        return sum(recent_values[-self.window:]) / self.window


# ═══════════════════════════════════════════════════════════
# UNIT 09 — LINEAR REGRESSION MODEL
# ═══════════════════════════════════════════════════════════

class TimeRegressionModel:
    """Predicts occupancy from hour-of-day using Linear Regression.

    Training X: [[hour], [hour], ...] shape (n, 1)
    Training y: [avg_occupancy, ...] shape (n,)
    """

    def __init__(self):
        self.model = LinearRegression()
        self.is_trained = False
        self.mae = None

    def train(self, hourly_df: pd.DataFrame) -> float:
        """Trains on hourly occupancy data.

        Args:
            hourly_df: must have 'hour' and 'avg_occupancy' columns
        Returns:
            MAE on training data (float)
        """
        if hourly_df.empty or len(hourly_df) < 5:
            raise ValueError("Need at least 5 hourly data points to train")

        X = hourly_df[['hour']].values
        y = hourly_df['avg_occupancy'].values.astype(float)

        self.model.fit(X, y)
        predictions = self.model.predict(X)
        self.mae = float(mean_absolute_error(y, predictions))
        self.is_trained = True
        return self.mae

    def predict(self, hour: int) -> float:
        """Predicts occupancy for given hour.
        Returns: predicted occupancy clamped to [0, MAX_CAPACITY]
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained yet")
        raw = self.model.predict([[hour]])[0]
        return max(0.0, min(float(MAX_CAPACITY), round(float(raw), 1)))

    def save(self, path: str) -> None:
        """Saves model to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)

    def load(self, path: str) -> None:
        """Loads model from disk."""
        self.model = joblib.load(path)
        self.is_trained = True


# ═══════════════════════════════════════════════════════════
# UNIT 10 — PREDICTION PIPELINE + PEAK DETECTION
# ═══════════════════════════════════════════════════════════

def detect_peak_hours(parking_id: str = PARKING_ID,
                      db_path: str = DB_PATH) -> dict:
    """Finds busiest and quietest hours from historical data.

    Returns: {peak_start, peak_end, peak_avg_occupancy,
              low_start, low_end}
    """
    hourly_avgs = get_hourly_averages(db_path, parking_id)
    if not hourly_avgs:
        return {
            "peak_start": "N/A", "peak_end": "N/A",
            "peak_avg_occupancy": 0,
            "low_start": "N/A", "low_end": "N/A"
        }

    # Find hour with highest average
    sorted_by_occ = sorted(hourly_avgs, key=lambda x: x['avg_occupancy'],
                           reverse=True)
    peak_hour = sorted_by_occ[0]['hour']
    peak_avg = round(sorted_by_occ[0]['avg_occupancy'], 1)

    # Find contiguous peak window (hours with > 70% of peak avg)
    threshold = peak_avg * 0.7
    peak_hours = [h['hour'] for h in hourly_avgs
                  if h['avg_occupancy'] >= threshold]
    peak_hours.sort()

    # Find the longest contiguous block containing the peak
    peak_start = peak_hours[0] if peak_hours else peak_hour
    peak_end = peak_hours[-1] + 1 if peak_hours else peak_hour + 1

    # Find quietest hours
    sorted_asc = sorted(hourly_avgs, key=lambda x: x['avg_occupancy'])
    low_hours = [h['hour'] for h in sorted_asc[:4]]
    low_hours.sort()
    low_start = low_hours[0] if low_hours else 0
    low_end = low_hours[-1] + 1 if low_hours else 6

    return {
        "peak_start": f"{peak_start:02d}:00",
        "peak_end": f"{peak_end:02d}:00",
        "peak_avg_occupancy": peak_avg,
        "low_start": f"{low_start:02d}:00",
        "low_end": f"{low_end:02d}:00"
    }


def compute_overall_utilization(parking_id: str = PARKING_ID,
                                db_path: str = DB_PATH) -> float:
    """Returns average utilization % across all data."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT AVG(occupancy_after) as avg_occ FROM occupancy_log "
            "WHERE parking_id = ?",
            (parking_id,)
        ).fetchone()
        avg = row['avg_occ'] if row and row['avg_occ'] is not None else 0
        return round((avg / MAX_CAPACITY) * 100, 1)
    finally:
        conn.close()


def run_full_prediction(parking_id: str = PARKING_ID,
                        db_path: str = DB_PATH) -> dict:
    """Master function — runs complete ML pipeline.

    Steps:
    1. Load training data
    2. Compute hourly occupancy
    3. Engineer features
    4. Train TimeRegressionModel
    5. Predict next hour occupancy
    6. Run MovingAveragePredictor
    7. Detect peak hours
    8. Compute utilization
    9. Save prediction to DB
    10. Save model to disk

    Returns dict with all results.
    """
    # Step 1: Load data
    df = load_training_data(parking_id, db_path)
    if df.empty:
        return {"error": "No training data available"}

    # Step 2: Compute hourly averages
    hourly = compute_hourly_occupancy(df)
    if hourly.empty or len(hourly) < 5:
        return {"error": "Insufficient hourly data for training"}

    # Step 3: Engineer features
    featured = compute_features_for_prediction(hourly)

    # Step 4: Train regression model
    regression = TimeRegressionModel()
    mae = regression.train(hourly)

    # Step 5: Predict next hour (current hour + 1)
    current_hour = datetime.now().hour
    next_hour = (current_hour + 1) % 24
    predicted_regression = regression.predict(next_hour)

    # Step 6: Moving average prediction
    ma_predictor = MovingAveragePredictor()
    recent = hourly['avg_occupancy'].tail(MOVING_AVG_WINDOW).tolist()
    predicted_ma = round(ma_predictor.predict(recent), 1)

    # Step 7: Peak detection
    peaks = detect_peak_hours(parking_id, db_path)

    # Step 8: Overall utilization
    utilization = compute_overall_utilization(parking_id, db_path)

    # Step 9: Save prediction to database
    final_prediction = round((predicted_regression + predicted_ma) / 2)
    final_prediction = max(0, min(MAX_CAPACITY, final_prediction))

    save_prediction(
        db_path, parking_id,
        predicted_count=final_prediction,
        peak_hour_start=peaks["peak_start"],
        peak_hour_end=peaks["peak_end"],
        utilization_avg=utilization
    )

    # Step 10: Save model
    try:
        regression.save(MODEL_PATH)
        model_saved = True
    except Exception:
        model_saved = False

    result = {
        "predicted_count_regression": predicted_regression,
        "predicted_count_moving_avg": predicted_ma,
        "predicted_count_final": final_prediction,
        "mae": round(mae, 3),
        "peak_hours": peaks,
        "utilization_avg": utilization,
        "training_samples": len(hourly),
        "total_events": len(df),
        "model_saved": model_saved
    }

    return result


# ═══════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Running ML prediction pipeline...\n")
    result = run_full_prediction()

    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(f"  Training samples:     {result['training_samples']} hourly records")
        print(f"  Total events:         {result['total_events']}")
        print(f"  MAE:                  {result['mae']}")
        print(f"  Regression prediction:{result['predicted_count_regression']}")
        print(f"  Moving avg prediction:{result['predicted_count_moving_avg']}")
        print(f"  Final prediction:     {result['predicted_count_final']}/4")
        print(f"  Peak hours:           {result['peak_hours']['peak_start']} - "
              f"{result['peak_hours']['peak_end']}")
        print(f"  Overall utilization:  {result['utilization_avg']}%")
        print(f"  Model saved:          {result['model_saved']}")
        print(f"\n  [OK] ML pipeline complete")
