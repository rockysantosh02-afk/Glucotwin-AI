"""
GlucoTwin AI - Observation Ingestion Schemas (Tier 1: Observed)
Validates individual observation items, multi-type measurement batches,
units (mg/dL and mmol/L), timestamps, and batch limits.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.units import (
    normalize_activity_to_minutes,
    normalize_bolus_to_units,
    normalize_carbs_to_grams,
    normalize_glucose_to_mgdl,
)
from app.schemas.telemetry import TelemetryReadingCreate


class ObservationItem(BaseModel):
    """
    Normalized observation item supporting multiple physiological measurement types.
    """
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(
        ...,
        description="Observation timestamp in ISO 8601 UTC"
    )
    type: Literal[
        "glucose", "carbohydrates", "carbs", "insulin_bolus", "bolus", "activity", "exercise"
    ] = Field(
        default="glucose",
        description="Physical measurement type"
    )
    value: float = Field(
        ...,
        description="Measurement numerical magnitude"
    )
    unit: str = Field(
        default="mg/dL",
        description="Measurement physical unit (e.g., 'mg/dL', 'mmol/L', 'g', 'U', 'min')"
    )
    sensor_status: Literal["OK", "CALIBRATING", "NOISE", "ERROR"] = Field(
        default="OK",
        description="CGM hardware status (for glucose observations)"
    )
    rate_of_change: Optional[float] = Field(
        default=0.0,
        ge=-15.0,
        le=15.0,
        description="Glucose velocity in mg/dL/min"
    )
    activity_intensity: Optional[int] = Field(
        default=0,
        ge=0,
        le=3,
        description="Activity intensity (0: None, 1: Light, 2: Moderate, 3: Heavy)"
    )
    patient_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional patient ID override"
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        # Enforce UTC timezone awareness
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)

        # Reject unreasonable timestamps (e.g., prior to 2020 or > 24 hours into the future)
        now_utc = datetime.now(timezone.utc)
        if v.year < 2020:
            raise ValueError(f"Timestamp {v.isoformat()} is too far in the past (must be >= 2020).")
        if v > now_utc + timedelta(hours=24):
            raise ValueError(f"Timestamp {v.isoformat()} cannot be more than 24 hours in the future.")
        return v

    @model_validator(mode="after")
    def validate_measurement_value_and_unit(self) -> "ObservationItem":
        m_type = self.type.lower()
        m_unit = self.unit.strip().lower()

        if m_type == "glucose":
            # Will normalize and validate [40.0, 500.0] mg/dL or [2.2, 27.8] mmol/L
            try:
                normalize_glucose_to_mgdl(self.value, self.unit)
            except ValueError as e:
                raise ValueError(str(e))
        elif m_type in ("carbohydrates", "carbs"):
            try:
                normalize_carbs_to_grams(self.value, self.unit)
            except ValueError as e:
                raise ValueError(str(e))
        elif m_type in ("insulin_bolus", "bolus"):
            try:
                normalize_bolus_to_units(self.value, self.unit)
            except ValueError as e:
                raise ValueError(str(e))
        elif m_type in ("activity", "exercise"):
            try:
                normalize_activity_to_minutes(self.value, self.unit)
            except ValueError as e:
                raise ValueError(str(e))

        return self


class ObservationBatchIngestRequest(BaseModel):
    """
    Unified batch request for POST /api/v1/observations/ingest.
    Accepts either granular observation items or telemetry readings.
    Bounded batch size between 1 and 5000 items.
    """
    model_config = ConfigDict(extra="forbid")

    patient_id: Optional[str] = Field(
        default=None,
        description="Target patient UUID or patient_code (e.g., SYN-T1D-001)"
    )
    observations: Optional[List[ObservationItem]] = Field(
        default=None,
        description="List of individual observation records"
    )
    readings: Optional[List[TelemetryReadingCreate]] = Field(
        default=None,
        description="Direct multi-channel telemetry readings format"
    )

    @model_validator(mode="after")
    def validate_batch_content(self) -> "ObservationBatchIngestRequest":
        obs_count = len(self.observations) if self.observations is not None else 0
        readings_count = len(self.readings) if self.readings is not None else 0
        total_items = obs_count + readings_count

        if total_items == 0:
            raise ValueError(
                "Observation ingest batch must contain at least one observation or telemetry reading."
            )
        if total_items > 5000:
            raise ValueError(
                f"Batch size of {total_items} exceeds maximum allowed batch limit of 5000 items."
            )
        return self


class ObservationIngestResponse(BaseModel):
    """
    Response returned upon successful processing of POST /api/v1/observations/ingest.
    """
    ingested_count: int
    duplicates_skipped: int
    stale_skipped: int = 0
    patient_id: str
    patient_code: str
    earliest_reading_time: Optional[datetime] = None
    latest_reading_time: Optional[datetime] = None
