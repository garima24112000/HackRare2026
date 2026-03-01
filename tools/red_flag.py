"""
tools/red_flag.py — Detect urgent / concerning phenotype combinations.

Owner: WS1 (Data & Retrieval)

Deterministic, auditable rule engine. NO LLM calls — medical urgency
detection must be reproducible and explainable.
"""

from __future__ import annotations

from core.models import RedFlag


# ---------------------------------------------------------------------------
# Urgent subtree roots (hardcoded — curated safety list)
# ---------------------------------------------------------------------------
_URGENT_ROOTS: dict[str, tuple[str, str, str]] = {
    # HP ID → (label, severity, recommended_action)
    "HP:0001695": ("Cardiac arrest", "URGENT",
                   "Immediate cardiac monitoring and resuscitation readiness"),
    "HP:0002098": ("Respiratory distress", "URGENT",
                   "Assess airway and breathing; consider respiratory support"),
    "HP:0002133": ("Status epilepticus", "URGENT",
                   "Urgent neurology consult; initiate seizure protocol"),
    "HP:0001259": ("Coma", "URGENT",
                   "Immediate neurological assessment and ICU evaluation"),
    "HP:0001279": ("Syncope", "WARNING",
                   "Cardiac and neurological workup recommended"),
    "HP:0006579": ("Neonatal onset", "WARNING",
                   "Neonatal onset detected — consider early metabolic and genetic screening"),
    "HP:0003812": ("Clinical deterioration", "WARNING",
                   "Monitor for progressive decline; reassess diagnosis"),
}

# ---------------------------------------------------------------------------
# Combination rules
# ---------------------------------------------------------------------------
_COMBO_CARDIOVASCULAR = "HP:0001626"  # Abnormality of the cardiovascular system
_COMBO_MUSCULATURE = "HP:0003011"     # Abnormality of the musculature
_COMBO_SEIZURES = "HP:0001250"        # Seizures
_COMBO_NEURODEV = "HP:0012759"        # Neurodevelopmental abnormality
_COMBO_METABOLISM = "HP:0001939"      # Abnormality of metabolism


def run(patient_hpo_ids: list[str], ontology) -> list[RedFlag]:
    """
    Screen for red-flag phenotype combinations that warrant urgent action.

    Parameters
    ----------
    patient_hpo_ids : list[str]
        HPO IDs observed in the patient.
    ontology : pronto.Ontology
        The parsed ``hp.obo`` ontology object (``data["ontology"]``).

    Returns
    -------
    list[RedFlag]
        Each flag includes severity, triggering terms, and a recommended action.
    """
    flags: list[RedFlag] = []
    seen_labels: set[str] = set()  # avoid duplicate flags

    # Pre-collect all ancestor IDs for each patient term
    term_ancestors: dict[str, set[str]] = {}
    all_ancestors: set[str] = set()

    for hpo_id in patient_hpo_ids:
        try:
            ancestors = set()
            for parent in ontology[hpo_id].superclasses():
                ancestors.add(parent.id)
            term_ancestors[hpo_id] = ancestors
            all_ancestors.update(ancestors)
        except Exception:
            term_ancestors[hpo_id] = set()

    # ------------------------------------------------------------------
    # Check each patient HPO term against urgent subtree roots
    # ------------------------------------------------------------------
    for hpo_id in patient_hpo_ids:
        ancestors = term_ancestors.get(hpo_id, set())

        for root_id, (label, severity, action) in _URGENT_ROOTS.items():
            if root_id in ancestors or hpo_id == root_id:
                if label not in seen_labels:
                    # Find all triggering terms for this root
                    triggering = [
                        t for t in patient_hpo_ids
                        if root_id in term_ancestors.get(t, set()) or t == root_id
                    ]
                    flags.append(RedFlag(
                        flag_label=label,
                        severity=severity,
                        triggering_terms=triggering,
                        recommended_action=action,
                    ))
                    seen_labels.add(label)

    # ------------------------------------------------------------------
    # Combination rules
    # ------------------------------------------------------------------
    has_cardiovascular = any(
        _COMBO_CARDIOVASCULAR in term_ancestors.get(t, set())
        for t in patient_hpo_ids
    )
    has_musculature = any(
        _COMBO_MUSCULATURE in term_ancestors.get(t, set())
        for t in patient_hpo_ids
    )
    has_seizures = any(
        _COMBO_SEIZURES in term_ancestors.get(t, set()) or t == _COMBO_SEIZURES
        for t in patient_hpo_ids
    )
    has_neurodev = any(
        _COMBO_NEURODEV in term_ancestors.get(t, set())
        for t in patient_hpo_ids
    )
    has_metabolism = any(
        _COMBO_METABOLISM in term_ancestors.get(t, set())
        for t in patient_hpo_ids
    )

    # Rule 1: Cardiovascular + Musculature → metabolic cardiomyopathy
    if has_cardiovascular and has_musculature:
        label = "Possible metabolic cardiomyopathy"
        if label not in seen_labels:
            flags.append(RedFlag(
                flag_label=label,
                severity="WARNING",
                triggering_terms=[
                    t for t in patient_hpo_ids
                    if _COMBO_CARDIOVASCULAR in term_ancestors.get(t, set())
                    or _COMBO_MUSCULATURE in term_ancestors.get(t, set())
                ],
                recommended_action="Consider metabolic cardiomyopathy workup",
            ))
            seen_labels.add(label)

    # Rule 2: Seizures + Neurodev + Metabolism → urgent metabolic screening
    if has_seizures and has_neurodev and has_metabolism:
        label = "Possible metabolic epilepsy"
        if label not in seen_labels:
            flags.append(RedFlag(
                flag_label=label,
                severity="WARNING",
                triggering_terms=[
                    t for t in patient_hpo_ids
                    if any(
                        cat in term_ancestors.get(t, set())
                        for cat in [_COMBO_SEIZURES, _COMBO_NEURODEV, _COMBO_METABOLISM]
                    ) or t == _COMBO_SEIZURES
                ],
                recommended_action="Consider urgent metabolic screening",
            ))
            seen_labels.add(label)

    return flags
