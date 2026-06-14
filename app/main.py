from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.arxiv_service import ArxivService

app = FastAPI()


@app.get("/")
def read_root():
    return { "status": "ok" }


@app.get("/digest")
async def arxiv_digest():
    return { "coming": "soon" }
