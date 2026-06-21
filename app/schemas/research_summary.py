from pydantic import BaseModel, Field


class ResearchSummaryGenerateRequest(BaseModel):
    arxiv_id: str = Field(min_length=1, max_length=255)


class ResearchSummaryGenerateResponse(BaseModel):
    research_summary: str
