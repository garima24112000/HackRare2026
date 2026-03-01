"""
chainlit_utils/formatters.py — HTML card builders for the Diagnostic Copilot UI.

Converts AgentOutput + metadata into rich HTML strings for cl.Message(content=...).
All phenotype evidence for differential tags is derived by joining
DifferentialEntry.disease_id → DiseaseCandidate.matched_terms / missing_terms.
No model changes required.
"""

from __future__ import annotations

import html
from typing import Optional

from core.models import AgentOutput


# ── Helpers ─────────────────────────────────────────────────────────────

def _esc(text) -> str:
    """HTML-escape any value safely."""
    return html.escape(str(text)) if text else ""


def _resolve_label(hpo_index: dict, hpo_id: str) -> str:
    """Resolve an HPO ID to its human-readable label.

    Handles both real format (hpo_index[id] is a dict with "label" key)
    and simple format (hpo_index[id] is a string).
    """
    entry = hpo_index.get(hpo_id)
    if entry is None:
        return hpo_id
    if isinstance(entry, dict):
        return entry.get("label", hpo_id)
    return str(entry)


CONF_CSS = {"high": "high", "moderate": "mod", "low": "low"}

ACTION_TYPE_LABELS = {
    "order_test": "Order Test",
    "refine_phenotype": "Refine Phenotype",
    "genetic_testing": "Genetic Testing",
    "reanalysis": "Reanalysis",
    "refer_specialist": "Refer Specialist",
    "urgent_escalation": "Urgent Escalation",
}

STEP_EMOJIS = {
    "Red Flag Check": "\U0001f6a8",
    "HPO Mapping": "\U0001f50d",
    "Disease Matching": "\U0001f9ec",
    "Phenotype Extraction": "\U0001f4dd",
    "Disease Profile Fetch": "\U0001f4cb",
    "Complete": "\U0001f9e0",
}


# ── Section builders ────────────────────────────────────────────────────

def _build_step_summary(step_durations: list[dict] | None) -> str:
    """Render the pipeline step timing summary."""
    if not step_durations:
        return ""
    rows = []
    for sd in step_durations:
        name = _esc(sd.get("name", ""))
        dur = sd.get("duration", 0)
        emoji = STEP_EMOJIS.get(sd.get("name", ""), "\u2699\ufe0f")
        rows.append(
            f'<div class="step-summary-row">'
            f'<div class="step-summary-icon">\u2713</div>'
            f'<div class="step-summary-name">{emoji} {name}</div>'
            f'<div class="step-summary-dur">{dur:.1f}s</div>'
            f'</div>'
        )
    return f'<div class="step-summary">{"".join(rows)}</div>'


def _build_patient_header(
    output: AgentOutput,
    patient_meta: dict | None,
    hpo_index: dict,
) -> str:
    """Render the patient header card with HPO chips."""
    if patient_meta is None:
        patient_meta = {}

    pid = _esc(patient_meta.get("_id", "??"))
    age = patient_meta.get("age", "?")
    sex = patient_meta.get("sex", "?")
    sex_class = "f" if str(sex).upper().startswith("F") else "m"
    avatar_text = f"{pid[-2:]}{str(sex).upper()[0]}" if pid else "??"
    diag = _esc(patient_meta.get("diagnosis_name", ""))

    chips_html = ""
    for m in output.patient_hpo_observed:
        label = _esc(m.label) if m.label else _esc(_resolve_label(hpo_index, m.hpo_id))
        chips_html += (
            f'<span class="hpo-chip">{_esc(m.hpo_id)}'
            f'<span class="hpo-chip-label">{label}</span></span>'
        )

    return (
        f'<div class="card-patient">'
        f'<div class="card-patient-avatar {sex_class}">{_esc(avatar_text)}</div>'
        f'<div>'
        f'<div class="cp-name">Patient {pid} &mdash; {age}yo {_esc(str(sex).upper())}</div>'
        f'<div class="cp-sub">{diag}</div>'
        f'<div class="cp-chips">{chips_html}</div>'
        f'</div></div>'
    )


def _build_stats_row(output: AgentOutput) -> str:
    """Render the 4-tile stats row with SVG gauge for data completeness."""
    pct = int(output.data_completeness * 100)
    offset = round(113 - (113 * output.data_completeness), 1)

    hpo_count = len(output.patient_hpo_observed)
    candidates = len(output.disease_candidates)
    flags = len(output.red_flags)
    flag_color = "r" if flags > 0 else "g"

    return (
        f'<div class="card-stats">'
        # Tile 1: Data completeness gauge
        f'<div class="stat-tile t">'
        f'<div class="stat-gauge">'
        f'<svg class="gauge" viewBox="0 0 40 40">'
        f'<circle class="gauge-bg" cx="20" cy="20" r="18"/>'
        f'<circle class="gauge-arc" cx="20" cy="20" r="18" '
        f'style="stroke-dashoffset:{offset}"/>'
        f'<text class="gauge-val" x="20" y="22" text-anchor="middle">{pct}%</text>'
        f'</svg>'
        f'<div><div class="stat-num" style="font-size:18px;">{pct}%</div>'
        f'<div class="stat-lbl">Completeness</div></div>'
        f'</div></div>'
        # Tile 2: HPO terms
        f'<div class="stat-tile g">'
        f'<div class="stat-num">{hpo_count}</div>'
        f'<div class="stat-lbl">HPO Terms</div></div>'
        # Tile 3: Candidates
        f'<div class="stat-tile a">'
        f'<div class="stat-num">{candidates}</div>'
        f'<div class="stat-lbl">Candidates</div></div>'
        # Tile 4: Red flags
        f'<div class="stat-tile {flag_color}">'
        f'<div class="stat-num">{flags}</div>'
        f'<div class="stat-lbl">Red Flags</div></div>'
        f'</div>'
    )


def _build_red_flags(output: AgentOutput) -> str:
    """Render the red flags alert card (empty string if none)."""
    if not output.red_flags:
        return ""
    items = ""
    for rf in output.red_flags:
        sev = _esc(rf.severity)
        label = _esc(rf.flag_label)
        action = _esc(rf.recommended_action)
        triggers = ", ".join(_esc(t) for t in rf.triggering_terms)
        items += (
            f'<div class="rf-item">'
            f'<strong>{sev}</strong> &mdash; {label}: {action}'
            f'<br><span style="font-size:10px;color:var(--text-muted);">'
            f'Triggers: {triggers}</span></div>'
        )
    return (
        f'<div class="red-flag-card">'
        f'<div class="rf-title">\U0001f6a8 Red Flags</div>'
        f'{items}</div>'
    )


def _build_differential(output: AgentOutput, hpo_index: dict) -> str:
    """Render accordion differential diagnosis cards.

    Phenotype tags are derived by joining DifferentialEntry.disease_id
    to DiseaseCandidate.matched_terms / missing_terms. No extra model
    fields needed.
    """
    if not output.differential:
        return ""

    # Build lookup: disease_id → DiseaseCandidate
    dc_lookup: dict[str, object] = {}
    for dc in output.disease_candidates:
        dc_lookup[dc.disease_id] = dc

    # Build set of excluded HPO IDs
    excluded_hpo_ids = set()
    for ex in output.patient_hpo_excluded:
        if ex.mapped_hpo_term:
            excluded_hpo_ids.add(ex.mapped_hpo_term)

    cards = []
    for i, entry in enumerate(output.differential):
        conf_cls = CONF_CSS.get(entry.confidence, "low")
        open_cls = " open" if i == 0 else ""

        # Get DiseaseCandidate for this differential entry
        dc = dc_lookup.get(entry.disease_id)

        # Derive coverage percentage
        if dc and dc.coverage_pct > 0:
            score_pct = int(dc.coverage_pct * 100)
        else:
            score_pct = max(10, 100 - (i * 15))

        # Build phenotype tags
        tags_html = ""
        if dc:
            for term_id in dc.matched_terms[:8]:
                lbl = _esc(_resolve_label(hpo_index, term_id))
                tags_html += f'<span class="tag s">\u2713 {lbl}</span>'
            for term_id in dc.missing_terms[:6]:
                lbl = _esc(_resolve_label(hpo_index, term_id))
                tags_html += f'<span class="tag m">\u26a0 {lbl}</span>'
            # Check for contradictions (excluded terms that appear in disease phenotype list)
            for term_id in dc.matched_terms:
                if term_id in excluded_hpo_ids:
                    lbl = _esc(_resolve_label(hpo_index, term_id))
                    tags_html += f'<span class="tag x">\u2717 {lbl}</span>'

        reasoning = _esc(entry.confidence_reasoning)

        cards.append(
            f'<div class="diff-card {conf_cls}{open_cls}">'
            f'<div class="dc-header">'
            f'<div class="dc-num">{i + 1}</div>'
            f'<div><div class="dc-name">{_esc(entry.disease)}</div>'
            f'<div class="dc-id">{_esc(entry.disease_id)}</div></div>'
            f'<div class="dc-score-col">'
            f'<div class="dc-pct">{score_pct}%</div>'
            f'<div class="dc-bar"><div class="dc-fill" style="width:{score_pct}%"></div></div>'
            f'</div>'
            f'<div class="dc-conf-badge">{_esc(entry.confidence)}</div>'
            f'<div class="dc-chevron">\u25bc</div>'
            f'</div>'
            # Expandable body
            f'<div class="dc-body"><div class="dc-body-inner">'
            f'<div class="dc-reasoning">{reasoning}</div>'
            f'<div class="dc-tags">{tags_html}</div>'
            f'</div></div>'
            f'</div>'
        )

    return (
        f'<div class="section-head"><span>\U0001f9ec</span> Differential Diagnosis '
        f'<span class="section-cnt">{len(output.differential)}</span></div>'
        f'<div class="diff-cards">{"".join(cards)}</div>'
    )


def _build_assess_chips(output: AgentOutput, hpo_index: dict) -> str:
    """Render assess/refine chips for missing phenotypes.

    Deduplicates missing_terms from the top 3 DiseaseCandidate entries.
    """
    seen: set[str] = set()
    chips = []

    for dc in output.disease_candidates[:3]:
        for term_id in dc.missing_terms:
            if term_id in seen:
                continue
            seen.add(term_id)
            label = _resolve_label(hpo_index, term_id)
            chips.append(
                f'<span class="assess-chip" data-hpo-id="{_esc(term_id)}" '
                f'data-hpo-label="{_esc(label)}">'
                f'+ {_esc(label)}</span>'
            )
            if len(chips) >= 12:
                break
        if len(chips) >= 12:
            break

    if not chips:
        return ""

    return (
        f'<div class="section-head"><span>\U0001f3f7\ufe0f</span> Assess Missing Phenotypes '
        f'<span class="section-cnt">{len(chips)}</span></div>'
        f'<div class="assess-row">{"".join(chips)}</div>'
    )


def _build_next_steps_and_uncertainty(output: AgentOutput) -> str:
    """Render the two-column layout: next steps (left) + uncertainty & what-would-change (right)."""
    # ── Next steps cards ──
    steps_html = ""
    for step in output.next_best_steps:
        urgency = step.urgency
        type_label = ACTION_TYPE_LABELS.get(step.action_type, step.action_type)
        steps_html += (
            f'<div class="step-crd {urgency}">'
            f'<div>'
            f'<div class="sc-type">{_esc(type_label)}</div>'
            f'<div class="sc-action">{_esc(step.action)}</div>'
            f'<div class="sc-disc">{_esc(step.rationale)}</div>'
            f'</div>'
            f'<div class="sc-num">{step.rank}</div>'
            f'</div>'
        )

    left = ""
    if steps_html:
        left = (
            f'<div>'
            f'<div class="section-head"><span>\U0001f4cb</span> Next Best Steps '
            f'<span class="section-cnt">{len(output.next_best_steps)}</span></div>'
            f'<div class="steps-list-cards">{steps_html}</div>'
            f'</div>'
        )

    # ── Uncertainty grid ──
    uc = output.uncertainty
    known_items = "".join(f'<div class="uc-item">{_esc(k)}</div>' for k in uc.known)
    missing_items = "".join(f'<div class="uc-item">{_esc(m)}</div>' for m in uc.missing)
    amb_items = "".join(f'<div class="uc-item">{_esc(a)}</div>' for a in uc.ambiguous)

    uncertainty_html = (
        f'<div class="section-head"><span>\u2753</span> Uncertainty</div>'
        f'<div class="uncert-cols">'
        f'<div class="uc known"><div class="uc-head">Known</div>{known_items}</div>'
        f'<div class="uc missing"><div class="uc-head">Missing</div>{missing_items}</div>'
        f'<div class="uc amb"><div class="uc-head">Ambiguous</div>{amb_items}</div>'
        f'</div>'
    )

    # ── What Would Change ──
    wwc_html = ""
    if output.what_would_change:
        wwc_items = "".join(
            f'<div class="wwc-item">'
            f'<span class="wwc-bullet">\u25b8</span>'
            f'<span class="wwc-text">{_esc(w)}</span></div>'
            for w in output.what_would_change
        )
        wwc_html = (
            f'<div class="section-head" style="margin-top:10px;">'
            f'<span>\U0001f504</span> What Would Change</div>'
            f'<div class="wwc-list">{wwc_items}</div>'
        )

    right = f'<div>{uncertainty_html}{wwc_html}</div>'

    if left:
        return f'<div class="two-col">{left}{right}</div>'
    return right


# ── Public API ──────────────────────────────────────────────────────────

def format_agent_output(
    output: AgentOutput,
    patient_meta: dict | None = None,
    hpo_index: dict | None = None,
    step_durations: list[dict] | None = None,
) -> str:
    """
    Build the complete HTML dashboard from an AgentOutput.

    Parameters
    ----------
    output : AgentOutput
        The full pipeline output.
    patient_meta : dict, optional
        The patient MongoDB document (for header display).
    hpo_index : dict, optional
        HPO ID → document dict (from load_all).
    step_durations : list[dict], optional
        List of {"name": str, "duration": float} dicts from step timing.

    Returns
    -------
    str
        A single HTML string for cl.Message(content=...).
    """
    if hpo_index is None:
        hpo_index = {}

    sections = [
        _build_step_summary(step_durations),
        _build_patient_header(output, patient_meta, hpo_index),
        _build_stats_row(output),
        _build_red_flags(output),
        _build_differential(output, hpo_index),
        _build_assess_chips(output, hpo_index),
        _build_next_steps_and_uncertainty(output),
    ]

    return "\n".join(s for s in sections if s)


def format_welcome_card(patients: list[dict], hpo_index: dict) -> str:
    """
    Build the branded HTML welcome dashboard.

    Parameters
    ----------
    patients : list[dict]
        List of patient MongoDB documents.
    hpo_index : dict
        HPO index dict for counting.

    Returns
    -------
    str
        HTML string for the welcome message.
    """
    n_patients = len(patients)
    n_hpo = len(hpo_index)

    # Patient selector grid
    patient_cards = ""
    for i, p in enumerate(patients[:15]):
        pid = _esc(p.get("_id", f"patient_{i+1}"))
        age = p.get("age", "?")
        sex = _esc(str(p.get("sex", "?")).upper())
        sex_class = "f" if sex.startswith("F") else "m"
        name = _esc(p.get("diagnosis_name", "Unknown"))
        hpo_count = len(p.get("hpo_terms", []))

        patient_cards += (
            f'<div class="patient-select-card" data-patient-index="{i}">'
            f'<div class="card-patient-avatar {sex_class}" '
            f'style="width:34px;height:34px;font-size:11px;border-radius:8px;">'
            f'{pid[-2:]}</div>'
            f'<div class="ps-info">'
            f'<div class="ps-name">{pid}</div>'
            f'<div class="ps-detail">{age}yo {sex} &mdash; {name}</div>'
            f'<div class="ps-hpo">{hpo_count} HPO terms</div>'
            f'</div></div>'
        )

    return (
        f'<div class="welcome-card">'
        # Hero header
        f'<div class="welcome-header">'
        f'<div class="welcome-logo">\U0001f9ec</div>'
        f'<div>'
        f'<div class="welcome-title">Diagnostic<span style="color:var(--teal)">Copilot</span></div>'
        f'<div class="welcome-subtitle">AI-powered rare disease diagnostic reasoning</div>'
        f'</div>'
        f'<div class="welcome-status">'
        f'<span class="welcome-status-dot"></span>'
        f'{n_patients} patients &middot; {n_hpo} HPO terms loaded'
        f'</div></div>'
        # Instruction tiles
        f'<div class="welcome-instructions">'
        f'<div class="welcome-instr-item">'
        f'<div class="welcome-instr-icon">\U0001f4cb</div>'
        f'<div><div class="welcome-instr-label">Clinical Note</div>'
        f'<div class="welcome-instr-desc">Paste free-text symptoms</div></div></div>'
        f'<div class="welcome-instr-item">'
        f'<div class="welcome-instr-icon">\U0001f3f7\ufe0f</div>'
        f'<div><div class="welcome-instr-label">HPO Terms</div>'
        f'<div class="welcome-instr-desc">Enter HP:XXXXXXX IDs</div></div></div>'
        f'<div class="welcome-instr-item">'
        f'<div class="welcome-instr-icon">\U0001f464</div>'
        f'<div><div class="welcome-instr-label">Test Patient</div>'
        f'<div class="welcome-instr-desc">Select below</div></div></div>'
        f'</div>'
        # Patient selector section
        f'<div class="section-head">\U0001f464 Select a Patient '
        f'<span class="section-cnt">{n_patients} available</span></div>'
        f'<div class="patient-select-grid">{patient_cards}</div>'
        # Disclaimer
        f'<div class="welcome-disclaimer">'
        f'LLMs can make mistakes &mdash; verify clinical decisions independently'
        f'</div></div>'
    )


def format_patient_load_card(patient: dict, hpo_index: dict) -> str:
    """
    Build a teal-bordered card echoing the loaded patient.

    Parameters
    ----------
    patient : dict
        Patient MongoDB document.
    hpo_index : dict
        HPO index dict for label resolution.

    Returns
    -------
    str
        HTML string.
    """
    pid = _esc(patient.get("_id", "??"))
    age = patient.get("age", "?")
    sex = _esc(str(patient.get("sex", "?")).upper())
    sex_class = "f" if sex.startswith("F") else "m"
    name = _esc(patient.get("diagnosis_name", "Unknown"))
    hpo_terms = patient.get("hpo_terms", [])
    hpo_count = len(hpo_terms)

    avatar_text = f"{pid[-2:]}{sex[0]}" if pid else "??"

    chips = ""
    for hid in hpo_terms[:10]:
        label = _esc(_resolve_label(hpo_index, hid))
        chips += (
            f'<span class="hpo-chip">{_esc(hid)}'
            f'<span class="hpo-chip-label">{label}</span></span>'
        )
    if hpo_count > 10:
        chips += f'<span class="hpo-chip">+{hpo_count - 10} more</span>'

    return (
        f'<div class="patient-load-card">'
        f'<div class="pl-top">'
        f'<div class="card-patient-avatar {sex_class}" '
        f'style="width:38px;height:38px;font-size:12px;border-radius:8px;">'
        f'{_esc(avatar_text)}</div>'
        f'<div>'
        f'<div class="pl-action">Loading patient for analysis</div>'
        f'<div class="cp-name">Patient {pid} &mdash; {age}yo {sex}</div>'
        f'<div class="cp-sub">{name} &middot; {hpo_count} HPO terms</div>'
        f'</div></div>'
        f'<div class="cp-chips" style="margin-top:8px;">{chips}</div>'
        f'</div>'
    )
