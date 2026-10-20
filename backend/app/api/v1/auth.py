"""
GlucoTwin AI - Authentication Endpoints
Provides demo session issuance and token revocation (logout) with rate limiting and audit logging.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedSession, get_current_session
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppException, build_error_response
from app.core.security import create_access_token, revoke_token
from app.core.security_middleware import rate_limiter
from app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["Authentication"])


class DemoSessionRequest(BaseModel):
    clinician_name: Optional[str] = Field(
        default="Guest Researcher",
        description="Optional display name for the demo session"
    )
    requested_sandbox: Optional[str] = Field(
        default="sandbox-demo-t1d",
        description="Target synthetic sandbox identifier"
    )


class DemoSessionResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in_seconds: int
    role: str
    sandbox_id: str
    scope: str
    issued_at: str


@router.post("/demo-session", status_code=status.HTTP_201_CREATED)
async def create_demo_session(
    request: Request,
    payload: Optional[DemoSessionRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Issues a short-lived, sandboxed demo clinician JWT session.
    Restricted to synthetic patients and sandbox boundaries.
    Protected by per-client rate limiting.
    """
    request_id = getattr(request.state, "request_id", "req-auth")
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Enforce strict rate limit on session issuance
    is_limited, retry_after = rate_limiter.is_rate_limited(
        f"auth:{client_ip}",
        settings.RATE_LIMIT_AUTH_PER_MINUTE
    )
    if is_limited:
        await AuditService.log_event(
            db=db,
            action="RATE_LIMIT_TRIGGERED",
            resource_type="auth",
            details={"endpoint": "/demo-session", "retry_after": retry_after},
            ip_address=client_ip
        )
        response = build_error_response(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message=f"Too many authentication attempts. Please retry after {retry_after} seconds.",
            request_id=request_id
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    body = payload or DemoSessionRequest()
    sandbox = body.requested_sandbox or settings.DEMO_SANDBOX_ID

    # Enforce that demo users can only request synthetic sandbox
    if sandbox != settings.DEMO_SANDBOX_ID:
        await AuditService.log_event(
            db=db,
            action="UNAUTHORIZED_SANDBOX_REQUEST",
            resource_type="auth",
            details={"requested_sandbox": sandbox},
            ip_address=client_ip
        )
        raise AppException(
            code="INVALID_SANDBOX",
            message=f"Requested sandbox '{sandbox}' is not authorized. Allowed sandbox: '{settings.DEMO_SANDBOX_ID}'.",
            status_code=403
        )

    # Generate short-lived demo token (30 minutes)
    expires_delta = timedelta(minutes=settings.DEMO_SESSION_DURATION_MINUTES)
    token_data = create_access_token(
        subject=f"demo-{client_ip}",
        role="demo_clinician",
        scope="synthetic:read synthetic:simulate",
        sandbox_id=sandbox,
        expires_delta=expires_delta
    )

    # Record security audit event
    await AuditService.log_event(
        db=db,
        action="DEMO_SESSION_CREATED",
        resource_type="auth",
        user_id=f"demo-{client_ip}",
        resource_id=token_data["jti"],
        details={
            "role": "demo_clinician",
            "sandbox": sandbox,
            "expires_in_seconds": token_data["expires_in_seconds"]
        },
        ip_address=client_ip
    )

    return {
        "success": True,
        "data": {
            "access_token": token_data["access_token"],
            "token_type": token_data["token_type"],
            "expires_in_seconds": token_data["expires_in_seconds"],
            "role": "demo_clinician",
            "sandbox_id": sandbox,
            "scope": "synthetic:read synthetic:simulate",
            "issued_at": datetime.now(timezone.utc).isoformat()
        },
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id
        }
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    """
    Terminates the active session by revoking the token ID (jti).
    Subsequent requests with this token will be rejected with HTTP 401 TOKEN_REVOKED.
    """
    request_id = getattr(request.state, "request_id", "req-auth")
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Revoke the token jti
    # If expiration timestamp is known, revoke until that time, else 2 hours
    exp_time = datetime.now(timezone.utc).timestamp() + 7200
    revoke_token(session.jti, exp_time)

    # Record audit event
    await AuditService.log_event(
        db=db,
        action="USER_LOGOUT",
        resource_type="auth",
        user_id=session.user_id,
        resource_id=session.jti,
        details={"role": session.role, "revoked_jti": session.jti},
        ip_address=client_ip
    )

    return {
        "success": True,
        "data": {
            "message": "Demo session successfully terminated. Token has been revoked.",
            "revoked_token_id": session.jti
        },
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id
        }
    }


@router.get("/session", status_code=status.HTTP_200_OK)
async def get_session_info(
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session)
):
    """
    Returns current authenticated session metadata.
    Enforces Cache-Control: no-store.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"

    request_id = getattr(request.state, "request_id", "req-auth")
    return {
        "success": True,
        "data": {
            "user_id": session.user_id,
            "role": session.role,
            "scope": session.scope,
            "sandbox_id": session.sandbox_id,
            "is_demo": session.is_demo
        },
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id
        }
    }
