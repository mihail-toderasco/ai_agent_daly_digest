import logging

from datetime import date
from sqlalchemy import select, cast, Date, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArxivEntry, Digest
from app.services.arxiv_service import ArxivService
from app.services.llm.factory import get_ai_provider
from app.services.llm.models import AIRequest
from app.services.research_summary_service import ResearchSummaryService


logger = logging.getLogger(__name__)


class DigestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_provider = get_ai_provider()

    async def execute(self, target_date: date, query: str):
        normalized_query = self._normalized_search_query(query)
        logger.info(
            f"[DigestService] Starting digest execution for date={target_date}, query='{normalized_query}'"
        )

        try:
            existing_digest = await self._get_existing_digest(target_date, normalized_query)
            if existing_digest:
                logger.info(
                    f"[DigestService] Digest already exists for date={target_date}, query='{normalized_query}'"
                )
                return existing_digest

            new_digest = await self._generate_daily_digest(target_date, normalized_query)
            logger.info(
                f"[DigestService] Digest generation finished for date={target_date}, query='{normalized_query}', status='{new_digest.status}'"
            )
            return new_digest
        except Exception as exc:
            logger.exception(
                f"[DigestService] Unexpected error while generating digest for date={target_date}, query='{normalized_query}': {exc}"
            )
            return await self._create_failed_digest(
                target_date=target_date,
                query=normalized_query,
                reason="Digest generation failed due to an internal error."
            )

    async def _get_existing_digest(self, target_date: date, query: str) -> Digest | None:
        result = await self.db.execute(
            select(Digest)
            .where(Digest.digest_date == target_date)
            .where(Digest.query == query)
        )
        return result.scalar_one_or_none()

    async def _generate_daily_digest(self, target_date: date, query: str) -> Digest:
        logger.info(
            f"[DigestService] Generating digest for date={target_date}, query='{query}'"
        )

        entries = await self._ensure_summarized_entries_for_date(target_date, query)

        if not entries:
            logger.info(
                f"[DigestService] No data found for date={target_date} after local and source checks"
            )
            return await self._create_no_data_digest(target_date, query)

        source_entry_ids = [entry.id for entry in entries]
        digest_content = await self._create_ai_synthesis(entries, target_date, query)

        if not digest_content:
            logger.error(
                f"[DigestService] AI provider failed to generate digest content for date={target_date}, query='{query}'"
            )
            return await self._create_failed_digest(
                target_date=target_date,
                query=query,
                reason="Digest generation failed while synthesizing summarized papers."
            )

        new_digest = Digest(
            digest_date=target_date,
            query=query,
            status="completed",
            content=digest_content,
            source_entry_ids=source_entry_ids
        )

        self.db.add(new_digest)
        await self.db.commit()
        await self.db.refresh(new_digest)
        logger.info(
            f"[DigestService] Created completed digest id={new_digest.id} with {len(source_entry_ids)} source entries"
        )
        return new_digest

    async def _ensure_summarized_entries_for_date(self, target_date: date, query: str) -> list[ArxivEntry]:
        entries = await self._fetch_summarized_entries(target_date)
        if entries:
            logger.info(
                f"[DigestService] Using {len(entries)} already summarized entries for date={target_date}"
            )
            return entries

        logger.info(
            f"[DigestService] No summarized entries found for date={target_date}. Looking for unsummarized local entries."
        )
        unsummarized_entries = await self._fetch_arxiv_entries(target_date)

        if unsummarized_entries:
            logger.info(
                f"[DigestService] Found {len(unsummarized_entries)} local unsummarized entries for date={target_date}. Generating summaries."
            )
            return await self._generate_summaries_for_entries(unsummarized_entries, target_date)

        logger.info(
            f"[DigestService] No local entries found for date={target_date}. Fetching from ArXiv source for query='{query}'."
        )
        await self._refresh_entries_from_source(query)

        refreshed_unsummarized_entries = await self._fetch_arxiv_entries(target_date)
        if not refreshed_unsummarized_entries:
            logger.info(
                f"[DigestService] Source refresh did not return entries for date={target_date}"
            )
            return []

        logger.info(
            f"[DigestService] Source refresh returned {len(refreshed_unsummarized_entries)} entries for date={target_date}. Generating summaries."
        )
        return await self._generate_summaries_for_entries(refreshed_unsummarized_entries, target_date)

    async def _fetch_summarized_entries(self, target_date: date) -> list[ArxivEntry]:
        result = await self.db.execute(
            select(ArxivEntry)
            .where(cast(ArxivEntry.published, Date) == target_date)
            .where(ArxivEntry.deep_research_summary.is_not(None))
            .where(ArxivEntry.deep_research_summary != "")
        )
        entries = list(result.scalars().all())
        logger.info(f"[DigestService] Found {len(entries)} summarized entries for {target_date}")
        return entries

    async def _generate_summaries_for_entries(
        self,
        entries_with_no_summary: list[ArxivEntry],
        target_date: date
    ) -> list[ArxivEntry]:
        if not entries_with_no_summary:
            logger.info(f"[DigestService] No unsummarized entries available for date={target_date}")
            return []

        logger.info(
            f"[DigestService] Generating summaries for {len(entries_with_no_summary)} entries for date={target_date}"
        )
        research_summary_service = ResearchSummaryService(self.db)

        success_count = 0
        for index, entry in enumerate(entries_with_no_summary, start=1):
            logger.info(
                f"[DigestService] [{index}/{len(entries_with_no_summary)}] Generating summary for entry_id={entry.id}, arxiv_id={entry.arxiv_id}"
            )
            try:
                result = await research_summary_service.execute(entry.arxiv_id)
                if result.status in {"generated", "already_exists"}:
                    success_count += 1
                    logger.info(
                        "[DigestService] Summary available for digest - "
                        f"entry_id={entry.id}, arxiv_id={entry.arxiv_id}, status='{result.status}'"
                    )
                else:
                    logger.warning(
                        "[DigestService] Summary unavailable for digest - "
                        f"entry_id={entry.id}, arxiv_id={entry.arxiv_id}, status='{result.status}'"
                    )
            except Exception as exc:
                logger.exception(
                    f"[DigestService] Error while generating summary for entry_id={entry.id}, arxiv_id={entry.arxiv_id}: {exc}"
                )

        logger.info(
            f"[DigestService] Summary generation completed for date={target_date}. successful={success_count}, total={len(entries_with_no_summary)}"
        )

        new_entries = await self._fetch_summarized_entries(target_date)
        return new_entries

    async def _refresh_entries_from_source(self, query: str) -> None:
        logger.info(f"[DigestService] Refreshing entries from ArXiv for query='{query}'")
        arxiv_service = ArxivService(self.db)
        try:
            result = await arxiv_service.get_digest(query=query, max_results=50, force_refresh=True)
            logger.info(
                f"[DigestService] ArXiv refresh completed for query='{query}', from_cache={result.get('from_cache')}, returned_entries={len(result.get('entries', []))}"
            )
        except Exception as exc:
            logger.exception(
                f"[DigestService] Failed to refresh entries from ArXiv for query='{query}': {exc}"
            )

    async def _fetch_arxiv_entries(self, target_date: date) -> list[ArxivEntry]:
        statement = (
            select(ArxivEntry)
            .where(cast(ArxivEntry.published, Date) == target_date)
            .where(
                or_(
                    ArxivEntry.deep_research_summary.is_(None),
                    ArxivEntry.deep_research_summary == ""
                )
            )
        )
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def _create_no_data_digest(self, target_date: date, query: str) -> Digest:
        no_data_digest = Digest(
            digest_date=target_date,
            query=query,
            status="no_data",
            content=f"No data found for date {target_date.isoformat()}.",
            source_entry_ids=[]
        )

        self.db.add(no_data_digest)
        await self.db.commit()
        await self.db.refresh(no_data_digest)
        logger.info(
            f"[DigestService] Created no_data digest id={no_data_digest.id} for date={target_date}, query='{query}'"
        )
        return no_data_digest

    async def _create_failed_digest(self, target_date: date, query: str, reason: str) -> Digest:
        existing_digest = await self._get_existing_digest(target_date, query)
        if existing_digest:
            logger.warning(
                f"[DigestService] Reusing existing digest id={existing_digest.id} after failure for date={target_date}, query='{query}'"
            )
            return existing_digest

        failed_digest = Digest(
            digest_date=target_date,
            query=query,
            status="failed",
            content=reason,
            source_entry_ids=[]
        )

        self.db.add(failed_digest)
        await self.db.commit()
        await self.db.refresh(failed_digest)
        logger.info(
            f"[DigestService] Created failed digest id={failed_digest.id} for date={target_date}, query='{query}'"
        )
        return failed_digest

    async def _create_ai_synthesis(self, entries: list[ArxivEntry], target_date: date, query: str) -> str | None:
        # Prepare the context by concatenating the individual summaries
        papers_context = ""
        for i, entry in enumerate(entries, 1):
            papers_context += f"--- PAPER {i} ---\n"
            papers_context += f"Summary:\n{entry.deep_research_summary}\n\n"

        system_prompt = """You are a Principal Technical Editor producing a premium daily newsletter. 
Your goal is to read multiple deep research summaries and synthesize them into a single, cohesive daily briefing.

Structure your response as follows:
    1. OVERVIEW: A one-paragraph executive summary of the day's overarching themes.
    2. KEY BREAKTHROUGHS: Bullet points of the most significant advancements.
    3. DETAILED SYNTHESIS: Group the papers by related topics and explain how they connect or contrast.
    4. PRACTICAL TAKEAWAYS: What this means for founders, engineers, and researchers.

Tone: Professional, highly analytical, and accessible. No fluff."""

        user_prompt = f"""Generate a research digest for {target_date.isoformat()} focusing on '{query}'.
Here are the deep research summaries for the day:

{papers_context}"""

        request = AIRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )

        try:
            response = await self.ai_provider.generate(request)
            return response.content
        except Exception as e:
            logger.error(f"Failed to synthesize daily digest: {e}")
            return None

    def _normalized_search_query(self, query: str) -> str:
        """Normalize search query to keep a stable uniqueness key."""
        return query.strip().lower()
