"""
Tests for the AST-based Python parser (Milestone 2), including call
extraction (Milestone 4).
"""

import tempfile
from pathlib import Path

from src.parsers.python_parser import PythonParser


def _parse_source(source: str):
    """Writes source to a temp file and parses it - the parser reads
    from disk by design, so tests go through the real file path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(source)
        temp_path = Path(f.name)
    try:
        return PythonParser().parse_file(temp_path)
    finally:
        temp_path.unlink()


def test_parses_top_level_function():
    parsed = _parse_source("def greet(name):\n    return f'hello {name}'\n")
    assert len(parsed.functions) == 1
    assert parsed.functions[0].name == "greet"
    assert parsed.functions[0].parameters == ["name"]


def test_parses_class_with_methods_not_as_top_level_functions():
    source = (
        "class Greeter:\n"
        "    def hello(self):\n"
        "        pass\n"
    )
    parsed = _parse_source(source)
    # Regression test for the ast.iter_child_nodes vs ast.walk decision
    # documented in the project handoff - methods must NOT leak into
    # the top-level functions list.
    assert parsed.functions == []
    assert len(parsed.classes) == 1
    assert len(parsed.classes[0].methods) == 1
    assert parsed.classes[0].methods[0].name == "hello"


def test_extracts_direct_function_calls():
    source = (
        "def helper():\n"
        "    pass\n"
        "\n"
        "def caller():\n"
        "    helper()\n"
    )
    parsed = _parse_source(source)
    caller = next(f for f in parsed.functions if f.name == "caller")
    assert "helper" in caller.calls


def test_extracts_method_calls_via_attribute_access():
    source = (
        "class Client:\n"
        "    def connect(self):\n"
        "        pass\n"
        "    def run(self):\n"
        "        self.connect()\n"
    )
    parsed = _parse_source(source)
    run_method = next(m for m in parsed.classes[0].methods if m.name == "run")
    assert "connect" in run_method.calls


def test_unparseable_file_returns_none_instead_of_raising():
    parsed = _parse_source("def broken(:\n    this is not valid python\n")
    assert parsed is None