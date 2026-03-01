"""
app.py — Chainlit entry point for the Diagnostic Copilot UI.

Owner: WS3 (UI & Chat)

Run with:  chainlit run app.py -w

This file directly imports the working backend (core.*, agent.pipeline)
and uses chainlit_utils.formatters for HTML rendering.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

import chainlit as cl

from core.data_loader import load_all
from core.database import get_db
from core.session_manager import SessionManager
from core.config import REDIS_URL
from core.models import PatientInput
from agent.pipeline import run_pipeline
from chainlit_utils.formatters import (
    format_agent_output,
    format_welcome_card,
    format_patient_load_card,
    _resolve_label,
)

logger = logging.getLogger(__name__)

# ---------- Globals loaded once at startup ----------
DATA: dict | None = None
SESSION_MGR: SessionManager | None = None
PATIENTS: list[dict] = []

STEP_EMOJIS = {
    "Red Flag Check": "\U0001f6a8",
    "HPO Mapping": "\U0001f50d",
    "Disease Matching": "\U0001f9ec",
    "Phenotype Extraction": "\U0001f4dd",
    "Disease Profile Fetch": "\U0001f4cb",
    "Complete": "\U0001f9e0",
}


# ═══════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════

@cl.on_chat_start
async def on_chat_start():
    """Initialise data and session on new conversation."""
    global DATA, SESSION_MGR, PATIENTS

    # Load reference data once (real MongoDB)
    if DATA is None:
        db = get_db()
        DATA = load_all(db)
        PATIENTS = DATA.get("patients", [])

    if SESSION_MGR is None:
        SESSION_MGR = SessionManager(REDIS_URL)

    # Generate session ID
    session_id = str(uuid.uuid4())
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("current_hpo_terms", [])
    cl.user_session.set("current_patient", None)

    # Build patient selector action buttons (functional clicks)
    actions = []
    for i, patient in enumerate(PATIENTS[:15]):
        pid = patient.get("_id", f"patient_{i+1}")
        age = patient.get("age", "?")
        sex = patient.get("sex", "?")
        name = patient.get("diagnosis_name", "Unknown")
        hpo_count = len(patient.get("hpo_terms", []))
        label = f"{pid}: {age}yo {sex} — {name} ({hpo_count} HPO)"

        actions.append(
            cl.Action(
                name="load_patient",
                payload={"patient_index": i, "patient_id": str(pid)},
                label=label,
            )
        )

    # Build styled HTML welcome dashboard
    hpo_index = DATA.get("hpo_index", {})
    welcome_html = format_welcome_card(PATIENTS, hpo_index)

    await cl.Message(
        content=welcome_html,
        actions=actions,
    ).send()


# ═══════════════════════════════════════════════════════════════════════
# PATIENT SELECTOR CALLBACK
# ═══════════════════════════════════════════════════════════════════════

@cl.action_callback("load_patient")
async def on_load_patient(action: cl.Action):
    """Handle patient button click — load patient and run analysis."""
    patient_index = action.payload.get("patient_index", 0)
    patient_id = action.payload.get("patient_id", "?")

    if patient_index >= len(PATIENTS):
        await cl.Message(content=f"❌ Patient index {patient_index} out of range.").send()
        return

    patient = PATIENTS[patient_index]
    hpo_terms = patient.get("hpo_terms", [])
    age = patient.get("age")
    sex = patient.get("sex")

    # Store in session
    cl.user_session.set("current_hpo_terms", list(hpo_terms))
    cl.user_session.set("current_patient", patient)

    # Send styled patient-load card
    hpo_index = DATA.get("hpo_index", {})
    load_html = format_patient_load_card(patient, hpo_index)
    await cl.Message(content=load_html).send()

    # Build input and run
    patient_input = PatientInput(
        hpo_terms=list(hpo_terms),
        age=age,
        sex=sex,
    )
    await run_analysis(patient_input, patient)


# ═══════════════════════════════════════════════════════════════════════
# MANUAL INPUT HANDLER
# ═══════════════════════════════════════════════════════════════════════

@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user message — parse and run pipeline."""
    text = message.content.strip()
    if not text:
        return

    # Check for HPO term pattern
    hpo_pattern = re.findall(r"HP:\d{7}", text)

    current_terms = cl.user_session.get("current_hpo_terms") or []
    patient_meta = cl.user_session.get("current_patient")

    if hpo_pattern:
        # HPO term input — merge with any existing session terms
        merged = list(set(current_terms + hpo_pattern))
        cl.user_session.set("current_hpo_terms", merged)

        patient_input = PatientInput(
            hpo_terms=merged,
            age=patient_meta.get("age") if patient_meta else None,
            sex=patient_meta.get("sex") if patient_meta else None,
        )
    else:
        # Treat as free text
        patient_input = PatientInput(
            free_text=text,
            hpo_terms=current_terms,
            age=patient_meta.get("age") if patient_meta else None,
            sex=patient_meta.get("sex") if patient_meta else None,
        )

    await run_analysis(patient_input, patient_meta)


# ═══════════════════════════════════════════════════════════════════════
# ADD HPO TERM CALLBACK (assess chip click)
# ═══════════════════════════════════════════════════════════════════════

@cl.action_callback("add_hpo_term")
async def on_add_hpo_term(action: cl.Action):
    """Handle assess chip click — add HPO term and re-run."""
    hpo_id = action.payload.get("hpo_id", "")
    label = action.payload.get("label", "")

    current_terms = cl.user_session.get("current_hpo_terms") or []
    patient_meta = cl.user_session.get("current_patient")

    if hpo_id and hpo_id not in current_terms:
        current_terms.append(hpo_id)
        cl.user_session.set("current_hpo_terms", current_terms)

    # Send a styled "phenotype added" card
    await cl.Message(
        content=(
            '<div class="patient-load-card" style="border-left-color:var(--green);">'
            '<div class="pl-top">'
            '<div style="width:32px;height:32px;border-radius:8px;background:var(--green-dim);'
            'color:var(--green);display:flex;align-items:center;justify-content:center;font-size:14px;">+</div>'
            '<div>'
            f'<div class="pl-action" style="color:var(--green);">Phenotype added — re-running analysis</div>'
            f'<div class="cp-name">{label}</div>'
            f'<div class="cp-sub" style="font-family:var(--font-mono);font-size:10px;">{hpo_id}</div>'
            '</div></div></div>'
        )
    ).send()

    patient_input = PatientInput(
        hpo_terms=current_terms,
        age=patient_meta.get("age") if patient_meta else None,
        sex=patient_meta.get("sex") if patient_meta else None,
    )

    await run_analysis(patient_input, patient_meta)


# ═══════════════════════════════════════════════════════════════════════
# CORE ANALYSIS RUNNER
# ═══════════════════════════════════════════════════════════════════════

async def run_analysis(
    patient_input: PatientInput,
    patient_meta: dict | None = None,
) -> None:
    """Run the pipeline with cl.Step visualization and send formatted output."""
    step_durations: list[dict] = []
    step_start_times: dict[str, float] = {}
    active_steps: dict[str, cl.Step] = {}

    async def step_callback(step_name: str, result: Any) -> None:
        """Chainlit step visualization callback — same protocol as real pipeline."""
        nonlocal step_durations

        # Close previous steps if open
        for prev_name, prev_step in list(active_steps.items()):
            if prev_name in step_start_times:
                dur = time.monotonic() - step_start_times[prev_name]
                step_durations.append({"name": prev_name, "duration": round(dur, 1)})
                del step_start_times[prev_name]

        if step_name == "Complete":
            for name, start in list(step_start_times.items()):
                dur = time.monotonic() - start
                step_durations.append({"name": name, "duration": round(dur, 1)})
            step_start_times.clear()
            active_steps.clear()
            return

        # Create a new Chainlit step
        emoji = STEP_EMOJIS.get(step_name, "\u2699\ufe0f")
        step = cl.Step(name=f"{emoji} {step_name}", type="tool")
        step_start_times[step_name] = time.monotonic()
        active_steps[step_name] = step

        await step.__aenter__()

        # Format step output
        if isinstance(result, dict):
            detail = result.get("detail", "")
            step.output = detail or json.dumps(result, indent=2, default=str)
        elif isinstance(result, list):
            step.output = json.dumps(
                [r.model_dump() if hasattr(r, "model_dump") else str(r) for r in result],
                indent=2, default=str,
            )
        else:
            step.output = str(result) if result else "Done"

        await step.__aexit__(None, None, None)

    try:
        # Run the pipeline
        output = await run_pipeline(
            patient_input=patient_input,
            data=DATA,
            session_mgr=SESSION_MGR,
            step_callback=step_callback,
        )

        # Build the complete HTML card output
        hpo_index = DATA.get("hpo_index", {})
        html_content = format_agent_output(
            output=output,
            patient_meta=patient_meta,
            hpo_index=hpo_index,
            step_durations=step_durations,
        )

        # Build action buttons for missing phenotypes (assess chips)
        assess_actions = []
        seen_labels: set[str] = set()
        for dc in output.disease_candidates[:3]:
            for term_id in dc.missing_terms:
                label = _resolve_label(hpo_index, term_id)
                if label.lower() not in seen_labels:
                    seen_labels.add(label.lower())
                    assess_actions.append(
                        cl.Action(
                            name="add_hpo_term",
                            payload={"hpo_id": term_id, "label": label},
                            label=f"+ {label}",
                        )
                    )

        # Send the single output message with all HTML cards
        await cl.Message(
            content=html_content,
            actions=assess_actions[:8],  # Cap at 8 action buttons
        ).send()

    except Exception as e:
        logger.exception("Pipeline error")
        await cl.Message(
            content=(
                f"❌ **Analysis Error**\n\n"
                f"`{type(e).__name__}: {e}`\n\n"
                f"Try loading a test patient, or paste HPO terms in format `HP:XXXXXXX`.\n\n"
                f"_If the error persists, check the server logs for details._"
            )
        ).send()
