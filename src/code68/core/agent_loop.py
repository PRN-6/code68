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
from code68.llm.models import FunctionCall, Message, ToolCall
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
        self.conversation.add_user_message(user_prompt)
        tools_schema = self.tool_registry.get_openai_tools()

        iteration = 0
        final_answer = ""

        while iteration < self.max_iterations:
            iteration += 1

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

                if self.renderer:
                    self.renderer.render_tool_call(tool_name, arguments)

                # Execute via registry (enforces permissions & sandbox)
                result_str = await self.tool_registry.execute(tool_name, arguments)
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
        """Fallback parser if model returns tool invocations inside XML tags or markdown blocks."""
        calls: list[ToolCall] = []
        call_idx = 1

        # 1. Qwen / XML format: <tool_call>\n{...}\n</tool_call>
        xml_matches = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL)
        for raw_json in xml_matches:
            try:
                data = json.loads(raw_json)
                name = data.get("name") or data.get("tool") or data.get("action")
                args = data.get("arguments", data.get("parameters", {}))
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                if name and self.tool_registry.has_tool(name):
                    calls.append(
                        ToolCall(
                            id=f"fallback_call_{call_idx}",
                            type="function",
                            function=FunctionCall(name=name, arguments=args_str),
                        )
                    )
                    call_idx += 1
            except Exception:
                continue

        if calls:
            return calls

        # 2. Markdown codeblock format: ```json\n{...}\n```
        md_matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        for raw_json in md_matches:
            try:
                data = json.loads(raw_json)
                name = data.get("name") or data.get("tool") or data.get("action")
                args = data.get("arguments", data.get("parameters", {}))
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                if name and self.tool_registry.has_tool(name):
                    calls.append(
                        ToolCall(
                            id=f"fallback_call_{call_idx}",
                            type="function",
                            function=FunctionCall(name=name, arguments=args_str),
                        )
                    )
                    call_idx += 1
            except Exception:
                continue

        return calls if calls else None
