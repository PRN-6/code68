"""Context builder for workspace awareness."""

from __future__ import annotations

from pathlib import Path

from code68.indexing.retrieval import ContextRetriever
from code68.indexing.scanner import CodebaseScanner, ProjectMetadata
from code68.tools.git import GitTools


class ContextBuilder:
    """Constructs dynamic workspace context for the agent."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.scanner = CodebaseScanner(self.workspace_root)
        self.retriever = ContextRetriever(self.workspace_root)
        self.git = GitTools(self.workspace_root)

    def build_workspace_summary(self) -> str:
        """Analyze workspace and return high-level structural context."""
        meta: ProjectMetadata = self.scanner.scan()
        tree = self.retriever.generate_project_tree(max_depth=2, max_entries=50)

        lines = [
            f"Workspace Path: {self.workspace_root}",
            f"Project Type: {meta.project_type}",
            f"Detected Languages: {', '.join(meta.detected_languages) if meta.detected_languages else 'None'}",
            f"Total Files Scanned: {meta.total_files}",
        ]

        if meta.entry_points:
            lines.append(f"Entry Points: {', '.join(meta.entry_points)}")
        if meta.config_files:
            lines.append(f"Config Files: {', '.join(meta.config_files)}")
        if meta.doc_files:
            lines.append(f"Doc Files: {', '.join(meta.doc_files)}")

        # Git branch
        try:
            branch_info = self.git.git_branch()
            lines.append(branch_info)
        except Exception:
            pass

        lines.append("\nProject Directory Tree:\n" + tree)
        return "\n".join(lines)

