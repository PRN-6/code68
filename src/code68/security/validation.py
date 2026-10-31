"""Security validation, destructive command detection, and secret sanitization."""

from __future__ import annotations

import re
from typing import Optional, Tuple

DESTRUCTIVE_PATTERNS = [
    # Shell rm / del / wipe
    (r"\brm\s+-(?:r|f|rf|fr)\s+[/~]", "Recursive deletion of root or home directory"),
    (r"\brmdir\s+/[sS]\s+/[qQ]\s+[cC]:", "Recursive Windows drive wipe"),
    (r"\bformat\s+[a-zA-Z]:", "Disk formatting command"),
    (r"\bmkfs\b", "Filesystem creation / wipe command"),
    (r"\bdd\s+if=.*of=/dev/(?:sd[a-z]|nvme|hd[a-z])", "Direct block device overwrite"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", "Fork bomb pattern"),
    (r"\bshutdown\b", "System shutdown command"),
    (r"\breboot\b", "System reboot command"),
    (r"\bgit\s+push\s+.*--force\b", "Git force push"),
    (r"\bgit\s+reset\s+--hard\b", "Git hard reset"),
    (r"\bgit\s+clean\s+-fdx\b", "Git destructive clean"),
    (r"\bdrop\s+(?:database|table)\b", "Destructive SQL operation"),
]

SECRET_PATTERNS = [
    (r"(bearer\s+)[a-zA-Z0-9_\-\.]{20,}", r"\1[REDACTED_TOKEN]"),
    (r"(api[_-]?key[\"'\s:=]+)[a-zA-Z0-9_\-]{16,}", r"\1[REDACTED_KEY]"),
    (r"(secret[\"'\s:=]+)[a-zA-Z0-9_\-]{16,}", r"\1[REDACTED_SECRET]"),
    (r"(password[\"'\s:=]+)[^\s\"']+", r"\1[REDACTED_PASSWORD]"),
    (r"(ghp_[a-zA-Z0-9]{36})", "[REDACTED_GITHUB_TOKEN]"),
    (r"(sk-[a-zA-Z0-9]{32,})", "[REDACTED_OPENAI_KEY]"),
]


def is_destructive_command(command: str) -> Tuple[bool, str]:
    """Check if command matches known high-risk destructive signatures."""
    cmd_lower = command.lower()
    for pattern, description in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return True, description
    return False, ""


def mask_secrets(text: str) -> str:
    """Mask known secret patterns from output and logs."""
    sanitized = text
    for pattern, repl in SECRET_PATTERNS:
        sanitized = re.sub(pattern, repl, sanitized, flags=re.IGNORECASE)
    return sanitized


def truncate_output(text: str, max_chars: int = 16000) -> str:
    """Truncate tool output if it exceeds max_chars, keeping head and tail with note."""
    if len(text) <= max_chars:
        return text

    keep = max_chars // 2
    head = text[:keep]
    tail = text[-keep:]
    omitted = len(text) - (len(head) + len(tail))
    return f"{head}\n\n... [Output truncated: {omitted} characters omitted] ...\n\n{tail}"


def check_prompt_injection(content: str) -> Optional[str]:
    """Detect suspected prompt injection directives within read files."""
    suspicious = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?prior\s+instructions",
        r"you\s+are\s+now\s+in\s+developer\s+mode",
        r"system\s+override\s*:",
    ]
    for pattern in suspicious:
        if re.search(pattern, content, re.IGNORECASE):
            return f"Suspected prompt injection pattern detected: '{pattern}'"
    return None
