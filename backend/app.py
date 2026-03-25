"""
Smart Parking System — Flask Backend + WebSocket + API
Single entry point: python -m backend.app [--simulate] [--port 5000]
"""

import sys
import os
import logging
import argparse

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import (
    FLASK_PORT, DB_PATH, PARKING_ID,
    MAX_CAPACITY, PARKING_NAME
)
from backend.database import (
    init_db, get_status, get_history,
    get_latest_prediction, get_daily_summaries,
    get_hourly_averages
)
from backend.serial_bridge import SerialBridge
from backend.ml_engine import run_full_prediction

# ═══════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('SmartParking')


# ═══════════════════════════════════════════════════════════
# APP INITIALIZATION
# ═══════════════════════════════════════════════════════════

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'frontend'
)

app = Flask(__name__,
            static_folder=FRONTEND_DIR,
            static_url_path='')
app.config['SECRET_KEY'] = 'smart-parking-prototype-2026'

socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

bridge = None  # SerialBridge instance


# ═══════════════════════════════════════════════════════════
# SERVE FRONTEND
# ═══════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Serves the dashboard HTML."""
    return send_from_directory(app.static_folder, 'index.html')


# ═══════════════════════════════════════════════════════════
# REST API ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.route('/api/status')
def api_status():
    """Returns current live parking status."""
    status = get_status(DB_PATH, PARKING_ID)
    if not status:
        return jsonify({
            "status": "ok",
            "data": {
                "parking_id": PARKING_ID,
                "current_count": 0,
                "available_slots": MAX_CAPACITY,
                "utilization_percent": 0.0,
                "is_full": False,
                "max_capacity": MAX_CAPACITY,
                "last_updated": None
            }
        })
    return jsonify({"status": "ok", "data": dict(status)})


@app.route('/api/history')
def api_history():
    """Returns recent occupancy events.
    Query param: hours (default 24)
    """
    hours = request.args.get('hours', 24, type=int)
    events = get_history(DB_PATH, PARKING_ID, hours=hours)
    return jsonify({"status": "ok", "data": events})


@app.route('/api/predictions')
def api_predictions():
    """Returns latest ML prediction."""
    pred = get_latest_prediction(DB_PATH, PARKING_ID)
    return jsonify({"status": "ok", "data": pred})


@app.route('/api/analytics/daily')
def api_daily():
    """Returns daily summaries.
    Query param: days (default 7)
    """
    days = request.args.get('days', 7, type=int)
    summaries = get_daily_summaries(DB_PATH, PARKING_ID, days=days)
    return jsonify({"status": "ok", "data": summaries})


@app.route('/api/analytics/hourly')
def api_hourly():
    """Returns hourly average occupancy data."""
    hourly = get_hourly_averages(DB_PATH, PARKING_ID)
    return jsonify({"status": "ok", "data": hourly})


@app.route('/api/ml/run', methods=['POST'])
def api_run_ml():
    """Triggers ML prediction cycle manually."""
    try:
        result = run_full_prediction(PARKING_ID, DB_PATH)
        return jsonify({"status": "ok", "data": result})
    except Exception as e:
        logger.error(f"ML run failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# WEBSOCKET HANDLERS
# ═══════════════════════════════════════════════════════════

@socketio.on('connect')
def handle_connect():
    """On client connect: send current status immediately."""
    status = get_status(DB_PATH, PARKING_ID)
    if status:
        payload = {
            "parking_id": status["parking_id"],
            "current_count": status["current_count"],
            "available_slots": status["available_slots"],
            "utilization_percent": status["utilization_percent"],
            "is_full": status["is_full"],
            "max_capacity": status.get("max_capacity", MAX_CAPACITY),
            "last_event": "CONNECT",
            "last_updated": status["last_updated"]
        }
        emit('parking_update', payload)
    logger.info("WebSocket client connected")


@socketio.on('disconnect')
def handle_disconnect():
    logger.info("WebSocket client disconnected")


# ═══════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════

def create_and_run(simulate: bool = False, port: int = FLASK_PORT,
                   serial_port: str = None):
    """Creates app, starts bridge, runs server."""
    global bridge

    # Override serial port if specified
    if serial_port:
        from backend import config
        config.SERIAL_PORT = serial_port

    # Initialize database
    logger.info("Initializing database...")
    init_db(DB_PATH, PARKING_ID, PARKING_NAME, MAX_CAPACITY)

    # Start serial bridge
    bridge = SerialBridge(socketio, simulate=simulate)
    bridge.start()

    mode = "SIMULATION" if simulate else "LIVE (Arduino)"
    print(f"\n{'='*60}")
    print(f"  SMART PARKING SYSTEM")
    print(f"  Mode:      {mode}")
    print(f"  Dashboard: http://localhost:{port}")
    print(f"  API:       http://localhost:{port}/api/status")
    print(f"{'='*60}\n")

    # Run Flask with SocketIO
    socketio.run(app, host='0.0.0.0', port=port,
                 debug=False, allow_unsafe_werkzeug=True)


# ═══════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Smart Parking Server')
    parser.add_argument('--simulate', action='store_true',
                        help='Run without Arduino (fake events)')
    parser.add_argument('--port', type=int, default=FLASK_PORT,
                        help=f'Server port (default {FLASK_PORT})')
    parser.add_argument('--serial', type=str, default=None,
                        help='Override serial port (e.g. COM4)')
    parser.add_argument('--generate-data', action='store_true',
                        help='Generate synthetic training data and exit')
    parser.add_argument('--run-ml', action='store_true',
                        help='Run ML prediction cycle and exit')
    args = parser.parse_args()

    if args.generate_data:
        from backend.data_generator import generate_dataset
        init_db(DB_PATH, PARKING_ID, PARKING_NAME, MAX_CAPACITY)
        generate_dataset("2026-03-10", 14)
        print("\nData generated. Run without --generate-data to start server.")
        sys.exit(0)

    if args.run_ml:
        init_db(DB_PATH, PARKING_ID, PARKING_NAME, MAX_CAPACITY)
        result = run_full_prediction()
        print(f"ML Result: {result}")
        sys.exit(0)

    create_and_run(simulate=args.simulate, port=args.port,
                   serial_port=args.serial)
