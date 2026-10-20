"""
Tests for Defensive Security Headers, Trusted Host Checks, and Exact-Origin CORS.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_defensive_security_headers_present(client: AsyncClient):
    """Verifies that all defensive security headers are applied to outgoing responses."""
    resp = await client.get("/health")
    assert resp.status_code == 200

    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")


@pytest.mark.asyncio
async def test_trusted_host_validation(client: AsyncClient):
    """Verifies that requests with an unauthorized Host header are rejected with HTTP 400."""
    untrusted_headers = {"Host": "attacker.malicious.com"}
    resp = await client.get("/health", headers=untrusted_headers)
    assert resp.status_code == 400
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_HOST_HEADER"


@pytest.mark.asyncio
async def test_exact_origin_cors_allowed_and_disallowed(client: AsyncClient):
    """
    Verifies that preflight / CORS requests from configured origins are allowed,
    while disallowed origins do not receive permissive CORS headers.
    """
    allowed_origin = "http://localhost:5173"
    disallowed_origin = "https://evil-phishing-site.com"

    # 1. Allowed origin preflight OPTIONS request
    allowed_headers = {
        "Origin": allowed_origin,
        "Access-Control-Request-Method": "GET"
    }
    resp_allowed = await client.options("/api/v1/health", headers=allowed_headers)
    assert resp_allowed.status_code == 200
    assert resp_allowed.headers.get("access-control-allow-origin") == allowed_origin

    # 2. Disallowed origin request
    disallowed_headers = {
        "Origin": disallowed_origin,
        "Access-Control-Request-Method": "GET"
    }
    resp_disallowed = await client.options("/api/v1/health", headers=disallowed_headers)
    # The CORS middleware must NOT echo the disallowed origin
    assert resp_disallowed.headers.get("access-control-allow-origin") != disallowed_origin
