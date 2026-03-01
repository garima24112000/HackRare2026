"""
scripts/ingest_diseases.py — (Optional) Parse Orphanet en_product4.xml and enrich
existing disease profiles in MongoDB with phenotype frequencies, inheritance,
genes, and recommended tests.

Owner: WS1 (Data & Retrieval)

Usage:  python -m scripts.ingest_diseases
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, ".")

from pymongo import UpdateOne
from core.database import get_db

XML_PATH = "data/raw/en_product4.xml"


def main() -> None:
    """Parse en_product4.xml → update disease_profiles with Orphanet enrichment."""

    db = get_db()
    col = db["disease_profiles"]

    print(f"Parsing Orphanet XML: {XML_PATH}")

    try:
        tree = ET.parse(XML_PATH)
    except FileNotFoundError:
        print(f"  !! {XML_PATH} not found — skipping Orphanet enrichment.")
        print("  The pipeline works without it (disease matching uses HPOA data).")
        return

    root = tree.getroot()

    # Build lookups from existing MongoDB docs for matching (in-memory for speed)
    print("Building id/name lookups from existing disease_profiles...")
    existing_ids: set[str] = set()
    name_to_id: dict[str, str] = {}
    for doc in col.find({}, {"_id": 1, "name": 1}):
        existing_ids.add(doc["_id"])
        if doc.get("name"):
            name_to_id[doc["name"].lower().strip()] = doc["_id"]
    print(f"  -> {len(existing_ids)} existing profiles loaded")

    # Namespace handling — Orphanet XML may use a default namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    updated = 0
    skipped = 0
    bulk_ops: list[UpdateOne] = []

    for disorder in root.iter(f"{ns}Disorder"):
        # Extract Orphanet number
        orpha_num_el = disorder.find(f"{ns}OrphaCode")
        orpha_num = orpha_num_el.text if orpha_num_el is not None else None

        # Extract disease name
        name_el = disorder.find(f"{ns}Name")
        disease_name = name_el.text.strip() if name_el is not None and name_el.text else ""

        # Extract HPO associations
        hpo_assocs = []
        for assoc in disorder.iter(f"{ns}HPODisorderAssociation"):
            hpo_el = assoc.find(f".//{ns}HPOId")
            freq_el = assoc.find(f".//{ns}HPOFrequency/{ns}Name")
            if hpo_el is not None and hpo_el.text:
                hpo_assocs.append({
                    "hpo_id": hpo_el.text.strip(),
                    "frequency": freq_el.text.strip() if freq_el is not None and freq_el.text else "Unknown",
                })

        # Extract inheritance
        inheritance = None
        inh_el = disorder.find(f".//{ns}TypeOfInheritance/{ns}Name")
        if inh_el is not None and inh_el.text:
            inheritance = inh_el.text.strip()

        # Extract genes
        genes = []
        for gene_el in disorder.iter(f"{ns}Gene"):
            sym_el = gene_el.find(f"{ns}Symbol")
            if sym_el is not None and sym_el.text:
                genes.append(sym_el.text.strip())

        # Match to existing disease profile (in-memory lookup, no network call)
        matched_id = None
        # Try ORPHA ID first
        if orpha_num:
            orpha_id = f"ORPHA:{orpha_num}"
            if orpha_id in existing_ids:
                matched_id = orpha_id

        # Try name matching
        if not matched_id and disease_name:
            matched_id = name_to_id.get(disease_name.lower().strip())

        if not matched_id:
            skipped += 1
            continue

        # Build orphanet enrichment sub-document
        orphanet_data = {
            "orpha_code": orpha_num,
            "name": disease_name,
            "hpo_associations": hpo_assocs,
            "inheritance": inheritance,
            "genes": genes,
        }

        bulk_ops.append(UpdateOne(
            {"_id": matched_id},
            {"$set": {"orphanet": orphanet_data}},
        ))
        updated += 1

    # Flush all updates in one batch
    if bulk_ops:
        print(f"  Writing {len(bulk_ops)} updates in bulk...")
        result = col.bulk_write(bulk_ops, ordered=False)
        print(f"  -> bulk_write matched={result.matched_count}, modified={result.modified_count}")

    print(f"\n=== Orphanet Enrichment Summary ===")
    print(f"  Diseases updated: {updated}")
    print(f"  Diseases skipped (no match): {skipped}")
    print("Done.")


if __name__ == "__main__":
    main()
