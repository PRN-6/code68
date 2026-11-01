"""CLI interface for Code68."""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from code68 import __version__
from code68.core.agent import Code68Agent
from code68.storage.config import Config, PermissionLevel
from code68.ui.terminal import TerminalUI

app = typer.Typer(
    name="code68",
    help="Code68: Autonomous AI Coding Agent — Cloud Intelligence + Local Execution",
    no_args_is_help=False,
)


SUBCOMMANDS = {"doctor", "config", "init"}


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override the LLM model name"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Override LLM provider"
    ),
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Display Code68 version"
    ),
) -> None:
    """Main CLI entrypoint for Code68."""
    if version:
        typer.echo(f"Code68 version {__version__}")
        raise typer.Exit()

    # If a subcommand (like doctor, config, init) was invoked, let Typer handle it
    if ctx.invoked_subcommand is not None:
        return

    # Check if a direct prompt was passed in argv (e.g. `code68 "Explain this project"`)
    # Skip known options and their arguments
    options_with_value = {"--model", "-m", "--provider", "-p"}
    positional_args = []
    skip_next = False
    for arg in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg in options_with_value:
            skip_next = True
            continue
        if any(arg.startswith(f"{opt}=") for opt in ("--model", "-m", "--provider", "-p")):
            continue
        if arg.startswith("-"):
            continue
        positional_args.append(arg)

    direct_prompt = None
    if positional_args and positional_args[0] not in SUBCOMMANDS:
        direct_prompt = " ".join(positional_args)

    # Load configuration
    cfg = Config.load(Path.cwd())
    if model:
        cfg.model = model
    if provider:
        cfg.provider = provider

    ui = TerminalUI()
    agent = Code68Agent(workspace_root=Path.cwd(), config=cfg, ui=ui)

    if direct_prompt:
        # Run one-shot prompt
        asyncio.run(agent.execute(direct_prompt, stream=True))
    else:
        # Start interactive REPL
        asyncio.run(run_interactive_session(agent, ui, cfg))


async def run_interactive_session(agent: Code68Agent, ui: TerminalUI, cfg: Config) -> None:
    """Interactive terminal REPL."""
    # Test connection for banner status
    try:
        health = await agent.check_connection()
        status_str = f"Connected ({health.get('status', 'ok')})"
    except Exception as e:
        status_str = f"Disconnected ({type(e).__name__})"

    ui.renderer.render_banner(
        model=cfg.model,
        provider=cfg.provider,
        connection_status=status_str,
        workspace=str(Path.cwd()),
    )

    while True:
        try:
            user_input = ui.components.ask_input("code68> ")
            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                cmd_parts = user_input.strip().split()
                cmd = cmd_parts[0].lower()

                if cmd in ("/exit", "/quit", "/q"):
                    ui.renderer.render_success("Goodbye!")
                    break

                elif cmd in ("/help", "/h"):
                    _show_help(ui)
                    continue

                elif cmd == "/clear":
                    agent.clear()
                    ui.renderer.render_success("Conversation context cleared.")
                    continue

                elif cmd == "/compact":
                    count = agent.compact()
                    ui.renderer.render_success(f"Compacted conversation ({count} messages pruned).")
                    continue

                elif cmd == "/status":
                    await _show_status(agent, ui, cfg)
                    continue

                elif cmd == "/model":
                    if len(cmd_parts) > 1:
                        new_model = cmd_parts[1]
                        cfg.model = new_model
                        agent.config.model = new_model
                        agent.llm_provider.model = new_model
                        ui.renderer.render_success(f"Model switched to: {new_model}")
                    else:
                        ui.print(f"Current model: [bold cyan]{cfg.model}[/bold cyan]")
                    continue

                elif cmd == "/diff":
                    diff_res = await agent.tool_registry.execute("git_diff", {})
                    ui.renderer.render_markdown(diff_res)
                    continue

                elif cmd == "/undo":
                    confirmed = ui.components.confirm(
                        "Are you sure you want to revert uncommitted changes? (git checkout .)",
                        default=False,
                    )
                    if confirmed:
                        ui.print("[yellow]Reverting unstaged changes...[/yellow]")
                        run_res = await agent.tool_registry.execute("run_command", {"command": "git checkout ."})
                        ui.print(run_res)
                    else:
                        ui.print("[dim]Undo cancelled.[/dim]")
                    continue

                elif cmd == "/sessions":
                    sessions = agent.session_manager.list_sessions()
                    if not sessions:
                        ui.print("[dim]No saved sessions found in this workspace.[/dim]")
                    else:
                        table = Table(title="Saved Sessions", border_style="cyan")
                        table.add_column("Session ID", style="bold green")
                        table.add_column("Created At")
                        table.add_column("Messages")
                        for s in sessions:
                            table.add_row(s["session_id"], s.get("created_at", "N/A"), str(s["message_count"]))
                        ui.print(table)
                    continue

                elif cmd == "/save":
                    sid = cmd_parts[1] if len(cmd_parts) > 1 else None
                    msg = agent.save_session(sid)
                    ui.renderer.render_success(msg)
                    continue

                elif cmd == "/resume":
                    if len(cmd_parts) < 2:
                        ui.renderer.render_warning("Usage: /resume <session_id>")
                    else:
                        sid = cmd_parts[1]
                        if agent.load_session(sid):
                            ui.renderer.render_success(f"Resumed session '{sid}'.")
                        else:
                            ui.renderer.render_error(f"Session '{sid}' not found.")
                    continue

                else:
                    ui.renderer.render_warning(f"Unknown slash command: {cmd}. Type /help for options.")
                    continue

            # Execute user prompt
            await agent.execute(user_input, stream=True)

        except (KeyboardInterrupt, EOFError):
            ui.print("\nSession interrupted. Type /exit to quit.")
        except Exception as e:
            ui.renderer.render_error(f"Error during execution: {e}")


def _show_help(ui: TerminalUI) -> None:
    """Display interactive commands help."""
    table = Table(title="Code68 Interactive Commands", border_style="bright_blue")
    table.add_column("Command", style="cyan bold")
    table.add_column("Description")
    table.add_row("/help", "Show this help table")
    table.add_row("/clear", "Clear conversation history")
    table.add_row("/compact", "Compact conversation context to stay within token limits")
    table.add_row("/model [name]", "View or switch active model")
    table.add_row("/status", "Show connection, workspace, and model details")
    table.add_row("/diff", "Show git diff of uncommitted changes")
    table.add_row("/undo", "Revert uncommitted file changes")
    table.add_row("/sessions", "List saved conversation sessions")
    table.add_row("/save [id]", "Save current conversation session")
    table.add_row("/resume <id>", "Resume a previously saved session")
    table.add_row("/exit", "Exit Code68")
    ui.print(table)


async def _show_status(agent: Code68Agent, ui: TerminalUI, cfg: Config) -> None:
    """Display current system and connection status."""
    try:
        health = await agent.check_connection()
        conn_text = f"[green]Connected[/green] ({health.get('status')})"
    except Exception as e:
        conn_text = f"[red]Disconnected[/red] ({e})"

    ui.print(f"[bold]LLM Endpoint:[/bold] {cfg.base_url}")
    ui.print(f"[bold]Model:[/bold] {cfg.model}")
    ui.print(f"[bold]Provider:[/bold] {cfg.provider}")
    ui.print(f"[bold]Permission Level:[/bold] {cfg.permission_level.value}")
    ui.print(f"[bold]Connection Status:[/bold] {conn_text}")
    ui.print(f"[bold]Workspace:[/bold] {agent.workspace_root}")


@app.command()
def doctor() -> None:
    """Run health diagnostics on environment, LLM endpoint, git, and tools."""
    ui = TerminalUI()
    ui.print("[bold cyan]Running Code68 System Diagnostics...[/bold cyan]\n")

    table = Table(border_style="cyan")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    table.add_row(
        "Python Runtime",
        "[green]OK[/green]" if py_ok else "[red]FAIL[/red]",
        f"v{py_ver} (Requires >= 3.11)",
    )

    # 2. Git
    git_path = shutil.which("git")
    table.add_row(
        "Git Version Control",
        "[green]OK[/green]" if git_path else "[yellow]NOT FOUND[/yellow]",
        git_path or "Git executable not in PATH",
    )

    # 3. ripgrep
    rg_path = shutil.which("rg")
    table.add_row(
        "ripgrep (rg)",
        "[green]OK[/green]" if rg_path else "[yellow]OPTIONAL[/yellow]",
        rg_path or "Not installed (Pure Python fallback will be used)",
    )

    # 4. LLM endpoint
    cfg = Config.load(Path.cwd())
    agent = Code68Agent(workspace_root=Path.cwd(), config=cfg, ui=ui)
    try:
        asyncio.run(agent.check_connection())
        table.add_row(
            "Cloud LLM Endpoint",
            "[green]CONNECTED[/green]",
            f"{cfg.base_url} (Model: {cfg.model})",
        )
    except Exception as e:
        table.add_row(
            "Cloud LLM Endpoint",
            "[yellow]UNREACHABLE[/yellow]",
            f"Cannot connect to {cfg.base_url}: {e}",
        )

    ui.print(table)


@app.command()
def init() -> None:
    """Initialize Code68 in the current workspace."""
    ws = Path.cwd()
    code68_dir = ws / ".code68"
    code68_dir.mkdir(parents=True, exist_ok=True)
    cfg = Config.load(ws)
    cfg_path = cfg.save(ws / ".code68" / "config.json")
    ui = TerminalUI()
    ui.renderer.render_success(f"Initialized Code68 in '{ws}'. Configuration saved to: {cfg_path}")


@app.command()
def config(
    set_model: Optional[str] = typer.Option(None, "--set-model", help="Set default model"),
    set_url: Optional[str] = typer.Option(None, "--set-url", help="Set base URL"),
    set_key: Optional[str] = typer.Option(None, "--set-key", help="Set API key"),
    set_permission: Optional[str] = typer.Option(
        None, "--set-permission", help="Set permission level"
    ),
    global_cfg: bool = typer.Option(
        False, "--global", "-g", help="Apply to global configuration (~/.code68/config.json)"
    ),
) -> None:
    """View or update Code68 configuration."""
    cfg = Config.load(Path.cwd())
    updated = False

    if set_model:
        cfg.model = set_model
        updated = True
    if set_url:
        cfg.base_url = set_url
        updated = True
    if set_key:
        cfg.api_key = set_key
        updated = True
    if set_permission:
        cfg.permission_level = PermissionLevel(set_permission)
        updated = True

    if updated:
        save_path = cfg.save(global_config=global_cfg)
        typer.echo(f"Configuration saved to {save_path}")
    else:
        typer.echo(cfg.model_dump_json(indent=2))
