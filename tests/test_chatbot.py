"""
Unit Tests — AI Chatbot v2.0
Tests intent classification, location extraction, hour extraction,
and response generation for all 10 intents.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db
from backend.chatbot import (
    classify_intent, _extract_location, _extract_hour,
    process_query
)

# Minimal location config for chatbot tests
TEST_LOCATIONS = [
    {
        "location_id": "LOC_MALL",
        "name": "Elante Mall",
        "address": "Test Address",
        "city": "Chandigarh",
        "latitude": 30.0,
        "longitude": 76.0,
        "location_type": "MALL",
        "operating_hours": "00:00-23:59",
        "pricing": {"rate_per_hour": 50, "rate_per_day": 300, "currency": "INR"},
        "zones": [
            {"zone_id": "Z_MALL_G", "zone_name": "Ground Floor", "max_capacity": 120},
            {"zone_id": "Z_MALL_B", "zone_name": "Basement P1", "max_capacity": 80},
        ]
    },
    {
        "location_id": "LOC_AIRPORT",
        "name": "Delhi Airport T3",
        "address": "IGI Airport",
        "city": "Delhi",
        "latitude": 28.0,
        "longitude": 77.0,
        "location_type": "AIRPORT",
        "operating_hours": "00:00-23:59",
        "pricing": {"rate_per_hour": 100, "rate_per_day": 600, "currency": "INR"},
        "zones": [
            {"zone_id": "Z_AIR_T3", "zone_name": "Terminal 3 Lot", "max_capacity": 300},
        ]
    }
]


@pytest.fixture
def db_path(tmp_path):
    """Creates a fresh database for chatbot tests."""
    path = str(tmp_path / "chatbot_test.db")
    init_db(path, TEST_LOCATIONS)
    return path


# ═══════════════════════════════════════════════
# INTENT CLASSIFICATION
# ═══════════════════════════════════════════════

def test_intent_availability():
    assert classify_intent("Is the mall parking full?") == "CHECK_AVAILABILITY"


def test_intent_availability_spots():
    assert classify_intent("How many spots at the airport?") == "CHECK_AVAILABILITY"


def test_intent_best_time():
    assert classify_intent("Best time to visit the mall?") == "BEST_TIME"


def test_intent_compare():
    assert classify_intent("Compare all parking locations") == "COMPARE"


def test_intent_price():
    assert classify_intent("How much is parking at the mall?") == "PRICE"


def test_intent_predict():
    assert classify_intent("Will the airport be full at 7 PM?") == "PREDICT"


def test_intent_book():
    assert classify_intent("Reserve a parking spot") == "BOOK"


def test_intent_my_bookings():
    assert classify_intent("List my reservation history") == "MY_BOOKINGS"


def test_intent_cancel():
    assert classify_intent("Cancel now") == "CANCEL"


def test_intent_help():
    assert classify_intent("Help") == "HELP"


def test_intent_unknown():
    assert classify_intent("Tell me a joke please") == "UNKNOWN"


# ═══════════════════════════════════════════════
# LOCATION EXTRACTION
# ═══════════════════════════════════════════════

def test_extract_location_mall():
    assert _extract_location("Is the mall full?") == "LOC_MALL"


def test_extract_location_airport():
    assert _extract_location("How busy is the airport?") == "LOC_AIRPORT"


def test_extract_location_elante():
    assert _extract_location("Parking at Elante?") == "LOC_MALL"


def test_extract_location_none():
    assert _extract_location("Is parking available?") is None


# ═══════════════════════════════════════════════
# HOUR EXTRACTION
# ═══════════════════════════════════════════════

def test_extract_hour_7pm():
    assert _extract_hour("at 7 PM") == 19


def test_extract_hour_3am():
    assert _extract_hour("at 3 AM") == 3


def test_extract_hour_noon():
    assert _extract_hour("at 12 PM") == 12


def test_extract_hour_none():
    assert _extract_hour("sometime today") is None


# ═══════════════════════════════════════════════
# FULL QUERY PROCESSING
# ═══════════════════════════════════════════════

def test_process_query_help(db_path):
    result = process_query("Help", db_path)
    assert result['intent'] == "HELP"
    assert 'response' in result
    assert len(result['response']) > 20


def test_process_query_availability(db_path):
    result = process_query("Is the mall full?", db_path)
    assert result['intent'] == "CHECK_AVAILABILITY"
    assert result['location_id'] == "LOC_MALL"
    assert 'response' in result


def test_process_query_compare(db_path):
    result = process_query("Compare all parking", db_path)
    assert result['intent'] == "COMPARE"
    assert 'response' in result


def test_process_query_price(db_path):
    result = process_query("How much is parking at the airport?", db_path)
    assert result['intent'] == "PRICE"
    assert result['location_id'] == "LOC_AIRPORT"


def test_process_query_unknown(db_path):
    result = process_query("Tell me a joke", db_path)
    assert result['intent'] == "UNKNOWN"
    assert 'response' in result


def test_process_query_book_without_login(db_path):
    result = process_query("Reserve a parking spot", db_path, user_id=None)
    assert result['intent'] == "BOOK"
    assert "log in" in result['response'].lower() or "login" in result['response'].lower()
