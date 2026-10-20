"""
GlucoTwin AI - Typed Environment Configuration
Research & Education Prototype - Synthetic Patient Data Only
"""

import os
from typing import List, Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration with strict fail-closed production startup guards.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

    # Application Metadata
    APP_NAME: str = "GlucoTwin AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    # Server Network Binding
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Cryptography & Authentication
    SECRET_KEY: str = Field(
        default="replace_with_a_secure_random_string_of_at_least_32_characters",
        description="Secret key for JWT token signing. Must be >= 32 characters in production."
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://glucotwin_user:glucotwin_password@localhost:5432/glucotwin_db",
        description="Target PostgreSQL asynchronous connection URI."
    )
    SQLITE_FALLBACK_URL: str = Field(
        default="sqlite+aiosqlite:///./glucotwin_dev.db",
        description="Fallback SQLite asynchronous URI for local development/testing."
    )
    USE_SQLITE_FALLBACK: bool = Field(
        default=True,
        description="Whether to permit SQLite fallback in development/testing mode."
    )

    # CORS Allowed Origins & Trusted Hosts
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    ALLOWED_HOSTS: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )

    # JWT Security Constraints & Validation
    JWT_ISSUER: str = "glucotwin-ai"
    JWT_AUDIENCE: str = "glucotwin-client"

    # Demo Session & Sandbox Parameters
    DEMO_SESSION_DURATION_MINUTES: int = 30
    DEMO_SANDBOX_ID: str = "sandbox-demo-t1d"

    # Rate Limiting & Payload Security
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    MAX_CONTENT_LENGTH_BYTES: int = 1048576  # 1 MB
    MAX_HEADER_SIZE_BYTES: int = 16384       # 16 KB

    # Clinical Safety & Research Prototype Enforcements
    RESEARCH_MODE_ONLY: bool = True
    ALLOW_SYNTHETIC_DATA_ONLY: bool = True
    ENFORCE_GUARDRAILS: bool = True
    ENABLE_RECOMMENDATION_BLOCKER: bool = True

    # Digital Twin Simulation & Metric Constants
    MODEL_TYPE: str = "arx_kalman"
    PREDICTION_HORIZON_MINUTES: int = 60
    SIMULATION_TIME_STEP_MINUTES: int = 5
    TARGET_GLUCOSE_MIN: float = 70.0
    TARGET_GLUCOSE_MAX: float = 180.0
    HYPO_GLUCOSE_THRESHOLD: float = 70.0
    HYPER_GLUCOSE_THRESHOLD: float = 180.0
    SEVERE_HYPO_THRESHOLD: float = 54.0
    SEVERE_HYPER_THRESHOLD: float = 250.0
    PHYSIOLOGICAL_MIN_GLUCOSE: float = 40.0
    PHYSIOLOGICAL_MAX_GLUCOSE: float = 500.0

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: object) -> List[str]:
        if isinstance(value, str):
            if not value.strip():
                return []
            return [h.strip() for h in value.split(",") if h.strip()]
        if isinstance(value, list):
            return [str(h).strip() for h in value]
        return []

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> List[str]:
        if isinstance(value, str):
            if not value.strip():
                return []
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(o).strip() for o in value]
        return []

    @property
    def effective_database_url(self) -> str:
        """
        Determines the active database URL based on environment and fallback configuration.
        """
        if self.ENVIRONMENT in ("development", "testing") and self.USE_SQLITE_FALLBACK:
            return self.SQLITE_FALLBACK_URL
        return self.DATABASE_URL

    @property
    def is_sqlite(self) -> bool:
        """Returns True if the effective database URL uses SQLite."""
        return self.effective_database_url.startswith("sqlite")

    @model_validator(mode="after")
    def validate_production_guards(self) -> "Settings":
        """
        Enforce strict fail-closed production startup guards.
        """
        if self.ENVIRONMENT == "production":
            # 1. Secret Key Security Guard
            insecure_defaults = [
                "replace_with",
                "secret",
                "change-me",
                "default",
                "password",
                "12345"
            ]
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Production Guard Failure: SECRET_KEY must be at least 32 characters long."
                )
            for bad_term in insecure_defaults:
                if bad_term in self.SECRET_KEY.lower():
                    raise ValueError(
                        f"Production Guard Failure: SECRET_KEY contains insecure default token '{bad_term}'."
                    )

            # 2. Debug Guard
            if self.DEBUG:
                raise ValueError(
                    "Production Guard Failure: DEBUG mode must be disabled in production."
                )

            # 3. Database Engine Guard (SQLite strictly forbidden in production)
            if self.USE_SQLITE_FALLBACK:
                raise ValueError(
                    "Production Guard Failure: USE_SQLITE_FALLBACK must be False in production."
                )
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    "Production Guard Failure: SQLite cannot be used as production database engine. "
                    "A valid PostgreSQL connection URI (postgresql+asyncpg://) is required."
                )
            if not self.DATABASE_URL.startswith("postgresql"):
                raise ValueError(
                    "Production Guard Failure: DATABASE_URL must start with 'postgresql+asyncpg://' in production."
                )

            # 4. CORS & Host Wildcard Guard
            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError(
                    "Production Guard Failure: Wildcard '*' in ALLOWED_ORIGINS is strictly prohibited in production."
                )
            if "*" in self.ALLOWED_HOSTS:
                raise ValueError(
                    "Production Guard Failure: Wildcard '*' in ALLOWED_HOSTS is strictly prohibited in production."
                )

            # 5. Mandatory Research Safety Guards
            if not self.RESEARCH_MODE_ONLY:
                raise ValueError(
                    "Production Guard Failure: RESEARCH_MODE_ONLY must remain True."
                )
            if not self.ALLOW_SYNTHETIC_DATA_ONLY:
                raise ValueError(
                    "Production Guard Failure: ALLOW_SYNTHETIC_DATA_ONLY must remain True."
                )
            if not self.ENFORCE_GUARDRAILS or not self.ENABLE_RECOMMENDATION_BLOCKER:
                raise ValueError(
                    "Production Guard Failure: Safety guardrails and recommendation blocker must remain active."
                )

        return self


# Global singleton settings instance
settings = Settings()
