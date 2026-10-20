"""
GlucoTwin AI - Protected Test Endpoints (Security Verification)
Exposes test routes for verifying authentication, role enforcement, patient scope, and anti-caching headers.
Patient data feature routes are not exposed yet in accordance with Phase 3/4 guidelines.
"""

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.auth import (
    AuthenticatedSession,
    add_cache_control_no_store,
    enforce_patient_scope,
    get_current_session,
    require_role,
)
from app.core.config import settings
from app.core.errors import NotFoundException
from app.core.security_middleware import rate_limiter

router = APIRouter(prefix="/security-test", tags=["Security Verification"])


@router.get("/clinician-only", status_code=status.HTTP_200_OK)
async def clinician_only_route(
    session: AuthenticatedSession = Depends(require_role(["clinician", "admin"]))
):
    """Restricted to clinician or admin roles. Denies demo_clinician."""
    return {
        "success": True,
        "message": f"Welcome, verified clinician ({session.user_id}).",
        "role": session.role
    }


@router.get("/admin-only", status_code=status.HTTP_200_OK)
async def admin_only_route(
    session: AuthenticatedSession = Depends(require_role(["admin"]))
):
    """Restricted to admin role only."""
    return {
        "success": True,
        "message": "Welcome, administrator.",
        "role": session.role
    }


@router.get("/patient-scope/{patient_code}", status_code=status.HTTP_200_OK)
async def test_patient_scope_route(
    patient_code: str,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session)
):
    """
    Enforces patient-level scope authorization and anti-caching headers.
    demo_clinician can only access synthetic patients (SYN-*).
    """
    # Enforce patient scope
    enforce_patient_scope(session=session, patient_id="mock-id", patient_code=patient_code)

    # Enforce anti-caching header on clinical data responses
    add_cache_control_no_store(response)

    return {
        "success": True,
        "patient_code": patient_code,
        "authorized_for": session.role,
        "sandbox_id": session.sandbox_id
    }


@router.get("/rate-limited-action", status_code=status.HTTP_200_OK)
async def rate_limited_test_route(
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session)
):
    """
    Route enforcing tight per-user rate limit (e.g., 3 requests per minute) for verification.
    """
    key = f"test_action:{session.user_id}"
    is_limited, retry_after = rate_limiter.is_rate_limited(key, limit_per_minute=3)
    if is_limited:
        from app.core.errors import build_error_response
        request_id = getattr(request.state, "request_id", "req-limit")
        resp = build_error_response(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded on test route. Retry after {retry_after}s.",
            request_id=request_id
        )
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    return {
        "success": True,
        "message": "Action permitted within rate limits."
    }
