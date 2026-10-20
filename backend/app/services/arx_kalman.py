"""
GlucoTwin AI - ARX AutoRegressive Model & Recursive Kalman Filter Engine (Tier 3: Predicted)
Implements short-term predictive glucose forecasting across horizons H in {15, 30, 45, 60} minutes.
Integrates recursive Kalman state estimation, analytical 95% confidence intervals, and fail-closed clinical abstention.
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.stats import norm

from app.schemas.predicted import (
    AbstentionDetail,
    ForecastResponse,
    PredictedRisk,
    TrajectoryPoint,
)


class ARXKalmanEngine:
    """
    ARX-Kalman predictive digital twin state estimator and forecaster.
    """

    MODEL_VERSION = "arx-kalman-v1.0.0"

    @classmethod
    def _evaluate_abstention_guardrails(
        cls,
        readings: List[Any],
        anchor_time: datetime
    ) -> Optional[AbstentionDetail]:
        """
        Evaluates strict fail-closed safety guardrails before running forecast:
        1. DATA_TOO_STALE: latest sample > 15 minutes old.
        2. INSUFFICIENT_HISTORY: context duration < 60 minutes (< 12 readings).
        3. SENSOR_GAP_EXCEEDED: missing sensor gap in window > 15 minutes.
        4. PHYSIOLOGICAL_ANOMALY: reading outside [40.0, 500.0] mg/dL.
        """
        if not readings:
            return AbstentionDetail(
                code="INSUFFICIENT_HISTORY",
                reason="No historical telemetry records available for this patient.",
                recommended_action="Transmit at least 60 minutes of synthetic CGM telemetry."
            )

        # 1. History requirement: minimum 12 contiguous readings (60 minutes)
        if len(readings) < 12:
            return AbstentionDetail(
                code="INSUFFICIENT_HISTORY",
                reason=f"Telemetry history contains {len(readings)} readings. Minimum required is 12 (60 minutes).",
                recommended_action="Accumulate at least 60 minutes of continuous sensor context before forecasting."
            )

        # Sort readings chronologically
        sorted_readings = sorted(readings, key=lambda r: r.timestamp)
        latest_reading = sorted_readings[-1]

        latest_ts = latest_reading.timestamp
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        if anchor_time.tzinfo is None:
            anchor_time = anchor_time.replace(tzinfo=timezone.utc)

        # 2. Freshness requirement: latest reading age <= 15 minutes
        age_seconds = (anchor_time - latest_ts).total_seconds()
        if age_seconds > 900.0:  # > 15 minutes
            age_min = round(age_seconds / 60.0, 1)
            return AbstentionDetail(
                code="DATA_TOO_STALE",
                reason=f"Latest telemetry reading is {age_min} minutes old (maximum allowed freshness is 15 minutes).",
                recommended_action="Resume continuous synthetic CGM stream to regain state synchronization."
            )

        # 3. Gap check in recent 60-minute window (last 12 points)
        recent_window = sorted_readings[-12:]
        for i in range(1, len(recent_window)):
            t_curr = recent_window[i].timestamp
            t_prev = recent_window[i - 1].timestamp
            if t_curr.tzinfo is None:
                t_curr = t_curr.replace(tzinfo=timezone.utc)
            if t_prev.tzinfo is None:
                t_prev = t_prev.replace(tzinfo=timezone.utc)

            gap_seconds = (t_curr - t_prev).total_seconds()
            if gap_seconds > 900.0:  # > 15 minutes
                gap_min = round(gap_seconds / 60.0, 1)
                return AbstentionDetail(
                    code="SENSOR_GAP_EXCEEDED",
                    reason=f"Detected sensor gap of {gap_min} minutes within recent 60-minute context window.",
                    recommended_action="Wait for 12 contiguous sensor readings without dropouts to re-establish filter."
                )

        # 4. Out-of-bounds anomaly check on latest reading
        latest_glucose = float(latest_reading.glucose_mg_dl)
        if latest_glucose < 40.0 or latest_glucose > 500.0:
            return AbstentionDetail(
                code="PHYSIOLOGICAL_ANOMALY",
                reason=f"Current glucose reading ({latest_glucose} mg/dL) is outside physiological bounds [40.0, 500.0].",
                recommended_action="Recalibrate sensor hardware or verify synthetic stream integrity."
            )

        return None

    @classmethod
    def forecast(
        cls,
        patient_profile: Any,
        readings: List[Any],
        horizon_minutes: int = 60,
        include_uncertainty: bool = True,
        anchor_timestamp: Optional[datetime] = None
    ) -> ForecastResponse:
        """
        Runs ARX feature vector construction and recursive Kalman filter forecasting.
        Returns ForecastResponse (either completed trajectory or safe abstention).
        """
        # Validate horizon
        if horizon_minutes not in (15, 30, 45, 60):
            horizon_minutes = 60

        # Anchor timestamp defaults to latest reading's timestamp if not explicitly supplied
        if anchor_timestamp is None:
            if readings:
                sorted_r = sorted(readings, key=lambda r: r.timestamp)
                anchor_time = sorted_r[-1].timestamp
            else:
                anchor_time = datetime.now(timezone.utc)
        else:
            anchor_time = anchor_timestamp

        if anchor_time.tzinfo is None:
            anchor_time = anchor_time.replace(tzinfo=timezone.utc)

        # 1. Fail-closed safety guardrails evaluation
        abstention = cls._evaluate_abstention_guardrails(readings, anchor_time)
        if abstention is not None:
            return ForecastResponse(
                status="abstained",
                horizon_minutes=horizon_minutes,
                run_timestamp=anchor_time,
                model_version=cls.MODEL_VERSION,
                abstention=abstention
            )

        sorted_readings = sorted(readings, key=lambda r: r.timestamp)
        latest_reading = sorted_readings[-1]
        baseline_glucose = round(float(latest_reading.glucose_mg_dl), 1)

        # Patient metabolic constants
        isf = float(getattr(patient_profile, "insulin_sensitivity_factor", 45.0))
        icr = float(getattr(patient_profile, "carb_ratio", 10.0))
        carb_impact_factor = isf / icr

        # 2. State space initialization
        # State vector x = [Glucose, Velocity, COB, IOB]^T
        dt = 5.0  # sampling minutes

        # Decay constants
        tau_gut = 45.0  # minutes
        tau_ins = 60.0  # minutes
        lambda_cob = np.exp(-dt / tau_gut)
        lambda_iob = np.exp(-dt / tau_ins)

        # State transition matrix A
        # G_{k+1} = G_k + v_k * dt + alpha_cob * COB_k - alpha_iob * IOB_k
        # v_{k+1} = gamma_v * v_k + beta_cob * COB_k - beta_iob * IOB_k
        alpha_cob = 0.08 * carb_impact_factor
        alpha_iob = 0.12 * isf
        beta_cob = 0.015 * carb_impact_factor
        beta_iob = 0.025 * isf
        gamma_v = 0.70  # velocity damping

        A = np.array([
            [1.0, dt, alpha_cob, -alpha_iob],
            [0.0, gamma_v, beta_cob, -beta_iob],
            [0.0, 0.0, lambda_cob, 0.0],
            [0.0, 0.0, 0.0, lambda_iob]
        ], dtype=np.float64)

        # Observation matrix C: observes glucose
        C = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float64)

        # Process and Measurement Noise Covariances
        Q = np.diag([4.0, 0.15, 0.5, 0.02])
        R = np.array([[8.0]], dtype=np.float64)  # sensor noise variance ~ 8.0 mg/dL^2

        # Initialize filter state using first available context reading
        first_r = sorted_readings[0]
        x_est = np.array([float(first_r.glucose_mg_dl), 0.0, 0.0, 0.0], dtype=np.float64)
        P_est = np.diag([25.0, 1.0, 10.0, 1.0])

        # 3. Recursive Kalman Filter update over history
        for k in range(len(sorted_readings)):
            rk = sorted_readings[k]
            z_meas = float(rk.glucose_mg_dl)
            carbs_in = float(rk.meal_carbs_grams or 0.0)
            bolus_in = float(rk.bolus_synthetic_units or 0.0)

            # Control input addition: new carbs / boluses entering compartment
            if k > 0:
                # Predict
                x_pred = A @ x_est
                x_pred[2] += carbs_in
                x_pred[3] += bolus_in
                P_pred = A @ P_est @ A.T + Q

                # Update
                y_innov = z_meas - (C @ x_pred)[0]
                S_innov = (C @ P_pred @ C.T)[0, 0] + R[0, 0]

                # Divergence check
                if S_innov <= 0 or np.isnan(S_innov) or P_pred[0, 0] > 10000.0:
                    return ForecastResponse(
                        status="abstained",
                        horizon_minutes=horizon_minutes,
                        run_timestamp=anchor_time,
                        model_version=cls.MODEL_VERSION,
                        abstention=AbstentionDetail(
                            code="MODEL_DIVERGENCE_ABSTAIN",
                            reason="Kalman state covariance matrix diverged during historical recursive estimation.",
                            recommended_action="Reset state estimator context or inspect sensor noise variance."
                        )
                    )

                K_gain = (P_pred @ C.T) / S_innov
                x_est = x_pred + K_gain.flatten() * y_innov
                P_est = (np.eye(4) - K_gain @ C) @ P_pred
            else:
                x_est[0] = z_meas

        # 4. Forward multi-step projection across forecast horizon
        num_steps = int(horizon_minutes / 5)
        trajectory: List[TrajectoryPoint] = []

        x_proj = x_est.copy()
        P_proj = P_est.copy()

        for step_idx in range(1, num_steps + 1):
            offset_min = step_idx * 5
            x_proj = A @ x_proj
            P_proj = A @ P_proj @ A.T + Q

            pred_g = float(x_proj[0])
            var_g = float(P_proj[0, 0])
            sigma_g = math.sqrt(max(0.1, var_g))

            # Clamping
            pred_g_clamped = round(float(np.clip(pred_g, 40.0, 500.0)), 1)

            if include_uncertainty:
                ci_low = round(float(np.clip(pred_g - 1.96 * sigma_g, 40.0, 500.0)), 1)
                ci_high = round(float(np.clip(pred_g + 1.96 * sigma_g, 40.0, 500.0)), 1)
            else:
                ci_low = None
                ci_high = None

            trajectory.append(
                TrajectoryPoint(
                    time_offset_min=offset_min,
                    predicted_glucose=pred_g_clamped,
                    ci_lower=ci_low,
                    ci_upper=ci_high
                )
            )

        # 5. Hypo/Hyperglycemia risk probabilities at the horizon endpoint
        final_glucose = float(x_proj[0])
        final_sigma = math.sqrt(max(0.1, float(P_proj[0, 0])))

        # P(Hypo) = P(G < 70)
        z_hypo = (70.0 - final_glucose) / final_sigma
        p_hypo = float(norm.cdf(z_hypo))
        p_hypo = round(min(1.0, max(0.0, p_hypo)), 3)

        # P(Hyper) = P(G > 180) = 1 - P(G <= 180)
        z_hyper = (180.0 - final_glucose) / final_sigma
        p_hyper = float(1.0 - norm.cdf(z_hyper))
        p_hyper = round(min(1.0, max(0.0, p_hyper)), 3)

        return ForecastResponse(
            status="completed",
            horizon_minutes=horizon_minutes,
            run_timestamp=anchor_time,
            model_version=cls.MODEL_VERSION,
            baseline_glucose_mg_dl=baseline_glucose,
            forecast=trajectory,
            predicted_risk=PredictedRisk(
                hypoglycemia_probability=p_hypo,
                hyperglycemia_probability=p_hyper
            )
        )
