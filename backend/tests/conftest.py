"""Pytest fixtures for async database tests."""

import asyncio
import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Use in-memory SQLite for tests (or test PostgreSQL)
DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """Create a test database session with schema."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    # For SQLite we need different schema - skip migrations, use simplified setup
    async with engine.begin() as conn:
        from sqlalchemy import text
        # Minimal schema for contacts/todos tests
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                company_id TEXT,
                full_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                country TEXT,
                notes TEXT,
                tags TEXT,
                last_contacted_at TEXT,
                last_interaction_summary TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                contact_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                occurred_at TEXT,
                created_at TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS todos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                contact_id TEXT,
                due_date TEXT,
                status TEXT DEFAULT 'pending',
                created_by_agent INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                action TEXT,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                created_at TEXT
            )
        """))
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()
