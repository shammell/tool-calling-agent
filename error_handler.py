from __future__ import annotations

from datetime import datetime, timezone
import traceback
from pydantic import BaseModel, ConfigDict

from logger import log_error


class AgentError(Exception):
    """Base exception for agent failures."""


class ToolError(AgentError):
    """Raised when a tool execution fails."""


class SchemaValidationError(AgentError):
    """Raised when tool input validation fails."""


class APIError(AgentError):
    """Raised when Groq API interaction fails."""


class NetworkError(AgentError):
    """Raised when network calls fail."""


class ToolErrorResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    error_type: str
    error_message: str
    suggestion: str
    timestamp: datetime


def handle_tool_error(tool_name: str, exception: Exception) -> dict:
    """Convert exceptions to structured tool error response."""
    if isinstance(exception, SchemaValidationError):
        suggestion = "Check required fields and value types for this tool call."
    elif isinstance(exception, NetworkError):
        suggestion = "Check internet connectivity or retry shortly."
    elif isinstance(exception, ToolError):
        suggestion = "Review tool input values and try again with valid parameters."
    elif isinstance(exception, APIError):
        suggestion = "Check GROQ_API_KEY and model configuration, then retry."
    else:
        suggestion = "Try again. If it persists, inspect logs for details."

    log_error(
        f"Tool '{tool_name}' failed: {exception}",
        traceback.format_exc(),
    )

    payload = ToolErrorResponse(
        tool_name=tool_name,
        error_type=exception.__class__.__name__,
        error_message=str(exception),
        suggestion=suggestion,
        timestamp=datetime.now(timezone.utc),
    )
    return payload.model_dump(mode="json")
