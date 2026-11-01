"""Streaming parser and accumulator for LLM responses."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from code68.llm.models import FunctionCall, Message, Role, ToolCall


class StreamAccumulator:
    """Accumulates SSE chunks into complete text and tool calls."""

    def __init__(self, on_token: Optional[Callable[[str], None]] = None) -> None:
        self.on_token = on_token
        self.role: Role = Role.ASSISTANT
        self.content_parts: List[str] = []
        # Key: tool index, Value: dict with id, name, args parts
        self._tool_call_builders: Dict[int, Dict[str, Any]] = {}
        self.finish_reason: Optional[str] = None

    def process_chunk_dict(self, data: Dict[str, Any]) -> None:
        """Process a raw parsed JSON object from SSE."""
        choices = data.get("choices", [])
        if not choices:
            return

        choice = choices[0]
        self.finish_reason = choice.get("finish_reason") or self.finish_reason
        delta = choice.get("delta", {})

        # Process role
        if delta.get("role"):
            try:
                self.role = Role(delta["role"])
            except ValueError:
                self.role = Role.ASSISTANT

        # Process content
        content = delta.get("content")
        if content:
            self.content_parts.append(content)
            if self.on_token:
                self.on_token(content)

        # Process tool calls
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                idx = tc.get("index", 0)
                if idx not in self._tool_call_builders:
                    self._tool_call_builders[idx] = {
                        "id": tc.get("id", f"call_{idx}"),
                        "name": "",
                        "arguments_parts": [],
                    }

                builder = self._tool_call_builders[idx]
                if tc.get("id"):
                    builder["id"] = tc["id"]

                func = tc.get("function", {})
                if func.get("name"):
                    builder["name"] += func["name"]
                if func.get("arguments"):
                    builder["arguments_parts"].append(func["arguments"])

    def get_message(self) -> Message:
        """Assemble and return the final Message object."""
        full_content = "".join(self.content_parts) if self.content_parts else None

        built_tool_calls: Optional[List[ToolCall]] = None
        if self._tool_call_builders:
            built_tool_calls = []
            for idx in sorted(self._tool_call_builders.keys()):
                b = self._tool_call_builders[idx]
                args_str = "".join(b["arguments_parts"])
                built_tool_calls.append(
                    ToolCall(
                        id=b["id"] or f"call_{idx}",
                        type="function",
                        function=FunctionCall(
                            name=b["name"],
                            arguments=args_str,
                        ),
                    )
                )

        return Message(
            role=self.role,
            content=full_content,
            tool_calls=built_tool_calls if built_tool_calls else None,
        )

