"""Session persistence and restoration for Code68."""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from code68.llm.models import Message


class SessionData(BaseModel):
    """Persisted session payload."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    workspace_path: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)


class SessionManager:
    """Manages saving and loading session state from disk."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.sessions_dir = self.workspace_root / ".code68" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session_id: str, messages: List[Message]) -> Path:
        """Save conversation session to JSON file."""
        data = SessionData(
            session_id=session_id,
            workspace_path=str(self.workspace_root),
            messages=[m.model_dump(mode="json") for m in messages],
        )
        file_path = self.sessions_dir / f"{session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(data.model_dump_json(indent=2))
        return file_path

    def load_session(self, session_id: str) -> Optional[List[Message]]:
        """Load conversation session messages by id."""
        file_path = self.sessions_dir / f"{session_id}.json"
        if not file_path.is_file():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Message(**m) for m in data.get("messages", [])]
        except Exception:
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions in current workspace."""
        sessions = []
        for p in self.sessions_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(
                    {
                        "session_id": data.get("session_id", p.stem),
                        "created_at": data.get("created_at"),
                        "message_count": len(data.get("messages", [])),
                        "file_path": str(p),
                    }
                )
            except Exception:
                continue
        return sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)

