"""
GlucoTwin AI - Observation Ingestion API (Tier 1: Observed)
Provides high-throughput, validated observation ingestion for continuous glucose monitors,
meal carbohydrate logs, synthetic bolus logs, and activity telemetry.
Enforces patient-level authorization, physical unit normalization (mg/dL <-> mmol/L),
unique constraint duplicate filtering, and concurrency safety.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
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
from app.core.units import (
    normalize_activity_to_minutes,
    normalize_bolus_to_units,
    normalize_carbs_to_grams,
    normalize_glucose_to_mgdl,
)
from app.models.patient import SyntheticPatient
from app.models.telemetry import TelemetryRecord
from app.schemas.observations import (
    ObservationBatchIngestRequest,
    ObservationIngestResponse,
    ObservationItem,
)
from app.schemas.telemetry import TelemetryReadingCreate
from app.services.audit_service import AuditService

logger = logging.getLogger("glucotwin.observations")

router = APIRouter(prefix="/observations", tags=["Observations (Tier 1: Observed)"])


async def _resolve_patient_by_identifier(db: AsyncSession, identifier: str) -> SyntheticPatient:
    """Resolves a synthetic patient by either UUID id or patient_code."""
    query = select(SyntheticPatient).where(
        (SyntheticPatient.id == identifier) | (SyntheticPatient.patient_code == identifier)
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise NotFoundException(resource="SyntheticPatient", resource_id=identifier)
    return patient


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_observations(
    payload: ObservationBatchIngestRequest,
    request: Request,
    response: Response,
    patient_id: Optional[str] = Query(default=None, description="Optional target patient ID query param"),
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests a batch of physiological observations and telemetry readings.
    - Validates measurement types, units (supporting mg/dL and mmol/L), and physiological ranges.
    - Resolves patient and enforces patient-level authorization.
    - Handles out-of-order timestamps and normalizes to chronological sequence.
    - Merges concurrent multi-channel observations (glucose, carbs, bolus, exercise) at identical timestamps.
    - Uses database unique constraint (uq_patient_timestamp) and savepoints to prevent duplicate key errors under concurrency.
    - Audits ingestion outcomes without logging raw patient payloads.
    """
    add_cache_control_no_store(response)

    # 1. Determine target patient
    target_patient_identifier = (
        payload.patient_id or
        patient_id or
        (payload.observations and payload.observations[0].patient_id)
    )
    if not target_patient_identifier:
        raise AppException(
            code="MISSING_PATIENT_IDENTIFIER",
            message="Target patient identifier (patient_id or patient_code) must be provided in payload or query parameter.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    patient = await _resolve_patient_by_identifier(db, target_patient_identifier)
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    patient_id_str = str(patient.id)
    patient_code_str = str(patient.patient_code)

    raw_obs_items: List[ObservationItem] = payload.observations or []
    raw_readings: List[TelemetryReadingCreate] = payload.readings or []
    total_submitted = len(raw_obs_items) + len(raw_readings)

    duplicates_skipped = 0

    # 2. Structure into normalized readings by timestamp
    # Timestamp -> dict of aggregated channel values
    timestamp_buckets: Dict[datetime, Dict] = defaultdict(lambda: {
        "glucose_mg_dl": None,
        "rate_of_change": 0.0,
        "sensor_status": "OK",
        "meal_carbs_grams": 0.0,
        "bolus_synthetic_units": 0.0,
        "activity_minutes": 0.0,
        "activity_intensity": 0
    })

    # (A) Process granular observation items
    for item in raw_obs_items:
        ts = item.timestamp if item.timestamp.tzinfo is not None else item.timestamp.replace(tzinfo=timezone.utc)
        m_type = item.type.lower()
        bucket = timestamp_buckets[ts]

        if m_type == "glucose":
            norm_val = normalize_glucose_to_mgdl(item.value, item.unit)
            if bucket["glucose_mg_dl"] is not None:
                # Duplicate glucose reading for this timestamp in the same batch
                duplicates_skipped += 1
            else:
                bucket["glucose_mg_dl"] = norm_val
                bucket["sensor_status"] = item.sensor_status
                if item.rate_of_change:
                    bucket["rate_of_change"] = item.rate_of_change
        elif m_type in ("carbohydrates", "carbs"):
            norm_val = normalize_carbs_to_grams(item.value, item.unit)
            bucket["meal_carbs_grams"] += norm_val
        elif m_type in ("insulin_bolus", "bolus"):
            norm_val = normalize_bolus_to_units(item.value, item.unit)
            bucket["bolus_synthetic_units"] += norm_val
        elif m_type in ("activity", "exercise"):
            norm_val = normalize_activity_to_minutes(item.value, item.unit)
            bucket["activity_minutes"] += norm_val
            bucket["activity_intensity"] = max(bucket["activity_intensity"], item.activity_intensity or 0)

    # (B) Process direct telemetry readings
    for r in raw_readings:
        ts = r.timestamp if r.timestamp.tzinfo is not None else r.timestamp.replace(tzinfo=timezone.utc)
        bucket = timestamp_buckets[ts]
        if bucket["glucose_mg_dl"] is not None:
            duplicates_skipped += 1
        else:
            bucket["glucose_mg_dl"] = r.glucose_mg_dl
            bucket["sensor_status"] = r.sensor_status
            bucket["rate_of_change"] = r.rate_of_change or 0.0
            bucket["meal_carbs_grams"] += (r.meal_carbs_grams or 0.0)
            bucket["bolus_synthetic_units"] += (r.bolus_synthetic_units or 0.0)
            bucket["activity_minutes"] += (r.activity_minutes or 0.0)
            bucket["activity_intensity"] = max(bucket["activity_intensity"], r.activity_intensity or 0)

    if not timestamp_buckets:
        raise AppException(
            code="NO_VALID_OBSERVATIONS",
            message="No valid observations could be processed from the submission.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # 3. Sort chronologically to handle out-of-order timestamps
    sorted_timestamps = sorted(timestamp_buckets.keys())

    # 4. Check for existing timestamps in database for this patient in the window
    min_ts = sorted_timestamps[0]
    max_ts = sorted_timestamps[-1]

    existing_query = select(TelemetryRecord.timestamp).where(
        TelemetryRecord.patient_id == patient_id_str,
        TelemetryRecord.timestamp >= min_ts,
        TelemetryRecord.timestamp <= max_ts
    )
    existing_result = await db.execute(existing_query)
    existing_db_timestamps = set()
    for row in existing_result.all():
        val = row[0]
        if isinstance(val, str):
            val = datetime.fromisoformat(val)
        if isinstance(val, datetime) and val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        existing_db_timestamps.add(val)

    # 5. Fetch preceding database record for velocity calculation if first glucose reading needs it
    last_known_reading = None
    preceding_query = select(TelemetryRecord).where(
        TelemetryRecord.patient_id == patient_id_str,
        TelemetryRecord.timestamp < min_ts
    ).order_by(TelemetryRecord.timestamp.desc()).limit(1)
    preceding_result = await db.execute(preceding_query)
    last_known_reading = preceding_result.scalar_one_or_none()

    records_data: List[Dict] = []

    for ts in sorted_timestamps:
        if ts in existing_db_timestamps:
            duplicates_skipped += 1
            continue

        data = timestamp_buckets[ts]
        # If glucose is missing (e.g. standalone meal/activity log), use previous known glucose or baseline
        glucose_val = data["glucose_mg_dl"]
        if glucose_val is None:
            if last_known_reading is not None:
                glucose_val = last_known_reading.glucose_mg_dl
            else:
                glucose_val = 110.0  # standard fasting baseline

        # Compute velocity if missing
        velocity = data["rate_of_change"]
        if velocity == 0.0 and last_known_reading is not None:
            prev_ts = last_known_reading.timestamp
            if isinstance(prev_ts, str):
                prev_ts = datetime.fromisoformat(prev_ts)
            if isinstance(prev_ts, datetime) and prev_ts.tzinfo is None:
                prev_ts = prev_ts.replace(tzinfo=timezone.utc)
            dt_minutes = (ts - prev_ts).total_seconds() / 60.0
            if 1.0 <= dt_minutes <= 15.0:
                velocity = round((glucose_val - last_known_reading.glucose_mg_dl) / dt_minutes, 2)

        rec_dict = {
            "patient_id": patient_id_str,
            "timestamp": ts,
            "glucose_mg_dl": glucose_val,
            "rate_of_change": velocity,
            "sensor_status": data["sensor_status"],
            "meal_carbs_grams": data["meal_carbs_grams"],
            "bolus_synthetic_units": data["bolus_synthetic_units"],
            "activity_minutes": data["activity_minutes"],
            "activity_intensity": data["activity_intensity"]
        }
        records_data.append(rec_dict)
        last_known_reading = TelemetryRecord(**rec_dict)

    # 6. Concurrency-safe persistence with fallback on unique constraint collision
    successful_records: List[TelemetryRecord] = []
    if records_data:
        try:
            records_to_insert = [TelemetryRecord(**d) for d in records_data]
            db.add_all(records_to_insert)
            await db.commit()
            successful_records = list(records_to_insert)
        except IntegrityError:
            # Race condition collision occurred under concurrent ingestion
            await db.rollback()
            # Fall back to item-by-item salvage, skipping collided rows
            for item in records_data:
                try:
                    fresh_rec = TelemetryRecord(**item)
                    db.add(fresh_rec)
                    await db.commit()
                    successful_records.append(fresh_rec)
                except IntegrityError:
                    await db.rollback()
                    duplicates_skipped += 1

    earliest_time = successful_records[0].timestamp if successful_records else None
    latest_time = successful_records[-1].timestamp if successful_records else None

    # 7. Audit log event (strictly redacting clinical values / payloads)
    await AuditService.log_event(
        db=db,
        action="OBSERVATIONS_INGESTED",
        resource_type="telemetry_stream",
        resource_id=patient_id_str,
        user_id=session.user_id,
        details={
            "patient_code": patient_code_str,
            "total_submitted": total_submitted,
            "ingested_count": len(successful_records),
            "duplicates_skipped": duplicates_skipped,
            "earliest_time": earliest_time.isoformat() if earliest_time else None,
            "latest_time": latest_time.isoformat() if latest_time else None,
        }
    )

    response_data = ObservationIngestResponse(
        ingested_count=len(successful_records),
        duplicates_skipped=duplicates_skipped,
        patient_id=patient_id_str,
        patient_code=patient_code_str,
        earliest_reading_time=earliest_time,
        latest_reading_time=latest_time
    ).model_dump(mode="json")

    return make_success_response(data=response_data, request=request)
