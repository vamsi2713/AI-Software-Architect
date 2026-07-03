"""
Gemini embeddings client wrapper.

Uses gemini-embedding-001, the current model as of mid-2026 - its
predecessor, text-embedding-004, was deprecated and shut down by
Google on January 14, 2026.
"""

import google.generativeai as genai

from src.core.config import Settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768  # truncated from the model's 3072 default via
                             # output_dimensionality, to match our Qdrant
                             # collection size


class EmbeddingClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._configured = False

    def _ensure_configured(self) -> None:
        if self._configured:
            return
        genai.configure(api_key=self._settings.gemini_api_key)
        self._configured = True

    def embed_text(self, text: str, task_type: str = "retrieval_document") -> list[float]:
        """
        task_type matters for embedding quality, not correctness - using
        the wrong one doesn't error, it just silently produces worse
        search results. Documents being stored should use the default
        "retrieval_document". A question being embedded at query time
        should pass task_type="retrieval_query" instead.
        """
        self._ensure_configured()
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )
        return result["embedding"]

    def health_check(self) -> dict:
        try:
            self.embed_text("health check ping")
            return {"service": "gemini_embeddings", "status": "up"}
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini embedding health check failed: %s", exc)
            return {"service": "gemini_embeddings", "status": "down", "reason": str(exc)}