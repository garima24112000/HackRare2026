"""
core/database.py — MongoDB singleton connection.

Owner: WS1 (Data & Retrieval)

Provides a shared MongoDB client and database handle used by data_loader,
ingestion scripts, and eval harness.
"""

from pymongo import MongoClient
from core.config import MONGODB_URI, DB_NAME


_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return (and cache) a MongoClient singleton."""
    global _client
    if _client is None:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI is not set in .env")
        _client = MongoClient(MONGODB_URI)
    return _client


def get_db():
    """Return the default database handle."""
    return get_client()[DB_NAME]
