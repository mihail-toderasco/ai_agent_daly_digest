import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArxivEntry
from app.services.llm.factory import get_ai_provider
from app.services.llm.models import AIRequest


logger = logging.getLogger(__name__)


@dataclass
class ResearchSummaryExecutionResult:
    status: str
    arxiv_id: str
    entry_id: int | None = None
    deep_research_summary: str | None = None
    message: str | None = None


class ResearchSummaryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_provider = get_ai_provider()

    async def execute(self, arxiv_id: str) -> ResearchSummaryExecutionResult:
        """Generate a deep research summary for one arXiv entry by arxiv_id."""
        normalized_arxiv_id = arxiv_id.strip()
        logger.info(
            f"[ResearchSummaryService] Starting summary generation - arxiv_id='{normalized_arxiv_id}'"
        )

        result = await self.db.execute(
            select(ArxivEntry).where(ArxivEntry.arxiv_id == normalized_arxiv_id)
        )
        entry = result.scalar_one_or_none()

        if not entry:
            logger.warning(
                f"[ResearchSummaryService] Entry not found - arxiv_id='{normalized_arxiv_id}'"
            )
            return ResearchSummaryExecutionResult(
                status="not_found",
                arxiv_id=normalized_arxiv_id,
                message="Entry not found.",
            )

        if entry.deep_research_summary:
            logger.info(
                "[ResearchSummaryService] Reusing existing summary - "
                f"entry_id={entry.id}, arxiv_id='{entry.arxiv_id}'"
            )
            return ResearchSummaryExecutionResult(
                status="already_exists",
                arxiv_id=entry.arxiv_id,
                entry_id=entry.id,
                deep_research_summary=entry.deep_research_summary,
                message="Summary already exists.",
            )

        document_link = self._document_link(entry.raw)
        if not document_link:
            logger.warning(
                "[ResearchSummaryService] Missing document link - "
                f"entry_id={entry.id}, arxiv_id='{entry.arxiv_id}'"
            )
            return ResearchSummaryExecutionResult(
                status="failed",
                arxiv_id=entry.arxiv_id,
                entry_id=entry.id,
                message="No valid PDF or HTML link found.",
            )

        request = AIRequest(
            system_prompt=self._build_prompt(),
            user_prompt=self._build_user_prompt(),
            document_url=document_link,
            temperature=0.2
        )

        try:
            response = await self.ai_provider.generate(request)
            summary = self._extract_json_body(response.content)

            if summary:
                entry.deep_research_summary = summary
                await self.db.commit()
                logger.info(
                    "[ResearchSummaryService] Summary generated successfully - "
                    f"entry_id={entry.id}, arxiv_id='{entry.arxiv_id}'"
                )
                return ResearchSummaryExecutionResult(
                    status="generated",
                    arxiv_id=entry.arxiv_id,
                    entry_id=entry.id,
                    deep_research_summary=summary,
                    message="Summary generated.",
                )

            logger.warning(
                "[ResearchSummaryService] Failed to extract summary body - "
                f"entry_id={entry.id}, arxiv_id='{entry.arxiv_id}'"
            )
            return ResearchSummaryExecutionResult(
                status="failed",
                arxiv_id=entry.arxiv_id,
                entry_id=entry.id,
                message="Failed to parse provider response.",
            )

        except Exception as e:
            logger.error(
                "[ResearchSummaryService] Provider call failed - "
                f"entry_id={entry.id}, arxiv_id='{entry.arxiv_id}', error='{e}'"
            )
            return ResearchSummaryExecutionResult(
                status="failed",
                arxiv_id=entry.arxiv_id,
                entry_id=entry.id,
                message="Failed to generate summary.",
            )

    def _document_link(self, raw: dict | None) -> str | None:
        """
        Extracts the best available resource link from raw metadata.
        Handles variations in JSON structure, missing arrays, and minimal data.
        """
        if not raw:
            return None

        # 1. Handle variations in the root key name
        links = raw.get("links") or raw.get("link") or []

        # Guard against a scenario where a single link is parsed as a dict instead of a list
        if isinstance(links, dict):
            links = [links]

        # 2. Helper to safely extract keys whether they have an '@' prefix or not
        def get_attr(item: dict, key: str):
            return item.get(key) or item.get(f"@{key}")

        # 3. Try to find the PDF link first
        pdf_link = next(
            (get_attr(link, "href") for link in links if get_attr(link, "type") == "application/pdf"),
            None
        )
        if pdf_link:
            return pdf_link

        # 4. Fall back to the HTML link
        html_link = next(
            (get_attr(link, "href") for link in links if get_attr(link, "type") == "text/html"),
            None
        )
        if html_link:
            return html_link

        # 5. Last resort: If the 'links' array is completely missing, 
        # fall back to the 'id' field if it contains a valid URL.
        raw_id = raw.get("id")
        if raw_id and isinstance(raw_id, str) and raw_id.startswith("http"):
            return raw_id

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
            logger.error(f"[ResearchSummaryService] Failed to parse provider response as JSON - error='{e}'")
            logger.debug(f"[ResearchSummaryService] Raw provider content - content='{content}'")
            return None

    def _build_user_prompt(self) -> str:
        return """
Step 1: The Extraction. Do not summarize or analyze it yet. First, extract the core technical contribution, the specific mathematical lemma used to prove the result, and the explicit experimental setup. List these as bullet points.

Step 2: The Reasoning. Now that you have those facts, explain the significance of the mathematical lemma you extracted in relation to quantum matrix math.
"""

    def _build_prompt(self) -> str:
        return """
You are an elite AI research analyst and science communicator.
Your task: Deeply read and understand the attached research paper and generate a structured, high-value explainer.

Audience: Curious, intelligent founders and professionals — not domain experts.

Primary mission: Explain the paper’s ideas, meaning, and significance. 
Do NOT repeat title, authors, arXiv ID, year, or metadata.

Tone: Clear, sharp, human, insightful (Karpathy + Paul Graham style).

CONTENT STRUCTURE (use brief bold section headers):
1. 3–5 core insights (executive brief)
2. Core idea and motivation — explained simply
3. Why this research matters now
4. Key innovations & contributions
5. Method — explained step-by-step in plain language
6. Math/theory intuition (no formulas — explain meaning)
7. Experiments and evaluation
8. Key results & what they prove
9. Limitations
10. Real-world impact and applications
11. Future work / open questions
12. Closing takeaway (2-3 sentences)

Output rules:
- Return ONLY valid JSON: { "body": "full narrative here" }
- No backticks, no markdown code blocks.
"""
