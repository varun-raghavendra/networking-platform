"""Summary agent - produces a one-line display summary of the interaction."""

import logging

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are a summary agent. Given an interaction summary between the user and a contact, produce a single concise one-line summary suitable for display in a table.

Requirements:
- One line only, no line breaks
- Capture the main takeaway or outcome
- Be specific (include names, companies, or topics when relevant)
- Keep it under 80 characters when possible
- Use title case or sentence case
- Do not start with "We discussed" or "The user" - be direct

Examples:
Input: "Discussed open roles at Nutanix. I need to search for roles relevant to my profile."
Output: "Exploring roles at Nutanix; will search for profile matches."

Input: "We decided to meet sometime in the week of March 16, 2026"
Output: "Meeting scheduled for week of March 16."

Input: "Met at conference, exchanged cards, follow up in 2 days"
Output: "Conference intro; follow-up in 2 days."

Return ONLY the one-line summary, no quotes or extra text."""

PARAGRAPH_PROMPT = """You are a summary agent. Given an interaction summary between the user and a contact, produce a short paragraph (2-4 sentences) that captures the full context of the last interaction.

Requirements:
- Write in clear, professional prose
- Include key details: who was contacted, what was discussed, any outcomes, commitments, or next steps
- Use past tense (e.g. "They discussed...", "The user agreed to...")
- Keep each sentence focused; aim for 2-4 sentences total
- Do not use bullet points or lists

Examples:
Input: "Discussed open roles at Nutanix. I need to search for roles relevant to my profile."
Output: "The user and contact discussed open roles at Nutanix. The contact suggested the user search for positions relevant to their profile. Follow-up on job applications was implied."

Input: "Met at conference, exchanged cards, follow up in 2 days"
Output: "The user met this contact at a conference and exchanged business cards. They agreed to follow up within two days to continue the conversation."

Return ONLY the paragraph, no quotes or extra text."""


class SummaryAgent:
    """Agent that produces a display-friendly one-line summary."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def get_one_line_summary(self, interaction_summary: str) -> str | None:
        """Return a concise one-line summary, or None on failure."""
        if not interaction_summary or not interaction_summary.strip():
            return None
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SUMMARY_PROMPT},
                    {"role": "user", "content": interaction_summary.strip()},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return None
            return content[:200]
        except Exception as e:
            logger.exception("SummaryAgent get_one_line_summary failed: %s", e)
            return None

    async def get_paragraph_summary(self, interaction_summary: str) -> str | None:
        """Return a short paragraph (2-4 sentences) capturing the interaction context, or None on failure."""
        if not interaction_summary or not interaction_summary.strip():
            return None
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": PARAGRAPH_PROMPT},
                    {"role": "user", "content": interaction_summary.strip()},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return None
            return content[:2000]
        except Exception as e:
            logger.exception("SummaryAgent get_paragraph_summary failed: %s", e)
            return None
