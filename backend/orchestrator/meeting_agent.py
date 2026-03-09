"""Meeting time agent - decides when to schedule a meeting from input context."""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

MOUNTAIN = ZoneInfo("America/Denver")

MEETING_PROMPT = """You are a meeting scheduling agent. Given the interaction context and CURRENT date/time, determine when to schedule a meeting with this contact.

CRITICAL: All dates and times must be in Mountain Time (America/Denver, GMT-7).
CRITICAL: Return ONLY FUTURE dates - never past dates. Today's date is provided below.
CRITICAL: Use the current date to interpret relative phrases (e.g. "week of March 16" = that week in the given year).

You must return a JSON object with exactly one key:
- scheduled_time: The date/time for the meeting in Mountain Time, or null if no meeting should be scheduled.
  Use format "YYYY-MM-DD HH:MM" (e.g. "2026-03-16 18:00") or natural: "tomorrow 6pm", "week of March 16 2026".
  Prefer 5PM-10PM Mountain when no specific time given.
  If meeting_time or meeting_context indicates a meeting, return the appropriate time.

Return ONLY valid JSON, e.g. {"scheduled_time": "2026-03-16 18:00"} or {"scheduled_time": null}."""


class MeetingAgent:
    """Agent that decides meeting time from context."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def get_meeting_time(
        self,
        contact_name: str,
        interaction_summary: str,
        meeting_time: str | None = None,
        meeting_context: str | None = None,
        last_contacted: str | None = None,
    ) -> str | None:
        """Return scheduled_time for meeting, or None if no meeting."""
        now = datetime.now(MOUNTAIN)
        now_str = now.strftime("%Y-%m-%d %H:%M")
        user_content = f"""CURRENT DATE AND TIME (Mountain Time): {now_str}

Contact: {contact_name}
Interaction summary: {interaction_summary}
Meeting time from user: {meeting_time or 'not specified'}
Meeting context: {meeting_context or 'none'}
Last contacted: {last_contacted or 'not specified'}

Determine if a meeting should be scheduled and when. MUST be in the future. Use Mountain Time. Return JSON with scheduled_time."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": MEETING_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return None
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "scheduled_time" in parsed:
                val = parsed["scheduled_time"]
                return str(val) if val else None
            return None
        except Exception as e:
            logger.exception("MeetingAgent get_meeting_time failed: %s", e)
            return None
