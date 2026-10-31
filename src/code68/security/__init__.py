"""Security package for Code68."""

from code68.security.permissions import ActionCategory, SecurityManager
from code68.security.sandbox import SecuritySandboxError, is_safe_path, resolve_safe_path
from code68.security.validation import (
    check_prompt_injection,
    is_destructive_command,
    mask_secrets,
    truncate_output,
)

__all__ = [
    "ActionCategory",
    "SecurityManager",
    "SecuritySandboxError",
    "check_prompt_injection",
    "is_destructive_command",
    "is_safe_path",
    "mask_secrets",
    "resolve_safe_path",
    "truncate_output",
]
