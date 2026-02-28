"""
eval/gold_cases.py — Gold-standard test cases for pipeline evaluation.

Owner: WS4 (Evaluation)

Provides reference cases with known diagnoses for scoring the pipeline.
"""

from __future__ import annotations


def load_gold_cases(db) -> list[dict]:
    """
    Load gold-standard evaluation cases from MongoDB ``eval_gold_cases`` collection.

    Parameters
    ----------
    db : pymongo.database.Database
        The MongoDB database handle.

    Returns
    -------
    list[dict]
        Each dict has at minimum:
        - ``"patient_input"`` : dict matching PatientInput schema
        - ``"expected_disease_ids"`` : list[str]
        - ``"expected_hpo_ids"`` : list[str]
    """
    raise NotImplementedError("WS4: implement gold-case loader from MongoDB")
