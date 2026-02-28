"""
tests/test_ws2.py — Unit tests for WS2: Agent Pipeline + LLM Extraction Tools.

Tests are designed to run WITHOUT Azure credentials or WS1 implementations.
All LLM calls are monkeypatched with mock responses.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Model imports
# ---------------------------------------------------------------------------
from core.models import (
    AgentOutput,
    DifferentialEntry,
    DiseaseCandidate,
    DiseaseProfile,
    ExcludedFinding,
    HPOMatch,
    NextStep,
    PatientInput,
    RedFlag,
    ReanalysisResult,
    TimingProfile,
    UncertaintySummary,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. PipelineState tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPipelineState:
    def test_defaults(self):
        from agent.state import PipelineState

        state = PipelineState()
        assert state.session_id == ""
        assert state.hpo_matches == []
        assert state.excluded == []
        assert state.timing == []
        assert state.diseases == []
        assert state.profiles == []
        assert state.red_flags == []
        assert state.reanalysis is None
        assert state.data_completeness == 0.0
        assert state.tool_log == []

    def test_snapshot(self):
        from agent.state import PipelineState

        state = PipelineState(session_id="test-123")
        state.hpo_matches = [
            HPOMatch(hpo_id="HP:0001250", label="Seizures")
        ]
        snap = state.snapshot()
        assert snap["session_id"] == "test-123"
        assert len(snap["hpo_matches"]) == 1
        assert snap["hpo_matches"][0]["hpo_id"] == "HP:0001250"


# ═══════════════════════════════════════════════════════════════════════════
# 2. LLM Client tests
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractJson:
    def test_plain_json(self):
        from agent.llm_client import extract_json

        result = extract_json('[{"a": 1}]')
        assert result == [{"a": 1}]

    def test_markdown_fenced(self):
        from agent.llm_client import extract_json

        result = extract_json('```json\n[{"a": 1}]\n```')
        assert result == [{"a": 1}]

    def test_json_with_preamble(self):
        from agent.llm_client import extract_json

        result = extract_json('Here is the output:\n[{"a": 1}]\nDone.')
        assert result == [{"a": 1}]

    def test_nested_object(self):
        from agent.llm_client import extract_json

        result = extract_json('{"key": {"nested": true}}')
        assert result == {"key": {"nested": True}}

    def test_invalid_raises(self):
        from agent.llm_client import extract_json

        with pytest.raises(json.JSONDecodeError):
            extract_json("no json here at all")


# ═══════════════════════════════════════════════════════════════════════════
# 3. Excluded Extract tests
# ═══════════════════════════════════════════════════════════════════════════


MOCK_EXCLUDED_LLM_RESPONSE = json.dumps([
    {
        "raw_text": "No seizures have ever been reported",
        "finding": "Seizures",
        "exclusion_type": "explicit",
        "confidence": "high",
    },
    {
        "raw_text": "Hearing was tested and confirmed normal",
        "finding": "Hearing impairment",
        "exclusion_type": "explicit",
        "confidence": "high",
    },
    {
        "raw_text": "Deep tendon reflexes are absent",
        "finding": "Absent deep tendon reflexes",
        "exclusion_type": "explicit",
        "confidence": "high",
    },
])


class TestExcludedExtract:
    @patch("tools.excluded_extract.call_llm", return_value=MOCK_EXCLUDED_LLM_RESPONSE)
    def test_basic_extraction(self, mock_llm):
        from tools.excluded_extract import run

        synonym_index = {
            "seizures": "HP:0001250",
            "hearing impairment": "HP:0000365",
            "absent deep tendon reflexes": "HP:0001284",
        }

        result = run(
            "Patient is a 5-year-old male. No seizures have ever been reported. "
            "Hearing was tested and confirmed normal. Deep tendon reflexes are absent. "
            "No family history of cardiac disease.",
            synonym_index,
        )

        assert len(result) == 3
        assert all(isinstance(r, ExcludedFinding) for r in result)

        seizure = next(r for r in result if "seizure" in r.raw_text.lower())
        assert seizure.mapped_hpo_term == "HP:0001250"
        assert seizure.exclusion_type == "explicit"
        assert seizure.confidence == "high"

    @patch("tools.excluded_extract.call_llm", return_value="[]")
    def test_no_negations(self, mock_llm):
        from tools.excluded_extract import run

        result = run("Patient presents with fever and cough.", {})
        assert result == []

    def test_empty_note(self):
        from tools.excluded_extract import run

        result = run("", {})
        assert result == []

    @patch("tools.excluded_extract.call_llm", return_value="not valid json at all")
    def test_invalid_json_returns_empty(self, mock_llm):
        from tools.excluded_extract import run

        result = run("Some note text.", {})
        assert result == []

    @patch("tools.excluded_extract.call_llm", return_value=MOCK_EXCLUDED_LLM_RESPONSE)
    def test_fuzzy_matching(self, mock_llm):
        from tools.excluded_extract import run

        # Synonym index uses slightly different names → fuzzy should match
        synonym_index = {
            "seizure": "HP:0001250",
            "hearing loss": "HP:0000365",
        }

        result = run("Test note.", synonym_index)
        # "Seizures" should fuzzy match "seizure"
        seizure = next((r for r in result if "seizure" in r.raw_text.lower()), None)
        assert seizure is not None
        assert seizure.mapped_hpo_term == "HP:0001250"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Timing Extract tests
# ═══════════════════════════════════════════════════════════════════════════


MOCK_TIMING_LLM_RESPONSE = json.dumps([
    {
        "phenotype_ref": "Hypotonia",
        "onset": "since birth",
        "onset_normalized": 0.0,
        "resolution": None,
        "is_ongoing": True,
        "progression": "stable",
        "raw_evidence": "Hypotonia was noted since birth.",
        "confidence": "high",
    },
    {
        "phenotype_ref": "Seizures",
        "onset": "at 4 months of age",
        "onset_normalized": 0.33,
        "resolution": None,
        "is_ongoing": True,
        "progression": "stable",
        "raw_evidence": "Seizures began at 4 months of age.",
        "confidence": "high",
    },
    {
        "phenotype_ref": "Speech delay",
        "onset": "18-month checkup",
        "onset_normalized": 1.5,
        "resolution": None,
        "is_ongoing": True,
        "progression": "stable",
        "raw_evidence": "Speech delay was identified at the 18-month checkup.",
        "confidence": "high",
    },
    {
        "phenotype_ref": "Gait disturbance",
        "onset": "at 28 months",
        "onset_normalized": 2.33,
        "resolution": None,
        "is_ongoing": True,
        "progression": "progressive",
        "raw_evidence": "Walking was achieved at 28 months but gait has progressively worsened.",
        "confidence": "high",
    },
])


class TestTimingExtract:
    @patch("tools.timing_extract.call_llm", return_value=MOCK_TIMING_LLM_RESPONSE)
    def test_basic_extraction(self, mock_llm):
        from tools.timing_extract import run

        result = run(
            "Hypotonia was noted since birth. Seizures began at 4 months of age. "
            "Speech delay was identified at the 18-month checkup. Walking was "
            "achieved at 28 months but gait has progressively worsened.",
            ["Hypotonia", "Seizures", "Speech delay", "Gait disturbance"],
        )

        assert len(result) == 4
        assert all(isinstance(r, TimingProfile) for r in result)

        hypo = next(r for r in result if r.phenotype_ref == "Hypotonia")
        assert hypo.onset_normalized == 0.0
        assert hypo.onset_stage == "Congenital/Neonatal"

        seizure = next(r for r in result if r.phenotype_ref == "Seizures")
        assert seizure.onset_normalized == pytest.approx(0.33, abs=0.1)
        assert seizure.onset_stage == "Infantile"

        speech = next(r for r in result if r.phenotype_ref == "Speech delay")
        assert speech.onset_stage == "Childhood"

        gait = next(r for r in result if r.phenotype_ref == "Gait disturbance")
        assert gait.progression == "progressive"
        assert gait.onset_stage == "Childhood"

    def test_empty_inputs(self):
        from tools.timing_extract import run

        assert run("", ["Seizures"]) == []
        assert run("Some text", []) == []

    @patch("tools.timing_extract.call_llm", return_value="[]")
    def test_no_timing_found(self, mock_llm):
        from tools.timing_extract import run

        result = run("No timing information in this note.", ["Seizures"])
        assert result == []


class TestOnsetStageNormalisation:
    def test_boundaries(self):
        from tools.timing_extract import _normalise_onset_stage

        assert _normalise_onset_stage(0.0) == "Congenital/Neonatal"
        assert _normalise_onset_stage(-0.1) == "Congenital/Neonatal"
        assert _normalise_onset_stage(0.5) == "Infantile"
        assert _normalise_onset_stage(1.0) == "Infantile"
        assert _normalise_onset_stage(1.1) == "Childhood"
        assert _normalise_onset_stage(5.0) == "Childhood"
        assert _normalise_onset_stage(5.1) == "Juvenile"
        assert _normalise_onset_stage(15.0) == "Juvenile"
        assert _normalise_onset_stage(15.1) == "Adult"
        assert _normalise_onset_stage(30.0) == "Adult"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Data Completeness tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDataCompleteness:
    def test_all_data_present(self):
        from agent.pipeline import _compute_completeness
        from agent.state import PipelineState

        state = PipelineState()
        state.hpo_matches = [
            HPOMatch(hpo_id=f"HP:{i:07d}", label=f"term{i}") for i in range(5)
        ]
        state.timing = [
            TimingProfile(
                phenotype_ref="t", onset="birth", onset_normalized=0.0,
                onset_stage="Neonatal", progression="stable",
                raw_evidence="e", confidence="high",
            )
        ] * 3
        state.excluded = [
            ExcludedFinding(raw_text="no X", exclusion_type="explicit", confidence="high")
        ]

        patient = PatientInput(
            hpo_terms=["HP:0000001"],
            prior_tests=[{"test": "exome"}],
            family_history="no known history",
        )

        score = _compute_completeness(state, patient)
        # hpo: 0.30*1.0=0.30, timing: 0.20*(3/5)=0.12, exclusion: 0.15*1.0=0.15,
        # test: 0.20*1.0=0.20, family: 0.15*1.0=0.15 → 0.92
        assert 0.85 <= score <= 1.0

    def test_no_data(self):
        from agent.pipeline import _compute_completeness
        from agent.state import PipelineState

        state = PipelineState()
        patient = PatientInput()
        score = _compute_completeness(state, patient)
        assert score == 0.0

    def test_sparse_data(self):
        from agent.pipeline import _compute_completeness
        from agent.state import PipelineState

        state = PipelineState()
        state.hpo_matches = [
            HPOMatch(hpo_id="HP:0001250", label="Seizures")
        ]
        patient = PatientInput(hpo_terms=["HP:0001250"])

        score = _compute_completeness(state, patient)
        # hpo: 0.30*0.5=0.15, rest 0 → 0.15
        assert score == pytest.approx(0.15, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Pipeline integration tests (all WS1 stubs, mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════


MOCK_FINAL_REASONING_RESPONSE = json.dumps({
    "differential": [
        {
            "disease": "Test Disease",
            "disease_id": "OMIM:100000",
            "confidence": "low",
            "confidence_reasoning": "Limited phenotype data available.",
            "supporting_phenotypes": [],
            "contradicting_phenotypes": [],
            "missing_key_phenotypes": ["Intellectual disability"],
        }
    ],
    "next_best_steps": [
        {
            "rank": 1,
            "action_type": "refine_phenotype",
            "action": "Provide additional phenotype details",
            "rationale": "Insufficient data for confident diagnosis.",
            "discriminates_between": ["Test Disease"],
            "urgency": "routine",
            "evidence_source": "pipeline",
        }
    ],
    "what_would_change": [
        "If intellectual disability is confirmed, confidence in Test Disease increases."
    ],
    "uncertainty": {
        "known": ["HPO terms identified"],
        "missing": ["Genetic testing not performed"],
        "ambiguous": [],
    },
})


class TestPipeline:
    """Integration tests for the full pipeline with WS1 stubs and mocked LLM."""

    def _make_mock_session_mgr(self):
        mgr = MagicMock(spec=[
            "create_session", "log_tool_call", "get_tool_log",
            "set_context", "get_context", "set_output",
        ])
        # Make all methods no-ops (don't raise NotImplementedError)
        return mgr

    @patch("agent.pipeline.call_llm", return_value=MOCK_FINAL_REASONING_RESPONSE)
    def test_hpo_only_degraded(self, mock_llm):
        """Pipeline with HPO terms only, all WS1 stubs → degraded but valid output."""
        from agent.pipeline import run_pipeline

        patient = PatientInput(hpo_terms=["HP:0001250", "HP:0001252"])
        data = {"ontology": None, "synonym_index": {}}
        mgr = self._make_mock_session_mgr()

        output = asyncio.run(run_pipeline(patient, data, mgr))

        assert isinstance(output, AgentOutput)
        # With WS1 stubs returning [], most fields will be empty
        # but the pipeline should not crash
        assert output.data_completeness >= 0.0
        assert isinstance(output.differential, list)
        assert isinstance(output.next_best_steps, list)
        assert isinstance(output.uncertainty, UncertaintySummary)

    @patch("agent.pipeline.call_llm", return_value=MOCK_FINAL_REASONING_RESPONSE)
    @patch("tools.excluded_extract.call_llm", return_value=MOCK_EXCLUDED_LLM_RESPONSE)
    @patch("tools.timing_extract.call_llm", return_value=MOCK_TIMING_LLM_RESPONSE)
    def test_free_text_pipeline(self, mock_timing, mock_excluded, mock_llm):
        """Pipeline with free text triggers extraction tools."""
        from agent.pipeline import run_pipeline

        patient = PatientInput(
            free_text=(
                "No seizures have ever been reported. Hypotonia was noted since birth. "
                "Hearing was tested and confirmed normal."
            ),
        )
        data = {"ontology": None, "synonym_index": {}}
        mgr = self._make_mock_session_mgr()

        output = asyncio.run(run_pipeline(patient, data, mgr))

        assert isinstance(output, AgentOutput)
        # Excluded findings should be populated (LLM was mocked)
        assert len(output.patient_hpo_excluded) == 3
        assert all(isinstance(e, ExcludedFinding) for e in output.patient_hpo_excluded)

    @patch("agent.pipeline.call_llm", return_value=MOCK_FINAL_REASONING_RESPONSE)
    def test_empty_input(self, mock_llm):
        """Pipeline with empty input should still return valid output."""
        from agent.pipeline import run_pipeline

        patient = PatientInput()
        data = {"ontology": None, "synonym_index": {}}
        mgr = self._make_mock_session_mgr()

        output = asyncio.run(run_pipeline(patient, data, mgr))

        assert isinstance(output, AgentOutput)
        assert output.data_completeness == 0.0

    @patch("tools.red_flag.run")
    def test_urgent_red_flag_early_exit(self, mock_rf):
        """URGENT red flag → pipeline returns early without further analysis."""
        from agent.pipeline import run_pipeline

        mock_rf.return_value = [
            RedFlag(
                flag_label="Status epilepticus",
                severity="URGENT",
                triggering_terms=["HP:0002133"],
                recommended_action="Immediate neurology consultation",
            )
        ]

        patient = PatientInput(hpo_terms=["HP:0002133"])
        data = {"ontology": None, "synonym_index": {}}
        mgr = self._make_mock_session_mgr()

        output = asyncio.run(run_pipeline(patient, data, mgr))

        assert isinstance(output, AgentOutput)
        assert len(output.red_flags) == 1
        assert output.red_flags[0].severity == "URGENT"
        # Should have returned early — no differential or next steps
        assert output.differential == []
        assert output.patient_hpo_observed == []

    @patch("agent.pipeline.call_llm", return_value="totally broken json }{{{")
    def test_llm_failure_degraded_output(self, mock_llm):
        """If LLM returns garbage, pipeline produces degraded but valid output."""
        from agent.pipeline import run_pipeline

        patient = PatientInput(hpo_terms=["HP:0001250"])
        data = {"ontology": None, "synonym_index": {}}
        mgr = self._make_mock_session_mgr()

        output = asyncio.run(run_pipeline(patient, data, mgr))

        assert isinstance(output, AgentOutput)
        # Should still be a valid AgentOutput (degraded)
        assert isinstance(output.uncertainty, UncertaintySummary)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Free-text splitting test
# ═══════════════════════════════════════════════════════════════════════════


class TestFreeTextSplitting:
    def test_basic_split(self):
        from agent.pipeline import _split_free_text

        result = _split_free_text("seizures, hypotonia, and speech delay")
        assert len(result) >= 3
        assert any("seizure" in r.lower() for r in result)
        assert any("hypotonia" in r.lower() for r in result)

    def test_empty_string(self):
        from agent.pipeline import _split_free_text

        assert _split_free_text("") == []


# ═══════════════════════════════════════════════════════════════════════════
# 8. Degraded output builder test
# ═══════════════════════════════════════════════════════════════════════════


class TestDegradedOutput:
    def test_builds_valid_structure(self):
        from agent.pipeline import _build_degraded_output
        from agent.state import PipelineState

        state = PipelineState()
        state.diseases = [
            DiseaseCandidate(
                rank=1,
                disease_id="OMIM:100000",
                disease_name="Test Disease",
                sim_score=0.75,
                matched_terms=["Seizures"],
                missing_terms=["Hypotonia"],
            )
        ]

        result = _build_degraded_output(state)

        assert "differential" in result
        assert len(result["differential"]) == 1
        assert result["differential"][0]["disease"] == "Test Disease"
        assert "next_best_steps" in result
        assert result["next_best_steps"][0]["action_type"] == "refine_phenotype"
