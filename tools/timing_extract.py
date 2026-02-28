"""
tools/timing_extract.py — Extract phenotype onset and timing from clinical text.

Owner: WS2 (Agent & Reasoning)

Uses the LLM to extract temporal information (onset, progression, resolution)
for each identified phenotype, then normalises onset_stage.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agent.llm_client import call_llm, extract_json
from core.models import TimingProfile

logger = logging.getLogger(__name__)

# ── prompt (loaded once) ────────────────────────────────────────────────
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "agent" / "prompts" / "timing.txt"
_PROMPT_CACHE: str | None = None


def _load_prompt() -> str:
    global _PROMPT_CACHE
    if _PROMPT_CACHE is None:
        _PROMPT_CACHE = _PROMPT_PATH.read_text(encoding="utf-8")
    return _PROMPT_CACHE


# ── onset_stage normalisation ───────────────────────────────────────────

def _normalise_onset_stage(onset_normalized: float) -> str:
    """Map a decimal-year onset value to a named developmental stage."""
    if onset_normalized <= 0.0:
        return "Congenital/Neonatal"
    if onset_normalized <= 1.0:
        return "Infantile"
    if onset_normalized <= 5.0:
        return "Childhood"
    if onset_normalized <= 15.0:
        return "Juvenile"
    return "Adult"


# ── public API ──────────────────────────────────────────────────────────

def run(note_text: str, hpo_labels: list[str]) -> list[TimingProfile]:
    """
    Extract temporal information (onset, progression, resolution) for phenotypes.

    Parameters
    ----------
    note_text : str
        The raw clinical note text.
    hpo_labels : list[str]
        Human-readable labels of already-matched HPO terms, used to anchor
        timing extraction.

    Returns
    -------
    list[TimingProfile]
        One entry per phenotype for which temporal data was found.
    """
    if not note_text or not note_text.strip():
        return []
    if not hpo_labels:
        return []

    # Build augmented system prompt with the phenotype list
    base_prompt = _load_prompt()
    phenotype_list = "\n".join(f"- {label}" for label in hpo_labels)
    system_prompt = (
        base_prompt
        + "\n\nPhenotypes to extract timing for:\n"
        + phenotype_list
    )

    # LLM call
    try:
        raw_response = call_llm(system=system_prompt, user=note_text)
    except Exception:
        logger.exception("LLM call failed in timing_extract")
        return []

    # Parse JSON
    try:
        items = extract_json(raw_response)
    except json.JSONDecodeError:
        logger.warning("Failed to parse timing_extract LLM response: %s", raw_response[:500])
        return []

    if not isinstance(items, list):
        logger.warning("Expected JSON array from timing_extract, got %s", type(items).__name__)
        return []

    # Build TimingProfile objects
    results: list[TimingProfile] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        onset_norm = float(item.get("onset_normalized", 0.0))
        onset_stage = _normalise_onset_stage(onset_norm)
        phenotype_ref = item.get("phenotype_ref", "")

        try:
            tp = TimingProfile(
                phenotype_ref=phenotype_ref,
                phenotype_label=phenotype_ref,  # LLM returns label as ref
                onset=item.get("onset", "unknown"),
                onset_normalized=onset_norm,
                onset_stage=onset_stage,
                resolution=item.get("resolution"),
                is_ongoing=item.get("is_ongoing", True),
                progression=item.get("progression", "stable"),
                raw_evidence=item.get("raw_evidence", ""),
                confidence=item.get("confidence", "medium"),
            )
            results.append(tp)
        except Exception:
            logger.warning("Skipping malformed timing item: %s", item)

    return results
