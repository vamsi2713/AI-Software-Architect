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
    
    def initialize_schema(self) -> None:
        """
        Creates the conversations/messages tables if they don't exist.
        Called once at startup - safe to call every time since
        CREATE TABLE IF NOT EXISTS is a no-op after the first run.
        """
        self.connect()
        with self._engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    agent_type TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
        logger.info("Postgres schema initialized (conversations, messages)")

    def create_conversation(self, title: str) -> int:
        self.connect()
        with self._engine.begin() as conn:
            result = conn.execute(
                text("INSERT INTO conversations (title) VALUES (:title) RETURNING id"),
                {"title": title},
            )
            return result.scalar_one()

    def save_message(self, conversation_id: int, role: str, content: str, agent_type: str | None = None) -> None:
        self.connect()
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO messages (conversation_id, role, content, agent_type)
                    VALUES (:conversation_id, :role, :content, :agent_type)
                """),
                {"conversation_id": conversation_id, "role": role, "content": content, "agent_type": agent_type},
            )

    def get_messages(self, conversation_id: int) -> list[dict]:
        self.connect()
        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT role, content, agent_type, created_at
                    FROM messages
                    WHERE conversation_id = :conversation_id
                    ORDER BY created_at ASC
                """),
                {"conversation_id": conversation_id},
            )
            return [dict(row._mapping) for row in result]

    def list_conversations(self) -> list[dict]:
        self.connect()
        with self._engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, title, created_at
                FROM conversations
                ORDER BY created_at DESC
            """))
            return [dict(row._mapping) for row in result]