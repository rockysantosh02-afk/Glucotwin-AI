"""
GlucoTwin AI - Security Middleware
Enforces Trusted Hosts, Security Headers, Request/Header Size Limits, and Client Rate Limiting.
"""

import time
from collections import defaultdict
from typing import Callable, Dict, List, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.errors import build_error_response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies standard defensive security headers to all responses.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Baseline defensive security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Guards against denial-of-service via oversized payloads or bloated request headers.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = getattr(request.state, "request_id", "req-security")

        # 1. Check Header Size
        header_size = sum(len(k) + len(v) for k, v in request.headers.items())
        if header_size > settings.MAX_HEADER_SIZE_BYTES:
            return build_error_response(
                status_code=431,
                code="HEADER_FIELDS_TOO_LARGE",
                message=f"Request headers exceed maximum permitted size ({settings.MAX_HEADER_SIZE_BYTES} bytes).",
                request_id=request_id
            )

        # 2. Check Content-Length for Request Body
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > settings.MAX_CONTENT_LENGTH_BYTES:
                    return build_error_response(
                        status_code=413,
                        code="PAYLOAD_TOO_LARGE",
                        message=f"Request payload exceeds maximum permitted size ({settings.MAX_CONTENT_LENGTH_BYTES} bytes).",
                        request_id=request_id
                    )
            except ValueError:
                pass

        return await call_next(request)


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """
    Validates that incoming requests target explicitly allowed hosts.
    Prevents HTTP Host header injection and cache poisoning attacks.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        host = request.headers.get("host", "").split(":")[0].strip()
        request_id = getattr(request.state, "request_id", "req-security")

        if settings.ALLOWED_HOSTS and host not in settings.ALLOWED_HOSTS:
            return build_error_response(
                status_code=400,
                code="INVALID_HOST_HEADER",
                message=f"Untrusted Host header '{host}'. Request rejected.",
                request_id=request_id
            )

        return await call_next(request)


class InMemoryRateLimiter:
    """
    Sliding window in-memory rate limiter tracking client requests per minute.
    """
    def __init__(self):
        # Maps client_key -> list of timestamp floats
        self._history: Dict[str, List[float]] = defaultdict(list)

    def is_rate_limited(
        self,
        key: str,
        limit_per_minute: int
    ) -> Tuple[bool, int]:
        """
        Returns (is_limited, retry_after_seconds).
        """
        now = time.time()
        window_start = now - 60.0

        # Prune timestamps older than 60 seconds
        timestamps = [t for t in self._history[key] if t > window_start]
        self._history[key] = timestamps

        if len(timestamps) >= limit_per_minute:
            oldest = timestamps[0]
            retry_after = max(1, int(oldest + 60.0 - now))
            return True, retry_after

        # Record this request
        self._history[key].append(now)
        return False, 0

    def reset(self) -> None:
        self._history.clear()


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()


def redact_sensitive_data(payload: dict) -> dict:
    """
    Recursively redacts passwords, tokens, and authorization headers from audit dictionaries.
    """
    sensitive_keys = {
        "password", "secret", "token", "access_token", "authorization",
        "hashed_password", "secret_key", "bearer"
    }
    redacted = {}
    for k, v in payload.items():
        if k.lower() in sensitive_keys:
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = redact_sensitive_data(v)
        elif isinstance(v, list):
            redacted[k] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            redacted[k] = v
    return redacted
