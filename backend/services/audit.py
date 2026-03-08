"""Audit log service."""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_audit(
    session: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Log an audit entry."""
    entry_id = uuid4()
    now = datetime.utcnow()
    import json

    details_json = json.dumps(details or {}, default=str)

    await session.execute(
        text(
            "INSERT INTO audit_log (id, action, entity_type, entity_id, details, created_at) "
            "VALUES (:id, :action, :entity_type, :entity_id, CAST(:details AS jsonb), :now)"
        ),
        {
            "id": entry_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details_json,
            "now": now,
        },
    )
    logger.info("Audit: %s %s %s", action, entity_type, entity_id)
