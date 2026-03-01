"""
scripts/ingest_patients.py — Load sample / gold-standard patient cases into MongoDB.

Owner: WS1 (Data & Retrieval)

Usage:  python -m scripts.ingest_patients
"""

from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")

from core.database import get_db

PATIENT_FILE = "data/raw/Phenotypic-profiles-Rare-Disease-Hackathon2025.txt"


def main() -> None:
    """Insert sample patient documents into MongoDB for demo and evaluation."""

    db = get_db()

    print(f"Parsing patient file: {PATIENT_FILE}")

    with open(PATIENT_FILE, "r", encoding="utf-8-sig") as fh:
        lines = [l.rstrip("\r\n") for l in fh.readlines()]

    patients: list[dict] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for "Patient N" header
        if re.match(r"^Patient\s+\d+", line, re.IGNORECASE):
            patient_num = len(patients) + 1
            pid = f"patient_{patient_num:02d}"

            # Next non-empty line is the description
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            desc_line = lines[i].strip() if i < len(lines) else ""

            # Parse age
            age_match = re.search(r"(\d+)-year-old", desc_line)
            age = int(age_match.group(1)) if age_match else None

            # Parse sex
            sex = None
            if "female" in desc_line.lower():
                sex = "F"
            elif "male" in desc_line.lower():
                sex = "M"

            # Parse diagnosis name and OMIM
            diag_match = re.search(
                r"diagnosed with\s+(.+?)(?:\s*[()]+\s*OMIM:\s*(\d+)\s*\))?$",
                desc_line,
                re.IGNORECASE,
            )
            diagnosis_name = diag_match.group(1).strip() if diag_match else desc_line
            omim_num = diag_match.group(2) if diag_match and diag_match.group(2) else None
            diagnosis_omim = f"OMIM:{omim_num}" if omim_num else None

            # Next non-empty line is HPO terms
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            hpo_line = lines[i].strip() if i < len(lines) else ""
            hpo_terms = [t.strip() for t in hpo_line.split(";") if t.strip()]

            patients.append({
                "_id": pid,
                "age": age,
                "sex": sex,
                "diagnosis_name": diagnosis_name,
                "diagnosis_omim": diagnosis_omim,
                "hpo_terms": hpo_terms,
            })

        i += 1

    print(f"  -> Parsed {len(patients)} patients")

    # Insert into MongoDB
    print("Dropping & inserting patients collection...")
    db["patients"].drop()
    if patients:
        db["patients"].insert_many(patients)

    # Summary
    for p in patients:
        print(
            f"  {p['_id']}: {p.get('age', '?')}y {p.get('sex', '?')} — "
            f"{p.get('diagnosis_name', 'N/A')} — {len(p['hpo_terms'])} HPO terms"
        )

    print(f"\n{len(patients)} patients inserted. Done.")


if __name__ == "__main__":
    main()
