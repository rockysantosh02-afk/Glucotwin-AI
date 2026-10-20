# GlucoTwin AI - Security & Clinical Safety Threat Model

**Document Version:** 1.1.0  
**Status:** Approved Architectural Threat Model (Updated Against Final Implementation)  
**Methodology:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) + Clinical Misuse & Physiological Hazard Analysis  

---

## 1. System Scope & Trust Boundaries

GlucoTwin AI processes synthetic metabolic data to simulate glucose dynamics and state-space digital twins. Although designed strictly as an academic research and education prototype, medical simulation software carries severe potential hazards if compromised, altered, or clinically misused.

```
       [ External Untrusted Internet / Client Browser ]
                             │
                             ▼  [ Trust Boundary 1: TLS 1.3 / Exact-Origin CORS / Rate Limiting / Size Limits ]
                ┌───────────────────────────┐
                │   FastAPI Gateway Router  │
                │  - TrustedHostMiddleware  │
                │  - SecurityHeaders (CSP)  │
                │  - RequestIDMiddleware    │
                │  - Rate Limiter (429)     │
                └─────────────┬─────────────┘
                             │
                             ▼  [ Trust Boundary 2: JWT Demo Session Auth & Strict RBAC ]
                ┌───────────────────────────┐
                │ Central Auth & IDOR Guard │
                │  - HS256 Token Signature  │
                │  - JTI Revocation List    │
                │  - Patient Scope Validator│
                └─────────────┬─────────────┘
                             │
                             ▼  [ Trust Boundary 3: Domain Services & Model Execution ]
                ┌───────────────────────────┐
                │  Domain Services Layer    │
                │  - Observation Ingestion  │
                │  - ARX-Kalman Estimator   │
                │  - Bergman ODE Simulator  │
                │  - Fail-Closed Abstention │
                └─────────────┬─────────────┘
                             │
                             ▼  [ Trust Boundary 4: Clinical Safety Guardrail Filter ]
                ┌───────────────────────────┐
                │ Refusal & Redaction Guard │
                │  - Therapeutic Refusal    │
                │  - Anti-Caching Headers   │
                │  - Audit Log Redaction    │
                └─────────────┬─────────────┘
                             │
                             ▼  [ Trust Boundary 5: Persistence Boundary ]
                ┌───────────────────────────┐
                │   Database Engine         │
                │  - PostgreSQL / SQLite    │
                │  - Parameterized ORM      │
                │  - Unique & Check Bounds  │
                └───────────────────────────┘
```

---

## 2. Implemented STRIDE Threat Analysis & Concrete Controls

| Threat Category | Specific Attack Vector | Implemented Defense Mechanism in Code | Residual Risk | Risk Level |
| :--- | :--- | :--- | :--- | :---: |
| **Spoofing (S)** | - Token forgery or modification<br>- Algorithm substitution (`alg: "none"`)<br>- Replay of expired sessions | - HMAC-SHA256 tokens signed with $\ge 256$-bit secret (`backend/app/core/security.py`).<br>- Explicit rejection of `none` algorithm.<br>- Strict claim validation (`iss`, `aud`, `exp`).<br>- `jti` revocation blocklist on logout (`POST /api/v1/auth/logout`). | Stolen token from compromised client device during 60-min window. | **Low** |
| **Tampering (T)** | - Malicious parameter tampering in REST payload<br>- Modifying model weight files on disk<br>- Concurrent duplicate sensor injection | - Strict Pydantic v2 schemas validating physiological bounds ($[40, 500] \text{ mg/dL}$).<br>- Model artifact SHA-256 checksums verified at startup and in `/ready` probe.<br>- Database unique constraint `(patient_id, timestamp)` with transaction rollback and item-by-item salvage (`backend/app/api/v1/observations.py`). | Host-level compromise of file system (requires server breach). | **Low** |
| **Repudiation (R)** | - User denies initiating simulation or data ingestion<br>- Audit record falsification | - Append-only `audit_logs` database table capturing UTC timestamp, user ID, client IP, action, resource, and execution status (`backend/app/services/audit.py`).<br>- Write-only access from application service; no user update endpoints exist. | DBA direct database access (requires separation of database administrator roles). | **Low** |
| **Information Disclosure (I)** | - Telemetry leak via HTTP caching<br>- Stack trace leakage on errors<br>- PHI leakage into audit logs<br>- Cross-patient data exposure (IDOR) | - `Cache-Control: no-store, no-cache, must-revalidate` on all authenticated patient endpoints.<br>- Sanitized standard error envelope (`error.code`, `error.message`, `error.request_id`); stack traces suppressed in production.<br>- Clinical telemetry payloads automatically redacted in audit logging.<br>- Strict IDOR check: `demo_clinician` blocked from non-synthetic patient IDs (`403 Forbidden`). | Side-channel timing attacks on JWT HMAC verification (mitigated by constant-time comparison). | **Low** |
| **Denial of Service (D)** | - Huge payload upload<br>- Infinite ODE integration time ($dt \to 0$ or duration $\to \infty$)<br>- High-frequency API hammering | - `RequestSizeLimitMiddleware` ($10 \text{ MB}$ body limit, $16 \text{ KB}$ header limit).<br>- Hard mathematical bounds on ODE: duration $[60, 1440] \text{ min}$, internal step size clamped, max evaluated points bounded.<br>- Sliding-window rate limiter: $60 \text{ req/min}$ general, $20 \text{ req/min}$ for simulations. Returns `429` with `Retry-After`. | Distributed volumetric DDoS at network layer (requires Cloudflare/Render edge protection). | **Medium** |
| **Elevation of Privilege (E)** | - `demo_clinician` executing admin routes<br>- Normal user invoking database migrations | - Centralized declarative role dependencies (`RequireRole(["clinician", "admin"])`).<br>- Fail-closed RBAC: unauthenticated returns `401`, insufficient role returns `403`.<br>- Migration commands restricted to CLI tooling (`alembic`). | Privilege escalation in underlying database server or hosting infrastructure. | **Low** |

---

## 3. Clinical & Physiological Misuse Threat Analysis

Because glucose digital twins simulate human metabolism, the primary existential threat is **human clinical misuse**:

### Hazard CM-1: Unauthorized Treatment / Insulin Dosing Extrapolation
- **Scenario:** A patient or caregiver inputs real-world glucose telemetry and meals into the simulator and uses the predicted curve to administer an insulin bolus or change pump basal rates.
- **Clinical Consequence:** Severe iatrogenic hypoglycemia, seizure, neuroglycopenia, or death.
- **Implemented Technical Safeguards:**
  1. **Strict Algorithmic Prohibition:** The software contains zero algorithms, formulas, or heuristics for insulin bolus calculation, correction dose calculation, or basal rate adjustment.
  2. **Clinical Safety Refusal Interceptor:** Every simulation and forecast request is inspected by `RefusalFilter`. Any query attempting to solicit dosing advice (e.g. `how many units`, `recommend bolus`, `prescribe dose`) is immediately rejected with HTTP 422 `CLINICAL_SAFETY_REFUSAL` and logged to security audit logs.
  3. **Visual Disclaimers & UI Banners:** Persistent, unclosable banners explicitly state: *"IN-SILICO RESEARCH PROTOTYPE ONLY. NOT FOR CLINICAL USE. NEVER USE FOR INSULIN DOSING."*
  4. **Synthetic Data Restriction:** Demographics and telemetry streams are tagged as synthetic; real patient PHI is strictly disallowed.

### Hazard CM-2: Silent Failure Under Acute Metabolic Disturbance
- **Scenario:** Rapid glycemic crash, ketoacidosis, or extreme sensor failure causes the linear ARX model or discrete Kalman filter to diverge, outputting deceptive predictions.
- **Implemented Technical Safeguards:**
  1. **Fail-Closed Abstention Boundaries:**
     - `DATA_TOO_STALE`: Rejects forecasting if latest reading $> 15 \text{ minutes}$ old (100.0% measured abstention rate).
     - `INSUFFICIENT_HISTORY`: Rejects if context $< 60 \text{ minutes}$ ($< 12$ readings).
     - `SENSOR_GAP_EXCEEDED`: Rejects if unrecorded sensor gap $> 15 \text{ minutes}$.
     - `PHYSIOLOGICAL_ANOMALY`: Rejects if reading falls outside $[40.0, 500.0] \text{ mg/dL}$.
  2. **Analytical Uncertainty Bounds:** Every prediction outputs explicit 95% confidence intervals ($\pm 1.96 \sigma$).
  3. **Physiological Validity Clamping:** All predictions are hard-clamped to $[40.0, 500.0] \text{ mg/dL}$ (0.00% out-of-bounds rate).

---

## 4. Production Deployment Hardening & Startup Guards

To prevent accidental deployment in an insecure state, the application executes **fail-closed configuration guards** during startup (`backend/app/core/config.py`):
1. **Refusal on Insecure Secret:** Refuses to boot if `SECRET_KEY` is `< 32 characters` or matches default insecure keys.
2. **Refusal on Debug Mode in Production:** Refuses to boot if `ENVIRONMENT=production` and `DEBUG=True`.
3. **Refusal on SQLite in Production:** Refuses to boot if `ENVIRONMENT=production` and `DATABASE_URL` specifies SQLite.
4. **Refusal on Wildcard CORS in Production:** Refuses to boot if `ALLOWED_ORIGINS` contains `*`.
5. **Refusal on Wildcard Hosts in Production:** Refuses to boot if `ALLOWED_HOSTS` contains `*`.

---

## 5. Residual Risks & Documented Mitigations

| Residual Risk | Description | Mitigating Factor |
| :--- | :--- | :--- |
| **In-Silico Simplification Gap** | 3-compartment ODE and linear ARX cannot model unmeasured hormonal surges (cortisol, adrenaline, glucagon) or gastroparesis. | Prominently documented in `docs/risk_and_limitations.md`; clear academic research scope. |
| **Physiological Interstitial Lag** | CGM measures subcutaneous fluid which lags capillary blood by 5–15 minutes. | Disclosed on all trajectory views; Kalman state filter accounts for measurement noise. |
| **Sensor Artifact Susceptibility** | Sensor compression ("compression low") mimics true hypoglycemia without multi-sensor accelerometer cross-validation. | Documented limitation; UI displays uncertainty bands; users instructed to verify with capillary fingerstick. |
| **Client-Side Code Modification** | Malicious actor downloading open-source frontend could remove UI disclaimer banners. | Server-side refusal filter, model abstention, and API-level guardrails operate independently of frontend client. |
