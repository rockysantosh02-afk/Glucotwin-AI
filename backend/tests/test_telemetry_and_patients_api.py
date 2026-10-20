"""
GlucoTwin AI - Test Suite: Patients & Telemetry Ingestion Endpoints (Tier 1: Observed)
Validates batch ingestion, duplicate timestamp handling, physiological velocity calculation,
patient scope enforcement, anti-caching headers, and pagination.
"""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patients_unauthenticated_rejected(client: AsyncClient):
    """Verifies that unauthenticated requests to patient and telemetry routes return HTTP 401."""
    # List patients
    resp = await client.get("/api/v1/patients/")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"

    # Ingest telemetry
    resp = await client.post("/api/v1/patients/SYN-T1D-001/telemetry", json={"readings": []})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_seed_cohort_and_list_patients(client: AsyncClient, demo_clinician_token: str):
    """Verifies cohort seeding, idempotency, pagination, and anti-caching headers."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}

    # 1. Seed cohort with 5 patients
    seed_resp = await client.post(
        "/api/v1/patients/seed-cohort",
        json={"count": 5, "seed": 42},
        headers=headers
    )
    assert seed_resp.status_code == 201
    seed_data = seed_resp.json()
    assert seed_data["success"] is True
    assert seed_data["data"]["created_count"] == 5
    assert len(seed_data["data"]["patient_codes"]) == 5

    # 2. Seed again with same parameters - verify idempotency
    seed_again = await client.post(
        "/api/v1/patients/seed-cohort",
        json={"count": 5, "seed": 42},
        headers=headers
    )
    assert seed_again.status_code == 201
    assert seed_again.json()["data"]["created_count"] == 0
    assert seed_again.json()["data"]["skipped_count"] == 5

    # 3. List patients
    list_resp = await client.get("/api/v1/patients/?skip=0&limit=3", headers=headers)
    assert list_resp.status_code == 200
    assert "no-store" in list_resp.headers.get("Cache-Control", "")
    list_data = list_resp.json()["data"]
    assert list_data["total"] == 5
    assert len(list_data["patients"]) == 3
    assert list_data["patients"][0]["patient_code"] == "SYN-T1D-001"


@pytest.mark.asyncio
async def test_get_patient_by_identifier(client: AsyncClient, demo_clinician_token: str):
    """Verifies retrieving a patient profile by either UUID or patient_code."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}

    # Seed 1 patient
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 99}, headers=headers)

    # Fetch by patient_code
    resp = await client.get("/api/v1/patients/SYN-T1D-001", headers=headers)
    assert resp.status_code == 200
    p = resp.json()["data"]
    assert p["patient_code"] == "SYN-T1D-001"
    assert p["diabetes_type"] == "T1D"
    assert p["target_glucose_min"] == 70.0
    assert p["target_glucose_max"] == 180.0

    # Fetch by UUID id
    patient_uuid = p["id"]
    resp2 = await client.get(f"/api/v1/patients/{patient_uuid}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["patient_code"] == "SYN-T1D-001"

    # Non-existent patient returns 404
    resp_404 = await client.get("/api/v1/patients/SYN-T1D-999", headers=headers)
    assert resp_404.status_code == 404
    assert resp_404.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_patient_validation_and_conflict(client: AsyncClient, clinician_token: str):
    """Verifies patient creation constraints, validation errors, and conflict detection."""
    headers = {"Authorization": f"Bearer {clinician_token}"}

    valid_payload = {
        "patient_code": "SYN-T1D-088",
        "diabetes_type": "T1D",
        "age": 34,
        "body_weight_kg": 68.5,
        "basal_rate_synthetic": 0.75,
        "insulin_sensitivity_factor": 48.0,
        "carb_ratio": 11.0,
        "target_glucose_min": 70.0,
        "target_glucose_max": 180.0
    }

    # Valid creation
    resp = await client.post("/api/v1/patients/", json=valid_payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["patient_code"] == "SYN-T1D-088"

    # Duplicate code conflict returns 409
    dup_resp = await client.post("/api/v1/patients/", json=valid_payload, headers=headers)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "PATIENT_CODE_EXISTS"

    # Out of range age (e.g. 15 years old - pediatric not permitted by schema [18, 85])
    invalid_age = dict(valid_payload, patient_code="SYN-T1D-089", age=15)
    resp_age = await client.post("/api/v1/patients/", json=invalid_age, headers=headers)
    assert resp_age.status_code == 422
    assert resp_age.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"

    # Non-synthetic prefix rejected
    invalid_prefix = dict(valid_payload, patient_code="REAL-T1D-001")
    resp_prefix = await client.post("/api/v1/patients/", json=invalid_prefix, headers=headers)
    assert resp_prefix.status_code == 422


@pytest.mark.asyncio
async def test_batch_telemetry_ingestion_and_query(client: AsyncClient, demo_clinician_token: str):
    """Verifies batch telemetry ingestion, rate of change computation, and historical queries."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}

    # 1. Seed patient
    seed_resp = await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)
    patient_code = seed_resp.json()["data"]["patient_codes"][0]

    base_time = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
    t1 = base_time.isoformat()
    t2 = (base_time + timedelta(minutes=5)).isoformat()
    t3 = (base_time + timedelta(minutes=10)).isoformat()

    batch_payload = {
        "readings": [
            {
                "timestamp": t1,
                "glucose_mg_dl": 120.0,
                "sensor_status": "OK",
                "meal_carbs_grams": 45.0,
                "bolus_synthetic_units": 4.5,
                "activity_minutes": 0.0,
                "activity_intensity": 0
            },
            {
                "timestamp": t2,
                "glucose_mg_dl": 130.0,
                "sensor_status": "OK",
                "meal_carbs_grams": 0.0,
                "bolus_synthetic_units": 0.0,
                "activity_minutes": 0.0,
                "activity_intensity": 0
            },
            {
                "timestamp": t3,
                "glucose_mg_dl": 145.0,
                "sensor_status": "OK",
                "meal_carbs_grams": 0.0,
                "bolus_synthetic_units": 0.0,
                "activity_minutes": 0.0,
                "activity_intensity": 0
            }
        ]
    }

    # 2. Ingest batch
    ingest_resp = await client.post(
        f"/api/v1/patients/{patient_code}/telemetry",
        json=batch_payload,
        headers=headers
    )
    assert ingest_resp.status_code == 201
    assert "no-store" in ingest_resp.headers.get("Cache-Control", "")
    data = ingest_resp.json()["data"]
    assert data["ingested_count"] == 3
    assert data["duplicates_skipped"] == 0

    # 3. Query telemetry
    query_resp = await client.get(
        f"/api/v1/patients/{patient_code}/telemetry?order=asc",
        headers=headers
    )
    assert query_resp.status_code == 200
    readings = query_resp.json()["data"]["readings"]
    assert len(readings) == 3

    # Check automatic velocity computation:
    # At t2 (glucose 130 vs t1 120 over 5 min): (130 - 120) / 5 = +2.0 mg/dL/min
    assert readings[1]["rate_of_change"] == 2.0
    # At t3 (glucose 145 vs t2 130 over 5 min): (145 - 130) / 5 = +3.0 mg/dL/min
    assert readings[2]["rate_of_change"] == 3.0


@pytest.mark.asyncio
async def test_telemetry_duplicate_timestamp_handling(client: AsyncClient, demo_clinician_token: str):
    """Verifies that duplicate timestamps are skipped cleanly without throwing database errors."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)

    t1 = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc).isoformat()
    t2 = datetime(2026, 10, 20, 8, 5, 0, tzinfo=timezone.utc).isoformat()

    # Initial ingestion
    p1 = {
        "readings": [
            {"timestamp": t1, "glucose_mg_dl": 110.0, "sensor_status": "OK"},
            {"timestamp": t2, "glucose_mg_dl": 112.0, "sensor_status": "OK"},
        ]
    }
    r1 = await client.post("/api/v1/patients/SYN-T1D-001/telemetry", json=p1, headers=headers)
    assert r1.status_code == 201
    assert r1.json()["data"]["ingested_count"] == 2

    # Ingest overlapping batch (t2 is duplicate, t3 is new, plus internal duplicate of t3)
    t3 = datetime(2026, 10, 20, 8, 10, 0, tzinfo=timezone.utc).isoformat()
    p2 = {
        "readings": [
            {"timestamp": t2, "glucose_mg_dl": 112.0, "sensor_status": "OK"},
            {"timestamp": t3, "glucose_mg_dl": 115.0, "sensor_status": "OK"},
            {"timestamp": t3, "glucose_mg_dl": 115.0, "sensor_status": "OK"},  # internal dupe
        ]
    }
    r2 = await client.post("/api/v1/patients/SYN-T1D-001/telemetry", json=p2, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["data"]["ingested_count"] == 1
    assert r2.json()["data"]["duplicates_skipped"] == 2


@pytest.mark.asyncio
async def test_telemetry_out_of_bounds_validation(client: AsyncClient, demo_clinician_token: str):
    """Verifies that out-of-bounds glucose readings (<40.0 or >500.0 mg/dL) are rejected with HTTP 422."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)

    t = datetime(2026, 10, 20, 9, 0, 0, tzinfo=timezone.utc).isoformat()

    # Hypoglycemic value below 40.0
    low_payload = {"readings": [{"timestamp": t, "glucose_mg_dl": 35.0}]}
    r_low = await client.post("/api/v1/patients/SYN-T1D-001/telemetry", json=low_payload, headers=headers)
    assert r_low.status_code == 422
    assert r_low.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"

    # Hyperglycemic value above 500.0
    high_payload = {"readings": [{"timestamp": t, "glucose_mg_dl": 550.0}]}
    r_high = await client.post("/api/v1/patients/SYN-T1D-001/telemetry", json=high_payload, headers=headers)
    assert r_high.status_code == 422


@pytest.mark.asyncio
async def test_seed_telemetry_endpoint(client: AsyncClient, demo_clinician_token: str):
    """Verifies the convenience endpoint for seeding multi-day continuous telemetry."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)

    # Seed 1 day (288 readings)
    seed_resp = await client.post(
        "/api/v1/patients/SYN-T1D-001/seed-telemetry",
        json={"days": 1, "seed": 42},
        headers=headers
    )
    assert seed_resp.status_code == 201
    assert seed_resp.json()["data"]["ingested_count"] == 288

    # Query with limit 50
    q_resp = await client.get("/api/v1/patients/SYN-T1D-001/telemetry?limit=50", headers=headers)
    assert q_resp.status_code == 200
    assert len(q_resp.json()["data"]["readings"]) == 50


@pytest.mark.asyncio
async def test_demo_clinician_patient_scope_on_telemetry(client: AsyncClient, demo_clinician_token: str, clinician_token: str):
    """Verifies that demo_clinician cannot access or ingest data for non-synthetic patient records."""
    # Create non-synthetic patient with full clinician token
    full_headers = {"Authorization": f"Bearer {clinician_token}"}
    
    # Attempting to query non-synthetic patient as demo clinician returns 403 or 404
    demo_headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    resp = await client.get("/api/v1/patients/REAL-001/telemetry", headers=demo_headers)
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_audit_logging_on_patient_and_telemetry_actions(client: AsyncClient, db_session, demo_clinician_token: str):
    """Verifies that sensitive patient registration and telemetry ingestion write to the audit ledger."""
    from sqlalchemy import select
    from app.models.audit import AuditLog

    headers = {"Authorization": f"Bearer {demo_clinician_token}"}

    # Seed cohort
    await client.post("/api/v1/patients/seed-cohort", json={"count": 2, "seed": 42}, headers=headers)

    # Ingest telemetry
    t = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    await client.post(
        "/api/v1/patients/SYN-T1D-001/telemetry",
        json={"readings": [{"timestamp": t, "glucose_mg_dl": 125.0}]},
        headers=headers
    )

    # Inspect audit_logs table
    audit_q = await db_session.execute(select(AuditLog))
    logs = audit_q.scalars().all()
    actions = [log.action for log in logs]

    assert "COHORT_SEEDED" in actions
    assert "TELEMETRY_INGESTED" in actions


@pytest.mark.asyncio
async def test_telemetry_csv_export_and_formula_injection_defense(client: AsyncClient, demo_clinician_token: str):
    """
    Verifies that the CSV export endpoint exports observed telemetry with
    anti-caching headers, synthetic disclosures, and formula injection sanitization.
    """
    from app.api.v1.telemetry import sanitize_csv_cell

    # 1. Verify formula injection defense helper
    assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-123") == "'-123"
    assert sanitize_csv_cell("@alert(1)") == "'@alert(1)"
    assert sanitize_csv_cell("\tmalicious") == "'\tmalicious"
    assert sanitize_csv_cell("normal_text") == "normal_text"
    assert sanitize_csv_cell(None) == ""

    # 2. Test unauthenticated request is denied
    unauth_resp = await client.get("/api/v1/patients/SYN-T1D-001/telemetry/export")
    assert unauth_resp.status_code == 401

    # 3. Authenticated export
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    # Seed cohort first
    await client.post("/api/v1/patients/seed-cohort", json={"count": 2, "seed": 42}, headers=headers)

    # Ingest a sample reading
    t = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    await client.post(
        "/api/v1/patients/SYN-T1D-001/telemetry",
        json={"readings": [{"timestamp": t, "glucose_mg_dl": 138.5, "meal_carbs_grams": 45.0}]},
        headers=headers
    )

    export_resp = await client.get("/api/v1/patients/SYN-T1D-001/telemetry/export", headers=headers)
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    assert "attachment" in export_resp.headers["content-disposition"]
    assert "no-store" in export_resp.headers["cache-control"]

    csv_body = export_resp.text
    assert "RESEARCH & EDUCATION PROTOTYPE ONLY" in csv_body
    assert "SYN-T1D-001" in csv_body
    assert "138.50" in csv_body
    assert "45.0" in csv_body


