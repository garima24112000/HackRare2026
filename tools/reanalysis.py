"""
tools/reanalysis.py — Determine whether a reanalysis is warranted.

Owner: WS2 (Agent & Reasoning) — optional tool
"""

from __future__ import annotations
from core.models import ReanalysisResult


def run(
    prior_tests: list[dict] | None,
    differential: list,
    data: dict,
) -> ReanalysisResult:
    """
    Evaluate whether re-analysis of prior genetic/exome data is warranted.

    Parameters
    ----------
    prior_tests : list[dict] or None
        Previous test results, if any.
    differential : list
        Current differential entries from the pipeline.
    data : dict
        Reference-data dict from ``load_all()``.

    Returns
    -------
    ReanalysisResult
        Score (0–1), recommendation text, and supporting reasons.
    """
    raise NotImplementedError("WS2: implement reanalysis trigger (optional)")
