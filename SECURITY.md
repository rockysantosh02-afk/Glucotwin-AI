# Security Policy: GlucoTwin AI

GlucoTwin AI takes software security and safety seriously. Even though this platform is an academic research and educational prototype operating exclusively on synthetic data, we enforce rigorous defensive security practices.

---

## 1. Supported Versions

Only the latest release of GlucoTwin AI receives active security updates and vulnerability patches.

| Version | Supported | Notes |
| :--- | :---: | :--- |
| `1.0.x` | ✅ Yes | Current main branch and active development |
| `< 1.0.0` | ❌ No | Deprecated development prototypes |

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability or clinical safety bypass within GlucoTwin AI, please report it responsibly:

- **Primary Security Contact:** `[SECURITY_CONTACT_EMAIL]`
- **Lead Maintainer:** `[TEAM_LEAD_NAME_AND_CONTACT]`
- **Institution:** `[COLLEGE_UNIVERSITY_AFFILIATION]`

### Reporting Guidelines:
1. **Do not create public GitHub issues** for security vulnerabilities or exploit disclosures.
2. Please provide:
   - A detailed description of the vulnerability (e.g. JWT validation bypass, IDOR flaw, rate-limit evasion, clinical refusal bypass).
   - Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
   - The affected endpoint, file, or component.
   - Proposed remediations, if available.
3. We will acknowledge receipt of your vulnerability report within **48 hours** and provide a patch timeline within **7 days**.

---

## 3. Core Security Tenets Implemented

- **Fail-Closed Design:** The application defaults to denying access, refusing unverified requests, and abstaining on degraded telemetry.
- **Strict Role-Based Access Control (RBAC):** Hierarchical user roles (`demo_clinician`, `clinician`, `admin`) enforced at the controller layer.
- **Insecure Direct Object Reference (IDOR) Protection:** Demo clinician tokens are strictly restricted to synthetic patient records.
- **Defensive HTTP Headers:** Enforced Content-Security-Policy (CSP), Strict-Transport-Security (HSTS), X-Content-Type-Options: nosniff, and X-Frame-Options: DENY.
- **Anti-Caching:** Authenticated health telemetry responses are strictly tagged with `Cache-Control: no-store, no-cache, must-revalidate`.
- **Payload Redaction:** Audit logging automatically redacts clinical glucose telemetry and observation arrays.
- **Rate Limiting:** Sliding-window per-client rate limits to prevent brute-force and denial-of-service attempts.

---

## 4. Academic & Synthetic Data Scope Disclaimer

GlucoTwin AI operates **exclusively on in-silico synthetic physiological data**. No real patient Protected Health Information (PHI) or Personally Identifiable Information (PII) is collected, stored, or processed by this platform. 

The software strictly prohibits clinical insulin dosage calculation or treatment advice. Never deploy or use this software in human clinical care.
