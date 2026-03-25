# Document 06 — ML Engine Documentation

---

## 6.1 Machine Learning Objective

The ML engine's purpose is **advisory analytics** — it predicts future parking occupancy and identifies usage patterns to provide actionable intelligence. The ML system is strictly read-only: it observes historical data and generates predictions. It **never** controls the physical barrier or directly influences hardware behavior.

**Key Principle:** AI is advisory. The barrier is rule-based. The ML engine cannot open or close the gate.

## 6.2 ML Pipeline Overview

```
Step 1:  Load raw events from occupancy_log table
            │
Step 2:  Parse timestamps, extract features (hour, day_of_week, is_weekend)
            │
Step 3:  Compute hourly aggregations (avg_occupancy, event_count, net_flow)
            │
Step 4:  Engineer additional features (rolling_avg_3, utilization_pct)
            │
Step 5:  Train Model 1 — Moving Average Predictor (window=3)
            │
Step 6:  Train Model 2 — Linear Regression (hour → avg_occupancy)
            │
Step 7:  Generate next-hour prediction (clamped to 0-4)
            │
Step 8:  Detect peak hours (highest average occupancy window)
            │
Step 9:  Compute overall utilization (avg across all data)
            │
Step 10: Save prediction to database + save model to disk
```

## 6.3 Data Loading & Feature Engineering

### Source Data
- **Table:** `occupancy_log`
- **Columns used:** `event_time`, `event_type`, `occupancy_after`
- **Volume:** 581 events (14 synthetic days)

### Feature Extraction (Step 2)

When loading events, the following features are extracted from the `event_time` timestamp:

| Feature | Type | Extraction | Example |
|---|---|---|---|
| `hour` | int (0-23) | `timestamp.hour` | 14 (2:00 PM) |
| `day_of_week` | int (0-6) | `timestamp.weekday()` | 0 (Monday) |
| `is_weekend` | int (0 or 1) | `1 if day_of_week >= 5 else 0` | 0 (weekday) |
| `occupancy_after` | int (0-4) | Direct from event | 3 |
| `event_type` | string | Direct from event | "ENTRY" |

### Hourly Aggregation (Step 3)

Events are grouped by hour (0-23) to create training samples:

| Aggregated Feature | Formula | Purpose |
|---|---|---|
| `avg_occupancy` | `mean(occupancy_after)` for each hour | Target variable for regression |
| `event_count` | `count(*)` for each hour | Activity level indicator |
| `net_flow` | `count(ENTRY) - count(EXIT)` for each hour | Directional trend |

### Additional Feature Engineering (Step 4)

| Feature | Formula | Purpose |
|---|---|---|
| `rolling_avg_3` | 3-period rolling mean of `avg_occupancy` | Smoothed trend |
| `utilization_pct` | `(avg_occupancy / MAX_CAPACITY) * 100` | Percentage utilization |

### Training Data Summary

| Metric | Value |
|---|---|
| Source events | 581 |
| Hourly training samples | 225 |
| Feature columns | 7 |
| Target variable | `avg_occupancy` |

## 6.4 Model 1: Moving Average Predictor

### Algorithm
The simplest model — a window-based average of recent occupancy values.

### Formula
```
prediction = (O[t] + O[t-1] + O[t-2]) / 3
```

Where `O[t]` is the most recent hourly average occupancy, and `window = 3`.

### Properties

| Property | Value |
|---|---|
| Type | Statistical (non-parametric) |
| Window size | 3 data points |
| Training required | No (uses last N values) |
| Interpretability | Very high — simple average |
| Strengths | Responsive to recent changes, no overfitting |
| Weaknesses | No time-of-day awareness, lag on sudden changes |

### Edge Cases
- If fewer than 3 values available, uses whatever is available
- If only 1 value, returns that value directly
- If empty input, returns 0

## 6.5 Model 2: Time Regression Model

### Algorithm
Scikit-learn `LinearRegression` that maps hour-of-day to average occupancy.

### Training

```python
X = [[0], [1], [2], ..., [23]]   # Hour of day (0-23)
y = [avg_occ_0, avg_occ_1, ..., avg_occ_23]   # Avg occupancy per hour
```

### Model Equation

```
predicted_occupancy = β₀ + β₁ × hour
```

Where `β₀` (intercept) and `β₁` (slope) are learned from the training data.

### Properties

| Property | Value |
|---|---|
| Type | Supervised regression |
| Library | scikit-learn 1.4+ |
| Algorithm | Ordinary Least Squares (OLS) |
| Features | 1 (hour of day) |
| Target | Average occupancy |
| Training time | < 1 second |
| Model file | `models/occupancy_model.pkl` (saved via joblib) |

### Performance Metrics

| Metric | Value | Interpretation |
|---|---|---|
| **MAE** | **0.918** | On average, prediction is off by less than 1 vehicle |
| Training samples | 225 | Hourly averages from 14 days |
| Prediction range | 0 to 4 | Hard-clamped to valid range (`max(0, min(4, pred))`) |

### Prediction Clamping
The model output is always clamped to the valid range `[0, MAX_CAPACITY]`:
```python
prediction = max(0, min(MAX_CAPACITY, raw_prediction))
```
This ensures the model never predicts negative occupancy or exceeds physical capacity.

## 6.6 Peak Hour Detection

The system identifies the hour with the highest average occupancy:

```python
peak_hour = hourly_data.loc[hourly_data['avg_occupancy'].idxmax()]
peak_start = f"{peak_hour['hour']:02d}:00"
peak_end = f"{(peak_hour['hour'] + 1) % 24:02d}:00"
```

### Current Results

| Metric | Value |
|---|---|
| Peak hour start | 06:00 |
| Peak hour end | 24:00 |
| Peak avg occupancy | Varies by data |

## 6.7 Overall Utilization

```python
utilization = (mean(all_avg_occupancy) / MAX_CAPACITY) * 100
```

### Current Results

| Metric | Value |
|---|---|
| Average utilization | **51.3%** |
| Interpretation | The parking lot is about half-used on average |

## 6.8 Model Persistence

| Item | Path | Format |
|---|---|---|
| Trained model | `models/occupancy_model.pkl` | joblib-serialized sklearn model |
| Predictions | `predictions` table in SQLite | Database rows |

The model is saved to disk after each training run and can be loaded for inference without retraining.

## 6.9 Synthetic Data Generation

The ML engine is trained on synthetic data generated by `data_generator.py`:

### Arrival Rate Model

Events are generated using **Poisson process** with time-varying rates (λ):

| Time Period | Weekday λ | Weekend λ | Description |
|---|---|---|---|
| 00:00 - 05:59 | 0.1 | 0.05 | Very low (night) |
| 06:00 - 08:59 | 1.5 | 0.3 | Morning rush (weekday) |
| 09:00 - 11:59 | 1.0 | 0.8 | Mid-morning |
| 12:00 - 13:59 | 1.8 | 1.0 | Lunch peak |
| 14:00 - 16:59 | 1.2 | 0.7 | Afternoon |
| 17:00 - 18:59 | 1.5 | 0.5 | Evening rush |
| 19:00 - 23:59 | 0.3 | 0.2 | Evening low |

### Event State Machine

```
IF random() < 0.5 AND count < MAX_CAPACITY:
    event = "ENTRY", count += 1
ELIF count > 0:
    event = "EXIT", count -= 1
```

### Generated Dataset Statistics

| Metric | Value |
|---|---|
| Days generated | 14 (Mar 10 - Mar 23, 2026) |
| Total events | 581 |
| Avg events/day | 41.5 |
| Weekdays | 10 |
| Weekends | 4 |

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
