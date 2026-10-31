"""Context retrieval, tree generation, and token budgeting."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional
from code68.indexing.ignore import IgnoreFilter


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~4 characters per token)."""
    return max(1, len(text) // 4)


class ContextRetriever:
    """Builds project structural view and identifies task-relevant files."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.ignore_filter = IgnoreFilter(self.workspace_root)

    def generate_project_tree(self, max_depth: int = 3, max_entries: int = 120) -> str:
        """Generate a concise visual ASCII tree of the workspace."""
        lines = [f"{self.workspace_root.name}/"]
        count = 0

        def _walk_dir(current_dir: Path, prefix: str, current_depth: int) -> None:
            nonlocal count
            if current_depth > max_depth or count >= max_entries:
                return

            try:
                entries = sorted(
                    [
                        e
                        for e in current_dir.iterdir()
                        if not self.ignore_filter.is_ignored(e)
                    ],
                    key=lambda x: (not x.is_dir(), x.name.lower()),
                )
            except Exception:
                return

            for i, entry in enumerate(entries):
                if count >= max_entries:
                    lines.append(f"{prefix}... (truncated after {max_entries} entries)")
                    break

                count += 1
                is_last = i == (len(entries) - 1)
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    _walk_dir(entry, prefix + sub_prefix, current_depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

        _walk_dir(self.workspace_root, "", 1)
        return "\n".join(lines)

    def find_relevant_files(self, prompt: str, top_k: int = 5) -> List[Path]:
        """Find candidate files relevant to the prompt keywords."""
        keywords = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_\-\.]{2,}\b", prompt.lower()))
        candidates = []

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if not self.ignore_filter.is_ignored(Path(root) / d)]
            for file_name in files:
                fpath = Path(root) / file_name
                if self.ignore_filter.is_ignored(fpath):
                    continue

                score = 0
                f_lower = file_name.lower()
                rel_str = str(fpath.relative_to(self.workspace_root)).lower()

                for kw in keywords:
                    if kw in f_lower:
                        score += 5
                    elif kw in rel_str:
                        score += 2

                if score > 0:
                    candidates.append((score, fpath))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates[:top_k]]

