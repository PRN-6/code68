"""Rich terminal renderers for Code68."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from code68 import __version__


class TerminalRenderer:
    """Renders formatted UI components using Rich."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    def render_banner(
        self,
        model: str,
        provider: str,
        connection_status: str,
        workspace: str,
    ) -> None:
        """Render the Code68 ASCII art header banner."""
        art_lines = [
            r"   ______ ____  ____   ______     ______  ____  ",
            r"  / ____// __ \/ __ \ / ____/    / ____/ ( __ ) ",
            r" / /    / / / / / / // __/      / __ \  / __  | ",
            r"/ /___ / /_/ / /_/ // /___     / /_/ / / /_/ /  ",
            r"\____/ \____/_____//_____/     \____/  \____/   ",
        ]

        banner_text = Text()
        gradient_colors = ["#38bdf8", "#60a5fa", "#818cf8", "#a78bfa", "#c084fc"]
        for line, color in zip(art_lines, gradient_colors):
            banner_text.append(line + "\n", style=f"bold {color}")

        banner_text.append("\n          Autonomous AI Coding Agent\n", style="bold white")
        banner_text.append("     Cloud Intelligence + Local Execution\n", style="italic cyan")

        panel = Panel(
            banner_text,
            title=f"[bold magenta]Code68 v{__version__}[/bold magenta]",
            subtitle="[dim]https://github.com/PRN-6/code68[/dim]",
            border_style="bright_blue",
            padding=(1, 3),
            expand=False,
        )
        self.console.print(panel)

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", justify="right")
        grid.add_column(style="white")
        grid.add_column(style="bold cyan", justify="right")
        grid.add_column(style="white")

        status_style = "green" if "connect" in connection_status.lower() else "yellow"
        grid.add_row(
            "Model:",
            model,
            "Connection:",
            f"[{status_style}]{connection_status}[/{status_style}]",
        )
        grid.add_row("Provider:", provider, "Workspace:", workspace)

        self.console.print(Panel(grid, border_style="dim", expand=False))
        self.console.print()

    def render_markdown(self, markdown_text: str) -> None:
        """Render markdown text with syntax highlighted code."""
        md = Markdown(markdown_text)
        self.console.print(md)

    def render_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Render tool execution indicator."""
        args_display = ", ".join(f"[cyan]{k}[/cyan]={v!r}" for k, v in arguments.items())
        text = Text()
        text.append(" ⚡ Tool: ", style="bold yellow")
        text.append(f"{tool_name}({args_display})", style="bold white")
        self.console.print(Panel(text, border_style="yellow", padding=(0, 1)))

    def render_tool_result(self, tool_name: str, result: str, is_error: bool = False) -> None:
        """Render tool result output."""
        border = "red" if is_error else "green"
        prefix = "❌ Error" if is_error else "✓ Result"

        # If diff is in output, render nicely
        if "```diff" in result:
            self.console.print(Markdown(result))
        else:
            snippet = result[:1000] + ("\n... [truncated]" if len(result) > 1000 else "")
            panel = Panel(
                Text(snippet, style="white" if not is_error else "red"),
                title=f"[{border}]{prefix} - {tool_name}[/{border}]",
                border_style=border,
                padding=(0, 1),
            )
            self.console.print(panel)

    def render_diff(self, diff_text: str, file_path: str) -> None:
        """Render a colorized unified diff."""
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        panel = Panel(
            syntax,
            title=f"[bold cyan]Proposed Changes: {file_path}[/bold cyan]",
            border_style="cyan",
        )
        self.console.print(panel)

    def render_error(self, message: str) -> None:
        """Render an error message."""
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def render_warning(self, message: str) -> None:
        """Render a warning message."""
        self.console.print(f"[bold yellow]Warning:[/bold yellow] {message}")

    def render_success(self, message: str) -> None:
        """Render a success message."""
        self.console.print(f"[bold green]Success:[/bold green] {message}")

