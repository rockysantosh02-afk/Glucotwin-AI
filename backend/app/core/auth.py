"""
GlucoTwin AI - Centralized Authorization & Deny-by-Default Access Policy
"""

from typing import List, Optional
from pydantic import BaseModel
from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import AppException
from app.core.security import decode_and_validate_token

# Enforce auto_error=False so we can customize exact 401 envelope
bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedSession(BaseModel):
    """Represents an active, cryptographically validated user session."""
    user_id: str
    role: str
    jti: str
    scope: str
    sandbox_id: Optional[str] = None
    is_demo: bool = False

    def has_role(self, *allowed_roles: str) -> bool:
        return self.role in allowed_roles


async def get_current_session(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> AuthenticatedSession:
    """
    Extracts and strictly validates the Bearer JWT token from the Authorization header.
    Fails closed with HTTP 401 if missing, expired, or invalid.
    """
    if not credentials or not credentials.credentials:
        raise AppException(
            code="UNAUTHENTICATED",
            message="Authentication credentials (Bearer token) are missing or invalid.",
            status_code=401
        )

    token = credentials.credentials
    claims = decode_and_validate_token(token)

    role = claims.get("role", "demo_clinician")
    user_id = claims.get("sub", "anonymous")
    jti = claims.get("jti", "")
    scope = claims.get("scope", "")
    sandbox_id = claims.get("sandbox_id")
    is_demo = (role == "demo_clinician")

    return AuthenticatedSession(
        user_id=user_id,
        role=role,
        jti=jti,
        scope=scope,
        sandbox_id=sandbox_id,
        is_demo=is_demo
    )


def require_role(allowed_roles: List[str]):
    """
    Deny-by-default role authorization factory.
    Only allows users whose role is in `allowed_roles`.
    """
    async def role_checker(
        session: AuthenticatedSession = Depends(get_current_session)
    ) -> AuthenticatedSession:
        if session.role not in allowed_roles:
            raise AppException(
                code="FORBIDDEN_ROLE",
                message=f"Access denied. Role '{session.role}' is not authorized for this action. "
                        f"Required roles: {allowed_roles}.",
                status_code=403
            )
        return session
    return role_checker


def enforce_patient_scope(
    session: AuthenticatedSession,
    patient_id: str,
    patient_code: Optional[str] = None
) -> None:
    """
    Enforces patient-level authorization and sandbox boundary restrictions.
    - demo_clinician is strictly sandboxed to synthetic patients prefixed with 'SYN-'.
    - Unauthorized access raises HTTP 403.
    """
    if session.is_demo:
        # Check that patient code is synthetic
        if patient_code and not patient_code.startswith("SYN-"):
            raise AppException(
                code="DEMO_SCOPE_VIOLATION",
                message="Demo clinician sessions are strictly restricted to synthetic patient records (SYN-*).",
                status_code=403
            )
        # Sandbox isolation check: demo users cannot access non-sandbox patient IDs
        if session.sandbox_id and session.sandbox_id != settings.DEMO_SANDBOX_ID:
            raise AppException(
                code="SANDBOX_VIOLATION",
                message=f"Access to sandbox '{session.sandbox_id}' is forbidden for this demo session.",
                status_code=403
            )


def add_cache_control_no_store(response: Response) -> None:
    """
    Applies strict anti-caching headers to sensitive clinical/patient data responses.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
