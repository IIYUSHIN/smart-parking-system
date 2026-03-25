"""
Smart Parking System — Global Configuration
All decisions locked per execution_blueprint.md
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Serial ──
SERIAL_PORT = "COM3"          # User adjusts per system
BAUD_RATE = 9600
SERIAL_TIMEOUT = 1            # seconds

# ── Database ──
DB_PATH = os.path.join(BASE_DIR, "data", "smart_parking.db")

# ── Parking ──
PARKING_ID = "MODEL_01"
PARKING_NAME = "Smart Parking Prototype"
MAX_CAPACITY = 4

# ── Flask ──
FLASK_PORT = 5000
FLASK_DEBUG = False

# ── ML ──
MODEL_PATH = os.path.join(BASE_DIR, "models", "occupancy_model.pkl")
PREDICTION_HORIZON_HOURS = 1
MOVING_AVG_WINDOW = 3

# ── Simulation ──
SIMULATE_MODE = False
SIMULATE_INTERVAL_MIN = 5     # seconds
SIMULATE_INTERVAL_MAX = 15    # seconds
