"""
tools/orphanet_fetch.py — Fetch detailed disease profiles from pre-loaded
Orphanet/OMIM data.

Owner: WS1 (Data & Retrieval)

Simple dict lookup — all heavy work was done in the ingestion scripts.
"""

from __future__ import annotations

from core.models import DiseaseProfile, PhenotypeFrequency


def run(disease_ids: list[str], data: dict) -> list[DiseaseProfile]:
    """
    Retrieve rich disease profiles (genes, inheritance, phenotype frequencies).

    Parameters
    ----------
    disease_ids : list[str]
        Disease identifiers to look up (e.g. ``["ORPHA:558", "OMIM:101200"]``).
    data : dict
        Reference-data dict from ``load_all()``.
        Relevant keys: ``"orphanet_profiles"``, ``"disease_to_name"``.

    Returns
    -------
    list[DiseaseProfile]
        One profile per disease ID requested. Missing Orphanet data returns
        a minimal profile with just name and empty lists.
    """
    orphanet_profiles: dict = data.get("orphanet_profiles", {})
    disease_to_name: dict = data.get("disease_to_name", {})

    results: list[DiseaseProfile] = []

    for did in disease_ids:
        orphanet_data = orphanet_profiles.get(did)

        if orphanet_data and isinstance(orphanet_data, dict):
            # Build phenotype frequency sub-models
            pheno_freqs = []
            for assoc in orphanet_data.get("hpo_associations", []):
                pheno_freqs.append(PhenotypeFrequency(
                    hpo_id=assoc.get("hpo_id", ""),
                    label=assoc.get("label", ""),
                    frequency=assoc.get("frequency", "Unknown"),
                ))

            results.append(DiseaseProfile(
                disease_id=did,
                disease_name=orphanet_data.get("name", disease_to_name.get(did, "")),
                inheritance=orphanet_data.get("inheritance"),
                causal_genes=orphanet_data.get("genes", []),
                phenotype_freqs=pheno_freqs,
                recommended_tests=orphanet_data.get("recommended_tests", []),
            ))
        else:
            # No Orphanet data — return minimal profile
            results.append(DiseaseProfile(
                disease_id=did,
                disease_name=disease_to_name.get(did, ""),
            ))

    return results
