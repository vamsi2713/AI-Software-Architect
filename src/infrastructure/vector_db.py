"""
Qdrant Cloud client wrapper.
"""

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams, PointStruct

from src.core.config import Settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "okf_nodes"
VECTOR_SIZE = 768  # matches Gemini text-embedding-004 output


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

    def ensure_collection(self) -> None:
        """Creates the collection if it doesn't exist yet. Safe to call
        every time - it's a no-op if the collection is already there."""
        self.connect()
        existing = [c.name for c in self._client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection '%s'", COLLECTION_NAME)

    def upsert_node(self, node_id: str, vector: list[float], payload: dict) -> None:
        """Writes (or overwrites) one embedded node. Qdrant needs a
        numeric or UUID point id, so we hash the string id deterministically."""
        self.connect()
        self.ensure_collection()
        point_id = abs(hash(node_id)) % (10**12)
        self._client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload={**payload, "okf_id": node_id})],
        )

    @property
    def client(self) -> QdrantClient:
        self.connect()
        return self._client