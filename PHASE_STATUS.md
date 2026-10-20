# GlucoTwin AI - Phase Status Tracking

**Current Phase:** Phase 8 - What-If Counterfactual Simulator & Safety Guardrails  
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
| **Phase 7** | **Digital Twin Physiological ODE & ARX-Kalman Engine** | **Completed** | **2026-10-20** | **Yes (5/5)** |
| **Phase 8** | **What-If Counterfactual Simulator & Safety Guardrails** | **Completed** | **2026-10-20** | **Yes (5/5)** |
| **Phase 9** | Frontend Web Dashboard & Interactive AGP Visualizer | Not Started | — | — |
| **Phase 10** | End-to-End Integration, Security Audit & QA Verification | Not Started | — | — |

---

## 2. Phase 8 Implementation Summary

- **Counterfactual Simulation Engine (`backend/app/services/counterfactual_simulator.py`):**
  - Executes paired in-silico simulations using the physiological Bergman Minimal Model ODE:
    1. Unperturbed Baseline Trajectory: standard meal (50.0g carbs at $t=15 \text{ min}$) with matched prandial bolus.
    2. Counterfactual Perturbed Trajectory: evaluates user-defined perturbations against the baseline.
  - Perturbation Dimensions (strictly complying with `docs/config_specification.md` Section 7):
    - Carbohydrate delta ($\Delta C \in [-100.0, +150.0] \text{ grams}$).
    - Meal timing shift ($\Delta t_{\text{meal}} \in [-60, +120] \text{ minutes}$).
    - Physical exercise intensity ($0 \text{ to } 3$: None, Light, Moderate, Heavy).
    - Physical exercise duration ($0 \text{ to } 180 \text{ minutes}$).
    - Simulation duration ($60 \text{ to } 1440 \text{ minutes} / 24 \text{ hours}$).
  - Comparative Metric Shift Analysis:
    - Shift in Time in Range ($\Delta TIR = \text{TIR}_{\text{simulated}} - \text{TIR}_{\text{baseline}}$ percentage points).
    - Shift in Mean Glucose ($\Delta \text{Mean} = \text{Mean}_{\text{simulated}} - \text{Mean}_{\text{baseline}} \text{ mg/dL}$).
    - Step-by-step differential trajectory: $\Delta G(t) = G_{\text{simulated}}(t) - G_{\text{baseline}}(t)$.
- **Fail-Closed Clinical Refusal Safety Guardrails:**
  - **MANDATORY SAFETY BOUNDARY:** The platform is an educational and research simulation platform and strictly refuses to calculate, recommend, or optimize therapeutic insulin doses or medication changes.
  - Fail-closed refusal trigger: Any request attempting to request insulin dose recommendations or therapeutic bolus calculations (e.g. `recommend_insulin_dose: true` or `calculate_bolus: true`) is immediately intercepted and rejected with HTTP 422 `CLINICAL_SAFETY_REFUSAL`.
  - Prominent clinical disclaimer attached to every simulation response: `"RESEARCH & EDUCATION PROTOTYPE ONLY. NOT A CLINICAL PRODUCT. NO INSULIN DOSING OR THERAPEUTIC RECOMMENDATIONS ARE PROVIDED."`
- **Pydantic v2 Schema Definitions (`backend/app/schemas/hypothetical.py`):**
  - `SimulationPerturbations`: Strictly bounded numerical fields for carb delta, timing shift, and exercise.
  - `SimulationRequest`: Scenario metadata, duration, perturbations, initial glucose override, and clinical dosing refusal trap.
  - `SimulationTrajectoryPoint`: `time_minutes`, `baseline_glucose`, `simulated_glucose`, `delta_glucose`.
  - `SimulationMetricsShift`: Baseline TIR, simulated TIR, $\Delta TIR$, baseline mean, simulated mean, $\Delta \text{Mean}$.
  - `SimulationResponse`: Master Tier 4 Hypothetical data contract matching `docs/api_contracts.md` Section 7.1.
- **Simulation API Endpoints (`backend/app/api/v1/simulation.py`):**
  - `POST /api/v1/patients/{patient_identifier}/twin/simulate`:
    - Executes counterfactual simulation scenario.
    - Persists every run into database table `simulation_scenarios` (Tier 4: Hypothetical) including scenario name, duration, perturbation parameters, baseline trajectory, simulated trajectory, and $\Delta TIR$.
    - Enforces patient-level authorization, demo clinician scope boundaries, anti-caching headers (`Cache-Control: no-store, no-cache, must-revalidate, private`), and append-only audit logging (`SIMULATION_SCENARIO_RUN`).
- **FastAPI Application Wiring (`backend/app/main.py`):**
  - Mounted `simulation_router` under `/api/v1`.

---

## 3. Actual Commands Executed & Outputs

1. `..\venv\Scripts\pytest.exe tests/test_simulation_engine.py` -> 6 simulation tests passed in 2.12s.
2. `..\venv\Scripts\pytest.exe` -> Full automated test suite executed:
   - **64 passed in 7.86s (100% Pass Rate)**.

---

## 4. Tests Passed and Failed

- **Total Tests Executed:** 64
- **Passed:** 64 (100%)
- **Failed:** 0 (0%)

### Detailed Breakdown of Phase 8 Test Suite:

- `tests/test_simulation_engine.py` (6 tests):
  - `test_simulation_carb_perturbation`: **PASSED** (Verified that +40g carb increase elevates simulated postprandial glucose by >10 mg/dL and increases mean glucose)
  - `test_simulation_exercise_perturbation`: **PASSED** (Verified that 45 min moderate exercise accelerates glucose clearance, dropping glucose by >5 mg/dL below baseline)
  - `test_simulation_meal_timing_shift`: **PASSED** (Verified that +30 min meal shift delays postprandial turning point)
  - `test_clinical_safety_refusal_on_insulin_dosage_requests`: **PASSED** (Requests with `recommend_insulin_dose=True` or `calculate_bolus=True` rejected with HTTP 422 `CLINICAL_SAFETY_REFUSAL`)
  - `test_twin_simulate_endpoint_integration_and_persistence`: **PASSED** (HTTP 200 OK, full comparative trajectory envelope, anti-caching headers, and database persistence in `simulation_scenarios` confirmed)
  - `test_twin_simulate_unauthenticated_and_scope`: **PASSED** (HTTP 401 on unauthenticated call, demo clinician blocked from non-synthetic patient IDs)

---

## 5. Known Issues & Residual Risks

1. **Safety Refusal Interception Layer:**
   - *Consideration:* To prevent any evasion of clinical safety boundaries, clinical dosage requests are rejected at both the Pydantic schema validation layer (`model_validator(mode="after")`) and backend route handlers, ensuring no therapeutic dosing advice can ever be emitted.

---

## 6. Files Created or Modified in Phase 8

- `backend/app/schemas/hypothetical.py` (Created)
- `backend/app/services/counterfactual_simulator.py` (Created)
- `backend/app/api/v1/simulation.py` (Created)
- `backend/app/main.py` (Modified: mounted `simulation_router`)
- `backend/tests/test_simulation_engine.py` (Created)
- `PHASE_STATUS.md` (Updated)

---

## 7. Exact Acceptance Criteria Verification

- [x] **Counterfactual Simulation Engine:** Verified in `test_simulation_carb_perturbation`, `test_simulation_exercise_perturbation`, and `test_simulation_meal_timing_shift`.
- [x] **Metric Divergence Analysis ($\Delta TIR$, $\Delta \text{Mean}$):** Verified in `test_simulation_carb_perturbation` and `test_twin_simulate_endpoint_integration_and_persistence`.
- [x] **Strict Clinical Refusal Guardrails:** Verified in `test_clinical_safety_refusal_on_insulin_dosage_requests` rejecting insulin dosing requests with HTTP 422.
- [x] **Tier 4 Hypothetical Storage & Persistence:** Verified in `test_twin_simulate_endpoint_integration_and_persistence` confirming records written to `simulation_scenarios`.
- [x] **Patient Scope Authorization & Anti-Caching Headers:** Verified on simulation routes returning `Cache-Control: no-store`.

---

## 8. Next Phase to Execute

**Phase 9: Frontend Web Dashboard & Interactive AGP Visualizer**
- Set up lightweight, state-of-the-art frontend application using modern HTML/Vanilla CSS/JavaScript or modern framework (Vite SPA) as per web application development standards.
- Dark mode theme, glassmorphic design, dynamic micro-animations, and responsive layout.
- Clinical safety banner: "RESEARCH & EDUCATION PROTOTYPE ONLY - NOT FOR MEDICAL USE".
- 4-Tier Data Segregation Dashboard:
  - Tier 1 (Observed): Continuous CGM time-series, meal logs, exercise tags.
  - Tier 2 (Derived): Ambulatory Glucose Profile (AGP) consensus visualizer with modal day percentiles (10th, 25th, 50th, 75th, 90th), TIR/TAR/TBR stacked gauge, GMI, and %CV.
  - Tier 3 (Predicted): Forward trajectory forecast with Kalman uncertainty envelope (95% CI) and fail-closed abstention alert banners.
  - Tier 4 (Hypothetical): Interactive "What-If" counterfactual scenario sliders (carb delta, meal shift, exercise intensity/duration) with side-by-side comparative trajectory curves.
- Demo session login workflow calling `POST /api/v1/auth/demo-session`.
