"""
agent/llm_client.py — Shared LLM client for all LLM-powered tools.

Every LLM call in WS2 flows through this module.  If the provider changes,
only this file needs updating.

Uses the standard OpenAI SDK against Azure AI Foundry (MaaS) endpoints.

Owner: WS2
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

from openai import OpenAI

from core.config import (
    AZURE_API_KEY,
    AZURE_DEPLOYMENT,
    AZURE_ENDPOINT,
)

logger = logging.getLogger(__name__)


# ── Client singleton ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """Return a cached :class:`OpenAI` client pointing at Azure AI Foundry."""
    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        raise RuntimeError(
            "AZURE_ENDPOINT and AZURE_API_KEY must be set in the environment. "
            "Copy .env.example to .env and fill in the values."
        )
    logger.info("LLM client → base_url=%s  model=%s", AZURE_ENDPOINT, AZURE_DEPLOYMENT)
    return OpenAI(
        base_url=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
        max_retries=5,          # handle 429s from S0 tier token-rate limits
    )


# ── JSON extraction helpers ─────────────────────────────────────────────────


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json … ``` wrappers that LLMs sometimes add."""
    text = text.strip()
    # Strip leading ```json or ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    # Strip trailing ```
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON value from *text*.

    1. Try direct ``json.loads`` on the stripped text.
    2. Try after stripping markdown code fences.
    3. Try extracting the first top-level ``[…]`` or ``{…}`` substring.
    4. Try repairing truncated JSON (common with reasoning models).
    5. Raise ``json.JSONDecodeError`` if all attempts fail.
    """
    text = text.strip()

    # Attempt 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip markdown fences
    cleaned = _strip_markdown_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 3: find outermost JSON structure
    # Try both brackets, pick the one that starts earliest (or spans more)
    candidates: list[tuple[int, int]] = []
    for open_ch, close_ch in [("[", "]"), ("{", "}")]:
        start = cleaned.find(open_ch)
        end = cleaned.rfind(close_ch)
        if start != -1 and end > start:
            candidates.append((start, end))

    # Sort by earliest start, then widest span
    candidates.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    for start, end in candidates:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            continue

    # Attempt 4: repair truncated JSON — find the deepest valid prefix.
    # This handles responses cut off at max_tokens.
    first_brace = cleaned.find("{")
    if first_brace != -1:
        fragment = cleaned[first_brace:]
        repaired = _repair_truncated_json(fragment)
        if repaired is not None:
            logger.info("Recovered truncated JSON (%d → %d chars)", len(fragment), len(repaired))
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

    logger.warning("No valid JSON found in LLM response. First 300 chars: %s", text[:300])
    raise json.JSONDecodeError("No valid JSON found in LLM response", text, 0)


def _repair_truncated_json(fragment: str) -> str | None:
    """Try to close open brackets/braces for a truncated JSON string.

    Works by counting nesting depth and trimming to the last complete
    value, then appending the necessary closing characters.
    """
    # Walk backwards to find the last complete value boundary
    # (after a comma, colon at the right nesting level)
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escape = False
    last_safe = -1

    for i, ch in enumerate(fragment):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
            if depth_brace >= 0:
                last_safe = i
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
            if depth_bracket >= 0:
                last_safe = i

    if last_safe <= 0:
        return None

    # Trim to last_safe and close all open brackets/braces
    trimmed = fragment[: last_safe + 1]
    # Count remaining open brackets
    open_braces = 0
    open_brackets = 0
    in_str = False
    esc = False
    for ch in trimmed:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            open_braces += 1
        elif ch == "}":
            open_braces -= 1
        elif ch == "[":
            open_brackets += 1
        elif ch == "]":
            open_brackets -= 1

    closing = "]" * open_brackets + "}" * open_braces
    return trimmed + closing


# ── Core LLM call (simple: system + user → text) ───────────────────────────


def call_llm(
    system: str,
    user: str,
    *,
    max_tokens: int = 8192,
    temperature: float = 0.2,
) -> str:
    """Send a chat completion and return the assistant's text content.

    Handles reasoning models (like Grok) that may put chain-of-thought
    in ``reasoning_content`` and the final answer in ``content``.
    """
    client = get_client()
    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    msg = response.choices[0].message
    content = msg.content or ""

    # Reasoning models may return empty content with reasoning_content
    if not content.strip():
        reasoning = getattr(msg, "reasoning_content", None) or ""
        if reasoning:
            logger.debug("Content empty; falling back to reasoning_content (%d chars)", len(reasoning))
            content = reasoning

    if not content.strip():
        logger.warning("LLM returned empty response. finish_reason=%s",
                       response.choices[0].finish_reason)

    return content
