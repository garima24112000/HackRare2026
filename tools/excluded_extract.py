"""
tools/excluded_extract.py — Extract negated / excluded phenotypes from clinical text.

Owner: WS2 (Agent & Reasoning)
"""

from __future__ import annotations
from core.models import ExcludedFinding


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
    raise NotImplementedError("WS2: implement excluded-phenotype extraction via LLM")
