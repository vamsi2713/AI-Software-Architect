"""
Tests for the OKF converter (Milestone 3) and call resolution
(Milestone 4) - specifically the trickiest part of the whole pipeline:
turning bare call names into resolved CALLS relationships across files.
"""

from src.parsers.models import ParsedFile, ParsedFunction
from src.parsers.okf_converter import OKFConverter
from src.parsers.okf_models import NodeType


def test_convert_creates_file_and_function_nodes_with_contains_relationship():
    parsed = ParsedFile(
        file_path="example.py",
        functions=[ParsedFunction(name="do_thing", line_number=1)],
    )
    converter = OKFConverter()
    nodes, relationships, pending_calls = converter.convert(parsed)

    node_types = {n.node_type for n in nodes}
    assert NodeType.FILE in node_types
    assert NodeType.FUNCTION in node_types

    contains = [r for r in relationships if r.relationship_type == "CONTAINS"]
    assert len(contains) == 1


def test_resolve_calls_creates_relationship_for_known_call():
    parsed_a = ParsedFile(
        file_path="a.py",
        functions=[ParsedFunction(name="caller", line_number=1, calls=["helper"])],
    )
    parsed_b = ParsedFile(
        file_path="b.py",
        functions=[ParsedFunction(name="helper", line_number=1)],
    )
    converter = OKFConverter()

    all_nodes, all_relationships, all_pending = [], [], []
    for parsed in (parsed_a, parsed_b):
        nodes, relationships, pending = converter.convert(parsed)
        all_nodes.extend(nodes)
        all_relationships.extend(relationships)
        all_pending.extend(pending)

    name_lookup = converter.build_name_lookup(all_nodes)
    call_relationships = converter.resolve_calls(all_pending, name_lookup)

    assert len(call_relationships) == 1
    rel = call_relationships[0]
    assert rel.relationship_type == "CALLS"
    assert rel.from_id == "function:a.py:caller"
    assert rel.to_id == "function:b.py:helper"


def test_resolve_calls_silently_skips_unknown_names():
    """Calls to built-ins (print, len) or third-party libraries should
    not produce broken/dangling relationships - they're simply not in
    the name lookup, so they get skipped."""
    parsed = ParsedFile(
        file_path="a.py",
        functions=[ParsedFunction(name="caller", line_number=1, calls=["print"])],
    )
    converter = OKFConverter()
    nodes, _, pending = converter.convert(parsed)
    name_lookup = converter.build_name_lookup(nodes)

    call_relationships = converter.resolve_calls(pending, name_lookup)
    assert call_relationships == []


def test_resolve_calls_skips_self_recursive_calls():
    parsed = ParsedFile(
        file_path="a.py",
        functions=[ParsedFunction(name="recursive", line_number=1, calls=["recursive"])],
    )
    converter = OKFConverter()
    nodes, _, pending = converter.convert(parsed)
    name_lookup = converter.build_name_lookup(nodes)

    call_relationships = converter.resolve_calls(pending, name_lookup)
    assert call_relationships == []