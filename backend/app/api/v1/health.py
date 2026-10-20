"""
GlucoTwin AI - Liveness Health Endpoint
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Request

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=200)
async def health_check(request: Request):
    """
    Liveness probe. Indicates that the ASGI process is running and accepting traffic.
    """
    request_id = getattr(request.state, "request_id", "req-health")
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id
    }
