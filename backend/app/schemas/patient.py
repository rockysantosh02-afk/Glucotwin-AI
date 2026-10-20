"""
GlucoTwin AI - Synthetic Patient Pydantic Schemas
Strictly validates synthetic patient demographics, basal settings, and metabolic parameters.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SyntheticPatientBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    patient_code: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Human-readable synthetic patient identifier (e.g., SYN-T1D-001)"
    )
    diabetes_type: Literal["T1D", "T2D"] = Field(
        default="T1D",
        description="Diabetes model type (T1D or T2D)"
    )
    age: int = Field(
        ...,
        ge=18,
        le=85,
        description="Patient age in years (18 to 85)"
    )
    body_weight_kg: float = Field(
        ...,
        ge=40.0,
        le=150.0,
        description="Body weight in kilograms (40.0 to 150.0 kg)"
    )
    basal_rate_synthetic: float = Field(
        ...,
        ge=0.1,
        le=3.0,
        description="Synthetic basal insulin rate (0.1 to 3.0 U/hr)"
    )
    insulin_sensitivity_factor: float = Field(
        ...,
        ge=10.0,
        le=150.0,
        description="Insulin Sensitivity Factor ISF (10.0 to 150.0 mg/dL/U)"
    )
    carb_ratio: float = Field(
        ...,
        ge=3.0,
        le=30.0,
        description="Insulin-to-Carb Ratio ICR (3.0 to 30.0 g/U)"
    )
    target_glucose_min: float = Field(
        default=70.0,
        ge=70.0,
        description="Target range minimum glucose (>= 70.0 mg/dL)"
    )
    target_glucose_max: float = Field(
        default=180.0,
        le=180.0,
        description="Target range maximum glucose (<= 180.0 mg/dL)"
    )

    @field_validator("patient_code")
    @classmethod
    def validate_synthetic_prefix(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean.startswith("SYN-"):
            raise ValueError("All synthetic patient codes must begin with 'SYN-' prefix.")
        return clean

    @field_validator("target_glucose_max")
    @classmethod
    def validate_target_range(cls, v: float, info) -> float:
        min_val = info.data.get("target_glucose_min", 70.0)
        if v <= min_val:
            raise ValueError(f"target_glucose_max ({v}) must be strictly greater than target_glucose_min ({min_val})")
        return v


class SyntheticPatientCreate(SyntheticPatientBase):
    """Schema for registering a new synthetic patient."""
    pass


class SyntheticPatientResponse(SyntheticPatientBase):
    """Schema for returned patient entity."""
    id: str = Field(..., description="Unique UUID for the patient entity")
    created_at: datetime
    updated_at: datetime


class PatientListResponse(BaseModel):
    """Paginated list of synthetic patients."""
    total: int
    skip: int
    limit: int
    patients: List[SyntheticPatientResponse]
