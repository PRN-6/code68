"""Testing and code analysis tools for Code68."""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Optional


class TestingTools:
    """Executes automated tests, linters, and type checkers."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    async def run_tests(self, test_path: Optional[str] = None, flags: str = "-v") -> str:
        """Run project tests using detected test runner (pytest, unittest, npm test)."""
        try:
            # 1. Detect Python pytest
            python_exe = sys.executable
            if (self.workspace_root / "pyproject.toml").exists() or any(
                self.workspace_root.glob("test*.py")
            ) or (self.workspace_root / "tests").exists():
                cmd = f'"{python_exe}" -m pytest'
                if test_path:
                    cmd += f" {test_path}"
                if flags:
                    cmd += f" {flags}"
                return await self._run_subproc(cmd)

            # 2. Detect Node.js
            if (self.workspace_root / "package.json").exists():
                return await self._run_subproc("npm test")

            # 3. Detect Rust
            if (self.workspace_root / "Cargo.toml").exists():
                return await self._run_subproc("cargo test")

            # Fallback to python unittest
            cmd = f'"{python_exe}" -m unittest discover'
            return await self._run_subproc(cmd)
        except Exception as e:
            return f"Error executing tests: {e}"

    async def run_linter(self, path: str = ".") -> str:
        """Run project linter (ruff, flake8, or eslint)."""
        try:
            python_exe = sys.executable
            # Try ruff
            cmd = f'"{python_exe}" -m ruff check {path}'
            result = await self._run_subproc(cmd)
            if "No module named ruff" not in result:
                return result

            # Try flake8
            cmd = f'"{python_exe}" -m flake8 {path}'
            return await self._run_subproc(cmd)
        except Exception as e:
            return f"Error running linter: {e}"

    async def run_type_checker(self, path: str = ".") -> str:
        """Run static type checker (mypy or tsc)."""
        try:
            python_exe = sys.executable
            cmd = f'"{python_exe}" -m mypy {path}'
            return await self._run_subproc(cmd)
        except Exception as e:
            return f"Error running type checker: {e}"

    async def _run_subproc(self, command: str, timeout: int = 120) -> str:
        def _exec():
            try:
                res = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=float(timeout),
                )
                return res.returncode, res.stdout.strip(), res.stderr.strip(), None
            except subprocess.TimeoutExpired:
                return -1, "", "", f"Execution timed out after {timeout} seconds: {command}"
            except Exception as e:
                return -1, "", "", f"Execution error: {e}"

        code, stdout_str, stderr_str, err = await asyncio.to_thread(_exec)
        if err:
            return err

        status_text = "PASSED" if code == 0 else f"FAILED (Exit Code: {code})"
        output = [f"Result: {status_text}", f"Command: {command}"]
        if stdout_str:
            output.append(f"STDOUT:\n{stdout_str}")
        if stderr_str:
            output.append(f"STDERR:\n{stderr_str}")

        return "\n\n".join(output)
