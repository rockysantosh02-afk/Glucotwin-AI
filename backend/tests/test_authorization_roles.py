"""
Tests for Centralized Deny-by-Default Role Authorization.
Verifies access controls for demo_clinician, clinician, and admin roles.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unauthenticated_request_denied(client: AsyncClient):
    """Protected routes must deny unauthenticated requests with HTTP 401."""
    resp = await client.get("/api/v1/security-test/clinician-only")
    assert resp.status_code == 401
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_demo_clinician_denied_on_clinician_only_route(
    client: AsyncClient,
    demo_clinician_token: str
):
    """demo_clinician role must be denied access to full clinician endpoints with HTTP 403."""
    headers = {"Authorization": f"Bearer {demo_clinician_token}"}
    resp = await client.get("/api/v1/security-test/clinician-only", headers=headers)
    assert resp.status_code == 403
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_clinician_allowed_on_clinician_route(
    client: AsyncClient,
    clinician_token: str
):
    """Verified clinician role must be permitted on clinician endpoints with HTTP 200."""
    headers = {"Authorization": f"Bearer {clinician_token}"}
    resp = await client.get("/api/v1/security-test/clinician-only", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["role"] == "clinician"


@pytest.mark.asyncio
async def test_clinician_denied_on_admin_only_route(
    client: AsyncClient,
    clinician_token: str
):
    """Clinician role must be denied access to admin endpoints with HTTP 403."""
    headers = {"Authorization": f"Bearer {clinician_token}"}
    resp = await client.get("/api/v1/security-test/admin-only", headers=headers)
    assert resp.status_code == 403
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_admin_allowed_on_all_protected_routes(
    client: AsyncClient,
    admin_token: str
):
    """Admin role must have access to both admin and clinician endpoints with HTTP 200."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin on admin route
    admin_resp = await client.get("/api/v1/security-test/admin-only", headers=headers)
    assert admin_resp.status_code == 200
    assert admin_resp.json()["success"] is True

    # Admin on clinician route
    clinician_resp = await client.get("/api/v1/security-test/clinician-only", headers=headers)
    assert clinician_resp.status_code == 200
    assert clinician_resp.json()["success"] is True
