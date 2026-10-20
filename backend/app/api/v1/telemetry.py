"""
GlucoTwin AI - Telemetry Ingestion & Query Endpoints (Tier 1: Observed)
Provides batch ingestion of continuous glucose readings, meal logs, and exercise events.
Computes physiological rate-of-change, filters duplicates, and enforces patient-scope authorization.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthenticatedSession,
    add_cache_control_no_store,
    enforce_patient_scope,
    get_current_session,
)
from app.core.database import get_db
from app.core.errors import AppException, NotFoundException
from app.core.response import make_success_response
from app.models.patient import SyntheticPatient
from app.models.telemetry import TelemetryRecord
from app.schemas.telemetry import (
    TelemetryBatchIngestRequest,
    TelemetryIngestResponse,
    TelemetryQueryResponse,
    TelemetryReadingCreate,
    TelemetryRecordResponse,
)
from app.services.audit_service import AuditService
from app.services.synthetic_data import SyntheticDataGenerator

router = APIRouter(prefix="/patients", tags=["Telemetry (Tier 1: Observed)"])


class SeedTelemetryRequest(BaseModel):
    days: int = Field(default=14, ge=1, le=30, description="Duration of continuous telemetry to generate (1 to 30 days)")
    seed: int = Field(default=42, description="Deterministic random seed")


async def _resolve_patient(db: AsyncSession, identifier: str) -> SyntheticPatient:
    """Helper to resolve a patient by either UUID id or patient_code."""
    query = select(SyntheticPatient).where(
        (SyntheticPatient.id == identifier) |
        (SyntheticPatient.patient_code == identifier)
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise NotFoundException(resource="SyntheticPatient", resource_id=identifier)
    return patient


@router.post("/{patient_identifier}/telemetry", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry_batch(
    patient_identifier: str,
    payload: TelemetryBatchIngestRequest,
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Batch ingestion of observed synthetic sensor readings, meal logs, and activity events.
    - Resolves patient and verifies patient scope.
    - De-duplicates identical timestamps.
    - Computes physiological rate-of-change (velocity) if missing.
    - Persists valid telemetry records to Tier 1 Observed storage.
    """
    add_cache_control_no_store(response)

    # 1. Resolve patient and enforce patient-level authorization
    patient = await _resolve_patient(db, patient_identifier)
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    raw_readings = payload.readings
    if not raw_readings:
        raise AppException(
            code="EMPTY_TELEMETRY_BATCH",
            message="Telemetry batch must contain at least one valid reading.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # 2. Normalize and sort chronologically
    sorted_readings = sorted(raw_readings, key=lambda r: r.timestamp)

    # De-duplicate within the submitted batch itself
    unique_batch: List[TelemetryReadingCreate] = []
    seen_batch_times = set()
    internal_duplicates = 0

    for r in sorted_readings:
        # Ensure UTC timezone awareness
        ts = r.timestamp if r.timestamp.tzinfo is not None else r.timestamp.replace(tzinfo=timezone.utc)
        if ts in seen_batch_times:
            internal_duplicates += 1
            continue
        seen_batch_times.add(ts)
        unique_batch.append(r)

    # 3. Check for existing timestamps in the database to prevent duplicate key violations
    timestamps_list = [
        r.timestamp if r.timestamp.tzinfo is not None else r.timestamp.replace(tzinfo=timezone.utc)
        for r in unique_batch
    ]
    min_ts = min(timestamps_list)
    max_ts = max(timestamps_list)

    existing_query = select(TelemetryRecord.timestamp).where(
        TelemetryRecord.patient_id == patient.id,
        TelemetryRecord.timestamp >= min_ts,
        TelemetryRecord.timestamp <= max_ts
    )
    existing_result = await db.execute(existing_query)
    existing_timestamps = set()
    for row in existing_result.all():
        val = row[0]
        if isinstance(val, str):
            val = datetime.fromisoformat(val)
        if isinstance(val, datetime) and val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        existing_timestamps.add(val)

    # 4. Fetch the immediate preceding database record to compute velocity for the first reading if needed
    last_known_reading = None
    preceding_query = select(TelemetryRecord).where(
        TelemetryRecord.patient_id == patient.id,
        TelemetryRecord.timestamp < min_ts
    ).order_by(TelemetryRecord.timestamp.desc()).limit(1)
    preceding_result = await db.execute(preceding_query)
    last_known_reading = preceding_result.scalar_one_or_none()

    records_to_insert: List[TelemetryRecord] = []
    duplicates_skipped = internal_duplicates

    for reading in unique_batch:
        ts = reading.timestamp if reading.timestamp.tzinfo is not None else reading.timestamp.replace(tzinfo=timezone.utc)
        if ts in existing_timestamps:
            duplicates_skipped += 1
            continue

        # Velocity / rate of change computation
        velocity = reading.rate_of_change
        if velocity is None or velocity == 0.0:
            if last_known_reading is not None:
                prev_ts = last_known_reading.timestamp
                if isinstance(prev_ts, str):
                    prev_ts = datetime.fromisoformat(prev_ts)
                if isinstance(prev_ts, datetime) and prev_ts.tzinfo is None:
                    prev_ts = prev_ts.replace(tzinfo=timezone.utc)
                dt_minutes = (ts - prev_ts).total_seconds() / 60.0
                if 1.0 <= dt_minutes <= 15.0:
                    velocity = round((reading.glucose_mg_dl - last_known_reading.glucose_mg_dl) / dt_minutes, 2)
                else:
                    velocity = 0.0
            else:
                velocity = 0.0

        telemetry_row = TelemetryRecord(
            patient_id=patient.id,
            timestamp=ts,
            glucose_mg_dl=reading.glucose_mg_dl,
            rate_of_change=velocity,
            sensor_status=reading.sensor_status,
            meal_carbs_grams=reading.meal_carbs_grams or 0.0,
            bolus_synthetic_units=reading.bolus_synthetic_units or 0.0,
            activity_minutes=reading.activity_minutes or 0.0,
            activity_intensity=reading.activity_intensity or 0
        )
        records_to_insert.append(telemetry_row)
        last_known_reading = telemetry_row

    # 5. Persist to database
    if records_to_insert:
        db.add_all(records_to_insert)
        await db.commit()

    latest_reading_time = (
        records_to_insert[-1].timestamp.isoformat()
        if records_to_insert else None
    )

    # 6. Audit log ingestion event
    await AuditService.log_event(
        db=db,
        action="TELEMETRY_INGESTED",
        resource_type="telemetry_stream",
        resource_id=patient.id,
        user_id=session.user_id,
        details={
            "patient_code": patient.patient_code,
            "ingested_count": len(records_to_insert),
            "duplicates_skipped": duplicates_skipped,
            "latest_reading_time": latest_reading_time
        }
    )

    response_data = TelemetryIngestResponse(
        ingested_count=len(records_to_insert),
        duplicates_skipped=duplicates_skipped,
        patient_id=patient.id,
        latest_reading_time=records_to_insert[-1].timestamp if records_to_insert else None
    ).model_dump(mode="json")

    return make_success_response(data=response_data, request=request)


@router.get("/{patient_identifier}/telemetry", status_code=status.HTTP_200_OK)
async def query_patient_telemetry(
    patient_identifier: str,
    request: Request,
    response: Response,
    start_time: Optional[datetime] = Query(default=None, description="Start timestamp filter (ISO 8601 UTC)"),
    end_time: Optional[datetime] = Query(default=None, description="End timestamp filter (ISO 8601 UTC)"),
    limit: int = Query(default=288, ge=1, le=2000, description="Max readings to return (default 288 = 24 hours)"),
    order: Literal["asc", "desc"] = Query(default="asc", description="Chronological ordering"),
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Query historical observed telemetry readings for a synthetic patient.
    Enforces patient-level authorization, anti-caching headers, and time-range filtering.
    """
    add_cache_control_no_store(response)

    patient = await _resolve_patient(db, patient_identifier)
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    # Build query
    query = select(TelemetryRecord).where(TelemetryRecord.patient_id == patient.id)

    if start_time is not None:
        st_utc = start_time if start_time.tzinfo is not None else start_time.replace(tzinfo=timezone.utc)
        query = query.where(TelemetryRecord.timestamp >= st_utc)
    if end_time is not None:
        et_utc = end_time if end_time.tzinfo is not None else end_time.replace(tzinfo=timezone.utc)
        query = query.where(TelemetryRecord.timestamp <= et_utc)

    if order == "desc":
        query = query.order_by(TelemetryRecord.timestamp.desc())
    else:
        query = query.order_by(TelemetryRecord.timestamp.asc())

    query = query.limit(limit)

    result = await db.execute(query)
    records = result.scalars().all()

    record_responses = [
        TelemetryRecordResponse.model_validate(r).model_dump(mode="json")
        for r in records
    ]

    return make_success_response(
        data={
            "total": len(record_responses),
            "patient_id": patient.id,
            "patient_code": patient.patient_code,
            "order": order,
            "readings": record_responses
        },
        request=request
    )


@router.post("/{patient_identifier}/seed-telemetry", status_code=status.HTTP_201_CREATED)
async def seed_patient_telemetry(
    patient_identifier: str,
    request: Request,
    response: Response,
    payload: Optional[SeedTelemetryRequest] = None,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates and seeds a multi-day deterministic CGM telemetry stream for a synthetic patient.
    """
    add_cache_control_no_store(response)
    patient = await _resolve_patient(db, patient_identifier)
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    req = payload or SeedTelemetryRequest()

    # Generate synthetic telemetry stream
    generated_readings = SyntheticDataGenerator.generate_telemetry(
        patient_profile=patient,
        days=req.days,
        seed=req.seed
    )

    # Ingest using batch ingestion logic
    ingest_payload = TelemetryBatchIngestRequest(readings=generated_readings)
    return await ingest_telemetry_batch(
        patient_identifier=patient_identifier,
        payload=ingest_payload,
        request=request,
        response=response,
        session=session,
        db=db
    )
