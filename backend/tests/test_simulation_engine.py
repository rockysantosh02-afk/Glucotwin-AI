"""
GlucoTwin AI - Test Suite: What-If Counterfactual Simulation Engine & Clinical Refusal Safety Guardrails (Tier 4: Hypothetical)
Validates physiological perturbations (carb deltas, timing shifts, exercise), metric divergence,
database persistence in simulation_scenarios, anti-caching headers, and strict refusal of insulin dosage requests.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.simulation import SimulationScenario
from app.schemas.hypothetical import SimulationPerturbations
from app.services.counterfactual_simulator import CounterfactualSimulator
from app.services.synthetic_data import SyntheticDataGenerator


def test_simulation_carb_perturbation():
    """Verifies that an increase in meal carbohydrate (+40g) elevates glucose and shifts glycemic metrics."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)

    pert = SimulationPerturbations(
        carb_delta_grams=40.0,
        meal_timing_shift_minutes=0,
        exercise_intensity=0,
        exercise_duration_minutes=0.0
    )

    res = CounterfactualSimulator.simulate_scenario(
        patient_profile=patient,
        scenario_name="Carb Excursion Test",
        duration_minutes=240,
        perturbations=pert,
        initial_glucose=110.0
    )

    assert res.scenario_name == "Carb Excursion Test"
    assert len(res.trajectory) == 49  # 240 / 5 + 1

    # In the postprandial phase (e.g. t = 60 to 120 min), perturbed glucose must be higher than baseline
    postprandial_points = [p for p in res.trajectory if 60 <= p.time_minutes <= 120]
    assert all(p.simulated_glucose >= p.baseline_glucose for p in postprandial_points)
    assert any(p.delta_glucose > 10.0 for p in postprandial_points)

    # Mean glucose must increase
    assert res.metrics_shift.mean_delta_mg_dl > 0.0
    assert res.metrics_shift.simulated_mean > res.metrics_shift.baseline_mean


def test_simulation_exercise_perturbation():
    """Verifies that postprandial exercise produces acute glucose clearance relative to baseline."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)

    # 45 minutes of moderate exercise (intensity 2)
    pert = SimulationPerturbations(
        carb_delta_grams=0.0,
        meal_timing_shift_minutes=0,
        exercise_intensity=2,
        exercise_duration_minutes=45.0
    )

    res = CounterfactualSimulator.simulate_scenario(
        patient_profile=patient,
        scenario_name="Postprandial Exercise Test",
        duration_minutes=240,
        perturbations=pert,
        initial_glucose=110.0
    )

    # During and post exercise (e.g. t = 90 to 150 min), simulated glucose must drop below baseline
    exercise_points = [p for p in res.trajectory if 90 <= p.time_minutes <= 150]
    assert any(p.delta_glucose < -5.0 for p in exercise_points)

    # Overall mean glucose should be lower
    assert res.metrics_shift.mean_delta_mg_dl < 0.0


def test_simulation_meal_timing_shift():
    """Verifies that shifting meal timing by +30 minutes delays the postprandial turning point."""
    patient = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)

    pert = SimulationPerturbations(
        carb_delta_grams=0.0,
        meal_timing_shift_minutes=30,  # meal at t=45 instead of t=15
        exercise_intensity=0,
        exercise_duration_minutes=0.0
    )

    res = CounterfactualSimulator.simulate_scenario(
        patient_profile=patient,
        scenario_name="Delayed Meal Test",
        duration_minutes=240,
        perturbations=pert,
        initial_glucose=110.0
    )

    # At t=30 min, baseline meal is already absorbing, but delayed meal has not yet started
    point_at_30 = next(p for p in res.trajectory if p.time_minutes == 30)
    assert point_at_30.baseline_glucose > point_at_30.simulated_glucose


@pytest.mark.asyncio
async def test_clinical_safety_refusal_on_insulin_dosage_requests(client: AsyncClient, demo_clinician_token: str):
    """
    MANDATORY CLINICAL SAFETY GUARDRAIL:
    Verifies that any request attempting to calculate, suggest, or recommend insulin dosages
    is strictly refused by the platform with HTTP 422 and clinical safety disclaimer.
    """
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)

    # Attempt 1: recommend_insulin_dose = true
    payload_1 = {
        "scenario_name": "Unsafe Dose Optimization Request",
        "simulation_duration_min": 240,
        "recommend_insulin_dose": True,
        "perturbations": {"carb_delta_grams": 30.0}
    }
    resp_1 = await client.post("/api/v1/patients/SYN-T1D-001/twin/simulate", json=payload_1, headers=headers)
    assert resp_1.status_code == 422
    assert "CLINICAL_SAFETY_REFUSAL" in str(resp_1.json())

    # Attempt 2: calculate_bolus = true
    payload_2 = {
        "scenario_name": "Unsafe Bolus Calculation Request",
        "simulation_duration_min": 240,
        "calculate_bolus": True,
        "perturbations": {"carb_delta_grams": 50.0}
    }
    resp_2 = await client.post("/api/v1/patients/SYN-T1D-001/twin/simulate", json=payload_2, headers=headers)
    assert resp_2.status_code == 422
    assert "CLINICAL_SAFETY_REFUSAL" in str(resp_2.json())


@pytest.mark.asyncio
async def test_twin_simulate_endpoint_integration_and_persistence(client: AsyncClient, db_session, demo_clinician_token: str):
    """
    Verifies POST /api/v1/patients/{id}/twin/simulate endpoint:
    - Executes counterfactual What-If simulation
    - Confirms comparative trajectory and metric delta response
    - Verifies database persistence in simulation_scenarios table
    - Confirms anti-caching headers and audit logging
    """
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)

    valid_payload = {
        "scenario_name": "Postprandial Walk Exploration",
        "simulation_duration_min": 240,
        "perturbations": {
            "carb_delta_grams": 20.0,
            "meal_timing_shift_minutes": 0,
            "exercise_intensity": 1,
            "exercise_duration_minutes": 30.0
        }
    }

    resp = await client.post(
        "/api/v1/patients/SYN-T1D-001/twin/simulate",
        json=valid_payload,
        headers=headers
    )
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")

    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["scenario_name"] == "Postprandial Walk Exploration"
    assert len(data["trajectory"]) == 49
    assert "NOT A CLINICAL PRODUCT" in data["clinical_disclaimer"]
    assert "NO INSULIN DOSING" in data["clinical_disclaimer"]

    # Verify record in database table simulation_scenarios
    persisted_q = await db_session.execute(select(SimulationScenario))
    scenarios = persisted_q.scalars().all()
    assert len(scenarios) == 1
    assert scenarios[0].scenario_name == "Postprandial Walk Exploration"
    assert scenarios[0].simulation_duration_min == 240
    assert scenarios[0].simulated_trajectory_json is not None


@pytest.mark.asyncio
async def test_twin_simulate_unauthenticated_and_scope(client: AsyncClient, demo_clinician_token: str):
    """Verifies that unauthenticated calls return 401 and demo clinician is blocked on non-synthetic patients."""
    # Unauthenticated
    resp = await client.post(
        "/api/v1/patients/SYN-T1D-001/twin/simulate",
        json={"scenario_name": "Unauth Test"}
    )
    assert resp.status_code == 401

    # Demo clinician on non-synthetic patient
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    resp_scope = await client.post(
        "/api/v1/patients/REAL-001/twin/simulate",
        json={"scenario_name": "Scope Test"},
        headers=headers
    )
    assert resp_scope.status_code in (403, 404)
