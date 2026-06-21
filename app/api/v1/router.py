from fastapi import APIRouter
from app.api.v1.endpoints import arxiv_entries, digests, research_summaries


api_router = APIRouter()


api_router.include_router(digests.router, prefix="/digests", tags=["digests"])
api_router.include_router(
    arxiv_entries.router,
    prefix="/arxiv_entries",
    tags=["arxiv_entries"],
)
api_router.include_router(
    research_summaries.router,
    prefix="/research_summaries",
    tags=["research_summaries"],
)
