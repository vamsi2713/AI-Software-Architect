"""
/query endpoint - Milestone 5's hybrid retrieval (semantic search +
graph traversal) combined with Milestone 6's LangGraph + Groq reasoning
layer, which synthesizes the retrieved context into a real
natural-language answer.
"""

from fastapi import APIRouter, Depends

from src.core.dependencies import get_graph_db, get_vector_db, get_embedding_client, get_groq_client
from src.infrastructure.graph_db import GraphDatabaseClient
from src.infrastructure.vector_db import VectorDatabaseClient
from src.infrastructure.embedding_client import EmbeddingClient
from src.infrastructure.groq_client import GroqClient
from src.agents.reasoning_agent import build_reasoning_graph
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("")
def query_knowledge_graph(
    question: str,
    top_k: int = 5,
    reason: bool = True,
    graph_db: GraphDatabaseClient = Depends(get_graph_db),
    vector_db: VectorDatabaseClient = Depends(get_vector_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    groq_client: GroqClient = Depends(get_groq_client),
) -> dict:
    query_vector = embedding_client.embed_text(question, task_type="retrieval_query")
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
        "results": results,
    }

    if reason:
        reasoning_graph = build_reasoning_graph(groq_client)
        final_state = reasoning_graph.invoke({
            "question": question,
            "context": results,
            "answer": "",
        })
        response["answer"] = final_state["answer"]

    return response