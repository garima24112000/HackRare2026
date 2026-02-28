"""
tools/orphanet_fetch.py — Fetch detailed disease profiles from Orphanet/OMIM data.

Owner: WS1 (Data & Retrieval)
"""

from __future__ import annotations
from core.models import DiseaseProfile


def run(disease_ids: list[str], data: dict) -> list[DiseaseProfile]:
    """
    Retrieve rich disease profiles (genes, inheritance, phenotype frequencies).

    Parameters
    ----------
    disease_ids : list[str]
        Disease identifiers to look up (e.g. ``["ORPHA:558", "OMIM:101200"]``).
    data : dict
        Reference-data dict from ``load_all()``.
        Relevant key: ``"orphanet_profiles"``.

    Returns
    -------
    list[DiseaseProfile]
        One profile per disease found; missing IDs are silently skipped.
    """
    raise NotImplementedError("WS1: implement Orphanet/OMIM profile lookup")
