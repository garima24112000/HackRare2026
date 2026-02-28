"""
tools/red_flag.py — Detect urgent / concerning phenotype combinations.

Owner: WS1 (Data & Retrieval)
"""

from __future__ import annotations
from core.models import RedFlag


def run(patient_hpo_ids: list[str], ontology) -> list[RedFlag]:
    """
    Screen for red-flag phenotype combinations that warrant urgent action.

    Parameters
    ----------
    patient_hpo_ids : list[str]
        HPO IDs observed in the patient.
    ontology : pronto.Ontology
        The parsed ``hp.obo`` ontology object (``data["ontology"]``).

    Returns
    -------
    list[RedFlag]
        Each flag includes severity, triggering terms, and a recommended action.
    """
    raise NotImplementedError("WS1: implement red-flag rule engine")
