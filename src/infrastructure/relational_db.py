"""
Postgres client wrapper (SQLAlchemy engine).

Postgres holds structured metadata that doesn't belong in the graph or
vector store: ingestion job status, audit logs. Neo4j holds relationships,
Qdrant holds embeddings, Postgres holds "boring" transactional records.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.core.config import Settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class RelationalDatabaseClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._engine: Engine | None = None

    def connect(self) -> None:
        if self._engine is not None:
            return
        self._engine = create_engine(self._settings.postgres_dsn, pool_pre_ping=True)
        logger.info("Postgres engine created")

    def health_check(self) -> dict:
        try:
            self.connect()
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"service": "postgres", "status": "up"}
        except SQLAlchemyError as exc:
            logger.error("Postgres health check failed: %s", exc)
            return {"service": "postgres", "status": "down", "reason": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("Postgres health check failed: %s", exc)
            return {"service": "postgres", "status": "down", "reason": str(exc)}

    @property
    def engine(self) -> Engine:
        self.connect()
        return self._engine