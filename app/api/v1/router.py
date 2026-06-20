from fastapi import APIRouter
from app.api.v1.endpoints import digests


api_router = APIRouter()


api_router.include_router(digests.router, prefix="/digests", tags=["digests"])
