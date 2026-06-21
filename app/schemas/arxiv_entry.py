from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArxivEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    arxiv_id: str
    title: str
    summary: str
    deep_research_summary: str | None
    authors: str
    categories: str
    published: datetime
    link: str
    created_at: datetime
