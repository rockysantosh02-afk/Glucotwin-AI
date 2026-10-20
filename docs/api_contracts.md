# GlucoTwin AI - REST API Specifications & Contracts

**API Version:** `v1`  
**Base URL:** `/api/v1`  
**Transport:** HTTPS / JSON  
**Authentication Scheme:** HTTP Bearer (JWT)  

---

## 1. Global Envelope Standards

All responses conform to a unified envelope structure. Clients must parse the top-level `success` flag.

### 1.1 Success Envelope
```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "timestamp": "2026-10-20T12:00:00Z",
    "request_id": "req-9b1c7f42-4e6a",
    "version": "1.0.0"
  }
}
```

### 1.2 Error Envelope
```json
{
  "success": false,
  "error": {
    "code": "BAD_REQUEST",
    "message": "Input validation failed on telemetry stream.",
    "details": [
      {
        "field": "glucose_mg_dl",
        "issue": "VALUE_OUT_OF_BOUNDS",
        "message": "Value must be between 40.0 and 500.0 mg/dL"
      }
    ]
  },
  "metadata": {
    "timestamp": "2026-10-20T12:00:00Z",
    "request_id": "req-9b1c7f42-4e6a"
  }
}
```

### 1.3 Forecast Abstention Envelope
When telemetry freshness is violated or historical context is insufficient, the system returns HTTP 200 with `status="abstained"`.
```json
{
  "success": true,
  "data": {
    "status": "abstained",
    "forecast": null,
    "abstention": {
      "code": "DATA_TOO_STALE",
      "reason": "Latest telemetry timestamp is 28 minutes old (limit is 15 minutes).",
      "recommended_action": "Resume synthetic CGM transmission to regain predictive state."
    }
  },
  "metadata": {
    "timestamp": "2026-10-20T12:00:00Z",
    "request_id": "req-9b1c7f42-4e6a",
    "model_version": "arx-kalman-v1.0.0"
  }
}
```

#### Valid Abstention Codes:
- `DATA_TOO_STALE`: Latest telemetry sample is > 15 minutes old.
- `INSUFFICIENT_HISTORY`: Historical context duration is < 60 minutes (< 12 points).
- `SENSOR_GAP_EXCEEDED`: Missing sensor gap in window > 15 minutes.
- `PHYSIOLOGICAL_ANOMALY`: Glucose reading outside [40.0, 500.0] mg/dL.
- `MODEL_DIVERGENCE_ABSTAIN`: Kalman filter prediction variance exceeds stability threshold.

---

## 2. Authentication & User Endpoints

### 2.1 `POST /api/v1/auth/login`
Authenticate a user and obtain an access token.

- **Access:** Public
- **Request Body:**
```json
{
  "username": "researcher_jane",
  "password": "StrongPassword123!"
}
```
- **Response `200 OK`:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in_minutes": 60,
    "user": {
      "id": "usr-8a213e4b-9f01-4467-bc12-f47a61d8a012",
      "username": "researcher_jane",
      "email": "jane@research.org",
      "role": "researcher"
    }
  },
  "metadata": { "timestamp": "2026-10-20T12:00:00Z", "request_id": "req-01" }
}
```

---

## 3. Synthetic Patient Endpoints

### 3.1 `GET /api/v1/patients/`
List all synthetic patients in the cohort.

- **Access:** Authenticated (`researcher`, `clinician_observer`, `auditor`)
- **Query Params:** `skip` (default 0), `limit` (default 20, max 100)
- **Response `200 OK`:**
```json
{
  "success": true,
  "data": {
    "total": 10,
    "patients": [
      {
        "id": "pat-1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
        "patient_code": "SYN-T1D-001",
        "diabetes_type": "T1D",
        "age": 28,
        "body_weight_kg": 72.5,
        "basal_rate_synthetic": 0.85,
        "insulin_sensitivity_factor": 45.0,
        "carb_ratio": 10.0,
        "target_glucose_min": 70.0,
        "target_glucose_max": 180.0
      }
    ]
  },
  "metadata": { "timestamp": "2026-10-20T12:00:00Z", "request_id": "req-02" }
}
```

### 3.2 `GET /api/v1/patients/{id}`
Retrieve detailed demographic and metabolic profile of a specific synthetic patient.

- **Access:** Authenticated
- **Response `200 OK`:** Returns patient profile entity.
- **Response `404 Not Found`:** Patient ID does not exist.

---

## 4. Telemetry Endpoints (Tier 1: Observed)

### 4.1 `POST /api/v1/patients/{id}/telemetry`
Batch ingestion of observed synthetic sensor readings, meal logs, and activity events.

- **Access:** `researcher`
- **Request Body:**
```json
{
  "readings": [
    {
      "timestamp": "2026-10-20T11:55:00Z",
      "glucose_mg_dl": 142.5,
      "sensor_status": "OK",
      "meal_carbs_grams": 45.0,
      "bolus_synthetic_units": 4.5,
      "activity_minutes": 0.0,
      "activity_intensity": 0
    },
    {
      "timestamp": "2026-10-20T12:00:00Z",
      "glucose_mg_dl": 149.0,
      "sensor_status": "OK",
      "meal_carbs_grams": 0.0,
      "bolus_synthetic_units": 0.0,
      "activity_minutes": 0.0,
      "activity_intensity": 0
    }
  ]
}
```
- **Response `201 Created`:**
```json
{
  "success": true,
  "data": {
    "ingested_count": 2,
    "patient_id": "pat-1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
    "latest_reading_time": "2026-10-20T12:00:00Z"
  },
  "metadata": { "timestamp": "2026-10-20T12:00:01Z", "request_id": "req-03" }
}
```

### 4.2 `GET /api/v1/patients/{id}/telemetry`
Query historical observed telemetry over a time window.

- **Access:** Authenticated
- **Query Params:** `start_time` (ISO 8601), `end_time` (ISO 8601), `limit` (max 2000)
- **Response `200 OK`:** Returns time-ordered list of observed readings.

---

## 5. Glycemic Metrics Endpoints (Tier 2: Derived)

### 5.1 `GET /api/v1/patients/{id}/metrics`
Calculate consensus Ambulatory Glucose Profile (AGP) metrics over a historical window (default last 14 days or custom window).

- **Access:** Authenticated
- **Query Params:** `window_days` (default 14, min 1, max 90)
- **Response `200 OK`:**
```json
{
  "success": true,
  "data": {
    "patient_id": "pat-1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
    "window_start": "2026-10-06T12:00:00Z",
    "window_end": "2026-10-20T12:00:00Z",
    "total_readings": 4032,
    "cgm_active_percentage": 98.4,
    "mean_glucose_mg_dl": 138.2,
    "standard_deviation": 32.4,
    "cv_percentage": 23.4,
    "gmi_percentage": 6.6,
    "ranges": {
      "tir_percentage": 78.5,        // 70.0 - 180.0 mg/dL
      "tar_level1_percentage": 14.2, // 180.1 - 250.0 mg/dL
      "tar_level2_percentage": 3.1,  // > 250.0 mg/dL
      "tbr_level1_percentage": 3.4,  // 54.0 - 69.9 mg/dL
      "tbr_level2_percentage": 0.8   // < 54.0 mg/dL
    },
    "clinical_targets_met": {
      "tir_above_70": true,
      "tbr_below_4": true,
      "cv_below_36": true
    }
  },
  "metadata": { "timestamp": "2026-10-20T12:00:02Z", "request_id": "req-04" }
}
```

---

## 6. Digital Twin Forecast Endpoints (Tier 3: Predicted)

### 6.1 `POST /api/v1/patients/{id}/twin/forecast`
Run short-term forward trajectory forecasting using the ARX-Kalman engine.

- **Access:** `researcher`
- **Request Body:**
```json
{
  "horizon_minutes": 60,
  "include_uncertainty": true
}
```
- **Response `200 OK` (Completed):**
```json
{
  "success": true,
  "data": {
    "status": "completed",
    "horizon_minutes": 60,
    "run_timestamp": "2026-10-20T12:00:00Z",
    "model_version": "arx-kalman-v1.0.0",
    "baseline_glucose_mg_dl": 149.0,
    "forecast": [
      { "time_offset_min": 5, "predicted_glucose": 152.1, "ci_lower": 146.3, "ci_upper": 157.9 },
      { "time_offset_min": 10, "predicted_glucose": 155.8, "ci_lower": 148.2, "ci_upper": 163.4 },
      { "time_offset_min": 15, "predicted_glucose": 159.2, "ci_lower": 149.8, "ci_upper": 168.6 },
      { "time_offset_min": 30, "predicted_glucose": 167.4, "ci_lower": 152.0, "ci_upper": 182.8 },
      { "time_offset_min": 45, "predicted_glucose": 171.0, "ci_lower": 151.4, "ci_upper": 190.6 },
      { "time_offset_min": 60, "predicted_glucose": 169.5, "ci_lower": 145.8, "ci_upper": 193.2 }
    ],
    "predicted_risk": {
      "hypoglycemia_probability_60m": 0.02,
      "hyperglycemia_probability_60m": 0.28
    }
  },
  "metadata": {
    "timestamp": "2026-10-20T12:00:03Z",
    "request_id": "req-05",
    "model_version": "arx-kalman-v1.0.0"
  }
}
```
- **Response `200 OK` (Abstained):** If telemetry is older than 15 minutes or history is < 60 minutes, returns abstention envelope (see Section 1.3).

---

## 7. What-If Counterfactual Simulation Endpoints (Tier 4: Hypothetical)

### 7.1 `POST /api/v1/patients/{id}/twin/simulate`
Simulate hypothetical glucose trajectories under user-defined perturbations using the Bergman Minimal Model.

- **Access:** `researcher`
- **Request Body:**
```json
{
  "scenario_name": "Postprandial 30m Walk",
  "simulation_duration_minutes": 240,
  "perturbations": {
    "carb_delta_grams": 0.0,
    "meal_time_shift_minutes": 0,
    "exercise_duration_minutes": 30,
    "exercise_intensity": 2
  }
}
```
- **Response `200 OK`:**
```json
{
  "success": true,
  "data": {
    "scenario_id": "scn-9f8e7d6c-5b4a-3120-ef01-9a8b7c6d5e4f",
    "scenario_name": "Postprandial 30m Walk",
    "duration_minutes": 240,
    "comparison": {
      "unperturbed_peak_mg_dl": 194.2,
      "simulated_peak_mg_dl": 162.8,
      "peak_reduction_mg_dl": 31.4,
      "unperturbed_tir_percentage": 74.2,
      "simulated_tir_percentage": 88.6,
      "tir_improvement_percentage": 14.4
    },
    "simulation_trajectory": [
      { "time_min": 0, "unperturbed_glucose": 149.0, "simulated_glucose": 149.0 },
      { "time_min": 30, "unperturbed_glucose": 178.5, "simulated_glucose": 158.2 },
      { "time_min": 60, "unperturbed_glucose": 194.2, "simulated_glucose": 162.8 },
      { "time_min": 120, "unperturbed_glucose": 165.0, "simulated_glucose": 138.5 },
      { "time_min": 240, "unperturbed_glucose": 120.0, "simulated_glucose": 115.0 }
    ],
    "disclaimer": "RESEARCH & EDUCATION PROTOTYPE ONLY. Not clinical advice. Do not adjust real insulin or therapy based on this simulation."
  },
  "metadata": { "timestamp": "2026-10-20T12:00:05Z", "request_id": "req-06" }
}
```

---

## 8. Clinical Guardrails & Audit Endpoints

### 8.1 `GET /api/v1/guardrails/status`
Returns the status of all active clinical safety guardrails, refusal filters, and model integrity assertions.

- **Access:** Authenticated
- **Response `200 OK`:**
```json
{
  "success": true,
  "data": {
    "research_mode_active": true,
    "synthetic_data_enforced": true,
    "dosing_refusal_blocker_active": true,
    "strict_data_segregation_enforced": true,
    "abstention_freshness_limit_minutes": 15,
    "prohibited_output_patterns_intercepted": 0
  },
  "metadata": { "timestamp": "2026-10-20T12:00:06Z", "request_id": "req-07" }
}
```

### 8.2 `GET /api/v1/audit/logs`
Query security events, authentication attempts, simulation runs, and guardrail interventions.

- **Access:** `auditor`
- **Query Params:** `limit` (default 50), `guardrail_only` (boolean)
- **Response `200 OK`:** Returns array of audit log entities.

---

## 9. System Health Endpoints

### 9.1 `GET /api/v1/health`
Liveness and readiness check probe.

- **Access:** Public
- **Response `200 OK`:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "connected",
    "dialect": "sqlite",
    "version": "1.0.0",
    "uptime_seconds": 3600
  },
  "metadata": { "timestamp": "2026-10-20T12:00:07Z", "request_id": "req-08" }
}
```
