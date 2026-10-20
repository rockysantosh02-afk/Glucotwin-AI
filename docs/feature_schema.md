# GlucoTwin AI - Feature Engineering & State Space Schema

**Document Version:** 1.0.0  
**Status:** Approved Architectural Contract  
**Target Engines:** ARX AutoRegressive Model, Kalman State Estimator, and Bergman ODE Minimal Model  

---

## 1. Feature Engineering Overview

The predictive digital twin models require structured feature vectors constructed from the discrete time-series stream of observed synthetic sensor readings:
$$\mathcal{S}_t = \{ (t_k, G_k, M_k, I_k, A_k) \}_{k=0}^t$$
where:
- $t_k$: UTC timestamp (step size $\Delta t = 5 \text{ min}$).
- $G_k$: Measured glucose in `mg/dL`.
- $M_k$: Logged meal carbohydrate mass in `grams`.
- $I_k$: Synthetic insulin delivery in `synthetic_units`.
- $A_k$: Physical activity intensity and duration.

---

## 2. Feature Definitions & Schema Table

| Feature Name | Symbol | Data Type | Physical Unit | Validity Bounds | Imputation Strategy | Mathematical Definition / Calculation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Current Glucose** | $G_t$ | `Float` | `mg/dL` | `[40.0, 500.0]` | No imputation. Fail closed if missing. | Measured interstitial glucose at current time $t$. |
| **Glucose Lag 1** | $G_{t-1}$ | `Float` | `mg/dL` | `[40.0, 500.0]` | Linear interpolation if single step missing. | Glucose reading at $t - 5 \text{ min}$. |
| **Glucose Lag 2** | $G_{t-2}$ | `Float` | `mg/dL` | `[40.0, 500.0]` | Linear interpolation if $\le 2$ steps missing. | Glucose reading at $t - 10 \text{ min}$. |
| **Glucose Lag 3** | $G_{t-3}$ | `Float` | `mg/dL` | `[40.0, 500.0]` | Linear interpolation if $\le 2$ steps missing. | Glucose reading at $t - 15 \text{ min}$. |
| **Glucose Lag 6** | $G_{t-6}$ | `Float` | `mg/dL` | `[40.0, 500.0]` | Nearest valid sample within $\pm 5 \text{ min}$. | Glucose reading at $t - 30 \text{ min}$. |
| **Glucose Lag 12**| $G_{t-12}$| `Float` | `mg/dL` | `[40.0, 500.0]` | Nearest valid sample within $\pm 5 \text{ min}$. | Glucose reading at $t - 60 \text{ min}$. |
| **Glucose Velocity** | $v_t$ | `Float` | `mg/dL/min` | `[-10.0, +10.0]` | Central difference or backward difference. | $v_t = \frac{G_t - G_{t-1}}{5.0}$ |
| **Glucose Acceleration** | $a_t$ | `Float` | `mg/dL/min²` | `[-5.0, +5.0]` | Second-order finite difference. | $a_t = \frac{G_t - 2G_{t-1} + G_{t-2}}{25.0}$ |
| **Carbs On Board** | $COB_t$ | `Float` | `grams` | `[0.0, 300.0]` | Default $0.0$ if unlogged. | Two-compartment gastrointestinal absorption decay: $COB_t = \sum_j M_j \cdot e^{-(t - t_j)/\tau_{gut}}$ ($\tau_{gut} \approx 45 \text{ min}$). |
| **Insulin On Board** | $IOB_t$ | `Float` | `synthetic_units` | `[0.0, 50.0]` | Default $0.0$ if unlogged. | Biexponential pharmacokinetic decay of synthetic insulin: $IOB_t = \sum_k I_k \cdot f_{decay}(t - t_k)$ ($\text{action duration} \approx 240 \text{ min}$). |
| **Activity Strain** | $ACT_t$ | `Float` | `strain_index` | `[0.0, 10.0]` | Default $0.0$ if no exercise. | Exponentially decaying exercise metabolic rate: $ACT_t = \text{Intensity} \cdot \frac{\text{Duration}}{60} \cdot e^{-\Delta t / \tau_{rec}}$ ($\tau_{rec} \approx 60 \text{ min}$). |
| **Circadian Sin** | $C_{sin}$ | `Float` | Unitless | `[-1.0, 1.0]` | Deterministic from timestamp. | $\sin\left(\frac{2\pi \cdot (\text{hour} + \text{min}/60)}{24}\right)$ |
| **Circadian Cos** | $C_{cos}$ | `Float` | Unitless | `[-1.0, 1.0]` | Deterministic from timestamp. | $\cos\left(\frac{2\pi \cdot (\text{hour} + \text{min}/60)}{24}\right)$ |

---

## 3. Normalization & Scaling Specification

To ensure numerical stability during ARX-Kalman recursive matrix inversion:

- **Z-Score Normalization Formula:**
  $$\hat{x} = \frac{x - \mu_{train}}{\sigma_{train}}$$
- **Fixed Training Population Reference Constants (Precomputed on Synthetic Baseline):**
  - Glucose $\mu_G = 140.0 \text{ mg/dL}$, $\sigma_G = 45.0 \text{ mg/dL}$
  - Velocity $\mu_v = 0.0 \text{ mg/dL/min}$, $\sigma_v = 1.2 \text{ mg/dL/min}$
  - $COB$ $\mu_{COB} = 15.0 \text{ g}$, $\sigma_{COB} = 25.0 \text{ g}$
  - $IOB$ $\mu_{IOB} = 1.2 \text{ U}$, $\sigma_{IOB} = 2.0 \text{ U}$
- **Invariance Rule:** Normalization parameters $\mu$ and $\sigma$ are strictly locked during model packaging; dynamic re-normalization on test sets is strictly forbidden to prevent leakage.

---

## 4. Missing Value & Out-of-Distribution Handling

1. **Gap $\le 10 \text{ minutes}$ (1 to 2 missing samples):**
   - Apply linear interpolation between nearest enclosing samples:
     $$G_{t_{gap}} = G_{left} + \frac{t_{gap} - t_{left}}{t_{right} - t_{left}} (G_{right} - G_{left})$$
2. **Gap $> 15 \text{ minutes}$:**
   - **Abstention Trigger:** Cease feature calculation. Flag the telemetry window as fragmented.
   - Return `DATA_TOO_STALE` or `SENSOR_GAP_EXCEEDED`.
3. **Out-of-Distribution (OOD) Sensor Readings:**
   - If $G_t < 40.0 \text{ mg/dL}$ or $G_t > 500.0 \text{ mg/dL}$, reading is rejected as unphysiological artifact.
   - Feature vector state is marked uncomputable, and model abstains.
