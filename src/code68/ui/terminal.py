"""Terminal interface for Code68."""

from __future__ import annotations

from typing import Optional
from rich.console import Console
from code68.ui.components import UIComponents
from code68.ui.renderer import TerminalRenderer


class TerminalUI:
    """Coordinates terminal rendering and user interactions."""

    def __init__(self) -> None:
        self.console = Console()
        self.renderer = TerminalRenderer(self.console)
        self.components = UIComponents(self.console)

    def print(self, *args, **kwargs) -> None:
        self.console.print(*args, **kwargs)

