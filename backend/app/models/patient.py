"""
GlucoTwin AI - Synthetic Patient Model
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SyntheticPatient(Base):
    __tablename__ = "synthetic_patients"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    patient_code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True
    )
    diabetes_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="T1D"
    )
    age: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    body_weight_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    basal_rate_synthetic: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    insulin_sensitivity_factor: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    carb_ratio: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    target_glucose_min: Mapped[float] = mapped_column(
        Float,
        default=70.0,
        nullable=False
    )
    target_glucose_max: Mapped[float] = mapped_column(
        Float,
        default=180.0,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    telemetry_records = relationship(
        "TelemetryRecord",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="TelemetryRecord.timestamp.desc()"
    )
    glycemic_metrics = relationship(
        "GlycemicMetric",
        back_populates="patient",
        cascade="all, delete-orphan"
    )
    forecast_runs = relationship(
        "ForecastRun",
        back_populates="patient",
        cascade="all, delete-orphan"
    )
    simulation_scenarios = relationship(
        "SimulationScenario",
        back_populates="patient",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("diabetes_type IN ('T1D', 'T2D')", name="ck_patients_diabetes_type"),
        CheckConstraint("age >= 18 AND age <= 85", name="ck_patients_age_range"),
        CheckConstraint("body_weight_kg >= 40.0 AND body_weight_kg <= 150.0", name="ck_patients_weight_range"),
        CheckConstraint("basal_rate_synthetic >= 0.1 AND basal_rate_synthetic <= 3.0", name="ck_patients_basal_range"),
        CheckConstraint("insulin_sensitivity_factor >= 10.0 AND insulin_sensitivity_factor <= 150.0", name="ck_patients_isf_range"),
        CheckConstraint("carb_ratio >= 3.0 AND carb_ratio <= 30.0", name="ck_patients_icr_range"),
        CheckConstraint("target_glucose_min >= 70.0", name="ck_patients_target_min"),
        CheckConstraint("target_glucose_max <= 180.0", name="ck_patients_target_max"),
    )
