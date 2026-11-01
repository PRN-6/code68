"""Permission and security control system for Code68."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, Optional

from code68.storage.config import PermissionLevel


class ActionCategory(str, Enum):
    """Categories of operations performed by tools."""

    READ = "read"
    EDIT = "edit"
    DELETE = "delete"
    COMMAND = "command"
    COMMAND_DESTRUCTIVE = "command_destructive"
    GIT_READ = "git_read"
    GIT_WRITE = "git_write"


class SecurityManager:
    """Evaluates whether actions are permitted or require interactive user confirmation."""

    def __init__(
        self,
        permission_level: PermissionLevel = PermissionLevel.EDIT_APPROVED,
        approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ) -> None:
        self.permission_level = permission_level
        self.approval_callback = approval_callback

    def check_permission(
        self,
        category: ActionCategory,
        description: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if an action is allowed, prompting for approval if required."""
        details = details or {}

        # Critical operations ALWAYS require explicit user confirmation unless full-auto
        if category in (ActionCategory.DELETE, ActionCategory.COMMAND_DESTRUCTIVE, ActionCategory.GIT_WRITE):
            if self.permission_level == PermissionLevel.FULL_AUTO:
                return True
            return self._ask_approval(f"⚠️  Dangerous operation: {description}", details)

        # Read-only permission
        if self.permission_level == PermissionLevel.READ_ONLY:
            if category in (ActionCategory.READ, ActionCategory.GIT_READ):
                return True
            return False  # Modification blocked in read-only mode

        # Edit-approved: prompt on any edits, commands, deletes
        if self.permission_level == PermissionLevel.EDIT_APPROVED:
            if category in (ActionCategory.READ, ActionCategory.GIT_READ):
                return True
            return self._ask_approval(f"Modify/Execute: {description}", details)

        # Auto-edit: automatically approve file edits, but prompt on commands
        if self.permission_level == PermissionLevel.AUTO_EDIT:
            if category in (ActionCategory.READ, ActionCategory.EDIT, ActionCategory.GIT_READ):
                return True
            return self._ask_approval(f"Execute command: {description}", details)

        # Command-approved: approve edits and reads, prompt before terminal commands
        if self.permission_level == PermissionLevel.COMMAND_APPROVED:
            if category in (ActionCategory.READ, ActionCategory.EDIT, ActionCategory.GIT_READ):
                return True
            return self._ask_approval(f"Terminal Command: {description}", details)

        # Full-auto: permit everything except if specifically configured otherwise
        if self.permission_level == PermissionLevel.FULL_AUTO:
            return True

        return False

    def _ask_approval(self, prompt: str, details: Dict[str, Any]) -> bool:
        """Prompt user via callback if registered, or default to False."""
        if self.approval_callback is not None:
            return self.approval_callback(prompt, details)
        return False

