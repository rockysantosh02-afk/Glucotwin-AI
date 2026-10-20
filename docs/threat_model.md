# GlucoTwin AI - Security & Clinical Safety Threat Model

**Document Version:** 1.0.0  
**Status:** Approved Security Contract  
**Methodology:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) + Clinical Misuse Analysis  

---

## 1. System Scope & Trust Boundaries

GlucoTwin AI processes synthetic metabolic data to simulate glucose dynamics. Although designed as an academic and educational prototype, medical decision-support systems carry severe potential risks if misused or compromised.

### Defined Trust Boundaries:
- **Trust Boundary 1 (Client <-> API Gateway):** External internet / untrusted browser boundary. Must enforce TLS 1.3, strict CORS, request size bounds, rate limiting, and JWT authentication.
- **Trust Boundary 2 (API Gateway <-> Core Simulation Engine):** Internal trust boundary. Enforces Pydantic v2 input schema validation, parameter bounding, and deterministic ODE step restrictions.
- **Trust Boundary 3 (Core Service <-> Persistence Layer):** Database boundary. Uses parameterized queries via SQLAlchemy 2.0 to eliminate SQL injection.
- **Trust Boundary 4 (Simulation Output <-> Client Output):** Clinical Safety Boundary. Mandatory output filtering intercepting any generated content that resembles insulin dosing, medical advice, or treatment adjustments.

---

## 2. STRIDE Threat Analysis Matrix

| Threat Category | Threat Description | Attack Vector / Scenario | Impact | Severity | Likelihood | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Spoofing (S)** | Attacker impersonates a legitimate researcher or administrator. | Stolen JWT, weak credentials, or token replay. | Unauthorized simulation runs or data injection. | **High** | Medium | Secure HTTP-only cookies or Bearer tokens with 60-min expiration; bcrypt password hashing ($>12$ rounds); TLS encryption. |
| **Tampering (T)** | Attacker alters synthetic patient baseline parameters or telemetry. | Parameter tampering in transit or unauthorized REST call. | Corrupted twin forecasts, deceptive simulation outcomes. | **High** | Low | Pydantic v2 fail-closed validation; database foreign key and check constraints; SHA-256 model artifact checksums. |
| **Repudiation (R)** | User denies executing an unauthorized simulation or altering parameters. | Absence of audit trails for scenario creation. | Compliance breakdown, lack of accountability. | **Medium** | Low | Append-only `audit_logs` table recording timestamp, `user_id`, action, IP address, and payload hash. |
| **Information Disclosure (I)** | Unauthorized extraction of research models or user records. | Unsanitized error messages (stack traces) or insecure API endpoints. | Model intellectual property leakage or system reconnaissance. | **Medium** | Medium | Standardized, sanitized error envelopes (stack traces suppressed); strict role-based access control (RBAC). |
| **Denial of Service (D)** | Attacker exhausts CPU via high-resolution numerical ODE solving. | Submitting simulation requests with tiny step sizes ($dt \to 0$) or massive horizons ($>100$ days). | Backend thread pool exhaustion, service outage. | **High** | Medium | Hard boundary checks: simulation duration capped at 1440 min (24h); minimum step size $\Delta t \ge 1 \text{ min}$; max 5 concurrent simulations per user. |
| **Elevation of Privilege (E)** | `clinician_observer` or `auditor` executes simulation runs or modifies telemetry. | Direct parameter tampering or missing role enforcement on endpoints. | Unauthorized state modification or simulation resource consumption. | **High** | Low | Declarative FastAPI role dependencies (`RequireRole(['researcher'])`); fail-closed RBAC middleware protecting write endpoints from `clinician_observer` and `auditor`. |

---

## 3. Clinical & Off-Label Misuse Threat Analysis

Because glucose modeling directly touches life-critical physiology, the threat of **human clinical misuse** is paramount:

### Threat CM-1: User Attempts to Treat Simulation as Clinical Insulin Bolus Guidance
- **Description:** A user or patient inputs real-life meals or blood glucose into GlucoTwin AI and uses the trajectory or counterfactual outputs to determine insulin bolus doses or basal rate adjustments.
- **Clinical Impact:** Potential severe hypoglycemia, coma, or death resulting from improper insulin administration.
- **Severity:** **CRITICAL**
- **Mitigation (Layered Defense):**
  1. **Strict Prohibition on Dosing Output (Rule 10):** The software contains **zero algorithms, functions, or formulas** for insulin dose calculation.
  2. **Refusal Blocker (`guardrails.py`):** An automated filter scans all outgoing responses. If any field or text matches dosing patterns (e.g. `X units`, `take insulin`, `bolus recommendation`), the request is immediately aborted with HTTP 400 and logged to `audit_logs`.
  3. **Prominent UI Banners:** Persistent, unclosable disclaimers appear on all views: *"RESEARCH & EDUCATION PROTOTYPE ONLY. NOT FOR CLINICAL USE. NEVER USE FOR INSULIN DOSING."*
  4. **Synthetic Data Policy:** System documentation and terms strictly restrict ingestion to synthetic data cohorts.

### Threat CM-2: Silent Failure Under Extreme Metabolic Crises
- **Description:** An extreme glucose spike ($>400 \text{ mg/dL}$) or drop ($<50 \text{ mg/dL}$) causes the linear ARX model or discrete Kalman filter to diverge or oscillate wildly.
- **Impact:** Misleading trajectory indicating false recovery.
- **Severity:** **High**
- **Mitigation:**
  - Hard physiological sanity clamping ($[40.0, 500.0] \text{ mg/dL}$).
  - Dynamic divergence detection: if prediction uncertainty bounds exceed $\pm 50 \text{ mg/dL}$, the model automatically **abstains** with `MODEL_DIVERGENCE_ABSTAIN`.

---

## 4. Residual Security Risks & Acceptance

1. **Client-Side Environment Tampering:** A malicious user running the open-source code locally could remove the disclaimer banners. *Accepted as inherent to open-source software; mitigated by server-side refusal guardrails and software licenses.*
2. **Synthetic Data Realism Divergence:** Synthetic models may not replicate individual human idiosyncratic biological responses (e.g. dawn phenomenon, sickness, cortisol spikes). *Documented comprehensively in Risk & Limitations.*
