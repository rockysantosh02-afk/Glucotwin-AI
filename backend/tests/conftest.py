"""
GlucoTwin AI - Test Fixtures & In-Memory Test Database
"""

import asyncio
import os
import sys
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force test environment settings
os.environ["ENVIRONMENT"] = "testing"
os.environ["USE_SQLITE_FALLBACK"] = "true"
os.environ["SQLITE_FALLBACK_URL"] = "sqlite+aiosqlite:///:memory:"

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app

# In-memory SQLite async engine for tests
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a clean in-memory database session for each test function."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides an asynchronous HTTP test client with database dependency override."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def demo_clinician_token() -> str:
    """Generates a valid demo_clinician JWT token."""
    res = create_access_token(
        subject="test-demo-user",
        role="demo_clinician",
        scope="synthetic:read synthetic:simulate",
        sandbox_id=settings.DEMO_SANDBOX_ID
    )
    return res["access_token"]


@pytest.fixture
def clinician_token() -> str:
    """Generates a valid full clinician JWT token."""
    res = create_access_token(
        subject="test-clinician-user",
        role="clinician",
        scope="patient:read patient:simulate",
        sandbox_id=None
    )
    return res["access_token"]


@pytest.fixture
def admin_token() -> str:
    """Generates a valid admin JWT token."""
    res = create_access_token(
        subject="test-admin-user",
        role="admin",
        scope="admin:all",
        sandbox_id=None
    )
    return res["access_token"]
