"""
Qdrant Cloud client wrapper. Same rationale as graph_db.py - isolate
the SDK, expose a stable interface, non-throwing health check.
"""

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from src.core.config import Settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class VectorDatabaseClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: QdrantClient | None = None

    def connect(self) -> None:
        if self._client is not None:
            return
        self._client = QdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key,
        )
        logger.info("Qdrant client initialized for %s", self._settings.qdrant_url)

    def health_check(self) -> dict:
        try:
            self.connect()
            self._client.get_collections()
            return {"service": "qdrant", "status": "up"}
        except UnexpectedResponse as exc:
            logger.error("Qdrant returned an unexpected response: %s", exc)
            return {"service": "qdrant", "status": "down", "reason": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant health check failed: %s", exc)
            return {"service": "qdrant", "status": "down", "reason": str(exc)}

    @property
    def client(self) -> QdrantClient:
        self.connect()
        return self._client