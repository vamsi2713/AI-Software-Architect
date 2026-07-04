"""
/query endpoint - hybrid retrieval + multi-agent LangGraph reasoning,
now with conversation memory (Milestone 11): messages are persisted to
Postgres, and prior turns in the same conversation are fed back into
the reasoning step so follow-up questions work.
"""

from fastapi import APIRouter, Depends

from src.core.dependencies import get_graph_db, get_vector_db, get_embedding_client, get_groq_client, get_relational_db
from src.infrastructure.graph_db import GraphDatabaseClient
from src.infrastructure.vector_db import VectorDatabaseClient
from src.infrastructure.embedding_client import EmbeddingClient
from src.infrastructure.groq_client import GroqClient
from src.infrastructure.relational_db import RelationalDatabaseClient
from src.agents.reasoning_agent import build_reasoning_graph
from src.core.logging_config import get_logger


def _rewrite_query_with_history(question: str, history: list[dict], groq_client: GroqClient) -> str:
    """
    Follow-up questions like "what does it call" have no meaning to a
    semantic search on their own - "it" isn't a concept with an
    embedding. This rewrites the question into a self-contained form
    using conversation history, BEFORE embedding it for retrieval, so
    the search actually finds relevant nodes.
    """
    if not history:
        return question

    history_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in history
    )
    system_prompt = (
        "Rewrite the user's latest question into a fully self-contained "
        "question that makes sense without any conversation history - "
        "replace pronouns and vague references (it, that, this, the other "
        "one) with the actual specific names they refer to, based on the "
        "conversation below. Reply with ONLY the rewritten question, "
        "nothing else. If the question is already self-contained, return "
        "it unchanged."
    )
    user_prompt = f"Conversation so far:\n{history_text}\n\nLatest question: {question}"
    return groq_client.generate(system_prompt, user_prompt).strip()

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("")
def query_knowledge_graph(
    question: str,
    top_k: int = 5,
    reason: bool = True,
    conversation_id: int | None = None,
    graph_db: GraphDatabaseClient = Depends(get_graph_db),
    vector_db: VectorDatabaseClient = Depends(get_vector_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    groq_client: GroqClient = Depends(get_groq_client),
    relational_db: RelationalDatabaseClient = Depends(get_relational_db),
) -> dict:
    # A conversation_id ties this question to prior turns - if none was
    # given, this is a brand new conversation, so create one now using
    # the question itself as a readable title.
    if conversation_id is None:
        conversation_id = relational_db.create_conversation(title=question[:80])

    history = relational_db.get_messages(conversation_id) if reason else []
    relational_db.save_message(conversation_id, role="user", content=question)
    search_question = _rewrite_query_with_history(question, history, groq_client) if reason else question

    query_vector = embedding_client.embed_text(search_question, task_type="retrieval_query")
    semantic_matches = vector_db.search(query_vector, top_k=top_k)

    results = []
    for match in semantic_matches:
        node_id = match.payload.get("okf_id")
        related = graph_db.get_related_nodes(node_id) if node_id else []
        results.append({
            "id": node_id,
            "name": match.payload.get("name"),
            "file_path": match.payload.get("file_path"),
            "similarity_score": match.score,
            "related_nodes": related,
        })

    logger.info("Query %r returned %d semantic matches", question, len(results))

    response = {
        "question": question,
        "conversation_id": conversation_id,
        "results": results,
    }

    if reason:
        reasoning_graph = build_reasoning_graph(groq_client)
        final_state = reasoning_graph.invoke({
            "question": question,
            "context": results,
            "history": history,
            "agent_type": "",
            "answer": "",
        })
        response["answer"] = final_state["answer"]
        response["agent_used"] = final_state["agent_type"]
        relational_db.save_message(
            conversation_id, role="assistant", content=final_state["answer"], agent_type=final_state["agent_type"]
        )

    return response