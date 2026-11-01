"""Filesystem sandbox and boundary enforcement."""

from __future__ import annotations

from pathlib import Path


class SecuritySandboxError(Exception):
    """Raised when an operation violates security boundaries."""


def resolve_safe_path(requested_path: str | Path, workspace_root: Path) -> Path:
    """Resolve a relative or absolute path ensuring it remains strictly inside workspace_root."""
    workspace_root = workspace_root.resolve()
    target = Path(requested_path)

    if not target.is_absolute():
        target = workspace_root / target

    target = target.resolve()

    try:
        # relative_to raises ValueError if target is not within workspace_root
        target.relative_to(workspace_root)
    except ValueError:
        raise SecuritySandboxError(
            f"Path traversal blocked: '{requested_path}' resolves to '{target}' which is outside workspace '{workspace_root}'"
        )

    return target


def is_safe_path(requested_path: str | Path, workspace_root: Path) -> bool:
    """Check whether a path resolves safely within workspace_root."""
    try:
        resolve_safe_path(requested_path, workspace_root)
        return True
    except SecuritySandboxError:
        return False

