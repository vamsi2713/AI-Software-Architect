"""
Tests for the /impact endpoint (Milestone 8), using fake graph clients
so tests never depend on a live Neo4j connection - same pattern as
test_health.py.
"""

from fastapi.testclient import TestClient

from src.main import app
from src.core.dependencies import get_graph_db


class _FakeGraphDb:
    def __init__(self, name_matches, impact_chain):
        self._name_matches = name_matches
        self._impact_chain = impact_chain

    def find_nodes_by_name(self, name: str) -> list[dict]:
        return self._name_matches

    def get_impact_chain(self, node_id: str, max_depth: int = 5) -> list[dict]:
        return self._impact_chain


def test_impact_returns_404_for_unknown_name():
    app.dependency_overrides[get_graph_db] = lambda: _FakeGraphDb([], [])
    client = TestClient(app)

    response = client.get("/impact?name=nonexistent")

    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_impact_flags_ambiguous_names():
    matches = [
        {"id": "method:a.py:A:connect", "name": "connect", "file_path": "a.py"},
        {"id": "method:b.py:B:connect", "name": "connect", "file_path": "b.py"},
    ]
    app.dependency_overrides[get_graph_db] = lambda: _FakeGraphDb(matches, [])
    client = TestClient(app)

    response = client.get("/impact?name=connect")

    assert response.status_code == 200
    body = response.json()
    assert body["ambiguous"] is True
    assert len(body["matches"]) == 2
    app.dependency_overrides.clear()


def test_impact_returns_dependents_for_unambiguous_name():
    matches = [{"id": "function:a.py:target", "name": "target", "file_path": "a.py"}]
    dependents = [{"id": "function:b.py:caller", "name": "caller", "file_path": "b.py", "hops": 1}]
    app.dependency_overrides[get_graph_db] = lambda: _FakeGraphDb(matches, dependents)
    client = TestClient(app)

    response = client.get("/impact?name=target")

    assert response.status_code == 200
    body = response.json()
    assert body["total_dependents"] == 1
    assert body["dependents"][0]["name"] == "caller"
    app.dependency_overrides.clear()