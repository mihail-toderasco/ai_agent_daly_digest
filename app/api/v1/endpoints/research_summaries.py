import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.research_summary import (
    ResearchSummaryGenerateRequest,
    ResearchSummaryGenerateResponse,
)
from app.services.research_summary_service import ResearchSummaryService


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ResearchSummaryGenerateResponse)
async def generate_research_summary(
    payload: ResearchSummaryGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        "[ResearchSummariesEndpoint] Received summary generation request - "
        f"arxiv_id='{payload.arxiv_id}'"
    )

    service = ResearchSummaryService(db)
    result = await service.execute(payload.arxiv_id)

    if result.status == "not_found":
        logger.warning(
            "[ResearchSummariesEndpoint] Entry not found - "
            f"arxiv_id='{payload.arxiv_id}'"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ArXiv entry not found.",
        )

    if result.status == "failed":
        logger.error(
            "[ResearchSummariesEndpoint] Summary generation failed - "
            f"arxiv_id='{payload.arxiv_id}', entry_id={result.entry_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.message or "Summary generation failed.",
        )

    logger.info(
        "[ResearchSummariesEndpoint] Returning summary generation result - "
        f"arxiv_id='{result.arxiv_id}', entry_id={result.entry_id}, status='{result.status}'"
    )

    return ResearchSummaryGenerateResponse(
        research_summary=result.deep_research_summary,
    )
