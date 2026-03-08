"""FastMCP Calendar Server - Google Calendar tools."""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import pytz
from fastmcp import FastMCP

from google_calendar import get_calendar_service, get_free_slots, schedule_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("Calendar")

PACIFIC = pytz.timezone("America/Los_Angeles")
START_HOUR = int(os.environ.get("SCHEDULE_START_HOUR", "17"))
END_HOUR = int(os.environ.get("SCHEDULE_END_HOUR", "22"))
DEFAULT_DURATION = int(os.environ.get("DEFAULT_MEETING_DURATION_MINUTES", "10"))
CALENDAR_EMAIL = os.environ.get("GOOGLE_CALENDAR_EMAIL", "varunraghavendra99@gmail.com")


def _parse_datetime(s: str) -> Optional[datetime]:
    """Parse natural date string to datetime in Pacific."""
    if not s or not s.strip():
        return None
    s = s.strip().lower()
    now = datetime.now(PACIFIC)
    if "tomorrow" in s:
        base = now + timedelta(days=1)
    elif "today" in s:
        base = now
    else:
        base = now
    # Default to 6pm if no time
    hour, minute = 18, 0
    for h in range(17, 22):
        if str(h) in s or f"{h}:" in s:
            hour = h
            break
    result = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return result if result.tzinfo else PACIFIC.localize(result)


@mcp.tool()
def get_calendar_free_slots(
    date: Optional[str] = None,
    duration_minutes: int = DEFAULT_DURATION,
) -> str:
    """
    Get available time slots in the calendar for the given date.
    Only returns slots between 5PM and 10PM Pacific Time.
    date: Optional date string (YYYY-MM-DD) or 'today'/'tomorrow'. Default: today.
    duration_minutes: Length of slot needed (default 10).
    """
    logger.info("get_calendar_free_slots date=%s duration=%s", date, duration_minutes)
    try:
        service = get_calendar_service()
        dt = None
        if date:
            if date.lower() in ("today", "tomorrow"):
                now = datetime.now(PACIFIC)
                if "tomorrow" in date.lower():
                    dt = (now + timedelta(days=1)).date()
                else:
                    dt = now.date()
            else:
                from datetime import date as dt_date
                parts = date.split("-")
                if len(parts) == 3:
                    dt = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))

        slots = get_free_slots(
            service,
            "primary",
            date=dt,
            start_hour=START_HOUR,
            end_hour=END_HOUR,
            duration_minutes=duration_minutes,
        )
        if not slots:
            return "No free slots available between 5PM and 10PM Pacific."
        return str(slots)
    except Exception as e:
        logger.exception("get_calendar_free_slots failed: %s", e)
        return f"Error: {str(e)}"


@mcp.tool()
def schedule_meeting(
    contact_name: str,
    summary: str,
    scheduled_time: Optional[str] = None,
    duration_minutes: int = DEFAULT_DURATION,
    description: str = "",
) -> str:
    """
    Schedule a meeting on Google Calendar.
    If scheduled_time is not provided, uses the first available 10-minute slot between 5PM-10PM Pacific.
    scheduled_time: e.g. '2025-03-10 18:00' or 'tomorrow 6pm' or None for first available.
    """
    logger.info("schedule_meeting contact=%s time=%s", contact_name, scheduled_time)
    try:
        service = get_calendar_service()
        if scheduled_time:
            start_dt = _parse_datetime(scheduled_time)
            if not start_dt:
                start_dt = datetime.now(PACIFIC)
        else:
            slots = get_free_slots(
                service, "primary", start_hour=START_HOUR, end_hour=END_HOUR, duration_minutes=duration_minutes
            )
            if not slots:
                return "Error: No free slots between 5PM-10PM Pacific."
            start_dt = datetime.fromisoformat(slots[0]["start"])

        event = schedule_event(
            service,
            summary=f"Meeting: {contact_name}",
            start_time=start_dt,
            duration_minutes=duration_minutes,
            description=description or summary,
        )
        return f"Success: Meeting scheduled at {start_dt.strftime('%Y-%m-%d %H:%M %Z')} (id={event.get('id')})"
    except Exception as e:
        logger.exception("schedule_meeting failed: %s", e)
        return f"Error: {str(e)}"


@mcp.tool()
def schedule_follow_up(
    contact_name: str,
    summary: str,
    scheduled_time: Optional[str] = None,
) -> str:
    """
    Schedule a follow-up on Google Calendar.
    If no time specified, defaults to 2 days from now. Uses 5PM-10PM Pacific window.
    scheduled_time: e.g. 'in 2 days' - defaults to 2 days from now at 6pm Pacific.
    """
    logger.info("schedule_follow_up contact=%s time=%s", contact_name, scheduled_time)
    try:
        service = get_calendar_service()
        now = datetime.now(PACIFIC)
        if scheduled_time:
            start_dt = _parse_datetime(scheduled_time)
            if not start_dt:
                start_dt = now + timedelta(days=2)
                start_dt = start_dt.replace(hour=18, minute=0, second=0)
        else:
            start_dt = now + timedelta(days=2)
            start_dt = start_dt.replace(hour=18, minute=0, second=0)
            if start_dt.tzinfo is None:
                start_dt = PACIFIC.localize(start_dt)

        event = schedule_event(
            service,
            summary=f"Follow-up: {contact_name}",
            start_time=start_dt,
            duration_minutes=DEFAULT_DURATION,
            description=summary,
        )
        return f"Success: Follow-up scheduled at {start_dt.strftime('%Y-%m-%d %H:%M %Z')} (id={event.get('id')})"
    except Exception as e:
        logger.exception("schedule_follow_up failed: %s", e)
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8001)
