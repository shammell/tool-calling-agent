from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ToolCall(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    tool_input: dict
    tool_result: dict | None
    error: dict | None
    execution_time_ms: float


class AgentResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_message: str
    assistant_text: str
    tools_called: list[ToolCall]
    total_input_tokens: int
    total_output_tokens: int
    stop_reason: str
    timestamp: datetime
