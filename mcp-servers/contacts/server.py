"""FastMCP Contacts Server - Contact management tools."""

import logging
import os
from typing import Optional
from uuid import UUID

import httpx
from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("Contacts")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


def _call_backend(method: str, path: str, **kwargs) -> dict:
    """Call backend API with retry."""
    url = f"{BACKEND_URL}{path}"
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.request(method, url, **kwargs)
                r.raise_for_status()
                return r.json() if r.content else {}
        except Exception as e:
            if attempt == 2:
                raise
            import time
            time.sleep(2**attempt)
    return {}


@mcp.tool()
def upsert_contact(
    full_name: str,
    company: str = "",
    email: Optional[str] = None,
    phone: Optional[str] = None,
    country: Optional[str] = None,
    interaction_summary: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """
    Create or update a contact. Deduplicates by email/phone.
    Call this when processing a new interaction to ensure the contact exists.
    """
    logger.info("upsert_contact name=%s company=%s", full_name, company)
    try:
        payload = {
            "full_name": full_name,
            "company_name": company or None,
            "email": email,
            "phone": phone,
            "country": country,
            "interaction_summary": interaction_summary,
            "notes": notes,
            "tags": tags.split(",") if tags else [],
        }
        data = _call_backend("POST", "/api/internal/contacts/upsert", json=payload)
        return f"Success: contact id={data.get('id')} created={data.get('created', False)}"
    except Exception as e:
        logger.exception("upsert_contact failed: %s", e)
        return f"Error: {str(e)}"


@mcp.tool()
def record_interaction(contact_id: str, summary: str) -> str:
    """
    Record an interaction for a contact. Updates last_contacted_at and last_interaction_summary.
    """
    logger.info("record_interaction contact=%s", contact_id)
    try:
        _call_backend(
            "POST",
            f"/api/internal/contacts/{contact_id}/interaction",
            json={"summary": summary},
        )
        return "Success: interaction recorded"
    except Exception as e:
        logger.exception("record_interaction failed: %s", e)
        return f"Error: {str(e)}"


@mcp.tool()
def get_contact(contact_id: str) -> str:
    """Get contact details by ID."""
    try:
        data = _call_backend("GET", f"/api/internal/contacts/{contact_id}")
        return str(data)
    except Exception as e:
        logger.exception("get_contact failed: %s", e)
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8002)
