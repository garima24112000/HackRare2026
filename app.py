"""
app.py — Chainlit entry point for the Diagnostic Copilot UI.

Owner: WS3 (UI & Chat)

Run with:  chainlit run app.py -w
"""

from __future__ import annotations

import chainlit as cl

from core.data_loader import load_all
from core.database import get_db
from core.session_manager import SessionManager
from core.config import REDIS_URL
from core.models import PatientInput
from agent.pipeline import run_pipeline


# ---------- Globals loaded once at startup ----------
DATA: dict | None = None
SESSION_MGR: SessionManager | None = None


@cl.on_chat_start
async def on_chat_start():
    """Initialise data and session on new conversation."""
    global DATA, SESSION_MGR

    # Load reference data once
    if DATA is None:
        db = get_db()
        DATA = load_all(db)

    if SESSION_MGR is None:
        SESSION_MGR = SessionManager(REDIS_URL)

    # TODO WS3: show patient-selector buttons from DATA["patients"]
    await cl.Message(content="Diagnostic Copilot ready. Paste a clinical note or select a patient.").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user message — run the diagnostic pipeline."""
    raise NotImplementedError("WS3: implement message handling, call run_pipeline()")
