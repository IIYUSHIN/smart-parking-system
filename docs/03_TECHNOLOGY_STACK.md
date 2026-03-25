# Document 03 — Technology Stack

---

## 3.1 Technology Selection Summary

Every technology in this project was pre-selected and locked before implementation to eliminate decision fatigue. The table below documents each technology, its version, its role, why it was chosen, and what alternatives were considered.

## 3.2 Hardware Technologies

| # | Technology | Version / Spec | Role in System | Why Selected | Alternatives Considered |
|---|---|---|---|---|---|
| H1 | **Arduino Uno** | ATmega328P, 16 MHz | Main microcontroller processing sensor inputs, controlling actuators, and transmitting data | Industry-standard educational microcontroller with extensive library support. Simple, reliable, sufficient I/O pins. | Arduino Mega (overkill), ESP32 (WiFi not needed), Raspberry Pi Pico (less library support) |
| H2 | **IR Sensor Module** (x2) | Digital output, 5V | Detects vehicle presence at entry and exit points by infrared beam interruption | Non-contact detection, reliable in indoor environments, simple digital output (HIGH/LOW), no calibration needed | Ultrasonic (HC-SR04 — distance-based, more complex), Camera (cost-prohibitive), Inductive loop (requires ground installation) |
| H3 | **SG90 Servo Motor** | 0-180°, 5V | Parking barrier arm — opens (90°) to allow vehicle passage, closes (0°) to block | Simple angular control, powered directly from Arduino 5V, lightweight, sufficient torque for model barrier | Stepper motor (overkill), DC motor with H-bridge (no positional control) |
| H4 | **16x2 LCD Display** | I2C interface, addr 0x27 | Displays live parking count and status on the physical hardware model | Only uses 2 pins (SDA/SCL via I2C) instead of 6+ pins for parallel LCD. Clear, readable digits. | OLED (smaller, harder to read at distance), 7-segment display (limited characters), Serial monitor only (no on-device display) |
| H5 | **USB Cable** | Type-A to Type-B | Physical data link between Arduino and laptop | Standard Arduino cable, no additional hardware, reliable bidirectional serial, powers Arduino simultaneously | Bluetooth HC-05 (pairing issues), WiFi ESP8266 (violates local-only constraint), XBee (expensive) |

## 3.3 Software Technologies — Backend

| # | Technology | Version | Role in System | Why Selected | Alternatives Considered |
|---|---|---|---|---|---|
| S1 | **Python** | 3.11+ | Primary programming language for all backend logic | Rich ML ecosystem (scikit-learn, pandas, numpy), clean syntax, single language for backend + ML + data generation | JavaScript/Node.js (weaker ML), Java (verbose), Go (less ML support) |
| S2 | **Flask** | 3.0+ | Web framework for REST API and serving frontend files | Lightweight, no boilerplate, perfect for single-server prototypes, native static file serving | Django (too heavy), FastAPI (async complexity not needed), Express.js (different language) |
| S3 | **Flask-SocketIO** | 5.3+ | WebSocket server for real-time push notifications to dashboard | Seamless integration with Flask, automatic fallback to polling, simple emit() API | plain WebSocket (more boilerplate), Server-Sent Events (one-directional), polling (high latency) |
| S4 | **SQLite** | 3 (stdlib) | Local relational database for all persistent data | Zero setup, file-based, built into Python stdlib, WAL mode for concurrent access, perfect for single-server | PostgreSQL (requires server), MySQL (requires server), MongoDB (schema-less, harder to reason about), JSON files (no queries) |
| S5 | **pyserial** | 3.5+ | USB serial communication library to read Arduino output | Industry standard, cross-platform, simple API (Serial.readline()), handles port management | Direct OS file I/O (fragile), Firmata protocol (different paradigm) |
| S6 | **scikit-learn** | 1.4+ | Machine learning library for Linear Regression model | Clean API, well-documented, lightweight, fits project scope (simple models) | TensorFlow (extremely heavy), PyTorch (overkill), statsmodels (less prediction API) |
| S7 | **pandas** | 2.1+ | Data manipulation and feature engineering for ML pipeline | DataFrame operations, time series handling, groupby aggregations | Raw Python lists/dicts (error-prone), PySpark (overkill) |
| S8 | **numpy** | 1.26+ | Numerical computing underlying pandas and scikit-learn | Required dependency for scikit-learn and pandas, fast array operations | Pure Python math (slow) |
| S9 | **joblib** | 1.3+ | Serialization of trained ML models to disk | Optimized for scikit-learn objects, fast save/load | pickle (less efficient for numpy arrays), ONNX (deployment complexity) |
| S10 | **eventlet** | 0.35+ | Async networking library for Flask-SocketIO | Required by Flask-SocketIO for WebSocket support in threading mode | gevent (similar, less Flask integration) |

## 3.4 Software Technologies — Frontend

| # | Technology | Version | Role in System | Why Selected | Alternatives Considered |
|---|---|---|---|---|---|
| F1 | **HTML5** | Standard | Page structure and semantic markup | Universal, no build step, accessible | N/A |
| F2 | **CSS3 (Vanilla)** | Standard | Design system, glassmorphism, animations, responsive grid | Full control, no dependency, CSS custom properties for theming | TailwindCSS (utility-class bloat), Bootstrap (generic look), Sass (build step needed) |
| F3 | **JavaScript (Vanilla)** | ES2020+ | Dashboard logic, DOM manipulation, API calls, WebSocket client | No build step, no bundler, no React/Vue overhead. Simple enough for 3 JS files. | React (build toolchain), Vue (build toolchain), jQuery (outdated) |
| F4 | **Chart.js** | 4.4+ (CDN) | Data visualization — timeline and daily utilization charts | Beautiful defaults, responsive, small bundle, simple API, dark theme support | D3.js (steep learning curve), Highcharts (commercial license), Plotly (heavy) |
| F5 | **Socket.IO Client** | 4.7+ (CDN) | WebSocket client for receiving real-time parking events | Matches Flask-SocketIO server, auto-reconnection, fallback support | Raw WebSocket API (less features, no auto-reconnect) |
| F6 | **Google Fonts (Inter)** | Variable weight | Typography — clean, professional, modern sans-serif | Free, widely used in premium dashboards, excellent readability | Roboto (too Google-branded), System fonts (inconsistent), Outfit (less common) |
| F7 | **PWA (manifest.json)** | W3C Standard | Makes dashboard installable on mobile devices | Zero extra code, just manifest + meta tags, same codebase serves desktop and mobile | React Native (complete rebuild), Flutter (complete rebuild) |

## 3.5 Development & Testing Technologies

| # | Technology | Version | Role in System | Why Selected |
|---|---|---|---|---|
| T1 | **pytest** | 8.0+ | Test framework for all unit and integration tests | Pythonic, fixtures, assertions, auto-discovery, verbose output |
| T2 | **Arduino IDE** | 2.x | Firmware compilation and upload to Arduino Uno | Official, well-supported, library manager |
| T3 | **Git** | Latest | Version control | Industry standard |
| T4 | **VS Code** | Latest | Code editor | Extension ecosystem |

## 3.6 Dependencies Summary

```
flask>=3.0
flask-socketio>=5.3
pyserial>=3.5
scikit-learn>=1.4
pandas>=2.1
numpy>=1.26
joblib>=1.3
eventlet>=0.35
pytest>=8.0
```

**Total Python packages installed:** 33 (including transitive dependencies)
**Frontend CDN dependencies:** 2 (Chart.js, Socket.IO client)
**Arduino libraries:** 3 (Servo.h, Wire.h, LiquidCrystal_I2C.h)

## 3.7 Standards Compliance

The following standards are referenced in the project design:

| Standard | Domain | How We Comply |
|---|---|---|
| IEEE 802.15 | IoT Communication | USB serial as reliable wired alternative to wireless |
| ISO 27001 | Information Security | Local-only data, no network exposure, no cloud |
| IEC 61131-3 | Industrial Control | Rule-based barrier logic in firmware (deterministic) |
| OWASP Top 10 | Web Security | No authentication (prototype), but API follows REST best practices |
| IEEE 2413-2019 | IoT Architecture | 5-layer architecture with clear separation of concerns |
| ISO 37154 | Smart Cities | Parking occupancy and utilization metrics as city intelligence |

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
