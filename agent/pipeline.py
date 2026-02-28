"""
agent/pipeline.py — Main diagnostic orchestrator.

Owner: WS2 (Agent & Reasoning)

This is THE main function. Chainlit (WS3) calls it on user message,
eval harness (WS4) calls it in batch.  It invokes all tools in order,
assembles context, calls the final LLM reasoning step, and returns
a complete AgentOutput.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

from agent.llm_client import call_llm, extract_json
from agent.state import PipelineState
from core.models import (
    AgentOutput,
    DifferentialEntry,
    ExcludedFinding,
    HPOMatch,
    NextStep,
    PatientInput,
    RedFlag,
    TimingProfile,
    UncertaintySummary,
)
from core.session_manager import SessionManager

import tools.disease_match as disease_match_tool
import tools.excluded_extract as excluded_extract_tool
import tools.hpo_lookup as hpo_lookup_tool
import tools.orphanet_fetch as orphanet_fetch_tool
import tools.red_flag as red_flag_tool
import tools.timing_extract as timing_extract_tool

logger = logging.getLogger(__name__)

# ── Prompt cache ────────────────────────────────────────────────────────
_FINAL_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "final_reasoning.txt"
_FINAL_PROMPT_CACHE: str | None = None


def _load_final_prompt() -> str:
    global _FINAL_PROMPT_CACHE
    if _FINAL_PROMPT_CACHE is None:
        _FINAL_PROMPT_CACHE = _FINAL_PROMPT_PATH.read_text(encoding="utf-8")
    return _FINAL_PROMPT_CACHE


# ── WS1 graceful-fallback helpers ───────────────────────────────────────
# Every WS1 tool call is wrapped in _safe_call so the pipeline runs
# (degraded) even before WS1 is integrated.
# TODO: remove once WS1 is integrated — replace with direct calls.


def _safe_call(fn: Callable, *args: Any, default: Any = None, **kwargs: Any) -> Any:
    """Call *fn* and return its result; on NotImplementedError return *default*."""
    try:
        return fn(*args, **kwargs)
    except NotImplementedError:
        logger.info("WS1 stub not yet implemented: %s — using default", fn.__module__)
        return default if default is not None else []


def _safe_session(method: Callable, *args: Any, **kwargs: Any) -> None:
    """Fire-and-forget a SessionManager method; swallow NotImplementedError."""
    try:
        method(*args, **kwargs)
    except NotImplementedError:
        pass  # WS1 stub — remove wrapper once SessionManager is integrated
    except Exception:
        logger.debug("SessionManager call failed: %s", method.__name__, exc_info=True)


# ── Tool-call logging helper ────────────────────────────────────────────

def _log_tool(
    state: PipelineState,
    session_mgr: SessionManager,
    tool_name: str,
    input_data: dict,
    output_data: Any,
    duration_ms: int,
) -> None:
    record = {
        "tool_name": tool_name,
        "input_data": input_data,
        "output_data": (
            [o.model_dump() for o in output_data]
            if isinstance(output_data, list)
            and output_data
            and hasattr(output_data[0], "model_dump")
            else output_data
        ),
        "duration_ms": duration_ms,
    }
    state.tool_log.append(record)
    _safe_session(
        session_mgr.log_tool_call,
        state.session_id,
        tool_name,
        input_data,
        record["output_data"],
    )


# ── Step callback helper ────────────────────────────────────────────────

StepCallback = Optional[Callable[[str, Any], Coroutine[Any, Any, None] | None]]


async def _fire_callback(cb: StepCallback, step_name: str, result: Any) -> None:
    if cb is None:
        return
    try:
        ret = cb(step_name, result)
        if ret is not None:
            await ret
    except Exception:
        logger.debug("Step callback error for %s", step_name, exc_info=True)


# ── Data completeness computation ───────────────────────────────────────

def _compute_completeness(state: PipelineState, patient_input: PatientInput) -> float:
    hpo_count = len(state.hpo_matches)
    hpo_val = 1.0 if hpo_count >= 3 else (0.5 if hpo_count >= 1 else 0.0)

    timing_val = (
        len(state.timing) / max(hpo_count, 1) if hpo_count else 0.0
    )
    timing_val = min(timing_val, 1.0)

    exclusion_val = 1.0 if state.excluded else 0.0
    test_val = 1.0 if patient_input.prior_tests else 0.0
    family_val = 1.0 if patient_input.family_history else 0.0

    return (
        0.30 * hpo_val
        + 0.20 * timing_val
        + 0.15 * exclusion_val
        + 0.20 * test_val
        + 0.15 * family_val
    )


# ── Context packet assembly ────────────────────────────────────────────

def _build_context_packet(state: PipelineState, patient_input: PatientInput) -> dict:
    return {
        "patient_hpo_matches": [m.model_dump() for m in state.hpo_matches],
        "excluded_findings": [e.model_dump() for e in state.excluded],
        "timing_profiles": [t.model_dump() for t in state.timing],
        "disease_candidates": [d.model_dump() for d in state.diseases[:10]],
        "disease_profiles": [p.model_dump() for p in state.profiles],
        "data_completeness": state.data_completeness,
        "red_flags": [r.model_dump() for r in state.red_flags],
        "prior_tests": patient_input.prior_tests,
        "family_history": patient_input.family_history,
        "patient_age": patient_input.age,
        "patient_sex": patient_input.sex,
    }


# ── Degraded output builder (fallback when LLM parse fails) ────────────

def _build_degraded_output(state: PipelineState) -> dict:
    """Build a minimal differential + next-steps from raw tool outputs."""
    differential = []
    for d in state.diseases[:5]:
        differential.append(
            DifferentialEntry(
                disease=d.disease_name,
                disease_id=d.disease_id,
                confidence="low",
                confidence_reasoning="Auto-generated from disease match score; LLM reasoning unavailable.",
                supporting_phenotypes=d.matched_terms,
                contradicting_phenotypes=[],
                missing_key_phenotypes=d.missing_terms,
            ).model_dump()
        )

    next_steps = [
        NextStep(
            rank=1,
            action_type="refine_phenotype",
            action="Provide additional clinical details and phenotype observations",
            rationale="Data completeness is low; more phenotype data is needed before recommending specific tests.",
            discriminates_between=[],
            urgency="routine",
            evidence_source="pipeline",
        ).model_dump()
    ]

    return {
        "differential": differential,
        "next_best_steps": next_steps,
        "what_would_change": ["Additional phenotype observations would improve disease ranking accuracy."],
        "uncertainty": {
            "known": [f"{len(state.hpo_matches)} HPO terms identified"],
            "missing": ["Full LLM reasoning was not available"],
            "ambiguous": [],
        },
    }


# ── Final LLM reasoning call ────────────────────────────────────────────


def _call_final_reasoning(context_packet: dict) -> dict:
    """Single LLM call: send the context packet and parse the structured output."""
    prompt = _load_final_prompt()
    raw = call_llm(system=prompt, user=json.dumps(context_packet, default=str))
    return extract_json(raw)


# ── Free-text splitting ─────────────────────────────────────────────────

def _split_free_text(text: str) -> list[str]:
    """Split clinical free text into rough symptom chunks."""
    # Split on common delimiters
    chunks = re.split(r"[,;.]|\band\b", text)
    return [c.strip() for c in chunks if c.strip() and len(c.strip()) > 2]


# ═════════════════════════════════════════════════════════════════════════
# THE MAIN PIPELINE
# ═════════════════════════════════════════════════════════════════════════


async def run_pipeline(
    patient_input: PatientInput,
    data: dict,
    session_mgr: SessionManager,
    step_callback: StepCallback = None,
) -> AgentOutput:
    """
    Execute the full diagnostic reasoning pipeline.

    Parameters
    ----------
    patient_input : PatientInput
        The user-supplied clinical information.
    data : dict
        Reference-data dict from ``core.data_loader.load_all()``.
    session_mgr : SessionManager
        Redis session manager for logging tool calls and context.
    step_callback : callable, optional
        ``async def cb(step_name: str, result: Any)`` — called after each
        pipeline step so the UI can display progress.

    Returns
    -------
    AgentOutput
        The complete diagnostic output.
    """

    # ── Step 0: Initialise ──────────────────────────────────────────────
    state = PipelineState(
        session_id=str(uuid.uuid4()),
        patient_input_raw=patient_input.model_dump(),
    )
    _safe_session(session_mgr.create_session, state.session_id, state.patient_input_raw)

    # ── Step 1: Red Flag Check (ALWAYS FIRST) ───────────────────────────
    t0 = time.perf_counter_ns()
    state.red_flags = _safe_call(
        red_flag_tool.run,
        patient_input.hpo_terms,
        data.get("ontology"),
        default=[],
    )
    _log_tool(state, session_mgr, "red_flag", {"hpo_terms": patient_input.hpo_terms}, state.red_flags, int((time.perf_counter_ns() - t0) / 1_000_000))
    await _fire_callback(step_callback, "Red Flag Check", state.red_flags)

    # Early exit on URGENT red flags
    urgent_flags = [f for f in state.red_flags if f.severity == "URGENT"]
    if urgent_flags:
        logger.warning("URGENT red flags detected — returning early")
        return AgentOutput(
            red_flags=state.red_flags,
            patient_hpo_observed=[],
            data_completeness=0.0,
            uncertainty=UncertaintySummary(
                known=[f"URGENT: {f.flag_label}" for f in urgent_flags],
                missing=["Full analysis not performed due to urgent flags"],
                ambiguous=[],
            ),
        )

    # ── Step 2: HPO Mapping ─────────────────────────────────────────────
    raw_texts_to_lookup: list[str] = []

    # Already-supplied HPO IDs → pass through for enrichment
    if patient_input.hpo_terms:
        raw_texts_to_lookup.extend(patient_input.hpo_terms)

    # Free text → split into chunks
    if patient_input.free_text:
        raw_texts_to_lookup.extend(_split_free_text(patient_input.free_text))

    t0 = time.perf_counter_ns()
    hpo_results: list[HPOMatch] = _safe_call(
        hpo_lookup_tool.run,
        raw_texts_to_lookup,
        data,
        default=[],
    )
    _log_tool(state, session_mgr, "hpo_lookup", {"raw_texts": raw_texts_to_lookup}, hpo_results, int((time.perf_counter_ns() - t0) / 1_000_000))

    # Deduplicate by hpo_id
    seen_ids: set[str] = set()
    for m in hpo_results:
        if m.hpo_id and m.hpo_id not in seen_ids:
            state.hpo_matches.append(m)
            seen_ids.add(m.hpo_id)

    await _fire_callback(step_callback, "HPO Mapping", state.hpo_matches)

    # ── Step 3: Disease Matching (initial) ──────────────────────────────
    hpo_ids = [m.hpo_id for m in state.hpo_matches if m.hpo_id]

    t0 = time.perf_counter_ns()
    state.diseases = _safe_call(
        disease_match_tool.run,
        hpo_ids,
        [],  # no exclusions yet
        data,
        default=[],
    )
    _log_tool(state, session_mgr, "disease_match", {"hpo_ids": hpo_ids, "excluded_ids": []}, state.diseases, int((time.perf_counter_ns() - t0) / 1_000_000))
    await _fire_callback(step_callback, "Disease Matching", state.diseases)

    # ── Step 4: Phenotype Extraction (only with free text) ──────────────
    if patient_input.free_text and patient_input.free_text.strip():
        free_text = patient_input.free_text
        hpo_labels = [m.label for m in state.hpo_matches if m.label]

        # 4a + 4b: Run excluded & timing extraction concurrently
        t0 = time.perf_counter_ns()
        excluded_result, timing_result = await asyncio.gather(
            asyncio.to_thread(
                excluded_extract_tool.run,
                free_text,
                data.get("synonym_index", {}),
            ),
            asyncio.to_thread(
                timing_extract_tool.run,
                free_text,
                hpo_labels,
            ),
        )
        elapsed = int((time.perf_counter_ns() - t0) / 1_000_000)

        state.excluded = excluded_result
        state.timing = timing_result

        _log_tool(state, session_mgr, "excluded_extract", {"note_length": len(free_text)}, state.excluded, elapsed)
        _log_tool(state, session_mgr, "timing_extract", {"note_length": len(free_text), "hpo_labels": hpo_labels}, state.timing, elapsed)

        await _fire_callback(step_callback, "Phenotype Extraction", {
            "excluded": state.excluded,
            "timing": state.timing,
        })

        # 4c: Re-run disease match with exclusions if any mapped
        excluded_hpo_ids = [
            e.mapped_hpo_term
            for e in state.excluded
            if e.mapped_hpo_term
        ]
        if excluded_hpo_ids:
            t0 = time.perf_counter_ns()
            refined = _safe_call(
                disease_match_tool.run,
                hpo_ids,
                excluded_hpo_ids,
                data,
                default=[],
            )
            if refined:
                state.diseases = refined
            _log_tool(state, session_mgr, "disease_match_refined", {"hpo_ids": hpo_ids, "excluded_ids": excluded_hpo_ids}, state.diseases, int((time.perf_counter_ns() - t0) / 1_000_000))

    # ── Step 5: Disease Profile Fetch ───────────────────────────────────
    top_disease_ids = [d.disease_id for d in state.diseases[:5]]
    if top_disease_ids:
        t0 = time.perf_counter_ns()
        state.profiles = _safe_call(
            orphanet_fetch_tool.run,
            top_disease_ids,
            data,
            default=[],
        )
        _log_tool(state, session_mgr, "orphanet_fetch", {"disease_ids": top_disease_ids}, state.profiles, int((time.perf_counter_ns() - t0) / 1_000_000))
        await _fire_callback(step_callback, "Disease Profile Fetch", state.profiles)

    # ── Step 6: Data Completeness ───────────────────────────────────────
    state.data_completeness = _compute_completeness(state, patient_input)

    # ── Step 7: Final LLM Reasoning ─────────────────────────────────────
    context_packet = _build_context_packet(state, patient_input)
    _safe_session(session_mgr.set_context, state.session_id, context_packet)

    try:
        llm_output = _call_final_reasoning(context_packet)
    except Exception:
        logger.exception("Final reasoning failed — building degraded output")
        llm_output = _build_degraded_output(state)

    # ── Assemble AgentOutput ────────────────────────────────────────────
    try:
        # Parse LLM-generated fields
        differential = [
            DifferentialEntry(**d) for d in llm_output.get("differential", [])
        ]
        next_best_steps = [
            NextStep(**s) for s in llm_output.get("next_best_steps", [])
        ]
        what_would_change = llm_output.get("what_would_change", [])
        uncertainty_raw = llm_output.get("uncertainty", {})
        uncertainty = UncertaintySummary(
            known=uncertainty_raw.get("known", []),
            missing=uncertainty_raw.get("missing", []),
            ambiguous=uncertainty_raw.get("ambiguous", []),
        )
    except Exception:
        logger.exception("Failed to parse LLM output fields — using degraded output")
        degraded = _build_degraded_output(state)
        differential = [DifferentialEntry(**d) for d in degraded["differential"]]
        next_best_steps = [NextStep(**s) for s in degraded["next_best_steps"]]
        what_would_change = degraded["what_would_change"]
        uncertainty = UncertaintySummary(**degraded["uncertainty"])

    output = AgentOutput(
        patient_hpo_observed=state.hpo_matches,
        patient_hpo_excluded=state.excluded,
        timing_profiles=state.timing,
        data_completeness=state.data_completeness,
        red_flags=state.red_flags,
        differential=differential,
        next_best_steps=next_best_steps,
        reanalysis=state.reanalysis,
        what_would_change=what_would_change,
        uncertainty=uncertainty,
    )

    # Store final output in Redis
    _safe_session(session_mgr.set_output, state.session_id, output.model_dump())

    await _fire_callback(step_callback, "Complete", output)

    return output
