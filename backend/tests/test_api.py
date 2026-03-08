"""API integration tests - run with backend and Postgres up."""

import os
import pytest
from httpx import AsyncClient, ASGITransport

# Only run if BACKEND_URL is set (e.g. in CI with services running)
pytestmark = pytest.mark.skipif(
    not os.environ.get("BACKEND_URL"),
    reason="BACKEND_URL not set - run with docker compose up",
)


@pytest.mark.asyncio
async def test_health():
    """Test health endpoint."""
    base = os.environ.get("BACKEND_URL", "http://localhost:8000")
    async with AsyncClient(base_url=base) as client:
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_list_contacts():
    """Test contacts list."""
    base = os.environ.get("BACKEND_URL", "http://localhost:8000")
    async with AsyncClient(base_url=base) as client:
        r = await client.get("/api/contacts")
        assert r.status_code == 200
        data = r.json()
        assert "contacts" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_list_todos():
    """Test TODOs list."""
    base = os.environ.get("BACKEND_URL", "http://localhost:8000")
    async with AsyncClient(base_url=base) as client:
        r = await client.get("/api/todos")
        assert r.status_code == 200
        data = r.json()
        assert "todos" in data
