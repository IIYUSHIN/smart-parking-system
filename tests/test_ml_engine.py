"""
Unit Tests — ML Engine
Tests data loading, feature engineering, models, and prediction pipeline.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, log_event
from backend.ml_engine import (
    load_training_data, compute_hourly_occupancy,
    compute_features_for_prediction,
    MovingAveragePredictor, TimeRegressionModel,
    detect_peak_hours, compute_overall_utilization,
    run_full_prediction
)

PARKING_ID = "TEST_ML"
MAX_CAP = 4


@pytest.fixture
def db_with_data(tmp_path):
    """Creates a DB with enough synthetic data for ML training."""
    path = str(tmp_path / "ml_test.db")
    init_db(path, PARKING_ID, "Test ML", MAX_CAP)

    # Generate simple pattern: entries in morning, exits in evening
    from datetime import datetime, timezone
    count = 0
    for day in range(7):
        for hour in range(24):
            for _ in range(2):  # 2 events per hour
                if hour < 12 and count < MAX_CAP:
                    count += 1
                    log_event(path, PARKING_ID, "ENTRY", count,
                              event_time=f"2026-03-{10+day:02d}T{hour:02d}:30:00+00:00")
                elif hour >= 12 and count > 0:
                    count -= 1
                    log_event(path, PARKING_ID, "EXIT", count,
                              event_time=f"2026-03-{10+day:02d}T{hour:02d}:30:00+00:00")
    return path


# ── MOVING AVERAGE ──

def test_moving_average_with_3_values():
    ma = MovingAveragePredictor(window=3)
    result = ma.predict([1.0, 2.0, 3.0])
    assert result == 2.0


def test_moving_average_uses_last_window():
    ma = MovingAveragePredictor(window=3)
    result = ma.predict([0.0, 0.0, 1.0, 2.0, 3.0])
    assert result == 2.0


def test_moving_average_with_fewer_values():
    ma = MovingAveragePredictor(window=3)
    result = ma.predict([5.0])
    assert result == 5.0


# ── LINEAR REGRESSION ──

def test_regression_trains_without_error(db_with_data):
    df = load_training_data(PARKING_ID, db_with_data)
    hourly = compute_hourly_occupancy(df)
    model = TimeRegressionModel()
    mae = model.train(hourly)
    assert mae >= 0
    assert model.is_trained is True


def test_prediction_clamped_to_capacity(db_with_data):
    df = load_training_data(PARKING_ID, db_with_data)
    hourly = compute_hourly_occupancy(df)
    model = TimeRegressionModel()
    model.train(hourly)
    for hour in range(24):
        pred = model.predict(hour)
        assert 0 <= pred <= MAX_CAP


# ── DATA LOADING ──

def test_load_training_data_has_features(db_with_data):
    df = load_training_data(PARKING_ID, db_with_data)
    assert not df.empty
    assert 'hour' in df.columns
    assert 'day_of_week' in df.columns
    assert 'is_weekend' in df.columns


def test_compute_hourly_returns_data(db_with_data):
    df = load_training_data(PARKING_ID, db_with_data)
    hourly = compute_hourly_occupancy(df)
    assert not hourly.empty
    assert 'avg_occupancy' in hourly.columns
    assert 'net_flow' in hourly.columns


def test_features_include_rolling_avg(db_with_data):
    df = load_training_data(PARKING_ID, db_with_data)
    hourly = compute_hourly_occupancy(df)
    featured = compute_features_for_prediction(hourly)
    assert 'rolling_avg_3' in featured.columns
    assert 'utilization_pct' in featured.columns
