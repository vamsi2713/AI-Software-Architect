"""
Endpoints for browsing conversation history (Milestone 11) - lets the
frontend show a sidebar of past conversations and load one back up.
"""

from fastapi import APIRouter, Depends

from src.core.dependencies import get_relational_db
from src.infrastructure.relational_db import RelationalDatabaseClient

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
def list_conversations(relational_db: RelationalDatabaseClient = Depends(get_relational_db)) -> list[dict]:
    return relational_db.list_conversations()


@router.get("/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: int,
    relational_db: RelationalDatabaseClient = Depends(get_relational_db),
) -> list[dict]:
    return relational_db.get_messages(conversation_id)