"""
Neo4j (AuraDB) client wrapper.

Agents and services depend on THIS class, not on `neo4j.GraphDatabase`
directly (Dependency Inversion). If we ever swap graph databases, only
this file changes. It also centralizes connection lifecycle and gives
us a health check for the /health endpoint.
"""

from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError

from src.core.config import Settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class GraphDatabaseClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._driver: Driver | None = None

    def connect(self) -> None:
        if self._driver is not None:
            return
        self._driver = GraphDatabase.driver(
            self._settings.neo4j_uri,
            auth=(self._settings.neo4j_username, self._settings.neo4j_password),
        )
        logger.info("Neo4j driver initialized for %s", self._settings.neo4j_uri)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed")

    def health_check(self) -> dict:
        """Returns a status dict instead of raising, so /health can report
        partial system health rather than crashing entirely."""
        try:
            self.connect()
            self._driver.verify_connectivity()
            return {"service": "neo4j", "status": "up"}
        except AuthError:
            logger.error("Neo4j authentication failed - check credentials")
            return {"service": "neo4j", "status": "down", "reason": "auth_error"}
        except ServiceUnavailable:
            logger.error("Neo4j service unreachable - check URI/network")
            return {"service": "neo4j", "status": "down", "reason": "unreachable"}
        except Exception as exc:  # noqa: BLE001
            logger.error("Neo4j health check failed: %s", exc)
            return {"service": "neo4j", "status": "down", "reason": str(exc)}

    def run_query(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Agents in later milestones call this, not the raw driver."""
        self.connect()
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
        
    def write_okf_nodes(self, nodes: list, relationships: list) -> None:
        """
        Writes OKF nodes and relationships into Neo4j using MERGE (not
        CREATE) - MERGE means re-running ingestion on the same repo
        updates existing nodes instead of creating duplicates every time.
        """
        self.connect()
        with self._driver.session() as session:
            for node in nodes:
                session.run(
                    """
                    MERGE (n:%s {id: $id})
                    SET n.name = $name,
                        n.file_path = $file_path,
                        n.line_number = $line_number,
                        n.docstring = $docstring
                    """ % node.node_type.value,
                    node.to_graph_properties(),
                )
            for rel in relationships:
                session.run(
                    """
                    MATCH (a {id: $from_id}), (b {id: $to_id})
                    MERGE (a)-[:%s]->(b)
                    """ % rel.relationship_type,
                    {"from_id": rel.from_id, "to_id": rel.to_id},
                )