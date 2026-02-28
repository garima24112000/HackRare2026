"""
core/models.py — Single source of truth for ALL data models across the project.
Every workstream imports from here. No workstream defines its own models.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# HPO Lookup Tool output
# ---------------------------------------------------------------------------

class HPOMatch(BaseModel):
    """Output of HPO Lookup Tool."""
    hpo_id: str                                          # e.g. "HP:0001250"
    label: str                                           # e.g. "Seizures"
    definition: Optional[str] = None
    ic_score: float = 0.0
    parents: list[str] = Field(default_factory=list)
    match_confidence: Literal["high", "medium", "low"] = "medium"
    raw_input: str = ""


# ---------------------------------------------------------------------------
# Disease Match Tool output
# ---------------------------------------------------------------------------

class DiseaseCandidate(BaseModel):
    """Output of Disease Match Tool."""
    rank: int
    disease_id: str
    disease_name: str
    sim_score: float
    matched_terms: list[str] = Field(default_factory=list)
    missing_terms: list[str] = Field(default_factory=list)   # in disease but not patient
    extra_terms: list[str] = Field(default_factory=list)     # in patient but not disease
    coverage_pct: float = 0.0
    excluded_penalty: bool = False


# ---------------------------------------------------------------------------
# Red Flag Detector output
# ---------------------------------------------------------------------------

class RedFlag(BaseModel):
    """Output of Red Flag Detector."""
    flag_label: str
    severity: Literal["URGENT", "WARNING", "WATCH"]
    triggering_terms: list[str]
    recommended_action: str


# ---------------------------------------------------------------------------
# Excluded Phenotype Extractor output
# ---------------------------------------------------------------------------

class ExcludedFinding(BaseModel):
    """Output of Excluded Phenotype Extractor."""
    raw_text: str                                        # negation phrase from the note
    mapped_hpo_term: Optional[str] = None
    mapped_hpo_label: Optional[str] = None
    exclusion_type: Literal["explicit", "soft"]
    confidence: Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Onset & Timing Extractor output
# ---------------------------------------------------------------------------

class TimingProfile(BaseModel):
    """Output of Onset & Timing Extractor."""
    phenotype_ref: str
    phenotype_label: Optional[str] = None
    onset: str                                           # e.g. "at birth", "age 4 months"
    onset_normalized: float                              # age in years, 0.0 = birth
    onset_stage: str                                     # e.g. "Neonatal", "Infantile", etc.
    resolution: Optional[str] = None
    is_ongoing: bool = True
    progression: Literal["stable", "progressive", "improving", "episodic"]
    raw_evidence: str
    confidence: Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Phenotype frequency sub-model (for disease profiles)
# ---------------------------------------------------------------------------

class PhenotypeFrequency(BaseModel):
    """Sub-model for disease profiles."""
    hpo_id: str
    label: str
    frequency: str                                       # e.g. "95-100%"


# ---------------------------------------------------------------------------
# Orphanet / OMIM Fetch output
# ---------------------------------------------------------------------------

class DiseaseProfile(BaseModel):
    """Output of Orphanet/OMIM Fetch."""
    disease_id: str
    disease_name: str
    inheritance: Optional[str] = None
    causal_genes: list[str] = Field(default_factory=list)
    phenotype_freqs: list[PhenotypeFrequency] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reanalysis models
# ---------------------------------------------------------------------------

class ReanalysisReason(BaseModel):
    """Sub-model for reanalysis trigger."""
    reason_type: str
    detail: str
    source: str


class ReanalysisResult(BaseModel):
    """Output of Reanalysis Trigger."""
    score: float                                         # 0 to 1
    recommendation: str
    reasons: list[ReanalysisReason] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Tool call logging
# ---------------------------------------------------------------------------

class ToolCallRecord(BaseModel):
    """For logging tool invocations."""
    tool_name: str
    input_data: dict
    output_data: dict
    timestamp: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Pipeline input
# ---------------------------------------------------------------------------

class PatientInput(BaseModel):
    """Input to the diagnostic pipeline."""
    free_text: Optional[str] = None
    hpo_terms: list[str] = Field(default_factory=list)
    prior_tests: Optional[list[dict]] = None
    family_history: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None


# ---------------------------------------------------------------------------
# Final output sub-models
# ---------------------------------------------------------------------------

class NextStep(BaseModel):
    """Part of final output — recommended next actions."""
    rank: int
    action_type: Literal[
        "order_test",
        "refine_phenotype",
        "genetic_testing",
        "reanalysis",
        "refer_specialist",
        "urgent_escalation",
    ]
    action: str
    rationale: str
    discriminates_between: list[str] = Field(default_factory=list)
    urgency: Literal["urgent", "routine", "low"]
    evidence_source: str


class DifferentialEntry(BaseModel):
    """Part of final output — one disease in the differential."""
    disease: str
    disease_id: str
    confidence: Literal["high", "moderate", "low"]
    confidence_reasoning: str
    supporting_phenotypes: list[str] = Field(default_factory=list)
    contradicting_phenotypes: list[str] = Field(default_factory=list)
    missing_key_phenotypes: list[str] = Field(default_factory=list)


class UncertaintySummary(BaseModel):
    """Part of final output — what is known, missing, and ambiguous."""
    known: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    ambiguous: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Complete pipeline output
# ---------------------------------------------------------------------------

class AgentOutput(BaseModel):
    """The complete pipeline output — assembled by the orchestrator."""
    patient_hpo_observed: list[HPOMatch] = Field(default_factory=list)
    patient_hpo_excluded: list[ExcludedFinding] = Field(default_factory=list)
    timing_profiles: list[TimingProfile] = Field(default_factory=list)
    data_completeness: float = 0.0
    red_flags: list[RedFlag] = Field(default_factory=list)
    differential: list[DifferentialEntry] = Field(default_factory=list)
    next_best_steps: list[NextStep] = Field(default_factory=list)
    reanalysis: Optional[ReanalysisResult] = None
    what_would_change: list[str] = Field(default_factory=list)
    uncertainty: UncertaintySummary = Field(default_factory=UncertaintySummary)
