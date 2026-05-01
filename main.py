from __future__ import annotations

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from agent import ToolCallingAgent
from error_handler import AgentError
from logger import console, log_assistant, log_error, log_info, log_user


def show_banner() -> None:
    console.print(
        Panel(
            "Tool-Calling AI Agent\n"
            "Tools: weather, calculate, dictionary, time, unit-converter\n"
            "Commands: /reset /history /stats /quit",
            title="Groq Agent",
            expand=False,
        )
    )


def show_history(agent: ToolCallingAgent) -> None:
    entries = agent.conversation_history[-10:]
    if not entries:
        log_info("No conversation history.")
        return
    for item in entries:
        role = item.get("role", "unknown")
        content = item.get("content", "")
        if isinstance(content, list):
            content = str(content)
        console.print(f"[{role}] {content}")


def show_stats(agent: ToolCallingAgent) -> None:
    summary = agent.get_conversation_summary()
    table = Table(title="Conversation Stats")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Total turns", str(summary["total_turns"]))
    table.add_row("Total tool calls", str(summary["total_tool_calls"]))
    table.add_row("Unique tools", ", ".join(summary["unique_tools_used"]) or "-")
    console.print(table)


def main() -> None:
    show_banner()

    try:
        agent = ToolCallingAgent()
    except AgentError as exc:
        log_error(str(exc))
        return

    while True:
        try:
            user_input = Prompt.ask("> ").strip()
            if not user_input:
                continue

            if user_input == "/quit":
                log_info("Goodbye!")
                break
            if user_input == "/reset":
                agent.reset_conversation()
                log_info("Conversation reset.")
                continue
            if user_input == "/history":
                show_history(agent)
                continue
            if user_input == "/stats":
                show_stats(agent)
                continue

            log_user(user_input)
            result = agent.run(user_input)
            log_assistant(result.assistant_text)
            if result.tools_called:
                tools = ", ".join(tc.tool_name for tc in result.tools_called)
                log_info(
                    f"Tools used: {tools} | Tokens: {result.total_input_tokens} in / {result.total_output_tokens} out"
                )

        except KeyboardInterrupt:
            log_info("\nGoodbye!")
            break
        except AgentError as exc:
            log_error(str(exc))
        except Exception as exc:
            log_error(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
