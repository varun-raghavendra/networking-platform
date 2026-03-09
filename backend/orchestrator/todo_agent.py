"""TODO extraction agent - parses interaction and extracts action items as TODOs."""

import json
import logging

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

TODO_PROMPT = """You are a TODO extraction agent. Given an interaction summary between the user and a contact, extract actionable TODO items.

Return a JSON array of objects. Each object has:
- title: Short actionable title (required)
- description: Optional longer description

If there are no clear action items, return an empty array [].

Example input: "Discussed open roles at Nutanix. I need to search for roles relevant to my profile."
Example output: [{"title": "Search for relevant roles at Nutanix", "description": "Find roles matching my profile"}]

Return ONLY valid JSON, no other text."""


class TodoAgent:
    """Agent that extracts TODOs from interaction summary."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def extract_todos(self, interaction_summary: str) -> list[dict]:
        """Extract TODO items from interaction summary. Returns list of {title, description?}."""
        if not interaction_summary or not interaction_summary.strip():
            return []
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": TODO_PROMPT},
                    {"role": "user", "content": interaction_summary.strip()},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return []
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                return []
            result = []
            for item in parsed:
                if isinstance(item, dict) and item.get("title"):
                    result.append({
                        "title": str(item["title"]),
                        "description": str(item["description"]) if item.get("description") else None,
                    })
            return result
        except Exception as e:
            logger.exception("TodoAgent extract_todos failed: %s", e)
            return []
