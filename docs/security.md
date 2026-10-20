# GlucoTwin AI - Security Architecture & Implementation Specification

**Document Version:** 1.0.0  
**Status:** Approved Security Specification  
**Classification:** Prototype Architecture Baseline  
**Scope:** Authentication Primitives, Authorization Matrix, IDOR Protections, Ingestion Security, Middleware Controls, and Secret Management  

---

## 1. Security Philosophy & Architectural Tenets

GlucoTwin AI implements a **defense-in-depth, fail-closed security architecture**. Even though this application is an academic in-silico prototype operating exclusively on synthetic data, it adheres to modern biomedical software security standards:

1. **Deny-by-Default:** Every API route is unauthenticated/unauthorized unless explicitly exempted or verified via strict dependency guards.
2. **Fail-Closed Operations:** If cryptographic signatures fail, tokens expire, request payloads exceed bounds, or telemetry inputs violate physiological plausibility, the system rejects or abstains immediately.
3. **Zero-Trust Patient Boundaries (Anti-IDOR):** Possession of a valid user session does not confer carte blanche access to patient records. Object-level access control explicitly validates role-to-resource ownership.
4. **Anti-Caching of Health Telemetry:** All patient profiles, telemetry streams, and forecast outputs are tagged with `Cache-Control: no-store, no-cache, must-revalidate` to prevent intermediary proxy caching.
5. **No PHI & Payload Redaction:** Audit trails log transactional metadata and user actions, but deliberately redact raw glucose telemetry arrays and clinical observation payloads to prevent log poisoning or compliance leakage.

---

## 2. Authentication Primitives: Short-Lived JWT Demo Sessions

### 2.1 Cryptographic Token Specification
Session tokens are generated using JSON Web Tokens (RFC 7519) signed via HMAC-SHA256 (`HS256`):
- **Secret Key:** Minimum 32 characters (256 bits). In production, missing or default secret keys trigger an immediate fatal startup abort.
- **Expiration:** Default `60 minutes` (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Standard Claims Enforced:**
  - `sub`: User UUID or demo session identifier.
  - `role`: User role (`demo_clinician`, `clinician`, `admin`).
  - `iss`: Enforced issuer (`settings.JWT_ISSUER`, default `"glucotwin-auth"`).
  - `aud`: Enforced audience (`settings.JWT_AUDIENCE`, default `"glucotwin-api"`).
  - `exp`: Explicit UTC expiration timestamp.
  - `jti`: Unique UUID4 token identifier tracked for explicit revocation.

### 2.2 Replay & Revocation Safeguards
- **Logout Endpoint (`POST /api/v1/auth/logout`):** Revokes active sessions by adding the token's `jti` to an in-memory or persisted token blocklist until token expiration.
- **Algorithm Enforcement:** The token verification engine explicitly rejects `none` algorithm tokens and validates that the header algorithm matches `HS256`.

---

## 3. Role-Based Access Control (RBAC) Matrix

The system implements three discrete user roles managed by FastAPI dependency injection:

| Endpoint Route | Method | `demo_clinician` | `clinician` | `admin` | Enforcement Mechanism |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/health` & `/ready` | `GET` | ✅ Public | ✅ Public | ✅ Public | Unauthenticated probe |
| `/api/v1/auth/demo-session` | `POST` | ✅ Public | ✅ Public | ✅ Public | Anonymous demo token issuance |
| `/api/v1/auth/logout` | `POST` | ✅ Allowed | ✅ Allowed | ✅ Allowed | `get_current_user` |
| `/api/v1/patients/` | `GET` | ✅ Synthetic only | ✅ Full | ✅ Full | `get_current_user` + IDOR scope |
| `/api/v1/patients/{id}` | `GET` | ✅ Synthetic only | ✅ Full | ✅ Full | `get_current_user` + IDOR check |
| `/api/v1/observations/ingest` | `POST` | ⚠️ Sandboxed only | ✅ Full | ✅ Full | Role verification & scope guard |
| `/api/v1/telemetry/{id}` | `GET` | ✅ Synthetic only | ✅ Full | ✅ Full | `get_current_user` + IDOR check |
| `/api/v1/metrics/agp/{id}` | `GET` | ✅ Synthetic only | ✅ Full | ✅ Full | `get_current_user` + IDOR check |
| `/api/v1/forecast/run` | `POST` | ✅ Synthetic only | ✅ Full | ✅ Full | `get_current_user` + IDOR check |
| `/api/v1/simulation/what-if` | `POST` | ✅ Synthetic only | ✅ Full | ✅ Full | `get_current_user` + IDOR check |
| `/api/v1/protected/clinician-only` | `GET` | ❌ 403 Forbidden | ✅ Allowed | ✅ Allowed | `RequireRole(["clinician", "admin"])` |
| `/api/v1/protected/admin-only` | `GET` | ❌ 403 Forbidden | ❌ 403 Forbidden | ✅ Allowed | `RequireRole(["admin"])` |

---

## 4. Insecure Direct Object Reference (IDOR) & Patient Scoping

GlucoTwin AI prevents IDOR attacks through rigorous object-level permission verification:

```python
# Simplified Architectural Pattern (backend/app/api/v1/patients.py)
async def get_patient_with_scope(patient_id: str, current_user: User, db: AsyncSession):
    patient = await db.get(SyntheticPatient, patient_id)
    if not patient:
        raise NotFoundException(f"Patient {patient_id} not found.")
    
    # IDOR Check: Demo clinicians are strictly confined to synthetic patients
    if current_user.role == "demo_clinician" and not patient.is_synthetic:
        raise ForbiddenException("Demo sessions are strictly restricted to synthetic patient records.")
        
    return patient
```

Any attempt by a `demo_clinician` to access or execute simulations against non-synthetic records yields an immediate `403 Forbidden` response and triggers a security audit event.

---

## 5. Network Middleware & Defensive Headers

### 5.1 Security Headers Middleware
Every HTTP response dispatched by FastAPI includes defensive headers:
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://api.render.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none';`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (enforced in production)
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()`

### 5.2 Exact-Origin Cross-Origin Resource Sharing (CORS)
- Wildcard CORS (`*`) is strictly forbidden in production.
- Only exact origins explicitly configured in `ALLOWED_ORIGINS` (e.g., `["https://glucotwin-frontend.onrender.com", "http://localhost:5173"]`) are permitted.

### 5.3 Request and Header Boundary Limits
- `RequestSizeLimitMiddleware`: Rejects request bodies exceeding `MAX_REQUEST_SIZE_BYTES` (`10 MB`) with `413 Payload Too Large`.
- Rejects HTTP header sets exceeding `MAX_HEADER_SIZE_BYTES` (`16 KB`) with `431 Request Header Fields Too Large`.

### 5.4 Rate Limiting & Abuse Prevention
- Implements an IP-based and user-based sliding window rate limiter:
  - Standard API endpoints: `60 requests / minute`.
  - Heavy ODE simulation and forecasting: `20 requests / minute`.
- Violations return `429 Too Many Requests` accompanied by standard `Retry-After: 60` headers.

---

## 6. Audit Logging & Payload Redaction

All security-critical actions are recorded to the append-only `audit_logs` database table via `AuditService`:
- **Captured Events:** `DEMO_SESSION_CREATED`, `LOGOUT`, `PATIENT_ACCESS`, `OBSERVATIONS_INGESTED`, `FORECAST_EXECUTED`, `SIMULATION_EXECUTED`, `AUTHORIZATION_DENIED`, `CLINICAL_SAFETY_REFUSAL`.
- **Payload Redaction:** Raw blood glucose values, meal logs, and telemetry time-series are stripped prior to serialization. Only metadata (record count, timestamp range, patient code, and user ID) is persisted.

---

## 7. Model Artifact Integrity & Checksums

To prevent model poisoning or unauthorized parameter tampering:
- All pre-calibrated baseline parameter sets and ARX coefficients are fingerprinted using SHA-256 checksums.
- During service startup and readiness checks (`GET /ready`), checksums are recalculated and verified against expected signatures.
- If a model file is modified or corrupted, the readiness probe fails (`ready: false`), preventing traffic routing to the unhealthy instance.
