"""
Application entrypoint. Kept thin on purpose - no business logic here.
That lives in agents/, parsers/, and services we'll add later.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.logging_config import configure_logging, get_logger
from src.api.health import router as health_router
from src.api.parse import router as parse_router
from src.api.ingest import router as ingest_router
from src.api.query import router as query_router

configure_logging()
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("%s starting up in %s mode", settings.app_name, settings.environment)
    yield
    logger.info("%s shutting down", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="AI Software Architect - reasons over an entire codebase's "
    "structure, dependencies, and documentation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(parse_router)
app.include_router(ingest_router)
app.include_router(query_router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "status": "running"}