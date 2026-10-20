"""
Tests for Patient-Level Scope Authorization, IDOR Prevention, and Anti-Caching Headers.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_demo_clinician_access_synthetic_patient(
    client: AsyncClient,
    demo_clinician_token: str
):
    """demo_clinician must be permitted to access synthetic patients prefixed with SYN-*."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    resp = await client.get("/api/v1/security-test/patient-scope/SYN-T1D-001", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["patient_code"] == "SYN-T1D-001"

    # Verify anti-caching headers (Cache-Control: no-store)
    assert "Cache-Control" in resp.headers
    assert "no-store" in resp.headers["Cache-Control"]
    assert "no-cache" in resp.headers["Cache-Control"]


@pytest.mark.asyncio
async def test_demo_clinician_blocked_from_non_synthetic_patient_idor(
    client: AsyncClient,
    demo_clinician_token: str
):
    """
    IDOR / Scope Protection:
    Attempt by demo_clinician to access non-synthetic patient ID must be strictly blocked with HTTP 403.
    """
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    resp = await client.get("/api/v1/security-test/patient-scope/REAL-CLINICAL-999", headers=headers)
    assert resp.status_code == 403
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "DEMO_SCOPE_VIOLATION"


@pytest.mark.asyncio
async def test_full_clinician_allowed_on_standard_patient(
    client: AsyncClient,
    clinician_token: str
):
    """Full clinician role is not blocked by synthetic demo prefix restriction."""
    headers = {"Authorization": f"Bearer {clinician_token}"}
    resp = await client.get("/api/v1/security-test/patient-scope/SYN-T1D-002", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
