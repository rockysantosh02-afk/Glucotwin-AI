# GlucoTwin AI — Render Deployment & Operational Validation Checklist

**Platform:** Render Cloud Infrastructure  
**Target Repository:** `https://github.com/rockysantosh02-afk/Glucotwin-AI`  
**Purpose:** Pre-Flight, Provisioning, and Post-Deployment Verification Checklist  
**Review Lead:** QA Reliability Engineer & DevOps Release Lead  

---

## 1. Pre-Flight Verification Checklist (Local Workspace)

Before initiating deployment on Render, ensure all local validation checks pass:

- [x] **VERIFIED** — **Clean Git State:** Branch `main` is clean, all files staged and committed.
- [x] **VERIFIED** — **Zero Secret Leakage:** No `.env`, private keys, or API tokens tracked in Git repository.
- [x] **VERIFIED** — **Backend Pytest Suite:** All 79 tests pass in under 5 seconds (`pytest` in `backend/`).
- [x] **VERIFIED** — **Production Startup Guards Tested:** Strict guards reject short secrets, debug mode, and wildcard hosts (`test_config_guards.py`).
- [x] **VERIFIED** — **Database URL Auto-Normalization Tested:** `Settings` automatically upgrades Render's `postgresql://` to `postgresql+asyncpg://` (`test_render_database_url_auto_normalization`).
- [x] **VERIFIED** — **Alembic Migrations Tested:** Upgrade and rollback execute cleanly on clean database (`test_database_migrations.py`).
- [x] **VERIFIED** — **Frontend Production Build:** Vite build produces single lightweight bundle (26.7 kB JS, 15.1 kB CSS) with zero errors (`npm run build` in `frontend/`).
- [x] **VERIFIED** — **In-Memory Session Security:** Frontend stores JWT access tokens strictly in JavaScript memory (`this.token`), zero tokens in `localStorage`.
- [x] **VERIFIED** — **E2E Smoke Test Suite:** Pure standard-library smoke test script verifies 10 live endpoints (`scripts/smoke_test.py`).
- [x] **VERIFIED** — **Infrastructure-as-Code Blueprint:** Root [`render.yaml`](file:///c:/Users/rocky/OneDrive/vs%20code%20project/glucotwin/render.yaml) validated against Render Blueprint specifications.

---

## 2. Cloud Provisioning Step-by-Step Runbook

### Step 1: Provision Managed PostgreSQL (`glucotwin-db`)
1. Log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **PostgreSQL**.
3. Fill in configuration:
   - **Name:** `glucotwin-db`
   - **Database:** `glucotwin`
   - **User:** `glucotwin_user`
   - **Region:** `Oregon (US West)` (or your preferred region)
   - **PostgreSQL Version:** `16`
   - **Plan:** `Starter` ($7/mo) or `Free` (if available for testing)
4. Click **Create Database**.
5. Once created, copy the **Internal Database URL** (`postgresql://...`).

### Step 2: Deploy Backend Web Service (`glucotwin-backend`)
1. Click **New +** -> **Web Service**.
2. Connect repository: `rockysantosh02-afk/Glucotwin-AI`.
3. Configure settings:
   - **Name:** `glucotwin-backend`
   - **Region:** Must match database region (e.g. `Oregon`)
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     pip install --upgrade pip && pip install -r requirements.txt && alembic upgrade head
     ```
   - **Start Command:**
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
     ```
   - **Plan:** `Starter` ($7/mo)
4. Under **Advanced**, configure **Health Check Path**: `/health`.
5. Under **Environment Variables**, add:
   - `ENVIRONMENT` = `production`
   - `DEBUG` = `false`
   - `LOG_LEVEL` = `INFO`
   - `SECRET_KEY` = *(Generate via `python -c "import secrets; print(secrets.token_hex(32))"`)*
   - `DATABASE_URL` = *(Paste Internal Database URL from Step 1)*
   - `USE_SQLITE_FALLBACK` = `false`
   - `ALLOWED_HOSTS` = `glucotwin-backend.onrender.com`
   - `ALLOWED_ORIGINS` = `https://glucotwin-frontend.onrender.com` *(temporary placeholder, update in Step 4)*
   - `ACCESS_TOKEN_EXPIRE_MINUTES` = `60`
   - `RATE_LIMIT_DEFAULT_PER_MINUTE` = `120`
6. Click **Create Web Service**. Wait for build and deployment to finish.

### Step 3: Deploy Frontend Static Site (`glucotwin-frontend`)
1. Click **New +** -> **Static Site**.
2. Connect repository: `rockysantosh02-afk/Glucotwin-AI`.
3. Configure settings:
   - **Name:** `glucotwin-frontend`
   - **Branch:** `main`
   - **Root Directory:** `frontend`
   - **Build Command:**
     ```bash
     npm install && npm run build
     ```
   - **Publish Directory:** `dist`
4. Under **Redirects/Rewrites**, add:
   - **Type:** `Rewrite`
   - **Source:** `/*`
   - **Destination:** `/index.html`
5. Under **Environment Variables**, add:
   - `VITE_API_BASE_URL` = `https://glucotwin-backend.onrender.com`
6. Click **Create Static Site**. Wait for build to finish.

### Step 4: Finalize Cross-Origin Alignment (CORS & Hosts)
1. Note the exact URL of your deployed frontend (e.g. `https://glucotwin-frontend.onrender.com`).
2. Go to **Backend Service** (`glucotwin-backend`) -> **Environment**.
3. Verify `ALLOWED_ORIGINS` exactly matches your frontend URL:
   ```env
   ALLOWED_ORIGINS=https://glucotwin-frontend.onrender.com
   ```
4. Verify `ALLOWED_HOSTS` matches your backend domain:
   ```env
   ALLOWED_HOSTS=glucotwin-backend.onrender.com
   ```
5. Click **Save Changes** (triggers an automated zero-downtime redeploy).

---

## 3. Post-Deployment Verification Checklist

Execute the automated smoke test suite directly against the live Render URLs:

```powershell
python scripts/smoke_test.py --backend-url https://glucotwin-backend.onrender.com --frontend-url https://glucotwin-frontend.onrender.com
```

### Verification Matrix:

| Check # | Assertion | Method / Endpoint | Expected Outcome | Live Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | Backend Liveness | `GET /health` | HTTP 200, `status: "healthy"` | Pending Operator Deploy |
| **2** | Component Readiness | `GET /ready` | HTTP 200, `database: true`, `migration_head: "0001_initial_schema"` | Pending Operator Deploy |
| **3** | Unauthenticated Denial | `GET /api/v1/patients/` | HTTP 401 Unauthorized, standardized error envelope | Pending Operator Deploy |
| **4** | Demo Session Creation | `POST /api/v1/auth/demo-session` | HTTP 201 Created, signed JWT returned | Pending Operator Deploy |
| **5** | Authorized Cohort Listing | `GET /api/v1/patients/` (Bearer) | HTTP 200 OK, synthetic patient array returned | Pending Operator Deploy |
| **6** | Defensive Security Headers | Response Header Inspection | `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, CSP present | Pending Operator Deploy |
| **7** | Digital Twin Forecast | `POST /api/v1/patients/{id}/twin/forecast` | HTTP 200 OK, multi-horizon predictions with uncertainty bands | Pending Operator Deploy |
| **8** | What-If ODE Simulation | `POST /api/v1/patients/{id}/twin/simulate` | HTTP 200 OK, counterfactual trajectory points returned | Pending Operator Deploy |
| **9** | Clinical Refusal Guardrail | `POST /api/v1/patients/{id}/twin/simulate` (with `recommend_insulin_dose: true`) | HTTP 422 Unprocessable Entity, `CLINICAL_SAFETY_REFUSAL` | Pending Operator Deploy |
| **10** | Telemetry CSV Export | `GET /api/v1/patients/{id}/telemetry/export` | HTTP 200 OK, `text/csv`, RFC 4180 formula-injection neutralized | Pending Operator Deploy |
| **11** | Frontend Static SPA | `GET /` | HTTP 200 OK, GlucoTwin UI loaded, zero JavaScript runtime errors | Pending Operator Deploy |

---

## 4. Disaster Recovery & Rollback Procedures

### Rollback Backend Deployment:
If an issue arises after deploying an update:
1. In the Render Dashboard, open `glucotwin-backend`.
2. Navigate to the **Deploys** tab.
3. Locate the previous healthy deployment and click **Rollback to this deploy**.

### Rollback Database Migration:
If a migration needs to be reversed:
```bash
alembic downgrade -1
```

### Rotating `SECRET_KEY`:
If `SECRET_KEY` needs to be rotated:
1. Generate a new secret: `python -c "import secrets; print(secrets.token_hex(32))"`.
2. Update `SECRET_KEY` in `glucotwin-backend` environment settings.
3. Save changes. Existing active sessions will seamlessly renew their in-memory tokens on their next action.
