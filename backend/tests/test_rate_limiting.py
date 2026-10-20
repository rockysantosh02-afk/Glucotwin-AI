"""
Tests for Client Rate Limiting and HTTP 429 Retry-After Headers.
"""

import pytest
from httpx import AsyncClient

from app.core.security_middleware import rate_limiter


@pytest.mark.asyncio
async def test_rate_limiting_enforcement(
    client: AsyncClient,
    clinician_token: str
):
    """
    Verifies that requests exceeding rate limits receive HTTP 429 with Retry-After header.
    """
    # Reset rate limiter history for clean test run
    rate_limiter.reset()

    headers = {"Authorization": f"Bearer {clinician_token}"}
    endpoint = "/api/v1/security-test/rate-limited-action"

    # Limit on test route is 3 requests per minute
    # 1st request -> 200
    r1 = await client.get(endpoint, headers=headers)
    assert r1.status_code == 200

    # 2nd request -> 200
    r2 = await client.get(endpoint, headers=headers)
    assert r2.status_code == 200

    # 3rd request -> 200
    r3 = await client.get(endpoint, headers=headers)
    assert r3.status_code == 200

    # 4th request -> 429 RATE_LIMIT_EXCEEDED
    r4 = await client.get(endpoint, headers=headers)
    assert r4.status_code == 429
    data = r4.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in r4.headers
    retry_after_val = int(r4.headers["Retry-After"])
    assert retry_after_val > 0
