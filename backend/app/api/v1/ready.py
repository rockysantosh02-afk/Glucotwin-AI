"""
GlucoTwin AI - Readiness Probe Endpoint
Verifies database connectivity, Alembic migration head, and model integrity status.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import check_db_connectivity, engine

router = APIRouter(tags=["Readiness"])


async def check_migration_status() -> Dict[str, Any]:
    """
    Checks the current Alembic revision in the database.
    """
    try:
        async with engine.connect() as conn:
            # Check if alembic_version table exists and has revision
            result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            if row:
                return {"status": "ok", "current_revision": row[0]}
            else:
                return {"status": "warning", "message": "No migrations applied yet"}
    except Exception as exc:
        # Table might not exist yet or connection issue
        return {"status": "unmigrated", "error": str(exc)}


def check_model_integrity() -> Dict[str, Any]:
    """
    Verifies model engine specifications and configuration integrity.
    """
    # Verify baseline model configuration parameters
    valid_horizons = {15, 30, 45, 60}
    if settings.PREDICTION_HORIZON_MINUTES not in valid_horizons:
        return {
            "status": "failed",
            "reason": f"Invalid horizon {settings.PREDICTION_HORIZON_MINUTES}"
        }

    return {
        "status": "ready",
        "model_type": settings.MODEL_TYPE,
        "prediction_horizon_minutes": settings.PREDICTION_HORIZON_MINUTES,
        "physiological_bounds": [
            settings.PHYSIOLOGICAL_MIN_GLUCOSE,
            settings.PHYSIOLOGICAL_MAX_GLUCOSE
        ],
        "guardrails_enforced": settings.ENFORCE_GUARDRAILS,
        "recommendation_blocker_active": settings.ENABLE_RECOMMENDATION_BLOCKER
    }


@router.get("/ready")
async def readiness_check(request: Request):
    """
    Readiness probe for orchestrators and load balancers.
    Fails with HTTP 503 if database is disconnected or core components are not ready.
    """
    request_id = getattr(request.state, "request_id", "req-ready")

    # 1. Database Connectivity Probe
    db_ok = await check_db_connectivity()

    # 2. Migration Status
    migration_info = await check_migration_status()

    # 3. Model Integrity Status
    model_info = check_model_integrity()

    is_ready = db_ok and (model_info.get("status") == "ready")
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    payload = {
        "ready": is_ready,
        "components": {
            "database": {
                "connected": db_ok,
                "engine": "sqlite" if settings.is_sqlite else "postgresql"
            },
            "migrations": migration_info,
            "model_integrity": model_info
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id
    }

    return JSONResponse(status_code=status_code, content=payload)
