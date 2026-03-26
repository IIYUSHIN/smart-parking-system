"""
Unit Tests — Serial Bridge Parser v2.0
Tests JSON parsing, validation, and edge cases.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.serial_bridge import SerialBridge


class FakeSocketIO:
    """Mock SocketIO that captures emitted events."""
    def __init__(self):
        self.events = []

    def emit(self, event, data):
        self.events.append((event, data))


@pytest.fixture
def bridge():
    sio = FakeSocketIO()
    return SerialBridge(sio, simulate=True)


# ── VALID PARSING ──

def test_valid_entry_json(bridge):
    result = bridge._parse_line('{"e":"ENTRY","c":2,"m":4,"t":12345}')
    assert result is not None
    assert result['e'] == "ENTRY"
    assert result['c'] == 2


def test_valid_exit_json(bridge):
    result = bridge._parse_line('{"e":"EXIT","c":1,"m":4,"t":67890}')
    assert result is not None
    assert result['e'] == "EXIT"
    assert result['c'] == 1


# ── INVALID PARSING ──

def test_malformed_json_returns_none(bridge):
    result = bridge._parse_line('not json at all')
    assert result is None


def test_missing_fields_returns_none(bridge):
    result = bridge._parse_line('{"e":"ENTRY"}')
    assert result is None


def test_invalid_event_type_returns_none(bridge):
    result = bridge._parse_line('{"e":"UNKNOWN","c":1,"m":4,"t":0}')
    assert result is None


def test_count_exceeds_max_returns_none(bridge):
    result = bridge._parse_line('{"e":"ENTRY","c":5,"m":4,"t":0}')
    assert result is None


def test_negative_count_returns_none(bridge):
    result = bridge._parse_line('{"e":"EXIT","c":-1,"m":4,"t":0}')
    assert result is None


# ── BOOT EVENT ──

def test_boot_event_handled(bridge):
    result = bridge._parse_line('{"e":"BOOT","c":0,"m":4,"t":0}')
    # BOOT events are consumed internally, return None
    assert result is None
    assert bridge.current_count == 0
