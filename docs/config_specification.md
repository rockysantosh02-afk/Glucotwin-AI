# GlucoTwin AI - Single Configuration Specification

**Specification Version:** 1.0.0  
**Status:** Approved Architectural Contract  
**Applies To:** Backend, Frontend, Feature Engineering, Simulation Engines, and Database Schema  

---

## 1. Overview & Authority

This document defines the single source of truth for all physical units, clinical thresholds, forecast horizons, data freshness bounds, telemetry history requirements, and event definitions across the entire GlucoTwin AI platform. 

Every backend validation schema, frontend visualization component, physiological simulator, and database column **must strictly comply** with these definitions. No module is permitted to define ad-hoc units or alternative thresholds.

---

## 2. Standard Physical Units

| Domain | Entity / Metric | Canonical Unit | Alternate / Forbidden Units | Description & Precision |
| :--- | :--- | :--- | :--- | :--- |
| **Glucose** | Blood / Interstitial Glucose | **`mg/dL`** | `mmol/L` (must convert at display if needed: $1 \text{ mmol/L} = 18.0182 \text{ mg/dL}$) | Standard US/clinical research unit. Stored as float rounded to 1 decimal place. |
| **Carbohydrates** | Meal / Snack Ingestion | **`grams` (g)** | `ounces`, `exchanges` | Macronutrient carbohydrate mass. Float >= 0.0. |
| **Synthetic Insulin** | Basal & Bolus Delivery | **`synthetic_units` (U)** | Real drug brand names (forbidden) | Research simulation parameter. Float >= 0.0, step 0.05. |
| **Time / Horizon** | Sampling & Forecasts | **`minutes` (min)** | `seconds`, `hours` | Discrete simulation time step $\Delta t = 5 \text{ min}$. |
| **Timestamps** | All recorded events | **`ISO 8601 UTC`** | Local non-timezone strings | Format: `YYYY-MM-DDTHH:MM:SSZ` (e.g. `2026-10-20T12:00:00Z`). |
| **Rate of Change** | Glucose Velocity | **`mg/dL/min`** | `mg/dL/hour` | Velocity of glucose shift: $\frac{G_t - G_{t-1}}{\Delta t}$. |
| **Body Weight** | Patient Demographics | **`kg`** | `lbs` | Stored as float rounded to 1 decimal place. |
| **Sensitivity** | Insulin Sensitivity (ISF) | **`mg/dL/U`** | `mmol/L/U` | Expected drop in glucose per synthetic unit of insulin. |
| **Carb Ratio** | Insulin-to-Carb (ICR) | **`g/U`** | `U/g` | Grams of carbohydrate covered by 1 synthetic unit of insulin. |

---

## 3. Glycemic Classification Thresholds

Standardized according to the International Consensus on Time in Range (ATTD / ADA 2019 standards):

| Classification | Threshold Range (mg/dL) | Clinical Target (%) | Description |
| :--- | :--- | :--- | :--- |
| **Level 2 Hypoglycemia (Severe)** | `< 54.0` | `< 1.0%` | Severe, neuroglycopenic risk zone requiring urgent alert. |
| **Level 1 Hypoglycemia (Mild)** | `[54.0, 70.0)` | `< 4.0%` (combined < 70) | Hypoglycemic threshold. |
| **Target In Range (TIR)** | `[70.0, 180.0]` | `> 70.0%` | Safe, target physiological window. |
| **Level 1 Hyperglycemia (Mild)** | `(180.0, 250.0]` | `< 25.0%` (combined > 180) | Elevated glycemic excursion zone. |
| **Level 2 Hyperglycemia (Severe)** | `> 250.0` | `< 5.0%` | Severe hyperglycemia, diabetic ketoacidosis (DKA) risk zone. |
| **Physiological Validity Limits** | `[40.0, 500.0]` | — | Readings outside this boundary indicate sensor error or artifact. |

---

## 4. Forecasting Horizons & Resolutions

The predictive forecasting engine evaluates trajectories across four fixed horizons:

| Horizon Name | Duration ($\tau$) | Discrete Steps ($N$) | Allowed Tolerance | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **H15** | **15 minutes** | 3 steps ($\Delta t = 5$) | $\pm 0$ steps | Immediate hypoglycemic avoidance warning. |
| **H30** | **30 minutes** | 6 steps ($\Delta t = 5$) | $\pm 0$ steps | Postprandial trajectory verification. |
| **H45** | **45 minutes** | 9 steps ($\Delta t = 5$) | $\pm 0$ steps | Mid-range metabolic absorption assessment. |
| **H60** | **60 minutes** | 12 steps ($\Delta t = 5$) | $\pm 0$ steps | Full hour exploratory trend forecast. |

---

## 5. Telemetry Freshness & History Requirements

To ensure prediction integrity and avoid ungrounded extrapolation, the engine enforces strict freshness and history constraints before computing any forecast:

| Requirement Parameter | Value | Enforcement Action if Violating |
| :--- | :--- | :--- |
| **CGM Sampling Rate** | **5 minutes** ($\pm 1 \text{ min}$) | Interpolate linearly if gap is exactly 1 missing step (5–10 min). |
| **Maximum Data Age (Freshness)** | **15 minutes** | **Abstain** (return `status="abstained"`, reason: `DATA_TOO_STALE`). |
| **Minimum Contiguous History** | **60 minutes** (12 points) | **Abstain** (return `status="abstained"`, reason: `INSUFFICIENT_HISTORY`). |
| **Optimal Context History** | **180 minutes** (36 points) | Use full context for optimal ARX-Kalman filter stabilization. |
| **Maximum Allowed Gap in Context** | **15 minutes** (3 missing points) | If gap $> 15 \text{ min}$ occurs within the last 60 minutes, **Abstain**. |
| **Glucose Out-of-Bounds** | $< 40.0$ or $> 500.0 \text{ mg/dL}$ | **Abstain** (return `status="abstained"`, reason: `PHYSIOLOGICAL_ANOMALY`). |

---

## 6. Dynamic Event Definitions

Dynamic physiological events are detected by analyzing consecutive telemetry samples:

| Event Type | Mathematical Condition | Significance & Handling |
| :--- | :--- | :--- |
| **Rapid Rise** | $\frac{dG}{dt} > +2.0 \text{ mg/dL/min}$ over 3 consecutive steps | Postprandial carb spike or rapid counter-regulatory response. Flag in telemetry metadata. |
| **Rapid Fall** | $\frac{dG}{dt} < -2.0 \text{ mg/dL/min}$ over 3 consecutive steps | Rapid insulin absorption or post-exercise drop. High acute hypoglycemia risk. |
| **Stable Trend** | $-1.0 \le \frac{dG}{dt} \le +1.0 \text{ mg/dL/min}$ | Steady state metabolism. |
| **Prolonged Hypoglycemia** | $G_t < 70.0 \text{ mg/dL}$ for $\ge 30 \text{ minutes}$ | Extended low event. Triggers high-priority safety banner in UI. |
| **Prolonged Hyperglycemia** | $G_t > 250.0 \text{ mg/dL}$ for $\ge 120 \text{ minutes}$ | Extended high excursion event. |
| **Sensor Disconnect / Gap** | $t_k - t_{k-1} > 15 \text{ minutes}$ | Sensor dropout. Resets ARX autoregressive lag buffer until 12 continuous readings reaccumulate. |

---

## 7. What-If Simulation Perturbation Bounds

For counterfactual "What-If" explorations, perturbations must fall within reasonable physiological bounds:

| Parameter | Minimum Value | Maximum Value | Default Step | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Carb Delta** ($\Delta C$) | `-100.0 g` | `+150.0 g` | `5.0 g` | Simulated meal size variation. |
| **Meal Timing Shift** ($\Delta t_{meal}$) | `-60 min` | `+120 min` | `15 min` | Simulating earlier or delayed meal ingestion. |
| **Exercise Intensity** ($I_{ex}$) | `0 (None)` | `3 (Vigorous)` | `1` | 0: None, 1: Light walking, 2: Moderate jogging, 3: High intensity. |
| **Exercise Duration** ($D_{ex}$) | `0 min` | `180 min` | `15 min` | Physical activity duration. |
| **Max Simulation Duration** | `60 min` | `1440 min (24h)` | `60 min` | Bound on ODE numerical integration time. |
