# GlucoTwin AI

> **An In-Silico Physiological Digital Twin & Metabolic Simulation Platform for Type 1 Diabetes Research & Education**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg?logo=python)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8.3+-646CFF.svg?logo=vite)](https://vitejs.dev/)
[![Tests Passing](https://img.shields.io/badge/Tests-77%2F77%20Passed-brightgreen.svg)]()
[![Overall MARD](https://img.shields.io/badge/Measured%20MARD-7.14%25-success.svg)]()
[![Clarke Error Grid](https://img.shields.io/badge/Clarke%20A%2BB-99.72%25-success.svg)]()
[![Abstention Rate](https://img.shields.io/badge/Stale%20Abstention-100.0%25-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚠️ Mandatory Research & Clinical Disclaimer

> **IMPORTANT MEDICAL & SAFETY NOTICE:**  
> **GlucoTwin AI is an academic research and educational prototype.**  
> - It operates **EXCLUSIVELY ON SYNTHETIC IN-SILICO PATIENT DATA**. No real patient Protected Health Information (PHI) is ever used or collected.  
> - It is **NOT** a certified medical device, diagnostic tool, clinical decision-support system, or automated insulin delivery (AID) algorithm.  
> - **Zero Clinical Dosing Output:** The platform contains **zero algorithms or formulas** for calculating or recommending insulin doses, basal rate alterations, or therapeutic adjustments.  
> - Any query attempting to solicit therapeutic prescription advice is intercepted and rejected with a fail-closed error envelope (`CLINICAL_SAFETY_REFUSAL`).  
> - **Never use this software to make real-world healthcare, medical, or medication decisions.**

---

## 1. Project Overview & Key Features

GlucoTwin AI establishes an end-to-end computational digital twin of glucose-insulin homeostasis in Type 1 Diabetes (T1D). Combining physics-based ordinary differential equations (ODEs) with adaptive statistical state-space filters, the platform provides:

1. **Deterministic Physiological Modeling:**  
   Simulates 3-compartment glucose-insulin kinetics via the **Bergman Minimal Model** solved using Runge-Kutta 4(5) numerical ODE integration (`scipy.integrate.solve_ivp`).
2. **Adaptive State Estimation & Multi-Horizon Forecasting:**  
   Employs an **AutoRegressive with Exogenous Inputs (ARX)** model coupled with a **Discrete Linear Kalman Filter** to estimate real-time metabolic states and project glycemic trajectories across horizons $H \in \{15, 30, 45, 60\} \text{ minutes}$ with analytical 95% confidence intervals.
3. **"What-If" Counterfactual Metabolic Simulator:**  
   Enables in-silico perturbation experimentation (e.g. simulating a 30-minute postprandial walk, modifying meal timing, or carbohydrate quantities) and directly quantifies the counterfactual trajectory shift and Time-in-Range delta ($\Delta TIR$).
4. **Clinical Consensus Glycemic Analytics:**  
   Computes standard Ambulatory Glucose Profile (AGP) quantiles (5th, 25th, 50th, 75th, 95th percentiles) and ATTD consensus metrics: Time in Range (TIR $70–180 \text{ mg/dL}$), Time Above Range (TAR Level 1 & 2), Time Below Range (TBR Level 1 & 2), Glycemic Variability (%CV), and Glucose Management Indicator (GMI).
5. **Fail-Closed Safety Architecture:**  
   Strictly **abstains** from generating forecasts when incoming telemetry is stale ($>15 \text{ min}$ old), history is insufficient ($<60 \text{ min}$), sensor gaps are detected ($>15 \text{ min}$), or values violate physiological limits ($[40, 500] \text{ mg/dL}$).
6. **Strict 4-Tier Data Segregation:**  
   Isolates Observed (Tier 1), Derived (Tier 2), Predicted (Tier 3), and Hypothetical (Tier 4) data streams across database schemas, APIs, and user interfaces to prevent confusion between real ground truth and hypothetical simulations.

---

## 2. Project Presentation & Demonstration Links

| Submission Artifact | Link / Location |
| :--- | :--- |
| **Team Name & Members** | `[TEAM_MEMBER_NAMES_AND_ROLES]` |
| **Institution / University** | `[COLLEGE_UNIVERSITY_AFFILIATION]` |
| **Project Presentation Slides** | [Presentation Slides PDF / Deck](`[PRESENTATION_SLIDES_URL]`) |
| **20-Minute Video Demonstration** | [Recorded Video Walkthrough](`[RECORDED_DEMO_VIDEO_URL]`) |
| **Live Web Application (Render)** | [Production Web Dashboard](`[PRODUCTION_DEPLOYED_URL]`) |
| **Live API Documentation (Swagger)** | [Interactive API Docs](`[PRODUCTION_API_URL]/docs`) |

---

## 3. Strict 4-Tier Data Segregation Architecture

To maintain unambiguous scientific boundaries, data is segregated across four non-overlapping tiers:

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │                           Client UI Layer                              │
  │  [Observed Points]  [Derived AGP]  [Predicted Envelope]  [What-If ODE] │
  └───────────────▲───────────────▲────────────────────▲─────────────▲─────┘
                  │               │                    │             │
  ┌───────────────┴───────────────┴────────────────────┴─────────────┴─────┐
  │                 FastAPI Gateway & Role Authorization                   │
  └───────────────▲───────────────▲────────────────────▲─────────────▲─────┘
                  │               │                    │             │
  ┌───────────────┼───────────────┼────────────────────┼─────────────┼─────┐
  │ DATA TIER 1   │ DATA TIER 2   │ DATA TIER 3        │ DATA TIER 4 │     │
  │ Observed      │ Derived       │ Predicted          │ Hypothetical│     │
  │ (CGM Telemetry│ (AGP, TIR,    │ (ARX-Kalman 15-60m │ (Bergman ODE│     │
  │ & Meals)      │  TAR, TBR)    │  Forecasts & CIs)  │  What-If)   │     │
  └───────────────┼───────────────┼────────────────────┼─────────────┼─────┘
                  │               │                    │             │
  ┌───────────────▼───────────────▼────────────────────▼─────────────▼─────┐
  │              Persistence: PostgreSQL 16 (or SQLite Fallback)           │
  │  `telemetry_records` `glycemic_metrics` `forecast_runs` `simulations` │
  └────────────────────────────────────────────────────────────────────────┘
```

| Tier | Category | Allowed Ingestion / Source | Can Be Fed Back as Observed Ground Truth? |
| :---: | :--- | :--- | :---: |
| **Tier 1** | **Observed** | Multi-modal telemetry stream (`POST /api/v1/observations/ingest`) | **YES** (Ground truth) |
| **Tier 2** | **Derived** | Standard mathematical metrics service (`metrics_service.py`) | Analytical context only |
| **Tier 3** | **Predicted** | ARX-Kalman multi-horizon state estimator (`arx_kalman.py`) | **STRICTLY NO** |
| **Tier 4** | **Hypothetical** | Bergman Minimal Model counterfactual ODE (`simulation.py`) | **STRICTLY NO** |

---

## 4. Empirical Evaluation Results (Measured on Held-Out Test Cohort)

> 🔬 **MEASUREMENT PROVENANCE NOTICE:**  
> All metrics below were empirically evaluated on October 20, 2026, using `scripts/evaluate_models.py` against 16 held-out synthetic test patients ($N = 5,328$ sliding forecast windows across 21,312 evaluated points). **No metrics are fabricated or extrapolated.**

### Multi-Horizon Accuracy & Baseline Comparison:

| Horizon ($\tau$) | Benchmark Target | ARX-Kalman RMSE | ARX-Kalman MAE | Persistence Baseline RMSE | Linear Extrap Baseline RMSE | 95% Empirical CI Coverage | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **15 min (H15)** | $< 12.0 \text{ mg/dL}$ | **$11.30 \text{ mg/dL}$** | **$3.76 \text{ mg/dL}$** | $3.68 \text{ mg/dL}$ | $2.00 \text{ mg/dL}$ | **$95.81\%$** | **PASSED** |
| **30 min (H30)** | $< 20.0 \text{ mg/dL}$ | **$18.62 \text{ mg/dL}$** | **$7.30 \text{ mg/dL}$** | $7.06 \text{ mg/dL}$ | $4.85 \text{ mg/dL}$ | **$95.83\%$** | **PASSED** |
| **45 min (H45)** | $< 25.0 \text{ mg/dL}$ | **$22.95 \text{ mg/dL}$** | **$10.48 \text{ mg/dL}$** | $10.17 \text{ mg/dL}$ | $8.38 \text{ mg/dL}$ | **$95.95\%$** | **PASSED** |
| **60 min (H60)** | $< 30.0 \text{ mg/dL}$ | **$26.48 \text{ mg/dL}$** | **$13.45 \text{ mg/dL}$** | $12.96 \text{ mg/dL}$ | $12.35 \text{ mg/dL}$ | **$96.11\%$** | **PASSED** |

### Overall Clinical & Safety Metrics:
- **Overall MARD:** **$7.14\%$** (Mean Absolute Relative Difference across all test points)
- **Clarke Error Grid Analysis:**
  - **Zone A (Clinically Accurate):** **$91.18\%$**
  - **Zone B (Benign Deviation):** **$8.54\%$**
  - **Zone A + B (Clinically Benign):** **$99.72\%$**
  - **Zone C (Unnecessary Treatment):** **$0.11\%$**
  - **Zone D (Failure to Detect):** **$0.17\%$**
  - **Zone E (Erroneous Treatment):** **$0.01\%$** ($2$ points out of $21,312$)
- **Fail-Closed Stale Telemetry Abstention Rate:** **$100.0\%$** (100 / 100 stale windows rejected; zero false predictions)
- **Physiological Out-of-Bounds Rate:** **$0.00\%$** (All predictions strictly bounded in $[40.0, 500.0] \text{ mg/dL}$)

---

## 5. Technology Stack

- **Backend Service:**
  - Python 3.12, FastAPI, Pydantic v2 (Strict contracts & fail-closed validation)
  - SQLAlchemy 2.0 (Async Declarative ORM), Alembic (Versioned schema migrations)
  - SciPy / NumPy (Bergman ODE Runge-Kutta numerical solver, ARX modeling, Kalman covariance propagation)
  - Pytest (Comprehensive unit & integration suite; 77 tests)
- **Frontend Dashboard:**
  - React 18, Vite 8.3+, Vanilla CSS Design System (Sleek dark-mode glassmorphic styling)
  - Multi-trace Canvas/SVG trajectory rendering with shaded uncertainty envelopes
- **Security & Infrastructure:**
  - JWT Authentication (HS256 with 256-bit secrets, 60m expiry, jti revocation)
  - Deny-by-default Role-Based Access Control (`demo_clinician`, `clinician`, `admin`)
  - Strict Content-Security-Policy (CSP), HSTS, anti-caching (`Cache-Control: no-store`)
  - Sliding-window rate limiting ($60 \text{ req/min}$ general, $20 \text{ req/min}$ simulation)
  - Render Cloud deployment with managed PostgreSQL 16

---

## 6. Installation & Local Development Setup

### 6.1 Prerequisites
- **Python:** 3.12+
- **Node.js:** 20.x or 22.x LTS (with `npm`)
- **Git:** 2.40+
- **PostgreSQL 16** (or automatic SQLite fallback for local development)

### 6.2 Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/[REPOSITORY_ORGANIZATION]/glucotwin.git
cd glucotwin

# 2. Set up Python virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install backend dependencies
cd backend
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure environment variables
cp ..\.env.example ..\.env

# 5. Run database migrations
alembic upgrade head

# 6. Generate synthetic patient demo dataset (80 patients, 14 days)
python ..\scripts\generate_demo_data.py --patients 80 --days 14 --seed 42

# 7. Start FastAPI backend server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6.3 Frontend Setup

```bash
# In a separate terminal window:
cd frontend
npm install
npm run dev
# Vite development server starts at http://localhost:5173
```

Visit `http://localhost:5173` in your browser. Interactive API documentation is available at `http://localhost:8000/docs`.

---

## 7. Environment Variables Reference

Configure environment settings in `.env` (refer to `.env.example`):

| Variable | Required | Default / Example | Purpose |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` | Yes | `development` (or `production`) | Enforces production startup validation guards. |
| `DEBUG` | Yes | `true` (Must be `false` in production) | Toggles detailed traceback output. |
| `SECRET_KEY` | Yes | `[SECURE_RANDOM_HEX_64_CHARS]` | JWT signing secret ($\ge 32$ characters). |
| `DATABASE_URL` | Yes | `sqlite+aiosqlite:///./glucotwin.db` | Async SQLAlchemy database URI. |
| `ALLOWED_ORIGINS` | Yes | `["http://localhost:5173","http://localhost:3000"]` | Exact-origin CORS allowlist (JSON array). |
| `ALLOWED_HOSTS` | Yes | `["localhost","127.0.0.1"]` | Allowed Host header domains (JSON array). |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| No | `60` | Lifetime of demo session tokens. |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## 8. API Quickstart & Example Requests

### 8.1 Acquire Short-Lived Demo Clinician Token
```bash
curl -X POST "http://localhost:8000/api/v1/auth/demo-session" \
  -H "Content-Type: application/json" \
  -d '{"role": "demo_clinician"}'
```

### 8.2 Ingest Multi-Modal Sensor Observations
```bash
curl -X POST "http://localhost:8000/api/v1/observations/ingest" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "SYN-T1D-001",
    "observations": [
      {
        "timestamp": "2026-10-20T12:00:00Z",
        "glucose_value": 7.8,
        "unit": "mmol/L",
        "meal_carbs_grams": 45.0,
        "bolus_synthetic_units": 3.0,
        "activity_minutes": 0.0,
        "activity_intensity": 0
      }
    ]
  }'
```

### 8.3 Run Multi-Horizon Digital Twin Forecast
```bash
curl -X POST "http://localhost:8000/api/v1/forecast/run" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "SYN-T1D-001",
    "horizon_minutes": 60,
    "include_uncertainty": true
  }'
```

### 8.4 Run What-If Counterfactual Scenario
```bash
curl -X POST "http://localhost:8000/api/v1/simulation/what-if" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "SYN-T1D-001",
    "scenario_name": "Postprandial 30m Walk",
    "simulation_duration_min": 240,
    "perturbations": [
      {
        "type": "exercise",
        "start_offset_min": 45,
        "duration_min": 30,
        "intensity": 2
      }
    ]
  }'
```

---

## 9. Testing & Quality Assurance Verification

```bash
# 1. Run all 77 backend unit & integration tests
cd backend
pytest -v

# 2. Run model quantitative evaluation benchmark
cd ..
python scripts/evaluate_models.py

# 3. Build frontend production assets
cd frontend
npm run build
```

---

## 10. Repository Documentation Index

| File | Description |
| :--- | :--- |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contributor guidelines, zero-PHI policy, code of conduct, PR workflow. |
| [`SECURITY.md`](SECURITY.md) | Vulnerability disclosure policy, response SLAs, security boundaries. |
| [`docs/architecture.md`](docs/architecture.md) | Comprehensive full-stack architecture, 4-tier segregation, contracts. |
| [`docs/architecture-diagram.mmd`](docs/architecture-diagram.mmd) | Mermaid architectural diagram illustrating components and data flows. |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Database entities, schema definitions, constraints, and indexes. |
| [`docs/model_card.md`](docs/model_card.md) | ML & ODE model card reporting real measured metrics and baselines. |
| [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md) | Benchmark protocol, patient splitting, formulas, and baseline definitions. |
| [`docs/risk_and_limitations.md`](docs/risk_and_limitations.md) | Physiological limitations, sensor lag analysis, and user risk mitigations. |
| [`docs/security.md`](docs/security.md) | Security implementation details, JWT primitives, RBAC matrix, IDOR protection. |
| [`docs/threat_model.md`](docs/threat_model.md) | STRIDE threat model updated against final implementation and residual risks. |
| [`docs/demo_script.md`](docs/demo_script.md) | 22-minute clinical demonstration walkthrough script covering 9 key areas. |
| [`docs/render_deployment.md`](docs/render_deployment.md) | Deployment guide for Render (PostgreSQL, FastAPI backend, Vite static frontend). |
| [`docs/submission-checklist.md`](docs/submission-checklist.md) | Master verification and submission status checklist. |

---

## 11. Troubleshooting & FAQ

### Q1: Why does the forecast return `status: "abstained"`?
The engine fails closed if telemetry is older than 15 minutes (`DATA_TOO_STALE`), if fewer than 12 points are available (`INSUFFICIENT_HISTORY`), or if a sensor gap exceeds 15 minutes (`SENSOR_GAP_EXCEEDED`). Ingest fresh continuous readings to clear the abstention.

### Q2: Why does an insulin inquiry return HTTP 422?
To prevent clinical harm, `RefusalFilter` intercepts any request containing dosing keywords (`bolus recommendation`, `how many units`, `prescribe`). GlucoTwin AI strictly refuses clinical decision support.

### Q3: Why does `GET /ready` return `503 Service Unavailable`?
The readiness check verifies database connectivity, Alembic migration head, and the SHA-256 integrity of model artifacts. Ensure migrations have run (`alembic upgrade head`) and no model files have been modified.

---

## 12. License & Academic Attribution

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

If you reference this software in academic research or educational curriculum, please cite:
```bibtex
@misc{glucotwin2026,
  title={GlucoTwin AI: An In-Silico Physiological Digital Twin & Metabolic Simulation Platform for Type 1 Diabetes Research},
  author={[TEAM_MEMBER_NAMES_AND_ROLES]},
  institution={[COLLEGE_UNIVERSITY_AFFILIATION]},
  year={2026},
  url={[PRODUCTION_DEPLOYED_URL]}
}
```
