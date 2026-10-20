# GlucoTwin AI — Render Environment Variables & Deployment Configuration Guide

**Application:** GlucoTwin AI (Academic Digital Twin & In-Silico Metabolic Simulator)  
**Target Infrastructure:** Render Cloud Platform  
**Hosting Topology:** Render Static Site (Frontend: Vite 8.3 / Vanilla CSS) + Render Web Service (Backend: Python 3.12 / FastAPI 0.115 / Uvicorn) + Render PostgreSQL 16  
**Auditor:** Senior DevOps & Application Security Reviewer  
**Classification:** Production Deployment Runbook  

---

## 1. Executive Summary & Architecture Overview

GlucoTwin AI is partitioned into two decoupled cloud services and a managed database:
1. **Frontend (`glucotwin-frontend`):** Render Static Site serving a pre-compiled Single-Page Application (SPA) built via Vite. All `VITE_*` environment variables are baked into static HTML/JS bundles at build time.
2. **Backend (`glucotwin-backend`):** Render Python Web Service executing asynchronous FastAPI endpoints under Uvicorn with Alembic database schema migrations.
3. **Database (`glucotwin-db`):** Render Managed PostgreSQL 16 instance running async I/O via SQLAlchemy 2.0 and `asyncpg`.

> [!IMPORTANT]
> **No Paid AI APIs or External LLMs:**  
> GlucoTwin AI does **NOT** use or require OpenAI, Anthropic, Gemini, or any paid AI credentials. All digital-twin predictions and what-if counterfactual simulations are executed locally in-process using deterministic Bergman Minimal Model ODE numerical integration (SciPy `solve_ivp` RK45) and discrete linear ARX-Kalman filters (NumPy).

---

## 2. Complete Environment Variable Inventory

The following table documents every environment variable supported, validated, or inspected by GlucoTwin AI.

| Exact Variable Name | Service | Status | Purpose | Evidence Source File | Classification | Expected Format | Generation / Source | Render Service Assignment | Redeploy / Rebuild Required | Development / Test Default | Production Configuration Requirements |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- | :--- | :--- | :---: | :--- | :--- |
| **`ENVIRONMENT`** | Backend | **Required** | Sets operational environment and triggers strict startup guards | `backend/app/core/config.py:26,135` | Non-Secret | `production` / `development` / `testing` | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `development` | Must be strictly set to `production`. Triggers fail-closed security validators. |
| **`DEBUG`** | Backend | **Required** | Enables or disables debug diagnostics | `backend/app/core/config.py:27,160` | Non-Secret | `false` or `true` | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `false` | Must be strictly `false`. Startup aborts if set to `true` when `ENVIRONMENT=production`. |
| **`SECRET_KEY`** | Backend | **Required** | Cryptographic key for HMAC-SHA256 JWT session token signing | `backend/app/core/config.py:36,140` | **Secret** | 64-character hexadecimal string ($\ge 32$ chars) | Generated locally via `secrets.token_hex(32)` or Render auto-generation | `glucotwin-backend` | Redeploy | Insecure default string (dev only) | Must be $\ge 32$ characters. Startup rejects default placeholders (`replace_with`, `secret`, `password`, `change-me`). |
| **`DATABASE_URL`** | Backend | **Required** | Asynchronous connection URI for PostgreSQL | `backend/app/core/config.py:44,98,165` | **Secret** | `postgresql+asyncpg://user:pass@host:5432/db` (or Render `postgresql://`) | Render managed DB connection string | `glucotwin-backend` | Redeploy | `postgresql+asyncpg://glucotwin_user:...` | Must target PostgreSQL. Automatic normalizer upgrades Render's `postgresql://` to `postgresql+asyncpg://`. SQLite is strictly prohibited in production. |
| **`USE_SQLITE_FALLBACK`** | Backend | **Required** | Flags whether SQLite fallback is permitted | `backend/app/core/config.py:52,166` | Non-Secret | `false` or `true` | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `true` | Must be strictly `false` in production. Backend refuses boot if SQLite fallback is enabled in production. |
| **`ALLOWED_ORIGINS`** | Backend | **Required** | Allowed origins for exact-origin CORS filtering | `backend/app/core/config.py:58,109,181` | Non-Secret | Comma-separated URLs or JSON array | Deployed frontend static site URL | `glucotwin-backend` | Redeploy | `http://localhost:5173,http://127.0.0.1:5173` | Must contain exact deployed HTTPS frontend origin (e.g. `https://glucotwin-frontend.onrender.com`). Wildcards (`*`) are rejected. |
| **`ALLOWED_HOSTS`** | Backend | **Required** | Trusted domain names for HTTP Host header validation | `backend/app/core/config.py:61,98,185` | Non-Secret | Comma-separated domain names | Deployed backend domain name | `glucotwin-backend` | Redeploy | `localhost,127.0.0.1,testserver` | Must match backend domain (e.g. `glucotwin-backend.onrender.com`). Wildcards (`*`) are rejected. |
| **`VITE_API_BASE_URL`** | Frontend | **Required** | Base URL of the backend API for client-side AJAX | `frontend/src/api.js:8-16` | Non-Secret | `https://<backend-service>.onrender.com` | Deployed backend service URL | `glucotwin-frontend` | **Rebuild Required** | Defaults to `/api/v1` (for dev proxy) | Public build-time variable. Embedded into JavaScript bundle. Must point to backend HTTPS domain. |
| **`PORT`** | Backend | Automatic | Port on which the ASGI web server listens | `backend/app/core/config.py:33` | Non-Secret | Integer (e.g. `10000`) | Automatically injected by Render runtime | `glucotwin-backend` | Redeploy | `8000` | Injected dynamically by Render. Used in start command `$PORT`. |
| **`LOG_LEVEL`** | Backend | Optional | Logging verbosity level | `backend/app/core/config.py:28` | Non-Secret | `INFO`, `WARNING`, `ERROR`, `DEBUG` | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `INFO` | `INFO` recommended for production. Emits structured JSON audit lines. |
| **`ACCESS_TOKEN_EXPIRE_MINUTES`** | Backend | Optional | Lifespan of demo session JWT access tokens | `backend/app/core/config.py:41` | Non-Secret | Integer (e.g. `60`) | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `60` | Recommended default 60 minutes for clinician evaluation sessions. |
| **`JWT_ISSUER`** | Backend | Optional | RFC 7519 `iss` claim checked in JWT verification | `backend/app/core/config.py:66` | Non-Secret | String | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `glucotwin-ai` | Enforced during token decoding. Default is optimal. |
| **`JWT_AUDIENCE`** | Backend | Optional | RFC 7519 `aud` claim checked in JWT verification | `backend/app/core/config.py:67` | Non-Secret | String | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `glucotwin-client` | Enforced during token decoding. Default is optimal. |
| **`RATE_LIMIT_DEFAULT_PER_MINUTE`** | Backend | Optional | Per-IP rate limiting ceiling | `backend/app/core/config.py:74` | Non-Secret | Integer (e.g. `120`) | Set manually in Render Dashboard | `glucotwin-backend` | Redeploy | `60` | Prevents API flooding. Returns HTTP 429 when exceeded. |
| **`RESEARCH_MODE_ONLY`** | Backend | Locked | Safety invariant: ensures non-clinical mode | `backend/app/core/config.py:80,191` | Non-Secret | `true` | Fixed in source code | `glucotwin-backend` | Redeploy | `true` | Must remain `true`. Backend refuses startup if set to `false`. |
| **`ALLOW_SYNTHETIC_DATA_ONLY`** | Backend | Locked | Safety invariant: prohibits ingestion of real PHI | `backend/app/core/config.py:81,195` | Non-Secret | `true` | Fixed in source code | `glucotwin-backend` | Redeploy | `true` | Must remain `true`. Backend refuses startup if set to `false`. |
| **`ENABLE_RECOMMENDATION_BLOCKER`** | Backend | Locked | Safety invariant: blocks therapeutic insulin dosing | `backend/app/core/config.py:83,199` | Non-Secret | `true` | Fixed in source code | `glucotwin-backend` | Redeploy | `true` | Must remain `true`. Refuses boot if disabled. |

---

## 3. Secret Generation & Storage Instructions

### 3.1 Cryptographic Signing Key (`SECRET_KEY`)
- **Algorithm:** HMAC-SHA256 (`HS256`).
- **Length Requirement:** Minimum 32 characters; 64 hex characters (256 bits of entropy) recommended.
- **Generation Command:** Run the following command in a local terminal:
  ```powershell
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- **Rules:**  
  - Never commit this value to Git.
  - Never paste this value into `.env.example`, documentation, or bug reports.
  - Render provides a `generateValue: true` feature in `render.yaml` which creates a cryptographically secure random string automatically.

### 3.2 Database Connection String (`DATABASE_URL`)
- **Managed Service:** Render PostgreSQL 16.
- **Internal vs. External Connection:**
  - **Internal Connection String (Recommended):** `postgresql://glucotwin_user:<PASSWORD>@dpg-<ID>-a/glucotwin` (Fast, zero data egress fees, secure inside Render's private network).
  - **External Connection String:** Used only if running migrations from a local developer machine outside of Render.
- **Driver Auto-Normalization:**  
  Render supplies connection strings starting with `postgresql://` or `postgres://`. GlucoTwin AI's `Settings.normalize_database_url` validator automatically converts this to `postgresql+asyncpg://` to satisfy the asynchronous SQLAlchemy 2.0 engine.

---

## 4. Frontend Configuration & API URL Safety

### 4.1 Build-Time Embedding Mechanics
In Vite-powered client applications, environment variables prefixed with `VITE_` are:
1. Read **only during `npm run build`**.
2. Statically replaced as string literals into the compiled JavaScript bundle (`dist/assets/*.js`).
3. **Publicly visible** to any user inspecting the browser Network tab or JavaScript sources.

> [!WARNING]
> **Zero Secrets in Frontend:**  
> Never define `SECRET_KEY`, database credentials, or private tokens with a `VITE_` prefix. `VITE_API_BASE_URL` is the **only** variable the frontend requires.

### 4.2 API Base URL & Prefix Resolution
The API client ([`frontend/src/api.js`](file:///c:/Users/rocky/OneDrive/vs%20code%20project/glucotwin/frontend/src/api.js#L8-L16)) uses the following resolution logic:
```javascript
const getApiBase = () => {
  const envUrl = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL;
  if (envUrl) {
    const cleanUrl = String(envUrl).trim().replace(/\/$/, '');
    if (cleanUrl.endsWith('/api/v1')) {
      return cleanUrl;
    }
    return `${cleanUrl}/api/v1`;
  }
  return '/api/v1';
};
```
- **Trailing Slashes:** Automatically stripped.
- **Path Suffix:** If the user supplies `https://glucotwin-backend.onrender.com`, `/api/v1` is automatically appended. If the user supplies `https://glucotwin-backend.onrender.com/api/v1`, it is preserved without duplicate nesting.
- **Rebuild Requirement:** Whenever `VITE_API_BASE_URL` is changed in Render, the static site **must be rebuilt** (`Manual Deploy` -> `Clear build cache & deploy`).

---

## 5. Backend CORS & Host Validation Setup

### 5.1 Exact-Origin CORS (`ALLOWED_ORIGINS`)
- In production, cross-origin requests carrying JWT Bearer authorization require exact origin matching.
- **Render Value:** `https://<YOUR-FRONTEND-STATIC-SITE>.onrender.com` (or comma-separated if supporting multiple custom domains).
- **Prohibited:** `*` (wildcards) are rejected at startup by `validate_production_guards`.

### 5.2 Host Header Validation (`ALLOWED_HOSTS`)
- Protects against HTTP Host Header Poisoning and DNS rebinding attacks.
- **Render Value:** `<YOUR-BACKEND-SERVICE>.onrender.com` (do not include `https://` protocol scheme or port).
- **Prohibited:** `*` (wildcards) are rejected at startup by `validate_production_guards`.

---

## 6. Copy-Ready Render Configuration

### Section A: Render Backend Web Service (`glucotwin-backend`)

| Setting Field | Recommended Production Value |
| :--- | :--- |
| **Service Type** | Web Service |
| **Name** | `glucotwin-backend` |
| **Region** | Oregon (USA) or Ohio (USA) — match PostgreSQL region |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt && alembic upgrade head` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2` |
| **Health Check Path** | `/health` |
| **Auto-Deploy** | Yes |

#### Environment Variables to Add in Render Dashboard:
```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=<GENERATE_VIA_SECRETS_TOKEN_HEX_32>
DATABASE_URL=<LINK_RENDER_POSTGRESQL_INTERNAL_CONNECTION_STRING>
USE_SQLITE_FALLBACK=false
ALLOWED_ORIGINS=https://<YOUR-FRONTEND-SERVICE>.onrender.com
ALLOWED_HOSTS=<YOUR-BACKEND-SERVICE>.onrender.com
ACCESS_TOKEN_EXPIRE_MINUTES=60
RATE_LIMIT_DEFAULT_PER_MINUTE=120
```

---

### Section B: Render Frontend Static Site (`glucotwin-frontend`)

| Setting Field | Recommended Production Value |
| :--- | :--- |
| **Service Type** | Static Site |
| **Name** | `glucotwin-frontend` |
| **Region** | Oregon (USA) |
| **Branch** | `main` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm install && npm run build` |
| **Publish Directory** | `dist` |
| **Auto-Deploy** | Yes |

#### Rewrite / Routing Rules (SPA Catch-All):
| Route Type | Source | Destination |
| :--- | :--- | :--- |
| **Rewrite** | `/*` | `/index.html` |

#### Environment Variables to Add in Render Dashboard:
```env
VITE_API_BASE_URL=https://<YOUR-BACKEND-SERVICE>.onrender.com
```

---

## 7. Migration & Pre-Deploy Procedures

Schema migrations are managed by Alembic.

### 7.1 Automated Build-Step Migrations (Recommended)
By including `alembic upgrade head` in the backend build command:
```bash
pip install --upgrade pip && pip install -r requirements.txt && alembic upgrade head
```
Render automatically executes pending database migrations against the provisioned PostgreSQL instance before launching the new Uvicorn server processes. If migration fails, the deployment is aborted cleanly without affecting the running container.

### 7.2 Migration Readiness Probe
To verify database connectivity and migration head status after deployment:
```bash
curl -s https://<YOUR-BACKEND-SERVICE>.onrender.com/ready
```
Expected JSON response:
```json
{
  "status": "ready",
  "database": true,
  "database_type": "PostgreSQL",
  "model_integrity": "intact",
  "migration_head": "0001_initial_schema"
}
```
