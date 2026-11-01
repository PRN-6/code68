"""Configuration management for Code68."""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load local .env if present
load_dotenv()


class PermissionLevel(str, Enum):
    """Permission levels for tool execution."""

    READ_ONLY = "read-only"
    EDIT_APPROVED = "edit-approved"
    AUTO_EDIT = "auto-edit"
    COMMAND_APPROVED = "command-approved"
    FULL_AUTO = "full-auto"


class Config(BaseModel):
    """Code68 configuration."""

    base_url: str = Field(
        default_factory=lambda: os.getenv("CODE68_BASE_URL", "http://localhost:8000/v1")
    )
    api_key: str = Field(
        default_factory=lambda: os.getenv("CODE68_API_KEY", "code68-secret-key")
    )
    model: str = Field(
        default_factory=lambda: os.getenv("CODE68_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
    )
    provider: str = Field(
        default_factory=lambda: os.getenv("CODE68_PROVIDER", "openai-compatible")
    )
    permission_level: PermissionLevel = Field(
        default_factory=lambda: PermissionLevel(
            os.getenv("CODE68_PERMISSION_LEVEL", PermissionLevel.EDIT_APPROVED.value)
        )
    )
    timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("CODE68_TIMEOUT_SECONDS", "120.0"))
    )
    max_iterations: int = Field(
        default_factory=lambda: int(os.getenv("CODE68_MAX_ITERATIONS", "25"))
    )
    max_output_chars: int = Field(
        default_factory=lambda: int(os.getenv("CODE68_MAX_OUTPUT_CHARS", "16000"))
    )
    context_token_limit: int = Field(
        default_factory=lambda: int(os.getenv("CODE68_CONTEXT_LIMIT", "32768"))
    )
    temperature: float = Field(
        default_factory=lambda: float(os.getenv("CODE68_TEMPERATURE", "0.2"))
    )
    kaggle_notebook_url: str = Field(
        default_factory=lambda: os.getenv(
            "CODE68_KAGGLE_URL", "https://www.kaggle.com/code/prinsonroyal/notebook42b8c0f4df/edit"
        )
    )

    @classmethod
    def get_config_dir(cls) -> Path:
        """Returns the user-level configuration directory."""
        config_dir = Path.home() / ".code68"
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return config_dir

    @classmethod
    def get_workspace_dir(cls, workspace_root: Path) -> Path:
        """Returns the workspace-level configuration and session directory."""
        ws_dir = workspace_root / ".code68"
        ws_dir.mkdir(parents=True, exist_ok=True)
        return ws_dir

    @classmethod
    def load(cls, workspace_root: Optional[Path] = None) -> Config:
        """Load configuration prioritizing workspace config over global over defaults/env."""
        config_dict = {}

        # 1. Global config file
        try:
            global_path = cls.get_config_dir() / "config.json"
            if global_path.is_file():
                with open(global_path, "r", encoding="utf-8") as f:
                    config_dict.update(json.load(f))
        except (OSError, PermissionError, Exception):
            pass

        # 2. Workspace config file
        if workspace_root:
            try:
                ws_path = workspace_root / ".code68" / "config.json"
                if ws_path.is_file():
                    with open(ws_path, "r", encoding="utf-8") as f:
                        config_dict.update(json.load(f))
            except (OSError, PermissionError, Exception):
                pass

        # Pydantic will fill in remaining from env vars and defaults
        return cls(**config_dict)

    def save(self, path: Optional[Path] = None, global_config: bool = False) -> Path:
        """Save configuration to JSON file."""
        if path is None:
            if global_config:
                path = self.get_config_dir() / "config.json"
            else:
                path = Path.cwd() / ".code68" / "config.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2)
        return path
