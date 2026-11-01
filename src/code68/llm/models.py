"""LLM Data models for Code68."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Message author role."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FunctionCall(BaseModel):
    """Function call definition."""

    name: str
    arguments: str  # JSON formatted string


class ToolCall(BaseModel):
    """Tool invocation requested by the model."""

    id: str
    type: str = "function"
    function: FunctionCall

    def parse_arguments(self) -> Dict[str, Any]:
        """Safely parse function arguments as dictionary."""
        try:
            return json.loads(self.function.arguments)
        except Exception:
            return {}


class Message(BaseModel):
    """Chat message object."""

    role: Role
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

    def to_api_dict(self) -> Dict[str, Any]:
        """Convert to dict representation compatible with OpenAI-style completions API."""
        d: Dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            d["content"] = self.content
        if self.name is not None:
            d["name"] = self.name
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        return d


class UsageInfo(BaseModel):
    """Token usage details."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StreamDelta(BaseModel):
    """Streaming chunk delta."""

    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class StreamChoice(BaseModel):
    """Choice item in a streaming chunk."""

    index: int = 0
    delta: StreamDelta
    finish_reason: Optional[str] = None


class StreamChunk(BaseModel):
    """Streaming response chunk."""

    id: Optional[str] = None
    choices: List[StreamChoice] = Field(default_factory=list)


class ChatCompletionResponse(BaseModel):
    """Full chat completion response."""

    id: str
    model: str
    message: Message
    finish_reason: Optional[str] = None
    usage: Optional[UsageInfo] = None

