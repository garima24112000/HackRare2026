"""
scripts/ingest_hpo.py — Parse hp.obo and phenotype.hpoa, load HPO terms and
disease profiles into MongoDB.

Owner: WS1 (Data & Retrieval)

Usage:  python -m scripts.ingest_hpo
"""

from __future__ import annotations

import math
import sys
import time

import pronto

# Ensure project root is importable
sys.path.insert(0, ".")

from core.database import get_db
import hpo_functions


OBO_PATH = "data/raw/hp.obo"
HPOA_PATH = "data/raw/phenotype.hpoa"


def main() -> None:
    """Parse hp.obo → insert HPO terms, compute IC scores, build disease
    profiles, and insert all into MongoDB."""

    db = get_db()

    # ------------------------------------------------------------------
    # 1. Load ontology
    # ------------------------------------------------------------------
    print("Loading ontology from", OBO_PATH, "...")
    ontology = pronto.Ontology(OBO_PATH)

    # ------------------------------------------------------------------
    # 2. Build HPO term documents
    # ------------------------------------------------------------------
    print("Extracting HPO terms...")
    term_docs: list[dict] = []

    for term in ontology.terms():
        tid = term.id
        if not tid.startswith("HP:"):
            continue

        parents = []
        for sup in term.superclasses(distance=1):
            if sup.id != tid:
                parents.append(sup.id)

        synonyms = [s.description for s in term.synonyms]

        term_docs.append({
            "_id": tid,
            "label": term.name,
            "definition": str(term.definition) if term.definition else None,
            "synonyms": synonyms,
            "parents": parents,
            "ic_score": None,  # computed later
        })

    print(f"  -> {len(term_docs)} HP terms extracted")

    # ------------------------------------------------------------------
    # 3. Insert HPO terms
    # ------------------------------------------------------------------
    print("Dropping & inserting hpo_terms collection...")
    db["hpo_terms"].drop()
    if term_docs:
        db["hpo_terms"].insert_many(term_docs)

    # ------------------------------------------------------------------
    # 4. Compute IC scores from disease annotations
    # ------------------------------------------------------------------
    print("Reading disease annotations from", HPOA_PATH, "...")
    disease_to_hpo, disease_to_name = hpo_functions.read_disease_annotations(HPOA_PATH)

    print("Computing IC scores...")
    hpo_probs = hpo_functions.hpo_term_probability(disease_to_hpo)

    updated = 0
    for hpo_id, prob in hpo_probs.items():
        ic = -math.log2(prob)
        db["hpo_terms"].update_one({"_id": hpo_id}, {"$set": {"ic_score": ic}})
        updated += 1

    print(f"  -> Updated IC scores for {updated} terms")

    # ------------------------------------------------------------------
    # 5. Build disease profile documents (with ancestor sets)
    # ------------------------------------------------------------------
    print("Building disease profiles (ancestor computation — may take minutes)...")
    disease_docs: list[dict] = []
    total = len(disease_to_hpo)

    for i, (disease_id, hpo_set) in enumerate(disease_to_hpo.items(), 1):
        if i % 1000 == 0 or i == total:
            print(f"  [{i}/{total}]")

        ancestor_set: set[str] = set()
        for hpo_id in hpo_set:
            try:
                ancestor_set.update(
                    hpo_functions.get_ancestors_up_to_root(ontology, hpo_id)
                )
            except Exception:
                # Some terms may not be under HP:0000118 — skip them
                pass

        disease_docs.append({
            "_id": disease_id,
            "name": disease_to_name.get(disease_id, ""),
            "hpo_terms": list(hpo_set),
            "ancestor_terms": list(ancestor_set),
            "orphanet": None,
        })

    # ------------------------------------------------------------------
    # 6. Insert disease profiles
    # ------------------------------------------------------------------
    print("Dropping & inserting disease_profiles collection...")
    db["disease_profiles"].drop()
    if disease_docs:
        db["disease_profiles"].insert_many(disease_docs)

    # ------------------------------------------------------------------
    # 7. Create text indexes for search
    # ------------------------------------------------------------------
    print("Creating indexes on hpo_terms...")
    db["hpo_terms"].create_index([("label", "text"), ("synonyms", "text")])

    # ------------------------------------------------------------------
    # 8. Summary
    # ------------------------------------------------------------------
    n_hpo = db["hpo_terms"].count_documents({})
    n_dis = db["disease_profiles"].count_documents({})
    avg_terms = (
        sum(len(d["hpo_terms"]) for d in disease_docs) / len(disease_docs)
        if disease_docs else 0
    )
    print(f"\n=== Ingestion Summary ===")
    print(f"  HPO terms inserted   : {n_hpo}")
    print(f"  Diseases inserted    : {n_dis}")
    print(f"  Avg HPO terms/disease: {avg_terms:.1f}")
    print("Done.")


if __name__ == "__main__":
    main()
