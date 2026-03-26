"""
Smart Parking System — Serial Bridge
Reads Arduino serial output (USB), parses JSON, updates DB, emits WebSocket events.
Includes simulation mode for development without physical Arduino.
"""

import json
import time
import random
import threading
import logging

from backend.config import (
    SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT,
    ARDUINO_ZONE_ID, ARDUINO_MAX_CAPACITY, DB_PATH,
    SIMULATE_INTERVAL_MIN, SIMULATE_INTERVAL_MAX
)
from backend.database import update_status, log_event

logger = logging.getLogger(__name__)


class SerialBridge:
    """Reads Arduino serial output, parses JSON, updates database,
    emits WebSocket events."""

    def __init__(self, socketio, simulate: bool = False):
        """
        Args:
            socketio: Flask-SocketIO instance
            simulate: if True, generates fake events without Arduino
        """
        self.socketio = socketio
        self.simulate = simulate
        self.running = False
        self.serial_conn = None
        self.current_count = 0  # shadow count for simulation

    def start(self) -> None:
        """Starts reading in a background daemon thread."""
        self.running = True
        if self.simulate:
            thread = threading.Thread(target=self._simulate_loop,
                                     daemon=True, name="SimulationBridge")
        else:
            thread = threading.Thread(target=self._serial_loop,
                                     daemon=True, name="SerialBridge")
        thread.start()
        mode = "SIMULATION" if self.simulate else f"SERIAL ({SERIAL_PORT})"
        logger.info(f"SerialBridge started in {mode} mode")

    def stop(self) -> None:
        """Stops the bridge."""
        self.running = False
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        logger.info("SerialBridge stopped")

    # ── REAL SERIAL ──

    def _serial_loop(self) -> None:
        """Real serial reading loop.
        Opens port, reads lines, parses JSON, processes events.
        On error: waits 5s, retries connection.
        """
        import serial as pyserial

        while self.running:
            try:
                logger.info(f"Connecting to {SERIAL_PORT} at {BAUD_RATE} baud...")
                self.serial_conn = pyserial.Serial(
                    port=SERIAL_PORT,
                    baudrate=BAUD_RATE,
                    timeout=SERIAL_TIMEOUT
                )
                logger.info(f"Connected to {SERIAL_PORT}")

                # Give Arduino time to reset after serial connection
                time.sleep(2)

                while self.running:
                    if self.serial_conn.in_waiting > 0:
                        raw = self.serial_conn.readline().decode('utf-8',
                                                                  errors='ignore').strip()
                        if raw:
                            event = self._parse_line(raw)
                            if event:
                                self._process_event(event)
                    else:
                        time.sleep(0.05)  # 50ms poll cycle

            except Exception as e:
                logger.warning(f"Serial error: {e}. Retrying in 5s...")
                time.sleep(5)

    # ── SIMULATION ──

    def _simulate_loop(self) -> None:
        """Simulation loop — no Arduino needed.
        Generates random ENTRY/EXIT events every 5-15 seconds.
        Respects 0 <= count <= MAX_CAPACITY.
        """
        logger.info("Simulation mode active — generating fake events")

        while self.running:
            interval = random.uniform(SIMULATE_INTERVAL_MIN,
                                      SIMULATE_INTERVAL_MAX)
            time.sleep(interval)

            if not self.running:
                break

            # Decide event type based on current state
            if self.current_count >= ARDUINO_MAX_CAPACITY:
                event_type = "EXIT"
            elif self.current_count == 0:
                event_type = "ENTRY"
            else:
                event_type = random.choice(["ENTRY", "EXIT"])

            # Apply event
            if event_type == "ENTRY":
                self.current_count += 1
            else:
                self.current_count -= 1

            event = {
                "e": event_type,
                "c": self.current_count,
                "m": ARDUINO_MAX_CAPACITY,
                "t": int(time.time() * 1000)
            }

            self._process_event(event)

    # ── PARSING ──

    def _parse_line(self, raw: str) -> dict | None:
        """Parses one serial line.
        Expected: {"e":"ENTRY","c":2,"m":4,"t":12345}

        Returns parsed dict or None if invalid.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Malformed JSON: {raw}")
            return None

        # Validate required fields
        if not all(k in data for k in ('e', 'c', 'm')):
            logger.warning(f"Missing fields: {raw}")
            return None

        # Validate event type
        if data['e'] not in ('ENTRY', 'EXIT', 'BOOT'):
            logger.warning(f"Invalid event type: {data['e']}")
            return None

        # Validate count bounds
        if not (0 <= data['c'] <= data['m']):
            logger.warning(f"Count out of bounds: {data['c']}/{data['m']}")
            return None

        # Skip BOOT events (just initialization)
        if data['e'] == 'BOOT':
            logger.info("Arduino BOOT event received")
            self.current_count = data['c']
            return None

        return data

    # ── PROCESSING ──

    def _process_event(self, event: dict) -> None:
        """Processes a validated event:
        1. Update parking_status in DB
        2. Log event in occupancy_log
        3. Emit WebSocket event to all connected clients
        """
        event_type = event['e']
        count = event['c']
        max_cap = event['m']

        # 1. Update status
        status = update_status(DB_PATH, ARDUINO_ZONE_ID, count, max_cap)

        # 2. Log event
        log_event(DB_PATH, ARDUINO_ZONE_ID, event_type, count)

        # 3. Emit to WebSocket
        payload = {
            "zone_id": ARDUINO_ZONE_ID,
            "current_count": count,
            "available_slots": max_cap - count,
            "utilization_percent": round((count / max_cap) * 100, 1),
            "is_full": count >= max_cap,
            "max_capacity": max_cap,
            "last_event": event_type,
            "last_updated": status["last_updated"]
        }

        self.socketio.emit('parking_update', payload)
        logger.info(f"Event: {event_type} | Count: {count}/{max_cap}")
