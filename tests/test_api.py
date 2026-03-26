"""
Unit Tests — Flask API Endpoints v2.0
Tests all REST API routes using Flask's test client.
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, update_status, log_event, save_prediction
from backend.app import app

# Minimal location config for API tests
TEST_LOCATIONS = [
    {
        "location_id": "LOC_API",
        "name": "API Test Lot",
        "address": "API Street",
        "city": "TestCity",
        "latitude": 30.0,
        "longitude": 76.0,
        "location_type": "MALL",
        "operating_hours": "00:00-23:59",
        "pricing": {"rate_per_hour": 50, "rate_per_day": 300, "currency": "INR"},
        "zones": [
            {"zone_id": "Z_API_A", "zone_name": "Test Zone A", "max_capacity": 100},
        ]
    }
]


@pytest.fixture
def db_setup(tmp_path):
    """Set up a temp database and configure the app to use it."""
    db_path = str(tmp_path / "api_test.db")
    init_db(db_path, TEST_LOCATIONS)

    # Seed some data
    update_status(db_path, "Z_API_A", 30, 100)
    log_event(db_path, "Z_API_A", "ENTRY", 30)
    save_prediction(db_path, "Z_API_A", 45, "08:00", "10:00", 55.0,
                    model_type="random_forest", mae=2.5)

    # Monkey-patch the DB path
    import backend.app as app_module
    original_db = getattr(app_module, 'DB_PATH', None)
    app_module.DB_PATH = db_path

    yield db_path

    if original_db is not None:
        app_module.DB_PATH = original_db


@pytest.fixture
def client(db_setup):
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _auth_headers(client, db_path):
    """Helper to register a user and return auth headers."""
    res = client.post('/api/auth/register', json={
        'name': 'Test User',
        'email': f'test_{id(client)}@example.com',
        'password': 'password123'
    })
    data = json.loads(res.data)
    token = data['data']['token']
    return {'Authorization': f'Bearer {token}'}


# ═══════════════════════════════════════════════
# FRONTEND SERVING
# ═══════════════════════════════════════════════

def test_index_serves_html(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'SmartPark' in res.data


# ═══════════════════════════════════════════════
# LOCATIONS API
# ═══════════════════════════════════════════════

def test_api_locations_returns_list(client):
    res = client.get('/api/locations')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert len(data['data']) == 1
    assert data['data'][0]['name'] == 'API Test Lot'


def test_api_location_detail(client):
    res = client.get('/api/locations/LOC_API')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert data['data']['name'] == 'API Test Lot'
    assert 'zones' in data['data']


def test_api_location_not_found(client):
    res = client.get('/api/locations/FAKE')
    assert res.status_code == 404


def test_api_location_zones(client):
    res = client.get('/api/locations/LOC_API/zones')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert len(data['data']) == 1
    assert data['data'][0]['zone_id'] == 'Z_API_A'


# ═══════════════════════════════════════════════
# DASHBOARD API
# ═══════════════════════════════════════════════

def test_api_zone_status(client):
    res = client.get('/api/dashboard/Z_API_A/status')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['data']['current_count'] == 30


def test_api_zone_status_not_found(client):
    res = client.get('/api/dashboard/Z_FAKE/status')
    assert res.status_code == 404


def test_api_zone_predictions(client):
    res = client.get('/api/dashboard/Z_API_A/predictions')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['data']['predicted_count'] == 45


def test_api_all_statuses(client):
    res = client.get('/api/statuses')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert isinstance(data['data'], list)


# ═══════════════════════════════════════════════
# AUTH API
# ═══════════════════════════════════════════════

def test_api_register(client):
    res = client.post('/api/auth/register', json={
        'name': 'New User',
        'email': 'new@example.com',
        'password': 'secret123'
    })
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert 'token' in data['data']
    assert data['data']['user']['name'] == 'New User'


def test_api_register_duplicate(client):
    client.post('/api/auth/register', json={
        'name': 'First', 'email': 'dup@example.com', 'password': 'pass'
    })
    res = client.post('/api/auth/register', json={
        'name': 'Second', 'email': 'dup@example.com', 'password': 'pass2'
    })
    assert res.status_code == 409


def test_api_login(client):
    client.post('/api/auth/register', json={
        'name': 'Login Test', 'email': 'login@example.com', 'password': 'mypass'
    })
    res = client.post('/api/auth/login', json={
        'email': 'login@example.com', 'password': 'mypass'
    })
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert 'token' in data['data']


def test_api_login_wrong_password(client):
    client.post('/api/auth/register', json={
        'name': 'Wrong', 'email': 'wrong@example.com', 'password': 'correct'
    })
    res = client.post('/api/auth/login', json={
        'email': 'wrong@example.com', 'password': 'incorrect'
    })
    assert res.status_code == 401


def test_api_profile_requires_auth(client):
    res = client.get('/api/auth/profile')
    assert res.status_code == 401


def test_api_profile_with_auth(client, db_setup):
    headers = _auth_headers(client, db_setup)
    res = client.get('/api/auth/profile', headers=headers)
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert 'name' in data['data']


# ═══════════════════════════════════════════════
# CHATBOT API
# ═══════════════════════════════════════════════

def test_api_chatbot_query(client):
    res = client.post('/api/chatbot/query', json={
        'query': 'Help'
    })
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert 'response' in data['data']
    assert data['data']['intent'] == 'HELP'


def test_api_chatbot_requires_query(client):
    res = client.post('/api/chatbot/query', json={})
    assert res.status_code == 400


# ═══════════════════════════════════════════════
# PRICING API
# ═══════════════════════════════════════════════

def test_api_pricing(client):
    res = client.get('/api/pricing/LOC_API?hours=2')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'
    assert data['data']['amount'] == 100  # 2 * 50


# ═══════════════════════════════════════════════
# BOOKINGS API (Phase 4)
# ═══════════════════════════════════════════════

def test_api_create_booking(client, db_setup):
    headers = _auth_headers(client, db_setup)
    res = client.post('/api/bookings/create', json={
        'zone_id': 'Z_API_A',
        'start_time': '2026-03-25T10:00:00+00:00'
    }, headers=headers)
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data['data']['status'] == 'CONFIRMED'
    assert data['data']['zone_id'] == 'Z_API_A'


def test_api_my_bookings(client, db_setup):
    headers = _auth_headers(client, db_setup)
    # Create a booking first
    client.post('/api/bookings/create', json={
        'zone_id': 'Z_API_A',
        'start_time': '2026-03-25T11:00:00+00:00'
    }, headers=headers)
    res = client.get('/api/bookings/my', headers=headers)
    assert res.status_code == 200
    data = json.loads(res.data)
    assert isinstance(data['data'], list)
    assert len(data['data']) >= 1


def test_api_cancel_booking(client, db_setup):
    headers = _auth_headers(client, db_setup)
    # Create then cancel
    create_res = client.post('/api/bookings/create', json={
        'zone_id': 'Z_API_A',
        'start_time': '2026-03-25T12:00:00+00:00'
    }, headers=headers)
    booking_id = json.loads(create_res.data)['data']['booking_id']
    res = client.post(f'/api/bookings/{booking_id}/cancel', headers=headers)
    assert res.status_code == 200


def test_api_create_booking_requires_auth(client):
    res = client.post('/api/bookings/create', json={
        'zone_id': 'Z_API_A',
        'start_time': '2026-03-25T10:00:00+00:00'
    })
    assert res.status_code == 401


# ═══════════════════════════════════════════════
# PAYMENTS API (Phase 4)
# ═══════════════════════════════════════════════

def test_api_create_payment(client, db_setup):
    headers = _auth_headers(client, db_setup)
    # Create a booking first
    create_res = client.post('/api/bookings/create', json={
        'zone_id': 'Z_API_A',
        'start_time': '2026-03-25T13:00:00+00:00'
    }, headers=headers)
    booking_id = json.loads(create_res.data)['data']['booking_id']
    # Create payment
    res = client.post('/api/payments/create', json={
        'booking_id': booking_id,
        'amount': 150.0,
        'method': 'SIMULATED'
    }, headers=headers)
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data['data']['status'] == 'PENDING'
    assert data['data']['amount'] == 150.0


def test_api_process_payment(client, db_setup):
    headers = _auth_headers(client, db_setup)
    # Create booking + payment
    create_res = client.post('/api/bookings/create', json={
        'zone_id': 'Z_API_A',
        'start_time': '2026-03-25T14:00:00+00:00'
    }, headers=headers)
    booking_id = json.loads(create_res.data)['data']['booking_id']
    pay_res = client.post('/api/payments/create', json={
        'booking_id': booking_id, 'amount': 100.0
    }, headers=headers)
    payment_id = json.loads(pay_res.data)['data']['payment_id']
    # Process payment
    res = client.post(f'/api/payments/{payment_id}/process', headers=headers)
    assert res.status_code == 200


def test_api_payment_history(client, db_setup):
    headers = _auth_headers(client, db_setup)
    res = client.get('/api/payments/history', headers=headers)
    assert res.status_code == 200
    data = json.loads(res.data)
    assert isinstance(data['data'], list)


# ═══════════════════════════════════════════════
# ADDITIONAL ENDPOINT COVERAGE (Phase 6)
# ═══════════════════════════════════════════════

def test_api_location_status(client):
    res = client.get('/api/locations/LOC_API/status')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['data']['location_id'] == 'LOC_API'
    assert 'total_capacity' in data['data']
    assert 'zones' in data['data']


def test_api_zone_history(client):
    res = client.get('/api/dashboard/Z_API_A/history?hours=24')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert isinstance(data['data'], list)


def test_api_zone_recommendation(client):
    res = client.get('/api/dashboard/Z_API_A/recommendation')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'


def test_api_all_recommendations(client):
    res = client.get('/api/recommendations')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'ok'


def test_api_profile_invalid_token(client):
    """Invalid token returns 403."""
    res = client.get('/api/auth/profile',
                     headers={'Authorization': 'Bearer fake_token'})
    assert res.status_code == 403
