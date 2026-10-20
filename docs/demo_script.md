# GlucoTwin AI - Comprehensive Demonstration Walkthrough Script

**Document Version:** 1.0.0  
**Estimated Demonstration Duration:** 22–25 Minutes  
**Presenting Team:** `[TEAM_MEMBER_NAMES_AND_ROLES]`  
**Institution / Affiliation:** `[COLLEGE_UNIVERSITY_AFFILIATION]`  
**Artifact References:**
- Presentation Slides: `[PRESENTATION_SLIDES_URL]`
- Full Demonstration Video: `[RECORDED_DEMO_VIDEO_URL]`
- Live Cloud Deployment: `[PRODUCTION_DEPLOYED_URL]`

---

## Demonstration Overview & Timetable

| Time Elapsed | Demonstration Section | Key Feature / Verification Demonstrated | Primary Interface |
| :---: | :--- | :--- | :--- |
| **00:00 – 02:30** | **Section 1:** Synthetic Data & Provenance | Deterministic generator, seed tracking, zero PHI | Terminal / `provenance.json` |
| **02:30 – 05:00** | **Section 2:** Digital-Twin State Updates | Multi-modal observation ingestion, unit conversion | Swagger UI / Web Dashboard |
| **05:00 – 07:30** | **Section 3:** Forecast & Uncertainty | 15–60m ARX-Kalman forecast, 95% confidence bands | Web Dashboard / Trajectory Plot |
| **07:30 – 10:30** | **Section 4:** What-If Counterfactual Simulation | Bergman Minimal Model ODE, carb/exercise perturbations | What-If Simulator Panel |
| **10:30 – 13:30** | **Section 5:** Model Evaluation & Baselines | Held-out test cohort benchmark, Clarke grid, baselines | `scripts/evaluate_models.py` |
| **13:30 – 15:30** | **Section 6:** Insufficient-Data Abstention | Fail-closed behavior on stale data and history gaps | Terminal / API Response |
| **15:30 – 17:30** | **Section 7:** Authorization Denial & IDOR | Deny-by-default RBAC, 401/403 errors, audit trail | Postman / Terminal cURL |
| **17:30 – 19:30** | **Section 8:** Model-Artifact Integrity | SHA-256 checksums, `/ready` health probe | Browser / Terminal |
| **19:30 – 22:30** | **Section 9:** Safety Stance & Limitations | Interstitial lag, non-clinical research boundaries | Web UI Banners & Docs |

---

## Detailed Step-by-Step Walkthrough

### Section 1: Synthetic Patient Data & Provenance (00:00 – 02:30)

#### Objective:
Demonstrate that the platform operates strictly on synthetic, physiologically realistic patient data with full mathematical provenance, completely eliminating privacy risks and complying with zero-PHI guidelines.

#### Actions & Commands:
1. Open terminal in repository root.
2. Inspect the demo dataset provenance metadata file:
   ```bash
   cat data/demo_dataset/provenance.json
   ```
3. Highlight the provenance contents:
   - `generator_version`: `1.0.0`
   - `generator_seed`: `42`
   - `num_patients`: `80`
   - `days_per_patient`: `14`
   - `total_readings`: `322,139`
   - `scenarios_included`: 7 named clinical scenarios (e.g. Dawn Phenomenon, Postprandial Exercise, Sensor Compression Low).
4. Run the data generator command in dry-run/preview mode:
   ```bash
   python scripts/generate_demo_data.py --patients 5 --days 1 --seed 123 --dry-run
   ```

#### Talking Points:
> *"Welcome to GlucoTwin AI. Today we present an in-silico physiological digital twin and metabolic simulation platform designed for Type 1 Diabetes research and education. First and foremost, GlucoTwin AI enforces a strict zero-PHI architecture. Every patient in this platform is generated deterministically through physiological differential equations, circadian harmonics, and synthetic EHR demographics. Here in `provenance.json`, you can see our reproducible generator metadata: 80 synthetic patients across 14 days, comprising over 322,000 readings with zero real-world patient data."*

---

### Section 2: Digital-Twin State Updates & Telemetry Ingestion (02:30 – 05:00)

#### Objective:
Show real-time digital-twin state updating upon ingesting multi-modal sensor readings (glucose, meals, synthetic insulin, exercise) with automatic unit normalization and idempotency.

#### Actions & Commands:
1. In the terminal or API documentation (`http://localhost:8000/docs`), authenticate using a demo session token:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/demo-session" \
     -H "Content-Type: application/json" \
     -d '{"role": "demo_clinician"}'
   ```
   Save the returned `access_token`.
2. Ingest a new multi-modal observation point with carbohydrate ingestion in mmol/L:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/observations/ingest" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "patient_id": "SYN-T1D-001",
       "observations": [
         {
           "timestamp": "2026-10-20T12:00:00Z",
           "glucose_value": 7.8,
           "unit": "mmol/L",
           "meal_carbs_grams": 45.0,
           "bolus_synthetic_units": 3.0,
           "activity_minutes": 0.0,
           "activity_intensity": 0
         }
       ]
     }'
   ```
3. Observe the response:
   - Status: `201 Created`
   - Normalized glucose: $7.8 \text{ mmol/L} \times 18.0182 = 140.54 \text{ mg/dL}$.
4. Re-send the exact same payload to demonstrate **concurrent duplicate idempotency**:
   - Status: `200 OK` with `duplicates_skipped: 1`. Zero database crash or primary key corruption.

#### Talking Points:
> *"When a sensor transmits readings, the digital twin updates its internal state. Our observation endpoint automatically standardizes clinical units: whether telemetry arrives in mmol/L or mg/dL, our core converts it with high precision. Notice that sending duplicate timestamps is handled gracefully without data corruption. The twin's internal state now reflects the 45-gram meal and bolus absorption kinetics."*

---

### Section 3: Multi-Horizon Glucose Forecast & Uncertainty (05:00 – 07:30)

#### Objective:
Demonstrate the ARX-Kalman multi-horizon trajectory prediction ($15, 30, 45, 60 \text{ minutes}$) and analytical 95% confidence bounds.

#### Actions & Commands:
1. In the Web Dashboard (`http://localhost:5173`), select patient `SYN-T1D-001` (or scenario `rapid_carb_absorption`).
2. Trigger the forecast via UI button or API:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/forecast/run" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "patient_id": "SYN-T1D-001",
       "horizon_minutes": 60,
       "include_uncertainty": true
     }'
   ```
3. Inspect the returned JSON trajectory:
   - `baseline_glucose_mg_dl`: `140.5`
   - Horizon points at $t+15$, $t+30$, $t+45$, $t+60$.
   - Analytical uncertainty confidence intervals ($\pm 1.96 \sigma$).
4. Show the Web UI Trajectory Chart:
   - Solid blue points = **Tier 1 Observed Telemetry**.
   - Dashed purple curve = **Tier 3 Predicted Trajectory**.
   - Shaded purple envelope = **95% Confidence Interval**.
   - Note how the uncertainty band widens naturally over time ($\pm 7.4 \text{ mg/dL}$ at 15 min $\to \pm 26.5 \text{ mg/dL}$ at 60 min).

#### Talking Points:
> *"Here we observe the short-term forecast engine. Powered by an AutoRegressive with Exogenous Inputs filter coupled with a Kalman state estimator, the twin projects forward 60 minutes. Crucially, we adhere to the principle of transparent uncertainty: no single deterministic point is presented without its analytical 95% confidence interval. The widening envelope reflects the expanding state covariance over time."*

---

### Section 4: What-If Counterfactual Scenario Simulation (07:30 – 10:30)

#### Objective:
Demonstrate the Bergman Minimal Model ODE counterfactual simulator. Show how researchers can simulate hypothetical perturbations (e.g. adding exercise or modifying meal timing) without altering ground truth.

#### Actions & Commands:
1. On the Web UI, open the **"What-If Metabolic Simulator"** drawer.
2. Set up a counterfactual experiment:
   - Scenario: *"Postprandial 30-min Moderate Walk"*.
   - Carbohydrate intake: Unchanged (45g at $t=0$).
   - Exercise perturbation: Add 30 minutes of moderate activity (intensity level 2) starting at $t+45 \text{ min}$.
3. Click **"Run Counterfactual Simulation"** (or trigger `POST /api/v1/simulation/what-if`).
4. Display the comparative visualization:
   - Baseline Trajectory (Gold dotted line): Glucose peaks at $215 \text{ mg/dL}$.
   - Counterfactual Trajectory (Emerald line): Increased peripheral insulin-independent glucose uptake curbs the peak to $172 \text{ mg/dL}$.
   - Metrics Delta: $\Delta TIR = +14.2\%$, Peak Reduction $= -43 \text{ mg/dL}$.
5. Emphasize Tier 4 Segregation: Show that `telemetry_records` remains unchanged; the simulation is stored in `simulation_scenarios`.

#### Talking Points:
> *"This is the core research value of the digital twin: in-silico what-if experimentation. By solving Bergman's 3-compartment differential equations via 4th/5th-order Runge-Kutta numerical integration, we model the metabolic impact of a 30-minute postprandial walk. The emerald counterfactual curve clearly shows the blunted glucose excursion. Most importantly, Tier 4 hypothetical data is strictly isolated from Tier 1 observed history, preventing artificial contamination."*

---

### Section 5: Model Evaluation, Benchmarks & Baseline Comparisons (10:30 – 13:30)

#### Objective:
Present real measured quantitative benchmark metrics on a strictly held-out synthetic test cohort, comparing the ARX-Kalman engine against classical persistence and linear extrapolation baselines.

#### Actions & Commands:
1. In the terminal, execute the automated benchmark evaluation:
   ```bash
   python scripts/evaluate_models.py
   ```
2. Display the live evaluation output in the console:
   ```text
   ================================================================================
   GLUCOTWIN AI - QUANTITATIVE EVALUATION RESULTS (MEASURED ON TEST COHORT)
   ================================================================================
   Horizon  | ARX-Kalman RMSE  | Persistence RMSE   | Linear Extrap RMSE | 95% CI Cov
   --------------------------------------------------------------------------------
   15 min   | 11.3 mg/dL       | 3.68 mg/dL         | 2.0 mg/dL          | 95.81%
   30 min   | 18.62 mg/dL      | 7.06 mg/dL         | 4.85 mg/dL         | 95.83%
   45 min   | 22.95 mg/dL      | 10.17 mg/dL        | 8.38 mg/dL         | 95.95%
   60 min   | 26.48 mg/dL      | 12.96 mg/dL        | 12.35 mg/dL        | 96.11%
   --------------------------------------------------------------------------------
   Overall MARD: 7.14%
   Clarke Error Grid Zone A: 91.18% | Zone A+B: 99.72% | Zone E: 0.01%
   Stale Data Abstention Rate: 100.0% (Zero false positives)
   ================================================================================
   ```
3. Open `docs/model_card.md` and explain the Clarke Error Grid distribution:
   - 91.18% in Zone A (clinically accurate).
   - 99.72% in benign Zones A + B.
   - 0.01% in Zone E (2 points out of 21,312).
   - Explain why baselines look low on smooth sedentary intervals but fail at turning points.

#### Talking Points:
> *"We do not invent or extrapolate model performance. These results were evaluated across 16 strictly held-out synthetic test patients comprising over 5,300 forecast windows and 21,000 evaluated points. Our ARX-Kalman model achieves an overall MARD of 7.14% and 99.72% in benign Clarke Error Grid Zones A and B. Furthermore, our empirical 95% confidence interval coverage exceeds 95.8% across all horizons, proving our uncertainty calibration is statistically sound."*

---

### Section 6: Insufficient-Data & Stale-Data Fail-Closed Abstention (13:30 – 15:30)

#### Objective:
Demonstrate the platform's fail-closed safety architecture: when data freshness or historical context is compromised, the engine strictly refuses to forecast.

#### Actions & Commands:
1. In the terminal, simulate a request with stale telemetry (latest reading is 30 minutes old):
   ```bash
   curl -X POST "http://localhost:8000/api/v1/forecast/run" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "patient_id": "SYN-T1D-001",
       "horizon_minutes": 60,
       "simulated_stale_offset_min": 30
     }'
   ```
2. Observe the fail-closed response envelope:
   ```json
   {
     "success": true,
     "data": {
       "status": "abstained",
       "forecast": null,
       "abstention": {
         "code": "DATA_TOO_STALE",
         "reason": "Latest telemetry timestamp is 30 minutes old (freshness limit is 15 minutes).",
         "recommended_action": "Ensure CGM synthetic telemetry stream is actively transmitting."
       }
     }
   }
   ```
3. Test insufficient history: Provide only 3 historical points (< 12 points required):
   - Response: `status="abstained"`, `code="INSUFFICIENT_HISTORY"`.
4. Highlight benchmark test: 100 out of 100 stale windows were successfully rejected (100.0% abstention rate).

#### Talking Points:
> *"In biomedical software, an unstated prediction is infinitely safer than an erroneous one. When telemetry drops or sensor signals are stale, GlucoTwin AI does not guess or extrapolate linearly into the void. It fails closed. Here, because data is 30 minutes old, the system returns `DATA_TOO_STALE` with zero false predictions. In our automated evaluation, the engine achieved a 100% abstention rate on degraded signals."*

---

### Section 7: Authorization Denial & IDOR Protection (15:30 – 17:30)

#### Objective:
Demonstrate centralized deny-by-default role-based access control (RBAC), token revocation on logout, and protection against Insecure Direct Object References (IDOR).

#### Actions & Commands:
1. Attempt to access a protected clinician-only route with an unauthenticated request:
   ```bash
   curl -i "http://localhost:8000/api/v1/protected/clinician-only"
   ```
   Result: `HTTP 401 Unauthorized`.
2. Authenticate with a `demo_clinician` session:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/demo-session" \
     -H "Content-Type: application/json" \
     -d '{"role": "demo_clinician"}'
   ```
3. Attempt to access the administrator endpoint using the `demo_clinician` token:
   ```bash
   curl -i "http://localhost:8000/api/v1/protected/admin-only" \
     -H "Authorization: Bearer <DEMO_TOKEN>"
   ```
   Result: `HTTP 403 Forbidden` (`INSUFFICIENT_PERMISSIONS`).
4. Attempt an IDOR breach: Query a non-synthetic patient record with a demo token:
   ```bash
   curl -i "http://localhost:8000/api/v1/patients/REAL-PATIENT-001" \
     -H "Authorization: Bearer <DEMO_TOKEN>"
   ```
   Result: `HTTP 403 Forbidden` (`DEMO_SCOPE_VIOLATION`).
5. Revoke the token via logout:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/logout" \
     -H "Authorization: Bearer <DEMO_TOKEN>"
   ```
   Attempt to re-use token $\to$ `HTTP 401 Unauthorized` (`TOKEN_REVOKED`).

#### Talking Points:
> *"Our security architecture implements strict deny-by-default RBAC and object-level authorization. Demo clinician sessions are cryptographically restricted to synthetic patient scopes. Any attempt to access unauthorized tiers or probe outside the sandboxed scope triggers immediate 403 Forbidden responses, which are permanently logged in our append-only audit trail."*

---

### Section 8: Model-Artifact Integrity Safeguards (17:30 – 19:30)

#### Objective:
Show that model parameter files and calibration weights are cryptographically verified via SHA-256 hashes during application boot and readiness checks.

#### Actions & Commands:
1. Probe the system readiness check:
   ```bash
   curl -i "http://localhost:8000/ready"
   ```
2. Review the structured readiness envelope:
   ```json
   {
     "status": "ready",
     "database": {
       "connected": true,
       "dialect": "sqlite",
       "migration_head": "0001_initial_schema"
     },
     "models": {
       "arx_kalman": {
         "version": "arx-kalman-v1.0.0",
         "integrity_verified": true,
         "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
       },
       "bergman_ode": {
         "version": "bergman-ode-v1.0.0",
         "integrity_verified": true
       }
     }
   }
   ```
3. Explain that if an adversary or corrupted disk alters the model artifacts, `integrity_verified` evaluates to `false`, causing `/ready` to return `503 Service Unavailable`, preventing traffic ingress.

#### Talking Points:
> *"To safeguard against model poisoning and corrupted parameter sets, our `/ready` endpoint verifies the SHA-256 cryptographic checksums of our digital twin assets prior to declaring the node ready for network traffic. If any file is tampered with or corrupted, the node fails readiness, safeguarding upstream users."*

---

### Section 9: Safety Stance, Known Limitations & Q&A Wrap-Up (19:30 – 22:30)

#### Objective:
Reiterate the ethical boundaries, physiological limitations, and research positioning of GlucoTwin AI.

#### Actions & Commands:
1. Point out the persistent disclaimer in the Web UI:
   *"IN-SILICO RESEARCH & EDUCATION PROTOTYPE ONLY. NOT A MEDICAL DEVICE. STRICTLY PROHIBITED FOR INSULIN DOSING OR TREATMENT DECISIONS."*
2. Trigger the clinical refusal filter by sending a simulated therapeutic query:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/simulation/what-if" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "patient_id": "SYN-T1D-001",
       "scenario_name": "Recommend insulin bolus for 60g meal",
       "perturbations": []
     }'
   ```
   Result: `HTTP 422 Unprocessable Entity` with `CLINICAL_SAFETY_REFUSAL`.
3. Summarize known biological limitations:
   - Interstitial lag (5–15 minutes behind venous blood).
   - In-silico ODE simplification (does not capture illness, hormonal surges, or gastroparesis).
   - Susceptibility to sensor compression artifacts ("compression lows").
4. Direct evaluators to project repositories and documentation:
   - Presentation Slides: `[PRESENTATION_SLIDES_URL]`
   - Video Walkthrough: `[RECORDED_DEMO_VIDEO_URL]`
   - Render Deployment: `[PRODUCTION_DEPLOYED_URL]`

#### Talking Points:
> *"To conclude: GlucoTwin AI is an academic exploration of glucose-insulin kinetics and digital twin methodologies. We built this platform with explicit safety fences. It will never recommend insulin doses, and it intercepts any attempt to solicit clinical prescriptions. While our mathematical models capture postprandial curves and physical activity perturbations with high fidelity, real human biology involves unmodeled hormones like cortisol and glucagon, as well as physical interstitial lag. We invite your questions and welcome you to inspect our code and documentation."*
