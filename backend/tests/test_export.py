"""Unit tests for export service."""

import pytest

pytestmark = pytest.mark.skip(reason="Requires PostgreSQL for full schema")


async def test_export_contacts_csv(db_session):
    """Test CSV export of contacts."""
    from services import export_service
    csv_str = await export_service.export_contacts_csv(db_session)
    assert isinstance(csv_str, str)
    assert "Name" in csv_str or csv_str == "Name,Email,Phone,Country,Company,Last Contacted,Last Interaction Summary,Tags\n"


async def test_export_todos_csv(db_session):
    """Test CSV export of TODOs."""
    from services import export_service
    csv_str = await export_service.export_todos_csv(db_session)
    assert isinstance(csv_str, str)
    assert "Title" in csv_str
