"""
Smart Parking System v2.0 — Production Startup Script (Render.com)

Handles first-run initialization:
  1. Creates database (14 tables) if not present
  2. Generates 30 days of synthetic data (~45K events)
  3. Runs ML predictions for all 9 zones
  4. Starts Flask server in SIMULATION mode

Local development remains unchanged — use `python -m backend.app --simulate` as before.
For viva with Arduino: `python -m backend.app --serial COM3`
"""

import os
import sys

# Ensure correct working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from backend.config import DB_PATH, LOCATIONS
from backend.database import init_db, get_connection
from backend.data_generator import generate_all_data
from backend.ml_engine import run_all_predictions
from backend.app import create_and_run


def needs_data():
    """Check if database needs synthetic data generation."""
    if not os.path.exists(DB_PATH):
        return True
    try:
        conn = get_connection(DB_PATH)
        count = conn.execute(
            "SELECT COUNT(*) FROM occupancy_log"
        ).fetchone()[0]
        conn.close()
        return count < 100
    except Exception:
        return True


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    # ── Step 1: Initialize database ──
    print("[STARTUP] Initializing database...")
    init_db(DB_PATH, LOCATIONS)

    # ── Step 2: Generate data if first run ──
    if needs_data():
        print("[STARTUP] First run detected — generating 30 days of synthetic data...")
        generate_all_data(start_date=None, num_days=30)

        # ── Step 3: Train ML models ──
        print("[STARTUP] Running ML predictions for all zones...")
        try:
            run_all_predictions(DB_PATH)
            print("[STARTUP] ML predictions complete.")
        except Exception as e:
            print(f"[STARTUP] ML warning (non-fatal): {e}")
    else:
        print("[STARTUP] Data already exists, skipping generation.")

    # ── Step 4: Start server ──
    print(f"[STARTUP] Starting server on port {port} (simulation mode)...")
    create_and_run(simulate=True, port=port)
