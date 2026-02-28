"""
tools/timing_extract.py — Extract phenotype onset and timing from clinical text.

Owner: WS2 (Agent & Reasoning)
"""

from __future__ import annotations
from core.models import TimingProfile


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
    raise NotImplementedError("WS2: implement timing extraction via LLM")
