# GlucoTwin AI - System Architecture & Engineering Contracts

**Document Version:** 1.0.0  
**Status:** Approved Architectural Baseline  
**Scope:** Full-Stack Architecture, Data Segregation, API Boundaries, Database Contracts, and Security Model  

---

## 1. System Overview & Core Objectives

GlucoTwin AI is an academic and research-oriented digital twin platform engineered to simulate, forecast, and explore glucose-insulin dynamics in individuals with Type 1 Diabetes (T1D). 

### Architectural Core Tenets:
1. **Strict 4-Tier Data Segregation:** Observed, Derived, Predicted, and Hypothetical data models are isolated at the database, schema, API, and UI layers.
2. **Deterministic Physiological & Statistical Modeling:** Transparent, verifiable models (Bergman Minimal Model ODEs and ARX-Kalman state estimators) are used exclusively. No black-box or paid commercial LLM APIs are used for medical forecasting or risk scoring.
3. **Fail-Closed Clinical Safety Guardrail:** The platform strictly refuses to calculate or output insulin dosing, medication alterations, or clinical treatment advice. When data freshness or model convergence is doubtful, the engine **abstains**.
4. **Synthetic Data Exclusively:** All datasets are generated deterministically or probabilistically through validated synthetic physiological profiles.

---

## 2. Technology Stack & Component Architecture

```
+-----------------------------------------------------------------------------------+
|                              Frontend Client (Vite + React)                       |
|  - AGP Modal & Multi-Trace Trajectory View                                        |
|  - What-If Perturbation Controls (Carbs, Activity, Timing)                         |
|  - Clinical Disclaimer & Refusal Indicators                                       |
+----------------------------------------+------------------------------------------+
                                         | JSON over HTTP / REST (JWT Bearer Auth)
                                         v
+-----------------------------------------------------------------------------------+
|                           Backend Gateway (FastAPI 0.111+)                        |
|  - CORS & Request Origin Validator                                                |
|  - JWT Authentication & RBAC Middleware                                           |
|  - Rate Limiting & Input Sanitization                                             |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         Core Service Layer (Python 3.12)                          |
|  +------------------------+  +--------------------------+  +-------------------+  |
|  | app.services.twin      |  | app.services.metrics     |  | app.services.data |  |
|  | - Bergman ODE Engine   |  | - TIR / TAR / TBR (ATTD) |  | - Synthetic Cohort|  |
|  | - ARX-Kalman Estimator |  | - CV% & GMI Calculator   |  |   Generator       |  |
|  +------------------------+  +--------------------------+  +-------------------+  |
|                                        |                                          |
|                                        v                                          |
|                      +-----------------------------------+                        |
|                      | app.core.guardrails               |                        |
|                      | - Dosing Refusal Blocker          |                        |
|                      | - Abstention Logic & Audit Logger |                        |
|                      +-----------------------------------+                        |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                      Persistence Layer (SQLAlchemy 2.0 Async)                     |
|  - Target Engine: PostgreSQL 16 (via asyncpg driver)                              |
|  - Offline Dev / Test Fallback: SQLite 3 (via aiosqlite driver)                   |
|  - Migration Management: Alembic versioned migrations                             |
+-----------------------------------------------------------------------------------+
```

---

## 3. Backend Module Boundaries

The backend application is structured within `backend/app/` to enforce clean separation of concerns:

- `app.core`: System-level singletons:
  - `config.py`: Environment configuration via Pydantic Settings (`.env`).
  - `security.py`: Cryptographic primitives, bcrypt password hashing, JWT encoding/decoding.
  - `database.py`: Async engine factory, connection pooling, and `get_db` session dependency.
  - `guardrails.py`: Output filter intercepting payload text/structures for forbidden dosing advice.
- `app.models`: SQLAlchemy 2.0 declarative database entities with explicit constraints and indexes.
- `app.schemas`: Pydantic v2 validation contracts divided by data class:
  - `schemas.observed`: Sensor telemetry, meal events, activity records.
  - `schemas.derived`: Glycemic statistics (TIR, TAR, TBR, GMI, CV).
  - `schemas.predicted`: Short-term ARX-Kalman forecasts with confidence intervals.
  - `schemas.hypothetical`: What-If counterfactual scenario inputs and simulation trajectories.
  - `schemas.envelope`: Standardized success, error, and abstention response wrappers.
- `app.services`: Domain logic isolated from web transport:
  - `physiological_model.py`: Bergman Minimal Model differential equations solved via `scipy.integrate.solve_ivp`.
  - `arx_kalman.py`: AutoRegressive exogenous filter and Kalman filter state estimation.
  - `metrics_service.py`: Standard international consensus glycemic metrics.
  - `synthetic_data.py`: Patient cohort parameter generator.
  - `audit_service.py`: Asynchronous compliance and guardrail trigger logger.
- `app.api.v1`: FastAPI versioned router endpoints:
  - `auth.py`: Token issuance (`/auth/demo-session`), revocation (`/auth/logout`), current profile (`/auth/me`).
  - `patients.py`: Patient demographic queries (`/patients/`), detail (`/patients/{id}`), scenario selection (`/patients/scenario/{name}`).
  - `observations.py`: Multi-modal sensor observation ingestion (`/observations/ingest`) with unit conversion and concurrent idempotency.
  - `telemetry.py`: Historical continuous telemetry stream retrieval (`/telemetry/{patient_id}`) and legacy batch ingestion.
  - `metrics.py`: International consensus glycemic metrics (`/metrics/summary/{patient_id}`) and hourly AGP quantiles (`/metrics/agp/{patient_id}`).
  - `forecast.py`: Digital-twin ARX-Kalman multi-horizon forecasting with analytical 95% confidence intervals (`/forecast/run`).
  - `simulation.py`: Bergman ODE counterfactual what-if perturbation simulator (`/simulation/what-if`).
  - `protected.py`: RBAC validation test routes (`/protected/clinician-only`, `/protected/admin-only`).
  - `health.py` & `ready.py`: Liveness (`/health`) and comprehensive readiness (`/ready`) verifying database connectivity, migration status, and model artifact SHA-256 integrity.

---

## 4. Frontend / Backend Communication Contract

- **Protocol:** RESTful HTTPS with JSON payloads.
- **Authentication:** All protected endpoints require an `Authorization: Bearer <JWT>` header.
- **Status Codes:** Standard HTTP semantics:
  - `200 OK`: Successful read or simulation completion.
  - `201 Created`: Successful resource creation (e.g., patient, telemetry batch).
  - `400 Bad Request`: Validation failure or malformed payload.
  - `401 Unauthorized`: Missing, expired, or invalid JWT.
  - `403 Forbidden`: Insufficient role permissions.
  - `404 Not Found`: Target patient or resource does not exist.
  - `422 Unprocessable Entity`: Semantic constraint failure (e.g. glucose out of range).
  - `500 Internal Server Error`: Sanitized server failure (stack traces strictly suppressed).

---

## 5. Strict 4-Tier Data Segregation Contracts

To prevent catastrophic confusion between historical facts, mathematical abstractions, and counterfactual speculations, data is partitioned into four distinct tiers:

| Tier | Category | Definition | Allowed Ingestion Source | Storage Table | Can Be Used As Model Input? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Observed** | Historical telemetry and real events. | Ingestion API / Synthetic Sensor Stream | `telemetry_records` | Yes (Ground truth) |
| **Tier 2** | **Derived** | Pure mathematical calculations derived from Tier 1. | `metrics_service.py` | `glycemic_metrics` | Yes (Analytical context) |
| **Tier 3** | **Predicted** | Forward-looking estimates of the true trajectory ($15–60 \text{ min}$). | `arx_kalman.py` | `forecast_runs` | No (Never feed predictions back into history) |
| **Tier 4** | **Hypothetical** | Simulated outcomes under artificial perturbations ("What-If"). | `twin_engine.py` / ODE | `simulation_scenarios` | No (Strictly segregated from observed history) |

---

## 6. Response Envelopes, Abstentions, and Errors

Every API response uses a deterministic envelope structure.

### 6.1 Success Envelope
```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "timestamp": "2026-10-20T12:00:00Z",
    "request_id": "req-9b1c7f42-4e6a",
    "model_version": "arx-kalman-v1.0.0"
  }
}
```

### 6.2 Error Envelope
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Input glucose value 38.0 mg/dL is below physiological validity limit (40.0 mg/dL).",
    "details": [
      {
        "field": "glucose_mg_dl",
        "issue": "VALUE_BELOW_MINIMUM",
        "limit": 40.0
      }
    ]
  },
  "metadata": {
    "timestamp": "2026-10-20T12:00:00Z",
    "request_id": "req-9b1c7f42-4e6a"
  }
}
```

### 6.3 Forecast Abstention Envelope
When conditions violate data freshness, history length, or physiological bounds, the engine **fails closed** and abstains rather than returning an unreliable forecast:
```json
{
  "success": true,
  "data": {
    "status": "abstained",
    "forecast": null,
    "abstention": {
      "code": "DATA_TOO_STALE",
      "reason": "Latest telemetry timestamp is 28 minutes old (freshness limit is 15 minutes).",
      "recommended_action": "Ensure CGM synthetic telemetry stream is actively transmitting."
    }
  },
  "metadata": {
    "timestamp": "2026-10-20T12:00:00Z",
    "request_id": "req-9b1c7f42-4e6a",
    "model_version": "arx-kalman-v1.0.0"
  }
}
```

#### Standard Abstention Codes:
| Abstention Code | Trigger Condition | System Action |
| :--- | :--- | :--- |
| `DATA_TOO_STALE` | Latest telemetry sample > 15 minutes old. | Abstain from forecasting; return last valid status. |
| `INSUFFICIENT_HISTORY` | Telemetry duration < 60 minutes (fewer than 12 contiguous readings). | Abstain until minimum historical buffer accumulates. |
| `SENSOR_GAP_EXCEEDED` | Missing sensor gap within the last 60 minutes > 15 minutes. | Abstain; linear interpolation buffer exceeded. |
| `PHYSIOLOGICAL_ANOMALY`| Glucose reading outside [40.0, 500.0] mg/dL. | Abstain; reject reading as sensor artifact. |
| `MODEL_DIVERGENCE_ABSTAIN` | Kalman filter state estimation covariance exceeds numerical threshold. | Abstain; reset filter state. |

---

## 7. Patient-Level Splitting & Leakage Prevention Protocol

To guarantee scientific rigor in model evaluation:

1. **Patient-Level Segregation (Strict Partitioning):**
   - Telemetry from any single patient $P_i$ resides **strictly in one partition**: Train (70%), Validation (15%), or Test (15%).
   - Random cross-time slicing across patients is strictly forbidden, as intra-patient metabolic correlation causes severe data leakage.
2. **Temporal Integrity within Patients:**
   - When tuning patient-specific adaptive Kalman parameters, training data must strictly precede validation/testing chronologically ($t_{train} < t_{val} < t_{test}$).
3. **Feature Preprocessing Independence:**
   - Normalization statistics (means, standard deviations) are computed exclusively on the Training cohort and applied to Validation/Test sets without recalculation.

---

## 8. Authentication Roles & Trust Boundaries

| Role | Permissions | Forbidden Operations |
| :--- | :--- | :--- |
| **`researcher`** | Ingest synthetic telemetry, execute forecasts, run what-if simulations, export aggregate metrics. | User management, modification of audit logs. |
| **`clinician_observer`** | Read-only access to AGP metrics, patient profiles, and completed simulation summaries. | Ingesting data, executing what-if perturbations, modifying configs. |
| **`auditor`** | Read-only access to system audit logs, guardrail refusal events, and model validation cards. | Modifying any patient data or system configuration. |

### Trust Boundaries:
- **Boundary 1 (External Web -> Gateway):** Untrusted boundary. Enforces HTTPS, CORS, rate limits, Pydantic input schema validation, and JWT verification.
- **Boundary 2 (Service Layer -> Physiological Core):** Internal boundary. Enforces parameter ranges and fail-closed numerical stability checks ($dt \ge 1 \text{ min}$, duration $\le 1440 \text{ min}$).
- **Boundary 3 (Service Layer -> Output Filter):** Clinical guardrail boundary. All generated text/JSON is scanned by `RefusalFilter` to ensure zero clinical dose advice leaves the backend.

---

## 9. Model & Artifact Versioning Specification

All model weights, parameter sets, and ODE calibration tables are tracked with immutable semantic versions and cryptographic hashes:

| Artifact Name | Version Format | File Format | Checksum Algorithm | Storage Location |
| :--- | :--- | :--- | :--- | :--- |
| `arx_kalman_weights` | `vX.Y.Z` (e.g. `v1.0.0`) | `.npz` / `.json` | SHA-256 | `backend/app/models/artifacts/` |
| `bergman_parameters` | `vX.Y.Z` (e.g. `v1.0.0`) | `.json` | SHA-256 | `backend/app/models/artifacts/` |
| `synthetic_cohort_seed` | `seed-YYYYMMDD-N` | `.json` | SHA-256 | `backend/app/data/synthetic/` |

Every forecast and simulation response header and metadata block records the active `model_version` and artifact SHA-256 checksum to guarantee end-to-end reproducibility.
