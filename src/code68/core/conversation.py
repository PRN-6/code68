"""Conversation management for Code68."""

from __future__ import annotations

from typing import List, Optional

from code68.llm.models import Message, Role, ToolCall
from code68.storage.history import ConversationHistory


class Conversation:
    """Represents an active conversation thread."""

    def __init__(self, system_prompt: str, token_limit: int = 32768) -> None:
        self.history = ConversationHistory(token_limit=token_limit)
        self.history.add_message(Message(role=Role.SYSTEM, content=system_prompt))

    def add_user_message(self, content: str) -> Message:
        """Add a user message."""
        msg = Message(role=Role.USER, content=content)
        self.history.add_message(msg)
        return msg

    def add_assistant_message(
        self, content: Optional[str] = None, tool_calls: Optional[List[ToolCall]] = None
    ) -> Message:
        """Add an assistant response message."""
        msg = Message(role=Role.ASSISTANT, content=content, tool_calls=tool_calls)
        self.history.add_message(msg)
        return msg

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str) -> Message:
        """Add a tool execution result message."""
        msg = Message(
            role=Role.TOOL,
            name=tool_name,
            tool_call_id=tool_call_id,
            content=result,
        )
        self.history.add_message(msg)
        return msg

    def get_messages(self) -> List[Message]:
        """Return all messages."""
        return self.history.get_messages()

    def clear(self) -> None:
        """Reset conversation."""
        self.history.clear()

    def compact(self) -> int:
        """Compact conversation history."""
        return self.history.compact()

