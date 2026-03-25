# Document 01 — Project Overview & Identity

---

## 1.1 Project Title

**AI-Enabled Smart Parking Management System**

## 1.2 Project Summary

This project implements a fully functional, AI-powered smart parking occupancy monitoring and prediction system. The system uses physical IoT hardware (Arduino Uno with IR sensors) to detect vehicle entry and exit, processes occupancy data through a Python backend with machine learning capabilities, stores data in a local SQLite database, and presents real-time analytics through a premium web dashboard with WebSocket-based live updates.

The system is designed as a scaled academic prototype that demonstrates enterprise-grade design principles within the constraint of a physical parking model with 4 slots.

## 1.3 Project Objective

To design, build, and validate an end-to-end smart parking system that:

1. **Detects** vehicle entry and exit using infrared sensors
2. **Counts** real-time occupancy using centralized total-capacity logic
3. **Controls** a barrier (servo motor) using deterministic rule-based logic
4. **Displays** live status on an LCD panel attached to the hardware model
5. **Transmits** event data to a laptop via USB serial communication (JSON)
6. **Stores** all events in a structured database for historical analysis
7. **Predicts** future occupancy using machine learning models
8. **Visualizes** everything through a real-time web dashboard with charts

## 1.4 Design Philosophy

| Principle | Implementation |
|---|---|
| **Local-Only** | No cloud, no WiFi, no internet dependency. Everything runs on the laptop via USB. |
| **AI is Advisory** | ML models predict and analyze — they never control the physical barrier. |
| **Rule-Based Safety** | Barrier control is deterministic in firmware. Parking full? Barrier stays closed. No ML in the loop. |
| **Simulation-First** | 70% of the software can be developed and tested without physical Arduino using simulation mode. |
| **Professional Standard** | Engineering-grade code quality, rubric-aligned deliverables, defensible before evaluation panel. |

## 1.5 Scope Definition

### In Scope
- Single parking zone with 4 physical slots
- Entry/exit detection via 2 IR sensors
- Servo motor barrier with rule-based control
- 16x2 LCD display showing live count
- USB serial communication (JSON at 9600 baud)
- Python Flask backend with REST API + WebSocket
- SQLite database with 5 tables
- ML prediction system (Moving Average + Linear Regression)
- Real-time web dashboard with Chart.js visualizations
- PWA mobile support
- 33-test automated validation framework
- Simulation mode for testing without hardware

### Out of Scope (Future Work)
- Multi-zone / multi-floor parking
- Per-slot detection (individual slot sensors)
- Cloud deployment
- Mobile native app
- Payment integration
- License plate recognition
- GPS navigation to parking

## 1.6 Academic Alignment

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Project Selection & Problem Definition | Completed |
| Phase 2 | Literature Review & Requirement Analysis | Completed |
| Phase 3 | System Design & Architecture | Completed (13 exchanges, Parts A-H) |
| Phase 4 | Implementation & Testing | **Completed** (this document) |

## 1.7 Key Design Decision — Why Design A?

The system follows **Design A: Centralized Total-Capacity IoT Model**, selected through a weighted multi-criteria decision matrix (Score: 435/500) over Design B (Per-Slot Sensor Grid).

**Reason:** Design A achieves the same functional outcome with significantly fewer components (2 sensors vs. N sensors per slot), lower cost, simpler wiring, and zero scalability overhead for the prototype.

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
