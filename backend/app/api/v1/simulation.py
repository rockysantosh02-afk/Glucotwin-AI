"""
GlucoTwin AI - Counterfactual Simulation Endpoints (Tier 4: Hypothetical)
Executes in-silico What-If perturbation scenarios and persists results to simulation_scenarios.
Enforces strict fail-closed clinical refusal against insulin dose calculation and recommendation requests.
"""

import json
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthenticatedSession,
    add_cache_control_no_store,
    enforce_patient_scope,
    get_current_session,
)
from app.core.database import get_db
from app.core.errors import AppException, NotFoundException
from app.core.response import make_success_response
from app.models.patient import SyntheticPatient
from app.models.simulation import SimulationScenario
from app.schemas.hypothetical import SimulationRequest, SimulationResponse
from app.services.audit_service import AuditService
from app.services.counterfactual_simulator import CounterfactualSimulator

router = APIRouter(prefix="/patients", tags=["What-If Simulation (Tier 4: Hypothetical)"])


async def _resolve_patient(db: AsyncSession, identifier: str) -> SyntheticPatient:
    query = select(SyntheticPatient).where(
        (SyntheticPatient.id == identifier) |
        (SyntheticPatient.patient_code == identifier)
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise NotFoundException(resource="SyntheticPatient", resource_id=identifier)
    return patient


@router.post("/{patient_identifier}/twin/simulate", status_code=status.HTTP_200_OK)
async def run_what_if_simulation(
    patient_identifier: str,
    payload: SimulationRequest,
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes in-silico What-If counterfactual simulation under user-defined perturbations.
    - Perturbations: carb delta [-100, +150]g, timing shift [-60, +120]m, exercise duration & intensity.
    - Compares unperturbed baseline vs counterfactual trajectory.
    - Evaluates delta TIR and delta Mean Glucose.
    - Strict clinical refusal guardrail: refuses any insulin dosing recommendation attempts.
    - Persists scenario to simulation_scenarios table.
    """
    add_cache_control_no_store(response)

    # 1. Resolve patient and enforce patient authorization scope
    patient = await _resolve_patient(db, patient_identifier)
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    # 2. Execute Counterfactual Simulation Engine
    sim_result: SimulationResponse = CounterfactualSimulator.simulate_scenario(
        patient_profile=patient,
        scenario_name=payload.scenario_name,
        duration_minutes=payload.simulation_duration_min,
        perturbations=payload.perturbations,
        initial_glucose=payload.initial_glucose_override
    )

    # 3. Persist to simulation_scenarios table
    baseline_json = json.dumps([p.baseline_glucose for p in sim_result.trajectory])
    simulated_json = json.dumps([p.simulated_glucose for p in sim_result.trajectory])
    perturbations_json = json.dumps(payload.perturbations.model_dump(mode="json"))

    scenario_record = SimulationScenario(
        patient_id=patient.id,
        scenario_name=payload.scenario_name,
        simulation_duration_min=payload.simulation_duration_min,
        perturbation_params_json=perturbations_json,
        baseline_trajectory_json=baseline_json,
        simulated_trajectory_json=simulated_json,
        tir_delta_percentage=sim_result.metrics_shift.tir_delta_percentage
    )
    db.add(scenario_record)
    await db.commit()
    await db.refresh(scenario_record)

    sim_result.scenario_id = scenario_record.id

    # 4. Record audit event
    await AuditService.log_event(
        db=db,
        action="SIMULATION_SCENARIO_RUN",
        resource_type="simulation_scenario",
        resource_id=scenario_record.id,
        user_id=session.user_id,
        details={
            "patient_code": patient.patient_code,
            "scenario_name": payload.scenario_name,
            "carb_delta": payload.perturbations.carb_delta_grams,
            "exercise_duration": payload.perturbations.exercise_duration_minutes,
            "tir_delta": sim_result.metrics_shift.tir_delta_percentage
        }
    )

    return make_success_response(data=sim_result.model_dump(mode="json"), request=request)
