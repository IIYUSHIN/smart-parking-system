"""
Smart Parking System v2.0 — Global Configuration
Multi-location, multi-zone system with AI chatbot, bookings, and payments.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════════════════════
# SERIAL COMMUNICATION (Arduino ↔ Laptop)
# ═══════════════════════════════════════════════════════════
SERIAL_PORT = "COM3"
BAUD_RATE = 9600
SERIAL_TIMEOUT = 1  # seconds


# ═══════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════
DB_PATH = os.path.join(BASE_DIR, "data", "smart_parking.db")


# ═══════════════════════════════════════════════════════════
# FLASK SERVER
# ═══════════════════════════════════════════════════════════
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False
SECRET_KEY = "sp_v2_dev_key_change_in_production"
SESSION_EXPIRY_HOURS = 24


# ═══════════════════════════════════════════════════════════
# ML CONFIGURATION
# ═══════════════════════════════════════════════════════════
MODELS_DIR = os.path.join(BASE_DIR, "models")
PREDICTION_HORIZON_HOURS = 1
MOVING_AVG_WINDOW = 3


# ═══════════════════════════════════════════════════════════
# SIMULATION
# ═══════════════════════════════════════════════════════════
SIMULATE_MODE = False
SIMULATE_INTERVAL_MIN = 5   # seconds between events
SIMULATE_INTERVAL_MAX = 15


# ═══════════════════════════════════════════════════════════
# PARKING LOCATIONS — Master Registry
# Each location represents a real-world parking venue.
# Zones are subdivisions within a location.
# ═══════════════════════════════════════════════════════════
LOCATIONS = [
    {
        "location_id": "LOC_MALL",
        "name": "Elante Mall Parking",
        "address": "Industrial Area Phase I, Chandigarh, 160002",
        "city": "Chandigarh",
        "latitude": 30.7061,
        "longitude": 76.8013,
        "location_type": "MALL",
        "operating_hours": "08:00-23:00",
        "image_url": "/assets/locations/mall.jpg",
        "zones": [
            {"zone_id": "LOC_MALL_GF", "zone_name": "Ground Floor", "max_capacity": 100},
            {"zone_id": "LOC_MALL_B1", "zone_name": "Basement P1", "max_capacity": 100},
        ],
        "pricing": {"rate_per_hour": 40, "rate_per_day": 300, "currency": "INR"},
    },
    {
        "location_id": "LOC_AIRPORT",
        "name": "Delhi Airport T3 Parking",
        "address": "IGI Airport Terminal 3, New Delhi, 110037",
        "city": "New Delhi",
        "latitude": 28.5562,
        "longitude": 77.1000,
        "location_type": "AIRPORT",
        "operating_hours": "00:00-23:59",
        "image_url": "/assets/locations/airport.jpg",
        "zones": [
            {"zone_id": "LOC_AIRPORT_S", "zone_name": "Short-Term Parking", "max_capacity": 200},
            {"zone_id": "LOC_AIRPORT_L", "zone_name": "Long-Term Parking", "max_capacity": 300},
        ],
        "pricing": {"rate_per_hour": 100, "rate_per_day": 800, "currency": "INR"},
    },
    {
        "location_id": "LOC_CORP",
        "name": "Infosys Tech Park Parking",
        "address": "Rajiv Gandhi Chandigarh Technology Park, 160101",
        "city": "Chandigarh",
        "latitude": 30.7632,
        "longitude": 76.7380,
        "location_type": "CORPORATE",
        "operating_hours": "06:00-22:00",
        "image_url": "/assets/locations/corporate.jpg",
        "zones": [
            {"zone_id": "LOC_CORP_MAIN", "zone_name": "Main Parking", "max_capacity": 150},
        ],
        "pricing": {"rate_per_hour": 20, "rate_per_day": 100, "currency": "INR"},
    },
    {
        "location_id": "LOC_UNI",
        "name": "Chandigarh University Campus",
        "address": "NH-95, Gharuan, Mohali, Punjab, 140413",
        "city": "Mohali",
        "latitude": 30.7698,
        "longitude": 76.5727,
        "location_type": "UNIVERSITY",
        "operating_hours": "06:00-21:00",
        "image_url": "/assets/locations/university.jpg",
        "zones": [
            {"zone_id": "LOC_UNI_STU", "zone_name": "Student Parking", "max_capacity": 50},
            {"zone_id": "LOC_UNI_STF", "zone_name": "Staff Parking", "max_capacity": 30},
        ],
        "pricing": {"rate_per_hour": 10, "rate_per_day": 50, "currency": "INR"},
    },
    {
        "location_id": "LOC_HOSP",
        "name": "PGIMER Hospital Parking",
        "address": "Sector 12, Chandigarh, 160012",
        "city": "Chandigarh",
        "latitude": 30.7637,
        "longitude": 76.7757,
        "location_type": "HOSPITAL",
        "operating_hours": "00:00-23:59",
        "image_url": "/assets/locations/hospital.jpg",
        "zones": [
            {"zone_id": "LOC_HOSP_OPD", "zone_name": "OPD Parking", "max_capacity": 80},
            {"zone_id": "LOC_HOSP_EM", "zone_name": "Emergency Parking", "max_capacity": 40},
        ],
        "pricing": {"rate_per_hour": 30, "rate_per_day": 200, "currency": "INR"},
    },
]


# ═══════════════════════════════════════════════════════════
# DERIVED CONSTANTS
# ═══════════════════════════════════════════════════════════
TOTAL_LOCATIONS = len(LOCATIONS)
TOTAL_ZONES = sum(len(loc["zones"]) for loc in LOCATIONS)
TOTAL_CAPACITY = sum(
    zone["max_capacity"]
    for loc in LOCATIONS
    for zone in loc["zones"]
)


# ═══════════════════════════════════════════════════════════
# HARDWARE PROTOTYPE MAPPING
# Maps the physical Arduino (4-slot model) to a specific zone
# for live hardware-in-the-loop demos.
# ═══════════════════════════════════════════════════════════
ARDUINO_ZONE_ID = "LOC_MALL_GF"
ARDUINO_MAX_CAPACITY = 4  # Physical model has 4 slots
