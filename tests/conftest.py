"""Pytest fixtures for Code68 test suite."""

import shutil
import uuid
from pathlib import Path
import git
import pytest
from code68.llm.models import Message, Role, ToolCall, FunctionCall
from code68.llm.providers import MockLLMProvider
from code68.security.permissions import SecurityManager
from code68.storage.config import Config, PermissionLevel
from code68.tools import build_default_tool_registry
from code68.tools.registry import ToolRegistry


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory inside workspace root for full sandbox write permissions."""
    base_tmp = Path(__file__).resolve().parent.parent / ".test_tmp"
    base_tmp.mkdir(parents=True, exist_ok=True)
    ws = base_tmp / f"test_{uuid.uuid4().hex[:8]}"
    ws.mkdir(parents=True, exist_ok=True)
    git.Repo.init(ws)
    # Create sample files
    (ws / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (ws / "README.md").write_text("# Test Project\nSample description.", encoding="utf-8")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


@pytest.fixture
def mock_security_manager():
    """Create a security manager with auto approval."""
    return SecurityManager(permission_level=PermissionLevel.FULL_AUTO)


@pytest.fixture
def tool_registry(temp_workspace, mock_security_manager):
    """Create a ToolRegistry bound to the temporary workspace."""
    return build_default_tool_registry(
        workspace_root=temp_workspace,
        security_manager=mock_security_manager,
    )


@pytest.fixture
def mock_llm_provider():
    """Create a MockLLMProvider for offline deterministic tests."""
    return MockLLMProvider()
