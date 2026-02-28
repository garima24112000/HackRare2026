"""
agent/pipeline.py — Main diagnostic orchestrator.

Owner: WS2 (Agent & Reasoning)

This is THE main function. Chainlit (WS3) calls it on user message,
eval harness (WS4) calls it in batch.  It invokes all tools in order,
assembles context, calls the final LLM reasoning step, and returns
a complete AgentOutput.
"""

from __future__ import annotations

from core.models import AgentOutput, PatientInput
from core.session_manager import SessionManager


async def run_pipeline(
    patient_input: PatientInput,
    data: dict,
    session_mgr: SessionManager,
) -> AgentOutput:
    """
    Execute the full diagnostic reasoning pipeline.

    Sequence (approximate):
      1. HPO lookup on free_text → observed HPO terms
      2. Excluded-phenotype extraction → excluded HPO terms
      3. Timing extraction → onset / progression profiles
      4. Disease matching (observed − excluded) → differential
      5. Orphanet fetch for top candidates → disease profiles
      6. Red-flag detection
      7. (Optional) Reanalysis trigger
      8. Final LLM reasoning → next steps, differential ranking,
         uncertainty summary

    Parameters
    ----------
    patient_input : PatientInput
        The user-supplied clinical information.
    data : dict
        Reference-data dict from ``core.data_loader.load_all()``.
    session_mgr : SessionManager
        Redis session manager for logging tool calls and context.

    Returns
    -------
    AgentOutput
        The complete diagnostic output.
    """
    raise NotImplementedError("WS2: implement the full pipeline orchestration")
