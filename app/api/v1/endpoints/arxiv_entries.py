import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.arxiv_entry import ArxivEntryResponse
from app.services.arxiv_entry_service import ArxivEntryService


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=list[ArxivEntryResponse])
async def list_arxiv_entries(
    skip: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1),
    sort_by: Literal["published", "created_at", "id"] = "published",
    sort_order: Literal["asc", "desc"] = "desc",
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        "[ArxivEntriesEndpoint] Received list request - "
        f"skip={skip}, limit={limit}, sort_by='{sort_by}', sort_order='{sort_order}'"
    )

    service = ArxivEntryService(db)
    entries = await service.list_entries(
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    logger.info(
        f"[ArxivEntriesEndpoint] Returning {len(entries)} records - "
        f"skip={skip}, limit={limit}, sort_by='{sort_by}', sort_order='{sort_order}'"
    )
    return entries
