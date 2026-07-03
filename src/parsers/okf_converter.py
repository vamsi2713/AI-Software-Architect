"""
Converts a ParsedFile (Milestone 2's output) into OKF nodes and
relationships (Milestone 3's unified shape) - ready to write into
Neo4j and Qdrant.
"""

from src.parsers.models import ParsedFile
from src.parsers.okf_models import OKFNode, OKFRelationship, NodeType


class OKFConverter:
    def convert(self, parsed_file: ParsedFile) -> tuple[list[OKFNode], list[OKFRelationship]]:
        nodes: list[OKFNode] = []
        relationships: list[OKFRelationship] = []

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

        return nodes, relationships