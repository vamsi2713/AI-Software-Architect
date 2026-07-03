"""
Groq client wrapper - fast LLM inference for agent reasoning.

Deliberately separate from EmbeddingClient (Gemini): Groq has no
embeddings endpoint, so it's used only for reasoning/text generation,
never for embedding text. See Section 3 of the project handoff doc.
"""

from groq import Groq

from src.core.config import Settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Groq's currently supported models change over time - llama-3.3-70b-versatile
# is a solid general-purpose choice as of mid-2026. Worth re-checking
# console.groq.com/docs/models if this ever starts returning 404s, same
# lesson learned from the Gemini embedding model deprecation.
MODEL_NAME = "openai/gpt-oss-20b"


class GroqClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: Groq | None = None

    def _connect(self) -> None:
        if self._client is not None:
            return
        self._client = Groq(api_key=self._settings.groq_api_key)
        logger.info("Groq client initialized")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self._connect()
        response = self._client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def health_check(self) -> dict:
        try:
            self.generate("You are a health check.", "Reply with just 'ok'.")
            return {"service": "groq", "status": "up"}
        except Exception as exc:  # noqa: BLE001
            logger.error("Groq health check failed: %s", exc)
            return {"service": "groq", "status": "down", "reason": str(exc)}