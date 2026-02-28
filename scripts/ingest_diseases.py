"""
scripts/ingest_diseases.py — Parse phenotype.hpoa and load disease–HPO associations.

Owner: WS1 (Data & Retrieval)

Usage:  python -m scripts.ingest_diseases
"""

from __future__ import annotations


def main() -> None:
    """Parse phenotype.hpoa → insert disease-to-HPO mappings into MongoDB."""
    raise NotImplementedError(
        "WS1: implement disease ingestion from data/raw/phenotype.hpoa"
    )


if __name__ == "__main__":
    main()
