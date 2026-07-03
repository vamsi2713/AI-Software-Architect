"""
Open Knowledge Format (OKF) - the unified shape every piece of
knowledge takes before it enters the graph or vector store, regardless
of whether it came from a Python file, a future JS parser, or a future
SQL schema parser.

This is the translation layer: ParsedFile/ParsedClass/ParsedFunction
(Milestone 2's language-specific shapes) all get converted INTO this
one consistent shape. Neo4j and Qdrant only ever need to know about
OKFNode - never about Python's ast module.
"""

from dataclasses import dataclass, field
from enum import Enum


class NodeType(str, Enum):
    FILE = "File"
    CLASS = "Class"
    FUNCTION = "Function"
    METHOD = "Method"


@dataclass
class OKFRelationship:
    from_id: str
    to_id: str
    relationship_type: str  # e.g. "CONTAINS", "DEFINES", "IMPORTS"


@dataclass
class OKFNode:
    id: str  # stable, unique - e.g. "file:src/main.py" or "class:src/main.py:MyClass"
    node_type: NodeType
    name: str
    file_path: str
    line_number: int = 0
    docstring: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_embedding_text(self) -> str:
        """
        Builds the text that actually gets embedded for semantic search.
        Deliberately includes type + name + docstring, not just the
        name alone - "health_check" alone embeds poorly, but "Method
        health_check: Returns a status dict instead of raising..."
        gives the embedding model real semantic signal to work with.
        """
        parts = [f"{self.node_type.value} {self.name}"]
        if self.docstring:
            parts.append(self.docstring)
        parts.append(f"defined in {self.file_path}")
        return ". ".join(parts)

    def to_graph_properties(self) -> dict:
        """Flat dict suitable for writing as Neo4j node properties."""
        return {
            "id": self.id,
            "name": self.name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "docstring": self.docstring or "",
        }