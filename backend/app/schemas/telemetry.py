"""
GlucoTwin AI - Telemetry Pydantic Schemas (Tier 1: Observed)
Strictly validates sensor telemetry, meal carbohydrate logs, and synthetic insulin boluses.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TelemetryReadingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(
        ...,
        description="Sensor reading timestamp in UTC (ISO 8601)"
    )
    glucose_mg_dl: float = Field(
        ...,
        ge=40.0,
        le=500.0,
        description="Measured interstitial glucose (40.0 to 500.0 mg/dL)"
    )
    rate_of_change: Optional[float] = Field(
        default=0.0,
        ge=-15.0,
        le=15.0,
        description="Glucose velocity in mg/dL/min (auto-computed if omitted)"
    )
    sensor_status: Literal["OK", "CALIBRATING", "NOISE", "ERROR"] = Field(
        default="OK",
        description="CGM sensor hardware status"
    )
    meal_carbs_grams: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=300.0,
        description="Ingested meal carbohydrate mass (0.0 to 300.0 grams)"
    )
    bolus_synthetic_units: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=50.0,
        description="Synthetic insulin bolus delivered (0.0 to 50.0 U)"
    )
    activity_minutes: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=360.0,
        description="Physical activity duration (0.0 to 360.0 minutes)"
    )
    activity_intensity: Optional[int] = Field(
        default=0,
        ge=0,
        le=3,
        description="Activity intensity (0: None, 1: Light, 2: Moderate, 3: Heavy)"
    )

    @field_validator("glucose_mg_dl")
    @classmethod
    def round_glucose(cls, v: float) -> float:
        return round(v, 1)

    @field_validator("meal_carbs_grams", "bolus_synthetic_units", "activity_minutes")
    @classmethod
    def round_optional_floats(cls, v: Optional[float]) -> float:
        if v is None:
            return 0.0
        return round(v, 2)


class TelemetryBatchIngestRequest(BaseModel):
    """Payload for batch ingestion of observed telemetry."""
    model_config = ConfigDict(extra="forbid")

    readings: List[TelemetryReadingCreate] = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="List of observed sensor readings to ingest (1 to 5000 readings)"
    )


class TelemetryIngestResponse(BaseModel):
    """Response returned upon successful batch telemetry ingestion."""
    ingested_count: int
    duplicates_skipped: int
    patient_id: str
    latest_reading_time: Optional[datetime] = None


class TelemetryRecordResponse(BaseModel):
    """Full telemetry record representation returned by queries."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    timestamp: datetime
    glucose_mg_dl: float
    rate_of_change: Optional[float] = 0.0
    sensor_status: str
    meal_carbs_grams: float = 0.0
    bolus_synthetic_units: float = 0.0
    activity_minutes: float = 0.0
    activity_intensity: int = 0
    created_at: datetime


class TelemetryQueryResponse(BaseModel):
    """Response returned for historical telemetry queries."""
    total: int
    patient_id: str
    readings: List[TelemetryRecordResponse]
