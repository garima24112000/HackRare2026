"""
core/config.py — Single responsibility: load environment variables from .env
and expose them as module-level constants.

Used by ALL workstreams.
"""

from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI: str = os.getenv("MONGODB_URI", "")
REDIS_URL: str = os.getenv("REDIS_URL", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
OMIM_API_KEY: str = os.getenv("OMIM_API_KEY", "")
DB_NAME: str = "diagnostic_copilot"
