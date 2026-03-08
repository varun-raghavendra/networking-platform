"""Unit tests for TODO service."""

import pytest
from uuid import uuid4

pytestmark = pytest.mark.skip(reason="Requires PostgreSQL for full schema")


async def test_create_todo(db_session):
    """Test creating a TODO."""
    from services import todos
    result = await todos.create_todo(
        db_session,
        title="Follow up with Jane",
        description="Send proposal",
        created_by_agent=True,
    )
    assert "id" in result
    assert result["title"] == "Follow up with Jane"
    assert result["status"] == "pending"


async def test_list_todos(db_session):
    """Test listing TODOs."""
    from services import todos
    rows, total = await todos.list_todos(db_session, status="pending")
    assert isinstance(rows, list)
    assert total >= 0
