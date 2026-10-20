"""
GlucoTwin AI - Simulation Scenario Model (Tier 4: Hypothetical)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SimulationScenario(Base):
    __tablename__ = "simulation_scenarios"

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
    scenario_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    simulation_duration_min: Mapped[int] = mapped_column(
        Integer,
        default=240,
        nullable=False
    )
    perturbation_params_json: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    baseline_trajectory_json: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    simulated_trajectory_json: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    tir_delta_percentage: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient = relationship("SyntheticPatient", back_populates="simulation_scenarios")

    __table_args__ = (
        CheckConstraint(
            "simulation_duration_min >= 60 AND simulation_duration_min <= 1440",
            name="ck_sim_duration_bounds"
        ),
    )
