"""
GlucoTwin AI - Security & Cryptographic Token Primitives
Enforces strict JWT issuer, audience, expiry, token ID (jti), algorithm validation, and revocation.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.errors import AppException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory token revocation registry (tracks revoked jti and expiration)
# In production, this can be backed by Redis or an audit/revocation table.
_REVOKED_TOKENS: Dict[str, float] = {}


def clean_expired_revocations() -> None:
    """Removes expired entries from the revocation registry to prevent memory growth."""
    now = time.time()
    expired_keys = [jti for jti, exp in _REVOKED_TOKENS.items() if exp < now]
    for key in expired_keys:
        _REVOKED_TOKENS.pop(key, None)


def revoke_token(jti: str, expires_at: float) -> None:
    """Marks a token ID (jti) as revoked until its natural expiration."""
    clean_expired_revocations()
    _REVOKED_TOKENS[jti] = expires_at


def is_token_revoked(jti: str) -> bool:
    """Checks whether a token ID has been revoked."""
    clean_expired_revocations()
    return jti in _REVOKED_TOKENS


def hash_password(password: str) -> str:
    """Hashes a raw password using bcrypt with standard salt rounds."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    role: str = "demo_clinician",
    scope: str = "synthetic:read synthetic:simulate",
    sandbox_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> Dict[str, Any]:
    """
    Creates a signed JWT with standard claims: iss, aud, exp, nbf, iat, jti, sub, role, scope.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = f"tok-{uuid.uuid4().hex}"

    claims = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": subject,
        "jti": jti,
        "role": role,
        "scope": scope,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if sandbox_id:
        claims["sandbox_id"] = sandbox_id

    # Enforce strict HS256 algorithm
    encoded_token = jwt.encode(
        claims,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return {
        "access_token": encoded_token,
        "token_type": "bearer",
        "expires_in_seconds": int((expire - now).total_seconds()),
        "jti": jti,
        "claims": claims
    }


def decode_and_validate_token(token: str) -> Dict[str, Any]:
    """
    Decodes and strictly validates a JWT:
    - Enforces algorithm == 'HS256' (rejects alg:none and RSA confusion)
    - Verifies issuer and audience
    - Verifies expiration and nbf
    - Checks revocation registry
    Raises AppException with HTTP 401 if invalid.
    """
    if not token or not isinstance(token, str):
        raise AppException(
            code="INVALID_TOKEN",
            message="Bearer token is missing or malformed.",
            status_code=401
        )

    try:
        # Strict validation: explicit algorithm, audience, and issuer checking
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
                "require_exp": True,
                "require_iat": True,
                "require_nbf": True,
            }
        )
    except jwt.ExpiredSignatureError:
        raise AppException(
            code="TOKEN_EXPIRED",
            message="The session token has expired. Please re-authenticate.",
            status_code=401
        )
    except jwt.JWTClaimsError as claim_err:
        raise AppException(
            code="INVALID_TOKEN_CLAIMS",
            message=f"Token claim verification failed: {claim_err}",
            status_code=401
        )
    except JWTError as jwt_err:
        raise AppException(
            code="TOKEN_VERIFICATION_FAILED",
            message=f"Cryptographic token verification failed: {jwt_err}",
            status_code=401
        )

    # Check required standard claims
    jti = payload.get("jti")
    if not jti:
        raise AppException(
            code="TOKEN_MISSING_JTI",
            message="Token is missing required unique identifier (jti).",
            status_code=401
        )

    if is_token_revoked(jti):
        raise AppException(
            code="TOKEN_REVOKED",
            message="This session token has been revoked / logged out.",
            status_code=401
        )

    return payload
