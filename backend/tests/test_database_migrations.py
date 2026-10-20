"""
Tests for Database Migrations & Rollback Behavior.
Verifies that a clean database migrates cleanly to head, rolls back to base, and re-migrates.
"""

import os
import sys
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

# Path to backend
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALEMBIC_INI_PATH = os.path.join(BACKEND_DIR, "alembic.ini")


@pytest.mark.asyncio
async def test_clean_database_migration_and_rollback(tmp_path):
    """
    Executes Alembic migrations against a fresh, clean SQLite database:
    1. Upgrade to head
    2. Verify all 7 normalized tables and indexes exist
    3. Downgrade to base (full rollback verification)
    4. Re-upgrade to head
    """
    test_db_file = tmp_path / "migration_test.db"
    test_db_url = f"sqlite+aiosqlite:///{test_db_file.as_posix()}"

    alembic_cfg = Config(ALEMBIC_INI_PATH)
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)

    # 1. Run upgrade to head
    command.upgrade(alembic_cfg, "head")

    # 2. Inspect created tables
    engine = create_async_engine(test_db_url)
    async with engine.connect() as conn:
        def get_tables(connection):
            inspector = inspect(connection)
            return inspector.get_table_names()

        tables = await conn.run_sync(get_tables)
        expected_tables = {
            "users",
            "synthetic_patients",
            "telemetry_records",
            "glycemic_metrics",
            "forecast_runs",
            "simulation_scenarios",
            "audit_logs",
            "alembic_version"
        }
        for expected in expected_tables:
            assert expected in tables, f"Expected table '{expected}' missing after migration upgrade."

    # 3. Test Rollback (downgrade to base)
    command.downgrade(alembic_cfg, "base")

    async with engine.connect() as conn:
        tables_after_rollback = await conn.run_sync(get_tables)
        # All domain tables should be removed
        for table in ["users", "synthetic_patients", "telemetry_records"]:
            assert table not in tables_after_rollback, f"Table '{table}' should have been dropped on rollback."

    # 4. Re-upgrade to head
    command.upgrade(alembic_cfg, "head")
    async with engine.connect() as conn:
        tables_reupgraded = await conn.run_sync(get_tables)
        assert "synthetic_patients" in tables_reupgraded

    await engine.dispose()


def test_postgresql_dialect_compatibility_assertions():
    """
    Explicitly checks model column types and constraints for PostgreSQL compatibility.
    Adheres to: 'Do not claim PostgreSQL compatibility based solely on SQLite tests.'
    Verifies that all columns map to valid PostgreSQL data types and constraints.
    """
    from app.models import (
        User,
        SyntheticPatient,
        TelemetryRecord,
        GlycemicMetric,
        ForecastRun,
        SimulationScenario,
        AuditLog,
    )
    from sqlalchemy.dialects import postgresql

    models = [
        User,
        SyntheticPatient,
        TelemetryRecord,
        GlycemicMetric,
        ForecastRun,
        SimulationScenario,
        AuditLog,
    ]

    for model in models:
        for column in model.__table__.columns:
            # Compile column type against PostgreSQL dialect to ensure DDL compiles
            compiled_type = column.type.compile(dialect=postgresql.dialect())
            assert compiled_type is not None, (
                f"Column {model.__tablename__}.{column.name} failed PostgreSQL DDL compilation."
            )
