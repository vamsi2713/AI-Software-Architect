"""
/query endpoint - Milestone 5's hybrid retrieval: given a natural
language question, combines semantic search (Qdrant) with graph
traversal (Neo4j) to return relevant, connected context.

This endpoint does NOT call an LLM to generate a text answer - that's
deliberately deferred to Milestone 6+ (LangGraph + Groq reasoning).
Right now the job is just proving we can retrieve the right MIX of
semantically similar nodes AND their structural neighbors.
"""

from fastapi import APIRouter, Depends

from src.core.dependencies import get_graph_db, get_vector_db, get_embedding_client
from src.infrastructure.graph_db import GraphDatabaseClient
from src.infrastructure.vector_db import VectorDatabaseClient
from src.infrastructure.embedding_client import EmbeddingClient
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("")
def query_knowledge_graph(
    question: str,
    top_k: int = 5,
    graph_db: GraphDatabaseClient = Depends(get_graph_db),
    vector_db: VectorDatabaseClient = Depends(get_vector_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> dict:
    # Embed the question with task_type="retrieval_query" - using
    # "retrieval_document" here would silently degrade match quality,
    # per the embedding model's documented asymmetry between the two.
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

    return {
        "question": question,
        "results": results,
    }