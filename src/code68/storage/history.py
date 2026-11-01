"""Conversation history and context compaction."""

from __future__ import annotations

from typing import List, Optional

from code68.indexing.retrieval import estimate_tokens
from code68.llm.models import Message, Role


class ConversationHistory:
    """Manages chat messages with token budgeting and history compaction."""

    def __init__(self, token_limit: int = 32768) -> None:
        self.token_limit = token_limit
        self.messages: List[Message] = []

    def add_message(self, message: Message) -> None:
        """Append message to history and auto-compact if exceeding token limit."""
        self.messages.append(message)
        if self.total_estimated_tokens() > self.token_limit:
            self.compact()

    def get_messages(self) -> List[Message]:
        """Return list of messages."""
        return list(self.messages)

    def clear(self) -> None:
        """Clear all messages except system message if present."""
        if self.messages and self.messages[0].role == Role.SYSTEM:
            self.messages = [self.messages[0]]
        else:
            self.messages = []

    def total_estimated_tokens(self) -> int:
        """Estimate token total for all stored messages."""
        total = 0
        for m in self.messages:
            if m.content:
                total += estimate_tokens(m.content)
            if m.tool_calls:
                for tc in m.tool_calls:
                    total += estimate_tokens(tc.function.arguments) + 10
        return total

    def compact(self, max_retained_messages: int = 10) -> int:
        """Compact history by summarizing older messages when token limit is approached."""
        if len(self.messages) <= max_retained_messages + 1:
            return 0

        # Preserve system message
        system_msg: Optional[Message] = None
        start_idx = 0
        if self.messages and self.messages[0].role == Role.SYSTEM:
            system_msg = self.messages[0]
            start_idx = 1

        older_messages = self.messages[start_idx:-max_retained_messages]
        recent_messages = self.messages[-max_retained_messages:]

        # Create compact summary of older messages
        summary_points = []
        for m in older_messages:
            if m.role == Role.USER and m.content:
                summary_points.append(f"User asked: {m.content[:150]}")
            elif m.role == Role.ASSISTANT and m.content:
                summary_points.append(f"Agent answered: {m.content[:150]}")
            elif m.role == Role.TOOL and m.content:
                summary_points.append(f"Tool executed ({m.name}): {m.content[:80]}")

        compacted_note = Message(
            role=Role.SYSTEM,
            content="[Previous conversation summary]:\n" + "\n".join(summary_points),
        )

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.append(compacted_note)
        new_messages.extend(recent_messages)

        pruned_count = len(older_messages)
        self.messages = new_messages
        return pruned_count

