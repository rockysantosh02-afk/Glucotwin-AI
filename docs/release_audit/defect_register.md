# GlucoTwin AI - Release Audit Defect Register

**Target Application:** GlucoTwin AI Research Prototype  
**Audit Scope:** Final Production-Readiness Audit, Self-Repair & Render Deployment  
**Audit Status:** Complete — All Confirmed Defects Remediated and Verified  

---

## Defect Summary Matrix

| Defect ID | Category | Severity | Description | Status | Verification Evidence |
| :--- | :--- | :---: | :--- | :---: | :--- |
| **DEF-01** | Frontend Architecture | **High** | `frontend/src/main.js` had template boilerplate mounting to non-existent `#app` instead of wiring `index.html` UI to `api.js` and `charts.js`. | **RESOLVED** | `npm run build` succeeds (26.6 kB JS, 15.1 kB CSS); DOM elements bound, demo auth, patient select, forecast & what-if controls active. |
| **DEF-02** | Security & Auth | **High** | `frontend/src/api.js` stored JWT tokens in browser `localStorage`, violating zero-persistence session security policy. | **RESOLVED** | In-memory token storage implemented (`this.token`), auto-reauthenticates on 401; zero tokens written to Web Storage. |
| **DEF-03** | DevOps / Deployment | **High** | Root `render.yaml` blueprint was absent, preventing automated Infrastructure-as-Code deployment to Render. | **RESOLVED** | `render.yaml` created at root configuring managed PostgreSQL 16, Python web service (FastAPI/Uvicorn), and static site (React/Vite). |
| **DEF-04** | QA Automation | **High** | Missing automated end-to-end smoke test script for pre-flight and post-deployment validation. | **RESOLVED** | `scripts/smoke_test.py` created using standard library `urllib`; tests 10 live security, API, ML, and refusal assertions (10/10 PASS). |
| **DEF-05** | Security / Ingestion | **Medium** | Missing CSV telemetry exporter with RFC 4180 CSV formula-injection defense (`=`, `+`, `-`, `@` neutralization) and synthetic disclaimer headers. | **RESOLVED** | Added `GET /api/v1/patients/{patient_identifier}/telemetry/export` with `sanitize_csv_cell()` in `backend/app/api/v1/telemetry.py`. Tested in pytest. |
| **DEF-06** | Networking / Config | **Medium** | `frontend/src/api.js` used hardcoded `/api/v1` base URL, failing against decoupled static hosting on Render without dev proxy. | **RESOLVED** | Added dynamic `import.meta.env.VITE_API_BASE_URL` resolution with fallback to `/api/v1`. |

---

## Detailed Defect Investigations & Remediation Records

### DEF-01: Frontend Event Binding & Architectural Decoupling
- **Component:** `frontend/src/main.js`, `frontend/index.html`
- **Severity:** High
- **Identified Condition:**  
  `index.html` defined a complete, beautifully structured clinical research UI (patient selector, digital twin status indicators, tabs for Time-Series, AGP, Forecast, and Counterfactual Simulation, plus modal inspection dialogues). However, `frontend/src/main.js` contained an unmodified Vite starter template (`setupCounter(document.querySelector('#counter'))`) trying to attach to `#app`. The real application logic was completely unwired.
- **Root Cause:**  
  The frontend build setup had separated `api.js` and `charts.js`, but the integration coordinator script (`main.js`) had not been implemented to bind DOM interactions to API methods and chart renderers.
- **Remediation:**  
  1. Rewrote `frontend/src/main.js` from scratch as an asynchronous event-driven controller:
     - Automatically requests a demo session on page load via `api.createDemoSession()`.
     - Populates the patient selector dropdown via `api.getPatients()`.
     - Fetches 14-day telemetry and renders the 24-hour CGM timeline using pure SVG.
     - Fetches AGP percentiles (p5, p25, p50, p75, p95) and renders the Ambulatory Glucose Profile.
     - Invokes `/twin/forecast` to generate multi-horizon predictions with empirical uncertainty bands.
     - Implements interactive What-If simulation slider bindings (Carb delta $\pm 100$g, meal shift $-60$ to $+120$ min, exercise intensity $0-3$, duration $0-180$ min) and renders counterfactual trajectory divergence.
     - Implements UI notifications for abstention reasons and clinical safety disclaimer popups.
  2. Verified build via `npm run build` in `frontend/`. Bundle size: 27.17 kB HTML, 15.11 kB CSS, 26.62 kB JS (gzipped: 7.89 kB).

---

### DEF-02: LocalStorage JWT Token Persistence Vulnerability
- **Component:** `frontend/src/api.js`
- **Severity:** High (Security)
- **Identified Condition:**  
  `api.js` contained calls to `localStorage.setItem('glucotwin_token', token)` and `localStorage.getItem('glucotwin_token')`. Browser local storage is persistent across sessions and vulnerable to exfiltration via cross-site scripting (XSS).
- **Security Policy Violation:**  
  Master Prompt Section 6: *"No JWT or session tokens persisted in browser localStorage."*
- **Remediation:**  
  1. Removed all references to `window.localStorage`.
  2. Refactored `ApiClient` to retain the signed JWT token strictly as an in-memory class attribute (`this.token = null`).
  3. Added automatic re-authentication logic: if an API call receives HTTP 401 Unauthorized, the client transparently re-authenticates via `createDemoSession()` and retries the request once before failing closed.
  4. Added `clearSession()` method that zeros the in-memory token on logout.
- **Verification:**  
  Inspected `frontend/src/api.js` via automated ripgrep. Zero occurrences of `localStorage` exist across the entire repository codebase.

---

### DEF-03: Missing Render Blueprint for Infrastructure as Code
- **Component:** `render.yaml` (Root)
- **Severity:** High (DevOps / Deployment)
- **Identified Condition:**  
  While documentation in `docs/render_deployment.md` described Render deployment steps, no root `render.yaml` file was present to enable one-click Blueprint deployment.
- **Remediation:**  
  Created `render.yaml` defining:
  1. **Managed Database:** PostgreSQL 16 named `glucotwin-db` (Starter plan), database `glucotwin`, user `glucotwin_user`.
  2. **Backend Web Service:** Python 3.12 service named `glucotwin-backend`:
     - Build Command: `pip install -r backend/requirements.txt && cd backend && alembic upgrade head`
     - Start Command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
     - Health Check Path: `/health`
     - Injected Env Vars: `DATABASE_URL` linked to `glucotwin-db`, `ENVIRONMENT=production`, `DEBUG=false`, `STRICT_CONFIG_VALIDATION=true`, auto-generated 64-char `SECRET_KEY`, exact `ALLOWED_ORIGINS`.
  3. **Frontend Static Site:** Static site named `glucotwin-frontend`:
     - Build Command: `cd frontend && npm install && npm run build`
     - Publish Directory: `frontend/dist`
     - Route Rewrite: Single-Page Application (SPA) catch-all rewrite rule (`/* -> /index.html`).
- **Verification:**  
  Validated syntax and schema against official Render Blueprint Specification.

---

### DEF-04: Lack of Automated Production Smoke Test Suite
- **Component:** `scripts/smoke_test.py`
- **Severity:** High (QA / Reliability)
- **Identified Condition:**  
  No automated smoke test script existed to probe live staging or production instances across network boundaries without third-party dependencies.
- **Remediation:**  
  Implemented `scripts/smoke_test.py` using strictly Python standard library modules (`urllib.request`, `json`, `argparse`, `sys`, `time`):
  1. Checks `/health` liveness (HTTP 200).
  2. Checks `/ready` component connectivity (HTTP 200, DB connected).
  3. Verifies unauthenticated access denial on `/api/v1/patients/` (HTTP 401).
  4. Obtains signed demo clinician JWT via `POST /api/v1/auth/demo-session` (HTTP 201).
  5. Retrieves patient cohort (HTTP 200).
  6. Verifies defensive HTTP headers (`X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, CSP).
  7. Invokes digital twin forecast trajectory with uncertainty (`/twin/forecast`) (HTTP 200, status `completed`).
  8. Executes What-If counterfactual ODE simulation (`/twin/simulate`) (HTTP 200, trajectory points returned).
  9. Verifies clinical dosing safety refusal: sends `recommend_insulin_dose: true` and verifies HTTP 422 with `CLINICAL_SAFETY_REFUSAL` refusal envelope.
  10. Exports telemetry CSV via `/telemetry/export` and verifies `text/csv` MIME type, synthetic disclaimer, and formula neutralization.
- **Verification:**  
  Executed against local backend on port 8001: 10/10 checks PASSED with exit code 0.

---

### DEF-05: Missing Telemetry CSV Export & Formula Injection Sanitization
- **Component:** `backend/app/api/v1/telemetry.py`, `frontend/index.html`
- **Severity:** Medium (Security & Data Handling)
- **Identified Condition:**  
  Clinicians and researchers required CSV telemetry export capabilities. However, export was missing and raw data export without sanitization could allow spreadsheet CSV formula injection (CVE-style CSV injection executing macros via `=CMD(...)`, `+`, `-`, or `@`).
- **Remediation:**  
  1. Implemented `sanitize_csv_cell(value)` in `backend/app/api/v1/telemetry.py` which prefixes dangerous formula-starting characters (`=`, `+`, `-`, `@`, `\t`, `\r`) with a single apostrophe (`'`).
  2. Implemented `GET /api/v1/patients/{patient_identifier}/telemetry/export` returning an RFC 4180 compliant CSV stream with mandatory research disclaimers:
     - `# RESEARCH & EDUCATION PROTOTYPE ONLY - NOT A MEDICAL DEVICE`
     - `# STRICTLY SYNTHETIC PATIENT DATA - ZERO PHI`
  3. Added export button in `frontend/index.html` linked in `frontend/src/main.js`.
  4. Added regression test `test_telemetry_csv_export_and_formula_injection_defense` in `backend/tests/test_telemetry_and_patients_api.py`.
- **Verification:**  
  Pytest suite verified test passes; smoke test check 10 verified live HTTP response.

---

### DEF-06: Static Frontend Cross-Origin API Host Resolution
- **Component:** `frontend/src/api.js`
- **Severity:** Medium (Networking)
- **Identified Condition:**  
  `ApiClient` initialized with static `const API_BASE = '/api/v1'`. In local Vite dev mode, requests are proxied by `vite.config.js`. In production, where frontend is hosted on `onrender.com` as a static site and backend is a separate web service, relative paths would result in 404s.
- **Remediation:**  
  Updated `api.js` constructor to inspect `import.meta.env.VITE_API_BASE_URL`. If provided, it configures `https://glucotwin-backend.onrender.com/api/v1`. If absent, it gracefully falls back to `/api/v1` for local containerized or reverse-proxy deployments.
- **Verification:**  
  Verified environment variable injection compatibility in `render.yaml` (`VITE_API_BASE_URL`).
