"""
GlucoTwin AI - Request ID & Audit Middleware
"""

import logging
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("glucotwin.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensures every incoming HTTP request has a unique request_id,
    measures request latency, and outputs structured audit log entries.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate unique request ID
        incoming_req_id = request.headers.get("X-Request-ID")
        if incoming_req_id and incoming_req_id.strip():
            request_id = incoming_req_id.strip()
        else:
            request_id = f"req-{uuid.uuid4().hex[:12]}"

        # Attach request_id to request state for access in endpoints & error handlers
        request.state.request_id = request_id

        start_time = time.perf_counter()

        # Log request receipt
        logger.info(
            f"Incoming request {request.method} {request.url.path}",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path}
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled exception during request {request.method} {request.url.path}: {exc}",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms
                }
            )
            raise exc

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Attach X-Request-ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log response completion
        logger.info(
            f"Completed {request.method} {request.url.path} with status {response.status_code} in {duration_ms}ms",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
        )

        return response
