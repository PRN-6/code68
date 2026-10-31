"""Pytest fixtures for Code68 test suite."""

import shutil
import tempfile
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
    """Create a temporary workspace directory with initialized git repo."""
    temp_dir = tempfile.mkdtemp(prefix="code68_test_")
    ws = Path(temp_dir)
    git.Repo.init(ws)
    # Create sample files
    (ws / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (ws / "README.md").write_text("# Test Project\nSample description.", encoding="utf-8")
    yield ws
    shutil.rmtree(temp_dir, ignore_errors=True)


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
