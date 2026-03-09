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

Scheduling rules (IMPORTANT - prevents conflicts):
- When meeting_time says "sometime in the week of March 16" or "week of March 16, 2026": pass that EXACT phrase to schedule_meeting (e.g. scheduled_time="week of March 16 2026"). The calendar will find the first available slot in that week.
- When meeting_time is vague (e.g. "next week", "sometime in March"): call get_calendar_free_slots_in_range with start_date and end_date for that range, then pass the first slot to schedule_meeting.
- NEVER guess a specific time like "6pm" for multiple meetings - that causes overlapping events. Each schedule_meeting/schedule_follow_up finds a free slot; if scheduling both a meeting and follow-up, the tools handle different slots.
- For explicit times (e.g. "tomorrow 6pm"), pass them to schedule_meeting; the tool checks availability and picks a free slot if busy.

Tools:
1. upsert_contact: Always call first. Returns {"id": "uuid"}.
2. record_interaction: Call IMMEDIATELY after upsert_contact. Pass contact_id from upsert_contact result.
3. schedule_follow_up: Schedule follow-up. Pass scheduled_time if specified (e.g. "week of March 16 2026").
4. schedule_meeting: Schedule meeting. Pass scheduled_time: exact datetime, or "week of March 16 2026" for flexible scheduling.
5. create_todo: Create TODO. Set created_by_agent=true.
6. get_calendar_free_slots: Get slots for one date (YYYY-MM-DD, today, tomorrow).
7. get_calendar_free_slots_in_range: Get slots across dates. Use for "week of X" or date ranges.

Always upsert_contact and record_interaction. Then schedule follow_up/meeting/todo as appropriate.
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
            "description": "Schedule meeting. Pass scheduled_time: '2026-03-18 18:00', 'tomorrow 6pm', or 'week of March 16 2026' for flexible week scheduling. Tool finds first free slot to avoid conflicts.",
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
            "description": "Get available slots for one date (5PM-10PM Pacific). date: YYYY-MM-DD, today, or tomorrow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_free_slots_in_range",
            "description": "Get slots across a date range. Use when user says 'week of March 16' or 'sometime in the week of X'. start_date and end_date: YYYY-MM-DD or 'March 16 2026'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                },
                "required": ["start_date", "end_date"],
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
