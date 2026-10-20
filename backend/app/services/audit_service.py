"""
GlucoTwin AI - Append-Only Audit Logging Service
Records security events, authentication outcomes, authorization denials, and guardrail actions.
Enforces strict redaction of tokens, credentials, and clinical payloads.
"""

import json
import logging
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_middleware import redact_sensitive_data
from app.models.audit import AuditLog

logger = logging.getLogger("glucotwin.audit")


class AuditService:
    @staticmethod
    async def log_event(
        db: Optional[AsyncSession],
        action: str,
        resource_type: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        guardrail_triggered: bool = False,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Optional[AuditLog]:
        """
        Appends an immutable audit event to the database and logs a structured event.
        Guarantees that credentials, tokens, and patient clinical payloads are redacted.
        """
        # Redact any sensitive tokens or passwords
        safe_details = redact_sensitive_data(details or {})

        # Strip clinical telemetry payload arrays if inadvertently passed
        if "readings" in safe_details:
            safe_details["readings"] = f"[{len(safe_details['readings'])} readings omitted from audit]"
        if "observations" in safe_details:
            safe_details["observations"] = f"[{len(safe_details['observations'])} observations omitted from audit]"
        if "glucose_values" in safe_details:
            safe_details["glucose_values"] = "[omitted from audit]"
        if "telemetry" in safe_details:
            safe_details["telemetry"] = "[omitted from audit]"

        details_str = json.dumps(safe_details, default=str)

        # Log to structured application logger
        logger.info(
            f"AUDIT_EVENT: {action} on {resource_type} (user={user_id or 'anon'}, guardrail={guardrail_triggered})",
            extra={
                "audit_action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": user_id,
                "guardrail_triggered": guardrail_triggered,
                "ip_address": ip_address
            }
        )

        # Persist to database if session is provided
        if db is not None:
            try:
                audit_entry = AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    guardrail_triggered=guardrail_triggered,
                    details_json=details_str,
                    ip_address=ip_address
                )
                db.add(audit_entry)
                await db.flush()
                return audit_entry
            except Exception as exc:
                logger.error(f"Failed to persist audit log entry to database: {exc}")
                return None

        return None
