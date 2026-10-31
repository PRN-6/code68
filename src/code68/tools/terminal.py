"""Terminal execution tools for Code68."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional
from code68.security.sandbox import resolve_safe_path
from code68.security.validation import is_destructive_command


class TerminalTools:
    """Safely executes terminal commands with timeouts and output capture."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    async def run_command(
        self,
        command: str,
        cwd: str = ".",
        timeout: int = 60,
    ) -> str:
        """Execute a shell command within the workspace and capture output."""
        try:
            target_cwd = resolve_safe_path(cwd, self.workspace_root)
            if not target_cwd.is_dir():
                return f"Error: Working directory '{cwd}' does not exist or is not a directory."

            is_destr, desc = is_destructive_command(command)
            if is_destr:
                # Still returned to agent as a security flag if not overridden by approval
                return f"Execution blocked: Command flagged as dangerous ({desc}): '{command}'"

            # Execute subprocess asynchronously
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(target_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(), timeout=float(timeout)
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                return f"Error: Command timed out after {timeout} seconds: '{command}'"

            stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_data.decode("utf-8", errors="replace").strip()
            exit_code = process.returncode

            output_parts = [f"Command: {command}", f"Exit Code: {exit_code}"]
            if stdout_str:
                output_parts.append(f"STDOUT:\n{stdout_str}")
            if stderr_str:
                output_parts.append(f"STDERR:\n{stderr_str}")
            if not stdout_str and not stderr_str:
                output_parts.append("(Command produced no output)")

            return "\n\n".join(output_parts)
        except Exception as e:
            return f"Error running command '{command}': {e}"
