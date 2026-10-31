"""LLM Client factory and wrapper for Code68."""

from __future__ import annotations

from typing import Optional
from code68.llm.base import BaseLLMProvider
from code68.llm.providers import MockLLMProvider, OpenAICompatibleProvider
from code68.storage.config import Config


def get_llm_provider(config: Config, mock_provider: Optional[MockLLMProvider] = None) -> BaseLLMProvider:
    """Create and return an LLM provider based on config."""
    if mock_provider is not None:
        return mock_provider

    provider_name = config.provider.lower().strip()
    if provider_name in ("openai-compatible", "kaggle", "vllm", "ollama", "openrouter", "custom"):
        return OpenAICompatibleProvider(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            timeout=config.timeout_seconds,
        )
    elif provider_name == "mock":
        return MockLLMProvider()
    else:
        # Default to OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            timeout=config.timeout_seconds,
        )
