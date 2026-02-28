"""
scripts/ingest_hpo.py — Parse hp.obo and load HPO terms into MongoDB.

Owner: WS1 (Data & Retrieval)

Usage:  python -m scripts.ingest_hpo
"""

from __future__ import annotations


def main() -> None:
    """Parse hp.obo → insert HPO terms, synonyms, and IC scores into MongoDB."""
    raise NotImplementedError("WS1: implement HPO ingestion from data/raw/hp.obo")


if __name__ == "__main__":
    main()
