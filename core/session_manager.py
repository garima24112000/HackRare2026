"""
core/session_manager.py — Redis-backed session operations.

Owner: WS1 (Data & Retrieval)

Manages per-conversation state: tool-call logs, running context,
and final output caching.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis

logger = logging.getLogger(__name__)


class SessionManager:
    """Thin wrapper around Redis for per-session state."""

    TTL: int = 3600  # 1 hour

    def __init__(self, redis_url: str) -> None:
        """
        Connect to Redis.

        Parameters
        ----------
        redis_url : str
            Full Redis connection string (e.g. ``redis://default:pw@host:port``).
        """
        self._r = redis.from_url(redis_url, decode_responses=True)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, session_id: str, raw_input: dict) -> None:
        """Create a new session entry with the original user input."""
        key = f"session:{session_id}:input"
        try:
            self._r.set(key, json.dumps(raw_input), ex=self.TTL)
        except Exception as exc:
            logger.error("Redis create_session failed: %s", exc)

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
        key = f"session:{session_id}:tools"
        record = {
            "tool_name": tool_name,
            "input_data": input_data,
            "output_data": output_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._r.rpush(key, json.dumps(record, default=str))
            self._r.expire(key, self.TTL)
        except Exception as exc:
            logger.error("Redis log_tool_call failed: %s", exc)

    def get_tool_log(self, session_id: str) -> list[dict]:
        """Return every tool-call record for the session in order."""
        key = f"session:{session_id}:tools"
        try:
            raw_list = self._r.lrange(key, 0, -1)
            return [json.loads(item) for item in raw_list]
        except Exception as exc:
            logger.error("Redis get_tool_log failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Context (intermediate pipeline state)
    # ------------------------------------------------------------------

    def set_context(self, session_id: str, context: dict) -> None:
        """Store / overwrite the running pipeline context."""
        key = f"session:{session_id}:context"
        try:
            self._r.set(key, json.dumps(context, default=str), ex=self.TTL)
        except Exception as exc:
            logger.error("Redis set_context failed: %s", exc)

    def get_context(self, session_id: str) -> dict | None:
        """Retrieve the running pipeline context, or ``None``."""
        key = f"session:{session_id}:context"
        try:
            raw = self._r.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.error("Redis get_context failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Final output
    # ------------------------------------------------------------------

    def set_output(self, session_id: str, output: dict) -> None:
        """Cache the final AgentOutput (serialised as dict)."""
        key = f"session:{session_id}:output"
        try:
            self._r.set(key, json.dumps(output, default=str), ex=self.TTL)
        except Exception as exc:
            logger.error("Redis set_output failed: %s", exc)
