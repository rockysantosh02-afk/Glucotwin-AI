"""
GlucoTwin AI - Test Suite: Ambulatory Glucose Profile (AGP) Engine & Glycemic Metrics (Tier 2: Derived)
Validates mathematical precision of consensus metrics (TIR, TAR, TBR, GMI, CV%), modal percentiles,
persistence, anti-caching headers, and patient scope.
"""

from datetime import datetime, timedelta, timezone
from typing import NamedTuple
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.metrics import GlycemicMetric
from app.services.agp_engine import AGPEngine


class DummyReading(NamedTuple):
    timestamp: datetime
    glucose_mg_dl: float


def test_agp_mathematical_precision():
    """
    Verifies mathematical accuracy of AGP calculation against a controlled dataset:
    70 readings at 120 mg/dL (TIR)
    15 readings at 200 mg/dL (TAR Level 1)
     5 readings at 280 mg/dL (TAR Level 2)
     8 readings at 60 mg/dL  (TBR Level 1)
     2 readings at 50 mg/dL  (TBR Level 2)
    Total: 100 readings.
    """
    base_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = []

    values = (
        [120.0] * 70 +
        [200.0] * 15 +
        [280.0] * 5 +
        [60.0] * 8 +
        [50.0] * 2
    )

    for i, g in enumerate(values):
        ts = base_time + timedelta(minutes=i * 5)
        readings.append(DummyReading(timestamp=ts, glucose_mg_dl=g))

    metrics = AGPEngine.calculate_metrics(
        patient_id="test-pat-001",
        patient_code="SYN-T1D-001",
        readings=readings,
        window_start=base_time,
        window_end=base_time + timedelta(minutes=100 * 5)
    )

    assert metrics.total_readings == 100

    # Range percentages
    assert metrics.ranges.tir_percentage == 70.0
    assert metrics.ranges.tar_level1_percentage == 15.0
    assert metrics.ranges.tar_level2_percentage == 5.0
    assert metrics.ranges.tbr_level1_percentage == 8.0
    assert metrics.ranges.tbr_level2_percentage == 2.0

    # Sum of ranges should equal 100%
    total_range_sum = (
        metrics.ranges.tir_percentage +
        metrics.ranges.tar_level1_percentage +
        metrics.ranges.tar_level2_percentage +
        metrics.ranges.tbr_level1_percentage +
        metrics.ranges.tbr_level2_percentage
    )
    assert round(total_range_sum, 1) == 100.0

    # Known arithmetic mean:
    # (70*120 + 15*200 + 5*280 + 8*60 + 2*50) / 100 = (8400 + 3000 + 1400 + 480 + 100) / 100 = 13380 / 100 = 133.8 mg/dL
    assert metrics.mean_glucose_mg_dl == 133.8

    # GMI = 3.31 + 0.02392 * 133.8 = 3.31 + 3.2005 = 6.51 -> 6.5%
    expected_gmi = round(3.31 + 0.02392 * 133.8, 1)
    assert metrics.gmi_percentage == expected_gmi

    # Clinical Targets Evaluation:
    # TIR is 70% -> tir_above_70 is True
    assert metrics.clinical_targets_met.tir_above_70 is True
    # Total TBR is 8% + 2% = 10% (> 4%) -> tbr_below_4 is False
    assert metrics.clinical_targets_met.tbr_below_4 is False


def test_agp_empty_telemetry():
    """Verifies that AGP calculation gracefully handles zero telemetry readings without exceptions."""
    now = datetime.now(timezone.utc)
    metrics = AGPEngine.calculate_metrics(
        patient_id="empty-pat",
        patient_code="SYN-T1D-000",
        readings=[],
        window_start=now - timedelta(days=14),
        window_end=now
    )

    assert metrics.total_readings == 0
    assert metrics.mean_glucose_mg_dl == 0.0
    assert metrics.ranges.tir_percentage == 0.0
    assert metrics.clinical_targets_met.tir_above_70 is False


def test_agp_hourly_percentiles_ordering():
    """Verifies that modal hourly percentiles are calculated and ordered (p10 <= p25 <= p50 <= p75 <= p90)."""
    base_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = []

    # 48 hours of fluctuating readings
    import numpy as np
    rng = np.random.RandomState(42)
    for i in range(48 * 12):  # 5-min intervals
        ts = base_time + timedelta(minutes=i * 5)
        g = float(rng.uniform(65.0, 240.0))
        readings.append(DummyReading(timestamp=ts, glucose_mg_dl=g))

    metrics = AGPEngine.calculate_metrics(
        patient_id="hourly-pat",
        patient_code="SYN-T1D-001",
        readings=readings,
        window_start=base_time,
        window_end=base_time + timedelta(hours=48)
    )

    assert metrics.hourly_percentiles is not None
    assert len(metrics.hourly_percentiles) == 24

    for hp in metrics.hourly_percentiles:
        assert 0 <= hp.hour <= 23
        assert hp.p10 <= hp.p25 <= hp.p50 <= hp.p75 <= hp.p90


@pytest.mark.asyncio
async def test_get_metrics_endpoint_with_persistence(client: AsyncClient, db_session, demo_clinician_token: str):
    """
    Verifies the GET /api/v1/patients/{id}/metrics endpoint:
    - Ingests telemetry
    - Computes AGP metrics
    - Verifies persistence in glycemic_metrics table
    - Confirms anti-caching headers and envelope structure
    """
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}

    # 1. Seed patient
    seed_resp = await client.post("/api/v1/patients/seed-cohort", json={"count": 1, "seed": 42}, headers=headers)
    patient_code = seed_resp.json()["data"]["patient_codes"][0]

    # 2. Seed 7 days of telemetry
    await client.post(
        f"/api/v1/patients/{patient_code}/seed-telemetry",
        json={"days": 7, "seed": 42},
        headers=headers
    )

    # 3. Request metrics with persist=true
    metrics_resp = await client.get(
        f"/api/v1/patients/{patient_code}/metrics?window_days=7&persist=true",
        headers=headers
    )
    assert metrics_resp.status_code == 200
    assert "no-store" in metrics_resp.headers.get("Cache-Control", "")

    data = metrics_resp.json()["data"]
    assert data["total_readings"] == 7 * 288
    assert data["mean_glucose_mg_dl"] > 0.0
    assert data["ranges"]["tir_percentage"] > 0.0
    assert len(data["hourly_percentiles"]) == 24

    # 4. Verify persisted record in database
    persisted_q = await db_session.execute(select(GlycemicMetric))
    saved_records = persisted_q.scalars().all()
    assert len(saved_records) == 1
    assert saved_records[0].total_readings == 7 * 288
    assert saved_records[0].tir_percentage == data["ranges"]["tir_percentage"]


@pytest.mark.asyncio
async def test_metrics_unauthenticated_and_not_found(client: AsyncClient, demo_clinician_token: str):
    """Verifies that unauthenticated access returns 401 and non-existent patient returns 404."""
    # Unauthenticated
    resp = await client.get("/api/v1/patients/SYN-T1D-001/metrics")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"

    # Non-existent patient
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    resp_404 = await client.get("/api/v1/patients/SYN-T1D-999/metrics", headers=headers)
    assert resp_404.status_code == 404
    assert resp_404.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
