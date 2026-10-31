"""Core package for Code68."""

from code68.core.agent import Code68Agent
from code68.core.agent_loop import AgentLoop
from code68.core.context import ContextBuilder
from code68.core.conversation import Conversation
from code68.core.planner import ExecutionPlan, PlanStep
from code68.core.prompts import CODE68_SYSTEM_PROMPT, get_system_prompt
from code68.core.state import LoopDetector

__all__ = [
    "CODE68_SYSTEM_PROMPT",
    "AgentLoop",
    "Code68Agent",
    "ContextBuilder",
    "Conversation",
    "ExecutionPlan",
    "LoopDetector",
    "PlanStep",
    "get_system_prompt",
]

