"""
tools/excluded_extract.py — Extract negated / excluded phenotypes from clinical text.

Owner: WS2 (Agent & Reasoning)

Uses the LLM to identify negated findings in clinical notes, then maps them
to HPO terms via the synonym_index + rapidfuzz fallback.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rapidfuzz import process as rfuzz_process

from agent.llm_client import call_llm, extract_json
from core.models import ExcludedFinding

logger = logging.getLogger(__name__)

# ── prompt (loaded once) ────────────────────────────────────────────────
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "agent" / "prompts" / "excluded.txt"
_PROMPT_CACHE: str | None = None


def _load_prompt() -> str:
    global _PROMPT_CACHE
    if _PROMPT_CACHE is None:
        _PROMPT_CACHE = _PROMPT_PATH.read_text(encoding="utf-8")
    return _PROMPT_CACHE


# ── HPO mapping helpers ─────────────────────────────────────────────────

def _map_to_hpo(
    finding: str,
    synonym_index: dict,
) -> tuple[str | None, str | None]:
    """Return (hpo_id, hpo_label) or (None, None) for *finding*."""
    key = finding.strip().lower()

    # 1. Exact match
    if key in synonym_index:
        hpo_id = synonym_index[key]
        return hpo_id, key  # label stored as key itself

    # 2. Fuzzy match via rapidfuzz
    if synonym_index:
        result = rfuzz_process.extractOne(
            key,
            synonym_index.keys(),
            score_cutoff=80,
        )
        if result:
            matched_synonym, _score, _idx = result
            hpo_id = synonym_index[matched_synonym]
            return hpo_id, matched_synonym

    return None, None


# ── public API ──────────────────────────────────────────────────────────

def run(note_text: str, synonym_index: dict) -> list[ExcludedFinding]:
    """
    Identify phenotypic findings that are explicitly or softly excluded.

    Parameters
    ----------
    note_text : str
        The raw clinical note text.
    synonym_index : dict
        Lowercase synonym → HPO ID mapping from ``data["synonym_index"]``.

    Returns
    -------
    list[ExcludedFinding]
        Each finding includes the raw negation phrase, mapped HPO term,
        exclusion type (explicit vs soft), and confidence.
    """
    if not note_text or not note_text.strip():
        return []

    prompt = _load_prompt()

    # LLM call
    try:
        raw_response = call_llm(system=prompt, user=note_text)
    except Exception:
        logger.exception("LLM call failed in excluded_extract")
        return []

    # Parse JSON
    try:
        items = extract_json(raw_response)
    except json.JSONDecodeError:
        logger.warning("Failed to parse excluded_extract LLM response: %s", raw_response[:500])
        return []

    if not isinstance(items, list):
        logger.warning("Expected JSON array from excluded_extract, got %s", type(items).__name__)
        return []

    # Build ExcludedFinding objects
    results: list[ExcludedFinding] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        finding_text = item.get("finding", "")
        hpo_id, hpo_label = _map_to_hpo(finding_text, synonym_index)

        try:
            ef = ExcludedFinding(
                raw_text=item.get("raw_text", ""),
                mapped_hpo_term=hpo_id,
                mapped_hpo_label=hpo_label,
                exclusion_type=item.get("exclusion_type", "explicit"),
                confidence=item.get("confidence", "medium"),
            )
            results.append(ef)
        except Exception:
            logger.warning("Skipping malformed excluded finding: %s", item)

    return results
