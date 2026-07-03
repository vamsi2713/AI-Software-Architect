"""
/impact endpoint - Milestone 8: dedicated impact analysis.

Given a function/method/class name, finds everything that transitively
depends on it (calls it, directly or indirectly) via the CALLS graph,
so a developer can answer "what would break if I change this?" with a
real multi-hop dependency chain instead of just one hop of context.
"""

from fastapi import APIRouter, Depends, HTTPException

from src.core.dependencies import get_graph_db
from src.infrastructure.graph_db import GraphDatabaseClient
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/impact", tags=["impact"])


@router.get("")
def analyze_impact(
    name: str,
    max_depth: int = 5,
    graph_db: GraphDatabaseClient = Depends(get_graph_db),
) -> dict:
    matches = graph_db.find_nodes_by_name(name)

    if not matches:
        raise HTTPException(status_code=404, detail=f"No node found with name '{name}'")

    if len(matches) > 1:
        # Ambiguous name - don't guess which one was meant. Return the
        # matches so the caller can pick the right one by full id.
        return {
            "name": name,
            "ambiguous": True,
            "matches": matches,
            "message": "Multiple nodes share this name. Re-query using the exact 'id' from one of these matches.",
        }

    target = matches[0]
    dependents = graph_db.get_impact_chain(target["id"], max_depth=max_depth)

    return {
        "name": name,
        "target": target,
        "max_depth": max_depth,
        "total_dependents": len(dependents),
        "dependents": dependents,
    }