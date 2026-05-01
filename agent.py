from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from error_handler import APIError, AgentError, SchemaValidationError, handle_tool_error
from logger import log_info, log_tool_call, log_tool_result
from response_models import AgentResponse, ToolCall
from schemas import GROQ_TOOLS
from tools import calculate, get_current_time, get_weather, search_dictionary, unit_converter

SYSTEM_PROMPT = (
    "You are helpful, precise assistant with tools for weather, math, dictionary, time, unit conversion. "
    "Always use tools when request needs real data. "
    "For time queries, always pass explicit IANA timezone when user gives location (example: Istanbul -> Europe/Istanbul). "
    "For unit conversion, normalize common aliases and use unit_converter tool exactly. "
    "When tool returns error, explain clearly and retry once with corrected normalized params if possible. "
    "Never fabricate data that tool should provide."
)

_TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
    "search_dictionary": search_dictionary,
    "get_current_time": get_current_time,
    "unit_converter": unit_converter,
}

_SCHEMA_BY_NAME = {t["function"]["name"]: t["function"]["parameters"] for t in GROQ_TOOLS}


class ToolCallingAgent:
    """Groq tool-calling agent with multi-round execution loop."""

    def __init__(
        self,
        model: str = "llama-3.1-8b-instant",
        max_tokens: int = 4096,
        max_tool_rounds: int = 10,
    ) -> None:
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise AgentError("GROQ_API_KEY is missing. Add it to your .env file.")

        self.client = Groq(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.max_tool_rounds = max_tool_rounds
        self.conversation_history: list[dict[str, Any]] = []

    def run(self, user_message: str) -> AgentResponse:
        """Execute full tool-calling loop and return structured response."""
        self.conversation_history.append({"role": "user", "content": user_message})
        tools_called: list[ToolCall] = []
        total_in = 0
        total_out = 0
        rounds = 0

        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history,
                    tools=GROQ_TOOLS,
                    max_tokens=self.max_tokens,
                )
            except Exception as exc:
                raise APIError(f"Groq API call failed: {exc}") from exc

            usage = response.usage
            if usage:
                total_in += usage.prompt_tokens or 0
                total_out += usage.completion_tokens or 0

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            message = choice.message

            if finish_reason == "stop":
                assistant_text = message.content or ""
                return AgentResponse(
                    user_message=user_message,
                    assistant_text=assistant_text,
                    tools_called=tools_called,
                    total_input_tokens=total_in,
                    total_output_tokens=total_out,
                    stop_reason=finish_reason,
                    timestamp=datetime.now(timezone.utc),
                )
            if finish_reason == "length":
                raise AgentError("Model output hit token limit. Try a shorter or narrower request.")
            if finish_reason != "tool_calls":
                raise AgentError(f"Unexpected finish_reason: {finish_reason}")

            rounds += 1
            if rounds > self.max_tool_rounds:
                raise AgentError("Max tool rounds exceeded.")

            tool_calls = message.tool_calls or []
            if not tool_calls:
                raise AgentError("finish_reason is tool_calls but tool_calls is empty.")

            assistant_entry = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
            self.conversation_history.append(assistant_entry)

            for tc in tool_calls:
                tool_name = tc.function.name
                raw_args = tc.function.arguments or "{}"

                try:
                    tool_input = json.loads(raw_args)
                except json.JSONDecodeError as exc:
                    err = handle_tool_error(tool_name, SchemaValidationError(f"Invalid JSON arguments: {exc}"))
                    tools_called.append(
                        ToolCall(
                            tool_name=tool_name,
                            tool_input={"raw": raw_args},
                            tool_result=None,
                            error=err,
                            execution_time_ms=0.0,
                        )
                    )
                    self.conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tool_name,
                            "content": json.dumps(err),
                        }
                    )
                    continue

                started = time.perf_counter()
                log_tool_call(tool_name, tool_input)

                try:
                    if tool_name == "get_current_time" and "timezone" not in tool_input:
                        user_low = user_message.lower()
                        if "istanbul" in user_low:
                            tool_input = {**tool_input, "timezone": "Europe/Istanbul"}

                    self._validate_input(tool_name, tool_input)
                    fn = _TOOL_FUNCTIONS.get(tool_name)
                    if fn is None:
                        raise SchemaValidationError(f"Unknown tool: {tool_name}")
                    tool_result = fn(**tool_input)
                    duration = (time.perf_counter() - started) * 1000
                    log_tool_result(tool_name, tool_result)
                    tools_called.append(
                        ToolCall(
                            tool_name=tool_name,
                            tool_input=tool_input,
                            tool_result=tool_result,
                            error=None,
                            execution_time_ms=duration,
                        )
                    )
                    self.conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tool_name,
                            "content": json.dumps(tool_result),
                        }
                    )
                except Exception as exc:
                    duration = (time.perf_counter() - started) * 1000
                    err = handle_tool_error(tool_name, exc)
                    tools_called.append(
                        ToolCall(
                            tool_name=tool_name,
                            tool_input=tool_input,
                            tool_result=None,
                            error=err,
                            execution_time_ms=duration,
                        )
                    )
                    self.conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tool_name,
                            "content": json.dumps(err),
                        }
                    )

            log_info("Tool round complete, requesting model synthesis.")

    def reset_conversation(self) -> None:
        """Clear stored conversation history."""
        self.conversation_history = []

    def get_conversation_summary(self) -> dict:
        """Return simple conversation summary metrics."""
        total_turns = sum(1 for m in self.conversation_history if m.get("role") == "user")
        tool_calls = 0
        tools: set[str] = set()

        for m in self.conversation_history:
            if m.get("role") == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    tool_calls += 1
                    fn = tc.get("function", {}).get("name")
                    if fn:
                        tools.add(fn)

        return {
            "total_turns": total_turns,
            "total_tool_calls": tool_calls,
            "unique_tools_used": sorted(tools),
        }

    def _validate_input(self, tool_name: str, payload: dict) -> None:
        schema = _SCHEMA_BY_NAME.get(tool_name)
        if schema is None:
            raise SchemaValidationError(f"No schema found for tool '{tool_name}'.")

        props = schema.get("properties", {})
        required = schema.get("required", [])

        for req in required:
            if req not in payload:
                raise SchemaValidationError(f"Missing required field '{req}' for {tool_name}.")

        for key, value in payload.items():
            if key not in props:
                raise SchemaValidationError(f"Unknown field '{key}' for {tool_name}.")
            self._validate_type(tool_name, key, value, props[key])

    def _validate_type(self, tool_name: str, key: str, value: Any, rule: dict) -> None:
        t = rule.get("type")
        if t == "string" and not isinstance(value, str):
            raise SchemaValidationError(f"Field '{key}' for {tool_name} must be string.")
        if t == "integer" and not isinstance(value, int):
            raise SchemaValidationError(f"Field '{key}' for {tool_name} must be integer.")
        if t == "number" and not isinstance(value, (int, float)):
            raise SchemaValidationError(f"Field '{key}' for {tool_name} must be number.")

        enum = rule.get("enum")
        if enum and value not in enum:
            raise SchemaValidationError(f"Field '{key}' for {tool_name} must be one of {enum}.")
