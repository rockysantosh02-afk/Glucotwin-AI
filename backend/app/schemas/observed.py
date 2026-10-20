"""
GlucoTwin AI - Observed Data Schemas (Tier 1: Observed)
Alias and re-export of telemetry schemas as specified in architecture contracts.
"""

from app.schemas.telemetry import (
    TelemetryBatchIngestRequest,
    TelemetryIngestResponse,
    TelemetryQueryResponse,
    TelemetryReadingCreate,
    TelemetryRecordResponse,
)

__all__ = [
    "TelemetryBatchIngestRequest",
    "TelemetryIngestResponse",
    "TelemetryQueryResponse",
    "TelemetryReadingCreate",
    "TelemetryRecordResponse",
]
