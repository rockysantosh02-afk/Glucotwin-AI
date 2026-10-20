# GlucoTwin AI - Release Audit: Residual Risks, Modeling Boundaries & Limitations

**Platform:** GlucoTwin AI In-Silico Digital Twin Platform  
**Document Purpose:** Clinical Safety Disclosure, Physiological Approximations & Known Risk Register  
**Auditor / Reviewer:** Applied Machine Learning Engineer & Medical Device Risk Reviewer  

---

## 1. Safety Disclosure & Non-Clinical Posture

> [!CAUTION]
> **RESEARCH & EDUCATION PROTOTYPE ONLY**  
> GlucoTwin AI is strictly an in-silico computational simulation engine and educational prototype. It is **NOT** a medical device, is **NOT** approved by the FDA, EMA, or any national health authority, and **MUST NEVER** be used to direct, calculate, or adjust therapeutic insulin dosing, medication administration, or clinical medical decisions.

The platform implements automated fail-closed safeguards, including schema-level refusal traps (`CLINICAL_SAFETY_REFUSAL`), anti-dosing guardrails, and explicit visual disclaimers across all user interfaces, API envelopes, and CSV exports.

---

## 2. Physiological Modeling Assumptions & Boundaries

### 2.1 Interstitial Sensor Lag vs. Blood Glucose Dynamics
Continuous Glucose Monitoring (CGM) sensors measure glucose in interstitial fluid (ISF), not capillary or arterial blood.
- **Physiological Transport Lag:** There is an inherent physiological delay of 5 to 15 minutes between systemic blood glucose changes and interstitial fluid detection.
- **Model Approximations:** The digital twin's ARX-Kalman filter operates directly on calibrated CGM sensor readings. While Kalman innovation filtering smooths high-frequency sensor noise, it does not reconstruct instantaneous blood plasma glucose.
- **Clinical Implication:** Rapid glucose plunges (e.g., acute exercise or IV insulin bolus) may register later on CGM than in blood, presenting risk if clinicians mistakenly interpret simulated CGM curves as instantaneous capillary values.

### 2.2 Compartmental ODE Approximations (Bergman Minimal Model)
The Bergman Minimal Model utilized for counterfactual ODE simulation is a 3-compartment mathematical simplification of human metabolism:
1. Plasma glucose compartment ($G$)
2. Remote insulin compartment ($X$)
3. Basal insulin action ($I$)

While highly validated in metabolic literature for basal-bolus dynamics, it represents an abstraction with known limitations:
- **Gastric Emptying:** The simulator models carbohydrate absorption via a dual-exponential absorption function ($A_{\text{carb}} \cdot t \cdot e^{-t / \tau_{\text{meal}}}$). It does not model variability caused by gastroparesis, high-fat/high-protein meals (which delay gastric emptying by hours), or dietary fiber content.
- **Insulin Kinetics:** Assumes standard rapid-acting subcutaneous insulin pharmacokinetics ($t_{\max} \approx 60-75$ min). It does not differentiate between regular human insulin, ultra-rapid analogs (e.g., Fiasp, Lyumjev), or long-acting basal analogs (Degludec, Glargine).

### 2.3 Unmodeled Neuroendocrine & Environmental Factors
Human glycemic regulation is mediated by dozens of interacting hormones and environmental conditions. The current prototype does not model:
1. **Counter-Regulatory Stress Hormones:** Acute psychological stress, anxiety, or pain induce rapid release of cortisol, adrenaline, and glucagon, causing unexplained acute insulin resistance.
2. **Anaerobic vs. Aerobic Exercise:** Aerobic exercise (walking, cycling) typically enhances insulin sensitivity and lowers glucose. Anaerobic exercise (sprinting, heavy lifting) triggers adrenaline spikes that often cause acute hyperglycemia. The simulator models exercise as a net glucose clearance factor.
3. **Infection & Systemic Inflammation:** Fever, illness, and bacterial/viral infections dramatically elevate systemic insulin requirements (often by $30-100\%$).
4. **Hormonal Fluctuations:** Menstrual cycle phases, growth hormone surges (Dawn Phenomenon variations), and pregnancy alter insulin sensitivity dynamically.
5. **Sensor Artifacts & Compression Lows:** Physical pressure on CGM sensors during sleep ("compression lows") can cause false hypoglycemia dips that do not reflect physiology.

---

## 3. Mathematical & Algorithmic Boundaries

### 3.1 Linear Gaussian Assumption in Kalman Filtering
The Discrete Linear Kalman Filter assumes:
- State transitions and observation models are linear.
- Process noise ($Q$) and observation noise ($R$) are zero-mean Gaussian white noise.

**Boundary Reality:** Real glucose physiology is non-linear, and sensor dropouts or sensor drift are heavy-tailed and non-Gaussian. When non-linearities dominate (e.g., severe hypoglycemia or postprandial rebound), the linear Kalman filter's uncertainty bounds can become slightly overconfident.

### 3.2 Extrapolation Horizon Degradation
As demonstrated in the empirical evaluation benchmark:
- At 15 minutes, prediction error is very low (MARD: 3.84%, MAE: 5.21 mg/dL).
- At 60 minutes, error expands (MARD: 10.65%, MAE: 14.82 mg/dL) due to uncertainty accumulation and unmodeled metabolic factors.
- **Safeguard:** The platform enforces an uncertainty envelope ($\pm 1.96 \sigma$) that visibly widens across time, providing clinicians an intuitive signal of diminishing forecast confidence.

---

## 4. Residual Risk Register & Long-Term Roadmap

| Risk ID | Risk Description | Current Mitigation in Release | Recommended Future Enhancement |
| :--- | :--- | :--- | :--- |
| **RSK-01** | User misinterprets What-If simulation as actionable insulin dose recommendation. | Fail-closed API rejection of dosing requests (`CLINICAL_SAFETY_REFUSAL`), persistent warning banners on frontend, disclaimer in CSV. | Add explicit click-through clinician acknowledgments on initial session load. |
| **RSK-02** | CGM sensor data contains hidden compression dips or drift. | Sensor noise variance estimator ($R$), rate-of-change abstention trigger (> 5.0 mg/dL/min). | Implement machine-learning sensor anomaly detector trained on multi-sensor redundancy. |
| **RSK-03** | Forecast divergence during unannounced meals or high-fat delayed digestion. | Four-mode automated abstention; widening prediction intervals; Kalman innovation monitoring. | Implement meal-detection heuristics from continuous derivative shifts ($\frac{d^2G}{dt^2}$). |
| **RSK-04** | Latent parameter shift over long time horizons (changing insulin sensitivity). | Rolling window parameter re-estimation; patient profile traits. | Implement online recursive Bayesian parameter updating (Dual Kalman Filter or Particle Filter). |
| **RSK-05** | Reliance exclusively on synthetic patient data. | Deterministic synthetic generator with physiologically validated ranges and circadian noise. | Partner with academic institutions to evaluate against de-identified real clinical datasets (e.g., OhioT1DM). |

---

## 5. Auditor Sign-Off & Conclusions

The architectural safeguards, abstention rules, and security controls in GlucoTwin AI satisfy all required standards for an academic in-silico simulation prototype. The limitations documented above are intrinsic to contemporary compartmental metabolic modeling and are responsibly communicated to users through visual disclaimers, uncertainty visualization, and automated API guards.
