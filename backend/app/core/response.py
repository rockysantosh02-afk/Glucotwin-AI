"""
GlucoTwin AI - Standardized Success Envelopes
Ensures all successful API responses strictly comply with architectural contracts.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import Request


def make_success_response(
    data: Any,
    request: Request,
    **extra_metadata: Any
) -> Dict[str, Any]:
    """
    Constructs the canonical JSON success response envelope.
    Includes top-level success flag, typed data payload, and request traceability metadata.
    """
    request_id = getattr(request.state, "request_id", "req-unknown")
    now_iso = datetime.now(timezone.utc).isoformat()

    metadata: Dict[str, Any] = {
        "timestamp": now_iso,
        "request_id": request_id,
        "version": "1.0.0"
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "success": True,
        "data": data,
        "metadata": metadata
    }
