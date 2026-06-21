import logging

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArxivEntry


logger = logging.getLogger(__name__)


class ArxivEntryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_entries(
        self,
        skip: int = 0,
        limit: int | None = None,
        sort_by: str = "published",
        sort_order: str = "desc",
    ) -> list[ArxivEntry]:
        logger.info(
            "[ArxivEntryService] Listing arxiv entries - "
            f"skip={skip}, limit={limit}, sort_by='{sort_by}', sort_order='{sort_order}'"
        )

        order_column = self._resolve_sort_column(sort_by)
        statement = self._build_statement(order_column, sort_order, skip, limit)

        result = await self.db.execute(statement)
        entries = list(result.scalars().all())

        logger.info(
            f"[ArxivEntryService] Listed {len(entries)} arxiv entries - "
            f"skip={skip}, limit={limit}, sort_by='{sort_by}', sort_order='{sort_order}'"
        )
        return entries

    def _resolve_sort_column(self, sort_by: str):
        if sort_by == "created_at":
            return ArxivEntry.created_at
        if sort_by == "id":
            return ArxivEntry.id
        return ArxivEntry.published

    def _build_statement(
        self,
        order_column,
        sort_order: str,
        skip: int,
        limit: int | None,
    ) -> Select[tuple[ArxivEntry]]:
        statement = select(ArxivEntry)

        if sort_order == "asc":
            statement = statement.order_by(order_column.asc(), ArxivEntry.id.asc())
        else:
            statement = statement.order_by(order_column.desc(), ArxivEntry.id.desc())

        statement = statement.offset(skip)
        if limit is not None:
            statement = statement.limit(limit)

        return statement
