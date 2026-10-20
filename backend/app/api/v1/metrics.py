"""
GlucoTwin AI - Glycemic Metrics Endpoints (Tier 2: Derived)
Computes consensus Ambulatory Glucose Profile (AGP) metrics over historical telemetry windows.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthenticatedSession,
    add_cache_control_no_store,
    enforce_patient_scope,
    get_current_session,
)
from app.core.database import get_db
from app.core.errors import NotFoundException
from app.core.response import make_success_response
from app.models.metrics import GlycemicMetric
from app.models.patient import SyntheticPatient
from app.models.telemetry import TelemetryRecord
from app.schemas.metrics import GlycemicMetricsResponse
from app.services.agp_engine import AGPEngine
from app.services.audit_service import AuditService

router = APIRouter(prefix="/patients", tags=["Glycemic Metrics (Tier 2: Derived)"])


async def _resolve_patient(db: AsyncSession, identifier: str) -> SyntheticPatient:
    query = select(SyntheticPatient).where(
        (SyntheticPatient.id == identifier) |
        (SyntheticPatient.patient_code == identifier)
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise NotFoundException(resource="SyntheticPatient", resource_id=identifier)
    return patient


@router.get("/{patient_identifier}/metrics", status_code=status.HTTP_200_OK)
async def get_patient_glycemic_metrics(
    patient_identifier: str,
    request: Request,
    response: Response,
    window_days: int = Query(default=14, ge=1, le=90, description="Analysis window duration in days (1 to 90)"),
    persist: bool = Query(default=False, description="Whether to persist computed metrics to database"),
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes consensus Ambulatory Glucose Profile (AGP) metrics over a historical window.
    Evaluates:
    - Time in Range (TIR: 70-180 mg/dL, target > 70%)
    - Time Below Range (TBR Level 1 & 2, target < 4% / < 1%)
    - Time Above Range (TAR Level 1 & 2, target < 25% / < 5%)
    - Glycemic variability (%CV <= 36%)
    - Glucose Management Indicator (GMI)
    - Modal hourly percentiles (10th, 25th, 50th, 75th, 90th)
    Enforces patient-level authorization and anti-caching headers.
    """
    add_cache_control_no_store(response)

    # 1. Resolve patient and enforce patient scope
    patient = await _resolve_patient(db, patient_identifier)
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    # 2. Determine time window
    # Query latest telemetry reading for this patient
    latest_q = select(func.max(TelemetryRecord.timestamp)).where(TelemetryRecord.patient_id == patient.id)
    latest_res = await db.execute(latest_q)
    max_ts = latest_res.scalar_one_or_none()

    if max_ts is not None:
        if isinstance(max_ts, str):
            max_ts = datetime.fromisoformat(max_ts)
        if max_ts.tzinfo is None:
            max_ts = max_ts.replace(tzinfo=timezone.utc)
        window_end = max_ts
        window_start = window_end - timedelta(days=window_days)
    else:
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(days=window_days)

    # 3. Fetch telemetry records in the analysis window
    records_q = select(TelemetryRecord).where(
        TelemetryRecord.patient_id == patient.id,
        TelemetryRecord.timestamp >= window_start,
        TelemetryRecord.timestamp <= window_end
    ).order_by(TelemetryRecord.timestamp.asc())
    records_res = await db.execute(records_q)
    readings = records_res.scalars().all()

    # 4. Compute metrics using AGPEngine
    metrics: GlycemicMetricsResponse = AGPEngine.calculate_metrics(
        patient_id=patient.id,
        patient_code=patient.patient_code,
        readings=readings,
        window_start=window_start,
        window_end=window_end
    )

    # 5. Persist to glycemic_metrics table if requested and data exists
    if persist and len(readings) > 0:
        metric_record = GlycemicMetric(
            patient_id=patient.id,
            window_start=window_start,
            window_end=window_end,
            total_readings=metrics.total_readings,
            cgm_active_percentage=metrics.cgm_active_percentage,
            mean_glucose_mg_dl=metrics.mean_glucose_mg_dl,
            standard_deviation=metrics.standard_deviation,
            cv_percentage=metrics.cv_percentage,
            gmi_percentage=metrics.gmi_percentage,
            tir_percentage=metrics.ranges.tir_percentage,
            tar_level1_percentage=metrics.ranges.tar_level1_percentage,
            tar_level2_percentage=metrics.ranges.tar_level2_percentage,
            tbr_level1_percentage=metrics.ranges.tbr_level1_percentage,
            tbr_level2_percentage=metrics.ranges.tbr_level2_percentage
        )
        db.add(metric_record)
        await db.commit()

    # 6. Audit log calculation
    await AuditService.log_event(
        db=db,
        action="METRICS_CALCULATED",
        resource_type="glycemic_metrics",
        resource_id=patient.id,
        user_id=session.user_id,
        details={
            "patient_code": patient.patient_code,
            "window_days": window_days,
            "total_readings": metrics.total_readings,
            "tir_percentage": metrics.ranges.tir_percentage,
            "mean_glucose": metrics.mean_glucose_mg_dl
        }
    )

    return make_success_response(data=metrics.model_dump(mode="json"), request=request)
