"""FastMCP Calendar Server - Google Calendar tools."""

import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

import pytz
from fastmcp import FastMCP

from google_calendar import (
    get_calendar_service,
    get_free_slots,
    get_free_slots_in_range,
    schedule_event,
)

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


def _parse_date(s: str) -> Optional[date]:
    """Parse date string to date. Handles YYYY-MM-DD, March 16 2026, week of March 16 2026."""
    if not s or not s.strip():
        return None
    s0 = s.strip()
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s0)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Month DD, YYYY or Month DD YYYY
    months = "jan feb mar apr may jun jul aug sep oct nov dec"
    parts = s0.lower().replace(",", " ").split()
    for i, p in enumerate(parts):
        if p in months.split() and i + 1 < len(parts):
            try:
                month = months.split().index(p) + 1
                day = int(parts[i + 1])
                year = int(parts[i + 2]) if i + 2 < len(parts) and parts[i + 2].isdigit() else datetime.now(PACIFIC).year
                return date(year, month, day)
            except (ValueError, IndexError):
                pass
    return None


def _parse_week_range(s: str) -> Optional[tuple[date, date]]:
    """Parse 'week of March 16, 2026' -> (start_date, end_date)."""
    if not s or "week" not in s.lower():
        return None
    s0 = re.sub(r"week\s+of\s+", "", s.strip(), flags=re.I).strip()
    d = _parse_date(s0)
    if not d:
        return None
    # Week = Mon-Sun; use the given date as start of "week" (or first day containing it)
    start = d
    end = start + timedelta(days=6)
    return (start, end)


def _parse_datetime(s: str) -> Optional[datetime]:
    """Parse natural date string to datetime in Pacific."""
    if not s or not s.strip():
        return None
    s0 = s.strip().lower()
    now = datetime.now(PACIFIC)
    base = None
    if "tomorrow" in s0:
        base = (now + timedelta(days=1)).date()
    elif "today" in s0:
        base = now.date()
    elif "in " in s0 and " day" in s0:
        m = re.search(r"in\s+(\d+)\s+days?", s0)
        if m:
            base = (now + timedelta(days=int(m.group(1)))).date()
    else:
        base = _parse_date(s)
    if base is None:
        base = now.date()
    hour, minute = 18, 0
    for h in range(17, 22):
        if str(h) in s0 or f"{h}:" in s0 or f"{h}pm" in s0 or f"{h} pm" in s0:
            hour = h
            break
    result = PACIFIC.localize(datetime(base.year, base.month, base.day, hour, minute, 0))
    return result


def _resolve_date(d: Optional[str]):
    """Resolve date string to date object."""
    if not d:
        return datetime.now(PACIFIC).date()
    d0 = d.strip().lower()
    if d0 == "tomorrow":
        return (datetime.now(PACIFIC) + timedelta(days=1)).date()
    if d0 == "today":
        return datetime.now(PACIFIC).date()
    return _parse_date(d) or datetime.now(PACIFIC).date()


@mcp.tool()
def get_calendar_free_slots(
    date: Optional[str] = None,
    duration_minutes: int = DEFAULT_DURATION,
) -> str:
    """
    Get available time slots in the calendar for the given date.
    Only returns slots between 5PM and 10PM Pacific Time.
    date: Optional date string (YYYY-MM-DD), 'today', or 'tomorrow'. Default: today.
    duration_minutes: Length of slot needed (default 10).
    """
    logger.info("get_calendar_free_slots date=%s duration=%s", date, duration_minutes)
    try:
        service = get_calendar_service()
        dt = _resolve_date(date)
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
def get_calendar_free_slots_in_range(
    start_date: str,
    end_date: str,
    duration_minutes: int = DEFAULT_DURATION,
) -> str:
    """
    Get available slots across a date range (e.g. for 'week of March 16').
    Use when the user says 'sometime in the week of X' or 'during the week of X'.
    start_date: YYYY-MM-DD or 'March 16 2026'
    end_date: YYYY-MM-DD or 'March 22 2026'
    duration_minutes: Length of slot needed (default 10).
    """
    logger.info("get_calendar_free_slots_in_range %s to %s", start_date, end_date)
    try:
        service = get_calendar_service()
        start = _parse_date(start_date) or datetime.now(PACIFIC).date()
        end = _parse_date(end_date) or start + timedelta(days=6)
        if end < start:
            end = start + timedelta(days=6)
        slots = get_free_slots_in_range(
            service,
            "primary",
            start_date=start,
            end_date=end,
            start_hour=START_HOUR,
            end_hour=END_HOUR,
            duration_minutes=duration_minutes,
            max_slots=20,
        )
        if not slots:
            return f"No free slots between {start} and {end} (5PM-10PM Pacific)."
        return str(slots)
    except Exception as e:
        logger.exception("get_calendar_free_slots_in_range failed: %s", e)
        return f"Error: {str(e)}"


def _find_available_slot(
    service,
    preferred_time: Optional[datetime],
    duration_minutes: int,
) -> Optional[datetime]:
    """Return a free slot: preferred time if it falls in a free slot, else first free that day."""
    day = (preferred_time or datetime.now(PACIFIC)).date()
    slots = get_free_slots(
        service, "primary", date=day,
        start_hour=START_HOUR, end_hour=END_HOUR,
        duration_minutes=duration_minutes,
    )
    if not slots:
        return None
    if preferred_time:
        pref_start = preferred_time
        pref_end = pref_start + timedelta(minutes=duration_minutes)
        for s in slots:
            slot_start = datetime.fromisoformat(s["start"])
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            if slot_start <= pref_start and pref_end <= slot_end:
                return slot_start
    return datetime.fromisoformat(slots[0]["start"])


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
    If scheduled_time not provided, uses first available slot 5PM-10PM Pacific.
    scheduled_time: '2026-03-18 18:00', 'tomorrow 6pm', or 'week of March 16 2026'.
    For 'week of X', finds first available slot in that week to avoid conflicts.
    """
    logger.info("schedule_meeting contact=%s time=%s", contact_name, scheduled_time)
    try:
        service = get_calendar_service()
        start_dt = None
        if scheduled_time:
            week_range = _parse_week_range(scheduled_time)
            if week_range:
                start_d, end_d = week_range
                slots = get_free_slots_in_range(
                    service, "primary",
                    start_date=start_d, end_date=end_d,
                    start_hour=START_HOUR, end_hour=END_HOUR,
                    duration_minutes=duration_minutes,
                    max_slots=1,
                )
                if slots:
                    start_dt = datetime.fromisoformat(slots[0]["start"])
            else:
                parsed = _parse_datetime(scheduled_time)
                start_dt = _find_available_slot(service, parsed, duration_minutes)
                if not start_dt and parsed:
                    start_dt = parsed
        if not start_dt:
            slots = get_free_slots(
                service, "primary", start_hour=START_HOUR, end_hour=END_HOUR,
                duration_minutes=duration_minutes,
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
    scheduled_time: e.g. '2026-03-18 6pm', 'week of March 16 2026'. Uses first available slot.
    """
    logger.info("schedule_follow_up contact=%s time=%s", contact_name, scheduled_time)
    try:
        service = get_calendar_service()
        now = datetime.now(PACIFIC)
        start_dt = None
        if scheduled_time:
            week_range = _parse_week_range(scheduled_time)
            if week_range:
                start_d, end_d = week_range
                slots = get_free_slots_in_range(
                    service, "primary",
                    start_date=start_d, end_date=end_d,
                    start_hour=START_HOUR, end_hour=END_HOUR,
                    duration_minutes=DEFAULT_DURATION,
                    max_slots=1,
                )
                if slots:
                    start_dt = datetime.fromisoformat(slots[0]["start"])
            else:
                parsed = _parse_datetime(scheduled_time)
                start_dt = _find_available_slot(service, parsed, DEFAULT_DURATION)
                if not start_dt and parsed:
                    start_dt = parsed
        if not start_dt:
            default_day = (now + timedelta(days=2)).date()
            slots = get_free_slots(
                service, "primary", date=default_day,
                start_hour=START_HOUR, end_hour=END_HOUR,
                duration_minutes=DEFAULT_DURATION,
            )
            if slots:
                start_dt = datetime.fromisoformat(slots[0]["start"])
            else:
                start_dt = PACIFIC.localize(
                    datetime(default_day.year, default_day.month, default_day.day, 18, 0, 0)
                )
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
