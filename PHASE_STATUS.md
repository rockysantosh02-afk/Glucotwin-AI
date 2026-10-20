# GlucoTwin AI - Phase Status Tracking

**Current Phase:** Phase 6 - Glycemic Metrics & Ambulatory Glucose Profile Engine  
**Status:** Completed  
**Last Updated:** October 20, 2026  

---

## 1. Phase Progression Overview

| Phase | Description | Status | Completion Date | Exit Criteria Met |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Workspace Inspection and Setup** | **Completed** | **2026-10-20** | **Yes (5/5)** |
| **Phase 2** | **Architecture and Contracts** | **Completed** | **2026-10-20** | **Yes (4/4)** |
| **Phase 3 & 4** | **Backend Foundation & Security Core** | **Completed** | **2026-10-20** | **Yes (4/4)** |
| **Phase 5** | **Synthetic Patient Data Generator & Telemetry Ingestion** | **Completed** | **2026-10-20** | **Yes (5/5)** |
| **Phase 6** | **Glycemic Metrics & Ambulatory Glucose Profile Engine** | **Completed** | **2026-10-20** | **Yes (5/5)** |
| **Phase 7** | Digital Twin Physiological ODE & ARX-Kalman Engine | Not Started | — | — |
| **Phase 8** | What-If Counterfactual Simulator & Safety Guardrails | Not Started | — | — |
| **Phase 9** | Frontend Web Dashboard & Interactive AGP Visualizer | Not Started | — | — |
| **Phase 10** | End-to-End Integration, Security Audit & QA Verification | Not Started | — | — |

---

## 2. Phase 6 Implementation Summary

- **Ambulatory Glucose Profile (AGP) Calculation Engine (`backend/app/services/agp_engine.py`):**
  - Strictly implements the International Consensus on Time in Range (ATTD / ADA 2019 standards).
  - Mathematical Metrics:
    - Arithmetic Mean Glucose ($\bar{G} \text{ mg/dL}$).
    - Sample Standard Deviation ($SD = \sqrt{\frac{1}{N-1}\sum (g_i - \bar{G})^2}$).
    - Glycemic Variability Coefficient of Variation ($CV = \frac{SD}{\text{Mean}} \times 100\%$, clinical stability target $\le 36.0\%$).
    - Glucose Management Indicator ($\text{GMI} = 3.31 + 0.02392 \times \bar{G}$, Bergenstal et al. 2018).
    - Sensor Active Sampling Duration percentage ($N / N_{\text{expected}} \times 100\%$).
  - Glycemic Range Discretization:
    - Time in Range (TIR): $70.0 \le g \le 180.0 \text{ mg/dL}$ (target $> 70.0\%$).
    - Time Above Range Level 1 (TAR 1): $180.0 < g \le 250.0 \text{ mg/dL}$ (target $< 25.0\%$).
    - Time Above Range Level 2 (TAR 2 / Severe Hyperglycemia): $g > 250.0 \text{ mg/dL}$ (target $< 5.0\%$).
    - Time Below Range Level 1 (TBR 1): $54.0 \le g < 70.0 \text{ mg/dL}$ (target $< 4.0\%$).
    - Time Below Range Level 2 (TBR 2 / Severe Hypoglycemia): $g < 54.0 \text{ mg/dL}$ (target $< 1.0\%$).
  - Clinical Consensus Targets Evaluation:
    - `tir_above_70`: Boolean indicating if TIR reaches clinical threshold ($\ge 70.0\%$).
    - `tbr_below_4`: Boolean indicating if total hypoglycemia remains safely below limit ($\text{TBR}_1 + \text{TBR}_2 \le 4.0\%$).
    - `cv_below_36`: Boolean indicating whether glycemic excursion stability target is met ($CV \le 36.0\%$).
  - Modal Day / Hourly Percentiles:
    - Evaluates 10th, 25th, 50th (median), 75th, and 90th percentiles for each of the 24 hours of the day ($h \in [0, 23]$) for interactive AGP visualization.
- **Pydantic v2 Schema Definitions (`backend/app/schemas/metrics.py`):**
  - `GlycemicRanges`: Strictly bounded floats for TIR, TAR1, TAR2, TBR1, TBR2 ($0.0 \le \text{range} \le 100.0$).
  - `ClinicalTargetsMet`: Boolean target fulfillment flags.
  - `HourlyPercentile`: Hour index ($0-23$) and percentile curves ($p10, p25, p50, p75, p90$).
  - `GlycemicMetricsResponse`: Master derived metrics data contract matching `docs/api_contracts.md` Section 5.1.
- **Glycemic Metrics API Endpoints (`backend/app/api/v1/metrics.py`):**
  - `GET /api/v1/patients/{patient_identifier}/metrics`:
    - Dynamic window filtering (`window_days`, default 14, min 1, max 90).
    - Supports both real-time windows and historical synthetic cohorts by dynamically referencing the patient's latest recorded telemetry sample.
    - Optional persistent caching to database table `glycemic_metrics` via query parameter `persist=true`.
    - Enforces patient-level authorization, demo clinician scope boundaries, anti-caching headers (`Cache-Control: no-store, no-cache, must-revalidate, private`), and append-only audit logging (`METRICS_CALCULATED`).
- **FastAPI Application Wiring (`backend/app/main.py`):**
  - Mounted `metrics_router` under `/api/v1`.

---

## 3. Actual Commands Executed & Outputs

1. `..\venv\Scripts\pytest.exe tests/test_agp_engine.py` -> 5 AGP engine unit tests passed in 0.85s.
2. `..\venv\Scripts\pytest.exe` -> Full automated test suite executed:
   - **50 passed in 4.30s (100% Pass Rate)**.

---

## 4. Tests Passed and Failed

- **Total Tests Executed:** 50
- **Passed:** 50 (100%)
- **Failed:** 0 (0%)

### Detailed Breakdown of Phase 6 Test Suite:

- `tests/test_agp_engine.py` (5 tests):
  - `test_agp_mathematical_precision`: **PASSED** (Verified against a controlled 100-sample dataset: TIR 70%, TAR1 15%, TAR2 5%, TBR1 8%, TBR2 2%, total sum 100.0%, exact Mean 133.8 mg/dL, GMI 6.5%, and clinical target booleans)
  - `test_agp_empty_telemetry`: **PASSED** (Zero telemetry readings handled gracefully without zero-division exceptions)
  - `test_agp_hourly_percentiles_ordering`: **PASSED** (24 modal hourly percentiles generated, verifying monotonic ordering $p10 \le p25 \le p50 \le p75 \le p90$)
  - `test_get_metrics_endpoint_with_persistence`: **PASSED** (HTTP 200 OK, full AGP envelope, anti-caching headers verified, and database persistence in `glycemic_metrics` confirmed)
  - `test_metrics_unauthenticated_and_not_found`: **PASSED** (HTTP 401 on unauthenticated call, HTTP 404 RESOURCE_NOT_FOUND on non-existent patient identifier)

---

## 5. Known Issues & Residual Risks

1. **Window Alignment for Historical Datasets:**
   - *Consideration:* When calculating metrics over historical synthetic cohorts (e.g. data generated with timestamps set in the past), calculating relative to `datetime.now()` would result in empty windows.
   - *Resolution:* Implemented dynamic window anchoring: the calculation window automatically anchors to the maximum timestamp recorded for the patient (`max_ts`), taking `[max_ts - window_days, max_ts]`, while falling back to `now` if no data exists.

---

## 6. Files Created or Modified in Phase 6

- `backend/app/schemas/metrics.py` (Created)
- `backend/app/services/agp_engine.py` (Created)
- `backend/app/api/v1/metrics.py` (Created)
- `backend/app/main.py` (Modified: mounted `metrics_router`)
- `backend/tests/test_agp_engine.py` (Created)
- `PHASE_STATUS.md` (Updated)

---

## 7. Exact Acceptance Criteria Verification

- [x] **Consensus AGP Metrics Precision:** Verified in `test_agp_mathematical_precision` confirming TIR, TAR, TBR, GMI, and CV% calculations match ATTD / ADA standards.
- [x] **Modal Hourly Percentiles:** Verified in `test_agp_hourly_percentiles_ordering` generating all 24 hours with monotonic percentiles.
- [x] **Tier 2 Derived Storage & Persistence:** Verified in `test_get_metrics_endpoint_with_persistence` confirming records written to `glycemic_metrics`.
- [x] **Fail-Closed Patient Scope & Anti-Caching:** Verified in `test_metrics_unauthenticated_and_not_found` with `Cache-Control: no-store` verified.

---

## 8. Next Phase to Execute

**Phase 7: Digital Twin Physiological ODE & ARX-Kalman Engine**
- Implement Bergman Minimal Model ODE simulation engine (`backend/app/services/bergman_model.py`) for physiological insulin-glucose dynamics:
  - $\frac{dG}{dt} = -(p_1 + X) G + p_1 G_b + \frac{R_a(t)}{V_I}$
  - $\frac{dX}{dt} = -p_2 X + p_3 (I - I_b)$
  - $\frac{dI}{dt} = -n (I - I_b) + \frac{U(t)}{V_I}$
- Implement Autoregressive with Exogenous Inputs (ARX) short-term forecasting engine with recursive Kalman Filter state estimation (`backend/app/services/arx_kalman.py`):
  - Autoregressive glucose lags ($G_{t-1}, G_{t-2}, G_{t-3}, G_{t-6}, G_{t-12}$), velocity ($v_t$), carbs on board ($COB_t$), insulin on board ($IOB_t$), and exercise strain.
  - Multi-step forward trajectories for horizons $H \in \{15, 30, 45, 60\} \text{ minutes}$.
  - Analytical 95% confidence intervals from Kalman covariance matrix $P_k$.
- Enforce clinical safety guardrail: Fail-closed abstention logic (`status="abstained"`) for stale data (>15 min), short history (<60 min), sensor gaps (>15 min), or physiological anomalies ($<40$ or $>500$ mg/dL).
- Implement Pydantic v2 schemas for forecast runs (`backend/app/schemas/predicted.py`).
- Implement API endpoint `POST /api/v1/patients/{id}/twin/forecast` (Tier 3: Predicted).
- Implement Pytest test suite for model convergence, deterministic forecasting, covariance bounds, and abstention triggers.
