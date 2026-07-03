"""
Tests for the health endpoint. We mock the clients so tests never
depend on live Neo4j/Qdrant/Postgres connections - FastAPI's
dependency_overrides lets us swap real clients for fakes.
"""

from fastapi.testclient import TestClient

from src.main import app
from src.core.dependencies import get_graph_db, get_vector_db, get_relational_db


class _FakeUpClient:
    def __init__(self, service_name: str):
        self._service_name = service_name

    def health_check(self) -> dict:
        return {"service": self._service_name, "status": "up"}


def test_health_endpoint_all_services_up():
    app.dependency_overrides[get_graph_db] = lambda: _FakeUpClient("neo4j")
    app.dependency_overrides[get_vector_db] = lambda: _FakeUpClient("qdrant")
    app.dependency_overrides[get_relational_db] = lambda: _FakeUpClient("postgres")

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "healthy"
    assert len(body["checks"]) == 3

    app.dependency_overrides.clear()


def test_health_endpoint_reports_degraded_when_one_service_down():
    class _FakeDownClient:
        def health_check(self) -> dict:
            return {"service": "qdrant", "status": "down", "reason": "timeout"}

    app.dependency_overrides[get_graph_db] = lambda: _FakeUpClient("neo4j")
    app.dependency_overrides[get_vector_db] = _FakeDownClient
    app.dependency_overrides[get_relational_db] = lambda: _FakeUpClient("postgres")

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["overall_status"] == "degraded"

    app.dependency_overrides.clear()