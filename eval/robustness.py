"""
eval/robustness.py — Robustness / stress tests for the diagnostic pipeline.

Owner: WS4 (Evaluation)

Tests pipeline behaviour under edge cases: missing data, conflicting
phenotypes, unusual input formats, etc.
"""

from __future__ import annotations


def run_robustness_tests(data: dict, session_mgr) -> dict:
    """
    Execute robustness test suite.

    Parameters
    ----------
    data : dict
        Reference-data dict from ``load_all()``.
    session_mgr : SessionManager

    Returns
    -------
    dict
        Test names → pass/fail results and diagnostic info.
    """
    raise NotImplementedError("WS4: implement robustness test suite")
