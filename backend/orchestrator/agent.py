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

Input format:
- contact_name: Full name of the contact
- interaction_summary: Summary of the conversation
- company: Company the contact belongs to
- Optional: email, phone, country, last_contacted, follow_up_time, meeting_time, meeting_context

You have these tools. Use them as needed:

1. upsert_contact: Always call first to create/update the contact. Use interaction_summary param. Returns {"id": "uuid"}.
2. record_interaction: Call IMMEDIATELY after upsert_contact. You MUST pass contact_id = the exact "id" string from the upsert_contact result. Pass summary = interaction_summary.
3. decide_follow_up: Decide if a follow-up should be scheduled. If the interaction mentions a specific time, use it. Otherwise default to 2 days.
4. schedule_follow_up: Schedule follow-up on calendar. Use contact_name and summary. Pass scheduled_time if specified.
5. decide_meeting: Decide if a meeting needs to be scheduled based on the interaction.
6. schedule_meeting: Schedule meeting. If meeting_time in prompt, use it. Else use first available slot (5PM-10PM Pacific).
7. decide_todo: Decide if a TODO should be created from action items in the interaction.
8. create_todo: Create TODO with title and optional description. Set created_by_agent=true.
9. get_calendar_free_slots: Call when you need to find available slots (e.g. before schedule_meeting with no time).

Always upsert_contact and record_interaction. Then decide and execute follow_up, meeting, todo as appropriate.
Log your reasoning briefly in the response.
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
    {
        "type": "function",
        "function": {
            "name": "schedule_follow_up",
            "description": "Schedule follow-up on calendar. Default 2 days if no time specified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "summary": {"type": "string"},
                    "scheduled_time": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_meeting",
            "description": "Schedule meeting. Use first available 5PM-10PM Pacific slot if no time given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "summary": {"type": "string"},
                    "scheduled_time": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                    "description": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_todo",
            "description": "Create TODO from action item",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "contact_id": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_free_slots",
            "description": "Get available slots between 5PM-10PM Pacific",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                },
            },
        },
    },
]


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
