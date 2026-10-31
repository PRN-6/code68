"""Autonomous tool-calling agent loop for Code68."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Callable, Optional
from code68.core.conversation import Conversation
from code68.core.state import LoopDetector
from code68.llm.base import BaseLLMProvider, LLMError
from code68.llm.models import Message, Role, ToolCall, FunctionCall
from code68.tools.registry import ToolRegistry
from code68.ui.renderer import TerminalRenderer

logger = logging.getLogger(__name__)


class AgentLoop:
    """Executes the tool-calling conversation loop."""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        conversation: Conversation,
        renderer: Optional[TerminalRenderer] = None,
        max_iterations: int = 25,
        temperature: float = 0.2,
    ) -> None:
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.conversation = conversation
        self.renderer = renderer
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.loop_detector = LoopDetector(max_repeated_calls=3)

    async def run(
        self,
        user_prompt: str,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Run the agent loop until the task is complete or maximum iterations reached."""
        print("[DEBUG Loop] Entered run()")
        self.conversation.add_user_message(user_prompt)
        print("[DEBUG Loop] Added user message")
        tools_schema = self.tool_registry.get_openai_tools()
        print(f"[DEBUG Loop] Got tools schema: {len(tools_schema)}")

        iteration = 0
        final_answer = ""

        while iteration < self.max_iterations:
            iteration += 1
            print(f"[DEBUG Loop] iteration {iteration}")

            # Check loop detector
            is_loop, loop_reason = self.loop_detector.is_looping()
            if is_loop:
                warning_msg = f"[Agent loop terminated early: {loop_reason}]"
                if self.renderer:
                    self.renderer.render_warning(warning_msg)
                self.conversation.add_assistant_message(content=warning_msg)
                return warning_msg

            # Query Cloud LLM
            messages = self.conversation.get_messages()
            print(f"[DEBUG Loop] calling chat_complete with {len(messages)} messages")
            try:
                response_msg: Message = await self.llm_provider.chat_complete(
                    messages=messages,
                    tools=tools_schema if tools_schema else None,
                    temperature=self.temperature,
                    on_token=on_token,
                )
            except LLMError as e:
                err_text = f"LLM Inference Error: {e}"
                if self.renderer:
                    self.renderer.render_error(err_text)
                return err_text
            except asyncio.CancelledError:
                if self.renderer:
                    self.renderer.render_warning("Operation cancelled by user.")
                return "Operation cancelled."

            print(f"[DEBUG Loop] got response: content={response_msg.content!r}, tool_calls={len(response_msg.tool_calls or [])}")

            # Check for native tool calls or fallback JSON in text
            tool_calls = response_msg.tool_calls
            if not tool_calls and response_msg.content:
                # Check for structured tool call fallback (e.g. ```json {"tool": ...} ```)
                tool_calls = self._parse_fallback_tool_calls(response_msg.content)

            # If no tool calls, model has finished reasoning
            if not tool_calls:
                self.conversation.add_assistant_message(content=response_msg.content)
                final_answer = response_msg.content or ""
                break

            # Store assistant message with tool calls
            self.conversation.add_assistant_message(
                content=response_msg.content, tool_calls=tool_calls
            )

            # Sequential tool execution
            for tc in tool_calls:
                tool_name = tc.function.name
                arguments = tc.parse_arguments()
                print(f"[DEBUG Loop] executing tool {tool_name} with args {arguments}")

                if self.renderer:
                    self.renderer.render_tool_call(tool_name, arguments)

                # Execute via registry (enforces permissions & sandbox)
                result_str = await self.tool_registry.execute(tool_name, arguments)
                print(f"[DEBUG Loop] tool {tool_name} executed, result len={len(result_str)}")
                is_error = result_str.startswith("Error") or result_str.startswith("Permission denied")

                # Record call in loop detector
                self.loop_detector.record_call(
                    tool_name=tool_name,
                    arguments=arguments,
                    success=not is_error,
                    iteration=iteration,
                )

                if self.renderer:
                    self.renderer.render_tool_result(tool_name, result_str, is_error=is_error)

                # Append tool result to conversation
                self.conversation.add_tool_result(
                    tool_call_id=tc.id,
                    tool_name=tool_name,
                    result=result_str,
                )

        if iteration >= self.max_iterations and not final_answer:
            final_answer = f"[Agent reached maximum iteration limit of {self.max_iterations} steps.]"
            if self.renderer:
                self.renderer.render_warning(final_answer)

        return final_answer

    def _parse_fallback_tool_calls(self, text: str) -> Optional[list[ToolCall]]:
        """Fallback parser if model returns tool invocations inside markdown code blocks."""
        pattern = r"```(?:json)?\s*\{\s*\"tool\"\s*:\s*\"([^\"]+)\"\s*,\s*\"arguments\"\s*:\s*(\{.*?\})\s*\}\s*```"
        matches = list(re.finditer(pattern, text, re.DOTALL))
        if not matches:
            return None

        calls = []
        for i, match in enumerate(matches):
            tool_name = match.group(1)
            raw_args = match.group(2)
            calls.append(
                ToolCall(
                    id=f"fallback_call_{i+1}",
                    type="function",
                    function=FunctionCall(name=tool_name, arguments=raw_args),
                )
            )
        return calls if calls else None
