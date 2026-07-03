"""
Converts a ParsedFile (Milestone 2's output) into OKF nodes and
relationships (Milestone 3's unified shape) - ready to write into
Neo4j and Qdrant.
"""

from src.parsers.models import ParsedFile
from src.parsers.okf_models import OKFNode, OKFRelationship, NodeType


class OKFConverter:
    def convert(
        self, parsed_file: ParsedFile
    ) -> tuple[list[OKFNode], list[OKFRelationship], list[tuple[str, str]]]:
        """
        Returns (nodes, relationships, pending_calls).
        pending_calls is a list of (source_node_id, called_name) pairs -
        these can't be turned into real CALLS relationships yet because
        we don't know which file the called function actually lives in
        until we've parsed the whole repo. Resolution happens later via
        build_name_lookup() + resolve_calls().
        """
        nodes: list[OKFNode] = []
        relationships: list[OKFRelationship] = []
        pending_calls: list[tuple[str, str]] = []

        file_id = f"file:{parsed_file.file_path}"
        file_node = OKFNode(
            id=file_id,
            node_type=NodeType.FILE,
            name=parsed_file.file_path.split("\\")[-1].split("/")[-1],
            file_path=parsed_file.file_path,
        )
        nodes.append(file_node)

        # Top-level functions -> CONTAINS relationship from file
        for func in parsed_file.functions:
            func_id = f"function:{parsed_file.file_path}:{func.name}"
            nodes.append(OKFNode(
                id=func_id,
                node_type=NodeType.FUNCTION,
                name=func.name,
                file_path=parsed_file.file_path,
                line_number=func.line_number,
                docstring=func.docstring,
            ))
            relationships.append(OKFRelationship(
                from_id=file_id, to_id=func_id, relationship_type="CONTAINS",
            ))
            for called_name in func.calls:
                pending_calls.append((func_id, called_name))

        # Classes -> CONTAINS from file, methods -> DEFINES from class
        for cls in parsed_file.classes:
            class_id = f"class:{parsed_file.file_path}:{cls.name}"
            nodes.append(OKFNode(
                id=class_id,
                node_type=NodeType.CLASS,
                name=cls.name,
                file_path=parsed_file.file_path,
                line_number=cls.line_number,
                docstring=cls.docstring,
            ))
            relationships.append(OKFRelationship(
                from_id=file_id, to_id=class_id, relationship_type="CONTAINS",
            ))

            for method in cls.methods:
                method_id = f"method:{parsed_file.file_path}:{cls.name}:{method.name}"
                nodes.append(OKFNode(
                    id=method_id,
                    node_type=NodeType.METHOD,
                    name=method.name,
                    file_path=parsed_file.file_path,
                    line_number=method.line_number,
                    docstring=method.docstring,
                ))
                relationships.append(OKFRelationship(
                    from_id=class_id, to_id=method_id, relationship_type="DEFINES",
                ))
                for called_name in method.calls:
                    pending_calls.append((method_id, called_name))

        return nodes, relationships, pending_calls

    def build_name_lookup(self, all_nodes: list[OKFNode]) -> dict[str, str]:
        """
        Maps a bare function/method name -> its OKF node ID, across the
        whole repo. Only FUNCTION and METHOD nodes are included, since
        those are the only things that can be "called".

        Known limitation: if two functions share the same name in
        different files, the last one wins - this is a simple
        name-based match, not true import resolution. Good enough for
        this milestone; a precise version would need to trace actual
        import statements.
        """
        lookup: dict[str, str] = {}
        for node in all_nodes:
            if node.node_type in (NodeType.FUNCTION, NodeType.METHOD):
                lookup[node.name] = node.id
        return lookup

    def resolve_calls(
        self, pending_calls: list[tuple[str, str]], name_lookup: dict[str, str]
    ) -> list[OKFRelationship]:
        """
        Turns (source_id, called_name) pairs into real CALLS
        relationships, using the name lookup. Calls to names we don't
        recognize (built-ins like `print`, third-party library calls,
        etc.) are silently skipped - we only care about calls within
        this codebase.
        """
        relationships: list[OKFRelationship] = []
        for source_id, called_name in pending_calls:
            target_id = name_lookup.get(called_name)
            if target_id is None:
                continue
            if target_id == source_id:
                continue  # skip self-recursive calls for now, keeps the graph cleaner
            relationships.append(OKFRelationship(
                from_id=source_id, to_id=target_id, relationship_type="CALLS",
            ))
        return relationships