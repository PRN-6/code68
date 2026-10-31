"""Abstract base interface for LLM providers in Code68."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from pydantic import BaseModel
from code68.llm.models import Message


class ProviderCapabilities(BaseModel):
    """Capabilities exposed by a model provider."""

    supports_tools: bool = True
    supports_streaming: bool = True
    context_window: int = 32768


class LLMError(Exception):
    """Base exception for LLM operations."""


class LLMConnectionError(LLMError):
    """Network connection failure."""


class LLMAuthError(LLMError):
    """Authentication or authorization failure."""


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""


class LLMTimeoutError(LLMError):
    """Request timeout."""


class BaseLLMProvider(ABC):
    """Abstract interface for LLM backends."""

    @abstractmethod
    async def chat_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Message:
        """Send chat completion request, optionally streaming tokens via on_token callback."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the inference server."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        pass

