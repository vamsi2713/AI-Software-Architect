"""
Finds all Python files in a repository, skipping folders that would
just add noise (virtual envs, git internals, caches, node_modules).
"""

from pathlib import Path

EXCLUDED_DIRS = {
    ".venv", "venv", "__pycache__", ".git", ".pytest_cache",
    "node_modules", "dist", "build", ".mypy_cache",
}


class RepositoryWalker:
    def __init__(self, repo_path: str):
        self._repo_path = Path(repo_path)
        if not self._repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

    def find_python_files(self) -> list[Path]:
        """Recursively walks the repo, returning every .py file that
        isn't inside an excluded directory."""
        python_files = []
        for path in self._repo_path.rglob("*.py"):
            if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
                continue
            python_files.append(path)
        return python_files