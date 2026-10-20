# GlucoTwin AI - Model Evaluation & Validation Protocol

**Document Version:** 1.0.0  
**Status:** Approved Architectural Protocol  
**Scope:** Offline Benchmark Validation, Forecast Accuracy, Error Grids, and Abstention Metrics  
**Disclaimer:** Evaluation is conducted strictly on synthetic patient benchmarks for research and educational purposes. No clinical efficacy or medical device clearance is implied.

---

## 1. Synthetic Dataset Partitioning & Leakage Prevention

### 1.1 Strict Patient-Level Partitioning
To prevent optimistic bias and memorization of patient-specific baselines:
- **Cohort Split Ratio:** 
  - **Training Cohort:** 70% of synthetic patient profiles.
  - **Validation Cohort:** 15% of synthetic patient profiles (used for hyperparameter tuning and Kalman noise covariance $Q, R$ calibration).
  - **Test Cohort:** 15% of synthetic patient profiles (held-out unseen benchmark).
- **Zero Cross-Contamination:** No patient identifier, telemetry stream, or profile parameters from the test cohort may ever appear in the training or validation splits.

### 1.2 Temporal Ordering Protocol
- For any adaptive calibration within a single patient, splitting must strictly follow chronological ordering:
  $$t_{\text{calibration}} < t_{\text{evaluation}}$$
- Random temporal k-fold cross-validation is **strictly prohibited**, as time-series autocorrelation between $G_t$ and $G_{t+1}$ leads to severe data leakage.

---

## 2. Standard Quantitative Evaluation Metrics

All predictive forecast horizons ($H \in \{15, 30, 45, 60\} \text{ minutes}$) are evaluated using the following benchmark equations:

### 2.1 Root Mean Squared Error (RMSE)
Measures standard forecast dispersion in $\text{mg/dL}$:
$$\text{RMSE}(H) = \sqrt{\frac{1}{N} \sum_{i=1}^N \left( \hat{G}_{t_i+H} - G_{t_i+H} \right)^2}$$

### 2.2 Mean Absolute Error (MAE)
Measures average absolute magnitude of forecast error:
$$\text{MAE}(H) = \frac{1}{N} \sum_{i=1}^N \left| \hat{G}_{t_i+H} - G_{t_i+H} \right|$$

### 2.3 Mean Absolute Relative Difference (MARD)
Clinical sensor and model benchmarking standard percentage:
$$\text{MARD}(H) = \frac{1}{N} \sum_{i=1}^N \frac{\left| \hat{G}_{t_i+H} - G_{t_i+H} \right|}{G_{t_i+H}} \times 100\%$$

---

## 3. Clinical Safety & Error Grid Analysis

Standard numerical metrics do not capture clinical significance (e.g. an error of $30 \text{ mg/dL}$ is benign at $200 \text{ mg/dL}$ but life-threatening at $65 \text{ mg/dL}$). Therefore, error grid analysis is standard:

### 3.1 Consensus (Parkes) & Clarke Error Grid Zones
Every prediction pair $(G_{\text{true}}, \hat{G}_{\text{pred}})$ at $H = 30 \text{ min}$ and $H = 60 \text{ min}$ is mapped to standard error grid zones:

| Zone | Clinical Meaning | Target Quality Benchmark |
| :--- | :--- | :--- |
| **Zone A** | Clinically accurate values with no treatment divergence. | $> 85.0\%$ of predictions |
| **Zone B** | Benign errors that would lead to benign or no treatment alterations. | Combined Zone A + B $> 98.0\%$ |
| **Zone C** | Overcorrecting acceptable blood glucose. | $< 1.5\%$ |
| **Zone D** | Dangerous failure to detect hypoglycemia or hyperglycemia. | $< 0.5\%$ |
| **Zone E** | Erroneous treatment: confusing hypoglycemia for hyperglycemia. | **$0.0\%$ (Strict Zero Tolerance)** |

---

## 4. Operational & Abstention Metrics

The engine is engineered to fail closed. Therefore, reliability metrics include:

| Metric | Calculation | Significance |
| :--- | :--- | :--- |
| **Abstention Rate** | $\frac{N_{\text{abstained}}}{N_{\text{total\_requests}}} \times 100\%$ | Quantifies frequency of fail-closed safety interventions. |
| **Lag Detection Delay** | $\Delta t_{\text{peak}} = t_{\hat{G}_{\text{peak}}} - t_{G_{\text{peak}}}$ | Quantifies temporal delay in predicting rapid glucose turning points. |
| **Confidence Calibration** | Empirical coverage of $95\%$ interval: $\frac{1}{N} \sum \mathbb{I}(G \in [CI_{\text{lower}}, CI_{\text{upper}}])$ | Verifies that Kalman covariance estimates accurately represent real error distributions. |
| **Out-of-Bounds Rate** | $\frac{N(\hat{G} < 40 \text{ or } \hat{G} > 500)}{N} \times 100\%$ | Measures physiological plausibility violations (target $0.0\%$). |

---

## 5. Benchmark Execution & Reporting Requirements

1. **Automated Reproduction Script:** Evaluation must be executable via a standalone, deterministic script (`scripts/run_model_evaluation.py`) accepting `--cohort-seed` and `--horizon`.
2. **Deterministic Seed Control:** All synthetic patient test cohorts must be seeded with fixed random states (`numpy.random.seed(42)`).
3. **Artifact Recording:** Metrics must be exported to a versioned machine-readable JSON summary (`eval_results_vX.Y.Z.json`).
