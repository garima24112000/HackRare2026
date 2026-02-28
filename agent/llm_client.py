"""
agent/llm_client.py — Shared Azure OpenAI client for all LLM-powered tools.

Every LLM call in WS2 flows through this module.  If the provider changes,
only this file needs updating.

Owner: WS2
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

from openai import AzureOpenAI

from core.config import (
    AZURE_API_KEY,
    AZURE_API_VERSION,
    AZURE_DEPLOYMENT,
    AZURE_ENDPOINT,
)

logger = logging.getLogger(__name__)

# ── Client singleton ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_client() -> AzureOpenAI:
    """Return a cached :class:`AzureOpenAI` client."""
    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        raise RuntimeError(
            "AZURE_ENDPOINT and AZURE_API_KEY must be set in the environment. "
            "Copy .env.example to .env and fill in the values."
        )
    return AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION,
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
    4. Raise ``json.JSONDecodeError`` if all attempts fail.
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

    raise json.JSONDecodeError("No valid JSON found in LLM response", text, 0)


# ── Core LLM call (simple: system + user → text) ───────────────────────────


def call_llm(
    system: str,
    user: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """Send a chat completion and return the assistant's text content.

    Used by the extraction tools and the final reasoning call.
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
    content = response.choices[0].message.content or ""
    return content
