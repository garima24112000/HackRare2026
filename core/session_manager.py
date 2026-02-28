"""
core/session_manager.py — Redis-backed session operations.

Owner: WS1 (Data & Retrieval)

Manages per-conversation state: tool-call logs, running context,
and final output caching.
"""

from __future__ import annotations
from typing import Any


class SessionManager:
    """Thin wrapper around Redis for per-session state."""

    def __init__(self, redis_url: str) -> None:
        """
        Connect to Redis.

        Parameters
        ----------
        redis_url : str
            Full Redis connection string (e.g. ``redis://default:pw@host:port``).
        """
        raise NotImplementedError("WS1: initialise Redis client from redis_url")

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, session_id: str, raw_input: dict) -> None:
        """Create a new session entry with the original user input."""
        raise NotImplementedError("WS1")

    # ------------------------------------------------------------------
    # Tool call logging
    # ------------------------------------------------------------------

    def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        input_data: dict,
        output_data: dict,
    ) -> None:
        """Append a tool-call record to the session's log list."""
        raise NotImplementedError("WS1")

    def get_tool_log(self, session_id: str) -> list[dict]:
        """Return every tool-call record for the session in order."""
        raise NotImplementedError("WS1")

    # ------------------------------------------------------------------
    # Context (intermediate pipeline state)
    # ------------------------------------------------------------------

    def set_context(self, session_id: str, context: dict) -> None:
        """Store / overwrite the running pipeline context."""
        raise NotImplementedError("WS1")

    def get_context(self, session_id: str) -> dict | None:
        """Retrieve the running pipeline context, or ``None``."""
        raise NotImplementedError("WS1")

    # ------------------------------------------------------------------
    # Final output
    # ------------------------------------------------------------------

    def set_output(self, session_id: str, output: dict) -> None:
        """Cache the final AgentOutput (serialised as dict)."""
        raise NotImplementedError("WS1")
