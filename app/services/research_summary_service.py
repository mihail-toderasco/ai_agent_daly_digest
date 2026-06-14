import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArxivEntry
from app.services.llm.factory import get_ai_provider
from app.services.llm.models import AIRequest


logger = logging.getLogger(__name__)


class ResearchSummaryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_provider = get_ai_provider()

    async def generate_entry_summary(self, entry_id: int) -> bool:
        """Fetch a single entry, request AI analysis, and save the summary."""
        result = await self.db.execute(
            select(ArxivEntry).where(ArxivEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()

        if not entry or entry.deep_research_summary is not None:
            return False

        document_link = self._document_link(entry.raw)
        if not document_link:
            logger.warning(f"Skipping summary for entry {entry.id}: No valid PDF or HTML link found in raw metadata.")
            return False

        request = AIRequest(
            system_prompt=self._build_prompt(),
            user_prompt=f"Please deeply analyze this research paper: {document_link}",
            temperature=0.2
        )

        try:
            response = await self.ai_provider.generate(request)
            summary = self._extract_json_body(response.content)

            if summary:
                entry.deep_research_summary = summary
                await self.db.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to generate summary for entry {entry_id}: {e}")

        return False

    def _document_link(self, raw: dict | None) -> str | None:
        """
        Extracts the best available resource link from raw metadata.
        Prioritizes application/pdf and falls back to text/html.
        """
        if not raw:
            return None

        links = raw.get("links", [])

        pdf_link = next(
            (link["href"] for link in links if link.get("type") == "application/pdf"),
            None
        )
        if pdf_link:
            return pdf_link

        html_link = next(
            (link["href"] for link in links if link.get("type") == "text/html"),
            None
        )
        if html_link:
            return html_link

        return None

    def _extract_json_body(self, content: str) -> str | None:
        """Safely extract the JSON body, stripping markdown blocks if the LLM hallucinated them."""
        content = content.strip()

        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            parsed_json = json.loads(content)
            return parsed_json.get("body")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Raw content was: {content}")
            return None

    def _build_prompt(self) -> str:
        return """
You are an elite AI research analyst and science communicator.

Your task: Deeply read and understand the attached research PDF and generate a structured, high-value explainer.

Audience:
    - Curious, intelligent founders and professionals;
    - Not technical experts, but can understand advanced concepts when clearly explained;

Primary mission: Explain the paper’s ideas, meaning, and significance — NOT the metadata. Do NOT repeat title, authors, arXiv ID, year, or publication info. We already store those separately.

Tone:
    - Clear, sharp, human, insightful;
    - Like Karpathy + Paul Graham + Ali Abdaal;
    - No fluff, no hype, no academic filler;
    - Metaphors and intuitive explanations welcome;
    - Convey meaning and understanding, not jargon;

CONTENT YOU MUST PRODUCE (as narrative with brief bold section headers inside text):
    1. 3–5 core insights (executive brief);
    2. Core idea and motivation — explained simply;
    3. Why this research matters now (context & importance);
    4. Key innovations & contributions;
    5. Method — explained step-by-step in plain language;
    6. Math/theory intuition (no formulas — explain what they *mean*);
    7. Experiments and evaluation — what was tested and why it matters;
    8. Key results & what they prove (plain English significance);
    9. Limitations/where it may fail;
    10. Real-world impact and applications;
    11. Future work/open questions;
    12. Closing takeaway — 2-3 sentences summarizing the big picture;

Output rules:
    - DO NOT repeat metadata (title, authors, arXiv ID, etc.);
    - NO backticks;
    - Make the text feel like a human expert teaching;

Return only valid JSON in this format:

{ "body": "content_here" }

Begin your analysis now.
"""
