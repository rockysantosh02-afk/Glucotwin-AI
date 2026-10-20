"""
GlucoTwin AI - Glycemic Metric Model (Tier 2: Derived)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GlycemicMetric(Base):
    __tablename__ = "glycemic_metrics"

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
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    total_readings: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    cgm_active_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    mean_glucose_mg_dl: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    standard_deviation: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    cv_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    gmi_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    tir_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    tar_level1_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    tar_level2_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    tbr_level1_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    tbr_level2_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient = relationship("SyntheticPatient", back_populates="glycemic_metrics")

    __table_args__ = (
        CheckConstraint("total_readings >= 1", name="ck_metrics_total_readings"),
        CheckConstraint("cgm_active_percentage >= 0.0 AND cgm_active_percentage <= 100.0", name="ck_metrics_cgm_active"),
        CheckConstraint("mean_glucose_mg_dl > 0.0", name="ck_metrics_mean_glucose"),
        CheckConstraint("standard_deviation >= 0.0", name="ck_metrics_std_dev"),
        CheckConstraint("cv_percentage >= 0.0", name="ck_metrics_cv"),
        CheckConstraint("gmi_percentage >= 4.0 AND gmi_percentage <= 18.0", name="ck_metrics_gmi"),
        CheckConstraint("tir_percentage >= 0.0 AND tir_percentage <= 100.0", name="ck_metrics_tir"),
        CheckConstraint("tar_level1_percentage >= 0.0 AND tar_level1_percentage <= 100.0", name="ck_metrics_tar1"),
        CheckConstraint("tar_level2_percentage >= 0.0 AND tar_level2_percentage <= 100.0", name="ck_metrics_tar2"),
        CheckConstraint("tbr_level1_percentage >= 0.0 AND tbr_level1_percentage <= 100.0", name="ck_metrics_tbr1"),
        CheckConstraint("tbr_level2_percentage >= 0.0 AND tbr_level2_percentage <= 100.0", name="ck_metrics_tbr2"),
    )
