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
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import UploadFile, File


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
    return _run_ingestion(repo_path, graph_db, vector_db, embedding_client)


def _run_ingestion(
    repo_path: str,
    graph_db: GraphDatabaseClient,
    vector_db: VectorDatabaseClient,
    embedding_client: EmbeddingClient,
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

    for file_path in walker.find_python_files():
        parsed = parser.parse_file(file_path)
        if parsed is None:
            continue

        nodes, relationships, pending_calls = converter.convert(parsed)
        all_nodes.extend(nodes)
        all_relationships.extend(relationships)
        all_pending_calls.extend(pending_calls)
        files_processed += 1

    name_lookup = converter.build_name_lookup(all_nodes)
    call_relationships = converter.resolve_calls(all_pending_calls, name_lookup)
    all_relationships.extend(call_relationships)

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

@router.post("/upload")
async def ingest_uploaded_repository(
    file: UploadFile = File(...),
    graph_db: GraphDatabaseClient = Depends(get_graph_db),
    vector_db: VectorDatabaseClient = Depends(get_vector_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> dict:
    """
    Same ingestion pipeline as /ingest, but the repo arrives as an
    uploaded .zip file instead of a local folder path - lets someone
    use the product from the website without needing terminal access
    to the server's filesystem.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")

    # Extract to a temp directory that gets cleaned up automatically,
    # even if ingestion fails partway through - we never want to leave
    # someone's uploaded code sitting on the server indefinitely.
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / file.filename
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        extract_dir = Path(temp_dir) / "extracted"
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid zip archive")

        # From here it's the exact same pipeline as /ingest - just
        # pointed at the extracted temp folder instead of a path the
        # user typed.
        return _run_ingestion(str(extract_dir), graph_db, vector_db, embedding_client)