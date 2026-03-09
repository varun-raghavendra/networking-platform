"""Backend API - FastAPI application."""

import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import re

from config import get_settings, setup_logging
from database import get_session, run_migrations
from orchestrator.agent import OrchestratorAgent
from orchestrator.followup_agent import FollowupAgent
from orchestrator.meeting_agent import MeetingAgent
from orchestrator.summary_agent import SummaryAgent
from orchestrator.todo_agent import TodoAgent
from orchestrator.tool_executor import ToolExecutor
from services import audit, contacts, export_service, todos

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    yield
    # shutdown


app = FastAPI(title="Networking Platform API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---
class PromptInput(BaseModel):
    contact_id: str | None = None  # For existing contact flow
    contact_name: str | None = None  # Required for new contact
    interaction_summary: str
    company: str | None = None  # Required for new contact
    email: str | None = None  # New contact only
    phone: str | None = None  # New contact only
    country: str | None = None  # New contact only, default United States
    last_contacted: str | None = None
    follow_up_time: str | None = None
    meeting_time: str | None = None
    meeting_context: str | None = None


class UpsertContactInput(BaseModel):
    full_name: str
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    notes: str | None = None
    interaction_summary: str | None = None
    tags: list[str] | None = None


class ContactUpdateInput(BaseModel):
    country: str | None = None
    phone: str | None = None
    email: str | None = None
    last_contacted_at: str | None = None  # ISO datetime, e.g. 2026-03-01 or 2026-03-01T18:00:00


class InteractionInput(BaseModel):
    summary: str


class TodoCreateInput(BaseModel):
    title: str
    description: str | None = None
    contact_id: str | None = None
    created_by_agent: bool = False
    priority: str = "medium"


# --- Public API ---
@app.post("/api/prompts")
async def process_prompt(input: PromptInput):
    """Process interaction prompt - orchestrate agent and tools."""
    contact_name = input.contact_name
    company = input.company
    email = input.email
    phone = input.phone
    country = input.country

    if input.contact_id:
        async with get_session() as session:
            c = await contacts.get_contact(session, UUID(input.contact_id))
            if not c:
                raise HTTPException(404, "Contact not found")
            contact_name = c.get("full_name") or ""
            company = c.get("company_name") or ""
            email = c.get("email")
            phone = c.get("phone")
            country = c.get("country")

    if not contact_name or not company:
        raise HTTPException(400, "contact_name and company required for new contact; or select existing contact")

    logger.info("Processing prompt for contact %s", contact_name)
    settings = get_settings()
    executor = ToolExecutor(settings.mcp_calendar_url)
    agent = OrchestratorAgent(executor)
    result = await agent.process_prompt(
        contact_name=contact_name,
        interaction_summary=input.interaction_summary,
        company=company,
        email=email,
        phone=phone,
        country=country,
        last_contacted=input.last_contacted,
        follow_up_time=None,
        meeting_time=input.meeting_time,
        meeting_context=input.meeting_context,
    )
    contact_id = result.get("contact_id")
    if result.get("status") == "completed" and contact_id:
        if input.last_contacted:
            parsed = contacts._parse_datetime_safe(input.last_contacted)
            if parsed:
                async with get_session() as session:
                    await contacts.update_contact_fields(
                        session, UUID(contact_id), last_contacted_at=input.last_contacted
                    )
        if input.meeting_time or input.meeting_context:
            meeting_agent = MeetingAgent()
            meeting_scheduled_time = await meeting_agent.get_meeting_time(
                contact_name=contact_name,
                interaction_summary=input.interaction_summary,
                meeting_time=input.meeting_time,
                meeting_context=input.meeting_context,
                last_contacted=input.last_contacted,
            )
            if meeting_scheduled_time:
                try:
                    meeting_result = await executor._call_calendar_mcp(
                        "schedule_meeting",
                        {
                            "contact_name": contact_name,
                            "summary": input.interaction_summary,
                            "scheduled_time": meeting_scheduled_time,
                        },
                    )
                    result.setdefault("actions", []).append({
                        "type": "schedule_meeting",
                        "success": "Error" not in meeting_result,
                        "details": {"result": meeting_result},
                    })
                except Exception as e:
                    logger.exception("schedule_meeting failed: %s", e)
                    result.setdefault("actions", []).append({"type": "schedule_meeting", "success": False, "details": {"error": str(e)}})
        summary_agent = SummaryAgent()
        one_line = await summary_agent.get_one_line_summary(input.interaction_summary)
        if one_line:
            async with get_session() as session:
                await contacts.update_contact_fields(
                    session, UUID(contact_id), last_interaction_summary=one_line
                )
        todo_agent = TodoAgent()
        todo_items = await todo_agent.extract_todos(input.interaction_summary)
        for item in todo_items:
            try:
                tr = await executor._create_todo({
                    "title": item["title"],
                    "description": item.get("description"),
                    "contact_id": contact_id,
                    "priority": item.get("priority", "medium"),
                })
                result.setdefault("actions", []).append({"type": "create_todo", "success": "Error" not in str(tr), "details": {"result": tr}})
            except Exception as e:
                logger.exception("create_todo failed: %s", e)
                result.setdefault("actions", []).append({"type": "create_todo", "success": False, "details": {"error": str(e)}})
        followup_agent = FollowupAgent()
        scheduled_time = await followup_agent.get_followup_time(
            contact_name=contact_name,
            interaction_summary=input.interaction_summary,
            follow_up_time=input.follow_up_time,
            meeting_time=input.meeting_time,
            meeting_context=input.meeting_context,
            last_contacted=input.last_contacted,
        )
        if scheduled_time:
            try:
                followup_result = await executor._call_calendar_mcp(
                    "schedule_follow_up",
                    {"contact_name": contact_name, "summary": input.interaction_summary, "scheduled_time": scheduled_time},
                )
                result.setdefault("actions", []).append({"type": "schedule_follow_up", "success": "Error" not in followup_result, "details": {"result": followup_result}})
                m = re.search(r"(\d{4}-\d{2}-\d{2})[T\s]+(\d{2}:\d{2})", followup_result)
                if m:
                    from datetime import datetime
                    from zoneinfo import ZoneInfo
                    dt_str = f"{m.group(1)}T{m.group(2)}:00"
                    try:
                        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("America/Denver"))
                        async with get_session() as session:
                            await contacts.set_next_follow_up(session, UUID(contact_id), dt)
                    except Exception:
                        pass
            except Exception as e:
                logger.exception("schedule_follow_up failed: %s", e)
                result.setdefault("actions", []).append({"type": "schedule_follow_up", "success": False, "details": {"error": str(e)}})
    return {"id": "prompt-1", **result}


@app.get("/api/contacts")
async def list_contacts(
    limit: int = Query(50, le=100),
    offset: int = 0,
    sort: str = "last_contacted_desc",
    search: str | None = None,
):
    """List contacts for warm dashboard."""
    async with get_session() as session:
        rows, total = await contacts.list_contacts(session, limit, offset, sort, search)
        return {"contacts": rows, "total": total}


@app.get("/api/contacts/{contact_id}")
async def get_contact(contact_id: UUID):
    """Get single contact."""
    async with get_session() as session:
        c = await contacts.get_contact(session, contact_id)
        if not c:
            raise HTTPException(404, "Contact not found")
        return c


@app.patch("/api/contacts/{contact_id}")
async def update_contact(contact_id: UUID, input: ContactUpdateInput):
    """Update contact country, phone, email, last_contacted_at."""
    async with get_session() as session:
        result = await contacts.update_contact_fields(
            session, contact_id,
            country=input.country,
            phone=input.phone,
            email=input.email,
            last_contacted_at=input.last_contacted_at,
        )
        if not result:
            raise HTTPException(404, "Contact not found")
        return result


@app.get("/api/contacts/{contact_id}/interactions")
async def get_contact_interactions(contact_id: UUID, limit: int = 20):
    """Get interaction history for contact."""
    async with get_session() as session:
        return await contacts.get_contact_interactions(session, contact_id, limit)


@app.get("/api/reminders")
async def get_reminders(days: int = 90):
    """Get contacts not contacted in N days (nudge reminders)."""
    async with get_session() as session:
        return await contacts.get_stale_contacts(session, days)


@app.get("/api/todos")
async def list_todos(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "priority_asc",
):
    """List TODO items. sort: priority_asc, priority_desc, created_asc, created_desc"""
    async with get_session() as session:
        rows, total = await todos.list_todos(session, status, limit, offset, sort)
        return {"todos": rows, "total": total}


@app.post("/api/todos")
async def create_todo_manual(input: TodoCreateInput):
    """Create TODO (manual)."""
    async with get_session() as session:
        return await todos.create_todo(
            session,
            title=input.title,
            description=input.description,
            contact_id=UUID(input.contact_id) if input.contact_id else None,
            created_by_agent=input.created_by_agent,
            priority=input.priority,
        )


class TodoUpdateInput(BaseModel):
    status: str | None = None
    priority: str | None = None


@app.patch("/api/todos/{todo_id}")
async def update_todo(todo_id: UUID, input: TodoUpdateInput | None = None):
    """Update TODO (e.g. mark done, change priority)."""
    inp = input or TodoUpdateInput()
    async with get_session() as session:
        return await todos.update_todo(session, todo_id, status=inp.status, priority=inp.priority)


@app.get("/api/export/contacts")
async def export_contacts_csv():
    """Export contacts as CSV."""
    async with get_session() as session:
        csv_content = await export_service.export_contacts_csv(session)
        from fastapi.responses import Response
        return Response(csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=contacts.csv"})


@app.get("/api/export/todos")
async def export_todos_csv():
    """Export TODOs as CSV."""
    async with get_session() as session:
        csv_content = await export_service.export_todos_csv(session)
        from fastapi.responses import Response
        return Response(csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=todos.csv"})


@app.get("/api/audit")
async def list_audit_log(limit: int = 50, offset: int = 0):
    """List audit log entries."""
    from sqlalchemy import text
    async with get_session() as session:
        r = await session.execute(
            text("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset},
        )
        rows = r.fetchall()
        return {"entries": [dict(row._mapping) for row in rows]}


# --- Internal API (for MCP servers) ---
@app.post("/api/internal/contacts/upsert")
async def internal_upsert_contact(input: UpsertContactInput):
    async with get_session() as session:
        return await contacts.upsert_contact(
            session,
            full_name=input.full_name,
            company_name=input.company_name,
            email=input.email,
            phone=input.phone,
            country=input.country,
            notes=input.notes,
            interaction_summary=input.interaction_summary,
            tags=input.tags,
        )


@app.post("/api/internal/contacts/{contact_id}/interaction")
async def internal_record_interaction(contact_id: UUID, input: InteractionInput):
    async with get_session() as session:
        await contacts.record_interaction(session, contact_id, input.summary)
        return {"success": True}


@app.get("/api/internal/contacts/{contact_id}")
async def internal_get_contact(contact_id: UUID):
    async with get_session() as session:
        c = await contacts.get_contact(session, contact_id)
        if not c:
            raise HTTPException(404, "Not found")
        return c


@app.post("/api/internal/todos")
async def internal_create_todo(input: TodoCreateInput):
    async with get_session() as session:
        return await todos.create_todo(
            session,
            title=input.title,
            description=input.description,
            contact_id=UUID(input.contact_id) if input.contact_id else None,
            created_by_agent=input.created_by_agent,
            priority=input.priority,
        )


@app.get("/api/internal/todos")
async def internal_list_todos(status: str | None = None):
    async with get_session() as session:
        rows, _ = await todos.list_todos(session, status=status, limit=100)
        return {"todos": rows}


@app.get("/health")
async def health():
    return {"status": "ok"}
