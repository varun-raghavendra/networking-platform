"""Unit tests for contacts service."""

import pytest
from uuid import uuid4
from sqlalchemy import text

# Skip if using PostgreSQL-specific features
pytestmark = pytest.mark.skip(reason="Requires PostgreSQL for full schema")


async def test_upsert_contact_creates_new(db_session):
    """Test creating a new contact."""
    from services import contacts
    result = await contacts.upsert_contact(
        db_session,
        full_name="Jane Doe",
        company_name="Acme Inc",
        email="jane@acme.com",
        interaction_summary="Discussed partnership",
    )
    assert "id" in result
    assert result.get("created") is True


async def test_upsert_contact_deduplicates_by_email(db_session):
    """Test deduplication by email."""
    from services import contacts
    r1 = await contacts.upsert_contact(
        db_session,
        full_name="Jane Doe",
        company_name="Acme",
        email="jane@acme.com",
    )
    r2 = await contacts.upsert_contact(
        db_session,
        full_name="Jane Doe",
        company_name="Acme Corp",
        email="jane@acme.com",
    )
    assert r1["id"] == r2["id"]
    assert r2.get("created") is False
