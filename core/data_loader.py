"""
core/data_loader.py — Startup hydration: load all reference data into memory.

Owner: WS1 (Data & Retrieval)

Called once at app startup. Returns a dict with all indexes and data
that tools need to operate without further DB queries.
"""

from __future__ import annotations

import time
from typing import Any

import pronto


def load_all(db) -> dict[str, Any]:
    """
    Load all reference data from MongoDB into memory.

    Parameters
    ----------
    db : pymongo.database.Database
        The MongoDB database handle (from ``core.database.get_db()``).

    Returns
    -------
    dict with keys:
        - ``"hpo_index"``        : dict  — HPO ID → document
        - ``"synonym_index"``    : dict  — lowercase synonym → HPO ID
        - ``"ic_scores"``        : dict  — HPO ID → information-content float
        - ``"disease_to_hpo"``   : dict  — disease ID → set of HPO IDs
        - ``"disease_ancestors"`` : dict  — disease ID → set of ancestor HPO IDs
        - ``"disease_to_name"``  : dict  — disease ID → human-readable name
        - ``"orphanet_profiles"`` : dict  — disease ID → Orphanet sub-document
        - ``"patients"``         : list  — sample patient documents
        - ``"ontology"``         : pronto.Ontology — parsed hp.obo
    """
    t0 = time.time()
    data: dict[str, Any] = {}

    # --- HPO terms -----------------------------------------------------------
    print("Loading HPO terms...")
    hpo_index: dict[str, dict] = {}
    synonym_index: dict[str, str] = {}
    ic_scores: dict[str, float] = {}

    for doc in db["hpo_terms"].find():
        hpo_id = doc["_id"]
        hpo_index[hpo_id] = doc

        # Build synonym index: label + synonyms → hpo_id
        label = doc.get("label", "")
        if label:
            synonym_index[label.lower()] = hpo_id
        for syn in doc.get("synonyms", []):
            if syn:
                synonym_index[syn.lower()] = hpo_id

        # IC scores (default null → 0.0 so downstream sums don't crash)
        ic_scores[hpo_id] = float(doc.get("ic_score") or 0.0)

    data["hpo_index"] = hpo_index
    data["synonym_index"] = synonym_index
    data["ic_scores"] = ic_scores
    print(f"  -> {len(hpo_index)} HPO terms, {len(synonym_index)} synonym entries, "
          f"{len(ic_scores)} IC scores")

    # --- Disease profiles ----------------------------------------------------
    print("Loading disease profiles...")
    disease_to_hpo: dict[str, set[str]] = {}
    disease_ancestors: dict[str, set[str]] = {}
    disease_to_name: dict[str, str] = {}
    orphanet_profiles: dict[str, dict | None] = {}

    for doc in db["disease_profiles"].find():
        did = doc["_id"]
        disease_to_hpo[did] = set(doc.get("hpo_terms", []))
        disease_ancestors[did] = set(doc.get("ancestor_terms", []))
        disease_to_name[did] = doc.get("name", "")
        orphanet_profiles[did] = doc.get("orphanet")

    data["disease_to_hpo"] = disease_to_hpo
    data["disease_ancestors"] = disease_ancestors
    data["disease_to_name"] = disease_to_name
    data["orphanet_profiles"] = orphanet_profiles
    print(f"  -> {len(disease_to_hpo)} diseases loaded")

    # --- Patients ------------------------------------------------------------
    print("Loading patients...")
    patients = list(db["patients"].find())
    data["patients"] = patients
    print(f"  -> {len(patients)} patients loaded")

    # --- Ontology ------------------------------------------------------------
    print("Loading HPO ontology from data/raw/hp.obo (this takes ~5s)...")
    data["ontology"] = pronto.Ontology("data/raw/hp.obo")
    print("  -> Ontology loaded")

    elapsed = time.time() - t0
    print(f"load_all() completed in {elapsed:.1f}s")
    return data
