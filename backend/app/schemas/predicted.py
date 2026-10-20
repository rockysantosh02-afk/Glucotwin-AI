"""
GlucoTwin AI - Digital Twin Forecast Schemas (Tier 3: Predicted)
Defines request payloads, trajectory projections, uncertainty bounds, risk probabilities, and abstention envelopes.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon_minutes: Literal[15, 30, 45, 60] = Field(
        default=60,
        description="Forecast horizon in minutes (15, 30, 45, or 60)"
    )
    include_uncertainty: bool = Field(
        default=True,
        description="Whether to include 95% confidence intervals from Kalman covariance"
    )
    anchor_timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional timestamp to anchor forecast (defaults to latest telemetry)"
    )


class TrajectoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_offset_min: int = Field(..., description="Minutes ahead from baseline (+5, +10, ..., +horizon)")
    predicted_glucose: float = Field(..., ge=40.0, le=500.0, description="Predicted glucose in mg/dL")
    ci_lower: Optional[float] = Field(default=None, ge=40.0, le=500.0, description="95% CI lower bound")
    ci_upper: Optional[float] = Field(default=None, ge=40.0, le=500.0, description="95% CI upper bound")


class PredictedRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypoglycemia_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability of glucose < 70.0 mg/dL at horizon"
    )
    hyperglycemia_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability of glucose > 180.0 mg/dL at horizon"
    )


class AbstentionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "DATA_TOO_STALE",
        "INSUFFICIENT_HISTORY",
        "SENSOR_GAP_EXCEEDED",
        "PHYSIOLOGICAL_ANOMALY",
        "MODEL_DIVERGENCE_ABSTAIN"
    ]
    reason: str
    recommended_action: str


class ForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "abstained", "failed"]
    horizon_minutes: Optional[int] = None
    run_timestamp: Optional[datetime] = None
    model_version: str = "arx-kalman-v1.0.0"
    baseline_glucose_mg_dl: Optional[float] = None
    forecast: Optional[List[TrajectoryPoint]] = None
    predicted_risk: Optional[PredictedRisk] = None
    abstention: Optional[AbstentionDetail] = None
