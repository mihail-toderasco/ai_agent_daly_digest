import logging

from fastapi import APIRouter, Depends
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.digest_service import DigestService


logger = logging.getLogger(__name__)
router = APIRouter()


# http://localhost/api/v1/digests/today?search_query=Artificial+Intelligence
@router.get("/today")
async def get_todays_digest(
    search_query: str,
    db: AsyncSession = Depends(get_db)
):
    today = datetime.now(timezone.utc).date()
    service = DigestService(db)
    return await service.execute(target_date=today, query=search_query)

# http://localhost/api/v1/digests/2026-06-14?search_query=Artificial+Intelligence
# "No Data" scenario: http://localhost/api/v1/digests/2026-06-01?search_query=very+specific+nonexistent+topic
@router.get("/{digest_date}")
async def get_specific_digest(
    digest_date: date,
    search_query: str,
    db: AsyncSession = Depends(get_db)
):
    service = DigestService(db)
    return await service.execute(target_date=digest_date, query=search_query)
