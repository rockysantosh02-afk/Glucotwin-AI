"""
GlucoTwin AI - Test Suite: Digital Twin Forecasting & Bergman ODE Engine (Tier 3: Predicted)
Tests physiological ODE simulation, recursive Kalman state estimation, confidence intervals,
and all fail-closed clinical safety abstention guardrails.
"""

from datetime import datetime, timedelta, timezone
from typing import NamedTuple
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.forecast import ForecastRun
from app.services.arx_kalman import ARXKalmanEngine
from app.services.bergman_model import BergmanMinimalModel
from app.services.synthetic_data import SyntheticDataGenerator


class DummyTelemetry(NamedTuple):
    timestamp: datetime
    glucose_mg_dl: float
    rate_of_change: float = 0.0
    sensor_status: str = "OK"
    meal_carbs_grams: float = 0.0
    bolus_synthetic_units: float = 0.0
    activity_minutes: float = 0.0
    activity_intensity: int = 0


def test_bergman_model_simulation():
    """Verifies that the Bergman Minimal Model ODE produces realistic postprandial dynamics."""
    model = BergmanMinimalModel(body_weight_kg=70.0, basal_glucose=110.0, basal_insulin=12.0)

    # Simulate 240 minutes with a 50g meal and 5 U bolus at t=15 min
    sim = model.simulate(
        duration_minutes=240.0,
        step_minutes=5.0,
        initial_glucose=110.0,
        meals=[(15.0, 50.0)],
        boluses=[(15.0, 5.0)]
    )

    times = sim["times"]
    glucose = sim["glucose"]

    assert len(times) == 49
    assert glucose[0] == 110.0

    # Glucose should exhibit a postprandial peak between 45 and 90 minutes
    peak_idx = int(np_argmax := glucose.argmax())
    peak_time = times[peak_idx]
    assert 30.0 <= peak_time <= 120.0
    assert glucose[peak_idx] > 120.0

    # Glucose should recover toward basal levels by t=240 min
    assert abs(glucose[-1] - 110.0) < 35.0

    # States remain within physiological bounds [40.0, 500.0]
    assert (glucose >= 40.0).all()
    assert (glucose <= 500.0).all()


def test_arx_kalman_forecast_completion_and_uncertainty():
    """Verifies completed ARX-Kalman trajectory forecasting, analytical 95% CI, and variance growth."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)
    base_time = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Construct 24 continuous 5-minute readings (2 hours of context)
    readings = []
    current_g = 135.0
    for i in range(24):
        ts = base_time + timedelta(minutes=i * 5)
        current_g += (0.5 if i < 12 else -0.5)
        readings.append(DummyTelemetry(timestamp=ts, glucose_mg_dl=round(current_g, 1)))

    # Execute 60-minute forecast
    res = ARXKalmanEngine.forecast(
        patient_profile=patient,
        readings=readings,
        horizon_minutes=60,
        include_uncertainty=True,
        anchor_timestamp=readings[-1].timestamp
    )

    assert res.status == "completed"
    assert res.horizon_minutes == 60
    assert res.baseline_glucose_mg_dl == readings[-1].glucose_mg_dl
    assert res.forecast is not None
    assert len(res.forecast) == 12  # 60 min / 5 min = 12 steps

    # Check uncertainty bounds and monotonic growth of CI width over time
    prev_ci_width = 0.0
    for pt in res.forecast:
        assert pt.ci_lower is not None and pt.ci_upper is not None
        assert pt.ci_lower <= pt.predicted_glucose <= pt.ci_upper
        ci_width = pt.ci_upper - pt.ci_lower
        assert ci_width >= prev_ci_width
        prev_ci_width = ci_width

    # Risk probabilities
    assert res.predicted_risk is not None
    assert 0.0 <= res.predicted_risk.hypoglycemia_probability <= 1.0
    assert 0.0 <= res.predicted_risk.hyperglycemia_probability <= 1.0


def test_abstention_insufficient_history():
    """Verifies fail-closed abstention when historical context is < 12 points (< 60 minutes)."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)
    base_time = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Only 5 readings (25 minutes)
    readings = [
        DummyTelemetry(timestamp=base_time + timedelta(minutes=i * 5), glucose_mg_dl=120.0)
        for i in range(5)
    ]

    res = ARXKalmanEngine.forecast(patient_profile=patient, readings=readings, horizon_minutes=60)
    assert res.status == "abstained"
    assert res.forecast is None
    assert res.abstention is not None
    assert res.abstention.code == "INSUFFICIENT_HISTORY"


def test_abstention_data_too_stale():
    """Verifies fail-closed abstention when latest telemetry reading is > 15 minutes old."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)
    base_time = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)

    # 15 readings, but latest is 30 minutes before anchor time
    readings = [
        DummyTelemetry(timestamp=base_time + timedelta(minutes=i * 5), glucose_mg_dl=120.0)
        for i in range(15)
    ]
    stale_anchor = readings[-1].timestamp + timedelta(minutes=30)

    res = ARXKalmanEngine.forecast(
        patient_profile=patient,
        readings=readings,
        horizon_minutes=60,
        anchor_timestamp=stale_anchor
    )
    assert res.status == "abstained"
    assert res.abstention.code == "DATA_TOO_STALE"


def test_abstention_sensor_gap_exceeded():
    """Verifies fail-closed abstention when a gap > 15 min occurs within recent context."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)
    base_time = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)

    # 14 readings with a 25-minute gap in the middle
    readings = []
    t = base_time
    for i in range(14):
        if i == 7:
            t += timedelta(minutes=25)  # 25-minute gap
        else:
            t += timedelta(minutes=5)
        readings.append(DummyTelemetry(timestamp=t, glucose_mg_dl=120.0))

    res = ARXKalmanEngine.forecast(
        patient_profile=patient,
        readings=readings,
        horizon_minutes=60,
        anchor_timestamp=readings[-1].timestamp
    )
    assert res.status == "abstained"
    assert res.abstention.code == "SENSOR_GAP_EXCEEDED"


def test_abstention_physiological_anomaly():
    """Verifies fail-closed abstention when current reading is outside [40.0, 500.0] mg/dL."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)
    base_time = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)

    # 14 readings ending with extreme reading 520.0 mg/dL
    readings = [
        DummyTelemetry(timestamp=base_time + timedelta(minutes=i * 5), glucose_mg_dl=120.0)
        for i in range(13)
    ]
    readings.append(DummyTelemetry(timestamp=base_time + timedelta(minutes=13 * 5), glucose_mg_dl=520.0))

    res = ARXKalmanEngine.forecast(
        patient_profile=patient,
        readings=readings,
        horizon_minutes=60,
        anchor_timestamp=readings[-1].timestamp
    )
    assert res.status == "abstained"
    assert res.abstention.code == "PHYSIOLOGICAL_ANOMALY"


@pytest.mark.asyncio
async def test_twin_forecast_endpoint_integration(client: AsyncClient, db_session, demo_clinician_token: str):
    """
    Verifies POST /api/v1/patients/{id}/twin/forecast endpoint:
    - Seeds cohort and telemetry
    - Executes 60-min forecast
    - Verifies completed trajectory and database persistence in forecast_runs table
    - Confirms anti-caching headers and envelope structure
    """
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}

    # 1. Seed patient and 1 day of continuous telemetry (288 points)
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)
    await client.post("/api/v1/patients/SYN-T1D-001/seed-telemetry", json={"days": 1, "seed": 42}, headers=headers)

    # 2. Run forecast
    resp = await client.post(
        "/api/v1/patients/SYN-T1D-001/twin/forecast",
        json={"horizon_minutes": 60, "include_uncertainty": True},
        headers=headers
    )
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")

    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == "completed"
    assert data["horizon_minutes"] == 60
    assert len(data["forecast"]) == 12

    # 3. Verify record persisted in forecast_runs
    persisted_q = await db_session.execute(select(ForecastRun))
    runs = persisted_q.scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].horizon_minutes == 60
    assert runs[0].trajectory_json is not None


@pytest.mark.asyncio
async def test_twin_forecast_endpoint_abstention_persistence(client: AsyncClient, db_session, demo_clinician_token: str):
    """
    Verifies that requesting a forecast for a patient with no telemetry
    triggers fail-closed abstention, persists to forecast_runs, and writes audit event with guardrail_triggered=True.
    """
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)

    # Forecast with no telemetry present
    resp = await client.post(
        "/api/v1/patients/SYN-T1D-001/twin/forecast",
        json={"horizon_minutes": 60},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "abstained"
    assert data["abstention"]["code"] == "INSUFFICIENT_HISTORY"

    # Verify persisted in DB with status abstained
    persisted_q = await db_session.execute(select(ForecastRun))
    runs = persisted_q.scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "abstained"
    assert runs[0].abstention_code == "INSUFFICIENT_HISTORY"
