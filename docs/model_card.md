# GlucoTwin AI - Model Card: ARX-Kalman & Bergman ODE Engines

**Model Identifier:** `glucotwin-arx-kalman-v1.0.0` / `glucotwin-bergman-ode-v1.0.0`  
**Model Card Version:** 1.0.0-template  
**Release Date:** Phase 2 Architectural Baseline (October 20, 2026)  
**Status:** **Initial Architecture Template - All Quantitative Performance Metrics Clearly Marked as Unmeasured**  

---

## 1. Model Details

- **Model Developers:** GlucoTwin AI Research Team.
- **Model Type:** Hybrid Physiological-Statistical Digital Twin:
  1. *Short-Term Forecast Engine:* AutoRegressive with Exogenous Inputs (ARX) coupled with a Discrete Linear Kalman State Estimator.
  2. *What-If Counterfactual Engine:* Bergman Minimal Model 3-Compartment Nonlinear Ordinary Differential Equation (ODE) integration via Runge-Kutta 4(5) (`scipy.integrate.solve_ivp`).
- **Input Modalities:** Historical interstitial glucose time series ($\Delta t = 5 \text{ min}$), carbohydrate ingestion (grams), synthetic insulin bolus/basal units, exercise intensity/duration, and circadian time embeddings.
- **Output:** Predicted glucose trajectories ($H \in \{15, 30, 45, 60\} \text{ minutes}$), 95% uncertainty confidence intervals, and counterfactual trajectory deltas.
- **License:** MIT License (Research & Education Prototype).

---

## 2. Intended Use & Target Users

- **Primary Intended Use:** Academic and educational exploration of glucose-insulin feedback dynamics, simulation of carbohydrate and physical activity impacts, and training researchers on digital twin methodologies in Type 1 Diabetes.
- **Target Audience:** Biomedical engineering students, clinical researchers, data scientists, and metabolic modelers.

### Explicitly Prohibited Non-Intended Uses:
- **NOT FOR CLINICAL USE:** Never use this model for diagnosing diabetes, adjusting basal rates, calculating bolus doses, or making medical treatment decisions.
- **NOT AN AUTOMATED INSULIN DELIVERY (AID) CONTROLLER:** The model is not validated or cleared for closed-loop subcutaneous insulin pumping.
- **NO REAL-PATIENT TRIALS:** The model must not be deployed on real human subjects without clinical institutional review board (IRB) approval and regulatory clearance.

---

## 3. Training & Evaluation Datasets

- **Synthetic Cohort Specification:** Deterministically generated cohort of 50 in-silico Type 1 Diabetes patient profiles (varying body weights, insulin sensitivity factors $ISF \in [20, 80] \text{ mg/dL/U}$, carb ratios $ICR \in [6, 18] \text{ g/U}$, and basal rates).
- **Partitioning Strategy:**
  - Training Set: 70% of synthetic patients (35 profiles).
  - Validation Set: 15% of synthetic patients (7 profiles) for Kalman tuning.
  - Test Set: 15% of synthetic patients (8 profiles) strictly held out.
- **Data Provenance:** Purely synthetic. Zero real patient Protected Health Information (PHI) or continuous sensor records used.

---

## 4. Quantitative Evaluation Metrics (Phase 2 Baseline Template)

> ⚠️ **MANDATORY NOTE ON METRICS:**  
> In strict compliance with project guidelines, **no evaluation results or clinical metrics are fabricated or invented**. The quantitative entries below represent the formal evaluation criteria defined in `docs/evaluation_protocol.md` and are explicitly marked as **UNMEASURED** until Phase 5 benchmark execution.

| Evaluation Metric | Target Benchmark | Measured Value (Test Cohort) | Measurement Status |
| :--- | :--- | :--- | :--- |
| **RMSE (15-minute horizon)** | $< 12.0 \text{ mg/dL}$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **RMSE (30-minute horizon)** | $< 18.0 \text{ mg/dL}$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **RMSE (45-minute horizon)** | $< 25.0 \text{ mg/dL}$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **RMSE (60-minute horizon)** | $< 32.0 \text{ mg/dL}$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **MAE (30-minute horizon)** | $< 14.0 \text{ mg/dL}$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **MAE (60-minute horizon)** | $< 24.0 \text{ mg/dL}$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **MARD (Overall)** | $< 10.0\%$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **Clarke Error Grid Zone A** | $> 85.0\%$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **Clarke Error Grid Zone A + B** | $> 98.0\%$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **Clarke Error Grid Zone D** | $< 0.5\%$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **Clarke Error Grid Zone E** | **$0.0\%$ (Strict Zero Tolerance)** | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **Abstention Rate on Stale Data**| $100.0\%$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |
| **Out-of-Bounds Forecasts** | $0.0\%$ | *Unmeasured* | **[UNMEASURED - Pending Phase 5 Benchmark Training]** |

---

## 5. Ethical & Safety Considerations

1. **Refusal Mechanism:** The model pipeline incorporates an outbound guardrail that intercepts and suppresses any output syntax resembling prescriptive medical dosage instructions.
2. **Abstention Over Guesswork:** Under conditions of sensor noise, missing data ($>15 \text{ min}$ gap), or rapid unmodeled excursions, the model yields an explicit abstention (`status="abstained"`) rather than hallucinating an extrapolation.
3. **Reproducibility:** All parameter weights, initial ODE state vectors, and covariance matrices are cryptographically hashed using SHA-256 and tracked in Git.
