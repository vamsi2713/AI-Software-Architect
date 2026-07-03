"""
Dependency injection wiring.

FastAPI's Depends() system needs functions that construct and return
instances. Centralizing them here means every route gets clients the
same way, and swapping an implementation later (or injecting a mock
during tests) means changing ONE function, not every route that uses it.
"""

from functools import lru_cache

from src.core.config import get_settings
from src.infrastructure.graph_db import GraphDatabaseClient
from src.infrastructure.vector_db import VectorDatabaseClient
from src.infrastructure.relational_db import RelationalDatabaseClient


@lru_cache
def get_graph_db() -> GraphDatabaseClient:
    return GraphDatabaseClient(get_settings())


@lru_cache
def get_vector_db() -> VectorDatabaseClient:
    return VectorDatabaseClient(get_settings())


@lru_cache
def get_relational_db() -> RelationalDatabaseClient:
    return RelationalDatabaseClient(get_settings())