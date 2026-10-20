# Contributing to GlucoTwin AI

Thank you for your interest in contributing to **GlucoTwin AI**! This project is an in-silico physiological digital twin and metabolic simulation platform developed for Type 1 Diabetes research and education.

Please review this document thoroughly before submitting issues or pull requests.

---

## 1. Core Architectural & Scientific Rules

All contributors must strictly adhere to the following mandatory guidelines:

1. **Synthetic Data Exclusively (Zero-PHI Policy):**  
   Never commit, upload, or process real-world patient data, electronic health records, or Protected Health Information (PHI). All data must be generated using `scripts/generate_demo_data.py`.
2. **Deterministic, Real Implementations:**  
   No fake APIs, mock dashboards, hardcoded predictions, or fabricated test results. All statistical and mathematical calculations must execute against actual Python and TypeScript engines.
3. **No Commercial LLM APIs for Predictions:**  
   Do not use paid third-party AI APIs or LLMs for blood glucose forecasting, risk scoring, or physiological parameter estimation. Modeling relies strictly on deterministic ODEs (Bergman Minimal Model) and statistical state estimators (ARX-Kalman).
4. **Fail-Closed Safety Guardrails:**  
   The platform must **strictly abstain** when data freshness, history length, or physiological bounds are violated. Never output insulin dosing calculations or clinical treatment recommendations.
5. **Strict 4-Tier Data Segregation:**  
   Maintain strict isolation between Observed (Tier 1), Derived (Tier 2), Predicted (Tier 3), and Hypothetical (Tier 4) data streams across database models, API schemas, and UI components.

---

## 2. Local Development Setup

### 2.1 Prerequisites
- **Python:** Version 3.12+
- **Node.js:** Version 20.x or 22.x LTS (with `npm`)
- **Git:** Version 2.40+
- **PostgreSQL:** Version 15+ (Production) or SQLite 3 (Development/Testing fallback)

### 2.2 Backend Setup
```bash
# 1. Clone repository
git clone https://github.com/[REPOSITORY_ORGANIZATION]/glucotwin.git
cd glucotwin

# 2. Setup Python virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
cd backend
pip install -r requirements.txt

# 4. Configure environment
copy ..\.env.example ..\.env

# 5. Run database migrations
alembic upgrade head

# 6. Generate synthetic demo dataset
python ..\scripts\generate_demo_data.py --patients 80 --days 14 --seed 42

# 7. Start FastAPI development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2.3 Frontend Setup
```bash
# In a separate terminal:
cd frontend
npm install
npm run dev
# Vite server boots at http://localhost:5173
```

---

## 3. Testing and Verification Workflow

Before submitting a Pull Request, verify that all test suites pass without warnings:

```bash
# 1. Run all backend unit and integration tests (77 tests)
cd backend
pytest -v

# 2. Run model quantitative evaluation benchmark
cd ..
python scripts/evaluate_models.py

# 3. Verify frontend build
cd frontend
npm run build
```

---

## 4. Git Commit & Pull Request Guidelines

1. **Branch Naming:**
   - Features: `feature/short-description`
   - Bugfixes: `fix/short-description`
   - Documentation: `docs/short-description`
2. **Commit Messages:**
   Follow Conventional Commits:
   - `feat(twin): add Kalman filter adaptive noise scaling`
   - `fix(security): enforce exact origin CORS on demo routes`
   - `docs(model-card): document measured 60-min Clarke grid distribution`
   - `test(ingestion): add concurrent duplicate timestamp collision test`
3. **Pull Request Checklist:**
   - [ ] Branch is rebased against latest `main`.
   - [ ] All 77 backend tests pass (`pytest`).
   - [ ] Frontend builds cleanly with zero TypeScript/Vite errors (`npm run build`).
   - [ ] No real patient data or secrets (`.env`) are staged or committed.
   - [ ] Documentation and data dictionaries are updated for any schema changes.
