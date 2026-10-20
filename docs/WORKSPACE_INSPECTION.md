# GlucoTwin AI - Workspace Inspection Report

**Date of Inspection:** October 20, 2026  
**Inspector:** Senior Full-Stack, Applied ML, Security, & QA Lead  
**Phase:** Phase 1 - Workspace Inspection and Setup  

---

## 1. Executive Summary

This report documents the baseline inspection of the GlucoTwin AI workspace. The inspection examined filesystem contents, Git configuration, runtime environments, toolchain availability, dependency compatibility, and safety constraints.

The workspace was verified to be a clean, previously empty directory (`c:\Users\rocky\OneDrive\vs code project\glucotwin`). To prevent conflicts with the user's outer home-directory Git repository (`C:\Users\rocky`), a dedicated Git repository on branch `main` has been initialized specifically for GlucoTwin AI. Baseline configuration files (`.gitignore` and `.env.example`) have been established with zero disruption to any existing work.

---

## 2. Directory & Git State Verification

| Parameter | State / Value | Notes |
| :--- | :--- | :--- |
| **Workspace Path** | `c:\Users\rocky\OneDrive\vs code project\glucotwin` | Local path on Windows 11 host within OneDrive structure |
| **Initial Files** | `0 files, 0 folders` | Clean workspace directory prior to Phase 1 setup |
| **Surrounding Repos** | `C:\Users\rocky\.git` (branch `main`) | Parent folder tracks separate project (`SMIRITI-AI`); untouched |
| **Local Git Status** | Initialized on branch `main` | Self-contained `.git` created inside `glucotwin/` to isolate project scope |
| **Working Tree** | Clean baseline | Only `.gitignore`, `.env.example`, `README.md`, `PHASE_STATUS.md`, and inspection docs added |

---

## 3. Toolchain & Runtime Environment Verification

The local environment was directly queried via PowerShell to obtain actual runtime versions:

| Tool / Runtime | Required Target | Detected / Actual Version | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | 3.12.x | **Python 3.12.10** (`C:\Users\rocky\AppData\Local\Programs\Python\Python312\python.exe`) | **Available** | Must explicitly invoke `py -3.12` or direct binary path, as Python 3.14.6 is also registered on host |
| **pip** | Latest compatible | **pip 26.1.2** (Python 3.12) | **Available** | Ready for virtual environment creation |
| **Node.js** | >= 18.x | **v25.9.0** | **Available** | Compatible with modern Vite + React frontend |
| **npm** | >= 9.x | **11.12.1** | **Available** | Package manager ready |
| **Git** | >= 2.x | **git version 2.53.0.windows.2** | **Available** | Fully operational |
| **PostgreSQL** | 15.x / 16.x | `psql` command not found; no Windows service active | **Missing / Blocked** | Development fallback to `aiosqlite` configured in `.env.example`; Docker Desktop v29.7.2 available when started |
| **Docker** | Engine / CLI | **Docker version 29.7.2** (Daemon currently stopped) | **Installed** | Can be started if containerized PostgreSQL is desired |

---

## 4. Existing Project Assets & Preserved Work

A thorough recursive inspection of the workspace confirmed:
- **Frontend:** No prior frontend code or artifacts existed.
- **Backend:** No prior backend code, frameworks, or dependencies existed.
- **Database / Migrations:** No existing schema or Alembic migrations existed.
- **Documentation & Tests:** No prior documentation or test suites existed in this folder.
- **Preservation Check:** No existing code or configuration was overwritten or removed. Surrounding user projects in sibling directories remain entirely isolated and untouched.

---

## 5. Dependency & Compatibility Risk Analysis

1. **Python Version Coexistence:**
   - The host system contains both Python 3.12.10 and Python 3.14.6.
   - *Risk:* Calling `python` directly might resolve to Python 3.14 depending on PATH order, where binary wheels for ML libraries (numpy, scipy, scikit-learn, statsmodels) may fail to build or compile.
   - *Mitigation:* Explicitly bind virtual environments using `py -3.12 -m venv venv` and configure IDE interpreter settings to `venv/Scripts/python.exe`.

2. **PostgreSQL Service Availability:**
   - Host does not have an active PostgreSQL Windows service running.
   - *Risk:* Immediate dependency on a live PostgreSQL server will block local development and CI runs.
   - *Mitigation:* Implement a dual-dialect database abstraction layer using SQLAlchemy 2.0 with `asyncpg` for PostgreSQL production/staging and `aiosqlite` for local offline unit/integration testing.

3. **Node.js Release (v25.9.0):**
   - Node 25 is an active release. Packages requiring native C++ bindings via `node-gyp` can occasionally encounter build friction on Windows.
   - *Mitigation:* Rely on standard ESM-based Vite with standard React ecosystem dependencies that utilize pre-bundled ESBuild and no native node-gyp bindings.

4. **OneDrive File Sync Locking:**
   - The workspace resides inside a OneDrive synced folder (`OneDrive\vs code project\glucotwin`).
   - *Risk:* Background file synchronizers can intermittently lock files during high-frequency writes (such as `npm install`, `venv` creation, or SQLite WAL writes).
   - *Mitigation:* Ensure `venv/`, `node_modules/`, `.pytest_cache/`, and `*.db` are strictly excluded from Git and kept clean.

---

## 6. Proposed Repository Architecture

In alignment with the master architecture contracts and mandatory safety guidelines:

```
glucotwin/
├── .env.example                       # Reference environment variables
├── .gitignore                          # Standard ignore patterns
├── README.md                           # Master architectural specification & guidelines
├── PHASE_STATUS.md                     # Phase progress tracking, tests, and exit criteria
├── docs/                               # Architectural & safety documentation
│   └── WORKSPACE_INSPECTION.md         # Workspace & toolchain inspection report
├── backend/                            # FastAPI backend service
│   ├── app/
│   │   ├── api/                        # Versioned API routes
│   │   │   └── v1/
│   │   │       ├── auth.py             # Authentication & RBAC endpoints
│   │   │       ├── patients.py         # Synthetic patient profile management
│   │   │       ├── twin.py             # Digital twin metabolic state & telemetry
│   │   │       ├── simulations.py      # What-If counterfactual scenario engine
│   │   │       ├── metrics.py          # Glycemic metrics (TIR, TAR, TBR, CV, GMI)
│   │   │       └── guardrails.py       # Clinical safety rule verification & audit
│   │   ├── core/                       # Core configuration, security, & middleware
│   │   │   ├── config.py               # Pydantic v2 settings management
│   │   │   ├── security.py             # JWT token handling & password hashing
│   │   │   ├── database.py             # Async database session & engine
│   │   │   └── guardrails.py           # Safety rule enforcement & recommendation blocker
│   │   ├── models/                     # SQLAlchemy declarative ORM models
│   │   │   ├── user.py                 # User & researcher accounts
│   │   │   ├── patient.py              # Synthetic patient profiles & parameters
│   │   │   ├── telemetry.py            # Observed CGM & telemetry records
│   │   │   └── simulation.py           # Hypothetical scenarios & twin run logs
│   │   ├── schemas/                    # Pydantic validation schemas (Strict separation)
│   │   │   ├── observed.py             # Real/observed synthetic telemetry
│   │   │   ├── derived.py              # Calculated metrics (TIR, GMI, glycemic variability)
│   │   │   ├── predicted.py            # ARX / Kalman filter forecast state
│   │   │   └── hypothetical.py         # What-if perturbation schemas
│   │   ├── services/                   # Business & ML logic
│   │   │   ├── twin_engine.py          # Digital twin metabolic simulator
│   │   │   ├── physiological_model.py  # Bergman Minimal Model ODE / discrete simulator
│   │   │   ├── arx_kalman.py           # ARX autoregressive & Kalman state estimator
│   │   │   ├── metrics_service.py      # Clinical standard glycemic statistics
│   │   │   └── synthetic_data.py       # Deterministic synthetic patient generator
│   │   └── main.py                     # FastAPI entry point & exception handlers
│   ├── alembic/                        # Database migration scripts
│   ├── tests/                          # Automated test suite
│   │   ├── conftest.py                 # Pytest fixtures & test database
│   │   ├── test_guardrails.py          # Clinical safety & recommendation blocker tests
│   │   ├── test_twin_engine.py         # Digital twin simulation tests
│   │   ├── test_metrics.py             # TIR / TAR / TBR validation tests
│   │   └── test_api.py                 # Endpoint integration tests
│   └── requirements.txt                # Backend dependencies (Python 3.12)
├── frontend/                           # React + Vite web dashboard
│   ├── src/
│   │   ├── components/                 # Reusable UI widgets (AGP, Metric Cards, Twin Chart)
│   │   ├── pages/                      # Dashboard, What-If Simulator, Patient Profile
│   │   ├── services/                   # API client layer
│   │   ├── App.jsx
│   │   └── index.css                   # Modern design system (tokens, glassmorphism, responsive)
│   ├── package.json
│   └── vite.config.js
└── scripts/                            # Operational & simulation scripts
    └── seed_synthetic_patients.py     # Deterministic synthetic patient generator
```

---

## 7. Safety & Clinical Guardrail Rules Enforced

1. **Synthetic Data Exclusively:** No real patient health information (PHI/PII) will ever be collected or stored.
2. **Clinical Decision Guardrail (Rule 10):** The system shall strictly refuse to generate or output insulin dosages, medication adjustments, or clinical treatment advice.
3. **Strict Data Segregation (Rule 9):** Schema contracts rigorously separate **Observed**, **Derived**, **Predicted**, and **Hypothetical** datasets.
4. **Fail-Closed Architecture (Rule 8):** Any anomalous input, authentication lapse, or model divergence triggers an immediate fail-closed response with clear audit logging.
5. **No Paid/External Black-Box LLM Predictions (Rule 6):** All metabolic modeling relies on transparent, verifiable mathematical/physiological engines (Bergman minimal model, ARX, Kalman filtering).

---

## 8. Acceptance Verification for Phase 1

- [x] Workspace directory structure and Git status thoroughly documented.
- [x] Toolchain and runtime availability verified (`Python 3.12.10`, `pip 26.1.2`, `Node v25.9.0`, `npm 11.12.1`, `Git 2.53.0`, `PostgreSQL status`).
- [x] Existing work preserved and zero destructive modifications made.
- [x] Dependency and compatibility risks identified with clear mitigation pathways.
- [x] Final repository architecture proposed.
- [x] Baseline `.gitignore` and `.env.example` added.
- [x] Strict adherence to Phase 1 boundaries (no application code or models implemented).
