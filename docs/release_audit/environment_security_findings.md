# GlucoTwin AI — Environment & Secret Security Audit Findings

**Target Codebase:** GlucoTwin AI Repository  
**Audit Scope:** Environment Variables, Secret Hygiene, Cloud Configuration & Key Management  
**Auditor:** Application Security Lead & DevOps Reviewer  
**Status:** PASS — Zero Committed Secrets; Hardened Fail-Closed Guards Active  

---

## 1. Executive Summary

A comprehensive security scan and static analysis of the GlucoTwin AI codebase was conducted to identify any credential exposures, insecure defaults, improper environment variable handling, or client-side secret leakage.

### Audit Summary Matrix:

| Check Category | Scope Inspected | Result | Risk Rating |
| :--- | :--- | :---: | :---: |
| **Tracked `.env` Files** | Working tree & Git index | **CLEAN** | None |
| **Committed Credentials** | Git history & source tree | **CLEAN** | None |
| **Frontend Secret Leakage** | `frontend/src` & `dist` | **CLEAN** | None |
| **`VITE_*` Namespace Hygiene** | Frontend environment variables | **CLEAN** | None |
| **Insecure Default Key Guards** | `app/core/config.py` | **PROTECTED** | None |
| **CORS Wildcard Prohibitions** | `ALLOWED_ORIGINS` validation | **PROTECTED** | None |
| **Host Header Poisoning Defense** | `ALLOWED_HOSTS` validation | **PROTECTED** | None |
| **Client Session Token Storage** | `frontend/src/api.js` | **PROTECTED** | None |
| **Spreadsheet Formula Injection** | `telemetry.py` CSV exporter | **PROTECTED** | None |

---

## 2. Detailed Findings & Verification Evidence

### 2.1 Git Tracking & File Hygiene
- **Inspection Performed:** Ran `git ls-files .env*` and scanned repository root and subdirectories for hidden credential files (`.env`, `.env.local`, `.env.production`, `*.pem`, `*.key`).
- **Findings:** Only `.env.example` is tracked by Git.
- **Verification Evidence:**
  - `.gitignore` explicitly excludes `.env`, `.env.local`, `.env.*.local`, `*.pem`, `*.key`, and `*.cert`.
  - Zero live credentials, private API keys, or database passwords exist in `.env.example`. All values in `.env.example` are generic development placeholders or localhost addresses.

### 2.2 Frontend Client Secret Isolation (`VITE_*` Namespace)
- **Vulnerability Context:** Modern build tools like Vite automatically embed any environment variable prefixed with `VITE_` into client-side JavaScript bundles, exposing them to anyone viewing the website.
- **Inspection Performed:** Searched all files in `frontend/` for `import.meta.env` and `process.env`.
- **Findings:**
  - Exactly one frontend variable exists: `VITE_API_BASE_URL`.
  - Zero backend secrets, JWT signing keys, or database URIs are defined in the frontend.
  - The compiled distribution bundle (`dist/assets/*.js`) was analyzed; zero sensitive configuration strings are present.

### 2.3 Session Token Storage Policy (Remediation of DEF-02)
- **Prior Condition:** `frontend/src/api.js` previously persisted demo session tokens in browser `localStorage`.
- **Remediation:**  
  All references to `window.localStorage` and `window.sessionStorage` were completely removed. Tokens are held strictly in JavaScript execution memory (`this.token`).
- **Residual Security Benefit:**  
  Tokens are destroyed on tab closure or navigation away, preventing session persistence on shared clinical workstations and eliminating persistence-based XSS token extraction vectors.

### 2.4 Fail-Closed Production Startup Guards
- **Implementation:** [`Settings.validate_production_guards`](file:///c:/Users/rocky/OneDrive/vs%20code%20project/glucotwin/backend/app/core/config.py#L135-L204).
- **Hardened Rules Enforced:**
  1. **Secret Key Strength:** Refuses boot if `SECRET_KEY` is shorter than 32 characters or contains default strings (`replace_with`, `secret`, `password`, `12345`, `change-me`).
  2. **Debug Refusal:** Refuses boot if `DEBUG=true` in production.
  3. **Engine Enforcement:** Refuses boot if `USE_SQLITE_FALLBACK=true` or if `DATABASE_URL` targets SQLite in production.
  4. **CORS Guard:** Refuses boot if wildcard `*` is present in `ALLOWED_ORIGINS`.
  5. **Host Header Guard:** Refuses boot if wildcard `*` is present in `ALLOWED_HOSTS`.
  6. **Research Invariant Guard:** Refuses boot if `RESEARCH_MODE_ONLY`, `ALLOW_SYNTHETIC_DATA_ONLY`, or `ENABLE_RECOMMENDATION_BLOCKER` are disabled.
- **Test Evidence:** All 9 guard permutations verified via automated unit tests in `test_config_guards.py`.

### 2.5 PostgreSQL Connection Normalization
- **Issue Identified:** Render PostgreSQL instances export connection URIs prefixed with `postgresql://` or `postgres://`. However, SQLAlchemy's `AsyncEngine` requires the explicit `postgresql+asyncpg://` driver scheme.
- **Remediation Implemented:** Added `normalize_database_url` field validator in `Settings`:
  ```python
  @field_validator("DATABASE_URL", mode="before")
  @classmethod
  def normalize_database_url(cls, value: object) -> str:
      if isinstance(value, str):
          val = value.strip()
          if val.startswith("postgres://"):
              return val.replace("postgres://", "postgresql+asyncpg://", 1)
          if val.startswith("postgresql://") and not val.startswith("postgresql+asyncpg://"):
              return val.replace("postgresql://", "postgresql+asyncpg://", 1)
          return val
      return str(value)
  ```
- **Test Evidence:** Verified by unit test `test_render_database_url_auto_normalization`.

---

## 3. Operational Security Recommendations for Deployment

When configuring the application on Render, the system operator must follow these rules:

1. **Never Reuse Keys:** Do not reuse `SECRET_KEY` across different staging and production environments.
2. **Use Internal Database URLs:** Always configure the backend web service with Render's internal PostgreSQL database URL. This keeps database traffic entirely within Render's private virtual network, reducing latency and preventing exposure to the public internet.
3. **Restrict CORS to Single Origin:** In `glucotwin-backend`, set `ALLOWED_ORIGINS` strictly to the deployed HTTPS frontend domain (e.g. `https://glucotwin-frontend.onrender.com`).
4. **Enforce HTTPS:** Ensure **Force HTTPS** is enabled on both the Render Static Site and Web Service settings.
