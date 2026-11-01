"""Git version control tools for Code68."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import git
from git.exc import InvalidGitRepositoryError


class GitTools:
    """Provides workspace Git inspection and controlled commit creation."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def _get_repo(self) -> git.Repo:
        if not (self.workspace_root / ".git").exists():
            raise RuntimeError(f"'{self.workspace_root}' is not a Git repository.")
        try:
            return git.Repo(self.workspace_root, search_parent_directories=False)
        except (InvalidGitRepositoryError, Exception) as e:
            raise RuntimeError(f"Failed to open Git repository at '{self.workspace_root}': {e}")

    def git_status(self) -> str:
        """Get git status showing modified, untracked, and staged files."""
        try:
            repo = self._get_repo()
            return repo.git.status()
        except Exception as e:
            return f"Git status error: {e}"

    def git_diff(self, cached: bool = False, file_path: Optional[str] = None) -> str:
        """Get git diff for uncommitted changes."""
        try:
            repo = self._get_repo()
            args = ["--cached"] if cached else []
            if file_path:
                args.extend(["--", file_path])
            diff = repo.git.diff(*args)
            if not diff.strip():
                return "No changes detected in git diff."
            return f"```diff\n{diff}\n```"
        except Exception as e:
            return f"Git diff error: {e}"

    def git_log(self, max_count: int = 5) -> str:
        """Get recent git commit history."""
        try:
            repo = self._get_repo()
            commits = list(repo.iter_commits(max_count=max_count))
            if not commits:
                return "No commits found in repository."

            lines = []
            for c in commits:
                short_hash = c.hexsha[:8]
                date_str = c.committed_datetime.strftime("%Y-%m-%d %H:%M")
                lines.append(f"* {short_hash} - {date_str} - {c.summary} ({c.author.name})")

            return "\n".join(lines)
        except Exception as e:
            return f"Git log error: {e}"

    def git_show(self, commit: str = "HEAD") -> str:
        """Show details and diff of a specific commit."""
        try:
            repo = self._get_repo()
            return repo.git.show(commit, stat=True)
        except Exception as e:
            return f"Git show error: {e}"

    def git_branch(self) -> str:
        """List branches or show active branch."""
        try:
            repo = self._get_repo()
            active = repo.active_branch.name if not repo.head.is_detached else "detached HEAD"
            branches = [b.name for b in repo.branches]
            return f"Active branch: {active}\nAll local branches: {', '.join(branches)}"
        except Exception as e:
            return f"Git branch error: {e}"

    def git_commit(self, message: str) -> str:
        """Create a git commit with staged changes (Requires user confirmation)."""
        try:
            repo = self._get_repo()
            # Stage modified and untracked files
            repo.git.add(A=True)
            commit = repo.index.commit(message)
            return f"Successfully created commit {commit.hexsha[:8]}: '{message}'"
        except Exception as e:
            return f"Git commit error: {e}"
