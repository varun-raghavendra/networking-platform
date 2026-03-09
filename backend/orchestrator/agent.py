"""
Orchestrator Agent - Processes prompts, calls LLM, dispatches to MCP tools.
Uses OpenAI for LLM and FastMCP Client for tool execution.
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an agentic networking assistant. You process interaction prompts and take actions.

You only do: upsert contact and record interaction. Meeting and follow-up scheduling are handled by separate LLM agents.

Tools:
1. upsert_contact: Always call first. Returns {"id": "uuid"}.
2. record_interaction: Call IMMEDIATELY after upsert_contact. You MUST use the exact "id" from the upsert_contact result as contact_id. If you call both in one turn, the system will auto-fill contact_id for record_interaction.

Always call upsert_contact first, then record_interaction with the contact_id from the result.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "upsert_contact",
            "description": "Create or update contact. Always call first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string"},
                    "company": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "country": {"type": "string"},
                    "interaction_summary": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_interaction",
            "description": "Record interaction for contact",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["contact_id", "summary"],
            },
        },
    },
]


def _parse_uuid(value) -> str | None:
    """Return hex string if valid UUID, else None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        from uuid import UUID
        UUID(s)
        return s
    except (ValueError, TypeError):
        return None


class OrchestratorAgent:
    """Agent that processes prompts and calls tools."""

    def __init__(self, tool_executor: "ToolExecutor"):
        self.client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        self.tool_executor = tool_executor

    async def process_prompt(
        self,
        contact_name: str,
        interaction_summary: str,
        company: str,
        email: str | None = None,
        phone: str | None = None,
        country: str | None = None,
        last_contacted: str | None = None,
        follow_up_time: str | None = None,
        meeting_time: str | None = None,
        meeting_context: str | None = None,
    ) -> dict:
        """Process a prompt and return actions taken."""
        user_content = f"""Process this interaction:

- contact_name: {contact_name}
- interaction_summary: {interaction_summary}
- company: {company}
- email: {email or 'not specified'}
- phone: {phone or 'not specified'}
- country: {country or 'not specified'}
- last_contacted: {last_contacted or 'not specified'}
- follow_up_time: {follow_up_time or 'not specified'}
- meeting_time: {meeting_time or 'not specified'}
- meeting_context: {meeting_context or 'none'}
"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        actions = []
        contact_id = None
        max_iterations = 15
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            choice = response.choices[0]
            if not choice.message.tool_calls:
                break

            messages.append(choice.message)
            for tc in choice.message.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                if name == "record_interaction" and contact_id and not _parse_uuid(args.get("contact_id")):
                    args["contact_id"] = str(contact_id)
                logger.info("Tool call: %s %s", name, args)
                try:
                    result = await self.tool_executor.execute(name, args)
                    if name == "upsert_contact" and isinstance(result, dict):
                        contact_id = result.get("id")
                    actions.append({
                        "type": name,
                        "success": "Error" not in str(result),
                        "details": {"result": result},
                        "reasoning": None,
                    })
                    tool_content = str(result)
                except Exception as e:
                    logger.exception("Tool %s failed: %s", name, e)
                    actions.append({
                        "type": name,
                        "success": False,
                        "details": {"error": str(e)},
                        "reasoning": None,
                    })
                    tool_content = f"Error: {str(e)}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_content,
                })

        return {
            "status": "completed",
            "actions": actions,
            "contact_id": contact_id,
        }
