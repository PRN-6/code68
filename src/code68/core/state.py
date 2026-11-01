"""Agent state and loop detection."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from pydantic import BaseModel


class ToolCallRecord(BaseModel):
    """Record of a tool invocation."""

    tool_name: str
    arguments_hash: str
    success: bool
    iteration: int


class LoopDetector:
    """Detects infinite loops and repetitive failed tool invocations."""

    def __init__(self, max_repeated_calls: int = 3) -> None:
        self.max_repeated_calls = max_repeated_calls
        self.history: List[ToolCallRecord] = []

    def record_call(self, tool_name: str, arguments: Dict[str, Any], success: bool, iteration: int) -> None:
        """Record a tool invocation."""
        args_str = str(sorted(arguments.items()))
        args_hash = hashlib.md5(args_str.encode()).hexdigest()
        self.history.append(
            ToolCallRecord(
                tool_name=tool_name,
                arguments_hash=args_hash,
                success=success,
                iteration=iteration,
            )
        )

    def is_looping(self) -> tuple[bool, str]:
        """Check if recent history indicates an infinite loop or repeated failures."""
        if len(self.history) < self.max_repeated_calls:
            return False, ""

        last = self.history[-1]
        consecutive_identical = 0
        for item in reversed(self.history):
            if item.tool_name == last.tool_name and item.arguments_hash == last.arguments_hash:
                consecutive_identical += 1
            else:
                break

        if consecutive_identical >= self.max_repeated_calls:
            return True, f"Detected {consecutive_identical} identical consecutive calls to '{last.tool_name}'"

        return False, ""

