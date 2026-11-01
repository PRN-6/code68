"""Tool registry and dispatcher for Code68."""

from __future__ import annotations

import datetime
import inspect
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from code68.security.permissions import ActionCategory, SecurityManager
from code68.security.validation import mask_secrets, truncate_output
from code68.tools.schemas import ToolDefinition

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution encounters an error."""


class ToolRegistry:
    """Central registry and executor for agent tools."""

    def __init__(
        self,
        workspace_root: Path,
        security_manager: SecurityManager,
        max_output_chars: int = 16000,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.security_manager = security_manager
        self.max_output_chars = max_output_chars
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        category: ActionCategory,
        parameters: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """Register a new tool."""
        defn = ToolDefinition(
            name=name,
            description=description,
            category=category,
            parameters=parameters,
        )
        self._tools[name] = defn
        self._handlers[name] = handler

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    def get_tool_names(self) -> List[str]:
        """Return list of all registered tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions in OpenAI format."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool with argument validation, permission checks, and audit logging."""
        if name not in self._tools:
            return f"Error: Unknown tool '{name}'."

        tool_defn = self._tools[name]
        handler = self._handlers[name]

        # 1. Permission check
        allowed = self.security_manager.check_permission(
            category=tool_defn.category,
            description=f"Tool: {name}({', '.join(f'{k}={v!r}' for k, v in arguments.items())})",
            details={"tool": name, "arguments": arguments},
        )
        if not allowed:
            self._log_audit(name, arguments, success=False, error="Permission denied by user or policy")
            return f"Permission denied: Execution of tool '{name}' was not approved."

        # 2. Execute handler
        try:
            if inspect.iscoroutinefunction(handler):
                result = await handler(**arguments)
            else:
                result = handler(**arguments)

            result_str = str(result)
            sanitized = mask_secrets(result_str)
            final_output = truncate_output(sanitized, self.max_output_chars)

            self._log_audit(name, arguments, success=True, output=final_output)
            return final_output
        except Exception as e:
            error_msg = f"Error executing tool '{name}': {type(e).__name__}: {str(e)}"
            self._log_audit(name, arguments, success=False, error=error_msg)
            return error_msg

    def _log_audit(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        success: bool,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append record to workspace audit log."""
        try:
            audit_dir = self.workspace_root / ".code68"
            audit_dir.mkdir(parents=True, exist_ok=True)
            audit_file = audit_dir / "audit.log"

            entry = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "tool": tool_name,
                "arguments": arguments,
                "success": success,
                "error": error,
                "output_preview": output[:200] if output else None,
            }
            with open(audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Failed to write to audit log: %s", e)

