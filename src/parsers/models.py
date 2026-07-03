"""
Data models representing a parsed Python file's structure.

These are plain dataclasses, not database models - they're the
in-memory representation that flows between the parser and (in
Milestone 3) the OKF converter. Keeping them separate from any
database schema means the parser doesn't need to know anything
about Neo4j, Qdrant, or Postgres.
"""

from dataclasses import dataclass, field


@dataclass
class ParsedFunction:
    name: str
    line_number: int
    docstring: str | None = None
    parameters: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)  # names of functions/methods called in this function's body

@dataclass
class ParsedClass:
    name: str
    line_number: int
    docstring: str | None = None
    methods: list[ParsedFunction] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)


@dataclass
class ParsedImport:
    module: str
    names: list[str] = field(default_factory=list)  # e.g. ["A", "B"] from "from x import A, B"
    line_number: int = 0


@dataclass
class ParsedFile:
    file_path: str
    classes: list[ParsedClass] = field(default_factory=list)
    functions: list[ParsedFunction] = field(default_factory=list)  # top-level only
    imports: list[ParsedImport] = field(default_factory=list)