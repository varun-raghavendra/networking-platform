#!/usr/bin/env python3
"""
Temporary script to re-assign priorities for all existing TODO items using the todo agent.

1. Runs a DB backup to backups/ first
2. Fetches all todos, calls the agent for each to get a suggested priority
3. Updates each todo with the new priority

Run from project root (postgres must be reachable; docker compose for backup):
  cd /path/to/networking_platform
  python scripts/reprioritize_todos.py

Requires: docker compose, OPENAI_API_KEY in .env
If running from host: use DATABASE_URL with localhost (script auto-replaces postgres->localhost)
"""
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

# Project root = parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Load .env from project root
def load_dotenv():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

load_dotenv()

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import get_settings
from orchestrator.todo_agent import TodoAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_backup() -> str:
    """Run DB backup via backup container. Returns path to backup file."""
    backups_dir = PROJECT_ROOT / "backups"
    backups_dir.mkdir(exist_ok=True)
    logger.info("Running DB backup...")
    result = subprocess.run(
        [
            "docker", "compose", "run", "--rm",
            "-v", f"{backups_dir}:/backups",
            "-e", "BACKUP_DIR=/backups",
            "backup", "/scripts/backup_db.sh",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Backup failed: %s", result.stderr)
        raise SystemExit(1)
    # Find the newest backup file
    files = sorted(backups_dir.glob("networking_*.sql.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(1)
    path = files[0]
    logger.info("Backup complete: %s (%s)", path.name, f"{path.stat().st_size / 1024:.1f} KB")
    return str(path)


async def main():
    db_url = get_settings().database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # If running from host (not in Docker), use localhost for postgres
    if "postgres:5432" in db_url and "localhost" not in db_url:
        db_url = db_url.replace("postgres:5432", "localhost:5432")
        logger.info("Using localhost for postgres (run from host)")

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    agent = TodoAgent()

    # 1. Backup
    run_backup()

    # 2. Fetch all todos
    async with session_factory() as session:
        r = await session.execute(
            text("SELECT id, title, description, priority FROM todos ORDER BY created_at")
        )
        todos = [dict(row._mapping) for row in r.fetchall()]

    if not todos:
        logger.info("No todos to reprioritize.")
        return

    logger.info("Found %d todos. Assigning priorities via agent...", len(todos))

    # 3. For each todo, get suggested priority and update
    updated = 0
    for t in todos:
        todo_id = t["id"]
        title = t["title"] or ""
        desc = (t["description"] or "").strip()
        current = t["priority"] or "medium"
        context = f"User has this TODO: {title}"
        if desc:
            context += f". {desc}"

        extracted = await agent.extract_todos(context)
        if extracted:
            suggested = extracted[0].get("priority", "medium")
        else:
            suggested = "medium"

        if suggested not in ("high", "medium", "low"):
            suggested = "medium"

        if suggested == current:
            logger.debug("  %s: unchanged (%s)", title[:50], suggested)
            continue

        async with session_factory() as session:
            await session.execute(
                text("UPDATE todos SET priority = :p, updated_at = NOW() WHERE id = :id"),
                {"p": suggested, "id": todo_id},
            )
            await session.commit()
        updated += 1
        logger.info("  %s: %s -> %s", title[:60], current, suggested)

    logger.info("Done. Updated %d of %d todos.", updated, len(todos))


if __name__ == "__main__":
    asyncio.run(main())
