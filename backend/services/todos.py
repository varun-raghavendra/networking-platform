"""TODO service - CRUD for TODO items."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def create_todo(
    session: AsyncSession,
    title: str,
    description: Optional[str] = None,
    contact_id: Optional[UUID] = None,
    due_date: Optional[datetime] = None,
    created_by_agent: bool = False,
) -> dict:
    """Create a TODO item."""
    todo_id = uuid4()
    now = datetime.utcnow()

    await session.execute(
        text(
            "INSERT INTO todos (id, title, description, contact_id, due_date, status, created_by_agent, created_at, updated_at, metadata) "
            "VALUES (:id, :title, :desc, :contact_id, :due_date, 'pending', :by_agent, :now, :now, '{}')"
        ),
        {
            "id": todo_id,
            "title": title,
            "desc": description or None,
            "contact_id": contact_id,
            "due_date": due_date,
            "by_agent": created_by_agent,
            "now": now,
        },
    )
    logger.info("Created TODO %s: %s", todo_id, title)
    return {"id": str(todo_id), "title": title, "status": "pending"}


async def list_todos(
    session: AsyncSession,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List TODO items for dashboard."""
    where = "1=1"
    params = {"limit": limit, "offset": offset}
    if status:
        where = "status = :status"
        params["status"] = status

    r = await session.execute(
        text(
            f"SELECT t.id, t.title, t.description, t.contact_id, t.due_date, t.status, "
            f"t.created_at, c.full_name as contact_name FROM todos t "
            f"LEFT JOIN contacts c ON t.contact_id = c.id WHERE {where} "
            f"ORDER BY t.created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    rows = r.fetchall()

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    count_r = await session.execute(
        text(f"SELECT COUNT(*) FROM todos WHERE {where}"), count_params
    )
    total = count_r.scalar() or 0

    return [dict(row._mapping) for row in rows], total


async def update_todo(
    session: AsyncSession,
    todo_id: UUID,
    status: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[dict]:
    """Update a TODO item."""
    updates = ["updated_at = :now"]
    params = {"id": todo_id, "now": datetime.utcnow()}
    if status:
        updates.append("status = :status")
        params["status"] = status
    if title is not None:
        updates.append("title = :title")
        params["title"] = title
    if description is not None:
        updates.append("description = :description")
        params["description"] = description

    await session.execute(
        text(f"UPDATE todos SET {', '.join(updates)} WHERE id = :id"), params
    )
    logger.info("Updated TODO %s", todo_id)
    return await get_todo(session, todo_id)


async def get_todo(session: AsyncSession, todo_id: UUID) -> Optional[dict]:
    """Get single TODO by ID."""
    r = await session.execute(
        text(
            "SELECT t.*, c.full_name as contact_name FROM todos t "
            "LEFT JOIN contacts c ON t.contact_id = c.id WHERE t.id = :id"
        ),
        {"id": todo_id},
    )
    row = r.fetchone()
    return dict(row._mapping) if row else None
