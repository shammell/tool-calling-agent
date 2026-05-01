from __future__ import annotations

import json
from rich.console import Console

console = Console()
MAX_LOG_OUTPUT_LENGTH = 300


def _safe_text(value: str) -> str:
    return value.encode("cp1252", errors="replace").decode("cp1252")


def log_user(message: str) -> None:
    console.print(f"[bold cyan]You:[/bold cyan] {_safe_text(message)}")


def log_assistant(message: str) -> None:
    console.print(f"[bold green]Assistant:[/bold green] {_safe_text(message)}")


def log_tool_call(tool_name: str, tool_input: dict) -> None:
    console.print(f"[bold yellow]Tool Call:[/bold yellow] {_safe_text(tool_name)}")
    payload = json.dumps(tool_input, indent=2, ensure_ascii=False)
    console.print(_safe_text(payload), style="yellow")


def log_tool_result(tool_name: str, tool_result: dict) -> None:
    rendered = json.dumps(tool_result, ensure_ascii=False)
    if len(rendered) > MAX_LOG_OUTPUT_LENGTH:
        rendered = rendered[:MAX_LOG_OUTPUT_LENGTH] + "..."
    console.print(f"[bold blue]Tool Result:[/bold blue] {_safe_text(tool_name)}")
    console.print(_safe_text(rendered), style="blue")


def log_error(message: str, traceback_text: str | None = None) -> None:
    console.print(f"[bold red]Error:[/bold red] {_safe_text(message)}")
    if traceback_text:
        console.print(_safe_text(traceback_text), style="red")


def log_info(message: str) -> None:
    console.print(f"[dim]{_safe_text(message)}[/dim]")
