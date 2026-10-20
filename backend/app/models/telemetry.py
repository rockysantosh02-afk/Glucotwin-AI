"""
GlucoTwin AI - Telemetry Record Model (Tier 1: Observed)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("synthetic_patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    glucose_mg_dl: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    rate_of_change: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True
    )
    sensor_status: Mapped[str] = mapped_column(
        String(20),
        default="OK",
        nullable=False
    )
    meal_carbs_grams: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True
    )
    bolus_synthetic_units: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True
    )
    activity_minutes: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True
    )
    activity_intensity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient = relationship("SyntheticPatient", back_populates="telemetry_records")

    __table_args__ = (
        UniqueConstraint("patient_id", "timestamp", name="uq_patient_timestamp"),
        Index("ix_telemetry_patient_time", "patient_id", timestamp.desc()),
        CheckConstraint("glucose_mg_dl >= 40.0 AND glucose_mg_dl <= 500.0", name="ck_telemetry_glucose_bounds"),
        CheckConstraint("sensor_status IN ('OK', 'CALIBRATING', 'NOISE', 'ERROR')", name="ck_telemetry_sensor_status"),
        CheckConstraint("meal_carbs_grams >= 0.0 AND meal_carbs_grams <= 300.0", name="ck_telemetry_carbs_bounds"),
        CheckConstraint("bolus_synthetic_units >= 0.0 AND bolus_synthetic_units <= 50.0", name="ck_telemetry_bolus_bounds"),
        CheckConstraint("activity_minutes >= 0.0 AND activity_minutes <= 360.0", name="ck_telemetry_activity_minutes"),
        CheckConstraint("activity_intensity >= 0 AND activity_intensity <= 3", name="ck_telemetry_activity_intensity"),
    )
