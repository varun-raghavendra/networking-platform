"""Database connection and session management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def get_engine():
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
    )
    return engine


engine = get_engine()
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope for database operations."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Database session rolled back")
            raise
        finally:
            await session.close()


async def run_migrations() -> None:
    """Run SQL migrations from shared/db/migrations."""
    import os

    migrations_dir = os.path.join(
        os.path.dirname(__file__), "shared", "db", "migrations"
    )
    if not os.path.isdir(migrations_dir):
        logger.warning("Migrations directory not found: %s", migrations_dir)
        return

    from sqlalchemy import text

    async with engine.begin() as conn:
        for fname in sorted(os.listdir(migrations_dir)):
            if not fname.endswith(".sql"):
                continue
            path = os.path.join(migrations_dir, fname)
            with open(path) as f:
                sql = f.read()
            logger.info("Running migration %s", fname)
            # asyncpg cannot run multiple statements in one execute; split by semicolon
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                # Remove leading comment/blank lines so "CREATE TABLE" isn't skipped
                lines = [l for l in stmt.split("\n") if l.strip() and not l.strip().startswith("--")]
                stmt = "\n".join(lines)
                if stmt:
                    await conn.execute(text(stmt))
