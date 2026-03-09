"""Contacts service - CRUD, warmth scoring, deduplication."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base

logger = logging.getLogger(__name__)


# Simple ORM - we use raw SQL-style for flexibility; SQLAlchemy 2.0 style
def get_contacts_table():
    from sqlalchemy import Table, Column, String, DateTime, Text, ARRAY
    from sqlalchemy.dialects.postgresql import UUID, JSONB

    return Table(
        "contacts",
        Base.metadata,
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("company_id", UUID(as_uuid=True)),
        Column("full_name", String),
        Column("email", String),
        Column("phone", String),
        Column("country", String),
        Column("notes", Text),
        Column("tags", ARRAY(String)),
        Column("last_contacted_at", DateTime),
        Column("last_interaction_summary", String),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )


async def find_duplicate_contact(
    session: AsyncSession,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    full_name: Optional[str] = None,
    company_id: Optional[str] = None,
) -> Optional[dict]:
    """Find existing contact by email, phone, or full_name+company for deduplication."""
    from sqlalchemy import text

    if email and email.strip():
        r = await session.execute(
            text("SELECT * FROM contacts WHERE LOWER(TRIM(email)) = LOWER(TRIM(:email)) LIMIT 1"),
            {"email": email},
        )
        row = r.fetchone()
        if row:
            return dict(row._mapping)
    if phone and phone.strip():
        r = await session.execute(
            text("SELECT * FROM contacts WHERE TRIM(phone) = TRIM(:phone) LIMIT 1"),
            {"phone": phone},
        )
        row = r.fetchone()
        if row:
            return dict(row._mapping)
    if full_name and full_name.strip():
        name_norm = full_name.strip()
        if company_id:
            r = await session.execute(
                text(
                    "SELECT * FROM contacts WHERE LOWER(TRIM(full_name)) = LOWER(:name) "
                    "AND company_id = :cid LIMIT 1"
                ),
                {"name": name_norm, "cid": company_id},
            )
        else:
            r = await session.execute(
                text(
                    "SELECT * FROM contacts WHERE LOWER(TRIM(full_name)) = LOWER(:name) "
                    "AND company_id IS NULL LIMIT 1"
                ),
                {"name": name_norm},
            )
        row = r.fetchone()
        if row:
            return dict(row._mapping)
    return None


async def upsert_contact(
    session: AsyncSession,
    full_name: str,
    company_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    country: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
    interaction_summary: Optional[str] = None,
) -> dict:
    """Create or update contact. Deduplicates by email, phone, or full_name+company."""
    from sqlalchemy import text
    from uuid import uuid4

    now = datetime.utcnow()
    company_id = None
    if company_name:
        r = await session.execute(
            text("SELECT id FROM companies WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
            {"name": company_name},
        )
        row = r.fetchone()
        if row:
            company_id = str(row[0])
        else:
            r = await session.execute(
                text(
                    "INSERT INTO companies (id, name, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :name, :now, :now) RETURNING id"
                ),
                {"name": company_name, "now": now},
            )
            row = r.fetchone()
            if row:
                company_id = str(row[0])

    existing = await find_duplicate_contact(
        session, email=email, phone=phone, full_name=full_name, company_id=company_id
    )
    if existing:
        contact_id = existing["id"]
        # Update
        updates = ["updated_at = :now", "last_contacted_at = :now"]
        params = {"id": contact_id, "now": now, "full_name": full_name}
        if interaction_summary:
            updates.append("last_interaction_summary = :summary")
            params["summary"] = interaction_summary[:200]
        if company_id:
            updates.append("company_id = :company_id")
            params["company_id"] = company_id
        if email:
            updates.append("email = COALESCE(email, :email)")
            params["email"] = email
        if phone:
            updates.append("phone = COALESCE(phone, :phone)")
            params["phone"] = phone
        if country:
            updates.append("country = COALESCE(country, :country)")
            params["country"] = country
        if notes:
            updates.append("notes = COALESCE(notes, :notes)")
            params["notes"] = notes

        await session.execute(
            text(f"UPDATE contacts SET {', '.join(updates)} WHERE id = :id"), params
        )
        logger.info("Updated existing contact %s", contact_id)
        return {"id": str(contact_id), "created": False}
    else:
        contact_id = uuid4()
        await session.execute(
            text(
                "INSERT INTO contacts (id, company_id, full_name, email, phone, country, "
                "notes, tags, last_contacted_at, last_interaction_summary, created_at, updated_at) "
                "VALUES (:id, :company_id, :full_name, :email, :phone, :country, :notes, "
                ":tags, :now, :summary, :now, :now)"
            ),
            {
                "id": contact_id,
                "company_id": company_id,
                "full_name": full_name,
                "email": email or None,
                "phone": phone or None,
                "country": country or None,
                "notes": notes or None,
                "tags": tags or [],
                "now": now,
                "summary": (interaction_summary or "")[:200],
            },
        )
        logger.info("Created new contact %s", contact_id)
        return {"id": str(contact_id), "created": True}


async def record_interaction(
    session: AsyncSession, contact_id: UUID, summary: str
) -> dict:
    """Record interaction and update contact's last_contacted_at."""
    from sqlalchemy import text
    from uuid import uuid4

    now = datetime.utcnow()
    short_summary = summary[:200] if summary else ""

    await session.execute(
        text(
            "INSERT INTO interactions (id, contact_id, summary, occurred_at, created_at) "
            "VALUES (:id, :contact_id, :summary, :now, :now)"
        ),
        {"id": uuid4(), "contact_id": contact_id, "summary": summary, "now": now},
    )
    await session.execute(
        text(
            "UPDATE contacts SET last_contacted_at = :now, last_interaction_summary = :summary, updated_at = :now "
            "WHERE id = :contact_id"
        ),
        {"now": now, "summary": short_summary, "contact_id": contact_id},
    )
    logger.info("Recorded interaction for contact %s", contact_id)
    return {"success": True}


async def list_contacts(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    sort: str = "last_contacted_desc",
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    """List contacts for warm dashboard."""
    from sqlalchemy import text

    where = "1=1"
    params = {"limit": limit, "offset": offset}
    if search:
        params["search_pattern"] = f"%{search}%"
        where = (
            "c.full_name ILIKE :search_pattern OR c.last_interaction_summary ILIKE :search_pattern "
            "OR co.name ILIKE :search_pattern"
        )

    order = "last_contacted_at DESC NULLS LAST"
    if sort == "name_asc":
        order = "full_name ASC"

    r = await session.execute(
        text(
            f"SELECT c.id, c.full_name, c.country, c.last_contacted_at, "
            f"c.last_interaction_summary, c.next_follow_up_at, co.name as company_name FROM contacts c "
            f"LEFT JOIN companies co ON c.company_id = co.id WHERE {where} "
            f"ORDER BY {order} LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    rows = r.fetchall()

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    count_r = await session.execute(
        text(
            f"SELECT COUNT(*) FROM contacts c LEFT JOIN companies co ON c.company_id = co.id WHERE {where}"
        ),
        count_params,
    )
    total = count_r.scalar() or 0

    return [dict(row._mapping) for row in rows], total


async def get_contact(session: AsyncSession, contact_id: UUID) -> Optional[dict]:
    """Get single contact by ID."""
    from sqlalchemy import text

    r = await session.execute(
        text(
            "SELECT c.*, co.name as company_name FROM contacts c "
            "LEFT JOIN companies co ON c.company_id = co.id WHERE c.id = :id"
        ),
        {"id": contact_id},
    )
    row = r.fetchone()
    return dict(row._mapping) if row else None


async def get_contact_interactions(
    session: AsyncSession, contact_id: UUID, limit: int = 20
) -> list[dict]:
    """Get full interaction history for a contact."""
    from sqlalchemy import text

    r = await session.execute(
        text(
            "SELECT id, summary, occurred_at FROM interactions "
            "WHERE contact_id = :id ORDER BY occurred_at DESC LIMIT :limit"
        ),
        {"id": contact_id, "limit": limit},
    )
    return [dict(row._mapping) for row in r.fetchall()]


def _parse_datetime_safe(s: Optional[str]):
    """Parse ISO or YYYY-MM-DD string to datetime. Returns None on failure."""
    if not s or not s.strip():
        return None
    from datetime import datetime as dt
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.strptime(s[:26], fmt)
        except (ValueError, TypeError):
            continue
    try:
        return dt.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def update_contact_fields(
    session: AsyncSession,
    contact_id: UUID,
    country: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    last_contacted_at: Optional[str] = None,
) -> Optional[dict]:
    """Update contact fields including last_contacted_at."""
    from sqlalchemy import text

    updates = ["updated_at = :now"]
    params = {"id": contact_id, "now": datetime.utcnow()}
    if country is not None:
        updates.append("country = :country")
        params["country"] = country or None
    if phone is not None:
        updates.append("phone = :phone")
        params["phone"] = phone or None
    if email is not None:
        updates.append("email = :email")
        params["email"] = email or None
    if last_contacted_at is not None:
        parsed = _parse_datetime_safe(last_contacted_at)
        if parsed:
            updates.append("last_contacted_at = :last_contacted_at")
            params["last_contacted_at"] = parsed

    if len(updates) == 1:
        return await get_contact(session, contact_id)

    await session.execute(
        text(f"UPDATE contacts SET {', '.join(updates)} WHERE id = :id"), params
    )
    logger.info("Updated contact fields for %s", contact_id)
    return await get_contact(session, contact_id)


async def set_next_follow_up(
    session: AsyncSession,
    contact_id: UUID,
    next_follow_up_at,
) -> None:
    """Set contact's next_follow_up_at (datetime or None)."""
    from sqlalchemy import text

    await session.execute(
        text(
            "UPDATE contacts SET next_follow_up_at = :at, updated_at = :now WHERE id = :id"
        ),
        {"id": contact_id, "at": next_follow_up_at, "now": datetime.utcnow()},
    )


async def get_stale_contacts(
    session: AsyncSession, days: int = 90
) -> list[dict]:
    """Get contacts not contacted in N days (for reminders/nudges)."""
    from sqlalchemy import text

    r = await session.execute(
        text(
            "SELECT c.id, c.full_name, c.last_contacted_at FROM contacts c "
            "WHERE c.last_contacted_at < NOW() - INTERVAL '1 day' * :days "
            "OR c.last_contacted_at IS NULL ORDER BY c.last_contacted_at ASC NULLS LAST"
        ),
        {"days": days},
    )
    return [dict(row._mapping) for row in r.fetchall()]
