"""Tests for LLM client, streaming, and provider abstraction."""

import pytest
from code68.llm.client import get_llm_provider
from code68.llm.models import FunctionCall, Message, Role, ToolCall
from code68.llm.providers import MockLLMProvider, OpenAICompatibleProvider
from code68.llm.streaming import StreamAccumulator
from code68.storage.config import Config


def test_message_api_dict_conversion():
    tc = ToolCall(
        id="call_123",
        type="function",
        function=FunctionCall(name="read_file", arguments='{"path": "test.py"}'),
    )
    msg = Message(role=Role.ASSISTANT, content="Checking file", tool_calls=[tc])
    api_dict = msg.to_api_dict()

    assert api_dict["role"] == "assistant"
    assert api_dict["content"] == "Checking file"
    assert len(api_dict["tool_calls"]) == 1
    assert api_dict["tool_calls"][0]["function"]["name"] == "read_file"


def test_streaming_accumulator():
    accum = StreamAccumulator()

    # Simulate chunks arriving
    chunk1 = {
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": "Hello "},
                "finish_reason": None,
            }
        ]
    }
    chunk2 = {
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_abc",
                            "function": {"name": "read_", "arguments": '{"path": '},
                        }
                    ]
                },
                "finish_reason": None,
            }
        ]
    }
    chunk3 = {
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"name": "file", "arguments": '"main.py"}'},
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    accum.process_chunk_dict(chunk1)
    accum.process_chunk_dict(chunk2)
    accum.process_chunk_dict(chunk3)

    final_msg = accum.get_message()
    assert final_msg.role == Role.ASSISTANT
    assert final_msg.content == "Hello "
    assert final_msg.tool_calls is not None
    assert len(final_msg.tool_calls) == 1
    assert final_msg.tool_calls[0].id == "call_abc"
    assert final_msg.tool_calls[0].function.name == "read_file"
    assert final_msg.tool_calls[0].parse_arguments() == {"path": "main.py"}


@pytest.mark.asyncio
async def test_mock_llm_provider():
    mock = MockLLMProvider()
    health = await mock.health_check()
    assert health["status"] == "connected"

    # Queue response
    expected = Message(role=Role.ASSISTANT, content="Completed successfully")
    mock.queue_response(expected)

    tokens = []
    resp = await mock.chat_complete(
        messages=[Message(role=Role.USER, content="Do something")],
        on_token=lambda t: tokens.append(t),
    )
    assert resp.content == "Completed successfully"
    assert "".join(tokens) == "Completed successfully"


def test_provider_factory():
    cfg = Config(provider="openai-compatible", base_url="http://test:8000/v1")
    prov = get_llm_provider(cfg)
    assert isinstance(prov, OpenAICompatibleProvider)
    assert prov.base_url == "http://test:8000/v1"

