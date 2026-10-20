"""
Tests for Typed Environment Configuration & Production Startup Guards.
Verifies fail-closed behavior for insecure secrets, debug mode, SQLite, and wildcard CORS/hosts.
"""

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_default_development_settings():
    """Verifies that development settings allow SQLite fallback and default test keys."""
    cfg = Settings(
        ENVIRONMENT="development",
        SECRET_KEY="replace_with_a_secure_random_string_of_at_least_32_characters",
        USE_SQLITE_FALLBACK=True
    )
    assert cfg.ENVIRONMENT == "development"
    assert cfg.is_sqlite is True
    assert cfg.RESEARCH_MODE_ONLY is True


def test_production_refusal_for_short_secret_key():
    """Production must refuse to start if SECRET_KEY is < 32 characters."""
    with pytest.raises(ValidationError, match="SECRET_KEY must be at least 32 characters long"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short_secret",
            DEBUG=False,
            USE_SQLITE_FALLBACK=False,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            ALLOWED_ORIGINS=["https://glucotwin.example.com"],
            ALLOWED_HOSTS=["glucotwin.example.com"]
        )


def test_production_refusal_for_default_insecure_secret_key():
    """Production must refuse to start if SECRET_KEY contains known default tokens."""
    with pytest.raises(ValidationError, match="contains insecure default token 'replace_with'"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="replace_with_a_secure_random_string_of_at_least_32_characters",
            DEBUG=False,
            USE_SQLITE_FALLBACK=False,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            ALLOWED_ORIGINS=["https://glucotwin.example.com"],
            ALLOWED_HOSTS=["glucotwin.example.com"]
        )


def test_production_refusal_for_debug_mode():
    """Production must refuse to start if DEBUG=True."""
    with pytest.raises(ValidationError, match="DEBUG mode must be disabled in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="c849e7b2a9f1406e987c2b0d3a5e8f1c4b7a9d2e0f3c5b8a1d4e7f0b3a6c9d2e",
            DEBUG=True,
            USE_SQLITE_FALLBACK=False,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            ALLOWED_ORIGINS=["https://glucotwin.example.com"],
            ALLOWED_HOSTS=["glucotwin.example.com"]
        )


def test_production_refusal_for_sqlite_fallback():
    """Production must refuse to start if SQLite fallback is enabled."""
    with pytest.raises(ValidationError, match="USE_SQLITE_FALLBACK must be False in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="c849e7b2a9f1406e987c2b0d3a5e8f1c4b7a9d2e0f3c5b8a1d4e7f0b3a6c9d2e",
            DEBUG=False,
            USE_SQLITE_FALLBACK=True,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            ALLOWED_ORIGINS=["https://glucotwin.example.com"],
            ALLOWED_HOSTS=["glucotwin.example.com"]
        )


def test_production_refusal_for_wildcard_cors():
    """Production must refuse wildcard '*' in ALLOWED_ORIGINS."""
    with pytest.raises(ValidationError, match="Wildcard '\\*' in ALLOWED_ORIGINS is strictly prohibited"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="c849e7b2a9f1406e987c2b0d3a5e8f1c4b7a9d2e0f3c5b8a1d4e7f0b3a6c9d2e",
            DEBUG=False,
            USE_SQLITE_FALLBACK=False,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            ALLOWED_ORIGINS=["*"],
            ALLOWED_HOSTS=["glucotwin.example.com"]
        )


def test_production_refusal_for_wildcard_hosts():
    """Production must refuse wildcard '*' in ALLOWED_HOSTS."""
    with pytest.raises(ValidationError, match="Wildcard '\\*' in ALLOWED_HOSTS is strictly prohibited"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="c849e7b2a9f1406e987c2b0d3a5e8f1c4b7a9d2e0f3c5b8a1d4e7f0b3a6c9d2e",
            DEBUG=False,
            USE_SQLITE_FALLBACK=False,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            ALLOWED_ORIGINS=["https://glucotwin.example.com"],
            ALLOWED_HOSTS=["*"]
        )


def test_valid_production_settings_pass():
    """Valid, hardened production settings must pass validation without error."""
    cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="c849e7b2a9f1406e987c2b0d3a5e8f1c4b7a9d2e0f3c5b8a1d4e7f0b3a6c9d2e",
        DEBUG=False,
        USE_SQLITE_FALLBACK=False,
        DATABASE_URL="postgresql+asyncpg://glucotwin_prod:Secr3tP@ssw0rd!@db.prod.internal:5432/glucotwin",
        ALLOWED_ORIGINS=["https://app.glucotwin.ai", "https://research.glucotwin.ai"],
        ALLOWED_HOSTS=["api.glucotwin.ai", "internal-gw.glucotwin.ai"],
        RESEARCH_MODE_ONLY=True,
        ALLOW_SYNTHETIC_DATA_ONLY=True,
        ENFORCE_GUARDRAILS=True,
        ENABLE_RECOMMENDATION_BLOCKER=True
    )
    assert cfg.ENVIRONMENT == "production"
    assert cfg.is_sqlite is False
    assert cfg.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_render_database_url_auto_normalization():
    """Verifies that postgresql:// or postgres:// from Render is automatically normalized to postgresql+asyncpg://."""
    cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="c849e7b2a9f1406e987c2b0d3a5e8f1c4b7a9d2e0f3c5b8a1d4e7f0b3a6c9d2e",
        DEBUG=False,
        USE_SQLITE_FALLBACK=False,
        DATABASE_URL="postgresql://user:pass@dpg-1234.oregon-postgres.render.com/glucotwin",
        ALLOWED_ORIGINS=["https://app.glucotwin.ai"],
        ALLOWED_HOSTS=["api.glucotwin.ai"]
    )
    assert cfg.DATABASE_URL == "postgresql+asyncpg://user:pass@dpg-1234.oregon-postgres.render.com/glucotwin"
