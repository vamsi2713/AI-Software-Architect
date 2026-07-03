"""
Parses a single Python file's source into a ParsedFile using the
built-in `ast` module - no regex, no LLM, 100% accurate against
however Python itself would parse the file.
"""

import ast
from pathlib import Path

from src.parsers.models import ParsedFile, ParsedClass, ParsedFunction, ParsedImport
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class PythonParser:
    def parse_file(self, file_path: Path) -> ParsedFile | None:
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            # A file that doesn't parse shouldn't crash the whole ingestion
            # run - log it and move on. Real repos sometimes have generated
            # or broken files.
            logger.warning("Skipping unparseable file %s: %s", file_path, exc)
            return None

        parsed = ParsedFile(file_path=str(file_path))

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                parsed.classes.append(self._parse_class(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parsed.functions.append(self._parse_function(node))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parsed.imports.append(
                        ParsedImport(module=alias.name, line_number=node.lineno)
                    )
            elif isinstance(node, ast.ImportFrom):
                parsed.imports.append(
                    ParsedImport(
                        module=node.module or "",
                        names=[alias.name for alias in node.names],
                        line_number=node.lineno,
                    )
                )

        return parsed

    def _parse_class(self, node: ast.ClassDef) -> ParsedClass:
        methods = [
            self._parse_function(item)
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        base_classes = [
            base.id for base in node.bases if isinstance(base, ast.Name)
        ]
        return ParsedClass(
            name=node.name,
            line_number=node.lineno,
            docstring=ast.get_docstring(node),
            methods=methods,
            base_classes=base_classes,
        )

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ParsedFunction:
        parameters = [arg.arg for arg in node.args.args]
        return ParsedFunction(
            name=node.name,
            line_number=node.lineno,
            docstring=ast.get_docstring(node),
            parameters=parameters,
        )