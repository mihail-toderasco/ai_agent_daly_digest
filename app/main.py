import logging

from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logging.getLogger("uvicorn.access").setLevel(settings.LOG_LEVEL)
logging.getLogger("uvicorn.error").setLevel(settings.LOG_LEVEL)

app = FastAPI(title="API")

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return { "status": "ok" }
