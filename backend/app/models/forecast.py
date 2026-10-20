"""
GlucoTwin AI - Forecast Run Model (Tier 3: Predicted)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

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
    run_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="arx-kalman-v1.0.0"
    )
    horizon_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="completed",
        nullable=False
    )
    trajectory_json: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    uncertainty_lower_json: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    uncertainty_upper_json: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    abstention_code: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )
    abstention_reason: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient = relationship("SyntheticPatient", back_populates="forecast_runs")

    __table_args__ = (
        CheckConstraint("horizon_minutes IN (15, 30, 45, 60)", name="ck_forecast_horizon"),
        CheckConstraint("status IN ('completed', 'abstained', 'failed')", name="ck_forecast_status"),
    )
