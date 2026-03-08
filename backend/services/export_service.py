"""Export service - CSV export for contacts and TODOs."""

import csv
import io
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def export_contacts_csv(session: AsyncSession) -> str:
    """Export contacts as CSV string."""
    r = await session.execute(
        text(
            "SELECT c.full_name, c.email, c.phone, c.country, co.name as company, "
            "c.last_contacted_at, c.last_interaction_summary, c.tags FROM contacts c "
            "LEFT JOIN companies co ON c.company_id = co.id ORDER BY c.last_contacted_at DESC NULLS LAST"
        )
    )
    rows = r.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Name",
            "Email",
            "Phone",
            "Country",
            "Company",
            "Last Contacted",
            "Last Interaction Summary",
            "Tags",
        ]
    )
    for row in rows:
        r = row._mapping
        writer.writerow(
            [
                r.get("full_name", ""),
                r.get("email", ""),
                r.get("phone", ""),
                r.get("country", ""),
                r.get("company", ""),
                r.get("last_contacted_at") or "",
                r.get("last_interaction_summary", ""),
                ",".join(r.get("tags") or []),
            ]
        )
    logger.info("Exported %d contacts to CSV", len(rows))
    return output.getvalue()


async def export_todos_csv(session: AsyncSession) -> str:
    """Export TODOs as CSV string."""
    r = await session.execute(
        text(
            "SELECT t.title, t.description, t.status, t.due_date, t.created_at, c.full_name as contact_name "
            "FROM todos t LEFT JOIN contacts c ON t.contact_id = c.id ORDER BY t.created_at DESC"
        )
    )
    rows = r.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Description", "Status", "Due Date", "Created At", "Contact"])
    for row in rows:
        r = row._mapping
        writer.writerow(
            [
                r.get("title", ""),
                r.get("description", ""),
                r.get("status", ""),
                r.get("due_date") or "",
                r.get("created_at") or "",
                r.get("contact_name", ""),
            ]
        )
    logger.info("Exported %d todos to CSV", len(rows))
    return output.getvalue()
