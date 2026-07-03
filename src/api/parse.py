"""
/parse endpoint - accepts a filesystem path to a repository, walks it,
parses every Python file, and returns a structural summary.

This is a synchronous, on-demand endpoint for now. In a later milestone,
this becomes a background ingestion job (so parsing a huge repo doesn't
block the HTTP request) - but proving the parsing logic works correctly
on-demand first is the right order of operations.
"""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from src.parsers.repository_walker import RepositoryWalker
from src.parsers.python_parser import PythonParser
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/parse", tags=["parse"])


@router.get("")
def parse_repository(repo_path: str) -> dict:
    try:
        walker = RepositoryWalker(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    python_files = walker.find_python_files()
    parser = PythonParser()

    parsed_files = []
    skipped_count = 0
    for file_path in python_files:
        result = parser.parse_file(file_path)
        if result is None:
            skipped_count += 1
            continue
        parsed_files.append(asdict(result))

    logger.info(
        "Parsed %d files (%d skipped) from %s",
        len(parsed_files), skipped_count, repo_path,
    )

    return {
        "repo_path": repo_path,
        "total_files_found": len(python_files),
        "files_parsed": len(parsed_files),
        "files_skipped": skipped_count,
        "files": parsed_files,
    }