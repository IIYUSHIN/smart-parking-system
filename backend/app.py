"""
Smart Parking System v2.0 — Flask Backend + WebSocket + REST API

20+ endpoints for: locations, zones, status, auth, bookings,
payments, chatbot, predictions, recommendations.

Entry point: python -m backend.app [--simulate] [--port 5000]
"""

import sys
import os
import logging
import argparse
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import (
    FLASK_PORT, FLASK_HOST, DB_PATH, LOCATIONS,
    SECRET_KEY, ARDUINO_ZONE_ID, ARDUINO_MAX_CAPACITY
)
from backend.database import (
    init_db, get_status, get_history, get_all_statuses,
    get_latest_prediction, get_daily_summaries, get_hourly_averages,
    get_all_locations, get_location, get_zones_for_location,
    get_location_predictions, get_location_events,
    create_user, authenticate_user, get_user_by_id,
    create_session, validate_session, invalidate_session,
    create_booking, get_user_bookings, cancel_booking, complete_booking,
    create_payment, process_payment, get_user_payments,
    calculate_parking_fee, get_latest_recommendation,
    save_recommendation
)
from backend.ml_engine import (
    run_zone_prediction, run_all_predictions,
    generate_recommendation, find_alternative_zone,
    generate_all_recommendations
)
from backend.chatbot import process_query
from backend.serial_bridge import SerialBridge


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
app.config['SECRET_KEY'] = SECRET_KEY

socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
bridge = None


# ═══════════════════════════════════════════════════════════
# AUTH MIDDLEWARE
# ═══════════════════════════════════════════════════════════

def require_auth(f):
    """Decorator that validates session token from Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"status": "error", "message": "No token provided"}), 401
        user = validate_session(DB_PATH, token)
        if not user:
            return jsonify({"status": "error", "message": "Invalid or expired token"}), 403
        request.user = user
        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """Decorator that attaches user if token present, but doesn't require it."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            user = validate_session(DB_PATH, token)
            request.user = user
        else:
            request.user = None
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════
# FRONTEND SERVING (SPA Router)
# ═══════════════════════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def catch_all(path):
    """SPA catch-all: serves index.html for all non-API, non-file routes."""
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


# ═══════════════════════════════════════════════════════════
# API: LOCATIONS
# ═══════════════════════════════════════════════════════════

@app.route('/api/locations')
def api_locations():
    """GET — Returns all parking locations with aggregated data."""
    locations = get_all_locations(DB_PATH)
    return jsonify({"status": "ok", "data": locations})


@app.route('/api/locations/<location_id>')
def api_location_detail(location_id):
    """GET — Returns detailed info for a single location with zone data."""
    loc = get_location(DB_PATH, location_id)
    if not loc:
        return jsonify({"status": "error", "message": "Location not found"}), 404
    return jsonify({"status": "ok", "data": loc})


@app.route('/api/locations/<location_id>/zones')
def api_location_zones(location_id):
    """GET — Returns zones for a location with live status."""
    zones = get_zones_for_location(DB_PATH, location_id)
    return jsonify({"status": "ok", "data": zones})


@app.route('/api/locations/<location_id>/status')
def api_location_status(location_id):
    """GET — Returns aggregated live status for a location."""
    loc = get_location(DB_PATH, location_id)
    if not loc:
        return jsonify({"status": "error", "message": "Location not found"}), 404
    return jsonify({"status": "ok", "data": {
        "location_id": location_id,
        "name": loc["name"],
        "total_capacity": loc["total_capacity"],
        "total_occupied": loc["total_occupied"],
        "total_available": loc["total_available"],
        "utilization_percent": loc["utilization_percent"],
        "is_full": loc["is_full"],
        "zones": loc.get("zones", [])
    }})


# ═══════════════════════════════════════════════════════════
# API: DASHBOARD DATA (Per Zone)
# ═══════════════════════════════════════════════════════════

@app.route('/api/dashboard/<zone_id>/status')
def api_zone_status(zone_id):
    """GET — Returns live status for a specific zone."""
    status = get_status(DB_PATH, zone_id)
    if not status:
        return jsonify({"status": "error", "message": "Zone not found"}), 404
    return jsonify({"status": "ok", "data": status})


@app.route('/api/dashboard/<zone_id>/history')
def api_zone_history(zone_id):
    """GET — Returns recent events for a zone. ?hours=24"""
    hours = request.args.get('hours', 24, type=int)
    events = get_history(DB_PATH, zone_id, hours=hours)
    return jsonify({"status": "ok", "data": events})


@app.route('/api/dashboard/<zone_id>/predictions')
def api_zone_predictions(zone_id):
    """GET — Returns latest ML prediction for a zone."""
    pred = get_latest_prediction(DB_PATH, zone_id)
    return jsonify({"status": "ok", "data": pred})


@app.route('/api/dashboard/<zone_id>/daily')
def api_zone_daily(zone_id):
    """GET — Returns daily summaries for a zone. ?days=7"""
    days = request.args.get('days', 7, type=int)
    summaries = get_daily_summaries(DB_PATH, zone_id, days=days)
    return jsonify({"status": "ok", "data": summaries})


@app.route('/api/dashboard/<zone_id>/hourly')
def api_zone_hourly(zone_id):
    """GET — Returns hourly average occupancy for a zone."""
    hourly = get_hourly_averages(DB_PATH, zone_id)
    return jsonify({"status": "ok", "data": hourly})


@app.route('/api/dashboard/<zone_id>/recommendation')
def api_zone_recommendation(zone_id):
    """GET — Returns latest AI recommendation for a zone."""
    rec = get_latest_recommendation(DB_PATH, zone_id)
    return jsonify({"status": "ok", "data": rec})


@app.route('/api/statuses')
def api_all_statuses():
    """GET — Returns status for all zones across all locations."""
    statuses = get_all_statuses(DB_PATH)
    return jsonify({"status": "ok", "data": statuses})


# ═══════════════════════════════════════════════════════════
# API: AUTHENTICATION
# ═══════════════════════════════════════════════════════════

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """POST — Create a new user account."""
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "JSON body required"}), 400

    required = ['name', 'email', 'password']
    for field in required:
        if not data.get(field):
            return jsonify({"status": "error",
                            "message": f"Missing field: {field}"}), 400

    try:
        user = create_user(
            DB_PATH, data['name'], data['email'], data['password'],
            phone=data.get('phone'), vehicle_plate=data.get('vehicle_plate')
        )
        token = create_session(DB_PATH, user['user_id'])
        return jsonify({
            "status": "ok",
            "data": {"user": user, "token": token}
        }), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 409


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """POST — Login with email + password."""
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"status": "error",
                        "message": "Email and password required"}), 400

    user = authenticate_user(DB_PATH, data['email'], data['password'])
    if not user:
        return jsonify({"status": "error",
                        "message": "Invalid email or password"}), 401

    token = create_session(DB_PATH, user['user_id'])
    return jsonify({"status": "ok", "data": {"user": user, "token": token}})


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def api_logout():
    """POST — Invalidate session token."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    invalidate_session(DB_PATH, token)
    return jsonify({"status": "ok", "message": "Logged out"})


@app.route('/api/auth/profile')
@require_auth
def api_profile():
    """GET — Returns current user's profile."""
    return jsonify({"status": "ok", "data": request.user})


# ═══════════════════════════════════════════════════════════
# API: BOOKINGS
# ═══════════════════════════════════════════════════════════

@app.route('/api/bookings/create', methods=['POST'])
@require_auth
def api_create_booking():
    """POST — Create a parking booking."""
    data = request.get_json()
    if not data or not data.get('zone_id') or not data.get('start_time'):
        return jsonify({"status": "error",
                        "message": "zone_id and start_time required"}), 400

    try:
        booking = create_booking(
            DB_PATH, request.user['user_id'], data['zone_id'],
            data['start_time'], data.get('vehicle_plate')
        )
        return jsonify({"status": "ok", "data": booking}), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 409


@app.route('/api/bookings/my')
@require_auth
def api_my_bookings():
    """GET — Returns current user's bookings."""
    bookings = get_user_bookings(DB_PATH, request.user['user_id'])
    return jsonify({"status": "ok", "data": bookings})


@app.route('/api/bookings/<int:booking_id>/cancel', methods=['POST'])
@require_auth
def api_cancel_booking(booking_id):
    """POST — Cancel a booking."""
    success = cancel_booking(DB_PATH, booking_id, request.user['user_id'])
    if success:
        return jsonify({"status": "ok", "message": "Booking cancelled"})
    return jsonify({"status": "error",
                    "message": "Could not cancel booking"}), 400


# ═══════════════════════════════════════════════════════════
# API: PAYMENTS
# ═══════════════════════════════════════════════════════════

@app.route('/api/payments/create', methods=['POST'])
@require_auth
def api_create_payment():
    """POST — Create a payment for a booking."""
    data = request.get_json()
    if not data or not data.get('booking_id') or not data.get('amount'):
        return jsonify({"status": "error",
                        "message": "booking_id and amount required"}), 400

    payment = create_payment(
        DB_PATH, data['booking_id'], request.user['user_id'],
        data['amount'], data.get('method', 'SIMULATED')
    )
    return jsonify({"status": "ok", "data": payment}), 201


@app.route('/api/payments/<int:payment_id>/process', methods=['POST'])
@require_auth
def api_process_payment(payment_id):
    """POST — Process (simulate) a payment."""
    success = process_payment(DB_PATH, payment_id)
    if success:
        return jsonify({"status": "ok", "message": "Payment processed"})
    return jsonify({"status": "error",
                    "message": "Payment already processed or not found"}), 400


@app.route('/api/payments/history')
@require_auth
def api_payment_history():
    """GET — Returns payment history for current user."""
    payments = get_user_payments(DB_PATH, request.user['user_id'])
    return jsonify({"status": "ok", "data": payments})


@app.route('/api/pricing/<location_id>')
def api_pricing(location_id):
    """GET — Calculate parking fee. ?hours=3"""
    hours = request.args.get('hours', 1, type=float)
    fee = calculate_parking_fee(DB_PATH, location_id, hours)
    return jsonify({"status": "ok", "data": fee})


# ═══════════════════════════════════════════════════════════
# API: AI CHATBOT
# ═══════════════════════════════════════════════════════════

@app.route('/api/chatbot/query', methods=['POST'])
@optional_auth
def api_chatbot():
    """POST — Send a question to the AI chatbot."""
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({"status": "error",
                        "message": "Query text required"}), 400

    user_id = request.user['user_id'] if request.user else None
    result = process_query(data['query'], DB_PATH, user_id)
    return jsonify({"status": "ok", "data": result})


# ═══════════════════════════════════════════════════════════
# API: ML / PREDICTIONS
# ═══════════════════════════════════════════════════════════

@app.route('/api/ml/run', methods=['POST'])
def api_run_ml():
    """POST — Triggers ML prediction cycle for all zones."""
    try:
        results = run_all_predictions(DB_PATH)
        return jsonify({"status": "ok", "data": "Predictions updated"})
    except Exception as e:
        logger.error(f"ML run failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ml/run/<zone_id>', methods=['POST'])
def api_run_zone_ml(zone_id):
    """POST — Triggers ML prediction for a specific zone."""
    try:
        status = get_status(DB_PATH, zone_id)
        if not status:
            return jsonify({"status": "error", "message": "Zone not found"}), 404
        max_cap = status.get('max_capacity', 100)
        result = run_zone_prediction(zone_id, max_cap, DB_PATH)
        return jsonify({"status": "ok", "data": result})
    except Exception as e:
        logger.error(f"ML run for {zone_id} failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/recommendations')
def api_all_recommendations():
    """GET — Returns smart recommendations for all zones."""
    recs = generate_all_recommendations(DB_PATH)
    return jsonify({"status": "ok", "data": recs})


# ═══════════════════════════════════════════════════════════
# WEBSOCKET HANDLERS
# ═══════════════════════════════════════════════════════════

@socketio.on('connect')
def handle_connect():
    """On client connect: send all zone statuses."""
    statuses = get_all_statuses(DB_PATH)
    emit('all_statuses', {"data": statuses})
    logger.info("WebSocket client connected")


@socketio.on('disconnect')
def handle_disconnect():
    logger.info("WebSocket client disconnected")


@socketio.on('subscribe_zone')
def handle_subscribe_zone(data):
    """Client subscribes to updates for a specific zone."""
    zone_id = data.get('zone_id')
    if zone_id:
        status = get_status(DB_PATH, zone_id)
        if status:
            emit('zone_update', {"data": status})


# ═══════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════

def create_and_run(simulate: bool = False, port: int = FLASK_PORT,
                   serial_port: str = None):
    """Creates app, starts bridge, runs server."""
    global bridge

    if serial_port:
        from backend import config
        config.SERIAL_PORT = serial_port

    logger.info("Initializing database with %d locations...", len(LOCATIONS))
    init_db(DB_PATH, LOCATIONS)

    bridge = SerialBridge(socketio, simulate=simulate)
    bridge.start()

    mode = "SIMULATION" if simulate else "LIVE (Arduino)"
    print(f"\n{'='*60}")
    print(f"  SMART PARKING SYSTEM v2.0")
    print(f"  Mode:      {mode}")
    print(f"  Locations: {len(LOCATIONS)}")
    print(f"  Dashboard: http://localhost:{port}")
    print(f"  API:       http://localhost:{port}/api/locations")
    print(f"{'='*60}\n")

    socketio.run(app, host=FLASK_HOST, port=port,
                 debug=False, allow_unsafe_werkzeug=True)


# ═══════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Smart Parking Server v2.0')
    parser.add_argument('--simulate', action='store_true',
                        help='Run without Arduino (fake events)')
    parser.add_argument('--port', type=int, default=FLASK_PORT,
                        help=f'Server port (default {FLASK_PORT})')
    parser.add_argument('--serial', type=str, default=None,
                        help='Override serial port (e.g. COM4)')
    parser.add_argument('--generate-data', action='store_true',
                        help='Generate synthetic data and exit')
    parser.add_argument('--run-ml', action='store_true',
                        help='Run ML predictions for all zones and exit')
    args = parser.parse_args()

    if args.generate_data:
        from backend.data_generator import generate_all_data
        init_db(DB_PATH, LOCATIONS)
        generate_all_data("2026-02-24", 30)
        print("\nData generated. Run without --generate-data to start server.")
        sys.exit(0)

    if args.run_ml:
        init_db(DB_PATH, LOCATIONS)
        results = run_all_predictions(DB_PATH)
        for loc_id, loc_data in results.items():
            print(f"\n[{loc_data['location_type']}] {loc_data['location_name']}")
            for zid, zdata in loc_data['zones'].items():
                if 'error' not in zdata:
                    print(f"  {zid}: MAE={zdata['models']['random_forest']['mae']:.3f}"
                          f" | Pred={zdata['predicted_count_final']}/{zdata['max_capacity']}")
        sys.exit(0)

    create_and_run(simulate=args.simulate, port=args.port,
                   serial_port=args.serial)
