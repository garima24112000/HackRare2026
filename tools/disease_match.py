"""
tools/disease_match.py — Match patient HPO terms against disease profiles.

Owner: WS1 (Data & Retrieval)

Core differential diagnosis engine: IC-weighted ancestor-overlap scoring
across all diseases in the database.
"""

from __future__ import annotations

import hpo_functions
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
        ``"disease_to_name"``, ``"ontology"``.

    Returns
    -------
    list[DiseaseCandidate]
        Top 15 candidates sorted by ``sim_score`` descending.
    """
    if not patient_hpo_ids:
        return []

    ontology = data["ontology"]
    ic_scores: dict[str, float] = data["ic_scores"]
    disease_to_hpo: dict[str, set] = data["disease_to_hpo"]
    disease_ancestors: dict[str, set] = data["disease_ancestors"]
    disease_to_name: dict[str, str] = data["disease_to_name"]

    # ------------------------------------------------------------------
    # 1. Build the patient's ancestral set
    # ------------------------------------------------------------------
    patient_ancestors: set[str] = set()
    for hpo_id in patient_hpo_ids:
        try:
            patient_ancestors.update(
                hpo_functions.get_ancestors_up_to_root(ontology, hpo_id)
            )
        except Exception:
            print(f"  [disease_match] WARNING: skipping unknown HPO ID {hpo_id}")

    patient_set = set(patient_hpo_ids)
    excluded_set = set(excluded_hpo_ids) if excluded_hpo_ids else set()

    # ------------------------------------------------------------------
    # 2. Score each disease
    # ------------------------------------------------------------------
    scored: list[tuple[float, str]] = []

    for disease_id, disease_hpo_terms in disease_to_hpo.items():
        d_ancestors = disease_ancestors.get(disease_id, set())

        # IC-weighted overlap of ancestor sets
        overlap = patient_ancestors & d_ancestors
        sim_score = sum(ic_scores.get(t, 0.0) for t in overlap)

        # Direct term overlap
        matched = patient_set & disease_hpo_terms
        missing = disease_hpo_terms - patient_set
        extra = patient_set - disease_hpo_terms
        coverage = len(matched) / len(disease_hpo_terms) if disease_hpo_terms else 0.0

        # Exclusion penalty
        has_penalty = False
        if excluded_set and (excluded_set & disease_hpo_terms):
            has_penalty = True
            sim_score *= 0.5

        scored.append((
            sim_score,
            disease_id,
            matched,
            missing,
            extra,
            coverage,
            has_penalty,
        ))

    # ------------------------------------------------------------------
    # 3. Sort and return top 15
    # ------------------------------------------------------------------
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:15]

    results: list[DiseaseCandidate] = []
    for rank, (score, did, matched, missing, extra, cov, pen) in enumerate(top, 1):
        results.append(DiseaseCandidate(
            rank=rank,
            disease_id=did,
            disease_name=disease_to_name.get(did, ""),
            sim_score=round(score, 4),
            matched_terms=sorted(matched),
            missing_terms=sorted(missing),
            extra_terms=sorted(extra),
            coverage_pct=round(cov, 4),
            excluded_penalty=pen,
        ))

    return results
