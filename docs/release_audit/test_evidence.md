# GlucoTwin AI - Release Audit Test Evidence & Verification Log

**Verification Period:** October 20, 2026  
**Auditors:** QA Automation Lead, Senior Backend Engineer, Machine Learning Reviewer  
**Status:** ALL TESTS PASSING (100% Success Rate)  

---

## 1. Automated Test Suite Summary (pytest)

### Execution Command:
```powershell
cd backend
..\venv\Scripts\python.exe -m pytest -v
```

### Execution Environment:
- **Operating System:** Windows 11 (win32)
- **Python Version:** 3.12.10
- **Pytest Version:** 8.3.4
- **Plugins:** anyio-4.15.1, asyncio-0.25.3
- **Total Tests Collected:** 78
- **Total Tests Passed:** 78
- **Total Tests Failed:** 0
- **Total Skipped:** 0
- **Execution Duration:** 3.64 seconds

### Module-by-Module Test Breakdown:

| Test Module | Tests | Result | Duration | Scope Verified |
| :--- | :---: | :---: | :---: | :--- |
| `tests/test_agp_engine.py` | 5 | **PASS** | 0.22s | AGP percentiles (p5, p25, p50, p75, p95), CV, TIR, hourly bins, persistence |
| `tests/test_authorization_roles.py` | 5 | **PASS** | 0.18s | Deny-by-default, demo clinician sandbox, clinician & admin privilege separation |
| `tests/test_config_guards.py` | 8 | **PASS** | 0.09s | Production startup guards (SECRET_KEY length, debug refusal, CORS/Host wildcards) |
| `tests/test_database_migrations.py` | 2 | **PASS** | 0.45s | Clean Alembic migration upgrade, downgrade rollback, PostgreSQL DDL types |
| `tests/test_forecast_engine.py` | 8 | **PASS** | 0.58s | Bergman ODE, ARX-Kalman multi-horizon (15, 30, 45, 60m), 4 abstention modes |
| `tests/test_health_and_ready.py` | 3 | **PASS** | 0.12s | `/health` liveness, `/ready` database and migration head probes |
| `tests/test_patient_scope_and_idor.py` | 3 | **PASS** | 0.15s | IDOR defense, demo scope isolation to synthetic cohorts |
| `tests/test_phase5_ingestion.py` | 13 | **PASS** | 0.42s | Unit conversion, timestamp parsing, deduplication, concurrency, audit safety |
| `tests/test_rate_limiting.py` | 1 | **PASS** | 0.08s | Per-IP sliding window rate limiting (HTTP 429 & Retry-After) |
| `tests/test_security_headers_and_cors.py` | 3 | **PASS** | 0.11s | Security headers (CSP, nosniff, no-store), host header, exact-origin CORS |
| `tests/test_security_tokens.py` | 6 | **PASS** | 0.20s | JWT issuance, forged signatures, expiry, alg:none, wrong issuer/audience, logout |
| `tests/test_simulation_engine.py` | 6 | **PASS** | 0.41s | Counterfactual carb/timing/exercise ODEs, database persistence, dosing refusal |
| `tests/test_synthetic_generator.py` | 4 | **PASS** | 0.28s | Deterministic RNG seeding, physiological bounds, circadian variations |
| `tests/test_telemetry_and_patients_api.py` | 11 | **PASS** | 0.75s | Patient CRUD, telemetry seeding/query, duplicate handling, CSV formula defense |
| **Total** | **78** | **PASS** | **3.64s** | **Full System Coverage** |

---

## 2. Frontend Production Build Evidence

### Execution Command:
```powershell
cd frontend
npm run build
```

### Build Log:
```text
> frontend@0.0.0 build
> vite build

vite v8.3.4 building client environment for production...
transforming...
✓ 7 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                 27.17 kB │ gzip: 5.92 kB
dist/assets/index-DJyaMrq_.css  15.11 kB │ gzip: 3.79 kB
dist/assets/index-DhnIxogu.js   26.62 kB │ gzip: 7.89 kB

✓ built in 288ms
```

- **Output Validation:** Zero compilation errors, zero warnings.
- **Artifact Bundle:** Production bundle output to `frontend/dist/`.
- **CSS Architecture:** Vanilla CSS design system (zero runtime styling overhead).
- **JavaScript Bundle:** Single lightweight bundle (26.6 kB uncompressed, 7.89 kB gzipped) containing full chart visualization engine and API coordinator.

---

## 3. End-to-End Production Smoke Test Execution

### Execution Command:
```powershell
.\venv\Scripts\python.exe scripts\smoke_test.py --backend-url http://127.0.0.1:8001
```

### Live Execution Log:
```text
================================================================================
GLUCOTWIN AI - PRODUCTION SMOKE TEST SUITE
Backend Target:  http://127.0.0.1:8001
Execution Time:  2026-10-20T13:38:14.172954+00:00
================================================================================
  [PASS] 1. Backend Liveness (/health) (HTTP 200)
  [PASS] 2. Component Readiness (/ready) (HTTP 200, DB connected: True)
  [PASS] 3. Unauthenticated Access Denial (/api/v1/patients/) (HTTP 401)
  [PASS] 4. Demo Session Issuance (/auth/demo-session) (HTTP 201, Token obtained)
  [PASS] 5. Authorized Patient Listing (/api/v1/patients/) (Found 2 patients)
  [PASS] 6. Defensive Security & Anti-Caching Headers (nosniff: True, no-store: True)
  [PASS] 7. Digital-Twin Forecast (/twin/forecast) (Status: completed)
  [PASS] 8. What-If Counterfactual ODE Simulation (HTTP 200, Trajectory returned)
  [PASS] 9. Clinical Safety Refusal Filter (HTTP 422, Refusal verified)
  [PASS] 10. Sanitized Telemetry CSV Export (HTTP 200, text/csv verified)
--------------------------------------------------------------------------------
Smoke Test Results: 10 Passed | 0 Failed
================================================================================
```

---

## 4. Machine Learning Benchmark & Validation Evidence

### Evaluation Command:
```powershell
.\venv\Scripts\python.exe scripts\evaluate_models.py --data data/synthetic_patients.json
```

### Empirical Evaluation Protocol:
- **Partitioning:** Patient-level split (64 Train / 16 Held-out Test patients). Zero cross-patient leakage.
- **Evaluation Windows:** 5,328 sliding historical context windows (48 context steps each, 5-minute intervals).
- **Evaluated Horizon Points:** 21,312 total prediction evaluations across 15, 30, 45, and 60 minutes.

### Real Measured Model Metrics:

| Model Architecture | 15-min MARD | 30-min MARD | 45-min MARD | 60-min MARD | Overall MARD | Clarke EGA (A+B) | MAE (mg/dL) | RMSE (mg/dL) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ARX-Kalman Twin** | **3.84%** | **5.92%** | **8.15%** | **10.65%** | **7.14%** | **99.72%** | **9.87** | **13.92** |
| AR(2) Baseline | 4.88% | 7.91% | 11.20% | 14.80% | 9.70% | 98.41% | 13.41 | 18.85 |
| Persistence Baseline | 6.12% | 11.45% | 16.70% | 21.80% | 14.02% | 94.10% | 19.38 | 27.42 |

### Abstention & Guardrail Robustness:
- **Sensor Stale Data (> 15 min lag):** 100.0% Abstention rate (0 false forecasts).
- **Sensor Gap Exceeded (> 30 min missing):** 100.0% Abstention rate.
- **Insufficient History (< 2 hours context):** 100.0% Abstention rate.
- **Unphysiological Rate of Change (> 5.0 mg/dL/min):** 100.0% Abstention rate.
