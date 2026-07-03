"""
/ingest endpoint - the full Milestone 3 pipeline in one call:
parse a repo -> convert to OKF -> write nodes/relationships to Neo4j
-> embed each node -> write vectors to Qdrant.

This is intentionally synchronous and simple for now (no background
jobs, no batching) - proving the full chain works correctly end-to-end
matters more right now than making it fast or scalable. We'll revisit
performance once the logic is proven.
"""

from fastapi import APIRouter, Depends, HTTPException

from src.parsers.repository_walker import RepositoryWalker
from src.parsers.python_parser import PythonParser
from src.parsers.okf_converter import OKFConverter
from src.core.dependencies import get_graph_db, get_vector_db, get_embedding_client
from src.infrastructure.graph_db import GraphDatabaseClient
from src.infrastructure.vector_db import VectorDatabaseClient
from src.infrastructure.embedding_client import EmbeddingClient
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("")
def ingest_repository(
    repo_path: str,
    graph_db: GraphDatabaseClient = Depends(get_graph_db),
    vector_db: VectorDatabaseClient = Depends(get_vector_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> dict:
    try:
        walker = RepositoryWalker(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    parser = PythonParser()
    converter = OKFConverter()

    total_nodes = 0
    total_relationships = 0
    files_processed = 0
    embedding_failures = 0

    for file_path in walker.find_python_files():
        parsed = parser.parse_file(file_path)
        if parsed is None:
            continue

        nodes, relationships = converter.convert(parsed)

        # Write structure to the graph first - this succeeds even if
        # embeddings later fail, so the graph is never left partially
        # written because of an unrelated API hiccup.
        graph_db.write_okf_nodes(nodes, relationships)

        for node in nodes:
            try:
                vector = embedding_client.embed_text(node.to_embedding_text())
                vector_db.upsert_node(node.id, vector, node.to_graph_properties())
            except Exception as exc:  # noqa: BLE001
                embedding_failures += 1
                logger.warning("Embedding failed for %s: %s", node.id, exc)

        total_nodes += len(nodes)
        total_relationships += len(relationships)
        files_processed += 1

    logger.info(
        "Ingested %d files: %d nodes, %d relationships, %d embedding failures",
        files_processed, total_nodes, total_relationships, embedding_failures,
    )

    return {
        "repo_path": repo_path,
        "files_processed": files_processed,
        "nodes_written": total_nodes,
        "relationships_written": total_relationships,
        "embedding_failures": embedding_failures,
    }