# GlucoTwin AI - Release Security & Privacy Audit Report

**Audit Type:** Application Security, Cryptographic Controls, and Threat Model Audit  
**Classification:** Confidential — System Security Assessment  
**Audit Target:** GlucoTwin AI Backend (`backend/app`), Frontend (`frontend/src`), and Infrastructure (`render.yaml`)  
**Security Status:** PASS — Production Security Controls Fully Verified  

---

## 1. Executive Summary

A comprehensive, defense-in-depth security audit was conducted covering authentication, authorization, token lifecycle, cryptographic validation, browser storage, HTTP transport defenses, API abuse mitigations, formula injection defenses, and secret hygiene.

All security requirements mandated by the platform specification and threat model have been verified through automated regression tests, manual code inspection, and live smoke tests.

---

## 2. Threat Vector Assessment & Mitigations

### 2.1 Synthetic Patient Scope & Zero-PHI Enforcement
- **Posture:** GlucoTwin AI is strictly an in-silico research and education prototype. Real Patient Health Information (PHI) is categorically forbidden.
- **Verification:**
  - Automated synthetic generator creates synthetic IDs prefixed with `SYN-T1D-` or `SYN-T2D-`.
  - Database schema (`patients` table) stores synthetic demographic traits (e.g., `is_synthetic=True`, `synthetic_cohort_seed=42`).
  - All API routes and CSV exports append explicit disclaimers:
    `"RESEARCH & EDUCATION PROTOTYPE ONLY - NOT A MEDICAL DEVICE - STRICTLY SYNTHETIC DATA"`.
  - No database tables or schemas permit storage of real clinical identifiers, Social Security Numbers, or real names.

### 2.2 Token Lifecycle & In-Memory Storage Policy
- **Vulnerability Remediated (DEF-02):**  
  Eliminated persistent `localStorage` token storage in `frontend/src/api.js`.
- **Implementation:**  
  The frontend now stores JWT access tokens strictly in volatile JavaScript heap memory (`this.token`).
- **Residual Risk Analysis:**  
  In-memory tokens are destroyed upon browser tab closure, page refresh, or explicit logout. To preserve clinician workflow usability across navigation, silent re-authentication is performed seamlessly using short-lived demo session credentials when a 401 response is encountered.
- **Cryptographic Rigor:**
  - Standard: Signed JWT using HMAC-SHA256 (`HS256`).
  - Algorithm Agility Defense: `alg: none` and unrecognized algorithms are strictly rejected (`test_alg_none_token_rejected`).
  - Audience & Issuer Validation: Strict claims enforcement (`iss: glucotwin-ai`, `aud: glucotwin-client`). Mismatched claims produce HTTP 401 (`test_wrong_issuer_and_audience_rejected`).
  - Expiry Enforcement: Short default lifespan (15 minutes); expired tokens reject with HTTP 401 (`test_expired_token_rejected`).

### 2.3 Role-Based Access Control (RBAC) & Deny-by-Default
- **Roles:**
  1. `demo_clinician`: Temporary evaluator role; strictly restricted to synthetic cohort exploration, in-memory simulations, and telemetry queries. Cannot modify global settings, run migrations, or access non-synthetic patient records.
  2. `clinician`: Standard authorized investigator role; access to assigned cohorts and telemetry ingestion.
  3. `admin`: Administrative role; access to system audit logs, health metrics, and patient management.
- **Enforcement:**  
  Implemented via FastAPI dependency injection (`require_role(...)` in `app/core/security.py`).
- **Test Evidence:**  
  - `test_unauthenticated_request_denied`: 401 on unauthenticated access.
  - `test_demo_clinician_denied_on_clinician_only_route`: 403 Forbidden.
  - `test_clinician_denied_on_admin_only_route`: 403 Forbidden.
  - `test_admin_allowed_on_all_protected_routes`: 200 OK.

### 2.4 Insecure Direct Object Reference (IDOR) & Sandbox Partitioning
- **Mechanism:**  
  `verify_patient_access_scope()` checks that callers with `demo_clinician` roles cannot access patient IDs outside the synthetic sandbox.
- **Test Evidence:**  
  - `test_demo_clinician_blocked_from_non_synthetic_patient_idor`: Calling `/api/v1/patients/REAL-001/telemetry` with a demo clinician token returns HTTP 403 Forbidden or 404 Not Found.

### 2.5 HTTP Defense-in-Depth & Anti-Caching Headers
- **Middleware:** `SecurityHeadersMiddleware` in `app/core/security_middleware.py`.
- **Headers Enforced on Every Response:**
  - `Content-Security-Policy`: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none';`
  - `X-Content-Type-Options`: `nosniff` (prevents MIME confusion attacks).
  - `X-Frame-Options`: `DENY` (prevents clickjacking attacks).
  - `X-XSS-Protection`: `1; mode=block`.
  - `Referrer-Policy`: `strict-origin-when-cross-origin`.
  - `Permissions-Policy`: `camera=(), microphone=(), geolocation=()`.
  - `Strict-Transport-Security`: `max-age=63072000; includeSubDomains; preload` (enforced when running over TLS/HTTPS).
  - `Cache-Control`: `no-store, no-cache, must-revalidate, private` (enforced on all authenticated patient data, telemetry, and forecasts to prevent intermediate proxy or disk caching).

### 2.6 CSV Telemetry Export Formula Injection Defense (CSV Injection)
- **Vulnerability:**  
  Spreadsheet applications (Excel, LibreOffice, Google Sheets) interpret cells starting with `=`, `+`, `-`, or `@` as executable calculation formulas or external DDE macro triggers.
- **Sanitization:**  
  `sanitize_csv_cell()` prepends a single apostrophe (`'`) to any string starting with `=`, `+`, `-`, `@`, `\t`, or `\r`.
- **Test Evidence:**  
  `test_telemetry_csv_export_and_formula_injection_defense` verified that adversarial payloads like `=cmd|' /C calc'!A0` are serialized safely as `'=cmd|' /C calc'!A0`.

### 2.7 Rate Limiting & Denial-of-Service (DoS) Defenses
- **Rate Limiting:**  
  In-memory sliding window rate limiter (`RateLimitMiddleware`) tracking requests per client IP. Default demo limit: 120 requests/minute. Exceeded threshold responds with HTTP 429 and standard `Retry-After` header.
- **Size Guards:**  
  - `RequestSizeLimitMiddleware` terminates any request payload exceeding 2.0 MB with HTTP 413 Payload Too Large.
  - Header inspection limits total header size to prevent Slowloris buffer exhaustion.

### 2.8 Append-Only Audit Trail
- **Table:** `audit_events`
- **Fields:** `id`, `event_type`, `user_id`, `role`, `action`, `resource_type`, `resource_id`, `ip_address`, `status_code`, `request_id`, `timestamp`.
- **Privacy Assurance:**  
  Audit logging strictly captures metadata (endpoint, status, role, patient code). Payload bodies, passwords, tokens, and raw telemetry arrays are strictly excluded to prevent sensitive data leakage in audit records (`test_audit_log_does_not_leak_payloads`).

### 2.9 Secret Management & Repository Hygiene
- **Git Hygiene Verification:**
  - Scanned repository history and working tree for leaked API keys, tokens, or private credentials.
  - `.env` is explicitly ignored in `.gitignore`.
  - `.env.example` provides documented placeholders with zero secret leakage.
  - Production configuration validator (`app/core/config.py`) refuses to start if `SECRET_KEY` is shorter than 32 characters or uses the default dev key when `ENVIRONMENT=production`.

---

## 3. Clinical Safety Refusal Guardrail (Fail-Closed Architecture)

GlucoTwin AI enforces a zero-tolerance clinical refusal filter on all what-if simulation requests.

- **Refusal Trigger:**  
  Any simulation payload containing `recommend_insulin_dose: true`, `calculate_bolus: true`, or attempting therapeutic dosage optimization is intercepted at the schema validator layer (`SimulationRequest.guard_against_clinical_dosage_requests`).
- **Response Behavior:**  
  Returns HTTP 422 Unprocessable Entity with explicit clinical refusal disclaimer:
  ```json
  {
    "success": false,
    "error": {
      "code": "CLINICAL_SAFETY_REFUSAL",
      "message": "CLINICAL_SAFETY_REFUSAL: GlucoTwin AI is a research and education simulator. The platform strictly refuses to calculate, recommend, or optimize therapeutic insulin dosages."
    }
  }
  ```
- **Test Evidence:**  
  Verified by unit test `test_clinical_safety_refusal_on_insulin_dosage_requests` and live smoke test Check 9.
