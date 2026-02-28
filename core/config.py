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

# Azure OpenAI (used by WS2 agent pipeline)
AZURE_ENDPOINT: str = os.getenv("AZURE_ENDPOINT", "")       # e.g. https://<resource>.openai.azure.com/
AZURE_API_KEY: str = os.getenv("AZURE_API_KEY", "")
AZURE_DEPLOYMENT: str = os.getenv("AZURE_DEPLOYMENT", "")   # deployment / model name
AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2024-12-01-preview")
