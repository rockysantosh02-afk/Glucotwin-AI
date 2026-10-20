# GlucoTwin AI - Render Cloud Deployment Guide

**Document Version:** 1.0.0  
**Target Platform:** [Render.com](https://render.com)  
**Architecture:** 3-Tier Distributed Topology (Managed PostgreSQL, FastAPI Backend Web Service, React/Vite Static Site)  
**Security Status:** Production Hardened (Strict CORS, CSP Headers, Non-Root Execution, Fail-Closed Startup Guards)  

---

## 1. Cloud Architecture Overview

```
 [ Client Browser ]
        │
        ├─── HTTPS (Static Assets) ───► [ Render Static Site: React/Vite Frontend ]
        │                                - Build: `npm install && npm run build`
        │                                - Publish: `frontend/dist`
        │                                - Rewrite: `/* -> /index.html` (SPA Routing)
        │
        └─── HTTPS (JSON API) ────────► [ Render Web Service: FastAPI Backend ]
                                         - Build: `pip install -r requirements.txt`
                                         - Pre-deploy: `alembic upgrade head`
                                         - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
                                         - Health: `/health` | Readiness: `/ready`
                                         │
                                         ▼ Private Network TLS
                                [ Render Managed PostgreSQL 16 ]
                                 - Dedicated Connection Pool
                                 - Non-destructive Migrations
```

---

## 2. Infrastructure Services Specification

### Service 1: Managed PostgreSQL Database
- **Name:** `glucotwin-db`
- **Database Engine:** PostgreSQL 16
- **Plan:** Free or Starter
- **Access Strategy:** Internal connection string (`postgresql+asyncpg://...`) used by the FastAPI web service via private network networking. External connections restricted to administrative maintenance.

### Service 2: Python FastAPI Backend Web Service
- **Name:** `glucotwin-backend`
- **Environment:** `Python 3.12`
- **Root Directory:** `backend`
- **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt && alembic upgrade head`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
- **Health Check Path:** `/health`
- **Readiness Check Path:** `/ready`
- **Auto-Deploy:** Enabled on Git push to branch `main`.

### Service 3: React / Vite Static Frontend
- **Name:** `glucotwin-frontend`
- **Environment:** `Static Site`
- **Root Directory:** `frontend`
- **Build Command:** `npm install && npm run build`
- **Publish Directory:** `dist`
- **SPA Routing Rules (Redirects/Rewrites):**
  - **Source:** `/*`
  - **Destination:** `/index.html`
  - **Action:** `Rewrite`

---

## 3. Production Environment Variables & Secrets

> ⚠️ **SECURITY WARNING:** Never commit real secrets to Git. Configure these variables directly in the Render Dashboard under **Environment Variables**.

### Backend Service Environment Variables:

| Variable Name | Required | Example / Production Value | Description |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` | **Yes** | `production` | Enforces production startup validation guards. |
| `DEBUG` | **Yes** | `false` | Disables debug mode and suppresses tracebacks. |
| `SECRET_KEY` | **Yes** | `[GENERATED_HEX_64_CHAR_SECRET]` | Cryptographic secret for signing JWTs ($\ge 32$ chars). |
| `DATABASE_URL` | **Yes** | `postgresql+asyncpg://user:pass@host/glucotwin` | Render internal database connection URI. |
| `ALLOWED_ORIGINS` | **Yes** | `["https://glucotwin-frontend.onrender.com"]` | Exact origin of deployed static frontend (JSON array). |
| `ALLOWED_HOSTS` | **Yes** | `["glucotwin-backend.onrender.com"]` | Exact hostname of backend service (JSON array). |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| No | `60` | Lifetime of demo session tokens in minutes. |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity (`INFO`, `WARNING`, `ERROR`). |

#### Secret Key Generation:
Generate a secure 64-character hexadecimal key in your local terminal:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Frontend Service Environment Variables:

| Variable Name | Required | Example / Production Value | Description |
| :--- | :---: | :--- | :--- |
| `VITE_API_BASE_URL` | **Yes** | `https://glucotwin-backend.onrender.com` | Public base URL of the FastAPI backend service. |

---

## 4. Render Blueprint Specification (`render.yaml`)

A blueprint file `render.yaml` enables one-click deployment across all three services.

```yaml
databases:
  - name: glucotwin-db
    databaseName: glucotwin
    user: glucotwin_user
    plan: starter
    postgresMajorVersion: "16"

services:
  # Backend Web Service
  - type: web
    name: glucotwin-backend
    env: python
    region: oregon
    plan: starter
    rootDir: backend
    buildCommand: "pip install --upgrade pip && pip install -r requirements.txt && alembic upgrade head"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"
    healthCheckPath: /health
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: DEBUG
        value: "false"
      - key: LOG_LEVEL
        value: INFO
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: glucotwin-db
          property: connectionString
      - key: ALLOWED_ORIGINS
        value: '["https://glucotwin-frontend.onrender.com"]'
      - key: ALLOWED_HOSTS
        value: '["glucotwin-backend.onrender.com"]'

  # Frontend Static Site
  - type: static
    name: glucotwin-frontend
    env: static
    region: oregon
    rootDir: frontend
    buildCommand: "npm install && npm run build"
    staticPublishPath: dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
    envVars:
      - key: VITE_API_BASE_URL
        value: https://glucotwin-backend.onrender.com
```

---

## 5. Non-Destructive Database Migration Strategy

1. **Alembic in Build Command:**
   During the Render build phase, `alembic upgrade head` runs automatically.
   - Migrations are strictly non-destructive.
   - If a migration fails, the Render build aborts before routing new traffic, preventing database-code version mismatch.
2. **Clean Database Initialization:**
   On a brand-new database instance, Alembic executes `0001_initial_schema.py`, creating all tables, foreign keys, unique constraints, and indices in an ACID transaction.
3. **Rollback Strategy:**
   If a deployment needs to be rolled back:
   ```bash
   # Connect via Render CLI or Shell and downgrade one revision
   alembic downgrade -1
   ```

---

## 6. Post-Deployment Verification & Smoke Tests

After deploying services on Render:
1. **Liveness Check:**
   ```bash
   curl -i "https://glucotwin-backend.onrender.com/health"
   # Expected: HTTP 200 {"status":"healthy"}
   ```
2. **Readiness Probe:**
   ```bash
   curl -i "https://glucotwin-backend.onrender.com/ready"
   # Expected: HTTP 200 with status: ready, database: connected, models: integrity_verified
   ```
3. **Automated Smoke Test Suite:**
   Run the automated smoke test script locally against the live production URLs:
   ```bash
   python scripts/smoke_test.py --backend-url https://glucotwin-backend.onrender.com --frontend-url https://glucotwin-frontend.onrender.com
   ```

---

## 7. Troubleshooting & Common Failure Modes

### Issue 1: Backend Fails Startup with "SECRET_KEY must be at least 32 characters"
- **Cause:** `SECRET_KEY` was not configured or is too short.
- **Remedy:** In Render Dashboard $\to$ `glucotwin-backend` $\to$ Environment, add a 64-character random string to `SECRET_KEY`.

### Issue 2: Frontend API Requests Fail with CORS Error
- **Cause:** `ALLOWED_ORIGINS` does not match the exact URL of the deployed frontend.
- **Remedy:** Verify whether the frontend URL has an extra trailing slash or different protocol. Set `ALLOWED_ORIGINS` to `["https://your-frontend.onrender.com"]`.

### Issue 3: Page Refresh on Frontend Returns 404
- **Cause:** SPA rewrite rule missing.
- **Remedy:** In Render Dashboard $\to$ `glucotwin-frontend` $\to$ Redirects/Rewrites, add `/* -> /index.html` (Rewrite).
