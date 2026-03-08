"""Shared Pydantic models for API contracts."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Company ---
class CompanyBase(BaseModel):
    name: str


class CompanyCreate(CompanyBase):
    pass


class Company(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Contact ---
class ContactBase(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ContactCreate(ContactBase):
    company_id: Optional[UUID] = None
    company_name: Optional[str] = None  # Create company if needed


class ContactUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class Contact(ContactBase):
    id: UUID
    company_id: Optional[UUID] = None
    company_name: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    last_interaction_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactListItem(Contact):
    """Contact for dashboard list - same as Contact."""


# --- Interaction ---
class InteractionBase(BaseModel):
    summary: str
    contact_id: UUID


class InteractionCreate(InteractionBase):
    pass


class Interaction(InteractionBase):
    id: UUID
    occurred_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# --- TODO ---
class TodoBase(BaseModel):
    title: str
    description: Optional[str] = None
    contact_id: Optional[UUID] = None
    due_date: Optional[datetime] = None


class TodoCreate(TodoBase):
    pass


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None


class Todo(TodoBase):
    id: UUID
    status: str = "pending"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Prompt / Orchestrator ---
class PromptInput(BaseModel):
    contact_name: str
    interaction_summary: str
    company: str
    follow_up_time: Optional[str] = None
    meeting_time: Optional[str] = None
    meeting_context: Optional[str] = None


class ActionResult(BaseModel):
    type: str  # contact_updated, follow_up_scheduled, meeting_scheduled, todo_created
    success: bool
    details: dict
    reasoning: Optional[str] = None


class PromptResponse(BaseModel):
    id: str
    status: str  # completed | failed
    actions: list[ActionResult]
    contact_id: Optional[str] = None


# --- Audit ---
class AuditLogEntry(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: dict
    created_at: datetime

    class Config:
        from_attributes = True
