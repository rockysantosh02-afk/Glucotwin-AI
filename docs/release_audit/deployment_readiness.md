# GlucoTwin AI - Release Audit Deployment Readiness Report

**Platform:** Render Cloud Platform (`render.yaml` Blueprint)  
**Architecture:** 3-Tier Distributed Topology (PostgreSQL + FastAPI Web Service + Vite Static SPA)  
**Target Environment:** Production / Staging  
**Readiness Rating:** READY FOR DEPLOYMENT (All configuration assets and guards verified)  

---

## 1. Deployment Topology & Infrastructure Blueprint

GlucoTwin AI is configured for automated Infrastructure-as-Code deployment via the root [`render.yaml`](file:///c:/Users/rocky/OneDrive/vs%20code%20project/glucotwin/render.yaml) file.

```
                          ┌─────────────────────────┐
                          │     User / Clinician    │
                          └────────────┬────────────┘
                                       │ HTTPS
                                       ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      Render Cloud Infrastructure                    │
    │                                                                     │
    │   ┌────────────────────────┐         ┌──────────────────────────┐   │
    │   │  glucotwin-frontend    │         │    glucotwin-backend     │   │
    │   │  (Static Site - Vite)  ├────────►│  (Python Web Service)    │   │
    │   │  SPA Rewrite: /*       │  CORS   │  Uvicorn / FastAPI       │   │
    │   └────────────────────────┘         └────────────┬─────────────┘   │
    │                                                   │ AsyncPG         │
    │                                                   ▼                 │
    │                                      ┌──────────────────────────┐   │
    │                                      │       glucotwin-db       │   │
    │                                      │  (Managed PostgreSQL 16) │   │
    │                                      └──────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────┘
```

### Component Specifications:

| Component | Render Service Type | Plan / Sizing | Build / Migration Command | Start / Publish Command |
| :--- | :--- | :--- | :--- | :--- |
| **`glucotwin-db`** | PostgreSQL Database | Starter (PG 16) | N/A (Managed by Render) | Automatic connection string injection (`DATABASE_URL`) |
| **`glucotwin-backend`** | Web Service (Python 3) | Starter / Standard | `pip install -r backend/requirements.txt && cd backend && alembic upgrade head` | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2` |
| **`glucotwin-frontend`** | Static Site | Free / Starter | `cd frontend && npm install && npm run build` | Publish: `frontend/dist` with SPA rewrite rule `/* -> /index.html` |

---

## 2. Production Environment Configuration

The backend implements strict startup verification in [`app/core/config.py`](file:///c:/Users/rocky/OneDrive/vs%20code%20project/glucotwin/backend/app/core/config.py). If `ENVIRONMENT=production`, the application refuses to boot if any security settings are inadequate.

### Required Injected Environment Variables:

| Variable | Target Service | Requirement | Validated Behavior |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | `glucotwin-backend` | Connection string starting with `postgresql://` | Refuses to start if SQLite is detected in production. Automatically transformed to `postgresql+asyncpg://`. |
| `ENVIRONMENT` | `glucotwin-backend` | `production` | Activates strict production mode, disables swagger docs (`/docs`, `/redoc`), and enables security validators. |
| `DEBUG` | `glucotwin-backend` | `false` | Must be strictly `false`. Startup aborts if `DEBUG=true`. |
| `STRICT_CONFIG_VALIDATION` | `glucotwin-backend` | `true` | Enforces fail-closed configuration audits at boot. |
| `SECRET_KEY` | `glucotwin-backend` | Cryptographically random string ($\ge 32$ chars) | Must not match the insecure default key. Startup fails if weak or short. |
| `ALLOWED_ORIGINS` | `glucotwin-backend` | JSON array or comma-separated origins | Wildcards (`*`) are strictly prohibited in production. Configured to match frontend domain. |
| `ALLOWED_HOSTS` | `glucotwin-backend` | Comma-separated domain names | Wildcards (`*`) are strictly prohibited. Enforces HTTP `Host` header validation. |
| `VITE_API_BASE_URL` | `glucotwin-frontend` | URL of backend web service | Injected at build time into Vite static distribution for cross-origin API calls. |

---

## 3. Step-by-Step Operator Deployment Runbook

### Method A: One-Click Render Blueprint Deployment (Recommended)
1. Push all verified commits to the GitHub repository on branch `main`.
2. Log in to the [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** and select **Blueprint**.
4. Connect the GitHub repository `glucotwin`.
5. Render detects [`render.yaml`](file:///c:/Users/rocky/OneDrive/vs%20code%20project/glucotwin/render.yaml) and automatically provisions:
   - PostgreSQL 16 database (`glucotwin-db`)
   - Web Service (`glucotwin-backend`)
   - Static Site (`glucotwin-frontend`)
6. Review the generated configuration and click **Apply**.
7. Once build completes, note the public URLs:
   - Backend: `https://glucotwin-backend.onrender.com`
   - Frontend: `https://glucotwin-frontend.onrender.com`

### Method B: Manual Service Creation
If deploying services individually via the Render UI:
1. **Create Database:**
   - Click **New +** -> **PostgreSQL**.
   - Name: `glucotwin-db`, Database: `glucotwin`, User: `glucotwin_user`, Version: `16`.
2. **Create Backend Web Service:**
   - Click **New +** -> **Web Service**.
   - Repository: `glucotwin`, Environment: `Python 3`.
   - Build Command: `pip install -r backend/requirements.txt && cd backend && alembic upgrade head`
   - Start Command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
   - Add Environment Variables: Link `DATABASE_URL` from `glucotwin-db`, set `ENVIRONMENT=production`, `DEBUG=false`, and a 64-character hex `SECRET_KEY`.
3. **Create Frontend Static Site:**
   - Click **New +** -> **Static Site**.
   - Build Command: `cd frontend && npm install && npm run build`
   - Publish Directory: `frontend/dist`
   - Add Environment Variable: `VITE_API_BASE_URL=https://<your-backend>.onrender.com`
   - Add Rewrite Rule: Source: `/*`, Destination: `/index.html`, Action: `Rewrite`.

---

## 4. Post-Deployment Verification & Smoke Test Protocol

Once the services are deployed and Render marks them "Live", execute the production smoke test suite against the live deployment URLs:

```powershell
python scripts/smoke_test.py --backend-url https://glucotwin-backend.onrender.com --frontend-url https://glucotwin-frontend.onrender.com
```

### Verification Criteria:
1. Backend `/health` returns `200 OK` (Liveness).
2. Backend `/ready` returns `200 OK` with `database: true` and current migration head.
3. Unauthenticated requests to `/api/v1/patients/` are rejected with `401 Unauthorized`.
4. Demo clinician session issues JWT token with `201 Created`.
5. Patient list loads successfully with anti-caching headers (`Cache-Control: no-store`).
6. Forecast execution completes and returns valid trajectory with uncertainty bounds.
7. What-If ODE counterfactual simulation returns perturbed trajectory.
8. Clinical safety refusal correctly catches dosing optimization requests (`422 Unprocessable Entity`).
9. Telemetry CSV export returns sanitized RFC 4180 stream with formula injection defenses.
10. Frontend static site loads and renders the GlucoTwin AI dashboard without console errors.

---

## 5. Rollback & Disaster Recovery Procedures

- **Database Rollback:**
  If a migration causes runtime schema divergence, rollback using Alembic:
  ```bash
  cd backend && alembic downgrade -1
  ```
- **Application Rollback:**
  In the Render Dashboard for `glucotwin-backend`, navigate to the **Deploys** tab and click **Rollback to this deploy** on the last known healthy deployment commit.
- **Circuit Breaker / Downtime Prevention:**
  If the PostgreSQL database experiences transient disconnects, `/health` continues to return 200 (keeping the container alive) while `/ready` returns 503 Service Unavailable, signaling routing proxies to halt incoming traffic until recovery.
