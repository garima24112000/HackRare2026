"""
core/data_loader.py — Startup hydration: load all reference data into memory.

Owner: WS1 (Data & Retrieval)

Called once at app startup. Returns a dict with all indexes and data
that tools need to operate without further DB queries.
"""

from __future__ import annotations
from typing import Any


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
        - ``"orphanet_profiles"`` : dict  — Orphanet ID → profile document
        - ``"patients"``         : list  — sample patient documents
        - ``"ontology"``         : pronto.Ontology — parsed hp.obo
    """
    raise NotImplementedError("WS1: implement data loading from MongoDB")
