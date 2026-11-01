"""Task planning and step tracking for Code68."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """An individual step in an execution plan."""

    step_number: int
    description: str
    completed: bool = False
    result_summary: Optional[str] = None


class ExecutionPlan(BaseModel):
    """Execution plan containing ordered steps."""

    goal: str
    steps: List[PlanStep] = Field(default_factory=list)

    def mark_completed(self, step_number: int, summary: Optional[str] = None) -> None:
        """Mark a step as completed."""
        for s in self.steps:
            if s.step_number == step_number:
                s.completed = True
                s.result_summary = summary
                break

    def get_progress_summary(self) -> str:
        """Format plan steps and completion status."""
        lines = [f"Goal: {self.goal}"]
        for s in self.steps:
            status = "✓" if s.completed else "○"
            lines.append(f"  [{status}] Step {s.step_number}: {s.description}")
        return "\n".join(lines)

