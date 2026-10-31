"""End-to-end tests for Code68 Agent loop, tool execution, and session management."""

import json
import pytest
from code68.core.agent import Code68Agent
from code68.core.agent_loop import AgentLoop
from code68.core.conversation import Conversation
from code68.llm.models import FunctionCall, Message, Role, ToolCall
from code68.llm.providers import MockLLMProvider
from code68.storage.config import Config, PermissionLevel
from code68.storage.sessions import SessionManager


@pytest.mark.asyncio
async def test_agent_full_tool_execution_flow(temp_workspace):
    # Setup mock LLM responses
    mock_llm = MockLLMProvider()

    # Turn 1: LLM decides to call read_file
    tc1 = ToolCall(
        id="call_read_1",
        type="function",
        function=FunctionCall(
            name="read_file",
            arguments=json.dumps({"path": "sample.py"}),
        ),
    )
    msg1 = Message(role=Role.ASSISTANT, content="I will inspect sample.py", tool_calls=[tc1])
    mock_llm.queue_response(msg1)

    # Turn 2: LLM receives file contents, decides to call edit_file
    tc2 = ToolCall(
        id="call_edit_2",
        type="function",
        function=FunctionCall(
            name="edit_file",
            arguments=json.dumps(
                {
                    "path": "sample.py",
                    "old_text": "return 'world'",
                    "new_text": "return 'code68-fixed'",
                }
            ),
        ),
    )
    msg2 = Message(role=Role.ASSISTANT, content="Fixing the return value", tool_calls=[tc2])
    mock_llm.queue_response(msg2)

    # Turn 3: LLM final response after successful edit
    msg3 = Message(
        role=Role.ASSISTANT,
        content="I have analyzed sample.py and replaced 'world' with 'code68-fixed'.",
    )
    mock_llm.queue_response(msg3)

    # Configure agent with full auto permissions for test
    cfg = Config(permission_level=PermissionLevel.FULL_AUTO)
    agent = Code68Agent(
        workspace_root=temp_workspace,
        config=cfg,
        mock_provider=mock_llm,
    )

    result = await agent.execute("Analyze sample.py and update it", stream=False)

    assert "code68-fixed" in result
    # Verify the local file was actually modified on disk!
    content = (temp_workspace / "sample.py").read_text(encoding="utf-8")
    assert "return 'code68-fixed'" in content


@pytest.mark.asyncio
async def test_agent_loop_detection(temp_workspace):
    mock_llm = MockLLMProvider()

    # Queue 4 identical read_file calls to trigger LoopDetector
    tc = ToolCall(
        id="call_repeat",
        type="function",
        function=FunctionCall(name="read_file", arguments=json.dumps({"path": "sample.py"})),
    )
    for _ in range(4):
        mock_llm.queue_response(Message(role=Role.ASSISTANT, tool_calls=[tc]))

    cfg = Config(permission_level=PermissionLevel.FULL_AUTO)
    agent = Code68Agent(
        workspace_root=temp_workspace,
        config=cfg,
        mock_provider=mock_llm,
    )

    result = await agent.execute("Check sample", stream=False)
    assert "Agent loop terminated early: Detected" in result


def test_conversation_compaction():
    conv = Conversation(system_prompt="You are Code68", token_limit=1000)
    for i in range(25):
        conv.add_user_message(f"User message {i}")
        conv.add_assistant_message(f"Assistant answer {i}")

    initial_len = len(conv.get_messages())
    assert initial_len > 40

    pruned = conv.compact()
    assert pruned > 0
    compacted_len = len(conv.get_messages())
    assert compacted_len < initial_len


def test_session_manager(temp_workspace):
    sm = SessionManager(temp_workspace)
    msgs = [
        Message(role=Role.USER, content="Hello"),
        Message(role=Role.ASSISTANT, content="Hi there"),
    ]

    session_id = "test_sess"
    path = sm.save_session(session_id, msgs)
    assert path.is_file()

    loaded = sm.load_session(session_id)
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].content == "Hello"

    sessions = sm.list_sessions()
    assert len(sessions) >= 1
    assert sessions[0]["session_id"] == "test_sess"

