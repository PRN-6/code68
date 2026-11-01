"""Tool schemas and function calling specifications."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from code68.security.permissions import ActionCategory


class ToolParameter(BaseModel):
    """Specification for a parameter."""

    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    """Complete definition of a tool callable by the agent."""

    name: str
    description: str
    category: ActionCategory
    parameters: Dict[str, ToolParameter]

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI tool schema format."""
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for p_name, p_spec in self.parameters.items():
            prop: Dict[str, Any] = {
                "type": p_spec.type,
                "description": p_spec.description,
            }
            if p_spec.enum is not None:
                prop["enum"] = p_spec.enum
            properties[p_name] = prop

            if p_spec.required:
                required.append(p_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

