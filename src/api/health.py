"""
Health check endpoint - the first feature we build. Before any parsing
or agent logic exists, we need certainty all three data stores are
reachable. Every later milestone assumes this works.
"""

from fastapi import APIRouter, Depends

from src.core.dependencies import get_graph_db, get_vector_db, get_relational_db
from src.infrastructure.graph_db import GraphDatabaseClient
from src.infrastructure.vector_db import VectorDatabaseClient
from src.infrastructure.relational_db import RelationalDatabaseClient

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check(
    graph_db: GraphDatabaseClient = Depends(get_graph_db),
    vector_db: VectorDatabaseClient = Depends(get_vector_db),
    relational_db: RelationalDatabaseClient = Depends(get_relational_db),
) -> dict:
    checks = [
        graph_db.health_check(),
        vector_db.health_check(),
        relational_db.health_check(),
    ]
    overall = "healthy" if all(c["status"] == "up" for c in checks) else "degraded"
    return {"overall_status": overall, "checks": checks}
