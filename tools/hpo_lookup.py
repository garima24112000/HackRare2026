"""
tools/hpo_lookup.py — Map free-text phenotype descriptions to HPO terms.

Owner: WS1 (Data & Retrieval)
"""

from __future__ import annotations
from core.models import HPOMatch


def run(raw_texts: list[str], data: dict) -> list[HPOMatch]:
    """
    Map a list of free-text phenotype descriptions to HPO terms.

    Parameters
    ----------
    raw_texts : list[str]
        Natural-language symptom descriptions extracted from the clinical note.
    data : dict
        The reference-data dict returned by ``core.data_loader.load_all()``.
        Relevant keys: ``"hpo_index"``, ``"synonym_index"``, ``"ic_scores"``.

    Returns
    -------
    list[HPOMatch]
        One ``HPOMatch`` per recognised phenotype, with confidence and IC score.
    """
    raise NotImplementedError("WS1: implement HPO lookup via synonym_index + rapidfuzz")
