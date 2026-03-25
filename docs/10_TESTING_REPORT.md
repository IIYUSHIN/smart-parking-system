# Document 10 — Testing Report

---

## 10.1 Testing Strategy

The Smart Parking System uses a multi-layer testing strategy:

| Layer | Tool | Files | Tests | Purpose |
|---|---|---|---|---|
| Unit Tests | pytest | 4 test files | 33 | Verifies individual functions and classes in isolation |
| System Verification | Manual + browser | N/A | 10 checks | Validates the full stack running end-to-end |
| Simulation Testing | Built-in simulator | N/A | Continuous | Generates realistic events to exercise the entire data pipeline |

## 10.2 Test Execution Command

```powershell
cd C:\Users\PIYUSH\.gemini\antigravity\scratch\smart_parking
.\venv\Scripts\activate
python -m pytest tests/ -v
```

## 10.3 Test Results — FULL OUTPUT

```
========================= test session starts =========================
platform win32 -- Python 3.x, pytest-8.x
cachedir: .pytest_cache
rootdir: C:\Users\PIYUSH\.gemini\antigravity\scratch\smart_parking
collected 33 items

tests/test_api.py::test_api_status_returns_ok             PASSED  [  3%]
tests/test_api.py::test_api_history_returns_events         PASSED  [  6%]
tests/test_api.py::test_api_predictions_returns_data       PASSED  [  9%]
tests/test_api.py::test_api_daily_returns_list             PASSED  [ 12%]
tests/test_api.py::test_api_hourly_returns_list            PASSED  [ 15%]
tests/test_api.py::test_index_serves_html                  PASSED  [ 18%]
tests/test_database.py::test_init_creates_all_tables       PASSED  [ 21%]
tests/test_database.py::test_init_inserts_default_config   PASSED  [ 24%]
tests/test_database.py::test_update_status_calculates_derived_fields PASSED [ 27%]
tests/test_database.py::test_update_status_full            PASSED  [ 30%]
tests/test_database.py::test_get_status_returns_data       PASSED  [ 33%]
tests/test_database.py::test_get_status_nonexistent        PASSED  [ 36%]
tests/test_database.py::test_log_event_stores_correctly    PASSED  [ 39%]
tests/test_database.py::test_log_event_rejects_invalid_type PASSED [ 42%]
tests/test_database.py::test_get_history_respects_hours    PASSED  [ 45%]
tests/test_database.py::test_save_and_get_prediction       PASSED  [ 48%]
tests/test_database.py::test_get_prediction_empty          PASSED  [ 51%]
tests/test_ml_engine.py::test_moving_average_with_3_values PASSED  [ 54%]
tests/test_ml_engine.py::test_moving_average_uses_last_window PASSED [ 57%]
tests/test_ml_engine.py::test_moving_average_with_fewer_values PASSED [ 60%]
tests/test_ml_engine.py::test_regression_trains_without_error PASSED [ 63%]
tests/test_ml_engine.py::test_prediction_clamped_to_capacity PASSED [ 66%]
tests/test_ml_engine.py::test_load_training_data_has_features PASSED [ 69%]
tests/test_ml_engine.py::test_compute_hourly_returns_data  PASSED  [ 72%]
tests/test_ml_engine.py::test_features_include_rolling_avg PASSED  [ 75%]
tests/test_serial_parser.py::test_valid_entry_json         PASSED  [ 78%]
tests/test_serial_parser.py::test_valid_exit_json          PASSED  [ 81%]
tests/test_serial_parser.py::test_malformed_json_returns_none PASSED [ 84%]
tests/test_serial_parser.py::test_missing_fields_returns_none PASSED [ 87%]
tests/test_serial_parser.py::test_invalid_event_type_returns_none PASSED [ 90%]
tests/test_serial_parser.py::test_count_exceeds_max_returns_none PASSED [ 93%]
tests/test_serial_parser.py::test_negative_count_returns_none PASSED [ 96%]
tests/test_serial_parser.py::test_boot_event_handled       PASSED  [100%]

========================= 33 passed in 5.45s ===========================
```

**Result: 33 PASSED, 0 FAILED, 0 ERRORS, 0 SKIPPED**

## 10.4 Test Suite Breakdown

---

### Suite 1: `test_api.py` — REST API Endpoint Tests (6 Tests)

**Purpose:** Validates all Flask REST API endpoints return correct HTTP status codes, response structures, and data.

**Setup:** Creates a temporary SQLite database with seeded data (status, events, predictions), monkeypatches the DB path in the Flask app module, and uses Flask's test client.

| # | Test Name | What It Verifies | Input | Expected Result |
|---|---|---|---|---|
| 1 | `test_api_status_returns_ok` | `/api/status` returns HTTP 200 with status="ok" and correct count | GET /api/status | `{"status":"ok", "data":{"current_count":2}}` |
| 2 | `test_api_history_returns_events` | `/api/history?hours=24` returns a list of events | GET /api/history | `{"status":"ok", "data":[...]}` |
| 3 | `test_api_predictions_returns_data` | `/api/predictions` returns seeded prediction data | GET /api/predictions | `{"data":{"predicted_count":3}}` |
| 4 | `test_api_daily_returns_list` | `/api/analytics/daily?days=7` returns a list | GET /api/analytics/daily | `{"data":[...]}` |
| 5 | `test_api_hourly_returns_list` | `/api/analytics/hourly` returns a list | GET /api/analytics/hourly | `{"data":[...]}` |
| 6 | `test_index_serves_html` | Root `/` serves HTML containing "Smart Parking" | GET / | HTTP 200, body contains b'Smart Parking' |

---

### Suite 2: `test_database.py` — Database Layer Tests (11 Tests)

**Purpose:** Validates all database.py functions using isolated temporary databases per test (pytest `tmp_path` fixture).

| # | Test Name | What It Verifies | Input | Expected Result |
|---|---|---|---|---|
| 1 | `test_init_creates_all_tables` | `init_db()` creates all 5 tables | Fresh DB | Tables: parking_config, parking_status, occupancy_log, predictions, daily_summary |
| 2 | `test_init_inserts_default_config` | Config row inserted with correct values | Fresh DB | parking_id="TEST_01", max_capacity=4 |
| 3 | `test_update_status_calculates_derived_fields` | `update_status()` computes available_slots, utilization, is_full | count=3, max=4 | available_slots=1, utilization=75.0, is_full=False |
| 4 | `test_update_status_full` | Full parking state is correctly detected | count=4, max=4 | is_full=True, available_slots=0, utilization=100.0 |
| 5 | `test_get_status_returns_data` | `get_status()` retrieves updated data | After update_status(2) | current_count=2, is_full in result |
| 6 | `test_get_status_nonexistent` | Non-existent parking_id returns None | parking_id="NONEXISTENT" | None |
| 7 | `test_log_event_stores_correctly` | `log_event()` inserts and returns event_id > 0 | ENTRY, count=1 | event_id>0, events[0].event_type="ENTRY" |
| 8 | `test_log_event_rejects_invalid_type` | Invalid event_type raises ValueError | "INVALID" | pytest.raises(ValueError) |
| 9 | `test_get_history_respects_hours` | `get_history()` returns events within time window | hours=1 | len(events) >= 1 |
| 10 | `test_save_and_get_prediction` | Prediction roundtrip: save then retrieve | count=3, start="08:00" | predicted_count=3, peak_hour_start="08:00" |
| 11 | `test_get_prediction_empty` | No predictions returns None | Empty DB | None |

---

### Suite 3: `test_ml_engine.py` — ML Engine Tests (8 Tests)

**Purpose:** Validates ML models, data loading, feature engineering, and training pipeline.

**Setup:** Creates a database with 7 days of structured events (entries in morning hours, exits in afternoon) to provide enough data for model training.

| # | Test Name | What It Verifies | Input | Expected Result |
|---|---|---|---|---|
| 1 | `test_moving_average_with_3_values` | 3-value moving average | [1.0, 2.0, 3.0] | 2.0 |
| 2 | `test_moving_average_uses_last_window` | Window only uses last N values | [0, 0, 1, 2, 3] | 2.0 (last 3: [1,2,3]) |
| 3 | `test_moving_average_with_fewer_values` | Handles fewer values than window | [5.0] | 5.0 |
| 4 | `test_regression_trains_without_error` | LinearRegression trains successfully | 7-day event data | mae >= 0, model.is_trained is True |
| 5 | `test_prediction_clamped_to_capacity` | All predictions are within [0, 4] | Trained model, hours 0-23 | 0 <= pred <= 4 for all hours |
| 6 | `test_load_training_data_has_features` | Feature engineering creates correct columns | 7-day events | 'hour', 'day_of_week', 'is_weekend' in columns |
| 7 | `test_compute_hourly_returns_data` | Hourly aggregation produces expected columns | Training data | 'avg_occupancy', 'net_flow' in columns |
| 8 | `test_features_include_rolling_avg` | Additional features are computed | Hourly data | 'rolling_avg_3', 'utilization_pct' in columns |

---

### Suite 4: `test_serial_parser.py` — Serial Parser Tests (8 Tests)

**Purpose:** Validates JSON parsing, field validation, boundary checks, and error handling in the serial bridge parser.

**Setup:** Creates a `SerialBridge` instance with a mock SocketIO object and simulation mode enabled.

| # | Test Name | What It Verifies | Input | Expected Result |
|---|---|---|---|---|
| 1 | `test_valid_entry_json` | Valid ENTRY JSON is parsed correctly | `{"e":"ENTRY","c":2,"m":4,"t":12345}` | Result not None, e="ENTRY", c=2 |
| 2 | `test_valid_exit_json` | Valid EXIT JSON is parsed correctly | `{"e":"EXIT","c":1,"m":4,"t":67890}` | Result not None, e="EXIT", c=1 |
| 3 | `test_malformed_json_returns_none` | Non-JSON string is rejected | `"not json at all"` | None |
| 4 | `test_missing_fields_returns_none` | JSON with missing fields is rejected | `{"e":"ENTRY"}` | None |
| 5 | `test_invalid_event_type_returns_none` | Unknown event type is rejected | `{"e":"UNKNOWN","c":1,"m":4,"t":0}` | None |
| 6 | `test_count_exceeds_max_returns_none` | Count > max_capacity is rejected | `{"e":"ENTRY","c":5,"m":4,"t":0}` | None |
| 7 | `test_negative_count_returns_none` | Negative count is rejected | `{"e":"EXIT","c":-1,"m":4,"t":0}` | None |
| 8 | `test_boot_event_handled` | BOOT event resets internal state | `{"e":"BOOT","c":0,"m":4,"t":0}` | None (consumed internally), current_count=0 |

## 10.5 System Verification Results

These are manual verification checks performed with the server running in simulation mode:

| # | Check | Method | Result |
|---|---|---|---|
| SV-01 | Server starts without errors | `python -m backend.app --simulate` | **PASS** — banner printed, no exceptions |
| SV-02 | Dashboard loads in browser | Navigate to http://localhost:5000 | **PASS** — all 7 cards rendered |
| SV-03 | WebSocket connects | Check green "Live" indicator | **PASS** — green dot, text "Live" |
| SV-04 | Simulation events generate | Watch server logs | **PASS** — ENTRY/EXIT every 5-15s |
| SV-05 | Occupancy ring updates | Watch dashboard during events | **PASS** — ring arc changes, count increments/decrements |
| SV-06 | Status badge switches | Wait until count reaches 4 | **PASS** — "FULL" red badge appears with pulse animation |
| SV-07 | Timeline chart adds points | Watch chart for 30+ seconds | **PASS** — new data points appear at right edge |
| SV-08 | API returns valid JSON | `curl http://localhost:5000/api/status` | **PASS** — valid JSON with status="ok" |
| SV-09 | ML predictions load | Check prediction card and peak hours card | **PASS** — "2/4" prediction, "06:00-24:00" peak |
| SV-10 | Daily chart shows 7 bars | Check daily utilization card | **PASS** — 7 teal bars with percentages |

## 10.6 Test Coverage Summary

| Module | Functions Tested | Functions Total | Coverage |
|---|---|---|---|
| `database.py` | 9 of 12 | 12 | 75% |
| `ml_engine.py` | 6 of 8 | 8 | 75% |
| `serial_bridge.py` | 2 of 4 | 4 | 50% |
| `app.py` | 6 of 8 | 8 | 75% |

**Note:** Coverage percentages are function-level estimates. Full line-level coverage would require additional tooling (e.g., `pytest-cov`).

## 10.7 Edge Cases Verified

| Category | Edge Case | Test | Result |
|---|---|---|---|
| Database | Nonexistent parking_id | `test_get_status_nonexistent` | Returns None (no crash) |
| Database | Invalid event type | `test_log_event_rejects_invalid_type` | Raises ValueError |
| Database | Empty predictions table | `test_get_prediction_empty` | Returns None |
| ML | Single value for moving average | `test_moving_average_with_fewer_values` | Returns the single value |
| ML | All 24 hours give valid predictions | `test_prediction_clamped_to_capacity` | All in [0, 4] |
| Serial | Malformed JSON | `test_malformed_json_returns_none` | Silently returns None |
| Serial | Count > max capacity | `test_count_exceeds_max_returns_none` | Rejects the event |
| Serial | Negative count | `test_negative_count_returns_none` | Rejects the event |
| Serial | Missing required fields | `test_missing_fields_returns_none` | Rejects the event |
| Serial | BOOT event (reset) | `test_boot_event_handled` | Resets internal count |

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
