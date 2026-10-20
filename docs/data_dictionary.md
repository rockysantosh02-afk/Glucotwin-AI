# GlucoTwin AI - Database Data Dictionary & Entity Contracts

**Document Version:** 1.0.0  
**Status:** Approved Architectural Baseline  
**ORM Framework:** SQLAlchemy 2.0 (Declarative Async)  
**Database Engines:** PostgreSQL 16 (Primary) / SQLite 3 (Dev/Test Fallback)  
**Migration Tool:** Alembic  

---

## 1. Entity-Relationship Overview

```
 [users] 
    | 
    +---> [audit_logs] (user_id FK, nullable)

 [synthetic_patients]
    |
    +---> [telemetry_records]   (Tier 1: Observed)
    +---> [glycemic_metrics]    (Tier 2: Derived)
    +---> [forecast_runs]       (Tier 3: Predicted)
    +---> [simulation_scenarios] (Tier 4: Hypothetical)
```

---

## 2. Table Specifications

### 2.1 Table: `users`
Stores user accounts for researchers, clinician-observers, and auditors.

| Column Name | SQL Type (PG / SQLite) | Nullable | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | No | UUID4 string | **PRIMARY KEY** | Unique user identifier. |
| `username` | `VARCHAR(50)` | No | — | **UNIQUE**, Indexed | Unique login handle. |
| `email` | `VARCHAR(255)` | No | — | **UNIQUE**, Indexed | User email address. |
| `hashed_password` | `VARCHAR(255)` | No | — | — | Bcrypt hash of user password. |
| `role` | `VARCHAR(30)` | No | `'researcher'` | CHECK (`role IN ('demo_clinician', 'clinician', 'admin', 'researcher', 'clinician_observer', 'auditor')`) | Role-based authorization tier. |
| `is_active` | `BOOLEAN` | No | `TRUE` | — | Account status flag. |
| `created_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Account creation timestamp (UTC). |
| `updated_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Last update timestamp (UTC). |

---

### 2.2 Table: `synthetic_patients`
Stores synthetic patient metabolic demographics and baseline physiological parameters.

| Column Name | SQL Type (PG / SQLite) | Nullable | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | No | UUID4 string | **PRIMARY KEY** | Unique synthetic patient ID. |
| `patient_code` | `VARCHAR(30)` | No | — | **UNIQUE**, Indexed | Human-readable identifier (e.g. `SYN-T1D-001`). |
| `diabetes_type` | `VARCHAR(10)` | No | `'T1D'` | CHECK (`diabetes_type IN ('T1D', 'T2D')`) | Classification of diabetes model. |
| `age` | `INTEGER` | No | — | CHECK (`age >= 18 AND age <= 85`) | Synthetic patient age (years). |
| `body_weight_kg` | `FLOAT` | No | — | CHECK (`body_weight_kg >= 40.0 AND body_weight_kg <= 150.0`) | Body weight in kilograms. |
| `basal_rate_synthetic` | `FLOAT` | No | — | CHECK (`basal_rate_synthetic >= 0.1 AND basal_rate_synthetic <= 3.0`) | Baseline hourly synthetic basal insulin rate (U/hr). |
| `insulin_sensitivity_factor` | `FLOAT` | No | — | CHECK (`insulin_sensitivity_factor >= 10.0 AND insulin_sensitivity_factor <= 150.0`) | ISF: Glucose drop per synthetic unit (mg/dL/U). |
| `carb_ratio` | `FLOAT` | No | — | CHECK (`carb_ratio >= 3.0 AND carb_ratio <= 30.0`) | ICR: Grams of carbohydrate per synthetic unit (g/U). |
| `target_glucose_min` | `FLOAT` | No | `70.0` | CHECK (`target_glucose_min >= 70.0`) | Target lower bound (mg/dL). |
| `target_glucose_max` | `FLOAT` | No | `180.0` | CHECK (`target_glucose_max <= 180.0`) | Target upper bound (mg/dL). |
| `created_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Creation timestamp (UTC). |
| `updated_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Last update timestamp (UTC). |

---

### 2.3 Table: `telemetry_records` (Tier 1: Observed)
Ingests and stores observed time-series data: continuous glucose readings, meal carbohydrate logs, and activity events.

| Column Name | SQL Type (PG / SQLite) | Nullable | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | No | UUID4 string | **PRIMARY KEY** | Unique telemetry record identifier. |
| `patient_id` | `VARCHAR(36)` | No | — | **FOREIGN KEY** (`synthetic_patients.id`) ON DELETE CASCADE | Associated patient. |
| `timestamp` | `TIMESTAMPTZ` / `DATETIME` | No | — | Indexed | Sensor recording timestamp (UTC). |
| `glucose_mg_dl` | `FLOAT` | No | — | CHECK (`glucose_mg_dl >= 40.0 AND glucose_mg_dl <= 500.0`) | Measured interstitial glucose (mg/dL). |
| `rate_of_change` | `FLOAT` | Yes | `0.0` | — | Rate of glucose shift: $(G_t - G_{t-1})/\Delta t$ in mg/dL/min. |
| `sensor_status` | `VARCHAR(20)` | No | `'OK'` | CHECK (`sensor_status IN ('OK', 'CALIBRATING', 'NOISE', 'ERROR')`) | Sensor operational status. |
| `meal_carbs_grams` | `FLOAT` | Yes | `0.0` | CHECK (`meal_carbs_grams >= 0.0 AND meal_carbs_grams <= 300.0`) | Ingested carbohydrate mass in grams. |
| `bolus_synthetic_units` | `FLOAT` | Yes | `0.0` | CHECK (`bolus_synthetic_units >= 0.0 AND bolus_synthetic_units <= 50.0`) | Synthetic meal bolus delivered (U). |
| `activity_minutes` | `FLOAT` | Yes | `0.0` | CHECK (`activity_minutes >= 0.0 AND activity_minutes <= 360.0`) | Duration of physical exercise (minutes). |
| `activity_intensity` | `INTEGER` | Yes | `0` | CHECK (`activity_intensity >= 0 AND activity_intensity <= 3`) | Intensity level (0: None, 1: Light, 2: Moderate, 3: Heavy). |
| `created_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Ingestion timestamp (UTC). |

**Table Constraints & Indexes:**
- **Unique Constraint:** `uq_patient_timestamp` on `(patient_id, timestamp)`. Prevents duplicate sensor readings.
- **Index:** `ix_telemetry_patient_time` on `(patient_id, timestamp DESC)`. Crucial for high-speed time-series window queries.

---

### 2.4 Table: `glycemic_metrics` (Tier 2: Derived)
Stores aggregated Ambulatory Glucose Profile (AGP) and clinical consensus metrics computed over historical windows.

| Column Name | SQL Type (PG / SQLite) | Nullable | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | No | UUID4 string | **PRIMARY KEY** | Unique metrics record identifier. |
| `patient_id` | `VARCHAR(36)` | No | — | **FOREIGN KEY** (`synthetic_patients.id`) ON DELETE CASCADE | Target patient. |
| `window_start` | `TIMESTAMPTZ` / `DATETIME` | No | — | Indexed | Analysis period start (UTC). |
| `window_end` | `TIMESTAMPTZ` / `DATETIME` | No | — | Indexed | Analysis period end (UTC). |
| `total_readings` | `INTEGER` | No | — | CHECK (`total_readings >= 1`) | Total CGM data points in window. |
| `cgm_active_percentage` | `FLOAT` | No | — | CHECK (`cgm_active_percentage >= 0.0 AND cgm_active_percentage <= 100.0`) | Percentage of expected readings present. |
| `mean_glucose_mg_dl` | `FLOAT` | No | — | CHECK (`mean_glucose_mg_dl > 0.0`) | Mean glucose over window (mg/dL). |
| `standard_deviation` | `FLOAT` | No | — | CHECK (`standard_deviation >= 0.0`) | Standard deviation of glucose (mg/dL). |
| `cv_percentage` | `FLOAT` | No | — | CHECK (`cv_percentage >= 0.0`) | Coefficient of variation: $(SD / Mean) \times 100$. |
| `gmi_percentage` | `FLOAT` | No | — | CHECK (`gmi_percentage >= 4.0 AND gmi_percentage <= 18.0`) | Glucose Management Indicator: $3.31 + 0.02392 \times Mean$. |
| `tir_percentage` | `FLOAT` | No | — | CHECK (`tir_percentage >= 0.0 AND tir_percentage <= 100.0`) | Time in Range (70.0–180.0 mg/dL) %. |
| `tar_level1_percentage` | `FLOAT` | No | — | CHECK (`tar_level1_percentage >= 0.0 AND tar_level1_percentage <= 100.0`) | Time Above Range Level 1 (180.1–250.0 mg/dL) %. |
| `tar_level2_percentage` | `FLOAT` | No | — | CHECK (`tar_level2_percentage >= 0.0 AND tar_level2_percentage <= 100.0`) | Severe Hyperglycemia Level 2 (>250.0 mg/dL) %. |
| `tbr_level1_percentage` | `FLOAT` | No | — | CHECK (`tbr_level1_percentage >= 0.0 AND tbr_level1_percentage <= 100.0`) | Time Below Range Level 1 (54.0–69.9 mg/dL) %. |
| `tbr_level2_percentage` | `FLOAT` | No | — | CHECK (`tbr_level2_percentage >= 0.0 AND tbr_level2_percentage <= 100.0`) | Severe Hypoglycemia Level 2 (<54.0 mg/dL) %. |
| `created_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Calculation timestamp (UTC). |

---

### 2.5 Table: `forecast_runs` (Tier 3: Predicted)
Stores short-term predictive forecast outputs generated by the ARX-Kalman engine, along with abstention records.

| Column Name | SQL Type (PG / SQLite) | Nullable | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | No | UUID4 string | **PRIMARY KEY** | Unique forecast run identifier. |
| `patient_id` | `VARCHAR(36)` | No | — | **FOREIGN KEY** (`synthetic_patients.id`) ON DELETE CASCADE | Target patient. |
| `run_timestamp` | `TIMESTAMPTZ` / `DATETIME` | No | — | Indexed | Prediction execution time (UTC). |
| `model_version` | `VARCHAR(50)` | No | — | — | Semantic model version (e.g. `arx-kalman-v1.0.0`). |
| `horizon_minutes` | `INTEGER` | No | `60` | CHECK (`horizon_minutes IN (15, 30, 45, 60)`) | Forecast duration. |
| `status` | `VARCHAR(20)` | No | `'completed'` | CHECK (`status IN ('completed', 'abstained', 'failed')`) | Forecast result status. |
| `trajectory_json` | `TEXT` / `JSONB` | Yes | — | — | Serialized array of predicted glucose points $[G_{t+5}, \dots, G_{t+\tau}]$. |
| `uncertainty_lower_json` | `TEXT` / `JSONB` | Yes | — | — | 95% confidence interval lower bound array. |
| `uncertainty_upper_json` | `TEXT` / `JSONB` | Yes | — | — | 95% confidence interval upper bound array. |
| `abstention_code` | `VARCHAR(50)` | Yes | — | — | Code if abstained (e.g. `DATA_TOO_STALE`, `INSUFFICIENT_HISTORY`). |
| `abstention_reason` | `TEXT` | Yes | — | — | Human-readable explanation for abstention. |
| `created_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Record creation timestamp. |

---

### 2.6 Table: `simulation_scenarios` (Tier 4: Hypothetical)
Stores "What-If" counterfactual simulation parameter sets and resulting metabolic trajectories.

| Column Name | SQL Type (PG / SQLite) | Nullable | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | No | UUID4 string | **PRIMARY KEY** | Unique scenario identifier. |
| `patient_id` | `VARCHAR(36)` | No | — | **FOREIGN KEY** (`synthetic_patients.id`) ON DELETE CASCADE | Associated patient. |
| `scenario_name` | `VARCHAR(100)` | No | — | — | Descriptive label (e.g. `Postprandial Walk +20m`). |
| `simulation_duration_min` | `INTEGER` | No | `240` | CHECK (`simulation_duration_min >= 60 AND simulation_duration_min <= 1440`) | Simulation horizon in minutes. |
| `perturbation_params_json` | `TEXT` / `JSONB` | No | — | — | JSON object defining meal/exercise deltas. |
| `baseline_trajectory_json` | `TEXT` / `JSONB` | No | — | — | Ground-truth or unperturbed baseline trajectory. |
| `simulated_trajectory_json`| `TEXT` / `JSONB` | No | — | — | Counterfactual ODE trajectory under perturbation. |
| `tir_delta_percentage` | `FLOAT` | Yes | `0.0` | — | Change in predicted Time in Range ($\Delta TIR$). |
| `created_at` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | — | Execution timestamp (UTC). |

---

### 2.7 Table: `audit_logs`
Append-only ledger capturing sensitive operations, access events, and clinical guardrail interventions.

| Column Name | SQL Type (PG / SQLite) | Nullable | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | No | UUID4 string | **PRIMARY KEY** | Unique log entry ID. |
| `user_id` | `VARCHAR(36)` | Yes | — | **FOREIGN KEY** (`users.id`) ON DELETE SET NULL | Acting user, if authenticated. |
| `action` | `VARCHAR(100)` | No | — | Indexed | Action name (e.g. `SIMULATION_RUN`, `GUARDRAIL_BLOCKED`). |
| `resource_type` | `VARCHAR(50)` | No | — | — | Target entity (e.g. `patient`, `forecast`, `simulation`). |
| `resource_id` | `VARCHAR(36)` | Yes | — | — | Target identifier. |
| `guardrail_triggered` | `BOOLEAN` | No | `FALSE` | Indexed | `TRUE` if clinical refusal filter intervened. |
| `details_json` | `TEXT` / `JSONB` | Yes | — | — | Sanitized context / trigger reason. |
| `ip_address` | `VARCHAR(45)` | Yes | — | — | Client IP address. |
| `timestamp` | `TIMESTAMPTZ` / `DATETIME` | No | `CURRENT_TIMESTAMP` | Indexed | Event timestamp (UTC). |

---

## 3. Database Migration Strategy (Alembic)

1. **Dual Dialect Support:**
   - Table DDL uses universal SQLAlchemy types (`String(36)`, `DateTime(timezone=True)`, `Float`, `Boolean`, `Text`).
   - For PostgreSQL, JSON columns utilize native `JSONB`; for SQLite fallback, SQLAlchemy automatically serializes them to text representations (`JSON` type mapped to SQLite `TEXT`).
2. **Versioned Reversible Migrations:**
   - All migrations reside under `backend/alembic/versions/`.
   - Each migration file implements both `upgrade()` and `downgrade()`.
   - Automatic migrations are generated using `alembic revision --autogenerate -m "..."` and verified by code review before execution.
3. **Database Health Verification:**
   - On application startup (lifespan handler), the backend runs a lightweight `SELECT 1` connectivity probe and checks the current Alembic revision in the `alembic_version` table.
