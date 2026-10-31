"""Tool initialization and registration helpers for Code68."""

from __future__ import annotations

from pathlib import Path
from code68.security.permissions import ActionCategory, SecurityManager
from code68.tools.filesystem import FilesystemTools
from code68.tools.git import GitTools
from code68.tools.registry import ToolRegistry
from code68.tools.schemas import ToolParameter
from code68.tools.search import SearchTools
from code68.tools.terminal import TerminalTools
from code68.tools.testing import TestingTools


def build_default_tool_registry(
    workspace_root: Path,
    security_manager: SecurityManager,
    max_output_chars: int = 16000,
) -> ToolRegistry:
    """Build and return standard tool registry initialized with all local tools."""
    registry = ToolRegistry(
        workspace_root=workspace_root,
        security_manager=security_manager,
        max_output_chars=max_output_chars,
    )

    fs = FilesystemTools(workspace_root)
    search = SearchTools(workspace_root)
    term = TerminalTools(workspace_root)
    git = GitTools(workspace_root)
    test = TestingTools(workspace_root)

    # 1. Filesystem Tools
    registry.register(
        name="read_file",
        description="Read lines from a file within the workspace. Numbers each line.",
        category=ActionCategory.READ,
        parameters={
            "path": ToolParameter(type="string", description="Relative path to the file"),
            "offset": ToolParameter(type="integer", description="Starting line number (1-based)", required=False, default=1),
            "limit": ToolParameter(type="integer", description="Maximum lines to return", required=False, default=400),
        },
        handler=fs.read_file,
    )

    registry.register(
        name="write_file",
        description="Write full content to a file in the workspace (creates file and parent directories if needed).",
        category=ActionCategory.EDIT,
        parameters={
            "path": ToolParameter(type="string", description="Relative path to the file"),
            "content": ToolParameter(type="string", description="Full content to write"),
        },
        handler=fs.write_file,
    )

    registry.register(
        name="edit_file",
        description="Replace an exact snippet of text with new text in a file. Generates a unified diff.",
        category=ActionCategory.EDIT,
        parameters={
            "path": ToolParameter(type="string", description="Relative path to the file"),
            "old_text": ToolParameter(type="string", description="Exact text snippet to replace"),
            "new_text": ToolParameter(type="string", description="Replacement text"),
        },
        handler=fs.edit_file,
    )

    registry.register(
        name="list_directory",
        description="List files and folders in a workspace directory.",
        category=ActionCategory.READ,
        parameters={
            "path": ToolParameter(type="string", description="Relative path to directory", required=False, default="."),
            "recursive": ToolParameter(type="boolean", description="Whether to recurse into subdirectories", required=False, default=False),
            "max_depth": ToolParameter(type="integer", description="Max recursion depth", required=False, default=2),
        },
        handler=fs.list_directory,
    )

    registry.register(
        name="create_directory",
        description="Create a new directory inside the workspace.",
        category=ActionCategory.EDIT,
        parameters={
            "path": ToolParameter(type="string", description="Relative path to new directory"),
        },
        handler=fs.create_directory,
    )

    registry.register(
        name="delete_file",
        description="Delete a file from the workspace (requires explicit confirmation).",
        category=ActionCategory.DELETE,
        parameters={
            "path": ToolParameter(type="string", description="Relative path to file to delete"),
        },
        handler=fs.delete_file,
    )

    # 2. Search Tools
    registry.register(
        name="search_files",
        description="Search for text or regex across workspace files using ripgrep or regex.",
        category=ActionCategory.READ,
        parameters={
            "query": ToolParameter(type="string", description="Text or regex to search for"),
            "path": ToolParameter(type="string", description="Relative root to search within", required=False, default="."),
            "case_sensitive": ToolParameter(type="boolean", description="Case-sensitive search", required=False, default=False),
        },
        handler=search.search_files,
    )

    registry.register(
        name="find_files",
        description="Find files matching glob pattern (e.g. '*.py', '*config*').",
        category=ActionCategory.READ,
        parameters={
            "pattern": ToolParameter(type="string", description="Glob pattern to match file names"),
            "path": ToolParameter(type="string", description="Relative root directory", required=False, default="."),
        },
        handler=search.find_files,
    )

    registry.register(
        name="search_symbols",
        description="Search for Python functions and classes matching a symbol name.",
        category=ActionCategory.READ,
        parameters={
            "name": ToolParameter(type="string", description="Symbol name or substring to search"),
            "path": ToolParameter(type="string", description="Relative path root", required=False, default="."),
        },
        handler=search.search_symbols,
    )

    # 3. Terminal Tool
    registry.register(
        name="run_command",
        description="Run a shell command in the workspace terminal and capture stdout, stderr, and exit code.",
        category=ActionCategory.COMMAND,
        parameters={
            "command": ToolParameter(type="string", description="Shell command string to execute"),
            "cwd": ToolParameter(type="string", description="Working directory relative to workspace root", required=False, default="."),
            "timeout": ToolParameter(type="integer", description="Execution timeout in seconds", required=False, default=60),
        },
        handler=term.run_command,
    )

    # 4. Git Tools
    registry.register(
        name="git_status",
        description="Check git status for modified, untracked, and staged files.",
        category=ActionCategory.GIT_READ,
        parameters={},
        handler=git.git_status,
    )

    registry.register(
        name="git_diff",
        description="View git diff for uncommitted workspace changes.",
        category=ActionCategory.GIT_READ,
        parameters={
            "cached": ToolParameter(type="boolean", description="Show staged changes if True", required=False, default=False),
            "file_path": ToolParameter(type="string", description="Filter diff to specific file", required=False),
        },
        handler=git.git_diff,
    )

    registry.register(
        name="git_log",
        description="View recent git commit history.",
        category=ActionCategory.GIT_READ,
        parameters={
            "max_count": ToolParameter(type="integer", description="Number of commits to show", required=False, default=5),
        },
        handler=git.git_log,
    )

    registry.register(
        name="git_show",
        description="Show commit details and diff for a git revision.",
        category=ActionCategory.GIT_READ,
        parameters={
            "commit": ToolParameter(type="string", description="Commit hash, tag, or ref", required=False, default="HEAD"),
        },
        handler=git.git_show,
    )

    registry.register(
        name="git_branch",
        description="Show current git branch and list of local branches.",
        category=ActionCategory.GIT_READ,
        parameters={},
        handler=git.git_branch,
    )

    registry.register(
        name="git_commit",
        description="Create a git commit with all current changes (Requires confirmation).",
        category=ActionCategory.GIT_WRITE,
        parameters={
            "message": ToolParameter(type="string", description="Git commit message"),
        },
        handler=git.git_commit,
    )

    # 5. Testing Tools
    registry.register(
        name="run_tests",
        description="Run project automated tests (pytest, npm test, etc.) and view pass/fail summary.",
        category=ActionCategory.COMMAND,
        parameters={
            "test_path": ToolParameter(type="string", description="Specific test file or directory", required=False),
            "flags": ToolParameter(type="string", description="Additional CLI flags for test runner", required=False, default="-v"),
        },
        handler=test.run_tests,
    )

    registry.register(
        name="run_linter",
        description="Run code linter (ruff / flake8) on project files.",
        category=ActionCategory.COMMAND,
        parameters={
            "path": ToolParameter(type="string", description="Target path or directory", required=False, default="."),
        },
        handler=test.run_linter,
    )

    registry.register(
        name="run_type_checker",
        description="Run static type checker (mypy) on project files.",
        category=ActionCategory.COMMAND,
        parameters={
            "path": ToolParameter(type="string", description="Target path or directory", required=False, default="."),
        },
        handler=test.run_type_checker,
    )

    return registry

