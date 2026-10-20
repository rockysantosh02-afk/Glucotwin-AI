# GlucoTwin AI - Algorithmic Risks & Physiological Limitations

**Document Version:** 1.0.0  
**Status:** Approved Architectural Baseline  
**Audience:** Researchers, Clinical Educators, System Engineers, and QA Teams  

---

## 1. Scope & Purpose

This document provides a rigorous, transparent breakdown of the mathematical, physiological, and operational limitations of the models implemented in GlucoTwin AI (specifically the **Bergman Minimal Model ODEs** and the **AutoRegressive with Exogenous Inputs [ARX] - Kalman Filter**). 

Understanding these limitations is essential to avoid unwarranted extrapolation or dangerous overreliance.

---

## 2. Physiological & Mathematical Limitations

### 2.1 The Bergman Minimal Model
The Bergman Minimal Model represents glucose-insulin kinetics using three coupled ordinary differential equations:
$$\frac{dG(t)}{dt} = - (p_1 + X(t)) G(t) + p_1 G_b + \frac{R_a(t)}{V_G}$$
$$\frac{dX(t)}{dt} = - p_2 X(t) + p_3 (I(t) - I_b)$$
$$\frac{dI(t)}{dt} = - n (I(t) - I_b) + \gamma [G(t) - h]^+ t$$

#### Identified Limitations:
1. **Lumped Compartment Simplification:** The human body possesses complex multi-organ metabolic pathways (liver hepatic glucose output, gut incretin hormones, renal threshold clearance, peripheral muscle uptake). The Minimal Model collapses these into single effective compartments.
2. **Subcutaneous vs. Intravenous Delay:** Real-world continuous sensors and insulin pumps operate in the **subcutaneous tissue**, not the plasma. Subcutaneous insulin absorption is delayed by $30–90 \text{ minutes}$ due to hexamer dissociation, which standard minimal models approximate with idealized delay kernels.
3. **Absence of Counter-Regulatory Hormonal Dynamics:** The model does not simulate glucagon secretion, epinephrine, cortisol, or growth hormone surges, which can cause sudden unmodeled hepatic glucose dumps during hypoglycemia, intense exercise, or emotional stress.
4. **Circadian Sensitivity Variations:** In vivo insulin sensitivity varies across a 24-hour cycle (e.g. dawn phenomenon). While circadian harmonics ($\sin/\cos$) are added in feature space, the ODE parameters $p_1, p_2, p_3$ are assumed quasi-static over simulation runs.

### 2.2 ARX & Kalman State-Space Limitations
1. **Linearity Assumption:** ARX is inherently a linear transfer function model. While effective for short-term perturbations ($15–30 \text{ minutes}$), glucose-insulin kinetics become highly nonlinear during large carbohydrate loads ($>75 \text{ g}$) or rapid hypoglycemic falls.
2. **Unmodeled Exogenous Variables:** Blood glucose is heavily influenced by factors that cannot be captured by standard CGM streams: illness, systemic inflammation, menstrual cycles, alcohol consumption, high-fat/high-protein meal delays, and dehydration.
3. **Physiological Lag in CGM Interstitial Fluid:** Continuous Glucose Monitors measure glucose in interstitial fluid rather than blood capillaries. This introduces an unavoidable physical physiological lag of **5 to 15 minutes**, meaning CGM readings lag true arterial glucose during rapid glycemic fluctuations.

---

## 3. Operational & User Risks

### 3.1 Risk of User Overreliance
- **Phenomenon:** Users or students may experience an "illusion of certainty" when viewing smooth, visually appealing simulation curves and treat hypothetical counterfactual trajectories as ground truth.
- **Mitigation:**
  - Trajectory visualizations must display distinct visual styles for Observed (solid points), Predicted (dashed line with shaded 95% confidence bands), and Hypothetical (contrasting dotted line).
  - Explicit warning badges and uncertainty bounds must accompany all visualizations.

### 3.2 Clinical Decision Risk
- **Phenomenon:** A user might attempt to calculate an insulin bolus or basal adjustment based on what-if simulations.
- **Mitigation:** The system strictly refuses to output dosing or therapeutic advice. If a user queries for treatment advice, the system responds with a hard refusal and logs the event to audit trails.

---

## 4. Fail-Closed Abstention Boundaries

The system will deterministically refuse to output forecasts or simulation predictions under any of the following fail-closed triggers:

| Abstention Trigger | Mathematical / Operational Condition | Return Code | System Response |
| :--- | :--- | :--- | :--- |
| **Telemetry Stale** | Current time $t - t_{\text{last\_cgm}} > 15 \text{ min}$ | `DATA_TOO_STALE` | Return HTTP 200 with `status="abstained"`. Do not extrapolate. |
| **Insufficient Context** | History duration $< 60 \text{ min}$ (fewer than 12 points) | `INSUFFICIENT_HISTORY` | Return `status="abstained"`. Request sensor warm-up. |
| **Excessive Missing Gap** | Gap in last 60 minutes $> 15 \text{ min}$ | `SENSOR_GAP_EXCEEDED` | Return `status="abstained"`. Linear interpolation prohibited. |
| **Physiological Anomaly** | $G_t < 40.0 \text{ mg/dL}$ or $G_t > 500.0 \text{ mg/dL}$ | `PHYSIOLOGICAL_ANOMALY` | Return `status="abstained"`. Sensor artifact detected. |
| **Model Divergence** | Prediction uncertainty band width $> 100.0 \text{ mg/dL}$ | `MODEL_DIVERGENCE_ABSTAIN` | Return `status="abstained"`. Kalman covariance blew up. |
