"""Search tools for Code68 with ripgrep integration and pure Python fallback."""

from __future__ import annotations

import ast
import fnmatch
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from code68.security.sandbox import resolve_safe_path


class SearchTools:
    """Implements file search and code symbol lookup."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.has_ripgrep = shutil.which("rg") is not None

    def search_files(
        self,
        query: str,
        path: str = ".",
        case_sensitive: bool = False,
        max_results: int = 50,
    ) -> str:
        """Search for string or regex pattern across workspace files."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            if not target.exists():
                return f"Error: Path '{path}' does not exist."

            if self.has_ripgrep:
                return self._search_ripgrep(query, target, case_sensitive, max_results)
            else:
                return self._search_python(query, target, case_sensitive, max_results)
        except Exception as e:
            return f"Error searching files: {e}"

    def _search_ripgrep(
        self, query: str, target: Path, case_sensitive: bool, max_results: int
    ) -> str:
        cmd = [
            "rg",
            "--line-number",
            "--color=never",
            "--max-count",
            str(max_results),
            "--glob",
            "!.git/*",
            "--glob",
            "!.code68/*",
            "--glob",
            "!.venv/*",
            "--glob",
            "!__pycache__/*",
        ]
        if not case_sensitive:
            cmd.append("-i")
        cmd.extend(["--", query, str(target)])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            output = res.stdout.strip()
            if not output:
                return f"No matches found for pattern '{query}'."

            # Make paths relative to workspace
            lines = output.splitlines()[:max_results]
            formatted = []
            for line in lines:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    file_path = Path(parts[0])
                    try:
                        rel = file_path.relative_to(self.workspace_root)
                    except ValueError:
                        rel = file_path
                    formatted.append(f"{rel}:{parts[1]}: {parts[2]}")
                else:
                    formatted.append(line)

            count = len(formatted)
            return f"Found {count} match(es) for '{query}':\n" + "\n".join(formatted)
        except Exception:
            # Fallback to python search if ripgrep fails
            return self._search_python(query, target, case_sensitive, max_results)

    def _search_python(
        self, query: str, target: Path, case_sensitive: bool, max_results: int
    ) -> str:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error:
            pattern = re.compile(re.escape(query), flags)

        results = []
        ignored_dirs = {".git", ".code68", ".venv", "__pycache__", "node_modules", ".pytest_cache"}

        if target.is_file():
            files_to_check = [target]
        else:
            files_to_check = []
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for f in files:
                    files_to_check.append(Path(root) / f)

        for fpath in files_to_check:
            if len(results) >= max_results:
                break
            try:
                # Skip large files (>2MB)
                if fpath.stat().st_size > 2 * 1024 * 1024:
                    continue
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        if pattern.search(line):
                            rel = fpath.relative_to(self.workspace_root)
                            results.append(f"{rel}:{line_no}: {line.strip()}")
                            if len(results) >= max_results:
                                break
            except Exception:
                continue

        if not results:
            return f"No matches found for pattern '{query}'."

        count = len(results)
        return f"Found {count} match(es) for '{query}':\n" + "\n".join(results)

    def find_files(self, pattern: str, path: str = ".") -> str:
        """Find files by glob pattern (e.g. '*.py', '*test*') in the workspace."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            matches = []
            ignored_dirs = {".git", ".code68", ".venv", "__pycache__", "node_modules", ".pytest_cache"}

            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for f in files:
                    if fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(f.lower(), pattern.lower()):
                        rel = (Path(root) / f).relative_to(self.workspace_root)
                        matches.append(str(rel))

            if not matches:
                return f"No files found matching pattern '{pattern}'."

            matches.sort()
            return f"Found {len(matches)} file(s) matching '{pattern}':\n" + "\n".join(matches)
        except Exception as e:
            return f"Error finding files: {e}"

    def search_symbols(self, name: str, path: str = ".") -> str:
        """Search Python classes and functions matching a symbol name."""
        try:
            target = resolve_safe_path(path, self.workspace_root)
            symbols = []
            ignored_dirs = {".git", ".code68", ".venv", "__pycache__", "node_modules"}

            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for f in files:
                    if f.endswith(".py"):
                        fpath = Path(root) / f
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as py_file:
                                tree = ast.parse(py_file.read(), filename=str(fpath))
                            rel = fpath.relative_to(self.workspace_root)
                            for node in ast.walk(tree):
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                    if name.lower() in node.name.lower():
                                        kind = "class" if isinstance(node, ast.ClassDef) else "def"
                                        symbols.append(f"{rel}:{node.lineno}: [{kind}] {node.name}")
                        except Exception:
                            continue

            if not symbols:
                return f"No symbols found matching '{name}'."

            return f"Found {len(symbols)} symbol(s) matching '{name}':\n" + "\n".join(symbols)
        except Exception as e:
            return f"Error searching symbols: {e}"
