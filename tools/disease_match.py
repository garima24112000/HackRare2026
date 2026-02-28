"""
tools/disease_match.py — Match patient HPO terms against disease profiles.

Owner: WS1 (Data & Retrieval)
"""

from __future__ import annotations
from core.models import DiseaseCandidate


def run(
    patient_hpo_ids: list[str],
    excluded_hpo_ids: list[str],
    data: dict,
) -> list[DiseaseCandidate]:
    """
    Score and rank diseases by semantic similarity to the patient's phenotype.

    Parameters
    ----------
    patient_hpo_ids : list[str]
        HPO IDs observed in the patient (e.g. ``["HP:0001250", ...]``).
    excluded_hpo_ids : list[str]
        HPO IDs explicitly excluded / negated.
    data : dict
        Reference-data dict from ``load_all()``.  Relevant keys:
        ``"disease_to_hpo"``, ``"disease_ancestors"``, ``"ic_scores"``,
        ``"disease_to_name"``.

    Returns
    -------
    list[DiseaseCandidate]
        Top 15 candidates sorted by ``sim_score`` descending.
    """
    raise NotImplementedError("WS1: implement IC-weighted Jaccard disease matching")
