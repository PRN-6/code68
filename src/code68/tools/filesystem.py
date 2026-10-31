"""Filesystem tools for Code68."""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Optional
from code68.security.permissions import ActionCategory
from code68.security.sandbox import resolve_safe_path
from code68.security.validation import check_prompt_injection
from code68.tools.schemas import ToolParameter


class FilesystemTools:
    """Implements safe, workspace-bound filesystem manipulation tools."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def read_file(self, path: str, offset: int = 1, limit: int = 400) -> str:
        """Read lines from a file within the workspace."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            if not target.is_file():
                return f"Error: '{path}' does not exist or is not a file."

            # Read with utf-8 fallback to latin-1
            try:
                with open(target, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(target, "r", encoding="latin-1") as f:
                    lines = f.readlines()

            total_lines = len(lines)
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)

            selected_lines = lines[start_idx:end_idx]
            numbered = [f"{start_idx + i + 1:5d} | {line}" for i, line in enumerate(selected_lines)]
            content_snippet = "".join(numbered)

            injection_warning = check_prompt_injection(content_snippet)
            warning_header = f"[Warning: {injection_warning}]\n" if injection_warning else ""

            header = f"File: {target.relative_to(self.workspace_root)} ({total_lines} lines total, showing lines {start_idx+1}-{end_idx})\n"
            return warning_header + header + ("-" * 60) + "\n" + content_snippet
        except Exception as e:
            return f"Error reading file '{path}': {e}"

    def write_file(self, path: str, content: str) -> str:
        """Create or overwrite a file with given content."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            target.parent.mkdir(parents=True, exist_ok=True)

            with open(target, "w", encoding="utf-8") as f:
                f.write(content)

            lines_count = len(content.splitlines())
            return f"Successfully wrote {lines_count} lines to '{target.relative_to(self.workspace_root)}'."
        except Exception as e:
            return f"Error writing file '{path}': {e}"

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        """Replace exact old_text with new_text in a file and generate diff."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            if not target.is_file():
                return f"Error: '{path}' does not exist or is not a file."

            with open(target, "r", encoding="utf-8") as f:
                content = f.read()

            if old_text not in content:
                # Provide a helpful hint
                return (
                    f"Error: Target text not found in '{path}'. "
                    "Make sure you match the exact whitespace and indentation."
                )

            count = content.count(old_text)
            if count > 1:
                return (
                    f"Error: Target text occurs {count} times in '{path}'. "
                    "Please provide more surrounding context to disambiguate the target."
                )

            # Perform replacement
            updated_content = content.replace(old_text, new_text, 1)

            # Generate diff
            old_lines = content.splitlines(keepends=True)
            new_lines = updated_content.splitlines(keepends=True)
            rel_path = str(target.relative_to(self.workspace_root))
            diff_lines = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                )
            )
            diff_str = "".join(diff_lines)

            with open(target, "w", encoding="utf-8") as f:
                f.write(updated_content)

            return f"Successfully edited '{rel_path}'.\n\n```diff\n{diff_str}\n```"
        except Exception as e:
            return f"Error editing file '{path}': {e}"

    def list_directory(self, path: str = ".", recursive: bool = False, max_depth: int = 2) -> str:
        """List files and directories within a path."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            if not target.is_dir():
                return f"Error: '{path}' is not a directory."

            items = []
            rel_base = target.relative_to(self.workspace_root)

            if recursive:
                for root, dirs, files in os.walk(target):
                    # Skip common noisy directories
                    dirs[:] = [
                        d
                        for d in dirs
                        if d not in (".git", ".code68", ".venv", "__pycache__", "node_modules", ".pytest_cache")
                    ]
                    current_path = Path(root)
                    depth = len(current_path.relative_to(target).parts)
                    if depth > max_depth:
                        continue

                    for d in sorted(dirs):
                        p = (current_path / d).relative_to(self.workspace_root)
                        items.append(f"[DIR]  {p}")
                    for f in sorted(files):
                        p = (current_path / f).relative_to(self.workspace_root)
                        items.append(f"[FILE] {p}")
            else:
                for entry in sorted(target.iterdir()):
                    if entry.name in (".git", ".code68", ".venv", "__pycache__"):
                        continue
                    p = entry.relative_to(self.workspace_root)
                    if entry.is_dir():
                        items.append(f"[DIR]  {p}")
                    else:
                        size = entry.stat().st_size
                        items.append(f"[FILE] {p} ({size} bytes)")

            count = len(items)
            output = f"Directory '{rel_base}' ({count} items):\n" + "\n".join(items)
            return output
        except Exception as e:
            return f"Error listing directory '{path}': {e}"

    def create_directory(self, path: str) -> str:
        """Create a new directory within the workspace."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            target.mkdir(parents=True, exist_ok=True)
            return f"Successfully created directory '{target.relative_to(self.workspace_root)}'."
        except Exception as e:
            return f"Error creating directory '{path}': {e}"

    def delete_file(self, path: str) -> str:
        """Delete a file within the workspace."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            if not target.exists():
                return f"Error: '{path}' does not exist."
            if target.is_dir():
                return f"Error: '{path}' is a directory. delete_file only removes files."

            target.unlink()
            return f"Successfully deleted file '{target.relative_to(self.workspace_root)}'."
        except Exception as e:
            return f"Error deleting file '{path}': {e}"

