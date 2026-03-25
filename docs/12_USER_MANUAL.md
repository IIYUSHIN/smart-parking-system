# Document 12 — User Manual

---

## 12.1 Introduction

This manual is for **anyone** — evaluators, faculty, or non-technical users — who wants to operate the Smart Parking System. No programming knowledge is required to follow these steps.

---

## 12.2 System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **Operating System** | Windows 10 | Windows 11 |
| **Python** | 3.11 | 3.12+ |
| **RAM** | 4 GB | 8 GB |
| **Disk Space** | 200 MB | 500 MB |
| **Browser** | Chrome 90+ | Chrome / Edge (latest) |
| **Arduino IDE** | 2.0+ | 2.3+ (only for hardware demo) |
| **Hardware (optional)** | Arduino Uno, 2x IR sensors, servo, LCD | Same |

---

## 12.3 Installation (One-Time Setup)

### Step 1: Open Terminal

Press `Win + X` → select **Terminal** (or **PowerShell**).

### Step 2: Navigate to Project

```powershell
cd C:\Users\PIYUSH\.gemini\antigravity\scratch\smart_parking
```

### Step 3: Create Virtual Environment (first time only)

```powershell
python -m venv venv
```

### Step 4: Activate Virtual Environment

```powershell
.\venv\Scripts\activate
```

You should see `(venv)` appear at the beginning of your terminal prompt. This confirms the virtual environment is active.

### Step 5: Install Dependencies

```powershell
pip install -r requirements.txt
```

This installs all 33 required Python packages. Wait for it to complete — it takes 1-2 minutes.

### Step 6: Generate Training Data

```powershell
python -m backend.app --generate-data
```

This creates 14 days of synthetic parking events (581 events). You should see:
```
Generating synthetic data: 14 days ...
Generated 581 events across 14 days
```

### Step 7: Train AI Model

```powershell
python -m backend.app --run-ml
```

This trains the prediction model. You should see:
```
Running ML prediction pipeline...
MAE: 0.918
Prediction saved: 2 vehicles expected
```

**Installation is now complete.** You only need to do Steps 1-7 once.

---

## 12.4 Running the System

### Option A: Simulation Mode (No Arduino Needed)

This is the **recommended mode** for demonstrations and testing. The system generates realistic parking events automatically.

```powershell
cd C:\Users\PIYUSH\.gemini\antigravity\scratch\smart_parking
.\venv\Scripts\activate
python -m backend.app --simulate
```

You should see:
```
============================================================
  SMART PARKING SYSTEM
  Mode:      SIMULATION
  Dashboard: http://localhost:5000
  API:       http://localhost:5000/api/status
============================================================
```

**Now open your web browser** and go to:

👉 **http://localhost:5000**

The dashboard will appear. You will see parking events (ENTRY/EXIT) being generated automatically every 5-15 seconds.

### Option B: Live Arduino Mode (Hardware Connected)

1. Connect Arduino Uno to laptop via USB cable
2. Note the COM port (check Arduino IDE → Tools → Port)
3. Upload the firmware first (see Section 12.7)
4. Then run:

```powershell
python -m backend.app --serial COM3
```

Replace `COM3` with your actual port.

---

## 12.5 Using the Dashboard

Once the dashboard is open in your browser at `http://localhost:5000`, here is what each element shows:

### Top Header Bar

| Element | Location | What It Shows |
|---|---|---|
| **Smart Parking System** | Top-left | Project title |
| **AI-Powered Occupancy Intelligence** | Below title | Project subtitle |
| **Green dot + "Live"** | Top-right | System is connected and receiving events |
| **Red dot + "Disconnected"** | Top-right | System lost connection (will auto-reconnect) |

### Card 1: Live Occupancy (Top-Left)

- **Large number in ring:** Current number of vehicles inside
- **"/ 4" below it:** Maximum capacity
- **Cyan ring arc:** Visual fill level — fills as parking gets busier
- **"X slots available":** How many empty spots remain
- **Ring turns amber:** When only 1 slot left
- **Ring turns red:** When parking is completely full

### Card 2: Parking Status (Top-Center)

- **Green badge "AVAILABLE":** Parking has free slots
- **Red badge "FULL" (pulsing):** All 4 slots occupied — no entry allowed
- **Last event:** Shows whether the most recent event was ENTRY or EXIT
- **Updated:** Timestamp of the last event

### Card 3: AI Prediction (Top-Right)

- **"2/4" (or similar):** The AI model predicts this many vehicles in the next hour
- This is advisory only — it does not control the barrier

### Card 4: Busiest Hours (Middle-Left)

- **"06:00 – 24:00" (or similar):** The time window with the highest average occupancy
- Derived from 14 days of training data

### Card 5: Overall Utilization (Middle-Center)

- **"51%" (or similar):** Average parking utilization across all recorded data
- **Gradient progress bar:** Visual representation of the percentage

### Card 6: Occupancy Timeline (Bottom-Left, wide)

- **Line chart:** Shows occupancy count over the last 24 hours
- **Live updates:** New data points appear on the right edge as events occur
- **Hover:** Shows exact occupancy value at any time point

### Card 7: Daily Utilization (Bottom-Right)

- **Bar chart:** Shows average utilization % for each of the last 7 days
- **Taller bars = busier days**

---

## 12.6 Running the Tests

To verify that all system components are working correctly:

```powershell
cd C:\Users\PIYUSH\.gemini\antigravity\scratch\smart_parking
.\venv\Scripts\activate
python -m pytest tests/ -v
```

**Expected output:** 33 tests, all showing `PASSED`. If any test shows `FAILED`, there is a problem that needs investigation.

---

## 12.7 Uploading Arduino Firmware (Hardware Mode Only)

1. Open **Arduino IDE**
2. Go to **File → Open** → navigate to:
   ```
   smart_parking\arduino\smart_parking\smart_parking.ino
   ```
3. Go to **Tools → Board** → select **Arduino Uno**
4. Go to **Tools → Port** → select the COM port (e.g., COM3)
5. If not installed, go to **Tools → Manage Libraries** → search for `LiquidCrystal I2C` → click **Install**
6. Click the **Upload button** (right arrow icon) or press `Ctrl+U`
7. Wait for "Done uploading" message
8. Open **Tools → Serial Monitor** → set baud to **9600**
9. You should see JSON output like: `{"e":"BOOT","c":0,"m":4,"t":0}`

---

## 12.8 Stopping the System

To stop the server, go to the terminal where it is running and press:

```
Ctrl + C
```

The server will shut down. The database is automatically saved — no data is lost.

---

## 12.9 Troubleshooting

| Problem | Solution |
|---|---|
| `python` command not found | Install Python from python.org, check "Add to PATH" during installation |
| `(venv)` not showing in terminal | Run `.\venv\Scripts\activate` |
| Port 5000 already in use | Run `python -m backend.app --simulate --port 8080` and open `http://localhost:8080` |
| Dashboard shows "Disconnected" | Server may have stopped — check terminal for errors, restart with `python -m backend.app --simulate` |
| Charts are empty | Run `python -m backend.app --generate-data` first to create training data |
| AI prediction shows "--" | Run `python -m backend.app --run-ml` to generate predictions |
| Arduino not detected | Try a different USB port, check Device Manager for COM port number |
| LCD shows nothing | Check I2C wiring (SDA→A4, SCL→A5), verify I2C address is 0x27 |
| Tests fail | Run `pip install -r requirements.txt` again to ensure all packages are installed |

---

## 12.10 Quick Reference Card

| Action | Command |
|---|---|
| Activate environment | `.\venv\Scripts\activate` |
| Start (simulation) | `python -m backend.app --simulate` |
| Start (Arduino) | `python -m backend.app --serial COM3` |
| Open dashboard | Browser → `http://localhost:5000` |
| Run tests | `python -m pytest tests/ -v` |
| Generate data | `python -m backend.app --generate-data` |
| Train AI model | `python -m backend.app --run-ml` |
| Stop server | `Ctrl + C` in terminal |

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
