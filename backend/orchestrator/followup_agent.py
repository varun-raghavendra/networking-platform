"""Follow-up date agent - calculates next follow-up date/time from full context."""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

MOUNTAIN = ZoneInfo("America/Denver")

FOLLOWUP_PROMPT = """You are a follow-up scheduling agent. Given the interaction context and CURRENT date/time, determine when the user should follow up with this contact.

CRITICAL: All dates and times must be in Mountain Time (America/Denver, GMT-7).
CRITICAL: Return ONLY FUTURE dates - never past dates. Today's date is provided below.
CRITICAL: Use the current date to interpret relative phrases (e.g. "in 2 days" = current date + 2 days).

You must return a JSON object with exactly one key:
- scheduled_time: The exact date and time for the follow-up in Mountain Time.
  Use format "YYYY-MM-DD HH:MM" (e.g. "2026-03-12 18:00") for specificity.
  Or natural language: "tomorrow 6pm", "in 2 days", "week of March 16 2026" - these will be interpreted relative to the current date.
  Prefer 5PM-10PM Mountain when no specific time given.
  DEFAULT: When the user has NOT specified a follow-up time, schedule within 24 hours max (e.g. tomorrow at 6pm, or same-day evening if still in window).
  If the user provided follow_up_time (e.g. "in 2 days"), use that.
  If no follow-up is needed, set scheduled_time to null.

Return ONLY valid JSON, e.g. {"scheduled_time": "2026-03-12 18:00"} or {"scheduled_time": null}."""


class FollowupAgent:
    """Agent that calculates next follow-up date from full context."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def get_followup_time(
        self,
        contact_name: str,
        interaction_summary: str,
        follow_up_time: str | None = None,
        meeting_time: str | None = None,
        meeting_context: str | None = None,
        last_contacted: str | None = None,
    ) -> str | None:
        """Return scheduled_time string for follow-up, or None if no follow-up."""
        now = datetime.now(MOUNTAIN)
        now_str = now.strftime("%Y-%m-%d %H:%M")
        user_content = f"""CURRENT DATE AND TIME (Mountain Time): {now_str}

Contact: {contact_name}
Interaction summary: {interaction_summary}
User's follow-up hint: {follow_up_time or 'not specified'}
Meeting time (if any): {meeting_time or 'not specified'}
Meeting context: {meeting_context or 'none'}
Last contacted: {last_contacted or 'not specified'}

Determine the next follow-up date and time. MUST be in the future. Use Mountain Time. When no follow-up hint is given, default to within 24 hours (max). Return JSON with scheduled_time."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": FOLLOWUP_PROMPT},
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
            logger.exception("FollowupAgent get_followup_time failed: %s", e)
            return None
