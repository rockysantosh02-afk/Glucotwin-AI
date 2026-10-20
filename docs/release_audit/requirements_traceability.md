# GlucoTwin AI - Requirements Traceability Matrix

**Document Version:** 1.0.0  
**Audit Phase:** Phase 1 - Requirements Traceability  
**Status:** Audit Complete  
**Review Date:** October 20, 2026  

---

## 1. Traceability Matrix

| Req ID | Capability Group | Expected Behavior | Implementation Location | Test Location | Status | Evidence / Verification | Remaining Defect or Risk |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **REQ-A** | **Synthetic Data & Provenance** | Deterministic generator, 60-120 patients, 14-28 days, circadian + AR(1) noise, EHR latent traits, 7 demo scenarios, provenance metadata. | `backend/app/services/synthetic_data.py`, `scripts/generate_demo_data.py` | `backend/tests/test_synthetic_generator.py`, `test_phase5_ingestion.py` | **Verified** | 80 patients / 322,139 readings generated; all 7 scenarios verified in test suite; `provenance.json` records seed and parameters. | None. In-silico synthetic scope strictly maintained. |
| **REQ-B** | **Sensor Ingestion & Adapter** | Multi-channel ingestion (`POST /api/v1/observations/ingest`), unit conversion (`mmol/L` $\leftrightarrow$ `mg/dL`), duplicate handling, bounds validation. | `backend/app/api/v1/observations.py`, `backend/app/core/units.py` | `backend/tests/test_phase5_ingestion.py` (13 tests) | **Verified** | High-precision conversion ($18.0182$), concurrent duplicate timestamp collision safety, payload bounds $[40, 500]$ enforced. | None. |
| **REQ-C** | **Digital-Twin State Engine** | Continuous tracking of metabolic state, Kalman state estimates, Bergman 3-compartment ODE integration. | `backend/app/services/arx_kalman.py`, `backend/app/services/bergman_model.py` | `backend/tests/test_forecast_engine.py`, `test_simulation_engine.py` | **Verified** | State covariance propagation, ODE solve_ivp with RK45, parameter initialization. | Simplified lumped ODE does not model unmeasured hormones (e.g. cortisol). |
| **REQ-D** | **Feature Engineering & Leakage** | Chronological ordering, zero future information leakage in rolling windows, patient-level data partitioning. | `backend/app/services/arx_kalman.py`, `scripts/evaluate_models.py` | `backend/tests/test_forecast_engine.py`, `scripts/evaluate_models.py` | **Verified** | Context window strictly sliced up to anchor timestamp $t$; test cohort strictly disjoint (seed 999). | None. |
| **REQ-E** | **Forecasting & Baselines** | Multi-horizon forecasts ($15, 30, 45, 60$ min), comparison against Persistence and Linear Extrapolation baselines. | `backend/app/services/arx_kalman.py`, `scripts/evaluate_models.py` | `backend/tests/test_forecast_engine.py`, `scripts/evaluate_models.py` | **Verified** | Measured RMSE: H15 11.30, H30 18.62, H45 22.95, H60 26.48 mg/dL; baselines tracked in `model_evaluation_results.json`. | ARX linearity assumption under massive carbohydrate overload. |
| **REQ-F** | **Event-Risk Classification** | Probabilistic classification of acute hypoglycemic ($<70$ mg/dL) and hyperglycemic ($>180$ mg/dL) excursion risk. | `backend/app/schemas/predicted.py`, `backend/app/services/arx_kalman.py` | `backend/tests/test_forecast_engine.py` | **Verified** | Risk probabilities computed from Kalman Gaussian cumulative density tail at horizon endpoints. | Requires user education on probability thresholds. |
| **REQ-G** | **Prediction Intervals & Coverage** | Analytical 95% confidence intervals ($\pm 1.96 \sigma$) with empirical held-out coverage verification. | `backend/app/services/arx_kalman.py` | `scripts/evaluate_models.py` | **Verified** | Empirical 95% CI coverage measured: H15 95.81%, H30 95.83%, H45 95.95%, H60 96.11%. | None. |
| **REQ-H** | **Anomaly Detection & Abstention** | Fail-closed abstention on stale data ($>15$m), short history ($<60$m), gaps ($>15$m), physiological anomalies. | `backend/app/services/arx_kalman.py` | `backend/tests/test_forecast_engine.py` | **Verified** | 100/100 stale windows rejected ($100.0\%$ abstention rate); zero false predictions emitted. | None. |
| **REQ-I** | **Model Artifact Integrity** | Verification of model engine parameters, configuration guards, readiness probes. | `backend/app/api/v1/ready.py`, `backend/app/core/config.py` | `backend/tests/test_health_and_ready.py`, `test_config_guards.py` | **Verified** | `/ready` probe validates parameters; production startup fails if config is invalid. | Enhance with explicit SHA-256 file manifest verification where applicable. |
| **REQ-J** | **API Contracts & Persistence** | Standardized response envelope, Tier 3 prediction persistence in `forecast_runs`. | `backend/app/api/v1/forecast.py`, `backend/app/models/forecast.py` | `backend/tests/test_forecast_engine.py` | **Verified** | Forecast trajectory and abstention records written to `forecast_runs`. | None. |
| **REQ-K** | **Auth, RBAC & Patient Isolation** | Signed JWT demo sessions, deny-by-default, centralized RBAC, synthetic patient IDOR scope enforcement. | `backend/app/core/security.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/patients.py` | `backend/tests/test_authorization_roles.py`, `test_patient_scope_and_idor.py`, `test_security_tokens.py` | **Verified** | 401 on missing auth, 403 on role mismatch, 403 on non-synthetic patient IDOR attempt. | Token storage in browser localStorage in frontend (DEF-02). |
| **REQ-L** | **What-If Simulation** | Counterfactual perturbations (carb delta, meal shift, exercise), Bergman ODE, clinical dosing refusal. | `backend/app/api/v1/simulation.py`, `backend/app/services/counterfactual_simulator.py` | `backend/tests/test_simulation_engine.py` | **Verified** | Dosing requests rejected with HTTP 422 `CLINICAL_SAFETY_REFUSAL`; persistence in `simulation_scenarios`. | None. |
| **REQ-M** | **Frontend Integration & UX** | Interactive web dashboard: 4-tier navigation, CGM chart, AGP percentiles, What-If sliders, mobile layout. | `frontend/index.html`, `frontend/src/` | `frontend/` (manual / visual) | **Partially Implemented** | HTML structure, CSS styling, and SVG charts exist, but `main.js` was disconnected from DOM (DEF-01). | Repair `frontend/src/main.js` to wire DOM event handlers. |
| **REQ-N** | **PDF/CSV Exports** | Export telemetry and AGP metrics with synthetic disclosure and CSV formula-injection defense. | `backend/app/api/v1/telemetry.py` / exports | *To be tested* | **Partially Implemented** | Basic CSV export exists in data generator; API export needs formula injection sanitization. | Add CSV export endpoint with `=,+,-,@` escaping (DEF-05). |
| **REQ-O** | **Audit, Rate Limits & Headers** | Append-only audit trail, per-client rate limiting (429 + Retry-After), CSP and defensive headers. | `backend/app/core/security_middleware.py`, `backend/app/services/audit_service.py` | `backend/tests/test_rate_limiting.py`, `test_security_headers_and_cors.py` | **Verified** | Audit logs redact raw telemetry; CSP, HSTS, X-Frame-Options: DENY, rate limiter passing. | None. |
| **REQ-P** | **Database Migrations & Concurrency** | Reversible Alembic migrations on clean database; concurrent duplicate safe insertion. | `backend/alembic/`, `backend/app/models/` | `backend/tests/test_database_migrations.py`, `test_phase5_ingestion.py` | **Verified** | Clean upgrade/downgrade verified; concurrent collision test verified. | None. |
| **REQ-Q** | **Automated Tests & CI** | Comprehensive backend unit/integration tests, model benchmarks, GitHub Actions CI workflow. | `backend/tests/`, `.github/workflows/ci.yml` | `pytest` in `backend/` | **Verified** | 77/77 tests passing in 3.86s; CI workflow configured. | None. |
| **REQ-R** | **Documentation & Submission** | Architecture, data dictionary, model card, evaluation protocol, threat model, demo script, checklist. | `README.md`, `docs/`, `CONTRIBUTING.md`, `SECURITY.md` | Manual inspection | **Verified** | All 14 core documents completed in Phase 12. | None. |
| **REQ-S** | **Render Config & Deployment** | Multi-service Render deployment blueprint (`render.yaml`), smoke test script (`smoke_test.py`). | `docs/render_deployment.md`, `render.yaml` | `scripts/smoke_test.py` | **Partially Implemented** | Documented in `docs/render_deployment.md`; root `render.yaml` and `smoke_test.py` pending. | Create `render.yaml` and `scripts/smoke_test.py` (DEF-03, DEF-04). |

---

## 2. Requirements Traceability Statistics

- **Total Capability Groups Inspected:** 19 (A through S)
- **Verified & Fully Implemented:** 15 (78.9%)
- **Partially Implemented (In Progress):** 4 (21.1%)
  - REQ-M: Frontend DOM wiring (`main.js`)
  - REQ-N: CSV Export endpoint with formula injection defense
  - REQ-K (frontend facet): Token memory-only storage
  - REQ-S: Root `render.yaml` blueprint & `scripts/smoke_test.py`
- **Missing / Unaddressed:** 0
- **Blocked:** 0
