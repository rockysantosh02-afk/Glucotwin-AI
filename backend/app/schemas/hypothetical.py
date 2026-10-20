"""
GlucoTwin AI - Counterfactual Simulation Schemas (Tier 4: Hypothetical)
Defines perturbation parameters, comparative trajectory schemas, and clinical safety refusal guards.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SimulationPerturbations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carb_delta_grams: float = Field(
        default=0.0,
        ge=-100.0,
        le=150.0,
        description="Carbohydrate variation relative to baseline meal (-100.0 to +150.0 grams)"
    )
    meal_timing_shift_minutes: int = Field(
        default=0,
        ge=-60,
        le=120,
        description="Meal timing shift in minutes earlier or later (-60 to +120 minutes)"
    )
    exercise_intensity: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Exercise intensity (0: None, 1: Light walking, 2: Moderate jogging, 3: Heavy aerobic)"
    )
    exercise_duration_minutes: float = Field(
        default=0.0,
        ge=0.0,
        le=180.0,
        description="Physical activity duration in minutes (0.0 to 180.0 minutes)"
    )


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_name: str = Field(
        default="Counterfactual Exploration",
        min_length=1,
        max_length=100,
        description="Descriptive identifier for the what-if simulation run"
    )
    simulation_duration_min: int = Field(
        default=240,
        ge=60,
        le=1440,
        description="Duration of simulation horizon in minutes (60 to 1440 minutes / 24 hours)"
    )
    perturbations: SimulationPerturbations = Field(
        default_factory=SimulationPerturbations,
        description="Perturbation parameter variations"
    )
    initial_glucose_override: Optional[float] = Field(
        default=None,
        ge=40.0,
        le=500.0,
        description="Optional initial baseline glucose override (mg/dL)"
    )
    recommend_insulin_dose: Optional[bool] = Field(
        default=None,
        description="Clinical refusal trap: system strictly refuses insulin dosage recommendations"
    )
    calculate_bolus: Optional[bool] = Field(
        default=None,
        description="Clinical refusal trap: system strictly refuses therapeutic bolus calculation"
    )

    @model_validator(mode="after")
    def guard_against_clinical_dosage_requests(self):
        """
        Enforces fail-closed clinical safety guardrail:
        Strictly refuses any attempt to calculate, suggest, or recommend insulin dosages.
        """
        if self.recommend_insulin_dose is True or self.calculate_bolus is True:
            raise ValueError(
                "CLINICAL_SAFETY_REFUSAL: GlucoTwin AI is a research and education simulator. "
                "The platform strictly refuses to calculate, recommend, or optimize therapeutic insulin dosages."
            )
        return self


class SimulationTrajectoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_minutes: int = Field(..., description="Simulation time offset in minutes from baseline (0, 5, 10, ...)")
    baseline_glucose: float = Field(..., ge=40.0, le=500.0, description="Unperturbed baseline glucose (mg/dL)")
    simulated_glucose: float = Field(..., ge=40.0, le=500.0, description="Counterfactual perturbed glucose (mg/dL)")
    delta_glucose: float = Field(..., description="Shift in glucose level: simulated - baseline (mg/dL)")


class SimulationMetricsShift(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_tir: float = Field(..., ge=0.0, le=100.0, description="Baseline Time in Range (70-180 mg/dL) %")
    simulated_tir: float = Field(..., ge=0.0, le=100.0, description="Counterfactual Time in Range (70-180 mg/dL) %")
    tir_delta_percentage: float = Field(..., description="Change in TIR: simulated_tir - baseline_tir")
    baseline_mean: float = Field(..., ge=0.0, description="Baseline Mean Glucose (mg/dL)")
    simulated_mean: float = Field(..., ge=0.0, description="Counterfactual Mean Glucose (mg/dL)")
    mean_delta_mg_dl: float = Field(..., description="Change in Mean Glucose: simulated_mean - baseline_mean")


class SimulationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: Optional[str] = None
    scenario_name: str
    patient_id: str
    patient_code: Optional[str] = None
    simulation_duration_min: int
    perturbations: SimulationPerturbations
    metrics_shift: SimulationMetricsShift
    trajectory: List[SimulationTrajectoryPoint]
    clinical_disclaimer: str = (
        "RESEARCH & EDUCATION PROTOTYPE ONLY. NOT A CLINICAL PRODUCT. "
        "NO INSULIN DOSING OR THERAPEUTIC RECOMMENDATIONS ARE PROVIDED."
    )
