"""
Tests for Liveness and Readiness Probes.
Verifies /health, /ready, /api/v1/health, /api/v1/ready, DB health, and degraded status codes.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_health_liveness_endpoints(client: AsyncClient):
    """Verifies that unversioned and versioned /health endpoints return 200 with status=healthy."""
    # 1. Unversioned root health
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "request_id" in data
    assert "X-Request-ID" in resp.headers

    # 2. Versioned /api/v1/health
    resp_v1 = await client.get("/api/v1/health")
    assert resp_v1.status_code == 200
    data_v1 = resp_v1.json()
    assert data_v1["status"] == "healthy"
    assert data_v1["app"] == "GlucoTwin AI"


@pytest.mark.asyncio
async def test_ready_endpoint_healthy(client: AsyncClient):
    """Verifies that /ready and /api/v1/ready return 200 when database and models are ready."""
    resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True
    assert data["components"]["database"]["connected"] is True
    assert data["components"]["model_integrity"]["status"] == "ready"
    assert data["components"]["model_integrity"]["guardrails_enforced"] is True

    # Versioned endpoint
    resp_v1 = await client.get("/api/v1/ready")
    assert resp_v1.status_code == 200
    assert resp_v1.json()["ready"] is True


@pytest.mark.asyncio
async def test_ready_endpoint_database_failure(client: AsyncClient):
    """Verifies that /ready returns 503 Service Unavailable when the database probe fails."""
    with patch("app.api.v1.ready.check_db_connectivity", return_value=False):
        resp = await client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["ready"] is False
        assert data["components"]["database"]["connected"] is False
