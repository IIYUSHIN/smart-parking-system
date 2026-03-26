"""
Unit Tests — ML Engine v2.0
Tests per-zone models, recommendation engine, anomaly detection,
peak detection, and best time finder.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, batch_log_events
from backend.ml_engine import (
    load_training_data, compute_hourly_occupancy,
    MovingAveragePredictor, ZoneLinearModel, ZoneRandomForest,
    generate_recommendation, detect_peak_hours, find_best_time,
    compute_overall_utilization
)

# Minimal location config for ML tests
TEST_LOCATIONS = [
    {
        "location_id": "LOC_ML",
        "name": "ML Test Lot",
        "address": "1 ML Drive",
        "city": "TestCity",
        "latitude": 30.0,
        "longitude": 76.0,
        "location_type": "MALL",
        "operating_hours": "00:00-23:59",
        "pricing": {"rate_per_hour": 50, "rate_per_day": 300, "currency": "INR"},
        "zones": [
            {"zone_id": "Z_ML_A", "zone_name": "Test Zone", "max_capacity": 100},
        ]
    }
]


@pytest.fixture
def db_with_data(tmp_path):
    """Creates a DB with enough events for ML training."""
    path = str(tmp_path / "ml_test.db")
    init_db(path, TEST_LOCATIONS)

    # Generate 7 days of events with a clear morning/evening pattern
    events = []
    count = 0
    for day in range(7):
        count = 0  # Reset each day
        for hour in range(24):
            for minute in [15, 45]:
                if hour < 12 and count < 80:
                    count += 3
                    events.append((
                        "Z_ML_A", "ENTRY",
                        f"2026-03-{10+day:02d}T{hour:02d}:{minute:02d}:00+00:00",
                        min(count, 100)
                    ))
                elif hour >= 12 and count > 0:
                    count = max(0, count - 3)
                    events.append((
                        "Z_ML_A", "EXIT",
                        f"2026-03-{10+day:02d}T{hour:02d}:{minute:02d}:00+00:00",
                        count
                    ))
    batch_log_events(path, events)
    return path


# ═══════════════════════════════════════════════
# MOVING AVERAGE PREDICTOR
# ═══════════════════════════════════════════════

def test_moving_average_basic():
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


def test_moving_average_empty():
    ma = MovingAveragePredictor(window=3)
    result = ma.predict([])
    assert result == 0.0


# ═══════════════════════════════════════════════
# ZONE LINEAR MODEL
# ═══════════════════════════════════════════════

def test_linear_model_trains(db_with_data):
    df = load_training_data("Z_ML_A", db_with_data)
    hourly = compute_hourly_occupancy(df)
    model = ZoneLinearModel("Z_ML_A", 100)
    mae = model.train(hourly)
    assert mae >= 0
    assert model.is_trained is True


def test_linear_model_prediction_clamped(db_with_data):
    df = load_training_data("Z_ML_A", db_with_data)
    hourly = compute_hourly_occupancy(df)
    model = ZoneLinearModel("Z_ML_A", 100)
    model.train(hourly)
    for hour in range(24):
        pred = model.predict(hour)
        assert 0 <= pred <= 100, f"Prediction {pred} out of bounds at hour {hour}"


def test_linear_model_predict_all_hours(db_with_data):
    df = load_training_data("Z_ML_A", db_with_data)
    hourly = compute_hourly_occupancy(df)
    model = ZoneLinearModel("Z_ML_A", 100)
    model.train(hourly)
    predictions = model.predict_all_hours()
    assert len(predictions) == 24
    assert all('hour' in p and 'predicted' in p for p in predictions)


def test_linear_model_not_trained_raises():
    model = ZoneLinearModel("Z_UNTRAINED", 100)
    with pytest.raises(RuntimeError, match="not trained"):
        model.predict(10)


# ═══════════════════════════════════════════════
# RANDOM FOREST MODEL
# ═══════════════════════════════════════════════

def test_random_forest_trains(db_with_data):
    df = load_training_data("Z_ML_A", db_with_data)
    hourly = compute_hourly_occupancy(df)
    model = ZoneRandomForest("Z_ML_A", 100)
    mae = model.train(hourly)
    assert mae >= 0
    assert model.is_trained is True


def test_random_forest_prediction_clamped(db_with_data):
    df = load_training_data("Z_ML_A", db_with_data)
    hourly = compute_hourly_occupancy(df)
    model = ZoneRandomForest("Z_ML_A", 100)
    model.train(hourly)
    pred = model.predict(10, day_of_week=2, is_weekend=False)
    assert 0 <= pred <= 100


def test_random_forest_not_trained_raises():
    model = ZoneRandomForest("Z_UNTRAINED", 100)
    with pytest.raises(RuntimeError, match="not trained"):
        model.predict(10)


# ═══════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════

def test_load_training_data_has_features(db_with_data):
    df = load_training_data("Z_ML_A", db_with_data)
    assert not df.empty
    assert 'hour' in df.columns
    assert 'day_of_week' in df.columns
    assert 'is_weekend' in df.columns


def test_load_training_data_empty_zone(db_with_data):
    df = load_training_data("Z_NONEXISTENT", db_with_data)
    assert df.empty


def test_compute_hourly_returns_data(db_with_data):
    df = load_training_data("Z_ML_A", db_with_data)
    hourly = compute_hourly_occupancy(df)
    assert not hourly.empty
    assert 'avg_occupancy' in hourly.columns
    assert 'net_flow' in hourly.columns


# ═══════════════════════════════════════════════
# RECOMMENDATION ENGINE
# ═══════════════════════════════════════════════

def test_recommendation_calm():
    rec = generate_recommendation("Z1", "Zone 1", 20.0, 80, 100)
    assert rec['category'] == "CALM"
    assert "plenty" in rec['message'].lower() or "great" in rec['message'].lower()


def test_recommendation_informational():
    rec = generate_recommendation("Z1", "Zone 1", 50.0, 50, 100)
    assert rec['category'] == "INFORMATIONAL"


def test_recommendation_alert():
    rec = generate_recommendation("Z1", "Zone 1", 75.0, 25, 100)
    assert rec['category'] == "ALERT"


def test_recommendation_urgent():
    rec = generate_recommendation("Z1", "Zone 1", 88.0, 12, 100)
    assert rec['category'] == "URGENT"


def test_recommendation_critical():
    rec = generate_recommendation("Z1", "Zone 1", 95.0, 5, 100)
    assert rec['category'] == "CRITICAL"


def test_recommendation_full_redirect():
    rec = generate_recommendation("Z1", "Zone 1", 100.0, 0, 100)
    assert rec['category'] == "FULL_REDIRECT"
    assert "full" in rec['message'].lower()


# ═══════════════════════════════════════════════
# PEAK + BEST TIME
# ═══════════════════════════════════════════════

def test_detect_peak_hours(db_with_data):
    peaks = detect_peak_hours("Z_ML_A", db_with_data)
    assert 'peak_start' in peaks
    assert 'peak_end' in peaks
    assert peaks['peak_avg_occupancy'] > 0


def test_detect_peak_hours_no_data(db_with_data):
    peaks = detect_peak_hours("Z_NONEXISTENT", db_with_data)
    assert peaks['peak_start'] == "N/A"


def test_find_best_time(db_with_data):
    best = find_best_time("Z_ML_A", db_with_data)
    assert 'best_hour' in best
    assert best['best_hour'] != "N/A"
    assert best['expected_occupancy'] >= 0


def test_compute_overall_utilization(db_with_data):
    util = compute_overall_utilization("Z_ML_A", 100, db_with_data)
    assert 0 <= util <= 100
