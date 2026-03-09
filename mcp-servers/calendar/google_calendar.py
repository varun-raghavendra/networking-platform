"""Google Calendar integration with retry, 5PM-10PM PT window."""

import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

import pytz

logger = logging.getLogger(__name__)

MOUNTAIN = pytz.timezone("America/Denver")


def get_calendar_service():
    """Get authenticated Google Calendar service with retry support."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import os

    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    token_path = os.environ.get("GOOGLE_TOKEN_PATH", "token.json")
    token_dir = os.path.dirname(token_path)
    if token_dir and not os.path.exists(token_dir):
        os.makedirs(token_dir, exist_ok=True)

    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("Token refresh failed: %s", e)
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _retry_with_backoff(func, max_retries: int = 3):
    """Retry with exponential backoff."""
    import time

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2**attempt
            logger.warning("Retry %s after %s due to %s", attempt + 1, wait, e)
            time.sleep(wait)


def get_free_slots(
    service,
    calendar_id: str = "primary",
    date: Optional[datetime] = None,
    start_hour: int = 17,
    end_hour: int = 22,
    duration_minutes: int = 10,
) -> list[dict]:
    """Get free slots between start_hour and end_hour Mountain Time."""
    if date is None:
        date = datetime.now(MOUNTAIN).date()

    day_start = MOUNTAIN.localize(
        datetime(date.year, date.month, date.day, start_hour, 0, 0)
    )
    day_end = MOUNTAIN.localize(datetime(date.year, date.month, date.day, end_hour, 0, 0))

    def _fetch():
        return (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

    events_result = _retry_with_backoff(_fetch)
    events = events_result.get("items", [])

    # Build busy ranges
    busy = []
    for e in events:
        start = e.get("start", {}).get("dateTime")
        end = e.get("end", {}).get("dateTime")
        if start and end:
            busy.append((datetime.fromisoformat(start.replace("Z", "+00:00")), datetime.fromisoformat(end.replace("Z", "+00:00"))))

    # Find free slots
    slots = []
    slot_duration = timedelta(minutes=duration_minutes)
    current = day_start
    while current + slot_duration <= day_end:
        slot_end = current + slot_duration
        is_busy = False
        for b_start, b_end in busy:
            if current < b_end and slot_end > b_start:
                is_busy = True
                break
        if not is_busy:
            slots.append({
                "start": current.isoformat(),
                "end": slot_end.isoformat(),
                "start_mountain": current.astimezone(MOUNTAIN).strftime("%Y-%m-%d %H:%M %Z"),
            })
        current += slot_duration

    return slots[:20]  # Limit to 20 slots


def get_free_slots_in_range(
    service,
    calendar_id: str = "primary",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    start_hour: int = 17,
    end_hour: int = 22,
    duration_minutes: int = 10,
    max_slots: int = 20,
) -> list[dict]:
    """Get free slots across a date range (e.g. week of March 16)."""
    now = datetime.now(MOUNTAIN).date()
    if start_date is None:
        start_date = now
    if end_date is None:
        end_date = start_date
    if end_date < start_date:
        end_date = start_date
    # Cap range to 14 days
    if (end_date - start_date).days > 14:
        end_date = start_date + timedelta(days=14)

    all_slots = []
    current = start_date
    while current <= end_date and len(all_slots) < max_slots:
        day_slots = get_free_slots(
            service, calendar_id, date=current,
            start_hour=start_hour, end_hour=end_hour,
            duration_minutes=duration_minutes,
        )
        for s in day_slots:
            all_slots.append(s)
            if len(all_slots) >= max_slots:
                break
        current += timedelta(days=1)
    return all_slots[:max_slots]


def schedule_event(
    service,
    summary: str,
    start_time: datetime,
    duration_minutes: int = 10,
    description: str = "",
    calendar_id: str = "primary",
) -> dict:
    """Schedule an event. start_time should be timezone-aware (Mountain)."""
    if start_time.tzinfo is None:
        start_time = MOUNTAIN.localize(start_time)
    end_time = start_time + timedelta(minutes=duration_minutes)

    event = {
        "summary": summary,
        "description": description or "",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "America/Denver",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "America/Denver",
        },
    }

    def _insert():
        return service.events().insert(calendarId=calendar_id, body=event).execute()

    result = _retry_with_backoff(_insert)
    logger.info("Scheduled event %s at %s", result.get("id"), start_time)
    return result
