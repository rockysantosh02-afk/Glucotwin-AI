"""
GlucoTwin AI - Synthetic Patient Endpoints
Provides authenticated cohort inspection, synthetic profile retrieval, and synthetic patient generation.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthenticatedSession,
    add_cache_control_no_store,
    enforce_patient_scope,
    get_current_session,
    require_role,
)
from app.core.database import get_db
from app.core.errors import AppException, NotFoundException
from app.core.response import make_success_response
from app.models.patient import SyntheticPatient
from app.schemas.patient import (
    PatientListResponse,
    SyntheticPatientCreate,
    SyntheticPatientResponse,
)
from app.services.audit_service import AuditService
from app.services.synthetic_data import SyntheticDataGenerator

router = APIRouter(prefix="/patients", tags=["Synthetic Patients"])


class SeedCohortRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=50, description="Number of synthetic patients to generate")
    seed: int = Field(default=42, description="Deterministic random seed")


@router.get("/", status_code=status.HTTP_200_OK)
async def list_patients(
    request: Request,
    response: Response,
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items per page"),
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    List synthetic patients in the cohort.
    Enforces role authorization, demo clinician synthetic scope filtering, and anti-caching headers.
    """
    add_cache_control_no_store(response)

    # Base query
    base_query = select(SyntheticPatient)
    count_query = select(func.count(SyntheticPatient.id))

    # If demo clinician, strictly filter to synthetic patients (SYN-*)
    if session.is_demo:
        base_query = base_query.where(SyntheticPatient.patient_code.startswith("SYN-"))
        count_query = count_query.where(SyntheticPatient.patient_code.startswith("SYN-"))

    # Execute count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one_or_none() or 0

    # Execute paginated fetch
    fetch_query = base_query.order_by(SyntheticPatient.patient_code.asc()).offset(skip).limit(limit)
    rows_result = await db.execute(fetch_query)
    patients = rows_result.scalars().all()

    patient_responses = [
        SyntheticPatientResponse.model_validate(p).model_dump(mode="json")
        for p in patients
    ]

    return make_success_response(
        data={
            "total": total,
            "skip": skip,
            "limit": limit,
            "patients": patient_responses
        },
        request=request
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_patient(
    request: Request,
    response: Response,
    payload: SyntheticPatientCreate,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new synthetic patient profile in the in-silico cohort.
    Demo clinicians are strictly restricted to SYN-* codes.
    """
    add_cache_control_no_store(response)

    # Patient scope check
    enforce_patient_scope(session=session, patient_id="new-patient", patient_code=payload.patient_code)

    # Check for duplicate patient_code
    existing = await db.execute(
        select(SyntheticPatient).where(SyntheticPatient.patient_code == payload.patient_code)
    )
    if existing.scalar_one_or_none() is not None:
        raise AppException(
            code="PATIENT_CODE_EXISTS",
            message=f"A synthetic patient with code '{payload.patient_code}' already exists.",
            status_code=status.HTTP_409_CONFLICT
        )

    patient = SyntheticPatient(
        patient_code=payload.patient_code,
        diabetes_type=payload.diabetes_type,
        age=payload.age,
        body_weight_kg=payload.body_weight_kg,
        basal_rate_synthetic=payload.basal_rate_synthetic,
        insulin_sensitivity_factor=payload.insulin_sensitivity_factor,
        carb_ratio=payload.carb_ratio,
        target_glucose_min=payload.target_glucose_min,
        target_glucose_max=payload.target_glucose_max,
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)

    # Log audit event
    await AuditService.log_event(
        db=db,
        action="PATIENT_CREATED",
        resource_type="synthetic_patient",
        resource_id=patient.id,
        user_id=session.user_id,
        details={
            "patient_code": patient.patient_code,
            "diabetes_type": patient.diabetes_type,
            "age": patient.age
        }
    )

    data = SyntheticPatientResponse.model_validate(patient).model_dump(mode="json")
    return make_success_response(data=data, request=request)


@router.post("/seed-cohort", status_code=status.HTTP_201_CREATED)
async def seed_synthetic_cohort(
    request: Request,
    response: Response,
    payload: Optional[SeedCohortRequest] = None,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Populates the database with a deterministic cohort of synthetic T1D patients.
    Idempotent: skips already registered patient codes.
    """
    add_cache_control_no_store(response)
    req = payload or SeedCohortRequest()

    cohort_profiles = SyntheticDataGenerator.generate_cohort(count=req.count, seed=req.seed)
    created_patients = []
    skipped_count = 0

    for profile in cohort_profiles:
        # Check if already exists
        check_q = await db.execute(
            select(SyntheticPatient).where(SyntheticPatient.patient_code == profile.patient_code)
        )
        if check_q.scalar_one_or_none() is not None:
            skipped_count += 1
            continue

        patient = SyntheticPatient(
            patient_code=profile.patient_code,
            diabetes_type=profile.diabetes_type,
            age=profile.age,
            body_weight_kg=profile.body_weight_kg,
            basal_rate_synthetic=profile.basal_rate_synthetic,
            insulin_sensitivity_factor=profile.insulin_sensitivity_factor,
            carb_ratio=profile.carb_ratio,
            target_glucose_min=profile.target_glucose_min,
            target_glucose_max=profile.target_glucose_max,
        )
        db.add(patient)
        created_patients.append(patient)

    if created_patients:
        await db.commit()
        for p in created_patients:
            await db.refresh(p)

    await AuditService.log_event(
        db=db,
        action="COHORT_SEEDED",
        resource_type="synthetic_cohort",
        user_id=session.user_id,
        details={
            "requested_count": req.count,
            "created_count": len(created_patients),
            "skipped_count": skipped_count,
            "seed": req.seed
        }
    )

    return make_success_response(
        data={
            "created_count": len(created_patients),
            "skipped_count": skipped_count,
            "patient_codes": [p.patient_code for p in created_patients]
        },
        request=request
    )


@router.get("/{patient_identifier}", status_code=status.HTTP_200_OK)
async def get_patient_profile(
    patient_identifier: str,
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve demographic and metabolic profile of a specific synthetic patient.
    Accepts either UUID ID or human-readable patient_code (e.g., SYN-T1D-001).
    Enforces patient-level authorization and anti-caching headers.
    """
    add_cache_control_no_store(response)

    # Query by ID or patient_code
    query = select(SyntheticPatient).where(
        (SyntheticPatient.id == patient_identifier) |
        (SyntheticPatient.patient_code == patient_identifier)
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()

    if patient is None:
        raise NotFoundException(resource="SyntheticPatient", resource_id=patient_identifier)

    # Enforce patient scope
    enforce_patient_scope(session=session, patient_id=patient.id, patient_code=patient.patient_code)

    data = SyntheticPatientResponse.model_validate(patient).model_dump(mode="json")
    return make_success_response(data=data, request=request)
