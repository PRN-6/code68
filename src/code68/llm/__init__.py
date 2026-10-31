"""LLM package for Code68."""

from code68.llm.base import (
    BaseLLMProvider,
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    ProviderCapabilities,
)
from code68.llm.client import get_llm_provider
from code68.llm.models import (
    ChatCompletionResponse,
    FunctionCall,
    Message,
    Role,
    StreamChunk,
    ToolCall,
    UsageInfo,
)
from code68.llm.providers import MockLLMProvider, OpenAICompatibleProvider

__all__ = [
    "BaseLLMProvider",
    "ChatCompletionResponse",
    "FunctionCall",
    "LLMAuthError",
    "LLMConnectionError",
    "LLMError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "Message",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "ProviderCapabilities",
    "Role",
    "StreamChunk",
    "ToolCall",
    "UsageInfo",
    "get_llm_provider",
]

