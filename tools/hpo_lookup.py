"""
tools/hpo_lookup.py — Map free-text phenotype descriptions to HPO terms.

Owner: WS1 (Data & Retrieval)

Pure programmatic — no LLM calls. Uses exact match on synonym_index,
then falls back to rapidfuzz for fuzzy matching.
"""

from __future__ import annotations

import re

from rapidfuzz import process as rfprocess

from core.models import HPOMatch


_HP_PATTERN = re.compile(r"^HP:\d{7}$")


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
        One ``HPOMatch`` per input text, with confidence and IC score.
    """
    hpo_index: dict = data["hpo_index"]
    synonym_index: dict = data["synonym_index"]
    # Pre-build the list of synonym keys once for rapidfuzz
    syn_keys: list[str] = list(synonym_index.keys())

    results: list[HPOMatch] = []

    for raw in raw_texts:
        normalized = raw.strip().lower()

        # ------------------------------------------------------------------
        # Direct HPO ID input (e.g. "HP:0001250")
        # ------------------------------------------------------------------
        if _HP_PATTERN.match(raw.strip()):
            hpo_id = raw.strip()
            if hpo_id in hpo_index:
                doc = hpo_index[hpo_id]
                results.append(HPOMatch(
                    hpo_id=hpo_id,
                    label=doc.get("label", ""),
                    definition=doc.get("definition"),
                    ic_score=data["ic_scores"].get(hpo_id, 0.0),
                    parents=doc.get("parents", []),
                    match_confidence="high",
                    raw_input=raw,
                ))
            else:
                # Unknown HPO ID — still record it
                results.append(HPOMatch(
                    hpo_id="",
                    label="",
                    match_confidence="low",
                    raw_input=raw,
                ))
            continue

        # ------------------------------------------------------------------
        # Exact match in synonym_index
        # ------------------------------------------------------------------
        if normalized in synonym_index:
            hpo_id = synonym_index[normalized]
            doc = hpo_index.get(hpo_id, {})
            results.append(HPOMatch(
                hpo_id=hpo_id,
                label=doc.get("label", ""),
                definition=doc.get("definition"),
                ic_score=data["ic_scores"].get(hpo_id, 0.0),
                parents=doc.get("parents", []),
                match_confidence="high",
                raw_input=raw,
            ))
            continue

        # ------------------------------------------------------------------
        # Fuzzy match via rapidfuzz
        # ------------------------------------------------------------------
        match = rfprocess.extractOne(normalized, syn_keys, score_cutoff=75)
        if match:
            matched_str, score, _ = match
            hpo_id = synonym_index[matched_str]
            doc = hpo_index.get(hpo_id, {})

            if score >= 85:
                conf = "high"
            elif score >= 75:
                conf = "medium"
            else:
                conf = "low"

            results.append(HPOMatch(
                hpo_id=hpo_id,
                label=doc.get("label", ""),
                definition=doc.get("definition"),
                ic_score=data["ic_scores"].get(hpo_id, 0.0),
                parents=doc.get("parents", []),
                match_confidence=conf,
                raw_input=raw,
            ))
            continue

        # ------------------------------------------------------------------
        # No match at all
        # ------------------------------------------------------------------
        results.append(HPOMatch(
            hpo_id="",
            label="",
            match_confidence="low",
            raw_input=raw,
        ))

    return results
