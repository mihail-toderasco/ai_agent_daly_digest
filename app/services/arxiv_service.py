from datetime import datetime, timezone, timedelta
from dateutil import parser as dateparse
import httpx
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArxivEntry, ExternalQueryState


class ArxivService:
    RATE_LIMIT_HOURS = 23
    ARXIV_URL = "https://export.arxiv.org/api/query"


    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_digest(self, query: str, max_results: int = 10):
        query_hash = self._hash_query(query)

        state = await self._get_state(query_hash)

        if state and not self._is_stale(state.last_fetched_at):
            entries = await self._get_cached_entries()
            return {
                "from_cache": True,
                "entries": entries
            }

        xml = await self._fetch_arxiv(query, max_results)
        entries = self._parse_xml(xml)

        new_entries = await self._save_entries(entries)
        await self._update_state(query_hash, len(new_entries))

        return {
            "from_cache": False,
            "entries": entries
        }


    async def _fetch_arxiv(self, query: str, max_results: int):
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 0,
            "max_results": max_results
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(self.ARXIV_URL, params=params)
            response.raise_for_status()
            return response.text


    def _parse_xml(self, xml_data: str):
        import xmltodict

        json_data = xmltodict.parse(xml_data, force_list=("entry",))
        entries = json_data["feed"].get("entry", [])

        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=94)

        result = []

        for e in entries:
            published_raw = e.get("published") or e.get("updated") or ""

            try:
                published_dt = dateparse.parse(published_raw)
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if published_dt < threshold:
                continue

            authors_field = e.get("author", [])
            if isinstance(authors_field, dict):
                authors_field = [authors_field]

            authors = ", ".join(
                a.get("name", "").strip()
                for a in authors_field
                if a.get("name")
            )

            cats = e.get("category", [])
            if isinstance(cats, dict):
                cats = [cats]

            categories = ", ".join(
                c.get("@term") or c.get("#text") or ""
                for c in cats if c
            )

            entry_id = self._extract_arxiv_id(e.get("id", ""))

            result.append({
                "arxiv_id": entry_id,
                "title": (e.get("title") or "").strip(),
                "summary": (e.get("summary") or "").strip(),
                "authors": authors,
                "categories": categories,
                "published": published_dt,
                "link": e.get("id"),
                "raw": e
            })

        return result


    def _extract_arxiv_id(self, entry_id: str) -> str:
        if not entry_id:
            raise ValueError("Missing arxiv entry id")

        return entry_id.rstrip("/").split("/")[-1]


    async def _save_entries(self, entries):
        new_entries = []

        for e in entries:
            exists = await self.db.execute(
                select(ArxivEntry).where(ArxivEntry.arxiv_id == e["arxiv_id"])
            )

            if exists.scalar_one_or_none():
                continue

            obj = ArxivEntry(
                arxiv_id=e["arxiv_id"],
                title=e["title"],
                summary=e["summary"],
                authors=e["authors"],
                categories=e["categories"],
                published=e["published"],
                link=e["link"],
                raw=e["raw"]
            )

            self.db.add(obj)
            new_entries.append(obj)

        await self.db.commit()
        return new_entries


    async def _get_state(self, query_hash: str):
        result = await self.db.execute(
            select(ExternalQueryState)
            .where(
                ExternalQueryState.source == "arxiv",
                ExternalQueryState.query_hash == query_hash
            )
        )
        return result.scalar_one_or_none()


    async def _update_state(self, query_hash: str, count: int):
        state = await self._get_state(query_hash)

        now = datetime.now(timezone.utc)

        if state:
            state.last_fetched_at = now
            state.last_success_count = count
        else:
            state = ExternalQueryState(
                source="arxiv",
                query_hash=query_hash,
                last_fetched_at=now,
                last_success_count=count
            )
            self.db.add(state)

        await self.db.commit()


    async def _get_cached_entries(self):
        result = await self.db.execute(
            select(ArxivEntry)
            .order_by(ArxivEntry.published.desc())
            .limit(10)
        )

        rows = result.scalars().all()

        return [
            {
                "arxiv_id": r.arxiv_id,
                "title": r.title,
                "summary": r.summary,
                "authors": r.authors,
                "categories": r.categories,
                "published": r.published.isoformat(),
                "link": r.link
            }
            for r in rows
        ]


    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()


    def _is_stale(self, last_fetched_at: datetime) -> bool:
        now = datetime.now(timezone.utc)
        return now - last_fetched_at > timedelta(hours=self.RATE_LIMIT_HOURS)
