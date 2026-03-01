"""
chainlit_utils/formatters.py — HTML card builders for the Diagnostic Copilot UI.

Generates two screens:
  Screen 1 (Input/Welcome) — centered patient-grid + HPO input
  Screen 2 (Dashboard)     — fixed 3-column clinical dashboard

Converts AgentOutput + metadata into rich HTML strings for cl.Message(content=...).
All phenotype evidence for differential tags is derived by joining
DifferentialEntry.disease_id → DiseaseCandidate.matched_terms / missing_terms.
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
    """Resolve an HPO ID to its human-readable label."""
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


# ═════════════════════════════════════════════════════════════════════
# SCREEN 1 — WELCOME / INPUT
# ═════════════════════════════════════════════════════════════════════

def format_welcome_card(patients: list[dict], hpo_index: dict) -> str:
    """Build the Screen 1 input card with patient grid + HPO textarea."""

    # Patient buttons (up to 6, arranged in 3-col grid)
    patient_btns = ""
    for i, p in enumerate(patients[:6]):
        pid = _esc(p.get("_id", f"patient_{i+1}"))
        age = p.get("age", "?")
        sex = str(p.get("sex", "?")).upper()
        sex_class = "f" if sex.startswith("F") else "m"
        name = _esc(p.get("diagnosis_name", "Unknown"))
        hpo_count = len(p.get("hpo_terms", []))
        short_id = pid[-2:] if len(pid) >= 2 else pid
        avatar_text = f"{short_id}{sex[0]}"
        sel_cls = " sel" if i == 0 else ""

        patient_btns += (
            f'<div class="pt-btn{sel_cls}" data-patient-index="{i}">'
            f'<div class="pt-btn-top">'
            f'<div class="pt-av {sex_class}">{_esc(avatar_text)}</div>'
            f'<div class="pt-meta">{age}yo {sex[0]} &middot; {hpo_count} HPO</div>'
            f'</div>'
            f'<div class="pt-name">{name}</div>'
            f'</div>'
        )

    return (
        f'<div class="screen-input" id="screen-input">'
        f'<div class="input-logo">Diagnostic<em>Copilot</em></div>'
        f'<div class="input-sub">AI-powered rare disease diagnostic reasoning</div>'
        f'<div class="input-card">'
        f'<div class="inp-section-label">Select a test patient</div>'
        f'<div class="patient-grid">{patient_btns}</div>'
        f'<div class="divider">or enter HPO terms manually</div>'
        f'<div class="hpo-input-wrap">'
        f'<textarea class="hpo-input-field" '
        f'placeholder="HP:0001250, HP:0001263, HP:0001252 — or paste a clinical note…">'
        f'</textarea></div>'
        f'<button class="run-btn">\u25b6 &nbsp; Run Diagnostic Pipeline</button>'
        f'</div></div>'
    )


# ═════════════════════════════════════════════════════════════════════
# SCREEN 2 — DASHBOARD (3-column fixed layout)
# ═════════════════════════════════════════════════════════════════════

def format_agent_output(
    output: AgentOutput,
    patient_meta: dict | None = None,
    hpo_index: dict | None = None,
    step_durations: list[dict] | None = None,
) -> str:
    """Build the complete 3-column dashboard HTML from an AgentOutput."""
    if hpo_index is None:
        hpo_index = {}
    if patient_meta is None:
        patient_meta = {}

    topbar = _build_topbar(output, patient_meta, step_durations)
    statsbar = _build_statsbar(output, hpo_index)
    col1 = _build_col_differential(output, hpo_index)
    col2 = _build_col_middle(output)
    col3 = _build_col_right(output, step_durations)

    return (
        f'<div class="screen-dash" id="screen-dash">'
        f'{topbar}'
        f'{statsbar}'
        f'<div class="dash-grid">'
        f'{col1}{col2}{col3}'
        f'</div>'
        f'</div>'
    )


# ── Topbar ──────────────────────────────────────────────────────────

def _build_topbar(
    output: AgentOutput,
    patient_meta: dict,
    step_durations: list[dict] | None,
) -> str:
    pid = _esc(patient_meta.get("_id", "??"))
    age = patient_meta.get("age", "?")
    sex = str(patient_meta.get("sex", "?")).upper()
    diag = _esc(patient_meta.get("diagnosis_name", ""))
    hpo_count = len(output.patient_hpo_observed)

    total_dur = sum(sd.get("duration", 0) for sd in (step_durations or []))
    dur_text = f"{total_dur:.1f}s" if total_dur > 0 else "—"

    return (
        f'<header class="topbar">'
        f'<div class="tbar-logo">Diagnostic<em>Copilot</em></div>'
        f'<div class="tbar-sep"></div>'
        f'<div class="tbar-patient">Patient {pid} — {age}yo {_esc(sex)}</div>'
        f'<div class="tbar-meta">'
        f'&nbsp;&middot;&nbsp; {diag} &nbsp;&middot;&nbsp; {hpo_count} HPO terms'
        f'</div>'
        f'<div class="tbar-dot"></div>'
        f'<div class="tbar-right">'
        f'<div class="tbar-badge">{dur_text} &middot; complete</div>'
        f'<button class="back-btn">&larr; New Patient</button>'
        f'</div>'
        f'</header>'
    )


# ── Statsbar (5 tiles) ─────────────────────────────────────────────

def _build_statsbar(output: AgentOutput, hpo_index: dict) -> str:
    pct = int(output.data_completeness * 100)
    offset = round(100 - (100 * output.data_completeness))

    hpo_count = len(output.patient_hpo_observed)
    candidates = len(output.disease_candidates)
    flags = len(output.red_flags)

    # HPO chip badges for tile 5
    hpo_chips = ""
    for m in output.patient_hpo_observed[:6]:
        hpo_chips += f'<span class="hpo-stat-chip">{_esc(m.hpo_id)}</span>'

    return (
        f'<div class="statsbar">'
        # Tile 1: Completeness gauge
        f'<div class="stat-tile" style="--cc:var(--teal)">'
        f'<div class="gauge-wrap">'
        f'<svg viewBox="0 0 42 42">'
        f'<circle class="gauge-bg" cx="21" cy="21" r="16"/>'
        f'<circle class="gauge-fill" cx="21" cy="21" r="16" '
        f'style="stroke-dashoffset:{offset}"/>'
        f'</svg>'
        f'<div class="gauge-label">{pct}%</div>'
        f'</div>'
        f'<div><div class="stat-sub">Data</div><div class="stat-sub">Completeness</div></div>'
        f'<div class="stat-accent"></div>'
        f'</div>'
        # Tile 2: HPO terms
        f'<div class="stat-tile" style="--cc:var(--blue)">'
        f'<div class="stat-num">{hpo_count}</div>'
        f'<div class="stat-sub">HPO<br>Terms</div>'
        f'<div class="stat-accent"></div>'
        f'</div>'
        # Tile 3: Candidates
        f'<div class="stat-tile" style="--cc:var(--amber)">'
        f'<div class="stat-num">{candidates}</div>'
        f'<div class="stat-sub">Disease<br>Candidates</div>'
        f'<div class="stat-accent"></div>'
        f'</div>'
        # Tile 4: Red flags
        f'<div class="stat-tile" style="--cc:{"var(--rose)" if flags > 0 else "var(--green)"}">'
        f'<div class="stat-num">{flags}</div>'
        f'<div class="stat-sub">Red<br>Flags</div>'
        f'<div class="stat-accent"></div>'
        f'</div>'
        # Tile 5: HPO chips
        f'<div class="stat-tile" style="--cc:var(--teal); border-right:none">'
        f'<div class="hpo-stat-chips">{hpo_chips}</div>'
        f'<div class="stat-accent"></div>'
        f'</div>'
        f'</div>'
    )


# ── Column 1: Differential Diagnosis ───────────────────────────────

def _build_col_differential(output: AgentOutput, hpo_index: dict) -> str:
    diff_count = len(output.differential) if output.differential else 0
    total_candidates = len(output.disease_candidates)

    # Build lookup: disease_id → DiseaseCandidate
    dc_lookup: dict[str, object] = {}
    for dc in output.disease_candidates:
        dc_lookup[dc.disease_id] = dc

    # Excluded HPO IDs
    excluded_hpo_ids = set()
    for ex in output.patient_hpo_excluded:
        if ex.mapped_hpo_term:
            excluded_hpo_ids.add(ex.mapped_hpo_term)

    # Differential cards
    cards_html = ""
    for i, entry in enumerate(output.differential or []):
        conf_cls = CONF_CSS.get(entry.confidence, "low")
        open_cls = " open" if i == 0 else ""

        dc = dc_lookup.get(entry.disease_id)

        # Coverage percentage
        if dc and dc.coverage_pct > 0:
            score_pct = int(dc.coverage_pct * 100)
        else:
            score_pct = max(10, 100 - (i * 15))

        # Phenotype tags
        tags_html = ""
        if dc:
            for term_id in dc.matched_terms[:8]:
                lbl = _esc(_resolve_label(hpo_index, term_id))
                tags_html += f'<span class="tag s">\u2713 {lbl}</span>'
            for term_id in dc.missing_terms[:6]:
                lbl = _esc(_resolve_label(hpo_index, term_id))
                tags_html += f'<span class="tag m">\u26a0 {lbl}</span>'
            for term_id in dc.matched_terms:
                if term_id in excluded_hpo_ids:
                    lbl = _esc(_resolve_label(hpo_index, term_id))
                    tags_html += f'<span class="tag x">\u2717 {lbl}</span>'

        reasoning = _esc(entry.confidence_reasoning)
        conf_label = _esc(entry.confidence)

        cards_html += (
            f'<div class="da {conf_cls}{open_cls}">'
            f'<div class="da-row">'
            f'<div class="da-num">{i + 1}</div>'
            f'<div>'
            f'<div class="da-name">{_esc(entry.disease)}</div>'
            f'<div class="da-id">{_esc(entry.disease_id)}</div>'
            f'</div>'
            f'<div class="da-badge">{conf_label}</div>'
            f'<div class="da-score-col">'
            f'<div class="da-pct">{score_pct}%</div>'
            f'<div class="da-bar"><div class="da-fill" style="width:{score_pct}%"></div></div>'
            f'</div>'
            f'<div class="da-chev">\u25be</div>'
            f'</div>'
            f'<div class="da-body"><div class="da-inner">'
            f'<div class="da-reason">{reasoning}</div>'
            f'<div class="tags">{tags_html}</div>'
            f'</div></div>'
            f'</div>'
        )

    # Assess chips
    assess_html = _build_assess_chips(output, hpo_index)

    return (
        f'<div class="col">'
        f'<div class="col-header">'
        f'<span style="font-size:12px">\U0001f52c</span>'
        f'<span class="col-title">Differential Diagnosis</span>'
        f'<div class="col-cnt">top {diff_count} of {total_candidates}</div>'
        f'</div>'
        f'<div class="col-body">'
        f'<div class="diff-list">{cards_html}</div>'
        f'{assess_html}'
        f'</div>'
        f'</div>'
    )


def _build_assess_chips(output: AgentOutput, hpo_index: dict) -> str:
    """Render assess/refine chips at the bottom of the differential column."""
    seen: set[str] = set()
    chips = []

    for dc in output.disease_candidates[:3]:
        for term_id in dc.missing_terms:
            if term_id in seen:
                continue
            seen.add(term_id)
            label = _resolve_label(hpo_index, term_id)
            chips.append(
                f'<span class="ac" data-hpo-id="{_esc(term_id)}" '
                f'data-hpo-label="{_esc(label)}">+ {_esc(label)}</span>'
            )
            if len(chips) >= 10:
                break
        if len(chips) >= 10:
            break

    if not chips:
        return ""

    return (
        f'<div class="assess-bar">'
        f'<div class="assess-label">Refine — add missing phenotypes \u2192</div>'
        f'<div class="assess-chips">{"".join(chips)}</div>'
        f'</div>'
    )


# ── Column 2: Next Steps + Uncertainty ─────────────────────────────

def _build_col_middle(output: AgentOutput) -> str:
    # Next steps cards
    steps_html = ""
    for i, step in enumerate(output.next_best_steps):
        urgency = step.urgency
        type_label = ACTION_TYPE_LABELS.get(step.action_type, step.action_type)

        steps_html += (
            f'<div class="step-card {urgency}">'
            f'<div>'
            f'<div class="sc-type">{_esc(type_label)}</div>'
            f'<div class="sc-action">{_esc(step.action)}</div>'
            f'<div class="sc-disc">{_esc(step.rationale)}</div>'
            f'</div>'
            f'<div class="sc-n">{step.rank}</div>'
            f'</div>'
        )

    step_count = len(output.next_best_steps)

    # Red flags (rendered inside mid column if any)
    red_flags_html = ""
    if output.red_flags:
        rf_items = ""
        for rf in output.red_flags:
            sev = _esc(rf.severity)
            label = _esc(rf.flag_label)
            action = _esc(rf.recommended_action)
            rf_items += f'<div class="rf-item"><strong>{sev}</strong> — {label}: {action}</div>'
        red_flags_html = (
            f'<div class="red-flag-banner">'
            f'<div class="rf-title">\U0001f6a8 Red Flags</div>'
            f'{rf_items}</div>'
        )

    # Uncertainty
    uc = output.uncertainty
    known_items = "".join(f'<div class="uc-item">{_esc(k)}</div>' for k in uc.known)
    missing_items = "".join(f'<div class="uc-item">{_esc(m)}</div>' for m in uc.missing)
    amb_items = "".join(f'<div class="uc-item">{_esc(a)}</div>' for a in uc.ambiguous)

    return (
        f'<div class="col">'
        f'<div class="col-header">'
        f'<span style="font-size:12px">\U0001f3af</span>'
        f'<span class="col-title">Next Steps</span>'
        f'<div class="col-cnt">{step_count} actions</div>'
        f'</div>'
        f'<div class="mid-col-body">'
        f'{red_flags_html}'
        f'<div class="steps-list">{steps_html}</div>'
        f'<hr class="mid-sep">'
        f'<div class="col-header" style="border-top:none">'
        f'<span style="font-size:12px">\u2753</span>'
        f'<span class="col-title">Uncertainty Summary</span>'
        f'</div>'
        f'<div class="uncert-wrap">'
        f'<div class="uc-col k"><div class="uc-head">\u2713 Known</div>{known_items}</div>'
        f'<div class="uc-col x"><div class="uc-head">\u2717 Missing</div>{missing_items}</div>'
        f'<div class="uc-col a"><div class="uc-head">\u26a1 Ambiguous</div>{amb_items}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


# ── Column 3: Pipeline + What Would Change ─────────────────────────

def _build_col_right(
    output: AgentOutput,
    step_durations: list[dict] | None,
) -> str:
    # Pipeline rows (all done since we render after pipeline completes)
    pipeline_html = ""
    pipeline_steps = step_durations or []
    for sd in pipeline_steps:
        name = _esc(sd.get("name", ""))
        dur = sd.get("duration", 0)
        pipeline_html += (
            f'<div class="pl-row">'
            f'<div class="pl-node done">\u2713</div>'
            f'<div class="pl-label done">{name}</div>'
            f'<div class="pl-ms">{dur:.1f}s</div>'
            f'</div>'
        )

    # If no step durations, show default pipeline stages
    if not pipeline_html:
        default_steps = [
            "Red Flag Check", "HPO Mapping", "Disease Matching",
            "Clinical Reasoning", "Final Output",
        ]
        for name in default_steps:
            pipeline_html += (
                f'<div class="pl-row">'
                f'<div class="pl-node done">\u2713</div>'
                f'<div class="pl-label done">{_esc(name)}</div>'
                f'<div class="pl-ms">—</div>'
                f'</div>'
            )

    # What would change
    wwc_html = ""
    for w in (output.what_would_change or []):
        wwc_html += (
            f'<div class="wwc-item">'
            f'<span class="wwc-dot">\u203a</span>'
            f'<span class="wwc-text">{_esc(w)}</span>'
            f'</div>'
        )

    pip_status = "complete"

    return (
        f'<div class="col">'
        f'<div class="col-header">'
        f'<span style="font-size:12px">\u2699\ufe0f</span>'
        f'<span class="col-title">Pipeline</span>'
        f'<div class="col-cnt complete">{pip_status}</div>'
        f'</div>'
        f'<div class="col-body">'
        f'<div class="pipeline-list">{pipeline_html}</div>'
        f'<div class="col-header" style="border-top: 1px solid var(--b1)">'
        f'<span style="font-size:12px">\U0001f504</span>'
        f'<span class="col-title">What Would Change This</span>'
        f'</div>'
        f'<div class="wwc-list">{wwc_html}</div>'
        f'</div>'
        f'</div>'
    )


# ═════════════════════════════════════════════════════════════════════
# PATIENT LOAD ECHO CARD (shown during pipeline run)
# ═════════════════════════════════════════════════════════════════════

def format_patient_load_card(patient: dict, hpo_index: dict) -> str:
    """Build a loading card that fills the viewport while pipeline runs."""
    pid = _esc(patient.get("_id", "??"))
    age = patient.get("age", "?")
    sex = _esc(str(patient.get("sex", "?")).upper())
    sex_class = "f" if sex.startswith("F") else "m"
    name = _esc(patient.get("diagnosis_name", "Unknown"))
    hpo_terms = patient.get("hpo_terms", [])
    hpo_count = len(hpo_terms)

    avatar_text = f"{pid[-2:]}{sex[0]}" if pid else "??"

    chips = ""
    for hid in hpo_terms[:8]:
        label = _esc(_resolve_label(hpo_index, hid))
        chips += (
            f'<span class="hpo-chip">{_esc(hid)}'
            f'<span class="hpo-chip-label">{label}</span></span>'
        )
    if hpo_count > 8:
        chips += f'<span class="hpo-chip">+{hpo_count - 8} more</span>'

    return (
        f'<div class="patient-load-card">'
        f'<div class="loading-spinner"></div>'
        f'<div class="pl-inner">'
        f'<div class="pl-top">'
        f'<div class="card-patient-avatar {sex_class}" '
        f'style="width:38px;height:38px;font-size:12px;border-radius:8px;">'
        f'{_esc(avatar_text)}</div>'
        f'<div>'
        f'<div class="pl-action">Running diagnostic pipeline\u2026</div>'
        f'<div class="cp-name">Patient {pid} — {age}yo {sex}</div>'
        f'<div class="cp-sub">{name} &middot; {hpo_count} HPO terms</div>'
        f'</div></div>'
        f'<div class="cp-chips" style="margin-top:8px;">{chips}</div>'
        f'</div></div>'
    )
