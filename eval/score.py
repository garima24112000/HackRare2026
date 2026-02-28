"""
eval/score.py — Score pipeline output against gold-standard cases.

Owner: WS4 (Evaluation)

Computes metrics like top-k accuracy, phenotype recall, etc.
"""

from __future__ import annotations

from core.models import AgentOutput


def score_case(output: AgentOutput, expected: dict) -> dict:
    """
    Score a single pipeline output against a gold-standard expectation.

    Parameters
    ----------
    output : AgentOutput
        The pipeline's complete output.
    expected : dict
        Gold-standard case with ``"expected_disease_ids"``,
        ``"expected_hpo_ids"``, etc.

    Returns
    -------
    dict
        Metric names → values (e.g. ``{"top1_hit": True, "top5_hit": True,
        "hpo_recall": 0.85, ...}``).
    """
    raise NotImplementedError("WS4: implement single-case scoring")


def run_eval(db, data: dict, session_mgr) -> dict:
    """
    Run full evaluation suite: load gold cases, run pipeline on each, aggregate scores.

    Parameters
    ----------
    db : pymongo.database.Database
    data : dict
        Reference-data dict from ``load_all()``.
    session_mgr : SessionManager

    Returns
    -------
    dict
        Aggregated metrics across all gold cases.
    """
    raise NotImplementedError("WS4: implement batch evaluation harness")
