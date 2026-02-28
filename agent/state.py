"""
agent/state.py — Pipeline state dataclass.

Accumulates results as each step of the pipeline executes.  This is the
single object threaded through ``run_pipeline`` — every tool step reads
what it needs and writes its output back.

Owner: WS2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.models import (
    DiseaseCandidate,
    DiseaseProfile,
    ExcludedFinding,
    HPOMatch,
    ReanalysisResult,
    RedFlag,
    TimingProfile,
)


@dataclass
class PipelineState:
    """Mutable accumulator for all intermediate and final pipeline data."""

    # ── Identity & raw input ────────────────────────────────────────────
    session_id: str = ""
    # PatientInput is stored here as a dict so it survives JSON round-trips
    # cleanly; the typed PatientInput is always available from the caller.
    patient_input_raw: dict = field(default_factory=dict)

    # ── Step outputs ────────────────────────────────────────────────────
    hpo_matches: list[HPOMatch] = field(default_factory=list)          # Step 2
    excluded: list[ExcludedFinding] = field(default_factory=list)      # Step 4
    timing: list[TimingProfile] = field(default_factory=list)          # Step 4
    diseases: list[DiseaseCandidate] = field(default_factory=list)     # Step 3 / 4b
    profiles: list[DiseaseProfile] = field(default_factory=list)       # Step 5
    red_flags: list[RedFlag] = field(default_factory=list)             # Step 1
    reanalysis: Optional[ReanalysisResult] = None                      # Future hook
    data_completeness: float = 0.0                                     # Step 6

    # ── Logging ─────────────────────────────────────────────────────────
    tool_log: list[dict] = field(default_factory=list)

    # ── Helpers ─────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Return a plain-dict snapshot suitable for JSON serialisation."""
        return {
            "session_id": self.session_id,
            "hpo_matches": [m.model_dump() for m in self.hpo_matches],
            "excluded": [e.model_dump() for e in self.excluded],
            "timing": [t.model_dump() for t in self.timing],
            "diseases": [d.model_dump() for d in self.diseases],
            "profiles": [p.model_dump() for p in self.profiles],
            "red_flags": [r.model_dump() for r in self.red_flags],
            "reanalysis": self.reanalysis.model_dump() if self.reanalysis else None,
            "data_completeness": self.data_completeness,
        }
