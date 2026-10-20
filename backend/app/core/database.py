"""
GlucoTwin AI - Database Engine & Async Session Management
Supports PostgreSQL (asyncpg) in production and SQLite (aiosqlite) in development/testing.
"""

import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger("glucotwin.database")


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities."""
    pass


def create_engine_for_url(db_url: str) -> AsyncEngine:
    """
    Creates an asynchronous engine configured for SQLite or PostgreSQL.
    """
    if db_url.startswith("sqlite"):
        # SQLite-specific connection arguments
        return create_async_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            echo=settings.DEBUG
        )
    else:
        # PostgreSQL-specific connection pooling
        return create_async_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.DEBUG
        )


# Global default engine and sessionmaker
engine: AsyncEngine = create_engine_for_url(settings.effective_database_url)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async session with transactional integrity.
    Commits on successful completion, automatically rolls back on exception.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(f"Database transaction rollback due to error: {exc}")
            raise exc
        finally:
            await session.close()


async def check_db_connectivity() -> bool:
    """
    Executes a simple probe query (SELECT 1) to verify database connectivity.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.warning(f"Database connectivity check failed: {exc}")
        return False
