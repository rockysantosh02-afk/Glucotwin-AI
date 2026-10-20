"""
GlucoTwin AI - Digital Twin Forecast Endpoints (Tier 3: Predicted)
Executes forward trajectory predictions using the ARX-Kalman engine and stores results in forecast_runs.
Enforces fail-closed clinical safety abstention when data freshness or sensor history requirements are violated.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, status
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
from app.models.forecast import ForecastRun
from app.models.patient import SyntheticPatient
from app.models.telemetry import TelemetryRecord
from app.schemas.predicted import ForecastRequest, ForecastResponse
from app.services.arx_kalman import ARXKalmanEngine
from app.services.audit_service import AuditService

router = APIRouter(prefix="/patients", tags=["Digital Twin Forecast (Tier 3: Predicted)"])


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


@router.post("/{patient_identifier}/twin/forecast", status_code=status.HTTP_200_OK)
async def run_twin_forecast(
    patient_identifier: str,
    request: Request,
    response: Response,
    payload: Optional[ForecastRequest] = None,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes short-term trajectory forecasting using the ARX-Kalman digital twin engine.
    - Evaluates data freshness, history bounds, and sensor gaps.
    - Returns HTTP 200 with status='abstained' if safety guardrails are triggered.
    - Persists all forecast executions and abstentions into the Tier 3 Predicted database.
    - Applies strict anti-caching headers (Cache-Control: no-store).
    """
    add_cache_control_no_store(response)
    req = payload or ForecastRequest()

    # 1. Resolve patient and verify authorization scope
    patient = await _resolve_patient(db, patient_identifier)
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    # 2. Determine anchor timestamp
    if req.anchor_timestamp is not None:
        anchor_time = req.anchor_timestamp
        if anchor_time.tzinfo is None:
            anchor_time = anchor_time.replace(tzinfo=timezone.utc)
    else:
        # Determine latest recorded telemetry sample
        max_ts_q = select(func.max(TelemetryRecord.timestamp)).where(TelemetryRecord.patient_id == patient.id)
        max_ts_res = await db.execute(max_ts_q)
        max_ts = max_ts_res.scalar_one_or_none()
        if max_ts is not None:
            if isinstance(max_ts, str):
                max_ts = datetime.fromisoformat(max_ts)
            if max_ts.tzinfo is None:
                max_ts = max_ts.replace(tzinfo=timezone.utc)
            anchor_time = max_ts
        else:
            anchor_time = datetime.now(timezone.utc)

    # 3. Retrieve historical context readings up to anchor_time (up to 72 readings = 6 hours)
    context_start = anchor_time - timedelta(hours=6)
    records_q = select(TelemetryRecord).where(
        TelemetryRecord.patient_id == patient.id,
        TelemetryRecord.timestamp <= anchor_time,
        TelemetryRecord.timestamp >= context_start
    ).order_by(TelemetryRecord.timestamp.asc()).limit(72)
    records_res = await db.execute(records_q)
    context_readings = records_res.scalars().all()

    # 4. Execute ARX-Kalman Engine with fail-closed safety guards
    forecast_result: ForecastResponse = ARXKalmanEngine.forecast(
        patient_profile=patient,
        readings=context_readings,
        horizon_minutes=req.horizon_minutes,
        include_uncertainty=req.include_uncertainty,
        anchor_timestamp=anchor_time
    )

    # 5. Persist run to forecast_runs table
    traj_json = None
    lower_json = None
    upper_json = None
    ab_code = None
    ab_reason = None

    if forecast_result.status == "completed" and forecast_result.forecast is not None:
        traj_json = json.dumps([p.model_dump(mode="json") for p in forecast_result.forecast])
        lower_json = json.dumps([p.ci_lower for p in forecast_result.forecast])
        upper_json = json.dumps([p.ci_upper for p in forecast_result.forecast])
    elif forecast_result.status == "abstained" and forecast_result.abstention is not None:
        ab_code = forecast_result.abstention.code
        ab_reason = forecast_result.abstention.reason

    forecast_run_record = ForecastRun(
        patient_id=patient.id,
        run_timestamp=forecast_result.run_timestamp or anchor_time,
        model_version=forecast_result.model_version,
        horizon_minutes=req.horizon_minutes,
        status=forecast_result.status,
        trajectory_json=traj_json,
        uncertainty_lower_json=lower_json,
        uncertainty_upper_json=upper_json,
        abstention_code=ab_code,
        abstention_reason=ab_reason
    )
    db.add(forecast_run_record)
    await db.commit()

    # 6. Audit log execution
    action_name = "FORECAST_COMPLETED" if forecast_result.status == "completed" else "FORECAST_ABSTAINED"
    guardrail_flag = (forecast_result.status == "abstained")

    await AuditService.log_event(
        db=db,
        action=action_name,
        resource_type="digital_twin_forecast",
        resource_id=forecast_run_record.id,
        user_id=session.user_id,
        guardrail_triggered=guardrail_flag,
        details={
            "patient_code": patient.patient_code,
            "horizon_minutes": req.horizon_minutes,
            "status": forecast_result.status,
            "abstention_code": ab_code
        }
    )

    return make_success_response(data=forecast_result.model_dump(mode="json"), request=request)
