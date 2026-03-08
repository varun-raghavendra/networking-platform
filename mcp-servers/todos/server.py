"""FastMCP TODOs Server - TODO management tools."""

import logging
import os
from typing import Optional

import httpx
from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("TODOs")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


def _call_backend(method: str, path: str, **kwargs) -> dict:
    """Call backend API with retry."""
    url = f"{BACKEND_URL}{path}"
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.request(method, url, **kwargs)
                r.raise_for_status()
                return r.json() if r.content else {}
        except Exception as e:
            if attempt == 2:
                raise
            import time
            time.sleep(2**attempt)
    return {}


@mcp.tool()
def create_todo(
    title: str,
    description: Optional[str] = None,
    contact_id: Optional[str] = None,
    created_by_agent: bool = True,
) -> str:
    """
    Create a TODO item. Use when the interaction indicates an action item.
    """
    logger.info("create_todo title=%s", title)
    try:
        payload = {
            "title": title,
            "description": description,
            "contact_id": contact_id,
            "created_by_agent": created_by_agent,
        }
        data = _call_backend("POST", "/api/internal/todos", json=payload)
        return f"Success: todo id={data.get('id')}"
    except Exception as e:
        logger.exception("create_todo failed: %s", e)
        return f"Error: {str(e)}"


@mcp.tool()
def list_todos(status: str = "pending") -> str:
    """List TODO items. status: pending, done, or all."""
    try:
        params = {} if status == "all" else {"status": status}
        data = _call_backend("GET", "/api/internal/todos", params=params)
        return str(data)
    except Exception as e:
        logger.exception("list_todos failed: %s", e)
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8003)
