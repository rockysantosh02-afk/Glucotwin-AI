"""
Tests for Cryptographic Token Validation, Forgery Detection, Expiration, alg:none, and Revocation.
"""

import time
import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, decode_and_validate_token


@pytest.mark.asyncio
async def test_create_and_validate_demo_token():
    """Verifies that create_access_token creates a cryptographically valid token with required claims."""
    res = create_access_token(
        subject="researcher-1",
        role="demo_clinician",
        sandbox_id="sandbox-demo-t1d"
    )
    token = res["access_token"]
    assert token is not None

    payload = decode_and_validate_token(token)
    assert payload["sub"] == "researcher-1"
    assert payload["role"] == "demo_clinician"
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["aud"] == settings.JWT_AUDIENCE
    assert "jti" in payload
    assert payload["exp"] > time.time()


@pytest.mark.asyncio
async def test_forged_token_signature_rejected(client: AsyncClient):
    """Verifies that tokens signed with an unauthorized secret are rejected with HTTP 401."""
    forged_claims = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": "attacker",
        "jti": "tok-forged",
        "role": "admin",
        "iat": int(time.time()),
        "nbf": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    forged_token = jwt.encode(forged_claims, "attacker_wrong_secret_key_1234567890", algorithm="HS256")

    headers = {"Authorization": f"Bearer {forged_token}"}
    resp = await client.get("/api/v1/security-test/admin-only", headers=headers)
    assert resp.status_code == 401
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] in ("TOKEN_VERIFICATION_FAILED", "UNAUTHENTICATED")


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    """Verifies that expired tokens are strictly rejected with HTTP 401."""
    expired_claims = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": "user-expired",
        "jti": "tok-expired",
        "role": "clinician",
        "iat": int(time.time()) - 7200,
        "nbf": int(time.time()) - 7200,
        "exp": int(time.time()) - 3600  # Expired 1 hour ago
    }
    expired_token = jwt.encode(expired_claims, settings.SECRET_KEY, algorithm="HS256")

    headers = {"Authorization": f"Bearer {expired_token}"}
    resp = await client.get("/api/v1/security-test/clinician-only", headers=headers)
    assert resp.status_code == 401
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_alg_none_token_rejected(client: AsyncClient):
    """Verifies that unsecure alg:none attack tokens are strictly rejected."""
    import base64
    import json

    unsecure_claims = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": "attacker",
        "jti": "tok-none",
        "role": "admin",
        "iat": int(time.time()),
        "nbf": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    # Manually construct an unsigned JWT token with header {"alg": "none"}
    header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(unsecure_claims).encode()).decode().rstrip("=")
    alg_none_token = f"{header_b64}.{payload_b64}."

    headers = {"Authorization": f"Bearer {alg_none_token}"}
    resp = await client.get("/api/v1/security-test/admin-only", headers=headers)
    assert resp.status_code == 401
    data = resp.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_wrong_issuer_and_audience_rejected(client: AsyncClient):
    """Verifies that tokens with incorrect issuer or audience claims fail validation."""
    wrong_claims = {
        "iss": "rogue-issuer",
        "aud": "rogue-audience",
        "sub": "user-rogue",
        "jti": "tok-rogue",
        "role": "admin",
        "iat": int(time.time()),
        "nbf": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    rogue_token = jwt.encode(wrong_claims, settings.SECRET_KEY, algorithm="HS256")

    headers = {"Authorization": f"Bearer {rogue_token}"}
    resp = await client.get("/api/v1/security-test/admin-only", headers=headers)
    assert resp.status_code == 401
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_TOKEN_CLAIMS"


@pytest.mark.asyncio
async def test_demo_session_endpoint_and_logout_revocation(client: AsyncClient):
    """
    Tests complete demo session lifecycle:
    1. POST /api/v1/auth/demo-session issues short-lived token
    2. Token successfully accesses protected session endpoint
    3. POST /api/v1/auth/logout revokes the token
    4. Subsequent access with revoked token is denied (401 TOKEN_REVOKED)
    """
    # 1. Request demo session
    resp = await client.post("/api/v1/auth/demo-session", json={"clinician_name": "Dr. Test"})
    assert resp.status_code == 201
    auth_data = resp.json()["data"]
    token = auth_data["access_token"]
    assert auth_data["role"] == "demo_clinician"
    assert auth_data["sandbox_id"] == settings.DEMO_SANDBOX_ID

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Access session endpoint successfully
    session_resp = await client.get("/api/v1/auth/session", headers=headers)
    assert session_resp.status_code == 200
    assert session_resp.json()["data"]["role"] == "demo_clinician"

    # 3. Logout / revoke session
    logout_resp = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert "revoked_token_id" in logout_resp.json()["data"]

    # 4. Attempt to use revoked token must fail with 401 TOKEN_REVOKED
    post_logout_resp = await client.get("/api/v1/auth/session", headers=headers)
    assert post_logout_resp.status_code == 401
    error_data = post_logout_resp.json()
    assert error_data["error"]["code"] == "TOKEN_REVOKED"
