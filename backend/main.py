"""Backend API - FastAPI application."""

import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_settings, setup_logging
from database import get_session, run_migrations
from orchestrator.agent import OrchestratorAgent
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


class InteractionInput(BaseModel):
    summary: str


class TodoCreateInput(BaseModel):
    title: str
    description: str | None = None
    contact_id: str | None = None
    created_by_agent: bool = False


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
        follow_up_time=input.follow_up_time,
        meeting_time=input.meeting_time,
        meeting_context=input.meeting_context,
    )
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
    """Update contact country, phone, email only. last_contacted must go through prompt."""
    async with get_session() as session:
        result = await contacts.update_contact_fields(
            session, contact_id,
            country=input.country,
            phone=input.phone,
            email=input.email,
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
):
    """List TODO items."""
    async with get_session() as session:
        rows, total = await todos.list_todos(session, status, limit, offset)
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
        )


class TodoUpdateInput(BaseModel):
    status: str | None = None


@app.patch("/api/todos/{todo_id}")
async def update_todo(todo_id: UUID, input: TodoUpdateInput | None = None):
    """Update TODO (e.g. mark done)."""
    status = (input or TodoUpdateInput()).status
    async with get_session() as session:
        return await todos.update_todo(session, todo_id, status=status)


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
        )


@app.get("/api/internal/todos")
async def internal_list_todos(status: str | None = None):
    async with get_session() as session:
        rows, _ = await todos.list_todos(session, status=status, limit=100)
        return {"todos": rows}


@app.get("/health")
async def health():
    return {"status": "ok"}
