"""Ignore rules and path filters for Code68 codebase scanning."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import List, Set

DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git",
    ".code68",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
}

DEFAULT_IGNORE_EXTENSIONS: Set[str] = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".iso",
    ".tar",
    ".gz",
    ".zip",
    ".7z",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".pdf",
    ".lock",
}


class IgnoreFilter:
    """Filters files based on .gitignore patterns and default exclusions."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.patterns: List[str] = []
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        gi_path = self.workspace_root / ".gitignore"
        if gi_path.is_file():
            try:
                with open(gi_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            self.patterns.append(line)
            except Exception:
                pass

    def is_ignored(self, path: Path) -> bool:
        """Check if path should be excluded from codebase indexing."""
        try:
            rel = path.relative_to(self.workspace_root)
        except ValueError:
            rel = path

        # Check directory names in parts
        for part in rel.parts:
            if part in DEFAULT_IGNORE_DIRS:
                return True

        # Check binary extensions
        if path.is_file() and path.suffix.lower() in DEFAULT_IGNORE_EXTENSIONS:
            return True

        # Check gitignore patterns
        rel_str = str(rel).replace("\\", "/")
        name = path.name
        for pat in self.patterns:
            pat_clean = pat.rstrip("/")
            if fnmatch.fnmatch(name, pat_clean) or fnmatch.fnmatch(rel_str, pat_clean):
                return True
            if fnmatch.fnmatch(rel_str, f"*/{pat_clean}") or fnmatch.fnmatch(rel_str, f"{pat_clean}/*"):
                return True

        return False

