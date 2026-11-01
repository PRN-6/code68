"""Interactive UI components and approval dialogs for Code68."""

from __future__ import annotations

from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt


class UIComponents:
    """Provides interactive prompts and confirmations."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    def confirm_action(self, description: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Prompt user for confirmation before executing an action."""
        self.console.print()
        panel = Panel(
            f"[bold yellow]{description}[/bold yellow]",
            title="[bold red]Action Approval Required[/bold red]",
            border_style="yellow",
            padding=(0, 1),
        )
        self.console.print(panel)
        if details:
            for k, v in details.items():
                self.console.print(f"  [dim]{k}:[/dim] {v}")

        try:
            return Confirm.ask("[bold cyan]Approve execution?[/bold cyan]", default=False)
        except (KeyboardInterrupt, EOFError):
            return False

    def confirm(self, prompt: str, default: bool = False) -> bool:
        """Prompt user for a simple yes/no confirmation."""
        try:
            return Confirm.ask(f"[bold cyan]{prompt}[/bold cyan]", default=default)
        except (KeyboardInterrupt, EOFError):
            return default

    def ask_input(self, prompt: str = "code68> ") -> str:
        """Prompt user for input."""
        try:
            return Prompt.ask(f"[bold green]{prompt}[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            return "/exit"

