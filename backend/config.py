"""Backend configuration."""

import logging
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/networking"
    openai_api_key: str = ""
    mcp_calendar_url: str = "http://localhost:8001/mcp"
    mcp_contacts_url: str = "http://localhost:8002/mcp"
    mcp_todos_url: str = "http://localhost:8003/mcp"
    google_calendar_email: str = "varunraghavendra99@gmail.com"
    schedule_start_hour: int = 17  # 5 PM Pacific
    schedule_end_hour: int = 22  # 10 PM Pacific
    default_meeting_duration_minutes: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from httpx, httpcore
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
