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
                return f"Execution blocked: Command flagged as dangerous ({desc}): '{command}'"

            def _execute_sync():
                try:
                    import shlex
                    try:
                        args = shlex.split(command, posix=False)
                        res = subprocess.run(
                            args,
                            cwd=str(target_cwd),
                            capture_output=True,
                            text=True,
                            timeout=float(timeout),
                        )
                    except Exception:
                        res = subprocess.run(
                            command,
                            shell=True,
                            cwd=str(target_cwd),
                            capture_output=True,
                            text=True,
                            timeout=float(timeout),
                        )
                    return res.returncode, res.stdout.strip(), res.stderr.strip(), None
                except subprocess.TimeoutExpired:
                    return -1, "", "", f"Error: Command timed out after {timeout} seconds: '{command}'"
                except Exception as ex:
                    return -1, "", "", f"Error running command '{command}': {ex}"

            exit_code, stdout_str, stderr_str, err = await asyncio.to_thread(_execute_sync)
            if err:
                return err

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
