"""Tests for Code68 security, sandboxing, and permissions."""

import pytest

from code68.security.permissions import ActionCategory, SecurityManager
from code68.security.sandbox import SecuritySandboxError, is_safe_path, resolve_safe_path
from code68.security.validation import (
    is_destructive_command,
    mask_secrets,
    truncate_output,
)
from code68.storage.config import PermissionLevel


def test_path_traversal_prevention(temp_workspace):
    # Attempting to access parent directory must raise SecuritySandboxError
    with pytest.raises(SecuritySandboxError):
        resolve_safe_path("../../secret.txt", temp_workspace)

    with pytest.raises(SecuritySandboxError):
        resolve_safe_path("../../../etc/passwd", temp_workspace)

    assert not is_safe_path("../outside.py", temp_workspace)
    assert is_safe_path("inside.py", temp_workspace)


def test_destructive_command_detection():
    is_destr, desc = is_destructive_command("rm -rf /")
    assert is_destr

    is_destr, desc = is_destructive_command("mkfs /dev/sda1")
    assert is_destr

    is_destr, desc = is_destructive_command("git push origin main --force")
    assert is_destr

    # Safe command
    is_destr, _ = is_destructive_command("pytest -v")
    assert not is_destr


def test_secret_masking():
    raw = "Here is my key: sk-abcdef12345678901234567890123456 and token: Bearer mySecretToken1234567890abcdef"
    masked = mask_secrets(raw)
    assert "sk-" not in masked
    assert "[REDACTED" in masked


def test_output_truncation():
    large_text = "A" * 20000
    truncated = truncate_output(large_text, max_chars=1000)
    assert len(truncated) < 2000
    assert "[Output truncated:" in truncated


def test_permission_levels():
    # 1. Read-only blocks edits
    ro_manager = SecurityManager(permission_level=PermissionLevel.READ_ONLY)
    assert ro_manager.check_permission(ActionCategory.READ, "read file")
    assert not ro_manager.check_permission(ActionCategory.EDIT, "edit file")

    # 2. Edit-approved triggers callback
    approvals = []

    def callback(prompt, details):
        return approvals.append(prompt) or True

    ea_manager = SecurityManager(permission_level=PermissionLevel.EDIT_APPROVED, approval_callback=callback)

    assert ea_manager.check_permission(ActionCategory.READ, "read file")
    assert len(approvals) == 0

    assert ea_manager.check_permission(ActionCategory.EDIT, "write file")
    assert len(approvals) == 1

