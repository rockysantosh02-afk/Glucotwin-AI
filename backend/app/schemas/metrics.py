"""
GlucoTwin AI - Glycemic Metrics Schemas (Tier 2: Derived)
Standardizes Ambulatory Glucose Profile (AGP) consensus metrics, target thresholds, and modal percentiles.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GlycemicRanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tir_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Time In Range (70.0 to 180.0 mg/dL) percentage"
    )
    tar_level1_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Time Above Range Level 1 (180.1 to 250.0 mg/dL) percentage"
    )
    tar_level2_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Time Above Range Level 2 (> 250.0 mg/dL) percentage"
    )
    tbr_level1_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Time Below Range Level 1 (54.0 to 69.9 mg/dL) percentage"
    )
    tbr_level2_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Time Below Range Level 2 (< 54.0 mg/dL) percentage"
    )


class ClinicalTargetsMet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tir_above_70: bool = Field(
        ...,
        description="True if TIR >= 70.0%"
    )
    tbr_below_4: bool = Field(
        ...,
        description="True if total TBR (Level 1 + Level 2) < 4.0%"
    )
    cv_below_36: bool = Field(
        ...,
        description="True if glycemic variability CV% <= 36.0%"
    )


class HourlyPercentile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0 to 23)")
    p10: float = Field(..., description="10th percentile glucose (mg/dL)")
    p25: float = Field(..., description="25th percentile glucose (mg/dL)")
    p50: float = Field(..., description="50th percentile (median) glucose (mg/dL)")
    p75: float = Field(..., description="75th percentile glucose (mg/dL)")
    p90: float = Field(..., description="90th percentile glucose (mg/dL)")


class GlycemicMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    patient_id: str
    patient_code: Optional[str] = None
    window_start: datetime
    window_end: datetime
    total_readings: int = Field(..., ge=0)
    cgm_active_percentage: float = Field(..., ge=0.0, le=100.0)
    mean_glucose_mg_dl: float = Field(..., ge=0.0)
    standard_deviation: float = Field(..., ge=0.0)
    cv_percentage: float = Field(..., ge=0.0)
    gmi_percentage: float = Field(..., ge=0.0)
    ranges: GlycemicRanges
    clinical_targets_met: ClinicalTargetsMet
    hourly_percentiles: Optional[List[HourlyPercentile]] = None
