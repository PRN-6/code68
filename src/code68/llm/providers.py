"""Concrete LLM provider implementations for Code68."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional
import httpx
from code68.llm.base import (
    BaseLLMProvider,
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    ProviderCapabilities,
)
from code68.llm.models import Message, Role, ToolCall, FunctionCall
from code68.llm.streaming import StreamAccumulator

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI-compatible inference provider (supports Kaggle vLLM, FastAPI, Ollama, OpenRouter)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_streaming=True,
            context_window=32768,
        )

    async def health_check(self) -> Dict[str, Any]:
        """Check if remote inference endpoint is reachable and healthy."""
        url = f"{self.base_url}/models"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id") for m in data.get("data", [])] if "data" in data else []
                    return {
                        "status": "connected",
                        "available_models": models,
                        "selected_model": self.model,
                        "base_url": self.base_url,
                    }
                elif resp.status_code == 401 or resp.status_code == 403:
                    raise LLMAuthError(f"Authentication failed: HTTP {resp.status_code}")
                else:
                    return {
                        "status": "warning",
                        "code": resp.status_code,
                        "message": f"Server responded with HTTP {resp.status_code}",
                        "base_url": self.base_url,
                    }
            except (httpx.ConnectError, httpx.NetworkError) as e:
                raise LLMConnectionError(f"Could not connect to {self.base_url}: {e}")
            except httpx.TimeoutException as e:
                raise LLMTimeoutError(f"Connection timed out to {self.base_url}: {e}")

    async def chat_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Message:
        """Call chat completions with streaming and retry logic."""
        endpoint = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_api_dict() for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._execute_streaming_request(endpoint, payload, on_token)
            except (LLMConnectionError, LLMTimeoutError, LLMRateLimitError) as e:
                last_error = e
                if attempt == self.max_retries:
                    raise
                backoff = 2**attempt * 0.5
                logger.warning("Attempt %d failed: %s. Retrying in %.1fs...", attempt, e, backoff)
                await asyncio.sleep(backoff)
            except Exception as e:
                raise LLMError(f"Chat completion failed: {e}") from e

        if last_error:
            raise last_error
        raise LLMError("Unknown error during chat completion")

    async def _execute_streaming_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Message:
        accumulator = StreamAccumulator(on_token=on_token)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST", endpoint, headers=self._headers(), json=payload
                ) as response:
                    if response.status_code == 401 or response.status_code == 403:
                        body = await response.aread()
                        raise LLMAuthError(f"Authentication failed: {body.decode('utf-8', errors='ignore')}")
                    elif response.status_code == 429:
                        raise LLMRateLimitError("Rate limit reached on inference server")
                    elif response.status_code != 200:
                        body = await response.aread()
                        raise LLMError(
                            f"HTTP {response.status_code} from {endpoint}: {body.decode('utf-8', errors='ignore')}"
                        )

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                accumulator.process_chunk_dict(chunk_json)
                            except json.JSONDecodeError:
                                continue

                return accumulator.get_message()
            except (httpx.ConnectError, httpx.NetworkError) as e:
                raise LLMConnectionError(f"Network error communicating with {self.base_url}: {e}")
            except httpx.TimeoutException as e:
                raise LLMTimeoutError(f"Request timed out after {self.timeout}s: {e}")


class MockLLMProvider(BaseLLMProvider):
    """In-memory mock provider for unit testing without network dependencies."""

    def __init__(self, responses: Optional[List[Message]] = None) -> None:
        self.responses: List[Message] = responses or []
        self.call_history: List[List[Message]] = []

    def queue_response(self, message: Message) -> None:
        self.responses.append(message)

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_tools=True, supports_streaming=True)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "connected",
            "available_models": ["mock-qwen2.5-coder"],
            "selected_model": "mock-qwen2.5-coder",
            "base_url": "mock://localhost",
        }

    async def chat_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Message:
        self.call_history.append(messages)
        if not self.responses:
            default_resp = Message(
                role=Role.ASSISTANT,
                content="Mock response: No predefined response found in queue.",
            )
            if on_token and default_resp.content:
                on_token(default_resp.content)
            return default_resp

        resp = self.responses.pop(0)
        if on_token and resp.content:
            # Simulate streaming by chunking the text
            words = resp.content.split(" ")
            for i, word in enumerate(words):
                on_token(word + (" " if i < len(words) - 1 else ""))
        return resp
