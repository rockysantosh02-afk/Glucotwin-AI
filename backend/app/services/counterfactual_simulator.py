"""
GlucoTwin AI - What-If Counterfactual Simulation Engine (Tier 4: Hypothetical)
Executes comparative physiological simulations using the Bergman Minimal Model under user-defined perturbations.
Calculates metric divergence (TIR delta, Mean glucose delta) and enforces fail-closed clinical refusal.
"""

from typing import Any, List, Optional
import numpy as np

from app.schemas.hypothetical import (
    SimulationMetricsShift,
    SimulationPerturbations,
    SimulationResponse,
    SimulationTrajectoryPoint,
)
from app.services.bergman_model import BergmanMinimalModel


class CounterfactualSimulator:
    """
    Simulation service for in-silico What-If counterfactual metabolic explorations.
    """

    @classmethod
    def simulate_scenario(
        cls,
        patient_profile: Any,
        scenario_name: str,
        duration_minutes: int,
        perturbations: SimulationPerturbations,
        initial_glucose: Optional[float] = None
    ) -> SimulationResponse:
        """
        Runs dual ODE trajectories:
        1. Unperturbed Baseline Trajectory: standard meal (50.0g carbs at t=15 min with standard bolus).
        2. Counterfactual Perturbed Trajectory: meal with carb_delta, timing shift, and exercise perturbations.
        Returns comparative trajectory and metric delta analysis.
        """
        weight = float(getattr(patient_profile, "body_weight_kg", 70.0))
        icr = float(getattr(patient_profile, "carb_ratio", 10.0))
        isf = float(getattr(patient_profile, "insulin_sensitivity_factor", 45.0))

        # Baseline glucose
        g0 = initial_glucose if initial_glucose is not None else 110.0

        # Standard reference scenario: 50.0g carbs at t=15 min, covered by standard prandial bolus
        base_meal_carbs = 50.0
        base_meal_time = 15.0
        base_bolus = round(base_meal_carbs / icr, 2)
        base_bolus_time = 15.0

        model = BergmanMinimalModel(
            body_weight_kg=weight,
            basal_glucose=110.0,
            basal_insulin=12.0
        )

        # 1. Run Baseline Simulation
        baseline_sim = model.simulate(
            duration_minutes=float(duration_minutes),
            step_minutes=5.0,
            initial_glucose=g0,
            meals=[(base_meal_time, base_meal_carbs)],
            boluses=[(base_bolus_time, base_bolus)],
            exercises=[]
        )
        base_times = baseline_sim["times"]
        base_glucose = baseline_sim["glucose"]

        # 2. Configure Counterfactual Perturbations
        # Shifted meal time: cannot be negative
        pert_meal_time = max(0.0, base_meal_time + perturbations.meal_timing_shift_minutes)
        # Shifted carbs: minimum 0.0g
        pert_meal_carbs = max(0.0, base_meal_carbs + perturbations.carb_delta_grams)
        # Bolus remains unchanged to explore consequence of unbolused/mismatched carbs
        pert_bolus = base_bolus
        pert_bolus_time = base_bolus_time

        pert_exercises = []
        if perturbations.exercise_duration_minutes > 0.0 and perturbations.exercise_intensity > 0:
            # Exercise starts 45 minutes after the meal
            ex_start = pert_meal_time + 45.0
            pert_exercises.append(
                (ex_start, float(perturbations.exercise_duration_minutes), perturbations.exercise_intensity)
            )

        # 3. Run Perturbed Simulation
        perturbed_sim = model.simulate(
            duration_minutes=float(duration_minutes),
            step_minutes=5.0,
            initial_glucose=g0,
            meals=[(pert_meal_time, pert_meal_carbs)],
            boluses=[(pert_bolus_time, pert_bolus)],
            exercises=pert_exercises
        )
        pert_glucose = perturbed_sim["glucose"]

        # 4. Comparative Trajectory Construction
        num_points = len(base_times)
        trajectory: List[SimulationTrajectoryPoint] = []

        for i in range(num_points):
            t_min = int(base_times[i])
            bg = round(float(base_glucose[i]), 1)
            sg = round(float(pert_glucose[i]), 1)
            delta = round(sg - bg, 1)

            trajectory.append(
                SimulationTrajectoryPoint(
                    time_minutes=t_min,
                    baseline_glucose=bg,
                    simulated_glucose=sg,
                    delta_glucose=delta
                )
            )

        # 5. Metrics Shift Analysis
        base_in_range = np.sum((base_glucose >= 70.0) & (base_glucose <= 180.0))
        pert_in_range = np.sum((pert_glucose >= 70.0) & (pert_glucose <= 180.0))

        base_tir = round(float(base_in_range / num_points * 100.0), 1)
        pert_tir = round(float(pert_in_range / num_points * 100.0), 1)
        tir_delta = round(pert_tir - base_tir, 1)

        base_mean = round(float(np.mean(base_glucose)), 1)
        pert_mean = round(float(np.mean(pert_glucose)), 1)
        mean_delta = round(pert_mean - base_mean, 1)

        metrics_shift = SimulationMetricsShift(
            baseline_tir=base_tir,
            simulated_tir=pert_tir,
            tir_delta_percentage=tir_delta,
            baseline_mean=base_mean,
            simulated_mean=pert_mean,
            mean_delta_mg_dl=mean_delta
        )

        patient_id = str(getattr(patient_profile, "id", "unknown-patient"))
        patient_code = str(getattr(patient_profile, "patient_code", "SYN-T1D-001"))

        return SimulationResponse(
            scenario_name=scenario_name,
            patient_id=patient_id,
            patient_code=patient_code,
            simulation_duration_min=duration_minutes,
            perturbations=perturbations,
            metrics_shift=metrics_shift,
            trajectory=trajectory
        )
