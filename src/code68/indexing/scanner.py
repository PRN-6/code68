"""Codebase scanner and project architecture analyzer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field
from code68.indexing.ignore import IgnoreFilter


class ProjectMetadata(BaseModel):
    """Metadata discovered from codebase scan."""

    project_type: str = "Unknown"
    detected_languages: List[str] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    config_files: List[str] = Field(default_factory=list)
    doc_files: List[str] = Field(default_factory=list)
    total_files: int = 0
    language_breakdown: Dict[str, int] = Field(default_factory=dict)


EXTENSION_MAP = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript/React",
    ".js": "JavaScript",
    ".jsx": "JavaScript/React",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".md": "Markdown",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
}

ENTRY_CANDIDATES = [
    "main.py",
    "app.py",
    "cli.py",
    "index.ts",
    "index.js",
    "src/main.py",
    "src/cli.py",
    "src/index.ts",
    "src/index.js",
    "src/main.rs",
    "main.go",
]

CONFIG_CANDIDATES = [
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "package.json",
    "tsconfig.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Dockerfile",
    "docker-compose.yml",
]


class CodebaseScanner:
    """Scans and analyzes directory structure and project properties."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.ignore_filter = IgnoreFilter(self.workspace_root)

    def scan(self) -> ProjectMetadata:
        """Perform scan on the workspace."""
        meta = ProjectMetadata()
        ext_counts: Dict[str, int] = {}
        scanned_files = 0

        for root, dirs, files in os.walk(self.workspace_root):
            # Exclude ignored directories in-place
            dirs[:] = [
                d for d in dirs if not self.ignore_filter.is_ignored(Path(root) / d)
            ]

            for file_name in files:
                fpath = Path(root) / file_name
                if self.ignore_filter.is_ignored(fpath):
                    continue

                scanned_files += 1
                ext = fpath.suffix.lower()
                lang = EXTENSION_MAP.get(ext)
                if lang:
                    ext_counts[lang] = ext_counts.get(lang, 0) + 1

                rel_str = str(fpath.relative_to(self.workspace_root)).replace("\\", "/")

                # Detect entry points
                if rel_str in ENTRY_CANDIDATES or file_name in ENTRY_CANDIDATES:
                    if rel_str not in meta.entry_points:
                        meta.entry_points.append(rel_str)

                # Detect config files
                if file_name in CONFIG_CANDIDATES:
                    if rel_str not in meta.config_files:
                        meta.config_files.append(rel_str)

                # Detect docs
                if file_name.lower().startswith("readme") or file_name.lower().startswith("contributing"):
                    if rel_str not in meta.doc_files:
                        meta.doc_files.append(rel_str)

        meta.total_files = scanned_files
        meta.language_breakdown = ext_counts
        meta.detected_languages = sorted(ext_counts.keys(), key=lambda l: ext_counts[l], reverse=True)

        # Infer project type
        if "Python" in ext_counts and (
            ext_counts["Python"] >= max(ext_counts.values(), default=0)
            or (self.workspace_root / "pyproject.toml").exists()
        ):
            meta.project_type = "Python Application/Package"
        elif "TypeScript" in ext_counts or "TypeScript/React" in ext_counts:
            meta.project_type = "TypeScript Project"
        elif "JavaScript" in ext_counts or "JavaScript/React" in ext_counts:
            meta.project_type = "JavaScript Project"
        elif "Rust" in ext_counts:
            meta.project_type = "Rust Project"
        elif "Go" in ext_counts:
            meta.project_type = "Go Project"
        elif meta.detected_languages:
            meta.project_type = f"{meta.detected_languages[0]} Project"
        else:
            meta.project_type = "General Project"

        return meta
