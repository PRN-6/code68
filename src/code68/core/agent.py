"""High-level Code68 Agent coordinator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional
from code68.core.agent_loop import AgentLoop
from code68.core.context import ContextBuilder
from code68.core.conversation import Conversation
from code68.core.prompts import get_system_prompt
from code68.llm.base import BaseLLMProvider
from code68.llm.client import get_llm_provider
from code68.llm.providers import MockLLMProvider
from code68.security.permissions import SecurityManager
from code68.storage.config import Config
from code68.storage.sessions import SessionManager
from code68.tools import build_default_tool_registry
from code68.tools.registry import ToolRegistry
from code68.ui.terminal import TerminalUI


class Code68Agent:
    """Main agent coordinating LLM communication, local tools, security, and conversation."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        config: Optional[Config] = None,
        ui: Optional[TerminalUI] = None,
        mock_provider: Optional[MockLLMProvider] = None,
    ) -> None:
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.ui = ui or TerminalUI()
        self.config = config or Config.load(self.workspace_root)

        # 1. Security Manager with Interactive Confirmation UI
        self.security_manager = SecurityManager(
            permission_level=self.config.permission_level,
            approval_callback=self.ui.components.confirm_action,
        )

        # 2. Tool Registry
        self.tool_registry: ToolRegistry = build_default_tool_registry(
            workspace_root=self.workspace_root,
            security_manager=self.security_manager,
            max_output_chars=self.config.max_output_chars,
        )

        # 3. LLM Provider
        self.llm_provider: BaseLLMProvider = get_llm_provider(self.config, mock_provider=mock_provider)

        # 4. Context Builder & Conversation
        self.context_builder = ContextBuilder(self.workspace_root)
        self.session_manager = SessionManager(self.workspace_root)
        self.conversation: Optional[Conversation] = None
        self._initialize_conversation()

    def _initialize_conversation(self) -> None:
        """Build initial workspace context and set up conversation."""
        ws_summary = self.context_builder.build_workspace_summary()
        system_prompt = get_system_prompt(ws_summary)
        self.conversation = Conversation(
            system_prompt=system_prompt,
            token_limit=self.config.context_token_limit,
        )

    async def check_connection(self) -> Dict[str, Any]:
        """Perform health check on the inference server."""
        return await self.llm_provider.health_check()

    async def execute(self, prompt: str, stream: bool = True) -> str:
        """Run an instruction through the agent loop."""
        if not self.conversation:
            self._initialize_conversation()

        token_callback = (lambda tok: self.ui.console.print(tok, end="", highlight=False)) if stream else None

        loop = AgentLoop(
            llm_provider=self.llm_provider,
            tool_registry=self.tool_registry,
            conversation=self.conversation,
            renderer=self.ui.renderer,
            max_iterations=self.config.max_iterations,
            temperature=self.config.temperature,
        )

        result = await loop.run(prompt, on_token=token_callback)
        if stream:
            self.ui.console.print()  # Final newline after streaming
        return result

    def clear(self) -> None:
        """Reset conversation context."""
        self._initialize_conversation()

    def compact(self) -> int:
        """Compact conversation context."""
        if self.conversation:
            return self.conversation.compact()
        return 0
