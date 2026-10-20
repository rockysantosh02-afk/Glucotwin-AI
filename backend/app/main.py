"""
GlucoTwin AI - FastAPI Application Factory
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.protected import router as protected_router
from app.api.v1.ready import router as ready_router
from app.core.config import settings
from app.core.database import Base, check_db_connectivity, engine
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware
from app.core.security_middleware import (
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
)

logger = logging.getLogger("glucotwin.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Initializes logging, establishes database connection, and cleans up resources.
    """
    # 1. Setup structured logging
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} (Environment: {settings.ENVIRONMENT})"
    )

    # 2. Check Database Connectivity
    is_connected = await check_db_connectivity()
    if is_connected:
        logger.info(
            f"Database connectivity established successfully using "
            f"{'SQLite fallback' if settings.is_sqlite else 'PostgreSQL'}"
        )
        # In development/testing, ensure all tables exist if using SQLite
        if settings.is_sqlite and settings.ENVIRONMENT in ("development", "testing"):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Local SQLite database tables verified / created.")
    else:
        logger.warning(
            "Database connectivity probe failed during startup. Running in degraded state."
        )

    yield

    # Teardown: close database engine connection pool
    logger.info("Shutting down application and disposing database connection pool...")
    await engine.dispose()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="A Physiological Digital Twin & Metabolic Simulation Platform for Type 1 Diabetes Research",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan
    )

    # 1. Register Global Error Handlers (Consistent Error Envelope)
    register_error_handlers(app)

    # 2. Register Middleware (Order matters: outermost runs first on request)
    # Host header check
    app.add_middleware(TrustedHostMiddleware)

    # Security headers on all outgoing responses
    app.add_middleware(SecurityHeadersMiddleware)

    # Request and Header size limits
    app.add_middleware(RequestSizeLimitMiddleware)

    # Request ID and audit timing
    app.add_middleware(RequestIDMiddleware)

    # Exact-origin CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 3. Mount Unversioned Root Health & Readiness Endpoints
    app.include_router(health_router)
    app.include_router(ready_router)

    # 4. Mount Versioned API v1 Routers
    api_v1_prefix = settings.API_V1_PREFIX
    app.include_router(health_router, prefix=api_v1_prefix)
    app.include_router(ready_router, prefix=api_v1_prefix)
    app.include_router(auth_router, prefix=api_v1_prefix)
    app.include_router(protected_router, prefix=api_v1_prefix)

    return app


# Default ASGI application instance
app = create_app()
