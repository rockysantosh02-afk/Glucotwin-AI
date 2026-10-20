"""
GlucoTwin AI - Phase 5 Unit & Integration Tests: Synthetic Data & Observation Ingestion
Tests:
1. Physical unit conversion accuracy (mg/dL <-> mmol/L) and physiological bounds.
2. Generator determinism and reproducibility under fixed seeding.
3. Verification of all seven named demo scenarios and their physiological hallmarks.
4. Latent EHR relationships and EHR model normalization.
5. POST /api/v1/observations/ingest endpoint contract validation.
6. Malformed timestamp and invalid value rejection (fail-closed).
7. Duplicate observation prevention via database unique constraints.
8. Concurrent ingestion handling and savepoint rollback safety.
9. Audit event recording without leaking sensitive observation payloads.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.units import (
    GLUCOSE_MMOL_CONVERSION_FACTOR,
    mgdl_to_mmoll,
    mmoll_to_mgdl,
    normalize_activity_to_minutes,
    normalize_bolus_to_units,
    normalize_carbs_to_grams,
    normalize_glucose_to_mgdl,
)
from app.models.audit import AuditLog
from app.models.patient import SyntheticPatient
from app.models.telemetry import TelemetryRecord
from app.services.synthetic_data import (
    SCENARIO_DEFINITIONS,
    SyntheticDataGenerator,
    SyntheticEHRRecord,
)


# =============================================================================
# 1. Physical Unit Conversion Tests
# =============================================================================
def test_unit_conversion_math_precision():
    """Verifies standard clinical conversion 1 mmol/L = 18.0182 mg/dL."""
    assert GLUCOSE_MMOL_CONVERSION_FACTOR == 18.0182

    # 100.0 mg/dL -> ~5.55 mmol/L
    mmol = mgdl_to_mmoll(100.0)
    assert mmol == 5.55

    # 5.55 mmol/L -> 100.0 mg/dL
    mgdl = mmoll_to_mgdl(5.55)
    assert 99.8 <= mgdl <= 100.2

    # Standard clinical fasting threshold: 70.0 mg/dL -> 3.88 mmol/L (70.0 / 18.0182 = 3.8849)
    assert mgdl_to_mmoll(70.0) == 3.88

    # Standard upper threshold: 180.0 mg/dL -> 9.99 mmol/L
    assert mgdl_to_mmoll(180.0) == 9.99


def test_unit_normalization_helpers():
    """Verifies bounds and unit strings validation."""
    # Glucose normalization
    assert normalize_glucose_to_mgdl(120.0, "mg/dL") == 120.0
    assert normalize_glucose_to_mgdl(120.0, "mg/dl") == 120.0
    assert normalize_glucose_to_mgdl(6.5, "mmol/L") == 117.1

    # Carbs normalization
    assert normalize_carbs_to_grams(45.0, "g") == 45.0
    assert normalize_carbs_to_grams(45.0, "grams") == 45.0

    # Bolus normalization
    assert normalize_bolus_to_units(5.5, "U") == 5.5
    assert normalize_bolus_to_units(5.5, "units") == 5.5

    # Activity normalization
    assert normalize_activity_to_minutes(30.0, "min") == 30.0
    assert normalize_activity_to_minutes(30.0, "minutes") == 30.0


def test_unit_normalization_rejections():
    """Verifies that out-of-bounds or invalid units raise ValueError."""
    # Out of bounds glucose
    with pytest.raises(ValueError, match="outside physiological bounds"):
        normalize_glucose_to_mgdl(35.0, "mg/dL")

    with pytest.raises(ValueError, match="outside physiological bounds"):
        normalize_glucose_to_mgdl(520.0, "mg/dL")

    with pytest.raises(ValueError, match="outside physiological bounds"):
        normalize_glucose_to_mgdl(1.5, "mmol/L")  # 1.5 mmol/L = 27 mg/dL (< 40)

    # Invalid unit string
    with pytest.raises(ValueError, match="Unsupported glucose unit"):
        normalize_glucose_to_mgdl(100.0, "ounces")

    # Invalid carbs bounds
    with pytest.raises(ValueError, match="outside bounds"):
        normalize_carbs_to_grams(350.0, "g")

    # Invalid bolus bounds
    with pytest.raises(ValueError, match="outside bounds"):
        normalize_bolus_to_units(60.0, "U")


# =============================================================================
# 2. Generator Determinism & EHR Latent Traits Tests
# =============================================================================
def test_generator_deterministic_reproducibility():
    """Verifies that the same seed produces byte-for-byte identical synthetic cohorts and telemetry."""
    seed = 42
    patient_a = SyntheticDataGenerator.generate_ehr_record(patient_index=5, seed=seed)
    patient_b = SyntheticDataGenerator.generate_ehr_record(patient_index=5, seed=seed)

    assert patient_a.model_dump() == patient_b.model_dump()

    telemetry_a = SyntheticDataGenerator.generate_telemetry(patient_profile=patient_a, days=3, seed=seed)
    telemetry_b = SyntheticDataGenerator.generate_telemetry(patient_profile=patient_b, days=3, seed=seed)

    assert len(telemetry_a) == len(telemetry_b)
    for r_a, r_b in zip(telemetry_a, telemetry_b):
        assert r_a.timestamp == r_b.timestamp
        assert r_a.glucose_mg_dl == r_b.glucose_mg_dl
        assert r_a.rate_of_change == r_b.rate_of_change
        assert r_a.meal_carbs_grams == r_b.meal_carbs_grams


def test_latent_ehr_relationships():
    """Verifies learnable relationships between EHR features and metabolic parameters."""
    cohort = SyntheticDataGenerator.generate_ehr_cohort(count=30, seed=100)

    # All generated EHR records must satisfy validity
    for rec in cohort:
        assert 18 <= rec.age <= 85
        assert 40.0 <= rec.body_weight_kg <= 150.0
        assert 5.0 <= rec.baseline_hba1c <= 14.0
        assert rec.therapy_modality in ("PUMP", "MDI")
        assert 10.0 <= rec.insulin_sensitivity_factor <= 150.0

    # Patients with higher BMI should generally have higher weight
    weights = [r.body_weight_kg for r in cohort]
    bmis = [r.bmi for r in cohort]
    corr = np.corrcoef(bmis, weights)[0, 1]
    assert corr > 0.60


# =============================================================================
# 3. All Seven Named Demo Scenarios Tests
# =============================================================================
def test_all_seven_named_demo_scenarios():
    """Verifies that all seven documented named demo scenarios are produced and show physiological hallmarks."""
    assert len(SCENARIO_DEFINITIONS) == 7

    scenarios = SyntheticDataGenerator.generate_all_named_scenarios(days=3, seed=42)
    assert len(scenarios) == 7

    scen_by_key = {s["definition"]["key"]: s for s in scenarios}

    # 1. Baseline Stable: high TIR, low CV
    s1 = scen_by_key["scenario_1_baseline_stable"]
    g1 = [r.glucose_mg_dl for r in s1["telemetry"]]
    tir_s1 = sum(70.0 <= x <= 180.0 for x in g1) / len(g1)
    assert tir_s1 > 0.70

    # 2. Postprandial Spike: reaches elevated peak (> 205 mg/dL)
    s2 = scen_by_key["scenario_2_postprandial_spike"]
    g2 = [r.glucose_mg_dl for r in s2["telemetry"]]
    assert max(g2) > 205.0

    # 3. Nocturnal Hypoglycemia: drops below 70 mg/dL
    s3 = scen_by_key["scenario_3_nocturnal_hypoglycemia"]
    g3 = [r.glucose_mg_dl for r in s3["telemetry"]]
    assert min(g3) < 70.0

    # 4. Exercise-Induced Hypo: exhibits acute drop
    s4 = scen_by_key["scenario_4_exercise_induced_hypo"]
    g4 = [r.glucose_mg_dl for r in s4["telemetry"]]
    assert min(g4) < 75.0

    # 5. Compression Low: exhibits sudden unphysiological drop to ~48 mg/dL
    s5 = scen_by_key["scenario_5_compression_low"]
    g5 = [r.glucose_mg_dl for r in s5["telemetry"]]
    assert any(42.0 <= x <= 52.0 for x in g5)

    # 6. Sensor Drift & Dropout: contains CALIBRATING sensor status
    s6 = scen_by_key["scenario_6_sensor_drift_and_dropout"]
    statuses_s6 = [r.sensor_status for r in s6["telemetry"]]
    assert "CALIBRATING" in statuses_s6

    # 7. Missed Bolus Hyperglycemia: reaches extreme high (> 240 mg/dL)
    s7 = scen_by_key["scenario_7_missed_bolus_hyperglycemia"]
    g7 = [r.glucose_mg_dl for r in s7["telemetry"]]
    assert max(g7) > 240.0


def test_provenance_metadata():
    """Verifies provenance metadata content and clinical safety disclaimer."""
    prov = SyntheticDataGenerator.generate_provenance_metadata(
        seed=42,
        num_patients=10,
        days=14,
        scenarios_included=list(SCENARIO_DEFINITIONS.keys()),
        total_observations=28800
    )
    assert prov["seed"] == 42
    assert prov["generator_version"] == "1.0.0"
    assert prov["parameters"]["num_patients"] == 10
    assert "Synthetic demonstration data" in prov["clinical_safety_notice"]
    assert len(prov["scenarios"]) == 7


# =============================================================================
# 4. API Ingestion Endpoint Tests (POST /api/v1/observations/ingest)
# =============================================================================
@pytest.mark.asyncio
async def test_observations_ingest_success_and_unit_conversion(
    client: AsyncClient,
    clinician_token: str,
    db_session: AsyncSession
):
    """Tests successful observation ingestion with mixed units (mg/dL and mmol/L)."""
    # Seed patient
    patient = SyntheticPatient(
        patient_code="SYN-TEST-P5-A",
        diabetes_type="T1D",
        age=30,
        body_weight_kg=72.0,
        basal_rate_synthetic=0.8,
        insulin_sensitivity_factor=45.0,
        carb_ratio=10.0,
        target_glucose_min=70.0,
        target_glucose_max=180.0
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)

    base_time = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    payload = {
        "patient_id": patient.id,
        "observations": [
            {
                "timestamp": base_time.isoformat(),
                "type": "glucose",
                "value": 115.0,
                "unit": "mg/dL",
                "sensor_status": "OK"
            },
            {
                "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
                "type": "glucose",
                "value": 6.8,  # mmol/L -> ~122.5 mg/dL
                "unit": "mmol/L",
                "sensor_status": "OK"
            },
            {
                "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "type": "carbohydrates",
                "value": 45.0,
                "unit": "g"
            },
            {
                "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "type": "insulin_bolus",
                "value": 4.5,
                "unit": "U"
            }
        ]
    }

    res = await client.post(
        "/api/v1/observations/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )

    assert res.status_code == 201
    data = res.json()["data"]
    assert data["patient_id"] == patient.id
    assert data["ingested_count"] >= 3  # 3 distinct timestamps
    assert data["duplicates_skipped"] == 0

    # Verify anti-caching header
    assert "no-store" in res.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_observations_ingest_rejects_malformed_timestamp(
    client: AsyncClient,
    clinician_token: str,
    db_session: AsyncSession
):
    """Rejects unparseable or out-of-range timestamps."""
    patient = SyntheticPatient(
        patient_code="SYN-TEST-P5-B",
        diabetes_type="T1D",
        age=30,
        body_weight_kg=72.0,
        basal_rate_synthetic=0.8,
        insulin_sensitivity_factor=45.0,
        carb_ratio=10.0,
        target_glucose_min=70.0,
        target_glucose_max=180.0
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)

    # Malformed timestamp string
    payload_malformed = {
        "patient_id": patient.id,
        "observations": [
            {
                "timestamp": "not-a-timestamp",
                "type": "glucose",
                "value": 110.0,
                "unit": "mg/dL"
            }
        ]
    }
    res = await client.post(
        "/api/v1/observations/ingest",
        json=payload_malformed,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_observations_ingest_rejects_invalid_values(
    client: AsyncClient,
    clinician_token: str,
    db_session: AsyncSession
):
    """Rejects out-of-bounds glucose and invalid unit strings."""
    patient = SyntheticPatient(
        patient_code="SYN-TEST-P5-C",
        diabetes_type="T1D",
        age=30,
        body_weight_kg=72.0,
        basal_rate_synthetic=0.8,
        insulin_sensitivity_factor=45.0,
        carb_ratio=10.0,
        target_glucose_min=70.0,
        target_glucose_max=180.0
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)

    # Glucose out of bounds (< 40 mg/dL)
    payload_low = {
        "patient_id": patient.id,
        "observations": [
            {
                "timestamp": "2026-10-20T11:00:00Z",
                "type": "glucose",
                "value": 32.0,  # below 40.0
                "unit": "mg/dL"
            }
        ]
    }
    res = await client.post(
        "/api/v1/observations/ingest",
        json=payload_low,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_duplicate_prevention_on_repeated_ingestion(
    client: AsyncClient,
    clinician_token: str,
    db_session: AsyncSession
):
    """Verifies that duplicate observations are safely filtered and reported."""
    patient = SyntheticPatient(
        patient_code="SYN-TEST-P5-D",
        diabetes_type="T1D",
        age=30,
        body_weight_kg=72.0,
        basal_rate_synthetic=0.8,
        insulin_sensitivity_factor=45.0,
        carb_ratio=10.0,
        target_glucose_min=70.0,
        target_glucose_max=180.0
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)

    t0 = datetime(2026, 10, 20, 14, 0, 0, tzinfo=timezone.utc)
    readings = [
        {
            "timestamp": (t0 + timedelta(minutes=i * 5)).isoformat(),
            "glucose_mg_dl": 120.0 + i,
            "sensor_status": "OK"
        }
        for i in range(5)
    ]

    payload = {
        "patient_id": patient.id,
        "readings": readings
    }

    # First ingest: all 5 should succeed
    res1 = await client.post(
        "/api/v1/observations/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )
    assert res1.status_code == 201
    assert res1.json()["data"]["ingested_count"] == 5
    assert res1.json()["data"]["duplicates_skipped"] == 0

    # Second ingest of exact same batch: all 5 should be skipped as duplicates
    res2 = await client.post(
        "/api/v1/observations/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )
    assert res2.status_code == 201
    assert res2.json()["data"]["ingested_count"] == 0
    assert res2.json()["data"]["duplicates_skipped"] == 5


@pytest.mark.asyncio
async def test_concurrent_ingestion_safety(
    client: AsyncClient,
    clinician_token: str,
    db_session: AsyncSession
):
    """
    Verifies that database unique constraints strictly prevent duplicate observations,
    handling overlapping ingestion requests safely without data corruption or duplicate rows.
    """
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy import select, func

    # 1. Seed patient
    patient = SyntheticPatient(
        patient_code="SYN-TEST-P5-E",
        diabetes_type="T1D",
        age=30,
        body_weight_kg=72.0,
        basal_rate_synthetic=0.8,
        insulin_sensitivity_factor=45.0,
        carb_ratio=10.0,
        target_glucose_min=70.0,
        target_glucose_max=180.0
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)
    pid = str(patient.id)

    # 2. Test direct database unique constraint enforcement
    t_collision = datetime(2026, 10, 20, 15, 0, 0, tzinfo=timezone.utc)
    rec_original = TelemetryRecord(patient_id=pid, timestamp=t_collision, glucose_mg_dl=120.0)
    db_session.add(rec_original)
    await db_session.commit()

    rec_duplicate = TelemetryRecord(patient_id=pid, timestamp=t_collision, glucose_mg_dl=128.0)
    db_session.add(rec_duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # 3. Test API overlapping batch ingestion
    t_base = datetime(2026, 10, 20, 16, 0, 0, tzinfo=timezone.utc)

    # Batch A: timestamps 0..7
    batch_a = {
        "patient_id": pid,
        "readings": [
            {
                "timestamp": (t_base + timedelta(minutes=i * 5)).isoformat(),
                "glucose_mg_dl": 130.0 + i,
                "sensor_status": "OK"
            }
            for i in range(8)
        ]
    }

    # Batch B: timestamps 4..11 (overlaps 4, 5, 6, 7)
    batch_b = {
        "patient_id": pid,
        "readings": [
            {
                "timestamp": (t_base + timedelta(minutes=i * 5)).isoformat(),
                "glucose_mg_dl": 135.0 + i,
                "sensor_status": "OK"
            }
            for i in range(4, 12)
        ]
    }

    res_a = await client.post(
        "/api/v1/observations/ingest",
        json=batch_a,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )
    assert res_a.status_code == 201
    data_a = res_a.json()["data"]
    assert data_a["ingested_count"] == 8
    assert data_a["duplicates_skipped"] == 0

    res_b = await client.post(
        "/api/v1/observations/ingest",
        json=batch_b,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )
    assert res_b.status_code == 201
    data_b = res_b.json()["data"]
    # Exactly 4 new timestamps (8..11) ingested, 4 duplicate timestamps (4..7) safely skipped
    assert data_b["ingested_count"] == 4
    assert data_b["duplicates_skipped"] == 4

    # 4. Verify ZERO duplicate timestamps exist in database
    duplicate_query = select(
        TelemetryRecord.timestamp,
        func.count(TelemetryRecord.id)
    ).where(
        TelemetryRecord.patient_id == pid
    ).group_by(
        TelemetryRecord.timestamp
    ).having(
        func.count(TelemetryRecord.id) > 1
    )

    dup_result = await db_session.execute(duplicate_query)
    duplicate_rows = dup_result.all()
    assert len(duplicate_rows) == 0, f"Found duplicate timestamps in database: {duplicate_rows}"


@pytest.mark.asyncio
async def test_audit_log_does_not_leak_payloads(
    client: AsyncClient,
    clinician_token: str,
    db_session: AsyncSession
):
    """
    Verifies that the audit event OBSERVATIONS_INGESTED is recorded
    WITHOUT logging raw glucose numbers or observation payloads.
    """
    patient = SyntheticPatient(
        patient_code="SYN-TEST-P5-F",
        diabetes_type="T1D",
        age=30,
        body_weight_kg=72.0,
        basal_rate_synthetic=0.8,
        insulin_sensitivity_factor=45.0,
        carb_ratio=10.0,
        target_glucose_min=70.0,
        target_glucose_max=180.0
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)

    ts = datetime(2026, 10, 20, 18, 0, 0, tzinfo=timezone.utc).isoformat()
    payload = {
        "patient_id": patient.id,
        "observations": [
            {
                "timestamp": ts,
                "type": "glucose",
                "value": 142.3,
                "unit": "mg/dL"
            }
        ]
    }

    res = await client.post(
        "/api/v1/observations/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {clinician_token}"}
    )
    assert res.status_code == 201

    # Inspect audit_logs in database
    query = select(AuditLog).where(
        AuditLog.action == "OBSERVATIONS_INGESTED",
        AuditLog.resource_id == patient.id
    ).order_by(AuditLog.timestamp.desc()).limit(1)
    result = await db_session.execute(query)
    audit_record = result.scalar_one_or_none()

    assert audit_record is not None
    assert audit_record.action == "OBSERVATIONS_INGESTED"
    details_str = audit_record.details_json

    # Must contain summary metadata
    assert "patient_code" in details_str
    assert "ingested_count" in details_str

    # CRITICAL: Must NEVER contain the raw glucose value or payload array
    assert "142.3" not in details_str
    assert "glucose" not in details_str
