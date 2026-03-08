"""Tool executor - routes tool calls to MCP servers or backend."""

import asyncio
import logging
from typing import Any, Optional
from uuid import UUID

from database import get_session

from services import audit, contacts, todos

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools by calling MCP servers or backend services."""

    def __init__(self, mcp_calendar_url: str):
        self.mcp_calendar_url = mcp_calendar_url

    async def execute(self, tool_name: str, args: dict) -> Any:
        """Execute a tool and return result."""
        if tool_name == "upsert_contact":
            return await self._upsert_contact(args)
        if tool_name == "record_interaction":
            return await self._record_interaction(args)
        if tool_name in ("schedule_follow_up", "schedule_meeting", "get_calendar_free_slots"):
            return await self._call_calendar_mcp(tool_name, args)
        if tool_name == "create_todo":
            return await self._create_todo(args)
        return f"Unknown tool: {tool_name}"

    async def _upsert_contact(self, args: dict) -> dict:
        async with get_session() as session:
            result = await contacts.upsert_contact(
                session,
                full_name=args.get("full_name", ""),
                company_name=args.get("company"),
                email=args.get("email"),
                phone=args.get("phone"),
                country=args.get("country"),
                notes=args.get("notes"),
                interaction_summary=args.get("interaction_summary"),
            )
            await audit.log_audit(
                session,
                "contact_upsert",
                "contact",
                result["id"],
                {"created": result.get("created"), "name": args.get("full_name")},
            )
            return result

    def _parse_uuid(self, value: Any) -> Optional[UUID]:
        """Extract a valid UUID from various formats (str, dict with id key, etc)."""
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        if isinstance(value, dict):
            value = value.get("id")
        s = str(value).strip()
        if not s:
            return None
        try:
            return UUID(s)
        except (ValueError, TypeError):
            return None

    async def _record_interaction(self, args: dict) -> dict:
        contact_id = self._parse_uuid(args.get("contact_id"))
        summary = args.get("summary", "")
        if not contact_id:
            return "Error: contact_id must be the UUID returned by upsert_contact (e.g. pass the id from the upsert_contact result)"
        async with get_session() as session:
            await contacts.record_interaction(session, contact_id, summary)
            return {"success": True}

    async def _create_todo(self, args: dict) -> dict:
        async with get_session() as session:
            result = await todos.create_todo(
                session,
                title=args.get("title", ""),
                description=args.get("description"),
                contact_id=UUID(args["contact_id"]) if args.get("contact_id") else None,
                created_by_agent=True,
            )
            await audit.log_audit(
                session,
                "todo_create",
                "todo",
                result["id"],
                {"title": args.get("title")},
            )
            return result

    async def _call_calendar_mcp(self, tool_name: str, args: dict) -> str:
        """Call Calendar MCP server via HTTP."""
        from fastmcp import Client

        client = Client(self.mcp_calendar_url)
        async with client:
            result = await client.call_tool(tool_name, args)
            content = getattr(result, "content", result) or []
            if content and hasattr(content[0], "text"):
                return content[0].text
            return str(result)
