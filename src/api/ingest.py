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

        all_nodes = []
        all_relationships = []
        all_pending_calls = []
        files_processed = 0
        embedding_failures = 0

        # First pass: parse and convert every file, but don't write yet -
        # call resolution needs to see nodes from ALL files first, since a
        # function in main.py might call a function defined in utils.py.
        for file_path in walker.find_python_files():
            parsed = parser.parse_file(file_path)
            if parsed is None:
                continue

            nodes, relationships, pending_calls = converter.convert(parsed)
            all_nodes.extend(nodes)
            all_relationships.extend(relationships)
            all_pending_calls.extend(pending_calls)
            files_processed += 1

        # Second pass: now that we've seen every function/method in the
        # repo, resolve call names to actual node IDs.
        name_lookup = converter.build_name_lookup(all_nodes)
        call_relationships = converter.resolve_calls(all_pending_calls, name_lookup)
        all_relationships.extend(call_relationships)

        # Write structure to the graph - this succeeds even if embeddings
        # later fail, so the graph is never left partially written because
        # of an unrelated API hiccup.
        graph_db.write_okf_nodes(all_nodes, all_relationships)

        for node in all_nodes:
            try:
                vector = embedding_client.embed_text(node.to_embedding_text())
                vector_db.upsert_node(node.id, vector, node.to_graph_properties())
            except Exception as exc:  # noqa: BLE001
                embedding_failures += 1
                logger.warning("Embedding failed for %s: %s", node.id, exc)

        logger.info(
            "Ingested %d files: %d nodes, %d relationships, %d embedding failures",
            files_processed, len(all_nodes), len(all_relationships), embedding_failures,
        )

        return {
            "repo_path": repo_path,
            "files_processed": files_processed,
            "nodes_written": len(all_nodes),
            "relationships_written": len(all_relationships),
            "embedding_failures": embedding_failures,
        }