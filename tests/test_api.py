"""
Unit Tests — Flask API Endpoints
Tests all REST API routes using Flask test client.
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, update_status, log_event, save_prediction
from backend.app import app, socketio

PARKING_ID = "MODEL_01"
MAX_CAP = 4


@pytest.fixture
def db_setup(tmp_path):
    """Set up a temp database and configure the app to use it."""
    db_path = str(tmp_path / "api_test.db")
    init_db(db_path, PARKING_ID, "Test Parking", MAX_CAP)

    # Seed some data
    update_status(db_path, PARKING_ID, 2, MAX_CAP)
    log_event(db_path, PARKING_ID, "ENTRY", 2)
    save_prediction(db_path, PARKING_ID, 3, "08:00", "10:00", 55.0)

    # Monkey-patch the DB path in the app module
    import backend.app as app_module
    original_db = app_module.DB_PATH
    app_module.DB_PATH = db_path

    yield db_path

    app_module.DB_PATH = original_db


@pytest.fixture
def client(db_setup):
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# ── API TESTS ──

def test_api_status_returns_ok(client):
    res = client.get('/api/status')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert 'data' in data
    assert data['data']['current_count'] == 2


def test_api_history_returns_events(client):
    res = client.get('/api/history?hours=24')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert isinstance(data['data'], list)


def test_api_predictions_returns_data(client):
    res = client.get('/api/predictions')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert data['data']['predicted_count'] == 3


def test_api_daily_returns_list(client):
    res = client.get('/api/analytics/daily?days=7')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert isinstance(data['data'], list)


def test_api_hourly_returns_list(client):
    res = client.get('/api/analytics/hourly')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert isinstance(data['data'], list)


def test_index_serves_html(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'Smart Parking' in res.data
